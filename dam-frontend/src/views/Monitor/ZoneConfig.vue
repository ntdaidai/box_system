<template>
  <div class="zone-config-page">
    <header class="config-header">
      <div>
        <h1>多级风险区域配置</h1>
        <p>为单个摄像头配置多个 Polygon 风险区域，实时监控页仅展示启用区域。</p>
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
        <el-button class="ghost-button" @click="$router.push('/monitor/camera')">
          <el-icon><Monitor /></el-icon>实时监控
        </el-button>
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
            @dblclick.prevent="finishPolygon"
            @mousemove="dragVertex"
            @mouseup="endDrag"
            @mouseleave="endDrag"
          >
            <g
              v-for="zone in zones"
              :key="zone.zone_id"
              class="editable-zone"
              :class="{ selected: zone.zone_id === selectedZoneId, disabled: !zone.enabled }"
              @click.stop="selectZone(zone.zone_id)"
            >
              <polygon
                :points="zonePolygonPoints(zone)"
                :stroke="zoneColor(zone)"
                :fill="zoneFill(zone)"
                :stroke-width="zone.zone_id === selectedZoneId ? 4 : 2"
              />
              <text
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
            <polyline
              v-if="draftPoints.length"
              class="draft-line"
              :points="draftPolyline"
            />
            <circle
              v-for="(point, index) in draftPoints"
              :key="`draft-${index}`"
              class="draft-point"
              :cx="point.x * overlayWidth"
              :cy="point.y * overlayHeight"
              r="6"
            />
          </svg>
          <div v-if="streamLoading" class="stage-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在获取摄像头画面</span>
          </div>
          <div v-if="drawing" class="draw-tip">依次点击添加顶点，双击或点击“完成多边形”结束</div>
        </div>
        <div class="editor-toolbar">
          <el-button class="tool-button" :class="{ active: drawing }" @click="toggleDrawing">
            <el-icon><EditPen /></el-icon>{{ drawing ? '取消绘制' : '新建区域' }}
          </el-button>
          <el-button class="tool-button" :disabled="draftPoints.length < 3" @click="finishPolygon">
            <el-icon><Finished /></el-icon>完成多边形
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
            <span>{{ zone.risk_level }}</span>
          </button>
        </div>

        <el-form v-if="selectedZone" label-position="top" class="zone-form">
          <el-form-item label="区域名称">
            <el-input v-model="selectedZone.zone_name" maxlength="80" />
          </el-form-item>
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
                <el-option label="LOW" value="LOW" />
                <el-option label="MEDIUM" value="MEDIUM" />
                <el-option label="HIGH" value="HIGH" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="启用状态">
            <el-switch v-model="selectedZone.enabled" active-text="启用" inactive-text="禁用" />
          </el-form-item>
          <div class="point-summary">
            <span>zone_id</span>
            <code>{{ selectedZone.zone_id }}</code>
            <span>顶点数</span>
            <code>{{ selectedZone.polygon_points.length }}</code>
          </div>
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
  Check, Delete, EditPen, Finished, Loading, Monitor,
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
const draftPoints = ref([])
const dragging = ref(null)
const saving = ref(false)

const overlayWidth = computed(() => Number(stageImageRef.value?.naturalWidth) || 1920)
const overlayHeight = computed(() => Number(stageImageRef.value?.naturalHeight) || 1080)
const selectedZone = computed(() => zones.value.find((zone) => zone.zone_id === selectedZoneId.value) || null)
const draftPolyline = computed(() => draftPoints.value.map((point) => `${point.x * overlayWidth.value},${point.y * overlayHeight.value}`).join(' '))

async function loadCameras() {
  const response = await getCameraList()
  cameras.value = response.data?.cameras || []
  currentCameraId.value = String(route.query.camera_id || cameras.value[0]?.camera_id || '')
}

async function activateCamera() {
  zones.value = []
  selectedZoneId.value = ''
  draftPoints.value = []
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
  const point = pointerToUnitPoint(event)
  draftPoints.value = [...draftPoints.value, point]
}

function toggleDrawing() {
  drawing.value = !drawing.value
  draftPoints.value = []
}

function finishPolygon() {
  if (draftPoints.value.length < 3) return
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
    polygon_points: draftPoints.value.map((point) => ({ ...point })),
    rect: polygonBounds(draftPoints.value),
    risk_level: defaultRiskLevel(zoneType),
    trigger_seconds: defaultTriggerSeconds(zoneType),
    enabled: true,
  }
  zones.value = [...zones.value, zone]
  selectedZoneId.value = id
  draftPoints.value = []
  drawing.value = false
}

function selectZone(zoneId) {
  selectedZoneId.value = zoneId
}

function startDrag(zoneId, index) {
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
  if (!currentCameraId.value) return
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
.config-header p { margin: 5px 0 0; color: #7f9bb0; font-size: 12px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.camera-select { width: 260px; }
.ghost-button {
  color: #b9d2df;
  border-color: rgba(101, 184, 212, 0.24);
  background: rgba(9, 40, 58, 0.62);
}
.save-button {
  color: #061b23;
  border: none;
  font-weight: 800;
  background: linear-gradient(110deg, #48d8ff, #51e6be);
}
.config-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
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
.draft-line {
  fill: none;
  stroke: #f5fbff;
  stroke-width: 3px;
  stroke-dasharray: 9 6;
}
.draft-point { fill: #f5fbff; }
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
.point-summary {
  display: grid;
  grid-template-columns: 70px minmax(0, 1fr);
  gap: 8px;
  padding: 10px;
  color: #7898aa;
  border-radius: 7px;
  background: rgba(3, 18, 29, 0.46);
}
.point-summary code {
  overflow: hidden;
  color: #cfe5ee;
  text-overflow: ellipsis;
  white-space: nowrap;
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
