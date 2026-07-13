<template>
  <div class="device-meta-card">
    <div class="meta-item">
      <span>设备 SN</span>
      <strong>{{ meta.sn }}</strong>
    </div>
    <div class="meta-item">
      <span>部署位置</span>
      <strong>{{ meta.location }}</strong>
    </div>
    <div class="meta-item">
      <span>供电状态</span>
      <strong>{{ meta.power }}</strong>
    </div>
    <div class="meta-item">
      <span>最后通讯</span>
      <strong>{{ lastSeenText }}</strong>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  meta: {
    type: Object,
    required: true,
  },
  timestamp: {
    type: Number,
    default: 0,
  },
})

const lastSeenText = computed(() => {
  if (!props.timestamp) return '--'
  return new Date(props.timestamp * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
})
</script>

<style scoped>
.device-meta-card {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px 16px;
  background: rgba(10, 28, 54, 0.48);
  border: 1px solid rgba(0, 200, 255, 0.24);
  border-radius: 8px;
}

.meta-item {
  min-width: 0;
}

.meta-item span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 4px;
}

.meta-item strong {
  display: block;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .device-meta-card {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
