<!-- 无人机设备（联动系统）- 直连 DJI 真实设备，对标广播设备页样式 -->
<template>
  <div class="linkage-drone-page">
    <header class="page-header">
      <div>
        <h2>无人机设备</h2>
        <p>展示无人机与绑定机场，选择航线测试自动巡检；航线以地图总览方式查看</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
    </header>

    <!-- 工具条 -->
    <section class="resource-control-card">
      <header class="tab-header">
        <h3>无人机列表</h3>
        <div class="tab-actions">
          <button type="button" class="toolbar-map-entry" @click="openWaylineMap">
            <el-icon><MapLocation /></el-icon>
            <span>查看航线 {{ waylineRoutes.length }}</span>
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
      </header>
    </section>

    <!-- 设备列表 -->
    <section class="resource-list-card" v-loading="deviceLoading">
      <div class="device-list" :class="{ 'is-empty': !filteredDevices.length }">
        <div v-if="filteredDevices.length" class="device-list-header-row">
          <div class="col-name">设备名称</div>
          <div class="col-desc">描述</div>
          <div class="col-dock">绑定机场</div>
          <div class="col-battery">电量(剩余飞行时间)</div>
          <div class="col-status">状态</div>
          <div class="col-enabled">是否启用</div>
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
          <div class="col-enabled">
            <el-switch
              :model-value="row.enabled !== false"
              @change="(value) => toggleEnabled(row, value)"
            />
          </div>
          <div class="col-actions list-actions">
            <el-button class="test-action" @click="openTestDialog(row)">测试</el-button>
            <el-button class="edit-action" @click="openEditDialog(row)">编辑</el-button>
            <el-button class="delete-action" @click="confirmDeleteDevice(row)">删除</el-button>
          </div>
        </article>
        <div v-if="!filteredDevices.length" class="empty-list">
          <strong>{{ authError ? 'DJI 服务连接失败' : '暂无在线无人机' }}</strong>
          <span>{{ authError || '当前无匹配的无人机设备' }}</span>
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

    <!-- 测试弹窗 -->
    <el-dialog
      v-model="testDialogVisible"
      title="无人机测试 · 航线巡检"
      width="92%"
      align-center
      class="drone-test-dialog"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="test-layout">
        <!-- 顶部工具条 -->
        <div class="test-toolbar">
          <div class="test-device">
            <strong>{{ testingDevice?.device_name || '--' }}</strong>
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
                v-for="route in waylineRoutes"
                :key="route.name"
                :label="route.name"
                :value="route.name"
              />
            </el-select>
            <el-button
              :icon="VideoCamera"
              :disabled="!testWaylineId"
              type="primary"
              @click="handleStartTest"
            >开始</el-button>
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
              <video
                v-if="testing && demoVideoSrc"
                :key="testWaylineId"
                :src="demoVideoSrc"
                class="video-stream"
                autoplay
                muted
                loop
                playsinline
              ></video>
              <div v-else class="video-placeholder">
                <el-icon :size="36"><VideoCamera /></el-icon>
                <strong>请选择航线</strong>
                <span>选择航线后点击开始，播放对应的巡检演示视频</span>
              </div>
              <div v-if="testing" class="video-progress-badge">{{ testProgress }}%</div>
              <div class="scan-grid"></div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 航线大图弹窗（对标感知源“查看点位图”的图片方式展示） -->
    <el-dialog
      v-model="waylineMapVisible"
      class="wayline-map-dialog"
      title="航线总览图"
      width="95vw"
      top="3vh"
    >
      <div class="wayline-map-stage">
        <img src="/dam-map.png" alt="大藤峡航线总览" draggable="false" />
        <svg
          class="wayline-map-svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <g v-for="(route, index) in waylineRoutes" :key="route.name" class="wayline-map-route-group">
            <polyline class="wayline-map-route route-glow" :class="`tone-${index}`" :points="routePolyline(route)" />
            <polyline class="wayline-map-route" :class="`tone-${index}`" :points="routePolyline(route)" />
            <circle
              v-for="(pt, i) in route.waypoints"
              :key="`${route.name}-${i}`"
              class="wayline-map-point"
              :cx="pt.x"
              :cy="pt.y"
              r="1.4"
            />
          </g>
        </svg>
        <div class="wayline-map-fixed-point" style="left: 94.9%; top: 24.9%;">
          <img src="/starting-point.png" alt="机场" />
          <span>P3 机场</span>
        </div>
        <div class="wayline-map-fixed-point" style="left: 47.4%; top: 58.1%;">
          <img src="/waypoint.png" alt="禁渔点" />
          <span>禁渔点</span>
        </div>
        <div class="wayline-map-fixed-point" style="left: 96.3%; top: 54.3%;">
          <img src="/waypoint.png" alt="禁涉水点" />
          <span>禁涉水点</span>
        </div>
        <div class="wayline-map-legend">
          <span class="legend-item"><img src="/starting-point.png" class="legend-icon-img" />起始点</span>
          <span class="legend-item"><img src="/waypoint.png" class="legend-icon-img" />航点</span>
          <span class="legend-item"><i class="legend-line tone-0"></i>禁渔航线</span>
          <span class="legend-item"><i class="legend-line tone-1"></i>禁涉水航线</span>
        </div>
      </div>
    </el-dialog>

    <!-- 编辑无人机弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑无人机设备"
      width="520px"
      class="drone-edit-dialog"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="设备名称">
          <el-input v-model.trim="editForm.device_name" maxlength="64" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model.trim="editForm.device_desc" type="textarea" :rows="3" maxlength="200" placeholder="请输入设备描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Close, MapLocation, Refresh, VideoCamera,
} from '@element-plus/icons-vue'
import {
  dijLogin,
  getBoundDevices,
  getCurrentWorkspace,
  getDroneDevices,
} from '@/api/drone'

// ========== 配置 ==========
const DIJ_HOST = '127.0.0.1:6790'
const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'
// 模拟航线（用于地图动画与航线总览图；真实航线以 DJI wayline 为准）
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

// 示例无人机数据（DJI 拓扑不可用或暂无真实设备时用于界面展示）
const MOCK_DRONES = [
  { device_sn: 'mock-drone-001', device_name: '御3行业版-1号', device_desc: 'P3 机场起降，负责禁渔区常态化巡检', device_model: 'M30T', dockName: 'P3 机场', battery: 86, remain: 32, status: 'online' },
  { device_sn: 'mock-drone-002', device_name: 'M350 RTK-2号', device_desc: 'P2 机场起降，负责禁涉水区重点巡查', device_model: 'M350', dockName: 'P2 机场', battery: 54, remain: 18, status: 'online' },
  { device_sn: 'mock-drone-003', device_name: '精灵4 RTK-3号', device_desc: 'P1 机场起降，应急巡检备用机', device_model: 'P4RTK', dockName: 'P1 机场', battery: 23, remain: 6, status: 'offline', enabled: false },
]

// ========== 视图状态 ==========
const loading = ref(false)
const deviceLoading = ref(false)
const authError = ref('')

// 演示视频映射：固定演示航线 → 本地演示视频（点击开始后播放，模拟真实视频流）
const DEMO_VIDEO_MAP = {
  '禁渔航线': '/demo/wading.mp4',
  '禁涉水航线': '/demo/fishing.mp4',
}

// ========== dij 连接 ==========
let workspaceId = ''
let wsClose = null
const wsState = ref('closed')

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

// 列表 = DJI 真实飞行器 + 合并 WS OSD（电量/剩余飞行时间）+ 绑定机场；示例数据自带电量/时长字段
const devices = computed(() =>
  djiDrones.value.map((d) => {
    const osd = osdMap[d.device_sn] || {}
    const battery = osd.battery?.capacity_percent ?? d.battery ?? null
    const remain = osd.battery?.remain_flight_time ?? d.remain ?? null
    const online = onlineSet.has(d.device_sn) || d.status === 'online' || d.online === true
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

// 从拓扑中解析飞行器绑定的机场名称（示例数据自带 dockName 时优先使用）
function bindDockName(drone) {
  if (drone.dockName) return drone.dockName
  if (drone.parent_name) return drone.parent_name
  // 通过机场节点的 child_device_sn 反向匹配
  const dock = rawTopology.value.find(
    (n) => (n.domain === 1 || n.device_type === 1) && (n.child_device_sn === drone.device_sn)
  )
  if (dock) return dock.nickname || dock.device_name || dock.device_sn
  return '--'
}

// ========== 测试弹窗 ==========
const testDialogVisible = ref(false)
const testingDevice = ref(null)
const testWaylineId = ref('')
const testing = ref(false)
const testProgress = ref(0)

// 地图动画
const dronePos = ref({ x: 94.9, y: 24.9 })
const activeRoute = computed(() => ROUTES[testWaylineId.value] || null)
const activeRouteName = computed(() => activeRoute.value?.name || '当前航线')
const activeRoutePoints = computed(() => activeRoute.value?.waypoints || [])
const activeRoutePolyline = computed(() =>
  activeRoutePoints.value.map((p) => `${p.x},${p.y}`).join(' ')
)
const droneOnMapStyle = computed(() => ({ left: `${dronePos.value.x}%`, top: `${dronePos.value.y}%` }))
// 当前航线对应的演示视频地址（选择航线后右侧自动播放）
const demoVideoSrc = computed(() => DEMO_VIDEO_MAP[testWaylineId.value] || '')

// 本地航线动画（演示用途，不依赖后端模拟/实时流）
let animFrame = null
let animStart = null
const ANIM_DURATION = 30000 // 单次演示时长 30s
function pointAt(pts, t) {
  const segs = pts.slice(0, -1).map((p, i) => ({
    a: p,
    b: pts[i + 1],
    len: Math.hypot(pts[i + 1].x - p.x, pts[i + 1].y - p.y),
  }))
  const total = segs.reduce((s, x) => s + x.len, 0) || 1
  let target = t * total
  for (const seg of segs) {
    if (target <= seg.len) {
      const k = seg.len ? target / seg.len : 0
      return { x: seg.a.x + (seg.b.x - seg.a.x) * k, y: seg.a.y + (seg.b.y - seg.a.y) * k }
    }
    target -= seg.len
  }
  const last = pts[pts.length - 1]
  return { x: last.x, y: last.y }
}
function startLocalAnimation(route) {
  stopLocalAnimation()
  const pts = route?.waypoints || []
  if (pts.length < 2) return
  animStart = performance.now()
  const step = (now) => {
    const t = Math.min(1, (now - animStart) / ANIM_DURATION)
    dronePos.value = pointAt(pts, t)
    testProgress.value = Math.round(t * 100)
    if (t < 1) {
      animFrame = requestAnimationFrame(step)
    } else {
      testing.value = false
    }
  }
  animFrame = requestAnimationFrame(step)
}
function stopLocalAnimation() {
  if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null }
  animStart = null
}

// ========== 工具函数 ==========
function batteryClass(pct) {
  if (pct <= 20) return 'is-danger'
  if (pct <= 40) return 'is-warn'
  return 'is-ok'
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
  await loadDjiTopology()
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
    // DJI 拓扑不可用或暂无真实设备时，回退示例数据用于界面展示
    if (!drones.length) {
      drones = MOCK_DRONES.map((d) => ({ ...d }))
    }
    djiDrones.value = drones
    // 同步在线集合
    djiDrones.value.forEach((d) => {
      if (d.status === 'online') onlineSet.add(d.device_sn)
    })
  } catch (err) {
    // DJI 服务连接失败时同样回退示例数据，保证列表始终有内容展示
    console.warn('[无人机] 获取 DJI 拓扑失败，回退示例数据:', err)
    djiDrones.value = MOCK_DRONES.map((d) => ({ ...d }))
  } finally {
    deviceLoading.value = false
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

// ========== 航线大图弹窗 ==========
const waylineMapVisible = ref(false)
const waylineRoutes = Object.values(ROUTES)
function routePolyline(route) {
  return (route.waypoints || []).map((p) => `${p.x},${p.y}`).join(' ')
}
function openWaylineMap() {
  waylineMapVisible.value = true
}

// ========== 编辑 / 删除（对标广播设备列表样式，示例数据与本地信息编辑） ==========
const editDialogVisible = ref(false)
const editingDevice = ref(null)
const editForm = reactive({ device_name: '', device_desc: '' })

function openEditDialog(row) {
  editingDevice.value = row
  editForm.device_name = row.device_name || ''
  editForm.device_desc = row.device_desc || ''
  editDialogVisible.value = true
}

function saveEdit() {
  if (!editingDevice.value) return
  const idx = djiDrones.value.findIndex((d) => d.device_sn === editingDevice.value.device_sn)
  if (idx >= 0) {
    djiDrones.value[idx] = {
      ...djiDrones.value[idx],
      device_name: editForm.device_name,
      nickname: editForm.device_name,
      device_desc: editForm.device_desc,
    }
  }
  editDialogVisible.value = false
  ElMessage.success('设备信息已更新')
}

function confirmDeleteDevice(row) {
  ElMessageBox.confirm(`确认删除无人机「${row.device_name}」？`, '删除设备', { type: 'warning' })
    .then(() => {
      djiDrones.value = djiDrones.value.filter((d) => d.device_sn !== row.device_sn)
      ElMessage.success('设备已删除')
    })
    .catch(() => {})
}

// 启用开关：本地切换展示状态（DJI 设备无启停接口，仅界面展示）
function toggleEnabled(row, value) {
  const idx = djiDrones.value.findIndex((d) => d.device_sn === row.device_sn)
  if (idx >= 0) djiDrones.value[idx].enabled = value
}

// ========== 测试弹窗 ==========
async function openTestDialog(row) {
  testingDevice.value = row
  testWaylineId.value = ''
  testProgress.value = 0
  dronePos.value = { x: 94.9, y: 24.9 }
  testDialogVisible.value = true
}

// 点击开始：左侧地图动画 + 右侧演示视频（模拟真实视频流，无进度条）
function handleStartTest() {
  const route = ROUTES[testWaylineId.value]
  if (!route) {
    ElMessage.warning('请先选择航线')
    return
  }
  stopLocalAnimation()
  startLocalAnimation(route)
  testing.value = true
}

function handleStopTest() {
  stopLocalAnimation()
  testing.value = false
}

// ========== 生命周期 ==========
onMounted(async () => {
  await initDrone()
})

onBeforeUnmount(() => {
  if (wsClose) wsClose()
  stopLocalAnimation()
})

watch(deviceFilters, () => { devicePage.value = 1 })
watch(filteredDevices, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (devicePage.value > maxPage) devicePage.value = maxPage
})

// 测试弹窗中切换航线：重置演示状态（重新点击开始才启动）
watch(testWaylineId, () => {
  stopLocalAnimation()
  testing.value = false
  testProgress.value = 0
  dronePos.value = { x: 94.9, y: 24.9 }
})

async function refreshCurrent() {
  loading.value = true
  try {
    await loadDjiTopology()
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

/* 工具条按钮：查看航线（大按钮，对标感知源“查看点位图”） */
.toolbar-map-entry {
  flex: 0 0 auto;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 18px 0 12px;
  border: 1px solid rgba(72, 216, 255, 0.58);
  border-radius: 6px;
  color: #e8faff;
  background: linear-gradient(135deg, rgba(23, 116, 155, 0.88), rgba(10, 59, 88, 0.86));
  font: inherit;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, 0.10), 0 0 18px rgba(72, 216, 255, 0.16);
  transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}
.toolbar-map-entry:hover {
  border-color: rgba(126, 238, 255, 0.82);
  color: #ffffff;
  background: linear-gradient(135deg, rgba(30, 136, 181, 0.96), rgba(12, 72, 108, 0.92));
}
.toolbar-map-entry .el-icon {
  width: 26px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  color: #031825;
  background: #48d8ff;
  font-size: 18px;
}
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
.device-list { min-width: 1400px; overflow: hidden; background: #081b2d; }
.device-list.is-empty { min-width: 0; }
.device-list-header-row,
.device-row {
  display: grid;
  align-items: center;
  gap: 14px;
  grid-template-columns: minmax(190px, 1.05fr) minmax(210px, 1.15fr) minmax(120px, 0.75fr) minmax(150px, 1fr) 100px 100px 300px;
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
.col-dock, .col-battery, .col-status, .col-enabled, .col-actions {
  display: grid;
  gap: 5px;
  justify-items: center;
  text-align: center;
}
.col-enabled :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, 0.34);
  background: rgba(96, 118, 134, 0.38);
}
.col-enabled :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, 0.66);
  background: #409eff;
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
.device-description {
  display: grid;
  justify-items: center;
  text-align: center;
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
.list-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: nowrap;
}
.list-actions :deep(.el-button) {
  width: auto;
  height: 34px;
  min-height: 34px;
  margin: 0;
  padding: 0 16px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.list-actions :deep(.test-action) { border-color: rgba(82, 178, 143, 0.46); color: #b9f1d8; background: rgba(30, 103, 78, 0.38); }
.list-actions :deep(.edit-action) { border-color: rgba(66, 164, 224, 0.50); color: #d5f0ff; background: rgba(29, 91, 133, 0.70); }
.list-actions :deep(.delete-action) { border-color: rgba(226, 88, 109, 0.46); color: #ffb1bd; background: rgba(128, 36, 54, 0.48); }
.list-actions :deep(.test-action:hover) { border-color: rgba(82, 178, 143, 0.70); color: #e3fff1; background: rgba(36, 123, 92, 0.52); }
.list-actions :deep(.edit-action:hover) { border-color: rgba(66, 164, 224, 0.72); color: #effaff; background: rgba(33, 107, 156, 0.82); }
.list-actions :deep(.delete-action:hover) { border-color: rgba(226, 88, 109, 0.68); color: #ffd5dd; background: rgba(144, 42, 62, 0.62); }
/* 与广播设备列表按钮样式严格对齐（!important 兜底，防止被 element-plus 默认样式覆盖） */
:global(.linkage-drone-page .list-actions .el-button.test-action) {
  border-color: rgba(82, 178, 143, .54) !important;
  color: #b9f1d8 !important;
  background: rgba(30, 103, 78, .42) !important;
}
:global(.linkage-drone-page .list-actions .el-button.edit-action) {
  border-color: rgba(66, 164, 224, .50) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .70) !important;
}
:global(.linkage-drone-page .list-actions .el-button.delete-action) {
  border-color: rgba(226, 88, 109, .46) !important;
  color: #ffb1bd !important;
  background: rgba(128, 36, 54, .48) !important;
}
:global(.linkage-drone-page .list-actions .el-button.test-action:hover) {
  border-color: rgba(82, 178, 143, .72) !important;
  color: #e3fff1 !important;
  background: rgba(36, 123, 92, .56) !important;
}
:global(.linkage-drone-page .list-actions .el-button.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .82) !important;
}
:global(.linkage-drone-page .list-actions .el-button.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68) !important;
  color: #ffd5dd !important;
  background: rgba(144, 42, 62, .62) !important;
}
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
.video-progress-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 3;
  padding: 2px 10px;
  border: 1px solid rgba(72, 216, 255, 0.35);
  border-radius: 12px;
  background: rgba(7, 20, 34, 0.72);
  color: #48d8ff;
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
}

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

/* ===== 航线大图弹窗（对标感知源“查看点位图”的图片方式） ===== */
:global(.wayline-map-dialog.el-dialog) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  border-radius: 8px;
  background: #07131a;
  box-shadow: 0 24px 60px rgba(0, 7, 18, 0.46);
}
:global(.wayline-map-dialog .el-dialog__header) {
  margin: 0;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(137, 174, 184, 0.14);
}
:global(.wayline-map-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-weight: 900;
}
:global(.wayline-map-dialog .el-dialog__body) {
  padding: 12px;
}
.wayline-map-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 2168 / 725;
  max-height: 84vh;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: #02080d;
}
.wayline-map-stage > img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  filter: saturate(1.08) contrast(1.06) brightness(0.76);
}
.wayline-map-svg {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.wayline-map-route {
  fill: none;
  stroke-width: 0.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.3;
  vector-effect: non-scaling-stroke;
}
.wayline-map-route.route-glow {
  stroke-width: 1.8;
  stroke-dasharray: none;
  opacity: 0.4;
}
.wayline-map-route.tone-0 { stroke: #48d8ff; }
.wayline-map-route.tone-1 { stroke: #ffd166; }
.wayline-map-point {
  fill: #eafcff;
  stroke: #48d8ff;
  stroke-width: 0.4;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.75));
}
.wayline-map-fixed-point {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  pointer-events: none;
}
.wayline-map-fixed-point img { width: 22px; height: 22px; object-fit: contain; }
.wayline-map-fixed-point span {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: monospace;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}
.wayline-map-legend {
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
.wayline-map-legend .legend-item { display: inline-flex; align-items: center; gap: 5px; }
.wayline-map-legend .legend-icon-img { width: 14px; height: 14px; object-fit: contain; vertical-align: middle; }
.wayline-map-legend .legend-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  vertical-align: middle;
}
.wayline-map-legend .legend-line.tone-0 { background: #48d8ff; }
.wayline-map-legend .legend-line.tone-1 { background: #ffd166; }

/* ===== 编辑无人机弹窗 ===== */
.drone-edit-dialog :deep(.el-dialog) {
  background: #0a1c2e;
  border: 1px solid rgba(93, 184, 225, 0.25);
  border-radius: 12px;
}
.drone-edit-dialog :deep(.el-dialog__title) { color: #f3f8fd; font-weight: 800; }
.drone-edit-dialog :deep(.el-form-item__label) { color: #a9c7de; }
.drone-edit-dialog :deep(.el-input__wrapper),
.drone-edit-dialog :deep(.el-textarea__inner) {
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, 0.36) inset;
  color: #d7e8f8;
}
.drone-edit-dialog :deep(.el-input__inner) { color: #d7e8f8; }

/* 响应式 */
@media (max-width: 1280px) {
  .test-body { grid-template-columns: 1fr 1fr; }
}
</style>
