<template>
  <div class="runtime-monitor-page">
    <main class="runtime-shell">
      <section class="topology-stage" aria-label="系统实时运行拓扑">
        <div class="topology-canvas">
          <svg
            class="runtime-svg"
            viewBox="20 32 1180 572"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="系统运行拓扑"
            @pointermove="onNodeDrag"
            @pointerup="stopNodeDrag"
            @pointerleave="stopNodeDrag"
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

            <g class="topology-viewport">
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
                  @pointerdown.stop.prevent="startNodeDrag($event, node.id)"
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
                  <text class="node-title" text-anchor="middle" y="-3">{{ node.displayLabel }}</text>
                  <text class="node-status" text-anchor="middle" y="23">{{ node.displaySubline }}</text>
                </g>
              </g>
            </g>
          </svg>
        </div>

        <div class="runtime-detail-row">
          <article class="node-inspector" :class="inspectorNode.tone">
            <div class="inspector-head">
              <div>
                <span>节点诊断</span>
                <strong>{{ inspectorNode.displayLabel }}</strong>
              </div>
              <p>{{ inspectorNode.statusText }} · {{ inspectorNode.description }}</p>
            </div>

            <div v-if="inspectorNode.id === 'edge-box'" class="resource-compact">
              <div v-for="metric in resourceMetrics" :key="metric.key" class="resource-meter" :class="metric.tone">
                <div>
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.display }}</strong>
                </div>
                <i><b :style="{ width: `${metric.value}%` }" /></i>
              </div>
              <div class="uptime-meter">
                <span>运行时长</span>
                <strong>{{ uptimeText }}</strong>
              </div>
            </div>

            <div v-else class="inspector-facts">
              <div v-for="fact in inspectorNode.facts" :key="fact.label">
                <span>{{ fact.label }}</span>
                <strong>{{ fact.value }}</strong>
              </div>
            </div>
          </article>

          <article class="alert-locator">
            <header>
              <div>
                <span>告警定位节点</span>
                <strong>{{ issueCounts.total ? `${issueCounts.total} 项需要关注` : '当前无阻断告警' }}</strong>
              </div>
            </header>
            <div v-if="issueItems.length" class="alert-list">
              <button
                v-for="issue in visibleIssues"
                :key="issue.key"
                type="button"
                class="alert-node"
                :class="issue.tone"
                @click="locateIssue(issue)"
              >
                <span>{{ issue.levelLabel }}</span>
                <strong>{{ issue.title }}</strong>
                <em>{{ issue.impactAbility }}</em>
              </button>
            </div>
            <div v-else class="alert-empty">拓扑主链路保持连通</div>
          </article>
        </div>

        <article class="dependency-card">
          <header>
            <div>
              <span>依赖服务</span>
              <strong>{{ dependencyTitle }}</strong>
            </div>
            <span class="dependency-meta">自动刷新 {{ currentTimeText }}</span>
          </header>
          <div class="dependency-grid">
            <button
              v-for="service in visibleDependencyServices"
              :key="service.key"
              type="button"
              class="dependency-node"
              :class="service.tone"
              @click="inspectNode(service.nodeId)"
            >
              <span>{{ service.name }}</span>
              <strong>{{ service.statusText }}</strong>
              <small>{{ service.description }}</small>
            </button>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getSystemInfo } from '@/api/dashboard'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList, getModelStatus } from '@/api/camera'

const loading = ref(false)
const systemInfo = ref({})
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const modelStatus = ref({ loaded: false, models: {} })
const currentTime = ref(new Date())
const selectedNodeId = ref('edge-box')
const highlightedNodeId = ref('')
const highlightedEdgeIds = ref([])
const draggingNodeId = ref('')
const dragOffset = ref({ x: 0, y: 0 })
const resourceHistory = ref({
  cpu: [],
  memory: [],
  disk: [],
  gpu: [],
})
let clockTimer = null
let focusTimer = null

const zones = [
  { key: 'perception', label: '感知层', x: 34, y: 46, width: 205, height: 548 },
  { key: 'decision', label: '决策层', x: 276, y: 46, width: 226, height: 548 },
  { key: 'model', label: '模型层', x: 538, y: 46, width: 190, height: 548 },
  { key: 'analysis', label: '分析层', x: 762, y: 46, width: 220, height: 548 },
  { key: 'system', label: '系统层', x: 1018, y: 46, width: 180, height: 548 },
]

const topologyDefinition = [
  { id: 'camera', label: '摄像头', sublabel: '视频接入', x: 136, y: 142, width: 142, height: 76, description: '数据库中启用的视频源经后端签发票据进入实时视频链路。' },
  { id: 'sensor', label: '传感器', sublabel: '实时采集', x: 136, y: 318, width: 142, height: 76, description: '振动、雨量、风速、温湿度等传感器由采集服务汇入实时状态。' },
  { id: 'edge-box', label: '边缘盒子', sublabel: '现场汇聚', x: 136, y: 494, width: 142, height: 76, description: 'Jetson AGX 承载现场接入、资源调度与边缘侧运行环境。', pulse: true },
  { id: 'rule', label: '规则引擎', sublabel: '规则判断', x: 388, y: 142, width: 150, height: 82, description: 'ECA 规则引擎根据传感器、视觉和融合事件触发运行时动作。' },
  { id: 'edge-qwen', label: '边缘模型', sublabel: '千问小模型', x: 388, y: 318, width: 150, height: 82, description: '边缘侧多模态小模型用于现场快速筛选和轻量判断。' },
  { id: 'route', label: '智能路由', sublabel: '任务分发', x: 388, y: 494, width: 150, height: 82, description: '根据资源压力、模型可用性和事件类型选择本地、专有或云端分析链路。' },
  { id: 'vision-model', label: '专有模型', sublabel: '视觉推理', x: 633, y: 318, width: 150, height: 86, description: 'YOLO 检测 / 分类模型负责视频巡查中的专有视觉识别。' },
  { id: 'cloud-model', label: '云端模型', sublabel: '千问大模型', x: 872, y: 218, width: 150, height: 82, description: '云端千问多模态大模型提供更强语义理解和复杂场景判断。' },
  { id: 'scene-reasoning', label: '场景推理', sublabel: '综合研判', x: 872, y: 418, width: 150, height: 82, description: '汇聚规则、专有模型和云端模型结果，形成面向场景的安全研判。' },
  { id: 'broadcast', label: '广播联动', sublabel: '现场提醒', x: 1064, y: 160, width: 126, height: 70, description: '广播服务订阅安全事件动作并执行现场提醒。' },
  { id: 'drone', label: '无人机', sublabel: '巡查调度', x: 1152, y: 288, width: 126, height: 70, description: '无人机调度服务根据事件动作执行巡检派发。' },
  { id: 'staff', label: '人工任务', sublabel: '处置派发', x: 1064, y: 418, width: 126, height: 70, description: '人工任务服务承接高风险事件处置流转。' },
  { id: 'report', label: '报告归档', sublabel: '证据沉淀', x: 1152, y: 546, width: 126, height: 70, description: '巡查报告和事件证据进入文档与对象存储链路。' },
]

const edgeDefinition = [
  { id: 'camera-edge', from: 'camera', to: 'edge-box' },
  { id: 'sensor-edge', from: 'sensor', to: 'edge-box' },
  { id: 'edge-rule', from: 'edge-box', to: 'rule' },
  { id: 'edge-qwen', from: 'edge-box', to: 'edge-qwen' },
  { id: 'edge-route', from: 'edge-box', to: 'route' },
  { id: 'rule-route', from: 'rule', to: 'route' },
  { id: 'qwen-vision', from: 'edge-qwen', to: 'vision-model' },
  { id: 'route-vision', from: 'route', to: 'vision-model' },
  { id: 'vision-cloud', from: 'vision-model', to: 'cloud-model' },
  { id: 'vision-scene', from: 'vision-model', to: 'scene-reasoning' },
  { id: 'cloud-scene', from: 'cloud-model', to: 'scene-reasoning' },
  { id: 'scene-broadcast', from: 'scene-reasoning', to: 'broadcast' },
  { id: 'scene-drone', from: 'scene-reasoning', to: 'drone' },
  { id: 'scene-staff', from: 'scene-reasoning', to: 'staff' },
  { id: 'scene-report', from: 'scene-reasoning', to: 'report' },
]

const nodePositions = ref(Object.fromEntries(
  topologyDefinition.map((node) => [node.id, { x: node.x, y: node.y }]),
))

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

  if (!systemReachable.value && !['camera', 'sensor'].includes(id)) {
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
    'edge-box': {
      tone: resourceTone,
      text: resourceTone === 'ok' ? '资源平稳' : resourceTone === 'warn' ? '资源承压' : '资源临界',
    },
    rule: {
      tone: systemReachable.value ? 'ok' : 'danger',
      text: systemReachable.value ? '规则运行中' : '不可确认',
    },
    'edge-qwen': {
      tone: systemReachable.value ? 'ok' : 'warn',
      text: systemReachable.value ? '可参与路由' : '待确认',
    },
    route: {
      tone: worstTone([resourceTone, edgeModelReady.value ? 'ok' : 'warn', cloudModelReady.value ? 'ok' : 'warn']),
      text: systemReachable.value ? '路由可用' : '不可确认',
    },
    'vision-model': {
      tone: edgeModelReady.value ? 'ok' : 'danger',
      text: edgeModelReady.value ? '模型已加载' : '模型未确认',
    },
    'cloud-model': {
      tone: cloudModelReady.value ? 'ok' : 'warn',
      text: cloudModelReady.value ? '云端可达' : '云端不可达',
    },
    'scene-reasoning': {
      tone: edgeModelReady.value || cloudModelReady.value ? 'ok' : 'danger',
      text: edgeModelReady.value || cloudModelReady.value ? '研判可用' : '研判受阻',
    },
    broadcast: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可执行' : '阻断',
    },
    drone: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可调度' : '阻断',
    },
    staff: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可派发' : '阻断',
    },
    report: {
      tone: eventRuntimeReady.value ? 'ok' : 'blocked',
      text: eventRuntimeReady.value ? '可归档' : '阻断',
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
  const position = nodePositions.value[node.id] || { x: node.x, y: node.y }
  return {
    ...node,
    x: position.x,
    y: position.y,
    tone: status.tone,
    statusText: status.text,
    displayLabel: node.label,
    displaySubline: node.sublabel,
    facts: nodeFacts(node.id),
  }
}))

const topologyNodeMap = computed(() => Object.fromEntries(topologyNodes.value.map((node) => [node.id, node])))

function isEdgeBlocked(edge, from, to) {
  if (!systemReachable.value && !['camera-edge', 'sensor-edge'].includes(edge.id)) return true
  if (edge.id === 'camera-edge') return cameraSummary.value.total > 0 && cameraSummary.value.online === 0
  if (edge.id === 'sensor-edge') return !collectorRunning.value
  if (['qwen-vision', 'route-vision', 'vision-cloud', 'vision-scene'].includes(edge.id)) return !edgeModelReady.value
  if (edge.id === 'cloud-scene') return !cloudModelReady.value
  return from.tone === 'danger' || from.tone === 'blocked' || to.tone === 'danger' || to.tone === 'blocked'
}

const topologyEdges = computed(() => edgeDefinition.map((edge, index) => {
  const from = topologyNodeMap.value[edge.from]
  const to = topologyNodeMap.value[edge.to]
  const blocked = isEdgeBlocked(edge, from, to)
  const tone = blocked ? 'danger' : worstTone([from.tone, to.tone])
  const path = edgePath(from, to)
  const breakPoint = edgeBreakPoint(path)
  return {
    ...edge,
    path,
    tone,
    blocked,
    active: !blocked && tone !== 'neutral',
    duration: `${8 + (index % 4) * 1.3}s`,
    secondary: index % 2 === 0,
    secondaryDuration: `${11 + (index % 5) * 1.2}s`,
    breakX: breakPoint.x,
    breakY: breakPoint.y,
  }
}))

function edgePath(from, to) {
  const startX = from.x + from.width / 2
  const startY = from.y
  const endX = to.x - to.width / 2
  const endY = to.y
  const delta = Math.max(70, Math.abs(endX - startX) * 0.48)
  return `M${startX} ${startY} C${startX + delta} ${startY}, ${endX - delta} ${endY}, ${endX} ${endY}`
}

function edgeMarkerTone(tone) {
  if (tone === 'blocked') return 'danger'
  return ['ok', 'warn', 'danger'].includes(tone) ? tone : 'neutral'
}

function edgeBreakPoint(path) {
  if (!path) return { x: 0, y: 0 }
  const numbers = path.match(/-?\d+(\.\d+)?/g)?.map(Number) || []
  if (numbers.length < 4) return { x: 0, y: 0 }
  const pairs = []
  for (let index = 0; index < numbers.length; index += 2) {
    pairs.push({ x: numbers[index], y: numbers[index + 1] })
  }
  return pairs[Math.floor(pairs.length / 2)] || pairs[0]
}

const issueItems = computed(() => {
  if (!systemReachable.value) {
    return [{
      key: 'system-unreachable',
      title: '后端系统信息不可达',
      nodeId: 'edge-box',
      edgeIds: ['edge-rule', 'edge-qwen', 'edge-route'],
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
      edgeIds: ['sensor-edge', 'edge-rule', 'edge-route'],
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
      edgeIds: ['sensor-edge'],
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
      edgeIds: ['camera-edge', 'qwen-vision', 'route-vision'],
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
      nodeId: 'vision-model',
      edgeIds: ['qwen-vision', 'route-vision', 'vision-scene'],
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
      nodeId: 'cloud-model',
      edgeIds: ['vision-cloud', 'cloud-scene'],
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
      nodeId: 'edge-box',
      edgeIds: ['edge-qwen', 'edge-route'],
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
    rule: [
      { label: '规则引擎', value: systemReachable.value ? '运行中' : '待确认' },
      { label: '触发输入', value: '传感器 / 模型' },
    ],
    'edge-qwen': [
      { label: '模型类型', value: '千问小模型' },
      { label: '运行位置', value: '边缘侧' },
    ],
    route: [
      { label: '路由依据', value: '资源 / 模型 / 事件' },
      { label: '链路状态', value: systemReachable.value ? '可用' : '待确认' },
    ],
    'vision-model': [
      { label: '模型类型', value: '视觉推理' },
      { label: '加载状态', value: edgeModelReady.value ? '已加载' : '未确认' },
    ],
    'cloud-model': [
      { label: '模型类型', value: '千问大模型' },
      { label: '连接状态', value: aiModelLabel(systemInfo.value.ai_model) },
    ],
    'scene-reasoning': [
      { label: '输入来源', value: '规则 / 专有模型 / 云端模型' },
      { label: '研判状态', value: edgeModelReady.value || cloudModelReady.value ? '可用' : '受阻' },
    ],
    broadcast: [{ label: '动作类型', value: '广播联动' }, { label: '执行状态', value: eventRuntimeReady.value ? '可执行' : '阻断' }],
    drone: [{ label: '动作类型', value: '无人机巡查' }, { label: '执行状态', value: eventRuntimeReady.value ? '可调度' : '阻断' }],
    staff: [{ label: '动作类型', value: '人工处置' }, { label: '执行状态', value: eventRuntimeReady.value ? '可派发' : '阻断' }],
    report: [{ label: '动作类型', value: '报告归档' }, { label: '归档状态', value: eventRuntimeReady.value ? '可归档' : '阻断' }],
  }
  return facts[id] || []
}

const serviceItems = computed(() => [
  {
    key: 'backend',
    name: 'Python 后端',
    group: 'Core',
    status: systemReachable.value ? 'online' : 'offline',
    tone: systemReachable.value ? 'ok' : 'danger',
    nodeId: 'edge-box',
    description: 'FastAPI 运行状态与系统信息接口。',
  },
  {
    key: 'mysql',
    name: 'MySQL',
    group: 'Data',
    status: systemReachable.value ? 'online' : 'offline',
    tone: systemReachable.value ? 'ok' : 'danger',
    nodeId: 'route',
    description: '业务主库，后端可达时视为可用。',
  },
  {
    key: 'redis',
    name: 'Redis',
    group: 'Cache',
    status: systemReachable.value ? 'online' : 'unknown',
    tone: systemReachable.value ? 'ok' : 'neutral',
    nodeId: 'route',
    description: '缓存与短期队列，当前接口无独立健康字段。',
  },
  {
    key: 'sensor-collector',
    name: '采集器',
    group: 'Perception',
    status: collectorRunning.value ? 'online' : 'offline',
    tone: collectorRunning.value ? 'ok' : 'danger',
    nodeId: 'sensor',
    description: '现场传感器采集进程。',
  },
  {
    key: 'camera-runtime',
    name: '摄像头运行时',
    group: 'Perception',
    status: cameraSummary.value.online > 0 ? 'online' : 'degraded',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
    nodeId: 'camera',
    description: '摄像头连接与代理运行链路。',
  },
  {
    key: 'iotdb',
    name: 'IoTDB',
    group: 'Time Series',
    status: collectorRunning.value ? 'online' : 'degraded',
    tone: collectorRunning.value ? 'ok' : 'warn',
    nodeId: 'rule',
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
    nodeId: 'camera',
    description: 'RTSP 视频流转发。',
  },
  {
    key: 'webrtc',
    name: 'WebRTC',
    group: 'Video',
    status: cameraSummary.value.online > 0 ? 'online' : 'degraded',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
    nodeId: 'camera',
    description: '浏览器实时视频播放信令。',
  },
  {
    key: 'eca',
    name: 'ECA 规则引擎',
    group: 'Decision',
    status: systemReachable.value ? 'online' : 'offline',
    tone: systemReachable.value ? 'ok' : 'danger',
    nodeId: 'rule',
    description: '规则调度与安全事件触发。',
  },
  {
    key: 'smart-route',
    name: '智能路由服务',
    group: 'Decision',
    status: systemReachable.value ? 'online' : 'unknown',
    tone: systemReachable.value ? 'ok' : 'neutral',
    nodeId: 'route',
    description: '按资源、模型和事件选择推理链路。',
  },
  {
    key: 'qwen-edge',
    name: '边缘千问小模型',
    group: 'AI',
    status: systemReachable.value ? 'configured' : 'unknown',
    tone: systemReachable.value ? 'neutral' : 'danger',
    nodeId: 'edge-qwen',
    description: '边缘侧多模态轻量研判能力。',
  },
  {
    key: 'qwen',
    name: '云端千问大模型',
    group: 'AI',
    status: cloudModelReady.value ? 'online' : 'offline',
    tone: cloudModelReady.value ? 'ok' : 'danger',
    nodeId: 'cloud-model',
    description: '多模态语义分析服务。',
  },
  {
    key: 'yolo',
    name: 'YOLO Detector',
    group: 'AI',
    status: edgeModelReady.value ? 'loaded' : 'offline',
    tone: edgeModelReady.value ? 'ok' : 'danger',
    nodeId: 'vision-model',
    description: '边缘目标检测 / 分类模型。',
  },
  {
    key: 'model-library',
    name: '模型库',
    group: 'AI',
    status: systemReachable.value ? 'configured' : 'unknown',
    tone: systemReachable.value ? 'neutral' : 'danger',
    nodeId: 'vision-model',
    description: '模型资产、模板和调用配置。',
  },
  {
    key: 'dam-workflow',
    name: '工作流服务',
    group: 'Analysis',
    status: systemReachable.value ? 'configured' : 'unknown',
    tone: systemReachable.value ? 'neutral' : 'danger',
    nodeId: 'scene-reasoning',
    description: '场景分析与综合研判流程。',
  },
  {
    key: 'safety-event',
    name: '安全事件总线',
    group: 'Runtime',
    status: eventRuntimeReady.value ? 'online' : 'offline',
    tone: eventRuntimeReady.value ? 'ok' : 'danger',
    nodeId: 'scene-reasoning',
    description: '安全事件分发与动作订阅。',
  },
  {
    key: 'broadcast',
    name: '广播联动',
    group: 'Action',
    status: eventRuntimeReady.value ? 'online' : 'unknown',
    tone: eventRuntimeReady.value ? 'ok' : 'neutral',
    nodeId: 'broadcast',
    description: '现场广播提醒动作。',
  },
  {
    key: 'drone-dispatch',
    name: '无人机调度',
    group: 'Action',
    status: eventRuntimeReady.value ? 'configured' : 'unknown',
    tone: eventRuntimeReady.value ? 'neutral' : 'danger',
    nodeId: 'drone',
    description: '无人机巡查任务派发。',
  },
  {
    key: 'staff-task',
    name: '人工任务服务',
    group: 'Action',
    status: eventRuntimeReady.value ? 'online' : 'unknown',
    tone: eventRuntimeReady.value ? 'ok' : 'neutral',
    nodeId: 'staff',
    description: '人工处置任务流转。',
  },
  {
    key: 'patrol-report',
    name: '巡查报告',
    group: 'Document',
    status: systemReachable.value ? 'online' : 'unknown',
    tone: systemReachable.value ? 'ok' : 'neutral',
    nodeId: 'report',
    description: '报告生成、归档与证据沉淀。',
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
  {
    key: 'wechat',
    name: '微信订阅',
    group: 'Action',
    status: eventRuntimeReady.value ? 'configured' : 'unknown',
    tone: eventRuntimeReady.value ? 'neutral' : 'danger',
    nodeId: 'staff',
    description: '小程序与订阅消息联动。',
  },
])

const visibleDependencyServices = computed(() => serviceItems.value
  .map((service) => ({
    ...service,
    statusText: serviceStatusText(service.status, service.tone),
  }))
  .sort((first, second) => dependencyToneRank(first.tone) - dependencyToneRank(second.tone)))

const dependencyTitle = computed(() => {
  const offline = visibleDependencyServices.value.filter((service) => service.tone === 'danger').length
  const degraded = visibleDependencyServices.value.filter((service) => service.tone === 'warn').length
  if (offline) return `${offline} 项不可用`
  if (degraded) return `${degraded} 项降级`
  return '核心依赖正常'
})

function serviceStatusText(status, tone) {
  if (tone === 'danger') return '不可用'
  if (tone === 'warn') return '降级'
  if (status === 'loaded') return '已加载'
  if (status === 'configured') return '已配置'
  if (status === 'on demand') return '按需'
  if (status === 'online') return '在线'
  return '待确认'
}

function dependencyToneRank(tone) {
  return ({ danger: 0, warn: 1, neutral: 2, ok: 3 })[tone] ?? 2
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

function startNodeDrag(event, nodeId) {
  inspectNode(nodeId)
  draggingNodeId.value = nodeId
  const point = svgPoint(event)
  const current = nodePositions.value[nodeId] || { x: 0, y: 0 }
  dragOffset.value = {
    x: point.x - current.x,
    y: point.y - current.y,
  }
}

function onNodeDrag(event) {
  if (!draggingNodeId.value) return
  const point = svgPoint(event)
  const node = topologyDefinition.find((item) => item.id === draggingNodeId.value)
  if (!node) return
  nodePositions.value = {
    ...nodePositions.value,
    [draggingNodeId.value]: {
      x: Math.max(70, Math.min(1160, point.x - dragOffset.value.x)),
      y: Math.max(86, Math.min(582, point.y - dragOffset.value.y)),
    },
  }
}

function stopNodeDrag() {
  draggingNodeId.value = ''
}

function svgPoint(event) {
  const svg = event.currentTarget.closest?.('svg') || event.currentTarget
  const point = svg.createSVGPoint()
  point.x = event.clientX
  point.y = event.clientY
  const matrix = svg.getScreenCTM()
  return matrix ? point.matrixTransform(matrix.inverse()) : { x: point.x, y: point.y }
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
  padding: 14px;
  color: #e8f1f5;
  background:
    radial-gradient(circle at 28% 12%, rgba(57, 138, 157, 0.15), transparent 36%),
    linear-gradient(180deg, #0b1620 0%, #0a141d 50%, #081119 100%);
}

.runtime-monitor-page,
.runtime-monitor-page * {
  box-sizing: border-box;
}

.node-inspector span,
.resource-meter span,
.uptime-meter span,
.alert-locator span,
.alert-node span,
.dependency-card span,
.dependency-node span {
  margin: 0;
  color: #7f95a3;
  font-size: 12px;
}

.runtime-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
}

.topology-stage {
  border: 1px solid rgba(115, 190, 206, 0.16);
  background: rgba(11, 26, 37, 0.88);
  box-shadow: 0 18px 40px rgba(0, 8, 16, 0.24);
}

.topology-stage {
  padding: 12px;
  border-radius: 10px;
}

.topology-canvas {
  position: relative;
  min-height: 720px;
  margin-top: 0;
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
  height: min(74vh, 780px);
  min-height: 690px;
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
  cursor: grab;
  outline: none;
}

.runtime-node:active {
  cursor: grabbing;
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
  font-size: 16px;
  font-weight: 650;
}

.node-status {
  fill: #7f95a3;
  font-size: 12px;
}

.runtime-node.ok .node-status { fill: #79ddc5; }
.runtime-node.warn .node-status { fill: #dfb863; }
.runtime-node.danger .node-status,
.runtime-node.blocked .node-status { fill: #ef7e8a; }

.node-pulse {
  fill: rgba(105, 215, 189, 0.08);
  stroke: rgba(105, 215, 189, 0.22);
  transform-box: fill-box;
  transform-origin: center;
  animation: nodePulse 4.8s ease-in-out infinite;
}

.runtime-node.danger .node-pulse,
.runtime-node.blocked .node-pulse {
  fill: rgba(239, 126, 138, 0.08);
  stroke: rgba(239, 126, 138, 0.22);
}

.runtime-detail-row {
  display: grid;
  grid-template-columns: minmax(560px, 1.15fr) minmax(360px, 0.85fr);
  gap: 12px;
  margin-top: 10px;
}

.node-inspector,
.alert-locator,
.dependency-card {
  min-height: 118px;
  padding: 13px;
  border: 1px solid rgba(115, 190, 206, 0.14);
  border-radius: 8px;
  background: rgba(8, 20, 30, 0.58);
}

.inspector-head {
  display: grid;
  grid-template-columns: 148px minmax(0, 1fr);
  align-items: start;
  gap: 14px;
  min-width: 0;
}

.inspector-head strong {
  display: block;
  margin-top: 4px;
  color: #f2f7f8;
  font-size: 15px;
}

.node-inspector p {
  margin: 0;
  color: #9badb8;
  font-size: 12px;
  line-height: 1.5;
}

.resource-compact {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr)) 92px;
  gap: 10px;
  align-items: end;
  margin-top: 12px;
}

.resource-meter {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.resource-meter div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.resource-meter strong,
.uptime-meter strong {
  color: #eaf4f5;
  font-size: 12px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.resource-meter i {
  display: block;
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.055);
}

.resource-meter b {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: rgba(105, 215, 189, 0.86);
}

.resource-meter.warn b { background: rgba(223, 184, 99, 0.9); }
.resource-meter.danger b { background: rgba(239, 126, 138, 0.92); }
.resource-meter.neutral b { background: rgba(111, 130, 146, 0.74); }
.resource-meter.warn strong { color: #dfb863; }
.resource-meter.danger strong { color: #ef7e8a; }

.uptime-meter {
  display: grid;
  gap: 5px;
  justify-items: end;
}

.inspector-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
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

.alert-locator header,
.dependency-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 11px;
}

.alert-locator header strong,
.dependency-card header strong {
  display: block;
  margin-top: 4px;
  color: #f2f7f8;
  font-size: 15px;
}

.alert-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.alert-node {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 5px 9px;
  align-items: center;
  min-height: 46px;
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-left: 2px solid rgba(111, 130, 146, 0.74);
  border-radius: 7px;
  padding: 7px 9px;
  background: rgba(255, 255, 255, 0.032);
  text-align: left;
  cursor: pointer;
}

.alert-node.warn {
  border-left-color: #dfb863;
}

.alert-node.danger {
  border-left-color: #ef7e8a;
  background: rgba(70, 25, 34, 0.16);
}

.alert-node span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.alert-node.warn span { color: #dfb863; }
.alert-node.danger span { color: #ef7e8a; }

.alert-node strong {
  overflow: hidden;
  color: #f2f7f8;
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-node em {
  grid-column: 2;
  overflow: hidden;
  color: #8fa0aa;
  font-size: 11px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-empty {
  min-height: 58px;
  display: grid;
  place-items: center;
  border: 1px dashed rgba(105, 215, 189, 0.2);
  border-radius: 7px;
  color: #9badb8;
  font-size: 12px;
}

.dependency-card {
  margin-top: 12px;
}

.dependency-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));
  gap: 8px;
}

.dependency-node {
  min-width: 0;
  min-height: 68px;
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-radius: 7px;
  padding: 7px 9px;
  background: rgba(255, 255, 255, 0.035);
  text-align: left;
  cursor: pointer;
}

.dependency-node strong {
  display: block;
  margin-top: 4px;
  color: #69d7bd;
  font-size: 12px;
  font-weight: 650;
}

.dependency-node small {
  display: block;
  margin-top: 6px;
  overflow: hidden;
  color: #8fa0aa;
  font-size: 11px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dependency-node.warn {
  border-color: rgba(223, 184, 99, 0.34);
}

.dependency-node.warn strong {
  color: #dfb863;
}

.dependency-node.danger {
  border-color: rgba(239, 126, 138, 0.38);
  background: rgba(70, 25, 34, 0.16);
}

.dependency-node.danger strong {
  color: #ef7e8a;
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
  .runtime-svg {
    height: min(72vh, 740px);
    min-height: 650px;
  }

  .topology-canvas {
    min-height: 680px;
  }
}

@media (max-width: 1480px) {
  .runtime-monitor-page {
    padding: 12px;
  }

  .runtime-svg {
    height: min(70vh, 700px);
    min-height: 610px;
  }

  .topology-canvas {
    min-height: 640px;
  }

  .node-inspector {
    gap: 10px;
  }

  .resource-compact {
    grid-template-columns: repeat(5, minmax(92px, 1fr));
  }
}

@media (max-width: 1180px) {
  .runtime-detail-row,
  .inspector-head,
  .resource-compact,
  .inspector-facts {
    grid-template-columns: 1fr;
  }

  .runtime-svg {
    min-height: 500px;
  }

  .topology-canvas {
    min-height: 530px;
  }

  .dependency-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alert-list {
    grid-template-columns: 1fr;
  }
}
</style>
