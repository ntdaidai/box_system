const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

const RANGE_CONFIG = {
  '1h': {
    durationMs: HOUR,
    sampleMs: MINUTE,
    majorTickMs: 10 * MINUTE,
    alignMs: 10 * MINUTE,
    labelMode: 'time',
  },
  '6h': {
    durationMs: 6 * HOUR,
    sampleMs: 10 * MINUTE,
    majorTickMs: HOUR,
    alignMs: 30 * MINUTE,
    labelMode: 'time',
  },
  '1d': {
    durationMs: DAY,
    sampleMs: 30 * MINUTE,
    majorTickMs: 4 * HOUR,
    alignMs: HOUR,
    labelMode: 'date-time',
  },
  '7d': {
    durationMs: 7 * DAY,
    sampleMs: HOUR,
    majorTickMs: DAY,
    alignMs: HOUR,
    labelMode: 'date',
  },
  '6mo': {
    durationMs: 180 * DAY,
    sampleMs: DAY,
    majorTickMs: 30 * DAY,
    alignMs: DAY,
    labelMode: 'date',
  },
}

export const getHistoryRangeConfig = (range = '1h') => {
  return RANGE_CONFIG[range] || RANGE_CONFIG['1h']
}

const alignDown = (timeMs, alignMs) => {
  return Math.floor(timeMs / alignMs) * alignMs
}

export const buildHistoryWindow = (range = '1h', now = new Date(), overrideConfig = null) => {
  const config = overrideConfig || getHistoryRangeConfig(range)
  const nowMs = now instanceof Date ? now.getTime() : new Date(now).getTime()
  const endMs = alignDown(nowMs, config.alignMs)
  return {
    startMs: endMs - config.durationMs,
    endMs,
    config,
  }
}

export const buildChartAxisWindow = (window) => {
  if (
    !Number.isFinite(window?.startMs) ||
    !Number.isFinite(window?.endMs) ||
    !Number.isFinite(window?.config?.majorTickMs)
  ) {
    return { min: window?.startMs, max: window?.endMs }
  }

  const edgePaddingMs = window.config.majorTickMs / 5
  return {
    min: window.startMs - edgePaddingMs,
    max: window.endMs + edgePaddingMs,
  }
}

export const getNextHistoryRefreshMs = (range = '1h', from = new Date()) => {
  const config = getHistoryRangeConfig(range)
  const fromMs = from instanceof Date ? from.getTime() : new Date(from).getTime()
  if (!Number.isFinite(fromMs)) return config.alignMs
  const currentBoundary = alignDown(fromMs, config.alignMs)
  return currentBoundary + config.alignMs - fromMs
}

export const buildTimeSeries = (range = '1h', now = new Date()) => {
  const window = buildHistoryWindow(range, now)
  return buildTimeSeriesFromWindow(window)
}

export const buildTimeSeriesFromWindow = (window) => {
  const points = []
  for (let start = window.startMs; start < window.endMs; start += window.config.sampleMs) {
    const end = Math.min(start + window.config.sampleMs, window.endMs)
    points.push({ start, end, time: start })
  }
  return points
}

export const formatAxisLabel = (value, range = '1h') => {
  const config = getHistoryRangeConfig(range)
  const date = new Date(value)

  if (config.labelMode === 'date') {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  }

  if (config.labelMode === 'date-time') {
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }

  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export const formatChartAxisLabel = (value, range = '1h', window = null) => {
  const time = Number(value)
  if (
    window &&
    Number.isFinite(time) &&
    Number.isFinite(window.startMs) &&
    Number.isFinite(window.endMs) &&
    (time < window.startMs || time > window.endMs)
  ) {
    return ''
  }

  return formatAxisLabel(value, range)
}

const buildWindowConfig = (range, meta = {}) => {
  const sampleMs = Number(meta.sample_interval) * 1000
  return {
    ...getHistoryRangeConfig(range),
    sampleMs: Number.isFinite(sampleMs) && sampleMs > 0 ? sampleMs : getHistoryRangeConfig(range).sampleMs,
  }
}

export const normalizeHistorySeries = (history = [], range = '1h', fieldMap = {}, now = new Date(), meta = {}) => {
  const config = buildWindowConfig(range, meta)
  const metaStartMs = Number(meta.window?.start) * 1000
  const metaEndMs = Number(meta.window?.end) * 1000
  const window = (
    Number.isFinite(metaStartMs) &&
    Number.isFinite(metaEndMs) &&
    metaEndMs > metaStartMs
  )
    ? { startMs: metaStartMs, endMs: metaEndMs, config }
    : buildHistoryWindow(range, now, config)
  return normalizeHistoryIntoWindow(history, fieldMap, window)
}

const normalizeHistoryIntoWindow = (history, fieldMap, window) => {
  const buckets = buildTimeSeriesFromWindow(window)
  const series = Object.fromEntries(Object.keys(fieldMap).map(key => [key, []]))

  buckets.forEach((bucket, index) => {
    const bucketPoints = history.filter(point => {
      const ts = Number(point.timestamp || 0) * 1000
      const isLast = index === buckets.length - 1
      return ts >= bucket.start && (isLast ? ts <= bucket.end : ts < bucket.end)
    })

    Object.entries(fieldMap).forEach(([key, field]) => {
      const values = bucketPoints
        .map(point => Number(point.data?.[field]))
        .filter(value => Number.isFinite(value))

      if (!values.length) {
        series[key].push([bucket.time, null])
        return
      }

      const value = values.at(-1)
      series[key].push([bucket.time, Number(value.toFixed(4))])
    })
  })

  return {
    series,
    buckets,
    window,
    config: window.config,
  }
}

/**
 * 计算 Y 轴范围，使数据居中显示。
 */
export const calcYAxisRange = (values = [], padding = 0.2, fallback = { min: 0, max: 1 }) => {
  const valid = values
    .map(value => Array.isArray(value) ? value[1] : value)
    .filter(value => value != null && Number.isFinite(Number(value)))
    .map(Number)

  if (!valid.length) return fallback
  const dataMin = Math.min(...valid)
  const dataMax = Math.max(...valid)
  const baseMin = Number(fallback.min)
  const baseMax = Number(fallback.max)

  if (Number.isFinite(baseMin) && Number.isFinite(baseMax) && dataMin >= baseMin && dataMax <= baseMax) {
    return { min: baseMin, max: baseMax }
  }

  const min = Number.isFinite(baseMin) ? Math.min(baseMin, dataMin) : dataMin
  const max = Number.isFinite(baseMax) ? Math.max(baseMax, dataMax) : dataMax
  const range = max - min || 1
  const pad = range * padding
  return {
    min: Number((min - pad).toFixed(2)),
    max: Number((max + pad).toFixed(2)),
  }
}
