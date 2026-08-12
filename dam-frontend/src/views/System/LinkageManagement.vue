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
          <el-button class="mode-action" @click="showTemplates">查看模板 {{ broadcastTemplates.length }}</el-button>
          <el-button type="primary" :icon="Plus" @click="openDeviceDialog()">新增设备</el-button>
          <el-radio-group v-model="deviceFilters.status" class="segmented-filter">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="online">在线</el-radio-button>
            <el-radio-button label="offline">离线</el-radio-button>
          </el-radio-group>
        </div>
        <div v-else class="tab-actions">
          <el-button class="mode-action" @click="showDevices">返回广播列表</el-button>
          <el-button type="primary" :icon="Plus" @click="openTemplateDialog()">新增模板</el-button>
        </div>
      </header>
    </section>

    <section class="resource-list-card" v-loading="loading">
      <template v-if="!isTemplateView">
        <div class="broadcast-list" :class="{ 'is-empty': !filteredBroadcastDevices.length }">
          <div v-if="filteredBroadcastDevices.length" class="broadcast-list-header-row">
            <div class="col-device">设备名称</div>
            <div class="col-device-desc">描述</div>
            <div class="col-device-status">运行状态</div>
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
              <span class="inline-state" :class="row.status === 'ONLINE' ? 'is-online' : 'is-offline'">
                <i></i>{{ row.status === 'ONLINE' ? '在线' : '离线' }}
              </span>
            </div>
            <div class="col-device-actions list-actions">
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
        <div class="template-list" :class="{ 'is-empty': !broadcastTemplates.length }">
          <div v-if="broadcastTemplates.length" class="template-list-header-row">
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
              <small v-if="sceneLabel(row.scene_type) !== row.scene_type">{{ row.scene_type }}</small>
            </div>
            <div class="col-template-risk">
              <span class="risk-pill" :class="`risk-${String(row.risk_level || '').toLowerCase()}`">{{ riskLabel(row.risk_level) }}</span>
            </div>
            <div class="col-template-content">
              <el-tooltip :content="row.content || ''" placement="top-start" :disabled="!row.content">
                <p class="content-preview">{{ row.content || '--' }}</p>
              </el-tooltip>
            </div>
            <div class="col-template-enabled">
              <span class="enabled-text" :class="{ muted: row.enabled === false }">{{ row.enabled === false ? '已停用' : '已启用' }}</span>
            </div>
            <div class="col-template-actions list-actions">
              <el-button class="edit-action" @click="openTemplateDialog(row)">编辑</el-button>
              <el-button class="delete-action" @click="confirmDeleteTemplate(row)">删除</el-button>
            </div>
          </article>
          <div v-if="!broadcastTemplates.length" class="empty-list">
            <strong>暂无播报模板</strong>
            <span>新增模板后可在事件联动策略中调用</span>
          </div>
        </div>
        <el-pagination
          v-if="broadcastTemplates.length"
          v-model:current-page="templatePage"
          class="list-pagination"
          :page-size="pageSize"
          :total="broadcastTemplates.length"
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
        <el-form-item label="备注" prop="description">
          <el-input
            v-model.trim="deviceForm.description"
            type="textarea"
            maxlength="500"
            :rows="4"
            show-word-limit
            placeholder="请输入设备备注"
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
        <el-form-item label="适用场景" prop="scene_type">
          <el-select
            v-model="templateForm.scene_type"
            filterable
            allow-create
            default-first-option
            placeholder="请选择或输入场景"
          >
            <el-option v-for="item in sceneOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级" prop="risk_level">
          <el-radio-group v-model="templateForm.risk_level" class="dialog-radio-group">
            <el-radio-button v-for="item in riskOptions" :key="item.value" :label="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="播报文本" prop="content">
          <el-input
            v-model.trim="templateForm.content"
            type="textarea"
            maxlength="500"
            :rows="8"
            show-word-limit
            placeholder="请输入播报文本"
          />
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch v-model="templateForm.enabled" active-text="已启用" inactive-text="已停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" @click="submitTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  createBroadcastDevice,
  createBroadcastTemplate,
  deleteBroadcastDevice,
  deleteBroadcastTemplate,
  getBroadcastDevices,
  getBroadcastTemplates,
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
const editingDeviceId = ref(null)
const editingTemplateId = ref('')
const savingDevice = ref(false)
const savingTemplate = ref(false)
const devicePage = ref(1)
const templatePage = ref(1)
const pageSize = 10
const deviceFilters = reactive({
  status: 'all',
})

const deviceForm = reactive({
  name: '',
  description: '',
  enabled: true,
})

const templateForm = reactive({
  name: '',
  scene_type: 'PERSON_SAFETY',
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
  { label: '人员安全', value: 'PERSON_SAFETY' },
  { label: '人员风险', value: 'PERSON' },
  { label: '非法捕鱼', value: 'ILLEGAL_FISHING' },
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
const pagedBroadcastTemplates = computed(() => {
  const start = (templatePage.value - 1) * pageSize
  return broadcastTemplates.value.slice(start, start + pageSize)
})

watch(deviceFilters, () => {
  devicePage.value = 1
})

watch(filteredBroadcastDevices, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (devicePage.value > maxPage) devicePage.value = maxPage
})

watch(broadcastTemplates, (items) => {
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
    scene_type: row?.scene_type || 'PERSON_SAFETY',
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

function sceneLabel(value) {
  return sceneOptions.find(item => item.value === value)?.label || value || '-'
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
  gap: 10px;
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
.segmented-filter {
  flex: 0 0 auto;
  display: inline-flex;
  padding: 2px;
  border: 1px solid rgba(84, 148, 193, .22);
  border-radius: 7px;
  background: rgba(7, 24, 39, .72);
}
.segmented-filter :deep(.el-radio-button__inner) {
  min-width: 58px;
  height: 32px;
  padding: 0 11px;
  border: 0;
  border-radius: 5px;
  color: #9db8cc;
  background: transparent;
  font-size: 12px;
  line-height: 32px;
  box-shadow: none;
}
.segmented-filter :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  color: #061827;
  background: #8fd4df;
  box-shadow: none;
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
  background: #0a1d30;
}
.broadcast-list {
  min-width: 1040px;
}
.template-list {
  min-width: 1220px;
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
  grid-template-columns: minmax(220px, 1.1fr) minmax(420px, 1.8fr) 150px 160px;
}
.template-list-header-row,
.template-row {
  grid-template-columns: minmax(190px, 1fr) minmax(150px, .8fr) 120px minmax(380px, 1.7fr) 120px 160px;
}
.col-device,
.col-device-desc,
.col-template-name,
.col-template-content,
.broadcast-name,
.broadcast-description,
.template-name-cell {
  min-width: 0;
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
  font-size: 13px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.col-device-status,
.col-device-actions,
.col-template-scene,
.col-template-risk,
.col-template-enabled,
.col-template-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.list-actions {
  gap: 10px;
}
.list-actions :deep(.el-button) {
  width: auto;
  height: 34px;
  min-height: 34px;
  margin: 0;
  padding: 0 12px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.list-actions :deep(.edit-action) {
  border-color: rgba(70, 145, 190, .42);
  color: #cae6fa;
  background: rgba(20, 58, 88, .78);
}
.list-actions :deep(.delete-action) {
  border-color: rgba(220, 92, 111, .42);
  color: #ff9aa9;
  background: rgba(122, 30, 48, .34);
}
.list-pagination {
  min-height: 72px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, .10);
  background: #092034;
}
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 44px;
  height: 44px;
  margin: 0 4px;
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
.scene-cell small {
  overflow: hidden;
  color: #829bb3;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scene-cell span {
  color: #d7e8f8;
  font-size: 13px;
}
.inline-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #9fb9c9;
  font-size: 13px;
}
.inline-state i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.inline-state.is-online {
  color: #77d9b1;
}
.inline-state.is-offline {
  color: #b7c1c9;
}
.inline-state.is-offline i {
  background: transparent;
  box-shadow: inset 0 0 0 1.5px currentColor;
}
.enabled-text {
  color: #d7e8f8;
  font-size: 13px;
}
.enabled-text.muted {
  color: #8399aa;
}
.risk-pill {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 4px;
  color: #cfe1ef;
  font-size: 12px;
  background: rgba(117, 142, 158, .16);
}
.risk-pill.risk-low {
  color: #8fd7b6;
  background: rgba(80, 184, 135, .12);
}
.risk-pill.risk-medium {
  color: #e8c681;
  background: rgba(196, 151, 67, .13);
}
.risk-pill.risk-high {
  color: #eda1a6;
  background: rgba(202, 85, 95, .13);
}
.content-preview {
  max-width: 100%;
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #cfdfeb;
  font-size: 13px;
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
  margin: 0;
  padding: 20px 24px 12px;
}
:global(.broadcast-config-dialog .el-dialog__title) {
  color: #eef7ff;
  font-size: 22px;
  font-weight: 800;
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
.dialog-radio-group {
  width: 100%;
}
.broadcast-config-dialog :deep(.el-form-item__label) {
  margin-bottom: 8px;
  color: #d3e3f0;
  font-size: 15px;
  font-weight: 700;
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
}
</style>
