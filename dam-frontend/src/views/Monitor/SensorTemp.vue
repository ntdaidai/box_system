<template>
  <div class="sensor-detail">
    <div class="detail-header">
      <div class="header-left">
        <img src="@/assets/images/sensors/temp_humidity.png" class="header-icon" />
        <div class="header-info">
          <h2>温湿度传感器</h2>
        </div>
      </div>
      <div class="header-status" :class="statusClass">
        <span class="dot"></span>{{ statusText }}
        <div class="header-comm" v-if="lastTimestamp">{{ formatCommTime(lastTimestamp) }}</div>
      </div>
    </div>

    <!-- 合并卡片：实时数据 + 温湿度 + 运行区间 -->
    <div class="data-panel">
      <div class="panel-title">实时数据</div>
      <!-- 温湿度大数字 -->
      <div class="metric-row-merged">
        <div class="metric-big">
          <div class="metric-big-icon">🌡️</div>
          <div class="metric-big-body">
            <div class="metric-big-label">温度</div>
            <div class="metric-big-value">{{ data.temperature != null ? data.temperature.toFixed(1) : '--' }}<span class="metric-big-unit">℃</span></div>
          </div>
        </div>
        <div class="metric-divider"></div>
        <div class="metric-big">
          <div class="metric-big-icon">💧</div>
          <div class="metric-big-body">
            <div class="metric-big-label">湿度</div>
            <div class="metric-big-value">{{ data.humidity != null ? data.humidity.toFixed(1) : '--' }}<span class="metric-big-unit">%</span></div>
          </div>
        </div>
      </div>
      <!-- 运行区间 -->
      <div class="range-grid">
        <div class="range-card">
          <div class="range-top">
            <span>近24小时温度范围</span>
            <strong>{{ tempMinMax }}</strong>
          </div>
          <div class="range-track">
            <i :style="{ left: tempPosition + '%' }"></i>
          </div>
          <div class="range-note">参考运行区间：18℃ - 28℃</div>
        </div>
        <div class="range-card">
          <div class="range-top">
            <span>当前湿度状态</span>
            <strong>{{ humidityState }}</strong>
          </div>
          <div class="range-track humidity">
            <i :style="{ left: humidityPosition + '%' }"></i>
          </div>
          <div class="range-note">参考运行区间：40% - 75%</div>
        </div>
      </div>
    </div>

    <!-- 温湿度趋势：近24小时 + 年/月日极值 -->
    <div class="data-panel history-panel">
      <div class="panel-header history-panel-header">
        <div class="history-heading">
          <span class="panel-title">温湿度趋势</span>
          <div class="metric-switch" aria-label="温湿度指标选择">
            <button
              type="button"
              :class="{ active: selectedMetric === 'temperature' }"
              @click="selectMetric('temperature')"
            ><span>♨</span>温度</button>
            <button
              type="button"
              :class="{ active: selectedMetric === 'humidity' }"
              @click="selectMetric('humidity')"
            ><span>◉</span>湿度</button>
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
          <div class="chart-container" ref="chartRef"></div>
          <div v-if="historyLoading" class="chart-loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">正在读取聚合数据...</div>
          </div>
          <div v-else-if="historyError" class="chart-loading-overlay">
            <div class="loading-text">{{ historyError }}</div>
          </div>
          <div v-else-if="seriesSelectionEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">请至少勾选一条极值曲线</div>
          </div>
          <div v-else-if="historyEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">该时间范围暂无{{ selectedMetricLabel }}数据</div>
          </div>
        </div>

        <div v-if="historyMode === 'calendar' && selectedMetric === 'temperature'" class="series-toggles">
          <label class="series-toggle minimum">
            <input v-model="seriesVisibility.min" type="checkbox" @change="renderChart" />
            <span class="checkbox-ui"></span>
            <i></i>{{ dailyMinimumLabel }}
          </label>
          <label class="series-toggle maximum">
            <input v-model="seriesVisibility.max" type="checkbox" @change="renderChart" />
            <span class="checkbox-ui"></span>
            <i></i>{{ dailyMaximumLabel }}
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { getSensorRealtime, getTempHumidityTrends } from '@/api/sensor'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, runWhenIdle } from '@/utils/sensorDetailStartup'
import * as echarts from 'echarts'

const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR
const TREND_URL = '/v1/sensor/history/temp-humidity/trends'

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const lastTimestamp = ref(0)
const historyMode = ref('recent24h')
const selectedMetric = ref('temperature')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref('all')
const availablePeriods = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'recent24h', history: [], window: null })
const recentData = ref(null)
const seriesVisibility = reactive({ min: true, max: true })
const historyCache = new Map()

let chart = null
let timer = null
let historyRefreshTimer = null
let preloadIdleTask = null
let resizeHandler = null

const metricMeta = computed(() => selectedMetric.value === 'temperature'
  ? {
      label: '温度', unit: '℃', shortUnit: '°', color: '#ff4d5d',
      minColor: '#1687ff', maxColor: '#ff3f50', fallback: { min: 10, max: 30 },
    }
  : {
      label: '湿度', unit: '%', shortUnit: '%', color: '#20a8ff',
      minColor: '#45b9ff', maxColor: '#1676ff', fallback: { min: 30, max: 90 },
    })

const selectedMetricLabel = computed(() => metricMeta.value.label)
const dailyMinimumLabel = computed(() => '每日最低温')
const dailyMaximumLabel = computed(() => '每日最高温')

const yearOptions = computed(() => {
  const years = availablePeriods.value.map(item => Number(item.year)).filter(Number.isFinite)
  return years.length ? years : [new Date().getFullYear()]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  return (period?.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const toNumericValue = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const numericValues = (values) => values
  .map(toNumericValue)
  .filter(value => value !== null)

const recentMetricValues = (metric = selectedMetric.value) => numericValues(
  (recentData.value?.history || []).map(point => point.data?.[metric]),
)

const tempMinMax = computed(() => {
  const values = recentMetricValues('temperature')
  if (!values.length) return '--'
  return `${Math.min(...values).toFixed(1)}℃ / ${Math.max(...values).toFixed(1)}℃`
})

const tempPosition = computed(() => {
  const value = Number(data.value.temperature)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, (value / 45) * 100))
})

const humidityPosition = computed(() => {
  const value = Number(data.value.humidity)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, value))
})

const humidityState = computed(() => {
  const value = Number(data.value.humidity)
  if (!Number.isFinite(value)) return '--'
  if (value < 40) return '偏干'
  if (value > 75) return '偏湿'
  return '适宜'
})

const metricSeriesValues = computed(() => {
  if (historyMode.value === 'recent24h') {
    return numericValues((chartData.value.history || []).map(point => point.data?.[selectedMetric.value]))
  }
  if (selectedMetric.value === 'humidity') {
    return numericValues((chartData.value.history || []).map(point => point.data?.humidity))
  }
  const minimum = `${selectedMetric.value}_min`
  const maximum = `${selectedMetric.value}_max`
  return numericValues((chartData.value.history || []).flatMap(point => [point.data?.[minimum], point.data?.[maximum]]))
})

const historyEmpty = computed(() => metricSeriesValues.value.length === 0)
const seriesSelectionEmpty = computed(() => (
  historyMode.value === 'calendar'
  && selectedMetric.value === 'temperature'
  && !seriesVisibility.min
  && !seriesVisibility.max
))

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
    const res = await getSensorRealtime('temp_humidity')
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

const currentQuery = () => historyMode.value === 'recent24h'
  ? { view: 'recent24h' }
  : {
      view: 'calendar',
      year: Number(selectedYear.value),
      month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
    }

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
  const selected = periods.find(item => Number(item.year) === Number(selectedYear.value))
  if (!selected) {
    selectedYear.value = Number(periods[0].year)
    selectedMonth.value = 'all'
    return
  }
  if (selectedMonth.value !== 'all' && !selected.months?.map(Number).includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
}

const applyTrendPayload = (payload, query, apply = true) => {
  if (!payload) return null
  syncAvailablePeriods(payload.available_periods)
  const normalized = { ...payload, history: payload.history || [] }
  historyCache.set(queryKey(query), normalized)
  if (query.view === 'recent24h') recentData.value = normalized
  if (apply) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadTrends = async (query = currentQuery(), apply = true, force = false) => {
  const key = queryKey(query)
  if (!force && historyCache.has(key)) {
    return applyTrendPayload(historyCache.get(key), query, apply)
  }

  if (apply) {
    historyLoading.value = true
    historyError.value = ''
  }
  try {
    const res = await getTempHumidityTrends(query)
    if (res.code !== 200) throw new Error('趋势响应无效')
    return applyTrendPayload(res.data, query, apply)
  } catch (error) {
    console.warn('加载温湿度趋势失败:', error)
    if (apply) historyError.value = '历史数据服务暂时不可用，请稍后重试'
    return null
  } finally {
    if (apply) historyLoading.value = false
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
  const interval = 30 * 60 * 1000
  return Math.floor(now / interval) * interval + interval - now
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  const delay = historyMode.value === 'recent24h' ? millisecondsToNextHalfHour() + 1000 : 30 * 60 * 1000
  historyRefreshTimer = setTimeout(async () => {
    const query = currentQuery()
    historyCache.delete(queryKey(query))
    await loadTrends(query, true, true)
    renderChart()
    scheduleHistoryRefresh()
  }, delay)
}

const selectRecent24h = async () => {
  if (historyMode.value === 'recent24h') return
  historyMode.value = 'recent24h'
  await loadTrends(currentQuery())
  renderChart()
  scheduleHistoryRefresh()
}

const onYearChange = async () => {
  historyMode.value = 'calendar'
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
  await loadTrends(currentQuery())
  renderChart()
  scheduleHistoryRefresh()
}

const onMonthChange = async () => {
  historyMode.value = 'calendar'
  await loadTrends(currentQuery())
  renderChart()
  scheduleHistoryRefresh()
}

const selectMetric = (metric) => {
  if (selectedMetric.value === metric) return
  selectedMetric.value = metric
  renderChart()
}

const toCalendarTimestamp = (dateValue) => new Date(`${dateValue}T00:00:00+08:00`).getTime()

const chartSeriesData = (field) => {
  if (historyMode.value === 'recent24h') {
    return (chartData.value.history || []).map(point => [
      Number(point.timestamp) * 1000,
      toNumericValue(point.data?.[field]),
    ])
  }
  return (chartData.value.history || []).map(point => [
    toCalendarTimestamp(point.date),
    toNumericValue(point.data?.[field]),
  ])
}

const formatXAxisLabel = (value) => {
  const dateValue = new Date(value)
  if (historyMode.value === 'recent24h') {
    return dateValue.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  if (selectedMonth.value === 'all') return `${dateValue.getMonth() + 1}月`
  return `${dateValue.getDate()}日`
}

const tooltipFormatter = (params) => {
  const items = Array.isArray(params) ? params : [params]
  if (!items.length || !items[0]?.value) return ''
  const dateValue = new Date(items[0].value[0])
  const heading = historyMode.value === 'recent24h'
    ? dateValue.toLocaleString('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    : dateValue.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  const rows = items
    .filter(item => item.value?.[1] != null)
    .map(item => `<div style="display:flex;justify-content:space-between;gap:24px;margin-top:7px">`
      + `<span>${item.marker}${item.seriesName}</span>`
      + `<strong>${Number(item.value[1]).toFixed(1)}${metricMeta.value.unit}</strong></div>`)
    .join('')
  return `<div style="min-width:150px"><strong>${heading}</strong>${rows}</div>`
}

const buildLineSeries = ({ id, name, data: points, color, areaOpacity = 0.08, markToday = false }) => {
  const series = {
    id,
    name,
    type: 'line',
    data: points,
    showSymbol: false,
    symbol: 'circle',
    symbolSize: 6,
    smooth: historyMode.value === 'recent24h' ? 0.32 : 0.16,
    smoothMonotone: 'x',
    connectNulls: false,
    clip: true,
    z: 3,
    lineStyle: { color, width: historyMode.value === 'recent24h' ? 2.4 : 1.7 },
    itemStyle: { color, borderColor: '#ffffff', borderWidth: 1 },
    emphasis: { focus: 'series', scale: true },
    animationDuration: 900,
    animationDurationUpdate: 650,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    universalTransition: true,
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: `${color}${Math.round(areaOpacity * 255).toString(16).padStart(2, '0')}` },
        { offset: 1, color: `${color}00` },
      ]),
    },
  }

  if (markToday && historyMode.value === 'calendar') {
    const today = new Date()
    const todayValue = new Date(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}T00:00:00+08:00`).getTime()
    const start = Number(chartData.value.window?.start) * 1000
    const end = Number(chartData.value.window?.end) * 1000
    if (todayValue >= start && todayValue < end) {
      series.markLine = {
        silent: true,
        symbol: ['none', 'none'],
        lineStyle: { color: 'rgba(255,255,255,0.48)', width: 1, type: 'solid' },
        label: {
          show: true, formatter: '今天', position: 'insideEndTop', color: '#fff',
          backgroundColor: '#343b4d', borderRadius: 10, padding: [3, 9], fontWeight: 600,
        },
        data: [{ xAxis: todayValue }],
      }
    }
  }
  return series
}

const fullChartOption = () => {
  const meta = metricMeta.value
  const recent = historyMode.value === 'recent24h'
  const minimumField = `${selectedMetric.value}_min`
  const maximumField = `${selectedMetric.value}_max`
  const recentPoints = recent ? chartSeriesData(selectedMetric.value) : []
  const humidityCalendar = !recent && selectedMetric.value === 'humidity'
  const minimumPoints = recent || humidityCalendar ? [] : chartSeriesData(minimumField)
  const maximumPoints = recent || humidityCalendar ? [] : chartSeriesData(maximumField)
  const dailyAveragePoints = humidityCalendar
    ? chartSeriesData('humidity')
    : []
  const allValues = numericValues(
    [...recentPoints, ...minimumPoints, ...maximumPoints, ...dailyAveragePoints].map(point => point[1]),
  )
  const yRange = calcNiceYAxisRange(
    allValues,
    meta.fallback,
    selectedMetric.value === 'humidity' ? 6 : 5,
  )

  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const xMin = Number.isFinite(windowStart) ? windowStart : Date.now() - DAY
  const xMax = Number.isFinite(windowEnd)
    ? windowEnd - (recent ? 0 : DAY)
    : Date.now()
  const tickInterval = recent ? 3 * HOUR : (selectedMonth.value === 'all' ? 30 * DAY : 5 * DAY)
  const series = []

  if (recent) {
    series.push(buildLineSeries({
      id: 'recent-average', name: `${meta.label}（30分钟平均）`,
      data: recentPoints, color: meta.color, areaOpacity: 0.16,
    }))
  } else if (selectedMetric.value === 'humidity') {
    series.push(buildLineSeries({
      id: 'daily-average', name: '每日平均湿度', data: dailyAveragePoints,
      color: meta.color, areaOpacity: 0.14, markToday: true,
    }))
  } else {
    if (seriesVisibility.min) {
      series.push(buildLineSeries({
        id: 'daily-minimum', name: dailyMinimumLabel.value,
        data: minimumPoints, color: meta.minColor, areaOpacity: 0.12, markToday: true,
      }))
    }
    if (seriesVisibility.max) {
      series.push(buildLineSeries({
        id: 'daily-maximum', name: dailyMaximumLabel.value,
        data: maximumPoints, color: meta.maxColor, areaOpacity: 0.08,
        markToday: !seriesVisibility.min,
      }))
    }
  }

  return {
    animation: true,
    animationDuration: 900,
    animationDurationUpdate: 650,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', confine: true, formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)', borderColor: 'rgba(89, 155, 255, 0.55)', borderWidth: 1,
      padding: [11, 13], textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(151, 190, 255, 0.55)', type: 'dashed' } },
    },
    grid: { left: 18, right: 22, bottom: 18, top: 24, containLabel: true },
    xAxis: {
      type: 'time', min: xMin, max: xMax, interval: tickInterval, minInterval: tickInterval,
      axisLine: { lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisTick: { show: true, lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisLabel: { color: '#91a9ca', margin: 12, hideOverlap: true, formatter: formatXAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true, min: yRange.min, max: yRange.max, interval: yRange.interval,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#b6c7df', margin: 12, formatter: value => `${value}${meta.shortUnit}` },
      splitLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.18)', width: 1 } },
    },
    series,
  }
}

const renderChart = () => {
  if (!chart) return
  chart.setOption(fullChartOption(), {
    notMerge: false,
    replaceMerge: ['series'],
    lazyUpdate: false,
  })
}

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption(fullChartOption(), true)
  resizeHandler = () => chart?.resize()
  window.addEventListener('resize', resizeHandler)
}

onMounted(() => {
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
  if (timer) clearInterval(timer)
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  window.removeEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  if (chart) chart.dispose()
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

/* 指标卡片 */
.metric-row-merged {
  display: flex;
  align-items: stretch;
  gap: 0;
  margin: 12px 0;
}
.metric-big {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
}
.metric-divider {
  width: 1px;
  background: rgba(0, 200, 255, 0.15);
  margin: 0 8px;
  align-self: stretch;
}
.metric-big-icon { font-size: 36px; line-height: 1; opacity: 0.85; }
.metric-big-body { flex: 1; }
.metric-big-label { font-size: 13px; color: var(--text-secondary); margin-bottom: 2px; }
.metric-big-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--accent-color);
  line-height: 1.2;
  font-family: "Consolas", "Monaco", monospace;
}
.metric-big-unit {
  font-size: 16px;
  font-weight: 400;
  color: var(--text-muted);
  margin-left: 2px;
}

.data-panel { background: var(--bg-panel); border: 1px solid var(--border-color); border-radius: 10px; padding: 16px; }
.panel-title { font-size: 15px; font-weight: 500; color: var(--text-primary); }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.chart-wrap { position: relative; height: 340px; }
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
.range-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
.range-card { padding: 10px 12px; background: rgba(0, 0, 0, 0.16); border: 1px solid rgba(0, 200, 255, 0.08); border-radius: 8px; }
.range-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: var(--text-secondary); font-size: 13px; }
.range-top strong { color: var(--text-primary); font-size: 15px; }
.range-track { position: relative; height: 6px; margin-top: 12px; background: linear-gradient(90deg, #409eff 0%, #67c23a 42%, #67c23a 62%, #f56c6c 100%); border-radius: 999px; }
.range-track.humidity { background: linear-gradient(90deg, #e6a23c 0%, #67c23a 40%, #67c23a 75%, #409eff 100%); }
.range-track i { position: absolute; top: -5px; width: 4px; height: 16px; transform: translateX(-50%); background: #fff; border-radius: 2px; box-shadow: 0 0 8px rgba(255,255,255,0.7); }
.range-note { margin-top: 8px; color: var(--text-muted); font-size: 12px; }

/* 气象站式趋势面板 */
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
  margin: 0;
  padding: 16px 18px;
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
.metric-switch {
  display: inline-flex;
  align-items: center;
  gap: 5px;
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
  background: transparent;
  color: #8fa7c8;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}
.metric-switch button:hover { color: #dceaff; }
.metric-switch button.active {
  color: #091426;
  font-weight: 700;
  background: linear-gradient(135deg, #ffd84a, #ffbc27);
  box-shadow: 0 4px 14px rgba(255, 190, 35, 0.24);
}
.metric-switch button:nth-child(2).active {
  color: #fff;
  background: linear-gradient(135deg, #21a9ff, #2572e7);
  box-shadow: 0 4px 14px rgba(31, 133, 255, 0.26);
}
.history-chart-wrap { height: 392px; }
.history-chart-wrap .chart-loading-overlay {
  background: rgba(8, 22, 43, 0.78);
  backdrop-filter: blur(3px);
}
.history-chart-wrap .chart-hint-overlay { background: rgba(8, 22, 43, 0.5); }
.history-chart-wrap .loading-spinner {
  width: 34px;
  height: 34px;
  border-color: rgba(55, 140, 255, 0.18);
  border-top-color: #438fff;
}

.series-toggles {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 4px 10px 0;
  border-top: 1px solid rgba(123, 154, 201, 0.1);
}
.series-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #b7cae4;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}
.series-toggle input { position: absolute; width: 1px; height: 1px; opacity: 0; }
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
.series-toggle input:checked + .checkbox-ui { border-color: #2d8cff; background: #247ee8; }
.series-toggle input:checked + .checkbox-ui::after { content: '✓'; color: #fff; font-size: 11px; font-weight: 700; line-height: 1; }
.series-toggle i { width: 18px; height: 3px; border-radius: 999px; background: #1687ff; box-shadow: 0 0 8px rgba(22, 135, 255, 0.4); }
.series-toggle.maximum i { background: #ff3f50; box-shadow: 0 0 8px rgba(255, 63, 80, 0.35); }

@media (max-width: 900px) {
  .history-panel-header { align-items: flex-start; }
  .history-controls { width: 100%; flex-wrap: wrap; }
  .history-chart-wrap { height: 340px; }
}

@media (max-width: 560px) {
  .range-grid { grid-template-columns: 1fr; }
  .history-heading { width: 100%; align-items: flex-start; flex-direction: column; gap: 12px; }
  .calendar-controls { width: 100%; }
  .history-select.year-select, .history-select.month-select { flex: 1; width: auto; }
  .series-toggles { gap: 14px; flex-wrap: wrap; }
}
</style>
