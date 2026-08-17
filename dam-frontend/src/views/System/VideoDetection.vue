<template>
  <div class="screening-page">
    <header class="page-header admin-header">
      <div class="title-block">
        <h2>视频测试</h2>
        <p>上传视频进行画面分析，联动触发事件处置与报告归档</p>
      </div>
    </header>

    <section class="workspace">
      <div class="media-panel">
        <header class="panel-header">
          <div>
            <span class="section-index">01</span>
            <div><small>VIDEO</small><h3>摄像头画面模拟</h3></div>
          </div>
          <div class="media-tools">
            <div class="runtime-state">
              <i :class="{ live: simulationActive }"></i>
              {{ mediaStatus }}
            </div>
            <el-button
              type="warning"
              plain
              :disabled="simulationActive || screening"
              @click="openSupplementDialog"
            >
              {{ specialContextButtonText }}
            </el-button>
            <el-button
              type="primary"
              :icon="simulationActive ? VideoPause : VideoPlay"
              :disabled="!videoUrl"
              @click="toggleSimulation"
            >
              {{ simulationActive ? '暂停模拟' : '开始模拟' }}
            </el-button>
          </div>
        </header>

        <div class="video-stage">
          <input
            ref="fileInputRef"
            class="hidden-file-input"
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.m4v"
            @change="handleNativeVideoFile"
          />
          <video
            v-if="videoUrl"
            ref="videoRef"
            :src="videoUrl"
            controls
            playsinline
            @ended="handleVideoEnded"
            @pause="handleNativePause"
          />
          <button v-else class="empty-stage" type="button" @click="openVideoPicker">
            <el-icon><VideoCamera /></el-icon>
            <strong>选择本地视频</strong>
            <span>MP4、MOV、WEBM 或 M4V</span>
          </button>
        </div>

        <div class="evidence-strip">
          <div class="strip-title">
            <span>复核帧</span>
            <b>{{ evidenceFrames.length }} / {{ FRAME_COUNT }} 帧</b>
          </div>
          <div class="frame-strip">
            <figure v-for="(frame, index) in evidenceFrames" :key="frame.id">
              <img v-if="!frame.failed" :src="frame.url" :alt="`模型复核帧 ${index + 1}`" @error="markFrameFailed(frame)" />
              <div v-else class="frame-error">复核帧加载失败</div>
              <span>{{ frame.label || `复核帧 ${String(index + 1).padStart(2, '0')}` }}</span>
            </figure>
            <div v-for="slot in Math.max(0, FRAME_COUNT - evidenceFrames.length)" :key="`slot-${slot}`" class="frame-slot">
              <b>{{ String(evidenceFrames.length + slot).padStart(2, '0') }}</b>
              <span>{{ frameSlotLabel }}</span>
            </div>
          </div>
        </div>
      </div>

      <aside class="result-panel">
        <header class="panel-header">
          <div>
            <span class="section-index">02</span>
            <div><small>PROCESS</small><h3>处理链路</h3></div>
          </div>
          <el-tag :type="result ? riskTag : 'info'" effect="dark">{{ result ? riskLabel : '待触发' }}</el-tag>
        </header>

        <div class="result-content detail-result">
          <!-- 空闲轨道动画（未选视频/未分析/无结果时，流程链路待机监听） -->
          <div v-if="!hasTask" class="alarm-idle flow-idle-visual">
            <div class="idle-orbit">
              <span></span>
              <i></i>
            </div>
            <div class="idle-copy">
              <strong>{{ flowStatusLabel }}</strong>
              <span>风险事件触发后将在此同步处置进度</span>
            </div>
          </div>

          <!-- 处理链路流程时间线（始终渲染；无任务时灰显待机） -->
          <ol class="progress-timeline flow-timeline" :class="{ idle: !hasTask }">
            <li
              v-for="item in flowSteps"
              :key="item.key"
              :class="[item.tone, item.state, item.connectorClass, { active: item.active }]"
            >
              <i class="flow-node-icon"><component :is="item.icon" /></i>
              <article>
                <header>
                  <strong :title="item.label">{{ item.label }}</strong>
                  <time>{{ item.time }}</time>
                </header>
                <p :title="item.message">{{ item.message }}</p>
                <ul v-if="item.active && item.logs.length" class="flow-node-logs">
                  <li v-for="log in item.logs" :key="log.key">
                    <b :title="log.title">{{ log.title }}</b>
                    <span :title="log.message">{{ log.message }}</span>
                  </li>
                </ul>
                <footer>
                  <span>{{ item.operator }}</span>
                  <b :class="item.statusClass">{{ item.statusText }}</b>
                </footer>
              </article>
            </li>
          </ol>

          <!-- 操作入口：完整事件信息与分析报告经详情按钮跳转查看 -->
          <div v-if="result" class="result-actions detail-actions">
            <el-button :disabled="!result.event_instance_id" type="primary" plain @click="openEventDetail(result.event_instance_id)">查看事件详情</el-button>
          </div>
        </div>

        <div v-if="lastError" class="error-banner">
          <el-icon><Warning /></el-icon><span>{{ lastError }}</span>
        </div>
      </aside>
    </section>

    <el-dialog
      v-model="supplementDialogVisible"
      title="选择特殊工况"
      width="520px"
      class="supplement-dialog"
    >
      <el-form label-position="top">
        <el-form-item label="特殊工况">
          <el-select v-model="supplementForm.context_type" style="width: 100%" @change="handleSpecialContextTypeChange">
            <el-option label="库坝正在泄洪" value="DAM_DISCHARGE" />
            <el-option label="强降雨/水位上涨" value="RAINSTORM" />
            <el-option label="闸门开启" value="GATE_OPEN" />
            <el-option label="下游禁入" value="DOWNSTREAM_RESTRICTED" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态说明">
          <el-input v-model="supplementForm.label" maxlength="100" />
        </el-form-item>
        <el-form-item label="影响区域">
          <el-input v-model="supplementForm.affected_area" maxlength="300" />
        </el-form-item>
        <el-form-item label="补充备注">
          <el-input
            v-model="supplementForm.note"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="supplementDialogVisible = false">取消</el-button>
        <el-button type="info" plain @click="clearSpecialContext">
          本次不使用
        </el-button>
        <el-button type="warning" @click="applySpecialContext">
          应用到本次模拟
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled, Connection, Promotion, VideoCamera, VideoPause, VideoPlay, Warning, WarningFilled,
} from '@element-plus/icons-vue'
import { simulateCameraVideoScreening } from '@/api/camera'
import { getUnifiedSafetyEventDetail } from '@/api/integration'

const FRAME_COUNT = 8
const WINDOW_SECONDS = 10
const DEFAULT_CAMERA_ID = 1
const DEFAULT_CAMERA_NAME = '9号监测点'
const router = useRouter()
const cameraId = ref(DEFAULT_CAMERA_ID)
const fileInputRef = ref(null)
const videoRef = ref(null)
const videoUrl = ref('')
const videoName = ref('')
const videoFile = ref(null)
// 视频输入完成时刻（选择本地视频成功时记录，流程节点显示固定时间，避免随轮询重算跳动）
const videoUploadedAt = ref(0)
const evidenceFrames = ref([])
const simulationActive = ref(false)
const screening = ref(false)
const result = ref(null)
const eventDetail = ref(null)
const lastError = ref('')
const pollTimer = ref(null)
const pollStartedAt = ref(0)
const lastDetailSignature = ref('')
const stablePollCount = ref(0)
const supplementDialogVisible = ref(false)
const supplementForm = ref(defaultSupplementForm())
const selectedSupplementContext = ref(null)

const selectedCameraName = computed(() => DEFAULT_CAMERA_NAME)
const mediaStatus = computed(() => {
  if (screening.value) return '分析中'
  if (simulationActive.value) return '实时采集中'
  if (videoUrl.value) return '视频已就绪'
  return '等待输入'
})
const frameSlotLabel = computed(() => {
  if (screening.value || result.value?.event_instance_id) return '等待复核帧'
  return '待生成'
})
const riskLabel = computed(() => labelForRisk(result.value?.risk_level))
const riskTag = computed(() => tagForRisk(result.value?.risk_level))
const specialContextButtonText = computed(() => selectedSupplementContext.value?.label || '特殊工况')
const detailEvent = computed(() => eventDetail.value?.event || null)
const eventReportId = computed(() => detailEvent.value?.analysis_report_id || result.value?.analysis_report_id || null)
// 事件处置报告日志（shouldStopEventPolling 依赖其状态判断轮询终止）
const reportLog = computed(() => latestTimelineLog(item => matchesLog(item, ['dam-event-report', '事件报告生成', '事件处置报告'])))
// ========== 处理链路流程时间线（参考 Dashboard「实时告警进度」设计） ==========
// 处理链路节点 = Dashboard「实时告警进度」4 节点（事件触发/智能路由/联动处理/闭环归档）+ 首个「视频输入」
const flowDefinitions = [
  { key: 'input', label: '视频输入', icon: markRaw(VideoCamera), tone: 'is-primary', logTypes: [], idleText: '等待上传视频', kind: 'input' },
  { key: 'trigger', label: '事件触发', icon: markRaw(WarningFilled), tone: 'is-primary', logTypes: ['TRIGGER', 'RISK_CHANGE'], idleText: '等待事件触发' },
  { key: 'route', label: '智能路由', icon: markRaw(Promotion), tone: 'is-warning', logTypes: ['DAM_WORKFLOW', 'WORKFLOW'], idleText: '等待匹配处置流程' },
  { key: 'linkage', label: '联动处理', icon: markRaw(Connection), tone: 'is-success', logTypes: ['ACTION', 'MANUAL', 'REPORT'], idleText: '等待联动动作执行' },
  { key: 'archive', label: '闭环归档', icon: markRaw(CircleCheckFilled), tone: 'is-info', logTypes: ['RESOLVE'], idleText: '等待闭环归档' },
]
const hasTask = computed(() => Boolean(videoFile.value || screening.value || result.value || eventDetail.value))
// 流程是否已启动：仅「开始模拟」后（分析中/已提交/已有事件）才进入执行流转；仅上传视频仍为等待状态
const started = computed(() => Boolean(screening.value || result.value || eventDetail.value))
const flowStatusLabel = computed(() => {
  if (screening.value) return '分析中'
  if (eventReportId.value) return '报告已生成'
  if (result.value?.event_instance_id) return '事件处理中'
  if (result.value) return '已提交'
  return '链路监听中'
})
const flowSteps = computed(() => {
  const rows = chainTimeline.value
  const idle = !hasTask.value
  const grouped = flowDefinitions.map((definition) => {
    const logs = rows
      .filter((row) => definition.logTypes.includes(String(row?.log_type || '').toUpperCase()))
      .map((row, index) => ({
        key: row.id || `${definition.key}-${row.create_time || row.created_at || index}`,
        title: row.title || logTypeLabel(row.log_type),
        status: String(row.status || '').toUpperCase(),
        statusText: timelineStatusLabel(row.status),
        message: row.message || row.action || row.title || '暂无处理说明',
        time: row.create_time || row.created_at,
        operator: operatorLabel(row.operator),
      }))
    return { definition, logs }
  })

  const stages = grouped.map(({ definition, logs }) => {
    const base = { definition, logs }
    // 视频输入：由本地文件状态推导
    if (definition.kind === 'input') {
      const done = Boolean(videoFile.value)
      return {
        ...base,
        rawState: done ? 'done' : 'pending',
        time: done && videoUploadedAt.value ? formatDetailTime(videoUploadedAt.value) : '--',
        message: videoName.value ? `已加载视频文件 ${videoName.value}` : definition.idleText,
        operator: '本机输入',
      }
    }
    // 事件触发：日志驱动 + ECA 已提交兜底
    if (definition.key === 'trigger' && !logs.length && result.value?.eca_dispatched) {
      return {
        ...base,
        rawState: 'done',
        time: formatNow(),
        message: '已提交事件入口，等待事件创建',
        operator: '系统自动',
      }
    }
    // 闭环归档：日志驱动 + 报告 ID 兜底
    if (definition.key === 'archive' && eventReportId.value) {
      return {
        ...base,
        rawState: 'done',
        time: formatNow(),
        message: '报告已生成并归档',
        operator: '系统自动',
      }
    }
    // 其余阶段：按日志聚合判断状态
    const latest = logs[logs.length - 1] || null
    const rawState = logs.length
      ? (logs.some((log) => ['FAILED', 'ERROR'].includes(log.status))
          ? 'failed'
          : logs.some((log) => ['PENDING', 'PROCESSING', 'RUNNING'].includes(log.status))
            ? 'running'
            : 'done')
      : 'pending'
    return {
      ...base,
      rawState,
      time: latest?.time ? formatDetailTime(latest.time) : '--',
      message: latest?.message || definition.idleText,
      operator: latest?.operator || '系统自动',
    }
  })

  const failedIndex = stages.findIndex((item) => item.rawState === 'failed')
  const runningIndex = stages.findIndex((item) => item.rawState === 'running')
  const pendingIndex = stages.findIndex((item) => item.rawState === 'pending')
  const activeIndex = idle ? -1 : !started.value ? -1 : failedIndex >= 0 ? failedIndex : runningIndex >= 0 ? runningIndex : pendingIndex >= 0 ? pendingIndex : -1
  const flowEndIndex = idle ? -1 : !started.value ? -1 : activeIndex >= 0 ? activeIndex : stages.length

  return stages.map(({ definition, logs, rawState, ...rest }, index) => {
    const active = index === activeIndex
    const failed = rawState === 'failed'
    const done = rawState === 'done'
    // 状态优先级仿 Dashboard：idle > failed > active(running) > done > pending（焦点节点即使底层 pending 也呈现 running）
    const state = idle ? 'idle' : failed ? 'failed' : active ? 'running' : done ? 'done' : 'pending'
    const connectorClass = idle
      ? 'connector-idle'
      : index < flowEndIndex - 1
        ? 'connector-done'
        : index === flowEndIndex - 1
          ? 'connector-running'
          : 'connector-pending'
    return {
      key: definition.key,
      label: definition.label,
      icon: definition.icon,
      tone: failed ? 'is-failed' : definition.tone,
      state,
      connectorClass,
      active,
      logs,
      time: rest.time || '--',
      message: rest.message || (done ? `已完成${definition.label}` : definition.idleText),
      operator: rest.operator || (logs.length ? '系统自动' : '待机监听'),
      statusText: idle ? '待机' : failed ? '异常' : done ? '已完成' : active ? '执行中' : '未开始',
      statusClass: idle ? 'is-muted' : failed ? 'is-failed' : done ? 'is-success' : active ? 'is-processing' : 'is-muted',
    }
  })
})
const chainTimeline = computed(() => eventDetail.value?.timeline || [])

function latestTimelineLog(predicate) {
  const items = Array.isArray(chainTimeline.value) ? chainTimeline.value : []
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return items[index]
  }
  return null
}

function matchesLog(item, keywords) {
  const text = [
    item?.action_key,
    item?.action_id,
    item?.log_type,
    item?.title,
    item?.message,
  ].filter(Boolean).join(' ').toLowerCase()
  return keywords.some(keyword => text.includes(String(keyword).toLowerCase()))
}

function logStatus(item) {
  const status = String(item?.status || '').toUpperCase()
  if (['SUCCESS', 'COMPLETED', 'DONE'].includes(status)) return 'DONE'
  if (['FAILED', 'ERROR'].includes(status)) return 'FAILED'
  if (['PROCESSING', 'RUNNING', 'PENDING'].includes(status)) return 'RUNNING'
  return ''
}

// 操作人显示名（后端 operator 常为大写标识，映射为友好名称）
function operatorLabel(value) {
  const operator = String(value || '').trim()
  const normalized = operator.toUpperCase()
  if (!operator) return '系统自动'
  if (['SYSTEM', 'AUTO', 'ECA', 'DAM', 'RUNTIME'].includes(normalized)) return '系统自动'
  if (normalized.startsWith('USER')) return '人工确认'
  return operator
}

// 时间线日志状态显示文案（对齐 Dashboard 徽章语义）
function timelineStatusLabel(value) {
  const status = String(value || '').toUpperCase()
  if (['SUCCESS', 'COMPLETED', 'DONE'].includes(status)) return '已完成'
  if (['FAILED', 'ERROR'].includes(status)) return '异常'
  if (['PROCESSING', 'RUNNING', 'PENDING'].includes(status)) return '执行中'
  return '已完成'
}

// 当前时间格式化（流程节点时间显示）
function formatNow() {
  return formatDetailTime(Date.now())
}

function handleVideoFile(raw) {
  if (!raw) return
  if (raw.size > 200 * 1024 * 1024) return ElMessage.error('视频大小不能超过 200MB')
  stopSimulation(false)
  stopEventPolling()
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoFile.value = raw
  videoUrl.value = URL.createObjectURL(raw)
  videoName.value = raw.name
  videoUploadedAt.value = Date.now()
  result.value = null
  eventDetail.value = null
  lastError.value = ''
  evidenceFrames.value = []
  nextTick(() => videoRef.value?.load())
}

function handleNativeVideoFile(event) {
  const raw = event.target?.files?.[0]
  handleVideoFile(raw)
  if (event.target) event.target.value = ''
}

function openVideoPicker() {
  fileInputRef.value?.click()
}

async function toggleSimulation() {
  if (simulationActive.value) {
    stopSimulation(true)
    return
  }
  if (!cameraId.value || !videoFile.value) return
  lastError.value = ''
  simulationActive.value = true
  await videoRef.value?.play().catch(() => null)
  await submitVideoFile()
}

function stopSimulation(pauseVideo = true) {
  simulationActive.value = false
  if (pauseVideo && videoRef.value && !videoRef.value.paused) videoRef.value.pause()
}

function handleNativePause() {
  if (simulationActive.value) stopSimulation(false)
}

async function handleVideoEnded() {
  stopSimulation(false)
}

async function submitVideoFile() {
  if (!cameraId.value || !videoFile.value || screening.value) return
  screening.value = true
  lastError.value = ''
  try {
    const response = await simulateCameraVideoScreening(
      cameraId.value,
      videoFile.value,
      {
        windowSeconds: WINDOW_SECONDS,
        supplementalContext: selectedSupplementContext.value,
      },
    )
    const normalizedResult = { ...response.data }
    result.value = normalizedResult
    evidenceFrames.value = []
    if (normalizedResult.event_instance_id) {
      await refreshEventDetail(normalizedResult.event_instance_id)
      startEventPolling(normalizedResult.event_instance_id)
    }
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '视频分析请求失败'
  } finally {
    screening.value = false
    stopSimulation(false)
  }
}

async function refreshEventDetail(id = result.value?.event_instance_id) {
  if (!id) return
  try {
    const response = await getUnifiedSafetyEventDetail(id)
    eventDetail.value = response.data
    updateWorkflowEvidenceFrames(response.data)
    const event = response.data?.event || {}
    result.value = {
      ...(result.value || {}),
      risk_level: event.risk_level || result.value?.risk_level,
      max_risk_level: event.max_risk_level || result.value?.max_risk_level,
      event_status: event.status,
      event_state: event.state,
      analysis_report_id: event.analysis_report_id,
    }
    updatePollingStability(response.data)
    if (shouldStopEventPolling(event)) {
      stopEventPolling()
    }
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '事件详情刷新失败'
  }
}

function startEventPolling(id) {
  stopEventPolling()
  pollStartedAt.value = Date.now()
  lastDetailSignature.value = ''
  stablePollCount.value = 0
  refreshEventDetail(id)
  pollTimer.value = window.setInterval(() => refreshEventDetail(id), 2000)
}

function stopEventPolling() {
  if (pollTimer.value) window.clearInterval(pollTimer.value)
  pollTimer.value = null
}

function updatePollingStability(data) {
  const timeline = Array.isArray(data?.timeline) ? data.timeline : []
  const lastLog = timeline[timeline.length - 1] || {}
  const event = data?.event || {}
  const signature = [
    event.status,
    event.state,
    event.analysis_report_id,
    timeline.length,
    lastLog.id,
    lastLog.status,
    lastLog.message,
  ].join('|')
  if (signature === lastDetailSignature.value) {
    stablePollCount.value += 1
  } else {
    stablePollCount.value = 0
    lastDetailSignature.value = signature
  }
}

function shouldStopEventPolling(event) {
  const elapsed = Date.now() - pollStartedAt.value
  if (elapsed > 15 * 60 * 1000) return true
  const status = String(event?.status || '').toUpperCase()
  const state = String(event?.state || '').toUpperCase()
  const reportStatus = logStatus(reportLog.value)
  const terminalEvent = ['COMPLETED', 'FAILED', 'FALSE_ALARM'].includes(status) || state === 'RESOLVED'
  const terminalReport = Boolean(event?.analysis_report_id) || ['DONE', 'FAILED'].includes(reportStatus)
  return terminalEvent && terminalReport && stablePollCount.value >= 3
}

function normalizeMediaUrls(urls) {
  return (urls || []).map(normalizeMediaUrl).filter(Boolean)
}

function normalizeMediaUrl(url) {
  if (!url) return ''
  const raw = String(url)
  if (raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('/')) return raw
  if (raw.startsWith('dam/')) {
    return `/api/v1/camera/media/minio-proxy?url=${encodeURIComponent(raw)}`
  }
  try {
    const parsed = new URL(raw)
    const isMinio = parsed.port === '9000' || ['localhost', '127.0.0.1', '172.17.0.1', 'minio'].includes(parsed.hostname)
    if (isMinio && parsed.pathname.startsWith('/dam/')) {
      return `/api/v1/camera/media/minio-proxy?url=${encodeURIComponent(raw)}`
    }
  } catch (_) {
    return raw
  }
  return raw
}

function updateWorkflowEvidenceFrames(detail) {
  const frames = extractWorkflowReviewFrames(detail)
  if (!frames.length) return
  evidenceFrames.value = frames.slice(0, FRAME_COUNT).map((item, index) => ({
    id: `workflow-frame-${item.key || index}`,
    url: normalizeMediaUrl(item.url),
    failed: false,
    timeLabel: item.timeLabel || `复核帧 ${String(index + 1).padStart(2, '0')}`,
    label: item.label || item.timeLabel || `复核帧 ${String(index + 1).padStart(2, '0')}`,
  }))
}

function extractWorkflowReviewFrames(detail) {
  const reviewFrames = Array.isArray(detail?.review_frames) ? detail.review_frames : []
  if (reviewFrames.length) {
    return reviewFrames
      .map((item, index) => {
        const url = item?.file_url || item?.url || item?.path || item?.object_key || item?.object_name
        if (!url) return null
        return {
          key: item?.id || item?.object_key || item?.object_name || url || index,
          url,
          timeLabel: item?.time_label || item?.timeLabel || frameTimeLabel(item, index),
          label: frameDisplayLabel(item, index),
        }
      })
      .filter(Boolean)
  }

  const timeline = Array.isArray(detail?.timeline) ? detail.timeline : []
  const workflowLog = [...timeline].reverse().find((row) => String(row?.log_type || '').toUpperCase() === 'DAM_WORKFLOW' && row?.payload?.execution_result)
  const nodeResults = workflowLog?.payload?.execution_result?.node_results
  if (!Array.isArray(nodeResults)) return []

  const reasoningNode = nodeResults.find((row) => row?.node_id === 'action_reasoning')
  const detectNode = nodeResults.find((row) => row?.node_id === 'action_detect')
  const reasoningMedia = mediaListFromNode(reasoningNode)
  const detectMedia = mediaListFromNode(detectNode)
  const candidates = [...reasoningMedia, ...detectMedia]
  const frames = []
  const seen = new Set()

  for (const item of candidates) {
    const ref = preferredReviewFrameRef(item)
    if (!ref) continue
    const key = `${ref.bucket || ''}/${ref.objectName || ref.url}`
    if (seen.has(key)) continue
    seen.add(key)
    frames.push({
      key,
      url: ref.url,
      timeLabel: frameTimeLabel(item, frames.length),
      label: frameDisplayLabel(item, frames.length),
    })
    if (frames.length >= FRAME_COUNT) break
  }
  return frames
}

function mediaListFromNode(node) {
  const output = node?.output || {}
  const inference = output.inference_result || {}
  const transform = inference.media_transform || {}
  return [
    ...(Array.isArray(inference.representative_frame_candidates) ? inference.representative_frame_candidates : []),
    ...(Array.isArray(transform.representative_frame_candidates) ? transform.representative_frame_candidates : []),
    ...(Array.isArray(inference.media_objects) ? inference.media_objects : []),
    ...(Array.isArray(inference.cloud_media_objects) ? inference.cloud_media_objects : []),
    ...(Array.isArray(inference.key_frames) ? inference.key_frames : []),
    ...(Array.isArray(output.media_objects) ? output.media_objects : []),
  ]
}

function preferredReviewFrameRef(item) {
  if (!item || String(item.type || '').toLowerCase() !== 'image') return null

  const source = item.source
  const sourceRef = typeof source === 'string' ? source : source?.path || source?.object_name || source?.object_key || ''
  const ownRef = item.path || item.file_url || item.url || item.object_name || item.object_key || ''
  const text = `${item.role || ''} ${sourceRef} ${ownRef}`.toLowerCase()
  const isWorkflowFrame = String(ownRef).includes('/workflow-media/') && String(ownRef).includes('/images/')
  const isQwen4BFrame = text.includes('/qwen4b-proxy-media/') || text.includes('qwen4b-proxy-media/')
  if (!isWorkflowFrame && !isQwen4BFrame) return null

  const localRef = String(ownRef || sourceRef || '')
  const normalized = localRef.startsWith('dam/') || localRef.startsWith('http')
    ? localRef
    : `dam/${localRef.replace(/^\/+/, '')}`
  return {
    url: normalized,
    bucket: normalized.split('/')[0],
    objectName: normalized.split('/').slice(1).join('/'),
  }
}

function frameTimeLabel(item, index) {
  const seconds = item?.timestamp_seconds ?? item?.source?.timestamp_seconds ?? item?.frame_time_sec ?? item?.source?.frame_time_sec
  if (seconds !== undefined && seconds !== null && seconds !== '') return `${Number(seconds).toFixed(1)}s`
  return `复核帧 ${String(index + 1).padStart(2, '0')}`
}

function frameDisplayLabel(item, index) {
  const sourceLabel = item?.source_label || item?.sourceLabel || inferFrameSourceLabel(item)
  const seconds = item?.timestamp_seconds ?? item?.source?.timestamp_seconds ?? item?.frame_time_sec ?? item?.source?.frame_time_sec
  if (seconds !== undefined && seconds !== null && seconds !== '') {
    return `${sourceLabel} ${Number(seconds).toFixed(1)}s`
  }
  return `${sourceLabel} ${String(index + 1).padStart(2, '0')}`
}

function inferFrameSourceLabel(item) {
  const source = item?.source
  const sourceRef = typeof source === 'string' ? source : source?.path || source?.object_name || source?.object_key || ''
  const ownRef = item?.path || item?.object_name || item?.object_key || item?.file_url || item?.url || ''
  const text = `${item?.role || ''} ${sourceRef} ${ownRef}`.toLowerCase()
  if (text.includes('qwen4b_review_frame_candidate') || text.includes('qwen4b_selected_representative_frame') || text.includes('qwen4b-proxy-media')) {
    return '复核帧'
  }
  if (text.includes('qwen_screening') || text.includes('/camera/')) return '初筛帧'
  return '复核帧'
}

function markFrameFailed(frame) {
  frame.failed = true
}

function openEventDetail(id) {
  if (!id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id } })
}

function defaultSupplementForm() {
  return specialContextDefaults('DAM_DISCHARGE')
}

function specialContextDefaults(type) {
  const presets = {
    DAM_DISCHARGE: {
      label: '库坝正在泄洪',
      affected_area: '滩涂、消落带、下游河道、近水岸线',
      note: '泄洪期间禁止人员进入滩涂边活动',
    },
    RAINSTORM: {
      label: '强降雨或水位上涨',
      affected_area: '库区岸线、下游河道、低洼滩涂、边坡区域',
      note: '强降雨或水位上涨期间，需提高人员亲水、洪水漫滩和边坡异常风险关注等级',
    },
    GATE_OPEN: {
      label: '闸门开启',
      affected_area: '闸门下游、泄流通道、近水岸线、桥下河道',
      note: '闸门开启期间，人员或船只进入下游影响区需结合知识库规则提高风险研判等级',
    },
    DOWNSTREAM_RESTRICTED: {
      label: '下游禁入管控',
      affected_area: '下游河道、滩涂、消落带、警戒范围',
      note: '下游禁入管控生效期间，发现人员活动需按警戒区异常进入复核处置',
    },
    OTHER: {
      label: '其他特殊情况',
      affected_area: '事件影响区域',
      note: '请补充当前特殊情况及其对风险等级的影响',
    },
  }
  const preset = presets[type] || presets.DAM_DISCHARGE
  return {
    context_type: type || 'DAM_DISCHARGE',
    active: true,
    label: preset.label,
    severity_hint: 'HIGH',
    affected_area: preset.affected_area,
    note: preset.note,
    source: 'OPERATOR',
  }
}

function handleSpecialContextTypeChange(type) {
  supplementForm.value = {
    ...supplementForm.value,
    ...specialContextDefaults(type),
  }
}

function openSupplementDialog() {
  supplementForm.value = selectedSupplementContext.value
    ? { ...selectedSupplementContext.value }
    : defaultSupplementForm()
  supplementDialogVisible.value = true
}

function applySpecialContext() {
  selectedSupplementContext.value = { ...supplementForm.value }
  supplementDialogVisible.value = false
  ElMessage.success('特殊工况已应用到本次模拟')
}

function clearSpecialContext() {
  selectedSupplementContext.value = null
  supplementDialogVisible.value = false
  ElMessage.info('本次模拟不使用特殊工况')
}

function logTypeLabel(value) {
  return ({
    TRIGGER: '触发',
    DAM_WORKFLOW: '工作流',
    ACTION: '动作',
    REPORT: '报告',
    RESOLVE: '闭环',
    MANUAL: '人工',
  })[value] || value || '记录'
}

function labelForRisk(level) { return ({ HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险' })[level] || '低风险' }
function tagForRisk(level) { return ({ HIGH: 'danger', MEDIUM: 'warning', LOW: 'success' })[level] || 'info' }
function formatDetailTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
onBeforeUnmount(() => {
  stopEventPolling()
  stopSimulation(false)
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  evidenceFrames.value.forEach(item => {
    if (item.url?.startsWith('blob:')) URL.revokeObjectURL(item.url)
  })
})
</script>

<style scoped>
.screening-page {
  --panel: #0c1b2b;
  --panel-soft: #102437;
  --panel-strong: #07121e;
  --line: rgba(127, 168, 198, .22);
  --text: #edf6fc;
  --muted: #8fa8ba;
  --cyan: #4fd0e8;
  --green: #42c6a6;
  --red: #ff6b78;
  --amber: #f2b75c;
  min-height: 100%;
  padding: 20px;
  color: var(--text);
  background: #07131f;
}
.page-header,
.media-tools,
.panel-header,
.panel-header > div:first-child,
.panel-title,
.runtime-state {
  display: flex;
  align-items: center;
}
/* 页头（参考「数据源管理」admin-header 设计：标题块 + 操作入口，无冗余面包屑） */
.page-header {
  min-height: 74px;
  padding: 16px 20px;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}
.title-block {
  min-width: 0;
  display: grid;
  gap: 8px;
}
.title-block p {
  margin: 0;
  color: #8aa9c3;
  font-size: 13px;
  line-height: 1.35;
}
h2,
h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}
h2 {
  font-size: 24px;
  font-weight: 700;
}
h3 {
  font-size: 16px;
}
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(380px, .9fr);
  gap: 16px;
  margin-top: 16px;
}
.media-panel,
.result-panel {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}
.panel-header {
  min-height: 64px;
  justify-content: space-between;
  gap: 14px;
  padding: 0 16px;
  border-bottom: 1px solid var(--line);
  background: var(--panel-soft);
}
.panel-title {
  gap: 11px;
}
.panel-header > div:first-child {
  gap: 11px;
}
.panel-header small {
  display: block;
  margin-bottom: 3px;
  color: #718da2;
  font-size: 10px;
  font-weight: 700;
}
.section-index {
  color: #547791;
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.media-tools {
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.runtime-state {
  gap: 8px;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid rgba(127,168,198,.18);
  border-radius: 6px;
  color: #9cb4c6;
  background: #0a1928;
  font-size: 12px;
}
.runtime-state i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #61798c;
}
.runtime-state i.live {
  background: var(--green);
  box-shadow: 0 0 0 5px rgba(66,198,166,.12);
}
.video-stage {
  position: relative;
  height: clamp(380px, 43vw, 620px);
  overflow: hidden;
  background: #02070d;
}
.hidden-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.video-stage video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #02070d;
}
.empty-stage {
  display: grid;
  width: 100%;
  height: 100%;
  place-content: center;
  justify-items: center;
  gap: 10px;
  border: 0;
  color: #7895aa;
  background: transparent;
  cursor: pointer;
}
.empty-stage:hover,
.empty-stage:focus-visible {
  outline: none;
  background: rgba(79, 208, 232, .05);
}
.empty-stage:hover .el-icon,
.empty-stage:focus-visible .el-icon {
  color: var(--cyan);
}
.empty-stage .el-icon {
  color: #426d87;
  font-size: 48px;
}
.empty-stage strong {
  color: #d0e2ed;
  font-size: 16px;
}
.empty-stage span {
  font-size: 12px;
}
.evidence-strip {
  padding: 14px 16px 16px;
  border-top: 1px solid var(--line);
  background: #081827;
}
.strip-title {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #91aabe;
  font-size: 12px;
}
.strip-title b {
  color: #d7e8f3;
}
.frame-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 4px;
  scroll-snap-type: x mandatory;
  scrollbar-width: thin;
  scrollbar-color: rgba(79, 208, 232, .42) rgba(8, 24, 39, .6);
}
.frame-strip figure,
.frame-slot {
  flex: 0 0 clamp(190px, 22vw, 280px);
  aspect-ratio: 16 / 9;
  border: 1px solid #284962;
  border-radius: 6px;
  scroll-snap-align: start;
}
.frame-strip figure {
  position: relative;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  background: #02070d;
}
.frame-strip img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.frame-error {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  color: #7895aa;
  background: #03101a;
  font-size: 12px;
}
.frame-strip figure span {
  position: absolute;
  right: 6px;
  bottom: 6px;
  padding: 3px 6px;
  border-radius: 4px;
  color: #e6f5ff;
  background: rgba(0,0,0,.68);
  font-size: 10px;
}
.frame-slot {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  color: #3c5b70;
  background: #0b2032;
}
.frame-slot b {
  font-size: 18px;
  font-weight: 800;
}
.frame-slot span {
  color: #607f94;
  font-size: 11px;
  font-weight: 600;
}
.result-panel {
  min-height: 620px;
}
.result-content {
  padding: 16px;
}
.detail-result {
  display: grid;
  gap: 14px;
}
/* ========== 处理链路流程时间线（移植自 Dashboard「实时告警进度」） ========== */
.progress-timeline {
  position: relative;
  display: grid;
  align-content: start;
  gap: 10px;
  margin: 12px 0 0;
  padding: 0 2px 0 22px;
  list-style: none;
  overflow: auto;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(67, 200, 255, .36) transparent;
}
.progress-timeline::before {
  content: "";
  position: absolute;
  top: 13px;
  bottom: 13px;
  left: 7px;
  width: 1px;
  background: linear-gradient(180deg, rgba(255, 91, 104, .86), rgba(255, 182, 72, .64), rgba(104, 161, 200, .22));
}
.progress-timeline li {
  position: relative;
  min-width: 0;
  color: #cfe2f0;
}
.progress-timeline > li > i {
  position: absolute;
  left: -20px;
  top: 16px;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(136, 169, 193, .58);
  border-radius: 50%;
  background: #071a2f;
  z-index: 1;
}
.progress-timeline li.is-primary > i {
  border-color: #43c8ff;
  background: #08243a;
}
.progress-timeline li.is-warning > i {
  border-color: #ffb648;
  background: #2c210d;
}
.progress-timeline li.is-success > i {
  border-color: #38d59c;
  background: #0a2d29;
}
.progress-timeline li.active > i {
  border-color: #ff5b68;
  box-shadow: 0 0 0 4px rgba(255, 91, 104, .12);
}
.progress-timeline article {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 8px;
  background: rgba(4, 20, 36, .48);
}
.progress-timeline li.active article {
  border-color: rgba(255, 91, 104, .32);
  background: linear-gradient(135deg, rgba(255, 91, 104, .1), rgba(4, 20, 36, .54));
}
.progress-timeline header,
.progress-timeline footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}
.progress-timeline header strong {
  min-width: 0;
  overflow: hidden;
  color: #f1fbff;
  font-size: 14px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.progress-timeline time,
.progress-timeline footer span {
  flex: 0 0 auto;
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}
.progress-timeline p {
  display: -webkit-box;
  margin: 8px 0 10px;
  overflow: hidden;
  color: #b7d0e3;
  font-size: 12px;
  line-height: 1.45;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.flow-timeline {
  gap: 12px;
  margin-top: 12px;
  padding-left: 52px;
}
.flow-timeline::before {
  content: none;
  display: none;
}
.flow-timeline > li:not(:last-child)::after {
  content: "";
  position: absolute;
  left: -27px;
  top: 47px;
  bottom: -12px;
  width: 1px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(143, 200, 242, .16), rgba(143, 200, 242, .06));
  pointer-events: none;
  z-index: 0;
}
.flow-timeline > li.connector-done:not(:last-child)::after {
  background: linear-gradient(180deg, rgba(67, 200, 255, .58), rgba(56, 213, 156, .38));
}
.flow-timeline > li.connector-running:not(:last-child)::after {
  background:
    linear-gradient(180deg, transparent, rgba(100, 223, 255, .98), transparent) 0 -80px / 100% 80px no-repeat,
    linear-gradient(180deg, rgba(67, 200, 255, .58), rgba(100, 223, 255, .28));
  animation: flowLineScan 1.7s linear infinite;
}
.flow-timeline > li.connector-pending:not(:last-child)::after,
.flow-timeline.idle > li:not(:last-child)::after {
  background:
    linear-gradient(180deg, rgba(143, 200, 242, .2), rgba(143, 200, 242, .08));
  animation: none;
}
.progress-timeline > li > .flow-node-icon {
  left: -44px;
  top: 9px;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(143, 200, 242, .22);
  border-radius: 9px;
  color: #8fc8f2;
  background: #082038;
  box-shadow: none;
  z-index: 2;
}
.flow-node-icon :deep(svg) {
  width: 18px;
  height: 18px;
}
.flow-timeline li.done > .flow-node-icon,
.flow-timeline li.is-success.done > .flow-node-icon {
  color: #48e6ae;
  border-color: rgba(72, 230, 174, .32);
  background: rgba(9, 45, 41, .92);
}
.flow-timeline li.running > .flow-node-icon {
  color: #64dfff;
  border-color: rgba(100, 223, 255, .68);
  animation: flowNodePulse 1.6s ease-in-out infinite;
  box-shadow: 0 0 0 3px rgba(100, 223, 255, .08), 0 0 14px rgba(100, 223, 255, .24);
}
.flow-timeline li.failed > .flow-node-icon,
.flow-timeline li.is-failed > .flow-node-icon {
  color: #ff7f88;
  border-color: rgba(255, 91, 104, .58);
  background: rgba(50, 18, 30, .9);
}
.flow-timeline li.idle > .flow-node-icon,
.flow-timeline li.pending > .flow-node-icon {
  opacity: .72;
}
.flow-timeline li.running article {
  position: relative;
  border-color: rgba(100, 223, 255, .44);
  background:
    linear-gradient(90deg, rgba(67, 200, 255, .12), rgba(4, 20, 36, .54) 48%, rgba(67, 200, 255, .08)),
    rgba(4, 20, 36, .52);
  overflow: hidden;
  z-index: 1;
}
.flow-timeline li.running article::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(100, 223, 255, .16), transparent);
  transform: translateX(-100%);
  animation: flowScan 2.2s ease-in-out infinite;
  pointer-events: none;
}
.flow-timeline.idle article {
  border-color: rgba(67, 200, 255, .1);
  background: rgba(4, 20, 36, .36);
}
.flow-timeline.idle {
  overflow: visible;
}
.flow-timeline.idle header strong,
.flow-timeline.idle p {
  color: #88a9c1;
}
.flow-node-logs {
  display: grid;
  gap: 6px;
  margin: 8px 0 10px;
  padding: 0;
  list-style: none;
}
.flow-node-logs li {
  min-width: 0;
  display: grid;
  gap: 4px;
  padding: 8px 9px;
  border-radius: 6px;
  color: #b8d4e8;
  background: rgba(2, 13, 25, .34);
}
.flow-node-logs b {
  min-width: 0;
  overflow: hidden;
  color: #e7f7ff;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flow-node-logs span {
  min-width: 0;
  display: -webkit-box;
  overflow: hidden;
  color: #9ed3f5;
  font-size: 11px;
  line-height: 1.35;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
/* 流程节点状态徽章（footer b） */
.progress-timeline footer b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  color: #9ed3f5;
  background: rgba(143, 200, 242, .08);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.progress-timeline footer b.is-pending {
  color: #ffcf78;
  background: rgba(255, 182, 72, .12);
}
.progress-timeline footer b.is-processing {
  color: #64dfff;
  background: rgba(67, 200, 255, .12);
}
.progress-timeline footer b.is-success {
  color: #48e6ae;
  background: rgba(56, 213, 156, .12);
}
.progress-timeline footer b.is-muted {
  color: #a6b8c8;
  background: rgba(166, 184, 200, .1);
}
.progress-timeline footer b.is-failed {
  color: #ff7f88;
  background: rgba(255, 91, 104, .13);
}
/* 空闲轨道动画（未触发时流程链路待机监听） */
.alarm-idle {
  display: grid;
  grid-template-columns: 74px 1fr;
  gap: 14px;
  align-items: center;
  margin-top: 18px;
  padding: 16px;
  border: 1px solid rgba(67, 200, 255, .16);
  border-radius: 8px;
  background:
    radial-gradient(circle at 36px 40px, rgba(56, 213, 156, .13), transparent 58px),
    rgba(5, 24, 43, .46);
}
.flow-idle-visual {
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 12px;
  margin-top: 12px;
  padding: 12px 13px;
  border-color: rgba(67, 200, 255, .14);
  background:
    radial-gradient(circle at 34px 36px, rgba(56, 213, 156, .12), transparent 54px),
    linear-gradient(135deg, rgba(7, 40, 65, .5), rgba(3, 18, 33, .38));
}
.flow-idle-visual .idle-orbit {
  width: 54px;
  height: 54px;
}
.flow-idle-visual .idle-copy strong {
  font-size: 15px;
}
.flow-idle-visual .idle-copy span {
  font-size: 12px;
}
.idle-orbit {
  position: relative;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(67, 200, 255, .22);
  border-radius: 50%;
  background: rgba(3, 18, 33, .58);
}
.idle-orbit::before,
.idle-orbit::after {
  content: "";
  position: absolute;
  border-radius: 50%;
}
.idle-orbit::before {
  inset: 15px;
  border: 2px solid rgba(56, 213, 156, .72);
}
.idle-orbit::after {
  left: 50%;
  top: 50%;
  width: 8px;
  height: 8px;
  transform: translate(-50%, -50%);
  background: #38d59c;
  box-shadow: 0 0 12px rgba(56, 213, 156, .72);
}
.idle-orbit span {
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  border-top: 2px solid rgba(67, 200, 255, .72);
  border-right: 2px solid transparent;
  animation: idleSpin 3.8s linear infinite;
}
.idle-orbit i {
  position: absolute;
  right: 8px;
  top: 12px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #43c8ff;
}
.idle-copy {
  min-width: 0;
  display: grid;
  gap: 7px;
}
.idle-copy strong {
  color: #e9f8ff;
  font-size: 16px;
  line-height: 1;
}
.idle-copy span {
  color: #8fc8f2;
  font-size: 12px;
  line-height: 1.35;
}
/* 关键帧动画 */
@keyframes idleSpin {
  to { transform: rotate(360deg); }
}
@keyframes flowNodePulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(100, 223, 255, .18);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(100, 223, 255, .08);
  }
}
@keyframes flowScan {
  0% { transform: translateX(-100%); }
  55%, 100% { transform: translateX(100%); }
}
@keyframes flowLineScan {
  from { background-position: 0 -90px, 0 0; }
  to { background-position: 0 100%, 0 0; }
}
.detail-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
.result-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.error-banner {
  display: flex;
  gap: 8px;
  margin: 0 16px 16px;
  padding: 10px;
  border: 1px solid rgba(255,107,120,.35);
  border-radius: 6px;
  color: #ff9aa4;
  background: rgba(110,27,39,.22);
  font-size: 12px;
}
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .result-panel {
    min-height: auto;
  }
}
@media (max-width: 760px) {
  .screening-page {
    padding: 12px;
  }
  .page-header,
  .panel-header {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
    padding-top: 12px;
    padding-bottom: 12px;
  }
  .media-tools {
    flex-wrap: wrap;
  }
  .video-stage {
    height: 340px;
  }
  .frame-strip figure,
  .frame-slot {
    flex-basis: 78vw;
  }
}
</style>
