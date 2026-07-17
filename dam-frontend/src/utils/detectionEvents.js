// dai
// Authenticated SSE reader for the camera detection list. Native EventSource
// cannot send the JWT Authorization header used by this application.

export function createSseParser(onEvent) {
  let buffer = ''

  function push(chunk) {
    buffer += chunk
    while (true) {
      const separator = buffer.match(/\r?\n\r?\n/)
      if (!separator || separator.index == null) break
      const block = buffer.slice(0, separator.index)
      buffer = buffer.slice(separator.index + separator[0].length)
      if (!block || block.startsWith(':')) continue

      let event = 'message'
      let id = ''
      const data = []
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('event:')) event = line.slice(6).trimStart()
        else if (line.startsWith('id:')) id = line.slice(3).trimStart()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      if (data.length > 0) onEvent({ event, id, data: data.join('\n') })
    }
  }

  return { push }
}

export function subscribeDetectionEvents(cameraId, handlers = {}) {
  let stopped = false
  let controller = null
  let retryTimer = null
  let resolveRetry = null

  const waitForRetry = (delay) => new Promise((resolve) => {
    resolveRetry = resolve
    retryTimer = setTimeout(() => {
      retryTimer = null
      resolveRetry = null
      resolve()
    }, delay)
  })

  async function connectLoop() {
    let retryDelay = 500
    while (!stopped) {
      controller = new AbortController()
      try {
        const token = globalThis.localStorage?.getItem('token')
        const headers = token ? { Authorization: `Bearer ${token}` } : {}
        const response = await fetch(
          `/api/v1/camera/${encodeURIComponent(cameraId)}/detections/events`,
          { headers, signal: controller.signal, cache: 'no-store' },
        )
        if (!response.ok || !response.body) {
          const error = new Error(`检测事件连接失败 (${response.status})`)
          error.status = response.status
          throw error
        }

        handlers.onState?.('connected')
        retryDelay = 500
        const parser = createSseParser((event) => {
          if (event.event !== 'detection') return
          try {
            handlers.onDetection?.(JSON.parse(event.data))
          } catch (error) {
            handlers.onError?.(error)
          }
        })
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        while (!stopped) {
          const { value, done } = await reader.read()
          if (done) break
          parser.push(decoder.decode(value, { stream: true }))
        }
      } catch (error) {
        if (stopped || error?.name === 'AbortError') break
        handlers.onState?.('reconnecting')
        handlers.onError?.(error)
      }

      if (!stopped) {
        await waitForRetry(retryDelay)
        retryDelay = Math.min(retryDelay * 2, 5000)
      }
    }
  }

  connectLoop()
  return () => {
    stopped = true
    controller?.abort()
    if (retryTimer) clearTimeout(retryTimer)
    resolveRetry?.()
    retryTimer = null
    resolveRetry = null
    handlers.onState?.('closed')
  }
}
