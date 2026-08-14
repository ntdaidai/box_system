<template>
  <el-dialog
    v-model="visible"
    title="一键喊话"
    width="480px"
    class="broadcast-dialog"
    destroy-on-close
  >
    <div class="broadcast-panel">
      <section class="broadcast-target">
        <span>当前点位</span>
        <strong>{{ event?.camera_name || event?.camera_id || '未选择摄像头' }}</strong>
        <small>{{ onlineDeviceCount ? `${onlineDeviceCount} 个广播设备可用` : '暂无可用广播设备' }}</small>
      </section>
      <p v-if="startUnavailableReason" class="broadcast-warning">{{ startUnavailableReason }}</p>

      <section class="talk-card" :class="{ active: isTalking }">
        <div class="talk-state">
          <i></i>
          <strong>{{ talkStateText }}</strong>
          <span>{{ durationText }}</span>
        </div>

        <button
          v-if="!isTalking"
          type="button"
          class="talk-button start"
          :disabled="!canStart"
          @click="startTalking"
        >
          {{ talkButtonText }}
        </button>
        <button
          v-else
          type="button"
          class="talk-button stop"
          @click="stopTalking(true)"
        >
          停止说话
        </button>
      </section>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getBroadcastDevices, playRecordedBroadcast } from '@/api/broadcast'

const props = defineProps({
  modelValue: Boolean,
  event: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue', 'played'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const devices = ref([])
const selectedDeviceIds = ref([])
const preparingRecorder = ref(false)
const isTalking = ref(false)
const submitting = ref(false)
const recorder = ref(null)
const recorderStream = ref(null)
const audioChunks = ref([])
const recordingStartedAt = ref(0)
const elapsedMs = ref(0)
const playAfterStop = ref(false)
let durationTimer = null

const onlineDevices = computed(() => devices.value.filter((device) => (
  device.enabled !== false
  && String(device.status || '').toUpperCase() !== 'OFFLINE'
  && String(device.vendor_type || '').toUpperCase() !== 'LOCAL_AUDIO'
)))
const onlineDeviceCount = computed(() => onlineDevices.value.length)
const microphoneSupported = computed(() => Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder))
const microphoneUnavailableReason = computed(() => {
  if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return '当前页面不是 HTTPS 或 localhost，浏览器禁止访问麦克风'
  }
  if (!navigator.mediaDevices?.getUserMedia) return '当前浏览器不支持麦克风采集'
  if (!window.MediaRecorder) return '当前浏览器不支持录音编码'
  return ''
})
const startUnavailableReason = computed(() => {
  if (onlineDeviceCount.value <= 0) return '暂无可用广播设备'
  return microphoneUnavailableReason.value
})
const canStart = computed(() => (
  !preparingRecorder.value
  && !submitting.value
  && !startUnavailableReason.value
))
const talkStateText = computed(() => {
  if (submitting.value) return '正在播放'
  if (isTalking.value) return '正在说话'
  if (startUnavailableReason.value) return '无法开始'
  return '等待开始'
})
const talkButtonText = computed(() => {
  if (preparingRecorder.value) return '正在打开麦克风'
  if (submitting.value) return '正在播放'
  if (startUnavailableReason.value) return '不可用'
  return '开始说话'
})
const durationText = computed(() => {
  const seconds = Math.floor(elapsedMs.value / 1000)
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) {
      stopTalking(false)
      return
    }
    await loadDevices()
  },
)

onBeforeUnmount(() => stopTalking(false))

async function loadDevices() {
  try {
    const response = await getBroadcastDevices()
    devices.value = response.data || []
    selectedDeviceIds.value = onlineDevices.value.map((device) => device.id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '广播设备加载失败')
  }
}

function preferredMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/mp4',
    'audio/mpeg',
  ]
  return candidates.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || ''
}

async function startTalking() {
  if (!canStart.value) {
    ElMessage.warning(startUnavailableReason.value || '暂时无法开始喊话')
    return
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    ElMessage.warning(microphoneUnavailableReason.value || '当前浏览器无法打开麦克风')
    return
  }
  preparingRecorder.value = true
  try {
    releaseRecording()
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorderStream.value = stream
    const mimeType = preferredMimeType()
    const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    audioChunks.value = []
    mediaRecorder.ondataavailable = (event) => {
      if (event.data?.size) audioChunks.value.push(event.data)
    }
    mediaRecorder.onstop = handleRecorderStop
    recorder.value = mediaRecorder
    playAfterStop.value = false
    recordingStartedAt.value = Date.now()
    elapsedMs.value = 0
    durationTimer = window.setInterval(() => {
      elapsedMs.value = Date.now() - recordingStartedAt.value
    }, 250)
    mediaRecorder.start(250)
    isTalking.value = true
  } catch (error) {
    releaseStream()
    ElMessage.warning(microphoneErrorMessage(error))
  } finally {
    preparingRecorder.value = false
  }
}

function stopTalking(shouldPlay) {
  playAfterStop.value = Boolean(shouldPlay)
  if (durationTimer) {
    window.clearInterval(durationTimer)
    durationTimer = null
  }
  if (isTalking.value && recorder.value?.state !== 'inactive') {
    elapsedMs.value = Date.now() - recordingStartedAt.value
    try {
      recorder.value.requestData?.()
    } catch {
      // Some browsers do not allow requestData during the stop transition.
    }
    recorder.value.stop()
  } else {
    releaseStream()
  }
  isTalking.value = false
}

async function handleRecorderStop() {
  const recorderType = recorder.value?.mimeType || preferredMimeType() || 'audio/webm'
  const audioBlob = new Blob(audioChunks.value, { type: recorderType })
  releaseStream()
  if (!playAfterStop.value) {
    releaseRecording()
    return
  }
  if (!audioBlob.size) {
    ElMessage.warning('未捕获到有效声音')
    releaseRecording()
    return
  }
  submitting.value = true
  try {
    const data = await playRecording(audioBlob)
    emit('played', { event: props.event, result: data.result || 'SUCCESS' })
    visible.value = false
    ElMessage.success(data.result === 'PARTIAL_SUCCESS' ? '部分广播设备已播放' : '喊话已播放')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '喊话失败')
  } finally {
    submitting.value = false
    releaseRecording()
  }
}

function releaseStream() {
  recorderStream.value?.getTracks?.().forEach((track) => track.stop())
  recorderStream.value = null
  recorder.value = null
}

function releaseRecording() {
  audioChunks.value = []
  elapsedMs.value = 0
}

function recordingFilename(blob) {
  const type = blob?.type || ''
  const suffix = type.includes('ogg')
    ? 'ogg'
    : type.includes('wav')
      ? 'wav'
      : type.includes('mpeg')
        ? 'mp3'
        : type.includes('mp4')
          ? 'm4a'
          : 'webm'
  return `one-touch-talk.${suffix}`
}

async function playRecording(audioBlob) {
  const formData = new FormData()
  formData.append('event_id', props.event?.event_id || '')
  formData.append('camera_id', props.event?.camera_id || '')
  formData.append('risk_level', props.event?.risk_level || '')
  formData.append('device_ids', JSON.stringify(selectedDeviceIds.value))
  formData.append('audio', audioBlob, recordingFilename(audioBlob))
  const response = await playRecordedBroadcast(formData)
  return response.data || {}
}

function microphoneErrorMessage(error) {
  const name = error?.name || ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return '浏览器未授权麦克风，请检查地址栏权限'
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return '未检测到可用麦克风'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return '麦克风被其他程序占用或系统拒绝访问'
  }
  if (name === 'SecurityError') {
    return '浏览器安全策略禁止访问麦克风'
  }
  if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
    return '当前麦克风不满足浏览器录音要求'
  }
  return error?.message || '无法打开麦克风'
}
</script>

<style scoped>
.broadcast-panel {
  display: grid;
  gap: 14px;
}
.broadcast-target,
.talk-card {
  border: 1px solid rgba(92, 166, 205, .18);
  border-radius: 8px;
  background: #092033;
}
.broadcast-target {
  padding: 14px 16px;
  display: grid;
  gap: 6px;
}
.broadcast-target span,
.broadcast-target small {
  color: #86a6bb;
  font-size: 13px;
}
.broadcast-target strong {
  color: #f2fbff;
  font-size: 18px;
}
.broadcast-warning {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid rgba(255, 194, 102, .28);
  border-radius: 6px;
  color: #ffd596;
  background: rgba(255, 194, 102, .08);
  font-size: 13px;
}
.talk-card {
  padding: 18px;
  display: grid;
  gap: 16px;
}
.talk-card.active {
  border-color: rgba(98, 215, 177, .48);
}
.talk-state {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}
.talk-state i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #708b9d;
}
.talk-card.active .talk-state i {
  background: #62d7b1;
  box-shadow: 0 0 12px rgba(98, 215, 177, .72);
}
.talk-state strong {
  color: #e5f5fb;
  font-size: 18px;
}
.talk-state span {
  color: #8fb0c4;
  font: 800 18px monospace;
}
.talk-button {
  width: 100%;
  min-height: 68px;
  border: 0;
  border-radius: 8px;
  color: #061412;
  background: #62d7b1;
  font-size: 20px;
  font-weight: 900;
  cursor: pointer;
}
.talk-button.stop {
  color: #fff;
  background: #d65b66;
}
.talk-button:disabled {
  cursor: not-allowed;
  opacity: .5;
}
:global(.broadcast-dialog .el-dialog) {
  background: #173454;
  border: 1px solid rgba(82, 157, 204, .24);
}
:global(.broadcast-dialog .el-dialog__title) {
  color: #eff9ff;
  font-weight: 800;
}
:global(.broadcast-dialog .el-dialog__body) {
  padding-top: 10px;
}
</style>
