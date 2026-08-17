<template>
  <div class="event-workbench" v-loading="loading">
    <template v-if="event">
      <section class="major-flow" :class="{ 'is-resolved': isResolved }">
        <button type="button" class="flow-back-button" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回列表</span>
        </button>
        <ol class="flow-rail">
          <li
            v-for="(step, index) in mainFlowSteps"
            :key="step.key"
            :class="[step.state, { current: step.current }]"
            :title="step.detail"
          >
            <div class="flow-node">
              <el-icon><component :is="step.icon" /></el-icon>
            </div>
            <div class="flow-text">
              <strong>{{ step.title }}</strong>
              <span>{{ step.statusText }}</span>
              <time>{{ step.time }}</time>
            </div>
            <svg v-if="index < mainFlowSteps.length - 1" class="flow-connector" viewBox="0 0 220 28" aria-hidden="true">
              <path class="connector-base" d="M4 14 H216" />
              <path v-if="step.state === 'done' || step.state === 'running'" class="connector-fill" d="M4 14 H216" />
              <path d="M216 14 L204 7 M216 14 L204 21" />
            </svg>
          </li>
        </ol>
      </section>

      <section class="workspace-grid" :class="{ 'no-linkage': !showRightRail }">
        <main class="primary-stack">
          <section class="work-card detail-card">
            <header class="detail-hero">
              <div class="detail-title-block">
                <span>{{ eventKindLabel }} / 事件详情</span>
                <h2>{{ event.event_name || '安全事件详情' }}</h2>
                <p v-if="event.summary">{{ event.summary }}</p>
              </div>
              <div class="detail-status-block">
                <div class="detail-badges">
                  <span class="risk-badge" :class="riskClass(event.risk_level)">{{ riskLevelLabel(event.risk_level, event.risk_label) }}</span>
                  <span class="status-badge" :class="statusClass(event.status)">{{ statusLabel(event.status) }}</span>
                </div>
                <time>{{ formatTime(event.started_at) }}</time>
                <small>持续 {{ eventDuration }}</small>
              </div>
            </header>

            <dl class="detail-fields">
              <div v-for="field in detailFields" :key="field.key">
                <dt>{{ field.label }}</dt>
                <dd>{{ field.value }}</dd>
              </div>
            </dl>
          </section>

          <section class="work-card evidence-card" :class="{ empty: !reviewFrames.length }">
            <header class="card-heading">
              <div>
                <span>现场证据</span>
              </div>
              <small>{{ reviewFrames.length }} / 8 帧</small>
            </header>

            <div v-if="reviewFrames.length" class="review-frame-strip">
              <button
                v-for="(item, index) in reviewFrames"
                :key="item.id"
                type="button"
                class="review-frame-item"
                @click="openEvidenceItem(item)"
              >
                <el-image :src="normalizeMediaUrl(item.file_url)" fit="cover" />
                <footer>
                  <span>复核帧 {{ String(index + 1).padStart(2, '0') }}</span>
                </footer>
              </button>
              <div v-for="slot in Math.max(0, 8 - reviewFrames.length)" :key="`review-slot-${slot}`" class="review-frame-slot">
                <strong>{{ String(reviewFrames.length + slot).padStart(2, '0') }}</strong>
                <span>待归档</span>
              </div>
            </div>
            <div v-else class="compact-empty">
              <el-icon><Picture /></el-icon>
              <span>暂无 Qwen4B 抽取帧</span>
            </div>
          </section>

          <section class="work-card log-card">
            <header class="card-heading">
              <div>
                <span>处理日志</span>
                <h2>记录流</h2>
              </div>
              <small>{{ timeline.length }} 条</small>
            </header>

            <div v-if="timeline.length" class="log-stream">
              <article v-for="item in timeline" :key="item.id" :class="timelineTone(item)">
                <span class="log-type">{{ logTypeLabel(item.log_type) }}</span>
                <div class="log-body">
                  <strong>{{ logTitle(item) }}</strong>
                  <p v-if="logMessage(item)">{{ logMessage(item) }}</p>
                </div>
                <div class="log-source">
                  <span>{{ operatorLabel(item.operator) }}</span>
                  <time>{{ formatTime(item.create_time || item.created_at) }}</time>
                </div>
                <el-button
                  v-if="evidenceForLog(item.id).length"
                  link
                  type="primary"
                  :icon="Picture"
                  @click="openEvidence(item.id)"
                >
                  证据
                </el-button>
              </article>
            </div>
            <div v-else class="compact-empty">
              <span>暂无处理日志</span>
            </div>
          </section>
        </main>

        <aside v-if="showRightRail" class="side-stack">
          <section v-if="actionModules.length" class="work-card linkage-card">
            <header class="card-heading">
              <div>
                <span>联动执行</span>
                <h2>动作结果</h2>
              </div>
              <small>{{ actionModules.length }} 项</small>
            </header>

            <div class="linkage-list">
              <article v-for="module in actionModules" :key="module.key" :class="module.state">
                <div class="linkage-icon">
                  <el-icon><component :is="module.icon" /></el-icon>
                </div>
                <div class="linkage-body">
                  <header>
                    <strong>{{ module.title }}</strong>
                    <span>{{ module.statusText }}</span>
                  </header>
                  <dl>
                    <div v-for="meta in module.meta" :key="meta.label">
                      <dt>{{ meta.label }}</dt>
                      <dd>{{ meta.value }}</dd>
                    </div>
                  </dl>
                  <p>{{ module.summary }}</p>
                  <p v-if="module.failureReason" class="failure-reason">失败原因：{{ module.failureReason }}</p>
                </div>
              </article>
            </div>
          </section>

          <section v-if="event.analysis_report_document_id" class="work-card report-card">
            <header class="card-heading">
              <div>
                <span>处置报告</span>
                <h2>报告归档</h2>
              </div>
              <small>DOCX</small>
            </header>
            <button class="report-card-link" type="button" @click="openReport">
              <el-icon><Document /></el-icon>
              <span class="report-card-copy">
                <strong>{{ reportTitle }}</strong>
                <small>{{ displayEventId }} · 点击查看</small>
              </span>
              <span class="report-open-text">查看</span>
            </button>
          </section>

          <section class="work-card operation-card">
            <header class="card-heading">
              <div>
                <span>处置操作</span>
                <h2>{{ event.state === 'ACTIVE' ? '人工决策' : '归档状态' }}</h2>
              </div>
            </header>
            <div class="action-context">
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
            <div v-if="event.state !== 'ACTIVE'" class="closed-note">
              {{ archivedReason }}
            </div>
          </section>
        </aside>
      </section>
    </template>

    <el-empty v-else-if="!loading" description="未找到安全事件" />

    <el-drawer v-model="evidenceVisible" title="事件证据" class="evidence-drawer" size="560px">
      <div v-if="currentEvidence.length" class="evidence-drawer-list">
        <figure v-for="item in currentEvidence" :key="item.id">
          <el-image
            v-if="isImageEvidence(item)"
            :src="normalizeMediaUrl(item.file_url)"
            fit="cover"
            :preview-src-list="currentEvidence.filter(isImageEvidence).map((record) => normalizeMediaUrl(record.file_url))"
            preview-teleported
          />
          <div v-else class="drawer-file">
            <el-icon><Document /></el-icon>
            <a :href="normalizeMediaUrl(item.file_url)" target="_blank" rel="noreferrer">{{ normalizeMediaUrl(item.file_url) }}</a>
          </div>
          <figcaption>
            <strong>{{ item.description || evidenceTypeLabel(item.evidence_type) }}</strong>
            <span>{{ sourceLabel(item.source_type) }} · {{ formatTime(item.captured_at) }}</span>
            <small>关联动作：{{ relatedLogLabel(item.timeline_log_id) }}</small>
          </figcaption>
        </figure>
      </div>
      <div v-else class="compact-empty">当前节点暂无证据</div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  CircleCheckFilled,
  Connection,
  Document,
  Microphone,
  Picture,
  Promotion,
  User,
  WarningFilled,
} from '@element-plus/icons-vue'
import { getIntegrationConfig, getUnifiedSafetyEventDetail, operateUnifiedSafetyEvent } from '@/api/integration'
import { normalizeMediaUrl } from '@/utils/media'

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
  review_frames: [],
  tasks: [],
})
const actionConfigs = ref([])

const event = computed(() => detail.event)
const visualDetail = computed(() => detail.visual_detail)
const timeline = computed(() => detail.timeline)
const evidence = computed(() => detail.evidence)
const reviewFrames = computed(() => {
  const frames = Array.isArray(detail.review_frames) ? detail.review_frames : []
  const fallback = evidence.value.filter(isImageEvidence)
  return dedupeEvidenceFrames(frames.length ? frames : fallback).slice(0, 8)
})
const latestTask = computed(() => detail.tasks[0] || null)
const isResolved = computed(() => event.value?.state === 'RESOLVED' || ['COMPLETED', 'FALSE_ALARM'].includes(event.value?.status))
const eventActionConfigs = computed(() => actionConfigs.value.filter((item) => item.event_id === event.value?.event_id && item.enabled))
const eventKind = computed(() => {
  if (String(event.value?.source_type || '').toLowerCase() === 'sensor') return 'sensor'
  if (visualDetail.value || String(event.value?.source_type || '').toLowerCase() === 'camera') return 'vision'
  return 'generic'
})
const eventKindLabel = computed(() => ({ vision: '视觉事件', sensor: '传感器事件', generic: '统一事件' })[eventKind.value])
const showRightRail = computed(() => Boolean(event.value))

const eventDuration = computed(() => {
  if (!event.value?.started_at) return '--'
  const end = event.value.resolved_at || event.value.last_observed_at || new Date()
  return formatDuration(event.value.started_at, end)
})

const needsManual = computed(() => {
  if (latestTask.value) return true
  if (event.value?.risk_level === 'HIGH' && event.value?.state === 'ACTIVE') return true
  return logsForModule('manual').length > 0
})

const autoCloseText = computed(() => {
  if (!isResolved.value) return ''
  if (logsForModule('manual').length || latestTask.value) return '人工闭环'
  return '自动闭环'
})
const archivedReason = computed(() => {
  return localizeText(event.value?.resolve_reason) || '事件已闭环归档，不能继续执行人工操作'
})
const displayEventId = computed(() => formatDisplayEventId(event.value))
const reportTitle = computed(() => {
  const name = String(event.value?.event_name || event.value?.summary || '').trim()
  const baseTitle = name
    ? (name.includes('事件') ? `${name}处置报告` : `${name}事件处置报告`)
    : '事件处置报告'
  return displayEventId.value && !baseTitle.includes(displayEventId.value)
    ? `${baseTitle}_${displayEventId.value}`
    : baseTitle
})

const sensorSourceNames = {
  1: '温湿度传感器',
  2: '风速风向传感器',
  3: '雨量计',
  4: '振动传感器',
  temp_humidity: '温湿度传感器',
  wind: '风速风向传感器',
  rain: '雨量计',
  vibration: '振动传感器',
}

const detailSchemas = {
  vision: [
    ['camera', '摄像头 / 点位', () => visualDetail.value?.camera_name || event.value?.source_name || sourceLabel(event.value?.source_type)],
    ['target', '目标类型', () => targetLabel(visualDetail.value?.target_type)],
    ['zone', '检测区域', () => visualDetail.value?.zone_name],
    ['confidence', '置信度', () => confidenceText(visualDetail.value?.confidence)],
    ['started', '首次发现', () => formatTime(event.value?.started_at)],
    ['last', '最近观测', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['reason', '触发原因', () => event.value?.summary],
  ],
  sensor: [
    ['sensor', '传感器名称', () => sensorSourceName()],
    ['monitor', '监测类型', () => eventCategoryLabel(event.value?.event_category)],
    ['started', '首次触发', () => formatTime(event.value?.started_at)],
    ['last', '最近更新时间', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['area', '所属区域', () => event.value?.area_name || event.value?.zone_name],
    ['reason', '触发原因', () => event.value?.summary],
  ],
  generic: [
    ['source', '事件来源', () => sourceLabel(event.value?.source_type)],
    ['started', '首次触发', () => formatTime(event.value?.started_at)],
    ['last', '最近更新时间', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['reason', '触发原因', () => event.value?.summary],
  ],
}

const detailFields = computed(() => {
  const schema = detailSchemas[eventKind.value] || detailSchemas.generic
  const fields = schema.map(([key, label, getter]) => ({ key, label, value: getter() })).filter((item) => hasValue(item.value))
  const common = [
    { key: 'instance', label: '事件 ID', value: displayEventId.value },
    { key: 'manual', label: '是否需要人工处置', value: needsManual.value ? '需要' : '不需要' },
    { key: 'closeMode', label: '闭环方式', value: autoCloseText.value },
  ].filter((item) => hasValue(item.value))
  return [...fields, ...common]
})

const mainFlowSteps = computed(() => {
  const failedAction = timeline.value.find((item) => isFailedStatus(item.status))
  const actionLog = firstLog((item) => item.log_type === 'ACTION')
  const manualLog = firstLog((item) => item.log_type === 'MANUAL')
  const resolveLog = firstLog((item) => item.log_type === 'RESOLVE')
  const hasLinkage = Boolean(actionLog || manualLog || latestTask.value)
  const linkageFailed = Boolean(failedAction)
  const linkageState = linkageFailed
    ? 'failed'
    : isResolved.value && hasLinkage
      ? 'done'
      : hasLinkage
        ? 'running'
        : eventActionConfigs.value.length
          ? 'pending'
          : 'skipped'
  const archiveState = isResolved.value ? 'done' : linkageState === 'failed' ? 'pending' : 'pending'
  const steps = [
    {
      key: 'trigger',
      title: '事件触发',
      state: 'done',
      statusText: '已触发',
      time: formatShortTime(event.value?.started_at),
      detail: event.value?.summary || '安全事件实例已创建',
      icon: WarningFilled,
    },
    {
      key: 'route',
      title: '智能路由',
      state: 'done',
      statusText: '已路由',
      time: formatShortTime(firstLog((item) => item.log_type === 'TRIGGER')?.create_time || event.value?.started_at),
      detail: event.value?.event_name || '系统已匹配事件定义',
      icon: Promotion,
    },
    {
      key: 'linkage',
      title: '联动处理',
      state: linkageState,
      statusText: stepStatusText(linkageState),
      time: formatShortTime((failedAction || actionLog || manualLog)?.create_time),
      detail: linkageFailed ? failedAction.message : hasLinkage ? '已产生联动或人工处置记录' : '当前事件未产生联动动作',
      icon: Connection,
    },
    {
      key: 'archive',
      title: '闭环归档',
      state: archiveState,
      statusText: isResolved.value ? '已处置' : '未开始',
      time: formatShortTime(resolveLog?.create_time || event.value?.resolved_at),
      detail: event.value?.resolve_reason || '等待事件闭环',
      icon: CircleCheckFilled,
    },
  ]
  const currentIndex = steps.findIndex((item) => item.state === 'running' || item.state === 'failed' || item.state === 'pending')
  return steps.map((item, index) => ({ ...item, current: index === currentIndex }))
})

const actionModules = computed(() => {
  const modules = [
    buildActionModule({
      key: 'broadcast',
      title: '广播',
      types: ['broadcast'],
      icon: Microphone,
      objectLabel: '设备',
      objectValue: (config) => config?.broadcast_device_name,
    }),
    buildActionModule({
      key: 'drone',
      title: '无人机',
      types: ['drone_dispatch'],
      icon: Connection,
      objectLabel: '航线 / 设备',
      objectValue: (config) => config?.route_id ? `航线 ${config.route_id}` : config?.drone_id,
    }),
    buildActionModule({
      key: 'manual',
      title: '人工处置',
      types: ['staff_task'],
      icon: User,
      objectLabel: '责任人',
      objectValue: () => latestTask.value?.assignee || latestTask.value?.dispatch_operator,
      forceVisible: Boolean(latestTask.value || logsForModule('manual').length),
    }),
  ]
  return modules.filter(Boolean)
})

const primaryAction = computed(() => {
  if (event.value?.state !== 'ACTIVE') {
    return { title: '事件已归档', hint: archivedReason.value, label: '已归档', action: 'RESOLVE', disabled: true }
  }
  if (event.value.risk_level === 'HIGH') {
    if (latestTask.value?.status === 'ACCEPTED' || latestTask.value?.status === 'PROCESSING') {
      return { title: '等待现场结果', hint: '完成现场确认后提交结果，事件将进入闭环。', label: '完成现场处置', action: 'COMPLETE_TASK' }
    }
    return { title: '需要人工接管', hint: '高风险事件需要先接受处置任务。', label: '接受处置', action: 'ACCEPT_TASK' }
  }
  return { title: '无需强制人工处置', hint: '确认事件真实性后可直接闭环，也可以升级风险。', label: '确认闭环', action: 'RESOLVE' }
})

const secondaryActions = computed(() => {
  if (event.value?.state !== 'ACTIVE') {
    return [
      { label: '升级风险', action: 'UPGRADE', type: 'danger', disabled: true },
      { label: '标记误报', action: 'FALSE_ALARM', type: 'default', disabled: true },
      { label: '完成闭环', action: 'RESOLVE', type: 'primary', disabled: true },
    ]
  }
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
    detail.review_frames = Array.isArray(data.review_frames) ? data.review_frames : []
    detail.tasks = Array.isArray(data.tasks) ? data.tasks : []
    actionConfigs.value = configResult.status === 'fulfilled' && Array.isArray(configResult.value.data?.action_configs)
      ? configResult.value.data.action_configs
      : []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '安全事件详情暂时不可达')
  } finally {
    loading.value = false
  }
}

function buildActionModule(options) {
  const logs = logsForModule(options.key)
  if (!logs.length && !options.forceVisible) return null
  const failed = logs.find((item) => isFailedStatus(item.status))
  const last = logs[logs.length - 1]
  const config = configsForModule(options.types)[0]
  const state = failed ? 'failed' : event.value?.state === 'ACTIVE' && last ? 'running' : 'done'
  const objectValue = options.objectValue(config) || '未记录'
  return {
    key: options.key,
    title: options.title,
    icon: options.icon,
    state,
    statusText: state === 'failed' ? '失败' : state === 'running' ? '执行中' : '已完成',
    summary: localizeText(failed?.message || last?.message || latestTask.value?.note || '已产生处置记录'),
    failureReason: localizeText(failed?.message || ''),
    meta: [
      { label: '对象', value: objectValue },
      { label: '执行时间', value: formatTime(last?.create_time || last?.created_at || latestTask.value?.completed_at || latestTask.value?.accepted_at) },
    ].filter((item) => hasValue(item.value)),
  }
}

function configsForModule(types) {
  return eventActionConfigs.value.filter((config) => types.includes(config.action_type))
}

function logsForModule(key) {
  const includes = {
    broadcast: ['broadcast', '广播', '喊话'],
    drone: ['drone', 'uav', '无人机', '派飞'],
    manual: ['manual', '人工', '处置', '接单', '工作人员'],
  }[key] || []
  return timeline.value.filter((item) => {
    const text = `${item.log_type || ''} ${item.title || ''} ${item.message || ''} ${item.action || ''}`.toLowerCase()
    return includes.some((keyword) => text.includes(keyword))
  })
}

function firstLog(predicate) {
  return timeline.value.find(predicate)
}

function hasValue(value) {
  return value !== undefined && value !== null && value !== '' && value !== '--'
}

function stepStatusText(state) {
  return ({ done: '已完成', running: '进行中', pending: '未开始', skipped: '已跳过', failed: '异常' })[state] || state
}

function goBack() {
  router.push('/workspace/safety-events')
}

function openReport() {
  if (!event.value?.analysis_report_document_id) return
  router.push({
    name: 'DocumentEditor',
    params: { documentId: event.value.analysis_report_document_id },
    query: { mode: 'view', title: reportTitle.value },
  })
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

function isFailedStatus(value) {
  return ['FAILED', 'FAIL', 'ERROR'].includes(String(value || '').toUpperCase())
}

function isImageEvidence(item) {
  const type = String(item?.evidence_type || '').toUpperCase()
  const url = String(item?.file_url || '').split('?')[0].toLowerCase()
  return type === 'IMAGE' || /\.(png|jpe?g|webp|gif|bmp)$/.test(url)
}

function dedupeEvidenceFrames(items) {
  const seen = new Set()
  return items.reduce((result, item, index) => {
    const url = String(item?.file_url || '').trim()
    if (!url || seen.has(url)) return result
    seen.add(url)
    result.push({
      ...item,
      id: item.id || `review-frame-${index + 1}`,
      evidence_type: item.evidence_type || 'IMAGE',
      source_type: item.source_type || 'SYSTEM',
    })
    return result
  }, [])
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
  return ({ TRIGGER: '事件触发', RECOVERY: '条件恢复', WORKFLOW: '工作流', DAM_WORKFLOW: '智能路由', ACTION: '联动动作', REPORT: '报告', MANUAL: '人工操作', RESOLVE: '闭环', SYSTEM: '系统记录', RISK_CHANGE: '风险变化' })[value] || localizeText(value) || '记录'
}

function logTitle(item) {
  return localizeText(item?.title || item?.message || item?.action || '事件记录')
}

function logMessage(item) {
  if (!item?.title || !item?.message) return ''
  const message = localizeText(item.message)
  return message === logTitle(item) ? '' : message
}

function timelineTone(item) {
  if (isFailedStatus(item?.status)) return 'is-failed'
  return ({ TRIGGER: 'is-trigger', DAM_WORKFLOW: 'is-action', WORKFLOW: 'is-action', RISK_CHANGE: 'is-warning', ACTION: 'is-action', RESOLVE: 'is-resolve', MANUAL: 'is-manual' })[item?.log_type] || 'is-system'
}

function targetLabel(value) {
  return ({
    person: '人员',
    boat: '船只',
    vehicle: '车辆',
    fire: '火点',
    qwen_camera_screening: '智能视觉复核',
    camera_screening: '视觉筛查',
  })[value] || localizeText(value) || ''
}

function sourceLabel(value) {
  return ({ CAMERA: '摄像头', DRONE: '无人机', STAFF: '人工上传', SYSTEM: '系统', camera: '摄像头', sensor: '传感器' })[value] || value || ''
}

function sensorSourceName() {
  const sourceName = event.value?.source_name
  if (sourceName && sourceName !== 'sensor') return sourceName
  const sourceId = event.value?.source_id
  if (sensorSourceNames[sourceId]) return sensorSourceNames[sourceId]
  return sensorSourceNames[String(sourceId)] || sourceLabel(event.value?.source_type)
}

function formatDisplayEventId(row) {
  if (!row) return ''
  if (row.display_instance_no) return row.display_instance_no
  const text = String(row.instance_no || '').trim()
  const date = dateToken(text) || dateToken(row.started_at)
  if (!date) return row.instance_no || ''
  const sequence = instanceSequence(text) || 1
  const shortSequence = String(sequence || 1).padStart(3, '0')
  return `EVT_${date}_${shortSequence}`
}

function dateToken(value) {
  if (!value) return ''
  const direct = String(value).match(/20\d{6}/)
  if (direct) return direct[0]
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

function instanceSequence(value) {
  const text = String(value || '')
  const matched = text.match(/_(\d{1,4})$/)
  return matched?.[1] || ''
}

function eventCategoryLabel(value) {
  return ({
    PERSON_SAFETY: '人员安全',
    ILLEGAL_FISHING: '非法捕捞',
    SENSOR: '传感器监测',
    ENVIRONMENT: '环境监测',
  })[value] || localizeText(value) || ''
}

function evidenceTypeLabel(value) {
  return ({ IMAGE: '图片证据', VIDEO: '视频证据', FILE: '文件证据' })[value] || value || '证据文件'
}

function operatorLabel(value) {
  if (!value) return '系统记录'
  return value === 'SYSTEM' ? '系统自动' : value
}

function localizeText(value) {
  if (!value) return ''
  let text = String(value)
  const replacements = [
    ['DAM_WORKFLOW', '智能路由'],
    ['qwen_camera_screening', '智能视觉复核'],
    ['camera_screening', '视觉筛查'],
    ['camera_condition_recovered', '摄像头条件已恢复'],
    ['condition_recovered', '触发条件已恢复'],
    ['PERSON_SAFETY', '人员安全'],
    ['ILLEGAL_FISHING', '非法捕捞'],
    ['TRIGGER', '事件触发'],
    ['RECOVERY', '条件恢复'],
    ['WORKFLOW', '工作流'],
    ['ACTION', '联动动作'],
    ['REPORT', '报告'],
    ['MANUAL', '人工操作'],
    ['RESOLVE', '闭环'],
    ['SYSTEM', '系统'],
    ['SUCCESS', '成功'],
    ['FAILED', '失败'],
    ['failed', '失败'],
    ['success', '成功'],
    ['PENDING', '待处理'],
    ['PROCESSING', '处理中'],
    ['COMPLETED', '已完成'],
    ['FALSE_ALARM', '误报'],
    ['broadcast', '广播'],
    ['drone_dispatch', '无人机派飞'],
    ['staff_task', '人工处置任务'],
    ['manual-operation', '人工操作'],
    ['manual operation', '人工操作'],
  ]
  replacements.forEach(([from, to]) => {
    text = text.replaceAll(from, to)
  })
  return text.replaceAll('_', ' ')
}

function relatedLogLabel(logId) {
  const log = timeline.value.find((item) => item.id === logId)
  return log ? (log.title || logTypeLabel(log.log_type)) : '未关联日志'
}

function confidenceText(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : ''
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', { hour12: false })
}

function formatShortTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
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
.event-workbench {
  position: relative;
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background:
    radial-gradient(circle at 50% -20%, rgba(42, 111, 151, .22), transparent 34%),
    linear-gradient(180deg, #081827 0%, #050d18 100%);
}
.risk-badge,
.status-badge {
  min-width: 78px;
  padding: 7px 10px;
  border-radius: 6px;
  text-align: center;
  background: rgba(12, 34, 54, .95);
}
.risk-badge.risk-high {
  color: #ffd6da;
  background: rgba(150, 39, 54, .58);
}
.risk-badge.risk-medium {
  color: #ffe7ac;
  background: rgba(142, 102, 22, .5);
}
.risk-badge.risk-low {
  color: #c9f7e4;
  background: rgba(30, 111, 86, .5);
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
.major-flow {
  position: sticky;
  top: 0;
  z-index: 20;
  margin-top: 0;
  min-height: 132px;
  padding: 20px 26px 22px;
  overflow: hidden;
  border-radius: 8px;
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 24px;
  align-items: center;
  background:
    linear-gradient(180deg, rgba(12, 35, 55, .86), rgba(7, 22, 36, .96)),
    rgba(8, 23, 39, .96);
  backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .08), 0 18px 38px rgba(0, 0, 0, .28);
}
.flow-back-button {
  position: relative;
  z-index: 4;
  width: fit-content;
  height: 42px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 15px 0 13px;
  border: 1px solid rgba(104, 161, 200, .2);
  border-radius: 999px;
  color: #9fc0d5;
  background: rgba(4, 16, 27, .34);
  cursor: pointer;
}
.flow-back-button:hover {
  color: #eff9ff;
  border-color: rgba(105, 216, 255, .42);
  background: rgba(10, 38, 60, .72);
}
.flow-back-button .el-icon {
  font-size: 15px;
}
.flow-rail {
  position: relative;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  list-style: none;
}
.flow-rail li {
  position: relative;
  min-width: 0;
  display: block;
  padding-right: 20px;
}
.flow-node {
  position: relative;
  z-index: 2;
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(110, 160, 194, .28);
  border-radius: 12px;
  color: #93afc3;
  background: rgba(8, 25, 42, .9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .06),
    0 10px 18px rgba(0, 0, 0, .18);
}
.flow-node::before {
  content: "";
  position: absolute;
  inset: auto auto 8px 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  opacity: .72;
  box-shadow: 0 0 10px currentColor;
}
.flow-node .el-icon {
  position: relative;
  z-index: 1;
  font-size: 24px;
}
.flow-text {
  position: relative;
  z-index: 2;
  margin-top: 10px;
  min-width: 0;
}
.flow-text strong,
.flow-text span,
.flow-text time {
  display: block;
}
.flow-text strong {
  color: #f5fbff;
  font-size: 19px;
  line-height: 1.2;
}
.flow-text span {
  width: fit-content;
  margin-top: 7px;
  padding: 3px 8px;
  border-radius: 999px;
  color: #8fb2c9;
  font-size: 13px;
  background: rgba(126, 171, 202, .1);
}
.flow-text time {
  margin-top: 5px;
  min-height: 17px;
  color: #7898ad;
  font-size: 12px;
}
.flow-rail li.done .flow-node {
  border-color: rgba(102, 215, 178, .48);
  color: #66d7b2;
  background: rgba(20, 74, 61, .34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 10px 18px rgba(0, 0, 0, .18);
}
.flow-rail li.running .flow-node {
  border-color: rgba(72, 216, 255, .58);
  color: #48d8ff;
  background: rgba(21, 79, 105, .34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 10px 18px rgba(0, 0, 0, .18),
    0 0 0 3px rgba(72, 216, 255, .08);
  animation: subtlePulse 1.8s ease-in-out infinite;
}
.flow-rail li.pending .flow-node {
  border-color: rgba(120, 152, 173, .28);
  color: #7898ad;
  background: rgba(8, 25, 42, .86);
}
.flow-rail li.skipped .flow-node {
  border-color: rgba(120, 152, 173, .18);
  color: #6f8798;
  background: rgba(18, 32, 48, .72);
}
.flow-rail li.failed .flow-node {
  border-color: rgba(255, 107, 118, .56);
  color: #ff6b76;
  background: rgba(110, 34, 47, .38);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 10px 18px rgba(0, 0, 0, .18),
    0 0 0 3px rgba(255, 107, 118, .08);
}
.flow-rail li.current .flow-text strong {
  color: #69d8ff;
}
.flow-rail li.done .flow-text span,
.major-flow.is-resolved .flow-text span {
  color: #a9e9d4;
}
.flow-connector {
  position: absolute;
  left: 66px;
  top: 14px;
  width: calc(100% - 84px);
  height: 28px;
  overflow: visible;
}
.flow-connector path {
  fill: none;
  stroke: rgba(120, 152, 173, .3);
  stroke-width: 2;
  stroke-linecap: round;
}
.connector-fill {
  stroke: #7ee2bd;
  stroke-dasharray: none;
  animation: none;
}
.major-flow.is-resolved .connector-fill {
  stroke-dasharray: none;
  animation: none;
}
.flow-rail li.failed .connector-fill {
  stroke: #d85667;
}
.flow-rail li.skipped .connector-fill {
  stroke: rgba(143, 164, 178, .42);
  stroke-dasharray: 4 8;
}
.workspace-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
  align-items: start;
}
.side-stack {
  position: sticky;
  top: 16px;
  display: grid;
  gap: 16px;
  align-self: start;
}
.workspace-grid.no-linkage {
  grid-template-columns: minmax(0, 1fr);
}
.primary-stack {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.work-card {
  min-width: 0;
  padding: 20px;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(13, 38, 60, .88), rgba(8, 25, 42, .88)),
    rgba(10, 29, 48, .88);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .07), 0 14px 34px rgba(0, 0, 0, .16);
}
.detail-card {
  position: relative;
  overflow: hidden;
}
.detail-card::after {
  content: "";
  position: absolute;
  top: 18px;
  right: 0;
  width: 4px;
  height: 150px;
  border-radius: 999px 0 0 999px;
  background: linear-gradient(180deg, #69d8ff, rgba(105, 216, 255, .08));
}
.detail-hero {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 20px;
  align-items: start;
  padding-bottom: 18px;
}
.detail-title-block {
  min-width: 0;
}
.detail-title-block span,
.card-heading span {
  display: block;
  color: #7fb1d4;
  font-size: 13px;
}
.detail-title-block h2 {
  margin: 6px 0 8px;
  color: #f9fdff;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: 0;
}
.detail-title-block p {
  margin: 0;
  color: #9fbed2;
  font-size: 15px;
  line-height: 1.55;
}
.detail-status-block {
  min-width: 230px;
  display: grid;
  justify-items: end;
  gap: 8px;
  color: #8faabd;
  font-size: 13px;
}
.detail-badges {
  display: flex;
  gap: 8px;
}
.detail-status-block time,
.detail-status-block small {
  display: block;
}
.card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.card-heading h2 {
  margin: 4px 0 0;
  color: #f4f9fd;
  font-size: 20px;
  letter-spacing: 0;
}
.card-heading small {
  color: #7f9eb3;
}
.evidence-card,
.log-card,
.linkage-card {
  background:
    linear-gradient(180deg, rgba(11, 34, 54, .82), rgba(7, 22, 37, .86)),
    rgba(8, 25, 42, .88);
}
.detail-fields {
  position: relative;
  z-index: 1;
  margin: 2px 0 0;
  padding-top: 18px;
  border-top: 1px solid rgba(126, 171, 202, .1);
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px 22px;
}
.detail-fields div {
  min-width: 0;
  padding: 12px 14px;
  border-radius: 7px;
  background: rgba(4, 14, 24, .32);
}
dt {
  color: #78a0ba;
  font-size: 12px;
}
dd {
  margin: 8px 0 0;
  overflow-wrap: anywhere;
  color: #eef7fc;
  font-size: 16px;
  line-height: 1.45;
}
.evidence-card.empty {
  padding-bottom: 14px;
}
.review-frame-strip {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 2px 8px 0;
  scroll-snap-type: x mandatory;
  scrollbar-width: thin;
  scrollbar-color: rgba(105, 216, 255, .42) rgba(4, 13, 22, .45);
}
.review-frame-item,
.review-frame-slot {
  flex: 0 0 clamp(220px, 23vw, 320px);
  aspect-ratio: 16 / 9;
  border: 1px solid rgba(105, 216, 255, .18);
  border-radius: 8px;
  scroll-snap-align: start;
}
.review-frame-item {
  position: relative;
  overflow: hidden;
  padding: 0;
  color: #e9f7ff;
  text-align: left;
  background: #020b13;
  cursor: pointer;
}
.review-frame-item .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.review-frame-item::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 42%, rgba(0, 0, 0, .78));
}
.review-frame-item:hover {
  border-color: rgba(105, 216, 255, .58);
}
.review-frame-item footer {
  position: absolute;
  z-index: 1;
  left: 10px;
  right: 10px;
  bottom: 10px;
}
.review-frame-item footer span,
.review-frame-item footer time {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-frame-item footer span {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.review-frame-item footer time {
  margin-top: 4px;
  color: #a9c5d6;
  font-size: 12px;
}
.review-frame-slot {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  color: #53758c;
  background: rgba(4, 13, 22, .42);
}
.review-frame-slot strong {
  color: #6f91a8;
  font-size: 18px;
}
.review-frame-slot span {
  color: #6f8798;
  font-size: 12px;
}
.evidence-grid {
  max-height: 440px;
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 14px;
  overflow-y: auto;
  padding-right: 2px;
}
.evidence-grid.single {
  grid-template-columns: minmax(320px, 520px);
}
.evidence-item {
  position: relative;
  height: 156px;
  overflow: hidden;
  border: 0;
  border-radius: 8px;
  color: #e9f7ff;
  text-align: left;
  background: linear-gradient(180deg, #082033, #061523);
  box-shadow: 0 10px 24px rgba(0, 0, 0, .18);
  cursor: pointer;
}
.evidence-grid.single .evidence-item {
  height: 260px;
}
.evidence-item .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.evidence-item::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 34%, rgba(0, 0, 0, .76));
}
.evidence-item:hover {
  outline: 2px solid rgba(105, 216, 255, .45);
}
.file-evidence {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #bdd8e9;
}
.file-evidence .el-icon {
  font-size: 32px;
}
.evidence-item footer {
  position: absolute;
  z-index: 1;
  left: 12px;
  right: 12px;
  bottom: 12px;
}
.evidence-item footer span,
.evidence-item footer time {
  display: block;
}
.evidence-item footer span {
  overflow: hidden;
  color: #fff;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-item footer time {
  margin-top: 5px;
  color: #a9c5d6;
  font-size: 12px;
}
.compact-empty {
  min-height: 78px;
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #86a5ba;
  border-radius: 8px;
  background: rgba(4, 13, 22, .34);
}
.compact-empty .el-icon {
  font-size: 24px;
}
.linkage-list {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}
.linkage-list article {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border-radius: 8px;
  background: rgba(4, 13, 22, .38);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .05);
}
.linkage-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #08251d;
  background: #7ee2bd;
}
.linkage-list article.running .linkage-icon {
  color: #061927;
  background: #69d8ff;
}
.linkage-list article.failed .linkage-icon {
  color: #fff;
  background: #d85667;
}
.linkage-body header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.linkage-body strong {
  color: #f4f9fd;
}
.linkage-body header span {
  color: #9eb9cb;
  font-size: 12px;
}
.linkage-body dl {
  margin: 12px 0 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.linkage-body p {
  margin: 12px 0 0;
  color: #95b1c4;
  line-height: 1.5;
}
.failure-reason {
  color: #ffb8c1;
}
.log-stream {
  margin-top: 16px;
  display: grid;
  gap: 6px;
}
.log-stream article {
  display: grid;
  grid-template-columns: 126px minmax(0, 1fr) 164px auto;
  gap: 12px;
  align-items: center;
  min-height: 54px;
  padding: 10px 12px 10px 14px;
  border-radius: 7px;
  background: rgba(4, 13, 22, .34);
  box-shadow: inset 3px 0 0 rgba(126, 171, 202, .16);
}
.log-stream article.is-trigger {
  box-shadow: inset 3px 0 0 rgba(105, 216, 255, .55);
}
.log-stream article.is-action {
  box-shadow: inset 3px 0 0 rgba(105, 216, 255, .36);
}
.log-stream article.is-warning {
  box-shadow: inset 3px 0 0 rgba(240, 199, 93, .52);
}
.log-stream article.is-resolve,
.log-stream article.is-manual {
  box-shadow: inset 3px 0 0 rgba(126, 226, 189, .45);
}
.log-stream article.is-failed {
  box-shadow: inset 3px 0 0 rgba(216, 86, 103, .6);
}
.log-type {
  width: 100%;
  max-width: 126px;
  padding: 5px 8px;
  overflow: hidden;
  border-radius: 6px;
  color: #b8d1e2;
  font-size: 12px;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(126, 171, 202, .1);
}
.log-stream article.is-trigger .log-type,
.log-stream article.is-action .log-type {
  color: #91ddff;
}
.log-stream article.is-warning .log-type {
  color: #f0c75d;
}
.log-stream article.is-resolve .log-type,
.log-stream article.is-manual .log-type {
  color: #a9e9d4;
}
.log-stream article.is-failed .log-type {
  color: #ffb8c1;
}
.log-body strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #f0f7fc;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.log-body p {
  margin: 5px 0 0;
  min-width: 0;
  overflow: hidden;
  color: #8eaabd;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.log-source {
  color: #7f9eb3;
  font-size: 12px;
  text-align: right;
}
.log-source span,
.log-source time {
  display: block;
}
.log-source time {
  margin-top: 4px;
}
.operation-card {
  background:
    linear-gradient(180deg, rgba(14, 42, 64, .88), rgba(8, 24, 39, .92)),
    rgba(10, 29, 48, .9);
}
.report-card {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(17, 52, 79, .94), rgba(8, 25, 42, .9)),
    rgba(8, 25, 42, .88);
}
.report-card::after {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, #69d8ff, rgba(126, 226, 189, .55), transparent);
}
.report-card-link {
  position: relative;
  width: 100%;
  margin-top: 14px;
  padding: 14px 14px 14px 16px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border: 1px solid rgba(105, 216, 255, .34);
  border-radius: 8px;
  color: #dcefff;
  text-align: left;
  background:
    linear-gradient(180deg, rgba(8, 28, 45, .86), rgba(4, 13, 22, .72)),
    rgba(4, 13, 22, .38);
  cursor: pointer;
}
.report-card-link:hover {
  border-color: rgba(105, 216, 255, .7);
  background:
    linear-gradient(180deg, rgba(13, 45, 70, .92), rgba(5, 18, 30, .76)),
    rgba(15, 49, 75, .62);
}
.report-card-link .el-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #061927;
  background: #69d8ff;
  font-size: 24px;
}
.report-card-copy,
.report-card-link strong,
.report-card-link small {
  display: block;
  min-width: 0;
}
.report-card-link strong {
  display: -webkit-box;
  color: #f4f9fd;
  font-size: 15px;
  line-height: 1.4;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.report-card-link small {
  margin-top: 5px;
  color: #8fd2f2;
  font-size: 12px;
}
.report-open-text {
  padding: 5px 10px;
  border-radius: 6px;
  color: #061927;
  background: #8bdcff;
  font-size: 12px;
  font-weight: 800;
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
  margin-top: 14px;
  color: #fff;
  font-size: 18px;
}
.action-context p {
  margin: 4px 0 0;
  color: #8faabd;
  font-size: 13px;
}
.decision-actions {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 10px;
}
.decision-actions .el-button {
  margin-left: 0;
}
.closed-note {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 7px;
  color: #91adbf;
  line-height: 1.5;
  background: rgba(4, 13, 22, .34);
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
@keyframes subtlePulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(105, 216, 255, .28);
  }
  50% {
    box-shadow: 0 0 0 9px rgba(105, 216, 255, 0);
  }
}
@keyframes flowMove {
  to {
    stroke-dashoffset: -20;
  }
}
@media (min-width: 1600px) {
  .event-workbench {
    max-width: 1720px;
    margin: 0 auto;
  }
}
@media (max-width: 1280px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
  .side-stack {
    position: static;
  }
  .detail-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .major-flow {
    padding: 22px;
    min-height: 0;
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .flow-back-button {
    width: fit-content;
  }
  .detail-hero {
    grid-template-columns: 1fr;
  }
  .detail-status-block {
    min-width: 0;
    justify-items: start;
  }
  .flow-rail {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .flow-rail li {
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr);
    gap: 14px;
    align-items: center;
    padding-right: 0;
  }
  .flow-node {
    width: 50px;
    height: 50px;
  }
  .flow-text {
    margin-top: 0;
  }
  .flow-connector {
    display: none;
  }
  .log-stream article {
    grid-template-columns: 1fr;
  }
  .log-source {
    text-align: left;
  }
}
@media (max-width: 640px) {
  .event-workbench {
    padding: 14px;
  }
  .detail-title-block h2 {
    font-size: 24px;
  }
  .detail-fields,
  .linkage-body dl {
    grid-template-columns: 1fr;
  }
  .evidence-grid,
  .evidence-grid.single {
    grid-template-columns: 1fr;
  }
  .decision-actions .el-button {
    flex: 1;
  }
}
</style>
