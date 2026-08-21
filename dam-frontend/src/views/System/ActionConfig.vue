<template>
  <div class="action-config-page">
    <header class="page-header system-page-header">
      <div>
        <p>系统管理 / 规则管理</p>
        <h2>动作配置</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
    </header>

    <section class="filter-bar">
      <el-select v-model="activeEventId" placeholder="全部事件" clearable>
        <el-option v-for="event in config.events" :key="event.id" :label="event.name" :value="event.id" />
      </el-select>
    </section>

    <section class="event-list" v-loading="loading">
      <article v-for="event in visibleEvents" :key="event.id" class="event-card">
        <header class="event-card-header">
          <div>
            <strong>{{ event.name }}</strong>
            <span>{{ event.category_label }} · {{ actionGroups[event.id]?.length || 0 }} 个动作</span>
          </div>
          <el-button :icon="Plus" type="primary" plain @click="addAction(event)">新增动作</el-button>
        </header>

        <div v-if="actionGroups[event.id]?.length" class="action-list">
          <article v-for="action in actionGroups[event.id]" :key="action.id" class="action-row">
            <el-input-number v-model="action.step_order" :min="1" :max="100" controls-position="right" />
            <el-select v-model="action.action_type" placeholder="动作类型">
              <el-option v-for="item in actionTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-input v-model.trim="action.action_name" placeholder="动作名称" />
            <label>
              <span>超时</span>
              <el-input-number v-model="action.timeout_seconds" :min="1" :max="86400" controls-position="right" />
              <em>秒</em>
            </label>
            <label>
              <span>重试</span>
              <el-input-number v-model="action.retry_count" :min="0" :max="20" controls-position="right" />
              <em>次</em>
            </label>
            <el-select v-model="action.failure_strategy" placeholder="失败策略">
              <el-option label="继续后续动作" value="continue" />
              <el-option label="中止流程" value="abort" />
            </el-select>

            <template v-if="action.action_type === 'broadcast'">
              <el-select v-model="action.broadcast_device_id" placeholder="广播设备">
                <el-option v-for="item in config.broadcast_devices" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
              </el-select>
              <el-select v-model="action.template_id" placeholder="广播模板">
                <el-option v-for="item in config.broadcast_templates" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
              </el-select>
              <label>
                <span>间隔</span>
                <el-input-number v-model="action.repeat_interval_seconds" :min="0" :max="86400" controls-position="right" />
                <em>秒</em>
              </label>
              <label>
                <span>最多</span>
                <el-input-number v-model="action.max_executions" :min="1" :max="100" controls-position="right" />
                <em>次</em>
              </label>
            </template>

            <template v-else-if="action.action_type === 'drone_dispatch'">
              <el-input v-model.trim="action.drone_id" placeholder="无人机编号" />
              <el-input v-model.trim="action.route_id" placeholder="航线编号" />
            </template>

            <div class="row-actions">
              <el-switch v-model="action.enabled" active-text="启用" inactive-text="停用" />
              <el-button type="primary" plain :loading="savingId === `action-${action.id}`" @click="saveAction(action)">保存</el-button>
              <el-button :icon="Delete" plain type="danger" @click="removeAction(action)" />
            </div>
          </article>
        </div>
        <el-empty v-else description="暂无动作配置" :image-size="70" />
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus, Refresh } from '@element-plus/icons-vue'
import {
  createActionConfig,
  deleteActionConfig,
  getIntegrationConfig,
  updateActionConfig,
} from '@/api/integration'

const loading = ref(false)
const savingId = ref('')
const activeEventId = ref('')
const config = reactive({
  events: [],
  action_configs: [],
  broadcast_devices: [],
  broadcast_templates: [],
})

const actionTypes = [
  { label: '摄像头抓拍', value: 'camera_snapshot' },
  { label: '自动广播', value: 'broadcast' },
  { label: '无人机派飞', value: 'drone_dispatch' },
  { label: '人工处置任务', value: 'staff_task' },
]

const visibleEvents = computed(() => {
  if (!activeEventId.value) return config.events
  return config.events.filter((event) => event.id === activeEventId.value)
})

const actionGroups = computed(() => {
  const groups = {}
  for (const action of config.action_configs) {
    const list = groups[action.event_id] || []
    list.push(action)
    groups[action.event_id] = list
  }
  for (const list of Object.values(groups)) {
    list.sort((a, b) => (a.step_order || 0) - (b.step_order || 0) || (a.id || 0) - (b.id || 0))
  }
  return groups
})

async function loadConfig() {
  loading.value = true
  try {
    const res = await getIntegrationConfig()
    Object.assign(config, res.data || {})
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '动作配置加载失败')
  } finally {
    loading.value = false
  }
}

function actionPayload(row) {
  return {
    enabled: row.enabled,
    step_order: row.step_order,
    action_type: row.action_type,
    action_name: row.action_name,
    timeout_seconds: row.timeout_seconds,
    failure_strategy: row.failure_strategy,
    retry_count: row.retry_count,
    broadcast_device_id: row.broadcast_device_id,
    template_id: row.template_id,
    drone_id: row.drone_id,
    route_id: row.route_id,
    repeat_interval_seconds: row.repeat_interval_seconds,
    max_executions: row.max_executions,
  }
}

async function saveAction(row) {
  savingId.value = `action-${row.id}`
  try {
    await updateActionConfig(row.id, actionPayload(row))
    ElMessage.success('动作配置已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = ''
  }
}

async function addAction(event) {
  const list = actionGroups.value[event.id] || []
  const nextOrder = list.reduce((max, item) => Math.max(max, Number(item.step_order || 0)), 0) + 1
  try {
    await createActionConfig({
      event_id: event.id,
      step_order: nextOrder,
      action_type: 'camera_snapshot',
      action_name: '摄像头抓拍',
      timeout_seconds: 60,
      failure_strategy: 'continue',
      retry_count: 0,
      repeat_interval_seconds: 60,
      max_executions: 1,
      enabled: true,
    })
    ElMessage.success('动作已新增')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '新增失败')
  }
}

async function removeAction(row) {
  try {
    await ElMessageBox.confirm('确认删除该动作配置？', '删除动作', {
      type: 'warning',
      customClass: 'delete-confirm-box',
    })
    await deleteActionConfig(row.id)
    ElMessage.success('动作已删除')
    await loadConfig()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.action-config-page { min-height: 100%; padding: 22px; color: #d9e8f8; background: #071422; }
.page-header,
.filter-bar,
.event-card-header,
.action-row,
.action-row label,
.row-actions { display: flex; align-items: center; }
.page-header { justify-content: space-between; gap: 16px; }
.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }
.filter-bar { margin: 18px 0; }
.filter-bar :deep(.el-select) { width: 220px; }
.event-list { display: grid; gap: 16px; }
.event-card { padding: 18px; border: 1px solid rgba(96,151,191,.2); border-radius: 8px; background: #0b1d30; }
.event-card-header { justify-content: space-between; gap: 14px; margin-bottom: 14px; }
.event-card-header strong { display: block; color: #f3f8fd; font-size: 17px; }
.event-card-header span { display: block; margin-top: 5px; color: #8fb0c9; font-size: 13px; }
.action-list { display: grid; gap: 10px; }
.action-row { display: grid; grid-template-columns: 92px minmax(150px, 1fr) minmax(170px, 1.1fr) repeat(3, auto) minmax(220px, auto); align-items: center; gap: 10px; padding: 12px; border: 1px solid rgba(96,151,191,.16); border-radius: 8px; background: rgba(7,24,40,.72); }
.action-row label { gap: 8px; color: #9fbcd0; white-space: nowrap; }
.action-row label :deep(.el-input-number) { width: 96px; }
.action-row em { color: #8fb0c9; font-style: normal; }
.row-actions { gap: 10px; justify-content: flex-end; }
@media (max-width: 1300px) {
  .action-row { display: flex; align-items: flex-start; flex-wrap: wrap; }
  .row-actions { margin-left: auto; }
}
</style>
