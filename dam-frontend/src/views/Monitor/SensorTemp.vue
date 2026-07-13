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
        <div class="header-comm" v-if="lastTimestamp">最后通讯: {{ formatCommTime(lastTimestamp) }}</div>
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
            <span>今日温度极值</span>
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

    <!-- 历史曲线: 全宽 -->
    <div class="data-panel">
      <div class="panel-header">
        <span class="panel-title">历史记录</span>
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
        <span class="humidity-axis-unit">%</span>
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
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { getSensorRealtime, getSensorHistory } from '@/api/sensor'
import { buildChartAxisWindow, calcYAxisRange, formatChartAxisLabel, getNextHistoryRefreshMs, normalizeHistorySeries } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, preloadHistoryRanges, runWhenIdle } from '@/utils/sensorDetailStartup'
import * as echarts from 'echarts'

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const selectedRange = ref('1h')
const lastTimestamp = ref(0)
const historyLoading = ref(false)
const historyError = ref('')
const historyEmpty = ref(false)
let chart = null, timer = null, historyRefreshTimer = null, preloadIdleTask = null
let resizeHandler = null
const chartData = ref({ temp: [], humi: [], window: null, config: null })
const historyCache = new Map()
const deviceMeta = {
  sn: 'DAM-TH-1042',
  location: '坝顶中段 K0+150',
  power: '太阳能 / 85%',
}
const historyFields = { temp: 'temperature', humi: 'humidity' }

const tempMinMax = computed(() => {
  const values = chartData.value.temp
    .map(point => point[1])
    .filter(v => v != null && Number.isFinite(Number(v)))
  if (!values.length) return '--'
  return `${Math.min(...values).toFixed(1)}℃ / ${Math.max(...values).toFixed(1)}℃`
})

const tempPosition = computed(() => {
  const value = Number(data.value.temperature)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, ((value - 0) / 45) * 100))
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

const formatCommTime = (ts) => {
  if (!ts) return '--'
  return new Date(ts * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
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
  } catch (e) {
    statusClass.value = 'offline'; statusText.value = '离线'
  }
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
    const res = await getSensorHistory('temp_humidity', range)
    if (res.code === 200) {
      const normalized = normalizeHistorySeries(res.data?.history || [], range, historyFields, new Date(), res.data || {})
      const nextData = {
        temp: normalized.series.temp,
        humi: normalized.series.humi,
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
    temp: normalized.series.temp,
    humi: normalized.series.humi,
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
  if (detail.url !== '/v1/sensor/history/temp_humidity') return
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

const onRangeChange = async (range) => {
  await loadHistory(range)
  renderChart()
  scheduleHistoryRefresh()
}

const renderChart = () => {
  if (!chart) return
  chart.setOption(fullChartOption(), true)
}

const fullChartOption = () => {
  const tempRange = calcYAxisRange(chartData.value.temp, 0.2, { min: 10, max: 30 })
  const humiRange = calcYAxisRange(chartData.value.humi, 0.2, { min: 30, max: 90 })
  const xAxisWindow = buildChartAxisWindow(chartData.value.window)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.85)', borderColor: '#00e5ff', textStyle: { color: '#E2F0FE', fontSize: 13 } },
    legend: { data: ['温度', '湿度'], textStyle: { color: '#AECAF5' }, top: 5 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
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
    yAxis: [
      { type: 'value', scale: true, name: '℃', min: tempRange.min, max: tempRange.max, nameLocation: 'end', nameGap: 8, nameTextStyle: { color: '#AECAF5', fontSize: 12 }, axisLine: { lineStyle: { color: '#2a4a6a' } }, axisLabel: { color: '#AECAF5' }, splitLine: { lineStyle: { color: 'rgba(0,200,255,0.06)' } } },
      { type: 'value', scale: true, position: 'right', min: humiRange.min, max: humiRange.max, axisLine: { lineStyle: { color: '#2a4a6a' } }, axisLabel: { color: '#AECAF5' }, splitLine: { show: false } },
    ],
    series: [
      { name: '温度', type: 'line', smooth: true, yAxisIndex: 0, data: chartData.value.temp, itemStyle: { color: '#f56c6c' }, symbol: 'circle', symbolSize: 8, lineStyle: { width: 2 }, connectNulls: false },
      { name: '湿度', type: 'line', smooth: true, yAxisIndex: 1, data: chartData.value.humi, itemStyle: { color: '#409eff' }, symbol: 'circle', symbolSize: 8, lineStyle: { width: 2 }, connectNulls: false },
    ],
  }
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
.humidity-axis-unit {
  position: absolute;
  top: 14px;
  right: 40px;
  color: #AECAF5;
  font-size: 12px;
  line-height: 1;
  pointer-events: none;
}

.range-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
.range-card { padding: 10px 12px; background: rgba(0, 0, 0, 0.16); border: 1px solid rgba(0, 200, 255, 0.08); border-radius: 8px; }
.range-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; color: var(--text-secondary); font-size: 13px; }
.range-top strong { color: var(--text-primary); font-size: 15px; }
.range-track { position: relative; height: 6px; margin-top: 12px; background: linear-gradient(90deg, #409eff 0%, #67c23a 42%, #67c23a 62%, #f56c6c 100%); border-radius: 999px; }
.range-track.humidity { background: linear-gradient(90deg, #e6a23c 0%, #67c23a 40%, #67c23a 75%, #409eff 100%); }
.range-track i { position: absolute; top: -5px; width: 4px; height: 16px; transform: translateX(-50%); background: #fff; border-radius: 2px; box-shadow: 0 0 8px rgba(255,255,255,0.7); }
.range-note { margin-top: 8px; color: var(--text-muted); font-size: 12px; }
</style>
