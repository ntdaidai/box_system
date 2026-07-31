<template>
  <el-dialog
    v-model="visible"
    title="一键喊话"
    width="620px"
    class="broadcast-dialog"
    destroy-on-close
  >
    <div class="broadcast-form">
      <div class="broadcast-context">
        <strong>{{ event?.event_type || '应急喊话' }}</strong>
        <span>{{ event?.camera_name || event?.camera_id || '--' }}</span>
      </div>

      <el-form label-position="top">
        <el-form-item label="USB外放设备">
          <el-checkbox-group v-model="selectedDeviceIds" class="device-list">
            <el-checkbox
              v-for="device in playableDevices"
              :key="device.id"
              :label="device.id"
              :disabled="device.status === 'OFFLINE'"
            >
              <span>{{ device.name }}</span>
              <em :class="{ offline: device.status === 'OFFLINE' }">{{ device.status }}</em>
            </el-checkbox>
          </el-checkbox-group>
          <el-empty v-if="!playableDevices.length" description="当前摄像头未绑定USB外放设备" :image-size="72" />
        </el-form-item>

        <el-form-item label="喊话方式">
          <el-segmented v-model="broadcastMode" :options="modeOptions" class="mode-segment" />
        </el-form-item>

        <template v-if="broadcastMode === 'template'">
          <el-form-item label="预设模板">
            <el-select v-model="selectedTemplateId" placeholder="选择预设模板" filterable>
              <el-option
                v-for="template in templates"
                :key="template.id"
                :label="template.name"
                :value="template.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="模板文字">
            <el-input
              v-model="customText"
              type="textarea"
              :rows="4"
              maxlength="500"
              show-word-limit
              placeholder="可以直接修改本次喊话内容"
            />
          </el-form-item>
        </template>

        <el-form-item v-else label="人工录音">
          <div class="record-panel" :class="{ recording: isRecording }">
            <div class="record-status">
              <span class="record-dot"></span>
              <strong>{{ recordStateText }}</strong>
              <small>{{ durationText }}</small>
            </div>
            <div class="record-actions">
              <el-button
                type="danger"
                :disabled="isRecording || playing"
                :loading="preparingRecorder"
                @click="startRecording"
              >
                开始录音
              </el-button>
              <el-button :disabled="!isRecording" @click="stopRecording">停止录音</el-button>
              <el-button :disabled="!audioBlob || isRecording || playing" @click="clearRecording">重录</el-button>
            </div>
            <audio v-if="recordingUrl" :src="recordingUrl" controls class="record-preview"></audio>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        v-if="broadcastMode === 'template'"
        :loading="previewing"
        :disabled="!canPreview"
        @click="handlePreview"
      >
        试听
      </el-button>
      <el-button type="primary" :loading="playing" :disabled="!canPlay" @click="handlePlay">
        {{ broadcastMode === 'template' ? '播放模板' : '播放录音' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getBroadcastTemplates,
  getCameraBroadcastDevices,
  playBroadcast,
  playRecordedBroadcast,
  previewBroadcast,
} from '@/api/broadcast'

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

const modeOptions = [
  { label: '模板喊话', value: 'template' },
  { label: '人工录音', value: 'record' },
]

const devices = ref([])
const templates = ref([])
const selectedDeviceIds = ref([])
const selectedTemplateId = ref('')
const customText = ref('')
const broadcastMode = ref('template')
const previewing = ref(false)
const preparingRecorder = ref(false)
const isRecording = ref(false)
const playing = ref(false)
const recorder = ref(null)
const recorderStream = ref(null)
const audioChunks = ref([])
const audioBlob = ref(null)
const recordingUrl = ref('')
const recordingStartedAt = ref(0)
const elapsedMs = ref(0)
let durationTimer = null

const playableDevices = computed(() => {
  return devices.value.filter((device) => String(device.vendor_type || '').toUpperCase() !== 'LOCAL_AUDIO')
})

const canPreview = computed(() => Boolean(selectedTemplateId.value || customText.value.trim()))

const canPlay = computed(() => {
  if (!selectedDeviceIds.value.length) return false
  if (broadcastMode.value === 'template') return canPreview.value
  return Boolean(audioBlob.value && !isRecording.value)
})

const recordStateText = computed(() => {
  if (isRecording.value) return '正在录音'
  if (audioBlob.value) return '录音已就绪'
  return '等待录音'
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
    if (!open || !props.event) {
      stopRecording()
      clearRecording()
      return
    }
    await loadOptions()
  },
)

watch(selectedTemplateId, (id) => {
  if (!id) return
  const template = templates.value.find((item) => item.id === id)
  if (template) customText.value = template.content
})

watch(broadcastMode, (mode) => {
  if (mode === 'template') {
    stopRecording()
    clearRecording()
  }
})

onBeforeUnmount(() => {
  stopRecording()
  clearRecording()
})

async function loadOptions() {
  stopRecording()
  clearRecording()
  broadcastMode.value = 'template'
  selectedDeviceIds.value = []
  selectedTemplateId.value = ''
  customText.value = ''
  const [templateResponse, deviceResponse] = await Promise.all([
    getBroadcastTemplates(),
    getCameraBroadcastDevices(props.event.camera_id),
  ])
  templates.value = templateResponse.data || []
  devices.value = deviceResponse.data || []
  selectedDeviceIds.value = playableDevices.value
    .filter((device) => device.status !== 'OFFLINE' && String(device.vendor_type || '').toUpperCase() === 'USB_AUDIO')
    .map((device) => device.id)
  if (!selectedDeviceIds.value.length) {
    selectedDeviceIds.value = playableDevices.value
      .filter((device) => device.status !== 'OFFLINE')
      .map((device) => device.id)
  }
  selectedTemplateId.value = defaultTemplateId()
  const template = templates.value.find((item) => item.id === selectedTemplateId.value)
  customText.value = template?.content || ''
}

function defaultTemplateId() {
  const risk = props.event?.risk_level || 'HIGH'
  const wanted = `PERSON_${risk}`
  if (templates.value.some((item) => item.id === wanted)) return wanted
  return templates.value[0]?.id || ''
}

function speak(text) {
  if (!window.speechSynthesis || !text) return false
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1
  window.speechSynthesis.speak(utterance)
  return true
}

async function handlePreview() {
  if (!canPreview.value) return
  previewing.value = true
  try {
    const response = await previewBroadcast({
      template_id: selectedTemplateId.value,
      custom_text: customText.value,
    })
    const text = response.data?.text || customText.value
    if (!speak(text)) ElMessage.info('当前浏览器不支持本机语音试听')
  } finally {
    previewing.value = false
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

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    ElMessage.error('当前浏览器不支持麦克风录音')
    return
  }
  preparingRecorder.value = true
  try {
    clearRecording()
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorderStream.value = stream
    const mimeType = preferredMimeType()
    const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    audioChunks.value = []
    mediaRecorder.ondataavailable = (event) => {
      if (event.data?.size) audioChunks.value.push(event.data)
    }
    mediaRecorder.onstop = () => {
      const type = mediaRecorder.mimeType || mimeType || 'audio/webm'
      audioBlob.value = new Blob(audioChunks.value, { type })
      recordingUrl.value = URL.createObjectURL(audioBlob.value)
      releaseStream()
    }
    recorder.value = mediaRecorder
    recordingStartedAt.value = Date.now()
    elapsedMs.value = 0
    durationTimer = window.setInterval(() => {
      elapsedMs.value = Date.now() - recordingStartedAt.value
    }, 250)
    mediaRecorder.start()
    isRecording.value = true
  } catch (error) {
    releaseStream()
    ElMessage.error(error?.message || '无法打开麦克风')
  } finally {
    preparingRecorder.value = false
  }
}

function stopRecording() {
  if (durationTimer) {
    window.clearInterval(durationTimer)
    durationTimer = null
  }
  if (isRecording.value && recorder.value?.state !== 'inactive') {
    elapsedMs.value = Date.now() - recordingStartedAt.value
    recorder.value.stop()
  } else {
    releaseStream()
  }
  isRecording.value = false
}

function releaseStream() {
  recorderStream.value?.getTracks?.().forEach((track) => track.stop())
  recorderStream.value = null
  recorder.value = null
}

function clearRecording() {
  if (recordingUrl.value) URL.revokeObjectURL(recordingUrl.value)
  recordingUrl.value = ''
  audioBlob.value = null
  audioChunks.value = []
  elapsedMs.value = 0
}

function recordingFilename() {
  const type = audioBlob.value?.type || ''
  const suffix = type.includes('ogg') ? 'ogg' : type.includes('wav') ? 'wav' : 'webm'
  return `manual-broadcast.${suffix}`
}

async function handlePlay() {
  if (!canPlay.value) return
  playing.value = true
  try {
    const data = broadcastMode.value === 'template'
      ? await playTemplate()
      : await playRecording()
    emit('played', { event: props.event, result: data.result || 'SUCCESS' })
    visible.value = false
    ElMessage.success(data.result === 'PARTIAL_SUCCESS' ? '部分USB外放已播放' : '喊话已播放')
  } finally {
    playing.value = false
  }
}

async function playTemplate() {
  const response = await playBroadcast({
    event_id: props.event.event_id,
    camera_id: props.event.camera_id,
    device_ids: selectedDeviceIds.value,
    template_id: selectedTemplateId.value,
    custom_text: customText.value,
    trigger_type: 'MANUAL',
  })
  return response.data || {}
}

async function playRecording() {
  const formData = new FormData()
  formData.append('event_id', props.event.event_id || '')
  formData.append('camera_id', props.event.camera_id || '')
  formData.append('risk_level', props.event.risk_level || '')
  formData.append('device_ids', JSON.stringify(selectedDeviceIds.value))
  formData.append('audio', audioBlob.value, recordingFilename())
  const response = await playRecordedBroadcast(formData)
  return response.data || {}
}
</script>

<style scoped>
.broadcast-form {
  display: grid;
  gap: 14px;
  color: #dbeaf1;
}

.broadcast-context {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(5, 22, 31, 0.82);
}

.broadcast-context strong {
  color: #f1fbff;
}

.broadcast-context span {
  color: #9fb8c2;
}

.device-list {
  display: grid;
  gap: 8px;
}

.device-list em {
  margin-left: 8px;
  color: #13a56f;
  font-style: normal;
  font-size: 12px;
}

.device-list em.offline {
  color: #d94841;
}

.mode-segment {
  width: 100%;
}

.record-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(5, 22, 31, 0.62);
}

.record-status {
  display: flex;
  align-items: center;
  gap: 10px;
}

.record-status strong {
  color: #f1fbff;
}

.record-status small {
  margin-left: auto;
  color: #9fb8c2;
  font-variant-numeric: tabular-nums;
}

.record-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #6f8490;
}

.record-panel.recording .record-dot {
  background: #ff5c5c;
  box-shadow: 0 0 0 6px rgba(255, 92, 92, 0.12);
}

.record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.record-preview {
  width: 100%;
  height: 40px;
}

:global(.broadcast-dialog .el-dialog) {
  color: #dbeaf1;
  border: 1px solid rgba(72, 216, 255, 0.32);
  border-radius: 8px;
  background:
    radial-gradient(circle at 100% 0%, rgba(72, 216, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(11, 35, 49, 0.98), rgba(3, 14, 23, 0.98));
  box-shadow: 0 24px 60px rgba(0, 5, 10, 0.38);
}

:global(.broadcast-dialog .el-dialog__header) {
  padding: 22px 24px 14px;
  border-bottom: 1px solid rgba(137, 174, 184, 0.16);
}

:global(.broadcast-dialog .el-dialog__title) {
  color: #f1fbff;
}

:global(.broadcast-dialog .el-dialog__body) {
  padding: 18px 24px;
}

:global(.broadcast-dialog .el-dialog__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid rgba(137, 174, 184, 0.16);
}

:global(.broadcast-dialog .el-form-item__label) {
  color: #9fb8c2;
}
</style>
