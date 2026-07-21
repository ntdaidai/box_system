<template>
  <div class="unified-sensors">
    <section class="live-grid">
      <button
        v-for="card in liveCards"
        :key="card.key"
        type="button"
        class="live-card"
        :class="[card.statusClass, { active: activeCardKey === card.key }]"
        @click="selectCard(card)"
      >
        <div class="card-head">
          <span class="card-title">{{ card.title }}</span>
          <span class="card-state">{{ card.state }}</span>
        </div>
        <div class="metric-row">
          <div v-for="metric in card.metrics" :key="metric.label" class="metric-cell">
            <strong>{{ metric.value }}</strong>
            <span>{{ metric.label }}</span>
          </div>
        </div>
        <div class="card-foot">
          <span>{{ card.note }}</span>
          <span>{{ card.time }}</span>
        </div>
      </button>
    </section>

    <section class="history-panel">
      <div class="history-header">
        <div class="history-title">
          <h3>历史记录</h3>
          <span>{{ activeTabMeta.subtitle }}</span>
        </div>
        <div class="history-controls">
          <button
            type="button"
            class="period-button"
            :class="{ active: historyMode === 'recent24h' }"
            @click="selectRecent24h"
          >
            近24小时
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

      <div class="history-tabs" role="tablist" aria-label="传感器历史记录">
        <button
          v-for="tab in historyTabs"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeHistoryTab === tab.key"
          :class="{ active: activeHistoryTab === tab.key }"
          @click="selectHistoryTab(tab.key)"
        >
          <span>{{ tab.icon }}</span>{{ tab.label }}
        </button>
      </div>

      <div class="chart-shell">
        <div ref="chartRef" class="chart"></div>
        <div v-if="historyLoading" class="chart-overlay">
          <div class="spinner"></div>
          <span>正在读取历史数据...</span>
        </div>
        <div v-else-if="historyError && historyEmpty" class="chart-overlay">
          <span>{{ historyError }}</span>
          <button type="button" class="retry-button" @click="retryHistory">重新加载</button>
        </div>
        <div v-else-if="historyEmpty" class="chart-overlay hint">
          <span>当前范围暂无{{ activeTabMeta.label }}数据</span>
        </div>
        <div v-if="historyError && !historyEmpty" class="chart-error-banner">
          <span>{{ historyError }}，当前显示上一次成功加载的数据</span>
          <button type="button" @click="retryHistory">重试</button>
        </div>
      </div>

      <div v-if="activeHistoryTab === 'vibration'" class="threshold-toggles">
        <label>
          <input v-model="thresholdVisibility.warning" type="checkbox" @change="renderChart" />
          <span></span>预警线 0.10g
        </label>
        <label>
          <input v-model="thresholdVisibility.alarm" type="checkbox" @change="renderChart" />
          <span></span>报警线 0.15g
        </label>
      </div>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <div class="summary-title">
          <h3>天气信息</h3>
          <span>过去 12 个月</span>
          <span>所有年份</span>
        </div>
        <div class="summary-table">
          <div v-for="item in weatherInfoRows" :key="item.label" class="summary-row">
            <span>{{ item.icon }} {{ item.label }}</span>
            <strong>{{ item.recent }}</strong>
            <strong>{{ item.all }}</strong>
          </div>
        </div>
      </div>

      <div class="summary-card">
        <div class="summary-title metrics">
          <h3>每日摘要（过去 12 个月）</h3>
          <span>最大值</span>
          <span>平均值</span>
          <span>最小值</span>
        </div>
        <div class="summary-table">
          <div v-for="item in dailySummaryRows" :key="item.label" class="summary-row metrics">
            <span>{{ item.label }}</span>
            <strong>{{ item.max }}</strong>
            <strong>{{ item.avg }}</strong>
            <strong>{{ item.min }}</strong>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  getAllSensorRealtime,
  getRainTrends,
  getTempHumidityTrends,
  getVibrationHistoryTrends,
  getVibrationProcessed,
  getWindTrends,
} from '@/api/sensor'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import * as echarts from 'echarts'

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const WARNING_RMS = 0.10
const ALARM_RMS = 0.15

const chartRef = ref(null)
const realtimeData = ref({})
const vibrationProcessed = ref({})
const activeCardKey = ref('temp_humidity')
const activeHistoryTab = ref('temperature')
const historyMode = ref('recent24h')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref('all')
const availablePeriods = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'recent24h', history: [], window: null })
const thresholdVisibility = reactive({ warning: true, alarm: true })
const summaryData = reactive({
  tempRecent: [],
  rainRecent: [],
  windRecent: [],
  tempAll: [],
  rainAll: [],
  windAll: [],
})

let chart = null
let realtimeTimer = null
let refreshTimer = null
let resizeHandler = null
let requestSerial = 0
let isMounted = false

const historyTabs = [
  { key: 'temperature', label: '气温', icon: '♨', subtitle: '温度变化趋势', unit: '℃', color: '#ff5b6e' },
  { key: 'humidity', label: '湿度', icon: '♧', subtitle: '湿度变化趋势', unit: '%', color: '#20a8ff' },
  { key: 'rain', label: '降水', icon: '◇', subtitle: '降水变化趋势', unit: 'mm', color: '#1fa6ff' },
  { key: 'wind', label: '风速', icon: '≋', subtitle: '风速变化趋势', unit: 'km/h', color: '#72cdf9' },
  { key: 'vibration', label: '振动', icon: '⌁', subtitle: '综合振动 RMS 趋势', unit: 'g', color: '#20d7ff' },
]

const activeTabMeta = computed(() => historyTabs.find(tab => tab.key === activeHistoryTab.value) || historyTabs[0])

const yearOptions = computed(() => {
  const years = availablePeriods.value.map(item => Number(item.year)).filter(Number.isFinite)
  const selected = Number(selectedYear.value)
  if (Number.isInteger(selected) && !years.includes(selected)) years.push(selected)
  return years.length ? [...new Set(years)].sort((a, b) => b - a) : [new Date().getFullYear()]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  if (!period) return Array.from({ length: 12 }, (_, index) => index + 1)
  return (period.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const historyEmpty = computed(() => chartValues().length === 0)

const liveCards = computed(() => {
  const temp = realtimeData.value.temp_humidity?.data || {}
  const rain = realtimeData.value.rain?.data || {}
  const wind = realtimeData.value.wind?.data || {}
  const vibration = vibrationProcessed.value || {}
  return [
    {
      key: 'temp_humidity',
      title: '温湿度',
      state: tempHumidityState(temp),
      statusClass: tempHumidityStatusClass(temp),
      note: '环境状态',
      time: formatCommTime(realtimeData.value.temp_humidity?.timestamp),
      metrics: [
        { label: '温度', value: formatMetric(temp.temperature, 1, '℃') },
        { label: '湿度', value: formatMetric(temp.humidity, 1, '%') },
      ],
      tab: 'temperature',
    },
    {
      key: 'rain',
      title: '降水',
      state: rainState(rain),
      statusClass: rainStatusClass(rain),
      note: '瞬时 / 今日',
      time: formatCommTime(realtimeData.value.rain?.timestamp),
      metrics: [
        { label: '瞬时', value: formatMetric(rain.instant_rain, 1, 'mm') },
        { label: '今日', value: formatMetric(rain.today_rain, 1, 'mm') },
      ],
      tab: 'rain',
    },
    {
      key: 'wind',
      title: '风速风向',
      state: windState(wind),
      statusClass: windStatusClass(wind),
      note: wind.wind_direction || '--',
      time: formatCommTime(realtimeData.value.wind?.timestamp),
      metrics: [
        { label: '风速', value: formatMetric(windSpeedKmh(wind), 1, 'km/h') },
        { label: '风向', value: wind.wind_direction || '--' },
      ],
      tab: 'wind',
    },
    {
      key: 'vibration',
      title: '振动',
      state: vibration.alert_level || '正常',
      statusClass: vibrationStatusClass(vibration),
      note: 'RMS / 主频',
      time: formatCommTime(vibration.timestamp),
      metrics: [
        { label: 'RMS', value: formatMetric(vibration.total_rms, 3, 'g') },
        { label: '主频', value: formatMetric(vibration.dominant_freq, 1, 'Hz') },
        { label: '峰值因子', value: formatMetric(vibration.crest_factor, 1, '') },
      ],
      tab: 'vibration',
    },
  ]
})

const weatherInfoRows = computed(() => {
  const recentStats = buildMonthlyStats({
    temp: summaryData.tempRecent,
    wind: summaryData.windRecent,
  })
  const allStats = buildMonthlyStats({
    temp: summaryData.tempAll,
    wind: summaryData.windAll,
  })
  return [
    {
      icon: '🌡',
      label: '最热的月份',
      recent: monthName(bestMonth(recentStats.temperatureMax, 'max')),
      all: monthName(bestMonth(allStats.temperatureMax, 'max')),
    },
    {
      icon: '❄',
      label: '最冷的月份',
      recent: monthName(bestMonth(recentStats.temperatureMin, 'min')),
      all: monthName(bestMonth(allStats.temperatureMin, 'min')),
    },
    {
      icon: '💧',
      label: '最潮湿的月份',
      recent: monthName(bestMonth(recentStats.humidity, 'max')),
      all: monthName(bestMonth(allStats.humidity, 'max')),
    },
    {
      icon: '≋',
      label: '风最多的月份',
      recent: monthName(bestMonth(recentStats.wind, 'max')),
      all: monthName(bestMonth(allStats.wind, 'max')),
    },
  ]
})

const dailySummaryRows = computed(() => [
  summaryRow('高温 (℃)', summaryData.tempRecent.map(row => toNumber(row.data?.temperature_max ?? row.data?.temperature)).filter(v => v !== null), 0),
  summaryRow('低温 (℃)', summaryData.tempRecent.map(row => toNumber(row.data?.temperature_min ?? row.data?.temperature)).filter(v => v !== null), 0),
  summaryRow('降水 (mm)', summaryData.rainRecent.map(row => toNumber(row.data?.daily_rain)).filter(v => v !== null), 2),
  summaryRow('风速 (km/h)', summaryData.windRecent.map(row => windSpeedKmh(row.data)).filter(v => v !== null), 1),
])

const toNumber = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatMetric = (value, decimals, unit) => {
  const numeric = toNumber(value)
  if (numeric === null) return '--'
  return `${numeric.toFixed(decimals)}${unit}`
}

const formatCommTime = (timestamp) => {
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric) || numeric <= 0) return '--'
  const timeMs = numeric > 1e12 ? numeric : numeric * 1000
  return new Date(timeMs).toLocaleTimeString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

const tempHumidityState = (data) => {
  const temp = toNumber(data.temperature)
  const humidity = toNumber(data.humidity)
  if (temp === null && humidity === null) return '--'
  if (temp >= 35) return '高温'
  if (temp <= 0) return '低温'
  if (humidity !== null && humidity < 40) return '偏干'
  if (humidity !== null && humidity > 75) return '偏湿'
  return '适宜'
}

const tempHumidityStatusClass = data => ['高温', '低温', '偏干', '偏湿'].includes(tempHumidityState(data)) ? 'warn' : 'ok'

const rainState = (data) => {
  const value = toNumber(data.instant_rain)
  if (value === null || value <= 0) return '无雨'
  if (value < 10) return '小雨'
  if (value < 25) return '中雨'
  if (value < 50) return '大雨'
  return '暴雨'
}

const rainStatusClass = data => ['大雨', '暴雨'].includes(rainState(data)) ? 'danger' : (rainState(data) === '中雨' ? 'warn' : 'ok')

const windSpeedKmh = (data = {}) => {
  const kmh = toNumber(data.wind_speed_kmh)
  if (kmh !== null) return kmh
  const ms = toNumber(data.wind_speed_ms)
  return ms === null ? null : ms * 3.6
}

const windState = (data) => {
  const speed = windSpeedKmh(data)
  if (speed === null) return '--'
  if (speed < 22) return '微风'
  if (speed < 38) return '和风'
  if (speed < 54) return '大风'
  return '强风'
}

const windStatusClass = data => ['大风', '强风'].includes(windState(data)) ? 'warn' : 'ok'

const vibrationStatusClass = (data) => {
  if (data.alert_level === '报警') return 'danger'
  if (data.alert_level === '预警' || data.alert_level === '关注') return 'warn'
  return 'ok'
}

const queryKey = ({ tab, view, year, month }) => [tab, view, year || '', month || 'all'].join(':')
const historyCache = new Map()

const currentQuery = () => historyMode.value === 'recent24h'
  ? { tab: activeHistoryTab.value, view: 'recent24h' }
  : {
      tab: activeHistoryTab.value,
      view: 'calendar',
      year: Number(selectedYear.value),
      month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
    }

const readHistoryCache = (query) => {
  const cached = historyCache.get(queryKey(query))
  if (!cached) return null
  const maxAge = query.view === 'recent24h' ? 5 * MINUTE : 30 * MINUTE
  if (Date.now() - cached.updatedAt <= maxAge) return cached.payload
  historyCache.delete(queryKey(query))
  return null
}

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
  if (!periods.some(item => Number(item.year) === Number(selectedYear.value))) {
    selectedYear.value = Number(periods[0].year)
    selectedMonth.value = 'all'
  }
}

const fetchRealtime = async () => {
  try {
    const [allRes, vibrationRes] = await Promise.all([
      getAllSensorRealtime(),
      getVibrationProcessed(),
    ])
    if (allRes.code === 200 && allRes.data) realtimeData.value = allRes.data
    if (vibrationRes.code === 200 && vibrationRes.data) {
      const payload = vibrationRes.data.data || vibrationRes.data
      vibrationProcessed.value = {
        ...payload,
        timestamp: vibrationRes.data.timestamp || vibrationRes.data.data?.timestamp,
      }
    }
  } catch (error) {
    console.warn('加载实时传感器数据失败:', error)
  }
}

const fetchHistoryPayload = async (query) => {
  const params = { view: query.view, year: query.year, month: query.month }
  if (query.tab === 'temperature' || query.tab === 'humidity') return getTempHumidityTrends(params)
  if (query.tab === 'rain') return getRainTrends(params)
  if (query.tab === 'wind') return getWindTrends(params)
  return getVibrationHistoryTrends(params)
}

const applyHistoryPayload = (query, payload, cacheResult = true) => {
  const normalized = { ...payload, history: Array.isArray(payload.history) ? payload.history : [] }
  syncAvailablePeriods(normalized.available_periods)
  if (cacheResult) historyCache.set(queryKey(query), { payload: normalized, updatedAt: Date.now() })
  if (queryKey(query) === queryKey(currentQuery())) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadHistory = async (query = currentQuery(), force = false) => {
  const key = queryKey(query)
  const requestId = ++requestSerial
  const cached = force ? null : readHistoryCache(query)
  if (cached) {
    applyHistoryPayload(query, cached, false)
    await nextTick()
    renderChart()
    return
  }

  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await fetchHistoryPayload(query)
    if (res.code !== 200 || !res.data || !Array.isArray(res.data.history)) {
      throw new Error('历史数据响应无效')
    }
    if (!isMounted || requestId !== requestSerial || key !== queryKey(currentQuery())) return
    applyHistoryPayload(query, res.data)
    await nextTick()
    renderChart()
    scheduleHistoryRefresh()
  } catch (error) {
    console.warn('加载综合历史失败:', error)
    if (key === queryKey(currentQuery())) historyError.value = '历史数据服务暂时不可用，请稍后重试'
  } finally {
    if (key === queryKey(currentQuery())) historyLoading.value = false
  }
}

const scheduleHistoryRefresh = () => {
  if (refreshTimer) clearTimeout(refreshTimer)
  const delay = historyMode.value === 'recent24h' ? millisecondsToNextHalfHour() + 1000 : 30 * MINUTE
  refreshTimer = setTimeout(() => {
    if (!isMounted) return
    loadHistory(currentQuery(), true)
  }, delay)
}

const millisecondsToNextHalfHour = () => {
  const now = Date.now()
  const interval = 30 * MINUTE
  return Math.floor(now / interval) * interval + interval - now
}

const selectCard = (card) => {
  activeCardKey.value = card.key
  selectHistoryTab(card.tab)
}

const selectHistoryTab = (tab) => {
  if (activeHistoryTab.value === tab && !historyError.value) return
  activeHistoryTab.value = tab
  const relatedCard = liveCards.value.find(card => card.tab === tab)
  if (relatedCard) activeCardKey.value = relatedCard.key
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const selectRecent24h = () => {
  if (historyMode.value === 'recent24h' && !historyError.value) return
  historyMode.value = 'recent24h'
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const onYearChange = () => {
  historyMode.value = 'calendar'
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
  loadHistory(currentQuery())
}

const onMonthChange = () => {
  historyMode.value = 'calendar'
  loadHistory(currentQuery())
}

const retryHistory = () => {
  loadHistory(currentQuery(), true)
}

const valueFromPoint = (point) => {
  const data = point?.data || {}
  if (activeHistoryTab.value === 'temperature') {
    const value = toNumber(data.temperature)
    if (value !== null) return value
    const min = toNumber(data.temperature_min)
    const max = toNumber(data.temperature_max)
    return min !== null && max !== null ? (min + max) / 2 : (min ?? max)
  }
  if (activeHistoryTab.value === 'humidity') return toNumber(data.humidity)
  if (activeHistoryTab.value === 'rain') return toNumber(historyMode.value === 'recent24h' ? data.rain_increment : data.daily_rain)
  if (activeHistoryTab.value === 'wind') return windSpeedKmh(data)
  return toNumber(data.rms)
}

const pointTime = (point) => {
  if (historyMode.value === 'recent24h') return Number(point.timestamp) * 1000
  if (point.date) return new Date(`${point.date}T00:00:00+08:00`).getTime()
  return Number(point.timestamp) * 1000
}

const chartSeriesData = () => (chartData.value.history || []).map(point => [pointTime(point), valueFromPoint(point)])

const chartValues = () => chartSeriesData().map(point => point[1]).filter(value => value !== null && Number.isFinite(value))

const formatXAxisLabel = (value) => {
  const date = new Date(value)
  if (historyMode.value === 'recent24h') {
    return date.toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return selectedMonth.value === 'all'
    ? date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric' })
    : `${date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', day: 'numeric' })}日`
}

const tooltipFormatter = (params) => {
  const item = (Array.isArray(params) ? params : [params]).find(entry => entry.value?.[1] != null)
  if (!item) return ''
  const date = new Date(item.value[0])
  const heading = historyMode.value === 'recent24h'
    ? date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' })
  return `<div style="min-width:160px"><strong>${heading}</strong><div style="display:flex;justify-content:space-between;gap:24px;margin-top:8px"><span>${item.marker}${activeTabMeta.value.label}</span><strong>${Number(item.value[1]).toFixed(activeHistoryTab.value === 'vibration' ? 4 : 1)} ${activeTabMeta.value.unit}</strong></div></div>`
}

const thresholdMarkLines = () => {
  if (activeHistoryTab.value !== 'vibration') return []
  const data = []
  if (thresholdVisibility.warning) data.push({ yAxis: WARNING_RMS, lineStyle: { color: '#e6a23c', type: 'dashed' }, label: { show: true, formatter: '预警 0.10g', color: '#e6a23c' } })
  if (thresholdVisibility.alarm) data.push({ yAxis: ALARM_RMS, lineStyle: { color: '#f56c6c', type: 'dashed' }, label: { show: true, formatter: '报警 0.15g', color: '#f56c6c' } })
  return data
}

const fullChartOption = () => {
  const meta = activeTabMeta.value
  const points = chartSeriesData()
  const values = chartValues()
  const fallback = activeHistoryTab.value === 'vibration'
    ? { min: 0, max: 0.2 }
    : activeHistoryTab.value === 'humidity'
      ? { min: 0, max: 100 }
      : { min: 0, max: Math.max(10, ...values, 10) }
  const thresholdValues = activeHistoryTab.value === 'vibration' ? [WARNING_RMS, ALARM_RMS] : []
  const yRange = calcNiceYAxisRange([...values, ...thresholdValues], fallback, 5)
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const recent = historyMode.value === 'recent24h'
  return {
    animation: true,
    animationDuration: 850,
    animationDurationUpdate: 550,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)',
      borderColor: 'rgba(89, 155, 255, 0.55)',
      borderWidth: 1,
      textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: activeHistoryTab.value === 'rain' ? 'shadow' : 'line' },
    },
    grid: { left: 18, right: 22, bottom: 18, top: 28, containLabel: true },
    xAxis: {
      type: 'time',
      min: Number.isFinite(windowStart) && recent ? windowStart : (points[0]?.[0] ?? Date.now() - DAY),
      max: Number.isFinite(windowEnd) && recent ? windowEnd : (points.at(-1)?.[0] ?? Date.now()),
      interval: recent ? 3 * HOUR : (selectedMonth.value === 'all' ? 30 * DAY : 5 * DAY),
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
      axisLabel: { color: '#b6c7df', margin: 12, formatter: value => `${value}${meta.unit}` },
      splitLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.18)', width: 1 } },
    },
    series: [{
      id: `history-${activeHistoryTab.value}`,
      name: meta.label,
      type: activeHistoryTab.value === 'rain' ? 'bar' : 'line',
      data: points,
      showSymbol: false,
      smooth: activeHistoryTab.value === 'rain' ? false : (recent ? 0.3 : 0.14),
      connectNulls: false,
      clip: true,
      barMaxWidth: recent ? 18 : 9,
      lineStyle: { color: meta.color, width: recent ? 2.4 : 1.8 },
      itemStyle: {
        color: meta.color,
        borderColor: '#ffffff',
        borderWidth: activeHistoryTab.value === 'rain' ? 0 : 1,
        borderRadius: activeHistoryTab.value === 'rain' ? [3, 3, 0, 0] : 0,
      },
      areaStyle: activeHistoryTab.value === 'rain' ? undefined : {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${meta.color}36` },
          { offset: 1, color: `${meta.color}00` },
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
  if (!chart || chart.isDisposed()) return
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
    chart?.resize()
    renderChart()
  }
  window.addEventListener('resize', resizeHandler)
}

const loadSummary = async () => {
  const year = new Date().getFullYear()
  const previousYear = year - 1
  try {
    const [tempCurrent, tempPrevious, rainRecent, windRecent] = await Promise.all([
      getTempHumidityTrends({ view: 'calendar', year, month: null }),
      getTempHumidityTrends({ view: 'calendar', year: previousYear, month: null }),
      getRainTrends({ view: 'rolling12' }),
      getWindTrends({ view: 'rolling12' }),
    ])
    const tempRecentSource = [
      ...(tempPrevious.data?.history || []),
      ...(tempCurrent.data?.history || []),
    ]
    if (tempCurrent.code === 200 || tempPrevious.code === 200) {
      summaryData.tempRecent = filterLast12Months(tempRecentSource)
      const tempPeriods = [
        ...(tempCurrent.data?.available_periods || []),
        ...(tempPrevious.data?.available_periods || []),
      ]
      summaryData.tempAll = await loadAllCalendarRows(
        periodUnion(tempPeriods),
        period => getTempHumidityTrends({ view: 'calendar', year: period.year, month: null }),
      )
    }
    if (rainRecent.code === 200) {
      summaryData.rainRecent = rainRecent.data?.history || []
      summaryData.rainAll = await loadAllCalendarRows(
        rainRecent.data?.available_periods || [],
        period => getRainTrends({ view: 'calendar', year: period.year, month: null }),
      )
    }
    if (windRecent.code === 200) {
      summaryData.windRecent = windRecent.data?.history || []
      summaryData.windAll = await loadAllCalendarRows(
        windRecent.data?.available_periods || [],
        period => getWindTrends({ view: 'calendar', year: period.year, month: null }),
      )
    }
  } catch (error) {
    console.warn('加载统计摘要失败:', error)
  }
}

const filterLast12Months = (rows = []) => {
  const cutoff = new Date()
  cutoff.setFullYear(cutoff.getFullYear() - 1)
  const cutoffMs = cutoff.getTime()
  return rows.filter(row => {
    const time = row?.date
      ? new Date(`${row.date}T00:00:00+08:00`).getTime()
      : Number(row?.timestamp || 0) * 1000
    return Number.isFinite(time) && time >= cutoffMs
  })
}

const periodUnion = (periods = []) => {
  const map = new Map()
  periods.forEach(period => {
    const year = Number(period.year)
    if (Number.isInteger(year)) map.set(year, period)
  })
  return [...map.values()].sort((a, b) => Number(b.year) - Number(a.year))
}

const loadAllCalendarRows = async (periods = [], loader) => {
  const validPeriods = periodUnion(periods)
  if (!validPeriods.length) return []
  const responses = await Promise.allSettled(validPeriods.map(loader))
  return responses.flatMap(result => (
    result.status === 'fulfilled' && result.value?.code === 200
      ? (result.value.data?.history || [])
      : []
  ))
}

const buildMonthlyStats = ({ temp = [], wind = [] } = {}) => {
  const result = {
    temperatureMax: new Map(),
    temperatureMin: new Map(),
    humidity: new Map(),
    wind: new Map(),
  }
  temp.forEach(row => {
    const month = monthFromRow(row)
    pushMonthValue(result.temperatureMax, month, toNumber(row.data?.temperature_max ?? row.data?.temperature))
    pushMonthValue(result.temperatureMin, month, toNumber(row.data?.temperature_min ?? row.data?.temperature))
    pushMonthValue(result.humidity, month, toNumber(row.data?.humidity))
  })
  wind.forEach(row => {
    pushMonthValue(result.wind, monthFromRow(row), windSpeedKmh(row.data))
  })
  return result
}

const monthFromRow = (row) => {
  const date = row?.date ? new Date(`${row.date}T00:00:00+08:00`) : new Date(Number(row?.timestamp || 0) * 1000)
  const month = date.getMonth() + 1
  return Number.isFinite(month) ? month : null
}

const pushMonthValue = (target, month, value) => {
  if (!month || value === null) return
  if (!target.has(month)) target.set(month, [])
  target.get(month).push(value)
}

const bestMonth = (source, mode) => {
  let winner = null
  let winnerValue = null
  source.forEach((values, month) => {
    if (!values.length) return
    const value = values.reduce((sum, current) => sum + current, 0) / values.length
    if (winnerValue === null || (mode === 'max' ? value > winnerValue : value < winnerValue)) {
      winner = month
      winnerValue = value
    }
  })
  return winner
}

const monthName = month => month ? `${month}月` : '--'

const summaryRow = (label, values, decimals) => {
  if (!values.length) return { label, max: '--', avg: '--', min: '--' }
  const max = Math.max(...values)
  const min = Math.min(...values)
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length
  return {
    label,
    max: max.toFixed(decimals),
    avg: avg.toFixed(decimals),
    min: min.toFixed(decimals),
  }
}

onMounted(async () => {
  isMounted = true
  initChart()
  await Promise.all([fetchRealtime(), loadHistory(currentQuery()), loadSummary()])
  realtimeTimer = setInterval(fetchRealtime, 5000)
})

onUnmounted(() => {
  isMounted = false
  requestSerial += 1
  if (realtimeTimer) clearInterval(realtimeTimer)
  if (refreshTimer) clearTimeout(refreshTimer)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  if (chart && !chart.isDisposed()) chart.dispose()
  chart = null
})
</script>

<style scoped>
.unified-sensors {
  min-height: 100%;
  padding: 0;
  color: var(--text-primary);
}

.live-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.live-card {
  min-width: 0;
  min-height: 148px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 10px;
  background:
    linear-gradient(145deg, rgba(16, 34, 61, 0.98), rgba(9, 23, 43, 0.98));
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
}

.live-card:hover,
.live-card.active {
  border-color: rgba(54, 151, 255, 0.72);
  box-shadow: 0 10px 28px rgba(18, 86, 170, 0.24);
  transform: translateY(-1px);
}

.live-card.ok { border-top: 3px solid #67c23a; }
.live-card.warn { border-top: 3px solid #e6a23c; }
.live-card.danger { border-top: 3px solid #f56c6c; }

.card-head,
.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: #f4f8ff;
}

.card-state {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 216, 74, 0.16);
  color: #ffd84a;
  font-size: 12px;
  font-weight: 700;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 18px 0 12px;
}

.metric-cell strong {
  display: block;
  color: #fff;
  font: 800 26px/1 "Consolas", "Monaco", monospace;
  white-space: nowrap;
}

.metric-cell span {
  display: block;
  margin-top: 6px;
  color: #8ea8c9;
  font-size: 12px;
}

.card-foot {
  color: #7e97b9;
  font-size: 12px;
}

.history-panel,
.summary-card {
  border: 1px solid rgba(84, 130, 202, 0.25);
  border-radius: 10px;
  background:
    radial-gradient(circle at 100% 0%, rgba(50, 105, 200, 0.13), transparent 34%),
    linear-gradient(145deg, rgba(15, 31, 57, 0.98), rgba(10, 23, 43, 0.98));
  box-shadow: 0 14px 36px rgba(0, 8, 24, 0.18);
  overflow: hidden;
}

.history-header {
  min-height: 64px;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid rgba(124, 157, 207, 0.14);
}

.history-title h3,
.summary-title h3 {
  margin: 0;
  color: #f4f8ff;
  font-size: 20px;
  font-weight: 750;
}

.history-title span {
  display: block;
  margin-top: 4px;
  color: #8ea8c9;
  font-size: 12px;
}

.history-controls {
  display: flex;
  align-items: center;
  gap: 9px;
}

.period-button {
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(120, 155, 211, 0.24);
  border-radius: 8px;
  background: rgba(33, 57, 94, 0.55);
  color: #a8bddb;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.period-button.active {
  color: #fff;
  border-color: #378cff;
  background: linear-gradient(135deg, #1d70e8, #245ac4);
}

.calendar-controls {
  display: flex;
  gap: 7px;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: 9px;
  opacity: 0.76;
}

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

.history-tabs {
  display: flex;
  gap: 8px;
  padding: 12px 18px 0;
  flex-wrap: wrap;
}

.history-tabs button {
  height: 32px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #a8bddb;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.history-tabs button.active {
  color: #071426;
  background: linear-gradient(135deg, #ffd84a, #ffbc27);
  box-shadow: 0 4px 14px rgba(255, 190, 35, 0.24);
}

.chart-shell {
  position: relative;
  height: 392px;
  margin: 12px 18px 12px;
}

.chart {
  height: 100%;
}

.chart-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-radius: 8px;
  background: rgba(8, 22, 43, 0.78);
  color: #AECAF5;
  backdrop-filter: blur(3px);
}

.chart-overlay.hint {
  background: rgba(8, 22, 43, 0.5);
}

.spinner {
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

.retry-button,
.chart-error-banner button {
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(255, 213, 138, 0.55);
  border-radius: 5px;
  background: rgba(255, 213, 138, 0.12);
  color: #ffe4b4;
  font: inherit;
  cursor: pointer;
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
}

.threshold-toggles {
  min-height: 38px;
  padding: 0 28px 12px;
  display: flex;
  align-items: center;
  gap: 20px;
  color: #b7cae4;
  font-size: 12px;
}

.threshold-toggles label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}

.threshold-toggles input {
  width: 15px;
  height: 15px;
  accent-color: #247ee8;
}

.threshold-toggles span {
  width: 18px;
  height: 3px;
  border-radius: 999px;
  background: #e6a23c;
}

.threshold-toggles label:nth-child(2) span {
  background: #f56c6c;
}

.summary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
  margin-top: 14px;
}

.summary-title {
  min-height: 44px;
  padding: 12px 16px;
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  align-items: center;
  gap: 12px;
  background: rgba(225, 237, 248, 0.08);
  color: #dce9fa;
  font-size: 13px;
  font-weight: 700;
}

.summary-title.metrics {
  grid-template-columns: 1.8fr repeat(3, 0.8fr);
}

.summary-table {
  padding: 0 16px;
}

.summary-row {
  min-height: 46px;
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  align-items: center;
  gap: 12px;
  border-top: 1px solid rgba(174, 202, 245, 0.12);
  color: #dce9fa;
  font-size: 14px;
}

.summary-row.metrics {
  grid-template-columns: 1.8fr repeat(3, 0.8fr);
}

.summary-row span {
  color: #f4f8ff;
}

.summary-row strong {
  color: #ffffff;
  font-weight: 700;
}

@media (max-width: 1280px) {
  .live-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .history-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-controls {
    width: 100%;
    flex-wrap: wrap;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .live-grid {
    grid-template-columns: 1fr;
  }

  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .calendar-controls {
    width: 100%;
  }

  .history-select.year-select,
  .history-select.month-select {
    flex: 1;
    width: auto;
  }

  .chart-shell {
    height: 330px;
  }
}
</style>
