<template>
  <div class="device-admin">
    <header class="admin-header">
      <div>
        <p class="eyebrow">实时监控 / 设备接入</p>
        <h2>智能感知设备管理</h2>
      </div>
      <button type="button" class="primary-action" @click="openCreate()">
        <el-icon><Plus /></el-icon>
        添加设备
      </button>
    </header>

    <section class="admin-layout">
      <aside class="type-panel">
        <button
          v-for="type in sourceTypes"
          :key="type.value"
          type="button"
          class="type-card"
          :class="{ active: selectedType === type.value }"
          @click="selectType(type.value)"
        >
          <span class="type-icon">
            <el-icon><component :is="type.icon" /></el-icon>
          </span>
          <span>
            <strong>{{ type.label }}</strong>
            <small>{{ type.description }}</small>
          </span>
          <em>{{ typeCount(type.value) }}</em>
        </button>
      </aside>

      <main class="source-panel">
        <div class="panel-toolbar">
          <div>
            <h3>{{ activeType.label }}</h3>
            <span>{{ activeType.hint }}</span>
          </div>
          <button type="button" class="ghost-action" @click="fetchSources">
            <el-icon><Refresh /></el-icon>
            刷新
          </button>
        </div>

        <div class="source-table" v-loading="loading">
          <div class="table-head">
            <span>设备名称</span>
            <span>数据路径 / 接口地址</span>
            <span>设备ID</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          <div v-if="filteredSources.length === 0" class="empty-state">
            暂无{{ activeType.label }}数据源，点击“添加设备”接入。
          </div>
          <div v-for="source in filteredSources" :key="source.id" class="table-row">
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
      </main>
    </section>

    <el-drawer v-model="drawerVisible" :title="editingSource ? '编辑设备' : '添加设备'" size="420px">
      <el-form label-position="top" class="source-form">
        <el-form-item label="设备类型">
          <el-select v-model="form.source_type">
            <el-option
              v-for="type in sourceTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model.trim="form.source_name" placeholder="例如：坝顶风速风向传感器" />
        </el-form-item>
        <el-form-item label="设备ID">
          <el-input-number v-model="form.device_id" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="数据路径或接口地址">
          <el-input v-model.trim="form.data_path" placeholder="/api/v1/sensor/realtime/wind 或 rtsp://..." />
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
import { Check, Cpu, Delete, Edit, Link, Plus, Refresh, VideoCamera } from '@element-plus/icons-vue'
import { createDataSource, deleteDataSource, getDataSources, updateDataSource } from '@/api/eca'

const sourceTypes = [
  { value: 'sensor', label: '传感器设备', icon: Cpu, description: '温湿度、雨量、风速、振动等', hint: '管理采集类传感器的数据源接入。' },
  { value: 'camera', label: '摄像头设备', icon: VideoCamera, description: 'RTSP、USB/UVC、AI 检测流', hint: '管理视频监控与视觉识别数据源。' },
  { value: 'beidou', label: '北斗通信', icon: Link, description: '定位、短报文、通信链路', hint: '管理北斗通信与定位链路。' },
  { value: 'api', label: '外部 API', icon: Link, description: '第三方接口或文件数据', hint: '管理其他接口型数据源。' },
]

const sources = ref([])
const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const editingSource = ref(null)
const selectedType = ref('sensor')

const form = reactive({
  source_name: '',
  source_type: 'sensor',
  device_id: null,
  data_path: '',
  description: '',
  is_activate: true,
})

const activeType = computed(() => sourceTypes.find(type => type.value === selectedType.value) || sourceTypes[0])
const filteredSources = computed(() => sources.value.filter(source => source.source_type === selectedType.value))

const typeCount = type => sources.value.filter(source => source.source_type === type).length

const selectType = (type) => {
  selectedType.value = type
}

const resetForm = (type = selectedType.value) => {
  form.source_name = ''
  form.source_type = type
  form.device_id = null
  form.data_path = ''
  form.description = ''
  form.is_activate = true
}

const openCreate = (type = selectedType.value) => {
  editingSource.value = null
  resetForm(type)
  drawerVisible.value = true
}

const openEdit = (source) => {
  editingSource.value = source
  form.source_name = source.source_name || ''
  form.source_type = source.source_type || selectedType.value
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
    ElMessage.error('数据源列表加载失败')
  } finally {
    loading.value = false
  }
}

const saveSource = async () => {
  if (!form.source_name || !form.source_type) {
    ElMessage.warning('请填写设备名称和设备类型')
    return
  }
  saving.value = true
  const payload = {
    source_name: form.source_name,
    source_type: form.source_type,
    device_id: form.device_id,
    data_path: form.data_path,
    description: form.description,
    is_activate: form.is_activate,
  }
  try {
    if (editingSource.value) {
      await updateDataSource(editingSource.value.id, payload)
      ElMessage.success('设备已更新')
    } else {
      await createDataSource(payload)
      ElMessage.success('设备已添加')
    }
    selectedType.value = form.source_type
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
    await ElMessageBox.confirm(`确认删除“${source.source_name}”？`, '删除数据源', { type: 'warning' })
    await deleteDataSource(source.id)
    ElMessage.success('数据源已删除')
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

.admin-layout {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.type-panel,
.source-panel {
  border: 1px solid rgba(83, 151, 210, 0.24);
  border-radius: 8px;
  background: rgba(11, 29, 52, 0.74);
  box-shadow: 0 18px 36px rgba(0, 8, 22, 0.22);
}

.type-panel {
  padding: 12px;
}

.type-card {
  width: 100%;
  min-height: 82px;
  margin-bottom: 10px;
  padding: 14px;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 34px;
  align-items: center;
  gap: 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: rgba(17, 42, 73, 0.72);
  color: #dce9fa;
  text-align: left;
  cursor: pointer;
}

.type-card.active,
.type-card:hover {
  border-color: rgba(57, 168, 255, 0.64);
  background: rgba(18, 63, 102, 0.78);
}

.type-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(49, 156, 255, 0.32), rgba(49, 221, 186, 0.18));
  color: #66d8ff;
  font-size: 20px;
}

.type-card strong,
.type-card small {
  display: block;
}

.type-card small,
.panel-toolbar span,
.source-name small {
  margin-top: 5px;
  color: #8ea8c9;
  font-size: 12px;
}

.type-card em {
  font-style: normal;
  color: #8ee7ff;
  font: 800 20px/1 "Consolas", "Monaco", monospace;
}

.source-panel {
  padding: 16px;
  overflow: hidden;
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

.source-form :deep(.el-input-number),
.source-form :deep(.el-select) {
  width: 100%;
}

@media (max-width: 980px) {
  .admin-layout {
    grid-template-columns: 1fr;
  }

  .table-head,
  .table-row {
    grid-template-columns: 1.2fr 1fr 0.45fr 0.45fr 0.5fr;
  }
}
</style>
