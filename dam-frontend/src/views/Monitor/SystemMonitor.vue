<template>
  <div class="system-monitor-page">
    <header class="system-head">
      <div>
        <h2>系统监测</h2>
        <p>汇总平台运行、感知接入、AI 推理和告警处置状态。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </header>

    <section class="health-hero" :class="overallTone">
      <div class="hero-icon"><el-icon><Monitor /></el-icon></div>
      <div>
        <span>当前系统状态</span>
        <strong>{{ overallTitle }}</strong>
        <p>{{ overallSummary }}</p>
      </div>
      <div class="hero-score">
        <b>{{ readyScore }}</b>
        <small>关键项正常</small>
      </div>
    </section>

    <section class="signal-grid">
      <article v-for="item in keySignals" :key="item.label" class="signal-card" :class="item.tone">
        <el-icon><component :is="item.icon" /></el-icon>
        <div>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </div>
      </article>
    </section>

    <section class="facts-panel">
      <article v-for="item in serviceFacts" :key="item.label" class="fact-item">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.detail }}</small>
      </article>
    </section>

    <main class="monitor-layout">
      <section class="resource-panel">
        <header>
          <h3>算力与资源</h3>
          <span>{{ formatHours(systemInfo.service_uptime_hours) }} 服务运行</span>
        </header>
        <div class="resource-row">
          <span>CPU</span>
          <el-progress :percentage="percent(systemInfo.cpu_percent)" :color="usageColor(systemInfo.cpu_percent)" />
        </div>
        <div class="resource-row">
          <span>内存</span>
          <el-progress :percentage="percent(systemInfo.memory?.percent)" :color="usageColor(systemInfo.memory?.percent)" />
        </div>
        <div class="resource-row">
          <span>磁盘</span>
          <el-progress :percentage="percent(systemInfo.disk?.percent)" :color="usageColor(systemInfo.disk?.percent)" />
        </div>
        <div class="gpu-line">
          <span>GPU</span>
          <strong>{{ gpuText }}</strong>
          <small>{{ gpuDetail }}</small>
        </div>
      </section>

      <section class="readiness-panel">
        <header>
          <h3>运行关注项</h3>
          <span>{{ pendingActionCount ? `${pendingActionCount} 项需关注` : '暂无待处理项' }}</span>
        </header>
        <article v-for="item in actionItems" :key="item.title" class="action-line" :class="item.tone">
          <i></i>
          <div>
            <strong>{{ item.title }}</strong>
            <small>{{ item.detail }}</small>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { CircleCheck, Cpu, Monitor, Refresh, VideoCamera, Warning } from '@element-plus/icons-vue'
import { getSystemInfo } from '@/api/dashboard'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList, getModelStatus } from '@/api/camera'
import { getUnifiedSafetyEventStatistics } from '@/api/integration'

const loading = ref(false)
const systemInfo = ref({})
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const modelStatus = ref({ loaded: false, models: {} })
const eventStats = ref({})

const sensorsOnline = computed(() => {
  const values = Object.values(deviceStatus.value || {})
  return values.filter((item) => item?.status === 'online').length
})
const sensorsTotal = computed(() => Object.keys(deviceStatus.value || {}).length)
const modelReady = computed(() => Boolean(modelStatus.value.loaded || Object.values(modelStatus.value.models || {}).some((item) => item?.loaded)))
const openEvents = computed(() => Number(eventStats.value.pending || eventStats.value.open_events || eventStats.value.unresolved || 0))
const highEvents = computed(() => Number(eventStats.value.high || eventStats.value.HIGH || eventStats.value.high_level || 0))
const collectorRunning = computed(() => Boolean(systemInfo.value.sensor_collector_running))

const readyChecks = computed(() => [
  collectorRunning.value,
  sensorsTotal.value === 0 ? false : sensorsOnline.value > 0,
  cameraSummary.value.total === 0 ? false : cameraSummary.value.online > 0,
  modelReady.value,
  openEvents.value === 0,
])
const readyScore = computed(() => `${readyChecks.value.filter(Boolean).length}/${readyChecks.value.length}`)
const pendingActionCount = computed(() => actionItems.value.filter((item) => item.tone !== 'ok').length)
const overallTone = computed(() => {
  if (highEvents.value > 0 || !modelReady.value) return 'danger'
  if (pendingActionCount.value > 0) return 'warn'
  return 'ok'
})
const overallTitle = computed(() => {
  if (overallTone.value === 'danger') return '需要关注'
  if (overallTone.value === 'warn') return '局部待确认'
  return '运行平稳'
})
const overallSummary = computed(() => {
  if (highEvents.value > 0) return `存在 ${highEvents.value} 起高风险事件，请优先处置。`
  if (!modelReady.value) return 'AI 推理模型未就绪，模拟检测和实时识别能力可能受影响。'
  if (pendingActionCount.value > 0) return '部分感知链路或设备状态需要确认，核心平台仍可访问。'
  return '平台服务、感知接入和模型推理处于可用状态。'
})

const keySignals = computed(() => [
  {
    label: '平台服务',
    value: collectorRunning.value ? '采集中' : '待确认',
    hint: `服务运行 ${formatHours(systemInfo.value.service_uptime_hours)}`,
    tone: collectorRunning.value ? 'ok' : 'warn',
    icon: CircleCheck,
  },
  {
    label: '感知设备',
    value: `${sensorsOnline.value}/${sensorsTotal.value || 0}`,
    hint: '传感器在线情况',
    tone: sensorsOnline.value > 0 ? 'ok' : 'warn',
    icon: Monitor,
  },
  {
    label: '视频通道',
    value: `${cameraSummary.value.online}/${cameraSummary.value.total}`,
    hint: '摄像头在线通道',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
    icon: VideoCamera,
  },
  {
    label: 'AI 推理',
    value: modelReady.value ? '就绪' : '未就绪',
    hint: modelReady.value ? '模型可执行检测' : '请检查模型服务',
    tone: modelReady.value ? 'ok' : 'danger',
    icon: Cpu,
  },
  {
    label: '待处置事件',
    value: String(openEvents.value),
    hint: highEvents.value ? `${highEvents.value} 起高风险` : '当前高风险为 0',
    tone: highEvents.value ? 'danger' : openEvents.value ? 'warn' : 'ok',
    icon: Warning,
  },
])

const actionItems = computed(() => [
  {
    title: modelReady.value ? 'AI 推理模型可用' : 'AI 推理模型未就绪',
    detail: modelReady.value ? '视频识别和模拟检测可以使用。' : '建议进入系统管理 / 模型管理检查模型加载状态。',
    tone: modelReady.value ? 'ok' : 'danger',
  },
  {
    title: cameraSummary.value.online > 0 ? '视频通道可用' : '暂无在线视频通道',
    detail: cameraSummary.value.total ? `${cameraSummary.value.online}/${cameraSummary.value.total} 路摄像头在线。` : '请确认摄像头设备配置和网络。',
    tone: cameraSummary.value.online > 0 ? 'ok' : 'warn',
  },
  {
    title: openEvents.value ? '存在待处置事件' : '告警处置平稳',
    detail: openEvents.value ? `还有 ${openEvents.value} 起事件待处理。` : '当前没有明显积压的告警事件。',
    tone: openEvents.value ? 'warn' : 'ok',
  },
])

const serviceFacts = computed(() => [
  {
    label: '采集服务',
    value: collectorRunning.value ? '运行中' : '待确认',
    detail: collectorRunning.value ? '传感器数据链路可用' : '请确认采集进程',
  },
  {
    label: '感知覆盖',
    value: `${sensorsOnline.value + cameraSummary.value.online} 路在线`,
    detail: `${sensorsTotal.value} 个传感器 / ${cameraSummary.value.total} 路视频`,
  },
  {
    label: '识别能力',
    value: modelReady.value ? '可检测' : '未就绪',
    detail: modelReady.value ? '模型服务已加载' : '模型状态需要检查',
  },
  {
    label: '事件压力',
    value: openEvents.value ? `${openEvents.value} 起` : '无积压',
    detail: highEvents.value ? `${highEvents.value} 起高风险` : '高风险为 0',
  },
])

const gpuText = computed(() => systemInfo.value.gpu?.status || (systemInfo.value.gpu?.available ? '可用' : '待确认'))
const gpuDetail = computed(() => {
  const gpu = systemInfo.value.gpu || {}
  const parts = []
  if (gpu.utilization_percent != null) parts.push(`利用率 ${gpu.utilization_percent}%`)
  if (gpu.temperature_c != null) parts.push(`温度 ${gpu.temperature_c}°C`)
  if (gpu.power_w != null) parts.push(`功耗 ${gpu.power_w}W`)
  return parts.join(' / ') || '暂无 GPU 明细'
})

function percent(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value || 0))))
}

function usageColor(value) {
  const next = percent(value)
  if (next >= 85) return '#f56c6c'
  if (next >= 65) return '#e6a23c'
  return '#51e6be'
}

function formatHours(value) {
  const hours = Number(value || 0)
  if (!hours) return '--'
  if (hours < 24) return `${hours.toFixed(1)} 小时`
  return `${(hours / 24).toFixed(1)} 天`
}

function unwrap(response) {
  return response?.data || {}
}

async function loadAll() {
  loading.value = true
  try {
    const [system, devices, cameras, models, stats] = await Promise.allSettled([
      getSystemInfo(),
      getDeviceStatus(),
      getCameraList(),
      getModelStatus(),
      getUnifiedSafetyEventStatistics(),
    ])

    if (system.status === 'fulfilled') systemInfo.value = unwrap(system.value)
    if (devices.status === 'fulfilled') deviceStatus.value = unwrap(devices.value)
    if (models.status === 'fulfilled') modelStatus.value = unwrap(models.value)
    if (stats.status === 'fulfilled') eventStats.value = unwrap(stats.value)
    if (cameras.status === 'fulfilled') {
      const list = unwrap(cameras.value)?.cameras || []
      const enabled = list.filter((camera) => camera.enabled !== false)
      cameraSummary.value = {
        online: enabled.filter((camera) => camera.connected).length,
        total: enabled.length,
      }
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.system-monitor-page {
  min-height: 100%;
  padding: 22px;
  color: #e9f7ff;
  background: #071422;
}

.system-head,
.health-hero,
.signal-card,
.facts-panel,
.resource-panel,
.readiness-panel {
  border: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 8px;
  background: #0b1d30;
}

.system-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

h2,
h3,
p {
  margin-top: 0;
}

.system-head h2 {
  margin-bottom: 6px;
  font-size: 22px;
}

.system-head p,
.health-hero p,
.signal-card small,
.resource-panel header span,
.readiness-panel header span,
.action-line small {
  color: #8fa8b8;
}

.health-hero {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  margin-top: 14px;
  padding: 20px 22px;
  overflow: hidden;
}

.health-hero.ok { border-color: rgba(81, 230, 190, 0.32); }
.health-hero.warn { border-color: rgba(230, 162, 60, 0.38); }
.health-hero.danger { border-color: rgba(245, 108, 108, 0.38); }
.health-hero::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #51e6be;
}
.health-hero.warn::before { background: #e6a23c; }
.health-hero.danger::before { background: #f56c6c; }

.hero-icon {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  color: #51e6be;
  border-radius: 8px;
  background: rgba(81, 230, 190, 0.12);
}

.health-hero span,
.signal-card span {
  color: #8fa8b8;
  font-size: 13px;
}

.health-hero strong {
  display: block;
  margin: 5px 0;
  font-size: 30px;
}

.health-hero p {
  margin-bottom: 0;
}

.hero-score {
  text-align: right;
}

.hero-score b {
  display: block;
  color: #51e6be;
  font-size: 30px;
}

.hero-score small {
  color: #8fa8b8;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.signal-card {
  position: relative;
  display: flex;
  gap: 12px;
  min-height: 104px;
  padding: 16px;
  overflow: hidden;
}

.signal-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: rgba(81, 230, 190, .72);
}

.signal-card.warn::before { background: rgba(230, 162, 60, .78); }
.signal-card.danger::before { background: rgba(245, 108, 108, .78); }

.signal-card .el-icon {
  flex: 0 0 auto;
  color: #51e6be;
  font-size: 24px;
}

.signal-card.warn .el-icon,
.signal-card.warn strong { color: #e6a23c; }
.signal-card.danger .el-icon,
.signal-card.danger strong { color: #f56c6c; }

.signal-card strong {
  display: block;
  margin: 8px 0 4px;
  font-size: 24px;
}

.facts-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin-top: 14px;
  overflow: hidden;
}

.fact-item {
  min-height: 96px;
  padding: 16px 18px;
  display: grid;
  align-content: center;
  gap: 5px;
  border-right: 1px solid rgba(93, 184, 225, 0.12);
}

.fact-item:last-child {
  border-right: 0;
}

.fact-item span,
.fact-item small {
  color: #8fa8b8;
  font-size: 13px;
}

.fact-item strong {
  color: #f3f8fd;
  font-size: 20px;
  line-height: 26px;
  font-variant-numeric: tabular-nums;
}

.monitor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 14px;
  margin-top: 14px;
}

.resource-panel,
.readiness-panel {
  padding: 18px;
}

.resource-panel header,
.readiness-panel header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.resource-panel h3,
.readiness-panel h3 {
  margin-bottom: 0;
  font-size: 18px;
}

.resource-row {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  margin-top: 15px;
}

.resource-row span,
.gpu-line span {
  color: #b8cfe0;
  font-weight: 700;
}

.gpu-line,
.action-line {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(93, 184, 225, 0.12);
}

.gpu-line strong {
  color: #51e6be;
}

.gpu-line small {
  margin-left: auto;
  color: #8fa8b8;
}

.action-line {
  align-items: flex-start;
}

.action-line i {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  margin-top: 5px;
  border-radius: 50%;
  background: #51e6be;
  box-shadow: 0 0 8px rgba(81, 230, 190, 0.7);
}

.action-line.warn i {
  background: #e6a23c;
  box-shadow: 0 0 8px rgba(230, 162, 60, 0.7);
}

.action-line.danger i {
  background: #f56c6c;
  box-shadow: 0 0 8px rgba(245, 108, 108, 0.7);
}

.action-line strong,
.action-line small {
  display: block;
}

.action-line small {
  margin-top: 4px;
}

@media (max-width: 1180px) {
  .signal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .facts-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fact-item:nth-child(2n) {
    border-right: 0;
  }

  .monitor-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .system-head,
  .health-hero {
    grid-template-columns: 1fr;
    align-items: flex-start;
  }

  .system-head {
    flex-direction: column;
  }

  .signal-grid {
    grid-template-columns: 1fr;
  }

  .facts-panel {
    grid-template-columns: 1fr;
  }

  .fact-item {
    border-right: 0;
    border-bottom: 1px solid rgba(93, 184, 225, 0.12);
  }

  .fact-item:last-child {
    border-bottom: 0;
  }

  .hero-score {
    text-align: left;
  }
}
</style>
