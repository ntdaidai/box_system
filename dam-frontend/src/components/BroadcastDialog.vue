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
          {{ preparingRecorder ? '正在打开麦克风' : submitting ? '正在播放' : '开始说话' }}
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
const canStart = computed(() => !preparingRecorder.value && !submitting.value && onlineDeviceCount.value > 0)
const talkStateText = computed(() => {
  if (submitting.value) return '正在播放'
  if (isTalking.value) return '正在说话'
  return '等待开始'
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
  ]
  return candidates.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || ''
}

async function startTalking() {
  if (!canStart.value) {
    ElMessage.warning('暂无可用广播设备')
    return
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    ElMessage.error('当前浏览器不支持麦克风')
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
    mediaRecorder.start()
    isTalking.value = true
  } catch (error) {
    releaseStream()
    ElMessage.error(error?.message || '无法打开麦克风')
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
  const suffix = type.includes('ogg') ? 'ogg' : type.includes('wav') ? 'wav' : 'webm'
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
