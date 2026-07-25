<template>
  <el-dialog
    v-model="visible"
    title="一键喊话"
    width="560px"
    class="broadcast-dialog"
    destroy-on-close
  >
    <div class="broadcast-form">
      <div class="broadcast-context">
        <strong>{{ event?.event_type || '风险事件' }}</strong>
        <span>{{ event?.camera_name || event?.camera_id || '--' }}</span>
      </div>

      <el-form label-position="top">
        <el-form-item label="广播设备">
          <el-checkbox-group v-model="selectedDeviceIds" class="device-list">
            <el-checkbox
              v-for="device in devices"
              :key="device.id"
              :label="device.id"
              :disabled="device.status === 'OFFLINE'"
            >
              <span>{{ device.name }}</span>
              <em :class="{ offline: device.status === 'OFFLINE' }">{{ device.status }}</em>
            </el-checkbox>
          </el-checkbox-group>
          <el-empty v-if="!devices.length" description="当前摄像头未绑定广播设备" :image-size="72" />
        </el-form-item>

        <el-form-item label="预设语音">
          <el-select v-model="selectedTemplateId" placeholder="选择预设语音" filterable>
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="template.name"
              :value="template.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="广播内容">
          <el-input
            v-model="customText"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="为空时使用预设语音；填写后优先播放自定义文字"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :loading="previewing" @click="handlePreview">试听</el-button>
      <el-button type="primary" :loading="playing" :disabled="!canPlay" @click="handlePlay">
        立即播放
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getBroadcastTemplates,
  getCameraBroadcastDevices,
  playBroadcast,
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

const devices = ref([])
const templates = ref([])
const selectedDeviceIds = ref([])
const selectedTemplateId = ref('')
const customText = ref('')
const previewing = ref(false)
const playing = ref(false)

const canPlay = computed(() => selectedDeviceIds.value.length > 0 && (selectedTemplateId.value || customText.value.trim()))

watch(
  () => props.modelValue,
  async (open) => {
    if (!open || !props.event) return
    await loadOptions()
  },
)

watch(selectedTemplateId, (id) => {
  if (!id) return
  const template = templates.value.find((item) => item.id === id)
  if (template) customText.value = template.content
})

async function loadOptions() {
  customText.value = ''
  selectedDeviceIds.value = []
  const [templateResponse, deviceResponse] = await Promise.all([
    getBroadcastTemplates(),
    getCameraBroadcastDevices(props.event.camera_id),
  ])
  templates.value = templateResponse.data || []
  devices.value = deviceResponse.data || []
  selectedDeviceIds.value = devices.value
    .filter((device) => device.status !== 'OFFLINE')
    .map((device) => device.id)
  selectedTemplateId.value = defaultTemplateId()
  const template = templates.value.find((item) => item.id === selectedTemplateId.value)
  customText.value = template?.content || ''
}

function defaultTemplateId() {
  const risk = props.event?.risk_level || 'LOW'
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

async function handlePlay() {
  playing.value = true
  try {
    const response = await playBroadcast({
      event_id: props.event.event_id,
      camera_id: props.event.camera_id,
      device_ids: selectedDeviceIds.value,
      template_id: selectedTemplateId.value,
      custom_text: customText.value,
      trigger_type: 'MANUAL',
    })
    const data = response.data || {}
    if (data.browser_tts) speak(data.text)
    emit('played', { event: props.event, result: data.result || 'SUCCESS' })
    visible.value = false
    ElMessage.success(data.result === 'PARTIAL_SUCCESS' ? '部分广播设备已播放' : '广播已播放')
  } finally {
    playing.value = false
  }
}
</script>

<style scoped>
.broadcast-form {
  display: grid;
  gap: 14px;
}

.broadcast-context {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
}

.broadcast-context span {
  color: #667085;
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
</style>
