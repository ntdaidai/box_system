const API_BASE_URL = 'http://10.199.204.140:8090'.trim()

export {
  API_BASE_URL,
}

export const MINI_API_BASE = `${API_BASE_URL}/api/miniprogram/v1`
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws')

// 展示模式：真实数据不足时，仅在待处理/处理中列表补充演示数据，不写入后端数据库。
export const ENABLE_DEMO_EVENTS = true
export const DEMO_EVENT_TARGETS = {
  pending: 3,
  processing: 3
}

export function withApiOrigin(path) {
  if (!path) return ''
  const rawPath = String(path).trim()
  if (/^(https?|rtmp|rtmps):\/\//i.test(rawPath)) {
    // 历史事件里的 MinIO URL 可能是后端容器生成的 localhost:9000，
    // 在 Windows/手机端应替换为当前 Jetson 的可达地址。
    const minioLocal = rawPath.match(/^(https?):\/\/(localhost|127\.0\.0\.1):9000(\/.*)?$/i)
    if (minioLocal) {
      const apiHost = API_BASE_URL.replace(/^https?:\/\//i, '').split('/')[0].split(':')[0]
      return `${minioLocal[1]}://${apiHost}:9000${minioLocal[3] || ''}`
    }
    return rawPath
  }
  const cleanPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
  return `${API_BASE_URL}${cleanPath}`.trim()
}
