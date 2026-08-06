<template>
  <div class="config-page">
    <header class="page-header">
      <div>
        <p>实时监控 / 信息配置</p>
        <h2>监测与处置参数</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
    </header>

    <el-tabs v-model="activeTab" class="config-tabs">
      <el-tab-pane label="触发条件" name="conditions">
        <section class="panel" v-loading="loading">
          <div class="config-list">
            <article v-for="condition in config.conditions" :key="condition.id" class="config-row condition-row">
              <div class="row-title">
                <strong>{{ condition.name }}</strong>
                <span>触发条件 ID {{ condition.id }}</span>
              </div>
              <label class="number-field">
                <span>持续时间</span>
                <el-input-number v-model="condition.duration" :min="0" :max="3600" controls-position="right" />
                <em>秒</em>
              </label>
              <el-switch v-model="condition.enabled" active-text="启用" inactive-text="停用" />
              <el-button type="primary" plain :loading="savingId === `condition-${condition.id}`" @click="saveCondition(condition)">保存</el-button>
            </article>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="事件策略" name="events">
        <section class="panel" v-loading="loading">
          <div class="event-grid">
            <article v-for="event in config.events" :key="event.id" class="event-card">
              <header>
                <div>
                  <strong>{{ event.name }}</strong>
                  <span>{{ event.category_label }} · {{ event.code }}</span>
                </div>
                <el-tag :type="riskTag(event.risk_level)" effect="dark">{{ event.risk_label }}</el-tag>
              </header>
              <div class="event-fields">
                <label class="number-field">
                  <span>恢复确认</span>
                  <el-input-number v-model="event.recovery_duration" :min="0" :max="3600" controls-position="right" />
                  <em>秒</em>
                </label>
                <el-input v-model.trim="event.route_role_id" placeholder="智能路由角色ID" clearable />
              </div>
              <footer>
                <el-switch v-model="event.enabled" active-text="启用" inactive-text="停用" />
                <el-button type="primary" plain :loading="savingId === `event-${event.id}`" @click="saveEvent(event)">保存</el-button>
              </footer>
            </article>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="动作流程" name="actions">
        <section class="panel action-panel" v-loading="loading">
          <div class="action-event-list">
            <article v-for="event in config.events" :key="event.id" class="action-event">
              <header class="action-event-header">
                <div>
                  <strong>{{ event.name }}</strong>
                  <span>{{ event.risk_label }} · {{ actionGroups[event.id]?.length || 0 }} 个动作</span>
                </div>
                <el-button :icon="Plus" type="primary" plain @click="addAction(event)">新增动作</el-button>
              </header>

              <div v-if="actionGroups[event.id]?.length" class="step-list">
                <article v-for="action in actionGroups[event.id]" :key="action.id" class="step-row">
                  <div class="step-order">
                    <el-input-number v-model="action.step_order" :min="1" :max="100" controls-position="right" />
                  </div>
                  <div class="step-main">
                    <div class="step-line">
                      <el-select v-model="action.action_type" placeholder="动作类型">
                        <el-option v-for="item in actionTypes" :key="item.value" :label="item.label" :value="item.value" />
                      </el-select>
                      <el-input v-model.trim="action.action_name" placeholder="动作名称" />
                    </div>
                    <div class="step-line compact">
                      <label class="number-field compact">
                        <span>超时</span>
                        <el-input-number v-model="action.timeout_seconds" :min="1" :max="86400" controls-position="right" />
                        <em>秒</em>
                      </label>
                      <label class="number-field compact">
                        <span>重试</span>
                        <el-input-number v-model="action.retry_count" :min="0" :max="20" controls-position="right" />
                        <em>次</em>
                      </label>
                      <el-select v-model="action.failure_strategy" placeholder="失败策略">
                        <el-option label="继续后续动作" value="continue" />
                        <el-option label="中止流程" value="abort" />
                      </el-select>
                    </div>
                    <div v-if="action.action_type === 'broadcast'" class="step-line">
                      <el-select v-model="action.broadcast_device_id" placeholder="广播设备">
                        <el-option v-for="item in config.broadcast_devices" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
                      </el-select>
                      <el-select v-model="action.template_id" placeholder="广播模板">
                        <el-option v-for="item in config.broadcast_templates" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
                      </el-select>
                    </div>
                    <div v-else-if="action.action_type === 'drone_dispatch'" class="step-line">
                      <el-input v-model.trim="action.drone_id" placeholder="无人机编号" />
                      <el-input v-model.trim="action.route_id" placeholder="航线编号" />
                    </div>
                    <div v-if="action.action_type === 'broadcast'" class="step-line compact">
                      <label class="number-field compact">
                        <span>间隔</span>
                        <el-input-number v-model="action.repeat_interval_seconds" :min="0" :max="86400" controls-position="right" />
                        <em>秒</em>
                      </label>
                      <label class="number-field compact">
                        <span>最多</span>
                        <el-input-number v-model="action.max_executions" :min="1" :max="100" controls-position="right" />
                        <em>次</em>
                      </label>
                    </div>
                  </div>
                  <div class="step-actions">
                    <el-switch v-model="action.enabled" active-text="启用" inactive-text="停用" />
                    <el-button type="primary" plain :loading="savingId === `action-${action.id}`" @click="saveAction(action)">保存</el-button>
                    <el-button :icon="Delete" plain type="danger" @click="removeAction(action)" />
                  </div>
                </article>
              </div>
              <el-empty v-else description="暂无动作配置" :image-size="70" />
            </article>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
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
  updateConditionConfig,
  updateEventConfig,
} from '@/api/integration'

const activeTab = ref('conditions')
const loading = ref(false)
const savingId = ref('')
const config = reactive({
  conditions: [],
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
    ElMessage.error(error.response?.data?.detail || '配置加载失败')
  } finally {
    loading.value = false
  }
}

async function save(key, action) {
  savingId.value = key
  try {
    await action()
    ElMessage.success('配置已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = ''
  }
}

function saveCondition(row) {
  return save(`condition-${row.id}`, () => updateConditionConfig(row.id, {
    duration: row.duration,
    enabled: row.enabled,
  }))
}

function saveEvent(row) {
  return save(`event-${row.id}`, () => updateEventConfig(row.id, {
    recovery_duration: row.recovery_duration,
    route_role_id: row.route_role_id || '',
    enabled: row.enabled,
  }))
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

function saveAction(row) {
  return save(`action-${row.id}`, () => updateActionConfig(row.id, actionPayload(row)))
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
    await ElMessageBox.confirm('确认删除该动作配置？', '删除动作', { type: 'warning' })
    await deleteActionConfig(row.id)
    ElMessage.success('动作已删除')
    await loadConfig()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

function riskTag(level) {
  return ({ 1: 'success', 2: 'warning', 3: 'danger', LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[level] || 'info'
}

onMounted(loadConfig)
</script>

<style scoped>
.config-page { min-height: 100%; padding: 20px; color: #d9e8f8; background: #071422; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }
.config-tabs { margin-top: 16px; }
.panel { padding: 14px; border: 1px solid rgba(96,151,191,.24); border-radius: 8px; background: #0b1d30; }
.config-list,
.action-event-list { display: grid; gap: 12px; }
.config-row {
  min-height: 68px;
  padding: 12px 14px;
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) auto auto auto;
  align-items: center;
  gap: 16px;
  border: 1px solid rgba(96,151,191,.16);
  border-radius: 6px;
  background: rgba(5,18,31,.55);
}
.row-title,
.event-card header div,
.action-event-header div { min-width: 0; }
.row-title strong,
.event-card strong,
.action-event-header strong { display: block; overflow: hidden; color: #f3f8fd; font-size: 16px; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }
.row-title span,
.event-card span,
.action-event-header span { display: block; margin-top: 5px; overflow: hidden; color: #92aac1; font-size: 13px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.number-field {
  display: grid;
  grid-template-columns: auto 132px auto;
  align-items: center;
  gap: 10px;
  color: #c4d8e8;
  font-size: 15px;
  white-space: nowrap;
}
.number-field.compact { grid-template-columns: auto 112px auto; }
.number-field em { color: #a9bed0; font-style: normal; font-size: 15px; }
.event-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.event-card,
.action-event,
.step-row {
  border: 1px solid rgba(96,151,191,.18);
  border-radius: 8px;
  background: rgba(5,18,31,.55);
}
.event-card { padding: 14px; display: grid; gap: 14px; }
.event-card header,
.event-card footer,
.action-event-header { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.event-fields { display: grid; grid-template-columns: 1fr minmax(180px, 1fr); gap: 12px; align-items: center; }
.action-event { padding: 14px; }
.action-event-header { margin-bottom: 12px; }
.step-list { display: grid; gap: 10px; }
.step-row {
  padding: 12px;
  display: grid;
  grid-template-columns: 116px minmax(360px, 1fr) auto;
  align-items: start;
  gap: 14px;
}
.step-order :deep(.el-input-number) { width: 108px; }
.step-main { display: grid; gap: 10px; min-width: 0; }
.step-line { display: grid; grid-template-columns: repeat(2, minmax(160px, 1fr)); gap: 10px; }
.step-line.compact { grid-template-columns: repeat(3, minmax(150px, auto)); justify-content: start; }
.step-actions { display: flex; align-items: center; gap: 10px; }
.config-page :deep(.el-tabs__item) { color: #9fb8ce; font-size: 15px; }
.config-page :deep(.el-tabs__item.is-active) { color: #74d7ff; font-weight: 700; }
.config-page :deep(.el-tabs__active-bar) { background-color: #43c7f4; }
.config-page :deep(.el-input-number) { width: 132px; }
.config-page :deep(.number-field.compact .el-input-number) { width: 112px; }
.config-page :deep(.el-input-number .el-input__wrapper),
.config-page :deep(.el-select .el-input__wrapper),
.config-page :deep(.el-input .el-input__wrapper) {
  min-height: 38px;
  background: #f8fbff;
  box-shadow: 0 0 0 1px rgba(139, 167, 188, .32) inset;
}
.config-page :deep(.el-input-number .el-input__inner) {
  color: #263849;
  font-size: 16px;
  font-weight: 700;
}
.config-page :deep(.el-input-number__decrease),
.config-page :deep(.el-input-number__increase) {
  width: 32px;
  color: #4f6475;
  background: #edf4fb;
  font-size: 15px;
}
.config-page :deep(.el-switch__label) { color: #9fb8ce; }
.config-page :deep(.el-switch__label.is-active) { color: #74d7ff; font-weight: 700; }
.config-page :deep(.el-button) { min-height: 36px; font-weight: 700; }
@media (max-width: 1250px) {
  .step-row { grid-template-columns: 1fr; }
  .step-actions { justify-content: flex-start; flex-wrap: wrap; }
}
@media (max-width: 900px) {
  .config-page { padding: 12px; }
  .page-header,
  .event-card header,
  .event-card footer,
  .action-event-header { align-items: flex-start; flex-direction: column; }
  .config-row,
  .event-fields,
  .step-line,
  .step-line.compact { grid-template-columns: 1fr; }
  .number-field,
  .number-field.compact { grid-template-columns: 76px 132px auto; }
}
</style>
