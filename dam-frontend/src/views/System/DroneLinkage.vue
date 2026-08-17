<!-- 无人机设备（联动系统）- 直连 DJI 真实设备，对标广播设备页样式 -->
<template>
  <div class="linkage-drone-page">
    <header class="page-header">
      <div>
        <h2>无人机设备</h2>
        <p>展示 DJI 真实无人机与绑定机场，选择航线测试自动巡检；设备配置请在 DJI 控制台完成</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
    </header>

    <!-- 工具条 -->
    <section class="resource-control-card">
      <header class="tab-header">
        <h3>{{ isWaylineView ? '航线列表' : '无人机列表' }}</h3>
        <div v-if="!isWaylineView" class="tab-actions">
          <a class="console-entry" :href="djiConsoleUrl" target="_blank" rel="noopener">
            <el-icon><Promotion /></el-icon>
            <span>DJI 控制台</span>
          </a>
          <button type="button" class="toolbar-template-entry" @click="showWaylines">
            <el-icon><Tickets /></el-icon>
            <span>查看航线 {{ waylineFiles.length }}</span>
          </button>
          <el-select
            v-model="deviceFilters.status"
            class="status-filter-select"
            popper-class="drone-filter-popper"
            placeholder="设备状态"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
          </el-select>
        </div>
        <div v-else class="tab-actions">
          <button type="button" class="toolbar-return-entry" @click="showDevices">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回设备列表</span>
          </button>
          <el-button :icon="Refresh" :loading="waylineLoading" @click="loadWaylines">刷新航线</el-button>
        </div>
      </header>
    </section>

    <!-- 设备列表 -->
    <section v-if="!isWaylineView" class="resource-list-card" v-loading="deviceLoading">
      <div class="device-list" :class="{ 'is-empty': !filteredDevices.length }">
        <div v-if="filteredDevices.length" class="device-list-header-row">
          <div class="col-name">设备名称</div>
          <div class="col-desc">描述</div>
          <div class="col-dock">绑定机场</div>
          <div class="col-battery">电量(剩余飞行时间)</div>
          <div class="col-status">状态</div>
          <div class="col-actions">操作</div>
        </div>
        <article
          v-for="row in pagedDevices"
          :key="row.device_sn"
          class="device-row"
          :class="row.online ? 'is-online' : 'is-offline'"
        >
          <div class="col-name device-name-cell">
            <strong>{{ row.device_name }}</strong>
          </div>
          <div class="col-desc device-description">
            <span>{{ row.device_desc || row.device_model || '--' }}</span>
          </div>
          <div class="col-dock">
            <span>{{ row.dockName }}</span>
          </div>
          <div class="col-battery">
            <template v-if="row.battery != null && row.battery !== '--'">
              <span class="battery-num" :class="batteryClass(row.battery)">{{ row.battery }}%</span>
              <span class="battery-remain">{{ row.remain != null ? `${row.remain}min` : '--' }}</span>
            </template>
            <span v-else>--</span>
          </div>
          <div class="col-status">
            <span class="status-pill" :class="row.online ? 'is-online' : 'is-offline'">
              {{ row.online ? '在线' : '离线' }}
            </span>
          </div>
          <div class="col-actions list-actions">
            <el-button class="test-action" @click="openTestDialog(row)">测试</el-button>
          </div>
        </article>
        <div v-if="!filteredDevices.length" class="empty-list">
          <strong>{{ authError ? 'DJI 服务连接失败' : '暂无在线无人机' }}</strong>
          <span>{{ authError || '请先在 DJI 控制台绑定机场与无人机，再回到本页刷新' }}</span>
        </div>
      </div>
      <el-pagination
        v-if="filteredDevices.length"
        v-model:current-page="devicePage"
        class="list-pagination"
        :page-size="pageSize"
        :total="filteredDevices.length"
        layout="prev, pager, next"
      />
    </section>

    <!-- 航线视图 -->
    <section v-else class="resource-list-card" v-loading="waylineLoading">
      <div class="wayline-list" :class="{ 'is-empty': !waylineFiles.length }">
        <div v-if="waylineFiles.length" class="wayline-list-header-row">
          <div>航线名称</div>
          <div>文件类型</div>
          <div>更新时间</div>
          <div>操作</div>
        </div>
        <article v-for="w in waylineFiles" :key="w.id || w.wayline_id" class="wayline-row">
          <div class="wayline-name">
            <strong>{{ w.file_name || w.name || `航线-${w.id}` }}</strong>
          </div>
          <div class="wayline-type">
            <span>{{ w.wayline_type === 1 ? '航点' : w.wayline_type === 2 ? '建图航迹' : '--' }}</span>
          </div>
          <div class="wayline-time">{{ formatTime(w.update_time || w.create_time) }}</div>
          <div class="wayline-actions list-actions">
            <a class="edit-action-link" :href="djiConsoleUrl" target="_blank" rel="noopener">
              <el-button class="edit-action" size="small">到控制台管理</el-button>
            </a>
          </div>
        </article>
        <div v-if="!waylineFiles.length" class="empty-list">
          <strong>暂无航线文件</strong>
          <span>请在 DJI 控制台上传航线后刷新</span>
        </div>
      </div>
      <el-pagination
        v-if="waylineFiles.length > pageSize"
        v-model:current-page="waylinePage"
        class="list-pagination"
        :page-size="pageSize"
        :total="waylineFiles.length"
        layout="prev, pager, next"
      />
    </section>

    <!-- 测试弹窗 -->
    <el-dialog
      v-model="testDialogVisible"
      title="无人机测试 · 航线巡检"
      width="92%"
      top="3vh"
      class="drone-test-dialog"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="test-layout">
        <!-- 顶部工具条 -->
        <div class="test-toolbar">
          <div class="test-device">
            <strong>{{ testingDevice?.device_name || '--' }}</strong>
            <span>{{ testingDevice?.dockName || '--' }} · {{ wsOnlineText }}</span>
          </div>
          <div class="test-wayline">
            <span class="toolbar-label">选择航线</span>
            <el-select
              v-model="testWaylineId"
              placeholder="请选择航线"
              filterable
              clearable
              class="wayline-select"
              popper-class="drone-filter-popper"
            >
              <el-option
                v-for="w in waylineFiles"
                :key="w.id || w.wayline_id"
                :label="w.file_name || w.name"
                :value="w.id || w.wayline_id"
              />
            </el-select>
            <el-button
              class="test-start-btn"
              type="primary"
              :icon="VideoPlay"
              :disabled="!testWaylineId || testStarting || testing"
              @click="handleStartTest"
            >
              {{ testStarting ? '启动中...' : testing ? '巡检中' : '启动' }}
            </el-button>
            <el-button v-if="testing" :icon="Close" @click="handleStopTest">停止</el-button>
          </div>
        </div>

        <!-- 主体：左地图 右视频 -->
        <div class="test-body">
          <div class="test-map" ref="mapRef">
            <img src="/dam-map.png" alt="大藤峡地图" class="map-image" draggable="false" />
            <svg
              v-if="activeRoutePoints.length"
              class="route-layer"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <polyline class="route-line route-line-glow" :points="activeRoutePolyline" />
              <polyline class="route-line" :points="activeRoutePolyline" />
              <circle
                v-for="(pt, index) in activeRoutePoints"
                :key="`${activeRouteName}-${index}`"
                class="route-point"
                :cx="pt.x"
                :cy="pt.y"
                r="1.2"
              />
            </svg>
            <!-- 机场 P3 -->
            <div class="map-fixed-point" style="left: 94.9%; top: 24.9%;">
              <img src="/starting-point.png" alt="机场" class="fixed-point-icon" />
              <span class="fixed-point-label">机场</span>
            </div>
            <!-- 禁渔点 P1 -->
            <div class="map-fixed-point" style="left: 47.4%; top: 58.1%;">
              <img src="/waypoint.png" alt="禁渔点" class="fixed-point-icon" />
              <span class="fixed-point-label">禁渔点</span>
            </div>
            <!-- 禁涉水点 P2 -->
            <div class="map-fixed-point" style="left: 96.3%; top: 54.3%;">
              <img src="/waypoint.png" alt="禁涉水点" class="fixed-point-icon" />
              <span class="fixed-point-label">禁涉水点</span>
            </div>
            <!-- 无人机（默认在起始点） -->
            <div class="drone-marker" :style="droneOnMapStyle">
              <div class="marker-pulse"></div>
              <img src="/drone-icon.png" alt="无人机" class="marker-icon" />
            </div>
            <!-- 图注 -->
            <div class="map-legend">
              <span class="legend-item"><img src="/starting-point.png" class="legend-icon-img" />起始点</span>
              <span class="legend-item"><img src="/waypoint.png" class="legend-icon-img" />航点</span>
              <span class="legend-item"><img src="/drone-icon.png" class="legend-icon-img" />无人机</span>
              <span class="legend-item"><i class="legend-line"></i>航线</span>
            </div>
          </div>

          <div class="test-video">
            <div class="video-stage">
              <video v-if="isLive" ref="liveVideoRef" class="video-stream" autoplay muted playsinline></video>
              <div v-else class="video-placeholder">
                <el-icon :size="36"><VideoCamera /></el-icon>
                <strong>{{ liveLoading ? '连接视频流...' : videoError ? '画面未连接' : '实时画面' }}</strong>
                <span>{{ liveLoading ? '正在建立推流连接' : videoError ? '不影响航线模拟' : '启动航线后自动开启画面' }}</span>
              </div>
              <div class="scan-grid"></div>
            </div>
          </div>
        </div>

        <!-- 底部遥测 -->
        <div class="test-telemetry">
          <div class="telemetry-item">
            <span class="t-label">电量</span>
            <span class="t-value" :class="batteryTone">{{ osdData.batteryPct ?? '--' }}%</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">剩余飞行</span>
            <span class="t-value">{{ osdData.remainMin ?? '--' }}min</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">高度</span>
            <span class="t-value">{{ osdData.height ?? '--' }}m</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">水平速度</span>
            <span class="t-value">{{ osdData.speed ?? '--' }}m/s</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">离机场</span>
            <span class="t-value">{{ osdData.homeDist ?? '--' }}m</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">飞行模式</span>
            <span class="t-value mode" :class="osdData.modeTone">{{ osdData.modeText }}</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">GPS/RTK</span>
            <span class="t-value">{{ osdData.gps ?? '--' }}/{{ osdData.rtk ?? '--' }}</span>
          </div>
          <div class="telemetry-item">
            <span class="t-label">任务进度</span>
            <span class="t-value">{{ testProgress }}%</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, Close, Promotion, Refresh, Tickets, VideoCamera, VideoPlay,
} from '@element-plus/icons-vue'
import {
  createFlightTask,
  dijLogin,
  getBoundDevices,
  getCurrentWorkspace,
  getDroneDevices,
  getLiveCapacity,
  getWaylineFiles,
  startLiveStream,
  startSimulation,
  stopLiveStream,
  stopSimulation,
} from '@/api/drone'
import { parseFlightMode } from '@/utils/droneWs'

// ========== 配置 ==========
const DIJ_HOST = '127.0.0.1:6790'
const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'
// DJI 控制台地址（dij-frontend，端口 8081）
const djiConsoleUrl = computed(() => `http://${window.location.hostname || 'localhost'}:8081`)

// 模拟航线（用于地图动画；真实航线以 DJI wayline 为准）
const ROUTES = {
  '禁渔航线': {
    name: '禁渔航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 47.4, y: 58.1, label: '禁渔点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ],
  },
  '禁涉水航线': {
    name: '禁涉水航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 96.3, y: 54.3, label: '禁涉水点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ],
  },
}
// ========== 视图状态 ==========
const viewMode = ref('devices')
const loading = ref(false)
const deviceLoading = ref(false)
const waylineLoading = ref(false)
const authError = ref('')

// ========== dij 连接 ==========
let workspaceId = ''
let wsClose = null
const wsState = ref('closed')
const wsOnlineText = computed(() => (wsState.value === 'connected' ? '已连接' : '未连接'))

// ========== DJI 拓扑数据 ==========
const djiDrones = ref([])      // 飞行器（domain=0）
const docks = ref([])          // 机场（domain=1）
const rawTopology = ref([])    // 原始拓扑（用于机场-飞行器关联）

// ========== 列表 ==========
const devicePage = ref(1)
const pageSize = 10
const deviceFilters = reactive({ status: 'all' })

// 实时 OSD（按设备 SN 缓存）：sn -> host 数据
const osdMap = reactive({})
// 在线集合（WS 上下线维护）
const onlineSet = reactive(new Set())

const filteredDevices = computed(() => {
  let list = devices.value
  if (deviceFilters.status !== 'all') {
    const online = deviceFilters.status === 'online'
    list = list.filter((d) => d.online === online)
  }
  return list
})
const pagedDevices = computed(() => {
  const start = (devicePage.value - 1) * pageSize
  return filteredDevices.value.slice(start, start + pageSize)
})

// 列表 = DJI 真实飞行器 + 合并 WS OSD（电量/剩余飞行时间）+ 绑定机场
const devices = computed(() =>
  djiDrones.value.map((d) => {
    const osd = osdMap[d.device_sn] || {}
    const battery = osd.battery?.capacity_percent
    const remain = osd.battery?.remain_flight_time
    const online = onlineSet.has(d.device_sn) || d.status === 'online'
    return {
      ...d,
      device_name: d.nickname || d.device_name || d.deviceCallsign || d.device_sn,
      device_desc: d.device_desc || d.deviceDesc || '',
      dockName: bindDockName(d),
      online,
      battery: battery != null ? battery : '--',
      remain: remain != null ? remain : '--',
    }
  })
)

// 从拓扑中解析飞行器绑定的机场名称
function bindDockName(drone) {
  if (drone.parent_name) return drone.parent_name
  // 通过机场节点的 child_device_sn 反向匹配
  const dock = rawTopology.value.find(
    (n) => (n.domain === 1 || n.device_type === 1) && (n.child_device_sn === drone.device_sn)
  )
  if (dock) return dock.nickname || dock.device_name || dock.device_sn
  return '--'
}

const isWaylineView = computed(() => viewMode.value === 'waylines')

// ========== 航线 ==========
const waylineFiles = ref([])
const waylinePage = ref(1)

// ========== 测试弹窗 ==========
const testDialogVisible = ref(false)
const testingDevice = ref(null)
const testWaylineId = ref('')
const testStarting = ref(false)
const testing = ref(false)
const testProgress = ref(0)
const liveVideoRef = ref(null)
const isLive = ref(false)
const liveLoading = ref(false)
const videoError = ref(false)
let peerConnection = null
let currentEventSource = null
let currentJobId = ''
let currentVideoId = ''

// 地图动画
const dronePos = ref({ x: 94.9, y: 24.9 })
const selectedWayline = computed(() =>
  waylineFiles.value.find((w) => (w.id || w.wayline_id) === testWaylineId.value) || null
)
const activeRoute = computed(() => {
  const name = selectedWayline.value?.file_name || selectedWayline.value?.name || ''
  return getRouteByName(name) || null
})
const activeRouteName = computed(() => activeRoute.value?.name || '当前航线')
const activeRoutePoints = computed(() => activeRoute.value?.waypoints || [])
const activeRoutePolyline = computed(() =>
  activeRoutePoints.value.map((p) => `${p.x},${p.y}`).join(' ')
)
const droneOnMapStyle = computed(() => ({ left: `${dronePos.value.x}%`, top: `${dronePos.value.y}%` }))

// 测试遥测
const osdData = computed(() => {
  const osd = testingDevice.value ? osdMap[testingDevice.value.device_sn] || {} : {}
  const battery = osd.battery || {}
  return {
    batteryPct: battery.capacity_percent,
    remainMin: battery.remain_flight_time,
    height: fmt(osd.height),
    speed: fmt(osd.horizontal_speed),
    homeDist: fmt(osd.home_distance),
    modeText: parseFlightMode(osd.mode_code),
    modeTone: modeToneClass(osd.mode_code),
    gps: osd.position_state?.gps_number,
    rtk: osd.position_state?.rtk_number,
  }
})
const batteryTone = computed(() => {
  const pct = osdData.value.batteryPct
  if (pct == null) return ''
  if (pct <= 20) return 'tone-danger'
  if (pct <= 40) return 'tone-warn'
  return 'tone-ok'
})

// ========== 工具函数 ==========
const fmt = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(1) : null
}
function batteryClass(pct) {
  if (pct <= 20) return 'is-danger'
  if (pct <= 40) return 'is-warn'
  return 'is-ok'
}
function modeToneClass(code) {
  if (code === 6 || code === 14 || code === 20) return 'tone-danger'
  if (code === 4 || code === 5 || code === 25) return 'tone-ok'
  return ''
}
function getRouteByName(name) {
  if (!name) return null
  if (ROUTES[name]) return ROUTES[name]
  for (const key of Object.keys(ROUTES)) {
    if (name.includes(key) || key.includes(name)) return ROUTES[key]
  }
  return null
}
function formatTime(t) {
  if (!t) return '--'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return '--'
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function normalizeDevice(d) {
  return {
    ...d,
    device_sn: d.device_sn || d.sn,
    status: d.status === true || d.status === 'online' || d.onlineStatus === true ? 'online' : 'offline',
  }
}

// ========== 初始化 ==========
async function initDrone() {
  authError.value = ''
  try {
    const res = await dijLogin(DIJ_USERNAME, DIJ_PASSWORD)
    const token = res.data?.access_token
    if (token) localStorage.setItem('dij_token', token)
  } catch (err) {
    authError.value = `认证失败: ${err.message || '无法连接 DJI Cloud API 后端'}`
    return
  }
  try {
    const wsRes = await getCurrentWorkspace()
    workspaceId = wsRes.data?.workspace_id || wsRes.data?.id || ''
  } catch {
    // 忽略
  }
  await Promise.all([loadDjiTopology(), loadWaylines()])
  connectWebSocket()
}

// 加载 DJI 真实设备：飞行器走 bound 接口（domain=0，含昵称/描述/状态），机场走拓扑（domain=1）
async function loadDjiTopology() {
  deviceLoading.value = true
  try {
    // 1. 拓扑：提取机场节点（domain=1），用于地图标注与绑定关联
    const res = await getDroneDevices(workspaceId || '0')
    const topology = (res.data?.list || res.data || []).map(normalizeDevice)
    rawTopology.value = topology
    docks.value = topology.filter((d) => d.domain === 1)

    // 2. 飞行器：bound 分页接口（返回真实设备：nickname、device_desc、status 等）
    let drones = []
    try {
      const boundRes = await getBoundDevices(workspaceId || '0', { page: 1, page_size: 100, domain: 0 })
      drones = (boundRes.data?.list || []).map(normalizeDevice)
    } catch (err) {
      console.warn('[无人机] bound 接口获取飞行器失败:', err)
    }
    // 3. 兜底一：拓扑中本身就是飞行器的节点
    if (!drones.length) drones = topology.filter((d) => d.domain === 0)
    // 4. 兜底二：由遥控器节点 child_device_sn 构造飞行器
    if (!drones.length) {
      for (const node of topology) {
        if (node.child_device_sn && !drones.find((d) => d.device_sn === node.child_device_sn)) {
          drones.push(normalizeDevice({
            device_sn: node.child_device_sn,
            device_name: `${node.device_name} 飞行器`,
            nickname: node.nickname?.replace(/遥控器|RC.*/, '').trim() || node.device_name,
            domain: 0,
            status: node.status,
          }))
        }
      }
    }
    djiDrones.value = drones
    // 同步在线集合
    djiDrones.value.forEach((d) => {
      if (d.status === 'online') onlineSet.add(d.device_sn)
    })
  } catch (err) {
    console.warn('[无人机] 获取 DJI 拓扑失败:', err)
  } finally {
    deviceLoading.value = false
  }
}

async function loadWaylines() {
  waylineLoading.value = true
  try {
    if (workspaceId) {
      const res = await getWaylineFiles(workspaceId, { page: 1, page_size: 100 })
      waylineFiles.value = res.data?.list || res.data || []
    }
  } catch (err) {
    console.warn('[无人机] 获取航线失败:', err)
    waylineFiles.value = []
  } finally {
    waylineLoading.value = false
  }
}

// WebSocket（保留设备 SN，用于多设备 OSD 缓存）
function connectWebSocket() {
  if (wsClose) wsClose()
  const token = localStorage.getItem('dij_token')
  if (!token) return
  const isDev = import.meta.env.DEV
  const finalUrl = isDev
    ? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/dij-ws`
    : `ws://${DIJ_HOST}/api/v1/ws`

  let ws = null
  let retryCount = 0
  let retryTimer = null
  let closed = false

  function setState(state) {
    wsState.value = state
  }
  function scheduleReconnect() {
    if (closed) return
    const delay = Math.min(3000 * 1.5 ** retryCount, 20000)
    retryCount++
    setState('reconnecting')
    retryTimer = setTimeout(connect, delay)
  }
  function connect() {
    if (closed) return
    setState(retryCount === 0 ? 'connecting' : 'reconnecting')
    try {
      ws = new WebSocket(`${finalUrl}?x-auth-token=${encodeURIComponent(token)}`)
    } catch (err) {
      scheduleReconnect()
      return
    }
    ws.onopen = () => { retryCount = 0; setState('connected') }
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const data = msg.data
        const sn = data?.sn
        const host = data?.host || {}
        switch (msg.biz_code) {
          case 'device_osd':
            if (sn) osdMap[sn] = host
            break
          case 'device_online':
            if (sn) onlineSet.add(sn)
            break
          case 'device_offline':
            if (sn) onlineSet.delete(sn)
            break
          case 'dock_osd':
            if (sn) osdMap[sn] = host
            break
          case 'flighttask_progress':
            if (data?.job_id) {
              if (data.job_id === currentJobId) {
                testProgress.value = Math.round(Number(data.progress || 0) * 100)
                if (data.status === 3 || data.status === 4 || data.status === 5) {
                  setTimeout(() => { testing.value = false }, 1000)
                }
              }
            }
            break
          default:
            break
        }
      } catch { /* 忽略 */ }
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      ws = null
      if (!closed) scheduleReconnect()
    }
  }
  connect()
  wsClose = () => {
    closed = true
    clearTimeout(retryTimer)
    if (ws) { ws.onclose = null; ws.close(); ws = null }
    setState('closed')
  }
}

// ========== 视图切换 ==========
function showWaylines() {
  viewMode.value = 'waylines'
  waylinePage.value = 1
}
function showDevices() {
  viewMode.value = 'devices'
  devicePage.value = 1
}

// ========== 测试弹窗 ==========
async function openTestDialog(row) {
  testingDevice.value = row
  testWaylineId.value = ''
  testProgress.value = 0
  dronePos.value = { x: 94.9, y: 24.9 }
  testDialogVisible.value = true
  await nextTick()
  if (!waylineFiles.value.length && workspaceId) loadWaylines()
}

// 启动：保存任务 -> 模拟飞行 -> 开启视频
async function handleStartTest() {
  if (!testingDevice.value || !testWaylineId.value) return
  const wl = selectedWayline.value
  const name = wl?.file_name || wl?.name || '测试航线'
  const route = getRouteByName(name) || ROUTES['禁渔航线']
  testStarting.value = true
  try {
    // 1. 保存飞行任务（复用 DJI 航线任务接口）
    let jobId = `test_${Date.now()}`
    try {
      const res = await createFlightTask(workspaceId, {
        name: `${name}_测试`,
        fileId: testWaylineId.value,
        dockSn: testingDevice.value.parent_sn || testingDevice.value.device_sn,
        waylineType: 0,
        taskType: 0,
        rthAltitude: 100,
        outOfControlAction: 0,
      })
      if (res.data?.job_id) jobId = res.data.job_id
    } catch (err) {
      console.warn('[测试] 保存任务失败，继续模拟:', err.message)
    }
    currentJobId = jobId
    // 2. 模拟飞行（地图动画；失败不阻断测试，仍展示航线）
    try {
      await startSimulation({
        job_id: jobId,
        route_name: route.name,
        waypoints: route.waypoints,
        duration: 60000,
      })
      connectSimulationSSE(jobId)
    } catch (err) {
      console.warn('[测试] 模拟飞行启动失败，仅展示航线:', err.message)
    }
    testing.value = true
    // 3. 视频流（失败不影响测试）
    await startTestLive()
  } catch (err) {
    ElMessage.error(err.message || '启动失败')
  } finally {
    testStarting.value = false
  }
}

function connectSimulationSSE(jobId) {
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null }
  const token = localStorage.getItem('dij_token')
  const sseUrl = `/dij-api/manage/api/v1/simulation/events/${jobId}?x-auth-token=${encodeURIComponent(token || '')}`
  const es = new EventSource(sseUrl)
  currentEventSource = es
  es.addEventListener('position', (e) => {
    try {
      const data = JSON.parse(e.data)
      dronePos.value = { x: data.x, y: data.y }
      testProgress.value = Math.round(Number(data.progress || 0) * 100)
    } catch { /* 忽略 */ }
  })
  es.addEventListener('complete', () => {
    testing.value = false
    testProgress.value = 100
    es.close()
    currentEventSource = null
  })
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) currentEventSource = null
  }
}

async function startTestLive() {
  if (!testingDevice.value) return
  videoError.value = false
  liveLoading.value = true
  try {
    const capRes = await getLiveCapacity()
    const droneCap = (capRes.data || []).find((d) => d.sn === testingDevice.value.device_sn)
    const cameraIndex = droneCap?.cameras_list?.[0]?.index || '88-0-0'
    const videoIndex = droneCap?.cameras_list?.[0]?.videos_list?.[0]?.index || 'normal-0'
    currentVideoId = `${testingDevice.value.device_sn}/${cameraIndex}/${videoIndex}`
    await startLiveStream({ video_id: currentVideoId, url_type: 1, video_quality: 0 })
    await new Promise((r) => setTimeout(r, 1500))
    const videoEl = liveVideoRef.value
    if (!videoEl) throw new Error('视频元素不存在')
    const streamName = `${testingDevice.value.device_sn}-88-0-0`
    await connectWhep(videoEl, streamName)
    isLive.value = true
  } catch (err) {
    // 视频流失败不影响航线模拟（测试功能不成熟阶段放宽）
    console.warn('[测试] 视频流启动失败，不影响航线模拟:', err.message)
    videoError.value = true
  } finally {
    liveLoading.value = false
  }
}

async function connectWhep(videoEl, streamName) {
  if (peerConnection) { try { peerConnection.close() } catch {} peerConnection = null }
  const pc = new RTCPeerConnection({ bundlePolicy: 'max-bundle', rtcpMuxPolicy: 'require' })
  peerConnection = pc
  pc.addTransceiver('video', { direction: 'recvonly' })
  pc.ontrack = (event) => {
    if (event.streams?.[0]) {
      videoEl.srcObject = event.streams[0]
      videoEl.play().catch(() => {})
    }
  }
  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  await new Promise((resolve) => {
    if (pc.iceGatheringState === 'complete') { resolve(); return }
    pc.onicegatheringstatechange = () => { if (pc.iceGatheringState === 'complete') resolve() }
    setTimeout(resolve, 2000)
  })
  const resp = await fetch(`/drone-mediamtx/live/${streamName}/whep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: pc.localDescription.sdp,
  })
  if (!resp.ok) throw new Error(`WHEP 连接失败: ${resp.status}`)
  const answer = await resp.text()
  await pc.setRemoteDescription({ type: 'answer', sdp: answer })
}

async function handleStopTest() {
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null }
  if (currentJobId) {
    try { await stopSimulation(currentJobId) } catch { /* 忽略 */ }
  }
  testing.value = false
  videoError.value = false
  if (peerConnection) { try { peerConnection.close() } catch {} peerConnection = null }
  if (liveVideoRef.value) liveVideoRef.value.srcObject = null
  isLive.value = false
  if (currentVideoId) {
    try { await stopLiveStream({ video_id: currentVideoId }) } catch { /* 忽略 */ }
    currentVideoId = ''
  }
}

// ========== 生命周期 ==========
onMounted(async () => {
  await initDrone()
})

onBeforeUnmount(() => {
  if (wsClose) wsClose()
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null }
  if (peerConnection) { try { peerConnection.close() } catch {} peerConnection = null }
})

watch(deviceFilters, () => { devicePage.value = 1 })
watch(filteredDevices, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (devicePage.value > maxPage) devicePage.value = maxPage
})

async function refreshCurrent() {
  loading.value = true
  try {
    await Promise.all([loadDjiTopology(), loadWaylines()])
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ===== 页面基础（沿用联动系统深蓝主题） ===== */
.linkage-drone-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.page-header,
.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header {
  min-height: 62px;
  margin-bottom: 14px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, 0.22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, 0.82) 0%, rgba(9, 29, 48, 0.72) 58%, rgba(7, 20, 34, 0.46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, 0.08);
}
.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; }
.page-header p { margin: 7px 0 0; color: #87a5bb; font-size: 13px; }
.page-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}
.tab-header h3 { margin: 0; color: #f3f8fd; font-size: 18px; }
.tab-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: nowrap;
}
.resource-control-card,
.resource-list-card {
  border: 1px solid rgba(96, 151, 191, 0.18);
  border-radius: 8px;
  background: #0b1d30;
}
.resource-control-card {
  min-height: 82px;
  display: flex;
  align-items: center;
  padding: 18px 20px;
}
.resource-control-card .tab-header { width: 100%; }
.resource-list-card { margin-top: 16px; overflow: hidden; }

/* 工具条按钮 */
.console-entry,
.toolbar-template-entry,
.toolbar-return-entry {
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  padding: 0 14px;
  text-decoration: none;
  transition: all 0.18s ease;
}
/* DJI 控制台（强调色） */
.console-entry {
  border: 1px solid rgba(72, 216, 255, 0.65);
  background: linear-gradient(135deg, rgba(18, 92, 133, 0.85), rgba(10, 52, 78, 0.9));
  color: #c8f4ff;
  box-shadow: 0 0 12px rgba(72, 216, 255, 0.18);
}
.console-entry:hover { border-color: #48d8ff; color: #fff; background: rgba(22, 112, 158, 0.9); }
.toolbar-template-entry {
  border: 1px solid rgba(72, 216, 255, 0.42);
  background: rgba(21, 82, 120, 0.55);
  color: #a8ecff;
}
.toolbar-template-entry:hover { border-color: #48d8ff; color: #fff; background: rgba(29, 111, 158, 0.75); }
.toolbar-return-entry {
  border: 1px solid rgba(70, 151, 198, 0.48);
  background: rgba(14, 52, 82, 0.9);
  color: #c6e8ff;
}
.toolbar-return-entry:hover { border-color: rgba(72, 216, 255, 0.78); color: #fff; }
.tab-actions :deep(.el-button) { height: 36px; margin-left: 0; }
.status-filter-select { width: 116px; flex: 0 0 auto; }
.status-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, 0.36) inset;
}
.status-filter-select :deep(.el-select__selected-item),
.status-filter-select :deep(.el-select__placeholder) { color: #d7edf6; font-weight: 700; }

/* ===== 设备列表 ===== */
.device-list,
.wayline-list { min-width: 1100px; overflow: hidden; background: #081b2d; }
.device-list.is-empty,
.wayline-list.is-empty { min-width: 0; }
.device-list-header-row,
.device-row {
  display: grid;
  align-items: center;
  gap: 14px;
  grid-template-columns: minmax(200px, 1.15fr) minmax(240px, 1.35fr) minmax(140px, 0.9fr) minmax(150px, 1fr) 100px 120px;
}
.device-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}
.device-row {
  min-height: 68px;
  padding: 10px 20px;
  border-top: 1px solid rgba(149, 190, 220, 0.10);
  color: #d7e8f8;
  background: #092034;
  transition: background 0.18s ease;
}
.device-row:hover { background: #102940; }
.device-row > div { min-width: 0; }
.col-dock, .col-battery, .col-status, .col-actions {
  display: grid;
  gap: 5px;
  justify-items: center;
  text-align: center;
}
.device-name-cell { display: grid; align-items: center; justify-items: center; text-align: center; }
.device-name-cell strong {
  display: block;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.device-sn {
  color: #6d90a8;
  font-size: 11px;
  font-family: monospace;
}
.device-description span {
  display: -webkit-box;
  overflow: hidden;
  color: #a9c0d2;
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  padding: 0 10px;
  border: 1px solid rgba(235, 124, 133, 0.34);
  border-radius: 4px;
  background: rgba(142, 48, 62, 0.18);
  color: #ffabb5;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}
.status-pill.is-online {
  border-color: rgba(92, 215, 154, 0.34);
  background: rgba(48, 154, 118, 0.18);
  color: #81efad;
}
.battery-num { font-weight: 800; font-size: 15px; }
.battery-num.is-ok { color: #67c23a; }
.battery-num.is-warn { color: #e6a23c; }
.battery-num.is-danger { color: #ff4d4f; }
.battery-remain { color: #7f9bb0; font-size: 12px; }
.list-actions { display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: nowrap; }
.list-actions :deep(.el-button) {
  height: 32px;
  margin: 0;
  padding: 0 14px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.list-actions :deep(.test-action) { border-color: rgba(82, 178, 143, 0.46); color: #b9f1d8; background: rgba(30, 103, 78, 0.38); }
.list-actions :deep(.edit-action) { border-color: rgba(66, 164, 224, 0.50); color: #d5f0ff; background: rgba(29, 91, 133, 0.70); }
.edit-action-link { text-decoration: none; }
.empty-list {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #7fa7bf;
  text-align: center;
}
.empty-list strong { color: #c8e9ff; font-size: 18px; }
.empty-list span { font-size: 14px; }
.list-pagination { min-height: 46px; justify-content: center; border-top: 1px solid rgba(149, 190, 220, 0.10); background: #092034; }
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 34px;
  height: 32px;
  margin: 0 3px;
  border: 1px solid rgba(70, 145, 190, 0.34);
  border-radius: 5px;
  color: #8fb6d1;
  background: #0b2238;
  font-weight: 700;
}
.list-pagination :deep(.el-pager li.is-active) { border-color: #4ba7e6; color: #fff; background: #3f95d7; }

/* ===== 航线视图 ===== */
.wayline-list-header-row,
.wayline-row {
  display: grid;
  align-items: center;
  gap: 14px;
  grid-template-columns: minmax(260px, 2fr) 130px 170px 150px;
}
.wayline-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}
.wayline-row {
  min-height: 62px;
  padding: 10px 20px;
  border-top: 1px solid rgba(149, 190, 220, 0.10);
  background: #092034;
  color: #d7e8f8;
}
.wayline-row > div { min-width: 0; }
.wayline-name strong { color: #f3f8fd; font-size: 15px; }
.wayline-type span { color: #8fb6d1; }
.wayline-time { color: #7f9bb0; font-size: 13px; text-align: center; }

/* ===== 测试弹窗 ===== */
.drone-test-dialog :deep(.el-dialog) {
  background: #0a1c2e;
  border: 1px solid rgba(93, 184, 225, 0.25);
  border-radius: 12px;
}
.drone-test-dialog :deep(.el-dialog__title) { color: #f3f8fd; font-weight: 800; }
.drone-test-dialog :deep(.el-dialog__header) { border-bottom: 1px solid rgba(93, 184, 225, 0.15); }
.test-layout { display: flex; flex-direction: column; gap: 10px; }

.test-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.test-device { display: flex; flex-direction: column; gap: 3px; }
.test-device strong { color: #f3f8fd; font-size: 16px; }
.test-device span { color: #7f9bb0; font-size: 12px; }
.test-wayline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-label { color: #a9c7de; font-size: 13px; font-weight: 700; }
.wayline-select { width: 240px; }
.test-start-btn { font-weight: 800; }

.test-body {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 10px;
  min-height: 420px;
}
.test-map {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  background: #030b12;
  border: 1px solid rgba(93, 184, 225, 0.17);
}
.map-image { width: 100%; height: 100%; object-fit: fill; display: block; }
.route-layer {
  position: absolute;
  inset: 0;
  z-index: 8;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}
.route-line {
  fill: none;
  stroke: #48d8ff;
  stroke-width: 0.7;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.2;
  vector-effect: non-scaling-stroke;
}
.route-line-glow {
  stroke: rgba(72, 216, 255, 0.28);
  stroke-width: 2.4;
  stroke-dasharray: none;
}
.route-point {
  fill: #eafcff;
  stroke: #48d8ff;
  stroke-width: 0.35;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.75));
}
.map-fixed-point {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  pointer-events: none;
}
.fixed-point-icon { width: 22px; height: 22px; object-fit: contain; }
.fixed-point-label {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: monospace;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}
.drone-marker { position: absolute; transform: translate(-50%, -50%); z-index: 10; pointer-events: none; }
.marker-pulse {
  position: absolute; top: 50%; left: 50%;
  width: 36px; height: 36px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(255, 93, 108, 0.3);
  animation: pulse 2s infinite;
}
.marker-icon {
  position: absolute; top: 50%; left: 50%;
  width: 28px; height: 28px;
  transform: translate(-50%, -50%);
  z-index: 2;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.6));
}
@keyframes pulse {
  0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.9; }
  100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
}
.map-legend {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 14;
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(4, 16, 26, 0.78);
  font-size: 12px;
  color: #9fc3da;
}
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-icon-img { width: 14px; height: 14px; object-fit: contain; vertical-align: middle; }
.legend-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  background: #48d8ff;
  vertical-align: middle;
}

.test-video { display: flex; }
.video-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 10px;
  background: #040d16;
  border: 1px solid rgba(93, 184, 225, 0.17);
}
.video-stream { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #7fa7bf;
  text-align: center;
}
.video-placeholder strong { color: #c8e9ff; font-size: 16px; }
.video-placeholder span { font-size: 12px; }
.scan-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(rgba(72, 216, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(72, 216, 255, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
}

.test-telemetry {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid rgba(87, 165, 199, 0.15);
  border-radius: 10px;
  background: rgba(3, 18, 29, 0.4);
}
.telemetry-item { display: flex; flex-direction: column; gap: 3px; }
.t-label { font-size: 11px; color: #607f94; }
.t-value { font-size: 15px; font-weight: 800; font-family: monospace; color: #a9c9da; }
.t-value.tone-ok { color: #67c23a; }
.t-value.tone-warn { color: #e6a23c; }
.t-value.tone-danger { color: #ff4d4f; }
.t-value.mode { font-family: inherit; }

/* 响应式 */
@media (max-width: 1280px) {
  .test-telemetry { grid-template-columns: repeat(4, 1fr); }
  .test-body { grid-template-columns: 1fr 1fr; }
}
</style>
