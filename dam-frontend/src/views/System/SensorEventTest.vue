<template>
  <div class="sensor-test-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 场景测试 / 传感器测试</p>
        <h2>传感器测试</h2>
      </div>
      <el-tag effect="dark" type="warning">传感器 ECA + 视频证据</el-tag>
    </header>

    <section class="status-grid">
      <div class="status-item">
        <span>当前事件</span>
        <strong>{{ selectedPreset.label }}</strong>
      </div>
      <div class="status-item">
        <span>传感器值</span>
        <strong>{{ windSpeed }} m/s</strong>
      </div>
      <div class="status-item">
        <span>证据视频</span>
        <strong>{{ videoName || '未选择' }}</strong>
      </div>
      <div class="status-item accent">
        <span>链路状态</span>
        <strong>{{ flowStatusText }}</strong>
      </div>
    </section>

    <section class="workspace">
      <div class="control-panel">
        <header class="panel-header">
          <div><span class="section-index">01</span><div><small>SENSOR</small><h3>触发参数</h3></div></div>
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
            <small>{{ preset.expression }}</small>
          </button>
        </div>

        <div class="form-grid">
          <label>
            <span>风速</span>
            <el-input-number v-model="windSpeed" :precision="1" :step="0.5" :min="0" :max="80" controls-position="right" />
          </label>
          <label>
            <span>风向</span>
            <el-input-number v-model="windDirection" :precision="0" :step="5" :min="0" :max="360" controls-position="right" />
          </label>
          <label>
            <span>摄像头 ID</span>
            <el-input-number v-model="cameraId" :min="1" :max="9999" controls-position="right" />
          </label>
          <label>
            <span>冷却期</span>
            <el-switch v-model="forceTrigger" active-text="测试跳过" inactive-text="遵守" />
          </label>
        </div>

        <div class="video-uploader">
          <div class="uploader-copy">
            <strong>现场证据视频</strong>
            <span>{{ videoName || '选择几秒到十几秒的摄像头视频，作为传感器告警的证据补充。' }}</span>
          </div>
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            accept="video/mp4,video/quicktime,video/webm,.m4v"
            :on-change="handleVideoFile"
          >
            <el-button :icon="FolderOpened">选择视频</el-button>
          </el-upload>
        </div>

        <video v-if="videoUrl" class="video-preview" :src="videoUrl" controls playsinline />

        <el-collapse class="json-collapse">
          <el-collapse-item title="传感器 JSON" name="payload">
            <el-input v-model="sensorJsonText" type="textarea" :rows="8" spellcheck="false" />
          </el-collapse-item>
        </el-collapse>

        <div class="actions">
          <el-button :icon="Refresh" @click="resetPayload">重置参数</el-button>
          <el-button
            type="primary"
            :icon="Promotion"
            :loading="submitting"
            :disabled="!canSubmit"
            @click="submit"
          >
            触发传感器 ECA
          </el-button>
        </div>
      </div>

      <aside class="result-panel">
        <header class="panel-header">
          <div><span class="section-index">02</span><div><small>ECA</small><h3>执行结果</h3></div></div>
          <el-tag :type="statusTag">{{ detailEvent?.status || 'WAITING' }}</el-tag>
        </header>

        <div v-if="!triggerResult && !submitting" class="empty-result">
          <el-icon><DataAnalysis /></el-icon>
          <strong>等待测试触发</strong>
          <span>触发后会显示安全事件、条件匹配和报告状态。</span>
        </div>

        <div v-else class="result-body">
          <div class="event-summary">
            <span>{{ detailEvent?.event_name || triggerResult?.event?.event_name || '--' }}</span>
            <strong>{{ detailEvent?.instance_no || triggerResult?.instance_no || '--' }}</strong>
            <p>{{ detailEvent?.summary || '事件已进入 ECA 处理链路' }}</p>
          </div>

          <div class="metric-row">
            <div>
              <span>风险</span>
              <strong>{{ detailEvent?.risk_label || riskLabel }}</strong>
            </div>
            <div>
              <span>状态</span>
              <strong>{{ stateLabel }}</strong>
            </div>
            <div>
              <span>报告</span>
              <strong>{{ detailEvent?.analysis_report_id ? '已生成' : '等待中' }}</strong>
            </div>
          </div>

          <div class="condition-list">
            <div
              v-for="item in conditionItems"
              :key="item.condition_id"
              :class="['condition-row', { matched: item.matched }]"
            >
              <div>
                <strong>{{ item.condition_name }}</strong>
                <span>{{ item.expression }}</span>
              </div>
              <el-tag :type="item.matched ? 'success' : 'info'" size="small">{{ item.matched ? '匹配' : '未匹配' }}</el-tag>
            </div>
          </div>

          <el-timeline v-if="timeline.length" class="timeline">
            <el-timeline-item
              v-for="item in timeline"
              :key="item.id"
              :timestamp="formatTime(item.create_time)"
              :type="timelineType(item.status)"
            >
              <strong>{{ item.title || item.message }}</strong>
              <p v-if="item.title">{{ item.message }}</p>
            </el-timeline-item>
          </el-timeline>

          <div class="result-actions">
            <el-button :disabled="!detailEvent?.id" @click="refreshDetail">刷新详情</el-button>
            <el-button type="success" :disabled="!detailEvent?.analysis_report_id" @click="openReport">打开报告</el-button>
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, FolderOpened, Promotion, Refresh, Warning } from '@element-plus/icons-vue'
import { simulateSensorEvent } from '@/api/eca'
import { getUnifiedSafetyEventDetail } from '@/api/integration'

const presets = [
  { key: 'wind6', eventId: 22, sensorName: 'wind', label: '大风预警', level: '6级', speed: 11.5, risk: 'LOW', expression: 'wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9' },
  { key: 'wind7', eventId: 23, sensorName: 'wind', label: '强风预警', level: '7级', speed: 15.0, risk: 'LOW', expression: 'wind_speed_ms >= 13.9 AND wind_speed_ms < 17.2' },
  { key: 'wind8', eventId: 24, sensorName: 'wind', label: '大风警报', level: '8级', speed: 18.5, risk: 'MEDIUM', expression: 'wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8' },
  { key: 'wind12', eventId: 28, sensorName: 'wind', label: '飓风警报', level: '12级', speed: 33.5, risk: 'HIGH', expression: 'wind_speed_ms >= 32.7' },
]

const selectedKey = ref('wind8')
const windSpeed = ref(18.5)
const windDirection = ref(135)
const cameraId = ref(1)
const forceTrigger = ref(true)
const sensorJsonText = ref('')
const videoFile = ref(null)
const videoUrl = ref('')
const videoName = ref('')
const submitting = ref(false)
const triggerResult = ref(null)
const detail = ref(null)
const lastError = ref('')
const pollTimer = ref(null)

const selectedPreset = computed(() => presets.find(item => item.key === selectedKey.value) || presets[0])
const detailEvent = computed(() => detail.value?.event || null)
const timeline = computed(() => detail.value?.timeline || [])
const conditionItems = computed(() => triggerResult.value?.condition_check?.conditions || [])
const riskLabel = computed(() => ({ HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险' })[selectedPreset.value.risk] || '--')
const flowStatusText = computed(() => {
  if (submitting.value) return '触发中'
  if (detailEvent.value?.analysis_report_id) return '报告已生成'
  if (detailEvent.value?.status) return detailEvent.value.status
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
const stateLabel = computed(() => {
  if (!detailEvent.value) return '--'
  const state = detailEvent.value.state === 'RESOLVED' ? '已闭环' : '处置中'
  return `${state} / ${detailEvent.value.status}`
})
const canSubmit = computed(() => Boolean(selectedPreset.value?.eventId && sensorJsonText.value.trim()))

function buildSensorData() {
  return {
    wind_speed_ms: Number(windSpeed.value),
    wind_direction: Number(windDirection.value),
    wind_level: windLevelFromSpeed(Number(windSpeed.value)),
    sensor_location: '库坝现场风速传感器',
    camera_id: Number(cameraId.value),
  }
}

function resetPayload() {
  const data = buildSensorData()
  sensorJsonText.value = JSON.stringify(data, null, 2)
}

function selectPreset(key) {
  const preset = presets.find(item => item.key === key)
  if (!preset) return
  selectedKey.value = key
  windSpeed.value = preset.speed
  resetPayload()
}

function handleVideoFile(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > 300 * 1024 * 1024) return ElMessage.error('视频大小不能超过 300MB')
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoFile.value = raw
  videoUrl.value = URL.createObjectURL(raw)
  videoName.value = raw.name
}

async function submit() {
  const preset = selectedPreset.value
  let sensorData
  try {
    sensorData = JSON.parse(sensorJsonText.value || '{}')
  } catch (error) {
    ElMessage.error('传感器 JSON 格式不正确')
    return
  }
  submitting.value = true
  lastError.value = ''
  triggerResult.value = null
  detail.value = null
  stopPolling()
  try {
    const response = await simulateSensorEvent({
      eventId: preset.eventId,
      sensorName: preset.sensorName,
      sensorData,
      cameraId: Number(cameraId.value),
      force: forceTrigger.value,
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

async function refreshDetail() {
  const id = triggerResult.value?.event_instance_id || detailEvent.value?.id
  if (!id) return
  const response = await getUnifiedSafetyEventDetail(id)
  detail.value = response.data
  if (detailEvent.value?.analysis_report_id || ['COMPLETED', 'FAILED'].includes(detailEvent.value?.status)) {
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

function openReport() {
  const instanceNo = detailEvent.value?.instance_no
  if (!instanceNo) return
  window.open(`/api/onlyoffice/document/dam_event_report_${instanceNo}`, '_blank')
}

function windLevelFromSpeed(speed) {
  if (speed >= 32.7) return 12
  if (speed >= 28.5) return 11
  if (speed >= 24.5) return 10
  if (speed >= 20.8) return 9
  if (speed >= 17.2) return 8
  if (speed >= 13.9) return 7
  if (speed >= 10.8) return 6
  return 0
}

function timelineType(status) {
  if (status === 'FAILED') return 'danger'
  if (status === 'SUCCESS') return 'success'
  return 'primary'
}

function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

watch([windSpeed, windDirection, cameraId], resetPayload)
resetPayload()

onBeforeUnmount(() => {
  stopPolling()
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
})
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
  padding: 20px;
  color: var(--text);
  background: #07131f;
}
.page-header,
.panel-header,
.panel-header > div:first-child,
.video-uploader,
.actions,
.result-actions {
  display: flex;
  align-items: center;
}
.page-header {
  justify-content: space-between;
  gap: 16px;
}
.page-header p {
  margin: 0 0 4px;
  color: #7ea9c6;
  font-size: 13px;
}
h2,
h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}
h2 {
  font-size: 24px;
}
h3 {
  font-size: 16px;
}
.status-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1.6fr 1fr;
  gap: 10px;
  margin-top: 16px;
}
.status-item {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #0b1d2e;
}
.status-item span,
.metric-row span {
  display: block;
  margin-bottom: 6px;
  color: #7794aa;
  font-size: 12px;
}
.status-item strong,
.metric-row strong {
  display: block;
  overflow: hidden;
  color: #e8f4fb;
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-item.accent strong {
  color: var(--green);
}
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(380px, .85fr);
  gap: 16px;
  margin-top: 16px;
}
.control-panel,
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
.panel-header > div:first-child {
  gap: 11px;
}
.panel-header small {
  display: block;
  margin-bottom: 2px;
  color: #6d8ba2;
  font-size: 11px;
}
.section-index {
  display: inline-grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid rgba(79, 208, 232, .42);
  border-radius: 50%;
  color: var(--cyan);
  font-weight: 700;
}
.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 16px;
}
.preset-card {
  min-width: 0;
  min-height: 112px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--text);
  text-align: left;
  background: #0a1d2f;
  cursor: pointer;
}
.preset-card.active {
  border-color: rgba(79, 208, 232, .85);
  background: #0e3146;
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
  color: var(--muted);
  line-height: 1.5;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 0 16px 16px;
}
.form-grid label > span {
  display: block;
  margin-bottom: 8px;
  color: #9db5c6;
  font-size: 13px;
}
.form-grid :deep(.el-input-number),
.form-grid :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}
.video-uploader {
  justify-content: space-between;
  gap: 14px;
  margin: 0 16px 16px;
  padding: 14px;
  border: 1px dashed rgba(127, 168, 198, .36);
  border-radius: 8px;
  background: #081827;
}
.uploader-copy {
  min-width: 0;
}
.uploader-copy strong,
.uploader-copy span {
  display: block;
}
.uploader-copy span {
  overflow: hidden;
  margin-top: 5px;
  color: var(--muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.video-preview {
  display: block;
  width: calc(100% - 32px);
  max-height: 320px;
  margin: 0 16px 16px;
  border-radius: 8px;
  background: #02070d;
}
.json-collapse {
  margin: 0 16px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.json-collapse :deep(.el-collapse-item__header),
.json-collapse :deep(.el-collapse-item__wrap) {
  border: 0;
  color: #d7eaf6;
  background: #0a1d2e;
}
.json-collapse :deep(textarea) {
  font-family: Consolas, Monaco, monospace;
}
.actions,
.result-actions {
  justify-content: flex-end;
  gap: 10px;
  padding: 0 16px 16px;
}
.empty-result {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: var(--muted);
}
.empty-result .el-icon {
  color: var(--cyan);
  font-size: 38px;
}
.result-body {
  padding: 16px;
}
.event-summary {
  padding: 14px;
  border-radius: 8px;
  background: #0a1d2e;
}
.event-summary span {
  color: var(--cyan);
}
.event-summary strong {
  display: block;
  margin-top: 6px;
  color: #fff;
  font-size: 20px;
  word-break: break-all;
}
.event-summary p {
  margin: 8px 0 0;
  color: var(--muted);
  line-height: 1.6;
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0;
}
.metric-row > div {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #081827;
}
.condition-list {
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
}
.condition-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #081827;
}
.condition-row.matched {
  border-color: rgba(66, 198, 166, .48);
}
.condition-row strong,
.condition-row span {
  display: block;
}
.condition-row strong {
  color: #ecf8fd;
}
.condition-row span {
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
}
.timeline {
  max-height: 340px;
  overflow: auto;
  padding: 6px 4px 0;
}
.timeline p {
  margin: 4px 0 0;
  color: var(--muted);
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
@media (max-width: 1200px) {
  .workspace,
  .status-grid {
    grid-template-columns: 1fr;
  }
  .preset-grid,
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .page-header,
  .video-uploader {
    align-items: stretch;
    flex-direction: column;
  }
  .preset-grid,
  .form-grid,
  .metric-row {
    grid-template-columns: 1fr;
  }
}
</style>
