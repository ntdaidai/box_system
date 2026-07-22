<template>
  <div class="sensor-detail">
    <div class="detail-header">
      <div class="header-left">
        <img src="@/assets/images/sensors/rain.png" class="header-icon" />
        <div class="header-info">
          <h2>雨量计</h2>
        </div>
      </div>
      <div class="header-status" :class="statusClass">
        <span class="dot"></span>{{ statusText }}
        <div class="header-comm" v-if="lastTimestamp">{{ formatCommTime(lastTimestamp) }}</div>
      </div>
    </div>

    <!-- 实时数据卡片 -->
    <div class="data-panel">
      <div class="panel-title">实时数据</div>
      <div class="rain-data-card">
        <!-- 核心防汛区 -->
        <div class="rain-core">
          <div class="rain-main-row">
            <div class="rain-main-item">
              <div class="rain-main-label">瞬时雨量</div>
              <div class="rain-main-val">{{ data.instant_rain != null ? data.instant_rain.toFixed(1) : '--' }}<span class="rain-main-unit">mm</span></div>
            </div>
            <div class="rain-main-divider"></div>
            <div class="rain-main-item">
              <div class="rain-main-label">小时雨量</div>
              <div class="rain-main-val">{{ data.hour_rain != null ? data.hour_rain.toFixed(1) : '--' }}<span class="rain-main-unit">mm</span></div>
            </div>
            <div class="rain-main-divider"></div>
            <div class="rain-main-item">
              <div class="rain-main-label">当天雨量</div>
              <div class="rain-main-val">{{ data.today_rain != null ? data.today_rain.toFixed(1) : '--' }}<span class="rain-main-unit">mm</span></div>
            </div>
          </div>
          <!-- 气象预警条 -->
          <div class="rain-warn-bar">
            <div class="rain-warn-track">
              <div class="rain-warn-cursor" :style="{ left: rainWarnPosition + '%' }"></div>
            </div>
            <div class="rain-warn-info">
              <span class="rain-warn-status" :class="rainWarnClass">状态：{{ rainWarnText }}</span>
              <span class="rain-warn-ref">参考阈值：25mm（瞬时雨量）</span>
            </div>
          </div>
        </div>
        <div class="rain-yesterday-card">
          <div class="rain-yesterday-head">
            <span>{{ yesterdayDayLabel }}</span>
            <span>昨天</span>
          </div>
          <div class="rain-yesterday-value">
            {{ data.yesterday_rain != null ? data.yesterday_rain.toFixed(1) : '--' }}<span>毫米</span>
          </div>
          <div class="rain-yesterday-foot">
            <el-icon><Pouring /></el-icon>
            <span>{{ yesterdayRainLevel }}</span>
          </div>
          <div class="rain-yesterday-track">
            <div class="rain-yesterday-fill" :style="{ height: yesterdayRainPosition + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 雨量历史 -->
    <div class="data-panel history-panel">
      <div class="history-panel-header">
        <div class="history-heading">
          <span class="panel-title">雨量趋势</span>
          <div class="metric-switch" aria-label="雨量指标">
            <button type="button" class="active"><el-icon><Pouring /></el-icon>雨量</button>
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
            <div class="loading-text">正在读取雨量数据...</div>
          </div>
          <div v-else-if="historyError && historyEmpty" class="chart-loading-overlay">
            <div class="loading-text">{{ historyError }}</div>
            <button type="button" class="chart-retry-button" @click="retryHistory">重新加载</button>
          </div>
          <div v-else-if="historyEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">该时间范围暂无雨量数据</div>
          </div>
        </div>

        <div class="rain-series-legend">
          <i></i>
          <span>{{ historyLegendLabel }}</span>
          <i class="zero-marker"></i>
          <span>0 mm</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getRainTrends, getSensorRealtime } from '@/api/sensor'
import {
  buildRainChartValues,
  rainBarMinHeight,
  rainLegendLabel,
  toRainNumber,
} from '@/utils/rainHistory'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, runWhenIdle } from '@/utils/sensorDetailStartup'
import { Pouring } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const TREND_URL = '/v1/sensor/history/rain/trends'
const shanghaiDateKey = (value) => {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date(value))
  const get = type => parts.find(part => part.type === type)?.value || ''
  return `${get('year')}-${get('month')}-${get('day')}`
}
const initialShanghaiYear = Number(shanghaiDateKey(Date.now()).slice(0, 4))

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const historyMode = ref('recent24h')
const selectedYear = ref(initialShanghaiYear)
const selectedMonth = ref('all')
const availablePeriods = ref([])
const lastTimestamp = ref(0)
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
  return (period?.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const historyValues = computed(() => buildRainChartValues(
  chartData.value.history || [],
  chartData.value.view,
).filter(value => value !== null))
const historyEmpty = computed(() => historyValues.value.length === 0)
const historyLegendLabel = computed(() => rainLegendLabel(chartData.value.view))

// 防汛预警条（0-100mm 映射）
const rainWarnPosition = computed(() => {
  const v = Number(data.value.instant_rain) || 0
  return Math.max(0, Math.min(100, (v / 100) * 100))
})
const rainWarnText = computed(() => {
  const v = Number(data.value.instant_rain) || 0
  if (v < 10) return '小雨（安全）'
  if (v < 25) return '中雨（注意）'
  if (v < 50) return '大雨（警惕）'
  return '暴雨（危险）'
})
const rainWarnClass = computed(() => {
  const v = Number(data.value.instant_rain) || 0
  if (v < 25) return 'rw-ok'
  if (v < 50) return 'rw-warn'
  return 'rw-danger'
})
const yesterdayDayLabel = computed(() => {
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return `${yesterday.getMonth() + 1}/${yesterday.getDate()}`
})
const yesterdayRainLevel = computed(() => {
  const v = Number(data.value.yesterday_rain)
  if (!Number.isFinite(v)) return '--'
  if (v <= 0) return '无雨'
  if (v < 10) return '小雨'
  if (v < 25) return '中雨'
  if (v < 50) return '大雨'
  return '暴雨'
})
const yesterdayRainPosition = computed(() => {
  const v = Number(data.value.yesterday_rain) || 0
  return Math.max(12, Math.min(100, (v / 50) * 100))
})

const formatCommTime = (ts) => {
  if (!ts) return '--'
  const date = new Date(ts * 1000)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
}

const fetchData = async () => {
  try {
    const res = await getSensorRealtime('rain')
    if (res.code === 200 && res.data?.data) {
      const d = res.data.data
      data.value = d
      lastTimestamp.value = res.data.timestamp || lastTimestamp.value
      statusClass.value = res.data.mock ? 'offline' : 'online'; statusText.value = res.data.mock ? '离线' : '在线'
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
  if (Array.isArray(periods) && periods.length) availablePeriods.value = periods
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
    isMounted && requestId === historyRequestSerial && key === queryKey(currentQuery())
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
    const res = await getRainTrends(query)
    if (res.code !== 200 || !res.data || !Array.isArray(res.data.history)) {
      throw new Error('雨量趋势响应无效')
    }
    const shouldApply = apply && isCurrentRequest()
    const normalized = applyTrendPayload(res.data, query, shouldApply)
    return { payload: normalized, applied: shouldApply, error: false }
  } catch (error) {
    console.warn('加载雨量趋势失败:', error)
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
  const interval = 30 * MINUTE
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
  if (result.error) restoreSelectionFromChart()
  renderChart()
  scheduleHistoryRefresh()
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (!isMounted) return
  const delay = historyMode.value === 'recent24h'
    ? millisecondsToNextHalfHour() + 1000
    : 30 * MINUTE
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

const chartSeriesData = () => {
  const recent = chartData.value.view === 'recent24h'
  return (chartData.value.history || []).map(point => {
    const value = toRainNumber(point?.data?.[recent ? 'rain_increment' : 'daily_rain'])
    return {
      value: recent ? [Number(point.timestamp) * 1000, value] : value,
      date: point?.date || '',
      inProgress: Boolean(point?.data?.in_progress),
    }
  })
}

const zeroRainPoints = points => points
  .filter(point => {
    const value = chartData.value.view === 'recent24h' ? point.value?.[1] : point.value
    return value === 0
  })
  .map(point => {
    if (chartData.value.view === 'recent24h') return [point.value[0], 0]
    return [point.date, 0]
  })

const formatXAxisLabel = (value) => {
  if (chartData.value.view === 'recent24h') {
    return new Date(value).toLocaleTimeString('zh-CN', {
      timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false,
    })
  }
  const [, month, day] = String(value).split('-').map(Number)
  return selectedMonth.value === 'all' ? `${month}月` : `${day}日`
}

const escapeTooltipHtml = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character])

const tooltipFormatter = (params) => {
  const recent = chartData.value.view === 'recent24h'
  const item = (Array.isArray(params) ? params : [params]).find(entry => {
    const value = recent ? entry.value?.[1] : entry.value
    return value !== null && value !== undefined
  })
  if (!item) return ''
  const dateValue = recent ? new Date(item.value[0]) : new Date(`${item.axisValue}T00:00:00+08:00`)
  const heading = recent
    ? dateValue.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    : dateValue.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' })
  const value = recent ? item.value[1] : item.value
  const label = recent ? '30分钟新增雨量' : (item.data?.inProgress ? '今日雨量（截至当前）' : '逐日雨量')
  return `<div style="min-width:190px"><strong>${escapeTooltipHtml(heading)}</strong>`
    + `<div style="display:flex;justify-content:space-between;gap:22px;margin-top:8px">`
    + `<span>${item.marker}${label}</span><strong>${Number(value).toFixed(1)} 毫米</strong></div></div>`
}

const currentDayMark = () => {
  if (chartData.value.view === 'recent24h') return undefined
  const dateKey = shanghaiDateKey(Date.now())
  const dates = (chartData.value.history || []).map(point => point?.date)
  if (!dates.includes(dateKey)) return undefined
  return {
    silent: true,
    symbol: ['none', 'none'],
    lineStyle: { color: 'rgba(255,255,255,0.5)', width: 1 },
    label: {
      show: true, formatter: '今天', position: 'insideEndTop', rotate: 0, color: '#fff',
      backgroundColor: '#343b4d', borderRadius: 10, padding: [3, 9], fontWeight: 600,
    },
    data: [{ xAxis: dateKey }],
  }
}

const fullChartOption = () => {
  const recent = chartData.value.view === 'recent24h'
  const monthly = !recent && selectedMonth.value !== 'all'
  const points = chartSeriesData()
  const zeroPoints = zeroRainPoints(points)
  const values = points
    .map(point => recent ? point.value[1] : point.value)
    .filter(value => value !== null)
  const observedMax = values.length ? Math.max(...values) : 0
  const fallbackMax = observedMax <= 1 ? 1 : (observedMax <= 5 ? 5 : 20)
  const yRange = calcNiceYAxisRange(values, { min: 0, max: fallbackMax }, 5)
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
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000

  return {
    animation: true,
    animationDuration: 850,
    animationDurationUpdate: 550,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', confine: true, formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)', borderColor: 'rgba(89, 155, 255, 0.55)', borderWidth: 1,
      padding: [11, 13], textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(47, 151, 255, 0.08)' } },
    },
    grid: { left: 18, right: 22, bottom: 18, top: 24, containLabel: true },
    xAxis: recent ? {
      type: 'time',
      min: Number.isFinite(windowStart) ? windowStart : Date.now() - DAY,
      max: Number.isFinite(windowEnd) ? windowEnd : Date.now(),
      interval: 3 * HOUR,
      minInterval: 3 * HOUR,
      axisLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.55)' } },
      axisTick: { show: true, lineStyle: { color: 'rgba(151, 177, 215, 0.45)' } },
      axisLabel: { color: '#aebdd1', margin: 11, hideOverlap: true, formatter: formatXAxisLabel },
      splitLine: { show: false },
    } : {
      type: 'category', data: calendarDates, boundaryGap: true,
      axisLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.55)' } },
      axisTick: { show: true, alignWithLabel: true, interval: calendarLabelInterval, lineStyle: { color: 'rgba(151, 177, 215, 0.45)' } },
      axisLabel: { color: '#aebdd1', margin: 11, interval: calendarLabelInterval, formatter: formatXAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', min: yRange.min, max: yRange.max, interval: yRange.interval,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#d4deec', margin: 12, formatter: value => `${value}\n毫米`, lineHeight: 17 },
      splitLine: { lineStyle: { color: 'rgba(187, 204, 229, 0.38)', width: 1 } },
    },
    series: [{
      id: 'rainfall',
      name: rainLegendLabel(chartData.value.view),
      type: 'bar',
      data: points,
      barMaxWidth: recent ? 18 : (monthly ? 22 : 7),
      barMinHeight: rainBarMinHeight(values),
      z: 3,
      itemStyle: {
        borderRadius: [3, 3, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#16c5ff' },
          { offset: 0.5, color: '#168dff' },
          { offset: 1, color: '#1762d5' },
        ]),
        shadowBlur: 6,
        shadowColor: 'rgba(22, 149, 255, 0.24)',
      },
      emphasis: {
        itemStyle: { color: '#43d7ff', shadowBlur: 12, shadowColor: 'rgba(31, 180, 255, 0.52)' },
      },
      markLine: currentDayMark(),
    }, ...(zeroPoints.length ? [{
      id: 'rain-zero-markers',
      name: '0 mm',
      type: 'scatter',
      data: zeroPoints,
      symbol: 'roundRect',
      symbolSize: [12, 3],
      z: 5,
      tooltip: { show: false },
      itemStyle: { color: 'rgba(151, 190, 255, 0.72)' },
      emphasis: { disabled: true },
    }] : [])],
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
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 14px 18px; background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 10px; }
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
.header-comm { font-size: 14px; font-weight: 500; color: var(--text-secondary); margin-top: 4px; font-family: "Consolas", "Monaco", monospace; }

.data-panel { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; margin-bottom: 12px; }
.panel-title { font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: 8px; }

/* 雨量数据卡片 */
.rain-data-card { display: flex; gap: 16px; align-items: stretch; }
.rain-core { flex: 1; }
.rain-main-row { display: flex; gap: 0; margin-bottom: 22px; }
.rain-main-item { flex: 1; min-width: 0; padding: 0 16px; }
.rain-main-divider { width: 1px; background: rgba(0, 200, 255, 0.12); margin: 0 4px; align-self: stretch; }
.rain-main-label { font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.rain-main-val {
  font-size: 40px;
  font-weight: 800;
  color: var(--accent-color);
  font-family: "Consolas", "Monaco", monospace;
  line-height: 1;
}
.rain-main-unit { font-size: 16px; font-weight: 400; color: var(--text-muted); margin-left: 4px; }
/* 防汛预警条 */
.rain-warn-bar { display: flex; flex-direction: column; gap: 6px; }
.rain-warn-track {
  position: relative;
  height: 10px;
  background: linear-gradient(90deg, #409eff 0%, #e6a23c 35%, #f59e2f 65%, #f56c6c 100%);
  border-radius: 5px;
  overflow: visible;
}
.rain-warn-cursor {
  position: absolute;
  top: -5px;
  width: 3px;
  height: 20px;
  background: #fff;
  border-radius: 2px;
  box-shadow: 0 0 6px rgba(255,255,255,0.7);
  transform: translateX(-50%);
  transition: left 0.6s ease;
}
.rain-warn-info { display: flex; justify-content: space-between; align-items: center; }
.rain-warn-status { font-size: 13px; font-weight: 600; }
.rain-warn-status.rw-ok { color: #67c23a; }
.rain-warn-status.rw-warn { color: #e6a23c; }
.rain-warn-status.rw-danger { color: #f56c6c; }
.rain-warn-ref { font-size: 12px; color: #AECAF5; }
.rain-yesterday-card {
  position: relative;
  flex: 0 0 158px;
  min-height: 126px;
  padding: 14px 16px;
  overflow: hidden;
  border: 1px solid rgba(0, 229, 255, 0.28);
  border-left: 4px solid #4d7cff;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(13, 39, 72, 0.96), rgba(8, 29, 56, 0.98));
  color: var(--text-primary);
  box-shadow: inset 0 0 18px rgba(0, 229, 255, 0.08), 0 8px 18px rgba(0, 0, 0, 0.18);
}
.rain-yesterday-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 22px;
  font-size: 17px;
  font-weight: 700;
  line-height: 1;
}
.rain-yesterday-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 26px;
  font-size: 24px;
  font-weight: 800;
  line-height: 1;
  font-family: "Consolas", "Monaco", monospace;
}
.rain-yesterday-value span {
  color: #AECAF5;
  font-family: inherit;
  font-size: 15px;
  font-weight: 500;
}
.rain-yesterday-foot {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 20px;
  color: #AECAF5;
  font-size: 13px;
  font-weight: 600;
}
.rain-yesterday-foot .el-icon {
  color: #5f84ff;
  font-size: 16px;
}
.rain-yesterday-track {
  position: absolute;
  right: 14px;
  top: 52px;
  width: 24px;
  height: 68px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(174, 202, 245, 0.16);
}
.rain-yesterday-fill {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  border-radius: 999px;
  background: linear-gradient(180deg, #5d7cff, #2f55f5);
  transition: height 0.4s ease;
}

/* 气象站式逐日雨量 */
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
.chart-retry-button { margin-top: 12px; }
.loading-spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(0, 200, 255, 0.2);
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
.rain-series-legend {
  min-height: 38px;
  padding: 4px 10px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid rgba(123, 154, 201, 0.1);
  color: #b7cae4;
  font-size: 12px;
}
.rain-series-legend i {
  width: 18px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, #1762d5, #16c5ff);
  box-shadow: 0 0 8px rgba(22, 149, 255, 0.45);
}
.rain-series-legend .zero-marker {
  width: 12px;
  height: 3px;
  margin-left: 14px;
  background: rgba(151, 190, 255, 0.72);
  box-shadow: none;
}

@media (max-width: 900px) {
  .history-panel-header { align-items: flex-start; flex-wrap: wrap; }
  .history-controls { width: 100%; flex-wrap: wrap; }
  .history-chart-wrap { height: 340px; }
}

@media (max-width: 620px) {
  .rain-data-card { flex-direction: column; }
  .rain-main-row { flex-direction: column; gap: 16px; }
  .rain-main-divider { width: 100%; height: 1px; }
  .rain-yesterday-card { flex-basis: auto; }
  .history-heading { width: 100%; align-items: flex-start; flex-direction: column; gap: 12px; }
  .calendar-controls { width: 100%; }
  .history-select.year-select, .history-select.month-select { flex: 1; width: auto; }
}
</style>
