<template>
  <div class="runtime-monitor-page">
    <header class="runtime-head">
      <div>
        <p>感知监测 / 系统监测</p>
        <h2>System Runtime Digital Twin</h2>
      </div>
      <div class="runtime-actions">
        <span>自动刷新 {{ currentTimeText }}</span>
        <el-button :icon="Refresh" :loading="loading" class="refresh-btn" @click="loadAll">
          刷新
        </el-button>
      </div>
    </header>

    <main class="runtime-shell">
      <section class="topology-stage" aria-label="系统实时运行拓扑">
        <div class="stage-toolbar">
          <div>
            <span>Runtime Topology</span>
            <strong>{{ topologyHeadline }}</strong>
          </div>
          <div class="score-chip" :class="healthTone">
            <span>System Score</span>
            <strong>{{ healthScore }} / 100</strong>
          </div>
        </div>

        <div class="topology-canvas">
          <svg
            class="runtime-svg"
            viewBox="0 0 1120 640"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="系统运行拓扑"
          >
            <defs>
              <marker
                id="arrow-ok"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="#63d7c1" />
              </marker>
              <marker
                id="arrow-warn"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="#dfb863" />
              </marker>
              <marker
                id="arrow-danger"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="#ef7e8a" />
              </marker>
              <marker
                id="arrow-neutral"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="#6f8292" />
              </marker>
              <filter id="node-glow" x="-35%" y="-35%" width="170%" height="170%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feColorMatrix
                  in="blur"
                  type="matrix"
                  values="0 0 0 0 0.21 0 0 0 0 0.78 0 0 0 0 0.86 0 0 0 0.36 0"
                />
                <feMerge>
                  <feMergeNode />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <g class="zones">
              <rect
                v-for="zone in zones"
                :key="zone.key"
                :x="zone.x"
                :y="zone.y"
                :width="zone.width"
                :height="zone.height"
                rx="26"
                class="zone-band"
              />
              <text
                v-for="zone in zones"
                :key="`${zone.key}-label`"
                :x="zone.x + 18"
                :y="zone.y + 28"
                class="zone-label"
              >
                {{ zone.label }}
              </text>
            </g>

            <g class="edges">
              <g
                v-for="edge in topologyEdges"
                :key="edge.id"
                class="edge-group"
                :class="[edge.tone, { muted: edge.blocked, highlighted: highlightedEdgeIds.includes(edge.id) }]"
              >
                <path
                  :id="`edge-path-${edge.id}`"
                  :d="edge.path"
                  class="edge-path"
                  :marker-end="`url(#arrow-${edgeMarkerTone(edge.tone)})`"
                />
                <path :d="edge.path" class="edge-hit" />
                <circle v-if="edge.active" r="4.5" class="flow-dot">
                  <animateMotion :dur="edge.duration" repeatCount="indefinite" rotate="auto">
                    <mpath :href="`#edge-path-${edge.id}`" />
                  </animateMotion>
                </circle>
                <circle v-if="edge.active && edge.secondary" r="3" class="flow-dot secondary">
                  <animateMotion :dur="edge.secondaryDuration" repeatCount="indefinite" rotate="auto">
                    <mpath :href="`#edge-path-${edge.id}`" />
                  </animateMotion>
                </circle>
                <g v-if="edge.blocked" class="edge-break" :transform="`translate(${edge.breakX} ${edge.breakY})`">
                  <line x1="-8" y1="-8" x2="8" y2="8" />
                  <line x1="8" y1="-8" x2="-8" y2="8" />
                </g>
              </g>
            </g>

            <g class="nodes">
              <g
                v-for="node in topologyNodes"
                :key="node.id"
                class="runtime-node"
                :class="[
                  node.tone,
                  {
                    selected: selectedNodeId === node.id,
                    highlighted: highlightedNodeId === node.id,
                    impacted: impactedNodeIds.includes(node.id),
                  },
                ]"
                :transform="`translate(${node.x} ${node.y})`"
                tabindex="0"
                role="button"
                @click="inspectNode(node.id)"
                @keyup.enter="inspectNode(node.id)"
              >
                <circle v-if="node.pulse" r="48" class="node-pulse" />
                <rect
                  :x="-node.width / 2"
                  :y="-node.height / 2"
                  :width="node.width"
                  :height="node.height"
                  rx="14"
                  class="node-body"
                />
                <circle :cx="-node.width / 2 + 18" :cy="-node.height / 2 + 18" r="5" class="node-led" />
                <text class="node-title" text-anchor="middle" y="-7">{{ node.label }}</text>
                <text class="node-subtitle" text-anchor="middle" y="14">{{ node.sublabel }}</text>
                <text class="node-status" text-anchor="middle" y="35">{{ node.statusText }}</text>
              </g>
            </g>
          </svg>

          <div class="node-inspector" :class="inspectorNode.tone">
            <div class="inspector-head">
              <div>
                <span>Node Inspector</span>
                <strong>{{ inspectorNode.label }}</strong>
              </div>
              <button type="button" class="icon-text" @click="clearFocus">清除定位</button>
            </div>
            <p>{{ inspectorNode.description }}</p>

            <div v-if="inspectorNode.id === 'jetson'" class="resource-compact">
              <div v-for="metric in resourceMetrics" :key="metric.key" class="resource-line" :class="metric.tone">
                <span>{{ metric.label }}</span>
                <strong>{{ metric.display }}</strong>
                <svg viewBox="0 0 100 26" preserveAspectRatio="none">
                  <polyline :points="sparklinePoints(metric.key)" />
                </svg>
              </div>
              <div class="uptime-line">
                <span>UPTIME</span>
                <strong>{{ uptimeText }}</strong>
              </div>
            </div>

            <div v-else class="inspector-facts">
              <div v-for="fact in inspectorNode.facts" :key="fact.label">
                <span>{{ fact.label }}</span>
                <strong>{{ fact.value }}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside class="impact-panel">
        <div class="impact-summary">
          <div>
            <span>Impact Panel</span>
            <strong>{{ issueCounts.total ? `当前 ${issueCounts.total} 项异常` : '当前无阻断异常' }}</strong>
          </div>
          <button type="button" class="icon-text" @click="dependencyDrawerVisible = true">
            依赖服务
          </button>
        </div>

        <section class="capability-matrix">
          <header>
            <span>业务能力状态</span>
          </header>
          <div
            v-for="capability in capabilityStatus"
            :key="capability.key"
            class="capability-row"
            :class="capability.tone"
            @click="inspectNode(capability.nodeId)"
          >
            <span>{{ capability.label }}</span>
            <strong>{{ capability.status }}</strong>
          </div>
        </section>

        <section class="impact-list">
          <article
            v-for="issue in visibleIssues"
            :key="issue.key"
            class="impact-item"
            :class="issue.tone"
          >
            <div class="impact-level">{{ issue.levelLabel }}</div>
            <h3>{{ issue.title }}</h3>
            <dl>
              <div>
                <dt>影响能力</dt>
                <dd>{{ issue.impactAbility }}</dd>
              </div>
              <div>
                <dt>受影响链路</dt>
                <dd>{{ issue.pathLabel }}</dd>
              </div>
              <div>
                <dt>建议动作</dt>
                <dd>{{ issue.action }}</dd>
              </div>
              <div v-if="issue.unaffected?.length">
                <dt>不影响</dt>
                <dd>{{ issue.unaffected.join(' / ') }}</dd>
              </div>
            </dl>
            <div class="impact-actions">
              <button type="button" @click="locateIssue(issue)">定位节点</button>
              <button v-if="issue.route" type="button" @click="goRoute(issue.route)">前往模块</button>
              <button v-else type="button" @click="inspectNode(issue.nodeId)">查看资源</button>
            </div>
          </article>

          <div v-if="!issueItems.length" class="no-impact">
            <strong>主链路可用</strong>
            <span>数据接入、事件运行与联动执行保持连通。</span>
          </div>
        </section>
      </aside>
    </main>

    <section class="dependency-strip">
      <button type="button" class="dependency-summary" @click="dependencyDrawerVisible = true">
        <span>{{ dependencySummary.online }} services online</span>
        <span>{{ dependencySummary.degraded }} degraded</span>
        <span>{{ dependencySummary.offline }} offline</span>
      </button>
      <div class="quiet-services">
        <span v-for="service in serviceAttentionItems" :key="service.key" :class="service.tone">
          {{ service.name }} {{ service.status }}
        </span>
        <span v-if="!serviceAttentionItems.length">依赖服务无阻断告警</span>
      </div>
    </section>

    <el-drawer v-model="dependencyDrawerVisible" title="Dependency Inspector" size="460px" class="runtime-drawer">
      <div class="service-matrix">
        <article
          v-for="service in serviceItems"
          :key="service.key"
          class="service-cell"
          :class="service.tone"
          @click="inspectNode(service.nodeId)"
        >
          <span>{{ service.group }}</span>
          <strong>{{ service.name }}</strong>
          <em>{{ service.status }}</em>
          <small>{{ service.description }}</small>
        </article>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { getSystemInfo } from '@/api/dashboard'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList, getModelStatus } from '@/api/camera'

const router = useRouter()

const loading = ref(false)
const systemInfo = ref({})
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const modelStatus = ref({ loaded: false, models: {} })
const currentTime = ref(new Date())
const selectedNodeId = ref('jetson')
const highlightedNodeId = ref('')
const highlightedEdgeIds = ref([])
const dependencyDrawerVisible = ref(false)
const resourceHistory = ref({
  cpu: [],
  memory: [],
  disk: [],
  gpu: [],
})
let clockTimer = null
let focusTimer = null

const zones = [
  { key: 'perception', label: '感知层', x: 32, y: 52, width: 210, height: 536 },
  { key: 'edge', label: '边缘计算层', x: 288, y: 52, width: 240, height: 536 },
  { key: 'data-ai', label: '数据 / AI 服务层', x: 570, y: 52, width: 244, height: 536 },
  { key: 'event', label: '事件运行层', x: 842, y: 52, width: 246, height: 238 },
  { key: 'action', label: '联动执行层', x: 842, y: 326, width: 246, height: 262 },
]

const topologyDefinition = [
  {
    id: 'camera',
    label: 'Camera',
    sublabel: '摄像头接入',
    x: 134,
    y: 138,
    width: 148,
    height: 76,
    description: '数据库中启用的视频源经后端签发票据进入实时视频链路。',
  },
  {
    id: 'sensor',
    label: 'Sensors',
    sublabel: '传感器采集',
    x: 134,
    y: 318,
    width: 148,
    height: 76,
    description: '振动、雨量、风速、温湿度等传感器由采集服务汇入实时状态。',
  },
  {
    id: 'manual-source',
    label: 'Manual / Mini',
    sublabel: '人工与小程序',
    x: 134,
    y: 498,
    width: 148,
    height: 76,
    description: '人工上报与微信小程序接口进入统一业务后端。',
  },
  {
    id: 'ingest',
    label: 'Perception Ingress',
    sublabel: '感知接入',
    x: 374,
    y: 318,
    width: 170,
    height: 82,
    description: '后端将视频、传感器与人工入口整理为统一运行输入。',
  },
  {
    id: 'jetson',
    label: 'Jetson AGX',
    sublabel: '边缘节点',
    x: 484,
    y: 168,
    width: 160,
    height: 86,
    description: '当前系统运行与边缘推理所在节点，资源压力会影响检测和事件响应时延。',
    pulse: true,
  },
  {
    id: 'media',
    label: 'Media Stream',
    sublabel: 'MediaMTX / WebRTC',
    x: 660,
    y: 168,
    width: 168,
    height: 82,
    description: 'RTSP 视频经 MediaMTX / WebRTC 网关进入浏览器实时播放链路。',
  },
  {
    id: 'ai',
    label: 'AI Inference',
    sublabel: 'YOLO / Qwen',
    x: 660,
    y: 298,
    width: 168,
    height: 82,
    description: '边缘视觉检测和云边多模态分析共同支撑视频 AI 巡查。',
  },
  {
    id: 'timeseries',
    label: 'Time Series',
    sublabel: 'IoTDB',
    x: 660,
    y: 428,
    width: 168,
    height: 82,
    description: '传感器实时数据与历史数据写入时序链路，供规则计算和趋势查看使用。',
  },
  {
    id: 'eca',
    label: 'Rule Runtime',
    sublabel: 'ECA',
    x: 660,
    y: 542,
    width: 168,
    height: 72,
    description: 'ECA 引擎根据传感器、视觉和融合事件触发安全事件运行时。',
  },
  {
    id: 'event',
    label: 'Safety Event',
    sublabel: 'Runtime',
    x: 944,
    y: 246,
    width: 172,
    height: 86,
    description: '安全事件运行时统一编排广播、无人机、人工任务和报告归档。',
    pulse: true,
  },
  {
    id: 'broadcast',
    label: 'Broadcast',
    sublabel: '广播联动',
    x: 884,
    y: 444,
    width: 132,
    height: 70,
    description: '广播服务订阅安全事件动作并执行现场提醒。',
  },
  {
    id: 'drone',
    label: 'Drone',
    sublabel: '无人机调度',
    x: 1002,
    y: 444,
    width: 132,
    height: 70,
    description: '无人机调度服务根据事件动作执行巡检派发。',
  },
  {
    id: 'staff',
    label: 'Staff Task',
    sublabel: '人工任务',
    x: 884,
    y: 548,
    width: 132,
    height: 70,
    description: '人工任务服务承接高风险事件处置流转。',
  },
  {
    id: 'report',
    label: 'Report Archive',
    sublabel: '报告归档',
    x: 1002,
    y: 548,
    width: 132,
    height: 70,
    description: '巡查报告和事件证据进入文档与对象存储链路。',
  },
]

const edgeDefinition = [
  { id: 'camera-ingest', from: 'camera', to: 'ingest', path: 'M208 138 C260 138 280 262 305 296' },
  { id: 'sensor-ingest', from: 'sensor', to: 'ingest', path: 'M208 318 C244 318 276 318 289 318' },
  { id: 'manual-ingest', from: 'manual-source', to: 'ingest', path: 'M208 498 C260 498 280 374 305 340' },
  { id: 'ingest-jetson', from: 'ingest', to: 'jetson', path: 'M404 279 C408 236 424 198 424 178' },
  { id: 'jetson-media', from: 'jetson', to: 'media', path: 'M564 168 C592 168 606 168 576 168' },
  { id: 'jetson-ai', from: 'jetson', to: 'ai', path: 'M520 210 C548 250 574 286 576 298' },
  { id: 'ingest-timeseries', from: 'ingest', to: 'timeseries', path: 'M459 344 C512 378 548 424 576 428' },
  { id: 'timeseries-eca', from: 'timeseries', to: 'eca', path: 'M660 469 C660 492 660 509 660 506' },
  { id: 'media-event', from: 'media', to: 'event', path: 'M744 168 C820 166 852 206 858 232' },
  { id: 'ai-event', from: 'ai', to: 'event', path: 'M744 298 C804 298 828 258 858 250' },
  { id: 'eca-event', from: 'eca', to: 'event', path: 'M744 542 C826 506 842 334 858 268' },
  { id: 'event-broadcast', from: 'event', to: 'broadcast', path: 'M924 289 C914 344 897 390 892 409' },
  { id: 'event-drone', from: 'event', to: 'drone', path: 'M970 289 C982 344 998 390 1002 409' },
  { id: 'event-staff', from: 'event', to: 'staff', path: 'M915 289 C888 370 875 482 884 513' },
  { id: 'event-report', from: 'event', to: 'report', path: 'M986 289 C1020 376 1018 484 1008 513' },
]

const currentTimeText = computed(() => currentTime.value.toLocaleTimeString('zh-CN', {
  hour12: false,
  hour: '2-digit',
  minute: '2-digit',
}))

const systemReachable = computed(() => Object.keys(systemInfo.value || {}).length > 0)
const collectorRunning = computed(() => Boolean(systemInfo.value.sensor_collector_running))
const sensorsOnline = computed(() => {
  const values = Object.values(deviceStatus.value || {})
  if (values.length) return values.filter((item) => item?.status === 'online').length
  return Number(systemInfo.value.sensor_count?.online || 0)
})
const sensorsTotal = computed(() => {
  const count = Object.keys(deviceStatus.value || {}).length
  return count || Number(systemInfo.value.sensor_count?.total || 0)
})
const edgeModelReady = computed(() => Boolean(
  modelStatus.value.loaded || Object.values(modelStatus.value.models || {}).some((item) => item?.loaded),
))
const cloudModelReady = computed(() => systemInfo.value.ai_model === 'healthy')
const videoReady = computed(() => cameraSummary.value.online > 0 && edgeModelReady.value)
const eventRuntimeReady = computed(() => systemReachable.value)

function percent(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value || 0))))
}

function formatNumber(value, digits = 1) {
  const next = Number(value)
  if (!Number.isFinite(next)) return '--'
  return next.toFixed(digits).replace(/\.0$/, '')
}

function aiModelLabel(value) {
  return ({ healthy: '正常', unhealthy: '异常', unreachable: '不可达', unknown: '未知' })[value] || '待确认'
}

function toneRank(tone) {
  return ({ danger: 4, blocked: 4, warn: 3, neutral: 2, ok: 1 })[tone] || 2
}

function worstTone(tones) {
  return tones.reduce((worst, tone) => (toneRank(tone) > toneRank(worst) ? tone : worst), 'ok')
}

function riskTone(percentValue) {
  if (!systemReachable.value) return 'neutral'
  if (percentValue >= 85) return 'danger'
  if (percentValue >= 70) return 'warn'
  return 'ok'
}

function severityLabel(tone) {
  return ({ danger: 'CRITICAL', blocked: 'BLOCKED', warn: 'WARNING', ok: 'NORMAL', neutral: 'UNKNOWN' })[tone] || 'NOTICE'
}

function nodeStatus(id) {
  const resourceTone = resourceOverallTone.value

  if (!systemReachable.value && !['camera', 'sensor', 'manual-source'].includes(id)) {
    return { tone: 'danger', text: '后端不可达' }
  }

  const cameraTone = cameraSummary.value.total === 0
    ? 'neutral'
    : cameraSummary.value.online === 0
      ? 'danger'
      : cameraSummary.value.online < cameraSummary.value.total
        ? 'warn'
        : 'ok'

  const sensorTone = !collectorRunning.value
    ? 'danger'
    : sensorsTotal.value === 0
      ? 'neutral'
      : sensorsOnline.value < sensorsTotal.value
        ? 'warn'
        : 'ok'

  const statusMap = {
    camera: {
      tone: cameraTone,
      text: cameraSummary.value.total
        ? `${cameraSummary.value.online}/${cameraSummary.value.total} 在线`
        : '待配置',
    },
    sensor: {
      tone: sensorTone,
      text: sensorsTotal.value ? `${sensorsOnline.value}/${sensorsTotal.value} 在线` : '状态待返回',
    },
    'manual-source': {
      tone: systemReachable.value ? 'ok' : 'neutral',
      text: systemReachable.value ? '可接入' : '待确认',
    },
    ingest: {
      tone: worstTone([cameraTone, sensorTone]),
      text: collectorRunning.value ? '接入运行中' : '采集阻断',
    },
    jetson: {
      tone: resourceTone,
      text: resourceTone === 'ok' ? '资源平稳' : resourceTone === 'warn' ? '资源承压' : '资源临界',
    },
    media: {
      tone: cameraTone === 'danger' ? 'blocked' : cameraTone,
      text: cameraSummary.value.online > 0 ? '流媒体可用' : '无可用视频',
    },
    ai: {
      tone: edgeModelReady.value ? (cloudModelReady.value ? 'ok' : 'warn') : 'danger',
      text: edgeModelReady.value ? `Qwen ${aiModelLabel(systemInfo.value.ai_model)}` : '推理不可用',
    },
    timeseries: {
      tone: collectorRunning.value ? 'ok' : 'warn',
      text: collectorRunning.value ? '写入链路可用' : '采集待恢复',
    },
    eca: {
      tone: systemReachable.value ? 'ok' : 'danger',
      text: systemReachable.value ? '规则运行中' : '不可确认',
    },
    event: {
      tone: eventRuntimeReady.value ? 'ok' : 'danger',
      text: eventRuntimeReady.value ? '事件总线可用' : '事件阻断',
    },
    broadcast: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可执行' : 'BLOCKED',
    },
    drone: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可调度' : 'BLOCKED',
    },
    staff: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可派发' : 'BLOCKED',
    },
    report: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可归档' : 'BLOCKED',
    },
  }

  return statusMap[id] || { tone: 'neutral', text: '待确认' }
}

const resourceMetrics = computed(() => {
  const gpu = systemInfo.value.gpu || {}
  const gpuMemory = gpu.memory || {}
  const gpuPercent = percent(gpu.utilization_percent ?? gpuMemory.percent)

  return [
    {
      key: 'cpu',
      label: 'CPU',
      value: percent(systemInfo.value.cpu_percent),
      display: `${formatNumber(systemInfo.value.cpu_percent)}%`,
      tone: riskTone(percent(systemInfo.value.cpu_percent)),
    },
    {
      key: 'memory',
      label: 'MEM',
      value: percent(systemInfo.value.memory?.percent),
      display: `${formatNumber(systemInfo.value.memory?.percent)}%`,
      tone: riskTone(percent(systemInfo.value.memory?.percent)),
      detail: `${formatNumber(systemInfo.value.memory?.used_gb)} / ${formatNumber(systemInfo.value.memory?.total_gb)} GB`,
    },
    {
      key: 'disk',
      label: 'DISK',
      value: percent(systemInfo.value.disk?.percent),
      display: `${formatNumber(systemInfo.value.disk?.percent)}%`,
      tone: riskTone(percent(systemInfo.value.disk?.percent)),
      detail: `${formatNumber(systemInfo.value.disk?.used_gb)} / ${formatNumber(systemInfo.value.disk?.total_gb)} GB`,
    },
    {
      key: 'gpu',
      label: 'GPU',
      value: gpuPercent,
      display: gpu.available ? `${formatNumber(gpuPercent)}%` : '待确认',
      tone: gpu.available ? riskTone(gpuPercent) : 'neutral',
      detail: gpu.available ? `${formatNumber(gpu.temperature_c)}C / ${formatNumber(gpu.power_w)}W` : 'GPU 信息待确认',
    },
  ]
})

const resourceOverallTone = computed(() => worstTone(resourceMetrics.value.map((metric) => metric.tone)))

const resourceIssueMetrics = computed(() => resourceMetrics.value.filter((metric) => metric.tone === 'warn' || metric.tone === 'danger'))

const uptimeText = computed(() => {
  const hours = Number(systemInfo.value.system_uptime_hours || 0)
  if (!hours) return '--'
  if (hours >= 24) return `${formatNumber(hours / 24)}d`
  return `${formatNumber(hours)}h`
})

const topologyNodes = computed(() => topologyDefinition.map((node) => {
  const status = nodeStatus(node.id)
  return {
    ...node,
    tone: status.tone,
    statusText: status.text,
    facts: nodeFacts(node.id),
  }
}))

const topologyNodeMap = computed(() => Object.fromEntries(topologyNodes.value.map((node) => [node.id, node])))

function isEdgeBlocked(edge, from, to) {
  if (!systemReachable.value && !['camera-ingest', 'sensor-ingest', 'manual-ingest'].includes(edge.id)) return true
  if (edge.id === 'camera-ingest') return cameraSummary.value.total > 0 && cameraSummary.value.online === 0
  if (edge.id === 'sensor-ingest') return !collectorRunning.value
  if (edge.id === 'jetson-ai') return !edgeModelReady.value
  if (edge.id === 'ai-event') return !edgeModelReady.value
  if (edge.id === 'media-event') return cameraSummary.value.total > 0 && cameraSummary.value.online === 0
  return from.tone === 'danger' || from.tone === 'blocked' || to.tone === 'danger' || to.tone === 'blocked'
}

const topologyEdges = computed(() => edgeDefinition.map((edge, index) => {
  const from = topologyNodeMap.value[edge.from]
  const to = topologyNodeMap.value[edge.to]
  const blocked = isEdgeBlocked(edge, from, to)
  const tone = blocked ? 'danger' : worstTone([from.tone, to.tone])
  return {
    ...edge,
    tone,
    blocked,
    active: !blocked && tone !== 'neutral',
    duration: `${8 + (index % 4) * 1.3}s`,
    secondary: index % 2 === 0,
    secondaryDuration: `${11 + (index % 5) * 1.2}s`,
    breakX: edgeBreakPoint(edge.path).x,
    breakY: edgeBreakPoint(edge.path).y,
  }
}))

function edgeMarkerTone(tone) {
  if (tone === 'blocked') return 'danger'
  return ['ok', 'warn', 'danger'].includes(tone) ? tone : 'neutral'
}

function edgeBreakPoint(path) {
  const numbers = path.match(/-?\d+(\.\d+)?/g)?.map(Number) || []
  if (numbers.length < 4) return { x: 0, y: 0 }
  const pairs = []
  for (let index = 0; index < numbers.length; index += 2) {
    pairs.push({ x: numbers[index], y: numbers[index + 1] })
  }
  return pairs[Math.floor(pairs.length / 2)] || pairs[0]
}

const capabilityStatus = computed(() => [
  {
    key: 'video',
    label: '实时视频',
    status: cameraSummary.value.online > 0 ? '可用' : '不可用',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'danger',
    nodeId: 'media',
  },
  {
    key: 'sensor',
    label: '传感器采集',
    status: collectorRunning.value ? '可用' : '不可用',
    tone: collectorRunning.value ? 'ok' : 'danger',
    nodeId: 'sensor',
  },
  {
    key: 'ai-video',
    label: 'AI 视频识别',
    status: videoReady.value ? '可用' : '不可用',
    tone: videoReady.value ? 'ok' : 'danger',
    nodeId: 'ai',
  },
  {
    key: 'event',
    label: '事件引擎',
    status: eventRuntimeReady.value ? '可用' : '不可用',
    tone: eventRuntimeReady.value ? 'ok' : 'danger',
    nodeId: 'event',
  },
  {
    key: 'action',
    label: '联动执行',
    status: eventRuntimeReady.value ? '可用' : '不可用',
    tone: eventRuntimeReady.value ? 'ok' : 'danger',
    nodeId: 'broadcast',
  },
])

const issueItems = computed(() => {
  if (!systemReachable.value) {
    return [{
      key: 'system-unreachable',
      title: '后端系统信息不可达',
      nodeId: 'jetson',
      edgeIds: ['ingest-jetson', 'jetson-media', 'jetson-ai', 'eca-event'],
      tone: 'danger',
      levelLabel: 'CRITICAL',
      impactAbility: '系统监测与事件运行确认',
      pathLabel: 'Jetson AGX → Safety Event Runtime',
      action: '确认 FastAPI 服务、网络代理与 /v1/system/info。',
    }]
  }

  const items = []

  if (!collectorRunning.value) {
    items.push({
      key: 'collector',
      title: '传感器采集服务未运行',
      nodeId: 'sensor',
      edgeIds: ['sensor-ingest', 'ingest-timeseries', 'timeseries-eca'],
      tone: 'danger',
      levelLabel: 'CRITICAL',
      impactAbility: '传感器采集、时序入库、ECA 传感器触发',
      pathLabel: 'Sensors → Perception Ingress → IoTDB → ECA',
      action: '检查采集器进程、串口链路与 IoTDB 写入状态。',
      route: '/monitor/sensors',
    })
  }

  if (sensorsTotal.value > 0 && sensorsOnline.value < sensorsTotal.value) {
    items.push({
      key: 'sensors-offline',
      title: '部分感知设备离线',
      nodeId: 'sensor',
      edgeIds: ['sensor-ingest'],
      tone: 'warn',
      levelLabel: 'WARNING',
      impactAbility: '传感器覆盖完整性',
      pathLabel: 'Sensors → Perception Ingress',
      action: '核对离线设备、电源和采集通道。',
      route: '/monitor/sensors',
    })
  }

  if (cameraSummary.value.total > 0 && cameraSummary.value.online < cameraSummary.value.total) {
    items.push({
      key: 'camera-offline',
      title: '视频通道不完整',
      nodeId: 'camera',
      edgeIds: ['camera-ingest', 'jetson-media', 'media-event'],
      tone: cameraSummary.value.online === 0 ? 'danger' : 'warn',
      levelLabel: cameraSummary.value.online === 0 ? 'CRITICAL' : 'WARNING',
      impactAbility: '实时视频、视频取证',
      pathLabel: 'Camera → Media Stream → Safety Event Runtime',
      action: '检查摄像头连接、RTSP 地址和 WebRTC 信令。',
      route: '/monitor/camera',
    })
  }

  if (!edgeModelReady.value) {
    items.push({
      key: 'edge-model',
      title: '边缘视觉模型未确认',
      nodeId: 'ai',
      edgeIds: ['jetson-ai', 'ai-event'],
      tone: 'danger',
      levelLabel: 'CRITICAL',
      impactAbility: '视频 AI 巡查',
      pathLabel: 'Camera → AI Inference → Detection',
      action: '检查模型加载状态，必要时重新加载边缘检测模型。',
      route: '/system/models',
      unaffected: ['传感器采集', 'ECA 规则', '安全事件人工处置'],
    })
  }

  if (!cloudModelReady.value) {
    items.push({
      key: 'cloud-model',
      title: '云边大模型不可达',
      nodeId: 'ai',
      edgeIds: ['ai-event'],
      tone: 'warn',
      levelLabel: 'WARNING',
      impactAbility: '多模态语义研判',
      pathLabel: 'AI Inference → Safety Event Runtime',
      action: '检查 Qwen3-VL 服务、模型端口和网络连通性。',
      route: '/system/models',
    })
  }

  for (const metric of resourceIssueMetrics.value) {
    items.push({
      key: `resource-${metric.key}`,
      title: `${metric.label} 资源压力偏高`,
      nodeId: 'jetson',
      edgeIds: ['ingest-jetson', 'jetson-ai'],
      tone: metric.tone,
      levelLabel: severityLabel(metric.tone),
      impactAbility: '边缘推理与页面响应时延',
      pathLabel: 'Jetson AGX → AI Inference',
      action: `当前 ${metric.label} ${metric.display}，建议查看进程和资源趋势。`,
    })
  }

  return items
})

const visibleIssues = computed(() => issueItems.value.slice(0, 4))

const issueCounts = computed(() => issueItems.value.reduce((acc, item) => {
  acc.total += 1
  if (item.tone === 'danger') acc.danger += 1
  else if (item.tone === 'warn') acc.warn += 1
  return acc
}, { total: 0, danger: 0, warn: 0 }))

const impactedNodeIds = computed(() => {
  const ids = new Set()
  for (const edge of topologyEdges.value) {
    if (edge.blocked) ids.add(edge.to)
  }
  return [...ids]
})

const healthScore = computed(() => {
  if (!systemReachable.value) return 0

  let score = 100
  if (!collectorRunning.value) score -= 18
  if (sensorsTotal.value > 0 && sensorsOnline.value < sensorsTotal.value) {
    score -= Math.min(18, (sensorsTotal.value - sensorsOnline.value) * 6)
  }
  if (cameraSummary.value.total > 0 && cameraSummary.value.online < cameraSummary.value.total) score -= 10
  if (!edgeModelReady.value) score -= 16
  if (!cloudModelReady.value) score -= 10

  for (const metric of resourceMetrics.value) {
    if (metric.tone === 'danger') score -= 12
    else if (metric.tone === 'warn') score -= 6
  }

  return Math.max(0, Math.min(100, score))
})

const healthTone = computed(() => {
  if (!systemReachable.value || issueCounts.value.danger > 0 || healthScore.value < 65) return 'danger'
  if (issueCounts.value.warn > 0 || healthScore.value < 85) return 'warn'
  return 'ok'
})

const topologyHeadline = computed(() => {
  if (!systemReachable.value) return '运行拓扑不可确认'
  if (issueCounts.value.danger > 0) return '关键链路存在阻断'
  if (issueCounts.value.warn > 0) return '主链路可用，局部能力降级'
  return '系统主链路运行中'
})

const inspectorNode = computed(() => {
  const node = topologyNodeMap.value[selectedNodeId.value] || topologyNodes.value[0] || {}
  return {
    ...node,
    facts: node.facts || [],
  }
})

function nodeFacts(id) {
  const facts = {
    camera: [
      { label: '启用通道', value: `${cameraSummary.value.total}` },
      { label: '在线通道', value: `${cameraSummary.value.online}` },
    ],
    sensor: [
      { label: '采集器', value: collectorRunning.value ? '运行中' : '待确认' },
      { label: '在线设备', value: sensorsTotal.value ? `${sensorsOnline.value}/${sensorsTotal.value}` : '待返回' },
    ],
    'manual-source': [
      { label: '后端接口', value: systemReachable.value ? '可达' : '待确认' },
      { label: '来源', value: '人工 / 小程序' },
    ],
    ingest: [
      { label: '视频输入', value: cameraSummary.value.total ? `${cameraSummary.value.online}/${cameraSummary.value.total}` : '待配置' },
      { label: '传感器输入', value: sensorsTotal.value ? `${sensorsOnline.value}/${sensorsTotal.value}` : '待返回' },
    ],
    media: [
      { label: 'MediaMTX', value: cameraSummary.value.total ? '已接入' : '待配置' },
      { label: 'WebRTC', value: cameraSummary.value.online > 0 ? '可用' : '待确认' },
    ],
    ai: [
      { label: '边缘模型', value: edgeModelReady.value ? '已加载' : '未确认' },
      { label: 'Qwen3-VL', value: aiModelLabel(systemInfo.value.ai_model) },
    ],
    timeseries: [
      { label: 'IoTDB', value: systemReachable.value ? '已配置' : '待确认' },
      { label: '写入前提', value: collectorRunning.value ? '采集运行中' : '采集待恢复' },
    ],
    eca: [
      { label: '规则引擎', value: systemReachable.value ? '可用' : '待确认' },
      { label: '触发源', value: '传感器 / 视觉' },
    ],
    event: [
      { label: '事件总线', value: eventRuntimeReady.value ? '可用' : '待确认' },
      { label: '联动订阅', value: '广播 / 无人机 / 人工任务' },
    ],
    broadcast: [{ label: '执行状态', value: eventRuntimeReady.value ? '可执行' : '阻断' }],
    drone: [{ label: '执行状态', value: eventRuntimeReady.value ? '可调度' : '阻断' }],
    staff: [{ label: '执行状态', value: eventRuntimeReady.value ? '可派发' : '阻断' }],
    report: [{ label: '归档状态', value: eventRuntimeReady.value ? '可归档' : '阻断' }],
  }
  return facts[id] || []
}

const serviceItems = computed(() => [
  {
    key: 'mysql',
    name: 'MySQL',
    group: 'Data',
    status: systemReachable.value ? 'online' : 'offline',
    tone: systemReachable.value ? 'ok' : 'danger',
    nodeId: 'event',
    description: '业务主库，后端可达时视为可用。',
  },
  {
    key: 'redis',
    name: 'Redis',
    group: 'Cache',
    status: systemReachable.value ? 'online' : 'unknown',
    tone: systemReachable.value ? 'ok' : 'neutral',
    nodeId: 'event',
    description: '缓存与短期队列，当前接口无独立健康字段。',
  },
  {
    key: 'iotdb',
    name: 'IoTDB',
    group: 'Time Series',
    status: collectorRunning.value ? 'online' : 'degraded',
    tone: collectorRunning.value ? 'ok' : 'warn',
    nodeId: 'timeseries',
    description: '时序数据写入依赖采集器运行。',
  },
  {
    key: 'minio',
    name: 'MinIO',
    group: 'Object',
    status: systemReachable.value ? 'configured' : 'unknown',
    tone: systemReachable.value ? 'ok' : 'neutral',
    nodeId: 'report',
    description: '截图、证据和文档对象存储。',
  },
  {
    key: 'mediamtx',
    name: 'MediaMTX',
    group: 'Video',
    status: cameraSummary.value.online > 0 ? 'online' : 'degraded',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
    nodeId: 'media',
    description: 'RTSP 视频流转发。',
  },
  {
    key: 'webrtc',
    name: 'WebRTC',
    group: 'Video',
    status: cameraSummary.value.online > 0 ? 'online' : 'degraded',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
    nodeId: 'media',
    description: '浏览器实时视频播放信令。',
  },
  {
    key: 'qwen',
    name: 'Qwen3-VL',
    group: 'AI',
    status: cloudModelReady.value ? 'online' : 'offline',
    tone: cloudModelReady.value ? 'ok' : 'danger',
    nodeId: 'ai',
    description: '多模态语义分析服务。',
  },
  {
    key: 'yolo',
    name: 'YOLO Detector',
    group: 'AI',
    status: edgeModelReady.value ? 'loaded' : 'offline',
    tone: edgeModelReady.value ? 'ok' : 'danger',
    nodeId: 'ai',
    description: '边缘目标检测 / 分类模型。',
  },
  {
    key: 'onlyoffice',
    name: 'OnlyOffice',
    group: 'Document',
    status: 'on demand',
    tone: 'neutral',
    nodeId: 'report',
    description: '文档预览与编辑服务。',
  },
])

const dependencySummary = computed(() => serviceItems.value.reduce((acc, service) => {
  if (service.tone === 'ok') acc.online += 1
  else if (service.tone === 'danger') acc.offline += 1
  else acc.degraded += 1
  return acc
}, { online: 0, degraded: 0, offline: 0 }))

const serviceAttentionItems = computed(() => serviceItems.value.filter((service) => service.tone === 'warn' || service.tone === 'danger').slice(0, 4))

function sparklinePoints(key) {
  const values = resourceHistory.value[key] || []
  const source = values.length > 1 ? values : [0, resourceMetrics.value.find((metric) => metric.key === key)?.value || 0]
  const step = 100 / Math.max(1, source.length - 1)
  return source.map((value, index) => {
    const x = index * step
    const y = 24 - (Math.max(0, Math.min(100, value)) / 100) * 20
    return `${formatNumber(x, 2)},${formatNumber(y, 2)}`
  }).join(' ')
}

function pushResourceSample() {
  const next = { ...resourceHistory.value }
  for (const metric of resourceMetrics.value) {
    next[metric.key] = [...(next[metric.key] || []), metric.value].slice(-24)
  }
  resourceHistory.value = next
}

function inspectNode(nodeId) {
  selectedNodeId.value = nodeId
  highlightedNodeId.value = nodeId
}

function locateIssue(issue) {
  selectedNodeId.value = issue.nodeId
  highlightedNodeId.value = issue.nodeId
  highlightedEdgeIds.value = issue.edgeIds || []
  if (focusTimer) clearTimeout(focusTimer)
  focusTimer = setTimeout(() => {
    highlightedEdgeIds.value = []
  }, 8000)
}

function clearFocus() {
  highlightedNodeId.value = ''
  highlightedEdgeIds.value = []
}

function goRoute(route) {
  router.push(route)
}

function unwrap(response) {
  return response?.data || {}
}

async function loadAll() {
  loading.value = true
  try {
    const [system, devices, cameras, models] = await Promise.allSettled([
      getSystemInfo(),
      getDeviceStatus(),
      getCameraList(),
      getModelStatus({ silentError: true }),
    ])

    systemInfo.value = system.status === 'fulfilled' ? unwrap(system.value) : {}
    deviceStatus.value = devices.status === 'fulfilled' ? unwrap(devices.value) : {}
    modelStatus.value = models.status === 'fulfilled' ? unwrap(models.value) : { loaded: false, models: {} }

    if (cameras.status === 'fulfilled') {
      const list = unwrap(cameras.value)?.cameras || []
      const enabled = list.filter((camera) => camera.enabled !== false)
      cameraSummary.value = {
        online: enabled.filter((camera) => camera.connected).length,
        total: enabled.length,
      }
    } else {
      cameraSummary.value = { online: 0, total: 0 }
    }

    pushResourceSample()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
  clockTimer = setInterval(() => {
    currentTime.value = new Date()
    loadAll()
  }, 30000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (focusTimer) clearTimeout(focusTimer)
})
</script>

<style scoped>
.runtime-monitor-page {
  min-height: 100%;
  padding: 18px;
  color: #e8f1f5;
  background:
    radial-gradient(circle at 28% 12%, rgba(57, 138, 157, 0.15), transparent 36%),
    linear-gradient(180deg, #0b1620 0%, #0a141d 50%, #081119 100%);
}

.runtime-monitor-page,
.runtime-monitor-page * {
  box-sizing: border-box;
}

.runtime-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 14px;
}

.runtime-head p,
.stage-toolbar span,
.score-chip span,
.impact-summary span,
.capability-matrix header span,
.node-inspector span,
.resource-line span,
.uptime-line span,
.service-cell span {
  margin: 0;
  color: #7f95a3;
  font-size: 12px;
}

.runtime-head h2 {
  margin: 4px 0 0;
  color: #f2f7f8;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: 0;
}

.runtime-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #9caab4;
  font-size: 12px;
}

.refresh-btn {
  border-radius: 8px;
}

.runtime-shell {
  display: grid;
  grid-template-columns: minmax(840px, 1fr) 360px;
  gap: 14px;
  align-items: stretch;
}

.topology-stage,
.impact-panel,
.dependency-strip {
  border: 1px solid rgba(115, 190, 206, 0.16);
  background: rgba(11, 26, 37, 0.88);
  box-shadow: 0 18px 40px rgba(0, 8, 16, 0.24);
}

.topology-stage {
  min-height: calc(100vh - 152px);
  padding: 14px;
  border-radius: 10px;
}

.stage-toolbar,
.impact-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.stage-toolbar strong,
.impact-summary strong {
  display: block;
  margin-top: 4px;
  color: #f2f7f8;
  font-size: 16px;
  font-weight: 650;
}

.score-chip {
  min-width: 120px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.035);
  text-align: right;
}

.score-chip strong {
  display: block;
  margin-top: 3px;
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}

.score-chip.ok strong { color: #69d7bd; }
.score-chip.warn strong { color: #dfb863; }
.score-chip.danger strong { color: #ef7e8a; }

.topology-canvas {
  position: relative;
  min-height: 650px;
  margin-top: 10px;
  overflow: hidden;
  border-radius: 8px;
  background:
    linear-gradient(rgba(119, 167, 183, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(119, 167, 183, 0.045) 1px, transparent 1px),
    rgba(7, 18, 27, 0.72);
  background-size: 34px 34px;
}

.runtime-svg {
  display: block;
  width: 100%;
  height: min(69vh, 700px);
  min-height: 560px;
}

.zone-band {
  fill: rgba(255, 255, 255, 0.018);
  stroke: rgba(137, 180, 192, 0.12);
  stroke-dasharray: 6 9;
}

.zone-label {
  fill: rgba(174, 195, 204, 0.58);
  font-size: 13px;
  letter-spacing: 0;
}

.edge-path {
  fill: none;
  stroke: rgba(105, 215, 189, 0.58);
  stroke-width: 2;
  stroke-linecap: round;
}

.edge-group.warn .edge-path {
  stroke: rgba(223, 184, 99, 0.7);
}

.edge-group.danger .edge-path,
.edge-group.blocked .edge-path {
  stroke: rgba(239, 126, 138, 0.78);
  stroke-dasharray: 8 10;
}

.edge-group.neutral .edge-path,
.edge-group.muted .edge-path {
  stroke: rgba(111, 130, 146, 0.48);
}

.edge-group.highlighted .edge-path {
  stroke-width: 4;
  filter: url(#node-glow);
}

.edge-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 18;
}

.flow-dot {
  fill: #bdf8ed;
  opacity: 0.8;
  filter: url(#node-glow);
}

.flow-dot.secondary {
  opacity: 0.48;
}

.edge-group.warn .flow-dot {
  fill: #ffe0a1;
}

.edge-break line {
  stroke: #ef7e8a;
  stroke-width: 3;
  stroke-linecap: round;
}

.runtime-node {
  cursor: pointer;
  outline: none;
}

.node-body {
  fill: rgba(13, 34, 48, 0.96);
  stroke: rgba(132, 164, 177, 0.36);
  stroke-width: 1.4;
  transition: fill 0.2s ease, stroke 0.2s ease, stroke-width 0.2s ease;
}

.runtime-node.ok .node-body {
  stroke: rgba(105, 215, 189, 0.7);
}

.runtime-node.warn .node-body {
  stroke: rgba(223, 184, 99, 0.84);
}

.runtime-node.danger .node-body,
.runtime-node.blocked .node-body {
  stroke: rgba(239, 126, 138, 0.92);
  fill: rgba(45, 23, 31, 0.96);
}

.runtime-node.neutral .node-body {
  stroke: rgba(113, 132, 147, 0.42);
}

.runtime-node.selected .node-body,
.runtime-node.highlighted .node-body {
  stroke-width: 3;
  filter: url(#node-glow);
}

.runtime-node.impacted .node-body {
  stroke-dasharray: 7 6;
}

.node-led {
  fill: #6f8292;
}

.runtime-node.ok .node-led { fill: #69d7bd; }
.runtime-node.warn .node-led { fill: #dfb863; }
.runtime-node.danger .node-led,
.runtime-node.blocked .node-led { fill: #ef7e8a; }

.node-title {
  fill: #edf6f7;
  font-size: 14px;
  font-weight: 650;
}

.node-subtitle {
  fill: #a9bac4;
  font-size: 11px;
}

.node-status {
  fill: #7f95a3;
  font-size: 10.5px;
}

.runtime-node.ok .node-status { fill: #79ddc5; }
.runtime-node.warn .node-status { fill: #dfb863; }
.runtime-node.danger .node-status,
.runtime-node.blocked .node-status { fill: #ef7e8a; }

.node-pulse {
  fill: rgba(105, 215, 189, 0.08);
  stroke: rgba(105, 215, 189, 0.22);
  animation: nodePulse 4.8s ease-in-out infinite;
}

.runtime-node.danger .node-pulse,
.runtime-node.blocked .node-pulse {
  fill: rgba(239, 126, 138, 0.08);
  stroke: rgba(239, 126, 138, 0.22);
}

.node-inspector {
  position: absolute;
  left: 18px;
  bottom: 18px;
  width: min(380px, calc(100% - 36px));
  padding: 13px;
  border: 1px solid rgba(115, 190, 206, 0.17);
  border-radius: 8px;
  background: rgba(8, 20, 30, 0.9);
  backdrop-filter: blur(10px);
}

.inspector-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.inspector-head strong {
  display: block;
  margin-top: 4px;
  color: #f2f7f8;
  font-size: 15px;
}

.node-inspector p {
  margin: 10px 0 0;
  color: #9badb8;
  font-size: 12px;
  line-height: 1.5;
}

.resource-compact {
  display: grid;
  gap: 7px;
  margin-top: 12px;
}

.resource-line {
  display: grid;
  grid-template-columns: 52px 64px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.resource-line strong,
.uptime-line strong {
  color: #eaf4f5;
  font-size: 12px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.resource-line svg {
  width: 100%;
  height: 26px;
}

.resource-line polyline {
  fill: none;
  stroke: #69d7bd;
  stroke-width: 2;
}

.resource-line.warn polyline { stroke: #dfb863; }
.resource-line.danger polyline { stroke: #ef7e8a; }
.resource-line.neutral polyline { stroke: #6f8292; }

.uptime-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.inspector-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.inspector-facts div {
  min-width: 0;
  padding: 9px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.035);
}

.inspector-facts strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: #eaf4f5;
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.impact-panel {
  min-height: calc(100vh - 152px);
  padding: 14px;
  border-radius: 10px;
}

.icon-text {
  border: 0;
  padding: 0;
  background: transparent;
  color: #90cdd4;
  font-size: 12px;
  cursor: pointer;
}

.icon-text:hover {
  color: #f2f7f8;
}

.capability-matrix {
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.028);
}

.capability-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.065);
  cursor: pointer;
}

.capability-row:first-of-type {
  margin-top: 7px;
}

.capability-row span {
  color: #b9c6cc;
  font-size: 12px;
}

.capability-row strong {
  font-size: 12px;
  font-weight: 650;
}

.capability-row.ok strong { color: #69d7bd; }
.capability-row.warn strong { color: #dfb863; }
.capability-row.danger strong { color: #ef7e8a; }

.impact-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.impact-item {
  padding: 13px;
  border-left: 3px solid #6f8292;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.impact-item.warn {
  border-left-color: #dfb863;
}

.impact-item.danger {
  border-left-color: #ef7e8a;
  background: rgba(70, 25, 34, 0.24);
}

.impact-level {
  color: #8fa0aa;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.impact-item.warn .impact-level { color: #dfb863; }
.impact-item.danger .impact-level { color: #ef7e8a; }

.impact-item h3 {
  margin: 6px 0 10px;
  color: #f2f7f8;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.35;
}

.impact-item dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.impact-item dt {
  color: #7f95a3;
  font-size: 11px;
}

.impact-item dd {
  margin: 3px 0 0;
  color: #bfccd2;
  font-size: 12px;
  line-height: 1.45;
}

.impact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.impact-actions button {
  min-height: 28px;
  border: 1px solid rgba(144, 205, 212, 0.26);
  border-radius: 7px;
  padding: 0 10px;
  background: rgba(144, 205, 212, 0.07);
  color: #c7eef1;
  font-size: 12px;
  cursor: pointer;
}

.impact-actions button:hover {
  border-color: rgba(199, 238, 241, 0.48);
  color: #ffffff;
}

.no-impact {
  display: grid;
  gap: 5px;
  min-height: 132px;
  place-content: center;
  border: 1px dashed rgba(105, 215, 189, 0.28);
  border-radius: 8px;
  color: #9badb8;
  text-align: center;
}

.no-impact strong {
  color: #bdf8ed;
  font-size: 14px;
}

.no-impact span {
  font-size: 12px;
}

.dependency-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 8px;
}

.dependency-summary {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 10px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #c8d8de;
  font-size: 12px;
  cursor: pointer;
}

.quiet-services {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  color: #7f95a3;
  font-size: 12px;
}

.quiet-services span {
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.035);
}

.quiet-services .warn { color: #dfb863; }
.quiet-services .danger { color: #ef7e8a; }

.service-matrix {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.service-cell {
  min-height: 116px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
  cursor: pointer;
}

.service-cell.ok { border-color: rgba(105, 215, 189, 0.28); }
.service-cell.warn { border-color: rgba(223, 184, 99, 0.36); }
.service-cell.danger { border-color: rgba(239, 126, 138, 0.42); }

.service-cell strong {
  display: block;
  margin-top: 6px;
  color: #f2f7f8;
  font-size: 14px;
}

.service-cell em {
  display: block;
  margin-top: 5px;
  color: #69d7bd;
  font-size: 12px;
  font-style: normal;
}

.service-cell.warn em { color: #dfb863; }
.service-cell.danger em { color: #ef7e8a; }
.service-cell.neutral em { color: #9badb8; }

.service-cell small {
  display: block;
  margin-top: 8px;
  color: #93a4ae;
  font-size: 12px;
  line-height: 1.45;
}

@keyframes nodePulse {
  0% {
    transform: scale(0.86);
    opacity: 0.2;
  }
  52% {
    transform: scale(1.12);
    opacity: 0.52;
  }
  100% {
    transform: scale(0.86);
    opacity: 0.2;
  }
}

@media (max-width: 1680px) {
  .runtime-shell {
    grid-template-columns: minmax(760px, 1fr) 340px;
  }

  .runtime-svg {
    height: min(66vh, 640px);
    min-height: 520px;
  }

  .topology-canvas {
    min-height: 606px;
  }
}

@media (max-width: 1480px) {
  .runtime-monitor-page {
    padding: 14px;
  }

  .runtime-shell {
    grid-template-columns: minmax(690px, 1fr) 330px;
    gap: 12px;
  }

  .topology-stage,
  .impact-panel {
    min-height: calc(100vh - 136px);
  }

  .runtime-svg {
    height: min(64vh, 600px);
    min-height: 500px;
  }

  .topology-canvas {
    min-height: 584px;
  }

  .node-inspector {
    width: 340px;
  }
}

@media (max-width: 1180px) {
  .runtime-shell {
    grid-template-columns: 1fr;
  }

  .impact-panel,
  .topology-stage {
    min-height: auto;
  }

  .impact-panel {
    display: grid;
    grid-template-columns: 320px minmax(0, 1fr);
    gap: 12px;
  }

  .capability-matrix,
  .impact-list {
    margin-top: 0;
  }
}
</style>
