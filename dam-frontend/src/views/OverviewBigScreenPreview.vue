<template>
  <main class="bigscreen-page">
    <div class="ambient-grid"></div>

    <section class="screen-grid">
      <aside class="left-column">
        <section class="screen-panel today-panel">
          <div class="panel-heading">
            <h2>今日态势</h2>
          </div>
          <div class="today-grid">
            <article v-for="metric in todayMetrics" :key="metric.key" class="today-card" :class="metric.tone">
              <span class="metric-icon">{{ metric.icon }}</span>
              <div>
                <span>{{ metric.label }}</span>
                <strong>{{ metric.value }}</strong>
                <em>
                  <i :class="metric.trend.tone">{{ metric.trend.icon }} {{ metric.trend.delta }}</i>
                  较昨日
                </em>
              </div>
            </article>
          </div>
        </section>

        <section class="screen-panel risk-panel">
          <div class="panel-heading">
            <h2>风险分布</h2>
            <div class="risk-switch">
              <button
                v-for="item in riskModes"
                :key="item.key"
                :class="{ active: activeRiskModeKey === item.key }"
                @click="handleRiskModeClick(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div class="risk-showcase">
            <div class="risk-chart-wrap">
              <div ref="riskChartRef" class="risk-main-chart echarts-chart"></div>
              <div class="risk-center">
                <strong>{{ formatNumber(activeRiskCount) }}</strong>
                <span :class="`risk-level-${activeRiskLevel.key}`">{{ activeRiskLevel.shortLabel }}</span>
              </div>
            </div>
            <div class="risk-summary">
              <span>{{ activeRiskMode.label }}</span>
              <strong :class="`risk-level-${activeRiskLevel.key}`">{{ activeRiskLevel.label }}</strong>
              <em>
                {{ activeRiskMode.compareLabel }}
                <b :class="activeRiskTrend.tone">{{ activeRiskTrend.icon }} {{ activeRiskTrend.delta }}</b>
              </em>
            </div>
          </div>
        </section>

        <section class="screen-panel trend-panel">
          <div class="panel-heading">
            <h2>闯入趋势</h2>
            <div class="segmented">
              <button
                v-for="item in trendModes"
                :key="item.key"
                :class="{ active: trendMode === item.key }"
                @click="trendMode = item.key"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div class="trend-legend">
            <span><i class="person"></i>人员</span>
            <span><i class="boat"></i>船只</span>
          </div>
          <div ref="trendChartRef" class="line-chart echarts-chart" aria-label="人员和船只闯入趋势"></div>
        </section>
      </aside>

      <main class="center-column">
        <section class="map-panel">
          <div
            ref="mapBoardRef"
            class="map-board"
            @wheel.prevent="handleMapWheel"
            @pointerdown="startMapDrag"
            @pointermove="moveMapDrag"
            @pointerup="endMapDrag"
            @pointercancel="endMapDrag"
          >
            <div class="map-scene" :style="mapSceneStyle">
              <img class="satellite-image" src="/dam.png" alt="大藤峡水电站卫星地图" />
              <div class="map-shade"></div>
              <button
                v-for="point in cameraPoints"
                :key="point.no"
                class="camera-point"
                :class="{ active: selectedPointNo === point.no }"
                :style="{ left: `${point.x}%`, top: `${point.y}%` }"
                @pointerdown.stop
                @click.stop="selectPoint(point.no)"
              >
                <span>{{ point.no }}</span>
              </button>
            </div>
            <div class="map-controls" aria-label="地图控制" @pointerdown.stop>
              <button type="button" title="放大" @click.stop="zoomMapBy(1.18)">+</button>
              <button type="button" title="缩小" @click.stop="zoomMapBy(0.84)">−</button>
              <button type="button" class="locate" title="定位当前点位" @click.stop="focusSelectedMapPoint" aria-label="定位当前点位">
                <span></span>
              </button>
            </div>
          </div>
        </section>

        <section class="selected-detail">
          <div class="selected-title">
            <div>
              <span>当前监测点位</span>
              <h2>{{ selectedPoint.no }}号摄像头 · {{ selectedGroup.typeLabel }}</h2>
            </div>
          </div>
          <div class="analytics-grid">
            <article class="analytics-card hourly-card">
              <div class="sub-heading">
                <h3>告警趋势</h3>
                <div class="mini-segmented">
                  <button
                    v-for="item in trendModes"
                    :key="item.key"
                    :class="{ active: detailTrendMode === item.key }"
                    @click="detailTrendMode = item.key"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>
              <div ref="hourlyChartRef" class="bar-chart echarts-chart"></div>
            </article>

            <article class="analytics-card composition-card">
              <div class="sub-heading">
                <h3>风险构成</h3>
              </div>
              <div ref="compositionChartRef" class="risk-composition echarts-chart"></div>
            </article>

            <article class="analytics-card disposal-card">
              <div class="sub-heading">
                <h3>告警状态</h3>
              </div>
              <div class="disposal-body">
                <div class="disposal-ring-wrap">
                  <div ref="disposalChartRef" class="disposal-ring echarts-chart"></div>
                  <div class="disposal-center">
                    <strong>{{ formatNumber(disposalStats.total) }}</strong>
                    <span>告警总数</span>
                  </div>
                </div>
                <div class="disposal-list">
                  <span><i class="handled"></i>已处置 {{ disposalStats.handled }}</span>
                  <span><i class="processing"></i>处理中 {{ disposalStats.processing }}</span>
                  <span><i class="pending"></i>未处置 {{ disposalStats.pending }}</span>
                </div>
              </div>
            </article>
          </div>
        </section>
      </main>

      <aside class="right-column">
        <section class="screen-panel clock-panel">
          <div class="clock-block">
            <span>{{ currentDate }} {{ currentWeek }}</span>
            <strong>{{ currentTime }}</strong>
            <em><i></i>{{ loading ? '同步中' : '实时刷新' }}</em>
          </div>
        </section>

        <section class="screen-panel progress-panel">
          <div class="panel-heading">
            <h2>实时告警进度 <span class="help-tip" title="最近最高风险">?</span></h2>
          </div>
          <div v-if="priorityAlert" class="priority-summary">
            <strong :class="riskClass(priorityAlert)">{{ riskLabel(priorityAlert) }}</strong>
            <span>{{ alertTitle(priorityAlert) }}</span>
          </div>
          <div v-else class="priority-summary empty">
            <strong>无告警</strong>
            <span>当前无未处理告警</span>
          </div>
          <div v-if="!priorityAlert" class="alarm-idle">
            <div class="idle-orbit">
              <span></span>
              <i></i>
            </div>
            <div class="idle-copy">
              <strong>告警监听中</strong>
              <span>风险事件触发后将在此同步处置进度</span>
            </div>
            <div class="idle-status-grid">
              <span>事件触发<i>待触发</i></span>
              <span>处置流程<i>待启动</i></span>
              <span>刷新状态<i>{{ loading ? '同步中' : '实时' }}</i></span>
            </div>
          </div>
          <ol class="progress-timeline">
            <li v-for="(item, index) in alarmTimeline" :key="item.key" :class="{ active: index === 0 }">
              <i></i>
              <span>{{ item.label }}</span>
            </li>
          </ol>
        </section>

        <section class="screen-panel device-panel" :class="{ warning: deviceOffline > 0 }">
          <div class="panel-heading">
            <h2>设备状态</h2>
          </div>
          <div class="device-state">
            <div class="device-gauge-wrap">
              <div ref="deviceChartRef" class="device-ring echarts-chart"></div>
              <div class="device-center">
                <strong>{{ deviceRate }}%</strong>
                <span>在线率</span>
              </div>
            </div>
            <div class="device-counts">
              <div class="device-count-row">
                <article class="online">
                  <span>在线</span>
                  <strong>{{ deviceOnline }}</strong>
                </article>
                <article class="offline">
                  <span>离线</span>
                  <strong>{{ deviceOffline }}</strong>
                </article>
              </div>
              <p class="device-report" :class="{ warning: deviceOffline > 0 }">{{ deviceReportText }}</p>
            </div>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { getUnifiedSafetyEventDetail, getUnifiedSafetyEventStatistics, getUnifiedSafetyEvents } from '@/api/integration'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList } from '@/api/camera'

const cameraPoints = [
  { no: 1, x: 17.3410, y: 40.8304, areaType: 'boatForbidden', regionKey: 'boat-1' },
  { no: 2, x: 7.3988, y: 15.2249, areaType: 'toConfirm', regionKey: 'camera-2' },
  { no: 3, x: 41.8497, y: 74.0484, areaType: 'boatForbidden', regionKey: 'boat-34568' },
  { no: 4, x: 47.3988, y: 38.0623, areaType: 'boatForbidden', regionKey: 'boat-34568' },
  { no: 5, x: 49.2486, y: 38.0623, areaType: 'boatForbidden', regionKey: 'boat-34568' },
  { no: 6, x: 66.3584, y: 52.5952, areaType: 'boatForbidden', regionKey: 'boat-34568' },
  { no: 7, x: 68.2081, y: 52.5952, areaType: 'boatForbidden', regionKey: 'boat-7' },
  { no: 8, x: 57.3410, y: 75.4325, areaType: 'boatForbidden', regionKey: 'boat-34568' },
  { no: 9, x: 91.7919, y: 24.2215, areaType: 'personForbidden', regionKey: 'person-9' },
]

const regionGroups = [
  { key: 'boat-1', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-34568', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-7', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'person-9', type: 'personForbidden', typeLabel: '人员禁入区', category: 'PERSON_SAFETY' },
  { key: 'camera-2', type: 'toConfirm', typeLabel: '待确认区', category: 'OTHER' },
]

const riskModes = [
  { key: 'today', label: '今日', compareLabel: '较昨日' },
  { key: 'week', label: '本周', compareLabel: '较上周' },
  { key: 'month', label: '本月', compareLabel: '较上月' },
]

const riskLevels = [
  { key: 'LOW', label: '低风险', shortLabel: '低风险' },
  { key: 'MEDIUM', label: '中风险', shortLabel: '中风险' },
  { key: 'HIGH', label: '高风险', shortLabel: '高风险' },
]

const trendModes = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
]

const riskColors = { LOW: '#38D59C', MEDIUM: '#FFB648', HIGH: '#FF5B68' }
const chartTextColor = '#8fc8f2'
const chartGridColor = 'rgba(143, 200, 242, .16)'
const chartTooltip = {
  appendToBody: true,
  confine: true,
  enterable: false,
  className: 'bigscreen-chart-tooltip',
  backgroundColor: 'rgba(2, 14, 28, .96)',
  borderColor: 'rgba(67, 200, 255, .36)',
  textStyle: { color: '#dff5ff', fontSize: 13 },
  extraCssText: 'max-width:240px;white-space:normal;word-break:break-word;border-radius:8px;box-shadow:0 10px 28px rgba(0,0,0,.28);z-index:99999;',
}
const mapFocusScale = 1.38
const selectedPointNo = ref(9)
const activeRiskModeKey = ref('today')
const riskFocusIndex = ref(2)
const trendMode = ref('today')
const detailTrendMode = ref('today')
const currentDate = ref('--')
const currentTime = ref('--:--:--')
const currentWeek = ref('--')
const loading = ref(false)
const eventStats = ref({})
const events = ref([])
const priorityDetail = ref({ timeline: [] })
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const mapBoardRef = ref(null)
const riskChartRef = ref(null)
const trendChartRef = ref(null)
const hourlyChartRef = ref(null)
const compositionChartRef = ref(null)
const disposalChartRef = ref(null)
const deviceChartRef = ref(null)
const mapBaseSize = ref({ width: 0, height: 0 })
const mapScale = ref(1)
const mapOffset = ref({ x: 120, y: 0 })
const minMapScale = ref(1)
const chartInstances = new Map()

const mapDragState = {
  active: false,
  moved: false,
  startX: 0,
  startY: 0,
  startOffsetX: 0,
  startOffsetY: 0,
}

let clockTimer
let refreshTimer
let riskTimer
let riskResumeTimer
let mapResizeObserver
let currentPriorityDetailId = null
let mapInitialFocused = false

const weekLabels = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const selectedPoint = computed(() => cameraPoints.find((point) => point.no === selectedPointNo.value) || cameraPoints[0])
const selectedGroup = computed(() => regionGroups.find((group) => group.key === selectedPoint.value.regionKey) || regionGroups[0])
const activeRiskLevel = computed(() => riskLevels[riskFocusIndex.value] || riskLevels[0])
const activeRiskMode = computed(() => riskModes.find((mode) => mode.key === activeRiskModeKey.value) || riskModes[0])
const mapSceneStyle = computed(() => ({
  width: `${mapBaseSize.value.width}px`,
  height: `${mapBaseSize.value.height}px`,
  transform: `translate3d(-50%, -50%, 0) translate3d(${mapOffset.value.x}px, ${mapOffset.value.y}px, 0) scale(${mapScale.value})`,
}))

const todayEvents = computed(() => eventsInWindow('today'))
const yesterdayEvents = computed(() => eventsInWindow('yesterday'))
const unhandledCount = computed(() => Number(eventStats.value.unhandled ?? events.value.filter((event) => !isHandled(event)).length))

const todayMetrics = computed(() => {
  const today = todayEvents.value
  const yesterday = yesterdayEvents.value
  return [
    buildTodayMetric('person', '人员告警', '●', today, yesterday),
    buildTodayMetric('boat', '船只告警', '▲', today, yesterday),
    buildTodayMetric('other', '其他告警', '◆', today, yesterday),
    {
      key: 'unhandled',
      label: '未处理告警',
      icon: '!',
      value: formatNumber(unhandledCount.value),
      tone: 'cyan',
      trend: compareNumber(unhandledCount.value, yesterday.filter((event) => !isHandled(event)).length),
    },
  ]
})

const riskDistribution = computed(() => {
  const build = (currentKey, previousKey) => {
    const current = eventsInWindow(currentKey)
    const previous = eventsInWindow(previousKey)
    const rows = ['LOW', 'MEDIUM', 'HIGH'].map((level) => {
      const count = current.filter((event) => riskLevel(event) === level).length
      const previousCount = previous.filter((event) => riskLevel(event) === level).length
      return {
        key: level,
        label: riskLevelLabel(level),
        count,
        trend: compareNumber(count, previousCount),
      }
    })
    return { rows, total: rows.reduce((sum, item) => sum + item.count, 0) }
  }
  return {
    today: build('today', 'yesterday'),
    week: build('week', 'lastWeek'),
    month: build('month', 'lastMonth'),
  }
})

const activeRiskStats = computed(() => riskDistribution.value[activeRiskModeKey.value] || { rows: [], total: 0 })
const activeRiskRow = computed(() => activeRiskStats.value.rows.find((row) => row.key === activeRiskLevel.value.key) || { count: 0, trend: compareNumber(0, 0) })
const activeRiskCount = computed(() => activeRiskRow.value.count || 0)
const activeRiskTrend = computed(() => activeRiskRow.value.trend || compareNumber(0, 0))

const intrusionTrend = computed(() => {
  const currentMode = trendMode.value
  const labels = trendLabels(currentMode)
  const person = trendBuckets(currentMode, 'person')
  const boat = trendBuckets(currentMode, 'boat')
  return {
    labels,
    person,
    boat,
  }
})

const selectedEvents = computed(() => {
  const category = selectedGroup.value.category
  if (category === 'PERSON_SAFETY') return events.value.filter((event) => getOverviewCategory(event) === 'person')
  if (category === 'ILLEGAL_FISHING') return events.value.filter((event) => getOverviewCategory(event) === 'boat')
  return events.value.filter((event) => getOverviewCategory(event) === 'other')
})

const selectedData = computed(() => {
  const timeline = eventTimelineBuckets(selectedEvents.value, detailTrendMode.value)
  return {
    total: timeline.total.reduce((sum, value) => sum + value, 0),
    labels: timeline.labels,
    totalCounts: timeline.total,
    risk: timeline.risk,
  }
})

const riskCompositionData = computed(() => {
  const rows = [
    { name: '闯入', events: events.value.filter((event) => ['person', 'boat'].includes(getOverviewCategory(event))) },
    { name: '灾害', events: events.value.filter((event) => getOverviewCategory(event) === 'disaster') },
    { name: '其他', events: events.value.filter((event) => getOverviewCategory(event) === 'other') },
  ]
  return {
    labels: rows.map((row) => row.name),
    risk: ['LOW', 'MEDIUM', 'HIGH'].reduce((acc, level) => {
      acc[level] = rows.map((row) => {
        if (row.name === '灾害' && !row.events.length) return 0
        return row.events.filter((event) => riskLevel(event) === level).length
      })
      return acc
    }, {}),
  }
})

const disposalStats = computed(() => {
  const total = events.value.length
  const handled = events.value.filter(isHandled).length
  const processing = events.value.filter((event) => event.status === 'PROCESSING').length
  const pending = Math.max(total - handled - processing, 0)
  return { total, handled, processing, pending }
})

const priorityAlert = computed(() => events.value
  .filter((event) => !isHandled(event))
  .slice()
  .sort((a, b) => riskRank(b) - riskRank(a) || eventTimestamp(b) - eventTimestamp(a))[0] || null)

const alarmTimeline = computed(() => {
  const rows = priorityDetail.value.timeline || []
  if (rows.length) {
    return rows.slice(0, 5).map((row) => ({
      key: row.id || `${row.log_type}-${row.created_at}`,
      label: logTypeLabel(row.log_type),
    }))
  }
  if (!priorityAlert.value) return [{ key: 'idle', label: '等待事件触发' }]
  return [
    { key: 'trigger', label: '事件触发' },
    { key: 'workflow', label: 'DAM_WORKFLOW' },
    { key: 'action', label: priorityAlert.value.status === 'PROCESSING' ? '执行动作' : '等待处置' },
  ]
})

const deviceRows = computed(() => {
  const rows = Object.entries(deviceStatus.value || {}).map(([key, item]) => {
    const total = Number(item?.total || 1)
    const online = Number(item?.online_count ?? (item?.status === 'online' ? total : 0))
    return { key, total, online }
  })
  if (cameraSummary.value.total > 0 || Object.prototype.hasOwnProperty.call(deviceStatus.value, 'camera')) {
    const index = rows.findIndex((row) => row.key === 'camera')
    const camera = { key: 'camera', online: cameraSummary.value.online, total: cameraSummary.value.total }
    if (index >= 0) rows.splice(index, 1, camera)
    else rows.push(camera)
  }
  return rows
})

const deviceOnline = computed(() => deviceRows.value.reduce((sum, item) => sum + item.online, 0))
const deviceTotal = computed(() => deviceRows.value.reduce((sum, item) => sum + item.total, 0))
const deviceOffline = computed(() => Math.max(deviceTotal.value - deviceOnline.value, 0))
const deviceRate = computed(() => deviceTotal.value ? Math.round((deviceOnline.value / deviceTotal.value) * 100) : 0)
const offlineDeviceNames = computed(() => deviceRows.value
  .filter((item) => item.total > item.online)
  .map((item) => deviceTypeLabel(item.key)))
const deviceReportText = computed(() => {
  if (!deviceTotal.value) return '暂无设备状态数据'
  if (!deviceOffline.value) return '所有设备正常运行'
  const names = offlineDeviceNames.value.length ? offlineDeviceNames.value.join('、') : '部分设备'
  return `${names}离线，请及时检查`
})

function buildTodayMetric(key, label, icon, today, yesterday) {
  const matchMetric = (event) => {
    const category = getOverviewCategory(event)
    if (key === 'other') return category !== 'person' && category !== 'boat'
    return category === key
  }
  const value = today.filter(matchMetric).length
  const previous = yesterday.filter(matchMetric).length
  return {
    key,
    label,
    icon,
    value: formatNumber(value),
    tone: key === 'person' ? 'danger' : key === 'boat' ? 'boat' : 'purple',
    trend: compareNumber(value, previous),
  }
}

function getChart(el, key) {
  if (!el) return null
  let chart = chartInstances.get(key)
  if (!chart) {
    chart = echarts.init(el, null, {
      renderer: 'canvas',
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight, 1),
    })
    chartInstances.set(key, chart)
  }
  resizeChartToElement(chart, el)
  return chart
}

function resizeChartToElement(chart, el) {
  const width = Math.max(el?.clientWidth || 0, 1)
  const height = Math.max(el?.clientHeight || 0, 1)
  chart.resize({ width, height })
}

function renderRiskCharts() {
  const chart = getChart(riskChartRef.value, 'risk-distribution-main')
  if (!chart) return
  const rows = activeRiskStats.value.rows || []
  const total = rows.reduce((sum, row) => sum + row.count, 0)
  const activeDataIndex = rows.findIndex((row) => row.key === activeRiskLevel.value.key)
  const data = total
    ? rows.map((row) => ({
      name: row.label,
      value: row.count,
      itemStyle: {
        color: riskColors[row.key],
        opacity: .86,
      },
    }))
    : [{ name: '暂无数据', value: 1, itemStyle: { color: 'rgba(143, 200, 242, .16)' } }]
  chart.setOption({
    tooltip: { ...chartTooltip, trigger: 'item', formatter: '{b}<br/>{c} 次，占比 {d}%' },
    series: [{
      type: 'pie',
      radius: ['58%', '78%'],
      center: ['50%', '50%'],
      selectedOffset: 0,
      minAngle: total ? 5 : 360,
      avoidLabelOverlap: true,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: { borderWidth: 0 },
      emphasis: {
        scale: true,
        scaleSize: 5,
        focus: 'self',
        itemStyle: {
          opacity: 1,
          shadowBlur: 18,
          shadowOffsetY: 8,
          shadowColor: 'rgba(0, 0, 0, .38)',
        },
      },
      blur: {
        itemStyle: {
          opacity: .18,
        },
      },
      data,
    }],
  }, true)
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  if (total && activeDataIndex >= 0) {
    chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: activeDataIndex })
  }
}

function renderTrendChart() {
  const el = trendChartRef.value
  const chart = getChart(el, 'intrusion-trend')
  if (!chart) return
  chart.setOption({
    color: ['#ff6873', '#41c8ff'],
    tooltip: { ...chartTooltip, trigger: 'axis' },
    grid: { left: 28, right: 10, top: 16, bottom: 24 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: intrusionTrend.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: chartTextColor, fontSize: 10, interval: 'auto', margin: 8 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: 10 },
    },
    series: [
      buildLineSeries('人员', intrusionTrend.value.person, '#ff6873'),
      buildLineSeries('船只', intrusionTrend.value.boat, '#41c8ff'),
    ],
  }, true)
}

function buildLineSeries(name, data, color) {
  return {
    name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 5,
    showSymbol: false,
    emphasis: { focus: 'series', scale: true },
    lineStyle: { width: 2.4, color },
    itemStyle: { color },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: `${color}44` },
        { offset: 1, color: `${color}00` },
      ]),
    },
    data,
  }
}

function renderHourlyChart() {
  const chart = getChart(hourlyChartRef.value, 'selected-alarm-trend')
  if (!chart) return
  chart.setOption({
    color: ['#52dcff'],
    tooltip: { ...chartTooltip, trigger: 'axis' },
    grid: { left: 34, right: 12, top: 14, bottom: 28 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: selectedData.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: chartTextColor, fontSize: 10, interval: 'auto' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: 10 },
    },
    series: [{
      name: '告警数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: false,
      lineStyle: { width: 2.4, color: '#52dcff' },
      itemStyle: { color: '#52dcff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(82, 220, 255, .42)' },
          { offset: 1, color: 'rgba(82, 220, 255, 0)' },
        ]),
      },
      emphasis: { focus: 'series' },
      data: selectedData.value.totalCounts,
    }],
  }, true)
}

function renderCompositionChart() {
  const chart = getChart(compositionChartRef.value, 'risk-composition')
  if (!chart) return
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value) => `${value} 次`,
    },
    legend: {
      right: 2,
      top: 0,
      icon: 'circle',
      itemWidth: 7,
      itemHeight: 7,
      itemGap: 10,
      textStyle: { color: chartTextColor, fontSize: 10 },
      data: ['低风险', '中风险', '高风险'],
    },
    grid: { left: 36, right: 12, top: 26, bottom: 24 },
    xAxis: {
      type: 'category',
      data: riskCompositionData.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: '#bdeaff', fontSize: 12, interval: 0 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: 10 },
    },
    series: ['LOW', 'MEDIUM', 'HIGH'].map((level) => ({
      name: riskLevelLabel(level),
      type: 'bar',
      stack: 'risk',
      barWidth: '38%',
      itemStyle: { color: riskColors[level], borderRadius: level === 'HIGH' ? [2, 2, 0, 0] : 0 },
      emphasis: { focus: 'series' },
      data: riskCompositionData.value.risk[level],
    })),
  }, true)
}

function renderDisposalChart() {
  const chart = getChart(disposalChartRef.value, 'disposal')
  if (!chart) return
  const stats = disposalStats.value
  const visibleUnit = Math.max(stats.total * .018, .22)
  const data = [
    { name: '已处置', value: stats.handled || visibleUnit, realValue: stats.handled, itemStyle: { color: '#38D59C' } },
    { name: '处理中', value: stats.processing || visibleUnit, realValue: stats.processing, itemStyle: { color: '#FFB648' } },
    { name: '未处置', value: stats.pending || visibleUnit, realValue: stats.pending, itemStyle: { color: '#FF5B68' } },
  ]
  if (!stats.total) data.splice(0, data.length, { name: '暂无数据', value: 1, realValue: 0, itemStyle: { color: 'rgba(143, 200, 242, .16)' } })
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'item',
      formatter: (params) => `${params.name}<br/>${params.data?.realValue ?? params.value} 次`,
    },
    series: [{
      type: 'pie',
      radius: ['72%', '86%'],
      center: ['50%', '50%'],
      label: { show: false },
      labelLine: { show: false },
      itemStyle: { borderColor: '#06182b', borderWidth: 2 },
      emphasis: { scale: true, scaleSize: 4 },
      data,
    }],
  }, true)
}

function renderDeviceChart() {
  const chart = getChart(deviceChartRef.value, 'device')
  if (!chart) return
  const total = Math.max(deviceTotal.value, 0)
  const visibleUnit = total ? Math.max(total * .018, .18) : 0
  const onlineValue = total ? (deviceOnline.value || visibleUnit) : 0
  const offlineValue = total ? (deviceOffline.value || visibleUnit) : 0
  const data = total
    ? [
      { name: '在线', value: onlineValue, realValue: deviceOnline.value, itemStyle: { color: '#38D59C' } },
      { name: '离线', value: offlineValue, realValue: deviceOffline.value, itemStyle: { color: '#FF5B68' } },
    ]
    : [
      { name: '暂无数据', value: 1, realValue: 0, itemStyle: { color: 'rgba(143, 200, 242, .18)' } },
    ]
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'item',
      formatter: (params) => `${params.name}<br/>${params.data?.realValue ?? params.value} 台`,
    },
    series: [{
      type: 'pie',
      radius: ['62%', '82%'],
      center: ['50%', '50%'],
      startAngle: 90,
      clockwise: true,
      avoidLabelOverlap: false,
      padAngle: 1.5,
      selectedOffset: 0,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: {
        borderColor: '#06182b',
        borderWidth: 1,
        borderRadius: 8,
      },
      emphasis: { scale: true, scaleSize: 2 },
      data,
    }],
  }, true)
}

function renderAllCharts() {
  renderRiskCharts()
  renderTrendChart()
  renderHourlyChart()
  renderCompositionChart()
  renderDisposalChart()
  renderDeviceChart()
}

function resizeCharts() {
  renderAllCharts()
}

function formatNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? String(Math.max(0, number)).padStart(2, '0') : '--'
}

function compareNumber(current, previous) {
  const delta = Number(current || 0) - Number(previous || 0)
  if (delta > 0) return { icon: '↑', delta: delta, tone: 'up' }
  if (delta < 0) return { icon: '↓', delta: Math.abs(delta), tone: 'down' }
  return { icon: '−', delta: 0, tone: 'flat' }
}

function eventTimestamp(event) {
  const time = Date.parse(event?.started_at || event?.last_observed_at || '')
  return Number.isFinite(time) ? time : 0
}

function riskLevel(event) {
  return ['LOW', 'MEDIUM', 'HIGH'].includes(event?.max_risk_level) ? event.max_risk_level : event?.risk_level
}

function riskRank(event) {
  return ({ LOW: 1, MEDIUM: 2, HIGH: 3 })[riskLevel(event)] || 0
}

function riskLevelLabel(level) {
  return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[level] || '未知'
}

function riskLabel(event) {
  return riskLevelLabel(riskLevel(event))
}

function riskClass(event) {
  return ({ LOW: 'low', MEDIUM: 'medium', HIGH: 'high' })[riskLevel(event)] || 'unknown'
}

function deviceTypeLabel(key) {
  return ({
    camera: '摄像头',
    sensor: '传感器',
    sensors: '传感器',
    rain: '雨量计',
    wind: '风速风向',
    vibration: '振动传感器',
    temp_humidity: '温湿度传感器',
    temperature_humidity: '温湿度传感器',
    drone: '无人机',
  })[key] || key || '设备'
}

function isHandled(event) {
  return event?.state === 'RESOLVED' || ['COMPLETED', 'FALSE_ALARM'].includes(event?.status)
}

function getOverviewCategory(event) {
  const category = String(event?.event_category || '').toUpperCase()
  const text = `${event?.event_name || ''} ${event?.summary || ''}`.toUpperCase()
  if (category === 'PERSON_SAFETY' || category.includes('PERSON')) return 'person'
  if (category === 'ILLEGAL_FISHING' || category.includes('FISH') || category.includes('BOAT')) return 'boat'
  if (
    category.includes('FLOOD')
    || category.includes('EARTHQUAKE')
    || category.includes('LANDSLIDE')
    || category.includes('DEBRIS')
    || /洪水|地震|泥石流|滑坡/.test(text)
  ) return 'disaster'
  return 'other'
}

function rangeStart(type) {
  const now = new Date()
  const start = new Date(now)
  if (type === 'today' || type === 'yesterday') start.setHours(0, 0, 0, 0)
  if (type === 'yesterday') start.setDate(start.getDate() - 1)
  if (type === 'week' || type === 'lastWeek') {
    const day = (start.getDay() + 6) % 7
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() - day)
    if (type === 'lastWeek') start.setDate(start.getDate() - 7)
  }
  if (type === 'month' || type === 'lastMonth') {
    start.setHours(0, 0, 0, 0)
    start.setDate(1)
    if (type === 'lastMonth') start.setMonth(start.getMonth() - 1)
  }
  return start
}

function rangeEnd(type) {
  const end = new Date()
  if (type === 'yesterday') end.setDate(end.getDate() - 1)
  if (type === 'lastWeek') {
    const start = rangeStart('week')
    return start
  }
  if (type === 'lastMonth') {
    const start = rangeStart('month')
    return start
  }
  return end
}

function eventsInWindow(type) {
  const start = rangeStart(type).getTime()
  const end = rangeEnd(type).getTime()
  return events.value.filter((event) => {
    const time = eventTimestamp(event)
    return time >= start && time <= end
  })
}

function trendLabels(mode) {
  if (mode === 'today') return Array.from({ length: 24 }, (_, index) => `${String(index).padStart(2, '0')}:00`)
  const start = rangeStart(mode)
  const end = new Date()
  const labels = []
  const cursor = new Date(start)
  while (cursor <= end) {
    labels.push(`${cursor.getMonth() + 1}/${cursor.getDate()}`)
    cursor.setDate(cursor.getDate() + 1)
  }
  return labels.length ? labels : ['--']
}

function trendBuckets(mode, category) {
  const labels = trendLabels(mode)
  const buckets = Array.from({ length: labels.length }, () => 0)
  const start = rangeStart(mode)
  const source = eventsInWindow(mode).filter((event) => getOverviewCategory(event) === category)
  source.forEach((event) => {
    const date = new Date(eventTimestamp(event))
    const index = mode === 'today'
      ? date.getHours()
      : Math.floor((date - start) / (24 * 60 * 60 * 1000))
    if (index >= 0 && index < buckets.length) buckets[index] += 1
  })
  return buckets
}

function eventTimelineBuckets(sourceEvents, mode) {
  const labels = trendLabels(mode)
  const start = rangeStart(mode)
  const end = rangeEnd(mode)
  const total = Array.from({ length: labels.length }, () => 0)
  const risk = {
    LOW: Array.from({ length: labels.length }, () => 0),
    MEDIUM: Array.from({ length: labels.length }, () => 0),
    HIGH: Array.from({ length: labels.length }, () => 0),
  }
  sourceEvents.forEach((event) => {
    const time = eventTimestamp(event)
    if (time < start.getTime() || time > end.getTime()) return
    const date = new Date(time)
    const index = mode === 'today'
      ? date.getHours()
      : Math.floor((date - start) / (24 * 60 * 60 * 1000))
    if (index < 0 || index >= labels.length) return
    const level = riskLevel(event)
    total[index] += 1
    if (risk[level]) risk[level][index] += 1
  })
  return { labels, total, risk }
}

function alertTitle(event) {
  return event?.event_name || event?.summary || '安全告警事件'
}

function logTypeLabel(value) {
  return ({ TRIGGER: '事件触发', RISK_CHANGE: '风险变化', ACTION: '执行动作', MANUAL: '人工操作', RESOLVE: '事件闭环', SYSTEM: '系统记录' })[value] || value || '系统记录'
}

function riskAutoSequence() {
  return riskModes.flatMap((mode) => riskLevels.map((_, levelIndex) => ({
    modeKey: mode.key,
    levelIndex,
  })))
}

function currentRiskAutoIndex() {
  const sequence = riskAutoSequence()
  const index = sequence.findIndex((item) => item.modeKey === activeRiskModeKey.value && item.levelIndex === riskFocusIndex.value)
  return index >= 0 ? index : 0
}

function applyRiskAutoStep(index) {
  const sequence = riskAutoSequence()
  const item = sequence[((index % sequence.length) + sequence.length) % sequence.length]
  activeRiskModeKey.value = item.modeKey
  riskFocusIndex.value = item.levelIndex
}

function advanceRiskAuto() {
  applyRiskAutoStep(currentRiskAutoIndex() + 1)
}

function restartRiskTimer() {
  window.clearInterval(riskTimer)
  riskTimer = window.setInterval(advanceRiskAuto, 3000)
}

function scheduleRiskAutoResume() {
  window.clearInterval(riskTimer)
  window.clearTimeout(riskResumeTimer)
  riskResumeTimer = window.setTimeout(() => {
    advanceRiskAuto()
    restartRiskTimer()
  }, 3000)
}

function handleRiskModeClick(modeKey) {
  activeRiskModeKey.value = modeKey
  riskFocusIndex.value = 0
  scheduleRiskAutoResume()
}

function clampMapOffset() {
  const board = mapBoardRef.value
  const { width, height } = mapBaseSize.value
  if (!board || !width || !height) return
  const rect = board.getBoundingClientRect()
  const maxX = Math.max((width * mapScale.value - rect.width) / 2, 0)
  const maxY = Math.max((height * mapScale.value - rect.height) / 2, 0)
  mapOffset.value = {
    x: Math.max(-maxX, Math.min(maxX, mapOffset.value.x)),
    y: Math.max(-maxY, Math.min(maxY, mapOffset.value.y)),
  }
}

function focusMapPoint(no, options = {}) {
  const point = cameraPoints.find((item) => item.no === no)
  const { width, height } = mapBaseSize.value
  if (!point || !width || !height) return
  const targetScale = Math.max(minMapScale.value, Math.min(4, options.scale || mapFocusScale))
  const pointX = (point.x / 100 - .5) * width
  const pointY = (point.y / 100 - .5) * height
  mapScale.value = targetScale
  mapOffset.value = {
    x: -pointX * targetScale,
    y: -pointY * targetScale,
  }
  clampMapOffset()
}

function focusSelectedMapPoint() {
  focusMapPoint(selectedPointNo.value, { scale: mapFocusScale })
}

function zoomMapBy(ratio) {
  const nextScale = Math.max(minMapScale.value, Math.min(4, mapScale.value * ratio))
  if (nextScale === mapScale.value) return
  const scaleRatio = nextScale / mapScale.value
  mapScale.value = nextScale
  mapOffset.value = {
    x: mapOffset.value.x * scaleRatio,
    y: mapOffset.value.y * scaleRatio,
  }
  clampMapOffset()
}

function updateMapBaseSize() {
  const board = mapBoardRef.value
  if (!board) return
  const rect = board.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const fitScale = Math.max(rect.width / 2168, rect.height / 725)
  const width = Math.ceil(2168 * fitScale)
  const height = Math.ceil(725 * fitScale)
  mapBaseSize.value = { width, height }
  minMapScale.value = Math.min(1, rect.width / width, rect.height / height)
  if (mapScale.value < minMapScale.value) mapScale.value = minMapScale.value
  if (!mapInitialFocused) {
    mapInitialFocused = true
    focusMapPoint(selectedPointNo.value, { scale: mapFocusScale })
  } else {
    clampMapOffset()
  }
}

function handleMapWheel(event) {
  if (!mapBaseSize.value.width) return
  const board = mapBoardRef.value
  const rect = board.getBoundingClientRect()
  const nextScale = Math.max(minMapScale.value, Math.min(4, mapScale.value * (event.deltaY > 0 ? 0.9 : 1.1)))
  if (nextScale === mapScale.value) return
  const pointerX = event.clientX - rect.left - rect.width / 2
  const pointerY = event.clientY - rect.top - rect.height / 2
  const ratio = nextScale / mapScale.value
  mapOffset.value = {
    x: pointerX - (pointerX - mapOffset.value.x) * ratio,
    y: pointerY - (pointerY - mapOffset.value.y) * ratio,
  }
  mapScale.value = nextScale
  clampMapOffset()
}

function startMapDrag(event) {
  if (event.button !== 0) return
  mapDragState.active = true
  mapDragState.moved = false
  mapDragState.startX = event.clientX
  mapDragState.startY = event.clientY
  mapDragState.startOffsetX = mapOffset.value.x
  mapDragState.startOffsetY = mapOffset.value.y
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function moveMapDrag(event) {
  if (!mapDragState.active) return
  const deltaX = event.clientX - mapDragState.startX
  const deltaY = event.clientY - mapDragState.startY
  if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) mapDragState.moved = true
  mapOffset.value = {
    x: mapDragState.startOffsetX + deltaX,
    y: mapDragState.startOffsetY + deltaY,
  }
  clampMapOffset()
}

function endMapDrag(event) {
  if (!mapDragState.active) return
  event.currentTarget.releasePointerCapture?.(event.pointerId)
  mapDragState.active = false
  window.setTimeout(() => {
    mapDragState.moved = false
  }, 0)
}

function selectPoint(no) {
  if (mapDragState.moved) return
  selectedPointNo.value = no
}

function updateClock() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  currentDate.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  currentTime.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  currentWeek.value = weekLabels[now.getDay()]
}

async function fetchPriorityDetail() {
  const id = priorityAlert.value?.id
  if (!id) {
    currentPriorityDetailId = null
    priorityDetail.value = { timeline: [] }
    return
  }
  if (id === currentPriorityDetailId) return
  currentPriorityDetailId = id
  try {
    const res = await getUnifiedSafetyEventDetail(id)
    priorityDetail.value = { timeline: res.data?.timeline || [] }
  } catch {
    priorityDetail.value = { timeline: [] }
  }
}

async function fetchData() {
  loading.value = true
  const [statsResult, eventsResult, statusResult, cameraResult] = await Promise.allSettled([
    getUnifiedSafetyEventStatistics(),
    getUnifiedSafetyEvents({ page: 1, page_size: 100 }),
    getDeviceStatus(),
    getCameraList(),
  ])

  if (statsResult.status === 'fulfilled' && statsResult.value?.data) {
    eventStats.value = statsResult.value.data || {}
  }
  if (eventsResult.status === 'fulfilled' && eventsResult.value?.data) {
    events.value = (eventsResult.value.data.items || []).slice().sort((a, b) => eventTimestamp(b) - eventTimestamp(a))
  }
  if (statusResult.status === 'fulfilled' && statusResult.value?.data) {
    deviceStatus.value = statusResult.value.data || {}
  }
  if (cameraResult.status === 'fulfilled') {
    const cameras = cameraResult.value?.data?.cameras || []
    const enabled = cameras.filter((camera) => camera.enabled !== false)
    cameraSummary.value = {
      online: enabled.filter((camera) => camera.connected).length,
      total: enabled.length,
    }
  }
  await fetchPriorityDetail()
  loading.value = false
  await nextTick()
  renderAllCharts()
}

watch(
  [riskDistribution, activeRiskModeKey, activeRiskLevel, intrusionTrend, selectedData, riskCompositionData, disposalStats, deviceRate],
  () => nextTick(renderAllCharts),
  { deep: true }
)

onMounted(() => {
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  updateMapBaseSize()
  if (window.ResizeObserver && mapBoardRef.value) {
    mapResizeObserver = new ResizeObserver(updateMapBaseSize)
    mapResizeObserver.observe(mapBoardRef.value)
  }
  restartRiskTimer()
  fetchData()
  refreshTimer = window.setInterval(fetchData, 30000)
  window.addEventListener('resize', resizeCharts)
  nextTick(renderAllCharts)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  window.clearInterval(refreshTimer)
  window.clearInterval(riskTimer)
  window.clearTimeout(riskResumeTimer)
  window.removeEventListener('resize', resizeCharts)
  mapResizeObserver?.disconnect()
  chartInstances.forEach((chart) => chart.dispose())
  chartInstances.clear()
})
</script>

<style scoped>
:global(.bigscreen-chart-tooltip) {
  max-width: 240px !important;
  white-space: normal !important;
  word-break: break-word !important;
  border-radius: 8px !important;
  z-index: 99999 !important;
  pointer-events: none;
}

.bigscreen-page {
  --panel-radius: 8px;
  --panel-border: rgba(74, 163, 214, .24);
  --panel-border-soft: rgba(74, 163, 214, .16);
  --panel-bg: linear-gradient(180deg, rgba(6, 28, 49, .94), rgba(3, 18, 33, .96));
  --panel-glow: 0 12px 28px rgba(0, 0, 0, .26), inset 0 1px 0 rgba(185, 229, 255, .045);
  --card-bg: linear-gradient(180deg, rgba(8, 35, 61, .68), rgba(4, 23, 42, .7));
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  color: #eef7ff;
  background:
    radial-gradient(circle at 50% 30%, rgba(38, 119, 170, 0.08), transparent 38%),
    linear-gradient(135deg, #020812 0%, #061827 54%, #020a13 100%);
  font-family: "Bahnschrift", "DIN Alternate", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.ambient-grid {
  position: absolute;
  inset: 0;
  opacity: .08;
  pointer-events: none;
  background:
    linear-gradient(rgba(67, 200, 255, .08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67, 200, 255, .06) 1px, transparent 1px);
  background-size: 44px 44px;
}

.screen-header,
.screen-grid {
  position: relative;
  z-index: 1;
}

.screen-header {
  height: 86px;
  display: grid;
  grid-template-columns: minmax(560px, 1fr) minmax(360px, 1fr) minmax(230px, 1fr);
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(74, 163, 214, .18);
  background: linear-gradient(180deg, rgba(2, 12, 24, .92), rgba(2, 12, 24, .72));
}

.brand-block,
.clock-block {
  display: flex;
  align-items: center;
}

.brand-block {
  gap: 11px;
  min-width: 0;
}

.brand-mark {
  width: 28px;
  height: 28px;
  clip-path: polygon(18% 0, 100% 0, 72% 42%, 100% 100%, 20% 72%, 0 38%);
  background: linear-gradient(135deg, #52d8ff, #2679ff);
  box-shadow: none;
}

.brand-block strong {
  flex: 0 0 auto;
  color: #cbe7ff;
  font-size: 16px;
  letter-spacing: 1px;
}

.screen-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-left: 18px;
}

.screen-nav span {
  height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 0 14px;
  border: 1px solid transparent;
  color: #748da3;
  font-size: 13px;
  white-space: nowrap;
}

.screen-nav span.active {
  border-color: rgba(67, 200, 255, .58);
  color: #bdeaff;
  background: rgba(35, 119, 204, .16);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .05);
}

.screen-title h1 {
  margin: 0;
  color: #f4fbff;
  font-size: 28px;
  letter-spacing: 6px;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.clock-block {
  width: 100%;
  height: 100%;
  justify-content: space-between;
  gap: 10px;
}

.clock-block span {
  color: #88a9c1;
  font-size: 12px;
  white-space: nowrap;
}

.clock-block strong {
  color: #fff;
  font-size: 23px;
  letter-spacing: 1px;
  line-height: 1;
}

.clock-block em {
  display: inline-flex;
  align-items: center;
  color: #38d59c;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.clock-block i,
.online-badge i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 6px currentColor;
}

.screen-grid {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 20fr) minmax(760px, 62fr) minmax(230px, 18fr);
  gap: 10px;
  padding: 10px 14px 12px;
  overflow: hidden;
}

.left-column,
.center-column,
.right-column {
  min-height: 0;
  display: grid;
  gap: 10px;
  overflow: hidden;
}

.left-column {
  grid-template-rows: minmax(0, 28fr) minmax(0, 28fr) minmax(0, 36fr);
}

.center-column {
  grid-template-rows: minmax(0, 65fr) minmax(240px, 35fr);
}

.right-column {
  grid-template-rows: 74px minmax(0, 1fr) 202px;
}

.screen-panel,
.map-panel,
.selected-detail {
  min-width: 0;
  min-height: 0;
  position: relative;
  border: 1px solid var(--panel-border);
  border-radius: var(--panel-radius);
  background: var(--panel-bg);
  box-shadow: var(--panel-glow);
  overflow: hidden;
  box-sizing: border-box;
}

.screen-panel::before,
.map-panel::before,
.selected-detail::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255, 255, 255, .045), transparent 26%);
  opacity: .55;
}

.screen-panel,
.selected-detail {
  padding: 14px;
}

.clock-panel {
  padding: 12px 14px;
}

.clock-panel .clock-block {
  position: relative;
  z-index: 1;
  align-items: center;
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(10, 45, 73, .5), rgba(3, 22, 40, .22));
  padding: 0 4px;
}

.panel-heading,
.sub-heading,
.selected-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-heading h2,
.selected-title h2,
.sub-heading h3 {
  margin: 0;
  color: #eef7ff;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0;
  text-shadow: none;
}

.sub-heading h3 {
  font-size: 16px;
}

.sub-heading span,
.selected-title span {
  color: #9ed3f5;
  font-size: 12px;
}

.disposal-card .sub-heading span {
  color: #8fc8f2;
  font-size: 12px;
}

.segmented {
  display: flex;
  padding: 2px;
  border: 1px solid rgba(67, 200, 255, .24);
  border-radius: 6px;
  background: rgba(2, 16, 31, .78);
  box-shadow: none;
}

.segmented button,
.mini-segmented button {
  height: 24px;
  padding: 0 10px;
  border: 0;
  color: #88a9c1;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}

.segmented button.active,
.mini-segmented button.active {
  color: #e9f8ff;
  background: linear-gradient(180deg, rgba(67, 200, 255, .26), rgba(37, 116, 204, .18));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .06);
}

.mini-segmented {
  display: flex;
  flex: 0 0 auto;
  padding: 1px;
  border: 1px solid rgba(67, 200, 255, .24);
  border-radius: 6px;
  background: rgba(2, 16, 31, .62);
}

.mini-segmented button {
  height: 22px;
  padding: 0 8px;
  font-size: 10px;
}

.today-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 10px;
}

.today-card {
  min-height: 76px;
  display: grid;
  grid-template-columns: 34px 1fr;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--panel-border-soft);
  border-radius: 8px;
  background: var(--card-bg);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .035);
}

.metric-icon {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: currentColor;
  background: rgba(255, 255, 255, .07);
  font-size: 18px;
  box-shadow: none;
}

.today-card span:not(.metric-icon),
.today-card em {
  display: block;
  color: #a4d2ee;
  font-size: 12px;
  font-style: normal;
}

.today-card strong {
  display: block;
  margin: 3px 0;
  color: #fff;
  font-size: 26px;
  line-height: 1;
}

.today-card em i {
  display: inline-flex;
  min-width: 22px;
  align-items: center;
  justify-content: flex-start;
  margin-right: 4px;
  font-style: normal;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.today-card.danger { color: #ff6873; }
.today-card.boat { color: #41c8ff; }
.today-card.purple { color: #9b73ff; }
.today-card.cyan { color: #43c8ff; }

.up,
.down,
.flat {
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.up { color: #ff5b68; }
.down { color: #38d59c; }
.flat { color: #88a9c1; }

.echarts-chart {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.risk-panel {
  display: grid;
  grid-template-rows: 34px minmax(0, 1fr);
  gap: 8px;
}

.risk-switch {
  display: flex;
  flex: 0 0 auto;
  padding: 2px;
  border: 1px solid rgba(74, 163, 214, .22);
  border-radius: 6px;
  background: rgba(3, 20, 36, .72);
}

.risk-switch button {
  height: 24px;
  padding: 0 12px;
  border: 0;
  color: #88a9c1;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}

.risk-switch button.active {
  color: #e9f8ff;
  background: rgba(42, 111, 157, .36);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .06);
}

.risk-showcase {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(128px, 1.05fr) minmax(106px, .95fr);
  align-items: center;
  gap: 14px;
}

.risk-chart-wrap {
  position: relative;
  width: min(150px, 100%);
  aspect-ratio: 1;
  justify-self: center;
}

.risk-main-chart {
  width: 100%;
  height: 100%;
}

.risk-center {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 76px;
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  gap: 4px;
  pointer-events: none;
  text-align: center;
}

.risk-center strong {
  color: #fff;
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.risk-center span {
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.risk-center span.risk-level-LOW,
.risk-summary strong.risk-level-LOW {
  color: #38d59c;
}

.risk-center span.risk-level-MEDIUM,
.risk-summary strong.risk-level-MEDIUM {
  color: #ffb648;
}

.risk-center span.risk-level-HIGH,
.risk-summary strong.risk-level-HIGH {
  color: #ff5b68;
}

.risk-summary {
  min-width: 0;
  display: grid;
  gap: 10px;
  color: #8fc8f2;
}

.risk-summary span {
  font-size: 14px;
}

.risk-summary strong {
  min-width: 74px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  justify-self: start;
  padding: 0 10px;
  border: 1px solid rgba(93, 183, 232, .26);
  border-radius: 6px;
  color: #eef7ff;
  background: rgba(14, 58, 92, .34);
  font-size: 15px;
  line-height: 1;
  font-weight: 800;
  box-shadow: none;
}

.risk-summary em {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  color: #c4e8fb;
  background: rgba(67, 200, 255, .07);
  font-size: 14px;
  font-style: normal;
  line-height: 1;
}

.risk-summary em b {
  display: inline-flex;
  min-width: 32px;
  align-items: center;
  justify-content: flex-start;
  margin-left: 0;
  font-weight: 700;
  font-size: 17px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.trend-legend i {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
}

.trend-panel {
  display: grid;
  grid-template-rows: 34px 18px minmax(0, 1fr);
  align-items: stretch;
}

.trend-panel .panel-heading {
  height: 34px;
  min-height: 0;
}

.trend-legend {
  display: flex;
  height: 18px;
  min-height: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  margin: 0;
  color: #a4d2ee;
  font-size: 12px;
  overflow: hidden;
}

.trend-legend i.person {
  background: #ff6873;
}

.trend-legend i.boat {
  background: #41c8ff;
}

.line-chart {
  width: 100%;
  height: 100%;
  min-height: 0;
  margin-top: 0;
  overflow: hidden;
}

.person-path { stroke: #ff6873; }
.boat-path { stroke: #41c8ff; }

.map-panel {
  overflow: hidden;
}

.map-board {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  background: #051323;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.map-board:active {
  cursor: grabbing;
}

.map-controls {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 6;
  display: grid;
  gap: 7px;
  pointer-events: auto;
}

.map-controls button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(96, 190, 244, .32);
  border-radius: 6px;
  color: #e6f8ff;
  background: rgba(4, 24, 43, .78);
  box-shadow: 0 8px 20px rgba(0, 0, 0, .22), inset 0 1px 0 rgba(255, 255, 255, .08);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background .18s ease, border-color .18s ease, color .18s ease, transform .18s ease;
}

.map-controls button:hover {
  border-color: rgba(111, 214, 255, .72);
  color: #fff;
  background: rgba(19, 71, 111, .82);
  transform: translateY(-1px);
}

.map-controls .locate {
  position: relative;
  margin-top: 3px;
  color: #e6f8ff;
  font-size: 0;
}

.map-controls .locate::before,
.map-controls .locate::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.map-controls .locate::before {
  width: 12px;
  height: 12px;
  border: 1px solid currentColor;
  border-radius: 50%;
  box-shadow: none;
}

.map-controls .locate::after {
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: currentColor;
  box-shadow:
    0 -8px 0 -1px currentColor,
    0 8px 0 -1px currentColor,
    -8px 0 0 -1px currentColor,
    8px 0 0 -1px currentColor;
}

.map-controls .locate span {
  position: absolute;
  inset: 0;
}

.map-controls .locate span::before,
.map-controls .locate span::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  background: currentColor;
  transform: translate(-50%, -50%);
}

.map-controls .locate span::before {
  width: 18px;
  height: 1px;
}

.map-controls .locate span::after {
  width: 1px;
  height: 18px;
}

.map-scene {
  position: absolute;
  top: 50%;
  left: 50%;
  transform-origin: center center;
  will-change: transform;
}

.satellite-image,
.map-shade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.satellite-image {
  object-fit: fill;
  filter: saturate(1.08) contrast(1.06) brightness(.72);
  pointer-events: none;
  user-select: none;
}

.map-shade {
  pointer-events: none;
  background:
    radial-gradient(circle at 48% 50%, transparent 48%, rgba(0, 9, 20, .34)),
    linear-gradient(180deg, rgba(0, 17, 35, .04), rgba(0, 12, 25, .08));
}

.camera-point {
  position: absolute;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid rgba(255, 172, 178, .9);
  border-radius: 50%;
  color: #fff;
  background: radial-gradient(circle, #ff6b72 0 42%, rgba(167, 30, 38, .92) 43% 100%);
  box-shadow: 0 0 0 4px rgba(255, 91, 104, .12), 0 4px 14px rgba(0, 0, 0, .28);
  transform: translate(-50%, -50%);
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease;
  animation: pointPulse 2.4s ease-in-out infinite;
  z-index: 3;
}

.camera-point span {
  display: block;
  font-size: 12px;
  font-weight: 800;
  line-height: 22px;
}

.camera-point:hover,
.camera-point.active {
  transform: translate(-50%, -50%) scale(1.12);
}

.camera-point.active {
  border-color: #fff;
  box-shadow: 0 0 0 6px rgba(255, 91, 104, .18), 0 6px 18px rgba(0, 0, 0, .34);
  animation-duration: 1.35s;
}

.selected-detail {
  min-height: 0;
  padding: 12px 16px 14px;
}

.selected-title {
  height: 42px;
  margin-bottom: 6px;
  align-items: flex-start;
}

.selected-title > div {
  display: grid;
  gap: 5px;
}

.selected-title span {
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1;
  letter-spacing: .5px;
}

.selected-title h2 {
  width: fit-content;
  max-width: 100%;
  margin: 0;
  color: #f2fbff;
  font-size: 21px;
  line-height: 1.12;
  letter-spacing: 0;
  text-shadow: none;
}

.selected-title h2::after {
  content: none;
}

.analytics-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.18fr .98fr;
  gap: 12px;
  height: calc(100% - 48px);
  min-height: 0;
}

.analytics-card {
  min-width: 0;
  min-height: 0;
  padding: 12px 14px;
  border: 1px solid rgba(67, 200, 255, .2);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(9, 37, 65, .66), rgba(1, 17, 32, .58));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
  overflow: hidden;
}

.analytics-card .sub-heading {
  height: 28px;
  align-items: flex-start;
}

.analytics-card .sub-heading h3 {
  color: #f2fbff;
  font-size: 17px;
  line-height: 1.1;
  font-weight: 800;
}

.analytics-card .sub-heading span {
  color: #8ecaf1;
  font-size: 12px;
  line-height: 1.1;
}

.bar-chart {
  height: calc(100% - 30px);
  min-height: 0;
  margin-top: 6px;
}

.risk-composition {
  height: calc(100% - 30px);
  min-height: 0;
  margin-top: 6px;
  overflow: hidden;
}

.disposal-body {
  display: grid;
  grid-template-columns: minmax(126px, .9fr) minmax(150px, 1.1fr);
  gap: 14px;
  align-items: center;
  height: calc(100% - 30px);
  margin-top: 6px;
}

.disposal-ring-wrap {
  position: relative;
  width: 132px;
  height: 132px;
  justify-self: center;
}

.disposal-ring {
  width: 100%;
  height: 100%;
}

.disposal-center {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 86px;
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  gap: 2px;
  pointer-events: none;
  text-align: center;
}

.disposal-center strong {
  color: #fff;
  font-size: 31px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.disposal-center span {
  color: #8fc8f2;
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}

.disposal-list {
  display: grid;
  gap: 14px;
  min-width: 0;
  color: #d8eefc;
  font-size: 15px;
}

.disposal-list i {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 9px;
  border-radius: 50%;
  box-shadow: none;
}

.disposal-list span {
  display: flex;
  align-items: center;
  min-width: 0;
  white-space: nowrap;
  line-height: 1.15;
}

.disposal-list .handled { background: #38d59c; }
.disposal-list .processing { background: #ffb648; }
.disposal-list .pending { background: #ff5b68; }

.help-tip {
  display: inline-grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border: 1px solid rgba(136, 169, 193, .42);
  border-radius: 50%;
  color: rgba(220, 237, 248, .72);
  font-size: 12px;
  cursor: help;
}

.priority-summary {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 91, 104, .34);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 91, 104, .12), rgba(255, 91, 104, .055));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .045);
}

.priority-summary strong {
  font-size: 15px;
}

.priority-summary strong.low { color: #38d59c; }
.priority-summary strong.medium { color: #ffb648; }
.priority-summary strong.high { color: #ff5b68; }

.priority-summary span {
  color: #eef7ff;
  font-size: 15px;
}

.priority-summary.empty {
  border-color: rgba(56, 213, 156, .24);
  background: rgba(56, 213, 156, .06);
}

.alarm-idle {
  display: grid;
  grid-template-columns: 74px 1fr;
  gap: 14px;
  align-items: center;
  margin-top: 18px;
  padding: 16px;
  border: 1px solid rgba(67, 200, 255, .16);
  border-radius: 8px;
  background:
    radial-gradient(circle at 36px 40px, rgba(56, 213, 156, .13), transparent 58px),
    rgba(5, 24, 43, .46);
}

.idle-orbit {
  position: relative;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(67, 200, 255, .22);
  border-radius: 50%;
  background: rgba(3, 18, 33, .58);
}

.idle-orbit::before,
.idle-orbit::after {
  content: "";
  position: absolute;
  border-radius: 50%;
}

.idle-orbit::before {
  inset: 15px;
  border: 2px solid rgba(56, 213, 156, .72);
}

.idle-orbit::after {
  left: 50%;
  top: 50%;
  width: 8px;
  height: 8px;
  transform: translate(-50%, -50%);
  background: #38d59c;
  box-shadow: 0 0 12px rgba(56, 213, 156, .72);
}

.idle-orbit span {
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  border-top: 2px solid rgba(67, 200, 255, .72);
  border-right: 2px solid transparent;
  animation: idleSpin 3.8s linear infinite;
}

.idle-orbit i {
  position: absolute;
  right: 8px;
  top: 12px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #43c8ff;
}

.idle-copy {
  min-width: 0;
  display: grid;
  gap: 7px;
}

.idle-copy strong {
  color: #e9f8ff;
  font-size: 16px;
  line-height: 1;
}

.idle-copy span {
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1.35;
}

.idle-status-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.idle-status-grid span {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 9px 8px;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 6px;
  color: #7faeca;
  font-size: 11px;
  background: rgba(2, 14, 28, .36);
}

.idle-status-grid i {
  color: #cceeff;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.progress-timeline {
  position: relative;
  display: grid;
  gap: 26px;
  margin: 22px 0 0;
  padding: 0 0 0 22px;
  list-style: none;
}

.progress-timeline::before {
  content: "";
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 7px;
  width: 1px;
  background: linear-gradient(180deg, #ff5b68, #ffb648, rgba(136, 169, 193, .25));
}

.progress-timeline li {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 22px;
  color: #cfe2f0;
  font-size: 15px;
}

.progress-timeline i {
  position: absolute;
  left: -22px;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(136, 169, 193, .58);
  border-radius: 50%;
  background: #071a2f;
}

.progress-timeline li.active i {
  border-color: #ff5b68;
  box-shadow: 0 0 0 4px rgba(255, 91, 104, .12);
}

.device-panel.warning {
  border-color: rgba(255, 91, 104, .34);
}

.device-state {
  display: grid;
  grid-template-columns: minmax(118px, .9fr) minmax(0, 1.1fr);
  gap: 14px;
  align-items: center;
  height: calc(100% - 34px);
  margin-top: 10px;
}

.device-gauge-wrap {
  position: relative;
  min-width: 0;
  min-height: 0;
  width: min(126px, 100%);
  aspect-ratio: 1;
  justify-self: center;
  border: 0;
  border-radius: 0;
  background: transparent;
  overflow: visible;
}

.device-gauge-wrap::after {
  content: none;
}

.device-ring {
  position: absolute;
  inset: 0;
}

.device-center {
  position: absolute;
  left: 50%;
  top: 50%;
  display: grid;
  place-items: center;
  gap: 4px;
  width: 62px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  text-align: center;
}

.device-center strong {
  color: #fff;
  font-size: 24px;
  line-height: 1;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.device-center span {
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.device-counts {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.device-count-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.device-counts article {
  position: relative;
  min-width: 0;
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 7px;
  background: rgba(2, 16, 30, .32);
}

.device-counts span {
  color: #a4d2ee;
  font-size: 12px;
  line-height: 1;
}

.device-counts strong {
  display: block;
  color: #38d59c;
  font-size: 22px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.device-counts .offline strong {
  color: #ff5b68;
}

.device-report {
  min-height: 48px;
  display: flex;
  align-items: center;
  margin: 0;
  padding: 8px 10px;
  border-radius: 7px;
  color: #cfe6f5;
  background: rgba(56, 213, 156, .07);
  font-size: 12px;
  line-height: 1.35;
}

.device-report.warning {
  color: #ffd6d9;
  background: rgba(255, 91, 104, .08);
}

@keyframes pointPulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(255, 91, 104, .12), 0 4px 14px rgba(0, 0, 0, .28); }
  50% { box-shadow: 0 0 0 7px rgba(255, 91, 104, .04), 0 6px 16px rgba(0, 0, 0, .32); }
}

@keyframes idleSpin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1280px) {
  .screen-grid {
    grid-template-columns: minmax(230px, 23fr) minmax(520px, 54fr) minmax(230px, 23fr);
    padding: 8px 10px 10px;
  }

  .screen-panel,
  .selected-detail {
    padding: 11px;
  }

  .today-card {
    min-height: 78px;
    padding: 10px;
  }

  .today-card strong {
    font-size: 24px;
  }

  .analytics-grid {
    gap: 8px;
  }
}
</style>
