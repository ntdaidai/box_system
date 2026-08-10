<template>
  <div class="screening-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 场景测试 / 视频测试</p>
        <h2>视频测试</h2>
      </div>
      <div class="source-control">
        <span>模拟数据源</span>
        <el-select
          v-model="cameraId"
          placeholder="选择摄像头"
          :loading="cameraLoading"
          class="camera-select"
        >
          <el-option
            v-for="camera in cameras"
            :key="camera.id"
            :value="camera.id"
            :label="camera.name || camera.camera_name || `摄像头 ${camera.id}`"
            :disabled="camera.enabled === false"
          >
            <span>{{ camera.name || camera.camera_name || `摄像头 ${camera.id}` }}</span>
            <small>{{ camera.connected ? '在线' : '模拟可用' }}</small>
          </el-option>
        </el-select>
        <el-button :icon="Refresh" circle title="刷新摄像头" @click="loadCameras" />
      </div>
    </header>

    <section class="status-grid" aria-label="检测状态">
      <div class="status-item">
        <span>任务状态</span>
        <strong>{{ mediaStatus }}</strong>
      </div>
      <div class="status-item">
        <span>数据源</span>
        <strong>{{ selectedCameraName }}</strong>
      </div>
      <div class="status-item">
        <span>视频文件</span>
        <strong>{{ videoName || '未选择' }}</strong>
      </div>
      <div class="status-item accent">
        <span>ECA 链路</span>
        <strong>{{ ecaStatusText }}</strong>
      </div>
    </section>

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
              type="primary"
              :icon="simulationActive ? VideoPause : VideoPlay"
              :disabled="!videoUrl || !cameraId"
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
          <div v-if="videoUrl" class="video-overlay">
            <span>{{ videoName }}</span>
            <span>{{ formatVideoTime(videoRef?.currentTime) }} / {{ formatVideoTime(videoRef?.duration) }}</span>
          </div>
        </div>

        <div class="evidence-strip">
          <div class="strip-title"><span>初筛采样帧</span><b>{{ evidenceFrames.length }} / {{ FRAME_COUNT }} 帧</b></div>
          <div class="frame-strip">
            <figure v-for="(frame, index) in evidenceFrames" :key="frame.id">
              <img v-if="!frame.failed" :src="frame.url" :alt="`关键帧 ${index + 1}`" @error="markFrameFailed(frame)" />
              <div v-else class="frame-error">关键帧加载失败</div>
              <span>初筛帧 {{ index + 1 }}</span>
            </figure>
            <div v-for="slot in Math.max(0, 4 - evidenceFrames.length)" :key="`slot-${slot}`" class="frame-slot">
              {{ String(evidenceFrames.length + slot).padStart(2, '0') }}
            </div>
          </div>
        </div>
      </div>

      <aside class="result-panel">
        <header class="panel-header">
          <div>
            <span class="section-index">02</span>
            <div><small>CHAIN</small><h3>链路结果</h3></div>
          </div>
          <el-tag :type="result ? riskTag : 'info'" effect="dark">{{ result ? riskLabel : '待触发' }}</el-tag>
        </header>

        <div v-if="screening" class="processing-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          <strong>Qwen 正在分析视频画面</strong>
          <span>结果返回后自动提交 ECA 条件判断</span>
        </div>
        <div v-else-if="result" class="result-content">
          <div class="decision-card" :class="riskClass">
            <span>{{ formatResultTime(result.timestamp) }}</span>
            <strong>{{ primarySceneLabel }}</strong>
            <p>{{ result.summary || '模型未返回摘要' }}</p>
          </div>

          <div class="chain-steps">
            <div v-for="step in chainSteps" :key="step.label" :class="['chain-step', step.state]">
              <i></i>
              <span>{{ step.label }}</span>
              <strong>{{ step.value }}</strong>
            </div>
          </div>

          <div class="metric-row">
            <div>
              <span>初筛帧</span>
              <strong>{{ resultImageUrls.length }}</strong>
            </div>
            <div>
              <span>触发场景</span>
              <strong>{{ detectedSceneCount }}</strong>
            </div>
            <div>
              <span>ECA</span>
              <strong>{{ result.eca_dispatched ? '已提交' : '未确认' }}</strong>
            </div>
          </div>

          <div class="scene-list">
            <div
              v-for="item in sortedSceneItems"
              :key="item.key"
              :class="['scene-row', { detected: item.detected }]"
            >
              <div class="scene-label">
                <span>{{ item.label }}</span>
                <b>{{ item.detected ? '触发' : '正常' }}</b>
              </div>
              <el-progress
                :percentage="item.percent"
                :stroke-width="7"
                :show-text="false"
                :color="item.detected ? '#ff6b6b' : '#40c7a7'"
              />
              <small>{{ item.percent }}%</small>
            </div>
          </div>

          <div class="result-meta">
            <span><el-icon><Files /></el-icon>{{ resultImageUrls.length }} 张初筛采样帧已存 MinIO</span>
            <span :class="{ ok: result.eca_dispatched }"><el-icon><CircleCheck /></el-icon>{{ result.eca_dispatched ? '已提交 ECA' : 'ECA 未确认' }}</span>
            <span v-if="result.event_instance_id" class="ok"><el-icon><CircleCheck /></el-icon>4B 视频理解将在事件 {{ result.instance_no }} 中生成 8 帧候选和代表帧</span>
            <span v-if="eventReportId" class="ok"><el-icon><CircleCheck /></el-icon>分析报告已生成</span>
          </div>
          <div v-if="result.event_instance_id" class="result-actions">
            <el-button type="primary" link @click="openEventDetail(result.event_instance_id)">查看事件详情</el-button>
            <el-button v-if="eventReportId" type="success" link @click="openReport">打开报告</el-button>
          </div>
          <el-collapse class="json-collapse">
            <el-collapse-item title="JSON 结果" name="json">
              <pre>{{ formattedResult }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
        <div v-else class="result-empty">
          <el-icon><DataAnalysis /></el-icon>
          <strong>等待链路任务</strong>
          <span>Qwen 初筛、ECA 提交和事件结果将在这里显示</span>
        </div>

        <div v-if="lastError" class="error-banner">
          <el-icon><Warning /></el-icon><span>{{ lastError }}</span>
        </div>
      </aside>
    </section>

    <section class="history-panel">
      <header class="panel-header compact">
        <div><span class="section-index">03</span><div><small>SESSION</small><h3>场景测试记录</h3></div></div>
        <span>{{ history.length }} 条</span>
      </header>
      <el-table :data="history" empty-text="暂无检测记录" class="history-table">
        <el-table-column label="序号" width="72"><template #default="{ $index }"><span class="event-no">{{ $index + 1 }}</span></template></el-table-column>
        <el-table-column label="触发场景" min-width="150"><template #default="{ row }"><strong class="event-name">{{ rowPrimarySceneLabel(row) }}</strong></template></el-table-column>
        <el-table-column label="摘要" min-width="360" show-overflow-tooltip><template #default="{ row }"><span class="event-summary">{{ row.summary || '暂无摘要' }}</span></template></el-table-column>
        <el-table-column label="风险" width="110"><template #default="{ row }"><el-tag :type="tagForRisk(row.risk_level)" effect="dark">{{ labelForRisk(row.risk_level) }}</el-tag></template></el-table-column>
        <el-table-column label="初筛帧" width="96"><template #default="{ row }">{{ (row.image_urls || []).length }} 帧</template></el-table-column>
        <el-table-column label="ECA" width="120"><template #default="{ row }"><span class="eca-cell"><i :class="{ ok: row.eca_dispatched }"></i>{{ row.eca_dispatched ? '已提交' : '未确认' }}</span></template></el-table-column>
        <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatResultTime(row.timestamp) }}</template></el-table-column>
        <el-table-column label="操作" width="92" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="selectHistory(row)">查看</el-button></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheck, DataAnalysis, Files, Loading,
  Refresh, VideoCamera, VideoPause, VideoPlay, Warning,
} from '@element-plus/icons-vue'
import { getCameraList, simulateCameraVideoScreening } from '@/api/camera'
import { getUnifiedSafetyEventDetail } from '@/api/integration'
import { camerasFromPayload } from '@/utils/cameraSnapshots'

const FRAME_COUNT = 4
const WINDOW_SECONDS = 10
const router = useRouter()
const sceneDefinitions = [
  ['mudslide_detected', 'mudslide_confidence', '泥石流'],
  ['landslide_detected', 'landslide_confidence', '滑坡'],
  ['flood_detected', 'flood_confidence', '洪水'],
  ['earthquake_detected', 'earthquake_confidence', '地震'],
  ['person_present', 'person_confidence', '人员'],
  ['boat_present', 'boat_confidence', '船只/捕鱼'],
]

const cameras = ref([])
const cameraId = ref('')
const cameraLoading = ref(false)
const fileInputRef = ref(null)
const videoRef = ref(null)
const videoUrl = ref('')
const videoName = ref('')
const videoFile = ref(null)
const evidenceFrames = ref([])
const simulationActive = ref(false)
const screening = ref(false)
const result = ref(null)
const eventDetail = ref(null)
const history = ref([])
const lastError = ref('')
const pollTimer = ref(null)

const selectedCameraName = computed(() => {
  const camera = cameras.value.find(item => item.id === cameraId.value)
  return camera?.name || camera?.camera_name || (cameraId.value ? `摄像头 ${cameraId.value}` : '--')
})
const mediaStatus = computed(() => {
  if (screening.value) return '模型分析中'
  if (simulationActive.value) return '实时采集中'
  if (videoUrl.value) return '视频已就绪'
  return '等待输入'
})
const sceneItems = computed(() => sceneDefinitions.map(([key, confidenceKey, label]) => ({
  key,
  label,
  detected: Number(result.value?.scene?.[key] || 0) === 1,
  percent: Math.round(Number(result.value?.confidence?.[confidenceKey] || 0) * 100),
})))
const sortedSceneItems = computed(() => [...sceneItems.value].sort((a, b) => {
  if (a.detected !== b.detected) return a.detected ? -1 : 1
  return b.percent - a.percent
}))
const detectedSceneCount = computed(() => sceneItems.value.filter(item => item.detected).length)
const primarySceneLabel = computed(() => {
  const detected = sortedSceneItems.value.find(item => item.detected)
  if (detected) return `${detected.label}疑似触发`
  const top = sortedSceneItems.value[0]
  return top?.percent ? `${top.label}关注度最高` : '未发现明确异常'
})
const riskLabel = computed(() => labelForRisk(result.value?.risk_level))
const riskTag = computed(() => tagForRisk(result.value?.risk_level))
const riskClass = computed(() => `risk-${String(result.value?.risk_level || 'LOW').toLowerCase()}`)
const resultImageUrls = computed(() => normalizeMediaUrls(result.value?.image_urls || []))
const detailEvent = computed(() => eventDetail.value?.event || null)
const eventReportId = computed(() => detailEvent.value?.analysis_report_id || result.value?.analysis_report_id || null)
const ecaStatusText = computed(() => {
  if (screening.value) return '分析中'
  if (eventReportId.value) return '报告已生成'
  if (result.value?.eca_dispatched) return '已提交'
  if (result.value) return '未确认'
  return '待触发'
})
const chainSteps = computed(() => [
  { label: '视频输入', value: videoName.value || '已上传', state: videoFile.value ? 'done' : 'pending' },
  { label: 'Qwen 初筛', value: result.value ? primarySceneLabel.value : '等待', state: result.value ? 'done' : 'pending' },
  { label: 'ECA 提交', value: result.value?.eca_dispatched ? '已提交' : '未确认', state: result.value?.eca_dispatched ? 'done' : 'pending' },
  {
    label: '4B 视频理解',
    value: detailEvent.value?.status === 'COMPLETED' ? '工作流已完成' : (result.value?.event_instance_id ? '工作流处理中' : (result.value?.eca_dispatched ? '等待事件回写' : '等待触发')),
    state: detailEvent.value?.status === 'COMPLETED' ? 'done' : (result.value?.event_instance_id ? 'active' : 'pending'),
  },
  {
    label: '报告生成',
    value: eventReportId.value ? '已生成' : (result.value?.event_instance_id ? '生成中' : '等待事件'),
    state: eventReportId.value ? 'done' : (result.value?.event_instance_id ? 'active' : 'pending'),
  },
])
const formattedResult = computed(() => JSON.stringify(result.value, null, 2))

async function loadCameras() {
  cameraLoading.value = true
  try {
    const response = await getCameraList()
    cameras.value = camerasFromPayload(response.data)
    if (!cameras.value.some(item => item.id === cameraId.value)) {
      cameraId.value = cameras.value.find(item => item.enabled !== false)?.id || ''
    }
  } catch (error) {
    lastError.value = error?.response?.data?.detail || '摄像头列表加载失败'
  } finally {
    cameraLoading.value = false
  }
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
      { windowSeconds: WINDOW_SECONDS },
    )
    const normalizedResult = {
      ...response.data,
      image_urls: normalizeMediaUrls(response.data?.image_urls || []),
    }
    result.value = normalizedResult
    evidenceFrames.value = normalizedResult.image_urls.slice(0, FRAME_COUNT).map((url, index) => ({
      id: `server-frame-${Date.now()}-${index}`,
      blob: null,
      url,
      failed: false,
      timeLabel: `FRAME ${String(index + 1).padStart(2, '0')}`,
    }))
    history.value = [normalizedResult, ...history.value].slice(0, 20)
    if (normalizedResult.event_instance_id) {
      await refreshEventDetail(normalizedResult.event_instance_id)
      startEventPolling(normalizedResult.event_instance_id)
    }
    ElMessage.success('Qwen 视频初筛完成，结果已提交 ECA')
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '视频初筛请求失败'
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
    const event = response.data?.event || {}
    result.value = {
      ...(result.value || {}),
      event_status: event.status,
      event_state: event.state,
      analysis_report_id: event.analysis_report_id,
    }
    if (event.analysis_report_id) {
      stopEventPolling()
    }
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '事件详情刷新失败'
  }
}

function startEventPolling(id) {
  stopEventPolling()
  pollTimer.value = window.setInterval(() => refreshEventDetail(id), 3000)
}

function stopEventPolling() {
  if (pollTimer.value) window.clearInterval(pollTimer.value)
  pollTimer.value = null
}

function normalizeMediaUrls(urls) {
  return (urls || []).map(normalizeMediaUrl).filter(Boolean)
}

function normalizeMediaUrl(url) {
  if (!url) return ''
  const raw = String(url)
  if (raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('/')) return raw
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

function markFrameFailed(frame) {
  frame.failed = true
}

function sceneItemsFor(row) {
  return sceneDefinitions.map(([key, confidenceKey, label]) => ({
    key,
    label,
    detected: Number(row?.scene?.[key] || 0) === 1,
    percent: Math.round(Number(row?.confidence?.[confidenceKey] || 0) * 100),
  })).sort((a, b) => {
    if (a.detected !== b.detected) return a.detected ? -1 : 1
    return b.percent - a.percent
  })
}

function rowPrimarySceneLabel(row) {
  const items = sceneItemsFor(row)
  const detected = items.find(item => item.detected)
  if (detected) return `${detected.label}疑似触发`
  const top = items[0]
  return top?.percent ? `${top.label}关注度最高` : '未发现明确异常'
}

function selectHistory(row) {
  stopEventPolling()
  result.value = row
  eventDetail.value = null
  evidenceFrames.value = normalizeMediaUrls(row.image_urls || []).slice(0, FRAME_COUNT).map((url, index) => ({
    id: `history-frame-${Date.now()}-${index}`,
    url,
    failed: false,
  }))
  if (row.event_instance_id) {
    refreshEventDetail(row.event_instance_id)
    startEventPolling(row.event_instance_id)
  }
}

function openEventDetail(id) {
  if (!id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id } })
}

function openReport() {
  const instanceNo = result.value?.instance_no || detailEvent.value?.instance_no
  if (!instanceNo) return
  window.open(`/api/onlyoffice/document/dam_event_report_${instanceNo}`, '_blank')
}

function labelForRisk(level) { return ({ HIGH: '高风险', MEDIUM: '中风险', LOW: '低风险' })[level] || '低风险' }
function tagForRisk(level) { return ({ HIGH: 'danger', MEDIUM: 'warning', LOW: 'success' })[level] || 'info' }
function formatResultTime(timestamp) {
  if (!timestamp) return '--'
  const date = new Date(Number(timestamp) * 1000)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}
function formatVideoTime(value) {
  const seconds = Number(value)
  if (!Number.isFinite(seconds)) return '00:00'
  const minute = Math.floor(seconds / 60)
  const rest = Math.floor(seconds % 60)
  return `${String(minute).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

onMounted(loadCameras)
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
.source-control,
.media-tools,
.panel-header,
.panel-header > div:first-child,
.panel-title,
.runtime-state,
.result-meta span,
.eca-cell {
  display: flex;
  align-items: center;
}
.page-header {
  justify-content: space-between;
  gap: 18px;
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
  font-weight: 700;
}
h3 {
  font-size: 16px;
}
.source-control {
  gap: 10px;
  color: #b3c7d6;
  font-size: 13px;
}
.camera-select {
  width: 260px;
}
.camera-select :deep(.el-select__wrapper) {
  min-height: 36px;
  background: #0c2134;
  box-shadow: inset 0 0 0 1px var(--line);
}
.camera-select :deep(.el-select__selected-item) {
  color: var(--text);
}
.source-control small {
  float: right;
  margin-left: 24px;
  color: #7594aa;
}
.status-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr 1.6fr 1fr;
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
.status-item span {
  display: block;
  margin-bottom: 6px;
  color: #7794aa;
  font-size: 12px;
}
.status-item strong {
  display: block;
  overflow: hidden;
  color: #e8f4fb;
  font-size: 16px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-item.accent strong {
  color: var(--green);
}
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(380px, .9fr);
  gap: 16px;
  margin-top: 16px;
}
.media-panel,
.result-panel,
.history-panel {
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
.video-overlay {
  position: absolute;
  right: 12px;
  bottom: 12px;
  left: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 12px;
  color: #d9eaf5;
  background: rgba(2,7,13,.82);
  font-size: 12px;
  pointer-events: none;
}
.video-overlay span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.frame-strip figure,
.frame-slot {
  aspect-ratio: 16 / 9;
  border: 1px solid #284962;
  border-radius: 6px;
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
  color: #3c5b70;
  background: #0b2032;
  font-size: 18px;
  font-weight: 800;
}
.result-panel {
  min-height: 620px;
}
.processing-state,
.result-empty {
  display: grid;
  min-height: 500px;
  place-content: center;
  justify-items: center;
  gap: 11px;
  color: var(--muted);
  text-align: center;
}
.processing-state .el-icon {
  color: var(--amber);
  font-size: 38px;
}
.processing-state strong,
.result-empty strong {
  color: #d9e9f5;
}
.processing-state span,
.result-empty span {
  font-size: 12px;
}
.result-empty .el-icon {
  color: #426d87;
  font-size: 46px;
}
.result-content {
  padding: 16px;
}
.decision-card {
  padding: 14px;
  border: 1px solid rgba(127,168,198,.22);
  border-left: 4px solid var(--green);
  border-radius: 8px;
  background: #091a29;
}
.decision-card.risk-high {
  border-left-color: var(--red);
  background: rgba(112,31,42,.22);
}
.decision-card.risk-medium {
  border-left-color: var(--amber);
  background: rgba(116,77,29,.18);
}
.decision-card span {
  color: #7c98ad;
  font-size: 11px;
}
.decision-card strong {
  display: block;
  margin-top: 8px;
  color: #f3f8fd;
  font-size: 20px;
}
.decision-card p {
  margin: 8px 0 0;
  color: #d8e8f2;
  line-height: 1.65;
}
.chain-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}
.chain-step {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(127,168,198,.18);
  border-radius: 6px;
  background: #071725;
}
.chain-step i {
  display: block;
  width: 8px;
  height: 8px;
  margin-bottom: 8px;
  border-radius: 50%;
  background: #5d7182;
}
.chain-step.done i {
  background: var(--green);
  box-shadow: 0 0 0 5px rgba(66,198,166,.1);
}
.chain-step.active i {
  background: var(--cyan);
  box-shadow: 0 0 0 5px rgba(79,208,232,.1);
}
.chain-step span,
.chain-step strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chain-step span {
  color: #7895aa;
  font-size: 11px;
}
.chain-step strong {
  margin-top: 5px;
  color: #eaf5fc;
  font-size: 13px;
}
.metric-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}
.metric-row div {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(127,168,198,.18);
  border-radius: 6px;
  background: #0a1928;
}
.metric-row span {
  display: block;
  color: #7895aa;
  font-size: 11px;
}
.metric-row strong {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  color: #eaf5fc;
  font-size: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scene-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.scene-row {
  display: grid;
  grid-template-columns: minmax(90px, .9fr) minmax(110px, 1.2fr) 42px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid rgba(127,168,198,.18);
  border-radius: 6px;
  background: #091a29;
}
.scene-row.detected {
  border-color: rgba(255,107,120,.46);
  background: rgba(112,31,42,.18);
}
.scene-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.scene-label span {
  color: #d4e5ef;
  font-size: 13px;
}
.scene-label b {
  color: var(--green);
  font-size: 11px;
  white-space: nowrap;
}
.scene-row.detected .scene-label b {
  color: #ff9ba4;
}
.scene-row small {
  color: #8aa5b8;
  font-size: 11px;
  text-align: right;
}
.result-meta {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}
.result-meta span {
  gap: 7px;
  color: #91aabd;
  font-size: 12px;
}
.result-meta span.ok {
  color: var(--green);
}
.result-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.json-collapse {
  margin-top: 12px;
  border-color: var(--line);
}
.json-collapse :deep(.el-collapse-item__header),
.json-collapse :deep(.el-collapse-item__wrap) {
  color: #bed3e2;
  background: transparent;
  border-color: var(--line);
}
.json-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}
pre {
  max-height: 260px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: #a4ddcf;
  background: #030c13;
  font: 11px/1.55 Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
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
.history-panel {
  margin-top: 16px;
}
.panel-header.compact {
  min-height: 56px;
}
.panel-header.compact > span {
  color: #7894a9;
  font-size: 12px;
}
.history-table {
  background: #091b2b;
}
.history-table :deep(.el-table__inner-wrapper::before) {
  background: var(--line);
}
.history-table :deep(th.el-table__cell) {
  background: #102940;
  color: #d4e7f4;
}
.history-table :deep(tr),
.history-table :deep(td.el-table__cell) {
  background: #091b2b;
  color: #bed3e2;
}
.history-table :deep(td.el-table__cell),
.history-table :deep(th.el-table__cell) {
  border-bottom-color: rgba(105,165,207,.15);
}
.history-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #0e273d;
}
.event-no {
  display: inline-grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid rgba(79,208,232,.28);
  border-radius: 6px;
  color: var(--cyan);
  background: rgba(79,208,232,.08);
  font-weight: 700;
}
.event-name {
  color: #e8f5fd;
  font-weight: 700;
}
.event-summary {
  color: #bed3e2;
}
.eca-cell {
  gap: 7px;
}
.eca-cell i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #6d7f8e;
}
.eca-cell i.ok {
  background: var(--green);
}
@media (max-width: 1180px) {
  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .chain-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
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
  .source-control,
  .media-tools {
    flex-wrap: wrap;
  }
  .camera-select {
    flex: 1;
    width: auto;
    min-width: 190px;
  }
  .status-grid,
  .metric-row {
    grid-template-columns: 1fr;
  }
  .video-stage {
    height: 340px;
  }
  .frame-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .scene-row {
    grid-template-columns: 1fr;
  }
  .scene-row small {
    text-align: left;
  }
}
</style>
