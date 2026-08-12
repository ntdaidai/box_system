<template>
  <main class="region-annotator">
    <aside class="tool-panel">
      <header>
        <span>总览地图区域标注</span>
        <h1>2号摄像头范围框选</h1>
      </header>

      <section class="target-list">
        <button
          v-for="target in targets"
          :key="target.key"
          type="button"
          :class="{ active: activeKey === target.key }"
          @click="selectTarget(target.key)"
        >
          <strong>{{ target.name }}</strong>
          <span>{{ target.pointNos.join(' / ') }} 号点位</span>
        </button>
      </section>

      <section class="tool-actions">
        <button type="button" :class="{ active: drawMode === 'draw' }" @click="drawMode = 'draw'">绘制</button>
        <button type="button" :class="{ active: drawMode === 'pan' }" @click="drawMode = 'pan'">拖动</button>
        <button type="button" @click="undoPoint">撤销点</button>
        <button type="button" @click="clearActive">清空当前</button>
      </section>

      <section class="hint-panel">
        <p>滚轮缩放地图；绘制模式下左键点击添加边界点。</p>
        <p>拖动模式下按住左键移动地图；绘制模式按住 Shift 也可以拖动。</p>
        <p>当前页面只标注 2 号摄像头范围，导出 JSON 只包含 camera-2。</p>
      </section>

      <section class="export-panel">
        <div class="export-head">
          <strong>导出参数</strong>
          <button type="button" @click="copyOutput">{{ copyButtonText }}</button>
        </div>
        <textarea ref="outputRef" readonly :value="outputJson"></textarea>
      </section>
    </aside>

    <section class="map-workspace">
      <div class="workspace-toolbar">
        <div>
          <strong>{{ activeTarget.name }}</strong>
          <span>{{ activePoints.length }} 个点</span>
        </div>
        <div class="zoom-actions">
          <button type="button" @click="zoomBy(1.18)">+</button>
          <button type="button" @click="zoomBy(0.84)">−</button>
          <button type="button" @click="fitMap">适配</button>
        </div>
      </div>

      <div
        ref="boardRef"
        class="map-board"
        :class="{ drawing: drawMode === 'draw', panning: drawMode === 'pan' }"
        @wheel.prevent="handleWheel"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointercancel="handlePointerUp"
        @contextmenu.prevent
      >
        <div class="map-layer" :style="mapLayerStyle">
          <img src="/dam.png" alt="大藤峡地图" draggable="false" />
          <svg class="region-layer" :viewBox="`0 0 ${imageSize.width} ${imageSize.height}`">
            <path
              v-for="target in targetsWithPath"
              :key="target.key"
              :d="target.path"
              :class="['region-path', target.type, { active: target.key === activeKey }]"
            />
            <polyline
              v-if="activePoints.length > 1"
              class="draft-line"
              :points="pointString(activePoints)"
            />
            <circle
              v-for="(point, index) in activePoints"
              :key="`${activeKey}-${index}`"
              class="vertex"
              :cx="point.x"
              :cy="point.y"
              r="3.2"
            />
          </svg>

          <button
            v-for="point in drawableCameraPoints"
            :key="point.no"
            type="button"
            class="camera-hotspot"
            :class="{ active: activeTarget.pointNos.includes(point.no) }"
            :style="{ left: `${point.x}%`, top: `${point.y}%` }"
            @pointerdown.stop
            @click.stop="selectByPoint(point.no)"
          >
            {{ point.no }}
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const imageSize = { width: 2168, height: 725 }
const storageKey = 'overview-camera-2-region-annotator-v1'

const targets = [
  { key: 'camera-2', pointNos: [2], type: 'toConfirm', name: '2号摄像头范围' },
]

const cameraPoints = [
  { no: 2, x: 7.3988, y: 15.2249 },
]

const boardRef = ref(null)
const outputRef = ref(null)
const activeKey = ref(targets[0].key)
const drawMode = ref('draw')
const copied = ref(false)
const copySelected = ref(false)
const view = reactive({ scale: 1, x: 0, y: 0 })
const dragState = reactive({ active: false, x: 0, y: 0, startX: 0, startY: 0 })
const regions = reactive(Object.fromEntries(targets.map((target) => [target.key, []])))

const activeTarget = computed(() => targets.find((target) => target.key === activeKey.value) || targets[0])
const activePoints = computed(() => regions[activeKey.value] || [])
const drawableCameraPoints = computed(() => cameraPoints)
const mapLayerStyle = computed(() => ({
  width: `${imageSize.width}px`,
  height: `${imageSize.height}px`,
  transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
}))

const targetsWithPath = computed(() => targets
  .map((target) => ({ ...target, path: pathFromPoints(regions[target.key]) }))
  .filter((target) => target.path))

const outputJson = computed(() => JSON.stringify({
  source: 'overview-camera-2-region-annotator',
  image: '/dam.png',
  annotateImage: '/dam.png',
  imageSize,
  regions: Object.fromEntries(targets.map((target) => [
    target.key,
    {
      key: target.key,
      pointNos: target.pointNos,
      type: target.type,
      name: target.name,
      path: pathFromPoints(regions[target.key]),
      points: regions[target.key].map((point) => ({
        x: Math.round(point.x),
        y: Math.round(point.y),
      })),
    },
  ])),
}, null, 2))

const copyButtonText = computed(() => {
  if (copied.value) return '已复制'
  if (copySelected.value) return '已选中，请按 Ctrl+C'
  return '复制 JSON'
})

function selectTarget(key) {
  activeKey.value = key
}

function selectByPoint(no) {
  const target = targets.find((item) => item.pointNos.includes(no))
  if (target) activeKey.value = target.key
}

function pointString(points) {
  return points.map((point) => `${point.x},${point.y}`).join(' ')
}

function pathFromPoints(points) {
  if (!points || points.length < 3) return ''
  return `${points.map((point, index) => `${index ? 'L' : 'M'}${Math.round(point.x)} ${Math.round(point.y)}`).join(' ')} Z`
}

function clientToImage(event) {
  const rect = boardRef.value.getBoundingClientRect()
  const x = (event.clientX - rect.left - view.x) / view.scale
  const y = (event.clientY - rect.top - view.y) / view.scale
  return {
    x: Math.max(0, Math.min(imageSize.width, x)),
    y: Math.max(0, Math.min(imageSize.height, y)),
  }
}

function addPoint(event) {
  const point = clientToImage(event)
  regions[activeKey.value].push({
    x: Math.round(point.x),
    y: Math.round(point.y),
  })
  saveLocal()
}

function undoPoint() {
  regions[activeKey.value].pop()
  saveLocal()
}

function clearActive() {
  regions[activeKey.value].splice(0)
  saveLocal()
}

function handlePointerDown(event) {
  if (event.button !== 0) return
  if (drawMode.value === 'draw' && !event.shiftKey) {
    addPoint(event)
    return
  }
  dragState.active = true
  dragState.x = event.clientX
  dragState.y = event.clientY
  dragState.startX = view.x
  dragState.startY = view.y
  boardRef.value?.setPointerCapture(event.pointerId)
}

function handlePointerMove(event) {
  if (!dragState.active) return
  view.x = dragState.startX + event.clientX - dragState.x
  view.y = dragState.startY + event.clientY - dragState.y
}

function handlePointerUp(event) {
  if (!dragState.active) return
  dragState.active = false
  try {
    boardRef.value?.releasePointerCapture?.(event.pointerId)
  } catch {
    // Pointer capture may already be released by the browser.
  }
}

function handleWheel(event) {
  const factor = event.deltaY < 0 ? 1.12 : 0.89
  zoomBy(factor, event.clientX, event.clientY)
}

function zoomBy(factor, clientX, clientY) {
  const rect = boardRef.value?.getBoundingClientRect()
  if (!rect) return
  const originX = clientX ?? rect.left + rect.width / 2
  const originY = clientY ?? rect.top + rect.height / 2
  const beforeX = (originX - rect.left - view.x) / view.scale
  const beforeY = (originY - rect.top - view.y) / view.scale
  const nextScale = Math.max(.45, Math.min(8, view.scale * factor))
  view.x = originX - rect.left - beforeX * nextScale
  view.y = originY - rect.top - beforeY * nextScale
  view.scale = nextScale
}

function fitMap() {
  const rect = boardRef.value?.getBoundingClientRect()
  if (!rect) return
  const scale = Math.min(rect.width / imageSize.width, rect.height / imageSize.height) * .96
  view.scale = scale
  view.x = (rect.width - imageSize.width * scale) / 2
  view.y = (rect.height - imageSize.height * scale) / 2
}

async function copyOutput() {
  copied.value = false
  copySelected.value = false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(outputJson.value)
      copied.value = true
      window.setTimeout(() => {
        copied.value = false
      }, 1400)
      return
    }
  } catch {
    // Fall through to the textarea selection fallback.
  }
  const textarea = outputRef.value
  if (!textarea) return
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)
  try {
    if (document.execCommand('copy')) {
      copied.value = true
    } else {
      copySelected.value = true
    }
  } catch {
    copySelected.value = true
  }
  window.setTimeout(() => {
    copied.value = false
    copySelected.value = false
  }, 1800)
}

function saveLocal() {
  localStorage.setItem(storageKey, JSON.stringify(regions))
}

function loadLocal() {
  const raw = localStorage.getItem(storageKey)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    targets.forEach((target) => {
      if (Array.isArray(parsed[target.key])) regions[target.key].splice(0, regions[target.key].length, ...parsed[target.key])
    })
  } catch {
    localStorage.removeItem(storageKey)
  }
}

function handleResize() {
  fitMap()
}

onMounted(() => {
  loadLocal()
  nextTick(fitMap)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.region-annotator {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 12px;
  width: 100%;
  height: 100%;
  padding: 12px;
  overflow: hidden;
  background: #061421;
  color: #dcecf8;
  box-sizing: border-box;
}

.tool-panel,
.map-workspace {
  min-height: 0;
  border: 1px solid rgba(58, 134, 188, .28);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(8, 32, 54, .92), rgba(4, 18, 34, .96));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
  overflow: hidden;
}

.tool-panel {
  display: grid;
  grid-template-rows: auto auto auto auto minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
}

.tool-panel header span,
.workspace-toolbar span {
  color: #8fbde0;
  font-size: 12px;
}

.tool-panel h1 {
  margin: 6px 0 0;
  color: #fff;
  font-size: 24px;
  line-height: 1.15;
}

.target-list,
.tool-actions {
  display: grid;
  gap: 8px;
}

.target-list button,
.tool-actions button,
.export-head button,
.zoom-actions button {
  border: 1px solid rgba(74, 160, 220, .28);
  border-radius: 7px;
  color: #bfe6ff;
  background: rgba(6, 28, 50, .72);
  cursor: pointer;
  transition: border-color .18s ease, background .18s ease, color .18s ease;
}

.target-list button {
  display: grid;
  gap: 5px;
  padding: 12px;
  text-align: left;
}

.target-list button strong {
  color: #eef8ff;
  font-size: 15px;
}

.target-list button span {
  color: #7faed0;
  font-size: 12px;
}

.target-list button.active,
.tool-actions button.active {
  border-color: rgba(67, 200, 255, .68);
  background: rgba(34, 113, 176, .34);
  color: #fff;
}

.tool-actions {
  grid-template-columns: repeat(2, 1fr);
}

.tool-actions button,
.export-head button,
.zoom-actions button {
  height: 34px;
}

.hint-panel {
  display: grid;
  gap: 7px;
  padding: 12px;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 7px;
  background: rgba(3, 17, 31, .48);
}

.hint-panel p {
  margin: 0;
  color: #9fc3dd;
  font-size: 12px;
  line-height: 1.45;
}

.export-panel {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 10px;
}

.export-head,
.workspace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.export-head strong,
.workspace-toolbar strong {
  color: #fff;
  font-size: 16px;
}

.export-head button {
  padding: 0 12px;
}

textarea {
  width: 100%;
  height: 100%;
  min-height: 0;
  resize: none;
  border: 1px solid rgba(67, 200, 255, .16);
  border-radius: 7px;
  color: #cae8fa;
  background: rgba(1, 10, 20, .72);
  padding: 10px;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
  box-sizing: border-box;
}

.map-workspace {
  display: grid;
  grid-template-rows: 54px minmax(0, 1fr);
}

.workspace-toolbar {
  padding: 0 14px;
  border-bottom: 1px solid rgba(58, 134, 188, .22);
}

.workspace-toolbar > div:first-child {
  display: grid;
  gap: 3px;
}

.zoom-actions {
  display: flex;
  gap: 8px;
}

.zoom-actions button {
  min-width: 38px;
  padding: 0 12px;
}

.map-board {
  position: relative;
  min-height: 0;
  overflow: hidden;
  background:
    linear-gradient(rgba(67, 200, 255, .05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67, 200, 255, .04) 1px, transparent 1px),
    #04111f;
  background-size: 36px 36px;
  touch-action: none;
}

.map-board.drawing {
  cursor: crosshair;
}

.map-board.panning {
  cursor: grab;
}

.map-layer {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  user-select: none;
}

.map-layer img,
.region-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.map-layer img {
  display: block;
  opacity: .94;
}

.region-layer {
  pointer-events: none;
}

.region-path {
  fill: rgba(67, 200, 255, .08);
  stroke: rgba(67, 200, 255, .7);
  stroke-width: 1.4;
}

.region-path.boatForbidden {
  fill: rgba(255, 182, 72, .08);
  stroke: rgba(255, 182, 72, .78);
}

.region-path.personForbidden {
  fill: rgba(255, 91, 104, .08);
  stroke: rgba(255, 91, 104, .78);
}

.region-path.active {
  stroke-width: 2.2;
}

.draft-line {
  fill: none;
  stroke: rgba(255, 255, 255, .82);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.vertex {
  fill: #ffffff;
  stroke: #061421;
  stroke-width: 1.4;
}

.camera-hotspot {
  position: absolute;
  width: 21px;
  height: 21px;
  display: grid;
  place-items: center;
  transform: translate(-50%, -50%);
  border: 1px solid rgba(255, 255, 255, .86);
  border-radius: 50%;
  color: #fff;
  background: rgba(216, 52, 62, .86);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 0 0 3px rgba(216, 52, 62, .2);
}

.camera-hotspot.active {
  border-color: #7ff1ff;
  box-shadow: 0 0 0 4px rgba(67, 200, 255, .22);
}
</style>
