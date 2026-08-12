/**
 * 媒体 URL 处理工具
 *
 * MinIO 对象地址（http://localhost:9000/dam/... 或 dam/...）在浏览器侧不可直接访问：
 * - localhost 在客户端指向用户自己的机器，局域网不可达
 * - MinIO 桶为私有权限，匿名访问返回 403
 *
 * 统一转换为后端媒体代理接口（同源访问，后端持有 MinIO 凭据）。
 */

const MINIO_HOSTS = ['localhost', '127.0.0.1', '172.17.0.1', 'minio']

/**
 * 将 MinIO 对象地址转换为后端媒体代理地址；非 MinIO 地址原样返回。
 * @param {string} url 原始媒体地址
 * @returns {string} 可访问的媒体地址
 */
export function normalizeMediaUrl(url) {
  if (!url) return ''
  const raw = String(url)
  if (raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('/')) return raw
  if (raw.startsWith('dam/')) {
    return `/api/v1/camera/media/minio-proxy?url=${encodeURIComponent(raw)}`
  }
  try {
    const parsed = new URL(raw)
    const isMinio = parsed.port === '9000' || MINIO_HOSTS.includes(parsed.hostname)
    if (isMinio && parsed.pathname.startsWith('/dam/')) {
      return `/api/v1/camera/media/minio-proxy?url=${encodeURIComponent(raw)}`
    }
  } catch (_) {
    return raw
  }
  return raw
}

/**
 * 批量转换媒体地址，过滤空值。
 * @param {Array<string>} urls 原始媒体地址列表
 * @returns {Array<string>} 可访问的媒体地址列表
 */
export function normalizeMediaUrls(urls) {
  return (urls || []).map(normalizeMediaUrl).filter(Boolean)
}
