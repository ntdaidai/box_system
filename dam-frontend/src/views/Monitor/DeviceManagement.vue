<template>
  <div class="device-admin">
    <header class="admin-header">
      <div>
        <p class="eyebrow">视频监测 / 设备管理</p>
        <h2>摄像头设备管理</h2>
      </div>
      <div class="admin-actions">
        <button type="button" class="primary-action" @click="openCreate()">
          <el-icon><Plus /></el-icon>
          添加设备
        </button>
        <button type="button" class="ghost-action" :class="{ loading }" @click="fetchSources">
          <el-icon><Refresh /></el-icon>
          刷新
        </button>
      </div>
    </header>

    <section class="source-panel">
      <div class="source-table" v-loading="loading">
        <div class="table-head">
          <span>设备名称</span>
          <span>数据路径 / 接口地址</span>
          <span>设备ID</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <div v-if="cameraSources.length === 0" class="empty-state">
          暂无摄像头设备数据源，点击“添加设备”接入。
        </div>
        <div v-for="source in cameraSources" :key="source.id" class="table-row">
          <div class="source-name">
            <strong>{{ source.source_name }}</strong>
            <small>{{ source.description || '--' }}</small>
          </div>
          <span class="path-cell">{{ source.data_path || '--' }}</span>
          <span>{{ source.device_id || '--' }}</span>
          <span class="status-pill" :class="source.is_activate ? 'online' : 'offline'">
            {{ source.is_activate ? '启用' : '停用' }}
          </span>
          <span class="row-actions">
            <button type="button" @click="openEdit(source)">
              <el-icon><Edit /></el-icon>
            </button>
            <button type="button" class="danger" @click="removeSource(source)">
              <el-icon><Delete /></el-icon>
            </button>
          </span>
        </div>
      </div>
    </section>

    <el-drawer v-model="drawerVisible" :title="editingSource ? '编辑摄像头设备' : '添加摄像头设备'" size="420px" class="source-drawer">
      <el-form label-position="top" class="source-form">
        <el-form-item label="设备名称">
          <el-input v-model.trim="form.source_name" placeholder="例如：坝顶 RTSP 摄像头" />
        </el-form-item>
        <el-form-item label="设备ID">
          <el-input-number v-model="form.device_id" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="数据路径或接口地址">
          <el-input v-model.trim="form.data_path" placeholder="rtsp://... 或 /dev/video0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model.trim="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.is_activate">启用该数据源</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <button type="button" class="ghost-action" @click="drawerVisible = false">取消</button>
        <button type="button" class="primary-action" :disabled="saving" @click="saveSource">
          <el-icon><Check /></el-icon>
          保存
        </button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { createDataSource, deleteDataSource, getDataSources, updateDataSource } from '@/api/eca'

const CAMERA_SOURCE_TYPE = 'camera'

const sources = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const editingSource = ref(null)

const form = reactive({
  source_name: '',
  source_type: CAMERA_SOURCE_TYPE,
  device_id: null,
  data_path: '',
  description: '',
  is_activate: true,
})

const cameraSources = computed(() => sources.value.filter(source => source.source_type === CAMERA_SOURCE_TYPE))

const resetForm = () => {
  form.source_name = ''
  form.source_type = CAMERA_SOURCE_TYPE
  form.device_id = null
  form.data_path = ''
  form.description = ''
  form.is_activate = true
}

const openCreate = () => {
  editingSource.value = null
  resetForm()
  drawerVisible.value = true
}

const openEdit = (source) => {
  editingSource.value = source
  form.source_name = source.source_name || ''
  form.source_type = CAMERA_SOURCE_TYPE
  form.device_id = source.device_id || null
  form.data_path = source.data_path || ''
  form.description = source.description || ''
  form.is_activate = Boolean(source.is_activate)
  drawerVisible.value = true
}

const fetchSources = async () => {
  loading.value = true
  try {
    const res = await getDataSources()
    if (res.code === 200) sources.value = res.data || []
  } catch (error) {
    ElMessage.error('摄像头设备列表加载失败')
  } finally {
    loading.value = false
  }
}

const saveSource = async () => {
  if (!form.source_name) {
    ElMessage.warning('请填写设备名称')
    return
  }
  saving.value = true
  const payload = {
    source_name: form.source_name,
    source_type: CAMERA_SOURCE_TYPE,
    device_id: form.device_id,
    data_path: form.data_path,
    description: form.description,
    is_activate: form.is_activate,
  }
  try {
    if (editingSource.value) {
      await updateDataSource(editingSource.value.id, payload)
      ElMessage.success('摄像头设备已更新')
    } else {
      await createDataSource(payload)
      ElMessage.success('摄像头设备已添加')
    }
    drawerVisible.value = false
    await fetchSources()
  } catch (error) {
    ElMessage.error('保存失败，请检查后端服务')
  } finally {
    saving.value = false
  }
}

const removeSource = async (source) => {
  try {
    await ElMessageBox.confirm(`确认删除“${source.source_name}”？`, '删除摄像头设备', { type: 'warning' })
    await deleteDataSource(source.id)
    ElMessage.success('摄像头设备已删除')
    await fetchSources()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败，可能已有规则引用该数据源')
  }
}

onMounted(fetchSources)
</script>

<style scoped>
.device-admin {
  min-height: 100%;
  padding: 22px;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 12% 4%, rgba(40, 159, 209, 0.16), transparent 32%),
    linear-gradient(180deg, rgba(7, 18, 35, 0.96), rgba(4, 10, 20, 0.98));
}

.admin-header,
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.admin-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #7fbbe8;
  font-size: 13px;
}

.admin-header h2,
.panel-toolbar h3 {
  margin: 0;
  color: #f4f8ff;
}

.admin-header h2 {
  font-size: 28px;
}

.source-panel {
  min-height: 620px;
  margin-top: 22px;
  padding: 16px 22px;
  overflow: hidden;
  border: 1px solid rgba(83, 151, 210, 0.24);
  border-radius: 8px;
  background: rgba(11, 29, 52, 0.74);
  box-shadow: 0 18px 36px rgba(0, 8, 22, 0.22);
}

.panel-toolbar span,
.source-name small {
  margin-top: 5px;
  color: #8ea8c9;
  font-size: 12px;
}

.primary-action,
.ghost-action {
  height: 36px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: 8px;
  font: inherit;
  cursor: pointer;
}

.primary-action {
  border: 0;
  color: #061425;
  background: linear-gradient(135deg, #31d9ff, #6effbd);
  font-weight: 800;
}

.primary-action:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.ghost-action {
  border: 1px solid rgba(120, 155, 211, 0.24);
  color: #cfe3fa;
  background: rgba(32, 57, 92, 0.58);
}

.ghost-action.loading .el-icon {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.source-table {
  margin-top: 16px;
  min-height: 420px;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 1.2fr 1.6fr 0.5fr 0.5fr 0.5fr;
  align-items: center;
  gap: 14px;
}

.table-head {
  min-height: 38px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(143, 181, 225, 0.14);
  color: #8ea8c9;
  font-size: 12px;
  font-weight: 700;
}

.table-row {
  min-height: 72px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(143, 181, 225, 0.1);
}

.source-name strong {
  display: block;
  color: #f4f8ff;
}

.path-cell {
  overflow: hidden;
  color: #bcd1ec;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  width: fit-content;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.status-pill.online {
  color: #8df27c;
  background: rgba(103, 194, 58, 0.14);
}

.status-pill.offline {
  color: #ff8f8f;
  background: rgba(245, 108, 108, 0.14);
}

.row-actions {
  display: inline-flex;
  gap: 8px;
}

.row-actions button {
  width: 30px;
  height: 30px;
  border: 1px solid rgba(120, 155, 211, 0.22);
  border-radius: 7px;
  background: rgba(32, 57, 92, 0.58);
  color: #cfe3fa;
  cursor: pointer;
}

.row-actions button.danger {
  color: #ff8f8f;
}

.empty-state {
  padding: 64px 20px;
  text-align: center;
  color: #8ea8c9;
}

.source-form :deep(.el-input-number) {
  width: 100%;
}

:global(.source-drawer.el-drawer) {
  color: #dce9fa;
  background:
    radial-gradient(circle at 100% 0%, rgba(49, 217, 255, 0.11), transparent 30%),
    linear-gradient(180deg, #0d2137 0%, #081827 100%);
  border-left: 1px solid rgba(49, 217, 255, 0.28);
}

:global(.source-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 22px 24px 14px;
  color: #f4f8ff;
  border-bottom: 1px solid rgba(143, 181, 225, 0.14);
}

:global(.source-drawer .el-drawer__body) {
  padding: 22px 24px;
}

:global(.source-drawer .el-drawer__footer) {
  padding: 14px 24px 22px;
  border-top: 1px solid rgba(143, 181, 225, 0.12);
}

:global(.source-drawer .el-form-item__label) {
  color: #a8bddb;
}

:global(.source-drawer .el-input__wrapper),
:global(.source-drawer .el-textarea__inner),
:global(.source-drawer .el-input-number .el-input__wrapper) {
  color: #f4f8ff;
  background: rgba(6, 22, 38, 0.76);
  box-shadow: 0 0 0 1px rgba(120, 155, 211, 0.24) inset;
}

:global(.source-drawer .el-input__inner),
:global(.source-drawer .el-textarea__inner) {
  color: #f4f8ff;
}

:global(.source-drawer .el-checkbox__label) {
  color: #bcd1ec;
}

@media (max-width: 980px) {
  .table-head,
  .table-row {
    grid-template-columns: 1.2fr 1fr 0.45fr 0.45fr 0.5fr;
  }
}
</style>
