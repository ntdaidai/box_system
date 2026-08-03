<template>
  <div class="zone-config-page">
    <header class="config-header">
      <div>
        <h1>多级风险区域配置</h1>
      </div>
      <div class="header-actions">
        <el-select
          v-model="currentCameraId"
          class="camera-select zone-config-select"
          popper-class="zone-config-select-popper"
          placeholder="选择摄像头"
          @change="activateCamera"
        >
          <el-option
            v-for="camera in cameras"
            :key="camera.id"
            :label="camera.name"
            :value="camera.id"
          />
        </el-select>
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
              :key="zone.id"
              class="editable-zone"
              :class="{ selected: zone.id === selectedZoneId, disabled: !zone.enabled }"
              @click.stop="handleZoneClick(zone.id, $event)"
            >
              <polygon
                v-if="zone.polygon_points.length >= 3"
                :points="zonePolygonPoints(zone)"
                :stroke="zoneColor(zone)"
                :fill="zoneFill(zone)"
                :stroke-width="zone.id === selectedZoneId ? 4 : 2"
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
                :font-size="zoneLabelFontSize"
              >
                {{ zone.zone_name || zoneTypeLabel(zone.zone_type) }}
              </text>
              <g
                v-for="(point, index) in zone.polygon_points"
                v-show="showZoneAnchors(zone)"
                :key="`${zone.id}-${index}`"
                class="vertex-marker"
                @click.stop.prevent
              >
                <circle
                  class="vertex-anchor"
                  :cx="point.x * overlayWidth"
                  :cy="point.y * overlayHeight"
                  :r="vertexAnchorRadius"
                  @mousedown.stop.prevent="startDrag(zone.id, index, $event)"
                />
                <text
                  class="vertex-index"
                  :x="vertexLabelPoint(point).x"
                  :y="vertexLabelPoint(point).y"
                  :font-size="vertexIndexFontSize"
                >
                  {{ index + 1 }}
                </text>
              </g>
            </g>
          </svg>
          <div v-if="streamLoading" class="stage-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在获取摄像头画面</span>
          </div>
          <div v-if="drawing" class="draw-tip">正在新增区域：点击画面添加顶点</div>
        </div>
        <div class="editor-toolbar">
          <span class="toolbar-note">顶点只在配置模式显示，可拖拽微调。</span>
        </div>
      </article>

      <section class="zone-list-section">
        <div class="list-heading">
          <div>
            <span>当前摄像头区域列表</span>
            <b>共 {{ zones.length }} 个区域</b>
          </div>
          <div class="list-actions">
            <el-button class="tool-button" :class="{ active: drawing }" @click="drawing ? exitDrawing() : startNewZone()">
              <el-icon><EditPen /></el-icon>{{ drawing ? '退出新增' : '新增区域' }}
            </el-button>
            <el-button class="save-button" :loading="saving" @click="saveZones">
              <el-icon><Check /></el-icon>保存配置
            </el-button>
          </div>
        </div>
        <div class="zone-table">
          <div class="zone-table-head">
            <span>区域名</span>
            <span>区域类型</span>
            <span>触发时间</span>
            <span>启用状态</span>
            <span>配置时间</span>
            <span>操作</span>
          </div>
          <div
            v-for="zone in zones"
            :key="zone.id"
            class="zone-table-row"
            :class="{ selected: zone.id === selectedZoneId, disabled: !zone.enabled }"
            @click="selectZone(zone.id)"
          >
            <strong>
              <i :style="{ background: zoneColor(zone) }"></i>
              {{ zone.zone_name || zoneTypeLabel(zone.zone_type) }}
            </strong>
            <span>{{ zoneTypeLabel(zone.zone_type) }}</span>
            <div class="trigger-cell" @click.stop>
              <span v-if="zone.zone_type === 'FISHING'">多条件</span>
              <el-input-number
                v-else
                v-model="zone.trigger_seconds"
                :min="0"
                :max="3600"
                :step="1"
                :controls="false"
                size="small"
              />
            </div>
            <span>
              <button
                type="button"
                class="zone-enable-toggle"
                :class="{ active: zone.enabled }"
                @click.stop="zone.enabled = !zone.enabled"
              >
                <i></i>{{ zone.enabled ? '启用' : '未启用' }}
              </button>
            </span>
            <span>{{ formatZoneTime(zone) }}</span>
            <div class="row-actions">
              <button type="button" class="row-edit" @click.stop="openZoneEditor(zone.id)">
                编辑
              </button>
              <button type="button" class="row-delete" @click.stop="deleteZone(zone.id)">
                删除
              </button>
            </div>
          </div>
          <div v-if="!zones.length" class="zone-table-empty">暂无区域配置</div>
        </div>
      </section>
    </section>

    <el-dialog
      v-model="editDialogVisible"
      append-to-body
      class="zone-editor-dialog"
      title="区域点位配置"
      width="760px"
    >
      <el-form v-if="selectedZone" label-position="top" class="zone-form">
          <el-form-item label="区域类型">
            <el-select
              v-model="selectedZone.zone_type"
              class="zone-config-select"
              popper-class="zone-config-select-popper"
              @change="applyTypeDefaults"
            >
              <el-option label="低风险区" value="PERSON_LOW" />
              <el-option label="中风险区" value="PERSON_MEDIUM" />
              <el-option label="高风险区" value="PERSON_HIGH" />
              <el-option label="捕鱼区" value="FISHING" />
            </el-select>
          </el-form-item>
          <div v-if="selectedZone.zone_type === 'FISHING'" class="fishing-duration-grid">
            <el-form-item label="船只闯入（秒）"><el-input-number v-model="selectedZone.condition_durations.BOAT_INTRUSION" :min="0" :max="3600" /></el-form-item>
            <el-form-item label="船只停留（秒）"><el-input-number v-model="selectedZone.condition_durations.BOAT_STAY" :min="0" :max="3600" /></el-form-item>
            <el-form-item label="船只偷捕（秒）"><el-input-number v-model="selectedZone.condition_durations.BOAT_ILLEGAL_FISHING" :min="0" :max="3600" /></el-form-item>
          </div>
          <section class="ros-panel">
            <div class="ros-heading">
              <strong>区域顶点 (ROS)</strong>
              <b>顶点 {{ selectedZone.polygon_points.length }}</b>
            </div>
            <div class="ros-unit">
              <i></i>
              <span>坐标以视频画面左下角为原点，支持直接微调顶点坐标</span>
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
                <span>X</span>
                <span>Y</span>
                <span>操作</span>
              </div>
              <div
                v-for="(point, index) in selectedZone.polygon_points"
                :key="`${selectedZone.id}-point-${index}`"
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
                </div>
                <button type="button" class="point-delete" @click="deletePoint(index)">删除</button>
              </div>
              <div v-if="!selectedZone.polygon_points.length" class="point-empty">暂无顶点</div>
            </div>
            <button
              type="button"
              class="add-point-button"
              :disabled="selectedZone.polygon_points.length >= 15"
              @click="appendVertex"
            >
              <el-icon><Plus /></el-icon>新增顶点
            </button>
          </section>
        </el-form>
        <div v-else class="panel-empty">请选择一个区域进行编辑。</div>
      <template #footer>
        <el-button class="exit-button" @click="editDialogVisible = false">完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Check, EditPen, Loading, Plus,
} from '@element-plus/icons-vue'
import {
  createStreamTicket, getCameraList, getCameraZones, saveCameraZones,
} from '@/api/camera'
import {
  defaultTriggerSeconds, normalizeZones, zoneTypeLabel,
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
const editDialogVisible = ref(false)

const overlayWidth = computed(() => Number(stageImageRef.value?.naturalWidth) || 1920)
const overlayHeight = computed(() => Number(stageImageRef.value?.naturalHeight) || 1080)
const selectedZone = computed(() => zones.value.find((zone) => zone.id === selectedZoneId.value) || null)
const zoneLabelFontSize = computed(() => Math.max(16, Math.min(64, overlayWidth.value * 0.022)))
const vertexAnchorRadius = computed(() => Math.max(6, Math.min(28, overlayWidth.value * 0.007)))
const vertexIndexFontSize = computed(() => Math.max(13, Math.min(42, overlayWidth.value * 0.016)))

function formatTriggerSeconds(value) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds)) return '--'
  return `${Number(seconds.toFixed(3))} 秒`
}

function formatZoneTime(zone) {
  const value = zone?.update_time
    || zone?.updated_at
    || zone?.config_time
    || zone?.configured_at
    || zone?.create_time
    || zone?.created_at
  if (!value) return '--'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadCameras() {
  const response = await getCameraList()
  cameras.value = (response.data?.cameras || []).map((camera) => ({ ...camera, id: String(camera.id) }))
  currentCameraId.value = String(route.query.camera_id || cameras.value[0]?.id || '')
}

async function activateCamera() {
  zones.value = []
  selectedZoneId.value = ''
  drawing.value = false
  editDialogVisible.value = false
  await Promise.all([loadZones(), refreshStream()])
}

async function loadZones() {
  if (!currentCameraId.value) return
  const response = await getCameraZones(currentCameraId.value)
  zones.value = normalizeZones(response.data)
  selectedZoneId.value = zones.value[0]?.id || ''
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
  const svg = event.currentTarget?.ownerSVGElement
    || event.currentTarget?.closest?.('svg')
    || event.currentTarget
  const screenMatrix = svg?.getScreenCTM?.()
  if (svg?.createSVGPoint && screenMatrix) {
    const screenPoint = svg.createSVGPoint()
    screenPoint.x = event.clientX
    screenPoint.y = event.clientY
    const point = screenPoint.matrixTransform(screenMatrix.inverse())
    return {
      x: Math.max(0, Math.min(1, point.x / overlayWidth.value)),
      y: Math.max(0, Math.min(1, point.y / overlayHeight.value)),
    }
  }
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
  const zoneType = 'PERSON_LOW'
  const id = `${zoneType}_${Date.now()}`
  const zone = {
    id,
    zone_name: `低风险区 ${zones.value.length + 1}`,
    name: `低风险区 ${zones.value.length + 1}`,
    zone_type: zoneType,
    type: zoneType,
    polygon_points: [],
    trigger_seconds: defaultTriggerSeconds(zoneType),
    condition_durations: {},
    enabled: true,
  }
  zones.value = [...zones.value, zone]
  selectedZoneId.value = id
  return zone
}

function startNewZone() {
  createZone()
  drawing.value = true
  editDialogVisible.value = false
}

function exitDrawing() {
  drawing.value = false
}

function appendPointToSelectedZone(point) {
  if (!selectedZone.value) return
  if (selectedZone.value.polygon_points.length >= 15) {
    ElMessage.warning('单个区域最多支持 15 个顶点')
    return
  }
  selectedZone.value.polygon_points = [
    ...selectedZone.value.polygon_points,
    { ...point },
  ]
}

function selectZone(zoneId) {
  selectedZoneId.value = zoneId
}

function openZoneEditor(zoneId) {
  selectZone(zoneId)
  drawing.value = false
  editDialogVisible.value = true
}

function showZoneAnchors(zone) {
  return zone.id === selectedZoneId.value || (drawing.value && zone.polygon_points.length > 0)
}

function startDrag(zoneId, index) {
  selectedZoneId.value = zoneId
  dragging.value = { zoneId, index }
}

function dragVertex(event) {
  if (!dragging.value) return
  const point = pointerToUnitPoint(event)
  const zone = zones.value.find((item) => item.id === dragging.value.zoneId)
  if (!zone) return
  zone.polygon_points[dragging.value.index] = point
}

function endDrag() {
  dragging.value = null
}

function deleteZone(zoneId) {
  zones.value = zones.value.filter((zone) => zone.id !== zoneId)
  selectedZoneId.value = zones.value[0]?.id || ''
  if (editDialogVisible.value && !selectedZone.value) editDialogVisible.value = false
  if (!selectedZoneId.value) drawing.value = false
}

function deletePoint(index) {
  if (!selectedZone.value) return
  selectedZone.value.polygon_points.splice(index, 1)
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
  selectedZone.value.trigger_seconds = defaultTriggerSeconds(zoneType)
  selectedZone.value.condition_durations = zoneType === 'FISHING'
    ? { BOAT_INTRUSION: 0, BOAT_STAY: 30, BOAT_ILLEGAL_FISHING: 120 }
    : {}
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
}

function zoneLabelPoint(zone) {
  const point = polygonCenterPoint(zone.polygon_points)
  return {
    x: point.x * overlayWidth.value,
    y: point.y * overlayHeight.value,
  }
}

function polygonCenterPoint(points = []) {
  if (!points.length) return { x: 0.5, y: 0.5 }
  if (points.length < 3) return averagePoint(points)

  let area = 0
  let centerX = 0
  let centerY = 0
  points.forEach((point, index) => {
    const next = points[(index + 1) % points.length]
    const cross = point.x * next.y - next.x * point.y
    area += cross
    centerX += (point.x + next.x) * cross
    centerY += (point.y + next.y) * cross
  })

  if (Math.abs(area) < 0.000001) return averagePoint(points)
  const factor = 1 / (3 * area)
  return {
    x: Math.max(0, Math.min(1, centerX * factor)),
    y: Math.max(0, Math.min(1, centerY * factor)),
  }
}

function averagePoint(points) {
  const total = points.reduce((sum, point) => ({
    x: sum.x + point.x,
    y: sum.y + point.y,
  }), { x: 0, y: 0 })
  return {
    x: total.x / points.length,
    y: total.y / points.length,
  }
}

function vertexLabelPoint(point) {
  const anchorX = point.x * overlayWidth.value
  const anchorY = point.y * overlayHeight.value
  const offset = vertexAnchorRadius.value + vertexIndexFontSize.value * 0.82
  const rightX = anchorX + offset
  const leftX = anchorX - offset * 1.35
  const belowY = anchorY + offset
  const aboveY = anchorY - offset * 0.72

  return {
    x: rightX < overlayWidth.value - offset ? rightX : Math.max(12, leftX),
    y: anchorY < offset ? belowY : Math.max(vertexIndexFontSize.value, aboveY),
  }
}

function zoneColor(zone) {
  return ({
    PERSON_LOW: '#48d8ff',
    PERSON_MEDIUM: '#ffbd65',
    PERSON_HIGH: '#ff5d6c',
    FISHING: '#57df9a',
  })[zone.zone_type] || '#48d8ff'
}

function zoneFill(zone) {
  return zone.enabled ? `${zoneColor(zone)}22` : 'rgba(120, 139, 153, 0.12)'
}

async function saveZones() {
  if (!currentCameraId.value) return false
  const invalidZone = zones.value.find((zone) => zone.polygon_points.length < 3 || zone.polygon_points.length > 15)
  if (invalidZone) {
    selectedZoneId.value = invalidZone.id
    ElMessage.warning('多边形区域必须包含 3 到 15 个顶点')
    return false
  }
  saving.value = true
  try {
    const payload = zones.value.map((zone) => ({
      id: zone.id,
      zone_name: zone.zone_name,
      zone_type: zone.zone_type,
      polygon_points: zone.polygon_points,
      trigger_seconds: zone.trigger_seconds,
      condition_durations: zone.condition_durations,
      enabled: zone.enabled,
    }))
    const response = await saveCameraZones(currentCameraId.value, payload)
    zones.value = normalizeZones(response.data)
    selectedZoneId.value = zones.value.find((zone) => zone.id === selectedZoneId.value)?.id || zones.value[0]?.id || ''
    ElMessage.success(response.data.message || '区域配置已保存')
    return true
  } finally {
    saving.value = false
  }
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
.zone-config-select :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: 6px;
  background: rgba(7, 30, 46, 0.92);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.28) inset;
}
.zone-config-select :deep(.el-select__wrapper:hover),
.zone-config-select :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.72) inset, 0 0 14px rgba(72, 216, 255, 0.14);
}
.zone-config-select :deep(.el-select__selected-item),
.zone-config-select :deep(.el-select__placeholder) {
  color: #e6f7ff;
  font-weight: 700;
}
.zone-config-select :deep(.el-select__placeholder.is-transparent) {
  color: #8fb0c2;
  font-weight: 500;
}
.zone-config-select :deep(.el-select__caret) { color: #8ddcf0; }
.save-button {
  color: #061b23;
  border: none;
  font-weight: 800;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.config-workspace {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.video-editor,
.config-panel,
.zone-list-section {
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
.zone-editor-overlay,
.zone-name,
.vertex-index {
  user-select: none;
  -webkit-user-select: none;
}
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
  font-weight: 900;
  dominant-baseline: central;
  paint-order: stroke;
  pointer-events: none;
  stroke: rgba(3, 12, 18, 0.92);
  stroke-width: 3.5px;
  text-anchor: middle;
}
.vertex-anchor {
  fill: #f5fbff;
  stroke: #061b23;
  stroke-width: 2.5px;
  vector-effect: non-scaling-stroke;
  cursor: grab;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.85));
}
.vertex-index {
  fill: #ffffff;
  font-weight: 900;
  paint-order: stroke;
  pointer-events: none;
  stroke: rgba(3, 12, 18, 0.95);
  stroke-width: 3px;
  text-anchor: middle;
  dominant-baseline: central;
  filter: drop-shadow(0 0 4px rgba(72, 216, 255, 0.78));
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
  pointer-events: none;
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
  pointer-events: none;
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
.zone-list-section {
  min-width: 0;
  padding: 12px;
}
.list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}
.list-heading > div:first-child {
  display: flex;
  align-items: baseline;
  gap: 10px;
  color: #9bbbd0;
  font-size: 16px;
  font-weight: 900;
}
.list-heading b {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  color: #061b23;
  border-radius: 7px;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
  font-size: 13px;
  font-weight: 900;
}
.list-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.zone-table {
  width: 100%;
  overflow-x: auto;
}
.zone-table-head,
.zone-table-row {
  min-width: 980px;
  display: grid;
  grid-template-columns: minmax(190px, 1.4fr) 130px 128px 124px 168px 140px;
  align-items: center;
  gap: 14px;
}
.zone-table-head {
  min-height: 38px;
  padding: 0 12px;
  color: #8fb0c2;
  border-bottom: 1px solid rgba(80, 165, 200, 0.16);
  font-size: 13px;
  font-weight: 900;
}
.zone-table-row {
  min-height: 58px;
  margin-top: 8px;
  padding: 8px 12px;
  color: #cfe5ee;
  border: 1px solid rgba(85, 166, 201, 0.14);
  border-radius: 8px;
  background: rgba(8, 31, 47, 0.58);
  cursor: pointer;
}
.zone-table-row:hover,
.zone-table-row.selected {
  border-color: rgba(72, 216, 255, 0.48);
  background: rgba(9, 43, 65, 0.72);
}
.zone-table-row.disabled { opacity: 0.56; }
.zone-table-row strong {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone-table-row strong i {
  width: 4px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: 2px;
}
.risk-cell {
  color: #8ddcf0;
  font-weight: 900;
}
.trigger-cell {
  min-width: 0;
  display: flex;
  align-items: center;
}
.trigger-cell > span {
  color: #8ddcf0;
  font-size: 12px;
  font-weight: 900;
}
.trigger-cell :deep(.el-input-number) { width: 86px; }
.trigger-cell :deep(.el-input__wrapper) {
  min-height: 30px;
  border-radius: 7px;
  background: rgba(3, 18, 29, 0.66);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.18) inset;
}
.trigger-cell :deep(.el-input__inner) {
  color: #dff5ff;
  font-weight: 800;
}
.zone-enable-toggle {
  min-width: 84px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid rgba(127, 155, 176, 0.28);
  border-radius: 999px;
  color: #9bbbd0;
  background: rgba(15, 39, 55, 0.72);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.zone-enable-toggle i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7f9bb0;
}
.zone-enable-toggle.active {
  color: #061b23;
  border-color: transparent;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.zone-enable-toggle.active i {
  background: #061b23;
  box-shadow: 0 0 8px rgba(6, 27, 35, 0.38);
}
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.row-edit,
.row-delete {
  min-width: 58px;
  height: 32px;
  border-radius: 6px;
  font: inherit;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}
.row-edit {
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.46);
  background: rgba(11, 73, 78, 0.52);
}
.row-delete {
  color: #ff8b9a;
  border: 1px solid rgba(255, 93, 108, 0.34);
  background: rgba(72, 32, 48, 0.58);
}
.row-edit:hover {
  color: #e9fff9;
  border-color: rgba(81, 230, 190, 0.72);
}
.row-delete:hover {
  color: #ffd5d9;
  border-color: rgba(255, 93, 108, 0.58);
}
.zone-table-empty {
  min-height: 92px;
  display: grid;
  place-items: center;
  color: #6f8da0;
  border: 1px dashed rgba(54, 221, 212, 0.28);
  border-radius: 8px;
}
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
.zone-form .zone-config-select { width: 100%; }
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
  min-width: 64px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.48);
  border-radius: 999px;
  background: rgba(4, 45, 55, 0.76);
  font-size: 12px;
  font-weight: 900;
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
.coordinate-field :deep(.el-input__wrapper) { padding-right: 11px; }
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
:global(.zone-config-select-popper.el-select__popper) {
  border: 1px solid rgba(72, 216, 255, 0.28);
  background: #082033;
  box-shadow: 0 16px 36px rgba(0, 7, 18, 0.38);
}
:global(.zone-config-select-popper .el-popper__arrow::before) {
  border-color: rgba(72, 216, 255, 0.28);
  background: #082033;
}
:global(.zone-config-select-popper .el-select-dropdown__item) {
  color: #aecdde;
}
:global(.zone-config-select-popper .el-select-dropdown__item.is-hovering),
:global(.zone-config-select-popper .el-select-dropdown__item:hover) {
  color: #e9fbff;
  background: rgba(72, 216, 255, 0.12);
}
:global(.zone-config-select-popper .el-select-dropdown__item.is-selected),
:global(.zone-config-select-popper .el-select-dropdown__item.selected) {
  color: #50e1d0;
  font-weight: 800;
}
:global(.zone-editor-dialog) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  border-radius: 8px;
  background: #061a28;
  box-shadow: 0 26px 70px rgba(0, 7, 18, 0.62);
}
:global(.zone-editor-dialog .el-dialog__header) {
  margin: 0;
  padding: 18px 20px 12px;
  border-bottom: 1px solid rgba(80, 165, 200, 0.14);
}
:global(.zone-editor-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
}
:global(.zone-editor-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #8ddcf0;
}
:global(.zone-editor-dialog .el-dialog__body) {
  padding: 16px 20px;
  color: #d7edf6;
}
:global(.zone-editor-dialog .el-dialog__footer) {
  padding: 0 20px 18px;
}
@media (max-width: 1000px) {
  .config-header,
  .header-actions { align-items: stretch; flex-direction: column; }
  .camera-select { width: 100%; }
  .list-heading,
  .list-actions { align-items: stretch; flex-direction: column; }
  .list-heading { align-items: stretch; }
}
</style>
