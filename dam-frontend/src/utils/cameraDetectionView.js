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

export function detectionName(detection) {
  return detection?.class_name_cn
    || detection?.class_name
    || `类别 ${detection?.class_id ?? '-'}`
}

export function confidencePercent(detection) {
  const confidence = Number(detection?.confidence || 0)
  return Math.max(0, Math.min(100, Math.round(confidence * 100)))
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
