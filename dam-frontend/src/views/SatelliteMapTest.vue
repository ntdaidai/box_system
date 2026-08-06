<template>
  <main class="satellite-map-page">
    <div class="screen-frame">
      <header class="map-header">
        <div>
          <span class="header-kicker">DATENGXIA SATELLITE ZONE TEST</span>
          <h1>大藤峡库区平面区域测试图</h1>
        </div>
        <div class="selected-readout" :class="selectedZone.type">
          <span>当前区域</span>
          <strong>{{ selectedZone.name }}</strong>
        </div>
      </header>

      <section class="map-stage" aria-label="大藤峡库区平面卫星图区域测试">
        <div class="map-perspective">
          <div ref="mapBoardRef" class="map-board">
            <div class="map-content" :style="mapContentStyle">
              <img class="satellite-image" src="/dammap.png" alt="大藤峡水电站卫星底图" />
              <div class="map-vignette"></div>
              <svg
                class="zone-layer"
                viewBox="0 0 1000 430"
                preserveAspectRatio="none"
                aria-label="可点击区域图层"
            >
                <g
                  v-for="zone in zones"
                  :key="zone.id"
                  class="zone-group"
                  :class="[zone.type, { active: selectedZone.id === zone.id }]"
                  @click="selectZone(zone)"
                >
                  <path v-if="zone.path" :d="zone.path" fill-rule="evenodd" />
                  <polygon v-else :points="zone.points" />
                <text v-if="zone.label" :x="zone.label.x" :y="zone.label.y">{{ zone.name }}</text>
                </g>
              </svg>
              <div class="dam-axis"></div>
              <div class="scan-line"></div>
            </div>
          </div>
        </div>

        <aside class="map-hud">
          <div class="hud-card" :class="selectedZone.type">
            <p>区域属性</p>
            <h2>{{ selectedZone.name }}</h2>
            <div class="hud-status">{{ selectedZone.rule }}</div>
            <div class="hud-meta">
              <span>覆盖对象</span>
              <strong>{{ selectedZone.coverage }}</strong>
            </div>
            <div class="hud-meta">
              <span>交互方式</span>
              <strong>点击区域切换高亮，滚轮缩放地图</strong>
            </div>
          </div>

          <div class="legend-card">
            <div v-for="item in legend" :key="item.type" class="legend-row">
              <i :class="item.type"></i>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </aside>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const zones = [
  {
    id: 'person-forbidden',
    type: 'personForbidden',
    name: '人员禁入区',
    rule: '禁止人员进入',
    coverage: '手动标注的岸边禁入范围',
    path: 'M998 212 L917 214 L850 216 L780 227 L745 232 L719 246 L698 249 L699 266 L755 242 L839 228 L955 222 L998 227 Z',
  },
  {
    id: 'boat-forbidden',
    type: 'boatForbidden',
    name: '禁船区',
    rule: '禁止船只进入',
    coverage: '手动标注的水域禁船范围',
    path: 'M832 165 L750 170 L635 205 L616 207 L573 200 L519 179 L463 159 L413 159 L399 144 L363 147 L363 160 L331 162 L328 176 L295 202 L254 193 L228 198 L206 191 L200 301 L213 305 L238 302 L270 289 L291 287 L325 297 L359 284 L388 292 L398 304 L444 292 L500 281 L553 291 L595 280 L644 274 L697 249 L746 230 L832 215 Z',
  },
]

const legend = [
  { type: 'personForbidden', label: '人员禁入区' },
  { type: 'boatForbidden', label: '禁船区' },
]

const selectedId = ref('boat-forbidden')
const mapBoardRef = ref(null)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const selectedZone = computed(() => zones.find((zone) => zone.id === selectedId.value) || zones[0])
const mapContentStyle = computed(() => ({
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
}))

const selectZone = (zone) => {
  selectedId.value = zone.id
}

const handleWheel = (event) => {
  event.preventDefault()

  const board = mapBoardRef.value
  if (!board) return

  const rect = board.getBoundingClientRect()
  const pointerX = event.clientX - rect.left
  const pointerY = event.clientY - rect.top
  const previousZoom = zoom.value
  const zoomFactor = event.deltaY > 0 ? 0.88 : 1.12
  const nextZoom = Math.min(3.5, Math.max(1, Number((previousZoom * zoomFactor).toFixed(3))))

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

onMounted(() => {
  mapBoardRef.value?.addEventListener('wheel', handleWheel, { passive: false })
})

onBeforeUnmount(() => {
  mapBoardRef.value?.removeEventListener('wheel', handleWheel)
})
</script>

<style scoped>
.satellite-map-page {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  color: #e2f0fe;
  background:
    radial-gradient(circle at 50% 18%, rgba(0, 229, 255, 0.18), transparent 30%),
    linear-gradient(180deg, #061424 0%, #020915 100%);
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}

.screen-frame {
  width: 100%;
  height: 100%;
  padding: 20px 26px 24px;
  display: flex;
  flex-direction: column;
  background:
    linear-gradient(rgba(0, 200, 255, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 200, 255, 0.06) 1px, transparent 1px);
  background-size: 42px 42px;
}

.map-header {
  height: 76px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  border: 1px solid rgba(0, 200, 255, 0.26);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(15, 44, 76, 0.84), rgba(7, 27, 50, 0.72));
  box-shadow: inset 0 0 24px rgba(0, 200, 255, 0.04), 0 10px 30px rgba(0, 0, 0, 0.22);
}

.header-kicker {
  display: block;
  color: rgba(0, 229, 255, 0.68);
  font-size: 12px;
  letter-spacing: 0;
}

.map-header h1 {
  margin: 6px 0 0;
  font-size: 28px;
  line-height: 1;
  color: #f0f8ff;
  letter-spacing: 0;
}

.selected-readout {
  min-width: 250px;
  height: 48px;
  padding: 0 18px;
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: rgba(3, 18, 33, 0.76);
}

.selected-readout span {
  color: rgba(174, 202, 245, 0.72);
  font-size: 12px;
}

.selected-readout strong {
  margin-top: 3px;
  font-size: 18px;
}

.selected-readout.personForbidden strong {
  color: #ff6b6b;
}

.selected-readout.boatForbidden strong {
  color: #f7b731;
}

.selected-readout.navigation strong {
  color: #35e6d4;
}

.map-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  padding-top: 20px;
}

.map-perspective {
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-board {
  position: relative;
  width: min(100%, 1480px);
  aspect-ratio: 1916 / 824;
  border: 1px solid rgba(0, 229, 255, 0.42);
  border-radius: 10px;
  overflow: hidden;
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
  transition: transform 0.12s ease-out;
  will-change: transform;
}

.map-board::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent 0 48%, rgba(0, 229, 255, 0.24) 49%, transparent 50%),
    linear-gradient(180deg, transparent, rgba(0, 229, 255, 0.08), transparent);
  mix-blend-mode: screen;
}

.satellite-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(1.12) contrast(1.08) brightness(0.72);
}

.map-vignette {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 45%, transparent 42%, rgba(2, 9, 21, 0.72) 100%),
    linear-gradient(180deg, rgba(0, 20, 38, 0.32), rgba(0, 9, 22, 0.12));
}

.zone-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
}

.zone-group {
  cursor: pointer;
}

.zone-group polygon,
.zone-group path {
  stroke-width: 2.2;
  vector-effect: non-scaling-stroke;
  transition: fill 0.18s ease, stroke 0.18s ease, filter 0.18s ease, opacity 0.18s ease;
}

.zone-group text {
  pointer-events: none;
  fill: rgba(241, 248, 255, 0.92);
  font-size: 18px;
  font-weight: 700;
  text-anchor: middle;
  paint-order: stroke;
  stroke: rgba(1, 9, 18, 0.88);
  stroke-width: 4px;
  vector-effect: non-scaling-stroke;
  opacity: 0.88;
}

.zone-group.personForbidden polygon,
.zone-group.personForbidden path {
  fill: rgba(245, 68, 92, 0.18);
  stroke: rgba(255, 91, 111, 0.72);
}

.zone-group.boatForbidden polygon,
.zone-group.boatForbidden path {
  fill: rgba(247, 183, 49, 0.2);
  stroke: rgba(247, 183, 49, 0.82);
}

.zone-group.navigation polygon,
.zone-group.navigation path {
  fill: rgba(24, 220, 196, 0.16);
  stroke: rgba(31, 238, 220, 0.78);
}

.zone-group:hover polygon,
.zone-group:hover path,
.zone-group.active polygon,
.zone-group.active path {
  opacity: 1;
  filter: drop-shadow(0 0 8px currentColor);
}

.zone-group.personForbidden:hover,
.zone-group.personForbidden.active {
  color: #ff5b6f;
}

.zone-group.boatForbidden:hover,
.zone-group.boatForbidden.active {
  color: #f7b731;
}

.zone-group.navigation:hover,
.zone-group.navigation.active {
  color: #18dcc4;
}

.zone-group.active polygon,
.zone-group.active path {
  stroke-width: 3.4;
  fill-opacity: 0.36;
}

.dam-axis {
  position: absolute;
  z-index: 4;
  left: 39.8%;
  top: 23%;
  width: 3px;
  height: 52%;
  background: linear-gradient(180deg, transparent, rgba(0, 229, 255, 0.7), transparent);
  box-shadow: 0 0 16px rgba(0, 229, 255, 0.5);
  pointer-events: none;
}

.scan-line {
  position: absolute;
  z-index: 5;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 0%, rgba(0, 229, 255, 0.16) 50%, transparent 100%);
  height: 18%;
  animation: scan 4.8s linear infinite;
}

.map-hud {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
}

.hud-card,
.legend-card {
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 8px;
  background: rgba(7, 27, 50, 0.74);
  box-shadow: inset 0 0 24px rgba(0, 200, 255, 0.04);
}

.hud-card {
  padding: 20px;
}

.hud-card p {
  margin: 0;
  color: rgba(174, 202, 245, 0.78);
  font-size: 13px;
}

.hud-card h2 {
  margin: 8px 0 14px;
  color: #fff;
  font-size: 24px;
}

.hud-status {
  height: 38px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 16px;
  font-weight: 800;
}

.hud-card.personForbidden .hud-status {
  color: #ff7a88;
  background: rgba(245, 68, 92, 0.13);
}

.hud-card.boatForbidden .hud-status {
  color: #f7c45e;
  background: rgba(247, 183, 49, 0.13);
}

.hud-card.navigation .hud-status {
  color: #5ff4e4;
  background: rgba(24, 220, 196, 0.13);
}

.hud-meta {
  margin-top: 16px;
  display: grid;
  gap: 5px;
}

.hud-meta span {
  color: rgba(174, 202, 245, 0.68);
  font-size: 12px;
}

.hud-meta strong {
  color: #e2f0fe;
  font-size: 15px;
}

.legend-card {
  padding: 14px;
}

.legend-row {
  height: 34px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary, #aecaf5);
  font-size: 14px;
}

.legend-row i {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid currentColor;
}

.legend-row i.personForbidden {
  color: #ff5b6f;
  background: rgba(245, 68, 92, 0.24);
}

.legend-row i.boatForbidden {
  color: #f7b731;
  background: rgba(247, 183, 49, 0.24);
}

.legend-row i.navigation {
  color: #18dcc4;
  background: rgba(24, 220, 196, 0.24);
}

@keyframes scan {
  0% {
    transform: translateY(-120%);
    opacity: 0;
  }
  18%,
  82% {
    opacity: 1;
  }
  100% {
    transform: translateY(560%);
    opacity: 0;
  }
}

@media (max-width: 1180px) {
  .map-stage {
    grid-template-columns: 1fr;
  }

  .map-hud {
    display: none;
  }

}
</style>
