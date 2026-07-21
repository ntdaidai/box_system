<template>
  <div class="vibration-monitor" :class="{ 'alert-flash': isAlertFlashing }">
    <!-- 页面头部 -->
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
        <div class="header-comm" v-if="lastTimestamp">{{ formatCommTime(lastTimestamp) }}</div>
      </div>
    </div>

    <!-- 第一层：核心指标卡 -->
    <div class="indicator-section">
      <div class="indicator-cards">
        <!-- 综合振动烈度 -->
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

        <!-- 当前主频 -->
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

        <!-- 运行状态 -->
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

        <!-- 峰值因子 -->
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

    <!-- 第二层：趋势图 -->
    <div class="trend-section">
      <div class="section-header">
        <h3>趋势分析</h3>
        <div class="time-range-selector">
          <button v-for="range in timeRanges" :key="range.value"
                  :class="{ active: selectedRange === range.value }"
                  @click="changeRange(range.value)">
            {{ range.label }}
          </button>
        </div>
      </div>

      <div class="trend-charts">
        <!-- 振动趋势 -->
        <div class="chart-panel">
          <div class="panel-title">
            <span>振动趋势</span>
            <span class="panel-subtitle">RMS值变化曲线</span>
          </div>
          <div class="chart-wrap">
            <div ref="rmsChartRef" class="chart-container"></div>
            <div v-if="historyLoading" class="chart-state-overlay">加载中 ...</div>
            <div v-else-if="historyError" class="chart-state-overlay chart-state-error">{{ historyError }}</div>
            <div v-else-if="historyEmpty" class="chart-state-overlay">当前时间范围暂无振动 RMS 数据</div>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="legend-line" style="background:#00e5ff"></span>振动RMS</span>
            <span class="legend-threshold"><span class="threshold-line" style="background:#67c23a"></span>关注线 0.05g</span>
            <span class="legend-threshold"><span class="threshold-line" style="background:#e6a23c"></span>预警线 0.10g</span>
            <span class="legend-threshold"><span class="threshold-line" style="background:#f56c6c"></span>报警线 0.15g</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 详细数据表格 -->
    <div class="detail-section">
      <div class="section-header">
        <h3>详细数据</h3>
      </div>
      <div class="data-table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>参数</th>
              <th>数值</th>
              <th>单位</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>综合振动RMS</td>
              <td class="value">{{ formatValue(processedData.total_rms, 4) }}</td>
              <td>g</td>
              <td>三轴合成加速度的均方根值</td>
            </tr>
            <tr>
              <td>峰值加速度</td>
              <td class="value">{{ formatValue(processedData.peak_accel, 4) }}</td>
              <td>g</td>
              <td>窗口内最大加速度幅值</td>
            </tr>
            <tr>
              <td>主频率</td>
              <td class="value">{{ formatValue(processedData.dominant_freq, 2) }}</td>
              <td>Hz</td>
              <td>FFT分析得到的主频</td>
            </tr>
            <tr>
              <td>主频偏移</td>
              <td class="value" :class="driftClass">{{ formatDrift(processedData.freq_drift_percent) }}</td>
              <td>%</td>
              <td>相对于基线主频的偏移百分比</td>
            </tr>
            <tr>
              <td>峰值因子</td>
              <td class="value">{{ formatValue(processedData.crest_factor, 2) }}</td>
              <td>-</td>
              <td>峰值/RMS比值，判断冲击信号</td>
            </tr>
            <tr>
              <td>传感器温度</td>
              <td class="value">{{ formatValue(processedData.temperature, 1) }}</td>
              <td>℃</td>
              <td>传感器内部温度</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 报警提示浮层 -->
    <div v-if="showAlertBanner" class="alert-banner" :class="'alert-' + processedData.alert_level">
      <div class="alert-icon">⚠️</div>
      <div class="alert-content">
        <div class="alert-level">{{ processedData.alert_level }}</div>
        <div class="alert-reason">{{ processedData.alert_reason }}</div>
      </div>
      <button class="alert-close" @click="dismissAlert">×</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { getVibrationProcessed, getVibrationTrends } from '@/api/sensor'
import { buildChartAxisWindow, formatChartAxisLabel, getNextHistoryRefreshMs, normalizeHistorySeries } from '@/utils/sensorHistory'
import { cancelIdleTask, createSensorDetailStartup, preloadHistoryRanges, runWhenIdle } from '@/utils/sensorDetailStartup'
import * as echarts from 'echarts'

// 状态数据
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

const lastTimestamp = ref(0)
const statusClass = ref('online')
const statusText = ref('在线')
const selectedRange = ref('1h')
const showAlertBanner = ref(false)
const isAlertFlashing = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const historyEmpty = ref(false)
const chartData = ref({ rms: [], window: null, config: null, pointCount: 0 })
const historyCache = new Map()

// 图表引用
const rmsChartRef = ref(null)

// 图表实例
let rmsChart = null

// 定时器
let realtimeTimer = null
let historyRefreshTimer = null
let preloadIdleTask = null

// 时间范围选项
const timeRanges = [
  { label: '1小时', value: '1h' },
  { label: '6小时', value: '6h' },
  { label: '1天', value: '1d' },
  { label: '7天', value: '7d' },
  { label: '6个月', value: '6mo' },
]

// 计算属性
const rmsStatusClass = computed(() => {
  const rms = processedData.total_rms
  if (rms === null) return 'status-unknown'
  if (rms >= 0.15) return 'status-alarm'
  if (rms >= 0.10) return 'status-warning'
  if (rms >= 0.05) return 'status-attention'
  return 'status-normal'
})

const freqStatusClass = computed(() => {
  const drift = Math.abs(processedData.freq_drift_percent || 0)
  if (drift > 15) return 'status-alarm'
  return 'status-normal'
})

const crestStatusClass = computed(() => {
  const cf = processedData.crest_factor
  if (cf === null) return 'status-unknown'
  if (cf > 3.5) return 'status-warning'
  return 'status-normal'
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

// 格式化函数
const formatValue = (value, decimals) => {
  if (value === null || value === undefined) return '--'
  return Number(value).toFixed(decimals)
}

const formatDrift = (drift) => {
  if (drift === null || drift === undefined) return '--'
  const sign = drift >= 0 ? '+' : ''
  return `${sign}${drift.toFixed(1)}%`
}

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

// API调用
const fetchProcessedData = async () => {
  try {
    const result = await getVibrationProcessed()

    if (result.code === 200 && result.data) {
      const data = result.data.data || result.data
      Object.assign(processedData, data)
      lastTimestamp.value = result.data.timestamp || Date.now() / 1000
      statusClass.value = result.data.mock ? 'offline' : 'online'
      statusText.value = result.data.mock ? '离线（模拟数据）' : '在线'

      // 检查是否需要报警闪烁
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

const normalizeTrendResponse = (range, result) => {
  if (result?.code !== 200) return null
  const rawHistory = result.data?.history || []
  const rmsHistory = rawHistory.filter(
    point => point.rms != null && Number.isFinite(Number(point.rms)),
  )
  const nestedHistory = rmsHistory.map(point => ({
    timestamp: point.timestamp,
    data: { rms: Number(point.rms) },
  }))
  const normalized = normalizeHistorySeries(
    nestedHistory,
    range,
    { rms: 'rms' },
    new Date(),
    result.data || {},
  )
  return {
    rms: normalized.series.rms,
    window: normalized.window,
    config: normalized.config,
    pointCount: rmsHistory.length,
  }
}

const applyTrendResponse = (range, result) => {
  const nextData = normalizeTrendResponse(range, result)
  if (!nextData) return null
  historyCache.set(range, nextData)
  chartData.value = nextData
  historyError.value = ''
  historyEmpty.value = nextData.pointCount === 0
  return nextData
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
    if (apply) {
      historyLoading.value = true
      historyError.value = ''
    }
    const result = await getVibrationTrends(range)
    const nextData = normalizeTrendResponse(range, result)
    if (!nextData) throw new Error('振动历史响应无效')
    historyCache.set(range, nextData)
    if (apply) {
      chartData.value = nextData
      historyEmpty.value = nextData.pointCount === 0
    }
    return nextData
  } catch (error) {
    console.error('获取趋势数据失败:', error)
    if (apply) historyError.value = '历史数据服务暂时不可用，请稍后重试'
  } finally {
    if (apply) historyLoading.value = false
  }
}

const handleHistoryCacheUpdate = (event) => {
  const detail = event.detail || {}
  if (detail.url !== '/v1/sensor/vibration/trends') return
  const range = detail.params?.range || '1h'
  if (range !== selectedRange.value) return
  if (applyTrendResponse(range, detail.data)) renderChart()
}

const preloadHistoryLater = () => {
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)
  preloadIdleTask = runWhenIdle(() => {
    preloadIdleTask = null
    preloadHistoryRanges(['6h'], loadHistory)
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

const fullChartOption = () => {
  const xAxisWindow = buildChartAxisWindow(chartData.value.window)
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0,0,0,0.85)',
      borderColor: '#00e5ff',
      textStyle: { color: '#E2F0FE' },
      formatter: function(params) {
        if (!params || params.length === 0) return ''
        const point = params[0].data
        const time = new Date(point?.[0]).toLocaleString('zh-CN', { hour12: false })
        const value = point?.[1]
        return `${time}<br/>振动RMS: ${value == null ? '--' : Number(value).toFixed(4)} g`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'time',
      min: xAxisWindow.min,
      max: xAxisWindow.max,
      interval: chartData.value.config?.majorTickMs,
      minInterval: chartData.value.config?.majorTickMs,
      maxInterval: chartData.value.config?.majorTickMs,
      axisLine: { lineStyle: { color: '#2a4a6a' } },
      axisLabel: {
        color: '#AECAF5',
        hideOverlap: true,
        showMaxLabel: true,
        formatter: value => formatChartAxisLabel(value, selectedRange.value, chartData.value.window),
      }
    },
    yAxis: {
      type: 'value',
      name: 'RMS (g)',
      nameTextStyle: { color: '#AECAF5' },
      axisLine: { lineStyle: { color: '#2a4a6a' } },
      axisLabel: { color: '#AECAF5' },
      splitLine: { lineStyle: { color: 'rgba(0,200,255,0.1)' } },
      min: 0
    },
    series: [{
      type: 'line',
      name: '振动RMS',
      smooth: true,
      symbol: 'none',
      connectNulls: false,
      lineStyle: { color: '#00e5ff', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0,229,255,0.3)' },
          { offset: 1, color: 'rgba(0,229,255,0)' }
        ])
      },
      markLine: {
        silent: true,
        lineStyle: { type: 'dashed' },
        data: [
          { yAxis: 0.05, lineStyle: { color: '#67c23a' }, label: { show: false } },
          { yAxis: 0.10, lineStyle: { color: '#e6a23c' }, label: { show: false } },
          { yAxis: 0.15, lineStyle: { color: '#f56c6c' }, label: { show: false } }
        ]
      },
      data: chartData.value.rms,
    }],
  }
}

const renderChart = () => {
  if (rmsChart) rmsChart.setOption(fullChartOption(), true)
}

const initChart = () => {
  if (!rmsChartRef.value) return
  rmsChart = echarts.init(rmsChartRef.value)
  renderChart()
}

const changeRange = async (range) => {
  selectedRange.value = range
  await loadHistory(range)
  renderChart()
  scheduleHistoryRefresh()
}

const dismissAlert = () => {
  showAlertBanner.value = false
}

// 生命周期
onMounted(() => {
  const startup = createSensorDetailStartup({
    initChart,
    fetchRealtime: fetchProcessedData,
    loadInitialHistory: () => loadHistory('1h'),
    renderHistory: renderChart,
    scheduleHistoryRefresh,
    preloadHistoryLater,
  })
  startup.start()

  // 设置定时刷新（每5秒刷新实时数据）
  realtimeTimer = setInterval(() => {
    fetchProcessedData()
  }, 5000)

  // 窗口大小变化时重绘图表
  window.addEventListener('resize', handleResize)
  window.addEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
})

onUnmounted(() => {
  // 清理定时器
  if (realtimeTimer) clearInterval(realtimeTimer)
  if (historyRefreshTimer) clearTimeout(historyRefreshTimer)
  if (preloadIdleTask) cancelIdleTask(preloadIdleTask)

  // 销毁图表
  if (rmsChart) rmsChart.dispose()

  // 移除事件监听
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('dam-api-cache-updated', handleHistoryCacheUpdate)
})

const handleResize = () => {
  rmsChart?.resize()
}
</script>

<style scoped>
/* 页面整体 */
.vibration-monitor {
  padding: 16px;
  background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 100%);
  min-height: 100vh;
  color: #e0e8f0;
  position: relative;
}

.vibration-monitor.alert-flash {
  animation: alertFlash 1s infinite;
}

@keyframes alertFlash {
  0%, 100% { background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 100%); }
  50% { background: linear-gradient(135deg, #1a0a0a 0%, #3a1a1a 100%); }
}

/* 头部 */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: rgba(10, 31, 55, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 12px;
  margin-bottom: 16px;
  backdrop-filter: blur(10px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  background: rgba(0, 100, 200, 0.3);
  border: 2px solid rgba(0, 200, 255, 0.3);
}

.header-info h2 {
  font-size: 24px;
  color: #ffffff;
  margin: 0 0 4px 0;
  font-weight: 600;
}

.header-subtitle {
  font-size: 14px;
  color: #8aa8c7;
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
  color: #67c23a;
}

.header-status.online .dot {
  background: #67c23a;
  box-shadow: 0 0 6px #67c23a;
}

.header-status.offline {
  color: #f56c6c;
}

.header-status.offline .dot {
  background: #f56c6c;
  box-shadow: 0 0 6px #f56c6c;
}

.header-comm {
  width: 100%;
  margin-top: 4px;
  text-align: right;
  font-size: 14px;
  font-weight: 500;
  color: #8aa8c7;
  font-family: "Consolas", "Monaco", monospace;
}

/* 指标卡片区 */
.indicator-section {
  margin-bottom: 16px;
}

.indicator-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.indicator-card {
  background: rgba(10, 31, 55, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.indicator-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
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
  font-family: 'Consolas', 'Monaco', monospace;
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

/* 状态灯卡片 */
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
  transition: all 0.3s ease;
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

/* 趋势图区域 */
.trend-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h3 {
  font-size: 18px;
  color: #ffffff;
  margin: 0;
}

.time-range-selector {
  display: flex;
  gap: 8px;
}

.time-range-selector button {
  padding: 6px 16px;
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  color: #8aa8c7;
  cursor: pointer;
  transition: all 0.3s ease;
}

.time-range-selector button:hover {
  border-color: #00e5ff;
  color: #00e5ff;
}

.time-range-selector button.active {
  background: rgba(0, 229, 255, 0.2);
  border-color: #00e5ff;
  color: #00e5ff;
}

.trend-charts {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.chart-panel {
  background: rgba(10, 31, 55, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 12px;
  padding: 16px;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title span:first-child {
  font-size: 15px;
  font-weight: 500;
  color: #e0e8f0;
}

.panel-subtitle {
  font-size: 12px;
  color: #8aa8c7;
}

.chart-container {
  height: 300px;
}

.chart-wrap {
  position: relative;
}

.chart-state-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8aa8c7;
  font-size: 14px;
  background: rgba(10, 31, 55, 0.38);
  pointer-events: none;
}

.chart-state-error {
  color: #f5a7a7;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.legend-item, .legend-threshold {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8aa8c7;
}

.legend-line {
  width: 20px;
  height: 2px;
}

.legend-threshold {
  opacity: 0.7;
}

.threshold-line {
  width: 20px;
  height: 2px;
  border-top: 2px dashed;
}

/* 详细数据区域 */
.detail-section {
  margin-bottom: 16px;
}

.data-table-container {
  background: rgba(10, 31, 55, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  background: rgba(0, 100, 200, 0.3);
  color: #e0e8f0;
  font-weight: 600;
  font-size: 14px;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
  font-size: 14px;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover {
  background: rgba(0, 100, 200, 0.1);
}

.data-table .value {
  font-family: 'Consolas', 'Monaco', monospace;
  font-weight: 600;
  color: #00e5ff;
}

.data-table .value.drift-normal { color: #67c23a; }
.data-table .value.drift-warning { color: #e6a23c; }
.data-table .value.drift-alarm { color: #f56c6c; }

/* 状态未知 */
.status-unknown {
  opacity: 0.6;
}

/* 报警提示浮层 */
.alert-banner {
  position: fixed;
  top: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  backdrop-filter: blur(10px);
  z-index: 1000;
  animation: slideIn 0.3s ease;
  max-width: 400px;
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
  font-size: 24px;
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
  background: none;
  border: none;
  color: #ffffff;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.3s ease;
}

.alert-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .indicator-cards {
    grid-template-columns: repeat(2, 1fr);
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
</style>
