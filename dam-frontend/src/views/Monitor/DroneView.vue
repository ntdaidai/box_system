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
        <!-- 飞行数据组 -->
        <div class="telemetry-group">
          <div class="group-title">飞行数据</div>
          <div class="telemetry-list">
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Position /></el-icon></div>
              <div class="item-info">
                <span class="item-label">飞行高度</span>
                <span class="item-value">{{ fmt(osd.height) }}<small>m</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Promotion /></el-icon></div>
              <div class="item-info">
                <span class="item-label">水平速度</span>
                <span class="item-value">{{ fmt(osd.horizontal_speed) }}<small>m/s</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Top /></el-icon></div>
              <div class="item-info">
                <span class="item-label">垂直速度</span>
                <span class="item-value">{{ fmt(osd.vertical_speed) }}<small>m/s</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Odometer /></el-icon></div>
              <div class="item-info">
                <span class="item-label">离机场距离</span>
                <span class="item-value">{{ fmt(osd.home_distance) }}<small>m</small></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 电池与环境组 -->
        <div class="telemetry-group">
          <div class="group-title">电池与环境</div>
          <div class="telemetry-list">
            <div class="telemetry-item" :class="batteryClass">
              <div class="item-icon"><el-icon :size="14"><Lightning /></el-icon></div>
              <div class="item-info">
                <span class="item-label">无人机电量</span>
                <span class="item-value">{{ osd.battery?.capacity_percent ?? '--' }}<small>%</small></span>
              </div>
              <!-- 电量条 -->
              <div class="battery-bar">
                <div class="battery-fill" :style="{ width: (osd.battery?.capacity_percent || 0) + '%' }"></div>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Van /></el-icon></div>
              <div class="item-info">
                <span class="item-label">机场电量</span>
                <span class="item-value">{{ fmt(gatewayOsd.capacity_percent) }}<small>%</small></span>
              </div>
              <div class="battery-bar">
                <div class="battery-fill dock" :style="{ width: (gatewayOsd.capacity_percent || 0) + '%' }"></div>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Warning /></el-icon></div>
              <div class="item-info">
                <span class="item-label">风速</span>
                <span class="item-value">{{ fmt(osd.wind_speed) }}<small>m/s</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Sunny /></el-icon></div>
              <div class="item-info">
                <span class="item-label">风向</span>
                <span class="item-value">{{ fmt(osd.wind_direction) }}<small>°</small></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 定位与模式组 -->
        <div class="telemetry-group">
          <div class="group-title">定位与模式</div>
          <div class="telemetry-list">
            <div class="telemetry-item" :class="gpsClass">
              <div class="item-icon"><el-icon :size="14"><MapLocation /></el-icon></div>
              <div class="item-info">
                <span class="item-label">GPS 卫星</span>
                <span class="item-value">{{ osd.position_state?.gps_number || 0 }}<small>颗</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Aim /></el-icon></div>
              <div class="item-info">
                <span class="item-label">RTK 定位</span>
                <span class="item-value">{{ osd.position_state?.rtk_number || 0 }}<small>颗</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><DataLine /></el-icon></div>
              <div class="item-info">
                <span class="item-label">海拔高度</span>
                <span class="item-value">{{ fmt(osd.elevation) }}<small>m</small></span>
              </div>
            </div>
            <div class="telemetry-item">
              <div class="item-icon"><el-icon :size="14"><Cpu /></el-icon></div>
              <div class="item-info">
                <span class="item-label">飞行档位</span>
                <span class="item-value gear">{{ gearText }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- 中间：航线任务管理面板 -->
    <section class="task-panel surface-card">
      <!-- 顶部操作栏：当前任务 + 操作按钮 -->
      <div class="task-panel-header">
        <div class="task-current-section">
          <div class="task-current-label">
            <el-icon><Promotion /></el-icon>
            当前任务
          </div>
          <el-select
            v-model="selectedFileId"
            placeholder="选择航线"
            size="small"
            class="task-select"
            filterable
            clearable
          >
            <el-option
              v-for="file in waylineFiles"
              :key="file.id || file.wayline_id"
              :label="file.file_name || file.name || `航线-${file.id}`"
              :value="file.id || file.wayline_id"
            />
          </el-select>
          <!-- 当前运行任务的进度百分比 -->
          <span class="task-rate" v-if="currentRunningTask">
            {{ formatProgress(currentRunningTask.progress) }}%
          </span>
        </div>

        <!-- 进度条（参考 InspectionTask 的分段样式） -->
        <div class="task-progress-bar-wrap">
          <div class="task-progress-bar" :style="{ width: currentRunningTask ? (Number(currentRunningTask.progress || 0) * 100) + '%' : '0%' }"></div>
          <ul class="task-progress-tags">
            <li v-for="n in 20" :key="n"></li>
          </ul>
        </div>

        <!-- 统计卡片 -->
        <div class="task-stats-row">
          <div class="task-stat-card">
            <p class="stat-val">{{ waylineFiles.length }}</p>
            <p class="stat-txt">可用航线</p>
          </div>
          <div class="task-stat-card">
            <p class="stat-val">{{ runningTaskCount }}/{{ flightTasks.length }}</p>
            <p class="stat-txt">执行中/总任务</p>
          </div>
          <div class="task-stat-card">
            <p class="stat-val">{{ completedTaskCount }}</p>
            <p class="stat-txt">已完成</p>
          </div>
        </div>

        <!-- 操作按钮 + 天气 -->
        <div class="task-action-section">
          <div class="task-action-btns">
            <div
              class="task-start-btn"
              :class="{ disabled: !selectedFileId || !currentDeviceSn || createTaskLoading }"
              @click="handleCreateTask"
            >
              <el-icon><VideoPlay /></el-icon>
              <span>{{ createTaskLoading ? '下发中...' : '立即开始' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 任务列表 -->
      <div class="task-list-wrap">
        <div class="task-list-header">
          <span class="task-list-title">任务列表</span>
          <span class="task-list-count">共 {{ flightTasks.length }} 条</span>
        </div>

        <!-- 任务卡片列表 -->
        <div class="task-card-list" v-loading="taskLoading">
          <!-- 空状态 -->
          <div v-if="!taskLoading && flightTasks.length === 0" class="task-empty">
            <el-icon :size="32"><Promotion /></el-icon>
            <p>暂无飞行任务</p>
          </div>

          <!-- 任务卡片 -->
          <div
            v-for="task in paginatedTasks"
            :key="task.job_id"
            class="task-card"
            :class="taskStatusClass(task.status)"
          >
            <!-- 左侧：任务信息 -->
            <div class="task-card-info">
              <div class="task-card-name">{{ task.job_name || '未命名任务' }}</div>
              <div class="task-card-meta">
                <span class="meta-item">
                  <el-icon :size="12"><OfficeBuilding /></el-icon>
                  {{ task.dock_name || '--' }}
                </span>
                <span class="meta-item">
                  <el-icon :size="12"><Clock /></el-icon>
                  {{ formatTaskTime(task) }}
                </span>
              </div>
            </div>

            <!-- 中间：状态 + 进度 -->
            <div class="task-card-status">
              <span class="task-status-tag" :class="taskStatusClass(task.status)">
                {{ taskStatusText(task.status) }}
              </span>
              <!-- 执行中/已暂停显示进度条 -->
              <div v-if="task.status === 2 || task.status === 6" class="task-mini-progress">
                <div class="mini-progress-bar" :style="{ width: (Number(task.progress || 0) * 100) + '%' }"></div>
              </div>
              <span v-if="task.status === 2 || task.status === 6" class="task-progress-num">
                {{ formatProgress(task.progress) }}%
              </span>
              <span v-else-if="task.status === 3" class="task-progress-num done">100%</span>
            </div>

            <!-- 右侧：操作按钮 -->
            <div class="task-card-actions">
              <el-button
                v-if="task.status === 2"
                type="warning"
                size="small"
                plain
                @click="handlePauseTask(task.job_id)"
              >
                <el-icon><VideoPause /></el-icon>暂停
              </el-button>
              <el-button
                v-if="task.status === 6"
                type="success"
                size="small"
                plain
                @click="handleResumeTask(task.job_id)"
              >
                <el-icon><VideoPlay /></el-icon>恢复
              </el-button>
              <el-button
                v-if="task.status === 1 || task.status === 2 || task.status === 6"
                type="danger"
                size="small"
                plain
                @click="handleCancelTask(task.job_id)"
              >
                <el-icon><Close /></el-icon>取消
              </el-button>
              <!-- 已完成/已取消/失败 显示状态图标 -->
              <span v-if="task.status === 3" class="task-done-icon">
                <el-icon :size="18"><CircleCheck /></el-icon>
              </span>
              <span v-if="task.status === 4" class="task-cancel-icon">
                <el-icon :size="18"><CircleClose /></el-icon>
              </span>
              <span v-if="task.status === 5" class="task-fail-icon">
                <el-icon :size="18"><WarningFilled /></el-icon>
              </span>
            </div>
          </div>
        </div>

        <!-- 分页控件 -->
        <div class="task-pagination" v-if="flightTasks.length > taskPageSize">
          <button
            class="page-btn"
            :disabled="taskPage <= 1"
            @click="changeTaskPage(taskPage - 1)"
          >
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <span class="page-info">{{ taskPage }} / {{ totalTaskPages }}</span>
          <button
            class="page-btn"
            :disabled="taskPage >= totalTaskPages"
            @click="changeTaskPage(taskPage + 1)"
          >
            <el-icon><ArrowRight /></el-icon>
          </button>
        </div>
      </div>
    </section>

    <!-- 底部：地图 + 视频 左右排版 -->
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

        </div>

        <!-- 图注 -->
        <div class="map-legend">
          <div class="legend-item">
            <img src="/starting-point.png" alt="起始点" class="legend-icon-img" />
            <span class="legend-label">起始点</span>
          </div>
          <div class="legend-item">
            <img src="/waypoint.png" alt="航点" class="legend-icon-img" />
            <span class="legend-label">航点</span>
          </div>
          <div class="legend-item">
            <img src="/drone-icon.png" alt="无人机" class="legend-icon-img" />
            <span class="legend-label">无人机</span>
          </div>
          <div class="legend-item">
            <svg width="24" height="10" class="legend-line-svg">
              <line x1="0" y1="5" x2="20" y2="5" stroke="#48d8ff" stroke-width="3" stroke-dasharray="6,3" />
            </svg>
            <span class="legend-label">当前路径</span>
          </div>
        </div>
      </div>

      <!-- 右侧：视频 -->
      <div class="video-area">
        <div v-if="selectedDevice?.status === 'online'" class="video-stage">
          <video ref="liveVideoRef" class="video-stream" autoplay muted playsinline></video>
          <div v-if="!isLive" class="video-placeholder">
            <el-icon :size="36"><VideoCamera /></el-icon>
            <el-button class="start-btn" :loading="liveLoading" :disabled="liveLoading" @click="handleStartLive()">
              {{ liveLoading ? '连接中...' : '开启实时画面' }}
            </el-button>
          </div>
          <div v-if="liveLoading" class="video-loading">
            <el-icon class="is-loading" :size="28"><Loading /></el-icon>
            <p style="color: #8ecae6; margin-top: 10px; font-size: 13px;">正在连接视频流...</p>
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
  VideoPlay, VideoPause, Close, OfficeBuilding, Clock,
  CircleCheck, CircleClose, WarningFilled, ArrowLeft, ArrowRight,
} from '@element-plus/icons-vue'
import {
  dijLogin, getDroneDevices, getBoundDevices, getCurrentWorkspace,
  sendPayloadCommand, getDeviceHmsDetail, startLiveStream, stopLiveStream, getLiveCapacity,
  getWaylineFiles, getFlightJobs, createFlightTask, pauseFlightTask, resumeFlightTask, cancelFlightTask,
  startSimulation, stopSimulation,
} from '@/api/drone'
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

// ========== 航线任务管理 ==========
const waylineFiles = ref([])           // 航线文件列表（从数据库获取）
const flightTasks = ref([])           // 飞行任务列表
const taskLoading = ref(false)        // 任务列表加载中
const taskPage = ref(1)              // 当前页码
const taskPageSize = 3               // 每页条数
const createTaskLoading = ref(false)  // 创建任务加载中
const selectedFileId = ref('')        // 选中的航线文件ID
const taskPagination = ref({ page: 1, page_size: 10, total: 0 })

// 任务状态文本映射
const TASK_STATUS = {
  1: { text: '待执行', cls: 'status-wait' },
  2: { text: '执行中', cls: 'status-running' },
  3: { text: '已完成', cls: 'status-success' },
  4: { text: '已取消', cls: 'status-cancel' },
  5: { text: '失败', cls: 'status-fail' },
  6: { text: '已暂停', cls: 'status-paused' },
}

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

// ========== 地图标点 ==========
const markerPoints = ref([])  // 标记点列表
const showCoordPanel = ref(false)  // 是否显示坐标面板
const coordPanelX = ref(0)  // 面板位置
const coordPanelY = ref(0)

// 标点模式（按住 Shift 键点击标点）
function onMapClick(e) {
  // 只在非拖拽状态下响应
  if (isDragging) return

  const mapArea = mapAreaRef.value
  if (!mapArea) return

  // 获取地图容器的边界
  const rect = mapArea.getBoundingClientRect()

  // 计算点击位置相对于地图容器的像素坐标
  const clickX = e.clientX - rect.left
  const clickY = e.clientY - rect.top

  // 考虑缩放和平移，计算相对于原始地图的坐标
  // 地图实际显示尺寸（考虑缩放）
  const mapImg = mapArea.querySelector('.map-image')
  if (!mapImg) return

  const imgRect = mapImg.getBoundingClientRect()
  const imgNaturalWidth = mapImg.naturalWidth || 1920
  const imgNaturalHeight = mapImg.naturalHeight || 1080

  // 计算点击位置在原始图片上的百分比坐标 (0-100)
  const percentX = ((e.clientX - imgRect.left) / imgRect.width) * 100
  const percentY = ((e.clientY - imgRect.top) / imgRect.height) * 100

  // 限制在有效范围内
  if (percentX < 0 || percentX > 100 || percentY < 0 || percentY > 100) return

  // 计算在原始图片上的像素坐标（以左上角为原点）
  const pixelX = Math.round((percentX / 100) * imgNaturalWidth)
  const pixelY = Math.round((percentY / 100) * imgNaturalHeight)

  // 添加标记点
  const newPoint = {
    id: Date.now(),
    x: percentX,
    y: percentY,
    pixelX,
    pixelY,
    label: `P${markerPoints.value.length + 1}`,
  }

  markerPoints.value.push(newPoint)
  ElMessage.success(`已标记点 ${newPoint.label}: (${pixelX}, ${pixelY})`)
}

// 删除标记点
function removeMarkerPoint(id) {
  markerPoints.value = markerPoints.value.filter(p => p.id !== id)
}

// 清空所有标记点
function clearMarkerPoints() {
  markerPoints.value = []
}

// 导出坐标
function exportCoordinates() {
  if (markerPoints.value.length === 0) {
    ElMessage.warning('暂无标记点')
    return
  }

  const text = markerPoints.value.map(p =>
    `${p.label}: (${p.pixelX}, ${p.pixelY})`
  ).join('\n')

  // 创建临时 textarea 复制文本
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)

  try {
    const success = document.execCommand('copy')
    if (success) {
      ElMessage.success('坐标已复制到剪贴板')
    } else {
      ElMessage.error('复制失败，请手动复制')
    }
  } catch (err) {
    ElMessage.error('复制失败，请手动复制')
  } finally {
    document.body.removeChild(textarea)
  }
}

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

// 无人机位置（百分比坐标，用于模拟飞行）
const dronePosition = ref({ x: 94.9, y: 24.9 })

// 无人机在地图上的位置
const droneOnMapStyle = computed(() => {
  // 优先使用模拟飞行位置
  if (dronePosition.value) {
    return { left: `${dronePosition.value.x}%`, top: `${dronePosition.value.y}%` }
  }
  // 有 GPS 数据时使用真实位置
  const lat = Number(osd.value.latitude) || 0
  const lng = Number(osd.value.longitude) || 0
  if (lat && lng) {
    const lngMin = 110.72, lngMax = 110.80
    const latMin = 23.96, latMax = 24.02
    const x = Math.max(0, Math.min(100, ((lng - lngMin) / (lngMax - lngMin)) * 100))
    const y = Math.max(0, Math.min(100, ((latMax - lat) / (latMax - latMin)) * 100))
    return { left: `${x}%`, top: `${y}%` }
  }
  // 默认在起始点
  return { left: '94.9%', top: '24.9%' }
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

  // 加载航线文件和任务列表
  await Promise.all([fetchWaylineFiles(), fetchFlightTasks()])
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
        // 解析电池数据（可能是 batteries 数组格式）
        let batteryData = data.battery || {}
        if (batteryData.batteries && batteryData.batteries.length > 0) {
          const firstBattery = batteryData.batteries[0]
          batteryData = {
            capacity_percent: firstBattery.capacity_percent || 0,
            landing_power: firstBattery.landing_power || 0,
            remain_flight_time: firstBattery.remain_flight_time || 0,
            return_home_power: firstBattery.return_home_power || 0,
          }
        }

        osd.value = {
          ...osd.value,
          ...data,
          battery: batteryData,
          position_state: data.position_state || osd.value.position_state,
        }
        console.log('[OSD] device_osd 解析后:', {
          elevation: osd.value.elevation,
          battery: osd.value.battery?.capacity_percent,
          attitude_head: osd.value.attitude_head,
        })
      }
    },
    onGatewayOsd(data) {
      if (data) {
        gatewayOsd.value = { ...gatewayOsd.value, ...data }
        // 从 gateway_osd 提取位置和高度信息到 osd
        if (data.latitude && data.longitude) {
          osd.value.latitude = data.latitude
          osd.value.longitude = data.longitude
        }
        if (data.height !== undefined) {
          osd.value.height = data.height
        }
        console.log('[OSD] gateway_osd 解析后:', {
          lat: gatewayOsd.value.latitude,
          lng: gatewayOsd.value.longitude,
          height: gatewayOsd.value.height,
          battery: gatewayOsd.value.capacity_percent,
        })
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
    onFlightTaskProgress(data) {
      // 实时更新任务进度
      if (data?.job_id) {
        const idx = flightTasks.value.findIndex(t => t.job_id === data.job_id)
        if (idx !== -1) {
          const task = flightTasks.value[idx]
          task.progress = data.progress ?? task.progress
          task.status = data.status ?? task.status
          task.media_count = data.media_count ?? task.media_count
          task.uploaded_count = data.uploaded_count ?? task.uploaded_count
          // 任务结束时刷新列表
          if (data.status === 3 || data.status === 4 || data.status === 5) {
            setTimeout(() => fetchFlightTasks(), 2000)
          }
        }
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

// ========== 航线任务管理方法 ==========

// 航线定义（用于模拟飞行演示，传递给后端）
const ROUTES = {
  '禁渔航线': {
    name: '禁渔航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 47.4, y: 58.1, label: '禁渔点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ]
  },
  '禁涉水航线': {
    name: '禁涉水航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 96.3, y: 54.3, label: '禁涉水点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ]
  }
}

/** 根据航线名称获取航线数据 */
function getRouteByFileName(fileName) {
  if (ROUTES[fileName]) return ROUTES[fileName]
  for (const key of Object.keys(ROUTES)) {
    if (fileName.includes(key) || key.includes(fileName)) {
      return ROUTES[key]
    }
  }
  return null
}

// 当前 SSE 连接
let currentEventSource = null

/** 从 localStorage 加载任务列表 */
/** 从数据库加载航线文件列表 */
async function fetchWaylineFiles() {
  if (!workspaceId.value) return
  try {
    const res = await getWaylineFiles(workspaceId.value, { page: 1, page_size: 50 })
    waylineFiles.value = res.data?.list || res.data || []
    console.log('[航线] 加载航线文件:', waylineFiles.value.length, '条')
  } catch (err) {
    console.warn('[航线] 获取航线文件失败:', err)
    waylineFiles.value = []
  }
}

/** 加载飞行任务列表 */
async function fetchFlightTasks() {
  taskLoading.value = true
  try {
    if (workspaceId.value) {
      const res = await getFlightJobs(workspaceId.value, {
        page: taskPagination.value.page,
        page_size: taskPagination.value.page_size,
      })
      flightTasks.value = res.data?.list || res.data || []
      taskPagination.value.total = flightTasks.value.length
    }
  } catch (err) {
    console.warn('从后端获取任务列表失败:', err)
    flightTasks.value = []
  }
  taskLoading.value = false
}

/** 创建立即执行任务 */
async function handleCreateTask() {
  if (!selectedFileId.value) return ElMessage.warning('请先选择航线')

  const selectedFile = waylineFiles.value.find(f => f.id === selectedFileId.value || f.wayline_id === selectedFileId.value)
  const routeName = selectedFile?.file_name || selectedFile?.name || '未知航线'

  const route = getRouteByFileName(routeName)
  if (!route) return ElMessage.warning(`航线"${routeName}"暂不支持模拟飞行`)

  createTaskLoading.value = true
  const taskName = `${routeName}_${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`

  const drone = selectedDevice.value
  const dockSn = drone?.parent_sn || drone?.device_sn || currentDeviceSn.value || 'DOCK_DEFAULT'

  // 调用后端API保存任务到数据库
  let jobId = null
  try {
    const res = await createFlightTask(workspaceId.value, {
      name: taskName, file_id: selectedFileId.value, dock_sn: dockSn,
      wayline_type: 0, task_type: 0, rth_altitude: 100, out_of_control_action: 0,
    })
    if (res.data?.job_id) jobId = res.data.job_id
  } catch (err) {
    console.warn('[任务] 保存到数据库失败:', err)
    ElMessage.error('创建任务失败: ' + (err.message || '未知错误'))
    createTaskLoading.value = false
    return
  }

  // 刷新任务列表（从后端获取正确的 dock_name）
  await fetchFlightTasks()

  // 调用后端模拟飞行接口（SSE）
  try {
    console.log('[模拟] 启动后端模拟飞行...')
    await startSimulation({
      job_id: jobId,
      route_name: routeName,
      waypoints: route.waypoints,
      duration: 60000,
    })
    // 连接 SSE 接收位置更新
    connectSimulationSSE(jobId)
  } catch (err) {
    console.error('[模拟] 启动模拟失败:', err)
    ElMessage.error('启动模拟飞行失败')
  }

  createTaskLoading.value = false
}

/** 连接 SSE 接收模拟飞行位置更新 */
function connectSimulationSSE(jobId) {
  // 关闭之前的 SSE
  if (currentEventSource) {
    currentEventSource.close()
    currentEventSource = null
  }

  const token = localStorage.getItem('dij_token')
  const sseUrl = `/dij-api/manage/api/v1/simulation/events/${jobId}?x-auth-token=${encodeURIComponent(token || '')}`
  console.log('[SSE] 连接:', sseUrl)

  const es = new EventSource(sseUrl)
  currentEventSource = es

  es.addEventListener('connected', (e) => {
    console.log('[SSE] 已连接:', e.data)
  })

  es.addEventListener('position', (e) => {
    try {
      const data = JSON.parse(e.data)
      // 更新无人机位置
      dronePosition.value = { x: data.x, y: data.y }

      // 更新任务进度
      const task = flightTasks.value.find(t => t.job_id === jobId)
      if (task) {
        task.progress = data.progress / 100
      }
    } catch (err) {
      console.warn('[SSE] 解析位置数据失败:', err)
    }
  })

  es.addEventListener('complete', (e) => {
    console.log('[SSE] 飞行完成:', e.data)
    const task = flightTasks.value.find(t => t.job_id === jobId)
    if (task) {
      task.status = 3
      task.progress = 1
    }
    es.close()
    currentEventSource = null
  })

  es.addEventListener('error', (e) => {
    if (e.data) {
      console.error('[SSE] 错误:', e.data)
    }
    // EventSource 会在连接关闭时触发 error，这是正常的
    if (es.readyState === EventSource.CLOSED) {
      console.log('[SSE] 连接已关闭')
      currentEventSource = null
    }
  })

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      console.log('[SSE] 连接已关闭')
      currentEventSource = null
    }
  }
}

/** 停止当前模拟飞行 */
async function stopCurrentSimulation(jobId) {
  // 关闭 SSE 连接
  if (currentEventSource) {
    currentEventSource.close()
    currentEventSource = null
  }
  // 调用后端停止模拟（忽略错误，可能已经完成）
  try {
    await stopSimulation(jobId)
  } catch (err) {
    // 忽略，模拟可能已结束
  }
}

/** 暂停任务 */
async function handlePauseTask(jobId) {
  const task = flightTasks.value.find(t => t.job_id === jobId)
  if (!task || task.status !== 2) return

  // 更新本地状态
  task.status = 6 // 已暂停

  // 停止当前模拟飞行
  await stopCurrentSimulation(jobId)
}

/** 恢复任务 */
async function handleResumeTask(jobId) {
  const task = flightTasks.value.find(t => t.job_id === jobId)
  if (!task || task.status !== 6) return

  // 更新本地状态
  task.status = 2 // 执行中

  // 重新启动模拟飞行，从上次暂停的进度继续
  const routeName = task.file_name
  const route = getRouteByFileName(routeName)
  if (route) {
    try {
      await startSimulation({
        job_id: jobId,
        route_name: routeName,
        waypoints: route.waypoints,
        duration: 60000,
        start_progress: task.progress || 0, // 传递当前进度
      })
      connectSimulationSSE(jobId)
    } catch (err) {
      console.warn('[模拟] 恢复模拟失败:', err)
    }
  }
}

/** 取消任务 */
async function handleCancelTask(jobId) {
  const task = flightTasks.value.find(t => t.job_id === jobId)
  if (!task || task.status === 3 || task.status === 4 || task.status === 5) return

  // 调用后端API取消任务
  try {
    await cancelFlightTask(workspaceId.value, jobId)
  } catch (err) {
    console.warn('[任务] 取消任务失败:', err)
  }

  // 更新本地状态
  task.status = 4 // 已取消

  // 停止当前模拟飞行
  await stopCurrentSimulation(jobId)
}

/** 任务状态文本 */
function taskStatusText(status) {
  return TASK_STATUS[status]?.text || `未知(${status})`
}

/** 任务状态样式类 */
function taskStatusClass(status) {
  return TASK_STATUS[status]?.cls || ''
}

/** 格式化任务进度百分比 */
function formatProgress(progress) {
  if (progress == null || progress === undefined) return '0'
  return Math.round(Number(progress) * 100).toString()
}

/** 格式化任务时间 */
function formatTaskTime(task) {
  const time = task.create_time || task.execute_time || task.start_time || task.begin_time || task.beginTime
  if (!time) return '--'
  try {
    // LocalDateTime 格式 "2026-07-27T12:44:37" 或时间戳
    const d = new Date(time)
    if (isNaN(d.getTime())) return '--'
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return '--'
  }
}

/** 当前正在执行的任务 */
const currentRunningTask = computed(() =>
  flightTasks.value.find(t => t.status === 2) || null
)

/** 执行中的任务数量 */
const runningTaskCount = computed(() =>
  flightTasks.value.filter(t => t.status === 2).length
)

/** 已完成的任务数量 */
const completedTaskCount = computed(() =>
  flightTasks.value.filter(t => t.status === 3).length
)

/** 分页后的任务列表 */
const paginatedTasks = computed(() => {
  const start = (taskPage.value - 1) * taskPageSize
  return flightTasks.value.slice(start, start + taskPageSize)
})

/** 总页数 */
const totalTaskPages = computed(() =>
  Math.max(1, Math.ceil(flightTasks.value.length / taskPageSize))
)

/** 切换页码 */
function changeTaskPage(page) {
  if (page < 1 || page > totalTaskPages.value) return
  taskPage.value = page
}

/** 开始直播（带重试机制） */
async function handleStartLive() {
  if (!currentDeviceSn.value) return ElMessage.warning('请先选择无人机')
  if (liveLoading.value || isLive.value) return // 防止重复点击

  liveLoading.value = true
  const maxRetries = 3
  let retryCount = 0

  while (retryCount < maxRetries) {
    try {
      // 1. 获取直播能力，找到当前无人机的摄像头 index
      console.log(`[直播] 获取直播能力... (尝试 ${retryCount + 1}/${maxRetries})`)
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

      // 3. 等待流就绪（给服务器一点时间准备）
      console.log('[直播] 等待流就绪...')
      await new Promise(resolve => setTimeout(resolve, 2000))

      // 4. 通过 MediaMTX WHEP 协议播放 WebRTC 流
      const videoEl = liveVideoRef.value
      if (!videoEl) throw new Error('视频元素不存在')
      const streamName = `${currentDeviceSn.value}-88-0-0`
      console.log('[直播] 建立 WHEP 连接, streamName:', streamName)
      await connectMediamtxWebRTC(videoEl, streamName)

      isLive.value = true
      break // 成功，退出重试循环
    } catch (err) {
      retryCount++
      console.error(`[直播] 第 ${retryCount} 次尝试失败:`, err.message)

      if (retryCount >= maxRetries) {
        console.error(`[直播] 启动失败，已重试 ${maxRetries} 次`)
        break
      }

      // 等待后重试
      console.log(`[直播] 2秒后重试...`)
      await new Promise(resolve => setTimeout(resolve, 2000))
    }
  }

  liveLoading.value = false
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
  if (!isLive.value) return // 防止重复点击

  console.log('[直播] 正在关闭...')
  isLive.value = false // 立即更新 UI 状态

  // 1. 断开 WebRTC
  if (peerConnection) {
    try {
      peerConnection.close()
      console.log('[直播] WebRTC 已关闭')
    } catch (e) {
      console.warn('[直播] 关闭 WebRTC 失败:', e)
    }
    peerConnection = null
  }

  // 2. 清空视频元素
  if (liveVideoRef.value) {
    liveVideoRef.value.srcObject = null
  }

  // 3. 调用 dij 后端停止推流
  try {
    if (currentVideoId) {
      await stopLiveStream({ video_id: currentVideoId })
      console.log('[直播] 推流已停止')
      currentVideoId = ''
    }
  } catch (err) {
    console.warn('[直播] 停止推流失败:', err)
  }
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
  // 关闭 SSE 连接
  if (currentEventSource) {
    currentEventSource.close()
    currentEventSource = null
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
  grid-template-columns: 180px 1fr 2fr;
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

/* 遥测数据区域 */
.telemetry-area {
  padding: 10px 14px;
  display: flex;
  gap: 10px;
  align-items: stretch;
}

/* 数据分组 */
.telemetry-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(3, 18, 29, 0.4);
  border: 1px solid rgba(87, 165, 199, 0.1);
}
.group-title {
  font-size: 10px;
  color: #4a7a9b;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(87, 165, 199, 0.08);
}

/* 数据列表 */
.telemetry-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.telemetry-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 4px;
  border-radius: 4px;
  transition: background 0.2s;
}
.telemetry-item:hover {
  background: rgba(72, 216, 255, 0.04);
}

/* 图标 */
.item-icon {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: rgba(72, 216, 255, 0.08);
  color: var(--cyan);
  flex-shrink: 0;
}

/* 信息区 */
.item-info {
  flex: 1;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  min-width: 0;
}
.item-label {
  font-size: 11px;
  color: #607f94;
  white-space: nowrap;
}
.item-value {
  font-size: 14px;
  font-weight: 700;
  font-family: monospace;
  color: #a9c9da;
  white-space: nowrap;
}
.item-value small {
  font-size: 10px;
  font-weight: 400;
  color: #4a7a9b;
  margin-left: 1px;
}
.item-value.gear {
  font-size: 16px;
  color: var(--cyan);
  font-weight: 800;
}

/* 电量条 */
.battery-bar {
  width: 36px;
  height: 4px;
  border-radius: 2px;
  background: rgba(75, 112, 132, 0.2);
  overflow: hidden;
  flex-shrink: 0;
}
.battery-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #67c23a, #52e5bd);
  transition: width 0.5s ease;
}
.battery-fill.dock {
  background: linear-gradient(90deg, #35c8ea, #52e5bd);
}

/* 电量状态颜色 */
.telemetry-item.good .item-icon { color: #67c23a; background: rgba(103, 194, 58, 0.1); }
.telemetry-item.good .item-value { color: #67c23a; }
.telemetry-item.medium .item-icon { color: #e6a23c; background: rgba(230, 162, 60, 0.1); }
.telemetry-item.medium .item-value { color: #e6a23c; }
.telemetry-item.low .item-icon { color: #f56c6c; background: rgba(245, 108, 108, 0.1); }
.telemetry-item.low .item-value { color: #f56c6c; }
.telemetry-item.critical .item-icon { color: #ff4d4f; background: rgba(255, 77, 79, 0.1); }
.telemetry-item.critical .item-value { color: #ff4d4f; }

/* GPS 信号状态 */
.telemetry-item.excellent .item-icon { color: #67c23a; }
.telemetry-item.good .item-icon { color: #67c23a; }
.telemetry-item.fair .item-icon { color: #e6a23c; }
.telemetry-item.poor .item-icon { color: #f56c6c; }

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
  position: relative;
  will-change: transform;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  transform: translateZ(0);
}
.map-image {
  width: 100%;
  height: 100%;
  object-fit: fill;
  display: block;
  pointer-events: none;
  will-change: transform;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}

/* 固定航点 */
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
.fixed-point-icon {
  width: 22px;
  height: 22px;
  object-fit: contain;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
}
.fixed-point-label {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: transparent;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: monospace;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8), 0 0 8px rgba(0, 0, 0, 0.5);
}

/* 无人机标记 */
.drone-marker { position: absolute; transform: translate(-50%, -50%); z-index: 10; pointer-events: none; }
.marker-pulse { position: absolute; top: 50%; left: 50%; width: 36px; height: 36px; transform: translate(-50%, -50%); border-radius: 50%; background: rgba(255, 93, 108, 0.3); animation: pulse 2s infinite; }
.marker-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 28px;
  height: 28px;
  transform: translate(-50%, -50%);
  z-index: 2;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
  object-fit: contain;
}
.marker-label { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); padding: 2px 8px; border-radius: 4px; background: rgba(0, 0, 0, 0.7); color: #fff; font-size: 11px; font-family: monospace; white-space: nowrap; }
@keyframes pulse { 0% { transform: translate(-50%, -50%) scale(0.8); opacity: 1; } 100% { transform: translate(-50%, -50%) scale(2); opacity: 0; } }

/* 图注容器 */
.map-legend {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  gap: 14px;
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(8, 20, 35, 0.25);
  border: 1px solid rgba(93, 184, 225, 0.1);
  font-size: 11px;
  color: #8ecae6;
  z-index: 20;
  pointer-events: none;
  backdrop-filter: blur(4px);
  align-items: center;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}
.legend-label {
  white-space: nowrap;
  color: #a9c9da;
  font-size: 11px;
}
.legend-line-svg {
  flex-shrink: 0;
}

/* 图注图片 */
.legend-icon-img {
  width: 18px;
  height: 18px;
  object-fit: contain;
  flex-shrink: 0;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
}

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

/* 航线任务管理面板 */
.task-panel {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

/* 顶部操作栏 */
.task-panel-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(93, 184, 225, 0.12);
  flex-shrink: 0;
  flex-wrap: wrap;
}

/* 当前任务选择区 */
.task-current-section {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.task-current-label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--cyan);
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
}
.task-select {
  width: 220px;
}
/* select 外框 - 覆盖 el-select__wrapper */
.task-select :deep(.el-select__wrapper) {
  background: rgba(10, 30, 48, 0.85) !important;
  border: 1px solid rgba(93, 184, 225, 0.3) !important;
  box-shadow: none !important;
  border-radius: 6px;
}
.task-select :deep(.el-select__wrapper:hover) {
  border-color: rgba(93, 184, 225, 0.5) !important;
}
.task-select :deep(.el-select__wrapper.is-focused) {
  border-color: #48d8ff !important;
  box-shadow: none !important;
}
/* 输入文字颜色 */
.task-select :deep(.el-select__selected-item) {
  color: #e9f7ff !important;
  font-size: 15px;
}
.task-select :deep(.el-select__placeholder) {
  color: #4a7a9b !important;
  font-size: 15px;
}
.task-select :deep(.el-select__placeholder.is-transparent) {
  color: #3a5a6d !important;
  font-size: 15px;
}
/* 箭头图标 */
.task-select :deep(.el-select__caret) {
  color: #4a7a9b !important;
}
/* 选中标签 */
.task-select :deep(.el-select__tags) {
  background: transparent !important;
}
.task-select :deep(.el-tag) {
  background: rgba(72, 216, 255, 0.15) !important;
  border-color: rgba(72, 216, 255, 0.3) !important;
  color: #e9f7ff !important;
}
.task-rate {
  font-size: 22px;
  font-weight: 800;
  font-family: monospace;
  color: var(--cyan);
  min-width: 50px;
  text-align: right;
}

/* 分段进度条（参考 InspectionTask） */
.task-progress-bar-wrap {
  flex: 1;
  min-width: 120px;
  position: relative;
  height: 18px;
  background: rgba(30, 58, 88, 0.6);
  border-radius: 3px;
  overflow: hidden;
}
.task-progress-bar {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #00d2ff, #52e5bd);
  border-radius: 3px;
  transition: width 0.6s ease;
  z-index: 1;
}
.task-progress-tags {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  margin: 0;
  padding: 0;
  list-style: none;
  z-index: 2;
}
.task-progress-tags li {
  flex: 1;
  border-right: 1px solid rgba(0, 0, 0, 0.15);
}
.task-progress-tags li:last-child {
  border-right: none;
}

/* 统计卡片 */
.task-stats-row {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.task-stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 14px;
  border-radius: 6px;
  background: rgba(3, 18, 29, 0.5);
  border: 1px solid rgba(87, 165, 199, 0.12);
  min-width: 70px;
}
.stat-val {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  font-family: monospace;
  color: #a9c9da;
  line-height: 1.3;
}
.stat-txt {
  margin: 0;
  font-size: 10px;
  color: #607f94;
  white-space: nowrap;
}

/* 操作按钮区 */
.task-action-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-left: auto;
}
.task-action-btns {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 立即开始按钮（参考 InspectionTask 的风格） */
.task-start-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 8px;
  background: linear-gradient(105deg, #35c8ea, #52e5bd);
  color: #061b23;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.task-start-btn:hover {
  opacity: 0.85;
  transform: scale(1.02);
}
.task-start-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

/* 任务列表区域 */
.task-list-wrap {
  flex: 1;
  overflow: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.task-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(93, 184, 225, 0.08);
  flex-shrink: 0;
}
.task-list-title {
  font-size: 15px;
  font-weight: 600;
  color: #8ecae6;
}
.task-list-count {
  font-size: 11px;
  color: #556;
}

/* 任务卡片列表 */
.task-card-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 空状态 */
.task-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #3a5a6d;
}
.task-empty p {
  margin: 8px 0 0;
  font-size: 13px;
}

/* 任务卡片 */
.task-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(3, 18, 29, 0.5);
  border: 1px solid rgba(87, 165, 199, 0.1);
  transition: all 0.2s;
}
.task-card:hover {
  background: rgba(72, 216, 255, 0.04);
  border-color: rgba(87, 165, 199, 0.2);
}
/* 执行中的卡片左边框高亮 */
.task-card.status-running {
  border-left: 3px solid var(--cyan);
}
.task-card.status-paused {
  border-left: 3px solid #ffbd65;
}
.task-card.status-success {
  border-left: 3px solid #51e6be;
}
.task-card.status-fail {
  border-left: 3px solid #ff5d6c;
}

/* 卡片左侧：任务信息 */
.task-card-info {
  flex: 1;
  min-width: 0;
}
.task-card-name {
  font-size: 13px;
  font-weight: 600;
  color: #c8dce8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #5a7a8d;
}
.meta-item .el-icon {
  color: #4a7a9b;
}

/* 卡片中间：状态 + 进度 */
.task-card-status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* 任务状态标签 */
.task-status-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.status-wait {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}
.status-running {
  background: rgba(72, 216, 255, 0.15);
  color: var(--cyan);
  animation: blink 1.5s infinite;
}
.status-success {
  background: rgba(81, 230, 190, 0.15);
  color: #51e6be;
}
.status-cancel {
  background: rgba(127, 155, 176, 0.15);
  color: #7f9bb0;
}
.status-fail {
  background: rgba(255, 93, 108, 0.15);
  color: #ff5d6c;
}
.status-paused {
  background: rgba(255, 189, 101, 0.15);
  color: #ffbd65;
}

/* 迷你进度条 */
.task-mini-progress {
  width: 60px;
  height: 4px;
  border-radius: 2px;
  background: rgba(75, 112, 132, 0.2);
  overflow: hidden;
}
.mini-progress-bar {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, #35c8ea, #52e5bd);
  transition: width 0.6s ease;
}
.task-progress-num {
  font-size: 12px;
  font-family: monospace;
  font-weight: 700;
  color: var(--cyan);
  min-width: 36px;
  text-align: right;
}
.task-progress-num.done {
  color: #51e6be;
}

/* 卡片右侧：操作按钮 */
.task-card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.task-card-actions .el-button {
  font-size: 12px;
}
.task-done-icon { color: #51e6be; }
.task-cancel-icon { color: #7f9bb0; }
.task-fail-icon { color: #ff5d6c; }

/* 分页控件 */
.task-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 12px;
  border-top: 1px solid rgba(93, 184, 225, 0.1);
  flex-shrink: 0;
}
.page-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  border: 1px solid rgba(93, 184, 225, 0.2);
  background: rgba(3, 18, 29, 0.5);
  color: #8ecae6;
  cursor: pointer;
  transition: all 0.2s;
}
.page-btn:hover:not(:disabled) {
  background: rgba(72, 216, 255, 0.1);
  border-color: rgba(72, 216, 255, 0.3);
}
.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.page-info {
  font-size: 12px;
  color: #8ecae6;
  font-family: monospace;
}

/* 任务状态标签 */
.task-status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.status-wait {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}
.status-running {
  background: rgba(72, 216, 255, 0.15);
  color: var(--cyan);
  animation: blink 1.5s infinite;
}
.status-success {
  background: rgba(81, 230, 190, 0.15);
  color: #51e6be;
}
.status-cancel {
  background: rgba(127, 155, 176, 0.15);
  color: #7f9bb0;
}
.status-fail {
  background: rgba(255, 93, 108, 0.15);
  color: #ff5d6c;
}
.status-paused {
  background: rgba(255, 189, 101, 0.15);
  color: #ffbd65;
}


@media (max-width: 900px) {
  .main-workspace { grid-template-columns: 1fr; }
  .map-area { border-right: none; border-radius: 12px 12px 0 0; border-bottom: 1px solid rgba(93, 184, 225, 0.17); }
  .video-area { border-radius: 0 0 12px 12px; min-height: 300px; }
  .bar-right { display: none; }
  .bottom-bar { flex-wrap: wrap; }
  .task-panel-header { flex-direction: column; align-items: flex-start; }
  .task-action-section { margin-left: 0; width: 100%; justify-content: space-between; }
  .task-progress-bar-wrap { width: 100%; }
}
</style>

<!-- 下拉弹窗全局样式（teleport 到 body，scoped 不生效） -->
<style>
/* 强制覆盖 Element Plus 下拉框深色主题 - 使用最高优先级 */
.el-select-dropdown,
.el-popper.is-light,
.el-select__popper {
  background-color: rgba(10, 30, 48, 0.95) !important;
  background: rgba(10, 30, 48, 0.95) !important;
  border-color: rgba(93, 184, 225, 0.3) !important;
  border: 1px solid rgba(93, 184, 225, 0.3) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5) !important;
}

.el-select-dropdown__item {
  color: #c8dce8 !important;
  background-color: transparent !important;
  background: transparent !important;

  &.hover,
  &:hover {
    background-color: rgba(72, 216, 255, 0.1) !important;
    background: rgba(72, 216, 255, 0.1) !important;
    color: #e9f7ff !important;
  }

  &.selected,
  &.is-selected {
    color: #48d8ff !important;
    font-weight: 700;
  }
}

.el-select-dropdown__empty {
  color: #4a7a9b !important;
  background-color: rgba(10, 30, 48, 0.95) !important;
  background: rgba(10, 30, 48, 0.95) !important;
}

.el-popper.is-light .el-popper__arrow::before {
  background-color: rgba(10, 30, 48, 0.95) !important;
  background: rgba(10, 30, 48, 0.95) !important;
  border-color: rgba(93, 184, 225, 0.3) !important;
}

/* select 框强制覆盖 */
.el-select .el-select__wrapper {
  background-color: rgba(10, 30, 48, 0.85) !important;
  background: rgba(10, 30, 48, 0.85) !important;
  border-color: rgba(93, 184, 225, 0.3) !important;
  border: 1px solid rgba(93, 184, 225, 0.3) !important;
  box-shadow: none !important;
}
.el-select .el-select__wrapper:hover {
  border-color: rgba(93, 184, 225, 0.5) !important;
}
.el-select .el-select__wrapper.is-focused {
  border-color: #48d8ff !important;
  box-shadow: none !important;
}
.el-select .el-select__selected-item {
  color: #e9f7ff !important;
}
.el-select .el-select__placeholder {
  color: #4a7a9b !important;
}
.el-select .el-select__caret {
  color: #4a7a9b !important;
}
</style>