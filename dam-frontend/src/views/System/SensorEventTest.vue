<template>
  <div class="sensor-test-page">
    <header class="page-header admin-header">
      <div class="page-header-copy">
        <div class="title-block">
          <h2>传感器测试工作台</h2>
          <p>模拟现场传感器信号，验证 ECA 规则与后续联动处置链路</p>
        </div>
      </div>
      <div class="page-header-meta">
        <div class="header-metric">
          <span>当前摄像头</span>
          <strong>{{ cameras.find(camera => String(camera.id) === String(cameraId))?.name || '未选择' }}</strong>
        </div>
        <div class="header-live-state">
          <i :class="{ live: submitting || detailEvent }"></i>
          <span>{{ submitting ? '触发中' : detailEvent ? '事件处理中' : '等待输入' }}</span>
        </div>
      </div>
    </header>

    <section class="workspace">
      <div class="control-panel">
        <header class="panel-header control-panel-header">
          <div><span class="section-index">01</span><div><small>SENSOR</small><h3>触发参数</h3></div></div>
          <el-select
            v-model="cameraId"
            class="camera-picker"
            :disabled="submitting"
            placeholder="选择摄像头"
            popper-class="sensor-event-select-popper"
          >
            <el-option
              v-for="camera in cameras"
              :key="camera.id"
              :label="camera.name"
              :value="String(camera.id)"
            />
          </el-select>
          <el-button
            type="primary"
            :icon="VideoPlay"
            :loading="submitting"
            :disabled="!canSubmit"
            :title="submitDisabledReason"
            @click="submit"
          >
            开始模拟
          </el-button>
        </header>

        <div class="preset-grid">
          <button
            v-for="preset in presets"
            :key="preset.key"
            type="button"
            :class="['preset-card', { active: preset.key === selectedKey }]"
            @click="selectPreset(preset.key)"
          >
            <span>{{ preset.level }}</span>
            <strong>{{ preset.label }}</strong>
            <small>{{ preset.rangeText }}</small>
          </button>
        </div>

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
            playsinline
          />
          <button v-else class="empty-stage" type="button" @click="openVideoPicker">
            <el-icon><VideoCamera /></el-icon>
            <strong>选择现场视频</strong>
            <span>MP4、MOV、WEBM 或 M4V</span>
          </button>
        </div>
        <p class="submit-hint" :class="{ ready: canSubmit }">{{ submitHint }}</p>

      </div>

      <aside class="result-panel">
        <header class="panel-header process-panel-header">
          <div><span class="section-index">02</span><div><small>ECA</small><h3>处理链路</h3></div></div>
          <el-tag :type="statusTag" effect="dark">{{ detailEvent?.status || '待触发' }}</el-tag>
        </header>

        <div class="result-content detail-result">
          <div v-if="!hasTask" class="alarm-idle flow-idle-visual">
            <div class="idle-orbit">
              <span></span>
              <i></i>
            </div>
            <div class="idle-copy">
              <strong>链路监听中</strong>
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
          <div v-if="triggerResult || detailEvent" class="result-actions detail-actions">
            <el-button :disabled="!detailEvent?.id" @click="refreshDetail">刷新详情</el-button>
            <el-button :disabled="!detailEvent?.id" type="primary" plain @click="openEventDetail(detailEvent?.id)">查看事件详情</el-button>
          </div>
        </div>

        <div v-if="lastError" class="error-banner">
          <el-icon><Warning /></el-icon><span>{{ lastError }}</span>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled, Connection, DataAnalysis, Promotion, VideoCamera, VideoPlay, Warning, WarningFilled,
} from '@element-plus/icons-vue'
import { simulateSensorEvent } from '@/api/eca'
import { getCameraList } from '@/api/camera'
import { getUnifiedSafetyEventDetail } from '@/api/integration'

const router = useRouter()

const presets = [
  { key: 'wind8', eventId: 24, sensorName: 'wind', label: '大风警报', level: '风速8级', risk: 'MEDIUM', rangeText: '17.2-20.7 m/s', sensorData: { wind_speed_ms: 18.5, wind_direction: 135, wind_level: 8 } },
  { key: 'wind12', eventId: 28, sensorName: 'wind', label: '飓风警报', level: '风速12级', risk: 'HIGH', rangeText: '>= 32.7 m/s', sensorData: { wind_speed_ms: 33.5, wind_direction: 135, wind_level: 12 } },
  { key: 'rain_hourly', eventId: 54, sensorName: 'rain', label: '小时暴雨预警', level: '雨量', risk: 'MEDIUM', rangeText: '小时雨量 >= 16 mm', sensorData: { hour_rain: 18, today_rain: 46, last_hour_rain: 9 } },
  { key: 'rain_heavy_day', eventId: 56, sensorName: 'rain', label: '当天大暴雨警报', level: '雨量', risk: 'HIGH', rangeText: '当天雨量 100-249 mm', sensorData: { hour_rain: 24, today_rain: 128, last_hour_rain: 18 } },
  { key: 'temp_low', eventId: 34, sensorName: 'temp_humidity', label: '低温告警', level: '温度', risk: 'MEDIUM', rangeText: '-10-0 ℃', sensorData: { temperature: -3.2, humidity: 62 } },
  { key: 'temp_high', eventId: 35, sensorName: 'temp_humidity', label: '高温告警', level: '温度', risk: 'MEDIUM', rangeText: '35-39 ℃', sensorData: { temperature: 37.6, humidity: 55 } },
  { key: 'humidity_high', eventId: 40, sensorName: 'temp_humidity', label: '高湿事件', level: '湿度', risk: 'MEDIUM', rangeText: '湿度 80-89 %', sensorData: { temperature: 28.4, humidity: 85 } },
  { key: 'freeze', eventId: 38, sensorName: 'temp_humidity', label: '冰冻风险告警', level: '温湿度', risk: 'HIGH', rangeText: '温度 < 0 ℃ 且湿度 >= 85%', sensorData: { temperature: -2.5, humidity: 91 } },
]

const selectedKey = ref('')
const cameraId = ref('1')
const cameras = ref([])
const fileInputRef = ref(null)
const videoRef = ref(null)
const videoFile = ref(null)
const videoUrl = ref('')
const videoName = ref('')
const submitting = ref(false)
const triggerResult = ref(null)
// 传感器输入完成时刻（触发提交时记录，流程节点显示固定时间，避免随轮询重算跳动）
const sensorInputAt = ref(0)
const detail = ref(null)
const lastError = ref('')
const pollTimer = ref(null)

const selectedPreset = computed(() => presets.find(item => item.key === selectedKey.value) || null)
const detailEvent = computed(() => detail.value?.event || null)
const chainTimeline = computed(() => detail.value?.timeline || [])
const conditionItems = computed(() => triggerResult.value?.condition_check?.conditions || [])
const canSubmit = computed(() => Boolean(selectedPreset.value?.eventId && cameraId.value && videoFile.value && !submitting.value))
const submitDisabledReason = computed(() => {
  if (!selectedPreset.value?.eventId) return '请先选择测试事件'
  if (!cameraId.value) return '请先选择摄像头'
  if (!videoFile.value) return '请先选择现场视频'
  if (submitting.value) return '正在提交'
  return '开始模拟'
})
const submitHint = computed(() => {
  if (canSubmit.value) return `已选择 ${selectedPreset.value.label} 和现场视频，可以开始模拟`
  if (!selectedPreset.value?.eventId && !videoFile.value) return '请选择测试事件、摄像头，并上传现场视频'
  if (!selectedPreset.value?.eventId) return '请选择测试事件'
  if (!cameraId.value) return '请选择摄像头'
  return '请上传现场视频'
})

// 处理链路节点 = Dashboard「实时告警进度」4 节点（事件触发/智能路由/联动处理/闭环归档）+ 首个「传感器输入」
const flowDefinitions = [
  { key: 'input', label: '传感器输入', icon: markRaw(DataAnalysis), tone: 'is-primary', logTypes: [], idleText: '等待传感器数据触发', kind: 'input' },
  { key: 'trigger', label: '事件触发', icon: markRaw(WarningFilled), tone: 'is-primary', logTypes: ['TRIGGER', 'RISK_CHANGE'], idleText: '等待事件触发' },
  { key: 'route', label: '智能路由', icon: markRaw(Promotion), tone: 'is-warning', logTypes: ['DAM_WORKFLOW', 'WORKFLOW'], idleText: '等待匹配处置流程' },
  { key: 'linkage', label: '联动处理', icon: markRaw(Connection), tone: 'is-success', logTypes: ['ACTION', 'MANUAL', 'REPORT'], idleText: '等待联动动作执行' },
  { key: 'archive', label: '闭环归档', icon: markRaw(CircleCheckFilled), tone: 'is-info', logTypes: ['RESOLVE'], idleText: '等待闭环归档' },
]
const hasTask = computed(() => Boolean(triggerResult.value || submitting.value || detailEvent.value))
// 链路是否已启动执行：仅触发后（触发中/已提交/已有事件）才进入流转，未触发仍为等待状态
const started = computed(() => Boolean(submitting.value || triggerResult.value || detailEvent.value))
const flowStatusLabel = computed(() => {
  if (submitting.value) return '触发中'
  if (detailEvent.value?.analysis_report_id) return '报告已生成'
  if (detailEvent.value?.id) return '事件处理中'
  if (triggerResult.value) return '已提交'
  return '待触发'
})
const statusTag = computed(() => {
  const status = detailEvent.value?.status
  if (status === 'COMPLETED') return 'success'
  if (status === 'FAILED') return 'danger'
  if (submitting.value || status === 'PROCESSING') return 'warning'
  return 'info'
})
const reportCompleted = computed(() => Boolean(detailEvent.value?.analysis_report_id) || chainTimeline.value.some((row) => {
  const logType = String(row?.log_type || '').toUpperCase()
  const actionKey = String(row?.action_key || '').toLowerCase()
  return (logType === 'REPORT' || actionKey.includes('dam-event-report')) && isDoneStatus(row?.status)
}))
const eventClosed = computed(() => ['COMPLETED', 'RESOLVED', 'CLOSED'].includes(String(detailEvent.value?.status || '').toUpperCase()))
const finalArchived = computed(() => reportCompleted.value || eventClosed.value)
const hasRunningTimeline = computed(() => chainTimeline.value.some((row) => isRunningStatus(row?.status)))

// 事件触发节点兜底文案：条件匹配结果
const triggerMessage = computed(() => {
  const items = conditionItems.value
  if (!items.length) return '已提交事件入口，等待事件创建'
  const matched = items.filter(item => item.matched).length
  return `${selectedPreset.value?.label || '传感器事件'}条件判定：${matched}/${items.length} 项匹配`
})

const flowSteps = computed(() => {
  const rows = chainTimeline.value
  const idle = !hasTask.value
  const grouped = flowDefinitions.map((definition) => {
    const logs = rows
      .filter((row) => definition.logTypes.includes(String(row?.log_type || '').toUpperCase()))
      .map((row, index) => ({
        key: row.id || `${definition.key}-${row.create_time || row.created_at || index}`,
        actionKey: row.action_key || row.action_id || '',
        title: row.title || logTypeLabel(row.log_type),
        status: String(row.status || '').toUpperCase(),
        statusText: timelineStatusLabel(row.status),
        message: row.message || row.action || row.title || '暂无处理说明',
        time: row.create_time || row.created_at,
        operator: operatorLabel(row.operator),
      }))
      .sort(compareLogs)
    return { definition, logs }
  })

  const stages = grouped.map(({ definition, logs }) => {
    const base = { definition, logs }
    // 传感器输入：本地推导（触发中或已提交即视为输入完成）
    if (definition.kind === 'input') {
      const done = Boolean(submitting.value || triggerResult.value)
      return {
        ...base,
        rawState: done ? 'done' : 'pending',
        time: done && sensorInputAt.value ? formatTime(sensorInputAt.value) : '--',
        message: done
          ? (videoName.value ? `已加载现场视频 ${videoName.value}` : `已提交 ${selectedPreset.value?.label || '传感器'} 数据`)
          : definition.idleText,
        operator: '本机输入',
      }
    }
    // 事件触发：日志驱动 + 已提交兜底（含条件匹配结果）
    if (definition.key === 'trigger' && !logs.length && (triggerResult.value || detailEvent.value)) {
      return {
        ...base,
        rawState: 'done',
        time: formatNow(),
        message: triggerMessage.value,
        operator: '系统自动',
      }
    }
    // 最终报告或闭环已落库时，说明路由链路已经走完；避免旧 PROCESSING 日志把节点卡在执行中。
    if (definition.key === 'route' && finalArchived.value) {
      const latest = latestLog(logs)
      return {
        ...base,
        rawState: 'done',
        time: latest?.time ? formatTime(latest.time) : formatNow(),
        message: '处置流程已匹配并执行完成',
        operator: latest?.operator || '系统自动',
      }
    }
    if (definition.key === 'linkage' && finalArchived.value) {
      const latest = latestLog(logs)
      return {
        ...base,
        rawState: 'done',
        time: latest?.time ? formatTime(latest.time) : formatNow(),
        message: reportCompleted.value ? '分析报告已生成，处置结果已归档' : '联动处置已完成',
        operator: latest?.operator || '系统自动',
      }
    }
    // 闭环归档：日志驱动 + 报告 ID 兜底
    if (definition.key === 'archive' && finalArchived.value) {
      const latest = latestLog(logs)
      return {
        ...base,
        rawState: 'done',
        time: latest?.time ? formatTime(latest.time) : formatNow(),
        message: reportCompleted.value ? '报告已生成并归档' : '事件已闭环归档',
        operator: latest?.operator || '系统自动',
      }
    }
    // 其余阶段：按日志聚合判断状态
    const latest = latestLog(logs)
    const rawState = aggregateLogState(logs)
    return {
      ...base,
      rawState,
      time: latest?.time ? formatTime(latest.time) : '--',
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

function buildSensorData() {
  const preset = selectedPreset.value
  if (!preset) return {}
  return {
    ...(preset.sensorData || {}),
    sensor_location: sensorLocationLabel(preset.sensorName),
    camera_id: Number(cameraId.value),
  }
}

function selectPreset(key) {
  const preset = presets.find(item => item.key === key)
  if (!preset) return
  selectedKey.value = key
}

function handleVideoFile(raw) {
  if (!raw) return
  if (raw.size > 300 * 1024 * 1024) return ElMessage.error('视频大小不能超过 300MB')
  stopPolling()
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoFile.value = raw
  videoUrl.value = URL.createObjectURL(raw)
  videoName.value = raw.name
  triggerResult.value = null
  detail.value = null
  lastError.value = ''
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

async function submit() {
  const preset = selectedPreset.value
  if (!preset?.eventId) {
    ElMessage.warning('请先选择测试事件')
    return
  }
  if (!videoFile.value) {
    ElMessage.warning('请先选择现场视频')
    return
  }
  submitting.value = true
  sensorInputAt.value = Date.now()
  lastError.value = ''
  triggerResult.value = null
  detail.value = null
  stopPolling()
  try {
    const response = await simulateSensorEvent({
      eventId: preset.eventId,
      sensorName: preset.sensorName,
      sensorData: buildSensorData(),
      cameraId: Number(cameraId.value),
      force: true,
      file: videoFile.value,
    })
    triggerResult.value = response.data
    ElMessage.success('传感器 ECA 已触发')
    await refreshDetail()
    startPolling()
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '触发失败'
  } finally {
    submitting.value = false
  }
}

async function loadCameras() {
  try {
    const response = await getCameraList({ silentError: true })
    cameras.value = (response.data?.cameras || []).map(camera => ({
      ...camera,
      id: String(camera.id),
      name: camera.name || camera.camera_name || `摄像头 ${camera.id}`,
    }))
    if (!cameras.value.some(camera => String(camera.id) === String(cameraId.value))) {
      cameraId.value = cameras.value[0]?.id || ''
    }
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '摄像头列表加载失败'
  }
}

async function refreshDetail() {
  const id = triggerResult.value?.event_instance_id || detailEvent.value?.id
  if (!id) return
  const response = await getUnifiedSafetyEventDetail(id)
  detail.value = response.data
  const status = String(detailEvent.value?.status || '').toUpperCase()
  if (reportCompleted.value || status === 'FAILED' || (status === 'COMPLETED' && !hasRunningTimeline.value)) {
    stopPolling()
  }
}

function startPolling() {
  stopPolling()
  pollTimer.value = window.setInterval(refreshDetail, 3000)
}

function stopPolling() {
  if (pollTimer.value) window.clearInterval(pollTimer.value)
  pollTimer.value = null
}

function openEventDetail(id) {
  if (!id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id } })
}

function sensorLocationLabel(sensorName) {
  return ({
    wind: '库坝现场风速风向传感器',
    rain: '库坝现场雨量计',
    temp_humidity: '库坝现场温湿度传感器',
  })[sensorName] || '库坝现场传感器'
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
  if (isDoneStatus(status)) return '已完成'
  if (isFailedStatus(status)) return '异常'
  if (isRunningStatus(status)) return '执行中'
  return '已完成'
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

// 当前时间格式化（流程节点时间显示）
function formatNow() {
  return formatTime(Date.now())
}

function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

function latestLog(logs) {
  return Array.isArray(logs) && logs.length ? logs[logs.length - 1] : null
}

function aggregateLogState(logs) {
  const latest = latestLog(logs)
  if (!latest) return 'pending'
  if (isFailedStatus(latest.status)) return 'failed'
  if (isRunningStatus(latest.status)) return 'running'
  if (isDoneStatus(latest.status)) return 'done'
  return 'done'
}

function compareLogs(a, b) {
  const diff = logTimestamp(a) - logTimestamp(b)
  if (diff !== 0) return diff
  return String(a.key || '').localeCompare(String(b.key || ''))
}

function logTimestamp(log) {
  const date = new Date(log?.time || 0)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function isDoneStatus(value) {
  return ['SUCCESS', 'COMPLETED', 'DONE'].includes(String(value || '').toUpperCase())
}

function isFailedStatus(value) {
  return ['FAILED', 'ERROR'].includes(String(value || '').toUpperCase())
}

function isRunningStatus(value) {
  return ['PROCESSING', 'RUNNING', 'PENDING'].includes(String(value || '').toUpperCase())
}

onBeforeUnmount(() => {
  stopPolling()
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})

onMounted(loadCameras)
</script>

<style scoped>
.sensor-test-page {
  --panel: #0c1b2b;
  --panel-soft: #102437;
  --line: rgba(127, 168, 198, .22);
  --text: #edf6fc;
  --muted: #8fa8ba;
  --cyan: #4fd0e8;
  --green: #42c6a6;
  --amber: #f2b75c;
  --red: #ff6b78;
  min-height: 100%;
  position: relative;
  isolation: isolate;
  padding: 24px;
  color: var(--text);
  background:
    radial-gradient(circle at 86% -8%, rgba(37, 132, 180, .24), transparent 30%),
    radial-gradient(circle at -5% 86%, rgba(35, 126, 113, .12), transparent 32%),
    linear-gradient(135deg, #06111c 0%, #091b2a 52%, #07131f 100%);
}
.page-header,
.page-header-copy,
.page-header-meta,
.source-control,
.panel-header,
.panel-header > div:first-child,
.result-actions {
  display: flex;
  align-items: center;
}
/* 页头（参考「数据源管理」admin-header 设计：标题块 + 操作入口，无冗余面包屑） */
.page-header {
  position: relative;
  min-height: 96px;
  padding: 18px 22px;
  justify-content: space-between;
  gap: 18px;
  overflow: hidden;
  border: 1px solid rgba(112, 181, 215, .24);
  border-radius: 16px;
  background:
    linear-gradient(105deg, rgba(16, 62, 92, .88) 0%, rgba(10, 35, 55, .86) 52%, rgba(7, 20, 34, .66) 100%);
  box-shadow: 0 18px 42px rgba(0, 0, 0, .18), inset 0 1px 0 rgba(177, 231, 255, .12);
}
.page-header::after {
  content: "";
  position: absolute;
  right: -70px;
  bottom: -94px;
  width: 300px;
  height: 170px;
  border: 1px solid rgba(79, 208, 232, .22);
  border-radius: 50%;
  box-shadow: 0 0 0 18px rgba(79, 208, 232, .035), 0 0 0 38px rgba(79, 208, 232, .022);
  pointer-events: none;
}
.page-header-copy {
  min-width: 0;
  position: relative;
  z-index: 1;
  display: block;
}
.page-header-meta {
  position: relative;
  z-index: 1;
  gap: 10px;
  flex: 0 0 auto;
}
.header-metric {
  display: grid;
  gap: 5px;
  min-width: 128px;
  padding: 9px 12px;
  border: 1px solid rgba(129, 193, 220, .16);
  border-radius: 10px;
  background: rgba(2, 19, 33, .28);
}
.header-metric span {
  color: #7f9eb3;
  font-size: 10px;
}
.header-metric strong {
  max-width: 150px;
  overflow: hidden;
  color: #e6f7ff;
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-live-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(66, 198, 166, .24);
  border-radius: 10px;
  color: #a9ddcf;
  background: rgba(22, 100, 88, .16);
  font-size: 12px;
  white-space: nowrap;
}
.header-live-state i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #61798c;
}
.header-live-state i.live {
  background: var(--green);
  box-shadow: 0 0 0 5px rgba(66, 198, 166, .12), 0 0 12px rgba(66, 198, 166, .48);
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
  font-size: 28px;
  font-weight: 760;
  letter-spacing: -.02em;
}
h3 {
  font-size: 16px;
}
.source-control {
  gap: 10px;
  color: #b3c7d6;
  font-size: 13px;
}
.workspace {
  display: grid;
  /* 与视频测试页保持同一主栏比例，保证“触发参数”和“摄像头画面模拟”对齐。 */
  grid-template-columns: minmax(0, 1.55fr) minmax(380px, .9fr);
  gap: 18px;
  margin-top: 18px;
}
.control-panel,
.result-panel {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(14, 34, 53, .96), rgba(8, 23, 37, .98));
  box-shadow: 0 16px 36px rgba(0, 0, 0, .16), inset 0 1px 0 rgba(180, 228, 248, .055);
}
.result-panel {
  min-height: 620px;
  background: linear-gradient(145deg, rgba(13, 35, 52, .98), rgba(7, 21, 35, .99));
}
.panel-header {
  min-height: 76px;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(127, 168, 198, .16);
  background: linear-gradient(180deg, rgba(18, 47, 71, .74), rgba(12, 31, 49, .46));
}
.control-panel-header { align-items: center; }
.process-panel-header { align-items: center; }
.camera-picker {
  width: 180px;
  margin-left: auto;
  margin-right: 2px;
}
.camera-picker :deep(.el-select__selected-item) {
  color: #ffffff !important;
  font-weight: 600;
}
.camera-picker :deep(.el-select__placeholder) {
  color: #718895 !important;
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
  display: inline-grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid rgba(79, 208, 232, .42);
  border-radius: 12px;
  color: #7de0f1;
  background: linear-gradient(145deg, rgba(79, 208, 232, .14), rgba(79, 208, 232, .035));
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 18px;
}
.preset-card {
  position: relative;
  min-width: 0;
  min-height: 124px;
  padding: 15px;
  border: 1px solid var(--line);
  border-radius: 14px;
  color: var(--text);
  text-align: left;
  background: linear-gradient(145deg, rgba(12, 39, 59, .88), rgba(7, 25, 42, .96));
  cursor: pointer;
  transition: transform .2s ease, border-color .2s ease, background .2s ease, box-shadow .2s ease;
}
.preset-card:hover,
.preset-card:focus-visible {
  outline: none;
  border-color: rgba(79, 208, 232, .55);
  background: linear-gradient(145deg, rgba(18, 60, 84, .96), rgba(8, 31, 49, .98));
  box-shadow: 0 10px 22px rgba(0, 0, 0, .15);
  transform: translateY(-2px);
}
.preset-card.active {
  border-color: rgba(79, 208, 232, .85);
  background: linear-gradient(145deg, rgba(16, 73, 94, .98), rgba(7, 39, 59, .98));
  box-shadow: 0 0 0 1px rgba(79, 208, 232, .16), 0 12px 28px rgba(0, 0, 0, .2), inset 0 1px 0 rgba(176, 241, 255, .12);
}
.preset-card span {
  color: var(--cyan);
  font-size: 13px;
}
.preset-card strong {
  display: block;
  margin: 8px 0;
  font-size: 17px;
}
.preset-card small {
  display: block;
  margin-top: 14px;
  padding: 4px 8px;
  width: fit-content;
  max-width: 100%;
  border: 1px solid rgba(79, 208, 232, .24);
  border-radius: 6px;
  color: #bfe9f4;
  font-size: 12px;
  line-height: 1.3;
  background: rgba(79, 208, 232, .08);
}
/* 现场证据视频（参考视频测试页：隐藏 input + 空态按钮，上传后出现画面） */
.video-stage {
  position: relative;
  height: clamp(220px, 30vw, 420px);
  margin: 0 18px 18px;
  overflow: hidden;
  border: 1px solid rgba(85, 148, 180, .3);
  border-radius: 14px;
  background: #02070d;
  box-shadow: 0 10px 26px rgba(0, 0, 0, .22), inset 0 0 0 1px rgba(255, 255, 255, .025);
}
.hidden-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.video-stage video {
  display: block;
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
.submit-hint {
  margin: -4px 18px 18px;
  padding: 9px 12px;
  border-left: 2px solid rgba(127, 168, 198, .3);
  border-radius: 0 8px 8px 0;
  color: #8fa8ba;
  background: rgba(3, 18, 31, .38);
  font-size: 13px;
  line-height: 1.4;
}
.submit-hint.ready {
  color: var(--green);
  border-left-color: var(--green);
  background: rgba(66, 198, 166, .08);
}
.result-actions {
  justify-content: flex-end;
  gap: 10px;
  padding: 0 16px 16px;
}
.result-content {
  padding: 16px;
}
.detail-result {
  display: grid;
  gap: 14px;
}
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
  flex: 0 0 auto;
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
  border-radius: 12px;
  background: rgba(4, 20, 36, .48);
  box-shadow: 0 8px 18px rgba(0, 0, 0, .1), inset 0 1px 0 rgba(174, 229, 250, .035);
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
  align-items: center;
  gap: 8px;
  margin: 0 16px 16px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 107, 120, .35);
  border-radius: 8px;
  color: #ffd6db;
  background: rgba(255, 107, 120, .12);
}
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .preset-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .sensor-test-page {
    padding: 12px;
  }
  .page-header,
  .panel-header {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }
  .page-header-meta {
    width: 100%;
    flex-wrap: wrap;
  }
  .header-metric {
    flex: 1 1 120px;
  }
  .header-live-state {
    flex: 1 1 120px;
    justify-content: center;
  }
  .preset-grid {
    grid-template-columns: 1fr;
  }
  .camera-picker {
    width: 100%;
    margin: 0;
  }
  .control-panel-header .el-button {
    width: 100%;
  }
}
</style>
