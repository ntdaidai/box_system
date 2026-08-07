<template>
  <div class="system-monitor-page">
    <header class="page-head">
      <div>
        <p>系统监测</p>
        <h2>关键设备与运行链路</h2>
      </div>
      <div class="head-actions">
        <span>自动刷新 · {{ currentTimeText }}</span>
        <el-button :icon="Refresh" :loading="loading" class="refresh-btn" @click="loadAll">刷新</el-button>
      </div>
    </header>

    <main class="system-grid">
      <section class="panel health-panel">
        <header class="panel-head">
          <div>
            <span>系统健康摘要</span>
            <h3>3 秒内看懂系统是否正常</h3>
          </div>
          <div class="panel-meta">{{ issueCounts.total }} 项待处理</div>
        </header>

        <div class="health-layout">
          <div class="health-core">
            <div class="score-block">
              <div class="score-value" :class="healthTone">{{ healthScore }}</div>
              <div class="score-copy">
                <div class="score-label">{{ healthLabel }}</div>
                <div class="score-issue">{{ primaryIssue.title }}</div>
                <p class="score-impact">{{ primaryIssue.impact }}</p>
              </div>
            </div>

            <div class="health-meta">
              <div class="meta-box">
                <span>异常</span>
                <strong>{{ issueCounts.total }}</strong>
              </div>
              <div class="meta-box">
                <span>严重</span>
                <strong>{{ issueCounts.danger }}</strong>
              </div>
              <div class="meta-box">
                <span>AI 服务</span>
                <strong>{{ aiModelLabel(systemInfo.ai_model) }}</strong>
              </div>
            </div>
          </div>

          <div class="health-side">
            <div class="side-block primary">
              <span>当前最严重问题</span>
              <strong>{{ primaryIssue.current }}</strong>
              <small>{{ primaryIssue.action }}</small>
            </div>

            <div class="side-grid">
              <div>
                <span>采集器</span>
                <strong>{{ collectorRunning ? '运行中' : '待确认' }}</strong>
              </div>
              <div>
                <span>资源压力</span>
                <strong>{{ resourceCriticalCount }} 项临界</strong>
              </div>
            </div>

            <div class="side-block">
              <span>建议优先处理</span>
              <strong>{{ firstAction.title }}</strong>
              <small>{{ firstAction.action }}</small>
            </div>
          </div>
        </div>
      </section>

      <section class="panel pipeline-panel">
        <header class="panel-head">
          <div>
            <span>运行链路</span>
            <h3>感知采集 → 边缘推理 → 云端协同 → 事件处理</h3>
          </div>
          <div class="panel-meta">{{ pipelineOkCount }}/4 正常</div>
        </header>

        <div class="pipeline-rail">
          <article
            v-for="(step, index) in runtimeSteps"
            :key="step.title"
            class="pipeline-step"
            :class="step.tone"
          >
            <div class="step-index">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="step-icon">
              <el-icon><component :is="step.icon" /></el-icon>
            </div>
            <div class="step-name">{{ step.title }}</div>
            <div class="step-state">{{ step.state }}</div>
            <div class="step-note">{{ step.note }}</div>
          </article>
        </div>
      </section>

      <section class="monitor-grid">
        <section class="panel resource-panel">
          <header class="panel-head">
            <div>
              <span>资源监控</span>
              <h3>{{ resourceHeadline }}</h3>
            </div>
            <div class="panel-meta">GPU / 内存 / 磁盘 / CPU</div>
          </header>

          <div class="resource-list">
            <el-tooltip
              v-for="metric in resourceMetrics"
              :key="metric.key"
              placement="right"
              :show-after="200"
            >
              <template #content>
                <div class="metric-tip">
                  <div>{{ metric.tipTitle }}</div>
                  <div>{{ metric.detail }}</div>
                  <div v-if="metric.extra">{{ metric.extra }}</div>
                </div>
              </template>

              <div class="resource-row" :class="metric.tone">
                <div class="resource-head">
                  <span>{{ metric.label }}</span>
                  <strong>{{ metric.percent }}%</strong>
                </div>
                <div class="resource-bar">
                  <i :style="{ width: `${metric.percent}%` }" />
                </div>
                <div class="resource-foot">{{ metric.detail }}</div>
              </div>
            </el-tooltip>
          </div>
        </section>

        <section class="panel action-panel">
          <header class="panel-head">
            <div>
              <span>待处理事项</span>
              <h3>{{ issueCounts.total }} 项需要关注</h3>
            </div>
            <div class="panel-meta">
              <span v-if="issueCounts.danger">{{ issueCounts.danger }} 项严重</span>
              <span v-else>{{ issueCounts.warn }} 项警告</span>
            </div>
          </header>

          <div v-if="issueItems.length" class="issue-list">
            <article
              v-for="issue in visibleIssues"
              :key="issue.key"
              class="issue-row"
              :class="issue.tone"
            >
              <div class="issue-strip" />
              <div class="issue-main">
                <div class="issue-top">
                  <strong>{{ issue.title }}</strong>
                  <span class="issue-level">{{ issue.levelLabel }}</span>
                </div>
                <div class="issue-current">{{ issue.current }}</div>
                <div class="issue-impact">{{ issue.impact }}</div>
                <div class="issue-action">{{ issue.action }}</div>
              </div>
              <div class="issue-buttons">
                <button type="button" class="text-action" @click="openIssue(issue)">
                  <el-icon><View /></el-icon>
                  查看详情
                </button>
                <button type="button" class="text-action handle" @click="processIssue(issue)">
                  <el-icon><ArrowRight /></el-icon>
                  处理
                </button>
              </div>
            </article>

            <button
              v-if="issueItems.length > visibleIssueLimit"
              type="button"
              class="more-issues"
              @click="openIssue(issueItems[visibleIssueLimit])"
            >
              还有 {{ issueItems.length - visibleIssueLimit }} 项更轻问题
            </button>
          </div>

          <div v-else class="empty-state">
            <div>
              <el-icon><CircleCheck /></el-icon>
              <strong>当前没有待处理事项</strong>
              <span>关键链路保持正常，继续观察即可。</span>
            </div>
          </div>
        </section>
      </section>

      <section class="panel service-panel">
        <header class="panel-head">
          <div>
            <span>系统服务</span>
            <h3>{{ serviceAttentionItems.length }} 项需要关注</h3>
          </div>
          <button type="button" class="text-action toggle-action" @click="showAllServices = !showAllServices">
            <el-icon><component :is="showAllServices ? ArrowDown : ArrowRight" /></el-icon>
            {{ showAllServices ? '收起全部' : '展开全部' }}
          </button>
        </header>

        <div v-if="serviceAttentionItems.length" class="service-focus-list">
          <article
            v-for="service in serviceAttentionItems"
            :key="`${service.group}-${service.name}`"
            class="service-item"
            :class="service.tone"
          >
            <div class="service-strip" />
            <div class="service-content">
              <div class="service-top">
                <strong>{{ service.name }}</strong>
                <span class="service-state">{{ service.status }}</span>
              </div>
              <small>{{ service.description }}</small>
            </div>
          </article>
        </div>

        <div v-if="!showAllServices && serviceQuietItems.length" class="service-quiet">
          稳定服务 {{ serviceQuietItems.length }} 项
        </div>

        <transition name="fade">
          <div v-if="showAllServices" class="service-expanded">
            <article v-for="group in serviceGroups" :key="group.title" class="service-group">
              <h4>{{ group.title }}</h4>
              <div v-for="service in group.items" :key="service.name" class="service-group-row">
                <span>{{ service.name }}</span>
                <strong>{{ service.status }}</strong>
              </div>
            </article>
          </div>
        </transition>
      </section>
    </main>

    <el-drawer v-model="issueDrawerVisible" :with-header="false" size="420px" class="issue-drawer">
      <div v-if="drawerIssue.key" class="drawer-body">
        <div class="drawer-head">
          <div>
            <span>{{ drawerIssue.group }}</span>
            <h3>{{ drawerIssue.title }}</h3>
          </div>
          <div class="drawer-level" :class="drawerIssue.tone">{{ drawerIssue.levelLabel }}</div>
        </div>

        <div class="drawer-block">
          <span>当前值</span>
          <strong>{{ drawerIssue.current }}</strong>
        </div>
        <div class="drawer-block">
          <span>影响</span>
          <strong>{{ drawerIssue.impact }}</strong>
        </div>
        <div class="drawer-block">
          <span>建议操作</span>
          <strong>{{ drawerIssue.action }}</strong>
        </div>

        <div class="drawer-actions">
          <button
            v-if="drawerIssue.route"
            type="button"
            class="drawer-action primary"
            @click="goToRelatedModule"
          >
            <el-icon><ArrowRight /></el-icon>
            前往相关模块
          </button>
          <button type="button" class="drawer-action" @click="issueDrawerVisible = false">关闭</button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowDown,
  ArrowRight,
  CircleCheck,
  Cloudy,
  Connection,
  Cpu,
  Monitor,
  Operation,
  Refresh,
  View,
  VideoCamera,
} from '@element-plus/icons-vue'
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
const showAllServices = ref(false)
const issueDrawerVisible = ref(false)
const selectedIssue = ref({})
let clockTimer = null

const currentTimeText = computed(() => currentTime.value.toLocaleTimeString('zh-CN', {
  hour12: false,
  hour: '2-digit',
  minute: '2-digit',
}))

const systemReachable = computed(() => Object.keys(systemInfo.value || {}).length > 0)
const collectorRunning = computed(() => Boolean(systemInfo.value.sensor_collector_running))
const sensorsOnline = computed(() => {
  const values = Object.values(deviceStatus.value || {})
  return values.filter((item) => item?.status === 'online').length
})
const sensorsTotal = computed(() => Object.keys(deviceStatus.value || {}).length)
const edgeModelReady = computed(() => Boolean(
  modelStatus.value.loaded || Object.values(modelStatus.value.models || {}).some((item) => item?.loaded),
))
const cloudModelReady = computed(() => systemInfo.value.ai_model === 'healthy')

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

function riskTone(percentValue) {
  if (percentValue >= 85) return 'danger'
  if (percentValue >= 70) return 'warn'
  return 'ok'
}

function severityLabel(tone) {
  return ({ danger: '严重', warn: '警告', ok: '正常' })[tone] || '关注'
}

const resourceMetrics = computed(() => {
  const gpu = systemInfo.value.gpu || {}
  const gpuMemory = gpu.memory || {}

  const items = [
    {
      key: 'cpu',
      label: 'CPU',
      percent: percent(systemInfo.value.cpu_percent),
      detail: `负载 ${formatNumber(systemInfo.value.cpu_percent)}%`,
      extra: '',
      tipTitle: 'CPU 使用率',
    },
    {
      key: 'memory',
      label: '内存',
      percent: percent(systemInfo.value.memory?.percent),
      detail: `${formatNumber(systemInfo.value.memory?.used_gb)} / ${formatNumber(systemInfo.value.memory?.total_gb)} GB`,
      extra: '',
      tipTitle: '内存占用',
    },
    {
      key: 'disk',
      label: '磁盘',
      percent: percent(systemInfo.value.disk?.percent),
      detail: `${formatNumber(systemInfo.value.disk?.used_gb)} / ${formatNumber(systemInfo.value.disk?.total_gb)} GB`,
      extra: '',
      tipTitle: '磁盘占用',
    },
    {
      key: 'gpu',
      label: 'GPU',
      percent: percent(gpu.utilization_percent ?? gpuMemory.percent),
      detail: gpuDetail.value,
      extra: gpuMemory.total_mb
        ? `显存 ${formatNumber(gpuMemory.used_mb / 1024)} / ${formatNumber(gpuMemory.total_mb / 1024)} GB`
        : '',
      tipTitle: 'GPU 运行态',
    },
  ]

  return items.map((metric) => ({
    ...metric,
    tone: systemReachable.value ? riskTone(metric.percent) : 'neutral',
  }))
})

const gpuDetail = computed(() => {
  const gpu = systemInfo.value.gpu || {}
  const parts = []
  if (gpu.utilization_percent != null) parts.push(`利用率 ${formatNumber(gpu.utilization_percent)}%`)
  if (gpu.temperature_c != null) parts.push(`${formatNumber(gpu.temperature_c)}°C`)
  if (gpu.power_w != null) parts.push(`${formatNumber(gpu.power_w)}W`)
  return parts.join(' · ') || (gpu.available ? 'GPU 已检测' : 'GPU 信息待确认')
})

const resourceCriticalCount = computed(() => resourceMetrics.value.filter((metric) => metric.tone !== 'ok' && metric.tone !== 'neutral').length)
const resourceHeadline = computed(() => {
  if (!systemReachable.value) return '系统信息待确认'
  if (!resourceCriticalCount.value) return '资源状态平稳'
  return `${resourceCriticalCount.value} 项临界`
})

const issueItems = computed(() => {
  if (!systemReachable.value) {
    return [{
      key: 'system-unreachable',
      title: '系统信息不可达',
      group: '系统接口',
      current: '未返回 /v1/system/info',
      impact: '健康摘要、资源监控和状态判断无法刷新。',
      action: '先确认后端服务与网络连通性。',
      tone: 'danger',
      levelLabel: '严重',
      route: null,
    }]
  }

  const items = []

  if (!collectorRunning.value) {
    items.push({
      key: 'collector',
      title: '采集服务待确认',
      group: '感知采集',
      current: 'sensor_collector 未运行',
      impact: '实时传感器数据可能中断。',
      action: '先确认采集器进程与串口链路。',
      tone: 'danger',
      levelLabel: '严重',
      route: '/monitor/sensors',
    })
  }

  if (sensorsTotal.value > 0 && sensorsOnline.value < sensorsTotal.value) {
    items.push({
      key: 'sensors-offline',
      title: '感知设备离线',
      group: '感知采集',
      current: `${sensorsOnline.value}/${sensorsTotal.value} 设备在线`,
      impact: '缺失的传感器会削弱告警判断。',
      action: '先核对离线设备和采集链路。',
      tone: 'warn',
      levelLabel: '警告',
      route: '/monitor/sensors',
    })
  }

  if (cameraSummary.value.total > 0 && cameraSummary.value.online < cameraSummary.value.total) {
    items.push({
      key: 'camera-offline',
      title: '视频通道不完整',
      group: '视频监测',
      current: `${cameraSummary.value.online}/${cameraSummary.value.total} 路在线`,
      impact: '视频联动和取证能力会受影响。',
      action: '先查看摄像头接入与推流状态。',
      tone: 'warn',
      levelLabel: '警告',
      route: '/monitor/camera',
    })
  }

  if (!edgeModelReady.value) {
    items.push({
      key: 'edge-model',
      title: '边缘视觉模型待确认',
      group: 'AI 协同',
      current: '本地视觉模型不可用',
      impact: '摄像头目标检测能力可能受限。',
      action: '先前往模型管理确认边缘模型。',
      tone: 'danger',
      levelLabel: '严重',
      route: '/system/models',
    })
  }

  if (!cloudModelReady.value) {
    items.push({
      key: 'cloud-model',
      title: '云边大模型不可达',
      group: 'AI 协同',
      current: `当前状态：${aiModelLabel(systemInfo.value.ai_model)}`,
      impact: '语义分析和辅助研判链路受影响。',
      action: '先检查云侧模型服务和网络。',
      tone: 'warn',
      levelLabel: '警告',
      route: '/system/models',
    })
  }

  for (const metric of resourceMetrics.value) {
    if (metric.tone === 'warn' || metric.tone === 'danger') {
      items.push({
        key: `resource-${metric.key}`,
        title: `${metric.label} 使用率偏高`,
        group: '资源监控',
        current: metric.detail,
        impact: '高占用会放大页面和推理时延。',
        action: '先处理高占用资源。',
        tone: metric.tone,
        levelLabel: severityLabel(metric.tone),
        route: null,
      })
    }
  }

  return items
})

const visibleIssueLimit = 4
const visibleIssues = computed(() => issueItems.value.slice(0, visibleIssueLimit))
const firstAction = computed(() => issueItems.value[0] || {
  key: 'nominal',
  title: '当前状态正常',
  current: '暂无异常项',
  impact: '关键链路保持稳定，继续观察即可。',
  action: '保持自动刷新并关注资源趋势。',
  tone: 'ok',
  levelLabel: '正常',
  route: null,
})

const issueCounts = computed(() => issueItems.value.reduce((acc, item) => {
  acc.total += 1
  if (item.tone === 'danger') acc.danger += 1
  else if (item.tone === 'warn') acc.warn += 1
  return acc
}, { total: 0, danger: 0, warn: 0 }))

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

const healthLabel = computed(() => {
  if (!systemReachable.value) return '系统待确认'
  if (healthTone.value === 'danger') return '需要优先处理'
  if (healthTone.value === 'warn') return '需要关注'
  return '运行稳定'
})

const runtimeSteps = computed(() => ([
  {
    title: '感知采集',
    state: collectorRunning.value ? '正常' : '待确认',
    note: sensorsTotal.value > 0
      ? `${sensorsOnline.value}/${sensorsTotal.value} 设备在线`
      : '传感器状态未返回',
    tone: collectorRunning.value && sensorsOnline.value > 0 ? 'ok' : 'warn',
    icon: Monitor,
  },
  {
    title: '边缘推理',
    state: edgeModelReady.value ? '可用' : '待确认',
    note: edgeModelReady.value ? '本地视觉模型在线' : '本地模型能力不可用',
    tone: edgeModelReady.value ? 'ok' : 'danger',
    icon: Cpu,
  },
  {
    title: '云端协同',
    state: cloudModelReady.value ? '可达' : '不可达',
    note: `AI 服务：${aiModelLabel(systemInfo.value.ai_model)}`,
    tone: cloudModelReady.value ? 'ok' : 'warn',
    icon: Cloudy,
  },
  {
    title: '事件处理',
    state: systemReachable.value ? '联通' : '待确认',
    note: systemReachable.value ? '规则编排与联动动作可执行' : '后端系统信息待确认',
    tone: systemReachable.value ? 'ok' : 'warn',
    icon: Operation,
  },
]))

const pipelineOkCount = computed(() => runtimeSteps.value.filter((step) => step.tone === 'ok').length)

const serviceGroups = computed(() => [
  {
    title: '感知与基础服务',
    items: [
      { name: 'EMQX', status: collectorRunning.value ? '正常' : '待确认', tone: collectorRunning.value ? 'ok' : 'warn', description: '传感器消息接入通道。' },
      { name: 'IoTDB', status: systemReachable.value ? '已配置' : '待确认', tone: systemReachable.value ? 'ok' : 'warn', description: '时序数据存储。' },
      { name: 'MediaMTX', status: cameraSummary.value.total > 0 ? '已接入' : '待配置', tone: cameraSummary.value.total > 0 ? 'ok' : 'warn', description: '视频流转发。' },
      { name: 'WebRTC Streamer', status: cameraSummary.value.total > 0 ? '已接入' : '待配置', tone: cameraSummary.value.total > 0 ? 'ok' : 'warn', description: '浏览器实时播放。' },
    ],
  },
  {
    title: '平台数据服务',
    items: [
      { name: 'MySQL', status: systemReachable.value ? '正常' : '待确认', tone: systemReachable.value ? 'ok' : 'warn', description: '业务主库。' },
      { name: 'Redis', status: systemReachable.value ? '正常' : '待确认', tone: systemReachable.value ? 'ok' : 'warn', description: '缓存与短期队列。' },
      { name: 'MinIO', status: systemReachable.value ? '已配置' : '待确认', tone: systemReachable.value ? 'ok' : 'warn', description: '截图与证据文件。' },
      { name: 'OnlyOffice', status: '按需', tone: 'neutral', description: '文档预览与编辑。' },
    ],
  },
  {
    title: 'AI 与业务协同',
    items: [
      { name: '边缘视觉推理', status: edgeModelReady.value ? '正常' : '待确认', tone: edgeModelReady.value ? 'ok' : 'warn', description: '本地检测能力。' },
      { name: '云边大模型', status: cloudModelReady.value ? '正常' : '不可达', tone: cloudModelReady.value ? 'ok' : 'warn', description: '多模态理解。' },
      { name: '工作流执行服务', status: systemReachable.value ? '已配置' : '待确认', tone: systemReachable.value ? 'ok' : 'warn', description: '规则编排与动作。' },
      { name: '模型库服务', status: '模型管理查看', tone: 'neutral', description: '模型版本与状态。' },
    ],
  },
])

const serviceFlatItems = computed(() => serviceGroups.value.flatMap((group) => group.items.map((item) => ({
  ...item,
  group: group.title,
}))))

const serviceAttentionItems = computed(() => serviceFlatItems.value.filter((item) => item.tone === 'warn' || item.tone === 'danger'))
const serviceQuietItems = computed(() => serviceFlatItems.value.filter((item) => item.tone === 'ok' || item.tone === 'neutral'))

const drawerIssue = computed(() => selectedIssue.value || {})

function openIssue(issue) {
  selectedIssue.value = { ...issue }
  issueDrawerVisible.value = true
}

function processIssue(issue) {
  if (issue.route) {
    router.push(issue.route)
    return
  }
  openIssue(issue)
}

function goToRelatedModule() {
  if (drawerIssue.value.route) router.push(drawerIssue.value.route)
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
      getModelStatus(),
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
})
</script>

<style scoped>
.system-monitor-page {
  min-height: 100%;
  padding: 18px;
  color: #d8e1e8;
  background: linear-gradient(180deg, #091018 0%, #0b121a 100%);
}

.system-monitor-page,
.system-monitor-page * {
  box-sizing: border-box;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.page-head p {
  margin: 0 0 4px;
  color: #7f8b95;
  font-size: 12px;
}

.page-head h2 {
  margin: 0;
  color: #f3f7fa;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #93a0aa;
  font-size: 12px;
}

.refresh-btn {
  border-radius: 12px;
}

.system-grid {
  display: grid;
  gap: 12px;
}

.panel {
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  background: rgba(13, 19, 27, 0.94);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head span {
  color: #7f8b95;
  font-size: 12px;
}

.panel-head h3 {
  margin: 4px 0 0;
  color: #f3f7fa;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0;
}

.panel-meta {
  color: #95a2ac;
  font-size: 12px;
  white-space: nowrap;
}

.health-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
  gap: 12px;
}

.health-core,
.health-side,
.pipeline-step,
.resource-row,
.issue-row,
.service-item,
.service-group,
.service-quiet {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.health-core {
  padding: 16px;
}

.score-block {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.score-value {
  min-width: 84px;
  color: #edf4f6;
  font-size: 32px;
  font-weight: 600;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.score-value.ok { color: #7ce1c0; }
.score-value.warn { color: #e2be73; }
.score-value.danger { color: #ef8690; }

.score-label {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: #b6c0c7;
  font-size: 12px;
}

.score-issue {
  margin-top: 10px;
  color: #f4f8fa;
  font-size: 16px;
  font-weight: 600;
}

.score-impact {
  margin: 6px 0 0;
  color: #90a0aa;
  font-size: 12px;
  line-height: 1.5;
}

.health-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.meta-box {
  padding: 10px 11px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.meta-box span {
  display: block;
  color: #7f8b95;
  font-size: 11px;
}

.meta-box strong {
  display: block;
  margin-top: 4px;
  color: #f4f8fa;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.health-side {
  padding: 16px;
  display: grid;
  gap: 10px;
}

.side-block {
  padding: 12px;
}

.side-block span,
.side-grid span {
  display: block;
  color: #7f8b95;
  font-size: 11px;
}

.side-block strong,
.side-grid strong {
  display: block;
  margin-top: 5px;
  color: #f4f8fa;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}

.side-block small {
  display: block;
  margin-top: 5px;
  color: #8d98a2;
  font-size: 12px;
  line-height: 1.45;
}

.side-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.side-grid div {
  padding: 10px 11px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.pipeline-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.pipeline-step {
  position: relative;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
}

.pipeline-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 44px;
  right: -5px;
  width: 10px;
  height: 1px;
  background: rgba(255, 255, 255, 0.12);
}

.step-index {
  color: #7f8b95;
  font-size: 11px;
  letter-spacing: 0.06em;
}

.step-icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
}

.pipeline-step.ok .step-icon {
  color: #7ce1c0;
}

.pipeline-step.warn .step-icon {
  color: #e2be73;
}

.pipeline-step.danger .step-icon {
  color: #ef8690;
}

.step-name {
  color: #f4f8fa;
  font-size: 14px;
  font-weight: 600;
}

.step-state {
  display: inline-flex;
  align-self: flex-start;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: #a8b3bb;
  font-size: 11px;
}

.pipeline-step.ok .step-state {
  color: #7ce1c0;
}

.pipeline-step.warn .step-state {
  color: #e2be73;
}

.pipeline-step.danger .step-state {
  color: #ef8690;
}

.step-note {
  color: #8d98a2;
  font-size: 12px;
  line-height: 1.5;
}

.monitor-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px;
}

.resource-panel {
  grid-column: span 8;
}

.action-panel {
  grid-column: span 4;
}

.resource-list,
.issue-list,
.service-focus-list {
  display: grid;
  gap: 10px;
}

.resource-row {
  padding: 12px;
}

.resource-row.ok {
  border-color: rgba(255, 255, 255, 0.06);
}

.resource-row.warn {
  border-color: rgba(226, 190, 115, 0.24);
}

.resource-row.danger {
  border-color: rgba(239, 134, 144, 0.26);
}

.resource-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.resource-head span {
  color: #97a4af;
  font-size: 12px;
}

.resource-head strong {
  color: #f4f8fa;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.resource-bar {
  height: 8px;
  margin-top: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  overflow: hidden;
}

.resource-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(124, 225, 192, 0.9), rgba(124, 225, 192, 0.65));
}

.resource-row.warn .resource-bar i {
  background: linear-gradient(90deg, rgba(226, 190, 115, 0.95), rgba(226, 190, 115, 0.68));
}

.resource-row.danger .resource-bar i {
  background: linear-gradient(90deg, rgba(239, 134, 144, 0.95), rgba(239, 134, 144, 0.68));
}

.resource-foot {
  margin-top: 8px;
  color: #8d98a2;
  font-size: 12px;
  line-height: 1.45;
}

.metric-tip {
  display: grid;
  gap: 4px;
  color: #f4f8fa;
  font-size: 12px;
  line-height: 1.5;
}

.issue-row {
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 12px;
}

.issue-strip {
  width: 4px;
  border-radius: 999px;
  background: #7ce1c0;
}

.issue-row.warn .issue-strip {
  background: #e2be73;
}

.issue-row.danger .issue-strip {
  background: #ef8690;
}

.issue-main {
  min-width: 0;
}

.issue-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.issue-top strong {
  color: #f4f8fa;
  font-size: 14px;
  font-weight: 600;
}

.issue-level {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: #a8b3bb;
  font-size: 11px;
}

.issue-row.warn .issue-level {
  color: #e2be73;
}

.issue-row.danger .issue-level {
  color: #ef8690;
}

.issue-current {
  margin-top: 6px;
  color: #bcc6ce;
  font-size: 12px;
}

.issue-impact,
.issue-action {
  margin-top: 4px;
  color: #8d98a2;
  font-size: 12px;
  line-height: 1.45;
}

.issue-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
  padding-left: 6px;
}

.text-action,
.drawer-action,
.more-issues,
.toggle-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #9dd1d5;
  font-size: 12px;
  cursor: pointer;
}

.text-action.handle,
.drawer-action.primary {
  color: #d8e1e8;
}

.text-action:hover,
.drawer-action:hover,
.toggle-action:hover,
.more-issues:hover {
  color: #f3f7fa;
}

.more-issues {
  justify-self: start;
  color: #97a4af;
}

.empty-state {
  min-height: 174px;
  display: grid;
  place-items: center;
  text-align: center;
  color: #93a0aa;
  border-radius: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.015);
}

.empty-state strong {
  display: block;
  margin-top: 8px;
  color: #f3f7fa;
  font-size: 14px;
  font-weight: 600;
}

.empty-state span {
  display: block;
  margin-top: 4px;
  color: #93a0aa;
  font-size: 12px;
}

.service-panel {
  grid-column: 1 / -1;
}

.service-focus-list {
  margin-bottom: 10px;
}

.service-item {
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
}

.service-item .service-strip {
  width: 4px;
  border-radius: 999px;
  background: #7ce1c0;
}

.service-item.warn .service-strip {
  background: #e2be73;
}

.service-item.neutral .service-strip {
  background: #8d98a2;
}

.service-content {
  min-width: 0;
}

.service-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.service-top strong {
  color: #f4f8fa;
  font-size: 13px;
  font-weight: 600;
}

.service-state {
  flex-shrink: 0;
  color: #a8b3bb;
  font-size: 12px;
}

.service-item.warn .service-state {
  color: #e2be73;
}

.service-item.neutral .service-state {
  color: #a8b3bb;
}

.service-content small {
  display: block;
  margin-top: 5px;
  color: #8d98a2;
  font-size: 12px;
  line-height: 1.45;
}

.service-quiet {
  margin-top: 2px;
  padding: 10px 12px;
  color: #97a4af;
  font-size: 12px;
}

.service-expanded {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.service-group {
  padding: 12px;
}

.service-group h4 {
  margin: 0 0 8px;
  color: #f3f7fa;
  font-size: 13px;
  font-weight: 600;
}

.service-group-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.service-group-row:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.service-group-row span {
  color: #8d98a2;
  font-size: 12px;
}

.service-group-row strong {
  color: #f4f8fa;
  font-size: 12px;
  font-weight: 600;
}

.drawer-body {
  display: grid;
  gap: 10px;
  color: #d8e1e8;
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.drawer-head span {
  color: #7f8b95;
  font-size: 12px;
}

.drawer-head h3 {
  margin: 4px 0 0;
  color: #f3f7fa;
  font-size: 16px;
  font-weight: 600;
}

.drawer-level {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: #a8b3bb;
  font-size: 11px;
  white-space: nowrap;
}

.drawer-level.warn {
  color: #e2be73;
}

.drawer-level.danger {
  color: #ef8690;
}

.drawer-block {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.drawer-block span {
  display: block;
  color: #7f8b95;
  font-size: 11px;
}

.drawer-block strong {
  display: block;
  margin-top: 5px;
  color: #f4f8fa;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
}

.drawer-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.drawer-action {
  padding: 0;
}

@media (max-width: 1320px) {
  .health-layout,
  .pipeline-rail,
  .service-expanded {
    grid-template-columns: 1fr;
  }

  .resource-panel,
  .action-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 820px) {
  .page-head,
  .panel-head,
  .score-block,
  .issue-top,
  .service-top,
  .drawer-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .health-layout,
  .monitor-grid,
  .health-meta,
  .side-grid,
  .service-expanded {
    grid-template-columns: 1fr;
  }

  .issue-row {
    grid-template-columns: 4px minmax(0, 1fr);
  }

  .issue-buttons {
    grid-column: 2 / -1;
    flex-direction: row;
    justify-content: flex-start;
  }
}
</style>
