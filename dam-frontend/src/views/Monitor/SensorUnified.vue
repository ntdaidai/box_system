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
        <div v-if="card.key === 'wind'" class="wind-card-body">
          <div class="wind-primary">
            <strong>{{ card.metrics[0].value }}</strong>
            <span>{{ card.metrics[0].label }}</span>
          </div>
          <div class="wind-direction">
            <strong>{{ card.directionText }}</strong>
            <span>{{ card.metrics[1].label }}</span>
          </div>
          <div class="mini-compass" aria-hidden="true">
            <i :style="{ transform: `translate(-50%, -50%) rotate(${card.angle}deg)` }"></i>
          </div>
        </div>
        <div v-else class="metric-row" :class="{ 'metric-columns': card.metrics.length > 2 }">
          <div v-for="metric in card.metrics" :key="metric.label" class="metric-cell">
            <strong>{{ metric.value }}</strong>
            <span>{{ metric.label }}</span>
          </div>
        </div>
      </button>
    </section>

    <section class="history-panel">
      <div class="history-header">
        <div class="history-title">
          <h3>历史记录</h3>
          <span>{{ activeTabMeta.subtitle }}；实时卡片每 5 秒刷新，历史图表按半小时或 30 分钟窗口刷新</span>
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
          <button
            type="button"
            class="period-button"
            :class="{ active: historyMode === 'overview' }"
            @click="selectOverview"
          >
            总览
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
            <span><i class="info-icon">{{ item.icon }}</i>{{ item.label }}</span>
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
  getVibrationTrends,
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
  vibrationRecent: [],
  vibrationAll: [],
})

let chart = null
let realtimeTimer = null
let refreshTimer = null
let summaryTimer = null
let resizeHandler = null
let requestSerial = 0
let isMounted = false
let lastPointerPixel = null

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
      angle: windDirectionAngle(wind),
      directionText: wind.wind_direction || '--',
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
    vibration: summaryData.vibrationRecent,
  })
  const allStats = buildMonthlyStats({
    temp: summaryData.tempAll,
    wind: summaryData.windAll,
    vibration: summaryData.vibrationAll,
  })
  return [
    {
      icon: '℃+',
      label: '最热的月份',
      recent: monthName(bestMonth(recentStats.temperatureMax, 'max')),
      all: monthName(bestMonth(allStats.temperatureMax, 'max')),
    },
    {
      icon: '℃-',
      label: '最冷的月份',
      recent: monthName(bestMonth(recentStats.temperatureMin, 'min')),
      all: monthName(bestMonth(allStats.temperatureMin, 'min')),
    },
    {
      icon: '%',
      label: '最潮湿的月份',
      recent: monthName(bestMonth(recentStats.humidity, 'max')),
      all: monthName(bestMonth(allStats.humidity, 'max')),
    },
    {
      icon: 'm/s',
      label: '风最多的月份',
      recent: monthName(bestMonth(recentStats.wind, 'max')),
      all: monthName(bestMonth(allStats.wind, 'max')),
    },
    {
      icon: 'g',
      label: '振动最高的月份',
      recent: monthName(bestMonth(recentStats.vibration, 'max')),
      all: monthName(bestMonth(allStats.vibration, 'max')),
    },
  ]
})

const dailySummaryRows = computed(() => [
  summaryRow('高温 (℃)', summaryData.tempRecent.map(row => toNumber(row.data?.temperature_max ?? row.data?.temperature)).filter(v => v !== null), 0),
  summaryRow('低温 (℃)', summaryData.tempRecent.map(row => toNumber(row.data?.temperature_min ?? row.data?.temperature)).filter(v => v !== null), 0),
  summaryRow('降水 (mm)', summaryData.rainRecent.map(row => toNumber(row.data?.daily_rain)).filter(v => v !== null), 2),
  summaryRow('风速 (km/h)', summaryData.windRecent.map(row => windSpeedKmh(row.data)).filter(v => v !== null), 1),
  summaryRow('振动 RMS (g)', summaryData.vibrationRecent.map(row => toNumber(row.data?.rms)).filter(v => v !== null), 3),
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
  return new Date(timeMs).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).replace(/\//g, '/')
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

const windDirectionAngle = (data = {}) => {
  const angle = toNumber(data.wind_angle ?? data.wind_direction_angle ?? data.direction_angle)
  if (angle !== null) return angle
  const direction = String(data.wind_direction || '')
  const map = {
    北: 0,
    东北: 45,
    东: 90,
    东南: 135,
    南: 180,
    西南: 225,
    西: 270,
    西北: 315,
    东东北: 67.5,
    东东南: 112.5,
    西西南: 247.5,
    西西北: 292.5,
    北东北: 22.5,
    南东南: 157.5,
    南西南: 202.5,
    北西北: 337.5,
  }
  return map[direction] ?? 0
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
  : historyMode.value === 'overview'
    ? { tab: activeHistoryTab.value, view: 'overview' }
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
  if (query.view === 'overview') return fetchOverviewPayload(query)
  const params = { view: query.view, year: query.year, month: query.month }
  if (query.tab === 'temperature' || query.tab === 'humidity') return getTempHumidityTrends(params)
  if (query.tab === 'rain') return getRainTrends(params)
  if (query.tab === 'wind') return getWindTrends(params)
  return fetchVibrationHistory(params)
}

const historyLoaderForTab = (tab) => {
  if (tab === 'temperature' || tab === 'humidity') return getTempHumidityTrends
  if (tab === 'rain') return getRainTrends
  if (tab === 'wind') return getWindTrends
  return fetchVibrationHistory
}

const fetchOverviewPayload = async (query) => {
  const loader = historyLoaderForTab(query.tab)
  const seedRes = await loader({ view: 'calendar', year: Number(selectedYear.value), month: null })
  if (seedRes.code !== 200 || !seedRes.data) return seedRes
  const periods = periodUnion(seedRes.data.available_periods || [{ year: selectedYear.value }])
  const history = await loadAllCalendarRows(periods, period => loader({ view: 'calendar', year: period.year, month: null }))
  return {
    code: 200,
    data: {
      ...seedRes.data,
      view: 'overview',
      history,
      available_periods: periods,
    },
  }
}

const fetchVibrationHistory = async (params) => {
  try {
    const res = await getVibrationHistoryTrends(params)
    if (res.code === 200 && res.data && Array.isArray(res.data.history)) return res
    throw new Error('vibration trends response invalid')
  } catch (error) {
    console.warn('振动新历史接口不可用，回退旧趋势接口:', error)
    return loadLegacyVibrationPayload(params)
  }
}

const loadLegacyVibrationPayload = async ({ view = 'recent24h', year, month } = {}) => {
  const res = await getVibrationTrends(view === 'recent24h' ? '1d' : '6mo')
  if (res.code !== 200 || !res.data) return res
  const sourceRows = Array.isArray(res.data.history) ? res.data.history : []
  const rows = sourceRows
    .map(row => normalizeLegacyVibrationRow(row))
    .filter(row => row && legacyRowInRange(row, view, year, month))
  const periods = buildPeriodsFromRows(rows)
  return {
    code: 200,
    data: {
      view,
      history: rows,
      window: res.data.window || legacyWindow(rows),
      available_periods: periods,
      fallback: true,
    },
  }
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

const selectOverview = () => {
  if (historyMode.value === 'overview' && !historyError.value) return
  historyMode.value = 'overview'
  selectedMonth.value = 'all'
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

const normalizeLegacyVibrationRow = (row = {}) => {
  const timestamp = toNumber(row.timestamp ?? row.time)
  if (timestamp === null) return null
  const timestampSeconds = timestamp > 1e12 ? timestamp / 1000 : timestamp
  const date = shanghaiDateKey(timestampSeconds * 1000)
  return {
    timestamp: timestampSeconds,
    date,
    data: {
      rms: toNumber(row.rms ?? row.total_rms ?? row.data?.rms ?? row.data?.total_rms),
      freq: toNumber(row.freq ?? row.dominant_freq ?? row.data?.freq ?? row.data?.dominant_freq),
      temperature: toNumber(row.temperature ?? row.data?.temperature),
    },
  }
}

const legacyRowInRange = (row, view, year, month) => {
  if (view === 'recent24h') return true
  const date = new Date(`${row.date}T00:00:00+08:00`)
  if (year != null && Number.isInteger(Number(year)) && date.getFullYear() !== Number(year)) return false
  if (month != null && Number.isInteger(Number(month)) && date.getMonth() + 1 !== Number(month)) return false
  return true
}

const shanghaiDateKey = (timeMs) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(timeMs))
  const value = Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, part.value]))
  return `${value.year}-${value.month}-${value.day}`
}

const buildPeriodsFromRows = (rows = []) => {
  const map = new Map()
  rows.forEach(row => {
    const date = row?.date ? new Date(`${row.date}T00:00:00+08:00`) : null
    if (!date || Number.isNaN(date.getTime())) return
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    if (!map.has(year)) map.set(year, new Set())
    map.get(year).add(month)
  })
  return [...map.entries()]
    .map(([year, months]) => ({ year, months: [...months].sort((a, b) => a - b) }))
    .sort((a, b) => b.year - a.year)
}

const legacyWindow = (rows = []) => {
  const times = rows.map(row => toNumber(row.timestamp)).filter(value => value !== null)
  if (!times.length) return null
  return { start: Math.min(...times), end: Math.max(...times) }
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

const chartSeriesData = () => (chartData.value.history || [])
  .map(point => [pointTime(point), valueFromPoint(point)])
  .filter(point => Number.isFinite(point[0]))
  .sort((a, b) => a[0] - b[0])

const chartValues = () => chartSeriesData().map(point => point[1]).filter(value => value !== null && Number.isFinite(value))

const visibleDaySpan = () => {
  const option = chart?.getOption?.()
  const zoom = option?.dataZoom?.[0]
  const startValue = Number(zoom?.startValue)
  const endValue = Number(zoom?.endValue)
  if (Number.isFinite(startValue) && Number.isFinite(endValue) && endValue > startValue) {
    return Math.ceil((endValue - startValue) / DAY)
  }
  const points = chartSeriesData()
  const first = points[0]?.[0]
  const last = points.at(-1)?.[0]
  return Number.isFinite(first) && Number.isFinite(last) ? Math.ceil((last - first) / DAY) : 365
}

const formatXAxisLabel = (value) => {
  const date = new Date(value)
  if (historyMode.value === 'recent24h') {
    return date.toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false })
  }
  if (historyMode.value === 'overview') {
    const span = visibleDaySpan()
    if (span <= 45) return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    if (span <= 400) {
      return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    }
    return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' })
  }
  return selectedMonth.value === 'all'
    ? date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric' })
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

const yAxisFallback = (values) => {
  if (activeHistoryTab.value === 'vibration') return { min: 0, max: 0.2, ticks: 5 }
  if (activeHistoryTab.value === 'humidity') return { min: 0, max: 100, ticks: 5 }
  if (activeHistoryTab.value === 'temperature') return { min: 0, max: 35, ticks: 7 }
  const max = values.length ? Math.max(...values) : 0
  if (activeHistoryTab.value === 'rain') return { min: 0, max: max <= 5 ? 5 : Math.ceil(max / 5) * 5, ticks: 5 }
  return { min: 0, max: max <= 35 ? 35 : Math.ceil(max / 5) * 5, ticks: 7 }
}

const zeroRainPoints = points => activeHistoryTab.value === 'rain'
  ? points.filter(point => point[1] === 0).map(point => [point[0], 0])
  : []

const restorePointerTooltip = () => {
  if (!chart || chart.isDisposed() || !lastPointerPixel || !chart.containPixel('grid', lastPointerPixel)) return
  const dataPoint = chart.convertFromPixel({ seriesIndex: 0 }, lastPointerPixel)
  const targetTime = Number(dataPoint?.[0])
  if (!Number.isFinite(targetTime)) return
  const points = chartSeriesData()
  if (!points.length) return
  let nearestIndex = -1
  let nearestDistance = Number.POSITIVE_INFINITY
  points.forEach((point, index) => {
    if (point[1] === null) return
    const distance = Math.abs(point[0] - targetTime)
    if (distance < nearestDistance) {
      nearestIndex = index
      nearestDistance = distance
    }
  })
  if (nearestIndex < 0) return
  chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: nearestIndex })
}

const handleChartWheel = (event) => {
  if (historyMode.value !== 'overview' || !chart || chart.isDisposed()) return
  const pixel = [event.offsetX, event.offsetY]
  if (!chart.containPixel('grid', pixel)) return
  event.event?.preventDefault?.()
  event.event?.stopPropagation?.()
  lastPointerPixel = pixel

  const points = chartSeriesData()
  const dataStart = points[0]?.[0]
  const dataEnd = points.at(-1)?.[0]
  if (!Number.isFinite(dataStart) || !Number.isFinite(dataEnd) || dataEnd <= dataStart) return

  const option = chart.getOption()
  const zoom = option?.dataZoom?.[0] || {}
  const currentStart = Number.isFinite(Number(zoom.startValue)) ? Number(zoom.startValue) : dataStart
  const currentEnd = Number.isFinite(Number(zoom.endValue)) ? Number(zoom.endValue) : dataEnd
  const center = Number(chart.convertFromPixel({ seriesIndex: 0 }, pixel)?.[0])
  if (!Number.isFinite(center) || currentEnd <= currentStart) return

  const zoomIn = Number(event.wheelDelta) > 0
  const factor = zoomIn ? 0.78 : 1.24
  const minSpan = DAY
  const maxSpan = dataEnd - dataStart
  let nextSpan = Math.min(maxSpan, Math.max(minSpan, (currentEnd - currentStart) * factor))
  const leftRatio = (center - currentStart) / (currentEnd - currentStart)
  let nextStart = center - nextSpan * leftRatio
  let nextEnd = nextStart + nextSpan

  if (nextStart < dataStart) {
    nextStart = dataStart
    nextEnd = dataStart + nextSpan
  }
  if (nextEnd > dataEnd) {
    nextEnd = dataEnd
    nextStart = dataEnd - nextSpan
  }

  chart.dispatchAction({
    type: 'dataZoom',
    dataZoomIndex: 0,
    startValue: nextStart,
    endValue: nextEnd,
  })
  chart.dispatchAction({
    type: 'dataZoom',
    dataZoomIndex: 1,
    startValue: nextStart,
    endValue: nextEnd,
  })
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
  const fallback = yAxisFallback(values)
  const thresholdValues = activeHistoryTab.value === 'vibration' ? [WARNING_RMS, ALARM_RMS] : []
  const yRange = calcNiceYAxisRange([...values, ...thresholdValues], fallback, fallback.ticks)
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const recent = historyMode.value === 'recent24h'
  const overview = historyMode.value === 'overview'
  const dataStart = points[0]?.[0] ?? Date.now() - DAY
  const dataEnd = points.at(-1)?.[0] ?? Date.now()
  const zeroPoints = zeroRainPoints(points)
  const rainLegend = activeHistoryTab.value === 'rain'
    ? (recent ? '逐半小时新增雨量' : '逐日雨量')
    : meta.label
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
    legend: activeHistoryTab.value === 'rain' ? {
      show: true,
      bottom: overview ? 34 : 4,
      left: 12,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: '#b7cae4', fontSize: 12 },
      data: [rainLegend, '0 mm'],
    } : undefined,
    grid: { left: 46, right: 54, bottom: overview ? 78 : 48, top: 44, containLabel: true },
    dataZoom: overview
      ? [{
          type: 'inside',
          zoomOnMouseWheel: false,
          moveOnMouseWheel: true,
          moveOnMouseMove: true,
          filterMode: 'none',
          minValueSpan: DAY,
          startValue: dataStart,
          endValue: dataEnd,
        }, {
          type: 'slider',
          height: 24,
          bottom: 10,
          borderColor: 'rgba(89, 155, 255, 0.32)',
          backgroundColor: 'rgba(7, 19, 38, 0.82)',
          fillerColor: 'rgba(47, 151, 255, 0.18)',
          handleStyle: { color: '#8fbfff', borderColor: '#d8e8ff' },
          moveHandleStyle: { color: '#5aa7ff' },
          textStyle: { color: '#9fb6d3' },
          brushSelect: false,
          filterMode: 'none',
          minValueSpan: DAY,
          startValue: dataStart,
          endValue: dataEnd,
        }]
      : [],
    xAxis: {
      type: 'time',
      min: Number.isFinite(windowStart) && recent ? windowStart : dataStart,
      max: Number.isFinite(windowEnd) && recent ? windowEnd : dataEnd,
      interval: recent ? 3 * HOUR : (overview ? DAY : (selectedMonth.value === 'all' ? 30 * DAY : 5 * DAY)),
      minInterval: overview ? DAY : (recent ? 30 * MINUTE : DAY),
      name: recent ? '时间' : '日期',
      nameLocation: 'end',
      nameGap: 18,
      nameTextStyle: { color: '#b6c7df', fontSize: 12, padding: [22, 0, 0, 0] },
      axisLine: { show: true, symbol: ['none', 'arrow'], symbolSize: [8, 10], lineStyle: { color: 'rgba(121, 155, 202, 0.68)' } },
      axisTick: { show: true, lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisLabel: { color: '#91a9ca', margin: 12, hideOverlap: true, formatter: formatXAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yRange.min,
      max: yRange.max,
      interval: yRange.interval,
      name: meta.unit,
      nameLocation: 'end',
      nameGap: 18,
      nameTextStyle: { color: '#b6c7df', fontSize: 12, padding: [0, 36, 4, 0] },
      axisLine: { show: true, symbol: ['none', 'arrow'], symbolSize: [8, 10], lineStyle: { color: 'rgba(121, 155, 202, 0.68)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#b6c7df',
        margin: 12,
        formatter: value => activeHistoryTab.value === 'vibration'
          ? Number(value).toFixed(2)
          : String(Number(value).toFixed(Number.isInteger(value) ? 0 : 1)),
      },
      splitLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.18)', width: 1 } },
    },
    series: [{
      id: `history-${activeHistoryTab.value}`,
      name: rainLegend,
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
  if (!chart || chart.isDisposed()) return
  chart.setOption(fullChartOption(), {
    notMerge: false,
    replaceMerge: ['legend', 'xAxis', 'yAxis', 'dataZoom', 'series'],
    lazyUpdate: true,
  })
}

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption(fullChartOption(), true)
  chart.getZr().on('mousemove', event => {
    lastPointerPixel = [event.offsetX, event.offsetY]
  })
  chart.getZr().on('mousewheel', handleChartWheel)
  chart.on('datazoom', () => {
    window.requestAnimationFrame(restorePointerTooltip)
  })
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
    const [tempCurrent, tempPrevious, rainRecent, windRecent, vibrationCurrent, vibrationPrevious] = await Promise.allSettled([
      getTempHumidityTrends({ view: 'calendar', year, month: null }),
      getTempHumidityTrends({ view: 'calendar', year: previousYear, month: null }),
      getRainTrends({ view: 'rolling12' }),
      getWindTrends({ view: 'rolling12' }),
      fetchVibrationHistory({ view: 'calendar', year, month: null }),
      fetchVibrationHistory({ view: 'calendar', year: previousYear, month: null }),
    ])
    const tempCurrentRes = fulfilledResponse(tempCurrent)
    const tempPreviousRes = fulfilledResponse(tempPrevious)
    const rainRecentRes = fulfilledResponse(rainRecent)
    const windRecentRes = fulfilledResponse(windRecent)
    const vibrationCurrentRes = fulfilledResponse(vibrationCurrent)
    const vibrationPreviousRes = fulfilledResponse(vibrationPrevious)
    const tempRecentSource = [
      ...(tempPreviousRes?.data?.history || []),
      ...(tempCurrentRes?.data?.history || []),
    ]
    if (tempCurrentRes?.code === 200 || tempPreviousRes?.code === 200) {
      summaryData.tempRecent = filterLast12Months(tempRecentSource)
    }
    if (rainRecentRes?.code === 200) summaryData.rainRecent = rainRecentRes.data?.history || []
    if (windRecentRes?.code === 200) summaryData.windRecent = windRecentRes.data?.history || []
    const vibrationRecentSource = [
      ...(vibrationPreviousRes?.data?.history || []),
      ...(vibrationCurrentRes?.data?.history || []),
    ]
    if (vibrationCurrentRes?.code === 200 || vibrationPreviousRes?.code === 200) {
      summaryData.vibrationRecent = filterLast12Months(vibrationRecentSource)
    }

    const [tempAll, rainAll, windAll, vibrationAll] = await Promise.allSettled([
      loadAllCalendarRows(
        periodUnion([
          ...(tempCurrentRes?.data?.available_periods || []),
          ...(tempPreviousRes?.data?.available_periods || []),
        ]),
        period => getTempHumidityTrends({ view: 'calendar', year: period.year, month: null }),
      ),
      rainRecentRes?.code === 200
        ? loadAllCalendarRows(
            rainRecentRes.data?.available_periods || [],
            period => getRainTrends({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
      windRecentRes?.code === 200
        ? loadAllCalendarRows(
            windRecentRes.data?.available_periods || [],
            period => getWindTrends({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
      (vibrationCurrentRes?.code === 200 || vibrationPreviousRes?.code === 200)
        ? loadAllCalendarRows(
            periodUnion([
              ...(vibrationCurrentRes?.data?.available_periods || []),
              ...(vibrationPreviousRes?.data?.available_periods || []),
            ]),
            period => fetchVibrationHistory({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
    ])
    summaryData.tempAll = fulfilledValue(tempAll) || summaryData.tempRecent
    summaryData.rainAll = fulfilledValue(rainAll) || summaryData.rainRecent
    summaryData.windAll = fulfilledValue(windAll) || summaryData.windRecent
    summaryData.vibrationAll = fulfilledValue(vibrationAll) || summaryData.vibrationRecent
  } catch (error) {
    console.warn('加载统计摘要失败:', error)
  }
}

const fulfilledResponse = result => result.status === 'fulfilled' ? result.value : null
const fulfilledValue = result => result.status === 'fulfilled' ? result.value : null

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

const buildMonthlyStats = ({ temp = [], wind = [], vibration = [] } = {}) => {
  const result = {
    temperatureMax: new Map(),
    temperatureMin: new Map(),
    humidity: new Map(),
    wind: new Map(),
    vibration: new Map(),
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
  vibration.forEach(row => {
    pushMonthValue(result.vibration, monthFromRow(row), toNumber(row.data?.rms))
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
  fetchRealtime()
  loadHistory(currentQuery())
  summaryTimer = window.setTimeout(() => {
    if (isMounted) loadSummary()
  }, 2200)
  realtimeTimer = setInterval(fetchRealtime, 5000)
})

onUnmounted(() => {
  isMounted = false
  requestSerial += 1
  if (realtimeTimer) clearInterval(realtimeTimer)
  if (refreshTimer) clearTimeout(refreshTimer)
  if (summaryTimer) clearTimeout(summaryTimer)
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
  grid-auto-flow: column;
  grid-auto-columns: minmax(360px, 1fr);
  gap: 12px;
  margin-bottom: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 8px;
  scroll-snap-type: x proximity;
  scroll-behavior: smooth;
  scrollbar-color: rgba(54, 151, 255, 0.55) rgba(9, 25, 48, 0.55);
  scrollbar-width: thin;
}

.live-grid::-webkit-scrollbar {
  height: 8px;
}

.live-grid::-webkit-scrollbar-track {
  border-radius: 999px;
  background: rgba(9, 25, 48, 0.55);
}

.live-grid::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: linear-gradient(90deg, #2f97ff, #52e5bd);
}

.live-card {
  min-width: 0;
  min-height: 166px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 16px;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 10px;
  background:
    linear-gradient(145deg, rgba(16, 34, 61, 0.98), rgba(9, 23, 43, 0.98));
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
  scroll-snap-align: start;
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
  margin: 4px 0 0;
}

.metric-row.metric-columns {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-cell strong {
  display: block;
  color: #fff;
  font: 800 30px/1 "Consolas", "Monaco", monospace;
  white-space: nowrap;
}

.metric-columns .metric-cell strong {
  font-size: 26px;
}

.metric-cell span {
  display: block;
  margin-top: 9px;
  color: #8ea8c9;
  font-size: 14px;
}

.wind-card-body {
  min-height: 78px;
  margin: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr) 42px;
  align-items: center;
  gap: 12px;
}

.wind-primary strong,
.wind-direction strong {
  display: block;
  color: #fff;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.wind-primary strong {
  font-family: "Consolas", "Monaco", monospace;
  font-size: 30px;
}

.wind-direction strong {
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 32px;
  letter-spacing: 0;
}

.wind-primary span,
.wind-direction span {
  display: block;
  margin-top: 8px;
  color: #8ea8c9;
  font-size: 14px;
}

.mini-compass {
  position: relative;
  width: 38px;
  height: 38px;
  border: 1px solid rgba(116, 201, 249, 0.45);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(38, 82, 128, 0.35), rgba(13, 31, 57, 0.2));
}

.mini-compass::before {
  content: "N";
  position: absolute;
  top: 2px;
  left: 50%;
  transform: translateX(-50%);
  color: #8ea8c9;
  font-size: 9px;
  font-weight: 700;
}

.mini-compass i {
  position: absolute;
  top: 54%;
  left: 50%;
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 18px solid #72cdf9;
  transform-origin: 50% 70%;
  filter: drop-shadow(0 0 8px rgba(114, 205, 249, 0.45));
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
  display: flex;
  align-items: center;
  gap: 8px;
  color: #f4f8ff;
}

.info-icon {
  min-width: 34px;
  height: 26px;
  padding: 0 8px;
  display: inline-grid;
  place-items: center;
  border-radius: 6px;
  background:
    linear-gradient(135deg, rgba(45, 170, 255, 0.24), rgba(82, 229, 189, 0.16));
  color: #bdf6ff;
  font-style: normal;
  font: 800 12px/1 "Consolas", "Monaco", monospace;
  box-shadow: inset 0 0 0 1px rgba(129, 214, 255, 0.24);
}

.summary-row strong {
  color: #ffffff;
  font-weight: 700;
}

@media (max-width: 1280px) {
  .live-grid {
    grid-auto-columns: minmax(330px, 1fr);
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
    grid-auto-columns: minmax(280px, 88vw);
  }

  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wind-card-body {
    grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr) 38px;
  }

  .wind-primary strong,
  .wind-direction strong {
    font-size: 22px;
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
