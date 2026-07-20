// dai
// Pure camera-result helpers kept outside the Vue component for boundary tests.

export function isValidDetection(item) {
  const box = item?.bbox
  return Boolean(
    box
      && [box.x1, box.y1, box.x2, box.y2].every(Number.isFinite)
      && box.x2 > box.x1
      && box.y2 > box.y1,
  )
}

export function normalizeDetections(payload) {
  return Array.isArray(payload?.detections)
    ? payload.detections.filter(isValidDetection)
    : []
}

export function normalizeClassifications(payload) {
  return Array.isArray(payload?.classifications)
    ? payload.classifications.filter((item) => (
      Number.isInteger(Number(item?.class_id))
      && Number.isFinite(Number(item?.confidence))
    ))
    : []
}

export function primaryClassification(payload) {
  return payload?.prediction || normalizeClassifications(payload)[0] || null
}

export function detectionName(detection) {
  return detection?.class_name_cn
    || detection?.class_name
    || `类别 ${detection?.class_id ?? '-'}`
}

export function confidencePercent(detection) {
  const confidence = Number(detection?.confidence || 0)
  return Math.max(0, Math.min(100, Math.round(confidence * 100)))
}

export function formatDeviceCommTime(timestamp) {
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric) || numeric <= 0) return '--'

  const milliseconds = numeric >= 1e12 ? numeric : numeric * 1000
  const date = new Date(milliseconds)
  if (Number.isNaN(date.getTime())) return '--'

  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return `${values.month}/${values.day} ${values.hour}:${values.minute}:${values.second}`
}

export function classColor(classId) {
  const fixed = ['#43d69b', '#ff9f43', '#ff5d6c', '#32c5ff']
  const numericId = Number(classId)
  if (Number.isInteger(numericId) && numericId >= 0 && numericId < fixed.length) {
    return fixed[numericId]
  }
  const safeId = Number.isFinite(numericId) ? numericId : 0
  const hue = Math.abs(safeId * 67) % 360
  return `hsl(${hue} 80% 58%)`
}

export function findVideoSample(timeline, currentTime) {
  if (!Array.isArray(timeline) || timeline.length === 0) return null
  const target = Math.max(0, Number(currentTime) || 0)
  let low = 0
  let high = timeline.length - 1
  while (low < high) {
    const middle = Math.ceil((low + high) / 2)
    if (Number(timeline[middle]?.time) <= target) low = middle
    else high = middle - 1
  }
  return timeline[low] || null
}
