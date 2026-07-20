<template>
  <div class="sensor-detail">
    <div class="detail-header">
      <div class="header-left">
        <img src="@/assets/images/sensors/wind.png" class="header-icon" />
        <div class="header-info">
          <h2>风速风向传感器</h2>
        </div>
      </div>
      <div class="header-status" :class="statusClass">
        <span class="dot"></span>{{ statusText }}
        <div class="header-comm" v-if="lastTimestamp">最后通讯: {{ formatCommTime(lastTimestamp) }}</div>
      </div>
    </div>

    <!-- 上半部分: 指南针 + 实时数据 -->
    <div class="top-row">
      <!-- 指南针 -->
      <div class="data-panel compass-panel">
        <div class="panel-title">风向指南针</div>
        <div class="compass-wrapper">
          <div class="wind-compass">
            <span class="compass-label label-n">北</span>
            <span class="compass-label label-e">东</span>
            <span class="compass-label label-s">南</span>
            <span class="compass-label label-w">西</span>
            <span class="compass-label compass-label-sub label-ne">东北</span>
            <span class="compass-label compass-label-sub label-se">东南</span>
            <span class="compass-label compass-label-sub label-sw">西南</span>
            <span class="compass-label compass-label-sub label-nw">西北</span>
            <div v-if="compassState.angle != null" class="compass-pointer" :style="compassState.pointerStyle">
              <span class="compass-arrow"></span>
            </div>
            <div class="compass-axis axis-vertical"></div>
            <div class="compass-axis axis-horizontal"></div>
            <div class="compass-center-info">
              <div class="compass-dir">{{ compassState.direction }}</div>
              <div class="compass-angle">{{ compassState.angleText }}</div>
            </div>
          </div>
        </div>
        <!-- 底部信息 -->
        <div class="compass-footer">
          <span>当前风向：{{ compassState.footerDirection }}</span>
          <span>方位角：{{ compassState.angleText }}</span>
        </div>
      </div>

      <!-- 实时数据卡片 -->
      <div class="data-panel data-strip-panel">
        <div class="panel-title">实时数据</div>
        <div class="wind-data-card">
          <!-- 左侧核心区 -->
          <div class="wind-core">
            <div class="wind-speed-main">
              <span class="wind-speed-num">{{ liveWindSpeedMs != null ? liveWindSpeedMs.toFixed(1) : '--' }}</span>
              <span class="wind-speed-unit">m/s</span>
            </div>
            <div class="wind-level-bar">
              <div class="wind-level-track">
                <div class="wind-level-cursor" :style="{ left: windSpeedPosition + '%' }"></div>
              </div>
              <div class="wind-level-labels">
                <span>0</span>
                <span>15 m/s</span>
                <span>30+</span>
              </div>
            </div>
            <div class="wind-level-status">
              <span class="wind-status-ref">参考安全区 &lt; 15m/s</span>
              <span class="wind-status-val" :class="windStatusClass">当前状态：{{ windStatusText }}</span>
            </div>
          </div>
          <!-- 右侧辅助区 -->
          <div class="wind-aux">
            <div class="wind-aux-item">
              <div class="wind-aux-val">{{ liveWindSpeedKmh != null ? liveWindSpeedKmh.toFixed(1) : '--' }}</div>
              <div class="wind-aux-label">风速 km/h</div>
            </div>
            <div class="wind-aux-divider"></div>
            <div class="wind-aux-item">
              <div class="wind-aux-val">{{ data.wind_direction || '--' }}</div>
              <div class="wind-aux-label">风向</div>
            </div>
            <div class="wind-aux-divider"></div>
            <div class="wind-aux-item">
              <div class="wind-aux-val">{{ compassState.angleText }}</div>
              <div class="wind-aux-label">角度</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 风速趋势：近24小时 + 年/月每日平均 -->
    <div class="data-panel history-panel">
      <div class="history-panel-header">
        <div class="history-heading">
          <span class="panel-title">风速趋势</span>
          <div class="metric-switch" aria-label="风速指标">
            <button type="button" class="active"><span>≋</span>风速</button>
          </div>
        </div>
        <div class="history-controls">
          <button
            type="button"
            class="period-button"
            :class="{ active: historyMode === 'recent24h' }"
            @click="selectRecent24h"
          >
            <span class="control-icon">◷</span>近24小时
          </button>
          <div class="calendar-controls" :class="{ active: historyMode === 'calendar' }">
            <el-select v-model="selectedYear" class="history-select year-select" @change="onYearChange">
              <el-option
                v-for="year in yearOptions"
                :key="year"
                :label="year === 'last12' ? '过去12个月' : `${year}年`"
                :value="year"
              />
            </el-select>
            <el-select
              v-model="selectedMonth"
              class="history-select month-select"
              :disabled="selectedYear === 'last12'"
              @change="onMonthChange"
            >
              <el-option label="所有月份" value="all" />
              <el-option
                v-for="month in monthOptions"
                :key="month"
                :label="`${month}月`"
                :value="month"
              />
            </el-select>
          </div>
        </div>
      </div>

      <div class="trend-shell">
        <div class="chart-wrap history-chart-wrap">
          <div class="chart-container" ref="chartRef"></div>
          <div v-if="historyError && !historyEmpty" class="chart-error-banner">
            <span>{{ historyError }}，当前显示上一次成功加载的数据</span>
            <button type="button" @click="retryHistory">重试</button>
          </div>
          <div v-if="historyLoading" class="chart-loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">正在读取聚合数据...</div>
          </div>
          <div v-else-if="historyError && historyEmpty" class="chart-loading-overlay">
            <div class="loading-text">{{ historyError }}</div>
            <button type="button" class="chart-retry-button" @click="retryHistory">重新加载</button>
          </div>
          <div v-else-if="historyEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">该时间范围暂无风速数据</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getSensorHistory, getSensorRealtime, getWindTrends } from '@/api/sensor'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, runWhenIdle } from '@/utils/sensorDetailStartup'
import { getWindCompassState } from '@/utils/sensorWindView'
import {
  formatWindSource,
  normalizeLegacyWindTrend,
  resolveWindLevel,
  shanghaiDateKey,
  toWindNumber,
  windDirectionByDate,
} from '@/utils/windHistory'
import * as echarts from 'echarts'

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const TREND_URL = '/v1/sensor/history/wind/trends'
const initialShanghaiYear = Number(shanghaiDateKey(Date.now()).slice(0, 4))

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const lastTimestamp = ref(0)
const historyMode = ref('recent24h')
const selectedYear = ref(initialShanghaiYear)
const selectedMonth = ref('all')
const availablePeriods = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'recent24h', history: [], window: null })
const historyCache = new Map()

let chart = null
let timer = null
let historyRefreshTimer = null
let preloadIdleTask = null
let resizeHandler = null
let resizeFrame = null
let historyRequestSerial = 0
let isMounted = false

const yearOptions = computed(() => {
  const years = availablePeriods.value.map(item => Number(item.year)).filter(Number.isFinite)
  const selected = Number(selectedYear.value)
  if (Number.isInteger(selected) && !years.includes(selected)) years.push(selected)
  return ['last12', ...(years.length ? [...new Set(years)].sort((a, b) => b - a) : [initialShanghaiYear])]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  if (!period) return Array.from({ length: 12 }, (_, index) => index + 1)
  return (period.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const getSpeedKmh = (source = {}) => {
  source = source || {}
  const kmh = toWindNumber(source.wind_speed_kmh)
  if (kmh !== null) return kmh
  const ms = toWindNumber(source.wind_speed_ms)
  return ms === null ? null : Number((ms * 3.6).toFixed(4))
}

const historyValues = computed(() => (chartData.value.history || [])
  .map(point => getSpeedKmh(point?.data))
  .filter(value => value !== null))

const historyEmpty = computed(() => historyValues.value.length === 0)

const liveWindSpeedMs = computed(() => {
  const ms = toWindNumber(data.value.wind_speed_ms)
  if (ms !== null) return ms
  const kmh = toWindNumber(data.value.wind_speed_kmh)
  return kmh === null ? null : kmh / 3.6
})

const liveWindSpeedKmh = computed(() => {
  const kmh = toWindNumber(data.value.wind_speed_kmh)
  if (kmh !== null) return kmh
  return liveWindSpeedMs.value === null ? null : liveWindSpeedMs.value * 3.6
})

// 风速进度条位置（0-30m/s 映射到 0-100%）
const windSpeedPosition = computed(() => {
  const v = liveWindSpeedMs.value || 0
  return Math.max(0, Math.min(100, (v / 30) * 100))
})
const windStatusText = computed(() => {
  const v = liveWindSpeedMs.value || 0
  if (v < 6) return '微风（安全）'
  if (v < 10) return '和风（注意）'
  if (v < 15) return '大风（警惕）'
  return '狂风（危险）'
})
const windStatusClass = computed(() => {
  const v = liveWindSpeedMs.value || 0
  if (v < 10) return 'status-ok'
  if (v < 15) return 'status-warn'
  return 'status-danger'
})
const compassState = computed(() => getWindCompassState(data.value))

const formatCommTime = (ts) => {
  const numeric = Number(ts)
  if (!Number.isFinite(numeric) || numeric <= 0) return '--'
  const timeMs = numeric > 1e12 ? numeric : numeric * 1000
  return new Date(timeMs).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

const fetchData = async () => {
  try {
    const res = await getSensorRealtime('wind')
    if (res.code === 200 && res.data?.data) {
      data.value = res.data.data
      lastTimestamp.value = res.data.timestamp || lastTimestamp.value
      statusClass.value = res.data.mock ? 'offline' : 'online'
      statusText.value = res.data.mock ? '离线' : '在线'
    }
  } catch {
    statusClass.value = 'offline'
    statusText.value = '离线'
  }
}

const queryKey = ({ view, year, month }) => [view, year || '', month || 'all'].join(':')

const historyCacheMaxAge = query => query.view === 'recent24h' ? 5 * MINUTE : 30 * MINUTE

const readHistoryCache = (query) => {
  const key = queryKey(query)
  const cached = historyCache.get(key)
  if (!cached) return null
  if (Date.now() - cached.updatedAt <= historyCacheMaxAge(query)) return cached.payload
  historyCache.delete(key)
  return null
}

const currentQuery = () => historyMode.value === 'recent24h'
  ? { view: 'recent24h' }
  : selectedYear.value === 'last12'
    ? { view: 'rolling12' }
    : {
      view: 'calendar',
      year: Number(selectedYear.value),
      month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
    }

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
}

const applyTrendPayload = (payload, query, apply = true, cacheResult = true) => {
  if (!payload) return null
  syncAvailablePeriods(payload.available_periods)
  const normalized = { ...payload, history: Array.isArray(payload.history) ? payload.history : [] }
  if (cacheResult) {
    historyCache.set(queryKey(query), { payload: normalized, updatedAt: Date.now() })
  }
  if (apply && queryKey(query) === queryKey(currentQuery())) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadLegacyTrends = async (query) => {
  const range = query.view === 'recent24h' ? '1d' : '6mo'
  const res = await getSensorHistory('wind', range)
  if (res.code !== 200) throw new Error('兼容历史响应无效')
  return normalizeLegacyWindTrend(res.data || {}, query)
}

const loadTrends = async (query = currentQuery(), apply = true, force = false) => {
  const key = queryKey(query)
  const requestId = apply ? ++historyRequestSerial : 0
  const isCurrentRequest = () => !apply || (
    isMounted
    && requestId === historyRequestSerial
    && key === queryKey(currentQuery())
  )
  const cached = force ? null : readHistoryCache(query)
  if (cached) {
    const shouldApply = apply && isCurrentRequest()
    const normalized = applyTrendPayload(cached, query, shouldApply, false)
    if (shouldApply) historyLoading.value = false
    return { payload: normalized, applied: shouldApply, error: false }
  }

  if (apply && isMounted) {
    historyLoading.value = true
    historyError.value = ''
  }
  try {
    const res = await getWindTrends(query)
    if (res.code !== 200 || !res.data || !Array.isArray(res.data.history)) {
      throw new Error('风速趋势响应无效')
    }
    const shouldApply = apply && isCurrentRequest()
    const normalized = applyTrendPayload(res.data, query, shouldApply)
    return { payload: normalized, applied: shouldApply, error: false }
  } catch (error) {
    console.warn('风速趋势专用接口不可用，尝试兼容历史接口:', error)
    if (apply && !isCurrentRequest()) {
      return { payload: null, applied: false, error: false }
    }
    try {
      const fallback = await loadLegacyTrends(query)
      const shouldApply = apply && isCurrentRequest()
      const normalized = applyTrendPayload(fallback, query, shouldApply)
      return { payload: normalized, applied: shouldApply, error: false }
    } catch (fallbackError) {
      console.warn('加载风速趋势失败:', fallbackError)
      const currentError = apply && isCurrentRequest()
      if (currentError) historyError.value = '历史数据服务暂时不可用，请稍后重试'
      return { payload: null, applied: false, error: currentError }
    }
  } finally {
    if (apply && isCurrentRequest()) historyLoading.value = false
  }
}

const handleHistoryCacheUpdate = (event) => {
  const detail = event.detail || {}
  if (detail.url !== TREND_URL || detail.data?.code !== 200) return
  const params = detail.params || {}
  const query = {
    view: params.view || 'recent24h',
    year: params.year != null ? Number(params.year) : undefined,
    month: params.month != null ? Number(params.month) : null,
  }
  const shouldApply = queryKey(query) === queryKey(currentQuery())
  applyTrendPayload(detail.data.data, query, shouldApply)
  if (shouldApply && queryKey(query) === queryKey(currentQuery())) renderChart()
}

const preloadCalendarLater = () => {
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  const preloadYear = Number.isInteger(Number(selectedYear.value))
    ? Number(selectedYear.value)
    : initialShanghaiYear
  preloadIdleTask = runWhenIdle(() => {
    preloadIdleTask = null
    loadTrends({ view: 'calendar', year: preloadYear, month: null }, false)
  }, 1200)
}

const millisecondsToNextHalfHour = () => {
  const now = Date.now()
  const interval = 30 * 60 * 1000
  return Math.floor(now / interval) * interval + interval - now
}

const restoreSelectionFromChart = () => {
  const view = chartData.value.view
  if (view === 'recent24h') {
    historyMode.value = 'recent24h'
    return
  }

  historyMode.value = 'calendar'
  if (view === 'rolling12') {
    selectedYear.value = 'last12'
    selectedMonth.value = 'all'
    return
  }

  const year = Number(chartData.value.year)
  selectedYear.value = Number.isInteger(year) ? year : initialShanghaiYear
  const month = Number(chartData.value.month)
  selectedMonth.value = Number.isInteger(month) && month >= 1 && month <= 12 ? month : 'all'
}

const finishHistorySelection = (query, result) => {
  if (!isMounted || queryKey(query) !== queryKey(currentQuery())) return
  if (!result?.applied && !result?.error) return
  if (result?.error) restoreSelectionFromChart()
  if (result?.applied || result?.error) renderChart()
  scheduleHistoryRefresh()
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (!isMounted) return
  const delay = historyMode.value === 'recent24h' ? millisecondsToNextHalfHour() + 1000 : 30 * 60 * 1000
  historyRefreshTimer = setTimeout(async () => {
    if (!isMounted) return
    const query = currentQuery()
    historyCache.delete(queryKey(query))
    const result = await loadTrends(query, true, true)
    finishHistorySelection(query, result)
  }, delay)
}

const selectRecent24h = async () => {
  if (historyMode.value === 'recent24h' && !historyError.value) return
  historyMode.value = 'recent24h'
  const query = currentQuery()
  const result = await loadTrends(query, true, Boolean(historyError.value))
  finishHistorySelection(query, result)
}

const onYearChange = async () => {
  historyMode.value = 'calendar'
  if (selectedYear.value === 'last12') selectedMonth.value = 'all'
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
  const query = currentQuery()
  const result = await loadTrends(query)
  finishHistorySelection(query, result)
}

const onMonthChange = async () => {
  historyMode.value = 'calendar'
  const query = currentQuery()
  const result = await loadTrends(query)
  finishHistorySelection(query, result)
}

const retryHistory = async () => {
  const query = currentQuery()
  historyCache.delete(queryKey(query))
  const result = await loadTrends(query, true, true)
  finishHistorySelection(query, result)
}

const toCalendarTimestamp = dateValue => new Date(`${dateValue}T00:00:00+08:00`).getTime()

const chartSeriesData = () => (chartData.value.history || []).map(point => {
  const pointData = point?.data || {}
  const speed = getSpeedKmh(pointData)
  return {
    value: historyMode.value === 'recent24h'
      ? [Number(point.timestamp) * 1000, speed]
      : speed,
    windLevel: resolveWindLevel(pointData),
    windDirection: pointData.wind_direction || '',
    date: point?.date || '',
  }
})

const formatXAxisLabel = (value) => {
  if (historyMode.value === 'recent24h') {
    const dateValue = new Date(value)
    return dateValue.toLocaleTimeString('zh-CN', {
      timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false,
    })
  }
  const [, month, day] = String(value).split('-').map(Number)
  if (selectedMonth.value === 'all') return `${month}月`
  const direction = windDirectionByDate(chartData.value.history).get(String(value)) || ' '
  return `{direction|${direction}}\n{day|${day}}`
}

const escapeTooltipHtml = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character])

const tooltipFormatter = (params) => {
  const recent = historyMode.value === 'recent24h'
  const item = (Array.isArray(params) ? params : [params]).find(entry => {
    const value = recent ? entry.value?.[1] : entry.value
    return value !== null && value !== undefined
  })
  if (!item) return ''
  const dateValue = recent ? new Date(item.value[0]) : new Date(`${item.axisValue}T00:00:00+08:00`)
  const heading = recent
    ? dateValue.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    : dateValue.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' })
  const speed = recent ? item.value[1] : item.value
  const speedLabel = recent ? '30分钟平均风速' : '每日平均风速'
  const level = item.data?.windLevel
  const levelText = level == null ? '--' : `${level}级`
  const directionText = escapeTooltipHtml(formatWindSource(item.data?.windDirection))
  return `<div style="min-width:205px"><strong>${escapeTooltipHtml(heading)}</strong>`
    + `<div style="display:flex;justify-content:space-between;gap:22px;margin-top:8px">`
    + `<span>${item.marker}${speedLabel}</span><strong>${Number(speed).toFixed(1)} 公里/小时</strong></div>`
    + `<div style="display:flex;justify-content:space-between;gap:22px;margin-top:7px">`
    + `<span>风级</span><strong>${levelText}</strong></div>`
    + `<div style="display:flex;justify-content:space-between;gap:22px;margin-top:7px">`
    + `<span>风向</span><strong>${directionText}</strong></div></div>`
}

const currentDayMark = () => {
  if (historyMode.value !== 'calendar') return undefined
  const dateKey = shanghaiDateKey(Date.now())
  const value = toCalendarTimestamp(dateKey)
  const start = Number(chartData.value.window?.start) * 1000
  const end = Number(chartData.value.window?.end) * 1000
  if (!Number.isFinite(start) || !Number.isFinite(end) || value < start || value >= end) return undefined
  return {
    silent: true,
    symbol: ['none', 'none'],
    lineStyle: { color: 'rgba(255,255,255,0.5)', width: 1, type: 'solid' },
    label: {
      show: true, formatter: '今天', position: 'insideEndTop', rotate: 0, color: '#fff',
      backgroundColor: '#343b4d', borderRadius: 10, padding: [3, 9], fontWeight: 600,
    },
    data: [{ xAxis: dateKey }],
  }
}

const fullChartOption = () => {
  const recent = historyMode.value === 'recent24h'
  const monthly = !recent && selectedMonth.value !== 'all'
  const points = chartSeriesData()
  const values = points
    .map(point => recent ? point.value[1] : point.value)
    .filter(value => value !== null)
  const observedMax = values.length ? Math.max(...values) : 0
  const fallbackMax = observedMax <= 1 ? 1 : (observedMax <= 5 ? 5 : 20)
  const yRange = calcNiceYAxisRange(values, { min: 0, max: fallbackMax }, 5)
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const xMin = Number.isFinite(windowStart) ? windowStart : Date.now() - DAY
  const xMax = Number.isFinite(windowEnd) ? windowEnd - (recent ? 0 : DAY) : Date.now()
  const calendarDates = recent ? [] : (chartData.value.history || []).map(point => point?.date || '')
  const chartWidth = chartRef.value?.clientWidth || 1000
  const monthlyLabelStep = chartWidth < 400 ? 6 : (chartWidth < 700 ? 4 : 2)
  const [firstYear, firstMonth] = String(calendarDates[0] || '').split('-').map(Number)
  const firstMonthIndex = firstYear * 12 + firstMonth
  const calendarLabelInterval = (index, value) => {
    const day = Number(String(value).slice(-2))
    if (monthly) return index % monthlyLabelStep === 0
    if (day !== 1) return false
    if (chartWidth >= 480 || !Number.isFinite(firstMonthIndex)) return true
    const [year, month] = String(value).split('-').map(Number)
    return (year * 12 + month - firstMonthIndex) % 2 === 0
  }

  return {
    animation: true,
    animationDuration: 900,
    animationDurationUpdate: 650,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', confine: true, formatter: tooltipFormatter,
      backgroundColor: 'rgba(3, 8, 17, 0.96)', borderColor: 'rgba(88, 191, 255, 0.5)', borderWidth: 1,
      padding: [11, 13], textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(185, 208, 239, 0.56)', type: 'dashed' } },
    },
    grid: { left: 18, right: 22, bottom: monthly ? 34 : 18, top: 24, containLabel: true },
    xAxis: recent ? {
      type: 'time', min: xMin, max: xMax, interval: 3 * HOUR, minInterval: 3 * HOUR,
      axisLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.55)' } },
      axisTick: { show: true, lineStyle: { color: 'rgba(151, 177, 215, 0.45)' } },
      axisLabel: {
        color: '#aebdd1', margin: 11, hideOverlap: true, formatter: formatXAxisLabel,
        rich: {
          direction: { color: '#b7c6db', fontSize: 12, lineHeight: 16 },
          day: { color: '#a8b8ce', fontSize: 12, fontWeight: 700, lineHeight: 15 },
        },
      },
      splitLine: { show: false },
    } : {
      type: 'category', data: calendarDates, boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.55)' } },
      axisTick: { show: true, alignWithLabel: true, interval: calendarLabelInterval, lineStyle: { color: 'rgba(151, 177, 215, 0.45)' } },
      axisLabel: {
        color: '#aebdd1', margin: 11, interval: calendarLabelInterval, formatter: formatXAxisLabel,
        rich: {
          direction: { width: 38, align: 'center', color: '#b7c6db', fontSize: 12, lineHeight: 16 },
          day: { width: 38, align: 'center', color: '#a8b8ce', fontSize: 12, fontWeight: 700, lineHeight: 15 },
        },
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true, min: yRange.min, max: yRange.max, interval: yRange.interval,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#d4deec', margin: 12, formatter: value => `${value}\n公里/小时`, lineHeight: 17 },
      splitLine: { lineStyle: { color: 'rgba(187, 204, 229, 0.38)', width: 1 } },
    },
    series: [{
      id: 'wind-speed',
      name: recent ? '风速（30分钟平均）' : '每日平均风速',
      type: 'line',
      data: points,
      showSymbol: !recent && observedMax <= 1,
      showAllSymbol: false,
      symbol: 'circle',
      symbolSize: 7,
      smooth: monthly ? 0.36 : (recent ? 0.28 : 0.08),
      smoothMonotone: 'x',
      connectNulls: false,
      clip: true,
      z: 3,
      lineStyle: { color: '#72cdf9', width: observedMax <= 1 ? 2.2 : (monthly ? 1.8 : 1.35) },
      itemStyle: { color: '#76d4ff', borderColor: '#dff5ff', borderWidth: 1 },
      emphasis: { focus: 'series', scale: true },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(113, 198, 246, 0.58)' },
          { offset: 1, color: 'rgba(68, 119, 195, 0.14)' },
        ]),
      },
      markLine: currentDayMark(),
    }],
  }
}

const renderChart = () => {
  if (!isMounted || !chart || chart.isDisposed()) return
  chart.setOption(fullChartOption(), {
    notMerge: false,
    replaceMerge: ['xAxis', 'yAxis', 'series'],
    lazyUpdate: false,
  })
}

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption(fullChartOption(), true)
  resizeHandler = () => {
    if (resizeFrame != null) cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = null
      if (!chart || chart.isDisposed()) return
      chart.resize()
      renderChart()
    })
  }
  window.addEventListener('resize', resizeHandler)
}

onMounted(() => {
  isMounted = true
  const startup = createSensorDetailStartup({
    initChart,
    fetchRealtime: fetchData,
    loadInitialHistory: async () => loadTrends({ view: 'recent24h' }),
    renderHistory: renderChart,
    scheduleHistoryRefresh,
    preloadHistoryLater: preloadCalendarLater,
  })
  startup.start()
  timer = setInterval(fetchData, 3000)
  window.addEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
})

onUnmounted(() => {
  isMounted = false
  historyRequestSerial += 1
  if (timer) clearInterval(timer)
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  window.removeEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  if (resizeFrame != null) cancelAnimationFrame(resizeFrame)
  if (chart && !chart.isDisposed()) chart.dispose()
  chart = null
})
</script>

<style scoped>
.sensor-detail { padding: 0; overflow-x: hidden; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 14px 18px; background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 10px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-icon { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; background: #1a3a5a; border: 1px solid var(--border-color); }
.header-info h2 { font-size: 22px; color: var(--text-primary); margin-bottom: 0; }
.header-status { display: inline-flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; column-gap: 6px; row-gap: 2px; font-size: 16px; font-weight: 600; text-align: right; }
.header-comm { width: 100%; text-align: right; }
.header-status .dot { width: 10px; height: 10px; border-radius: 50%; }
.header-status.online { color: var(--success-color); }
.header-status.online .dot { background: var(--success-color); box-shadow: 0 0 6px var(--success-color); }
.header-status.offline { color: var(--danger-color); }
.header-status.offline .dot { background: var(--danger-color); box-shadow: 0 0 6px var(--danger-color); }
.header-comm { font-size: 11px; font-weight: 400; color: var(--text-secondary); margin-top: 4px; }

/* 上半部分: 指南针 + 数据卡片 并排 */
.top-row { display: flex; gap: 12px; margin-bottom: 10px; }
.compass-panel { flex: 0 0 280px; text-align: center; }
.data-strip-panel { flex: 1; display: flex; flex-direction: column; }

.data-panel { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; }
.panel-title { font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 8px; }

/* 指南针 */
.compass-wrapper { display: flex; justify-content: center; position: relative; }
.wind-compass {
  position: relative;
  width: 188px;
  height: 188px;
  border: 1px solid rgba(0, 216, 255, 0.18);
  border-radius: 50%;
  background:
    radial-gradient(circle at center, rgba(0, 216, 255, 0.07) 0 1px, transparent 2px),
    radial-gradient(circle at center, rgba(10, 31, 55, 0.45) 0 58%, rgba(10, 31, 55, 0.32) 59% 100%);
  box-shadow: inset 0 0 0 28px rgba(0, 216, 255, 0.025);
}
.wind-compass::before,
.wind-compass::after {
  content: "";
  position: absolute;
  inset: 20px;
  border-radius: 50%;
  pointer-events: none;
}
.wind-compass::before { border: 1px solid rgba(0, 216, 255, 0.10); }
.wind-compass::after { inset: 46px; border: 1px solid rgba(0, 216, 255, 0.08); }
.compass-axis {
  position: absolute;
  left: 50%;
  top: 50%;
  background: rgba(0, 216, 255, 0.10);
  transform: translate(-50%, -50%);
}
.axis-vertical { width: 1px; height: 132px; }
.axis-horizontal { width: 132px; height: 1px; }
.compass-label {
  position: absolute;
  z-index: 2;
  color: #9fc4df;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  transform: translate(-50%, -50%);
  white-space: nowrap;
}
.label-n { top: 12px; left: 50%; color: #00d8ff; }
.label-e { top: 50%; left: calc(100% - 12px); }
.label-s { top: calc(100% - 12px); left: 50%; }
.label-w { top: 50%; left: 12px; }
.compass-label-sub {
  color: rgba(159, 196, 223, 0.55);
  font-size: 10px;
  font-weight: 500;
}
.label-ne { top: 28%; left: 72%; }
.label-se { top: 72%; left: 72%; }
.label-sw { top: 72%; left: 28%; }
.label-nw { top: 28%; left: 28%; }
.compass-pointer {
  position: absolute;
  inset: 0;
  z-index: 3;
  transform-origin: 50% 50%;
  transition: transform 0.55s cubic-bezier(0.25, 0.1, 0.25, 1);
  pointer-events: none;
}
.compass-arrow {
  position: absolute;
  left: 50%;
  top: 22px;
  width: 2px;
  height: 68px;
  background: #00d8ff;
  border-radius: 2px;
  transform: translateX(-50%);
}
.compass-arrow::before {
  content: "";
  position: absolute;
  left: 50%;
  top: -9px;
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-bottom: 15px solid #00d8ff;
  transform: translateX(-50%);
}
.compass-arrow::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -5px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #00d8ff;
  transform: translateX(-50%);
}
.compass-center-info {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 4;
  min-width: 62px;
  padding: 7px 8px;
  border: 1px solid rgba(0, 216, 255, 0.14);
  border-radius: 8px;
  background: rgba(10, 31, 55, 0.72);
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}
.compass-dir {
  font-size: 18px;
  font-weight: 700;
  color: #00d8ff;
  line-height: 1.2;
}
.compass-angle {
  font-size: 13px;
  color: #9fc4df;
  font-family: "Consolas", "Monaco", monospace;
  margin-top: 2px;
}
.compass-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(0, 216, 255, 0.10);
  font-size: 12px;
  color: #9fc4df;
}

/* 实时数据横向指标条 */
/* 实时数据卡片 */
.wind-data-card { display: flex; align-items: stretch; gap: 0; flex: 1; }
.wind-core { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 14px; padding-right: 24px; }
.wind-speed-main { display: flex; align-items: baseline; gap: 6px; }
.wind-speed-num { font-size: 48px; font-weight: 800; color: var(--accent-color); font-family: "Consolas", "Monaco", monospace; line-height: 1; }
.wind-speed-unit { font-size: 16px; color: var(--text-secondary); font-weight: 500; }
.wind-level-bar { display: flex; flex-direction: column; gap: 4px; }
.wind-level-track { position: relative; height: 8px; background: linear-gradient(90deg, #67c23a 0%, #e6a23c 50%, #f56c6c 100%); border-radius: 4px; overflow: visible; }
.wind-level-cursor { position: absolute; top: -5px; width: 3px; height: 18px; background: #fff; border-radius: 2px; box-shadow: 0 0 6px rgba(255,255,255,0.7); transform: translateX(-50%); transition: left 0.6s ease; }
.wind-level-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); }
.wind-level-status { display: flex; justify-content: space-between; align-items: center; }
.wind-status-ref { font-size: 11px; color: var(--text-muted); }
.wind-status-val { font-size: 12px; font-weight: 500; }
.wind-status-val.status-ok { color: #67c23a; }
.wind-status-val.status-warn { color: #e6a23c; }
.wind-status-val.status-danger { color: #f56c6c; }
.wind-aux { display: flex; align-items: center; gap: 0; border-left: 1px solid rgba(0, 200, 255, 0.12); padding-left: 20px; }
.wind-aux-item { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 0 16px; }
.wind-aux-val { font-size: 22px; font-weight: 700; color: var(--text-primary); font-family: "Consolas", "Monaco", monospace; }
.wind-aux-label { font-size: 11px; color: var(--text-secondary); }
.wind-aux-divider { width: 1px; height: 36px; background: rgba(0, 200, 255, 0.1); }

/* 气象站式风速趋势 */
.history-panel {
  margin-top: 12px;
  padding: 0;
  overflow: hidden;
  border-color: rgba(84, 130, 202, 0.25);
  background:
    radial-gradient(circle at 100% 0%, rgba(50, 138, 210, 0.15), transparent 34%),
    linear-gradient(145deg, rgba(15, 31, 57, 0.98), rgba(10, 23, 43, 0.98));
  box-shadow: 0 14px 36px rgba(0, 8, 24, 0.18);
}
.history-panel-header {
  min-height: 66px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid rgba(124, 157, 207, 0.14);
}
.history-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; }
.history-heading .panel-title {
  display: block;
  margin: 0;
  padding: 0;
  border: 0;
  color: #f4f8ff;
  font-size: 22px;
  font-weight: 750;
  letter-spacing: 0.03em;
  text-shadow: 0 2px 14px rgba(74, 139, 255, 0.18);
}
.metric-switch {
  display: inline-flex;
  align-items: center;
  padding: 4px;
  border-radius: 10px;
  background: rgba(4, 15, 33, 0.44);
  border: 1px solid rgba(119, 153, 204, 0.13);
}
.metric-switch button {
  min-width: 86px;
  height: 32px;
  padding: 0 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  border-radius: 7px;
  color: #091426;
  background: linear-gradient(135deg, #ffd84a, #ffbc27);
  box-shadow: 0 4px 14px rgba(255, 190, 35, 0.24);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
}
.history-controls { display: flex; align-items: center; gap: 9px; }
.period-button {
  height: 34px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid rgba(120, 155, 211, 0.24);
  border-radius: 8px;
  background: rgba(33, 57, 94, 0.55);
  color: #a8bddb;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}
.period-button:hover { color: #fff; border-color: rgba(65, 147, 255, 0.6); }
.period-button.active {
  color: #fff;
  border-color: #378cff;
  background: linear-gradient(135deg, #1d70e8, #245ac4);
  box-shadow: 0 5px 16px rgba(20, 100, 230, 0.3);
}
.control-icon { font-size: 16px; line-height: 1; }
.calendar-controls {
  display: flex;
  gap: 7px;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: 9px;
  opacity: 0.72;
  transition: 0.2s ease;
}
.calendar-controls:hover,
.calendar-controls.active {
  opacity: 1;
  border-color: rgba(77, 141, 234, 0.28);
  background: rgba(26, 49, 83, 0.38);
}
.history-select.year-select { width: 112px; }
.history-select.month-select { width: 126px; }
.history-select :deep(.el-select__wrapper) {
  min-height: 28px;
  border: 0;
  border-radius: 7px;
  background: rgba(31, 53, 88, 0.82);
  box-shadow: 0 0 0 1px rgba(120, 155, 211, 0.18) inset;
}
.history-select :deep(.el-select__selected-item) { color: #dce9fa; font-size: 13px; }
.history-select :deep(.el-select__caret) { color: #91a8c9; }
.trend-shell { padding: 12px 18px 14px; }
.chart-wrap { position: relative; height: 310px; }
.history-chart-wrap { height: 392px; }
.chart-container { height: 100%; }
.chart-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(10, 25, 41, 0.8);
  border-radius: 8px;
  z-index: 10;
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(0, 200, 255, 0.2);
  border-top-color: #00e5ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-text {
  margin-top: 12px;
  color: #AECAF5;
  font-size: 14px;
}
.history-chart-wrap .chart-loading-overlay {
  background: rgba(8, 22, 43, 0.78);
  backdrop-filter: blur(3px);
}
.history-chart-wrap .chart-hint-overlay { background: rgba(8, 22, 43, 0.5); }
.chart-error-banner {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 9;
  max-width: calc(100% - 20px);
  padding: 7px 11px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 190, 82, 0.35);
  border-radius: 6px;
  background: rgba(66, 43, 17, 0.9);
  color: #ffd58a;
  font-size: 12px;
  line-height: 18px;
}
.chart-error-banner button,
.chart-retry-button {
  flex: 0 0 auto;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(255, 213, 138, 0.55);
  border-radius: 5px;
  background: rgba(255, 213, 138, 0.12);
  color: #ffe4b4;
  font: inherit;
  cursor: pointer;
}
.chart-error-banner button:hover,
.chart-retry-button:hover {
  border-color: rgba(255, 226, 174, 0.9);
  background: rgba(255, 213, 138, 0.2);
}
.chart-retry-button {
  margin-top: 12px;
}
.history-chart-wrap .loading-spinner {
  width: 34px;
  height: 34px;
  border-color: rgba(55, 140, 255, 0.18);
  border-top-color: #438fff;
}

@media (max-width: 900px) {
  .history-panel-header { align-items: flex-start; flex-wrap: wrap; }
  .history-controls { width: 100%; flex-wrap: wrap; }
  .history-chart-wrap { height: 340px; }
}

@media (max-width: 1200px) {
  .top-row { flex-direction: column; }
  .compass-panel { flex-basis: auto; }
}

@media (max-width: 700px) {
  .detail-header { align-items: stretch; flex-direction: column; gap: 8px; }
  .header-info h2 { font-size: 18px; }
  .header-status { font-size: 14px; }
  .wind-data-card { flex-direction: column; }
  .wind-core { padding-right: 0; }
  .wind-aux {
    justify-content: space-between;
    margin-top: 18px;
    padding: 16px 0 0;
    border-top: 1px solid rgba(0, 200, 255, 0.12);
    border-left: 0;
  }
  .wind-aux-item { min-width: 0; padding: 0 6px; }
  .wind-aux-val { font-size: 18px; white-space: nowrap; }
  .wind-aux-label { white-space: nowrap; }
}

@media (max-width: 560px) {
  .history-heading { width: 100%; align-items: flex-start; flex-direction: column; gap: 12px; }
  .calendar-controls { width: 100%; }
  .history-select.year-select, .history-select.month-select { flex: 1; width: auto; }
}
</style>
