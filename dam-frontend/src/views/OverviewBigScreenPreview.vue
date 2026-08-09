<template>
  <main class="bigscreen-page">
    <div class="ambient-grid"></div>

    <header class="screen-header">
      <div class="brand-block">
        <span class="brand-mark">BOX</span>
        <div>
          <span class="eyebrow">DAM SAFETY COMMAND CENTER</span>
          <strong>大坝智能安防平台</strong>
        </div>
      </div>

      <div class="screen-title">
        <span>DATENGXIA HYDROPOWER STATION</span>
        <h1>大藤峡安防态势总览</h1>
      </div>

      <div class="clock-block">
        <span>{{ currentDate }} · {{ currentWeek }}</span>
        <strong>{{ currentTime }}</strong>
        <em><i></i>{{ loading ? '数据同步中' : '数据实时接入' }}</em>
      </div>
    </header>

    <section class="screen-grid">
      <aside class="left-column">
        <section class="screen-panel overview-panel">
          <div class="panel-heading">
            <div>
              <span>01 / OVERVIEW</span>
              <h2>今日态势</h2>
            </div>
            <b>LIVE</b>
          </div>
          <div class="metric-grid">
            <div
              v-for="metric in overviewMetrics"
              :key="metric.key"
              class="metric-item"
              :class="metric.tone"
            >
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <em v-if="metric.trend">
                较昨日
                <i :class="metric.trend.tone">{{ metric.trend.icon }} {{ metric.trend.text }}</i>
              </em>
              <em v-else>{{ metric.note }}</em>
            </div>
          </div>
        </section>

        <section class="screen-panel risk-panel">
          <div class="panel-heading compact">
            <div>
              <span>02 / RISK DISTRIBUTION</span>
              <h2>风险分布</h2>
            </div>
            <span class="panel-note">今日 / 昨日</span>
          </div>
          <div class="risk-total">
            <div>
              <span>今日综合风险</span>
              <strong>{{ formatNumber(todayRiskTotal) }}</strong>
              <em>
                较昨日
                <i :class="riskComparison.tone">{{ riskComparison.icon }} {{ riskComparison.text }}</i>
              </em>
            </div>
            <div class="risk-orbit">
              <span>高风险</span>
              <strong>{{ formatNumber(todayHighRisk) }}</strong>
            </div>
          </div>
          <div class="risk-bars">
            <div v-for="row in riskRows" :key="row.key" class="risk-bar-row">
              <span>{{ row.label }}</span>
              <div>
                <i :class="row.key" :style="{ width: `${row.currentWidth}%` }"></i>
                <b :style="{ width: `${row.previousWidth}%` }"></b>
              </div>
              <em>{{ formatNumber(row.current) }} / {{ formatNumber(row.previous) }}</em>
            </div>
            <div class="risk-legend">
              <span><i class="legend-today"></i>今日</span>
              <span><i class="legend-yesterday"></i>昨日</span>
            </div>
          </div>
        </section>

        <section class="screen-panel trend-panel">
          <div class="panel-heading compact">
            <div>
              <span>03 / INCIDENT TREND</span>
              <h2>闯入趋势</h2>
            </div>
            <span class="panel-note">今日 · 按小时</span>
          </div>
          <div class="trend-legend">
            <span><i class="person-line"></i>人员</span>
            <span><i class="boat-line"></i>船只</span>
          </div>
          <svg class="mini-trend" viewBox="0 0 520 150" preserveAspectRatio="none" aria-label="今日闯入趋势">
            <line v-for="line in [30, 70, 110]" :key="line" x1="0" :y1="line" x2="520" :y2="line"></line>
            <polyline class="person-path" :points="trendSeries.person"></polyline>
            <polyline class="boat-path" :points="trendSeries.boat"></polyline>
          </svg>
          <div class="trend-labels">
            <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
          </div>
        </section>
      </aside>

      <main class="center-column">
        <section class="selected-banner" :class="selectedGroup.type">
          <div>
            <span>当前监测区域 / SELECTED MONITORING ZONE</span>
            <strong>{{ selectedGroup.label }} · {{ selectedGroup.typeLabel }}</strong>
          </div>
          <div class="selected-summary">
            <span>{{ selectedData.primary }}</span>
            <strong>{{ formatNumber(selectedData.value) }}<small>{{ selectedData.unit }}</small></strong>
            <em>{{ selectedData.status }}</em>
          </div>
        </section>

        <section class="map-panel">
          <div class="map-topline">
            <span>REAL-TIME SATELLITE ZONE MAP</span>
            <span>点击点位查看区域数据</span>
          </div>
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
              <img class="satellite-image" src="/dammap.png" alt="大藤峡水电站卫星地图" />
              <div class="map-shade"></div>
              <svg class="map-overlay" viewBox="0 0 1000 430" preserveAspectRatio="none" aria-label="大藤峡摄像头区域地图">
                <path
                  v-if="selectedRegion"
                  class="selected-region"
                  :class="selectedGroup.type"
                  :d="selectedRegion.path"
                />
                <g
                  v-for="point in cameraPoints"
                  :key="point.no"
                  class="camera-hotspot"
                  :class="{ active: point.regionKey === selectedGroup.key }"
                  @pointerdown.stop
                  @click.stop="handlePointClick(point.regionKey)"
                >
                  <circle class="hotspot-hit" :cx="point.x" :cy="point.y" r="9"></circle>
                  <circle class="hotspot-ring" :cx="point.x" :cy="point.y" r="7"></circle>
                  <circle class="hotspot-core" :cx="point.x" :cy="point.y" r="1.4"></circle>
                  <title>{{ point.no }}号 / {{ point.typeLabel }}</title>
                </g>
                <g v-for="point in pendingPoints" :key="point.id" class="pending-hotspot" @pointerdown.stop>
                  <circle class="pending-hit" :cx="point.x" :cy="point.y" r="8"></circle>
                  <circle class="pending-ring" :cx="point.x" :cy="point.y" r="6"></circle>
                  <title>待建中</title>
                </g>
              </svg>
              <div class="map-scan"></div>
            </div>
          </div>
        </section>

        <section class="selected-detail">
          <div class="detail-heading">
            <div>
              <span>SELECTED ZONE DETAIL</span>
              <h2>{{ selectedGroup.label }}数据概况</h2>
            </div>
            <div class="detail-state"><i></i>{{ selectedData.status }}</div>
          </div>
          <div class="detail-grid">
            <div class="detail-stat">
              <span>今日事件</span>
              <strong>{{ formatNumber(selectedData.recognized) }}</strong>
              <em>{{ selectedGroup.type === 'personForbidden' ? '人员事件' : '船只事件' }}</em>
            </div>
            <div class="detail-stat">
              <span>未处理事件</span>
              <strong>{{ formatNumber(selectedData.unhandled) }}</strong>
              <em>当前累计</em>
            </div>
            <div class="detail-stat">
              <span>最近事件</span>
              <strong class="time-value">{{ selectedData.lastTime }}</strong>
              <em>已记录</em>
            </div>
            <div class="detail-chart">
              <div class="chart-title">今日按小时事件变化</div>
              <svg viewBox="0 0 360 78" preserveAspectRatio="none">
                <polyline :points="selectedData.chart"></polyline>
              </svg>
            </div>
          </div>
        </section>
      </main>

      <aside class="right-column">
        <section class="screen-panel clock-panel">
          <div class="panel-heading compact">
            <div>
              <span>04 / SYSTEM TIME</span>
              <h2>实时状态</h2>
            </div>
            <b class="online-badge"><i></i>{{ loading ? 'SYNCING' : 'ONLINE' }}</b>
          </div>
          <div class="large-clock">{{ currentTime }}</div>
          <div class="clock-meta"><span>{{ currentDate }}</span><span>{{ currentWeek }}</span><span>30s 自动刷新</span></div>
        </section>

        <section class="screen-panel alerts-panel">
          <div class="panel-heading compact">
            <div>
              <span>05 / RECENT ALERTS</span>
              <h2>近期告警</h2>
            </div>
            <span class="count-badge">{{ formatNumber(unhandledCount) }} 未处理</span>
          </div>
          <div v-if="priorityAlert" class="priority-alert">
            <div class="alert-pin"></div>
            <div>
              <span>最高优先级 · 未处理</span>
              <strong>{{ alertTitle(priorityAlert) }}</strong>
              <em>{{ formatAlertTime(priorityAlert.started_at) }} · {{ riskLabel(priorityAlert) }}</em>
            </div>
          </div>
          <div v-else class="empty-alert">
            <span class="empty-mark">—</span>
            <div>
              <strong>当前无未处理告警</strong>
              <em>系统将持续接收安全事件</em>
            </div>
          </div>
          <div class="alert-list">
            <div v-if="recentAlerts.length === 0" class="empty-list">暂无告警记录</div>
            <div v-for="alert in recentAlerts" :key="alert.id" class="alert-item">
              <span class="alert-time">{{ formatAlertTime(alert.started_at) }}</span>
              <i :class="riskClass(alert)"></i>
              <div>
                <strong>{{ alertTitle(alert) }}</strong>
                <small>{{ alertZone(alert) }}</small>
              </div>
              <b>{{ statusLabel(alert) }}</b>
            </div>
          </div>
        </section>

        <section class="screen-panel device-panel">
          <div class="panel-heading compact">
            <div>
              <span>06 / DEVICE STATUS</span>
              <h2>设备情况</h2>
            </div>
            <span class="panel-note">在线 {{ deviceOnline }} / {{ deviceTotal }}</span>
          </div>
          <div class="device-summary">
            <div class="device-donut" :style="deviceDonutStyle">
              <strong>{{ deviceRate }}<small>%</small></strong>
              <span>在线率</span>
            </div>
            <div v-if="deviceRows.length" class="device-list">
              <div v-for="device in deviceRows" :key="device.key">
                <span><i class="online-dot" :class="{ offline: device.status !== 'online' }"></i>{{ device.label }}</span>
                <b :class="{ offline: device.status !== 'online' }">{{ device.online }} / {{ device.total }}</b>
              </div>
            </div>
            <div v-else class="device-empty">暂无设备状态数据</div>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getUnifiedSafetyEventStatistics, getUnifiedSafetyEvents } from '@/api/integration'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList } from '@/api/camera'

const cameraPoints = [
  { no: 1, x: 206, y: 178, typeLabel: '禁船区', regionKey: 'boat-1' },
  { no: 3, x: 445, y: 286, typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 4, x: 499, y: 167, typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 5, x: 520, y: 167, typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 6, x: 685, y: 215, typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 7, x: 704, y: 215, typeLabel: '禁船区', regionKey: 'boat-7' },
  { no: 8, x: 595, y: 290, typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 9, x: 931, y: 121, typeLabel: '人员禁入区', regionKey: 'person-9' },
]

const pendingPoints = [
  { id: 'pending-1', x: 206, y: 192 },
  { id: 'pending-2', x: 126, y: 120 },
  { id: 'pending-3', x: 88, y: 143 },
  { id: 'pending-4', x: 73, y: 132 },
  { id: 'pending-5', x: 77, y: 107 },
]

const regions = {
  'boat-1': { path: 'M400 145 L397 303 L386 289 L375 289 L362 283 L333 302 L295 285 L256 293 L240 303 L229 303 L211 307 L179 299 L194 187 L225 201 L261 195 L293 203 L328 185 L337 175 L329 172 L330 161 L366 162 L365 150 L384 145 Z' },
  'boat-34568': { path: 'M415 160 L459 160 L544 188 L562 197 L609 207 L646 208 L679 196 L693 249 L653 268 L612 278 L583 280 L567 289 L557 285 L548 291 L497 279 L459 287 L417 281 Z' },
  'boat-7': { path: 'M686 195 L747 172 L843 167 L850 217 L746 231 L723 243 L711 243 L697 249 Z' },
  'person-9': { path: 'M998 213 L904 214 L904 227 L998 227 Z' },
}

const regionGroups = [
  { key: 'boat-1', label: '1号', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-34568', label: '3/4/5/6/8号', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-7', label: '7号', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'person-9', label: '9号', type: 'personForbidden', typeLabel: '人员禁入区', category: 'PERSON_SAFETY' },
]

const selectedKey = ref('person-9')
const currentDate = ref('--')
const currentTime = ref('--:--:--')
const currentWeek = ref('--')
const loading = ref(false)
const eventStats = ref({})
const events = ref([])
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const mapBoardRef = ref(null)
const mapBaseSize = ref({ width: 0, height: 0 })
const mapScale = ref(1)
const mapOffset = ref({ x: 0, y: 0 })

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
let mapResizeObserver

const weekLabels = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
const deviceNames = {
  temp_humidity: '温湿度传感器',
  wind: '风速风向传感器',
  rain: '雨量计',
  vibration: '振动传感器',
  agx: '边缘计算盒',
  camera: '摄像头',
}

const selectedGroup = computed(() => regionGroups.find((group) => group.key === selectedKey.value) || regionGroups[0])
const selectedRegion = computed(() => regions[selectedGroup.value.key])
const selectedCategory = computed(() => selectedGroup.value.category)
const mapSceneStyle = computed(() => ({
  width: `${mapBaseSize.value.width}px`,
  height: `${mapBaseSize.value.height}px`,
  transform: `translate3d(-50%, 0, 0) translate3d(${mapOffset.value.x}px, ${mapOffset.value.y}px, 0) scale(${mapScale.value})`,
}))
const unhandledCount = computed(() => Number(eventStats.value.unhandled ?? events.value.filter((event) => !isHandled(event)).length))
const todayEvents = computed(() => eventsForDay(0))
const yesterdayEvents = computed(() => eventsForDay(-1))
const todayRiskTotal = computed(() => todayEvents.value.length)
const yesterdayRiskTotal = computed(() => yesterdayEvents.value.length)
const todayHighRisk = computed(() => todayEvents.value.filter((event) => riskValue(event) >= 3).length)

const overviewMetrics = computed(() => [
  {
    key: 'person',
    label: '人员闯入',
    value: formatNumber(categoryEvents('PERSON_SAFETY', 0).length),
    tone: 'danger',
    trend: compareValues(categoryEvents('PERSON_SAFETY', 0).length, categoryEvents('PERSON_SAFETY', -1).length),
  },
  {
    key: 'boat',
    label: '船只闯入',
    value: formatNumber(categoryEvents('ILLEGAL_FISHING', 0).length),
    tone: 'warning',
    trend: compareValues(categoryEvents('ILLEGAL_FISHING', 0).length, categoryEvents('ILLEGAL_FISHING', -1).length),
  },
  {
    key: 'unhandled',
    label: '未处理告警',
    value: formatNumber(unhandledCount.value),
    tone: 'cyan',
    note: unhandledCount.value ? '当前需关注' : '当前无未处理',
  },
  {
    key: 'devices',
    label: '在线设备',
    value: `${deviceOnline.value}`,
    tone: 'green',
    note: `共 ${deviceTotal.value} 台`,
  },
])

const riskComparison = computed(() => compareValues(todayRiskTotal.value, yesterdayRiskTotal.value))
const riskRows = computed(() => {
  const rows = [
    { key: 'person', label: '人员风险', current: categoryEvents('PERSON_SAFETY', 0).length, previous: categoryEvents('PERSON_SAFETY', -1).length },
    { key: 'boat', label: '船只风险', current: categoryEvents('ILLEGAL_FISHING', 0).length, previous: categoryEvents('ILLEGAL_FISHING', -1).length },
  ]
  return rows.map((row) => {
    const base = Math.max(row.current + row.previous, 1)
    return { ...row, currentWidth: Math.round((row.current / base) * 100), previousWidth: Math.round((row.previous / base) * 100) }
  })
})

const trendSeries = computed(() => ({
  person: buildPolyline(hourBuckets('PERSON_SAFETY')),
  boat: buildPolyline(hourBuckets('ILLEGAL_FISHING')),
}))

const selectedData = computed(() => {
  const items = categoryEvents(selectedCategory.value, 0)
  const unhandled = items.filter((event) => !isHandled(event)).length
  const latest = items[0]
  return {
    primary: selectedCategory.value === 'PERSON_SAFETY' ? '今日人员事件' : '今日船只事件',
    value: items.length,
    unit: '次',
    status: unhandled ? `${unhandled} 项待处置` : '区域稳定',
    recognized: items.length,
    unhandled,
    lastTime: latest ? formatAlertTime(latest.started_at) : '--:--:--',
    chart: buildPolyline(hourBuckets(selectedCategory.value), 360, 78),
  }
})

const priorityAlert = computed(() => events.value
  .filter((event) => !isHandled(event))
  .slice()
  .sort((a, b) => riskValue(b) - riskValue(a) || eventTimestamp(b) - eventTimestamp(a))[0] || null)

const recentAlerts = computed(() => {
  const priorityId = priorityAlert.value?.id
  const filtered = events.value.filter((event) => event.id !== priorityId)
  return filtered.slice(0, priorityId ? 3 : 4)
})

const deviceRows = computed(() => {
  const rows = Object.entries(deviceStatus.value || {}).map(([key, item]) => {
    const total = Number(item?.total || 1)
    const online = Number(item?.online_count ?? (item?.status === 'online' ? total : 0))
    return {
      key,
      label: deviceNames[key] || key,
      total,
      online,
      status: item?.status === 'online' && online > 0 ? 'online' : 'offline',
    }
  })
  if (cameraSummary.value.total > 0 || Object.prototype.hasOwnProperty.call(deviceStatus.value, 'camera')) {
    const camera = deviceSummaryRow('camera', cameraSummary.value.online, cameraSummary.value.total)
    const index = rows.findIndex((row) => row.key === 'camera')
    if (index >= 0) rows.splice(index, 1, camera)
    else rows.push(camera)
  }
  return rows
})

const deviceOnline = computed(() => deviceRows.value.reduce((sum, item) => sum + item.online, 0))
const deviceTotal = computed(() => deviceRows.value.reduce((sum, item) => sum + item.total, 0))
const deviceRate = computed(() => deviceTotal.value ? Math.round((deviceOnline.value / deviceTotal.value) * 100) : 0)
const deviceDonutStyle = computed(() => ({
  background: `conic-gradient(#59edc8 ${deviceRate.value * 3.6}deg, rgba(82, 231, 196, 0.12) 0deg)`,
}))

function deviceSummaryRow(key, online, total) {
  return {
    key,
    label: deviceNames[key] || key,
    online: Number(online || 0),
    total: Number(total || 0),
    status: Number(online || 0) > 0 && Number(online || 0) >= Number(total || 0) ? 'online' : 'offline',
  }
}

function formatNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? String(Math.max(0, number)).padStart(2, '0') : '--'
}

function eventTimestamp(event) {
  const time = Date.parse(event?.started_at || '')
  return Number.isFinite(time) ? time : 0
}

function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function eventDateKey(event) {
  const time = eventTimestamp(event)
  return time ? dateKey(new Date(time)) : ''
}

function eventsForDay(offset) {
  const target = new Date()
  target.setHours(0, 0, 0, 0)
  target.setDate(target.getDate() + offset)
  const key = dateKey(target)
  return events.value.filter((event) => eventDateKey(event) === key)
}

function categoryEvents(category, offset) {
  return eventsForDay(offset).filter((event) => event.event_category === category)
}

function riskValue(event) {
  return ({ LOW: 1, MEDIUM: 2, HIGH: 3 })[event?.max_risk_level || event?.risk_level] || 0
}

function isHandled(event) {
  return event?.state === 'RESOLVED' || ['COMPLETED', 'FALSE_ALARM'].includes(event?.status)
}

function compareValues(current, previous) {
  if (current === previous) return { icon: '—', text: '持平', tone: 'flat' }
  if (!previous && current > 0) return { icon: '↑', text: '新增', tone: 'up' }
  const percent = Math.round(Math.abs((current - previous) / previous) * 100)
  return current > previous
    ? { icon: '↑', text: `${percent}%`, tone: 'up' }
    : { icon: '↓', text: `${percent}%`, tone: 'down' }
}

function hourBuckets(category) {
  const values = Array.from({ length: 24 }, () => 0)
  categoryEvents(category, 0).forEach((event) => {
    const time = eventTimestamp(event)
    if (time) values[new Date(time).getHours()] += 1
  })
  return values
}

function buildPolyline(values, width = 520, height = 150) {
  const max = Math.max(...values, 1)
  const step = width / Math.max(values.length - 1, 1)
  return values.map((value, index) => {
    const x = Math.round(index * step)
    const y = Math.round(height - 10 - ((value / max) * (height - 24)))
    return `${x},${y}`
  }).join(' ')
}

function riskLabel(event) {
  return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[event?.max_risk_level || event?.risk_level] || '风险待确认'
}

function riskClass(event) {
  return ({ HIGH: 'high', MEDIUM: 'medium', LOW: 'low' })[event?.max_risk_level || event?.risk_level] || 'low'
}

function statusLabel(event) {
  if (isHandled(event)) return '已处理'
  if (event?.status === 'PROCESSING') return '处理中'
  return '未处理'
}

function alertTitle(event) {
  return event?.event_name || event?.summary || (event?.event_category === 'PERSON_SAFETY' ? '人员安全事件' : '船只安全事件')
}

function alertZone(event) {
  return event?.event_category === 'PERSON_SAFETY' ? '9号人员禁入区' : '禁船区 · 共用船只统计'
}

function formatAlertTime(value) {
  if (!value) return '--:--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  const pad = (number) => String(number).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
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

function updateMapBaseSize() {
  const board = mapBoardRef.value
  if (!board) return
  const rect = board.getBoundingClientRect()
  const fitScale = rect.width / 1916
  mapBaseSize.value = {
    width: Math.ceil(1916 * fitScale),
    height: Math.ceil(824 * fitScale),
  }
  clampMapOffset()
}

function handleMapWheel(event) {
  if (!mapBaseSize.value.width) return
  const board = mapBoardRef.value
  const rect = board.getBoundingClientRect()
  const nextScale = Math.max(1, Math.min(4, mapScale.value * (event.deltaY > 0 ? 0.9 : 1.1)))
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
    x: mapDragState.startOffsetX + deltaX / mapScale.value,
    y: mapDragState.startOffsetY + deltaY / mapScale.value,
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

function handlePointClick(key) {
  if (mapDragState.moved) return
  selectRegion(key)
}

function selectRegion(key) {
  selectedKey.value = key
}

function updateClock() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  currentDate.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  currentTime.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  currentWeek.value = weekLabels[now.getDay()]
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
  loading.value = false
}

onMounted(() => {
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  updateMapBaseSize()
  if (window.ResizeObserver && mapBoardRef.value) {
    mapResizeObserver = new ResizeObserver(updateMapBaseSize)
    mapResizeObserver.observe(mapBoardRef.value)
  }
  fetchData()
  refreshTimer = window.setInterval(fetchData, 30000)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  window.clearInterval(refreshTimer)
  mapResizeObserver?.disconnect()
})
</script>

<style scoped>
.bigscreen-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  color: #dcefff;
  background:
    radial-gradient(circle at 50% 45%, rgba(0, 139, 205, 0.13), transparent 34%),
    linear-gradient(135deg, #020b16 0%, #061a31 48%, #03101f 100%);
  font-family: "DIN Alternate", "Bahnschrift", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.ambient-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.22;
  background:
    linear-gradient(rgba(52, 183, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(52, 183, 255, 0.06) 1px, transparent 1px);
  background-size: 42px 42px;
}

.screen-header,
.screen-grid {
  position: relative;
  z-index: 1;
}

.screen-header {
  height: 72px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(52, 191, 255, 0.28);
  background: linear-gradient(180deg, rgba(10, 39, 69, 0.92), rgba(5, 20, 39, 0.7));
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
}

.brand-block,
.clock-block {
  display: flex;
  align-items: center;
}

.brand-block {
  gap: 10px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border: 1px solid rgba(66, 227, 255, 0.66);
  display: grid;
  place-items: center;
  color: #51e8ff;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 1px;
  box-shadow: inset 0 0 18px rgba(0, 216, 255, 0.14), 0 0 15px rgba(0, 216, 255, 0.18);
}

.eyebrow,
.screen-title span,
.panel-heading span,
.map-topline,
.detail-heading span {
  color: rgba(126, 203, 247, 0.62);
  font-size: 9px;
  letter-spacing: 0.8px;
}

.brand-block strong {
  display: block;
  margin-top: 3px;
  color: #eef9ff;
  font-size: 16px;
}

.screen-title {
  text-align: center;
}

.screen-title h1 {
  margin: 3px 0 0;
  color: #f3fbff;
  font-size: 26px;
  letter-spacing: 4px;
  text-shadow: 0 0 18px rgba(66, 218, 255, 0.46);
}

.clock-block {
  justify-content: flex-end;
  gap: 10px;
}

.clock-block > span {
  color: rgba(174, 215, 245, 0.76);
  font-size: 11px;
}

.clock-block strong {
  color: #f6fdff;
  font-size: 21px;
  letter-spacing: 1px;
}

.clock-block em {
  color: #59edc8;
  font-size: 10px;
  font-style: normal;
}

.clock-block em i,
.online-badge i,
.detail-state i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 5px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 9px currentColor;
}

.screen-grid {
  height: calc(100% - 72px);
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(230px, 0.24fr) minmax(520px, 0.52fr) minmax(230px, 0.24fr);
  gap: 12px;
  padding: 12px 16px 14px;
}

.left-column,
.right-column,
.center-column {
  min-height: 0;
  display: grid;
  gap: 10px;
}

.left-column {
  grid-template-rows: auto auto minmax(160px, 1fr);
}

.center-column {
  grid-template-rows: 58px auto minmax(174px, 1fr);
}

.right-column {
  grid-template-rows: auto minmax(238px, 1fr) auto;
}

.screen-panel,
.selected-banner,
.map-panel,
.selected-detail {
  min-width: 0;
  border: 1px solid rgba(50, 181, 255, 0.22);
  background: linear-gradient(145deg, rgba(8, 38, 68, 0.78), rgba(3, 19, 38, 0.72));
  box-shadow: inset 0 0 24px rgba(0, 190, 255, 0.035), 0 12px 26px rgba(0, 0, 0, 0.18);
}

.screen-panel {
  padding: 12px;
}

.panel-heading,
.detail-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.panel-heading h2,
.detail-heading h2 {
  margin: 3px 0 0;
  color: #effaff;
  font-size: 18px;
}

.panel-heading b {
  color: #54e6c0;
  font-size: 10px;
  letter-spacing: 1px;
}

.panel-heading.compact {
  align-items: center;
}

.panel-note {
  color: rgba(174, 215, 245, 0.64);
  font-size: 10px;
}

.metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 11px;
}

.metric-item {
  position: relative;
  min-height: 70px;
  padding: 9px 10px;
  border-left: 2px solid currentColor;
  background: rgba(1, 13, 27, 0.38);
}

.metric-item > span,
.metric-item > em,
.risk-total span,
.risk-total em,
.risk-bar-row > span,
.risk-bar-row > em {
  display: block;
  color: rgba(174, 215, 245, 0.72);
  font-size: 10px;
  font-style: normal;
}

.metric-item strong {
  display: block;
  margin-top: 3px;
  color: #f7fdff;
  font-size: 26px;
  line-height: 1;
}

.metric-item em {
  margin-top: 6px;
}

.metric-item em i,
.risk-total em i {
  font-style: normal;
}

.metric-item em i.up,
.risk-total em i.up {
  color: #ff6f76;
}

.metric-item em i.down,
.risk-total em i.down {
  color: #59edc8;
}

.metric-item em i.flat,
.risk-total em i.flat {
  color: rgba(174, 215, 245, 0.72);
}

.metric-item.danger { color: #ff6f76; }
.metric-item.warning { color: #ffc65c; }
.metric-item.cyan { color: #50e5ff; }
.metric-item.green { color: #55e4be; }

.risk-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 13px 2px 16px;
}

.risk-total strong {
  display: block;
  margin-top: 3px;
  color: #f8fdff;
  font-size: 30px;
}

.risk-orbit {
  width: 58px;
  height: 58px;
  border: 1px solid rgba(255, 102, 111, 0.55);
  border-radius: 50%;
  display: grid;
  place-content: center;
  text-align: center;
  box-shadow: 0 0 18px rgba(255, 102, 111, 0.16), inset 0 0 15px rgba(255, 102, 111, 0.1);
}

.risk-orbit span {
  font-size: 9px;
}

.risk-orbit strong {
  margin: 0;
  color: #ff7e83;
  font-size: 20px;
}

.risk-bars {
  display: grid;
  gap: 11px;
}

.risk-bar-row {
  display: grid;
  grid-template-columns: 55px 1fr 38px;
  align-items: center;
  gap: 7px;
}

.risk-bar-row > div {
  display: flex;
  height: 7px;
  overflow: hidden;
  background: rgba(174, 215, 245, 0.11);
}

.risk-bar-row > div i,
.risk-bar-row > div b {
  display: block;
}

.risk-bar-row > div i.person { background: #ff6f76; }
.risk-bar-row > div i.boat { background: #ffc65c; }
.risk-bar-row > div b { background: rgba(174, 215, 245, 0.22); }

.risk-bar-row > em {
  text-align: right;
}

.risk-legend,
.trend-legend,
.trend-labels,
.clock-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.risk-legend {
  justify-content: flex-end;
  gap: 14px;
  color: rgba(174, 215, 245, 0.62);
  font-size: 9px;
}

.risk-legend i,
.trend-legend i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 5px;
  background: #ff6f76;
}

.risk-legend .legend-yesterday {
  background: rgba(174, 215, 245, 0.3);
}

.trend-legend {
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
  color: rgba(174, 215, 245, 0.66);
  font-size: 9px;
}

.trend-legend i {
  width: 16px;
  height: 2px;
  vertical-align: middle;
}

.trend-legend .boat-line {
  background: #ffc65c;
}

.mini-trend {
  width: 100%;
  height: calc(100% - 63px);
  min-height: 92px;
  margin-top: 5px;
  overflow: visible;
}

.mini-trend line {
  stroke: rgba(126, 203, 247, 0.12);
  stroke-width: 1;
}

.mini-trend polyline,
.detail-chart polyline {
  fill: none;
  stroke-width: 2.4;
  vector-effect: non-scaling-stroke;
}

.mini-trend .person-path { stroke: #ff7180; }
.mini-trend .boat-path { stroke: #ffc65c; }

.trend-labels {
  color: rgba(174, 215, 245, 0.54);
  font-size: 9px;
}

.selected-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-left: 3px solid #ffc65c;
}

.selected-banner.personForbidden {
  border-left-color: #ff7180;
}

.selected-banner > div > span {
  display: block;
  color: rgba(126, 203, 247, 0.62);
  font-size: 9px;
}

.selected-banner > div > strong {
  display: block;
  margin-top: 3px;
  color: #f5fdff;
  font-size: 19px;
}

.selected-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-summary > span {
  color: rgba(174, 215, 245, 0.68);
  font-size: 10px;
}

.selected-summary > strong {
  color: #ffd260;
  font-size: 26px;
}

.selected-banner.personForbidden .selected-summary > strong {
  color: #ff7a84;
}

.selected-summary small {
  margin-left: 3px;
  color: rgba(174, 215, 245, 0.68);
  font-size: 11px;
}

.selected-summary em {
  color: #59edc8;
  font-size: 10px;
  font-style: normal;
}

.map-panel {
  min-height: 0;
  display: grid;
  grid-template-rows: 25px auto;
  overflow: hidden;
}

.map-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 11px;
  background: rgba(1, 12, 26, 0.42);
}

.map-board {
  position: relative;
  width: 100%;
  height: auto;
  aspect-ratio: 1916 / 824;
  overflow: hidden;
  background: #061421;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.map-board:active {
  cursor: grabbing;
}

.map-scene {
  position: absolute;
  top: 0;
  left: 50%;
  transform-origin: center center;
  will-change: transform;
}

.satellite-image,
.map-overlay,
.map-shade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.satellite-image {
  object-fit: fill;
  filter: saturate(1.1) contrast(1.08) brightness(0.76);
  pointer-events: none;
  user-select: none;
}

.map-shade {
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 48%, transparent 35%, rgba(2, 10, 22, 0.58) 100%),
    linear-gradient(180deg, rgba(0, 17, 35, 0.18), rgba(0, 10, 22, 0.28));
}

.map-overlay {
  z-index: 2;
}

.selected-region {
  fill: rgba(255, 198, 92, 0.045);
  stroke: rgba(255, 198, 92, 0.72);
  stroke-width: 1.1;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(255, 198, 92, 0.28));
}

.selected-region.personForbidden {
  fill: rgba(255, 113, 128, 0.045);
  stroke: rgba(255, 113, 128, 0.76);
  filter: drop-shadow(0 0 5px rgba(255, 113, 128, 0.3));
}

.camera-hotspot {
  cursor: pointer;
}

.hotspot-hit {
  fill: rgba(255, 255, 255, 0.005);
  stroke: transparent;
}

.hotspot-ring,
.hotspot-core {
  fill: transparent;
  stroke: transparent;
  opacity: 0;
  vector-effect: non-scaling-stroke;
}

.hotspot-ring {
  stroke-width: 1;
}

.hotspot-core {
  fill: #64efff;
}

.camera-hotspot:hover .hotspot-ring,
.camera-hotspot.active .hotspot-ring,
.camera-hotspot:hover .hotspot-core,
.camera-hotspot.active .hotspot-core {
  opacity: 1;
}

.camera-hotspot:hover .hotspot-ring,
.camera-hotspot.active .hotspot-ring {
  stroke: #64efff;
  filter: drop-shadow(0 0 5px rgba(100, 239, 255, 0.72));
}

.camera-hotspot.active .hotspot-ring {
  stroke-width: 1.5;
}

.pending-hotspot {
  cursor: help;
}

.pending-hit {
  fill: rgba(70, 143, 244, 0.005);
  stroke: transparent;
}

.pending-ring {
  fill: transparent;
  stroke: transparent;
  stroke-width: 1;
  opacity: 0;
  vector-effect: non-scaling-stroke;
}

.pending-hotspot:hover .pending-ring {
  opacity: 1;
  stroke: rgba(117, 173, 255, 0.84);
  filter: drop-shadow(0 0 5px rgba(70, 143, 244, 0.65));
}

.map-scan {
  position: absolute;
  z-index: 3;
  inset: 0;
  height: 18%;
  pointer-events: none;
  background: linear-gradient(180deg, transparent, rgba(66, 228, 255, 0.14), transparent);
  animation: scan 5.5s linear infinite;
}

.selected-detail {
  padding: 12px 16px;
}

.detail-state {
  color: #59edc8;
  font-size: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 0.8fr 0.8fr 1.1fr 1.8fr;
  align-items: end;
  gap: 12px;
  margin-top: 10px;
}

.detail-stat {
  min-width: 0;
  padding-right: 12px;
  border-right: 1px solid rgba(126, 203, 247, 0.14);
}

.detail-stat span,
.detail-stat em {
  display: block;
  color: rgba(174, 215, 245, 0.64);
  font-size: 9px;
  font-style: normal;
}

.detail-stat strong {
  display: block;
  margin-top: 4px;
  color: #f5fdff;
  font-size: 22px;
}

.detail-stat .time-value {
  font-size: 17px;
}

.detail-stat em {
  margin-top: 3px;
}

.detail-chart {
  min-width: 0;
}

.chart-title {
  color: rgba(174, 215, 245, 0.64);
  font-size: 9px;
}

.detail-chart svg {
  width: 100%;
  height: 60px;
  margin-top: 3px;
}

.detail-chart polyline {
  stroke: #58e9ff;
}

.clock-panel {
  padding-bottom: 10px;
}

.online-badge {
  color: #59edc8;
  font-size: 9px;
  font-weight: 600;
}

.large-clock {
  margin-top: 10px;
  color: #f5fdff;
  font-size: 33px;
  letter-spacing: 2px;
}

.clock-meta {
  justify-content: flex-start;
  gap: 11px;
  margin-top: 5px;
  color: rgba(174, 215, 245, 0.66);
  font-size: 9px;
}

.count-badge {
  padding: 4px 6px;
  border: 1px solid rgba(255, 113, 128, 0.35);
  color: #ff8994;
  font-size: 9px;
}

.priority-alert,
.empty-alert {
  display: flex;
  gap: 9px;
  margin-top: 11px;
  padding: 9px;
  border-left: 2px solid #ff7180;
  background: rgba(255, 76, 91, 0.08);
}

.empty-alert {
  border-left-color: rgba(89, 237, 200, 0.7);
  background: rgba(89, 237, 200, 0.06);
}

.alert-pin {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  margin-top: 4px;
  border-radius: 50%;
  background: #ff7180;
  box-shadow: 0 0 10px #ff7180;
}

.empty-mark {
  color: #59edc8;
  font-size: 18px;
  line-height: 1;
}

.priority-alert span,
.priority-alert em,
.empty-alert em {
  display: block;
  color: rgba(255, 166, 175, 0.72);
  font-size: 9px;
  font-style: normal;
}

.empty-alert em {
  color: rgba(174, 215, 245, 0.62);
}

.priority-alert strong,
.empty-alert strong {
  display: block;
  margin: 3px 0;
  color: #fff3f4;
  font-size: 12px;
}

.empty-alert strong {
  color: #cffff0;
}

.alert-list {
  margin-top: 8px;
}

.alert-item {
  display: grid;
  grid-template-columns: 48px 5px 1fr auto;
  align-items: center;
  gap: 6px;
  min-height: 39px;
  border-bottom: 1px solid rgba(126, 203, 247, 0.1);
}

.alert-time,
.alert-item small,
.alert-item b {
  color: rgba(174, 215, 245, 0.6);
  font-size: 9px;
}

.alert-item i {
  width: 4px;
  height: 20px;
  background: #ff7180;
}

.alert-item i.medium { background: #ffc65c; }
.alert-item i.low { background: #59edc8; }

.alert-item strong {
  display: block;
  overflow: hidden;
  color: #e9f7ff;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-item small {
  display: block;
  margin-top: 2px;
}

.alert-item b {
  font-weight: 400;
  white-space: nowrap;
}

.empty-list,
.device-empty {
  padding: 16px 0;
  color: rgba(174, 215, 245, 0.56);
  font-size: 10px;
  text-align: center;
}

.device-summary {
  display: grid;
  grid-template-columns: 96px 1fr;
  align-items: center;
  gap: 11px;
  margin-top: 13px;
}

.device-donut {
  position: relative;
  width: 78px;
  height: 78px;
  border-radius: 50%;
  display: grid;
  place-content: center;
  text-align: center;
  box-shadow: 0 0 18px rgba(89, 237, 200, 0.14);
}

.device-donut::before {
  content: "";
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: #09233d;
}

.device-donut strong,
.device-donut span {
  position: relative;
  z-index: 1;
}

.device-donut strong {
  color: #f4ffff;
  font-size: 20px;
}

.device-donut small {
  font-size: 10px;
}

.device-donut span {
  color: rgba(174, 215, 245, 0.66);
  font-size: 9px;
}

.device-list {
  display: grid;
  gap: 8px;
}

.device-list div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgba(225, 244, 255, 0.84);
  font-size: 10px;
}

.device-list b {
  color: #59edc8;
  font-size: 10px;
  font-weight: 600;
}

.device-list b.offline,
.online-dot.offline {
  color: #ff7180;
  background: #ff7180;
  box-shadow: 0 0 8px #ff7180;
}

.online-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  background: #59edc8;
  box-shadow: 0 0 8px #59edc8;
}

@keyframes scan {
  0% { transform: translateY(-120%); opacity: 0; }
  18%, 80% { opacity: 1; }
  100% { transform: translateY(620%); opacity: 0; }
}

@media (max-width: 1280px) {
  .screen-header {
    padding: 0 16px;
  }

  .screen-title h1 {
    font-size: 22px;
  }

  .screen-grid {
    gap: 8px;
    padding: 8px 10px 10px;
  }

  .screen-panel,
  .selected-detail {
    padding: 10px;
  }

  .metric-item strong {
    font-size: 23px;
  }

  .detail-grid {
    gap: 8px;
  }
}

@media (max-width: 980px) {
  .bigscreen-page {
    height: auto;
    min-height: 100%;
    overflow: auto;
  }

  .screen-header {
    height: auto;
    min-height: 76px;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px;
  }

  .screen-title {
    grid-column: 1 / -1;
    grid-row: 1;
  }

  .brand-block,
  .clock-block {
    grid-row: 2;
  }

  .clock-block {
    justify-content: flex-end;
  }

  .screen-grid {
    height: auto;
    grid-template-columns: 1fr;
  }

  .left-column,
  .right-column,
  .center-column {
    grid-template-rows: auto;
  }

  .center-column {
    order: -1;
    min-height: 740px;
  }
}
</style>
