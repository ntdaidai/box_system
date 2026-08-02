<template>
  <div class="config-page">
    <header class="page-header">
      <div><p>实时监控 / 信息配置</p><h2>监测与处置参数</h2></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadConfig">刷新</el-button>
    </header>

    <el-tabs v-model="activeTab" class="config-tabs">
      <el-tab-pane label="触发条件" name="conditions">
        <section class="panel" v-loading="loading">
          <el-table :data="config.conditions" row-key="id">
            <el-table-column prop="name" label="条件名称" min-width="220" />
            <el-table-column label="持续时间" width="220"><template #default="{ row }"><el-input-number v-model="row.duration" :min="0" :max="3600" /><span class="unit">秒</span></template></el-table-column>
            <el-table-column label="启用" width="100"><template #default="{ row }"><el-switch v-model="row.enabled" /></template></el-table-column>
            <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="primary" :loading="savingId === `condition-${row.id}`" @click="saveCondition(row)">保存</el-button></template></el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="事件与恢复" name="events">
        <section class="panel" v-loading="loading">
          <el-table :data="config.events" row-key="id">
            <el-table-column prop="name" label="事件名称" width="150" />
            <el-table-column prop="category_label" label="事件类型" width="130" />
            <el-table-column label="风险等级" width="110"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)">{{ row.risk_label }}</el-tag></template></el-table-column>
            <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip />
            <el-table-column label="恢复确认" width="210"><template #default="{ row }"><el-input-number v-model="row.recovery_duration" :min="0" :max="3600" /><span class="unit">秒</span></template></el-table-column>
            <el-table-column label="启用" width="90"><template #default="{ row }"><el-switch v-model="row.enabled" /></template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="{ row }"><el-button link type="primary" :loading="savingId === `event-${row.id}`" @click="saveEvent(row)">保存</el-button></template></el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="处置流程" name="flows">
        <section class="panel flow-panel" v-loading="loading">
          <div class="flow-list">
            <div v-for="flow in config.flows" :key="flow.id" class="flow-row">
              <strong>{{ flow.name }}</strong><span>失败后继续后续步骤</span>
              <label>超时 <el-input-number v-model="flow.timeout_seconds" :min="1" :max="86400" /> 秒</label>
              <el-switch v-model="flow.enabled" active-text="启用" />
              <el-button link type="primary" :loading="savingId === `flow-${flow.id}`" @click="saveFlow(flow)">保存</el-button>
            </div>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="动作配置" name="actions">
        <section class="panel" v-loading="loading">
          <el-table :data="config.action_configs" row-key="id">
            <el-table-column prop="event_name" label="事件" width="130" />
            <el-table-column prop="camera_name" label="摄像头" width="150" />
            <el-table-column prop="action_label" label="动作" width="175" />
            <el-table-column label="执行配置" min-width="300">
              <template #default="{ row }">
                <div v-if="row.action_type === 'broadcast'" class="action-fields">
                  <el-select v-model="row.broadcast_device_id" placeholder="广播设备"><el-option v-for="item in config.broadcast_devices" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" /></el-select>
                  <el-select v-model="row.template_id" placeholder="广播模板"><el-option v-for="item in config.broadcast_templates" :key="item.id" :label="item.name" :value="item.id" :disabled="!item.enabled" /></el-select>
                </div>
                <div v-else-if="row.action_type === 'drone_dispatch'" class="action-fields"><el-input v-model.trim="row.drone_id" placeholder="无人机编号" /><el-input v-model.trim="row.route_id" placeholder="航线编号" /></div>
                <span v-else class="muted">由系统按事件与摄像头执行</span>
              </template>
            </el-table-column>
            <el-table-column label="执行频率" width="260"><template #default="{ row }"><div class="frequency"><el-input-number v-model="row.repeat_interval_seconds" :min="0" :max="86400" /><span>秒，最多</span><el-input-number v-model="row.max_executions" :min="1" :max="100" /><span>次</span></div></template></el-table-column>
            <el-table-column label="启用" width="85"><template #default="{ row }"><el-switch v-model="row.enabled" /></template></el-table-column>
            <el-table-column label="操作" width="85"><template #default="{ row }"><el-button link type="primary" :loading="savingId === `action-${row.id}`" @click="saveAction(row)">保存</el-button></template></el-table-column>
          </el-table>
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
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }
.config-tabs { margin-top: 16px; }.panel { padding: 14px; border: 1px solid rgba(96,151,191,.24); border-radius: 8px; background: #0b1d30; }.unit { margin-left: 8px; color: #8da6bc; }.action-fields { display: grid; grid-template-columns: repeat(2,minmax(130px,1fr)); gap: 8px; }.frequency { display: flex; align-items: center; gap: 6px; }.frequency :deep(.el-input-number) { width: 84px; }.muted,.flow-row span { color: #829bb3; }
.flow-list { display: grid; gap: 8px; }.flow-row { min-height: 58px; padding: 10px 14px; display: grid; grid-template-columns: minmax(210px,1.5fr) 1fr auto auto auto; align-items: center; gap: 16px; border-bottom: 1px solid rgba(96,151,191,.16); }.flow-row label { display: flex; align-items: center; gap: 7px; white-space: nowrap; }.flow-row :deep(.el-input-number) { width: 100px; }
@media (max-width: 900px) { .page-header { align-items: flex-start; flex-direction: column; }.flow-row { grid-template-columns: 1fr; align-items: start; }.action-fields { grid-template-columns: 1fr; }.config-page { padding: 12px; } }
</style>
