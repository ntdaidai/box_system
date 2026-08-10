<template>
  <div class="event-command-page" v-loading="loading">
    <header class="command-topbar">
      <el-button class="back-button" :icon="ArrowLeft" @click="goBack">返回</el-button>
      <div class="topbar-title">
        <span>安全事件指挥 / 处置工作台</span>
        <h1>{{ event?.event_name || '安全事件详情' }}</h1>
      </div>
      <div v-if="event" class="topbar-badges">
        <span class="risk-badge" :class="riskClass(event.risk_level)">{{ riskLevelLabel(event.risk_level, event.risk_label) }}</span>
        <span class="status-badge" :class="statusClass(event.status)">{{ statusLabel(event.status) }}</span>
        <span class="duration-badge">持续 {{ eventDuration }}</span>
      </div>
    </header>

    <template v-if="event">
      <section class="incident-stage" :class="riskClass(event.risk_level)">
        <div class="scene-panel">
          <div class="scene-visual" :class="{ 'has-image': primaryEvidenceImage }">
            <el-image
              v-if="primaryEvidenceImage"
              class="scene-image"
              :src="primaryEvidenceImage.file_url"
              fit="cover"
              :preview-src-list="previewImageUrls"
              preview-teleported
            />
            <div v-else class="scene-empty">
              <el-icon><Picture /></el-icon>
              <strong>暂无现场证据</strong>
              <span>当前详情未返回摄像头截图、检测截图或视频帧</span>
            </div>

            <div class="scene-overlay">
              <div>
                <span>{{ visualDetail?.camera_name || event.camera_name || event.source_name || sourceLabel(event.source_type) }}</span>
                <strong>{{ visualDetail?.zone_name || '未标注检测区域' }}</strong>
              </div>
              <time>{{ formatTime(primaryEvidenceImage?.captured_at || event.last_observed_at || event.started_at) }}</time>
            </div>
          </div>
          <div class="scene-note">
            <el-icon><DataAnalysis /></el-icon>
            <span>{{ visualFrameNote }}</span>
          </div>
        </div>

        <aside class="incident-brief">
          <div class="brief-heading">
            <span>发现了什么</span>
            <h2>{{ event.summary || defaultSummary }}</h2>
            <p>{{ eventExplanation }}</p>
          </div>

          <dl class="signal-grid">
            <div>
              <dt>风险等级</dt>
              <dd>{{ riskLevelLabel(event.risk_level, event.risk_label) }}</dd>
            </div>
            <div>
              <dt>识别置信度</dt>
              <dd>{{ confidenceText(visualDetail?.confidence) }}</dd>
            </div>
            <div>
              <dt>首次发现</dt>
              <dd>{{ formatTime(event.started_at) }}</dd>
            </div>
            <div>
              <dt>最近观测</dt>
              <dd>{{ formatTime(event.last_observed_at) }}</dd>
            </div>
            <div>
              <dt>感知来源</dt>
              <dd>{{ visualDetail?.camera_name || event.camera_name || event.source_name || sourceLabel(event.source_type) }}</dd>
            </div>
            <div>
              <dt>目标类型</dt>
              <dd>{{ targetLabel(visualDetail?.target_type) }}</dd>
            </div>
          </dl>

          <div class="current-phase">
            <span>当前处置阶段</span>
            <strong>{{ currentPhase.title }}</strong>
            <p>{{ currentPhase.description }}</p>
          </div>
        </aside>
      </section>

      <section class="event-flow-panel">
        <header class="section-heading">
          <div>
            <span>事件演进轨道</span>
            <h3>从感知触发到闭环归档</h3>
          </div>
          <small>{{ timeline.length }} 条原始记录</small>
        </header>

        <div class="flow-scroll">
          <ol class="event-flow">
            <li
              v-for="(node, index) in flowNodes"
              :key="node.key"
              :class="[node.state, { current: node.current, broken: node.failed }]"
              :title="node.message"
            >
              <div class="flow-node">
                <el-icon><component :is="node.icon" /></el-icon>
              </div>
              <div class="flow-copy">
                <strong>{{ node.title }}</strong>
                <span>{{ node.time }}</span>
                <small>{{ node.subtitle }}</small>
              </div>
              <svg v-if="index < flowNodes.length - 1" class="flow-link" viewBox="0 0 132 32" aria-hidden="true">
                <path d="M2 16 H118" />
                <path d="M118 16 L106 8 M118 16 L106 24" />
              </svg>
            </li>
          </ol>
        </div>
      </section>

      <section class="command-grid">
        <main class="command-main">
          <section class="evidence-gallery">
            <header class="section-heading compact">
              <div>
                <span>现场证据</span>
                <h3>Evidence Strip</h3>
              </div>
              <small>{{ evidence.length }} 份</small>
            </header>

            <div v-if="evidence.length" class="evidence-strip">
              <button
                v-for="item in evidence"
                :key="item.id"
                type="button"
                class="evidence-tile"
                :class="{ 'is-image': isImageEvidence(item) }"
                @click="openEvidenceItem(item)"
              >
                <el-image v-if="isImageEvidence(item)" :src="item.file_url" fit="cover" />
                <div v-else class="file-evidence">
                  <el-icon><Document /></el-icon>
                  <span>{{ evidenceTypeLabel(item.evidence_type) }}</span>
                </div>
                <span class="evidence-source">{{ sourceLabel(item.source_type) }}</span>
                <time>{{ formatTime(item.captured_at) }}</time>
              </button>
            </div>
            <div v-else class="clean-empty">
              <el-icon><Picture /></el-icon>
              <strong>尚无证据留存</strong>
              <span>系统还没有返回截图、视频帧、人工照片或文件</span>
            </div>
          </section>

          <section class="log-ledger">
            <header class="section-heading compact">
              <div>
                <span>原始记录</span>
                <h3>处置日志</h3>
              </div>
            </header>
            <div v-if="timeline.length" class="log-list">
              <article v-for="item in timeline" :key="item.id" :class="timelineTone(item)">
                <div>
                  <strong>{{ item.title || logTypeLabel(item.log_type) }}</strong>
                  <p>{{ item.message || item.action || '暂无处理说明' }}</p>
                </div>
                <footer>
                  <span>{{ operatorLabel(item.operator) }}</span>
                  <time>{{ formatTime(item.create_time || item.created_at) }}</time>
                  <el-button
                    v-if="evidenceForLog(item.id).length"
                    class="evidence-button"
                    link
                    type="primary"
                    :icon="Picture"
                    @click="openEvidence(item.id)"
                  >
                    证据
                  </el-button>
                </footer>
              </article>
            </div>
            <div v-else class="clean-empty slim">
              <strong>暂无处置日志</strong>
              <span>事件创建后产生的触发、联动、人工处置会沉淀在这里</span>
            </div>
          </section>
        </main>

        <aside class="command-side">
          <section class="disposal-status">
            <header class="section-heading compact">
              <div>
                <span>处置状态</span>
                <h3>当前链路</h3>
              </div>
            </header>

            <ol class="status-chain">
              <li v-for="step in disposalSteps" :key="step.key" :class="[step.state, { current: step.current }]">
                <span class="step-mark">
                  <el-icon><component :is="step.icon" /></el-icon>
                </span>
                <div>
                  <strong>{{ step.title }}</strong>
                  <small>{{ step.text }}</small>
                </div>
              </li>
            </ol>
          </section>

          <section class="action-modules">
            <header class="section-heading compact">
              <div>
                <span>联动动作</span>
                <h3>执行模块</h3>
              </div>
            </header>

            <article v-for="module in actionModules" :key="module.key" :class="['action-module', module.state]">
              <div class="module-icon">
                <el-icon><component :is="module.icon" /></el-icon>
              </div>
              <div class="module-body">
                <header>
                  <strong>{{ module.title }}</strong>
                  <span>{{ module.statusText }}</span>
                </header>
                <p>{{ module.description }}</p>
                <dl>
                  <div>
                    <dt>{{ module.metaLabel }}</dt>
                    <dd>{{ module.metaValue }}</dd>
                  </div>
                  <div>
                    <dt>最近记录</dt>
                    <dd>{{ module.lastTime }}</dd>
                  </div>
                </dl>
              </div>
            </article>
          </section>
        </aside>
      </section>

      <section v-if="event.state === 'ACTIVE'" class="sticky-action-bar">
        <div class="action-context">
          <span>用户现在需要做什么</span>
          <strong>{{ primaryAction.title }}</strong>
          <p>{{ primaryAction.hint }}</p>
        </div>
        <div class="decision-actions">
          <el-button
            v-if="primaryAction.action"
            type="primary"
            size="large"
            :disabled="primaryAction.disabled"
            @click="operate(primaryAction.action)"
          >
            {{ primaryAction.label }}
          </el-button>
          <el-button
            v-for="button in secondaryActions"
            :key="button.action"
            plain
            :type="button.type"
            :disabled="button.disabled"
            @click="operate(button.action)"
          >
            {{ button.label }}
          </el-button>
        </div>
      </section>
    </template>

    <el-empty v-else-if="!loading" description="未找到安全事件" />

    <el-drawer v-model="evidenceVisible" title="事件证据" class="evidence-drawer" size="560px">
      <div v-if="currentEvidence.length" class="evidence-drawer-list">
        <figure v-for="item in currentEvidence" :key="item.id">
          <el-image
            v-if="isImageEvidence(item)"
            :src="item.file_url"
            fit="cover"
            :preview-src-list="currentEvidence.filter(isImageEvidence).map((record) => record.file_url)"
            preview-teleported
          />
          <div v-else class="drawer-file">
            <el-icon><Document /></el-icon>
            <a :href="item.file_url" target="_blank" rel="noreferrer">{{ item.file_url }}</a>
          </div>
          <figcaption>
            <strong>{{ item.description || evidenceTypeLabel(item.evidence_type) }}</strong>
            <span>{{ sourceLabel(item.source_type) }} · {{ formatTime(item.captured_at) }}</span>
            <small>关联动作：{{ relatedLogLabel(item.timeline_log_id) }}</small>
          </figcaption>
        </figure>
      </div>
      <div v-else class="clean-empty">当前节点暂无证据</div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  CircleCheck,
  Connection,
  DataAnalysis,
  Document,
  Finished,
  Microphone,
  Picture,
  Promotion,
  User,
  Warning,
} from '@element-plus/icons-vue'
import { getIntegrationConfig, getUnifiedSafetyEventDetail, operateUnifiedSafetyEvent } from '@/api/integration'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const evidenceVisible = ref(false)
const currentEvidence = ref([])
const detail = reactive({
  event: null,
  visual_detail: null,
  timeline: [],
  evidence: [],
  tasks: [],
})
const actionConfigs = ref([])

const event = computed(() => detail.event)
const visualDetail = computed(() => detail.visual_detail)
const timeline = computed(() => detail.timeline)
const evidence = computed(() => detail.evidence)
const imageEvidence = computed(() => evidence.value.filter(isImageEvidence))
const primaryEvidenceImage = computed(() => imageEvidence.value[0] || null)
const previewImageUrls = computed(() => imageEvidence.value.map((item) => item.file_url).filter(Boolean))
const latestTask = computed(() => detail.tasks[0] || null)
const eventActionConfigs = computed(() => actionConfigs.value.filter((item) => item.event_id === event.value?.event_id && item.enabled))

const defaultSummary = computed(() => {
  const source = visualDetail.value?.camera_name || event.value?.camera_name || sourceLabel(event.value?.source_type)
  return `${source} 触发安全事件，当前状态为${statusLabel(event.value?.status)}。`
})

const eventDuration = computed(() => {
  if (!event.value?.started_at) return '--'
  const end = event.value.resolved_at || event.value.last_observed_at || new Date()
  return formatDuration(event.value.started_at, end)
})

const eventExplanation = computed(() => {
  const target = targetLabel(visualDetail.value?.target_type)
  const zone = visualDetail.value?.zone_name
  if (target !== '--' && zone) return `系统在 ${zone} 识别到${target}目标，并按规则生成告警。`
  if (target !== '--') return `系统识别到${target}目标，并按规则生成告警。`
  return '系统根据感知数据和规则判断生成该事件，请结合时间线和证据确认现场情况。'
})

const visualFrameNote = computed(() => {
  if (!primaryEvidenceImage.value) return '没有可展示的真实画面，因此保持正式空状态。'
  if (visualDetail.value?.zone_name) return '当前接口未返回检测框坐标，主视觉仅展示真实证据画面与区域信息。'
  return '当前接口未返回检测区域或检测框坐标，主视觉仅展示真实证据画面。'
})

const currentPhase = computed(() => {
  if (event.value?.state !== 'ACTIVE') {
    return {
      title: statusLabel(event.value?.status),
      description: event.value?.resolve_reason || '事件已完成闭环归档。',
    }
  }
  if (event.value?.risk_level === 'HIGH') {
    if (latestTask.value?.status === 'ACCEPTED' || latestTask.value?.status === 'PROCESSING') {
      return { title: '现场处置中', description: '人工任务已接单，等待现场结果回传。' }
    }
    return { title: '等待处置接管', description: '高风险事件需要人员接单并完成现场处置。' }
  }
  return { title: '等待人工确认', description: '请确认事件真实性，必要时升级风险或闭环归档。' }
})

const flowNodes = computed(() => {
  const triggerLog = firstLogByType(['TRIGGER'])
  const riskLog = firstLogByType(['RISK_CHANGE'])
  const actionLog = firstLogByType(['ACTION'])
  const manualLog = firstLogByType(['MANUAL'])
  const resolveLog = firstLogByType(['RESOLVE'])
  const failedLog = timeline.value.find((item) => isFailedStatus(item.status))

  return [
    flowNode('detect', '目标出现', visualDetail.value ? targetLabel(visualDetail.value.target_type) : '感知源上报', event.value?.started_at, visualDetail.value || event.value, DataAnalysis),
    flowNode('threshold', '条件达到阈值', riskLog ? logTypeLabel(riskLog.log_type) : eventExplanation.value, riskLog?.create_time || event.value?.started_at, riskLog, Warning),
    flowNode('created', '安全事件触发', event.value?.instance_no || '实例已创建', triggerLog?.create_time || event.value?.started_at, triggerLog || event.value, Promotion),
    flowNode('workflow', '自动工作流', actionLog ? '已产生联动记录' : actionModuleSummary.value, actionLog?.create_time, actionLog, Connection),
    flowNode('manual', '人工处置', manualStageText.value, manualLog?.create_time || latestTask.value?.accepted_at, manualLog || latestTask.value, User),
    flowNode('archive', '闭环归档', event.value?.state === 'RESOLVED' ? statusLabel(event.value.status) : '等待闭环', resolveLog?.create_time || event.value?.resolved_at, resolveLog || event.value, Finished),
  ].map((node, index, nodes) => {
    const currentIndex = nodes.findIndex((item) => item.state === 'running' || item.state === 'pending')
    return {
      ...node,
      current: index === (currentIndex === -1 ? nodes.length - 1 : currentIndex),
      failed: failedLog && node.source?.id === failedLog.id,
    }
  })
})

const actionModuleSummary = computed(() => {
  const configured = eventActionConfigs.value.length
  if (!configured) return '未配置自动动作'
  return `已配置 ${configured} 个自动动作`
})

const manualStageText = computed(() => {
  if (event.value?.state === 'RESOLVED') return '已完成'
  if (latestTask.value?.status === 'ACCEPTED' || latestTask.value?.status === 'PROCESSING') return '现场处置中'
  if (latestTask.value?.status === 'WAITING_ACCEPT' || latestTask.value?.status === 'DISPATCHED') return '等待人员接单'
  if (event.value?.risk_level === 'HIGH') return '等待人员接管'
  return '等待人工确认'
})

const disposalSteps = computed(() => [
  statusStep('ai', 'AI 识别确认', visualDetail.value ? '已返回目标识别结果' : '未返回视觉识别详情', visualDetail.value ? 'done' : 'waiting', DataAnalysis),
  statusStep('event', '安全事件创建', event.value?.instance_no || '实例已创建', event.value ? 'done' : 'waiting', Promotion),
  statusStep('broadcast', '广播任务', moduleStateByKey('broadcast'), actionState('broadcast'), Microphone),
  statusStep('drone', '无人机任务', moduleStateByKey('drone'), actionState('drone'), Connection),
  statusStep('manual', '人工确认', manualStageText.value, manualState.value, User),
  statusStep('archive', '闭环归档', event.value?.state === 'RESOLVED' ? statusLabel(event.value.status) : '等待完成处置', event.value?.state === 'RESOLVED' ? 'done' : 'waiting', CircleCheck),
].map((step, index, steps) => {
  const currentIndex = steps.findIndex((item) => item.state === 'running' || item.state === 'waiting')
  return { ...step, current: index === currentIndex }
}))

const manualState = computed(() => {
  if (event.value?.state === 'RESOLVED') return 'done'
  if (latestTask.value?.status === 'ACCEPTED' || latestTask.value?.status === 'PROCESSING') return 'running'
  return 'waiting'
})

const actionModules = computed(() => [
  buildActionModule({
    key: 'broadcast',
    title: '广播喊话',
    types: ['broadcast'],
    icon: Microphone,
    metaLabel: '设备',
    metaValue: (config) => config?.broadcast_device_name || '未指定设备',
  }),
  buildActionModule({
    key: 'drone',
    title: '无人机驱动',
    types: ['drone_dispatch', 'drone'],
    icon: Connection,
    metaLabel: '航线',
    metaValue: (config) => config?.route_id ? `航线 ${config.route_id}` : '未指定航线',
  }),
  buildActionModule({
    key: 'manual',
    title: '人工处置',
    types: ['manual_task', 'staff_task', 'dispatch_task'],
    icon: User,
    metaLabel: '人员',
    metaValue: () => latestTask.value?.assignee || latestTask.value?.dispatch_operator || '等待分配',
    fallbackConfigured: event.value?.risk_level === 'HIGH',
    fallbackText: manualStageText.value,
  }),
])

const primaryAction = computed(() => {
  if (event.value?.state !== 'ACTIVE') {
    return { title: '事件已归档', hint: event.value?.resolve_reason || '无需继续处置', label: '', action: '', disabled: true }
  }
  if (event.value.risk_level === 'HIGH') {
    if (latestTask.value?.status === 'ACCEPTED' || latestTask.value?.status === 'PROCESSING') {
      return { title: '回传现场处置结果', hint: '完成现场确认后提交结果，事件将进入闭环。', label: '完成现场处置', action: 'COMPLETE_TASK' }
    }
    return { title: '接管高风险事件', hint: '先接受处置任务，再推进现场确认。', label: '接受处置', action: 'ACCEPT_TASK' }
  }
  return { title: '确认事件真实性', hint: '低中风险事件可确认闭环，也可以升级或标记误报。', label: '确认闭环', action: 'RESOLVE' }
})

const secondaryActions = computed(() => {
  if (event.value?.state !== 'ACTIVE') return []
  const actions = []
  if (event.value?.risk_level !== 'HIGH') {
    actions.push({ label: '升级风险', action: 'UPGRADE', type: 'danger', disabled: false })
  }
  actions.push({ label: '标记误报', action: 'FALSE_ALARM', type: 'default', disabled: false })
  if (event.value?.risk_level === 'HIGH' && latestTask.value?.status !== 'ACCEPTED' && latestTask.value?.status !== 'PROCESSING') {
    actions.push({ label: '完成闭环', action: 'RESOLVE', type: 'primary', disabled: true })
  }
  return actions
})

async function loadDetail() {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const [detailResult, configResult] = await Promise.allSettled([
      getUnifiedSafetyEventDetail(id),
      getIntegrationConfig(),
    ])
    if (detailResult.status === 'rejected') throw detailResult.reason
    const data = detailResult.value.data || {}
    detail.event = data.event || null
    detail.visual_detail = data.visual_detail || null
    detail.timeline = Array.isArray(data.timeline) ? data.timeline : []
    detail.evidence = Array.isArray(data.evidence) ? data.evidence : []
    detail.tasks = Array.isArray(data.tasks) ? data.tasks : []
    if (configResult.status === 'fulfilled') {
      actionConfigs.value = Array.isArray(configResult.value.data?.action_configs) ? configResult.value.data.action_configs : []
    } else {
      actionConfigs.value = []
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '安全事件详情暂时不可达')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/alarm/safety-events')
}

function evidenceForLog(logId) {
  return evidence.value.filter((item) => item.timeline_log_id === logId)
}

function openEvidence(logId) {
  const matched = logId ? evidenceForLog(logId) : []
  currentEvidence.value = matched.length ? matched : evidence.value
  evidenceVisible.value = true
}

function openEvidenceItem(item) {
  currentEvidence.value = item ? [item] : evidence.value
  evidenceVisible.value = true
}

async function operate(action) {
  if (!event.value?.id) return
  const riskLevel = action === 'UPGRADE'
    ? (event.value.risk_level === 'LOW' ? 'MEDIUM' : 'HIGH')
    : undefined
  const title = ({
    ACCEPT_TASK: '接受处置',
    COMPLETE_TASK: '完成现场处置',
    FALSE_ALARM: '标记误报',
    RESOLVE: '确认闭环',
    UPGRADE: '升级风险',
  })[action] || '事件操作'
  try {
    const { value: reason } = await ElMessageBox.prompt('请输入处置说明', title, {
      inputPlaceholder: '简要说明本次操作原因',
    })
    await operateUnifiedSafetyEvent(event.value.id, { action, risk_level: riskLevel, reason })
    ElMessage.success('事件状态已更新')
    await loadDetail()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || '事件操作失败')
  }
}

function flowNode(key, title, subtitle, time, source, icon) {
  const failed = source && isFailedStatus(source.status)
  let state = 'pending'
  if (failed) state = 'failed'
  else if (source) state = 'done'
  if (key === 'workflow' && source && !failed && event.value?.state === 'ACTIVE') state = 'running'
  if (key === 'manual' && event.value?.state === 'ACTIVE' && manualState.value === 'running') state = 'running'
  if (key === 'archive' && event.value?.state !== 'RESOLVED') state = 'pending'
  return {
    key,
    title,
    subtitle: subtitle || '--',
    time: formatShortTime(time),
    state,
    source,
    icon,
    message: source?.message || subtitle || title,
  }
}

function statusStep(key, title, text, state, icon) {
  return { key, title, text, state, icon }
}

function firstLogByType(types) {
  return timeline.value.find((item) => types.includes(item.log_type))
}

function logsForModule(key) {
  const includes = {
    broadcast: ['broadcast', '广播', '喊话'],
    drone: ['drone', 'uav', '无人机', '派飞'],
    manual: ['manual', '人工', '处置', '接单'],
  }[key] || []
  return timeline.value.filter((item) => {
    const text = `${item.log_type || ''} ${item.title || ''} ${item.message || ''} ${item.action || ''}`.toLowerCase()
    return includes.some((keyword) => text.includes(keyword))
  })
}

function configsForModule(types) {
  return eventActionConfigs.value.filter((config) => types.includes(config.action_type))
}

function buildActionModule(options) {
  const logs = logsForModule(options.key)
  const failed = logs.find((item) => isFailedStatus(item.status))
  const last = logs[logs.length - 1]
  const config = configsForModule(options.types)[0]
  const configured = Boolean(config || options.fallbackConfigured)
  const state = failed ? 'failed' : last ? 'done' : configured ? 'waiting' : 'unconfigured'
  const statusText = ({
    done: '已执行',
    failed: '执行失败',
    waiting: '等待执行',
    unconfigured: '未配置',
  })[state]
  return {
    key: options.key,
    title: options.title,
    icon: options.icon,
    state,
    statusText,
    description: failed?.message || last?.message || options.fallbackText || (configured ? '任务已配置，尚未产生执行记录。' : '当前事件未配置该联动动作。'),
    metaLabel: options.metaLabel,
    metaValue: options.metaValue(config),
    lastTime: formatShortTime(last?.create_time || last?.created_at),
  }
}

function actionState(key) {
  return actionModules.value.find((item) => item.key === key)?.state || 'waiting'
}

function moduleStateByKey(key) {
  const module = actionModules.value.find((item) => item.key === key)
  return module ? module.statusText : '等待执行'
}

function isFailedStatus(value) {
  return ['FAILED', 'FAIL', 'ERROR'].includes(String(value || '').toUpperCase())
}

function isImageEvidence(item) {
  const type = String(item?.evidence_type || '').toUpperCase()
  const url = String(item?.file_url || '').split('?')[0].toLowerCase()
  return type === 'IMAGE' || /\.(png|jpe?g|webp|gif|bmp)$/.test(url)
}

function riskClass(value) {
  return ({ LOW: 'risk-low', MEDIUM: 'risk-medium', HIGH: 'risk-high' })[value] || 'risk-unknown'
}

function riskLevelLabel(value, fallback) {
  return fallback || ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[value] || '--'
}

function statusLabel(value) {
  return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[value] || value || '--'
}

function statusClass(value) {
  return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', COMPLETED: 'is-completed', FALSE_ALARM: 'is-false-alarm' })[value] || ''
}

function logTypeLabel(value) {
  return ({ TRIGGER: '事件触发', RISK_CHANGE: '风险变化', ACTION: '执行动作', MANUAL: '人工操作', RESOLVE: '事件闭环', SYSTEM: '系统记录' })[value] || value || '记录'
}

function timelineTone(item) {
  if (isFailedStatus(item?.status)) return 'is-failed'
  return ({ TRIGGER: 'is-primary', RISK_CHANGE: 'is-warning', ACTION: 'is-success', RESOLVE: 'is-success' })[item?.log_type] || 'is-info'
}

function targetLabel(value) {
  return ({ person: '人员', boat: '船只', vehicle: '车辆', fire: '火点' })[value] || value || '--'
}

function sourceLabel(value) {
  return ({ CAMERA: '摄像头', DRONE: '无人机', STAFF: '人工上传', SYSTEM: '系统', camera: '摄像头' })[value] || value || '系统感知'
}

function evidenceTypeLabel(value) {
  return ({ IMAGE: '图片证据', VIDEO: '视频证据', FILE: '文件证据' })[value] || value || '证据文件'
}

function operatorLabel(value) {
  if (!value) return '系统记录'
  return value === 'SYSTEM' ? '系统自动' : value
}

function relatedLogLabel(logId) {
  const log = timeline.value.find((item) => item.id === logId)
  return log ? (log.title || logTypeLabel(log.log_type)) : '未关联日志'
}

function confidenceText(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : '--'
}

function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

function formatShortTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

function formatDuration(startValue, endValue) {
  const start = new Date(startValue)
  const end = new Date(endValue)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '--'
  const seconds = Math.max(0, Math.floor((end.getTime() - start.getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

loadDetail()
</script>

<style scoped>
.event-command-page {
  min-height: 100%;
  padding: 20px;
  color: #d9e8f8;
  background:
    linear-gradient(180deg, rgba(10, 27, 44, .96), rgba(4, 12, 22, .98)),
    #071422;
}
.command-topbar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
}
.back-button {
  border-color: rgba(86, 171, 221, .32);
  color: #c3dfef;
  background: rgba(9, 31, 50, .92);
}
.topbar-title span,
.section-heading span {
  display: block;
  color: #7fb1d4;
  font-size: 13px;
}
.topbar-title h1 {
  margin: 4px 0 0;
  color: #f6fbff;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: 0;
}
.topbar-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.risk-badge,
.status-badge,
.duration-badge {
  min-width: 82px;
  padding: 8px 12px;
  border-radius: 6px;
  color: #dcecff;
  text-align: center;
  background: rgba(14, 37, 58, .9);
}
.risk-badge.risk-high {
  color: #ffd2d7;
  background: rgba(156, 38, 55, .48);
}
.risk-badge.risk-medium {
  color: #ffe7ac;
  background: rgba(157, 114, 28, .42);
}
.risk-badge.risk-low {
  color: #c9f7e4;
  background: rgba(31, 119, 91, .42);
}
.status-badge.is-pending {
  color: #f0c75d;
}
.status-badge.is-processing {
  color: #69d8ff;
}
.status-badge.is-completed,
.status-badge.is-false-alarm {
  color: #7ee2bd;
}
.duration-badge {
  color: #a9c7dc;
}
.incident-stage {
  margin-top: 16px;
  min-height: 470px;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(380px, .65fr);
  overflow: hidden;
  border-radius: 8px;
  background:
    linear-gradient(110deg, rgba(8, 24, 40, .98), rgba(10, 32, 52, .96)),
    #091b2b;
  box-shadow: 0 24px 60px rgba(0, 0, 0, .22);
}
.incident-stage.risk-high {
  box-shadow: inset 0 0 0 1px rgba(255, 94, 107, .26), 0 24px 60px rgba(0, 0, 0, .24);
}
.scene-panel {
  min-width: 0;
  padding: 18px;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 12px;
}
.scene-visual {
  position: relative;
  min-height: 390px;
  overflow: hidden;
  border-radius: 8px;
  background: #030b13;
}
.scene-image {
  width: 100%;
  height: 100%;
  display: block;
}
.scene-empty {
  height: 100%;
  min-height: 390px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: #85a7bd;
  background:
    linear-gradient(90deg, rgba(105, 216, 255, .08) 1px, transparent 1px),
    linear-gradient(180deg, rgba(105, 216, 255, .08) 1px, transparent 1px),
    #051320;
  background-size: 42px 42px;
}
.scene-empty .el-icon {
  font-size: 42px;
  color: #6b9fbd;
}
.scene-empty strong {
  color: #eaf6fc;
  font-size: 22px;
}
.scene-empty span {
  color: #7e9eb6;
}
.scene-overlay {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 16px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(3, 10, 18, .78);
  backdrop-filter: blur(10px);
}
.scene-overlay span,
.scene-overlay time {
  color: #8fb5ce;
  font-size: 13px;
}
.scene-overlay strong {
  display: block;
  margin-top: 4px;
  color: #f2fbff;
  font-size: 20px;
  letter-spacing: 0;
}
.scene-note {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  color: #8fb1c8;
  font-size: 13px;
}
.incident-brief {
  padding: 24px;
  display: grid;
  align-content: space-between;
  gap: 22px;
  background: rgba(7, 20, 34, .84);
}
.brief-heading span {
  color: #7fb1d4;
  font-size: 13px;
}
.brief-heading h2 {
  margin: 8px 0 12px;
  color: #fff;
  font-size: 24px;
  line-height: 1.35;
  letter-spacing: 0;
}
.brief-heading p {
  margin: 0;
  color: #9fbacf;
  line-height: 1.75;
}
.signal-grid {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.signal-grid div {
  min-height: 76px;
  padding: 12px;
  border-radius: 7px;
  background: rgba(5, 18, 30, .72);
}
dt {
  color: #7d9db4;
  font-size: 12px;
}
dd {
  margin: 8px 0 0;
  color: #f1f9ff;
  font-size: 14px;
  line-height: 1.35;
}
.current-phase {
  padding: 16px;
  border-radius: 8px;
  background: rgba(105, 216, 255, .09);
}
.current-phase span {
  color: #86b8d6;
  font-size: 13px;
}
.current-phase strong {
  display: block;
  margin-top: 7px;
  color: #fff;
  font-size: 22px;
}
.current-phase p {
  margin: 8px 0 0;
  color: #a9c2d3;
  line-height: 1.6;
}
.event-flow-panel,
.evidence-gallery,
.log-ledger,
.disposal-status,
.action-modules,
.sticky-action-bar {
  border-radius: 8px;
  background: rgba(10, 29, 48, .86);
}
.event-flow-panel {
  margin-top: 16px;
  padding: 18px;
}
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.section-heading h3 {
  margin: 4px 0 0;
  color: #f3f8fd;
  font-size: 20px;
  letter-spacing: 0;
}
.section-heading.compact h3 {
  font-size: 18px;
}
.section-heading small {
  color: #84a4ba;
}
.flow-scroll {
  margin-top: 18px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.event-flow {
  min-width: 1120px;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  list-style: none;
}
.event-flow li {
  position: relative;
  min-width: 0;
  padding-right: 26px;
}
.flow-node {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #89b8d2;
  background: #102a41;
  box-shadow: 0 0 0 1px rgba(127, 177, 212, .18);
}
.flow-node .el-icon {
  font-size: 24px;
}
.event-flow li.done .flow-node {
  color: #0d281f;
  background: #7ee2bd;
}
.event-flow li.running .flow-node {
  color: #04131d;
  background: #69d8ff;
  animation: nodePulse 1.8s ease-in-out infinite;
}
.event-flow li.failed .flow-node {
  color: #fff;
  background: #ff5e6b;
}
.event-flow li.pending .flow-node {
  color: #7898ad;
  background: #0b1b2b;
}
.flow-copy {
  margin-top: 10px;
  min-height: 92px;
}
.flow-copy strong,
.flow-copy span,
.flow-copy small {
  display: block;
}
.flow-copy strong {
  color: #f1f8fd;
  font-size: 15px;
}
.flow-copy span {
  margin-top: 6px;
  color: #9fbfd4;
  font-size: 13px;
}
.flow-copy small {
  margin-top: 6px;
  color: #7492a7;
  line-height: 1.4;
}
.event-flow li.current .flow-copy strong {
  color: #69d8ff;
}
.flow-link {
  position: absolute;
  left: 58px;
  top: 12px;
  width: calc(100% - 66px);
  height: 32px;
  overflow: visible;
}
.flow-link path {
  fill: none;
  stroke: rgba(105, 216, 255, .42);
  stroke-width: 2;
  stroke-linecap: round;
}
.event-flow li.pending .flow-link path {
  stroke: rgba(117, 148, 169, .2);
}
.event-flow li.broken .flow-link path,
.event-flow li.failed .flow-link path {
  stroke: rgba(255, 94, 107, .7);
  stroke-dasharray: 7 7;
}
.command-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
  align-items: start;
}
.command-main,
.command-side {
  min-width: 0;
  display: grid;
  gap: 16px;
}
.evidence-gallery,
.log-ledger,
.disposal-status,
.action-modules {
  padding: 16px;
}
.evidence-strip {
  margin-top: 14px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(180px, 220px);
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.evidence-tile {
  position: relative;
  height: 142px;
  overflow: hidden;
  border: 0;
  border-radius: 8px;
  color: #dff2ff;
  text-align: left;
  background: #071421;
  cursor: pointer;
}
.evidence-tile .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.evidence-tile::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 30%, rgba(0, 0, 0, .72));
}
.evidence-tile:hover {
  outline: 2px solid rgba(105, 216, 255, .48);
}
.file-evidence {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  background: #0b1b2b;
}
.file-evidence .el-icon {
  font-size: 30px;
  color: #9bc1d8;
}
.evidence-source,
.evidence-tile time {
  position: absolute;
  z-index: 1;
  left: 12px;
  right: 12px;
}
.evidence-source {
  bottom: 34px;
  color: #fff;
  font-size: 13px;
}
.evidence-tile time {
  bottom: 14px;
  color: #a9c5d6;
  font-size: 12px;
}
.clean-empty {
  min-height: 132px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #7f9db2;
  border: 1px dashed rgba(127, 177, 212, .22);
  border-radius: 8px;
  background: rgba(4, 13, 22, .42);
}
.clean-empty.slim {
  min-height: 96px;
}
.clean-empty .el-icon {
  font-size: 28px;
}
.clean-empty strong {
  color: #dcecf7;
}
.clean-empty span {
  font-size: 13px;
}
.log-list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}
.log-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  padding: 12px 14px;
  border-left: 3px solid #69d8ff;
  border-radius: 7px;
  background: rgba(4, 13, 22, .46);
}
.log-list article.is-warning {
  border-left-color: #f0c75d;
}
.log-list article.is-success {
  border-left-color: #7ee2bd;
}
.log-list article.is-failed {
  border-left-color: #ff5e6b;
}
.log-list strong {
  color: #f1f8fd;
}
.log-list p {
  margin: 6px 0 0;
  color: #97b3c7;
  line-height: 1.55;
}
.log-list footer {
  display: grid;
  justify-items: end;
  align-content: center;
  gap: 5px;
  color: #7e9eb6;
  font-size: 12px;
}
.status-chain {
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 4px;
}
.status-chain li {
  position: relative;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 0;
}
.status-chain li::before {
  content: "";
  position: absolute;
  left: 16px;
  top: 42px;
  bottom: -8px;
  width: 1px;
  background: rgba(127, 177, 212, .18);
}
.status-chain li:last-child::before {
  display: none;
}
.step-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #7898ad;
  background: #0b1b2b;
}
.status-chain li.done .step-mark {
  color: #0b211b;
  background: #7ee2bd;
}
.status-chain li.running .step-mark {
  color: #03131e;
  background: #69d8ff;
  animation: nodePulse 1.8s ease-in-out infinite;
}
.status-chain li.failed .step-mark,
.status-chain li.unconfigured .step-mark {
  color: #fff;
  background: #794151;
}
.status-chain strong,
.status-chain small {
  display: block;
}
.status-chain strong {
  color: #edf7fd;
  font-size: 14px;
}
.status-chain small {
  margin-top: 5px;
  color: #7f9db2;
  line-height: 1.45;
}
.status-chain li.current strong {
  color: #69d8ff;
}
.action-modules {
  display: grid;
  gap: 12px;
}
.action-module {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 12px;
  padding: 13px;
  border-radius: 8px;
  background: rgba(4, 13, 22, .48);
}
.module-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #8cb0c8;
  background: rgba(127, 177, 212, .12);
}
.action-module.done .module-icon {
  color: #0b241d;
  background: #7ee2bd;
}
.action-module.waiting .module-icon {
  color: #061724;
  background: #f0c75d;
}
.action-module.failed .module-icon,
.action-module.unconfigured .module-icon {
  color: #fff;
  background: #794151;
}
.module-body header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.module-body strong {
  color: #f3f9ff;
}
.module-body header span {
  color: #9eb9cb;
  font-size: 12px;
}
.module-body p {
  margin: 8px 0 10px;
  color: #94b0c3;
  line-height: 1.5;
}
.module-body dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.module-body dl div {
  min-width: 0;
}
.module-body dd {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sticky-action-bar {
  position: sticky;
  bottom: 16px;
  z-index: 5;
  margin-top: 16px;
  padding: 14px 16px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  box-shadow: 0 16px 42px rgba(0, 0, 0, .28);
}
.action-context span,
.action-context strong,
.action-context p {
  display: block;
}
.action-context span {
  color: #83b3d1;
  font-size: 13px;
}
.action-context strong {
  margin-top: 4px;
  color: #fff;
  font-size: 18px;
}
.action-context p {
  margin: 4px 0 0;
  color: #8faabd;
  font-size: 13px;
}
.decision-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
:global(.evidence-drawer.el-drawer) {
  background: #0b1d30;
}
:global(.evidence-drawer .el-drawer__header) {
  margin: 0;
  padding: 18px;
  color: #f3f8fd;
  border-bottom: 1px solid rgba(104, 161, 200, .16);
}
.evidence-drawer-list {
  display: grid;
  gap: 14px;
}
.evidence-drawer-list figure {
  margin: 0;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(5, 19, 31, .56);
}
.evidence-drawer-list .el-image {
  width: 100%;
  aspect-ratio: 16 / 9;
  display: block;
  background: #02090f;
}
.drawer-file {
  min-height: 180px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  background: #061523;
}
.drawer-file .el-icon {
  font-size: 34px;
  color: #9bc1d8;
}
.drawer-file a {
  max-width: 90%;
  overflow: hidden;
  color: #69d8ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-drawer-list figcaption {
  padding: 12px;
}
.evidence-drawer-list figcaption strong,
.evidence-drawer-list figcaption span,
.evidence-drawer-list figcaption small {
  display: block;
}
.evidence-drawer-list figcaption span,
.evidence-drawer-list figcaption small {
  margin-top: 6px;
  color: #85a3b8;
  font-size: 12px;
}
@keyframes nodePulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(105, 216, 255, .34);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(105, 216, 255, 0);
  }
}
@media (min-width: 1600px) {
  .event-command-page {
    max-width: 1720px;
    margin: 0 auto;
  }
}
@media (max-width: 1280px) {
  .incident-stage,
  .command-grid {
    grid-template-columns: 1fr;
  }
  .event-flow {
    min-width: 980px;
  }
}
@media (max-width: 760px) {
  .event-command-page {
    padding: 14px;
  }
  .command-topbar,
  .topbar-badges,
  .signal-grid,
  .sticky-action-bar {
    grid-template-columns: 1fr;
  }
  .topbar-badges,
  .decision-actions {
    justify-content: stretch;
  }
  .decision-actions .el-button {
    flex: 1;
  }
  .incident-brief {
    padding: 16px;
  }
  .scene-panel {
    padding: 12px;
  }
  .scene-visual,
  .scene-empty {
    min-height: 280px;
  }
}
</style>
