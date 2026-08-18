<template>
  <div class="linkage-page">
    <header class="page-header">
      <div>
        <h2>广播设备</h2>
        <p>管理广播设备与播报模板，供事件联动策略调用</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
    </header>

    <section class="resource-control-card" v-loading="loading">
      <header class="tab-header">
        <h3>{{ isTemplateView ? '播报模板' : '广播列表' }}</h3>
        <div v-if="!isTemplateView" class="tab-actions">
          <button type="button" class="toolbar-template-entry" @click="showTemplates">
            <el-icon><Tickets /></el-icon>
            <span>查看模板</span>
          </button>
          <el-button type="primary" :icon="Plus" @click="openDeviceDialog()">新增设备</el-button>
          <el-select
            v-model="deviceFilters.status"
            class="status-filter-select"
            popper-class="broadcast-filter-popper"
            placeholder="在线状态"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
          </el-select>
        </div>
        <div v-else class="tab-actions">
          <button type="button" class="toolbar-return-entry" @click="showDevices">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回广播列表</span>
          </button>
          <el-button type="primary" :icon="Plus" @click="openTemplateDialog()">新增模板</el-button>
          <el-select
            v-model="templateFilters.scene_type"
            class="scene-filter-select"
            popper-class="broadcast-filter-popper"
            placeholder="全部场景"
          >
            <el-option label="全部场景" value="all" />
            <el-option v-for="item in sceneOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-model="templateFilters.enabled"
            class="status-filter-select"
            popper-class="broadcast-filter-popper"
            placeholder="启用状态"
          >
            <el-option label="全部" value="all" />
            <el-option label="启用" value="enabled" />
            <el-option label="未启用" value="disabled" />
          </el-select>
        </div>
      </header>
    </section>

    <section class="resource-list-card" v-loading="loading">
      <template v-if="!isTemplateView">
        <div class="broadcast-list" :class="{ 'is-empty': !filteredBroadcastDevices.length }">
          <div v-if="filteredBroadcastDevices.length" class="broadcast-list-header-row">
            <div class="col-device">设备名称</div>
            <div class="col-device-desc">描述</div>
            <div class="col-device-status">状态</div>
            <div class="col-device-enabled">是否启用</div>
            <div class="col-device-actions">操作</div>
          </div>
          <article v-for="row in pagedBroadcastDevices" :key="row.id" class="broadcast-row">
            <div class="col-device broadcast-name">
              <strong>{{ row.name }}</strong>
            </div>
            <div class="col-device-desc broadcast-description">
              <span>{{ row.description || '--' }}</span>
            </div>
            <div class="col-device-status">
              <span class="status-pill" :class="row.status === 'ONLINE' ? 'is-online' : 'is-offline'">
                {{ row.status === 'ONLINE' ? '在线' : '离线' }}
              </span>
            </div>
            <div class="col-device-enabled">
              <el-switch
                :model-value="row.enabled !== false"
                :loading="deviceEnableLoading[row.id]"
                @change="(value) => toggleDeviceEnabled(row, value)"
              />
            </div>
            <div class="col-device-actions list-actions">
              <el-button class="test-action" :loading="testLoading[row.id]" @click="testBroadcastDevice(row)">测试</el-button>
              <el-button class="edit-action" @click="openDeviceDialog(row)">编辑</el-button>
              <el-button class="delete-action" @click="confirmDeleteDevice(row)">删除</el-button>
            </div>
          </article>
          <div v-if="!filteredBroadcastDevices.length" class="empty-list">
            <strong>暂无匹配设备</strong>
            <span>调整在线状态筛选后再试</span>
          </div>
        </div>
        <el-pagination
          v-if="filteredBroadcastDevices.length"
          v-model:current-page="devicePage"
          class="list-pagination"
          :page-size="pageSize"
          :total="filteredBroadcastDevices.length"
          layout="prev, pager, next"
        />
      </template>

      <template v-else>
        <div class="template-list" :class="{ 'is-empty': !filteredBroadcastTemplates.length }">
          <div v-if="filteredBroadcastTemplates.length" class="template-list-header-row">
            <div class="col-template-name">模板名称</div>
            <div class="col-template-scene">适用场景</div>
            <div class="col-template-risk">风险等级</div>
            <div class="col-template-content">播报内容</div>
            <div class="col-template-enabled">启用状态</div>
            <div class="col-template-actions">操作</div>
          </div>
          <article v-for="row in pagedBroadcastTemplates" :key="row.id" class="template-row">
            <div class="col-template-name template-name-cell">
              <strong>{{ row.name }}</strong>
            </div>
            <div class="col-template-scene scene-cell">
              <span>{{ sceneLabel(row.scene_type) }}</span>
            </div>
            <div class="col-template-risk">
              <el-tag :type="riskTag(row.risk_level)" effect="dark">{{ riskLabel(row.risk_level) }}</el-tag>
            </div>
            <div class="col-template-content">
              <p class="content-preview">{{ row.content || '--' }}</p>
            </div>
            <div class="col-template-enabled">
              <el-switch
                :model-value="row.enabled !== false"
                :loading="templateEnableLoading[row.id]"
                @change="(value) => toggleTemplateEnabled(row, value)"
              />
            </div>
            <div class="col-template-actions list-actions">
              <el-button class="edit-action" @click="openTemplateDialog(row)">编辑</el-button>
              <el-button class="delete-action" @click="confirmDeleteTemplate(row)">删除</el-button>
            </div>
          </article>
          <div v-if="!filteredBroadcastTemplates.length" class="empty-list">
            <strong>暂无播报模板</strong>
            <span>新增模板后可在事件联动策略中调用</span>
          </div>
        </div>
        <el-pagination
          v-if="filteredBroadcastTemplates.length"
          v-model:current-page="templatePage"
          class="list-pagination"
          :page-size="pageSize"
          :total="filteredBroadcastTemplates.length"
          layout="prev, pager, next"
        />
      </template>
    </section>

    <el-dialog
      v-model="deviceDialogVisible"
      :title="deviceDialogTitle"
      width="560px"
      class="broadcast-config-dialog"
      destroy-on-close
    >
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceRules" label-position="top">
        <el-form-item label="设备名称" prop="name">
          <el-input v-model.trim="deviceForm.name" maxlength="128" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model.trim="deviceForm.description"
            type="textarea"
            maxlength="500"
            :rows="4"
            placeholder="请输入设备描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDevice" @click="submitDevice">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="templateDialogVisible"
      :title="templateDialogTitle"
      width="620px"
      class="broadcast-config-dialog"
      destroy-on-close
    >
      <el-form ref="templateFormRef" :model="templateForm" :rules="templateRules" label-position="top">
        <el-form-item label="模板名称" prop="name">
          <el-input v-model.trim="templateForm.name" maxlength="128" placeholder="请输入模板名称" />
        </el-form-item>
        <div class="form-grid two">
          <el-form-item label="适用场景" prop="scene_type">
            <el-select v-model="templateForm.scene_type" placeholder="请选择场景">
              <el-option v-for="item in sceneOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="风险等级" prop="risk_level">
            <el-select v-model="templateForm.risk_level" placeholder="请选择风险等级">
              <el-option v-for="item in riskOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="播报文本" prop="content">
          <el-input
            v-model.trim="templateForm.content"
            type="textarea"
            maxlength="500"
            :rows="5"
            placeholder="请输入播报文本"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" @click="submitTemplate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="testDialogVisible"
      title="测试广播播放"
      width="560px"
      class="broadcast-config-dialog"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="广播设备">
          <el-input :model-value="testingDevice?.name || '--'" disabled />
        </el-form-item>
        <el-form-item label="测试模板" required>
          <el-select
            v-model="testTemplateId"
            class="template-test-select"
            popper-class="broadcast-filter-popper"
            placeholder="请选择测试模板"
          >
            <el-option
              v-for="item in enabledTemplates"
              :key="item.id"
              :label="`${item.name} · ${sceneLabel(item.scene_type)} · ${riskLabel(item.risk_level)}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="testSubmitting" @click="submitTestBroadcast">开始测试</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Refresh, Tickets } from '@element-plus/icons-vue'
import {
  createBroadcastDevice,
  createBroadcastTemplate,
  deleteBroadcastDevice,
  deleteBroadcastTemplate,
  getBroadcastDevices,
  getBroadcastTemplates,
  playBroadcast,
  updateBroadcastDevice,
  updateBroadcastTemplate,
} from '@/api/broadcast'

const viewMode = ref('devices')
const loading = ref(false)
const broadcastDevices = ref([])
const broadcastTemplates = ref([])
const deviceFormRef = ref(null)
const templateFormRef = ref(null)
const deviceDialogVisible = ref(false)
const templateDialogVisible = ref(false)
const testDialogVisible = ref(false)
const editingDeviceId = ref(null)
const editingTemplateId = ref('')
const testingDevice = ref(null)
const testTemplateId = ref('')
const testSubmitting = ref(false)
const savingDevice = ref(false)
const savingTemplate = ref(false)
const devicePage = ref(1)
const templatePage = ref(1)
const deviceEnableLoading = ref({})
const templateEnableLoading = ref({})
const testLoading = ref({})
const pageSize = 10
const deviceFilters = reactive({
  status: 'all',
})
const templateFilters = reactive({
  enabled: 'all',
  scene_type: 'all',
})

const deviceForm = reactive({
  name: '',
  description: '',
  enabled: true,
})

const templateForm = reactive({
  name: '',
  scene_type: 'PERSON',
  risk_level: 'MEDIUM',
  content: '',
  enabled: true,
})

const deviceRules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
}

const templateRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  scene_type: [{ required: true, message: '请选择或输入场景', trigger: 'change' }],
  risk_level: [{ required: true, message: '请选择风险等级', trigger: 'change' }],
  content: [{ required: true, message: '请输入播报文本', trigger: 'blur' }],
}

const riskOptions = [
  { label: '低风险', value: 'LOW' },
  { label: '中风险', value: 'MEDIUM' },
  { label: '高风险', value: 'HIGH' },
]

const sceneOptions = [
  { label: '人员风险', value: 'PERSON' },
  { label: '非法捕鱼', value: 'FISHING' },
  { label: '设备异常', value: 'EQUIPMENT' },
  { label: '环境风险', value: 'ENVIRONMENT' },
]

const deviceDialogTitle = computed(() => editingDeviceId.value ? '编辑广播设备' : '新增广播设备')
const templateDialogTitle = computed(() => editingTemplateId.value ? '编辑播报模板' : '新增播报模板')
const isTemplateView = computed(() => viewMode.value === 'templates')
const filteredBroadcastDevices = computed(() => {
  return broadcastDevices.value.filter((item) => {
    const status = item.status === 'ONLINE' ? 'online' : 'offline'
    const matchesStatus = deviceFilters.status === 'all' || deviceFilters.status === status
    return matchesStatus
  })
})
const pagedBroadcastDevices = computed(() => {
  const start = (devicePage.value - 1) * pageSize
  return filteredBroadcastDevices.value.slice(start, start + pageSize)
})
const filteredBroadcastTemplates = computed(() => {
  return broadcastTemplates.value.filter((item) => {
    const matchesEnabled = templateFilters.enabled === 'all'
      || (templateFilters.enabled === 'enabled'
      ? item.enabled !== false
      : item.enabled === false)
    const matchesScene = templateFilters.scene_type === 'all'
      || normalizeSceneType(item.scene_type) === templateFilters.scene_type
    return matchesEnabled && matchesScene
  })
})
const enabledTemplates = computed(() => broadcastTemplates.value.filter((item) => item.enabled !== false))
const pagedBroadcastTemplates = computed(() => {
  const start = (templatePage.value - 1) * pageSize
  return filteredBroadcastTemplates.value.slice(start, start + pageSize)
})

watch(deviceFilters, () => {
  devicePage.value = 1
})

watch(templateFilters, () => {
  templatePage.value = 1
})

watch(filteredBroadcastDevices, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (devicePage.value > maxPage) devicePage.value = maxPage
})

watch(filteredBroadcastTemplates, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (templatePage.value > maxPage) templatePage.value = maxPage
})

async function refreshCurrent() {
  loading.value = true
  try {
    await loadBroadcast()
  } finally {
    loading.value = false
  }
}

async function loadBroadcast() {
  try {
    const [deviceRes, templateRes] = await Promise.all([getBroadcastDevices(), getBroadcastTemplates()])
    broadcastDevices.value = deviceRes.data || []
    broadcastTemplates.value = templateRes.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '广播设备加载失败')
  }
}

function showTemplates() {
  viewMode.value = 'templates'
  templatePage.value = 1
}

function showDevices() {
  viewMode.value = 'devices'
}

function openDeviceDialog(row = null) {
  editingDeviceId.value = row?.id || null
  Object.assign(deviceForm, {
    name: row?.name || '',
    description: row?.description || '',
    enabled: row?.enabled !== false,
  })
  deviceDialogVisible.value = true
  nextTick(() => deviceFormRef.value?.clearValidate?.())
}

async function submitDevice() {
  try {
    await deviceFormRef.value?.validate?.()
  } catch {
    return
  }
  savingDevice.value = true
  try {
    const payload = {
      name: deviceForm.name,
      description: deviceForm.description || null,
      enabled: deviceForm.enabled,
    }
    const res = editingDeviceId.value
      ? await updateBroadcastDevice(editingDeviceId.value, payload)
      : await createBroadcastDevice(payload)
    ElMessage.success(res.message || '广播设备已保存')
    deviceDialogVisible.value = false
    await loadBroadcast()
  } catch {
    return
  } finally {
    savingDevice.value = false
  }
}

async function toggleDeviceEnabled(row, enabled) {
  const previous = row.enabled !== false
  deviceEnableLoading.value = { ...deviceEnableLoading.value, [row.id]: true }
  row.enabled = enabled
  try {
    const res = await updateBroadcastDevice(row.id, {
      name: row.name,
      description: row.description || null,
      enabled,
    })
    ElMessage.success(res.message || (enabled ? '广播设备已启用' : '广播设备已停用'))
    await loadBroadcast()
  } catch (error) {
    row.enabled = previous
    ElMessage.error(error.response?.data?.detail || '启用状态更新失败')
  } finally {
    deviceEnableLoading.value = { ...deviceEnableLoading.value, [row.id]: false }
  }
}

async function testBroadcastDevice(row) {
  if (!enabledTemplates.value.length) {
    ElMessage.warning('请先新增并启用一个播报模板')
    return
  }
  if (row.enabled === false) {
    ElMessage.warning('当前广播设备未启用')
    return
  }
  testingDevice.value = row
  testTemplateId.value = enabledTemplates.value[0]?.id || ''
  testDialogVisible.value = true
}

async function submitTestBroadcast() {
  const row = testingDevice.value
  if (!row) return
  if (!testTemplateId.value) {
    ElMessage.warning('请选择测试模板')
    return
  }
  const template = broadcastTemplates.value.find((item) => item.id === testTemplateId.value)
  testSubmitting.value = true
  testLoading.value = { ...testLoading.value, [row.id]: true }
  try {
    const res = await playBroadcast({
      device_ids: [Number(row.id)],
      template_id: testTemplateId.value,
      trigger_type: 'MANUAL',
    })
    ElMessage.success(res.message || `已播放测试模板：${template?.name || '未命名模板'}`)
    testDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '广播测试失败')
  } finally {
    testSubmitting.value = false
    testLoading.value = { ...testLoading.value, [row.id]: false }
  }
}

async function confirmDeleteDevice(row) {
  try {
    await ElMessageBox.confirm(`确认删除广播设备「${row.name}」？`, '删除设备', { type: 'warning' })
    const res = await deleteBroadcastDevice(row.id)
    ElMessage.success(res.message || '广播设备已删除')
    await loadBroadcast()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      return
    }
  }
}

function openTemplateDialog(row = null) {
  editingTemplateId.value = row?.id || ''
  Object.assign(templateForm, {
    name: row?.name || '',
    scene_type: normalizeSceneType(row?.scene_type || 'PERSON'),
    risk_level: row?.risk_level || 'MEDIUM',
    content: row?.content || '',
    enabled: row?.enabled !== false,
  })
  templateDialogVisible.value = true
  nextTick(() => templateFormRef.value?.clearValidate?.())
}

async function submitTemplate() {
  try {
    await templateFormRef.value?.validate?.()
  } catch {
    return
  }
  savingTemplate.value = true
  try {
    const payload = {
      name: templateForm.name,
      scene_type: templateForm.scene_type,
      risk_level: templateForm.risk_level,
      content: templateForm.content,
      enabled: templateForm.enabled,
    }
    const res = editingTemplateId.value
      ? await updateBroadcastTemplate(editingTemplateId.value, payload)
      : await createBroadcastTemplate(payload)
    ElMessage.success(res.message || '广播模板已保存')
    templateDialogVisible.value = false
    await loadBroadcast()
  } catch {
    return
  } finally {
    savingTemplate.value = false
  }
}

async function toggleTemplateEnabled(row, enabled) {
  const previous = row.enabled !== false
  templateEnableLoading.value = { ...templateEnableLoading.value, [row.id]: true }
  row.enabled = enabled
  try {
    const res = await updateBroadcastTemplate(row.id, {
      name: row.name,
      scene_type: row.scene_type,
      risk_level: row.risk_level,
      content: row.content,
      enabled,
    })
    ElMessage.success(res.message || (enabled ? '播报模板已启用' : '播报模板已停用'))
    await loadBroadcast()
  } catch (error) {
    row.enabled = previous
    ElMessage.error(error.response?.data?.detail || '启用状态更新失败')
  } finally {
    templateEnableLoading.value = { ...templateEnableLoading.value, [row.id]: false }
  }
}

async function confirmDeleteTemplate(row) {
  try {
    await ElMessageBox.confirm(`确认删除播报模板「${row.name}」？`, '删除模板', { type: 'warning' })
    const res = await deleteBroadcastTemplate(row.id)
    ElMessage.success(res.message || '广播模板已删除')
    await loadBroadcast()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      return
    }
  }
}

function riskLabel(value) {
  return riskOptions.find(item => item.value === value)?.label || value || '-'
}

function riskTag(value) {
  return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[value] || 'info'
}

function sceneLabel(value) {
  return sceneOptions.find(item => item.value === normalizeSceneType(value))?.label || value || '-'
}

function normalizeSceneType(value) {
  return ({
    PERSON_SAFETY: 'PERSON',
    ILLEGAL_FISHING: 'FISHING',
  })[value] || value
}

onMounted(refreshCurrent)
</script>

<style scoped>
.linkage-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.page-header,
.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header {
  min-height: 62px;
  margin-bottom: 14px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}
.page-header h2,
.tab-header h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}
.page-header h2 {
  font-size: 25px;
  line-height: 1.15;
}
.page-header p {
  margin: 7px 0 0;
  color: #87a5bb;
  font-size: 13px;
  line-height: 1.45;
}
.page-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}
.tab-header {
  margin: 0;
}
.tab-header h3 {
  font-size: 18px;
}
.tab-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  flex-wrap: nowrap;
}
.tab-actions :deep(.el-button) {
  min-width: 108px;
  height: 36px;
  margin-left: 0;
  padding: 0 15px;
}
.resource-control-card,
.resource-list-card {
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
}
.resource-control-card {
  min-height: 82px;
  display: flex;
  align-items: center;
  padding: 18px 20px;
}
.resource-control-card .tab-header {
  width: 100%;
}
.resource-list-card {
  margin-top: 16px;
  overflow: hidden;
}
.status-filter-select {
  width: 116px;
  flex: 0 0 auto;
}
.scene-filter-select {
  width: 136px;
  flex: 0 0 auto;
}
.status-filter-select :deep(.el-select__wrapper),
.scene-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, .36) inset;
}
.status-filter-select :deep(.el-select__selected-item),
.status-filter-select :deep(.el-select__placeholder),
.scene-filter-select :deep(.el-select__selected-item),
.scene-filter-select :deep(.el-select__placeholder) {
  color: #d7edf6;
  font-weight: 700;
}
.status-filter-select :deep(.el-select__caret),
.scene-filter-select :deep(.el-select__caret) {
  color: #8fd4df;
}
.toolbar-template-entry,
.toolbar-return-entry {
  flex: 0 0 auto;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 18px 0 12px;
  border: 1px solid rgba(72, 216, 255, .58);
  border-radius: 6px;
  color: #e8faff;
  background: linear-gradient(135deg, rgba(23, 116, 155, .78), rgba(10, 59, 88, .78));
  font: inherit;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, .10), 0 0 16px rgba(72, 216, 255, .14);
  transition: border-color .18s ease, background .18s ease, color .18s ease;
}
.toolbar-return-entry {
  height: 36px;
  padding: 0 14px 0 10px;
  font-size: 14px;
  background: rgba(13, 45, 70, .72);
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, .08);
}
.toolbar-template-entry:hover,
.toolbar-return-entry:hover {
  border-color: rgba(126, 238, 255, .82);
  color: #ffffff;
  background: linear-gradient(135deg, rgba(30, 136, 181, .9), rgba(12, 72, 108, .9));
}
.toolbar-template-entry .el-icon,
.toolbar-return-entry .el-icon {
  width: 26px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  color: #031825;
  background: #48d8ff;
  font-size: 18px;
}
.toolbar-return-entry .el-icon {
  width: 22px;
  height: 22px;
  font-size: 15px;
}
.mode-action {
  border-color: rgba(70, 145, 190, .38);
  color: #bfe2f7;
  background: rgba(13, 45, 70, .72);
}
.broadcast-list,
.template-list {
  overflow: hidden;
  border: 0;
  border-radius: 8px 8px 0 0;
  background: #081b2d;
}
.broadcast-list {
  min-width: 1180px;
}
.template-list {
  min-width: 1400px;
}
.broadcast-list-header-row,
.broadcast-row,
.template-list-header-row,
.template-row {
  display: grid;
  align-items: center;
  gap: 14px;
}
.broadcast-list-header-row,
.template-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}
.broadcast-row,
.template-row {
  min-height: 72px;
  padding: 12px 20px;
  border-top: 1px solid rgba(149, 190, 220, .10);
  color: #d7e8f8;
  background: #092034;
  transition: background .18s ease;
}
.broadcast-row:hover,
.template-row:hover {
  background: #102940;
}
.broadcast-list-header-row,
.broadcast-row {
  grid-template-columns: minmax(180px, 1fr) minmax(260px, 1.15fr) 152px 164px 300px;
}
.template-list-header-row,
.template-row {
  grid-template-columns: minmax(210px, 1fr) 150px 112px minmax(340px, 1.45fr) 122px 190px;
}
.col-device,
.col-device-desc,
.col-device-status,
.col-device-enabled,
.col-device-actions,
.col-template-name,
.col-template-scene,
.col-template-risk,
.col-template-content,
.col-template-enabled,
.col-template-actions,
.broadcast-name,
.broadcast-description,
.template-name-cell {
  min-width: 0;
  display: grid;
  gap: 6px;
  justify-items: center;
  text-align: center;
}

.broadcast-name strong,
.template-name-cell strong {
  display: block;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.broadcast-description span {
  display: -webkit-box;
  overflow: hidden;
  color: #a9c0d2;
  font-size: 15px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.list-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: nowrap;
}
.list-actions :deep(.el-button) {
  width: auto;
  height: 34px;
  min-height: 34px;
  margin: 0;
  padding: 0 16px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.list-actions :deep(.test-action) {
  border-color: rgba(82, 178, 143, .46);
  color: #b9f1d8;
  background: rgba(30, 103, 78, .38);
}
.list-actions :deep(.edit-action) {
  border-color: rgba(66, 164, 224, .50);
  color: #d5f0ff;
  background: rgba(29, 91, 133, .70);
}
.list-actions :deep(.delete-action) {
  border-color: rgba(226, 88, 109, .46);
  color: #ffb1bd;
  background: rgba(128, 36, 54, .48);
}
.list-actions :deep(.test-action:hover) {
  border-color: rgba(82, 178, 143, .7);
  color: #e3fff1;
  background: rgba(36, 123, 92, .52);
}
.list-actions :deep(.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72);
  color: #effaff;
  background: rgba(33, 107, 156, .82);
}
.list-actions :deep(.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68);
  color: #ffd5dd;
  background: rgba(144, 42, 62, .62);
}
:global(.linkage-page .list-actions .el-button.test-action) {
  border-color: rgba(82, 178, 143, .54) !important;
  color: #b9f1d8 !important;
  background: rgba(30, 103, 78, .42) !important;
}
:global(.linkage-page .list-actions .el-button.edit-action) {
  border-color: rgba(66, 164, 224, .50) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .70) !important;
}
:global(.linkage-page .list-actions .el-button.delete-action) {
  border-color: rgba(226, 88, 109, .46) !important;
  color: #ffb1bd !important;
  background: rgba(128, 36, 54, .48) !important;
}
:global(.linkage-page .list-actions .el-button.test-action:hover) {
  border-color: rgba(82, 178, 143, .72) !important;
  color: #e3fff1 !important;
  background: rgba(36, 123, 92, .56) !important;
}
:global(.linkage-page .list-actions .el-button.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .82) !important;
}
:global(.linkage-page .list-actions .el-button.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68) !important;
  color: #ffd5dd !important;
  background: rgba(144, 42, 62, .62) !important;
}
.list-pagination {
  min-height: 46px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, .10);
  background: #092034;
}
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 34px;
  height: 32px;
  margin: 0 3px;
  border: 1px solid rgba(70, 145, 190, .34);
  border-radius: 5px;
  color: #8fb6d1;
  background: #0b2238;
  font-weight: 700;
}
.list-pagination :deep(.el-pager li.is-active) {
  border-color: #4ba7e6;
  color: #fff;
  background: #3f95d7;
}
.list-pagination :deep(.btn-prev:disabled),
.list-pagination :deep(.btn-next:disabled) {
  color: rgba(143, 182, 209, .35);
  background: #0b2238;
}
.empty-list {
  min-height: 220px;
  display: grid;
  place-content: center;
  gap: 8px;
  color: #8fa8bf;
  text-align: center;
}
.empty-list strong {
  color: #e9f7ff;
  font-size: 16px;
}
.scene-cell {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.scene-cell span {
  color: #d7e8f8;
  font-size: 15px;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  height: 24px;
  padding: 0 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}
.status-pill.is-online {
  border: 1px solid rgba(92, 215, 154, .34);
  color: #81efad;
  background: rgba(48, 154, 118, .18);
}
.status-pill.is-offline {
  border: 1px solid rgba(235, 124, 133, .34);
  color: #ffabb5;
  background: rgba(142, 48, 62, .18);
}
.col-device-enabled :deep(.el-switch__core),
.col-template-enabled :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, .34);
  background: rgba(96, 118, 134, .38);
}
.col-device-enabled :deep(.el-switch.is-checked .el-switch__core),
.col-template-enabled :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, .66);
  background: #409eff;
}
.content-preview {
  max-width: 100%;
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  line-height: 1.5;
  text-align: center;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.linkage-page :deep(.el-button) {
  min-height: 34px;
  font-weight: 700;
}
:global(.broadcast-config-dialog.el-dialog) {
  border: 1px solid rgba(97, 167, 214, .40);
  border-radius: 10px;
  background: #1d426a;
}
:global(.broadcast-config-dialog .el-dialog__header) {
  position: relative;
  min-height: 58px;
  display: flex;
  align-items: center;
  margin: 0;
  padding: 18px 58px 10px 24px;
}
:global(.broadcast-config-dialog .el-dialog__title) {
  color: #eef7ff;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
}
:global(.broadcast-config-dialog .el-dialog__headerbtn) {
  top: 14px;
  right: 18px;
  width: 34px;
  height: 34px;
}
:global(.broadcast-config-dialog .el-dialog__close) {
  color: #c8d9e7;
}
:global(.broadcast-config-dialog .el-dialog__body) {
  padding: 12px 24px 8px;
}
:global(.broadcast-config-dialog .el-dialog__footer) {
  padding: 12px 24px 20px;
}
.broadcast-config-dialog :deep(.el-select),
.broadcast-config-dialog :deep(.el-input-number) {
  width: 100%;
}
.broadcast-config-dialog :deep(.el-form-item__label) {
  margin-bottom: 8px;
  color: #e2f0fb !important;
  font-size: 15px;
  font-weight: 700;
}
:global(.broadcast-config-dialog .el-form-item__label) {
  margin-bottom: 8px !important;
  color: #e2f0fb !important;
  font-size: 15px !important;
  font-weight: 700 !important;
}
.broadcast-config-dialog :deep(.el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::before) {
  display: none;
}
.broadcast-config-dialog :deep(.el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::after) {
  content: "*";
  margin-left: 6px;
  color: #ff6b78;
  font-size: 20px;
  font-weight: 900;
  line-height: 1;
  vertical-align: -2px;
}
:global(.broadcast-config-dialog .el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::before) {
  display: none !important;
}
:global(.broadcast-config-dialog .el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::after) {
  content: "*" !important;
  margin-left: 6px !important;
  color: #ff6b78 !important;
  font-size: 20px !important;
  font-weight: 900 !important;
  line-height: 1 !important;
  vertical-align: -2px !important;
}
.broadcast-config-dialog :deep(.el-input__wrapper),
.broadcast-config-dialog :deep(.el-textarea__inner) {
  background: #092034;
  box-shadow: inset 0 0 0 1px rgba(36, 128, 176, .46);
  color: #f4fbff;
}
.broadcast-config-dialog :deep(.el-input__inner),
.broadcast-config-dialog :deep(.el-textarea__inner) {
  color: #f4fbff;
}
.broadcast-config-dialog :deep(.el-input__inner::placeholder),
.broadcast-config-dialog :deep(.el-textarea__inner::placeholder) {
  color: #a5b8c7;
}
.broadcast-config-dialog :deep(.el-input__count) {
  display: none;
}
.template-test-select {
  width: 100%;
}
.form-grid {
  display: grid;
  gap: 14px;
}
.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
:global(.broadcast-filter-popper.el-select__popper) {
  border: 1px solid rgba(72, 216, 255, .28);
  background: #082033;
  box-shadow: 0 16px 36px rgba(0, 7, 18, .38);
}
:global(.broadcast-filter-popper .el-popper__arrow::before) {
  border-color: rgba(72, 216, 255, .28);
  background: #082033;
}
:global(.broadcast-filter-popper .el-select-dropdown__item) {
  color: #aecdde;
}
:global(.broadcast-filter-popper .el-select-dropdown__item.is-hovering),
:global(.broadcast-filter-popper .el-select-dropdown__item:hover) {
  color: #e9fbff;
  background: rgba(72, 216, 255, .12);
}
:global(.broadcast-filter-popper .el-select-dropdown__item.is-selected),
:global(.broadcast-filter-popper .el-select-dropdown__item.selected) {
  color: #50e1d0;
  font-weight: 800;
}
@media (max-width: 900px) {
  .linkage-page { padding: 12px; }
  .page-header,
  .tab-header { align-items: flex-start; flex-direction: column; }
  .resource-control-card {
    min-height: 108px;
  }
  .tab-actions {
    width: 100%;
    align-items: flex-start;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
  .resource-list-card { overflow-x: auto; }
  .form-grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
