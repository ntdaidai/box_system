<template>
  <div class="vibration-monitor sensor-detail" :class="{ 'alert-flash': isAlertFlashing }">
    <div class="detail-header">
      <div class="header-left">
        <img src="@/assets/images/sensors/vibration.png" class="header-icon" />
        <div class="header-info">
          <h2>振动监测系统</h2>
          <div class="header-subtitle">库坝振动实时监测与分析</div>
        </div>
      </div>
      <div class="header-status" :class="statusClass">
        <span class="dot"></span>{{ statusText }}
        <div class="header-comm" v-if="lastTimestamp">最后通讯: {{ formatCommTime(lastTimestamp) }}</div>
      </div>
    </div>

    <div class="indicator-section">
      <div class="indicator-cards">
        <div class="indicator-card" :class="rmsStatusClass">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 12h2l3-9 4 18 4-18 3 9h4"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-value">{{ formatValue(processedData.total_rms, 3) }}</div>
            <div class="card-unit">g</div>
          </div>
          <div class="card-label">综合振动烈度</div>
          <div class="card-desc">三轴加速度合成后的RMS值</div>
          <div class="card-threshold">
            <span class="threshold-normal">&lt; 0.05 正常</span>
            <span class="threshold-warn">0.10 预警</span>
            <span class="threshold-alarm">0.15 报警</span>
          </div>
        </div>

        <div class="indicator-card" :class="freqStatusClass">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-value">{{ formatValue(processedData.dominant_freq, 1) }}</div>
            <div class="card-unit">Hz</div>
          </div>
          <div class="card-drift" :class="driftClass">
            <span class="drift-arrow">{{ freqDriftArrow }}</span>
            {{ formatDrift(processedData.freq_drift_percent) }}
          </div>
          <div class="card-label">当前主频</div>
          <div class="card-desc">FFT分析1-20Hz范围内主频</div>
        </div>

        <div class="indicator-card status-card">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <div class="status-lights">
            <div class="light" :class="{ active: processedData.alert_level === '正常' }">
              <span class="light-dot"></span>
              <span class="light-label">正常</span>
            </div>
            <div class="light" :class="{ active: processedData.alert_level === '关注' }">
              <span class="light-dot"></span>
              <span class="light-label">关注</span>
            </div>
            <div class="light" :class="{ active: processedData.alert_level === '预警' }">
              <span class="light-dot"></span>
              <span class="light-label">预警</span>
            </div>
            <div class="light" :class="{ active: processedData.alert_level === '报警' }">
              <span class="light-dot"></span>
              <span class="light-label">报警</span>
            </div>
          </div>
          <div class="card-label">运行状态</div>
          <div class="card-desc">基于RMS和主频偏移综合判断</div>
        </div>

        <div class="indicator-card" :class="crestStatusClass">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-value">{{ formatValue(processedData.crest_factor, 1) }}</div>
            <div class="card-unit">-</div>
          </div>
          <div class="card-label">峰值因子</div>
          <div class="card-desc">峰值/RMS，>3.5表示冲击信号</div>
        </div>
      </div>
    </div>

    <div class="data-panel history-panel">
      <div class="history-panel-header">
        <div class="history-heading">
          <span class="panel-title">振动趋势</span>
          <div class="metric-switch" aria-label="振动指标">
            <button type="button" class="active"><span>≈</span>RMS</button>
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
                :label="`${year}年`"
                :value="year"
              />
            </el-select>
            <el-select v-model="selectedMonth" class="history-select month-select" @change="onMonthChange">
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
          <div ref="chartRef" class="chart-container"></div>
          <div v-if="historyError && !historyEmpty" class="chart-error-banner">
            <span>{{ historyError }}，当前显示上一次成功加载的数据</span>
            <button type="button" @click="retryHistory">重试</button>
          </div>
          <div v-if="historyLoading" class="chart-loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">正在读取振动 RMS 数据...</div>
          </div>
          <div v-else-if="historyError && historyEmpty" class="chart-loading-overlay">
            <div class="loading-text">{{ historyError }}</div>
            <button type="button" class="chart-retry-button" @click="retryHistory">重新加载</button>
          </div>
          <div v-else-if="historyEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">该时间范围暂无振动 RMS 数据</div>
          </div>
        </div>

        <div class="series-toggles">
          <span class="series-plain">
            <i></i>综合振动烈度 RMS
          </span>
          <label class="series-toggle warning">
            <input v-model="thresholdVisibility.warning" type="checkbox" @change="renderChart" />
            <span class="checkbox-ui"></span>
            <i></i>预警线 0.10g
          </label>
          <label class="series-toggle alarm">
            <input v-model="thresholdVisibility.alarm" type="checkbox" @change="renderChart" />
            <span class="checkbox-ui"></span>
            <i></i>报警线 0.15g
          </label>
        </div>
      </div>
    </div>

    <div v-if="showAlertBanner" class="alert-banner" :class="'alert-' + processedData.alert_level">
      <div class="alert-icon">!</div>
      <div class="alert-content">
        <div class="alert-level">{{ processedData.alert_level }}</div>
        <div class="alert-reason">{{ processedData.alert_reason }}</div>
      </div>
      <button class="alert-close" @click="dismissAlert">×</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { getVibrationHistoryTrends, getVibrationProcessed } from '@/api/sensor'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, runWhenIdle } from '@/utils/sensorDetailStartup'
import * as echarts from 'echarts'

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const TREND_URL = '/v1/sensor/history/vibration/trends'
const WARNING_RMS = 0.10
const ALARM_RMS = 0.15

const shanghaiDateKey = (value) => {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(value))
  const get = type => parts.find(part => part.type === type)?.value || ''
  return `${get('year')}-${get('month')}-${get('day')}`
}

const initialShanghaiYear = Number(shanghaiDateKey(Date.now()).slice(0, 4))

const processedData = reactive({
  total_rms: null,
  dominant_freq: null,
  freq_drift_percent: null,
  crest_factor: null,
  peak_accel: null,
  temperature: null,
  alert_level: '正常',
  alert_reason: '',
})

const chartRef = ref(null)
const lastTimestamp = ref(0)
const statusClass = ref('online')
const statusText = ref('在线')
const historyMode = ref('recent24h')
const selectedYear = ref(initialShanghaiYear)
const selectedMonth = ref('all')
const availablePeriods = ref([])
const showAlertBanner = ref(false)
const isAlertFlashing = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'recent24h', history: [], window: null })
const thresholdVisibility = reactive({ warning: true, alarm: true })
const historyCache = new Map()

let chart = null
let realtimeTimer = null
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
  return years.length ? [...new Set(years)].sort((a, b) => b - a) : [initialShanghaiYear]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  if (!period) return Array.from({ length: 12 }, (_, index) => index + 1)
  return (period.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const chartValues = computed(() => (chartData.value.history || [])
  .map(point => toNumber(point?.data?.rms))
  .filter(value => value !== null))

const historyEmpty = computed(() => chartValues.value.length === 0)

const rmsStatusClass = computed(() => {
  const rms = processedData.total_rms
  if (rms === null) return 'status-unknown'
  if (rms >= ALARM_RMS) return 'status-alarm'
  if (rms >= WARNING_RMS) return 'status-warning'
  if (rms >= 0.05) return 'status-attention'
  return 'status-normal'
})

const freqStatusClass = computed(() => {
  const drift = Math.abs(processedData.freq_drift_percent || 0)
  return drift > 15 ? 'status-alarm' : 'status-normal'
})

const crestStatusClass = computed(() => {
  const cf = processedData.crest_factor
  if (cf === null) return 'status-unknown'
  return cf > 3.5 ? 'status-warning' : 'status-normal'
})

const driftClass = computed(() => {
  const drift = processedData.freq_drift_percent
  if (drift === null) return ''
  if (Math.abs(drift) > 15) return 'drift-alarm'
  if (Math.abs(drift) > 10) return 'drift-warning'
  return 'drift-normal'
})

const freqDriftArrow = computed(() => {
  const drift = processedData.freq_drift_percent
  if (drift === null) return ''
  if (drift > 0) return '↑'
  if (drift < 0) return '↓'
  return '→'
})

const toNumber = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatValue = (value, decimals) => {
  const numeric = toNumber(value)
  return numeric === null ? '--' : numeric.toFixed(decimals)
}

const formatDrift = (drift) => {
  const numeric = toNumber(drift)
  if (numeric === null) return '--'
  const sign = numeric >= 0 ? '+' : ''
  return `${sign}${numeric.toFixed(1)}%`
}

const formatCommTime = (ts) => {
  const numeric = Number(ts)
  if (!Number.isFinite(numeric) || numeric <= 0) return '--'
  const timeMs = numeric > 1e12 ? numeric : numeric * 1000
  return new Date(timeMs).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

const fetchProcessedData = async () => {
  try {
    const result = await getVibrationProcessed()
    if (result.code === 200 && result.data) {
      const data = result.data.data || result.data
      Object.assign(processedData, data)
      lastTimestamp.value = result.data.timestamp || Date.now() / 1000
      statusClass.value = result.data.mock ? 'offline' : 'online'
      statusText.value = result.data.mock ? '离线（模拟数据）' : '在线'

      if (data.alert_level === '报警' || data.alert_level === '预警') {
        isAlertFlashing.value = true
        showAlertBanner.value = true
      } else {
        isAlertFlashing.value = false
      }
    }
  } catch (error) {
    console.error('获取处理数据失败:', error)
    statusClass.value = 'offline'
    statusText.value = '连接失败'
  }
}

const queryKey = ({ view, year, month }) => [view, year || '', month || 'all'].join(':')

const currentQuery = () => historyMode.value === 'recent24h'
  ? { view: 'recent24h' }
  : {
      view: 'calendar',
      year: Number(selectedYear.value),
      month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
    }

const historyCacheMaxAge = query => query.view === 'recent24h' ? 5 * MINUTE : 30 * MINUTE

const readHistoryCache = (query) => {
  const key = queryKey(query)
  const cached = historyCache.get(key)
  if (!cached) return null
  if (Date.now() - cached.updatedAt <= historyCacheMaxAge(query)) return cached.payload
  historyCache.delete(key)
  return null
}

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
  if (!periods.some(item => Number(item.year) === Number(selectedYear.value))) {
    selectedYear.value = Number(periods[0].year)
    selectedMonth.value = 'all'
    return
  }
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
}

const applyTrendPayload = (payload, query, apply = true, cacheResult = true) => {
  if (!payload) return null
  syncAvailablePeriods(payload.available_periods)
  const normalized = { ...payload, history: Array.isArray(payload.history) ? payload.history : [] }
  if (cacheResult) historyCache.set(queryKey(query), { payload: normalized, updatedAt: Date.now() })
  if (apply && queryKey(query) === queryKey(currentQuery())) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadTrends = async (query = currentQuery(), apply = true, force = false) => {
  const key = queryKey(query)
  const requestId = apply ? ++historyRequestSerial : 0
  const isCurrentRequest = () => !apply || (
    isMounted &&
    requestId === historyRequestSerial &&
    key === queryKey(currentQuery())
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
    const res = await getVibrationHistoryTrends(query)
    if (res.code !== 200 || !res.data || !Array.isArray(res.data.history)) {
      throw new Error('振动趋势响应无效')
    }
    const shouldApply = apply && isCurrentRequest()
    const normalized = applyTrendPayload(res.data, query, shouldApply)
    return { payload: normalized, applied: shouldApply, error: false }
  } catch (error) {
    console.warn('加载振动趋势失败:', error)
    const currentError = apply && isCurrentRequest()
    if (currentError) historyError.value = '历史数据服务暂时不可用，请稍后重试'
    return { payload: null, applied: false, error: currentError }
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
  if (shouldApply) renderChart()
}

const preloadCalendarLater = () => {
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  preloadIdleTask = runWhenIdle(() => {
    preloadIdleTask = null
    loadTrends({ view: 'calendar', year: Number(selectedYear.value), month: null }, false)
  }, 1200)
}

const millisecondsToNextHalfHour = () => {
  const now = Date.now()
  const interval = 30 * MINUTE
  return Math.floor(now / interval) * interval + interval - now
}

const restoreSelectionFromChart = () => {
  if (chartData.value.view === 'recent24h') {
    historyMode.value = 'recent24h'
    return
  }
  historyMode.value = 'calendar'
  selectedYear.value = Number(chartData.value.year) || initialShanghaiYear
  selectedMonth.value = Number.isInteger(Number(chartData.value.month)) ? Number(chartData.value.month) : 'all'
}

const finishHistorySelection = (query, result) => {
  if (!isMounted || queryKey(query) !== queryKey(currentQuery())) return
  if (!result?.applied && !result?.error) return
  if (result?.error) restoreSelectionFromChart()
  renderChart()
  scheduleHistoryRefresh()
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (!isMounted) return
  const delay = historyMode.value === 'recent24h' ? millisecondsToNextHalfHour() + 1000 : 30 * MINUTE
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

const chartSeriesData = () => {
  if (chartData.value.view === 'recent24h') {
    return (chartData.value.history || []).map(point => [
      Number(point.timestamp) * 1000,
      toNumber(point.data?.rms),
    ])
  }
  return (chartData.value.history || []).map(point => [
    new Date(`${point.date}T00:00:00+08:00`).getTime(),
    toNumber(point.data?.rms),
  ])
}

const formatXAxisLabel = (value) => {
  const dateValue = new Date(value)
  if (historyMode.value === 'recent24h') {
    return dateValue.toLocaleTimeString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  if (selectedMonth.value === 'all') {
    return dateValue.toLocaleDateString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: 'numeric',
      day: 'numeric',
    })
  }
  return `${dateValue.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', day: 'numeric' })}日`
}

const escapeTooltipHtml = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character])

const tooltipFormatter = (params) => {
  const item = (Array.isArray(params) ? params : [params]).find(entry => entry.value?.[1] != null)
  if (!item) return ''
  const dateValue = new Date(item.value[0])
  const heading = historyMode.value === 'recent24h'
    ? dateValue.toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : dateValue.toLocaleDateString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
  return `<div style="min-width:170px"><strong>${escapeTooltipHtml(heading)}</strong>`
    + `<div style="display:flex;justify-content:space-between;gap:24px;margin-top:8px">`
    + `<span>${item.marker}RMS</span><strong>${Number(item.value[1]).toFixed(4)} g</strong></div></div>`
}

const thresholdMarkLines = () => {
  const data = []
  if (thresholdVisibility.warning) {
    data.push({
      yAxis: WARNING_RMS,
      name: '预警线',
      lineStyle: { color: '#e6a23c', width: 1.4, type: 'dashed' },
      label: { show: true, formatter: '预警 0.10g', color: '#e6a23c', position: 'insideEndTop' },
    })
  }
  if (thresholdVisibility.alarm) {
    data.push({
      yAxis: ALARM_RMS,
      name: '报警线',
      lineStyle: { color: '#f56c6c', width: 1.4, type: 'dashed' },
      label: { show: true, formatter: '报警 0.15g', color: '#f56c6c', position: 'insideEndTop' },
    })
  }
  return data
}

const fullChartOption = () => {
  const recent = historyMode.value === 'recent24h'
  const points = chartSeriesData()
  const values = points.map(point => point[1]).filter(value => value !== null)
  const thresholdValues = [
    thresholdVisibility.warning ? WARNING_RMS : null,
    thresholdVisibility.alarm ? ALARM_RMS : null,
  ].filter(value => value !== null)
  const yRange = calcNiceYAxisRange([...values, ...thresholdValues], { min: 0, max: 0.2 }, 5)
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const xMin = Number.isFinite(windowStart) && recent ? windowStart : (points[0]?.[0] ?? Date.now() - DAY)
  const xMax = Number.isFinite(windowEnd) && recent ? windowEnd : (points.at(-1)?.[0] ?? Date.now())
  const tickInterval = recent ? 3 * HOUR : (selectedMonth.value === 'all' ? 30 * DAY : 5 * DAY)

  return {
    animation: true,
    animationDuration: 900,
    animationDurationUpdate: 650,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)',
      borderColor: 'rgba(89, 155, 255, 0.55)',
      borderWidth: 1,
      padding: [11, 13],
      textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(151, 190, 255, 0.55)', type: 'dashed' } },
    },
    grid: { left: 18, right: 22, bottom: 18, top: 28, containLabel: true },
    xAxis: {
      type: 'time',
      min: xMin,
      max: xMax,
      interval: tickInterval,
      minInterval: recent ? 30 * MINUTE : DAY,
      axisLine: { lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisTick: { show: true, lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisLabel: { color: '#91a9ca', margin: 12, hideOverlap: true, formatter: formatXAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yRange.min,
      max: yRange.max,
      interval: yRange.interval,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#b6c7df', margin: 12, formatter: value => `${Number(value).toFixed(2)}g` },
      splitLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.18)', width: 1 } },
    },
    series: [{
      id: 'vibration-rms',
      name: '综合振动烈度 RMS',
      type: 'line',
      data: points,
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 6,
      smooth: recent ? 0.32 : 0.16,
      smoothMonotone: 'x',
      connectNulls: false,
      clip: true,
      z: 3,
      lineStyle: { color: '#20d7ff', width: recent ? 2.4 : 1.8 },
      itemStyle: { color: '#20d7ff', borderColor: '#ffffff', borderWidth: 1 },
      emphasis: { focus: 'series', scale: true },
      universalTransition: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(32, 215, 255, 0.24)' },
          { offset: 1, color: 'rgba(32, 215, 255, 0)' },
        ]),
      },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        data: thresholdMarkLines(),
      },
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

const dismissAlert = () => {
  showAlertBanner.value = false
}

onMounted(() => {
  isMounted = true
  const startup = createSensorDetailStartup({
    initChart,
    fetchRealtime: fetchProcessedData,
    loadInitialHistory: async () => loadTrends({ view: 'recent24h' }),
    renderHistory: renderChart,
    scheduleHistoryRefresh,
    preloadHistoryLater: preloadCalendarLater,
  })
  startup.start()

  realtimeTimer = setInterval(fetchProcessedData, 5000)
  window.addEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
})

onUnmounted(() => {
  isMounted = false
  historyRequestSerial += 1
  if (realtimeTimer) clearInterval(realtimeTimer)
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
.vibration-monitor {
  padding: 16px;
  min-height: 100vh;
  color: #e0e8f0;
  position: relative;
}

.vibration-monitor.alert-flash {
  animation: alertFlash 1s infinite;
}

@keyframes alertFlash {
  0%, 100% { background: transparent; }
  50% { background: rgba(120, 16, 16, 0.18); }
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  background: #1a3a5a;
  border: 1px solid var(--border-color);
}

.header-info h2 {
  font-size: 22px;
  color: var(--text-primary);
  margin: 0;
  font-weight: 600;
}

.header-subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.header-status {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  column-gap: 6px;
  row-gap: 2px;
  font-size: 16px;
  font-weight: 600;
  text-align: right;
}

.header-status .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.header-status.online {
  color: var(--success-color);
}

.header-status.online .dot {
  background: var(--success-color);
  box-shadow: 0 0 6px var(--success-color);
}

.header-status.offline {
  color: var(--danger-color);
}

.header-status.offline .dot {
  background: var(--danger-color);
  box-shadow: 0 0 6px var(--danger-color);
}

.header-comm {
  width: 100%;
  margin-top: 4px;
  text-align: right;
  font-size: 11px;
  font-weight: 400;
  color: var(--text-secondary);
}

.indicator-section {
  margin-bottom: 16px;
}

.indicator-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.indicator-card {
  min-width: 0;
  min-height: 164px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 20px;
  position: relative;
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.indicator-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.22);
}

.indicator-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.indicator-card.status-normal::before { background: #67c23a; }
.indicator-card.status-attention::before { background: #e6a23c; }
.indicator-card.status-warning::before { background: #f56c6c; }
.indicator-card.status-alarm::before { background: #ff0000; animation: alarmPulse 1s infinite; }

@keyframes alarmPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.card-icon {
  width: 40px;
  height: 40px;
  margin-bottom: 12px;
  color: #00e5ff;
}

.card-icon svg {
  width: 100%;
  height: 100%;
}

.card-content {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.card-value {
  font-size: 36px;
  font-weight: 700;
  font-family: "Consolas", "Monaco", monospace;
  color: #ffffff;
  line-height: 1;
}

.card-unit {
  font-size: 18px;
  color: #8aa8c7;
  font-weight: 500;
}

.card-drift {
  font-size: 14px;
  margin-bottom: 8px;
  font-weight: 500;
}

.card-drift.drift-normal { color: #67c23a; }
.card-drift.drift-warning { color: #e6a23c; }
.card-drift.drift-alarm { color: #f56c6c; }

.drift-arrow {
  font-size: 16px;
}

.card-label {
  font-size: 14px;
  color: #8aa8c7;
  margin-bottom: 4px;
}

.card-desc {
  font-size: 11px;
  color: #6a8aa7;
  margin-bottom: 8px;
}

.card-threshold {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10px;
}

.threshold-normal { color: #67c23a; }
.threshold-warn { color: #e6a23c; }
.threshold-alarm { color: #f56c6c; }

.status-card .status-lights {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.light {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0.5;
  transition: 0.25s ease;
}

.light.active {
  opacity: 1;
  background: rgba(0, 100, 200, 0.3);
}

.light-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #555;
}

.light.active .light-dot {
  box-shadow: 0 0 10px currentColor;
}

.light:nth-child(1) .light-dot { background: #67c23a; }
.light:nth-child(2) .light-dot { background: #e6a23c; }
.light:nth-child(3) .light-dot { background: #f56c6c; }
.light:nth-child(4) .light-dot { background: #ff0000; }

.light.active:nth-child(1) { color: #67c23a; }
.light.active:nth-child(2) { color: #e6a23c; }
.light.active:nth-child(3) { color: #f56c6c; }
.light.active:nth-child(4) { color: #ff0000; }

.light-label {
  font-size: 14px;
  font-weight: 500;
}

.data-panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 12px;
}

.history-panel {
  margin-top: 12px;
  padding: 0;
  overflow: hidden;
  border-color: rgba(84, 130, 202, 0.25);
  background:
    radial-gradient(circle at 100% 0%, rgba(50, 105, 200, 0.13), transparent 34%),
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

.history-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

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
  border: 1px solid rgba(119, 153, 204, 0.13);
  border-radius: 10px;
  background: rgba(4, 15, 33, 0.44);
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

.history-controls {
  display: flex;
  align-items: center;
  gap: 9px;
}

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

.period-button:hover {
  color: #fff;
  border-color: rgba(65, 147, 255, 0.6);
}

.period-button.active {
  color: #fff;
  border-color: #378cff;
  background: linear-gradient(135deg, #1d70e8, #245ac4);
  box-shadow: 0 5px 16px rgba(20, 100, 230, 0.3);
}

.control-icon {
  font-size: 16px;
  line-height: 1;
}

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

.trend-shell {
  padding: 12px 18px 14px;
}

.chart-wrap {
  position: relative;
}

.history-chart-wrap {
  height: 392px;
}

.chart-container {
  height: 100%;
}

.chart-loading-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(8, 22, 43, 0.78);
  backdrop-filter: blur(3px);
}

.chart-hint-overlay {
  background: rgba(8, 22, 43, 0.5);
}

.loading-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(55, 140, 255, 0.18);
  border-top-color: #438fff;
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

.series-toggles {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 4px 10px 0;
  border-top: 1px solid rgba(123, 154, 201, 0.1);
}

.series-plain,
.series-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #b7cae4;
  font-size: 12px;
  user-select: none;
}

.series-toggle {
  cursor: pointer;
}

.series-toggle input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.checkbox-ui {
  width: 15px;
  height: 15px;
  display: inline-grid;
  place-items: center;
  border-radius: 4px;
  border: 1px solid rgba(147, 174, 215, 0.6);
  background: rgba(5, 15, 32, 0.55);
  transition: 0.18s ease;
}

.series-toggle input:checked + .checkbox-ui {
  border-color: #2d8cff;
  background: #247ee8;
}

.series-toggle input:checked + .checkbox-ui::after {
  content: '✓';
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.series-plain i,
.series-toggle i {
  width: 18px;
  height: 3px;
  border-radius: 999px;
  background: #20d7ff;
  box-shadow: 0 0 8px rgba(32, 215, 255, 0.4);
}

.series-toggle.warning i {
  background: #e6a23c;
  box-shadow: 0 0 8px rgba(230, 162, 60, 0.35);
}

.series-toggle.alarm i {
  background: #f56c6c;
  box-shadow: 0 0 8px rgba(245, 108, 108, 0.35);
}

.status-unknown {
  opacity: 0.6;
}

.alert-banner {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  max-width: 400px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  backdrop-filter: blur(10px);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.alert-banner.alert-预警 {
  background: rgba(245, 108, 108, 0.9);
  border: 2px solid #f56c6c;
}

.alert-banner.alert-报警 {
  background: rgba(255, 0, 0, 0.9);
  border: 2px solid #ff0000;
  animation: slideIn 0.3s ease, alarmBanner 1s infinite;
}

@keyframes alarmBanner {
  0%, 100% { box-shadow: 0 0 20px rgba(255, 0, 0, 0.5); }
  50% { box-shadow: 0 0 40px rgba(255, 0, 0, 0.8); }
}

.alert-icon {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  font-size: 16px;
  font-weight: 800;
}

.alert-content {
  flex: 1;
}

.alert-level {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 4px;
}

.alert-reason {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.alert-close {
  width: 30px;
  height: 30px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: none;
  color: #ffffff;
  font-size: 24px;
  cursor: pointer;
  transition: background 0.3s ease;
}

.alert-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

@media (max-width: 1200px) {
  .indicator-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .history-panel-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .history-controls {
    width: 100%;
    flex-wrap: wrap;
  }

  .history-chart-wrap {
    height: 340px;
  }
}

@media (max-width: 768px) {
  .indicator-cards {
    grid-template-columns: 1fr;
  }

  .detail-header {
    flex-direction: column;
    gap: 12px;
    text-align: center;
  }

  .header-left {
    flex-direction: column;
  }

  .alert-banner {
    left: 20px;
    right: 20px;
    max-width: none;
  }
}

@media (max-width: 560px) {
  .history-heading {
    width: 100%;
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .calendar-controls {
    width: 100%;
  }

  .history-select.year-select,
  .history-select.month-select {
    flex: 1;
    width: auto;
  }

  .series-toggles {
    gap: 14px;
    flex-wrap: wrap;
  }
}
</style>
