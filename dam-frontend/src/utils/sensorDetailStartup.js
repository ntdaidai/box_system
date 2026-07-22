export const runWhenIdle = (callback, timeout = 600) => {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    return window.requestIdleCallback(callback, { timeout })
  }
  return setTimeout(callback, timeout)
}

export const cancelIdleTask = (taskId) => {
  if (taskId == null) return
  if (typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(taskId)
    return
  }
  clearTimeout(taskId)
}

export const preloadHistoryRanges = async (ranges, loadHistory) => {
  for (const range of ranges) {
    await loadHistory(range, false)
  }
}

export const createSensorDetailStartup = ({
  initChart,
  fetchRealtime,
  loadInitialHistory,
  renderHistory,
  scheduleHistoryRefresh,
  preloadHistoryLater,
}) => {
  let resolveHistoryReady
  const historyReady = new Promise(resolve => {
    resolveHistoryReady = resolve
  })

  const start = () => {
    initChart()
    fetchRealtime()

    Promise.resolve()
      .then(loadInitialHistory)
      .then(() => {
        renderHistory()
        scheduleHistoryRefresh()
        preloadHistoryLater()
      })
      .finally(resolveHistoryReady)
  }

  return { start, historyReady }
}
