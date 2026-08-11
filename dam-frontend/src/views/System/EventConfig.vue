<template>
  <div class="event-config-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 联动系统</p>
        <h2>事件配置</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
    </header>

    <section class="filter-bar">
      <el-segmented v-model="activeSource" :options="sourceOptions" />
      <el-select v-model="activeCategory" placeholder="事件类型" clearable>
        <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </section>

    <section class="event-list" v-loading="loading">
      <article v-for="event in filteredEvents" :key="event.id" class="event-row">
        <div class="event-main">
          <strong>{{ event.name }}</strong>
          <span>{{ event.category_label || '未分类' }} · {{ event.code || `事件 ${event.id}` }}</span>
        </div>
        <div class="event-info">
          <span>{{ sourceLabel(event) }}</span>
          <span>{{ conditionSummary(event) }}</span>
          <el-tag :type="riskTag(event.risk_level)" effect="dark">{{ event.risk_label || '未知风险' }}</el-tag>
        </div>
        <div class="event-actions">
          <label>
            <span>触发持续</span>
            <el-input-number v-model="event.trigger_duration" :min="0" :max="3600" controls-position="right" />
            <em>秒</em>
          </label>
          <label>
            <span>恢复确认</span>
            <el-input-number v-model="event.recovery_duration" :min="0" :max="3600" controls-position="right" />
            <em>秒</em>
          </label>
          <el-switch v-model="event.enabled" active-text="启用" inactive-text="停用" />
          <el-button type="primary" plain :loading="savingId === event.id" @click="saveEvent(event)">保存</el-button>
        </div>
      </article>
      <el-empty v-if="!filteredEvents.length && !loading" description="暂无事件配置" />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getIntegrationConfig, updateConditionConfig, updateEventConfig } from '@/api/integration'

const loading = ref(false)
const savingId = ref('')
const activeSource = ref('all')
const activeCategory = ref('')
const events = ref([])

const sourceOptions = [
  { label: '全部', value: 'all' },
  { label: '视觉事件', value: 'camera' },
  { label: '传感器事件', value: 'sensor' },
]

const categoryOptions = computed(() => {
  const map = new Map()
  events.value.forEach((event) => {
    if (event.category) map.set(event.category, event.category_label || event.category)
  })
  return Array.from(map, ([value, label]) => ({ value, label }))
})

const filteredEvents = computed(() => events.value.filter((event) => {
  if (activeSource.value !== 'all' && event.source_type !== activeSource.value) return false
  if (activeCategory.value && event.category !== activeCategory.value) return false
  return true
}))

function normalizeEvent(row) {
  const conditions = Array.isArray(row.conditions) ? row.conditions : []
  const primary = conditions[0] || {}
  return {
    ...row,
    conditions,
    primary_condition_id: primary.id || null,
    trigger_duration: Number(primary.duration ?? 0),
    source_type: primary.source_type || inferSourceType(row),
  }
}

function inferSourceType(row) {
  const text = `${row.category || ''} ${row.code || ''}`.toLowerCase()
  if (text.includes('person') || text.includes('boat') || text.includes('camera')) return 'camera'
  return 'sensor'
}

async function loadConfig() {
  loading.value = true
  try {
    const res = await getIntegrationConfig()
    events.value = (res.data?.events || []).map(normalizeEvent)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '事件配置加载失败')
  } finally {
    loading.value = false
  }
}

async function saveEvent(event) {
  savingId.value = event.id
  try {
    await updateEventConfig(event.id, {
      recovery_duration: event.recovery_duration,
      enabled: event.enabled,
    })
    if (event.primary_condition_id) {
      await updateConditionConfig(event.primary_condition_id, {
        duration: event.trigger_duration,
        enabled: event.enabled,
      })
    }
    ElMessage.success('事件配置已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = ''
  }
}

function sourceLabel(event) {
  if (event.source_type === 'camera') return '视觉'
  if (event.source_type === 'sensor') return '传感器'
  return event.source_type || '未绑定数据源'
}

function conditionSummary(event) {
  const condition = event.conditions?.[0]
  if (!condition) return '未绑定触发条件'
  return condition.expression || condition.name || '已绑定触发条件'
}

function riskTag(level) {
  return ({ 1: 'success', 2: 'warning', 3: 'danger', LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[level] || 'info'
}

onMounted(loadConfig)
</script>

<style scoped>
.event-config-page { min-height: 100%; padding: 22px; color: #d9e8f8; background: #071422; }
.page-header,
.filter-bar,
.event-row,
.event-info,
.event-actions,
.event-actions label { display: flex; align-items: center; }
.page-header { justify-content: space-between; gap: 16px; }
.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }
.filter-bar { gap: 12px; margin: 18px 0; }
.filter-bar :deep(.el-select) { width: 180px; }
.event-list { display: grid; gap: 10px; }
.event-row { min-height: 76px; padding: 14px 18px; gap: 18px; border: 1px solid rgba(96,151,191,.18); border-radius: 8px; background: #0b1d30; }
.event-main { min-width: 240px; flex: 1.1; }
.event-main strong { display: block; overflow: hidden; color: #f3f8fd; font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.event-main span { display: block; margin-top: 5px; overflow: hidden; color: #8fb0c9; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.event-info { flex: 1.2; min-width: 260px; gap: 10px; color: #9bb7cb; }
.event-info > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.event-info > span:first-child { width: 72px; color: #63dcf7; }
.event-actions { gap: 12px; justify-content: flex-end; }
.event-actions label { gap: 8px; color: #9fbcd0; white-space: nowrap; }
.event-actions label :deep(.el-input-number) { width: 112px; }
.event-actions em { color: #8fb0c9; font-style: normal; }
@media (max-width: 1200px) {
  .event-row { align-items: flex-start; flex-direction: column; }
  .event-main,
  .event-info { width: 100%; }
  .event-actions { width: 100%; justify-content: flex-start; flex-wrap: wrap; }
}
</style>
