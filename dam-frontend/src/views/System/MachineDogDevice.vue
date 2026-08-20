<template>
  <div class="machine-dog-page">
    <header class="page-header">
      <div>
        <h2>机器狗设备</h2>
        <p>选择机器狗进入测试，查看实时监控与巡检任务</p>
      </div>
      <div class="status-summary compact-summary" aria-label="机器狗设备统计">
        <div class="metric"><i class="dot total"></i><strong>{{ machineDogs.length }}</strong><span>总数</span></div>
        <div class="metric"><i class="dot online"></i><strong>{{ dogOnlineCount }}</strong><span>在线</span></div>
        <div class="metric"><i class="dot offline"></i><strong>{{ dogOfflineCount }}</strong><span>离线</span></div>
      </div>
    </header>

    <section class="resource-list-card dog-resource-card">
      <header class="tab-header">
        <h3>机器狗列表</h3>
      </header>
      <div class="device-list">
        <div class="device-list-header-row">
          <div class="col-name">设备名称</div>
          <div class="col-desc">设备型号</div>
          <div class="col-dock">当前位置</div>
          <div class="col-runtime">电量</div>
          <div class="col-status">状态</div>
          <div class="col-actions">操作</div>
        </div>
        <article v-for="dog in machineDogs" :key="dog.id" class="device-row" :class="dog.status === 'offline' ? 'is-offline' : 'is-online'">
          <div class="col-name device-name-cell"><strong>{{ dog.name }}</strong></div>
          <div class="col-desc device-description"><span>{{ dog.model }}</span></div>
          <div class="col-dock"><span>{{ dog.location }}</span></div>
          <div class="col-runtime device-runtime"><strong>{{ dog.battery }}%</strong></div>
          <div class="col-status"><span class="status-pill" :class="dog.status === 'offline' ? 'is-offline' : 'is-online'">{{ dogStatusMeta[dog.status].text }}</span></div>
          <div class="col-actions list-actions">
            <el-button class="test-action" @click="openTestDialog(dog)">测试</el-button>
          </div>
        </article>
      </div>
    </section>

    <!-- 测试弹窗：原调度工作台移入此处，视频作为主要内容展示 -->
    <el-dialog v-model="testDialogVisible" :title="`${testingDog?.name || '机器狗'} · 测试`" width="94%" align-center class="dog-test-dialog" destroy-on-close :close-on-click-modal="false">

    <section class="command-panel">
      <div class="route-builder">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">巡检任务</span>
            <h3>路线编排</h3>
          </div>
          <el-button class="route-manage-btn" :icon="EditPen" size="small" @click="openRouteEditor">
            路线管理
          </el-button>
        </div>

        <div class="control-grid">
          <el-select v-model="selectedDeviceId" class="dog-picker" placeholder="选择机器狗" popper-class="dog-select-popper">
            <el-option
              v-for="dog in machineDogs"
              :key="dog.id"
              :label="`${dog.name} · ${dogStatusMeta[dog.status].text}`"
              :value="dog.id"
              :disabled="dog.status === 'offline'"
            />
          </el-select>
          <el-select
            v-model="selectedPresetRouteId"
            class="route-picker"
            placeholder="选择预设路线"
            @change="applyPresetRoute"
          >
            <el-option v-for="route in presetRoutes" :key="route.id" :label="route.name" :value="route.id" />
          </el-select>
          <el-button class="ctrl-btn" :icon="VideoPlay" type="primary" :disabled="!canStartTask" @click="startInspection">
            开始巡检
          </el-button>
          <el-button class="ctrl-btn" :icon="RefreshLeft" @click="resetRoute">重置路线</el-button>
        </div>

        <div class="selected-route">
          <div class="selected-route-head">
            <span>已选巡检点</span>
            <strong>{{ selectedWaypoints.length }}</strong>
          </div>
          <div v-if="selectedWaypoints.length" class="route-chip-list">
            <span
              v-for="(point, index) in selectedWaypoints"
              :key="point.id"
              class="route-chip"
            >
              <b>{{ index + 1 }}</b>
              <span>{{ point.name }}</span>
            </span>
          </div>
          <div v-else class="route-empty">请选择一条预设路线，或点击"编辑路线"自定义巡检点</div>
        </div>
      </div>

      <div class="task-current">
        <div class="panel-heading compact">
          <div>
            <span class="panel-kicker">当前任务</span>
            <h3>{{ activeTask ? activeTask.name : '待下发' }}</h3>
          </div>
          <span class="task-state" :class="{ running: Boolean(activeTask) }">
            {{ activeTask ? '巡检中' : '待命' }}
          </span>
        </div>
        <div class="task-metrics">
          <div>
            <span>执行机器狗</span>
            <strong>{{ activeDog?.name || '--' }}</strong>
          </div>
          <div>
            <span>巡检进度</span>
            <strong>{{ activeTask ? Math.round(taskProgress) : 0 }}%</strong>
          </div>
          <div>
            <span>预计剩余</span>
            <strong>{{ activeTask ? remainingTimeText : '--' }}</strong>
          </div>
        </div>
        <div class="task-progress">
          <div :style="{ width: `${taskProgress}%` }"></div>
        </div>
      </div>

      <div class="machine-status">
        <div class="panel-heading compact">
          <div>
            <span class="panel-kicker">设备状态</span>
            <h3>{{ selectedDog?.name || '未选择设备' }}</h3>
          </div>
          <span v-if="selectedDog" class="live-badge">{{ dogStatusMeta[selectedDog.status].text }}</span>
        </div>
        <div v-if="selectedDog" class="status-grid">
          <div class="status-cell">
            <span class="status-label">移动速度</span>
            <strong :class="{ moving: selectedDog.speed > 0 }">
              {{ selectedDog.speed.toFixed(1) }} <em>m/s</em>
            </strong>
          </div>
          <div class="status-cell">
            <span class="status-label">当前位置</span>
            <strong class="status-loc" :title="selectedDog.location">{{ selectedDog.location }}</strong>
          </div>
          <div class="status-cell">
            <span class="status-label">当前任务</span>
            <strong class="status-task" :title="selectedDog.task || '待命'">{{ selectedDog.task || '待命' }}</strong>
          </div>
          <div class="status-cell">
            <span class="status-label">电量</span>
            <div class="status-meter">
              <div class="meter-track" :class="{ low: selectedDog.battery < 30 }">
                <div class="meter-fill battery" :style="{ width: `${selectedDog.battery}%` }"></div>
              </div>
              <b>{{ selectedDog.battery }}%</b>
            </div>
          </div>
        </div>
        <div v-else class="status-empty">请先在左侧选择设备</div>
      </div>
    </section>

    <section class="workspace">
      <div ref="mapAreaRef" class="map-area">
        <img src="/9point.png" alt="大藤峡地图" class="map-image" draggable="false" />

        <svg class="route-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline v-if="activePolyline" class="route-line route-line-back" :points="activePolyline" />
          <polyline v-if="activePolyline" class="route-line" :points="activePolyline" />
          <polyline v-if="passedPolyline" class="route-line passed" :points="passedPolyline" />
        </svg>

        <span
          v-for="point in displayWaypoints"
          :key="point.id"
          class="waypoint"
          :class="{ selected: selectedWaypointIds.includes(point.id) }"
          :style="{ left: `${point.displayX}%`, top: `${point.displayY}%` }"
        >
          <span class="waypoint-dot">{{ waypointOrder(point.id) || '' }}</span>
          <span class="waypoint-label">{{ point.name }}</span>
        </span>

        <div
          v-for="dog in machineDogs"
          :key="dog.id"
          class="dog-marker"
          :class="[dog.status, { active: dog.id === selectedDeviceId }]"
          :style="{ left: `${toDisplay(dog.position).x}%`, top: `${toDisplay(dog.position).y}%` }"
          @click="selectedDeviceId = dog.id"
        >
          <span class="dog-pulse"></span>
          <span class="dog-body">
            <el-icon><Aim /></el-icon>
          </span>
          <span class="dog-label">{{ dog.name }}</span>
        </div>

        <div class="charge-zone" :style="{ left: displayChargeZone.x + '%', top: displayChargeZone.y + '%' }">
          <span class="charge-zone-icon">
            <el-icon><Lightning /></el-icon>
          </span>
          <span class="charge-zone-label">充电区</span>
        </div>

        <div class="map-corner-label">
          <el-icon :size="13"><MapLocation /></el-icon>
          <span>9号巡检区域</span>
        </div>

        <div class="map-legend">
          <span><i class="legend-dot idle"></i>空闲</span>
          <span><i class="legend-dot running"></i>巡检中</span>
          <span><i class="legend-dot offline"></i>离线</span>
          <span><i class="legend-line"></i>当前路线</span>
        </div>
      </div>

      <aside class="live-panel">
        <div class="panel-heading compact">
          <div>
            <span class="panel-kicker">实时监控</span>
            <h3>{{ activeDog?.name || selectedDog?.name || '未选择设备' }}</h3>
          </div>
          <span class="live-badge">{{ activeTask ? '任务画面' : '预览' }}</span>
        </div>
        <div class="video-stage">
          <video
            v-if="videoUrl"
            class="video-stream"
            :src="videoUrl"
            autoplay
            muted
            loop
            playsinline
            controls
          ></video>
          <div v-else class="video-placeholder">
            <el-icon :size="36"><VideoCamera /></el-icon>
            <strong>实时画面</strong>
            <span>等待机器狗回传视频</span>
          </div>
          <div class="scan-grid"></div>
        </div>
      </aside>
    </section>

    </el-dialog>

    <el-dialog v-model="routeManagerVisible" title="路线管理" width="620px" class="route-editor">
      <!-- 视图一：路线列表 -->
      <template v-if="!routeFormVisible">
        <div class="route-manager-list">
          <div
            v-for="route in presetRoutes"
            :key="route.id"
            class="route-manager-item"
            :class="{ active: route.id === selectedPresetRouteId }"
          >
            <div class="route-manager-item-main">
              <strong>{{ route.name }}</strong>
              <span>{{ route.points.length }} 个巡检点 · {{ route.points.map(waypointName).join(' → ') }}</span>
            </div>
            <div class="route-manager-item-actions">
              <el-button size="small" type="primary" @click="useRoute(route)">使用</el-button>
              <el-button size="small" @click="editExistingRoute(route)">编辑</el-button>
              <el-button size="small" :disabled="presetRoutes.length <= 1" @click="deleteRoute(route)">删除</el-button>
            </div>
          </div>
          <div v-if="!presetRoutes.length" class="route-pool-empty">暂无路线，点击下方新建</div>
        </div>
        <div class="route-manager-footer">
          <el-button @click="resetToDefaultRoutes">恢复默认</el-button>
          <el-button type="primary" :icon="Plus" @click="startNewRoute">新建路线</el-button>
        </div>
      </template>

      <!-- 视图二：新建 / 编辑表单 -->
      <template v-else>
        <div class="route-editor-name">
          <span class="route-editor-label">路线名称</span>
          <el-input v-model="editingRouteName" placeholder="请输入路线名称，如：岸线综合巡检" maxlength="16" show-word-limit />
        </div>
        <div class="route-editor-body">
          <div class="route-pool">
            <div class="route-editor-label">可选巡检点（点击添加）</div>
            <button
              v-for="point in editablePoolPoints"
              :key="point.id"
              type="button"
              class="route-pool-item"
              @click="addEditingPoint(point)"
            >
              <el-icon><Plus /></el-icon>
              <span>{{ point.name }}</span>
            </button>
            <div v-if="!editablePoolPoints.length" class="route-pool-empty">巡检点已全部加入路线</div>
          </div>
          <div class="route-seq">
            <div class="route-editor-label">路线顺序（{{ editingRoutePointIds.length }}）</div>
            <div v-if="editingRoutePointIds.length" class="route-seq-list">
              <div v-for="(pid, index) in editingRoutePointIds" :key="pid" class="route-seq-item">
                <b>{{ index + 1 }}</b>
                <span>{{ waypointName(pid) }}</span>
                <div class="route-seq-actions">
                  <button type="button" :disabled="index === 0" @click="moveEditingPoint(index, -1)">
                    <el-icon><Top /></el-icon>
                  </button>
                  <button
                    type="button"
                    :disabled="index === editingRoutePointIds.length - 1"
                    @click="moveEditingPoint(index, 1)"
                  >
                    <el-icon><Bottom /></el-icon>
                  </button>
                  <button type="button" class="danger" @click="removeEditingPoint(pid)">
                    <el-icon><Close /></el-icon>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="route-seq-empty">请从左侧至少选择一个巡检点</div>
          </div>
        </div>
      </template>

      <template #footer>
        <template v-if="!routeFormVisible">
          <el-button @click="routeManagerVisible = false">关闭</el-button>
        </template>
        <template v-else>
          <el-button @click="backToRouteList">返回</el-button>
          <el-button
            type="primary"
            :disabled="!editingRouteName.trim() || editingRoutePointIds.length < 1"
            @click="saveEditingRoute"
          >
            保存路线
          </el-button>
        </template>
      </template>
    </el-dialog>

    <el-drawer
      v-model="deviceDrawerVisible"
      title="机器狗状态"
      direction="rtl"
      size="390px"
      custom-class="machine-dog-drawer"
    >
      <div class="drawer-filter">
        <el-segmented v-model="deviceFilter" :options="deviceFilterOptions" size="small" />
      </div>
      <div class="dog-list">
        <article
          v-for="dog in filteredDogs"
          :key="dog.id"
          class="dog-card"
          :class="[dog.status, { active: dog.id === selectedDeviceId }]"
          @click="selectDog(dog)"
        >
          <div class="dog-card-main">
            <div>
              <h4>{{ dog.name }}</h4>
              <p>{{ dog.model }} · {{ dog.location }}</p>
            </div>
            <span class="dog-status" :class="dog.status">{{ dogStatusMeta[dog.status].text }}</span>
          </div>
          <div class="dog-card-data">
            <span>电量 <b>{{ dog.battery }}%</b></span>
            <span>任务 <b>{{ dog.task || '无' }}</b></span>
          </div>
          <div class="dog-card-actions">
            <el-button size="small" :icon="View" @click.stop="selectDog(dog)">查看</el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="dog.status === 'offline'"
              @click.stop="assignDog(dog)"
            >
              指派任务
            </el-button>
          </div>
        </article>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Aim,
  Bottom,
  Close,
  EditPen,
  Lightning,
  MapLocation,
  Menu,
  Plus,
  RefreshLeft,
  Top,
  VideoCamera,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'

const dogStatusMeta = {
  offline: { text: '离线', className: 'offline' },
  online: { text: '空闲', className: 'idle' },
  running: { text: '巡检中', className: 'running' },
  idle: { text: '空闲', className: 'idle' },
  warning: { text: '异常', className: 'warning' },
}

// 坐标换算说明：
// tip.png 是 9point.png 中央区域 (705,308) 起的精确截图，标记位置先映射回 9point 全局坐标（百分比）。
// 地图容器 object-fit: cover 会根据容器宽高比动态裁切，因此渲染时用 toDisplay() 将全局坐标换算为容器坐标。
const waypoints = [
  { id: 'p1', name: '巡检点 1', x: 25.0, y: 45.5 },
  { id: 'p2', name: '巡检点 2', x: 46.3, y: 41.2 },
  { id: 'p3', name: '巡检点 3', x: 65.7, y: 37.9 },
]

// 机器狗充电区（标记图紫色区域，全局坐标）
const chargeZone = { x: 82, y: 36.2 }

// 路线数据持久化：编辑后的路线保存到 localStorage，刷新页面后保持
const ROUTE_STORAGE_KEY = 'machine-dog-preset-routes-v1'
const SELECTED_ROUTE_STORAGE_KEY = 'machine-dog-selected-route-v1'
// 默认路线（首次访问或点击「恢复默认」时使用）
const DEFAULT_PRESET_ROUTES = [
  { id: 'route-a', name: '岸线由西向东巡检', points: ['p1', 'p2', 'p3'] },
  { id: 'route-b', name: '岸线由东向西巡检', points: ['p3', 'p2', 'p1'] },
]

function cloneDefaultRoutes() {
  return DEFAULT_PRESET_ROUTES.map((route) => ({ ...route, points: [...route.points] }))
}

function loadStoredRoutes() {
  try {
    const raw = localStorage.getItem(ROUTE_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch (e) {
    // 存储数据损坏时回退默认路线
  }
  return cloneDefaultRoutes()
}

function persistRoutes() {
  localStorage.setItem(ROUTE_STORAGE_KEY, JSON.stringify(presetRoutes.value))
}

// 恢复默认路线（清空本地保存）
function resetToDefaultRoutes() {
  presetRoutes.value = cloneDefaultRoutes()
  selectedPresetRouteId.value = presetRoutes.value[0].id
  selectedWaypointIds.value = [...presetRoutes.value[0].points]
  localStorage.removeItem(ROUTE_STORAGE_KEY)
  localStorage.removeItem(SELECTED_ROUTE_STORAGE_KEY)
  ElMessage.success('已恢复默认路线')
}

const presetRoutes = ref(loadStoredRoutes())

const machineDogs = ref([
  {
    id: 'dog-01',
    name: '绝影 Lite 3',
    model: 'Unitree Lite 3',
    status: 'idle',
    battery: 92,
    signal: 95,
    location: '充电区',
    speed: 0, // 移动速度（m/s），巡检移动时更新
    task: '',
    position: { x: chargeZone.x, y: chargeZone.y },
  },
])

// ===== 地图坐标换算（全局坐标 → 容器坐标） =====
const IMG_W = 3072
const IMG_H = 1344
const mapAreaRef = ref(null)
// 地图容器实际尺寸，通过 ResizeObserver 动态更新
const mapSize = ref({ w: 0, h: 0 })
let mapResizeObserver = null

function toDisplay(globalPoint) {
  const { w, h } = mapSize.value
  if (!w || !h) return { x: globalPoint.x, y: globalPoint.y }
  // object-fit: cover 换算：按较窄方向撑满容器，另一方向居中裁切
  const scale = Math.max(w / IMG_W, h / IMG_H)
  const offsetX = (IMG_W * scale - w) / 2
  const offsetY = (IMG_H * scale - h) / 2
  return {
    x: ((globalPoint.x / 100) * IMG_W * scale - offsetX) / w * 100,
    y: ((globalPoint.y / 100) * IMG_H * scale - offsetY) / h * 100,
  }
}

// 渲染用的容器坐标（waypoints / 充电区）
const displayWaypoints = computed(() =>
  waypoints.map((p) => ({ ...p, displayX: toDisplay(p).x, displayY: toDisplay(p).y }))
)
const displayChargeZone = computed(() => toDisplay(chargeZone))

const deviceFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '空闲', value: 'idle' },
  { label: '巡检中', value: 'running' },
  { label: '异常', value: 'warning' },
]

const deviceDrawerVisible = ref(false)
const testDialogVisible = ref(false)
const testingDog = ref(null)
const selectedDeviceId = ref('dog-01')
const selectedPresetRouteId = ref(
  (() => {
    const stored = localStorage.getItem(SELECTED_ROUTE_STORAGE_KEY)
    if (stored && presetRoutes.value.some((route) => route.id === stored)) return stored
    return presetRoutes.value[0]?.id || ''
  })()
)
const selectedWaypointIds = ref([...presetRoutes.value[0].points])
const deviceFilter = ref('all')
const videoUrl = ref('')
// 初始无巡检任务，机器狗停在充电区待命，点击"开始巡检"后从充电区出发巡检
const activeTask = ref(null)

// 路线管理弹窗状态
const routeManagerVisible = ref(false)
const routeFormVisible = ref(false)
const editingRouteId = ref(null)
const editingRouteName = ref('')
const editingRoutePointIds = ref([])

const editablePoolPoints = computed(() =>
  waypoints.filter((point) => !editingRoutePointIds.value.includes(point.id))
)

// ===== 巡检任务模拟：充电区出发 → 逐点移动+停留 → 逆序回程 =====
const STAY_MS = 3500 // 每个巡检点停留时长
const MOVE_SPEED = 100 // 移动速率系数（百分比距离 → 毫秒，值越大越慢）
const CRUISE_SPEED = 1.5 // 移动巡航速度（m/s），用于设备状态框实时展示
let tripSegments = [] // 当前任务的行程分段（move / stay）

function buildTrip(routePoints) {
  const segments = []
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)
  const moveDur = (from, to) => Math.max(600, dist(from, to) * MOVE_SPEED)
  // 去程：充电区 → p1 → ... → pN，每到达一个巡检点停留
  for (let i = 0; i < routePoints.length; i++) {
    const from = i === 0 ? chargeZone : routePoints[i - 1]
    const to = routePoints[i]
    segments.push({ type: 'move', from, to, duration: moveDur(from, to) })
    segments.push({ type: 'stay', point: to, duration: STAY_MS })
  }
  // 回程：pN → ... → p1 → 充电区（不再停留）
  const backSeq = [...routePoints].reverse()
  for (let i = 0; i < backSeq.length - 1; i++) {
    const from = backSeq[i]
    const to = backSeq[i + 1]
    segments.push({ type: 'move', from, to, duration: moveDur(from, to) })
  }
  if (routePoints.length) {
    segments.push({ type: 'move', from: backSeq[backSeq.length - 1], to: chargeZone, duration: moveDur(backSeq[backSeq.length - 1], chargeZone) })
  }
  return segments
}

function positionAtElapsed(task) {
  let acc = 0
  for (const seg of tripSegments) {
    if (task.elapsed <= acc + seg.duration) {
      if (seg.type === 'stay') return { ...seg.point }
      const local = Math.min(1, (task.elapsed - acc) / seg.duration)
      return {
        x: seg.from.x + (seg.to.x - seg.from.x) * local,
        y: seg.from.y + (seg.to.y - seg.from.y) * local,
      }
    }
    acc += seg.duration
  }
  return { ...chargeZone }
}

// 返回 elapsed 时刻所在的行程分段（用于设备状态框的实时速度展示）
function currentTripSegment(task) {
  let acc = 0
  for (const seg of tripSegments) {
    if (task.elapsed <= acc + seg.duration) return { seg, local: 1 }
    acc += seg.duration
  }
  return { seg: null, local: 0 }
}

function buildPassedPolyline(task) {
  const pts = []
  let acc = 0
  for (const seg of tripSegments) {
    if (task.elapsed >= acc + seg.duration) {
      if (seg.type === 'move') pts.push({ ...seg.to })
    } else {
      if (seg.type === 'move') {
        const local = Math.max(0, (task.elapsed - acc) / seg.duration)
        pts.push({
          x: seg.from.x + (seg.to.x - seg.from.x) * local,
          y: seg.from.y + (seg.to.y - seg.from.y) * local,
        })
      } else {
        pts.push({ ...seg.point })
      }
      break
    }
    acc += seg.duration
  }
  if (!pts.length && tripSegments.length) pts.push({ ...chargeZone })
  return pointsToPolyline(pts.map(toDisplay))
}

let timer = null

const selectedDog = computed(() => machineDogs.value.find((dog) => dog.id === selectedDeviceId.value) || null)
const dogOnlineCount = computed(() => machineDogs.value.filter((dog) => dog.status !== 'offline').length)
const dogOfflineCount = computed(() => machineDogs.value.filter((dog) => dog.status === 'offline').length)
const activeDog = computed(() => {
  if (!activeTask.value) return null
  return machineDogs.value.find((dog) => dog.id === activeTask.value.dogId) || null
})
const selectedWaypoints = computed(() =>
  selectedWaypointIds.value.map((id) => waypoints.find((point) => point.id === id)).filter(Boolean)
)
const activeRoutePoints = computed(() => {
  const ids = activeTask.value?.routePointIds?.length ? activeTask.value.routePointIds : selectedWaypointIds.value
  return ids.map((id) => waypoints.find((point) => point.id === id)).filter(Boolean)
})
// 路线与机器狗位置统一换算到容器坐标（cover 动态裁切）
const activePolyline = computed(() => pointsToPolyline(activeRoutePoints.value.map(toDisplay)))
const passedPolyline = computed(() => {
  if (!activeTask.value || !tripSegments.length) return ''
  return buildPassedPolyline(activeTask.value)
})
const canStartTask = computed(() =>
  selectedDog.value && selectedDog.value.status !== 'offline' && selectedWaypoints.value.length >= 1
)
const remainingTimeText = computed(() => {
  if (!activeTask.value) return '--'
  const remainMs = Math.max(0, activeTask.value.totalMs - activeTask.value.elapsed)
  const sec = Math.ceil(remainMs / 1000)
  return sec < 60 ? `${sec} 秒` : `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
})
const taskProgress = computed(() => {
  if (!activeTask.value || !activeTask.value.totalMs) return 0
  return Math.min(100, (activeTask.value.elapsed / activeTask.value.totalMs) * 100)
})
const filteredDogs = computed(() => {
  if (deviceFilter.value === 'all') return machineDogs.value
  return machineDogs.value.filter((dog) => dog.status === deviceFilter.value)
})
const summaryCards = computed(() => {
  const counts = machineDogs.value.reduce((acc, dog) => {
    acc[dog.status] = (acc[dog.status] || 0) + 1
    return acc
  }, {})
  return [
    { label: '设备总数', value: machineDogs.value.length, className: 'all' },
    { label: '空闲', value: counts.idle || 0, className: 'idle' },
    { label: '巡检中', value: counts.running || 0, className: 'running' },
    { label: '离线', value: counts.offline || 0, className: 'offline' },
    { label: '异常', value: counts.warning || 0, className: 'warning' },
  ]
})

function pointsToPolyline(points) {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

function updateActiveDogPosition() {
  if (!activeTask.value) return
  const dog = machineDogs.value.find((item) => item.id === activeTask.value.dogId)
  if (!dog) return

  activeTask.value.elapsed += 300
  if (activeTask.value.elapsed >= activeTask.value.totalMs) {
    activeTask.value.elapsed = activeTask.value.totalMs
    dog.position = { ...chargeZone } // 完成任务后回到充电区
    dog.speed = 0
    dog.status = 'idle'
    dog.task = ''
    activeTask.value = null
    ElMessage.success('巡检任务已完成，机器狗已返回充电区')
    return
  }

  dog.position = positionAtElapsed(activeTask.value)
  // 更新实时速度：移动段巡航速度，停留/待命为 0
  dog.speed = currentTripSegment(activeTask.value).seg?.type === 'move' ? CRUISE_SPEED : 0
}

function applyPresetRoute(routeId) {
  const route = presetRoutes.value.find((item) => item.id === routeId)
  if (!route) return
  selectedWaypointIds.value = [...route.points]
}

function waypointOrder(pointId) {
  const index = selectedWaypointIds.value.indexOf(pointId)
  return index >= 0 ? index + 1 : ''
}

function waypointName(pointId) {
  return waypoints.find((point) => point.id === pointId)?.name || pointId
}

function resetRoute() {
  const route = presetRoutes.value[0]
  selectedPresetRouteId.value = route.id
  selectedWaypointIds.value = [...route.points]
}

// 打开路线管理（先展示路线列表）
function openRouteEditor() {
  routeFormVisible.value = false
  editingRouteId.value = null
  routeManagerVisible.value = true
}

// 新建路线：默认不选任何巡检点
function startNewRoute() {
  editingRouteId.value = null
  editingRouteName.value = ''
  editingRoutePointIds.value = []
  routeFormVisible.value = true
}

// 编辑已有路线
function editExistingRoute(route) {
  editingRouteId.value = route.id
  editingRouteName.value = route.name
  editingRoutePointIds.value = [...route.points]
  routeFormVisible.value = true
}

// 使用已有路线（关闭弹窗并应用）
function useRoute(route) {
  selectedPresetRouteId.value = route.id
  selectedWaypointIds.value = [...route.points]
  localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, route.id)
  routeManagerVisible.value = false
  routeFormVisible.value = false
  ElMessage.success(`已选择路线：${route.name}`)
}

// 删除路线（至少保留一条）
function deleteRoute(route) {
  if (presetRoutes.value.length <= 1) {
    ElMessage.warning('至少需要保留一条路线')
    return
  }
  presetRoutes.value = presetRoutes.value.filter((item) => item.id !== route.id)
  if (selectedPresetRouteId.value === route.id) {
    const next = presetRoutes.value[0]
    selectedPresetRouteId.value = next.id
    selectedWaypointIds.value = [...next.points]
    localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, next.id)
  }
  persistRoutes()
  ElMessage.success(`已删除路线：${route.name}`)
}

// 返回路线列表
function backToRouteList() {
  routeFormVisible.value = false
  editingRouteId.value = null
}

function addEditingPoint(point) {
  if (editingRoutePointIds.value.includes(point.id)) return
  editingRoutePointIds.value.push(point.id)
}

function removeEditingPoint(pointId) {
  editingRoutePointIds.value = editingRoutePointIds.value.filter((id) => id !== pointId)
}

function moveEditingPoint(index, dir) {
  const target = index + dir
  if (target < 0 || target >= editingRoutePointIds.value.length) return
  const arr = [...editingRoutePointIds.value]
  ;[arr[index], arr[target]] = [arr[target], arr[index]]
  editingRoutePointIds.value = arr
}

function saveEditingRoute() {
  const name = editingRouteName.value.trim()
  if (!name || editingRoutePointIds.value.length < 1) return
  if (editingRouteId.value) {
    presetRoutes.value = presetRoutes.value.map((item) =>
      item.id === editingRouteId.value
        ? { ...item, name, points: [...editingRoutePointIds.value] }
        : item
    )
  } else {
    const newRoute = { id: `route-${Date.now()}`, name, points: [...editingRoutePointIds.value] }
    presetRoutes.value.push(newRoute)
    selectedPresetRouteId.value = newRoute.id
    selectedWaypointIds.value = [...newRoute.points]
    localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, newRoute.id)
  }
  persistRoutes()
  routeFormVisible.value = false
  editingRouteId.value = null
  ElMessage.success(`已保存路线：${name}`)
}

function startInspection() {
  if (!canStartTask.value) return
  const dog = selectedDog.value
  const routeName = presetRoutes.value.find((item) => item.id === selectedPresetRouteId.value)?.name || '临时巡检路线'
  const routePoints = activeRoutePoints.value

  // 构建行程分段：去程逐点+停留，回程逆序直达充电区
  tripSegments = buildTrip(routePoints)
  const totalMs = tripSegments.reduce((sum, seg) => sum + seg.duration, 0)

  machineDogs.value = machineDogs.value.map((item) => {
    if (item.id === dog.id) {
      return {
        ...item,
        status: 'running',
        task: routeName,
        speed: 0,
        position: { ...chargeZone }, // 从充电区出发
      }
    }
    return item
  })
  activeTask.value = {
    id: `task-${Date.now()}`,
    name: routeName,
    dogId: dog.id,
    routePointIds: [...selectedWaypointIds.value],
    elapsed: 0,
    totalMs,
  }
  ElMessage.success('巡检任务已下发，机器狗从充电区出发')
}

function selectDog(dog) {
  selectedDeviceId.value = dog.id
  deviceDrawerVisible.value = false
}

function assignDog(dog) {
  selectedDeviceId.value = dog.id
  deviceDrawerVisible.value = false
  ElMessage.info('已选中设备，请确认路线后开始巡检')
}

function openTestDialog(dog) {
  testingDog.value = dog
  selectedDeviceId.value = dog.id
  testDialogVisible.value = true
}

onMounted(() => {
  timer = window.setInterval(updateActiveDogPosition, 300)
  // 监听地图容器尺寸，动态换算 cover 裁切后的显示坐标
  const el = mapAreaRef.value
  if (el && typeof ResizeObserver !== 'undefined') {
    const updateMapSize = () => {
      mapSize.value = { w: el.clientWidth, h: el.clientHeight }
    }
    updateMapSize()
    mapResizeObserver = new ResizeObserver(updateMapSize)
    mapResizeObserver.observe(el)
  }
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
  if (mapResizeObserver) mapResizeObserver.disconnect()
})
</script>

<style scoped>
.machine-dog-page {
  min-height: 100%;
  padding: 18px;
  color: #dcecf8;
  background:
    radial-gradient(circle at 18% 10%, rgba(31, 187, 198, .18), transparent 26%),
    linear-gradient(135deg, #07131f 0%, #091724 48%, #0b1620 100%);
}

.overview-bar,
.command-panel,
.workspace {
  border: 1px solid rgba(99, 171, 210, .22);
  border-radius: 8px;
  background: rgba(9, 28, 43, .88);
  box-shadow: 0 18px 40px rgba(0, 0, 0, .22);
}

.overview-bar {
  min-height: 96px;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(420px, 1.8fr) auto;
  align-items: center;
  gap: 18px;
  padding: 16px 18px;
}

.title-block .eyebrow,
.panel-kicker {
  color: #79b9d8;
  font-size: 12px;
}

.title-block h2,
.panel-heading h3 {
  margin: 4px 0 0;
  color: #f5fbff;
  font-size: 24px;
  letter-spacing: 0;
}

/* 面板标题左侧装饰竖条 */
.panel-heading h3 {
  position: relative;
  padding-left: 11px;
  line-height: 1;
}

.panel-heading h3::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 15px;
  border-radius: 2px;
  background: linear-gradient(180deg, #43d9ff, #43e6b8);
}

.status-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(74px, 1fr));
  gap: 10px;
}

.summary-card {
  min-height: 62px;
  padding: 10px 12px;
  border: 1px solid rgba(108, 169, 201, .18);
  border-radius: 8px;
  background: rgba(14, 39, 57, .8);
}

.summary-card span {
  display: block;
  color: #8db2c8;
  font-size: 12px;
}

.summary-card strong {
  display: block;
  margin-top: 4px;
  color: #f2fbff;
  font-size: 24px;
}

.summary-card.idle strong { color: #48e6bf; }
.summary-card.running strong { color: #43d4ff; }
.summary-card.offline strong { color: #8494a3; }
.summary-card.warning strong { color: #ffca66; }

.drawer-entry {
  min-width: 122px;
}

.command-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, .8fr) minmax(280px, .8fr);
  gap: 16px;
  margin-top: 14px;
  padding: 16px;
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-heading.compact h3 {
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 18px;
}

.control-grid {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

/* 横向压缩路线选择控件：下拉框定宽，按钮紧凑 */
.control-grid .dog-picker {
  flex: 0 0 170px;
}

.control-grid .route-picker {
  flex: 0 1 260px;
  min-width: 0;
}

.control-grid .ctrl-btn {
  flex: 0 0 auto;
  margin-left: 0;
}

.selected-route {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid rgba(79, 151, 187, .18);
  border-radius: 8px;
  background: rgba(5, 18, 30, .46);
}

.selected-route-head {
  display: flex;
  justify-content: space-between;
  color: #90b5c8;
  font-size: 13px;
}

.selected-route-head strong {
  color: #3ed9ff;
}

.route-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.route-chip {
  height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid rgba(64, 202, 255, .28);
  border-radius: 8px;
  color: #dff8ff;
  background: rgba(30, 118, 150, .28);
}

.route-chip b {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06212e;
  background: #4ddfff;
  font-size: 12px;
}

.route-empty {
  margin-top: 10px;
  color: #6f8fa5;
  font-size: 13px;
}

.task-current {
  padding: 14px;
  border: 1px solid rgba(78, 151, 188, .18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(13, 42, 60, .9), rgba(8, 24, 38, .88));
}

.task-state,
.live-badge {
  flex: 0 0 auto;
  padding: 4px 9px;
  border-radius: 999px;
  color: #8aa8b9;
  background: rgba(122, 143, 160, .16);
  font-size: 12px;
}

.task-state.running,
.live-badge {
  color: #43e5bd;
  background: rgba(67, 229, 189, .12);
}

.task-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 16px;
}

.task-metrics div {
  min-width: 0;
  padding: 9px;
  border-radius: 8px;
  background: rgba(1, 10, 19, .38);
}

.task-metrics span {
  display: block;
  color: #789caf;
  font-size: 12px;
}

.task-metrics strong {
  display: block;
  margin-top: 6px;
  overflow: hidden;
  color: #eef9ff;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress {
  height: 10px;
  margin-top: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(118, 142, 164, .18);
}

.task-progress div {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #42e8bd, #36cfff);
  transition: width .28s ease;
}

/* 机器状态框：展示当前选中设备的电量、速度、信号等信息 */
.machine-status {
  padding: 14px;
  border: 1px solid rgba(78, 151, 188, .18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(13, 42, 60, .9), rgba(8, 24, 38, .88));
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.status-cell {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(94, 163, 196, .14);
  border-radius: 8px;
  background: rgba(1, 10, 19, .38);
}

.status-label {
  display: block;
  margin-bottom: 6px;
  color: #789caf;
  font-size: 11px;
  letter-spacing: .5px;
}

.status-cell > strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #eef9ff;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cell strong.moving {
  color: #3ed9ff;
}

.status-cell strong em {
  font-style: normal;
  color: #6f95ab;
  font-size: 11px;
  font-weight: 400;
}

.status-cell strong.status-loc,
.status-cell strong.status-task {
  color: #9fd4e8;
  font-size: 13px;
  font-weight: 500;
}

.status-meter {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.meter-track {
  flex: 1;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(118, 142, 164, .2);
}

.meter-fill {
  height: 100%;
  border-radius: inherit;
  transition: width .28s ease;
}

.meter-fill.battery {
  background: linear-gradient(90deg, #42e8bd, #36cfff);
}

.meter-track.low .meter-fill.battery {
  background: linear-gradient(90deg, #ff9f43, #ff5f57);
}

.meter-fill.signal {
  background: linear-gradient(90deg, #6ac8ff, #3d7bff);
}

.status-meter b {
  flex: 0 0 auto;
  color: #eef9ff;
  font-size: 13px;
}

.status-empty {
  margin-top: 14px;
  padding: 18px 10px;
  border-radius: 8px;
  color: #6f8fa5;
  text-align: center;
  font-size: 13px;
  background: rgba(1, 10, 19, .38);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) 420px;
  gap: 16px;
  min-height: 400px;
  margin-top: 14px;
  padding: 16px;
}

.map-area {
  position: relative;
  height: 380px;
  overflow: hidden;
  border: 1px solid rgba(87, 153, 190, .22);
  border-radius: 8px;
  background: #06111b;
}

.map-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  opacity: .86;
}

.route-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.route-line {
  fill: none;
  stroke: #42d9ff;
  stroke-width: .62;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.3;
  filter: drop-shadow(0 0 5px rgba(66, 217, 255, .72));
}

.route-line-back {
  stroke: rgba(24, 90, 126, .68);
  stroke-width: 1.22;
  stroke-dasharray: none;
}

.route-line.passed {
  stroke: #43e6b8;
  stroke-dasharray: none;
}

.charge-zone {
  position: absolute;
  z-index: 2;
  transform: translate(-100%, -50%);
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  border: 1.5px dashed rgba(67, 230, 184, .62);
  border-radius: 999px;
  background: rgba(12, 68, 56, .2);
  box-shadow:
    0 0 18px rgba(67, 230, 184, .14),
    inset 0 0 22px rgba(67, 230, 184, .08);
  color: #c8f7e8;
  white-space: nowrap;
  pointer-events: none;
  animation: chargeGlow 2.6s ease-in-out infinite;
}

.charge-zone-icon {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #062a20;
  background: #43e6b8;
  box-shadow: 0 0 14px rgba(67, 230, 184, .5);
  font-size: 13px;
}

.charge-zone-label {
  color: #d9fbf0;
  font-size: 12px;
}

.waypoint {
  position: absolute;
  z-index: 2;
  /* 锚点即标记点本身，dot 居中于锚点，label 单独偏移 */
  transform: translate(-50%, -50%);
  width: 0;
  height: 0;
  border: 0;
  color: #dff8ff;
  background: transparent;
}

.waypoint-dot {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  transform: translate(-50%, -50%);
  border: 2px solid rgba(77, 223, 255, .72);
  border-radius: 50%;
  color: #082232;
  background: #45d7ff;
  box-shadow: 0 0 16px rgba(69, 215, 255, .5);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.waypoint-label {
  position: absolute;
  left: 50%;
  top: 15px;
  transform: translateX(-50%);
  max-width: 86px;
  padding: 3px 7px;
  border-radius: 6px;
  color: #ccecf9;
  background: rgba(4, 17, 28, .74);
  font-size: 12px;
  white-space: nowrap;
}

.waypoint:not(.selected) .waypoint-dot {
  background: rgba(8, 29, 42, .88);
  color: transparent;
}

.dog-marker {
  position: absolute;
  z-index: 3;
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: left .28s linear, top .28s linear;
}

.dog-pulse {
  position: absolute;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: rgba(66, 217, 255, .14);
  animation: pulse 1.8s infinite;
}

.dog-body {
  position: relative;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 2px solid rgba(208, 247, 255, .82);
  border-radius: 8px;
  color: #072536;
  background: #41d9ff;
  box-shadow: 0 0 16px rgba(65, 217, 255, .42);
}

.dog-marker.idle .dog-body { background: #43e6b8; }
.dog-marker.running .dog-body { background: #43d9ff; }
.dog-marker.warning .dog-body { background: #ffca66; }
.dog-marker.offline .dog-body {
  background: #7e8c99;
  box-shadow: none;
}

.dog-marker.active .dog-body {
  border-color: #fff;
}

.dog-label {
  margin-top: 4px;
  padding: 3px 7px;
  border-radius: 6px;
  color: #effcff;
  background: rgba(3, 12, 20, .76);
  font-size: 12px;
  white-space: nowrap;
}

.map-corner-label {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 4;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid rgba(111, 183, 220, .22);
  border-radius: 8px;
  color: #e6f6ff;
  background: rgba(5, 19, 31, .78);
  backdrop-filter: blur(8px);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1px;
}

.map-corner-label .el-icon {
  color: #42d9ff;
}

.map-legend {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 4;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(111, 183, 220, .22);
  border-radius: 8px;
  color: #abc9d7;
  background: rgba(5, 19, 31, .78);
  backdrop-filter: blur(8px);
  font-size: 12px;
}

.map-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #43d9ff;
}

.legend-dot.idle { background: #43e6b8; }
.legend-dot.running { background: #43d9ff; }
.legend-dot.offline { background: #8997a3; }
.legend-line {
  width: 24px;
  height: 0;
  border-top: 2px dashed #42d9ff;
}

.live-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(87, 153, 190, .22);
  border-radius: 8px;
  background: rgba(7, 22, 35, .86);
}

.video-stage {
  position: relative;
  height: 300px;
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid rgba(90, 165, 204, .24);
  border-radius: 8px;
  background: #020910;
}

.video-stream {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.video-placeholder {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #79b9d8;
}

.video-placeholder strong {
  color: #eef9ff;
}

.video-placeholder span {
  color: #7d9db0;
  font-size: 13px;
}

/* 联动设备页：列表入口与无人机页保持同一层级 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 86px;
  padding: 18px 20px;
  border: 1px solid rgba(99, 171, 210, .22);
  border-radius: 8px;
  background: rgba(9, 28, 43, .88);
}

.page-header h2 { margin: 0; color: #f5fbff; font-size: 24px; }
.page-header p { margin: 7px 0 0; color: #86a9bd; font-size: 13px; }
.compact-summary { display: flex; gap: 26px; align-items: center; }
.compact-summary .metric { display: grid; grid-template-columns: 9px auto; column-gap: 8px; align-items: center; min-width: 58px; }
.compact-summary .metric span { grid-column: 2; color: #86a9bd; font-size: 12px; }
.compact-summary .metric strong { color: #f2fbff; font-size: 22px; line-height: 1; }
.compact-summary .dot { width: 9px; height: 9px; grid-row: 1 / span 2; border-radius: 50%; background: #43d9ff; }
.compact-summary .dot.online { background: #43e6b8; }
.compact-summary .dot.offline { background: #8293a0; }

.dog-resource-card {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid rgba(99, 171, 210, .22);
  border-radius: 8px;
  background: rgba(9, 28, 43, .88);
}
.dog-resource-card .tab-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.dog-resource-card .tab-header h3 { margin: 0; color: #f5fbff; font-size: 18px; }
.dog-resource-card .device-list { overflow: hidden; border: 1px solid rgba(111, 183, 220, .16); border-radius: 8px; }
.dog-resource-card .device-list-header-row,
.dog-resource-card .device-row { display: grid; grid-template-columns: 1.2fr 1fr 1fr 1fr .75fr 110px; align-items: center; gap: 14px; padding: 14px 18px; }
.dog-resource-card .device-list-header-row { color: #7fa5b9; background: rgba(5, 19, 31, .64); font-size: 12px; }
.dog-resource-card .device-row { min-height: 64px; color: #c9e0eb; border-top: 1px solid rgba(111, 183, 220, .1); background: rgba(10, 31, 47, .55); }
.dog-resource-card .device-row:hover { background: rgba(22, 64, 86, .55); }
.dog-resource-card .device-name-cell strong { color: #f1fbff; font-size: 15px; }
.dog-resource-card .device-description span, .dog-resource-card .col-dock span { color: #91b2c1; font-size: 13px; }
.dog-resource-card .device-runtime { display: flex; gap: 12px; align-items: center; }
.dog-resource-card .device-runtime strong { color: #47e5bd; }
.dog-resource-card .device-runtime span { color: #82bfe0; font-size: 13px; }
.dog-resource-card .status-pill { display: inline-flex; padding: 4px 10px; border-radius: 999px; font-size: 12px; }
.dog-resource-card .status-pill.is-online { color: #42e4b9; background: rgba(66, 228, 185, .12); }
.dog-resource-card .status-pill.is-offline { color: #95a5af; background: rgba(149, 165, 175, .12); }
.dog-resource-card .test-action { color: #dffaff; border-color: rgba(65, 213, 255, .45); background: rgba(35, 143, 179, .18); }

.dog-test-dialog :deep(.el-dialog__body) { padding: 0 16px 16px; }
.dog-test-dialog :deep(.el-dialog__header) { margin-right: 0; padding: 16px 20px 12px; }
.dog-test-dialog :deep(.el-dialog__title) { color: #f5fbff; font-size: 18px; }
.dog-test-dialog .command-panel { margin-top: 0; }
.dog-test-dialog .command-panel { gap: 10px; padding: 10px; }
.dog-test-dialog .selected-route { margin-top: 8px; padding: 8px 10px; }
.dog-test-dialog .task-metrics { margin-top: 10px; }
.dog-test-dialog .workspace { grid-template-columns: minmax(260px, .72fr) minmax(520px, 1.8fr); min-height: 420px; margin-top: 8px; padding: 10px; }
.dog-test-dialog .map-area { height: 390px; }
.dog-test-dialog .live-panel { padding: 10px; }
.dog-test-dialog .live-panel .panel-heading { display: none; }
.dog-test-dialog .video-stage { height: 390px; margin-top: 0; }

/* 充电区与机器狗标记使用同一中心点，避免两个标记视觉错位 */
.dog-test-dialog .charge-zone { transform: translate(-50%, -50%); }
.dog-test-dialog .charge-zone-label { margin-left: 6px; }

/* 与联动系统其它设备页统一的容器风格 */
.machine-dog-page {
  padding: 22px;
  background: #071422;
}

.page-header {
  min-height: 62px;
  margin-bottom: 14px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}

.dog-resource-card {
  margin-top: 0;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
}

.dog-resource-card .tab-header {
  margin: 0;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(96, 151, 191, .14);
}

.dog-resource-card .device-list {
  border: 0;
  border-radius: 0;
  background: #081b2d;
}

.dog-resource-card .device-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  border: 0;
  border-radius: 0;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}

.dog-resource-card .device-row {
  min-height: 68px;
  padding: 10px 20px;
  border-top: 1px solid rgba(149, 190, 220, .10);
  border-radius: 0;
  color: #d7e8f8;
  background: #092034;
}

.dog-resource-card .device-row:hover { background: #102940; }
.dog-resource-card .device-name-cell strong { color: #f3f8fd; font-weight: 800; }
.dog-resource-card .device-description span,
.dog-resource-card .col-dock span { color: #a9c0d2; font-size: 14px; }
.dog-resource-card .status-pill { height: 24px; padding: 0 10px; border: 1px solid rgba(235, 124, 133, .34); border-radius: 4px; font-size: 13px; font-weight: 600; }
.dog-resource-card .status-pill.is-online { border-color: rgba(92, 215, 154, .34); color: #81efad; background: rgba(48, 154, 118, .18); }
.dog-resource-card .status-pill.is-offline { border-color: rgba(235, 124, 133, .34); color: #ffabb5; background: rgba(142, 48, 62, .18); }
.dog-resource-card .test-action { border-color: rgba(82, 178, 143, .54); border-radius: 5px; color: #b9f1d8; background: rgba(30, 103, 78, .42); }

.dog-test-dialog :deep(.el-dialog) {
  border: 1px solid rgba(93, 184, 225, .25);
  border-radius: 12px;
  background: #0a1c2e;
}

.dog-test-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(93, 184, 225, .15);
}

.dog-test-dialog .command-panel,
.dog-test-dialog .workspace {
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
  box-shadow: none;
}

@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .compact-summary { width: 100%; justify-content: space-between; }
  .dog-resource-card .device-list-header-row { display: none; }
  .dog-resource-card .device-row { grid-template-columns: 1fr auto; gap: 8px 14px; }
  .dog-resource-card .device-row > :not(.col-name):not(.col-actions) { display: none; }
  .dog-test-dialog .workspace { grid-template-columns: 1fr; }
  .dog-test-dialog .map-area { height: 240px; }
  .dog-test-dialog .video-stage { height: min(56vw, 360px); }
}

.scan-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(84, 216, 255, .08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(84, 216, 255, .08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.drawer-filter {
  margin-bottom: 14px;
}

.dog-list {
  display: grid;
  gap: 12px;
}

.dog-card {
  padding: 14px;
  border: 1px solid rgba(105, 164, 197, .22);
  border-radius: 8px;
  background: #0c2132;
  cursor: pointer;
}

.dog-card.active {
  border-color: rgba(67, 213, 255, .72);
}

.dog-card-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.dog-card h4 {
  margin: 0;
  color: #f2fbff;
  font-size: 16px;
}

.dog-card p {
  margin: 5px 0 0;
  color: #86a9bc;
  font-size: 12px;
}

.dog-status {
  flex: 0 0 auto;
  height: 24px;
  padding: 4px 9px;
  border-radius: 999px;
  color: #dbeef7;
  background: rgba(125, 145, 160, .2);
  font-size: 12px;
}

.dog-status.idle { color: #49e6bf; background: rgba(73, 230, 191, .12); }
.dog-status.running { color: #43d9ff; background: rgba(67, 217, 255, .12); }
.dog-status.warning { color: #ffca66; background: rgba(255, 202, 102, .14); }
.dog-status.offline { color: #98a4ad; background: rgba(137, 151, 163, .14); }

.dog-card-data {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
}

.dog-card-data span {
  min-width: 0;
  padding: 8px;
  border-radius: 6px;
  color: #789bac;
  background: rgba(4, 14, 24, .42);
  font-size: 12px;
}

.dog-card-data b {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: #f0fbff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dog-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

/* 编辑路线弹窗 */
.route-editor-name {
  display: grid;
  gap: 8px;
}

.route-editor-label {
  color: #8db2c8;
  font-size: 13px;
}

.route-editor-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
  gap: 16px;
  margin-top: 16px;
}

.route-pool {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.route-pool-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid rgba(64, 202, 255, .24);
  border-radius: 8px;
  color: #c9eefb;
  background: rgba(27, 96, 125, .28);
  cursor: pointer;
}

.route-pool-item:hover {
  background: rgba(38, 140, 180, .4);
}

.route-pool-empty,
.route-seq-empty {
  padding: 8px;
  color: #6f8fa5;
  font-size: 13px;
}

/* 路线管理（列表视图） */
.route-manager-list {
  display: grid;
  gap: 10px;
}

.route-manager-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(87, 153, 190, .22);
  border-radius: 10px;
  background: rgba(8, 30, 44, .5);
  transition: border-color .2s, background .2s;
}

.route-manager-item:hover {
  border-color: rgba(87, 153, 190, .4);
}

.route-manager-item.active {
  border-color: rgba(69, 215, 255, .55);
  background: rgba(24, 96, 122, .3);
  box-shadow: 0 0 14px rgba(69, 215, 255, .12);
}

.route-manager-item-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.route-manager-item-main strong {
  color: #eefbff;
  font-size: 14px;
}

.route-manager-item-main span {
  color: #7fa3b8;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.route-manager-item-actions {
  display: flex;
  gap: 6px;
  flex: 0 0 auto;
}

.route-manager-footer {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(87, 153, 190, .16);
}

/* 路线管理按钮（主题化） */
.route-manage-btn.el-button {
  color: #bdf1ff;
  border-color: rgba(69, 215, 255, .38);
  background: linear-gradient(135deg, rgba(27, 96, 125, .32), rgba(14, 54, 74, .4));
}

.route-manage-btn.el-button:hover {
  color: #ffffff;
  border-color: rgba(69, 215, 255, .65);
  background: linear-gradient(135deg, rgba(38, 140, 180, .42), rgba(18, 72, 96, .5));
}

.route-seq {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.route-seq-list {
  display: grid;
  gap: 6px;
}

.route-seq-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid rgba(67, 230, 184, .22);
  border-radius: 8px;
  background: rgba(8, 30, 44, .6);
}

.route-seq-item b {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #06212e;
  background: #4ddfff;
  font-size: 12px;
}

.route-seq-item > span {
  flex: 1;
  color: #dff8ff;
  font-size: 13px;
}

.route-seq-actions {
  display: flex;
  gap: 4px;
}

.route-seq-actions button {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(99, 171, 210, .3);
  border-radius: 5px;
  color: #9cc7da;
  background: rgba(20, 62, 84, .5);
  cursor: pointer;
}

.route-seq-actions button:disabled {
  opacity: .35;
  cursor: default;
}

.route-seq-actions button.danger {
  color: #ff9a8c;
  border-color: rgba(255, 120, 110, .3);
}

:deep(.route-editor) {
  border: 1px solid rgba(87, 153, 190, .28);
  border-radius: 10px;
  background: #0a1c2b;
  color: #dcecf8;
}

:deep(.route-editor .el-dialog__title) {
  color: #f0fbff;
}

:deep(.route-editor .el-dialog__body) {
  padding: 18px 20px;
}

:deep(.route-editor .el-dialog__footer) {
  padding-top: 14px;
  border-top: 1px solid rgba(87, 153, 190, .16);
}

@keyframes chargeGlow {
  0%,
  100% {
    box-shadow:
      0 0 14px rgba(67, 230, 184, .18),
      inset 0 0 18px rgba(67, 230, 184, .06);
  }
  50% {
    box-shadow:
      0 0 28px rgba(67, 230, 184, .36),
      inset 0 0 28px rgba(67, 230, 184, .13);
  }
}

@keyframes pulse {
  0% {
    transform: scale(.72);
    opacity: .95;
  }
  100% {
    transform: scale(1.35);
    opacity: 0;
  }
}

:deep(.el-drawer) {
  background: #071724;
  color: #dcecf8;
}

:deep(.el-drawer__header) {
  margin-bottom: 10px;
  color: #f0fbff;
}

:deep(.el-segmented) {
  --el-segmented-bg-color: rgba(4, 17, 28, .72);
  --el-segmented-item-selected-bg-color: rgba(47, 177, 224, .32);
  --el-segmented-item-selected-color: #eafaff;
  --el-segmented-item-hover-color: #eafaff;
  --el-border-radius-base: 6px;
}

/* 中等视口：路线编排占整行，当前任务与设备状态并排，避免控件被挤压溢出 */
@media (max-width: 1520px) {
  .command-panel {
    grid-template-columns: minmax(0, 1fr) minmax(280px, 1fr);
  }

  .route-builder {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1180px) {
  .overview-bar,
  .command-panel,
  .workspace {
    grid-template-columns: 1fr;
  }

  .status-summary {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }

  .control-grid {
    flex-wrap: wrap;
  }

  .control-grid .dog-picker,
  .control-grid .route-picker {
    flex: 1 1 40%;
    min-width: 170px;
  }

  .workspace {
    min-height: auto;
  }
}

@media (max-width: 720px) {
  .machine-dog-page {
    padding: 12px;
  }

  .status-summary,
  .task-metrics {
    grid-template-columns: 1fr;
  }

  .control-grid {
    flex-direction: column;
    align-items: stretch;
  }

  .control-grid .dog-picker,
  .control-grid .route-picker {
    flex: 1 1 auto;
    width: 100%;
  }

  .control-grid .ctrl-btn {
    width: 100%;
  }

  .map-area {
    height: 280px;
  }
}
</style>
