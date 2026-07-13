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
              <span class="wind-speed-num">{{ data.wind_speed_ms != null ? data.wind_speed_ms.toFixed(1) : '--' }}</span>
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
              <div class="wind-aux-val">{{ data.wind_speed_kmh != null ? data.wind_speed_kmh.toFixed(1) : '--' }}</div>
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
import { getWindCompassState } from '@/utils/sensorWindView'
import * as echarts from 'echarts'

const data = ref({})
const chartRef = ref(null)
const statusClass = ref('online')
const statusText = ref('在线')
const selectedRange = ref('1h')
const selectedChart = ref('ms')
const lastTimestamp = ref(0)
const historyLoading = ref(false)
const historyError = ref('')
const historyEmpty = ref(false)
let chart = null, timer = null, historyRefreshTimer = null, preloadIdleTask = null
let resizeHandler = null
const chartData = ref({ ms: [], kmh: [], level: [], angle: [], window: null, config: null })
const historyCache = new Map()
const deviceMeta = {
  sn: 'DAM-WD-2031',
  location: '坝顶迎风侧 K0+210',
  power: '市电 / 备用电池',
}
const historyFields = {
  ms: 'wind_speed_ms',
  kmh: 'wind_speed_kmh',
  level: 'wind_level',
  angle: 'wind_angle',
}

// 风速进度条位置（0-30m/s 映射到 0-100%）
const windSpeedPosition = computed(() => {
  const v = Number(data.value.wind_speed_ms) || 0
  return Math.max(0, Math.min(100, (v / 30) * 100))
})
const windStatusText = computed(() => {
  const v = Number(data.value.wind_speed_ms) || 0
  if (v < 6) return '微风（安全）'
  if (v < 10) return '和风（注意）'
  if (v < 15) return '大风（警惕）'
  return '狂风（危险）'
})
const windStatusClass = computed(() => {
  const v = Number(data.value.wind_speed_ms) || 0
  if (v < 10) return 'status-ok'
  if (v < 15) return 'status-warn'
  return 'status-danger'
})
const compassState = computed(() => getWindCompassState(data.value))

const chartList = [
  { key: 'ms',    name: '风速 (m/s)',  color: '#00e5ff', unit: 'm/s' },
  { key: 'kmh',   name: '风速 (km/h)', color: '#409eff', unit: 'km/h' },
  { key: 'level', name: '风级 (级)',    color: '#e6a23c', unit: '级' },
  { key: 'angle', name: '风向角度 (°)', color: '#67c23a', unit: '°' },
]

const getSeriesData = (key) => {
  const map = { ms: [chartData.value.ms], kmh: [chartData.value.kmh], level: [chartData.value.level], angle: [chartData.value.angle] }
  return map[key] || map.ms
}
const getChartUnit = (key) => chartList.find(c => c.key === key)?.unit || ''
const getYAxisFallback = (key) => {
  const map = {
    ms: { min: 0, max: 20 },
    kmh: { min: 0, max: 72 },
    level: { min: 0, max: 12 },
    angle: { min: 0, max: 360 },
  }
  return map[key] || map.ms
}

const formatCommTime = (ts) => {
  if (!ts) return '--'
  return new Date(ts * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

const fetchData = async () => {
  try {
    const res = await getSensorRealtime('wind')
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
    const res = await getSensorHistory('wind', range)
    if (res.code === 200) {
      const normalized = normalizeHistorySeries(res.data?.history || [], range, historyFields, new Date(), res.data || {})
      const nextData = {
        ms: normalized.series.ms,
        kmh: normalized.series.kmh,
        level: normalized.series.level,
        angle: normalized.series.angle,
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
    ms: normalized.series.ms,
    kmh: normalized.series.kmh,
    level: normalized.series.level,
    angle: normalized.series.angle,
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
  if (detail.url !== '/v1/sensor/history/wind') return
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
  const unit = getChartUnit(selectedChart.value)
  const color = chartList.find(c => c.key === selectedChart.value)?.color || '#00e5ff'
  const xAxisWindow = buildChartAxisWindow(chartData.value.window)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.85)', borderColor: '#00e5ff', textStyle: { color: '#E2F0FE', fontSize: 13 } },
    legend: { show: false },
    grid: { left: '3%', right: '6%', bottom: '3%', top: '8%', containLabel: true },
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
    yAxis: { type: 'value', scale: true, name: unit, ...calcYAxisRange(dataArr[0], 0.2, getYAxisFallback(selectedChart.value)), nameLocation: 'end', nameGap: 8, nameTextStyle: { color: '#AECAF5', fontSize: 12 }, axisLine: { lineStyle: { color: '#2a4a6a' } }, axisLabel: { color: '#AECAF5' }, splitLine: { lineStyle: { color: 'rgba(0,200,255,0.06)' } } },
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

/* 图表区域 */
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
.chart-wrap { position: relative; height: 310px; }
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
