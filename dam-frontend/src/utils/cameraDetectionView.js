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

export function normalizeZoneType(type) {
  if (!type) return 'PERSON_LOW'
  return ({
    PERSON_LOW: 'PERSON_LOW',
    PERSON_MEDIUM: 'PERSON_MEDIUM',
    PERSON_HIGH: 'PERSON_HIGH',
    FISHING: 'FISHING',
  })[type] || null
}

export function zoneTypeLabel(type) {
  return ({
    PERSON_LOW: '低风险区',
    PERSON_MEDIUM: '中风险区',
    PERSON_HIGH: '高风险区',
    FISHING: '捕鱼区',
  })[normalizeZoneType(type)] || '检测区域'
}

export function riskLevelLabel(level) {
  return ({ LOW: 'LOW', MEDIUM: 'MEDIUM', HIGH: 'HIGH' })[level] || 'LOW'
}

export function personZoneTypes() {
  return ['PERSON_LOW', 'PERSON_MEDIUM', 'PERSON_HIGH']
}

export function defaultTriggerSeconds(type) {
  return ({ PERSON_LOW: 5, PERSON_MEDIUM: 3, PERSON_HIGH: 0, FISHING: 0 })[normalizeZoneType(type)] ?? 0
}

export function polygonBounds(points) {
  if (!Array.isArray(points) || points.length < 3) return null
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const x = Math.min(...xs)
  const y = Math.min(...ys)
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y }
}

export function normalizeZones(payload) {
  const zones = Array.isArray(payload?.zones) ? payload.zones : []
  return zones.map((zone) => {
    const zoneType = normalizeZoneType(zone?.zone_type || zone?.type)
    const polygonPoints = (Array.isArray(zone?.polygon_points) ? zone.polygon_points : [])
      .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    const bounds = polygonBounds(polygonPoints)
    const zoneId = zone?.id === undefined || zone?.id === null ? '' : String(zone.id)
    if (!zoneId || !bounds || polygonPoints.length > 15 || ![...personZoneTypes(), 'FISHING'].includes(zoneType)) return null
    const zoneName = zone?.zone_name || zone?.name || zoneTypeLabel(zoneType)
    return {
      ...zone,
      zone_name: zoneName,
      zone_type: zoneType,
      polygon_points: polygonPoints,
      trigger_seconds: Number.isFinite(Number(zone?.trigger_seconds))
        ? Number(zone.trigger_seconds)
        : defaultTriggerSeconds(zoneType),
      enabled: zone?.enabled !== false,
      condition_durations: zone?.condition_durations || (zoneType === 'FISHING' ? {
        BOAT_INTRUSION: 0, BOAT_STAY: 30, BOAT_ILLEGAL_FISHING: 120,
      } : {}),
      id: zoneId,
      name: zoneName,
      type: zoneType,
    }
  }).filter(Boolean)
}

export function targetPointForDetection(detection, zoneType) {
  if (!isValidDetection(detection)) return null
  const { x1, y1, x2, y2 } = detection.bbox
  return personZoneTypes().includes(normalizeZoneType(zoneType))
    ? { x: (x1 + x2) / 2, y: y2 }
    : { x: (x1 + x2) / 2, y: (y1 + y2) / 2 }
}

export function detectionMatchesZoneType(detection, zoneType) {
  const normalizedZoneType = normalizeZoneType(zoneType)
  const classId = Number(detection?.class_id)
  const name = String(detection?.class_name || '').toLowerCase()
  if (normalizedZoneType === 'FISHING') return classId === 0 || ['boat', 'ship', 'vessel', 'fishing_boat'].includes(name)
  if (personZoneTypes().includes(normalizedZoneType)) return [1, 2, 3].includes(classId) || name.includes('person')
  return false
}

export function pointInPolygon(point, points) {
  if (!point || !Array.isArray(points) || points.length < 3) return false
  let inside = false
  let previous = points[points.length - 1]
  points.forEach((current) => {
    const onEdge = point.x >= Math.min(current.x, previous.x)
      && point.x <= Math.max(current.x, previous.x)
      && point.y >= Math.min(current.y, previous.y)
      && point.y <= Math.max(current.y, previous.y)
      && Math.abs((point.x - current.x) * (previous.y - current.y) - (point.y - current.y) * (previous.x - current.x)) < 1e-9
    if (onEdge) {
      inside = true
    } else if (((current.y > point.y) !== (previous.y > point.y))
      && point.x < (previous.x - current.x) * (point.y - current.y) / (previous.y - current.y) + current.x) {
      inside = !inside
    }
    previous = current
  })
  return inside
}

export function detectionInZone(detection, zone, imageWidth, imageHeight) {
  if (!detectionMatchesZoneType(detection, zone?.zone_type || zone?.type)) return false
  const point = targetPointForDetection(detection, zone.zone_type || zone.type)
  if (!point || imageWidth <= 0 || imageHeight <= 0) return false
  return pointInPolygon(
    { x: point.x / imageWidth, y: point.y / imageHeight },
    zone?.polygon_points || [],
  )
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
