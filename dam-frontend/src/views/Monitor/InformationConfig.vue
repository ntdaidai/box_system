<template>
  <div class="config-page">
    <header class="page-header">
      <div><p>实时监控 / 信息配置</p><h2>监测与处置参数</h2></div>
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

      <el-tab-pane label="事件与恢复" name="events">
        <section class="panel" v-loading="loading">
          <div class="config-list">
            <article v-for="event in config.events" :key="event.id" class="config-row event-row">
              <div class="row-title">
                <strong>{{ event.name }}</strong>
                <span>{{ event.category_label }} · {{ event.description || '暂无说明' }}</span>
              </div>
              <el-tag :type="riskTag(event.risk_level)" effect="dark" class="risk-tag">{{ event.risk_label }}</el-tag>
              <label class="number-field">
                <span>恢复确认</span>
                <el-input-number v-model="event.recovery_duration" :min="0" :max="3600" controls-position="right" />
                <em>秒</em>
              </label>
              <el-switch v-model="event.enabled" active-text="启用" inactive-text="停用" />
              <el-button type="primary" plain :loading="savingId === `event-${event.id}`" @click="saveEvent(event)">保存</el-button>
            </article>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="处置流程" name="flows">
        <section class="panel flow-panel" v-loading="loading">
          <div class="flow-list">
            <div v-for="flow in config.flows" :key="flow.id" class="flow-row">
              <div class="row-title">
                <strong>{{ flow.name }}</strong>
                <span>失败后继续后续步骤</span>
              </div>
              <label class="number-field">
                <span>超时</span>
                <el-input-number v-model="flow.timeout_seconds" :min="1" :max="86400" controls-position="right" />
                <em>秒</em>
              </label>
              <el-switch v-model="flow.enabled" active-text="启用" inactive-text="停用" />
              <el-button type="primary" plain :loading="savingId === `flow-${flow.id}`" @click="saveFlow(flow)">保存</el-button>
            </div>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="动作配置" name="actions">
        <section class="panel" v-loading="loading">
          <div class="config-list">
            <article v-for="action in config.action_configs" :key="action.id" class="config-row action-row">
              <div class="row-title">
                <strong>{{ action.event_name }}</strong>
                <span>{{ action.camera_name }} · {{ action.action_label }}</span>
              </div>

              <div class="action-editor">
                <div v-if="action.action_type === 'broadcast'" class="action-fields">
                  <el-select v-model="action.broadcast_device_id" placeholder="广播设备">
                    <el-option v-for="item in config.broadcast_devices" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
                  </el-select>
                  <el-select v-model="action.template_id" placeholder="广播模板">
                    <el-option v-for="item in config.broadcast_templates" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" />
                  </el-select>
                </div>
                <div v-else-if="action.action_type === 'drone_dispatch'" class="action-fields">
                  <el-input v-model.trim="action.drone_id" placeholder="无人机编号" />
                  <el-input v-model.trim="action.route_id" placeholder="航线编号" />
                </div>
                <span v-else class="muted">由系统按事件与摄像头执行</span>
              </div>

              <div class="frequency">
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

              <el-switch v-model="action.enabled" active-text="启用" inactive-text="停用" />
              <el-button type="primary" plain :loading="savingId === `action-${action.id}`" @click="saveAction(action)">保存</el-button>
            </article>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getIntegrationConfig, updateActionConfig, updateConditionConfig, updateEventConfig, updateFlowConfig } from '@/api/integration'

const activeTab = ref('conditions')
const loading = ref(false)
const savingId = ref('')
const config = reactive({ conditions: [], events: [], flows: [], action_configs: [], broadcast_devices: [], broadcast_templates: [] })
async function loadConfig() { loading.value = true; try { const res = await getIntegrationConfig(); Object.assign(config, res.data || {}) } catch (error) { ElMessage.error(error.response?.data?.detail || '配置加载失败') } finally { loading.value = false } }
async function save(key, action) { savingId.value = key; try { await action(); ElMessage.success('配置已保存') } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { savingId.value = '' } }
function saveCondition(row) { return save(`condition-${row.id}`, () => updateConditionConfig(row.id, { duration: row.duration, enabled: row.enabled })) }
function saveEvent(row) { return save(`event-${row.id}`, () => updateEventConfig(row.id, { recovery_duration: row.recovery_duration, enabled: row.enabled })) }
function saveFlow(row) { return save(`flow-${row.id}`, () => updateFlowConfig(row.id, { timeout_seconds: row.timeout_seconds, enabled: row.enabled })) }
function saveAction(row) { return save(`action-${row.id}`, () => updateActionConfig(row.id, { enabled: row.enabled, broadcast_device_id: row.broadcast_device_id, template_id: row.template_id, drone_id: row.drone_id, route_id: row.route_id, repeat_interval_seconds: row.repeat_interval_seconds, max_executions: row.max_executions })) }
function riskTag(level) { return ({ 1: 'success', 2: 'warning', 3: 'danger' })[level] || 'info' }
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
.flow-list { display: grid; gap: 10px; }
.config-row,
.flow-row {
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
.action-row { grid-template-columns: minmax(180px, .9fr) minmax(260px, 1.4fr) auto auto auto; }
.row-title { min-width: 0; }
.row-title strong { display: block; overflow: hidden; color: #f3f8fd; font-size: 16px; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }
.row-title span,
.muted { display: block; margin-top: 5px; overflow: hidden; color: #92aac1; font-size: 13px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.number-field {
  display: grid;
  grid-template-columns: auto 132px auto;
  align-items: center;
  gap: 10px;
  color: #c4d8e8;
  font-size: 15px;
  white-space: nowrap;
}
.number-field.compact { grid-template-columns: auto 118px auto; }
.number-field em { color: #a9bed0; font-style: normal; font-size: 15px; }
.risk-tag { justify-self: start; min-width: 66px; justify-content: center; font-weight: 700; }
.action-editor { min-width: 0; }
.action-fields { display: grid; grid-template-columns: repeat(2,minmax(128px,1fr)); gap: 8px; }
.frequency { display: flex; align-items: center; gap: 12px; }
.config-page :deep(.el-tabs__item) { color: #9fb8ce; font-size: 15px; }
.config-page :deep(.el-tabs__item.is-active) { color: #74d7ff; font-weight: 700; }
.config-page :deep(.el-tabs__active-bar) { background-color: #43c7f4; }
.config-page :deep(.el-input-number) { width: 132px; }
.config-page :deep(.number-field.compact .el-input-number) { width: 118px; }
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
@media (max-width: 1200px) {
  .action-row { grid-template-columns: 1fr; align-items: start; }
  .action-fields { grid-template-columns: 1fr; width: 100%; }
  .frequency { flex-wrap: wrap; }
}
@media (max-width: 900px) {
  .config-page { padding: 12px; }
  .page-header { align-items: flex-start; flex-direction: column; }
  .config-row,
  .flow-row { grid-template-columns: 1fr; align-items: start; }
  .number-field,
  .number-field.compact { grid-template-columns: 76px 132px auto; }
}
</style>
