export function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatTime(seconds) {
  if (!seconds) return '--'
  const date = new Date(seconds * 1000)
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function formatDateTime(seconds) {
  if (!seconds) return '--'
  const date = new Date(seconds * 1000)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hours) return `${hours}小时${minutes}分钟`
  if (minutes) return `${minutes}分钟${secs}秒`
  return `${secs}秒`
}

export function riskClass(riskLevel) {
  if (riskLevel === 'HIGH') return 'risk-high'
  if (riskLevel === 'MEDIUM') return 'risk-medium'
  return 'risk-low'
}
