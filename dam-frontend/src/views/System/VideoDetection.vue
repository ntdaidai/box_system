<template>
  <div class="screening-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 视频检测</p>
        <h2>视频检测</h2>
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

    <section class="control-band">
      <el-radio-group v-model="inputMode" @change="changeInputMode">
        <el-radio-button value="video"><el-icon><VideoCamera /></el-icon>视频文件</el-radio-button>
        <el-radio-button value="images"><el-icon><Picture /></el-icon>图片组</el-radio-button>
      </el-radio-group>

      <div class="chain-state" aria-label="处理链路状态">
        <span :class="{ done: evidenceFrames.length }"><i>1</i>画面采集</span>
        <el-icon><ArrowRight /></el-icon>
        <span :class="{ active: screening, done: result }"><i>2</i>Qwen 初筛</span>
        <el-icon><ArrowRight /></el-icon>
        <span :class="{ done: result?.eca_dispatched }"><i>3</i>ECA</span>
      </div>

      <div class="control-actions">
        <el-upload
          v-if="inputMode === 'video'"
          :auto-upload="false"
          :show-file-list="false"
          accept="video/mp4,video/quicktime,video/webm,.m4v"
          :on-change="handleVideoFile"
        >
          <el-button :icon="FolderOpened">选择视频</el-button>
        </el-upload>
        <el-upload
          v-else
          multiple
          :limit="4"
          :auto-upload="false"
          :show-file-list="false"
          accept="image/jpeg,image/png,image/webp"
          :on-change="handleImageFiles"
          :on-exceed="handleImageExceed"
        >
          <el-button :icon="FolderOpened">选择图片</el-button>
        </el-upload>
        <el-button
          v-if="inputMode === 'video'"
          type="primary"
          :icon="simulationActive ? VideoPause : VideoPlay"
          :disabled="!videoUrl || !cameraId"
          @click="toggleSimulation"
        >
          {{ simulationActive ? '暂停模拟' : '开始模拟' }}
        </el-button>
        <el-button
          v-else
          type="primary"
          :icon="Promotion"
          :loading="screening"
          :disabled="!imageFrames.length || !cameraId"
          @click="submitImageFrames"
        >
          提交初筛
        </el-button>
      </div>
    </section>

    <section class="workspace">
      <div class="media-panel">
        <header class="panel-header">
          <div>
            <span class="section-index">01</span>
            <div><small>INPUT</small><h3>模拟画面</h3></div>
          </div>
          <div class="runtime-state">
            <i :class="{ live: simulationActive }"></i>
            {{ mediaStatus }}
          </div>
        </header>

        <div v-if="inputMode === 'video'" class="video-stage">
          <video
            v-if="videoUrl"
            ref="videoRef"
            :src="videoUrl"
            controls
            playsinline
            @ended="handleVideoEnded"
            @pause="handleNativePause"
          />
          <button v-else class="empty-stage" type="button" @click="triggerVideoPickerHint">
            <el-icon><VideoCamera /></el-icon>
            <strong>选择本地视频</strong>
            <span>MP4、MOV、WEBM 或 M4V</span>
          </button>
          <div v-if="videoUrl" class="video-overlay">
            <span>{{ videoName }}</span>
            <span>{{ formatVideoTime(videoRef?.currentTime) }} / {{ formatVideoTime(videoRef?.duration) }}</span>
          </div>
        </div>

        <div v-else class="image-stage" :class="{ empty: !imageFrames.length }">
          <div v-if="imageFrames.length" class="image-grid">
            <figure v-for="(frame, index) in imageFrames" :key="frame.id">
              <img :src="frame.url" :alt="`模拟画面 ${index + 1}`" />
              <figcaption>FRAME {{ String(index + 1).padStart(2, '0') }}</figcaption>
              <button title="移除图片" @click="removeImageFrame(frame.id)"><el-icon><Close /></el-icon></button>
            </figure>
          </div>
          <button v-else class="empty-stage" type="button" @click="triggerImagePickerHint">
            <el-icon><Picture /></el-icon>
            <strong>选择 1–4 张连续画面</strong>
            <span>JPG、PNG 或 WEBP</span>
          </button>
        </div>

        <div class="evidence-strip">
          <div class="strip-title"><span>当前采样窗口</span><b>{{ evidenceFrames.length }} / 4 帧</b></div>
          <div class="frame-strip">
            <figure v-for="(frame, index) in evidenceFrames" :key="frame.id">
              <img :src="frame.url" :alt="`关键帧 ${index + 1}`" />
              <span>{{ frame.timeLabel }}</span>
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
            <div><small>OUTPUT</small><h3>初筛结果</h3></div>
          </div>
          <el-tag v-if="result" :type="riskTag" effect="dark">{{ riskLabel }}</el-tag>
        </header>

        <div v-if="screening" class="processing-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          <strong>Qwen 正在分析 {{ submittingFrameCount }} 张画面</strong>
          <span>结果返回后自动提交 ECA 条件判断</span>
        </div>
        <div v-else-if="result" class="result-content">
          <div class="summary-block">
            <span>{{ formatResultTime(result.timestamp) }}</span>
            <p>{{ result.summary }}</p>
          </div>
          <div class="scene-grid">
            <div
              v-for="item in sceneItems"
              :key="item.key"
              :class="['scene-item', { detected: item.detected }]"
            >
              <div><span>{{ item.label }}</span><b>{{ item.detected ? '触发' : '正常' }}</b></div>
              <el-progress
                :percentage="item.percent"
                :stroke-width="5"
                :show-text="false"
                :color="item.detected ? '#ff6b6b' : '#40c7a7'"
              />
              <small>置信度 {{ item.percent }}%</small>
            </div>
          </div>
          <div class="result-meta">
            <span><el-icon><Files /></el-icon>{{ result.image_urls?.length || 0 }} 张证据已存 MinIO</span>
            <span :class="{ ok: result.eca_dispatched }"><el-icon><CircleCheck /></el-icon>{{ result.eca_dispatched ? '已提交 ECA' : 'ECA 未确认' }}</span>
          </div>
          <el-collapse class="json-collapse">
            <el-collapse-item title="JSON 结果" name="json">
              <pre>{{ formattedResult }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
        <div v-else class="result-empty">
          <el-icon><DataAnalysis /></el-icon>
          <strong>等待初筛任务</strong>
          <span>结果将在这里显示</span>
        </div>

        <div v-if="lastError" class="error-banner">
          <el-icon><Warning /></el-icon><span>{{ lastError }}</span>
        </div>
      </aside>
    </section>

    <section class="history-panel">
      <header class="panel-header compact">
        <div><span class="section-index">03</span><div><small>SESSION</small><h3>本次记录</h3></div></div>
        <span>{{ history.length }} 条</span>
      </header>
      <el-table :data="history" empty-text="暂无检测记录" class="history-table">
        <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatResultTime(row.timestamp) }}</template></el-table-column>
        <el-table-column label="数据源" min-width="150"><template #default>{{ selectedCameraName }}</template></el-table-column>
        <el-table-column label="风险" width="110"><template #default="{ row }"><el-tag :type="tagForRisk(row.risk_level)">{{ labelForRisk(row.risk_level) }}</el-tag></template></el-table-column>
        <el-table-column prop="summary" label="Qwen 摘要" min-width="360" show-overflow-tooltip />
        <el-table-column label="ECA" width="120"><template #default="{ row }"><span class="eca-cell"><i :class="{ ok: row.eca_dispatched }"></i>{{ row.eca_dispatched ? '已提交' : '未确认' }}</span></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowRight, CircleCheck, Close, DataAnalysis, Files, FolderOpened, Loading,
  Picture, Promotion, Refresh, VideoCamera, VideoPause, VideoPlay, Warning,
} from '@element-plus/icons-vue'
import { getCameraList, simulateCameraScreening, simulateCameraVideoScreening } from '@/api/camera'
import { camerasFromPayload } from '@/utils/cameraSnapshots'

const FRAME_COUNT = 4
const WINDOW_SECONDS = 10
const CAPTURE_INTERVAL_MS = Math.round(WINDOW_SECONDS * 1000 / (FRAME_COUNT - 1))
const SUBMIT_INTERVAL_MS = 15000
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
const inputMode = ref('video')
const videoRef = ref(null)
const videoUrl = ref('')
const videoName = ref('')
const videoFile = ref(null)
const imageFrames = ref([])
const evidenceFrames = ref([])
const simulationActive = ref(false)
const screening = ref(false)
const submittingFrameCount = ref(0)
const result = ref(null)
const history = ref([])
const lastError = ref('')

let captureTimer = null
let frameSequence = 0

const selectedCameraName = computed(() => {
  const camera = cameras.value.find(item => item.id === cameraId.value)
  return camera?.name || camera?.camera_name || (cameraId.value ? `摄像头 ${cameraId.value}` : '--')
})
const mediaStatus = computed(() => {
  if (screening.value) return '模型分析中'
  if (simulationActive.value) return '实时采集中'
  if (inputMode.value === 'video' && videoUrl.value) return '视频已就绪'
  if (inputMode.value === 'images' && imageFrames.value.length) return '图片已就绪'
  return '等待输入'
})
const sceneItems = computed(() => sceneDefinitions.map(([key, confidenceKey, label]) => ({
  key,
  label,
  detected: Number(result.value?.scene?.[key] || 0) === 1,
  percent: Math.round(Number(result.value?.confidence?.[confidenceKey] || 0) * 100),
})))
const riskLabel = computed(() => labelForRisk(result.value?.risk_level))
const riskTag = computed(() => tagForRisk(result.value?.risk_level))
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

function changeInputMode() {
  stopSimulation(false)
  lastError.value = ''
  result.value = null
  replaceEvidence([])
}

function handleVideoFile(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > 200 * 1024 * 1024) return ElMessage.error('视频大小不能超过 200MB')
  stopSimulation(false)
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoFile.value = raw
  videoUrl.value = URL.createObjectURL(raw)
  videoName.value = raw.name
  result.value = null
  lastError.value = ''
  replaceEvidence([])
  nextTick(() => videoRef.value?.load())
}

function handleImageFiles(file) {
  const raw = file.raw
  if (!raw?.type?.startsWith('image/')) return ElMessage.error('请选择图片文件')
  if (raw.size > 10 * 1024 * 1024) return ElMessage.error('单张图片不能超过 10MB')
  if (imageFrames.value.length >= FRAME_COUNT) return ElMessage.warning('每次最多选择 4 张图片')
  imageFrames.value.push(makeFrame(raw, URL.createObjectURL(raw), '图片'))
  replaceEvidence(imageFrames.value)
  result.value = null
}

function handleImageExceed() {
  ElMessage.warning('每次最多选择 4 张图片')
}

function removeImageFrame(id) {
  const frame = imageFrames.value.find(item => item.id === id)
  if (frame) URL.revokeObjectURL(frame.url)
  imageFrames.value = imageFrames.value.filter(item => item.id !== id)
  replaceEvidence(imageFrames.value)
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
  window.clearInterval(captureTimer)
  captureTimer = null
  if (pauseVideo && videoRef.value && !videoRef.value.paused) videoRef.value.pause()
}

function handleNativePause() {
  if (simulationActive.value) stopSimulation(false)
}

async function handleVideoEnded() {
  stopSimulation(false)
}

async function captureVideoFrame() {
  const video = videoRef.value
  if (!simulationActive.value || !video || video.paused || video.ended || !video.videoWidth) return
  const blob = await videoToJpeg(video)
  const frame = makeFrame(blob, URL.createObjectURL(blob), formatVideoTime(video.currentTime))
  const next = [...evidenceFrames.value, frame]
  while (next.length > FRAME_COUNT) {
    const removed = next.shift()
    if (removed?.url?.startsWith('blob:')) URL.revokeObjectURL(removed.url)
  }
  evidenceFrames.value = next
  const submitDue = !lastSubmitStartedAt || Date.now() - lastSubmitStartedAt >= SUBMIT_INTERVAL_MS
  if (next.length === FRAME_COUNT && !screening.value && submitDue) await submitFrames([...next])
}

function videoToJpeg(video) {
  const maxSide = 960
  const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('视频画面采集失败')), 'image/jpeg', 0.72)
  })
}

async function submitImageFrames() {
  replaceEvidence(imageFrames.value)
  await submitFrames([...imageFrames.value])
}

async function submitVideoFile() {
  if (!cameraId.value || !videoFile.value || screening.value) return
  screening.value = true
  submittingFrameCount.value = FRAME_COUNT
  lastError.value = ''
  try {
    const response = await simulateCameraVideoScreening(
      cameraId.value,
      videoFile.value,
      { windowSeconds: WINDOW_SECONDS },
    )
    result.value = response.data
    evidenceFrames.value = (response.data?.image_urls || []).slice(0, FRAME_COUNT).map((url, index) => ({
      id: `server-frame-${Date.now()}-${index}`,
      blob: null,
      url,
      timeLabel: `FRAME ${String(index + 1).padStart(2, '0')}`,
    }))
    history.value = [response.data, ...history.value].slice(0, 20)
    ElMessage.success('Qwen 视频初筛完成，结果已提交 ECA')
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '视频初筛请求失败'
  } finally {
    screening.value = false
    submittingFrameCount.value = 0
    stopSimulation(false)
  }
}

async function submitFrames(frames) {
  if (!cameraId.value || !frames.length || screening.value) return
  screening.value = true
  submittingFrameCount.value = frames.length
  lastError.value = ''
  try {
    const response = await simulateCameraScreening(
      cameraId.value,
      frames.map(item => item.blob),
      { windowSeconds: frames.length > 1 ? WINDOW_SECONDS : 1 },
    )
    result.value = response.data
    history.value = [response.data, ...history.value].slice(0, 20)
    ElMessage.success('Qwen 初筛完成，结果已提交 ECA')
  } catch (error) {
    lastError.value = error?.response?.data?.detail || error?.message || '初筛请求失败'
  } finally {
    screening.value = false
    submittingFrameCount.value = 0
  }
}

function makeFrame(blob, url, timeLabel) {
  frameSequence += 1
  return { id: `frame-${frameSequence}`, blob, url, timeLabel }
}

function replaceEvidence(frames) {
  const retained = new Set(frames.map(item => item.url))
  evidenceFrames.value.forEach(item => {
    if (!retained.has(item.url) && item.url?.startsWith('blob:')) URL.revokeObjectURL(item.url)
  })
  evidenceFrames.value = [...frames]
}

function triggerVideoPickerHint() { ElMessage.info('请点击右上方“选择视频”') }
function triggerImagePickerHint() { ElMessage.info('请点击右上方“选择图片”') }
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
  stopSimulation(false)
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  imageFrames.value.forEach(item => URL.revokeObjectURL(item.url))
  evidenceFrames.value.forEach(item => {
    if (item.url?.startsWith('blob:')) URL.revokeObjectURL(item.url)
  })
})
</script>

<style scoped>
.screening-page {
  --panel: #0b1d30;
  --panel-strong: #071624;
  --line: rgba(105, 165, 207, .24);
  --text: #e7f2fb;
  --muted: #88a3ba;
  --cyan: #54d4ef;
  --mint: #40c7a7;
  min-height: 100%;
  padding: 22px;
  color: var(--text);
  background: #071422;
}
.page-header, .source-control, .control-band, .control-actions, .chain-state,
.panel-header, .panel-header > div, .runtime-state, .result-meta span, .eca-cell {
  display: flex;
  align-items: center;
}
.page-header { justify-content: space-between; gap: 18px; }
.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
h2, h3 { margin: 0; color: #f3f8fd; letter-spacing: 0; }
h2 { font-size: 25px; }
h3 { font-size: 16px; }
.source-control { gap: 10px; color: #a9bfd2; font-size: 13px; }
.camera-select { width: 240px; }
.camera-select :deep(.el-select__wrapper) { background: #0c2236; box-shadow: inset 0 0 0 1px var(--line); }
.camera-select :deep(.el-select__selected-item) { color: var(--text); }
.source-control small { float: right; margin-left: 24px; color: #7390a7; }
.control-band { justify-content: space-between; gap: 18px; margin-top: 18px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px; background: #0b1d30; }
.control-band :deep(.el-radio-button__inner) { border-color: #24506e; color: #a9c0d2; background: #0b1d30; box-shadow: none; }
.control-band :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) { border-color: #46cce3; color: #051824; background: #54d4ef; box-shadow: -1px 0 0 0 #46cce3; }
.control-band :deep(.el-radio-button__inner .el-icon) { margin-right: 6px; vertical-align: -2px; }
.control-actions { gap: 9px; }
.chain-state { gap: 10px; color: #6e8aa1; font-size: 12px; }
.chain-state span { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.chain-state i { display: grid; width: 21px; height: 21px; place-items: center; border: 1px solid #36566d; border-radius: 50%; color: #7d99ae; font-style: normal; }
.chain-state span.active { color: #ffd278; }.chain-state span.active i { border-color: #d89b37; color: #ffd278; }
.chain-state span.done { color: #74dfc4; }.chain-state span.done i { border-color: #40c7a7; color: #74dfc4; background: rgba(64,199,167,.12); }
.workspace { display: grid; grid-template-columns: minmax(0, 1.62fr) minmax(340px, .88fr); gap: 18px; margin-top: 18px; }
.media-panel, .result-panel, .history-panel { overflow: hidden; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
.panel-header { min-height: 66px; justify-content: space-between; padding: 0 18px; border-bottom: 1px solid var(--line); background: #0d2338; }
.panel-header > div { gap: 12px; }.panel-header small { display: block; margin-bottom: 3px; color: #6888a0; font-size: 10px; }
.section-index { color: #4e718b; font-size: 24px; font-weight: 800; font-variant-numeric: tabular-nums; }
.runtime-state { gap: 8px; color: #91a9bc; font-size: 12px; }
.runtime-state i { width: 7px; height: 7px; border-radius: 50%; background: #61798c; }
.runtime-state i.live { background: #40c7a7; box-shadow: 0 0 0 5px rgba(64,199,167,.12); }
.video-stage, .image-stage { position: relative; height: clamp(360px, 42vw, 590px); overflow: hidden; background: #02090f; }
.video-stage video { width: 100%; height: 100%; object-fit: contain; background: #02090f; }
.video-overlay { position: absolute; right: 12px; bottom: 12px; left: 12px; display: flex; justify-content: space-between; padding: 8px 11px; color: #d7e9f6; background: rgba(2,9,15,.78); font-size: 12px; pointer-events: none; }
.empty-stage { display: grid; width: 100%; height: 100%; place-content: center; justify-items: center; gap: 10px; border: 0; color: #7895aa; background: transparent; cursor: pointer; }
.empty-stage .el-icon { font-size: 48px; color: #3f6d89; }.empty-stage strong { color: #c6dae8; font-size: 16px; }.empty-stage span { font-size: 12px; }
.image-grid { display: grid; height: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(2, minmax(0, 1fr)); gap: 1px; background: #1b3446; }
.image-grid figure, .frame-strip figure { position: relative; min-width: 0; margin: 0; overflow: hidden; background: #02090f; }
.image-grid img { width: 100%; height: 100%; object-fit: contain; }.image-grid figcaption { position: absolute; bottom: 8px; left: 8px; padding: 4px 7px; color: #cce3f2; background: rgba(3,12,19,.8); font-size: 10px; }
.image-grid button { position: absolute; top: 8px; right: 8px; display: grid; width: 28px; height: 28px; place-items: center; border: 1px solid rgba(255,255,255,.18); border-radius: 50%; color: #fff; background: rgba(4,14,22,.78); cursor: pointer; }
.evidence-strip { padding: 14px 16px 16px; border-top: 1px solid var(--line); background: #081827; }
.strip-title { display: flex; justify-content: space-between; margin-bottom: 10px; color: #8fa9bd; font-size: 12px; }.strip-title b { color: #cbe2f1; }
.frame-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.frame-strip figure, .frame-slot { aspect-ratio: 16 / 9; border: 1px solid #24435a; border-radius: 4px; }
.frame-strip img { width: 100%; height: 100%; object-fit: cover; }.frame-strip figure span { position: absolute; right: 4px; bottom: 4px; padding: 2px 4px; color: #e6f5ff; background: rgba(0,0,0,.7); font-size: 9px; }
.frame-slot { display: grid; place-items: center; color: #36566d; background: #0b2032; font-size: 18px; font-weight: 800; }
.result-panel { min-height: 600px; }.processing-state, .result-empty { display: grid; min-height: 460px; place-content: center; justify-items: center; gap: 11px; color: var(--muted); text-align: center; }
.processing-state .el-icon { color: #ffd278; font-size: 38px; }.processing-state strong, .result-empty strong { color: #d9e9f5; }.processing-state span, .result-empty span { font-size: 12px; }
.result-empty .el-icon { color: #3f6680; font-size: 46px; }
.result-content { padding: 16px; }.summary-block { padding-bottom: 14px; border-bottom: 1px solid var(--line); }.summary-block span { color: #6f8da4; font-size: 11px; }.summary-block p { margin: 7px 0 0; color: #e5f2fb; line-height: 1.65; }
.scene-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.scene-item { padding: 10px; border: 1px solid rgba(75,132,169,.2); border-radius: 6px; background: #091a29; }.scene-item.detected { border-color: rgba(255,107,107,.55); background: rgba(101,30,39,.26); }
.scene-item > div { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 9px; }.scene-item span { color: #c6dbe9; font-size: 12px; }.scene-item b { color: #62d4b9; font-size: 11px; }.scene-item.detected b { color: #ff8b8b; }.scene-item small { display: block; margin-top: 5px; color: #69879d; font-size: 10px; }
.result-meta { display: grid; gap: 8px; margin-top: 14px; }.result-meta span { gap: 7px; color: #8da8bb; font-size: 12px; }.result-meta span.ok { color: #66d5ba; }
.json-collapse { margin-top: 12px; border-color: var(--line); }.json-collapse :deep(.el-collapse-item__header), .json-collapse :deep(.el-collapse-item__wrap) { color: #bed3e2; background: transparent; border-color: var(--line); }.json-collapse :deep(.el-collapse-item__content) { padding-bottom: 0; }
pre { max-height: 280px; margin: 0; padding: 12px; overflow: auto; color: #9fd8c9; background: #030c13; font: 11px/1.55 Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.error-banner { display: flex; gap: 8px; margin: 0 16px 16px; padding: 10px; border: 1px solid rgba(255,107,107,.35); color: #ff9a9a; background: rgba(110,27,39,.22); font-size: 12px; }
.history-panel { margin-top: 18px; }.panel-header.compact { min-height: 58px; }.panel-header.compact > span { color: #7894a9; font-size: 12px; }
.history-table { background: #091b2b; }.history-table :deep(.el-table__inner-wrapper::before) { background: var(--line); }.history-table :deep(th.el-table__cell) { background: #102940; color: #d4e7f4; }.history-table :deep(tr), .history-table :deep(td.el-table__cell) { background: #091b2b; color: #bed3e2; }.history-table :deep(td.el-table__cell), .history-table :deep(th.el-table__cell) { border-bottom-color: rgba(105,165,207,.15); }.history-table :deep(.el-table__row:hover > td.el-table__cell) { background: #0e273d; }
.eca-cell { gap: 7px; }.eca-cell i { width: 7px; height: 7px; border-radius: 50%; background: #6d7f8e; }.eca-cell i.ok { background: #40c7a7; }
@media (max-width: 1100px) { .workspace { grid-template-columns: 1fr; }.chain-state { display: none; }.result-panel { min-height: auto; } }
@media (max-width: 760px) { .screening-page { padding: 12px; }.page-header, .control-band { align-items: stretch; flex-direction: column; }.source-control { flex-wrap: wrap; }.camera-select { flex: 1; width: auto; min-width: 190px; }.control-actions { flex-wrap: wrap; }.video-stage, .image-stage { height: 340px; }.scene-grid { grid-template-columns: 1fr; }.frame-strip { grid-template-columns: repeat(2, 1fr); } }
</style>
