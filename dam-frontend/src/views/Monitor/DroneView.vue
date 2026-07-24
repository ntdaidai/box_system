<!-- 无人机监测页面 - 对接 DJI Cloud API -->
<template>
  <div class="drone-page">
    <!-- 顶部：三列布局 -->
    <header class="top-section surface-card">
      <!-- 左：无人机图片 -->
      <div class="drone-image-area">
        <img src="/drone.png" alt="无人机" class="drone-hero-img" />
      </div>
      <!-- 中：设备信息 -->
      <div class="info-area">
        <div class="info-row">
          <span class="info-icon">◆</span>
          <span class="info-label">无人机型号</span>
          <span class="info-value cyan">大疆Matrice 4E</span>
        </div>
        <div class="info-row">
          <span class="info-icon">◆</span>
          <span class="info-label">机场名称</span>
          <span class="info-value cyan">DJI RC Plus 2</span>
        </div>
        <div class="info-row">
          <span class="info-icon">◆</span>
          <span class="info-label">机场状态</span>
          <span class="info-value" :class="wsState === 'connected' ? 'green' : 'red'">{{ wsState === 'connected' ? '在线' : '离线' }}</span>
        </div>
        <div class="info-row">
          <span class="info-icon">◆</span>
          <span class="info-label">无人机状态</span>
          <span class="info-value" :class="flightModeClass === 'mode-auto' ? 'green' : 'cyan'">{{ flightModeText }}</span>
        </div>
      </div>
      <!-- 右：遥测数据 -->
      <div class="telemetry-area">
        <div class="telemetry-grid">
          <div class="telemetry-chip"><el-icon :size="12"><Position /></el-icon><span>高度</span><strong>{{ fmt(osd.height) }} m</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Promotion /></el-icon><span>速度</span><strong>{{ fmt(osd.horizontal_speed) }} m/s</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Top /></el-icon><span>垂直速度</span><strong>{{ fmt(osd.vertical_speed) }} m/s</strong></div>
          <div class="telemetry-chip" :class="batteryClass"><el-icon :size="12"><Lightning /></el-icon><span>电量</span><strong>{{ osd.battery?.capacity_percent ?? '--' }}%</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Warning /></el-icon><span>风速</span><strong>{{ fmt(osd.wind_speed) }} m/s</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Sunny /></el-icon><span>风向</span><strong>{{ fmt(osd.wind_direction) }}°</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Odometer /></el-icon><span>离机场</span><strong>{{ fmt(osd.home_distance) }} m</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><MapLocation /></el-icon><span>GPS</span><strong>{{ osd.position_state?.gps_number || 0 }}颗</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Aim /></el-icon><span>RTK</span><strong>{{ osd.position_state?.rtk_number || 0 }}颗</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><DataLine /></el-icon><span>海拔</span><strong>{{ fmt(osd.elevation) }} m</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Cpu /></el-icon><span>档位</span><strong>{{ gearText }}</strong></div>
          <div class="telemetry-chip"><el-icon :size="12"><Van /></el-icon><span>机场电量</span><strong>{{ fmt(gatewayOsd.capacity_percent) }}%</strong></div>
        </div>
      </div>
    </header>

    <!-- 主工作区：地图 + 视频 左右排版 -->
    <section class="main-workspace surface-card">
      <!-- 左侧：地图 -->
      <div class="map-area" ref="mapAreaRef"
        @wheel.prevent="onMapWheel"
        @mousedown="onMapMouseDown"
        @mousemove="onMapMouseMove"
        @mouseup="onMapMouseUp"
        @mouseleave="onMapMouseUp"
        @dblclick="onMapDblClick"
      >
        <div class="map-transform" :style="mapTransformStyle">
          <img src="/dam-map.png" alt="大藤峡地图" class="map-image" draggable="false" />
          <div class="drone-marker" :style="droneMarkerStyle">
            <div class="marker-pulse"></div>
            <div class="marker-dot"></div>
            <span class="marker-label">{{ fmt(osd.height) }}m</span>
          </div>
        </div>
        <div class="map-legend">
          <span><i class="legend-dot drone"></i>无人机</span>
          <span><i class="legend-dot dock"></i>机场</span>
        </div>
      </div>

      <!-- 右侧：视频 -->
      <div class="video-area">
        <div v-if="selectedDevice?.status === 'online'" class="video-stage">
          <video ref="liveVideoRef" class="video-stream" autoplay muted playsinline></video>
          <div v-if="!isLive" class="video-placeholder">
            <el-icon :size="36"><VideoCamera /></el-icon>
            <el-button class="start-btn" :loading="liveLoading" @click="handleStartLive()">
              开启实时画面
            </el-button>
          </div>
          <div v-if="liveLoading" class="video-loading">
            <el-icon class="is-loading" :size="28"><Loading /></el-icon>
          </div>
          <div class="scan-grid"></div>
          <el-button v-if="isLive" class="stop-btn" size="small" @click="handleStopLive()">关闭实时画面</el-button>
        </div>
        <div v-else class="video-stage empty">
          <el-icon :size="36"><VideoCamera /></el-icon>
          <h3 v-if="authError">连接失败</h3>
          <h3 v-else>暂无在线无人机</h3>
          <el-button v-if="authError" class="start-btn" @click="initDrone">重新连接</el-button>
        </div>
      </div>
    </section>


  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Position, Connection, Camera, VideoCamera, Top, Warning, Lightning,
  MapLocation, Promotion, Loading, Odometer, Sunny, Aim, DataLine, Cpu, Van,
} from '@element-plus/icons-vue'
import { dijLogin, getDroneDevices, getBoundDevices, getCurrentWorkspace, sendPayloadCommand, getDeviceHmsDetail, startLiveStream, stopLiveStream, getLiveCapacity } from '@/api/drone'
import { connectDroneWs, WS_STATE, parseFlightMode, parseGear } from '@/utils/droneWs'

// ========== 配置 ==========
// dij 后端地址（用于 WebSocket 直连，HTTP 通过 Vite 代理）
const DIJ_HOST = '127.0.0.1:6790'
// 静默认证凭据（后台自动登录，无需用户操作）
const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'

// ========== 设备列表 ==========
const deviceLoading = ref(false)
const droneDevices = ref([])
const currentDeviceSn = ref('')
const selectedDevice = computed(() =>
  droneDevices.value.find(d => d.device_sn === currentDeviceSn.value) || null
)

// ========== WebSocket 状态 ==========
const wsState = ref(WS_STATE.CLOSED)
const wsStateClass = computed(() => {
  if (wsState.value === WS_STATE.CONNECTED) return 'online'
  if (wsState.value === WS_STATE.CONNECTING || wsState.value === WS_STATE.RECONNECTING) return 'connecting'
  return 'offline'
})
const wsStateText = computed(() => ({
  [WS_STATE.CLOSED]: '未连接',
  [WS_STATE.CONNECTING]: '连接中...',
  [WS_STATE.CONNECTED]: '已连接',
  [WS_STATE.RECONNECTING]: '重连中...',
}[wsState.value] || '未知'))

// ========== OSD 遥测数据 ==========
const osd = ref({
  latitude: 0,
  longitude: 0,
  height: '0',
  elevation: '0',
  home_distance: '0',
  horizontal_speed: '0',
  vertical_speed: '0',
  wind_speed: '0',
  wind_direction: '--',
  gear: 0,
  mode_code: 0,
  battery: {
    capacity_percent: 0,
    landing_power: 0,
    remain_flight_time: 0,
    return_home_power: 0,
  },
  position_state: {
    gps_number: 0,
    rtk_number: 0,
    is_fixed: 0,
  },
})

// DRC 高频 OSD（通过 MQTT，仅在飞行控制模式下可用）
const drcOsd = ref({ attitude_head: 0 })

// 遥控器 OSD
const gatewayOsd = ref({
  capacity_percent: 0,
  transmission_signal_quality: 0,
  longitude: 0,
  latitude: 0,
})

// ========== HMS 告警 ==========
const hmsAlerts = ref([])

// ========== 功能状态 ==========
const authError = ref('')
const isRecording = ref(false)
let wsClose = null
let workspaceId = ref('')

// ========== 直播状态 ==========
const liveVideoRef = ref(null)
const isLive = ref(false)
const liveLoading = ref(false)
let peerConnection = null
let currentVideoId = ''

// ========== 地图交互 ==========
const mapAreaRef = ref(null)
const mapScale = ref(1)
const mapX = ref(0)
const mapY = ref(0)
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragStartMapX = 0
let dragStartMapY = 0

const mapTransformStyle = computed(() => ({
  transform: `translate(${mapX.value}px, ${mapY.value}px) scale(${mapScale.value})`,
  transformOrigin: 'center center',
}))

function onMapWheel(e) {
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  mapScale.value = Math.max(0.5, Math.min(5, mapScale.value + delta))
}

function onMapMouseDown(e) {
  if (e.button !== 0) return
  isDragging = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragStartMapX = mapX.value
  dragStartMapY = mapY.value
  e.currentTarget.style.cursor = 'grabbing'
}

function onMapMouseMove(e) {
  if (!isDragging) return
  mapX.value = dragStartMapX + (e.clientX - dragStartX)
  mapY.value = dragStartMapY + (e.clientY - dragStartY)
}

function onMapMouseUp(e) {
  isDragging = false
  if (e?.currentTarget) e.currentTarget.style.cursor = 'grab'
}

function onMapDblClick() {
  mapScale.value = 1
  mapX.value = 0
  mapY.value = 0
}

// ========== 工具函数 ==========
const fmt = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(1) : '--'
}

// ========== 计算属性 ==========
const flightModeText = computed(() => parseFlightMode(osd.value.mode_code))
const gearText = computed(() => parseGear(osd.value.gear))

const batteryClass = computed(() => {
  const level = Number(osd.value.battery?.capacity_percent) || 0
  if (level <= 20) return 'critical'
  if (level <= 40) return 'low'
  if (level <= 60) return 'medium'
  return 'good'
})

const gpsClass = computed(() => {
  const sats = Number(osd.value.position_state?.gps_number) || 0
  if (sats >= 15) return 'excellent'
  if (sats >= 10) return 'good'
  if (sats >= 6) return 'fair'
  return 'poor'
})

const gpsLevelText = computed(() => {
  const sats = Number(osd.value.position_state?.gps_number) || 0
  const rtk = Number(osd.value.position_state?.rtk_number) || 0
  if (rtk > 0) return `RTK ${rtk}颗`
  if (sats >= 15) return 'GPS 优'
  if (sats >= 10) return 'GPS 良'
  if (sats >= 6) return 'GPS 弱'
  return '信号弱'
})

const flightModeClass = computed(() => {
  const mode = osd.value.mode_code
  if (mode === 6 || mode === 13) return 'mode-return'
  if (mode === 4 || mode === 5 || mode === 25) return 'mode-auto'
  if (mode === 10) return 'mode-hover'
  return 'mode-manual'
})

// 图传信号质量（SDR 0-5 级）
const sdrQualityText = computed(() => {
  const link = gatewayOsd.value.wireless_link
  if (!link) return '--'
  const q = link.sdr_quality
  if (q >= 4) return '优'
  if (q >= 3) return '良'
  if (q >= 2) return '中'
  if (q >= 1) return '弱'
  return link.sdr_link_state ? '极弱' : '断开'
})

// 无人机在地图上的位置（基于 GPS 坐标映射到图片像素）
// 大藤峡地图坐标范围：经度 110.72~110.80, 纬度 23.96~24.02
const droneMarkerStyle = computed(() => {
  const lat = Number(osd.value.latitude) || 0
  const lng = Number(osd.value.longitude) || 0
  if (!lat || !lng) return { display: 'none' }
  // GPS 坐标映射到地图图片上的百分比位置
  const lngMin = 110.72, lngMax = 110.80
  const latMin = 23.96, latMax = 24.02
  const x = Math.max(0, Math.min(100, ((lng - lngMin) / (lngMax - lngMin)) * 100))
  const y = Math.max(0, Math.min(100, ((latMax - lat) / (latMax - latMin)) * 100))
  return { left: `${x}%`, top: `${y}%` }
})

// ========== 方法 ==========

/** 静默认证 + 初始化（页面加载时自动执行） */
async function initDrone() {
  authError.value = ''
  console.log('[init] 开始初始化...')
  try {
    const res = await dijLogin(DIJ_USERNAME, DIJ_PASSWORD)
    const token = res.data?.access_token
    if (token) {
      localStorage.setItem('dij_token', token)
      console.log('[init] 登录成功, token:', token.substring(0, 20) + '...')
    }
  } catch (err) {
    authError.value = `认证失败: ${err.message || '无法连接 DJI Cloud API 后端'}`
    console.error('[init] 登录失败:', err)
    return
  }

  await fetchWorkspace()
  console.log('[init] workspaceId:', workspaceId.value)
  await fetchDevices()
  console.log('[init] 设备列表:', droneDevices.value.map(d => d.device_sn))
  connectWebSocket()
}

/** 获取工作空间 */
async function fetchWorkspace() {
  try {
    const res = await getCurrentWorkspace()
    // 注意：API 路径需要 workspace_id（UUID），不是数字 id
    workspaceId.value = res.data?.workspace_id || res.data?.id || ''
  } catch {
    // 忽略
  }
}

/** 获取设备列表 */
async function fetchDevices() {
  deviceLoading.value = true
  try {
    // 用拓扑接口获取所有设备
    const res = await getDroneDevices(workspaceId.value)
    const topology = res.data || []

    // 从拓扑中提取飞行器（domain=0）
    // children 可能是 dict 或空；也可能通过 child_device_sn 关联
    const drones = []
    for (const node of topology) {
      // 当前节点本身是飞行器
      if (node.domain === 0) {
        drones.push(normalizeDevice(node))
      }
      // 子设备中找飞行器（children dict 有内容时）
      const child = node.children
      if (child && typeof child === 'object' && !Array.isArray(child) && child.device_sn) {
        if (child.domain === 0) {
          drones.push(normalizeDevice(child))
        }
      }
      // children 为空但有 child_device_sn 时，构造飞行器记录
      if (node.child_device_sn && !drones.find(d => d.device_sn === node.child_device_sn)) {
        drones.push(normalizeDevice({
          device_sn: node.child_device_sn,
          device_name: `${node.device_name} 飞行器`,
          nickname: node.nickname?.replace(/遥控器|RC.*/, '').trim() || node.device_name,
          domain: 0,
          status: node.status,
          firmware_version: node.firmware_version,
          workspace_id: node.workspace_id,
        }))
      }
    }

    droneDevices.value = drones.length ? drones : topology.map(normalizeDevice)

    // 默认选中第一个
    if (droneDevices.value.length && !currentDeviceSn.value) {
      currentDeviceSn.value = droneDevices.value[0].device_sn
    }

    // 拓扑为空时尝试分页接口
    if (!droneDevices.value.length) {
      const boundRes = await getBoundDevices(workspaceId.value, { page: 1, page_size: 50, domain: 0 })
      droneDevices.value = (boundRes.data?.list || []).map(normalizeDevice)
      if (droneDevices.value.length && !currentDeviceSn.value) {
        currentDeviceSn.value = droneDevices.value[0].device_sn
      }
    }
  } catch (err) {
    console.warn('获取设备列表失败:', err)
    try {
      const boundRes = await getBoundDevices(workspaceId.value || '0', { page: 1, page_size: 50 })
      droneDevices.value = (boundRes.data?.list || []).map(normalizeDevice)
      if (droneDevices.value.length && !currentDeviceSn.value) {
        currentDeviceSn.value = droneDevices.value[0].device_sn
      }
    } catch {
      // 忽略
    }
  } finally {
    deviceLoading.value = false
  }
}

/** 标准化设备数据（统一 status 为字符串） */
function normalizeDevice(d) {
  return {
    ...d,
    status: d.status === true || d.status === 'online' ? 'online' : 'offline',
  }
}

/** 建立 WebSocket 连接 */
function connectWebSocket() {
  if (wsClose) wsClose()

  const token = localStorage.getItem('dij_token')
  if (!token) { console.warn('[WS] 无 token，跳过连接'); return }

  const isDev = import.meta.env.DEV
  const wsUrl = isDev
    ? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/dij-ws`
    : undefined

  console.log('[WS] 连接:', wsUrl || `ws://${DIJ_HOST}/api/v1/ws`)
  wsClose = connectDroneWs({
    host: isDev ? undefined : DIJ_HOST,
    wsUrl,
    token,
    onDeviceOsd(data) {
      if (data) {
        osd.value = {
          ...osd.value,
          ...data,
          battery: data.battery || osd.value.battery,
          position_state: data.position_state || osd.value.position_state,
        }
        console.log('[OSD] device_osd:', JSON.stringify(data).substring(0, 100))
      }
    },
    onGatewayOsd(data) {
      if (data) {
        gatewayOsd.value = { ...gatewayOsd.value, ...data }
        console.log('[OSD] gateway_osd:', JSON.stringify(data).substring(0, 100))
      }
    },
    onDockOsd(data) {
      // 机场 OSD，可以提取环境信息
      if (data?.basic_osd) {
        // 可以展示机场环境数据
      }
    },
    onDeviceOnline(data) {
      ElMessage.success(`设备上线: ${data?.device_sn || '未知'}`)
      fetchDevices()
    },
    onDeviceOffline(data) {
      ElMessage.warning(`设备离线: ${data?.device_sn || '未知'}`)
      fetchDevices()
    },
    onDeviceHms(data) {
      if (data) {
        hmsAlerts.value = Array.isArray(data) ? data : [data]
      }
    },
    onState(state) {
      wsState.value = state
      console.log('[WS] 状态:', state)
    },
    onError(err) {
      console.warn('WebSocket 错误:', err)
    },
  })
}

/** 切换设备 */
function switchDevice(sn) {
  currentDeviceSn.value = sn
  // 重置 OSD 数据
  osd.value = {
    latitude: 0, longitude: 0, height: '0', elevation: '0',
    home_distance: '0', horizontal_speed: '0', vertical_speed: '0',
    wind_speed: '0', wind_direction: '--', gear: 0, mode_code: 0,
    battery: { capacity_percent: 0, landing_power: 0, remain_flight_time: 0, return_home_power: 0 },
    position_state: { gps_number: 0, rtk_number: 0, is_fixed: 0 },
  }
  hmsAlerts.value = []
  // 加载该设备的 HMS 告警
  loadDeviceHms(sn)
}

/** 加载设备 HMS 告警 */
async function loadDeviceHms(sn) {
  if (!workspaceId.value || !sn) return
  try {
    const res = await getDeviceHmsDetail(workspaceId.value, sn)
    hmsAlerts.value = res.data || []
  } catch {
    // 忽略
  }
}

/** 拍照 */
async function handleTakePhoto() {
  if (!currentDeviceSn.value) return ElMessage.warning('请先选择无人机')
  try {
    await sendPayloadCommand(currentDeviceSn.value, {
      cmd: 'camera_photo_take',
      data: { payload_index: '0-0' },
    })
    ElMessage.success('拍照指令已发送')
  } catch (err) {
    ElMessage.error(err.message || '拍照失败')
  }
}

/** 切换录像 */
async function handleToggleRecording() {
  if (!currentDeviceSn.value) return ElMessage.warning('请先选择无人机')
  try {
    const cmd = isRecording.value ? 'camera_recording_stop' : 'camera_recording_start'
    await sendPayloadCommand(currentDeviceSn.value, {
      cmd,
      data: { payload_index: '0-0' },
    })
    isRecording.value = !isRecording.value
    ElMessage.success(isRecording.value ? '开始录像' : '停止录像')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

/** HMS 告警等级样式 */
function hmsLevelClass(level) {
  if (level === 1) return 'hms-critical'
  if (level === 2) return 'hms-warn'
  return 'hms-info'
}

/** 开始直播 */
async function handleStartLive() {
  if (!currentDeviceSn.value) return ElMessage.warning('请先选择无人机')
  liveLoading.value = true
  try {
    // 1. 获取直播能力，找到当前无人机的摄像头 index
    console.log('[直播] 获取直播能力...')
    const capRes = await getLiveCapacity()
    const droneCap = (capRes.data || []).find(d => d.sn === currentDeviceSn.value)
    const cameraIndex = droneCap?.cameras_list?.[0]?.index || '88-0-0'
    const videoIndex = droneCap?.cameras_list?.[0]?.videos_list?.[0]?.index || 'normal-0'
    currentVideoId = `${currentDeviceSn.value}/${cameraIndex}/${videoIndex}`
    console.log('[直播] videoId:', currentVideoId)

    // 2. 调用 dij 后端开始推流
    console.log('[直播] 发送推流指令...')
    await startLiveStream({
      video_id: currentVideoId,
      url_type: 1,       // RTMP
      video_quality: 0,  // 自适应
    })

    // 3. 通过 MediaMTX WHEP 协议播放 WebRTC 流
    const videoEl = liveVideoRef.value
    if (!videoEl) return
    const streamName = `${currentDeviceSn.value}-88-0-0`
    console.log('[直播] 建立 WHEP 连接, streamName:', streamName)
    await connectMediamtxWebRTC(videoEl, streamName)

    isLive.value = true
  } catch (err) {
    console.error('[直播] 失败:', err)
    ElMessage.error(err.message || '直播启动失败')
  } finally {
    liveLoading.value = false
  }
}

/** 通过 MediaMTX WHEP 协议建立 WebRTC 连接 */
async function connectMediamtxWebRTC(videoEl, streamName) {
  if (peerConnection) {
    try { peerConnection.close() } catch {}
    peerConnection = null
  }

  const pc = new RTCPeerConnection({
    bundlePolicy: 'max-bundle',
    rtcpMuxPolicy: 'require',
  })
  peerConnection = pc

  pc.addTransceiver('video', { direction: 'recvonly' })

  pc.ontrack = (event) => {
    console.log('[WHEP] ontrack 收到视频流')
    if (event.streams?.[0]) {
      videoEl.srcObject = event.streams[0]
      videoEl.play().catch(e => console.warn('[WHEP] 播放被阻止:', e))
    }
  }

  pc.oniceconnectionstatechange = () => {
    console.log('[WHEP] ICE 状态:', pc.iceConnectionState)
    if (pc.iceConnectionState === 'failed') {
      console.warn('[WHEP] 视频连接失败')
    }
  }

  // 等待 ICE 收集完成（含候选）
  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)

  // 等待 ICE 候选收集（最多 2 秒）
  await new Promise(resolve => {
    if (pc.iceGatheringState === 'complete') { resolve(); return }
    pc.onicegatheringstatechange = () => {
      if (pc.iceGatheringState === 'complete') resolve()
    }
    setTimeout(resolve, 2000)
  })

  // 用包含候选的 offer 发送
  const offerWithCandidates = pc.localDescription.sdp
  console.log('[WHEP] offer 含候选, 长度:', offerWithCandidates.length)

  const whepUrl = `/drone-mediamtx/live/${streamName}/whep`
  console.log('[WHEP] 请求:', whepUrl)
  const response = await fetch(whepUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: offerWithCandidates,
  })

  console.log('[WHEP] 响应状态:', response.status)
  if (!response.ok) {
    const errText = await response.text()
    console.error('[WHEP] 错误:', errText)
    throw new Error(`WHEP 连接失败: ${response.status}`)
  }

  const answerSdp = await response.text()
  console.log('[WHEP] answer 含候选, 长度:', answerSdp.length)

  // 从 answer 中提取 ICE 候选并添加到连接
  const candidateLines = answerSdp.split('\r\n').filter(l => l.startsWith('a=candidate:'))
  console.log('[WHEP] ICE 候选数:', candidateLines.length)

  await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
  console.log('[WHEP] 连接建立完成')
}

/** 停止直播 */
async function handleStopLive() {
  // 1. 断开 WebRTC
  if (peerConnection) {
    try { peerConnection.close() } catch {}
    peerConnection = null
  }
  if (liveVideoRef.value) {
    liveVideoRef.value.srcObject = null
  }

  // 2. 调用 dij 后端停止推流
  try {
    if (currentVideoId) {
      await stopLiveStream({ video_id: currentVideoId })
      currentVideoId = ''
    }
  } catch {}

  isLive.value = false
}

// ========== 生命周期 ==========
onMounted(async () => {
  await initDrone()
})

onBeforeUnmount(() => {
  if (wsClose) wsClose()
  if (peerConnection) {
    try { peerConnection.close() } catch {}
    peerConnection = null
  }
})
</script>

<style scoped>
.drone-page {
  --cyan: #48d8ff;
  --mint: #51e6be;
  --amber: #ffbd65;
  --muted: #7f9bb0;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  color: #e9f7ff;
  background:
    radial-gradient(circle at 15% 0%, rgba(33, 126, 190, 0.18), transparent 30%),
    linear-gradient(145deg, #071522, #091b2d 58%, #071522);
}

.surface-card {
  border: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(13, 38, 59, 0.94), rgba(8, 26, 43, 0.94));
  box-shadow: 0 8px 24px rgba(0, 7, 18, 0.2), inset 0 1px rgba(255, 255, 255, 0.025);
}

h1, h2, h3, p { margin: 0; }

/* 顶部三列布局 */
.top-section {
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  gap: 0;
  padding: 0;
  overflow: hidden;
}
.drone-image-area {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(20, 60, 90, 0.6), rgba(10, 30, 50, 0.8));
  border-right: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 12px 0 0 12px;
  padding: 12px;
}
.drone-hero-img {
  max-width: 100%;
  max-height: 140px;
  object-fit: contain;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4));
}
.info-area {
  padding: 14px 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  border-right: 1px solid rgba(93, 184, 225, 0.1);
}
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  line-height: 1.9;
}
.info-icon { color: var(--cyan); font-size: 11px; }
.info-label { color: #c8dce8; font-weight: 500; min-width: 80px; }
.info-value { font-weight: 700; font-size: 17px; }
.info-value.cyan { color: var(--cyan); }
.info-value.green { color: #51e6be; }
.info-value.red { color: #ff5d6c; }

.telemetry-area {
  padding: 12px 16px;
  display: flex;
  align-items: center;
}
.telemetry-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.telemetry-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 6px;
  background: rgba(3, 18, 29, 0.5);
  border: 1px solid rgba(87, 165, 199, 0.12);
  color: #7d9bb0;
  font-size: 11px;
}
.telemetry-chip .el-icon { color: var(--cyan); flex-shrink: 0; }
.telemetry-chip span { color: #7d9bb0; }
.telemetry-chip strong {
  margin-left: auto;
  color: #a9c9da;
  font: 600 12px monospace;
}
.telemetry-chip.good .el-icon { color: #67c23a; }
.telemetry-chip.medium .el-icon { color: #e6a23c; }
.telemetry-chip.low .el-icon { color: #f56c6c; }
.telemetry-chip.critical .el-icon { color: #ff4d4f; }

/* 主工作区 */
.main-workspace {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 0;
  padding: 0;
  overflow: hidden;
}

/* 地图区域 */
.map-area {
  position: relative;
  overflow: hidden;
  background: #030b12;
  border-right: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 12px 0 0 12px;
  cursor: grab;
  user-select: none;
}
.map-transform {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s ease-out;
}
.map-image {
  max-width: 100%;
  max-height: 100%;
  display: block;
  pointer-events: none;
}
.drone-marker { position: absolute; transform: translate(-50%, -50%); z-index: 10; pointer-events: none; }
.marker-pulse { position: absolute; top: 50%; left: 50%; width: 36px; height: 36px; transform: translate(-50%, -50%); border-radius: 50%; background: rgba(255, 93, 108, 0.3); animation: pulse 2s infinite; }
.marker-dot { position: absolute; top: 50%; left: 50%; width: 12px; height: 12px; transform: translate(-50%, -50%); border-radius: 50%; background: #ff5d6c; border: 2px solid #fff; box-shadow: 0 0 8px rgba(255, 93, 108, 0.8); z-index: 2; }
.marker-label { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); padding: 2px 8px; border-radius: 4px; background: rgba(0, 0, 0, 0.7); color: #fff; font-size: 11px; font-family: monospace; white-space: nowrap; }
@keyframes pulse { 0% { transform: translate(-50%, -50%) scale(0.8); opacity: 1; } 100% { transform: translate(-50%, -50%) scale(2); opacity: 0; } }
.map-legend { position: absolute; bottom: 10px; left: 10px; display: flex; gap: 12px; padding: 6px 12px; border-radius: 6px; background: rgba(0, 0, 0, 0.65); font-size: 11px; color: #ccc; z-index: 5; pointer-events: none; }
.map-zoom-hint { position: absolute; bottom: 10px; right: 10px; padding: 4px 10px; border-radius: 4px; background: rgba(0, 0, 0, 0.5); color: #667; font-size: 10px; z-index: 5; pointer-events: none; }
.legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.legend-dot.drone { background: #ff5d6c; }
.legend-dot.dock { background: #67c23a; }

/* 视频区域 */
.video-area {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0 12px 12px 0;
  aspect-ratio: 16/9;
}
.video-stage {
  position: relative;
  flex: 1;
  background: #030b12;
  overflow: hidden;
}
.video-stage.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #556;
}
.video-stage.empty h3 { color: #8aa; margin: 0; font-size: 14px; }
.video-stream { width: 100%; height: 100%; object-fit: contain; display: block; }
.video-placeholder {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; color: #556;
}
.start-btn {
  padding: 8px 20px; font-size: 13px; border-radius: 8px;
  color: #061b23; border: none; font-weight: 700;
  background: linear-gradient(105deg, #35c8ea, #52e5bd);
}
.stop-btn {
  position: absolute; z-index: 6; right: 10px; bottom: 10px;
  border-radius: 6px; background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.2); color: #ddd;
}
.stop-btn:hover { background: rgba(255, 93, 108, 0.7); color: #fff; }
.video-loading {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: #8ddcf0; background: rgba(3, 14, 23, 0.76);
}
.scan-grid {
  position: absolute; inset: 0; z-index: 2;
  pointer-events: none; opacity: 0.08;
  background: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(66, 210, 245, 0.12) 4px);
}

/* 底部状态栏 */
.bottom-bar { display: flex; align-items: center; gap: 2px; padding: 8px 12px; overflow-x: auto; }
.bottom-item { flex: 1; min-width: 80px; display: flex; flex-direction: column; align-items: center; padding: 6px 8px; border-radius: 6px; background: rgba(3, 18, 29, 0.36); }
.bottom-item small { color: #607f94; font-size: 10px; margin-bottom: 2px; }
.bottom-item strong { color: #a9c9da; font: 600 15px monospace; }
.bottom-item strong span { font-size: 10px; color: #6a8da3; font-weight: 400; }
.bottom-item strong.good { color: #67c23a; }
.bottom-item strong.medium { color: #e6a23c; }
.bottom-item strong.low { color: #f56c6c; }
.bottom-item strong.critical { color: #ff4d4f; }
.mini-bar { width: 100%; height: 3px; margin-top: 4px; border-radius: 2px; background: rgba(75, 112, 132, 0.16); overflow: hidden; }
.mini-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
.mini-bar-fill.good { background: #67c23a; }
.mini-bar-fill.medium { background: #e6a23c; }
.mini-bar-fill.low { background: #f56c6c; }
.mini-bar-fill.critical { background: #ff4d4f; }

@keyframes blink { 50% { opacity: 0.4; } }

@media (max-width: 900px) {
  .main-workspace { grid-template-columns: 1fr; }
  .map-area { border-right: none; border-radius: 12px 12px 0 0; border-bottom: 1px solid rgba(93, 184, 225, 0.17); }
  .video-area { border-radius: 0 0 12px 12px; min-height: 300px; }
  .bar-right { display: none; }
  .bottom-bar { flex-wrap: wrap; }
}
</style>