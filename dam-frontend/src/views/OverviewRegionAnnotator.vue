<template>
  <main class="region-annotator">
    <header class="annotator-header">
      <div>
        <span>OVERVIEW REGION ANNOTATOR</span>
        <h1>总览页摄像头区域标注</h1>
      </div>
      <div class="active-readout" :class="activeGroup.type">
        <span>当前点位</span>
        <strong>{{ activeGroup.label }} / {{ activeGroup.typeLabel }}</strong>
      </div>
    </header>

    <section class="annotator-body">
      <div class="map-section">
        <div class="map-toolbar">
          <div>
            <strong>{{ activeRegionKey }}</strong>
            <span>{{ savedCurrentRegion ? '已保存区域' : '未保存区域' }}</span>
          </div>
          <div class="zoom-readout">{{ zoomPercent }}</div>
        </div>

        <div ref="mapBoardRef" class="map-board">
          <div class="map-content" :style="mapContentStyle">
            <img class="satellite-image" src="/dammap.png" alt="大藤峡水电站卫星底图" />
            <svg
              class="draw-layer"
              viewBox="0 0 1000 430"
              preserveAspectRatio="none"
              @click="addPoint"
              @dblclick.prevent="finishRegion"
              @mousemove="updateHoverPoint"
              @mouseleave="hoverPoint = null"
            >
              <g
                v-for="region in savedRegions"
                :key="region.key"
                class="saved-region"
                :class="[region.type, { active: region.key === activeRegionKey }]"
              >
                <path :d="region.path" />
              </g>

              <polyline
                v-if="draftPoints.length"
                class="draft-line"
                :class="activeGroup.type"
                :points="pointsToString(draftPoints)"
              />
              <line
                v-if="draftPoints.length && hoverPoint"
                class="hover-line"
                :class="activeGroup.type"
                :x1="lastDraftPoint.x"
                :y1="lastDraftPoint.y"
                :x2="hoverPoint.x"
                :y2="hoverPoint.y"
              />
              <circle
                v-for="(point, index) in draftPoints"
                :key="`${point.x}-${point.y}-${index}`"
                class="draft-point"
                :class="activeGroup.type"
                :cx="point.x"
                :cy="point.y"
                r="4"
              />

              <g
                v-for="point in pendingPoints"
                :key="point.id"
                class="pending-marker"
              >
                <circle class="pending-hit-area" :cx="point.x" :cy="point.y" r="12" />
                <title>待建中</title>
              </g>

              <g
                v-for="point in cameraPoints"
                :key="point.no"
                class="camera-marker"
                :class="[point.type, { active: point.regionKey === activeRegionKey }]"
                @click.stop="selectPoint(point.no)"
              >
                <circle class="marker-hit-area" :cx="point.x" :cy="point.y" r="12" />
                <circle class="marker-ring" :cx="point.x" :cy="point.y" r="8" />
                <title>{{ point.no }}号 / {{ point.typeLabel }}</title>
              </g>
            </svg>
          </div>
        </div>
      </div>

      <aside class="side-panel">
        <section class="panel-block point-block">
          <h2>摄像头点位</h2>
          <div class="point-grid">
            <button
              v-for="group in regionGroups"
              :key="group.key"
              type="button"
              :class="[group.type, { active: group.key === activeRegionKey }]"
              @click="selectRegion(group.key)"
            >
              <strong>{{ group.label }}</strong>
              <span>{{ group.typeLabel }}</span>
            </button>
          </div>
        </section>

        <section class="panel-block status-block">
          <h2>标注状态</h2>
          <div class="status-row">
            <span>已保存点位</span>
            <strong>{{ savedRegions.length }} / {{ regionGroups.length }}</strong>
          </div>
          <div class="status-row">
            <span>当前点数</span>
            <strong>{{ draftPoints.length }}</strong>
          </div>
          <div class="status-row">
            <span>保存位置</span>
            <strong>浏览器本地</strong>
          </div>
        </section>

        <section class="panel-block action-block">
          <h2>绘制操作</h2>
          <div class="action-grid">
            <button type="button" class="primary" @click="finishRegion">完成并保存当前区域</button>
            <button type="button" @click="undoPoint">撤销点</button>
            <button type="button" @click="clearDraft">清空当前点</button>
            <button type="button" @click="clearCurrentRegion">删除当前区域</button>
            <button type="button" @click="copyParams">复制参数</button>
            <button type="button" @click="downloadParams">下载 JSON</button>
          </div>
          <p>{{ message }}</p>
        </section>

        <section class="panel-block export-block">
          <h2>区域参数</h2>
          <textarea readonly :value="exportText"></textarea>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const STORAGE_KEY = 'boxsystem-overview-camera-regions-v2'

const cameraPoints = [
  { no: 1, x: 206, y: 178, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-1' },
  { no: 3, x: 445, y: 286, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 4, x: 499, y: 167, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 5, x: 520, y: 167, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 6, x: 685, y: 215, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 7, x: 704, y: 215, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-7' },
  { no: 8, x: 595, y: 290, type: 'boatForbidden', typeLabel: '禁船区', regionKey: 'boat-34568' },
  { no: 9, x: 931, y: 121, type: 'personForbidden', typeLabel: '人员禁入区', regionKey: 'person-9' },
]

const pendingPoints = [
  { id: 'pending-1', no: 1, x: 206, y: 192 },
  { id: 'pending-2', no: 2, x: 126, y: 120 },
  { id: 'pending-3', no: 3, x: 88, y: 143 },
  { id: 'pending-4', no: 4, x: 73, y: 132 },
  { id: 'pending-5', no: 5, x: 77, y: 107 },
]

const regionGroups = [
  { key: 'boat-1', label: '1号', pointNos: [1], type: 'boatForbidden', typeLabel: '禁船区' },
  { key: 'boat-34568', label: '3/4/5/6/8号', pointNos: [3, 4, 5, 6, 8], type: 'boatForbidden', typeLabel: '禁船区' },
  { key: 'boat-7', label: '7号', pointNos: [7], type: 'boatForbidden', typeLabel: '禁船区' },
  { key: 'person-9', label: '9号', pointNos: [9], type: 'personForbidden', typeLabel: '人员禁入区' },
]

const mapBoardRef = ref(null)
const activeRegionKey = ref('person-9')
const draftPoints = ref([])
const hoverPoint = ref(null)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const message = ref('点击地图添加点，双击地图或点击完成按钮保存当前区域。')
const regions = reactive({})

const activeGroup = computed(() => regionGroups.find((group) => group.key === activeRegionKey.value) || regionGroups[0])
const savedCurrentRegion = computed(() => regions[activeRegionKey.value])
const savedRegions = computed(() => Object.values(regions))
const lastDraftPoint = computed(() => draftPoints.value[draftPoints.value.length - 1] || { x: 0, y: 0 })
const zoomPercent = computed(() => `${Math.round(zoom.value * 100)}%`)
const mapContentStyle = computed(() => ({
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
}))
const exportText = computed(() => JSON.stringify({
  source: 'overview-region-annotator',
  image: '/dammap.png',
  regions,
}, null, 2))

const selectPoint = (pointNo) => {
  const point = cameraPoints.find((item) => item.no === pointNo)
  if (!point) return

  selectRegion(point.regionKey)
}

const selectRegion = (regionKey) => {
  activeRegionKey.value = regionKey
  clearDraft()
  message.value = `已切换到 ${activeGroup.value.label}${activeGroup.value.typeLabel}。`
}

const addPoint = (event) => {
  if (event.detail > 1) return
  draftPoints.value.push(toSvgPoint(event))
  message.value = `${activeGroup.value.label}区域已添加 ${draftPoints.value.length} 个点。`
}

const updateHoverPoint = (event) => {
  hoverPoint.value = toSvgPoint(event)
}

const finishRegion = () => {
  if (draftPoints.value.length < 3) {
    message.value = '至少需要 3 个点才能保存区域。'
    return
  }

  const points = draftPoints.value.map((point) => ({ ...point }))
  regions[activeRegionKey.value] = {
    key: activeRegionKey.value,
    pointNos: activeGroup.value.pointNos,
    type: activeGroup.value.type,
    name: `${activeGroup.value.label}${activeGroup.value.typeLabel}`,
    path: pointsToPath(points),
    points,
  }
  persistRegions()
  clearDraft()
  message.value = `${activeGroup.value.label}区域已保存。`
}

const undoPoint = () => {
  draftPoints.value = draftPoints.value.slice(0, -1)
  message.value = `已撤销 1 个点，当前剩余 ${draftPoints.value.length} 个点。`
}

const clearDraft = () => {
  draftPoints.value = []
  hoverPoint.value = null
}

const clearCurrentRegion = () => {
  delete regions[activeRegionKey.value]
  clearDraft()
  persistRegions()
  message.value = `${activeGroup.value.label}区域已删除。`
}

const copyParams = async () => {
  try {
    await navigator.clipboard.writeText(exportText.value)
    message.value = '区域参数已复制。'
  } catch (error) {
    message.value = '浏览器未允许复制，可以直接选中下方参数。'
  }
}

const downloadParams = () => {
  const blob = new Blob([exportText.value], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'overview-camera-regions.json'
  link.click()
  URL.revokeObjectURL(url)
  message.value = '区域参数已下载。'
}

const toSvgPoint = (event) => {
  const board = mapBoardRef.value
  const rect = board.getBoundingClientRect()
  const pointerX = event.clientX - rect.left
  const pointerY = event.clientY - rect.top
  const contentX = (pointerX - pan.value.x) / zoom.value
  const contentY = (pointerY - pan.value.y) / zoom.value

  return {
    x: Math.max(0, Math.min(1000, Math.round((contentX / rect.width) * 1000))),
    y: Math.max(0, Math.min(430, Math.round((contentY / rect.height) * 430))),
  }
}

const handleWheel = (event) => {
  event.preventDefault()

  const board = mapBoardRef.value
  if (!board) return

  const rect = board.getBoundingClientRect()
  const pointerX = event.clientX - rect.left
  const pointerY = event.clientY - rect.top
  const previousZoom = zoom.value
  const nextZoom = Math.min(4, Math.max(1, Number((previousZoom * (event.deltaY > 0 ? 0.88 : 1.12)).toFixed(3))))

  if (nextZoom === previousZoom) return

  if (nextZoom === 1) {
    zoom.value = 1
    pan.value = { x: 0, y: 0 }
    return
  }

  const contentX = (pointerX - pan.value.x) / previousZoom
  const contentY = (pointerY - pan.value.y) / previousZoom
  zoom.value = nextZoom
  pan.value = {
    x: pointerX - contentX * nextZoom,
    y: pointerY - contentY * nextZoom,
  }
}

const persistRegions = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(regions))
}

const loadRegions = () => {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return

  try {
    const saved = JSON.parse(raw)
    Object.entries(saved).forEach(([key, value]) => {
      regions[key] = value
    })
    message.value = '已加载浏览器本地保存的区域参数。'
  } catch (error) {
    message.value = '本地参数读取失败，请重新标注。'
  }
}

function pointsToString(points) {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

function pointsToPath(points) {
  if (!points.length) return ''
  const [firstPoint, ...restPoints] = points
  return `M${firstPoint.x} ${firstPoint.y} ${restPoints.map((point) => `L${point.x} ${point.y}`).join(' ')} Z`
}

onMounted(() => {
  loadRegions()
  mapBoardRef.value?.addEventListener('wheel', handleWheel, { passive: false })
})

onBeforeUnmount(() => {
  mapBoardRef.value?.removeEventListener('wheel', handleWheel)
})
</script>

<style scoped>
.region-annotator {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  display: grid;
  grid-template-rows: 76px minmax(0, 1fr);
  gap: 16px;
  padding: 18px;
  color: #e2f0fe;
  background:
    radial-gradient(circle at 46% 20%, rgba(0, 218, 255, 0.16), transparent 30%),
    linear-gradient(180deg, #061424 0%, #020915 100%);
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

.annotator-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  border: 1px solid rgba(0, 200, 255, 0.26);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(15, 44, 76, 0.86), rgba(7, 27, 50, 0.72));
  box-shadow: inset 0 0 24px rgba(0, 200, 255, 0.05), 0 10px 30px rgba(0, 0, 0, 0.24);
}

.annotator-header span,
.active-readout span {
  display: block;
  color: rgba(0, 229, 255, 0.68);
  font-size: 12px;
}

.annotator-header h1 {
  margin: 6px 0 0;
  color: #f0f8ff;
  font-size: 27px;
  line-height: 1;
}

.active-readout {
  min-width: 220px;
  height: 48px;
  padding: 0 16px;
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: rgba(3, 18, 33, 0.76);
}

.active-readout strong {
  margin-top: 3px;
  font-size: 18px;
}

.active-readout.personForbidden strong {
  color: #ff7180;
}

.active-readout.boatForbidden strong {
  color: #ffd15f;
}

.annotator-body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 370px;
  gap: 16px;
}

.map-section,
.side-panel {
  min-height: 0;
}

.map-section {
  display: grid;
  grid-template-rows: 48px minmax(0, 1fr);
  gap: 10px;
}

.map-toolbar,
.panel-block {
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 8px;
  background: rgba(7, 27, 50, 0.76);
  box-shadow: inset 0 0 24px rgba(0, 200, 255, 0.04);
}

.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
}

.map-toolbar strong {
  color: #fff;
  font-size: 16px;
}

.map-toolbar span {
  margin-left: 12px;
  color: rgba(174, 202, 245, 0.76);
  font-size: 13px;
}

.zoom-readout {
  width: 70px;
  height: 30px;
  border: 1px solid rgba(0, 200, 255, 0.22);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #57f3ff;
  background: rgba(2, 11, 22, 0.58);
  font-weight: 800;
}

.map-board {
  position: relative;
  width: 100%;
  aspect-ratio: 1916 / 824;
  align-self: center;
  min-height: 0;
  border: 1px solid rgba(0, 229, 255, 0.42);
  border-radius: 8px;
  overflow: hidden;
  background: #061424;
  box-shadow:
    0 18px 42px rgba(0, 0, 0, 0.42),
    0 0 38px rgba(0, 200, 255, 0.18),
    inset 0 0 30px rgba(0, 200, 255, 0.1);
  touch-action: none;
}

.map-content {
  position: absolute;
  inset: 0;
  transform-origin: 0 0;
  transition: transform 0.08s ease-out;
  will-change: transform;
}

.satellite-image,
.draw-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.satellite-image {
  object-fit: cover;
  filter: saturate(1.08) contrast(1.08) brightness(0.76);
}

.draw-layer {
  cursor: crosshair;
  background:
    radial-gradient(circle at 50% 45%, transparent 42%, rgba(2, 9, 21, 0.42) 100%),
    linear-gradient(180deg, rgba(0, 20, 38, 0.16), rgba(0, 9, 22, 0.08));
}

.saved-region path {
  stroke-width: 1.6;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}

.saved-region.personForbidden path {
  fill: rgba(245, 68, 92, 0.08);
  stroke: rgba(255, 91, 111, 0.72);
}

.saved-region.boatForbidden path {
  fill: rgba(247, 183, 49, 0.08);
  stroke: rgba(247, 183, 49, 0.74);
}

.saved-region.active path {
  stroke-width: 2.4;
  filter: drop-shadow(0 0 7px currentColor);
}

.draft-line,
.hover-line {
  fill: none;
  vector-effect: non-scaling-stroke;
}

.draft-line {
  stroke-width: 2.4;
  stroke-dasharray: 8 6;
}

.hover-line {
  stroke-width: 1.7;
  stroke-dasharray: 5 5;
  opacity: 0.78;
}

.draft-line.personForbidden,
.hover-line.personForbidden {
  stroke: #ff7180;
}

.draft-line.boatForbidden,
.hover-line.boatForbidden {
  stroke: #ffd15f;
}

.draft-point {
  stroke: #fff;
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}

.draft-point.personForbidden {
  fill: #ff7180;
}

.draft-point.boatForbidden {
  fill: #ffd15f;
}

.camera-marker {
  cursor: pointer;
}

.camera-marker .marker-hit-area {
  fill: rgba(255, 255, 255, 0.01);
  stroke: transparent;
  stroke-width: 0;
}

.camera-marker .marker-ring {
  fill: transparent;
  stroke: rgba(255, 255, 255, 0.16);
  stroke-width: 1.1;
  vector-effect: non-scaling-stroke;
  opacity: 0;
  transition: opacity 0.16s ease, stroke 0.16s ease, filter 0.16s ease;
}

.camera-marker:hover .marker-ring {
  opacity: 1;
}

.camera-marker.active .marker-ring {
  opacity: 1;
  stroke: #57f3ff;
  stroke-width: 1.7;
  filter: drop-shadow(0 0 5px rgba(0, 229, 255, 0.62));
}

.camera-marker text,
.pending-marker text {
  pointer-events: none;
  fill: #fff;
  font-size: 14px;
  font-weight: 900;
  text-anchor: middle;
}

.pending-marker {
  cursor: help;
}

.pending-marker .pending-hit-area {
  fill: rgba(255, 255, 255, 0.01);
  stroke: rgba(80, 160, 255, 0.12);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.pending-marker:hover .pending-hit-area {
  stroke: rgba(80, 160, 255, 0.72);
  filter: drop-shadow(0 0 5px rgba(80, 160, 255, 0.55));
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-block {
  padding: 14px;
}

.panel-block h2 {
  margin: 0 0 12px;
  color: #f0f8ff;
  font-size: 16px;
}

.point-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.point-grid button,
.action-grid button {
  height: 42px;
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 6px;
  background: rgba(5, 21, 40, 0.78);
  color: #d9ecff;
  cursor: pointer;
}

.point-grid button {
  display: grid;
  gap: 2px;
  align-content: center;
}

.point-grid button strong {
  font-size: 16px;
}

.point-grid button span {
  font-size: 12px;
  color: rgba(174, 202, 245, 0.76);
}

.point-grid button.active {
  border-color: currentColor;
  box-shadow: 0 0 16px rgba(0, 200, 255, 0.16);
}

.point-grid button.personForbidden.active {
  color: #ff7180;
}

.point-grid button.boatForbidden.active {
  color: #ffd15f;
}

.status-block {
  display: grid;
  gap: 10px;
}

.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgba(174, 202, 245, 0.82);
  font-size: 14px;
}

.status-row strong {
  color: #fff;
}

.action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.action-grid .primary {
  grid-column: 1 / -1;
  color: #57f3ff;
  border-color: rgba(87, 243, 255, 0.45);
}

.action-block p {
  min-height: 18px;
  margin: 10px 0 0;
  color: rgba(174, 202, 245, 0.84);
  font-size: 13px;
}

.export-block {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.export-block textarea {
  flex: 1;
  min-height: 180px;
  resize: none;
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 6px;
  background: rgba(2, 11, 22, 0.78);
  color: #bfe7ff;
  padding: 10px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  line-height: 1.55;
  outline: none;
}

@media (max-width: 1180px) {
  .region-annotator {
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .annotator-body {
    grid-template-columns: 1fr;
  }

  .map-section {
    min-height: 560px;
  }

  .side-panel {
    min-height: 620px;
  }
}
</style>
