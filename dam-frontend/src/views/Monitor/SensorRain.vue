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
        <div class="header-comm" v-if="lastTimestamp">最后通讯: {{ formatCommTime(lastTimestamp) }}</div>
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

    <!-- 逐日雨量历史 -->
    <div class="data-panel history-panel">
      <div class="history-panel-header">
        <span class="panel-title">降水趋势</span>
        <div class="calendar-controls">
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

      <div class="trend-shell">
        <div class="history-stat-strip">
          <div v-for="item in historyStats" :key="item.label" class="history-stat">
            <span>{{ item.label }}</span>
            <strong :class="item.tone">{{ item.value }}</strong>
          </div>
        </div>

        <div class="chart-wrap history-chart-wrap">
          <div class="chart-container" ref="chartRef"></div>
          <div v-if="historyLoading" class="chart-loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">正在读取逐日雨量...</div>
          </div>
          <div v-else-if="historyError" class="chart-loading-overlay">
            <div class="loading-text">{{ historyError }}</div>
          </div>
          <div v-else-if="historyEmpty" class="chart-loading-overlay chart-hint-overlay">
            <div class="loading-text">该时间范围暂无逐日雨量数据</div>
          </div>
        </div>

        <div class="rain-series-legend">
          <i></i>
          <span>逐日雨量</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getRainTrends, getSensorRealtime } from '@/api/sensor'
import {
  buildDailyRainChartValues,
  buildDailyRainRows,
  resolveRainCalendarSelection,
  toRainNumber,
} from '@/utils/rainHistory'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, runWhenIdle } from '@/utils/sensorDetailStartup'
import { Pouring } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const TREND_URL = '/v1/sensor/history/rain/trends'

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref('all')
const availablePeriods = ref([])
const lastTimestamp = ref(0)
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'calendar', history: [], window: null })
const historyCache = new Map()

let chart = null
let timer = null
let historyRefreshTimer = null
let preloadIdleTask = null
let resizeHandler = null

const yearOptions = computed(() => {
  const years = availablePeriods.value.map(item => Number(item.year)).filter(Number.isFinite)
  return years.length ? years : [new Date().getFullYear()]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  return (period?.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const dailyRainRows = computed(() => buildDailyRainRows(chartData.value.history || []))

const historyEmpty = computed(() => dailyRainRows.value.length === 0)

const formatRain = (value) => {
  const numeric = toRainNumber(value)
  return numeric === null ? '--' : `${numeric.toFixed(1)} mm`
}

const formatRainDate = (dateValue) => {
  if (!dateValue) return '--'
  const value = new Date(`${dateValue}T00:00:00+08:00`)
  return value.toLocaleDateString('zh-CN', {
    month: 'numeric', day: 'numeric',
    ...(selectedMonth.value === 'all' ? { year: 'numeric' } : {}),
  })
}

const historyStats = computed(() => {
  const rows = dailyRainRows.value
  const wetDays = rows.filter(row => row.value > 0).length
  const maximum = rows.reduce((result, row) => (
    !result || row.value > result.value ? row : result
  ), null)
  return [
    { label: '最大日雨量', value: formatRain(maximum?.value), tone: 'maximum' },
    { label: '最大雨量日期', value: maximum?.value > 0 ? formatRainDate(maximum.date) : '--', tone: 'date' },
    { label: '有雨天数', value: `${wetDays} 天`, tone: 'wet-days' },
    { label: '有效数据', value: `${rows.length} 天`, tone: '' },
  ]
})

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
  return new Date(ts * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
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

const queryKey = ({ year, month }) => [year, month || 'all'].join(':')

const currentQuery = () => ({
  year: Number(selectedYear.value),
  month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
})

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
  const selection = resolveRainCalendarSelection(periods, selectedYear.value, selectedMonth.value)
  selectedYear.value = selection.year
  selectedMonth.value = selection.month
}

const applyTrendPayload = (payload, query, apply = true) => {
  if (!payload) return null
  syncAvailablePeriods(payload.available_periods)
  const normalized = { ...payload, history: payload.history || [] }
  historyCache.set(queryKey(query), normalized)
  if (apply && queryKey(query) === queryKey(currentQuery())) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadTrends = async (query = currentQuery(), apply = true, force = false) => {
  const key = queryKey(query)
  if (!force && historyCache.has(key)) {
    const normalized = applyTrendPayload(historyCache.get(key), query, apply)
    if (apply && key !== queryKey(currentQuery())) {
      return loadTrends(currentQuery(), true, force)
    }
    return normalized
  }

  if (apply) {
    historyLoading.value = true
    historyError.value = ''
  }
  try {
    const res = await getRainTrends(query)
    if (res.code !== 200) throw new Error('逐日雨量响应无效')
    const normalized = applyTrendPayload(res.data, query, apply)
    if (apply && key !== queryKey(currentQuery())) {
      return await loadTrends(currentQuery(), true, force)
    }
    return normalized
  } catch (error) {
    console.warn('加载逐日雨量失败:', error)
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
    year: params.year != null ? Number(params.year) : new Date().getFullYear(),
    month: params.month != null ? Number(params.month) : null,
  }
  const shouldApply = queryKey(query) === queryKey(currentQuery())
  applyTrendPayload(detail.data.data, query, shouldApply)
  if (shouldApply && queryKey(query) === queryKey(currentQuery())) {
    renderChart()
  } else if (shouldApply) {
    void loadTrends(currentQuery()).then(renderChart)
  }
}

const preloadHistoryLater = () => {
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  preloadIdleTask = runWhenIdle(() => {
    preloadIdleTask = null
    if (selectedMonth.value !== 'all') {
      loadTrends({ year: Number(selectedYear.value), month: null }, false)
    }
  }, 1200)
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  historyRefreshTimer = setTimeout(async () => {
    const query = currentQuery()
    historyCache.delete(queryKey(query))
    await loadTrends(query, true, true)
    renderChart()
    preloadHistoryLater()
    scheduleHistoryRefresh()
  }, 30 * 60 * 1000)
}

const onYearChange = async () => {
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
  await loadTrends(currentQuery())
  renderChart()
  preloadHistoryLater()
  scheduleHistoryRefresh()
}

const onMonthChange = async () => {
  await loadTrends(currentQuery())
  renderChart()
  preloadHistoryLater()
  scheduleHistoryRefresh()
}

const chartDates = () => (chartData.value.history || []).map(row => row.date)

const chartValues = () => buildDailyRainChartValues(chartData.value.history || [])

const formatXAxisLabel = (dateValue) => {
  const value = new Date(`${dateValue}T00:00:00+08:00`)
  return selectedMonth.value === 'all' ? `${value.getMonth() + 1}月` : `${value.getDate()}日`
}

const shouldShowXAxisLabel = (_index, dateValue) => {
  const day = Number(String(dateValue).slice(8, 10))
  if (selectedMonth.value === 'all') return day === 1
  return day === 1 || day % 4 === 1
}

const tooltipFormatter = (params) => {
  const item = (Array.isArray(params) ? params : [params]).find(entry => entry?.data != null)
  if (!item || item.data === null) return ''
  const dateValue = new Date(`${item.axisValue}T00:00:00+08:00`)
  const heading = dateValue.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  const source = (chartData.value.history || []).find(row => row.date === item.axisValue)
  const seriesLabel = source?.data?.in_progress ? '今日雨量（截至当前）' : '逐日雨量'
  return `<div style="min-width:160px"><strong>${heading}</strong>`
    + `<div style="display:flex;justify-content:space-between;gap:24px;margin-top:8px">`
    + `<span>${item.marker}${seriesLabel}</span><strong>${Number(item.data).toFixed(1)} mm</strong></div></div>`
}

const fullChartOption = () => {
  const values = chartValues()
  const yRange = calcNiceYAxisRange(values, { min: 0, max: 20 }, 7)
  const today = new Date()
  const todayDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  const dates = chartDates()
  const todayVisible = dates.includes(todayDate)
  const series = {
    id: 'daily-rainfall',
    name: '逐日雨量',
    type: 'bar',
    data: values,
    barMaxWidth: selectedMonth.value === 'all' ? 6 : 22,
    barMinHeight: 3,
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
    animationDuration: 850,
    animationDurationUpdate: 550,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    animationDelay: index => Math.min(index * 3, 420),
    universalTransition: true,
  }

  if (todayVisible) {
    series.markLine = {
      silent: true,
      symbol: ['none', 'none'],
      lineStyle: { color: 'rgba(255,255,255,0.48)', width: 1 },
      label: {
        show: true, formatter: '今天', position: 'insideEndTop', color: '#fff',
        backgroundColor: '#343b4d', borderRadius: 10, padding: [3, 9], fontWeight: 600,
      },
      data: [{ xAxis: todayDate }],
    }
  }

  return {
    animation: true,
    animationDuration: 850,
    animationDurationUpdate: 550,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', confine: true, formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)', borderColor: 'rgba(89, 155, 255, 0.55)', borderWidth: 1,
      padding: [11, 13], textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(47, 151, 255, 0.08)' } },
    },
    grid: { left: 18, right: 22, bottom: 18, top: 24, containLabel: true },
    xAxis: {
      type: 'category', data: dates, boundaryGap: true,
      axisLine: { lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisTick: { show: true, alignWithLabel: true, interval: shouldShowXAxisLabel, lineStyle: { color: 'rgba(121, 155, 202, 0.42)' } },
      axisLabel: { color: '#91a9ca', margin: 12, interval: shouldShowXAxisLabel, formatter: formatXAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', min: yRange.min, max: yRange.max, interval: yRange.interval,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#b6c7df', margin: 12, formatter: value => `${value}\n毫米` },
      splitLine: { lineStyle: { color: 'rgba(151, 177, 215, 0.18)', width: 1 } },
    },
    series: [series],
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
    loadInitialHistory: async () => loadTrends(currentQuery()),
    renderHistory: renderChart,
    scheduleHistoryRefresh,
    preloadHistoryLater,
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
.header-comm { font-size: 11px; font-weight: 400; color: var(--text-secondary); margin-top: 4px; }

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
    radial-gradient(circle at 100% 0%, rgba(34, 132, 217, 0.14), transparent 34%),
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
.history-panel-header .panel-title {
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
.calendar-controls {
  display: flex;
  gap: 7px;
  padding: 3px;
  border: 1px solid rgba(77, 141, 234, 0.28);
  border-radius: 9px;
  background: rgba(26, 49, 83, 0.38);
}
.history-select.year-select { width: 112px; }
.history-select.month-select { width: 126px; }
.history-select :deep(.el-select__wrapper) {
  min-height: 30px;
  border: 0;
  border-radius: 7px;
  background: rgba(31, 53, 88, 0.82);
  box-shadow: 0 0 0 1px rgba(120, 155, 211, 0.18) inset;
}
.history-select :deep(.el-select__selected-item) { color: #dce9fa; font-size: 13px; }
.history-select :deep(.el-select__caret) { color: #91a8c9; }

.trend-shell { padding: 12px 18px 14px; }
.history-stat-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 3px;
}
.history-stat {
  min-width: 0;
  padding: 9px 11px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 8px;
  background: rgba(5, 17, 36, 0.34);
  border: 1px solid rgba(120, 155, 211, 0.11);
}
.history-stat span {
  overflow: hidden;
  color: #738cac;
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.history-stat strong {
  color: #dbe9fb;
  font-family: "Consolas", "Monaco", monospace;
  font-size: 14px;
  white-space: nowrap;
}
.history-stat strong.maximum { color: #38c9ff; }
.history-stat strong.date { color: #ffd552; }
.history-stat strong.wet-days { color: #60a5ff; }

.chart-wrap { position: relative; }
.history-chart-wrap { height: 420px; }
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

@media (max-width: 900px) {
  .history-panel-header { align-items: flex-start; flex-wrap: wrap; }
  .history-stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .history-chart-wrap { height: 360px; }
}

@media (max-width: 620px) {
  .rain-data-card { flex-direction: column; }
  .rain-main-row { flex-direction: column; gap: 16px; }
  .rain-main-divider { width: 100%; height: 1px; }
  .rain-yesterday-card { flex-basis: auto; }
  .calendar-controls { width: 100%; }
  .history-select.year-select, .history-select.month-select { flex: 1; width: auto; }
  .history-stat { padding: 8px; flex-direction: column; align-items: flex-start; }
}
</style>
