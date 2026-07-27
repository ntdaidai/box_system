<template>
  <div class="zone-config-page">
    <header class="config-header">
      <div>
        <h1>多级风险区域配置</h1>
      </div>
      <div class="header-actions">
        <el-select v-model="currentCameraId" class="camera-select" placeholder="选择摄像头" @change="activateCamera">
          <el-option
            v-for="camera in cameras"
            :key="camera.camera_id"
            :label="camera.name || camera.camera_id"
            :value="camera.camera_id"
          />
        </el-select>
        <el-button class="save-button" :loading="saving" @click="saveZones">
          <el-icon><Check /></el-icon>保存配置
        </el-button>
      </div>
    </header>

    <section class="config-workspace">
      <article class="video-editor">
        <div class="editor-stage">
          <img
            v-if="streamUrl"
            ref="stageImageRef"
            :src="streamUrl"
            class="video-stream"
            alt="摄像头实时画面"
            @load="streamLoading = false"
            @error="refreshStream"
          />
          <svg
            class="zone-editor-overlay"
            :viewBox="`0 0 ${overlayWidth} ${overlayHeight}`"
            preserveAspectRatio="xMidYMid meet"
            @click="handleOverlayClick"
            @mousemove="dragVertex"
            @mouseup="endDrag"
            @mouseleave="endDrag"
          >
            <g
              v-for="zone in zones"
              :key="zone.zone_id"
              class="editable-zone"
              :class="{ selected: zone.zone_id === selectedZoneId, disabled: !zone.enabled }"
              @click.stop="handleZoneClick(zone.zone_id, $event)"
            >
              <polygon
                v-if="zone.polygon_points.length >= 3"
                :points="zonePolygonPoints(zone)"
                :stroke="zoneColor(zone)"
                :fill="zoneFill(zone)"
                :stroke-width="zone.zone_id === selectedZoneId ? 4 : 2"
              />
              <polyline
                v-else-if="zone.polygon_points.length"
                class="zone-polyline"
                :points="zonePolygonPoints(zone)"
                :stroke="zoneColor(zone)"
              />
              <text
                v-if="zone.polygon_points.length"
                class="zone-name"
                :x="zoneLabelPoint(zone).x"
                :y="zoneLabelPoint(zone).y"
                :fill="zoneColor(zone)"
              >
                {{ zone.zone_name || zoneTypeLabel(zone.zone_type) }}
              </text>
              <circle
                v-for="(point, index) in zone.polygon_points"
                v-show="zone.zone_id === selectedZoneId"
                :key="`${zone.zone_id}-${index}`"
                class="vertex-anchor"
                :cx="point.x * overlayWidth"
                :cy="point.y * overlayHeight"
                r="7"
                @mousedown.stop.prevent="startDrag(zone.zone_id, index, $event)"
              />
            </g>
          </svg>
          <div v-if="streamLoading" class="stage-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在获取摄像头画面</span>
          </div>
          <div v-if="drawing" class="draw-tip">正在新增区域：点击画面添加顶点，右侧可编辑坐标</div>
        </div>
        <div class="editor-toolbar">
          <el-button class="tool-button" :class="{ active: drawing }" @click="drawing ? exitDrawing() : startNewZone()">
            <el-icon><EditPen /></el-icon>{{ drawing ? '退出新增' : '新建区域' }}
          </el-button>
          <el-button class="tool-button danger" :disabled="!selectedZone" @click="deleteSelectedZone">
            <el-icon><Delete /></el-icon>删除区域
          </el-button>
          <span class="toolbar-note">顶点只在配置模式显示，可拖拽微调。</span>
        </div>
      </article>

      <aside class="config-panel">
        <div class="panel-heading">
          <span>区域列表</span>
          <b>{{ zones.length }}</b>
        </div>
        <div class="zone-list">
          <button
            v-for="zone in zones"
            :key="zone.zone_id"
            type="button"
            class="zone-row"
            :class="{ selected: zone.zone_id === selectedZoneId, disabled: !zone.enabled }"
            @click="selectZone(zone.zone_id)"
          >
            <i :style="{ background: zoneColor(zone) }"></i>
            <strong>{{ zone.zone_name || zoneTypeLabel(zone.zone_type) }}</strong>
            <span>{{ riskLevelLabel(zone.risk_level) }}</span>
          </button>
        </div>

        <el-form v-if="selectedZone" label-position="top" class="zone-form">
          <el-form-item label="区域类型">
            <el-select v-model="selectedZone.zone_type" @change="applyTypeDefaults">
              <el-option label="警戒区" value="WARNING_ZONE" />
              <el-option label="亲水区" value="WATERFRONT_ZONE" />
              <el-option label="涉水区" value="WATER_ZONE" />
            </el-select>
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="触发时间">
              <el-input-number v-model="selectedZone.trigger_seconds" :min="0" :max="3600" :step="1" controls-position="right" />
            </el-form-item>
            <el-form-item label="风险等级">
              <el-select v-model="selectedZone.risk_level">
                <el-option label="低风险" value="LOW" />
                <el-option label="中风险" value="MEDIUM" />
                <el-option label="高风险" value="HIGH" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="启用状态">
            <div class="zone-state-control" role="group" aria-label="启用状态">
              <button
                type="button"
                :class="{ active: selectedZone.enabled }"
                @click="selectedZone.enabled = true"
              >
                启用监测
              </button>
              <button
                type="button"
                :class="{ active: !selectedZone.enabled }"
                @click="selectedZone.enabled = false"
              >
                暂停监测
              </button>
            </div>
          </el-form-item>
          <section class="ros-panel">
            <div class="ros-heading">
              <strong>区域顶点 (ROS)</strong>
              <b>{{ selectedZone.polygon_points.length }}</b>
            </div>
            <div class="ros-unit">
              <i></i>
              <span>单位: m，支持直接微调顶点坐标</span>
            </div>
            <div class="ros-name-field">
              <div class="field-title">
                <strong>区域名称</strong>
                <span>用于保存与回显</span>
              </div>
              <el-input v-model="selectedZone.zone_name" maxlength="80" placeholder="请输入区域名称" />
            </div>
            <div class="point-table">
              <div class="point-head">
                <span>序号</span>
                <span>X (m)</span>
                <span>Y (m)</span>
                <span>操作</span>
              </div>
              <div
                v-for="(point, index) in selectedZone.polygon_points"
                :key="`${selectedZone.zone_id}-point-${index}`"
                class="point-row"
              >
                <strong>#{{ index + 1 }}</strong>
                <div class="coordinate-field">
                  <el-input-number
                    :model-value="pointCoordinateX(point)"
                    :controls="false"
                    :precision="3"
                    :step="0.1"
                    :min="0"
                    :max="overlayWidth"
                    @update:model-value="updatePointCoordinate(index, 'x', $event)"
                  />
                  <span>m</span>
                </div>
                <div class="coordinate-field">
                  <el-input-number
                    :model-value="pointCoordinateY(point)"
                    :controls="false"
                    :precision="3"
                    :step="0.1"
                    :min="0"
                    :max="overlayHeight"
                    @update:model-value="updatePointCoordinate(index, 'y', $event)"
                  />
                  <span>m</span>
                </div>
                <button type="button" class="point-delete" @click="deletePoint(index)">删除</button>
              </div>
              <div v-if="!selectedZone.polygon_points.length" class="point-empty">暂无顶点</div>
            </div>
            <button
              type="button"
              class="add-point-button"
              :disabled="selectedZone.polygon_points.length >= 20"
              @click="appendVertex"
            >
              <el-icon><Plus /></el-icon>新增顶点
            </button>
            <div v-if="drawing" class="new-zone-actions">
              <el-button class="continue-button" :loading="saving" @click="saveAndContinue">
                <el-icon><Check /></el-icon>保存并继续
              </el-button>
              <el-button class="exit-button" @click="exitDrawing">
                <el-icon><CloseBold /></el-icon>退出新增
              </el-button>
            </div>
          </section>
        </el-form>
        <div v-else class="panel-empty">选择一个区域进行编辑，或在画面中新建多边形。</div>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Check, CloseBold, Delete, EditPen, Loading, Plus,
} from '@element-plus/icons-vue'
import {
  createStreamTicket, getCameraList, getCameraZones, saveCameraZones,
} from '@/api/camera'
import {
  defaultRiskLevel, defaultTriggerSeconds, normalizeZones, polygonBounds, zoneTypeLabel,
} from '@/utils/cameraDetectionView'

const route = useRoute()
const cameras = ref([])
const currentCameraId = ref('')
const zones = ref([])
const selectedZoneId = ref('')
const streamUrl = ref('')
const streamLoading = ref(false)
const stageImageRef = ref(null)
const drawing = ref(false)
const dragging = ref(null)
const saving = ref(false)

const overlayWidth = computed(() => Number(stageImageRef.value?.naturalWidth) || 1920)
const overlayHeight = computed(() => Number(stageImageRef.value?.naturalHeight) || 1080)
const selectedZone = computed(() => zones.value.find((zone) => zone.zone_id === selectedZoneId.value) || null)

function riskLevelLabel(level) {
  return ({
    LOW: '低风险',
    MEDIUM: '中风险',
    HIGH: '高风险',
  })[level] || '低风险'
}

async function loadCameras() {
  const response = await getCameraList()
  cameras.value = response.data?.cameras || []
  currentCameraId.value = String(route.query.camera_id || cameras.value[0]?.camera_id || '')
}

async function activateCamera() {
  zones.value = []
  selectedZoneId.value = ''
  drawing.value = false
  await Promise.all([loadZones(), refreshStream()])
}

async function loadZones() {
  if (!currentCameraId.value) return
  const response = await getCameraZones(currentCameraId.value)
  zones.value = normalizeZones(response.data)
  selectedZoneId.value = zones.value[0]?.zone_id || ''
}

async function refreshStream() {
  if (!currentCameraId.value) return
  streamLoading.value = true
  try {
    const response = await createStreamTicket(currentCameraId.value, false)
    streamUrl.value = response.data.stream_url
    await nextTick()
  } catch {
    streamLoading.value = false
  }
}

function pointerToUnitPoint(event) {
  const svg = event.currentTarget.closest?.('svg') || event.currentTarget
  const rect = svg.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
    y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
  }
}

function handleOverlayClick(event) {
  if (!drawing.value) return
  if (!selectedZone.value) startNewZone()
  const point = pointerToUnitPoint(event)
  appendPointToSelectedZone(point)
}

function handleZoneClick(zoneId, event) {
  if (drawing.value) {
    handleOverlayClick(event)
    return
  }
  selectZone(zoneId)
}

function createZone() {
  const zoneType = 'WARNING_ZONE'
  const id = `${zoneType}_${Date.now()}`
  const zone = {
    zone_id: id,
    id,
    zone_name: `警戒区 ${zones.value.length + 1}`,
    name: `警戒区 ${zones.value.length + 1}`,
    zone_type: zoneType,
    type: zoneType,
    camera_id: currentCameraId.value,
    polygon_points: [],
    rect: null,
    risk_level: defaultRiskLevel(zoneType),
    trigger_seconds: defaultTriggerSeconds(zoneType),
    enabled: true,
  }
  zones.value = [...zones.value, zone]
  selectedZoneId.value = id
  return zone
}

function startNewZone() {
  createZone()
  drawing.value = true
}

function exitDrawing() {
  drawing.value = false
}

function appendPointToSelectedZone(point) {
  if (!selectedZone.value) return
  if (selectedZone.value.polygon_points.length >= 20) {
    ElMessage.warning('单个区域最多支持 20 个顶点')
    return
  }
  selectedZone.value.polygon_points = [
    ...selectedZone.value.polygon_points,
    { ...point },
  ]
  selectedZone.value.rect = polygonBounds(selectedZone.value.polygon_points)
}

function selectZone(zoneId) {
  selectedZoneId.value = zoneId
}

function startDrag(zoneId, index) {
  selectedZoneId.value = zoneId
  dragging.value = { zoneId, index }
}

function dragVertex(event) {
  if (!dragging.value) return
  const point = pointerToUnitPoint(event)
  const zone = zones.value.find((item) => item.zone_id === dragging.value.zoneId)
  if (!zone) return
  zone.polygon_points[dragging.value.index] = point
  zone.rect = polygonBounds(zone.polygon_points)
}

function endDrag() {
  dragging.value = null
}

function deleteSelectedZone() {
  if (!selectedZone.value) return
  zones.value = zones.value.filter((zone) => zone.zone_id !== selectedZoneId.value)
  selectedZoneId.value = zones.value[0]?.zone_id || ''
  if (!selectedZoneId.value) drawing.value = false
}

function deletePoint(index) {
  if (!selectedZone.value) return
  selectedZone.value.polygon_points.splice(index, 1)
  selectedZone.value.rect = polygonBounds(selectedZone.value.polygon_points)
}

function appendVertex() {
  if (!selectedZone.value) startNewZone()
  const points = selectedZone.value?.polygon_points || []
  const lastPoint = points[points.length - 1]
  const point = lastPoint
    ? {
      x: Math.max(0, Math.min(1, lastPoint.x + 0.03)),
      y: Math.max(0, Math.min(1, lastPoint.y + 0.03)),
    }
    : { x: 0.5, y: 0.5 }
  appendPointToSelectedZone(point)
}

function applyTypeDefaults(zoneType) {
  if (!selectedZone.value) return
  selectedZone.value.type = zoneType
  selectedZone.value.risk_level = defaultRiskLevel(zoneType)
  selectedZone.value.trigger_seconds = defaultTriggerSeconds(zoneType)
  if (!selectedZone.value.zone_name) selectedZone.value.zone_name = zoneTypeLabel(zoneType)
}

function zonePolygonPoints(zone) {
  return zone.polygon_points.map((point) => `${point.x * overlayWidth.value},${point.y * overlayHeight.value}`).join(' ')
}

function pointCoordinateX(point) {
  return Number((point.x * overlayWidth.value).toFixed(3))
}

function pointCoordinateY(point) {
  return Number(((1 - point.y) * overlayHeight.value).toFixed(3))
}

function updatePointCoordinate(index, axis, value) {
  if (!selectedZone.value || !Number.isFinite(Number(value))) return
  const point = selectedZone.value.polygon_points[index]
  if (!point) return
  if (axis === 'x') {
    point.x = Math.max(0, Math.min(1, Number(value) / overlayWidth.value))
  } else {
    point.y = Math.max(0, Math.min(1, 1 - (Number(value) / overlayHeight.value)))
  }
  selectedZone.value.rect = polygonBounds(selectedZone.value.polygon_points)
}

function zoneLabelPoint(zone) {
  const first = zone.polygon_points[0] || { x: 0, y: 0 }
  return {
    x: Math.max(12, first.x * overlayWidth.value + 10),
    y: Math.max(22, first.y * overlayHeight.value + 20),
  }
}

function zoneColor(zone) {
  return ({
    WARNING_ZONE: '#48d8ff',
    WATERFRONT_ZONE: '#ffbd65',
    WATER_ZONE: '#ff5d6c',
  })[zone.zone_type] || '#48d8ff'
}

function zoneFill(zone) {
  return zone.enabled ? `${zoneColor(zone)}22` : 'rgba(120, 139, 153, 0.12)'
}

async function saveZones() {
  if (!currentCameraId.value) return false
  const invalidZone = zones.value.find((zone) => zone.polygon_points.length < 3)
  if (invalidZone) {
    selectedZoneId.value = invalidZone.zone_id
    ElMessage.warning('多边形区域至少需要 3 个顶点')
    return false
  }
  saving.value = true
  try {
    const payload = zones.value.map((zone) => ({
      zone_id: zone.zone_id,
      zone_name: zone.zone_name,
      zone_type: zone.zone_type,
      camera_id: currentCameraId.value,
      polygon_points: zone.polygon_points,
      risk_level: zone.risk_level,
      trigger_seconds: zone.trigger_seconds,
      enabled: zone.enabled,
    }))
    const response = await saveCameraZones(currentCameraId.value, payload)
    zones.value = normalizeZones(response.data)
    selectedZoneId.value = zones.value.find((zone) => zone.zone_id === selectedZoneId.value)?.zone_id || zones.value[0]?.zone_id || ''
    ElMessage.success(response.data.message || '区域配置已保存')
    return true
  } finally {
    saving.value = false
  }
}

async function saveAndContinue() {
  const saved = await saveZones()
  if (saved) startNewZone()
}

onMounted(async () => {
  await loadCameras()
  if (currentCameraId.value) await activateCamera()
})
</script>

<style scoped>
.zone-config-page {
  min-height: 100%;
  padding: 14px;
  color: #e9f7ff;
  background: linear-gradient(145deg, #071522, #0a1c2b 58%, #071522);
}
.config-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid rgba(80, 165, 200, 0.14);
  border-radius: 8px;
  background: rgba(5, 22, 34, 0.72);
}
.config-header h1 { margin: 0; font-size: 22px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.camera-select { width: 260px; }
.save-button {
  color: #061b23;
  border: none;
  font-weight: 800;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.config-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 460px;
  gap: 12px;
}
.video-editor,
.config-panel {
  border: 1px solid rgba(80, 165, 200, 0.14);
  border-radius: 8px;
  background: rgba(5, 20, 31, 0.78);
}
.editor-stage {
  position: relative;
  min-height: 560px;
  overflow: hidden;
  border-radius: 8px 8px 0 0;
  background: #020a11;
}
.video-stream,
.zone-editor-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.video-stream { object-fit: cover; }
.zone-editor-overlay { z-index: 2; cursor: crosshair; }
.editable-zone polygon {
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 4px currentColor);
}
.zone-polyline {
  fill: none;
  stroke-width: 3px;
  stroke-dasharray: 9 6;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 4px currentColor);
}
.editable-zone.disabled { opacity: 0.42; }
.zone-name {
  font-size: 16px;
  font-weight: 900;
  paint-order: stroke;
  stroke: rgba(3, 12, 18, 0.92);
  stroke-width: 4px;
}
.vertex-anchor {
  fill: #f5fbff;
  stroke: #061b23;
  stroke-width: 2px;
  cursor: grab;
}
.stage-loading {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: #8ddcf0;
  background: rgba(3, 14, 23, 0.72);
}
.draw-tip {
  position: absolute;
  z-index: 4;
  left: 14px;
  bottom: 14px;
  padding: 8px 11px;
  color: #d7edf6;
  border: 1px solid rgba(245, 251, 255, 0.22);
  border-radius: 7px;
  background: rgba(4, 16, 25, 0.82);
}
.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
}
.tool-button {
  color: #b9d2df;
  border-color: rgba(101, 184, 212, 0.22);
  background: rgba(20, 64, 86, 0.42);
}
.tool-button.active {
  color: #061b23;
  border-color: transparent;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.tool-button.danger:not(.is-disabled):hover {
  color: #ffd5d9;
  border-color: rgba(255, 93, 108, 0.42);
  background: rgba(96, 24, 34, 0.56);
}
.toolbar-note { margin-left: auto; color: #69889a; font-size: 12px; }
.config-panel { min-width: 0; padding: 12px; }
.panel-heading {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #8fb0c2;
}
.panel-heading b { color: #48d8ff; font: 800 18px monospace; }
.zone-list { display: flex; flex-direction: column; gap: 7px; margin-bottom: 12px; }
.zone-row {
  width: 100%;
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 9px;
  color: #cfe5ee;
  border: 1px solid rgba(85, 166, 201, 0.12);
  border-radius: 7px;
  background: rgba(8, 31, 47, 0.58);
  cursor: pointer;
}
.zone-row.selected { border-color: rgba(72, 216, 255, 0.5); }
.zone-row.disabled { opacity: 0.5; }
.zone-row i { width: 4px; height: 30px; border-radius: 2px; }
.zone-row strong {
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone-row span { font: 800 10px monospace; }
.zone-form :deep(.el-form-item__label) { color: #8fb0c2; font-size: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.zone-state-control {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 4px;
  border: 1px solid rgba(85, 166, 201, 0.18);
  border-radius: 9px;
  background: rgba(3, 18, 29, 0.58);
}
.zone-state-control button {
  min-height: 34px;
  border: 1px solid transparent;
  border-radius: 7px;
  color: #8fb0c2;
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.zone-state-control button.active {
  color: #061b23;
  border-color: rgba(72, 216, 255, 0.32);
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.ros-panel {
  margin-top: 4px;
  padding: 12px;
  border: 1px solid rgba(54, 221, 212, 0.42);
  border-radius: 8px;
  background: rgba(8, 30, 48, 0.72);
  box-shadow: inset 0 0 18px rgba(28, 185, 210, 0.08);
}
.ros-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.ros-heading strong {
  color: #e9f7ff;
  font-size: 16px;
}
.ros-heading b {
  min-width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.48);
  border-radius: 50%;
  background: rgba(4, 45, 55, 0.76);
  font: 800 13px monospace;
}
.ros-unit {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #a8c9dc;
  font-size: 12px;
}
.ros-unit i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #51e6be;
  box-shadow: 0 0 12px rgba(81, 230, 190, 0.72);
}
.ros-name-field {
  margin-bottom: 14px;
  padding: 10px;
  border: 1px solid rgba(50, 197, 255, 0.28);
  border-radius: 8px;
  background: rgba(4, 25, 42, 0.64);
}
.field-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.field-title strong { color: #51e6be; font-size: 14px; }
.field-title span { color: #9bbbd0; font-size: 12px; }
.point-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.point-head,
.point-row {
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr) minmax(0, 1fr) 82px;
  align-items: center;
  gap: 8px;
}
.point-head {
  color: #9bbbd0;
  font-size: 12px;
  font-weight: 800;
}
.point-row {
  padding: 8px;
  border: 1px solid rgba(54, 221, 212, 0.28);
  border-radius: 8px;
  background: rgba(7, 40, 55, 0.66);
}
.point-row strong {
  height: 36px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.36);
  border-radius: 7px;
  background: rgba(17, 82, 91, 0.72);
  font: 800 14px monospace;
}
.coordinate-field {
  position: relative;
  min-width: 0;
}
.coordinate-field :deep(.el-input-number) { width: 100%; }
.coordinate-field :deep(.el-input__wrapper) { padding-right: 26px; }
.coordinate-field span {
  position: absolute;
  top: 50%;
  right: 9px;
  color: #a8c9dc;
  font-size: 12px;
  font-weight: 800;
  transform: translateY(-50%);
  pointer-events: none;
}
.point-delete {
  height: 36px;
  border: 1px solid rgba(255, 93, 108, 0.28);
  border-radius: 7px;
  color: #e99099;
  background: rgba(72, 32, 48, 0.58);
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.point-delete:hover {
  color: #ffd5d9;
  border-color: rgba(255, 93, 108, 0.5);
}
.point-empty {
  min-height: 52px;
  display: grid;
  place-items: center;
  color: #6f8da0;
  border: 1px dashed rgba(54, 221, 212, 0.32);
  border-radius: 8px;
}
.add-point-button {
  width: 100%;
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 12px;
  border: 1px dashed rgba(81, 230, 190, 0.7);
  border-radius: 8px;
  color: #51e6be;
  background: rgba(5, 29, 43, 0.62);
  font: inherit;
  font-weight: 900;
  cursor: pointer;
}
.add-point-button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}
.new-zone-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
.continue-button {
  color: #f8fbff;
  border: none;
  font-weight: 900;
  background: #2f67d8;
}
.exit-button {
  color: #fff7ed;
  border: none;
  font-weight: 900;
  background: #f47a16;
}
.panel-empty {
  min-height: 220px;
  display: grid;
  place-items: center;
  color: #668397;
  text-align: center;
}
@media (max-width: 1000px) {
  .config-header,
  .header-actions { align-items: stretch; flex-direction: column; }
  .camera-select { width: 100%; }
  .config-workspace { grid-template-columns: 1fr; }
}
</style>
