<template>
  <div class="machine-dog-page">
    <header class="overview-bar">
      <div class="title-block">
        <span class="eyebrow">系统管理 / 联动系统</span>
        <h2>机器狗巡检调度</h2>
      </div>
      <div class="status-summary">
        <div v-for="item in summaryCards" :key="item.label" class="summary-card" :class="item.className">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
      <el-button class="drawer-entry" :icon="Menu" @click="deviceDrawerVisible = true">
        机器狗列表
      </el-button>
    </header>

    <section class="command-panel">
      <div class="route-builder">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">巡检任务</span>
            <h3>路线编排</h3>
          </div>
          <el-segmented v-model="routeMode" :options="routeModeOptions" size="small" />
        </div>

        <div class="control-grid">
          <el-select v-model="selectedDeviceId" placeholder="选择机器狗" popper-class="dog-select-popper">
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
            placeholder="选择预设路线"
            :disabled="routeMode !== 'preset'"
            @change="applyPresetRoute"
          >
            <el-option v-for="route in presetRoutes" :key="route.id" :label="route.name" :value="route.id" />
          </el-select>
          <el-button :icon="VideoPlay" type="primary" :disabled="!canStartTask" @click="startInspection">
            开始巡检
          </el-button>
          <el-button :icon="RefreshLeft" @click="resetRoute">重置路线</el-button>
        </div>

        <div class="selected-route">
          <div class="selected-route-head">
            <span>已选巡检点</span>
            <strong>{{ selectedWaypoints.length }}</strong>
          </div>
          <div v-if="selectedWaypoints.length" class="route-chip-list">
            <button
              v-for="(point, index) in selectedWaypoints"
              :key="point.id"
              type="button"
              class="route-chip"
              @click="removeWaypoint(point.id)"
            >
              <b>{{ index + 1 }}</b>
              <span>{{ point.name }}</span>
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <div v-else class="route-empty">在地图上点击巡检点，或选择一条预设路线</div>
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
            <strong>{{ activeTask ? Math.round(activeTask.progress) : 0 }}%</strong>
          </div>
          <div>
            <span>预计剩余</span>
            <strong>{{ activeTask ? remainingTimeText : '--' }}</strong>
          </div>
        </div>
        <div class="task-progress">
          <div :style="{ width: `${activeTask?.progress || 0}%` }"></div>
        </div>
      </div>
    </section>

    <section class="workspace">
      <div class="map-area">
        <img src="/dam-map.png" alt="大藤峡地图" class="map-image" draggable="false" />

        <svg class="route-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline v-if="activePolyline" class="route-line route-line-back" :points="activePolyline" />
          <polyline v-if="activePolyline" class="route-line" :points="activePolyline" />
          <polyline v-if="passedPolyline" class="route-line passed" :points="passedPolyline" />
        </svg>

        <button
          v-for="point in waypoints"
          :key="point.id"
          type="button"
          class="waypoint"
          :class="{ selected: selectedWaypointIds.includes(point.id), disabled: routeMode === 'preset' }"
          :style="{ left: `${point.x}%`, top: `${point.y}%` }"
          @click="toggleWaypoint(point)"
        >
          <span class="waypoint-dot">{{ waypointOrder(point.id) || '' }}</span>
          <span class="waypoint-label">{{ point.name }}</span>
        </button>

        <div
          v-for="dog in machineDogs"
          :key="dog.id"
          class="dog-marker"
          :class="[dog.status, { active: dog.id === selectedDeviceId }]"
          :style="{ left: `${dog.position.x}%`, top: `${dog.position.y}%` }"
          @click="selectedDeviceId = dog.id"
        >
          <span class="dog-pulse"></span>
          <span class="dog-body">
            <el-icon><Aim /></el-icon>
          </span>
          <span class="dog-label">{{ dog.name }}</span>
        </div>

        <div class="map-toolbar">
          <span>地图监控</span>
          <button type="button" @click="routeMode = 'custom'">
            <el-icon><Location /></el-icon>
            点选路线
          </button>
          <button type="button" @click="deviceDrawerVisible = true">
            <el-icon><List /></el-icon>
            设备
          </button>
        </div>

        <div class="map-legend">
          <span><i class="legend-dot online"></i>在线</span>
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
            <strong>视频接口占位</strong>
            <span>填入视频地址即可替换实时画面</span>
          </div>
          <div class="scan-grid"></div>
        </div>
        <el-input v-model="videoUrl" class="video-input" clearable placeholder="视频地址，如 /mock/robot-dog.mp4">
          <template #prepend>videoUrl</template>
        </el-input>
        <div class="interface-note">
          <span>预留接口</span>
          <code>GET /api/machine-dogs/:id/live-stream</code>
        </div>
      </aside>
    </section>

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
            <span>信号 <b>{{ dog.signal }}%</b></span>
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
  Close,
  List,
  Location,
  Menu,
  RefreshLeft,
  VideoCamera,
  VideoPlay,
  View,
} from '@element-plus/icons-vue'

const dogStatusMeta = {
  offline: { text: '离线', className: 'offline' },
  online: { text: '在线', className: 'online' },
  running: { text: '巡检中', className: 'running' },
  idle: { text: '待命', className: 'idle' },
  warning: { text: '异常', className: 'warning' },
}

const waypoints = [
  { id: 'p1', name: '坝顶廊道', x: 25.8, y: 33.5 },
  { id: 'p2', name: '闸门平台', x: 43.2, y: 50.6 },
  { id: 'p3', name: '右岸栈桥', x: 58.6, y: 42.2 },
  { id: 'p4', name: '厂房入口', x: 69.4, y: 62.5 },
  { id: 'p5', name: '尾水平台', x: 82.2, y: 54.4 },
  { id: 'p6', name: '升船机区', x: 35.5, y: 66.8 },
]

const presetRoutes = [
  { id: 'route-a', name: '坝面安全巡检', points: ['p1', 'p2', 'p3', 'p5'] },
  { id: 'route-b', name: '厂房周界巡检', points: ['p2', 'p6', 'p4', 'p5'] },
  { id: 'route-c', name: '右岸复核路线', points: ['p3', 'p4', 'p5'] },
]

const machineDogs = ref([
  {
    id: 'dog-01',
    name: '机器狗 A01',
    model: 'Unitree B2',
    status: 'running',
    battery: 76,
    signal: 92,
    location: '坝顶廊道',
    task: '坝面安全巡检',
    position: { x: 32.2, y: 39.8 },
  },
  {
    id: 'dog-02',
    name: '机器狗 A02',
    model: 'Unitree Go2',
    status: 'online',
    battery: 88,
    signal: 86,
    location: '厂房入口',
    task: '',
    position: { x: 69.4, y: 62.5 },
  },
  {
    id: 'dog-03',
    name: '机器狗 B01',
    model: 'DeepRobotics X30',
    status: 'warning',
    battery: 34,
    signal: 61,
    location: '右岸栈桥',
    task: '异常复核',
    position: { x: 58.6, y: 42.2 },
  },
  {
    id: 'dog-04',
    name: '机器狗 B02',
    model: 'DeepRobotics Lite3',
    status: 'offline',
    battery: 0,
    signal: 0,
    location: '充电仓',
    task: '',
    position: { x: 18.6, y: 73.4 },
  },
])

const routeModeOptions = [
  { label: '预设路线', value: 'preset' },
  { label: '地图点选', value: 'custom' },
]

const deviceFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '巡检中', value: 'running' },
  { label: '异常', value: 'warning' },
]

const deviceDrawerVisible = ref(false)
const selectedDeviceId = ref('dog-01')
const selectedPresetRouteId = ref('route-a')
const selectedWaypointIds = ref([...presetRoutes[0].points])
const routeMode = ref('preset')
const deviceFilter = ref('all')
const videoUrl = ref('')
const activeTask = ref({
  id: 'task-demo',
  name: '坝面安全巡检',
  dogId: 'dog-01',
  routePointIds: [...presetRoutes[0].points],
  progress: 28,
})

let timer = null

const selectedDog = computed(() => machineDogs.value.find((dog) => dog.id === selectedDeviceId.value) || null)
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
const activePolyline = computed(() => pointsToPolyline(activeRoutePoints.value))
const passedPolyline = computed(() => {
  if (!activeTask.value || activeRoutePoints.value.length < 2) return ''
  const point = interpolateRoutePoint(activeRoutePoints.value, activeTask.value.progress)
  const passedCount = Math.floor((activeTask.value.progress / 100) * (activeRoutePoints.value.length - 1)) + 1
  const passedPoints = activeRoutePoints.value.slice(0, passedCount)
  return pointsToPolyline([...passedPoints, point])
})
const canStartTask = computed(() =>
  selectedDog.value && selectedDog.value.status !== 'offline' && selectedWaypoints.value.length >= 2
)
const remainingTimeText = computed(() => {
  const progress = activeTask.value?.progress || 0
  return `${Math.max(1, Math.ceil((100 - progress) / 8))} 分钟`
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
    { label: '在线', value: counts.online || 0, className: 'online' },
    { label: '巡检中', value: counts.running || 0, className: 'running' },
    { label: '离线', value: counts.offline || 0, className: 'offline' },
    { label: '异常', value: counts.warning || 0, className: 'warning' },
  ]
})

function pointsToPolyline(points) {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

function interpolateRoutePoint(points, progress) {
  if (!points.length) return { x: 0, y: 0 }
  if (points.length === 1) return points[0]

  const totalSegments = points.length - 1
  const exact = Math.min(99.999, Math.max(0, progress)) / 100 * totalSegments
  const index = Math.floor(exact)
  const local = exact - index
  const start = points[index]
  const end = points[index + 1] || start
  return {
    x: start.x + (end.x - start.x) * local,
    y: start.y + (end.y - start.y) * local,
  }
}

function updateActiveDogPosition() {
  if (!activeTask.value) return
  const dog = machineDogs.value.find((item) => item.id === activeTask.value.dogId)
  if (!dog) return

  activeTask.value.progress += 0.45
  if (activeTask.value.progress >= 100) {
    activeTask.value.progress = 100
    dog.status = 'online'
    dog.task = ''
    activeTask.value = null
    ElMessage.success('巡检任务已完成')
    return
  }

  dog.position = interpolateRoutePoint(activeRoutePoints.value, activeTask.value.progress)
}

function applyPresetRoute(routeId) {
  const route = presetRoutes.find((item) => item.id === routeId)
  if (!route) return
  selectedWaypointIds.value = [...route.points]
}

function toggleWaypoint(point) {
  if (routeMode.value === 'preset') return
  const index = selectedWaypointIds.value.indexOf(point.id)
  if (index >= 0) {
    selectedWaypointIds.value.splice(index, 1)
    return
  }
  selectedWaypointIds.value.push(point.id)
}

function removeWaypoint(pointId) {
  selectedWaypointIds.value = selectedWaypointIds.value.filter((id) => id !== pointId)
  routeMode.value = 'custom'
}

function waypointOrder(pointId) {
  const index = selectedWaypointIds.value.indexOf(pointId)
  return index >= 0 ? index + 1 : ''
}

function resetRoute() {
  selectedWaypointIds.value = []
  selectedPresetRouteId.value = ''
  routeMode.value = 'custom'
}

function startInspection() {
  if (!canStartTask.value) return
  const dog = selectedDog.value
  const routeName = routeMode.value === 'preset'
    ? presetRoutes.find((item) => item.id === selectedPresetRouteId.value)?.name || '临时巡检路线'
    : '临时巡检路线'

  machineDogs.value = machineDogs.value.map((item) => {
    if (item.id === dog.id) {
      return {
        ...item,
        status: 'running',
        task: routeName,
        position: { ...selectedWaypoints.value[0] },
      }
    }
    return item
  })
  activeTask.value = {
    id: `task-${Date.now()}`,
    name: routeName,
    dogId: dog.id,
    routePointIds: [...selectedWaypointIds.value],
    progress: 0,
  }
  ElMessage.success('巡检任务已下发')
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

onMounted(() => {
  timer = window.setInterval(updateActiveDogPosition, 300)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
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

.summary-card.online strong { color: #48e6bf; }
.summary-card.running strong { color: #43d4ff; }
.summary-card.offline strong { color: #8494a3; }
.summary-card.warning strong { color: #ffca66; }

.drawer-entry {
  min-width: 122px;
}

.command-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(310px, .8fr);
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
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(180px, 1fr) auto auto;
  gap: 10px;
  margin-top: 16px;
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
  border: 1px solid rgba(64, 202, 255, .28);
  border-radius: 8px;
  color: #dff8ff;
  background: rgba(30, 118, 150, .28);
  cursor: pointer;
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

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  min-height: 560px;
  margin-top: 14px;
  padding: 16px;
}

.map-area {
  position: relative;
  min-height: 528px;
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

.waypoint {
  position: absolute;
  z-index: 2;
  transform: translate(-50%, -50%);
  display: grid;
  gap: 4px;
  place-items: center;
  border: 0;
  color: #dff8ff;
  background: transparent;
  cursor: pointer;
}

.waypoint.disabled {
  cursor: default;
}

.waypoint-dot {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 2px solid rgba(77, 223, 255, .72);
  border-radius: 50%;
  color: #082232;
  background: #45d7ff;
  box-shadow: 0 0 16px rgba(69, 215, 255, .5);
  font-size: 12px;
  font-weight: 700;
}

.waypoint:not(.selected) .waypoint-dot {
  background: rgba(8, 29, 42, .88);
  color: transparent;
}

.waypoint-label {
  max-width: 86px;
  padding: 3px 7px;
  border-radius: 6px;
  color: #ccecf9;
  background: rgba(4, 17, 28, .74);
  font-size: 12px;
  white-space: nowrap;
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

.dog-marker.running .dog-body { background: #43e6b8; }
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

.map-toolbar,
.map-legend {
  position: absolute;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(111, 183, 220, .22);
  border-radius: 8px;
  background: rgba(5, 19, 31, .78);
  backdrop-filter: blur(8px);
}

.map-toolbar {
  top: 14px;
  left: 14px;
  padding: 8px;
}

.map-toolbar span {
  padding: 0 8px;
  color: #e8f8ff;
  font-weight: 700;
}

.map-toolbar button {
  height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid rgba(71, 204, 255, .24);
  border-radius: 6px;
  color: #c9eefb;
  background: rgba(27, 96, 125, .28);
  cursor: pointer;
}

.map-legend {
  right: 14px;
  bottom: 14px;
  flex-wrap: wrap;
  padding: 8px 10px;
  color: #abc9d7;
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

.legend-dot.running { background: #43e6b8; }
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

.scan-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(84, 216, 255, .08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(84, 216, 255, .08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.video-input {
  margin-top: 12px;
}

.interface-note {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  color: #8cb1c4;
  font-size: 12px;
}

.interface-note code {
  color: #45d7ff;
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

.dog-status.online { color: #49e6bf; background: rgba(73, 230, 191, .12); }
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

:deep(.el-input-group__prepend) {
  color: #84afc5;
  background: rgba(4, 17, 28, .86);
  border-color: rgba(96, 151, 191, .24);
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
    grid-template-columns: repeat(2, minmax(0, 1fr));
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
  .control-grid,
  .task-metrics {
    grid-template-columns: 1fr;
  }

  .map-area {
    min-height: 420px;
  }

  .map-toolbar {
    right: 12px;
    flex-wrap: wrap;
  }
}
</style>
