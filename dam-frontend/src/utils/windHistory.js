// Exclusive upper bounds for Beaufort levels 0..11. Published integer ranges
// are inclusive (for example level 1 is 1–5 km/h), so using 6 as the next
// boundary avoids classifying an exact 5 km/h reading as level 2.
const BEAUFORT_KMH_UPPER_BOUNDS = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
const BEAUFORT_MS_UPPER_BOUNDS = [0.3, 1.6, 3.4, 5.5, 8, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]

export const toWindNumber = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

export const windForceFromKmh = (speedKmh) => {
  const speed = toWindNumber(speedKmh)
  if (speed === null || speed < 0) return null
  const level = BEAUFORT_KMH_UPPER_BOUNDS.findIndex(limit => speed < limit)
  return level < 0 ? 12 : level
}

export const windForceFromMs = (speedMs) => {
  const speed = toWindNumber(speedMs)
  if (speed === null || speed < 0) return null
  const level = BEAUFORT_MS_UPPER_BOUNDS.findIndex(limit => speed < limit)
  return level < 0 ? 12 : level
}

export const resolveWindLevel = (data = {}) => {
  const measured = toWindNumber(data.wind_level)
  if (measured !== null) return Math.max(0, Math.min(12, Math.round(measured)))

  const ms = toWindNumber(data.wind_speed_ms)
  if (ms !== null) return windForceFromMs(ms)

  const kmh = toWindNumber(data.wind_speed_kmh)
  return kmh === null ? null : windForceFromKmh(kmh)
}

export const formatWindSource = (direction) => {
  const value = String(direction || '').trim()
  if (!value) return '--'
  const cardinal = { 北: '北方', 东: '东方', 南: '南方', 西: '西方' }
  return `来自${cardinal[value] || `${value}方向`}`
}

export const shanghaiDateKey = (value) => {
  const dateValue = value instanceof Date ? value : new Date(value)
  if (!Number.isFinite(dateValue.getTime())) return ''
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(dateValue)
  const get = type => parts.find(part => part.type === type)?.value || ''
  return `${get('year')}-${get('month')}-${get('day')}`
}

export const windDirectionByDate = (history = []) => new Map(
  history
    .filter(row => row?.date && row?.data?.wind_direction)
    .map(row => [row.date, row.data.wind_direction]),
)

const calendarDateParts = (value) => {
  const [year, month, day] = String(value || '').split('-').map(Number)
  if (![year, month, day].every(Number.isInteger)) return null
  return { year, month, day }
}

export const formatWindCalendarAxisLabel = (value, monthly) => {
  const parts = calendarDateParts(value)
  if (!parts) return ''
  return monthly ? `${parts.day}日` : `${parts.month}月`
}

export const shouldShowWindCalendarLabel = (_index, value, monthly, chartWidth, firstMonthIndex) => {
  const parts = calendarDateParts(value)
  if (!parts) return false
  if (monthly) return (parts.day - 1) % 4 === 0
  if (parts.day !== 1) return false
  if (chartWidth >= 480 || !Number.isFinite(firstMonthIndex)) return true
  return (parts.year * 12 + parts.month - firstMonthIndex) % 2 === 0
}

const calendarDateKeys = (year, month = null) => {
  const startMonth = month == null ? 0 : Number(month) - 1
  const endMonth = month == null ? 12 : startMonth + 1
  const result = []
  for (let monthIndex = startMonth; monthIndex < endMonth; monthIndex += 1) {
    const days = new Date(Date.UTC(Number(year), monthIndex + 1, 0)).getUTCDate()
    for (let day = 1; day <= days; day += 1) {
      result.push(`${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`)
    }
  }
  return result
}

const rolling12DateKeys = (anchorValue) => {
  const anchorKey = shanghaiDateKey(anchorValue)
  const [anchorYear, anchorMonth] = anchorKey.split('-').map(Number)
  if (!Number.isInteger(anchorYear) || !Number.isInteger(anchorMonth)) return []

  const firstMonthIndex = anchorYear * 12 + anchorMonth - 1 - 11
  const result = []
  for (let offset = 0; offset < 12; offset += 1) {
    const monthIndex = firstMonthIndex + offset
    const year = Math.floor(monthIndex / 12)
    const month = monthIndex % 12 + 1
    result.push(...calendarDateKeys(year, month))
  }
  return result
}

const materializeDailyRows = (history, dateKeys) => {
  const allowed = new Set(dateKeys)
  const rows = new Map()
  history.forEach(point => {
    const key = shanghaiDateKey(Number(point.timestamp) * 1000 - 1)
    if (allowed.has(key)) rows.set(key, { date: key, timestamp: point.timestamp, data: point.data || {} })
  })
  return dateKeys.map(key => rows.get(key) || { date: key, data: {} })
}

const calendarWindow = (dateKeys) => {
  if (!dateKeys.length) return null
  const start = new Date(`${dateKeys[0]}T00:00:00+08:00`).getTime()
  const end = new Date(`${dateKeys.at(-1)}T00:00:00+08:00`).getTime() + 24 * 60 * 60 * 1000
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null
  return { start: start / 1000, end: end / 1000 }
}

const populatedWindDays = rows => rows.filter(row => (
  toWindNumber(row.data?.wind_speed_kmh) !== null
  || toWindNumber(row.data?.wind_speed_ms) !== null
)).length

export const normalizeLegacyWindTrend = (payload = {}, query = {}) => {
  const history = Array.isArray(payload.history) ? payload.history : []
  if (query.view === 'recent24h') {
    const start = Number(payload.window?.start)
    const end = Number(payload.window?.end)
    const maxPoints = Number(payload.max_point_count || 48)
    const points = history
      .filter(point => Number(point.timestamp) > start && Number(point.timestamp) <= end)
      .slice(-maxPoints)
    return {
      ...payload,
      view: 'recent24h',
      aggregation: '30m_average',
      history: points,
      point_count: points.length,
    }
  }

  if (query.view === 'rolling12') {
    const payloadEnd = Number(payload.window?.end) * 1000
    const anchor = query.now ?? (Number.isFinite(payloadEnd) ? payloadEnd : Date.now())
    const dateKeys = rolling12DateKeys(anchor)
    const rows = materializeDailyRows(history, dateKeys)
    const pointCount = populatedWindDays(rows)
    return {
      ...payload,
      view: 'rolling12',
      aggregation: 'daily_average_compatibility',
      window: calendarWindow(dateKeys),
      max_point_count: rows.length,
      history: rows,
      point_count: pointCount,
      coverage_ratio: rows.length ? Number((pointCount / rows.length).toFixed(4)) : 0,
    }
  }

  const year = Number(query.year)
  const month = query.month == null ? null : Number(query.month)
  const dateKeys = calendarDateKeys(year, month)
  const materialized = materializeDailyRows(history, dateKeys)
  const pointCount = populatedWindDays(materialized)
  return {
    ...payload,
    view: 'calendar',
    aggregation: 'daily_average_compatibility',
    year,
    month,
    window: calendarWindow(dateKeys),
    max_point_count: materialized.length,
    history: materialized,
    point_count: pointCount,
  }
}
