<template>
  <div class="zone-config-page">
    <header class="config-header">
      <div class="title-block">
        <h1>区域配置</h1>
        <p>维护摄像头监测区域、画框边界和启用状态</p>
      </div>
      <el-button :icon="Refresh" @click="refreshZones">刷新</el-button>
    </header>

    <section class="zone-toolbar-card">
      <div class="list-heading">
        <div>
          <span>区域列表</span>
        </div>
        <div class="header-actions">
          <el-button class="tool-button new-zone-action" @click="startNewZone">
            <el-icon><EditPen /></el-icon>新增区域
          </el-button>
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
      </div>
    </section>

    <section class="zone-list-section full">
      <div class="zone-table">
        <div class="zone-table-head">
          <span>区域名</span>
          <span>区域类型</span>
          <span>所属点位</span>
          <span>是否启用</span>
          <span>配置时间</span>
          <span>操作</span>
        </div>
        <div
          v-for="zone in pagedZones"
          :key="zone.id"
          class="zone-table-row"
          :class="{ disabled: !zone.enabled }"
        >
          <strong>{{ zone.zone_name || zoneTypeText(zone.zone_type) }}</strong>
          <span>{{ zoneTypeText(zone.zone_type) }}</span>
          <span>{{ zoneCameraName(zone) }}</span>
          <span>
            <el-switch
              :model-value="zone.enabled !== false"
              :loading="zoneEnableLoading[zone.id]"
              @change="(value) => toggleZoneEnabled(zone, value)"
            />
          </span>
          <span>{{ formatZoneTime(zone) }}</span>
          <div class="row-actions">
            <button type="button" class="row-edit" @click.stop="openZoneEditor(zone.id)">
              查看
            </button>
            <button type="button" class="row-delete" @click.stop="deleteZone(zone.id)">
              删除
            </button>
          </div>
        </div>
        <div v-if="!zones.length" class="zone-table-empty">暂无区域配置</div>
      </div>
      <el-pagination
        v-if="zones.length"
        v-model:current-page="zonePage"
        class="list-pagination"
        :page-size="pageSize"
        :total="zones.length"
        layout="prev, pager, next"
      />
    </section>

    <el-dialog
      v-model="drawDialogVisible"
      append-to-body
      class="zone-draw-dialog"
      :title="drawDialogTitle"
      width="1320px"
      @closed="handleDrawDialogClosed"
    >
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
              @mousemove="handleStageMouseMove"
              @mouseup="endDrag"
              @mouseleave="handleStageMouseLeave"
            >
              <g
                v-for="zone in editorZones"
                :key="zone.id"
                class="editable-zone selected"
                :class="{ disabled: !zone.enabled }"
                @click.stop="handleZoneClick(zone.id, $event)"
              >
                <polygon
                  v-if="zone.polygon_points.length >= 3"
                  :points="zonePolygonPoints(zone)"
                  :stroke="zoneColor(zone)"
                  :fill="zoneFill(zone)"
                  stroke-width="4"
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
                  {{ zone.zone_name || zoneTypeText(zone.zone_type) }}
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
              <!-- 矩形画框：已放置的左上角锚点与实时预览虚线框 -->
              <g v-if="rectFirstPoint" class="vertex-marker" @click.stop.prevent>
                <circle
                  class="vertex-anchor"
                  :cx="rectFirstPoint.x * overlayWidth"
                  :cy="rectFirstPoint.y * overlayHeight"
                  :r="vertexAnchorRadius"
                />
                <text
                  class="vertex-index"
                  :x="vertexLabelPoint(rectFirstPoint).x"
                  :y="vertexLabelPoint(rectFirstPoint).y"
                  :font-size="vertexIndexFontSize"
                >
                  1
                </text>
              </g>
              <rect
                v-if="rectPreviewRect"
                class="zone-rect-preview"
                :x="rectPreviewRect.x"
                :y="rectPreviewRect.y"
                :width="rectPreviewRect.width"
                :height="rectPreviewRect.height"
                :stroke="selectedZone ? zoneColor(selectedZone) : '#48d8ff'"
              />
            </svg>
            <div v-if="streamLoading" class="stage-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在获取摄像头画面</span>
            </div>
            <div v-if="drawing" class="draw-tip">{{ drawTipText }}</div>
          </div>
          <div class="editor-toolbar">
            <span class="toolbar-note">{{ currentCameraName }}</span>
          </div>
        </article>

        <aside class="zone-side-editor">
          <div class="side-editor-title">
            <strong>编辑点位</strong>
            <span>{{ selectedZone ? `顶点 ${selectedZone.polygon_points.length}` : '未选择区域' }}</span>
          </div>
          <el-form v-if="selectedZone" label-position="top" class="zone-form">
          <el-form-item label="区域名称">
            <el-input v-model="selectedZone.zone_name" maxlength="80" placeholder="请输入区域名称" />
          </el-form-item>
          <el-form-item label="区域类型">
            <el-select
              v-model="selectedZone.zone_type"
              class="zone-config-select"
              popper-class="zone-config-select-popper"
              @change="applyTypeDefaults"
            >
              <el-option label="人员低风险区" value="PERSON_LOW" />
              <el-option label="人员中风险区" value="PERSON_MEDIUM" />
              <el-option label="人员高风险区" value="PERSON_HIGH" />
              <el-option label="捕鱼区" value="FISHING" />
            </el-select>
          </el-form-item>
          <section class="ros-panel">
            <div class="ros-heading">
              <strong>区域顶点</strong>
              <b>顶点 {{ selectedZone.polygon_points.length }}</b>
            </div>
            <div class="ros-unit">
              <i></i>
              <span>坐标以视频画面左下角为原点，支持直接微调顶点坐标</span>
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
            <!-- 旧多边形画法入口：矩形画法下隐藏，代码保留以便回退 -->
            <button
              v-if="false"
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
          <div class="side-editor-actions">
            <el-button class="exit-button" @click="drawDialogVisible = false">完成</el-button>
            <el-button class="save-button" :loading="saving" @click="saveZones({ includeDraft: true, closeOnSuccess: true })">
              <el-icon><Check /></el-icon>保存配置
            </el-button>
          </div>
        </aside>
      </section>
      <template #footer>
        <span></span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check, EditPen, Loading, Plus, Refresh,
} from '@element-plus/icons-vue'
import {
  createStreamTicket, getCameraList, getCameraZones, saveCameraZones,
} from '@/api/camera'
import {
  normalizeZones, zoneTypeLabel,
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
// 矩形画框临时状态：已放置的左上角点、鼠标实时预览点（归一化 0-1 坐标）
const rectFirstPoint = ref(null)
const rectPreview = ref(null)
const saving = ref(false)
const drawDialogVisible = ref(false)
const editorMode = ref('')
const draftZone = ref(null)
const zonePage = ref(1)
const zoneEnableLoading = ref({})
const pageSize = 10

const overlayWidth = computed(() => Number(stageImageRef.value?.naturalWidth) || 1920)
const overlayHeight = computed(() => Number(stageImageRef.value?.naturalHeight) || 1080)
const selectedZone = computed(() => draftZone.value || zones.value.find((zone) => zone.id === selectedZoneId.value) || null)
const editorZones = computed(() => (selectedZone.value ? [selectedZone.value] : []))
const currentCameraName = computed(() => cameras.value.find((camera) => camera.id === currentCameraId.value)?.name || '未选择摄像头')
const zoneLabelFontSize = computed(() => Math.max(16, Math.min(64, overlayWidth.value * 0.022)))
const vertexAnchorRadius = computed(() => Math.max(6, Math.min(28, overlayWidth.value * 0.007)))
const vertexIndexFontSize = computed(() => Math.max(13, Math.min(42, overlayWidth.value * 0.016)))
const drawDialogTitle = computed(() => (editorMode.value === 'create' ? '新增区域' : '区域画框'))
const drawTipText = computed(() => {
  if (rectFirstPoint.value) return '已放置左上角，请点击画面确定右下角'
  if (selectedZone.value?.polygon_points?.length) return '区域已生成：可拖拽顶点微调，或修改右侧坐标'
  return '点击画面放置矩形左上角，再点击右下角完成矩形'
})
const rectPreviewRect = computed(() => {
  if (!rectFirstPoint.value || !rectPreview.value) return null
  const x = Math.min(rectFirstPoint.value.x, rectPreview.value.x) * overlayWidth.value
  const y = Math.min(rectFirstPoint.value.y, rectPreview.value.y) * overlayHeight.value
  const width = Math.abs(rectFirstPoint.value.x - rectPreview.value.x) * overlayWidth.value
  const height = Math.abs(rectFirstPoint.value.y - rectPreview.value.y) * overlayHeight.value
  return { x, y, width, height }
})
const pagedZones = computed(() => {
  const start = (zonePage.value - 1) * pageSize
  return zones.value.slice(start, start + pageSize)
})

watch(zones, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (zonePage.value > maxPage) zonePage.value = maxPage
})

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

function zoneTypeText(type) {
  return ({
    PERSON_LOW: '人员低风险区',
    PERSON_MEDIUM: '人员中风险区',
    PERSON_HIGH: '人员高风险区',
    FISHING: '捕鱼区',
  })[type] || zoneTypeLabel(type)
}

function zoneCameraName(zone) {
  return zone?.camera_name || zone?.cameraName || currentCameraName.value
}

async function loadCameras() {
  const response = await getCameraList()
  cameras.value = (response.data?.cameras || []).map((camera) => ({ ...camera, id: String(camera.id) }))
  currentCameraId.value = String(route.query.camera_id || cameras.value[0]?.id || '')
}

async function activateCamera() {
  zones.value = []
  selectedZoneId.value = ''
  zonePage.value = 1
  drawing.value = false
  editorMode.value = ''
  draftZone.value = null
  drawDialogVisible.value = false
  rectFirstPoint.value = null
  rectPreview.value = null
  streamUrl.value = ''
  await loadZones()
}

async function loadZones() {
  if (!currentCameraId.value) return
  const response = await getCameraZones(currentCameraId.value)
  zones.value = normalizeZones(response.data)
  selectedZoneId.value = zones.value[0]?.id || ''
}

async function refreshZones() {
  if (!currentCameraId.value) {
    await loadCameras()
  }
  await loadZones()
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
  if (!drawing.value || !selectedZone.value) return
  // 已有顶点的区域进入编辑微调，点击画面不再追加点，避免覆盖已有区域
  if (selectedZone.value.polygon_points.length) return
  const point = pointerToUnitPoint(event)
  // 第一点：记录左上角，等待右下角
  if (!rectFirstPoint.value) {
    rectFirstPoint.value = point
    return
  }
  // 第二点：由两个角点生成矩形 4 顶点，完成画框
  selectedZone.value.polygon_points = rectPointsFromCorners(rectFirstPoint.value, point)
  rectFirstPoint.value = null
  rectPreview.value = null
  drawing.value = false
}

// 由两个角点（任意顺序）生成顺时针 4 点多边形，供 polygon_points 存储
function rectPointsFromCorners(first, second) {
  const minX = Math.min(first.x, second.x)
  const maxX = Math.max(first.x, second.x)
  const minY = Math.min(first.y, second.y)
  const maxY = Math.max(first.y, second.y)
  return [
    { x: minX, y: minY },
    { x: maxX, y: minY },
    { x: maxX, y: maxY },
    { x: minX, y: maxY },
  ]
}

// 画布鼠标移动：拖拽顶点时走原逻辑，矩形预览时跟随鼠标
function handleStageMouseMove(event) {
  if (dragging.value) {
    dragVertex(event)
    return
  }
  if (rectFirstPoint.value) {
    rectPreview.value = pointerToUnitPoint(event)
  }
}

function handleStageMouseLeave() {
  endDrag()
  rectPreview.value = null
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
    zone_name: `人员低风险区 ${zones.value.length + 1}`,
    name: `人员低风险区 ${zones.value.length + 1}`,
    zone_type: zoneType,
    type: zoneType,
    polygon_points: [],
    enabled: true,
  }
  return zone
}

function startNewZone() {
  draftZone.value = createZone()
  selectedZoneId.value = draftZone.value.id
  editorMode.value = 'create'
  drawDialogVisible.value = true
  rectFirstPoint.value = null
  rectPreview.value = null
  if (!streamUrl.value) refreshStream()
  drawing.value = true
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
  const source = zones.value.find((zone) => zone.id === zoneId)
  if (!source) return
  draftZone.value = cloneZone(source)
  selectedZoneId.value = draftZone.value.id
  editorMode.value = 'edit'
  drawing.value = true
  drawDialogVisible.value = true
  rectFirstPoint.value = null
  rectPreview.value = null
  if (!streamUrl.value) refreshStream()
}

function handleDrawDialogClosed() {
  drawing.value = false
  dragging.value = null
  editorMode.value = ''
  draftZone.value = null
  rectFirstPoint.value = null
  rectPreview.value = null
}

function showZoneAnchors(zone) {
  return zone.id === selectedZoneId.value || (drawing.value && zone.polygon_points.length > 0)
}

function startDrag(zoneId, index) {
  if (draftZone.value?.id !== zoneId) return
  selectedZoneId.value = zoneId
  dragging.value = { zoneId, index }
}

function dragVertex(event) {
  if (!dragging.value) return
  const point = pointerToUnitPoint(event)
  const zone = draftZone.value?.id === dragging.value.zoneId
    ? draftZone.value
    : zones.value.find((item) => item.id === dragging.value.zoneId)
  if (!zone) return
  zone.polygon_points[dragging.value.index] = point
}

function endDrag() {
  dragging.value = null
}

async function deleteZone(zoneId) {
  const target = zones.value.find((zone) => zone.id === zoneId)
  if (!target) return
  try {
    await ElMessageBox.confirm(`确认删除“${target.zone_name || zoneTypeText(target.zone_type)}”？`, '删除区域', { type: 'warning' })
  } catch {
    return
  }
  const previousZones = cloneZones(zones.value)
  zones.value = zones.value.filter((zone) => zone.id !== zoneId)
  selectedZoneId.value = zones.value[0]?.id || ''
  if (!selectedZoneId.value) drawing.value = false
  try {
    await saveZones({ includeDraft: false, closeOnSuccess: false })
  } catch {
    zones.value = previousZones
  }
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
  if (!selectedZone.value.zone_name) selectedZone.value.zone_name = zoneTypeText(zoneType)
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

async function saveZones(options = {}) {
  return persistZones(options)
}

async function persistZones(options = {}) {
  const { includeDraft = true, closeOnSuccess = false } = options
  if (!currentCameraId.value) return false
  const zonesToSave = buildZonesForSave(includeDraft)
  const invalidZone = zonesToSave.find((zone) => zone.polygon_points.length < 3 || zone.polygon_points.length > 15)
  if (invalidZone) {
    selectedZoneId.value = invalidZone.id
    ElMessage.warning('区域尚未完成画框：请点击两个点确定矩形，区域至少需要 3 个顶点')
    return false
  }
  saving.value = true
  try {
    const payload = zonesToSave.map((zone) => ({
      id: zone.id,
      zone_name: zone.zone_name,
      zone_type: zone.zone_type,
      polygon_points: zone.polygon_points,
      enabled: zone.enabled,
    }))
    const response = await saveCameraZones(currentCameraId.value, payload)
    zones.value = normalizeZones(response.data)
    selectedZoneId.value = zones.value.find((zone) => zone.id === selectedZoneId.value)?.id || zones.value[0]?.id || ''
    if (includeDraft && draftZone.value) {
      draftZone.value = null
      editorMode.value = ''
      drawing.value = false
    }
    if (closeOnSuccess) drawDialogVisible.value = false
    ElMessage.success(response.data.message || '区域配置已保存')
    return true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '区域配置保存失败')
    throw error
  } finally {
    saving.value = false
  }
}

function buildZonesForSave(includeDraft) {
  if (!includeDraft || !draftZone.value) return cloneZones(zones.value)
  const draft = normalizeDraftZone(draftZone.value)
  if (editorMode.value === 'edit') {
    const replaced = zones.value.map((zone) => (zone.id === draft.id ? draft : zone))
    return replaced.some((zone) => zone.id === draft.id) ? replaced : [...replaced, draft]
  }
  return [...zones.value, draft]
}

function normalizeDraftZone(zone) {
  return {
    ...zone,
    name: zone.zone_name,
    type: zone.zone_type,
    enabled: zone.enabled !== false,
    polygon_points: clonePoints(zone.polygon_points),
  }
}

function clonePoints(points = []) {
  return points.map((point) => ({ x: Number(point.x), y: Number(point.y) }))
}

function cloneZone(zone) {
  return {
    ...zone,
    polygon_points: clonePoints(zone.polygon_points),
  }
}

function cloneZones(items) {
  return items.map(cloneZone)
}

async function toggleZoneEnabled(zone, enabled) {
  const previous = zone.enabled !== false
  zoneEnableLoading.value = { ...zoneEnableLoading.value, [zone.id]: true }
  zone.enabled = enabled
  try {
    await saveZones({ includeDraft: false, closeOnSuccess: false })
  } catch {
    zone.enabled = previous
  } finally {
    zoneEnableLoading.value = { ...zoneEnableLoading.value, [zone.id]: false }
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
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 74px;
  margin-bottom: 16px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, 0.22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, 0.82) 0%, rgba(9, 29, 48, 0.72) 58%, rgba(7, 20, 34, 0.46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, 0.08);
}

.title-block {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.config-header h1 {
  margin: 0;
  color: #f3f8fd;
  font-size: 25px;
  line-height: 1.1;
  letter-spacing: 0;
}

.config-header p {
  margin: 0;
  color: #8aa9c3;
  font-size: 13px;
  line-height: 1.35;
}

.config-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}
.header-actions { display: flex; align-items: center; gap: 8px; }
.camera-select { width: 260px; }
.zone-config-select :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 6px;
  background: rgba(6, 25, 42, 0.82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, 0.46) !important;
}
.zone-config-select :deep(.el-select__wrapper:hover),
.zone-config-select :deep(.el-select__wrapper.is-focused),
.zone-config-select :deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px rgba(87, 190, 255, 0.82), 0 0 0 2px rgba(72, 216, 255, 0.08) !important;
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
  background: linear-gradient(110deg, rgba(62, 187, 219, 0.88), rgba(67, 205, 169, 0.88));
  box-shadow: none;
}
.config-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 14px;
  align-items: stretch;
}
.video-editor,
.zone-side-editor,
.zone-list-section {
  border: 1px solid rgba(104, 161, 200, 0.18);
  border-radius: 8px;
  background: #0b1d30;
}
.video-editor {
  min-width: 0;
  overflow: hidden;
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
.zone-rect-preview {
  fill: rgba(72, 216, 255, 0.08);
  stroke-width: 3px;
  stroke-dasharray: 9 6;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 4px currentColor);
  pointer-events: none;
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
  min-height: 40px;
  color: #d9e8f8;
  border-color: rgba(104, 161, 200, 0.28);
  background: rgba(6, 25, 42, 0.82);
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
  margin-top: 16px;
  min-width: 0;
  padding: 0;
  overflow: hidden;
}
.zone-toolbar-card {
  min-height: 82px;
  display: flex;
  align-items: center;
  padding: 18px 20px;
  border: 1px solid rgba(104, 161, 200, 0.18);
  border-radius: 8px;
  background: #0b1d30;
}
.list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
  min-height: 44px;
  margin: 0;
  padding: 0;
  border-bottom: 0;
}
.list-heading > div:first-child {
  display: flex;
  align-items: baseline;
  gap: 10px;
  color: #d9e8f8;
  font-size: 16px;
  font-weight: 800;
}
.new-zone-action { min-width: 116px; }
.zone-table {
  width: 100%;
  overflow-x: auto;
  background: #081b2d;
}
.zone-table-head,
.zone-table-row {
  min-width: 1120px;
  display: grid;
  grid-template-columns: minmax(190px, 1fr) 170px minmax(180px, 1fr) 120px minmax(190px, 1fr) 160px;
  align-items: center;
  gap: 16px;
  text-align: center;
}
.zone-table-head {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  background: #15314d;
  font-size: 14px;
  font-weight: 800;
}
.zone-table-row {
  min-height: 72px;
  margin-top: 0;
  padding: 12px 20px;
  color: #d8e7ff;
  border-top: 1px solid rgba(104, 161, 200, 0.1);
  background: #092034;
  transition: background 0.16s ease;
}
.zone-table-row:hover {
  background: #102940;
}
.zone-table-row.disabled { opacity: 0.56; }
.zone-table-row strong {
  min-width: 0;
  display: block;
  gap: 9px;
  overflow: hidden;
  color: #f3f8fd;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone-table-row > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone-table-row :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, 0.34);
  background: rgba(96, 118, 134, 0.38);
}
.zone-table-row :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, 0.66);
  background: #409eff;
}
.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.row-edit,
.row-delete {
  min-width: auto;
  height: 32px;
  padding: 0 12px;
  border: 1px solid;
  border-radius: 5px;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.row-edit {
  border-color: rgba(66, 164, 224, 0.5);
  color: #d5f0ff;
  background: rgba(29, 91, 133, 0.7);
}
.row-delete {
  border-color: rgba(226, 88, 109, 0.46);
  color: #ffb1bd;
  background: rgba(128, 36, 54, 0.48);
}
.row-edit:hover {
  color: #c7f0ff;
}
.row-delete:hover {
  color: #ffd5d9;
}
.zone-table-empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: #789bb4;
  font-size: 13px;
}
.list-pagination {
  min-height: 46px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, 0.1);
  background: #092034;
}
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
.list-pagination :deep(.el-pager li.is-active) {
  border-color: #4ba7e6;
  color: #fff;
  background: #3f95d7;
}
.list-pagination :deep(.btn-prev:disabled),
.list-pagination :deep(.btn-next:disabled) {
  color: rgba(143, 182, 209, 0.35);
  background: #0b2238;
}
.zone-side-editor {
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 14px;
}
.side-editor-title {
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(80, 165, 200, 0.14);
}
.side-editor-title strong {
  color: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
}
.side-editor-title span {
  min-width: 68px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.42);
  border-radius: 999px;
  background: rgba(4, 45, 55, 0.68);
  font-size: 12px;
  font-weight: 900;
}
.zone-form {
  min-height: 0;
  flex: 1 1 auto;
  overflow: auto;
  padding-right: 2px;
}
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
.point-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.point-head,
.point-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) minmax(0, 1fr) 64px;
  align-items: center;
  gap: 8px;
}
.point-head {
  color: #9bbbd0;
  font-size: 12px;
  font-weight: 800;
  text-align: center;
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
.coordinate-field :deep(.el-input__inner) { text-align: center; }
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
.exit-button {
  color: #d8e9f7;
  border-color: rgba(104, 161, 200, 0.28);
  font-weight: 900;
  background: rgba(6, 25, 42, 0.82);
}
.panel-empty {
  min-height: 220px;
  display: grid;
  place-items: center;
  color: #668397;
  text-align: center;
}
.side-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid rgba(80, 165, 200, 0.14);
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
:global(.zone-draw-dialog) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  border-radius: 8px;
  background: #061a28;
  box-shadow: 0 26px 70px rgba(0, 7, 18, 0.62);
}
:global(.zone-draw-dialog .el-dialog__header) {
  margin: 0;
  padding: 18px 20px 12px;
  border-bottom: 1px solid rgba(80, 165, 200, 0.14);
}
:global(.zone-draw-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
}
:global(.zone-draw-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #8ddcf0;
}
:global(.zone-draw-dialog .el-dialog__body) {
  padding: 14px;
  color: #d7edf6;
}
:global(.zone-draw-dialog .el-dialog__footer) {
  display: none;
}
@media (max-width: 1000px) {
  .config-header,
  .header-actions { align-items: stretch; flex-direction: column; }
  .camera-select { width: 100%; }
  .config-workspace { grid-template-columns: 1fr; }
  .list-heading,
  .header-actions { align-items: stretch; flex-direction: column; }
  .list-heading { align-items: stretch; }
}
</style>
