const API_BASE_URL = 'http://192.168.31.52:8090'.trim()

export {
  API_BASE_URL,
}

export const MINI_API_BASE = `${API_BASE_URL}/api/miniprogram/v1`
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws')

export function withApiOrigin(path) {
  if (!path) return ''
  const rawPath = String(path).trim()
  if (/^(https?|rtmp|rtmps):\/\//i.test(rawPath)) return rawPath
  const cleanPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
  return `${API_BASE_URL}${cleanPath}`.trim()
}
