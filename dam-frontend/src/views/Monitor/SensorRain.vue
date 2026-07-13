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

    <!-- 历史曲线: 全宽 -->
    <div class="data-panel">
      <div class="chart-top-row">
        <span class="panel-title">历史记录</span>
        <div class="chart-tabs">
          <button v-for="c in chartList" :key="c.key"
            class="chart-tab" :class="{ active: selectedChart === c.key }"
            :style="{ '--tab-color': c.color }"
            @click="selectChart(c.key)">{{ c.name }}</button>
        </div>
        <el-radio-group v-model="selectedRange" size="small" @change="onRangeChange">
          <el-radio-button value="1h">1小时</el-radio-button>
          <el-radio-button value="6h">6小时</el-radio-button>
          <el-radio-button value="1d">1天</el-radio-button>
          <el-radio-button value="7d">7天</el-radio-button>
          <el-radio-button value="6mo">6个月</el-radio-button>
        </el-radio-group>
      </div>
      <div class="chart-wrap">
        <div class="chart-container" ref="chartRef"></div>
        <div v-if="historyLoading" class="chart-loading-overlay">
          <div class="loading-spinner"></div>
          <div class="loading-text">加载中 ...</div>
        </div>
        <div v-else-if="historyError" class="chart-loading-overlay">
          <div class="loading-text">{{ historyError }}</div>
        </div>
        <div v-else-if="historyEmpty" class="chart-loading-overlay">
          <div class="loading-text">当前时间范围暂无历史数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getSensorRealtime, getSensorHistory } from '@/api/sensor'
import { buildChartAxisWindow, calcYAxisRange, formatChartAxisLabel, getNextHistoryRefreshMs, normalizeHistorySeries } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, preloadHistoryRanges, runWhenIdle } from '@/utils/sensorDetailStartup'
import { Pouring } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const selectedRange = ref('1h')
const selectedChart = ref('hour')
const lastTimestamp = ref(0)
const historyLoading = ref(false)
const historyError = ref('')
const historyEmpty = ref(false)
let chart = null, timer = null, historyRefreshTimer = null, preloadIdleTask = null
let resizeHandler = null
const chartData = ref({ today: [], hour: [], instant: [], window: null, config: null })
const historyCache = new Map()
const deviceMeta = {
  sn: 'DAM-RG-3018',
  location: '库区左岸雨量站',
  power: '太阳能 / 92%',
}
const historyFields = {
  today: 'today_rain',
  hour: 'hour_rain',
  instant: 'instant_rain',
}

const chartList = [
  { key: 'instant',  name: '瞬时降雨量 (mm)',   color: '#00e5ff' },
  { key: 'hour',     name: '小时降雨量 (mm)',   color: '#409eff' },
  { key: 'today',    name: '当天降雨量 (mm)',   color: '#67c23a' },
]

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

const getSeriesData = (key) => {
  const map = { today: [chartData.value.today], hour: [chartData.value.hour], instant: [chartData.value.instant] }
  return map[key] || map.hour
}
const getChartUnit = () => 'mm'
const getYAxisFallback = (key) => {
  const map = {
    hour: { min: 0, max: 20 },
    instant: { min: 0, max: 20 },
    today: { min: 0, max: 100 },
  }
  return map[key] || map.hour
}

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
  } catch (e) { statusClass.value = 'offline'; statusText.value = '离线' }
}

const loadHistory = async (range = '1h', apply = true) => {
  try {
    if (historyCache.has(range)) {
      const cached = historyCache.get(range)
      if (apply) {
        chartData.value = cached
        historyError.value = ''
        historyEmpty.value = cached.pointCount === 0
      }
      return cached
    }
    historyLoading.value = true
    if (apply) historyError.value = ''
    const res = await getSensorHistory('rain', range)
    if (res.code === 200) {
      const normalized = normalizeHistorySeries(res.data?.history || [], range, historyFields, new Date(), res.data || {})
      const nextData = {
        today: normalized.series.today,
        hour: normalized.series.hour,
        instant: normalized.series.instant,
        window: normalized.window,
        config: normalized.config,
        pointCount: Number(res.data?.point_count || 0),
      }
      historyCache.set(range, nextData)
      if (apply) {
        chartData.value = nextData
        historyEmpty.value = nextData.pointCount === 0
      }
      return nextData
    }
  } catch (e) {
    console.warn('加载历史数据失败:', e)
    if (apply) historyError.value = '历史数据服务暂时不可用，请稍后重试'
  }
  finally {
    historyLoading.value = false
  }
}

const applyHistoryResponse = (range, res) => {
  if (res?.code !== 200) return null
  const normalized = normalizeHistorySeries(res.data?.history || [], range, historyFields, new Date(), res.data || {})
  const nextData = {
    today: normalized.series.today,
    hour: normalized.series.hour,
    instant: normalized.series.instant,
    window: normalized.window,
    config: normalized.config,
    pointCount: Number(res.data?.point_count || 0),
  }
  historyCache.set(range, nextData)
  chartData.value = nextData
  historyError.value = ''
  historyEmpty.value = nextData.pointCount === 0
  return nextData
}

const handleHistoryCacheUpdate = (event) => {
  const detail = event.detail || {}
  if (detail.url !== '/v1/sensor/history/rain') return
  const range = detail.params?.range || '1h'
  if (range !== selectedRange.value) return
  if (applyHistoryResponse(range, detail.data)) renderChart()
}

const preloadHistory = () => {
  preloadHistoryRanges(['6h'], loadHistory)
}

const preloadHistoryLater = () => {
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  preloadIdleTask = runWhenIdle(() => {
    preloadIdleTask = null
    preloadHistory()
  }, 1200)
}

const scheduleHistoryRefresh = () => {
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  historyRefreshTimer = setTimeout(async () => {
    historyCache.clear()
    await loadHistory(selectedRange.value)
    renderChart()
    preloadHistoryLater()
    scheduleHistoryRefresh()
  }, getNextHistoryRefreshMs(selectedRange.value) + 1000)
}

const selectChart = (key) => { selectedChart.value = key; renderChart() }

const onRangeChange = async (range) => {
  await loadHistory(range); renderChart(); scheduleHistoryRefresh()
}

const fullChartOption = () => {
  const dataArr = getSeriesData(selectedChart.value)
  const color = chartList.find(c => c.key === selectedChart.value)?.color || '#409eff'
  const xAxisWindow = buildChartAxisWindow(chartData.value.window)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.85)', borderColor: '#00e5ff', textStyle: { color: '#E2F0FE', fontSize: 13 } },
    legend: { show: false },
    grid: { left: '3%', right: '5%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'time',
      min: xAxisWindow.min,
      max: xAxisWindow.max,
      interval: chartData.value.config?.majorTickMs,
      minInterval: chartData.value.config?.majorTickMs,
      maxInterval: chartData.value.config?.majorTickMs,
      axisLine: { lineStyle: { color: '#2a4a6a' } },
      axisLabel: { color: '#AECAF5', hideOverlap: true, showMaxLabel: true, formatter: value => formatChartAxisLabel(value, selectedRange.value, chartData.value.window) },
    },
    yAxis: { type: 'value', scale: true, name: 'mm', ...calcYAxisRange(dataArr[0], 0.2, getYAxisFallback(selectedChart.value)), nameLocation: 'end', nameGap: 8, nameTextStyle: { color: '#AECAF5', fontSize: 12 }, axisLine: { lineStyle: { color: '#2a4a6a' } }, axisLabel: { color: '#AECAF5' }, splitLine: { lineStyle: { color: 'rgba(0,200,255,0.06)' } } },
    series: [{ type: 'line', smooth: true, data: dataArr[0], itemStyle: { color }, symbol: 'circle', symbolSize: 8, lineStyle: { width: 2 } }],
  }
}
const renderChart = () => { if (chart) chart.setOption(fullChartOption(), true) }
const updateChart = () => {
  if (!chart) return
  renderChart()
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
    loadInitialHistory: async () => {
      await loadHistory('1h')
    },
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

/* 图表 */
.chart-top-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px; }
.chart-top-row .panel-title { margin-bottom: 0; }
.chart-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.chart-tab {
  padding: 4px 12px; border: 1px solid rgba(0, 200, 255, 0.2); border-radius: 14px;
  background: rgba(0, 0, 0, 0.2); color: #AECAF5; font-size: 12px;
  cursor: pointer; transition: all 0.25s; white-space: nowrap;
}
.chart-tab:hover { border-color: var(--tab-color, #00e5ff); color: var(--tab-color, #00e5ff); background: rgba(0, 0, 0, 0.35); }
.chart-tab.active {
  border-color: var(--tab-color, #00e5ff); background: color-mix(in srgb, var(--tab-color, #00e5ff) 15%, transparent);
  color: var(--tab-color, #00e5ff); font-weight: 600;
  box-shadow: 0 0 10px color-mix(in srgb, var(--tab-color, #00e5ff) 25%, transparent);
}
.chart-wrap { position: relative; height: 380px; }
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
</style>
