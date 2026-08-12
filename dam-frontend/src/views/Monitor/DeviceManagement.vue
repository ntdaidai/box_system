<template>
  <div class="device-admin">
    <header class="admin-header">
      <div class="title-block">
        <h2>数据源管理</h2>
        <p>统一维护系统数据源设备和运行状态</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadCurrent">刷新</el-button>
    </header>

    <section class="data-panel camera-toolbar-card">
      <div class="panel-head">
        <div>
          <h3>摄像头列表</h3>
        </div>
        <div class="panel-toolbar">
          <el-button type="primary" :icon="Plus" @click="openCreate()">
            {{ createButtonText }}
          </el-button>
          <el-radio-group v-model="statusFilter" class="status-filter">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="online">在线</el-radio-button>
            <el-radio-button label="offline">离线</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </section>

    <section class="data-panel camera-list-card" v-loading="loading">
      <div class="camera-list" :class="{ 'is-empty': !filteredCameras.length }">
        <div v-if="filteredCameras.length" class="camera-list-header-row">
          <div class="col-name">设备名称</div>
          <div class="col-description">描述</div>
          <div class="col-connection">连接信息</div>
          <div class="col-console">控制台</div>
          <div class="col-status">状态</div>
          <div class="col-enabled">启用</div>
          <div class="col-actions">操作</div>
        </div>
        <article v-for="row in pagedCameras" :key="row.id" class="camera-row" :class="row.connected ? 'is-online' : 'is-offline'">
          <div class="col-name">
            <strong>{{ row.name }}</strong>
          </div>
          <div class="col-description">
            <span>{{ row.description || '--' }}</span>
          </div>
          <div class="col-connection connection-cell">
            <div v-if="connectionVisible[row.id]" class="connection-chips">
              <span><b>IP</b>{{ row.ip_address || '--' }}</span>
              <span><b>账号</b>{{ row.username || '--' }}</span>
              <span><b>密码</b>{{ connectionPassword(row) }}</span>
            </div>
            <div v-else class="connection-masked">
              <span>已隐藏</span>
              <small>IP / 账号 / 密码</small>
            </div>
            <el-button
              class="connection-eye"
              :icon="connectionVisible[row.id] ? Hide : View"
              :loading="passwordLoading[row.id]"
              title="显示/隐藏连接信息"
              @click="toggleConnection(row)"
            />
          </div>
          <div class="col-console">
            <el-link v-if="row.web_console_url" :href="row.web_console_url" target="_blank" type="primary">打开控制台</el-link>
            <span v-else>--</span>
          </div>
          <div class="col-status">
            <span class="status-pill" :class="row.connected ? 'is-online' : 'is-offline'">
              {{ row.connected ? '在线' : '离线' }}
            </span>
            <small v-if="!row.connected && row.last_online_at">最后在线：{{ formatDateTime(row.last_online_at) }}</small>
          </div>
          <div class="col-enabled">
            <el-switch
              :model-value="row.enabled !== false"
              :loading="enabledLoading[row.id]"
              @change="(value) => toggleCameraEnabled(row, value)"
            />
          </div>
          <div class="col-actions action-buttons">
            <el-button class="edit-action" @click="openCameraEdit(row)">编辑</el-button>
            <el-button class="delete-action" @click="removeCamera(row)">删除</el-button>
          </div>
        </article>
        <div v-if="!filteredCameras.length" class="empty-list">
          <strong>暂无匹配设备</strong>
          <span>调整状态筛选后再试</span>
        </div>
      </div>
      <el-pagination
        v-if="filteredCameras.length"
        v-model:current-page="cameraPage"
        class="list-pagination"
        :page-size="pageSize"
        :total="filteredCameras.length"
        layout="prev, pager, next"
      />
    </section>

    <el-dialog v-model="cameraDialog" :title="editingCamera ? '编辑摄像头' : '添加摄像头'" width="680px" class="camera-config-dialog" destroy-on-close>
      <el-form label-position="top">
        <div class="form-grid two">
          <el-form-item label="名称">
            <el-input v-model.trim="cameraForm.camera_name" maxlength="128" />
          </el-form-item>
          <el-form-item label="IP 地址">
            <el-input v-model.trim="cameraForm.ip_address" />
          </el-form-item>
        </div>
        <div class="form-grid two">
          <el-form-item label="登录账号">
            <el-input v-model.trim="cameraForm.username" autocomplete="off" />
          </el-form-item>
          <el-form-item label="登录密码">
            <el-input v-model="cameraForm.password" type="password" show-password autocomplete="new-password" :placeholder="editingCamera ? '留空则保留原密码' : ''" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model.trim="cameraForm.description" type="textarea" :rows="2" maxlength="1000" />
        </el-form-item>
        <el-collapse class="advanced-collapse">
          <el-collapse-item title="高级设置（选填）" name="advanced">
            <el-form-item label="安装地址">
              <el-input v-model.trim="cameraForm.install_address" />
            </el-form-item>
            <div class="form-grid two">
              <el-form-item label="纬度">
                <el-input-number v-model="cameraForm.latitude" :controls="false" :min="-90" :max="90" :precision="6" />
              </el-form-item>
              <el-form-item label="经度">
                <el-input-number v-model="cameraForm.longitude" :controls="false" :min="-180" :max="180" :precision="6" />
              </el-form-item>
            </div>
            <div class="form-grid two">
              <el-form-item label="RTSP 端口">
                <el-input-number v-model="cameraForm.rtsp_port" :min="1" :max="65535" />
              </el-form-item>
              <el-form-item label="Web 端口">
                <el-input-number v-model="cameraForm.web_port" :min="1" :max="65535" />
              </el-form-item>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="cameraDialog = false">取消</el-button>
        <el-button :icon="Connection" :loading="testing" @click="testConnection">测试连接</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" :disabled="!connectionVerified" @click="saveCamera">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Connection, Hide, Plus, Refresh, View } from '@element-plus/icons-vue'
import { createCameraDevice, deleteCameraDevice, getCameraDevicePassword, getCameraDevices, testCameraDeviceConnection, updateCameraDevice } from '@/api/camera'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const cameras = ref([])
const cameraDialog = ref(false)
const editingCamera = ref(null)
const verifiedKey = ref('')
const statusFilter = ref('all')
const cameraPage = ref(1)
const pageSize = 10
const connectionVisible = ref({})
const passwordLoading = ref({})
const passwordValues = ref({})
const enabledLoading = ref({})

const cameraForm = reactive({
  camera_name: '',
  ip_address: '',
  username: '',
  password: '',
  description: '',
  install_address: '',
  latitude: undefined,
  longitude: undefined,
  rtsp_port: 554,
  web_port: 80,
  enabled: true,
})
const createButtonText = computed(() => '添加摄像头')
const connectionKey = computed(() => JSON.stringify([cameraForm.ip_address, cameraForm.rtsp_port, cameraForm.username, cameraForm.password]))
const connectionVerified = computed(() => !needsTest.value || verifiedKey.value === connectionKey.value)
const needsTest = computed(() => !editingCamera.value || connectionKey.value !== editingCamera.value.connectionKey)
const filteredCameras = computed(() => {
  return cameras.value.filter((camera) => {
    const status = camera.connected ? 'online' : 'offline'
    return statusFilter.value === 'all' || statusFilter.value === status
  })
})
const pagedCameras = computed(() => {
  const start = (cameraPage.value - 1) * pageSize
  return filteredCameras.value.slice(start, start + pageSize)
})

watch(statusFilter, () => {
  cameraPage.value = 1
})

watch(filteredCameras, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (cameraPage.value > maxPage) cameraPage.value = maxPage
})

async function loadCameras() {
  const res = await getCameraDevices()
  cameras.value = res.data?.cameras || []
}

async function loadCurrent() {
  loading.value = true
  try {
    await loadCameras()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '数据加载失败')
  } finally {
    loading.value = false
  }
}

function resetCameraForm() {
  Object.assign(cameraForm, {
    camera_name: '',
    ip_address: '',
    username: '',
    password: '',
    description: '',
    install_address: '',
    latitude: undefined,
    longitude: undefined,
    rtsp_port: 554,
    web_port: 80,
    enabled: true,
  })
  verifiedKey.value = ''
}

function openCreate() {
  editingCamera.value = null
  resetCameraForm()
  cameraDialog.value = true
}

function openCameraEdit(row) {
  editingCamera.value = {
    ...row,
    connectionKey: JSON.stringify([row.ip_address, Number(row.rtsp_port) || 554, row.username || '', '']),
  }
  Object.assign(cameraForm, {
    camera_name: row.name,
    ip_address: row.ip_address,
    username: row.username || '',
    password: '',
    description: row.description || '',
    install_address: row.install_address || '',
    latitude: row.latitude ?? undefined,
    longitude: row.longitude ?? undefined,
    rtsp_port: Number(row.rtsp_port) || 554,
    web_port: Number(row.web_port) || 80,
    enabled: Boolean(row.enabled),
  })
  verifiedKey.value = ''
  cameraDialog.value = true
}

async function testConnection() {
  if (!cameraForm.ip_address || !cameraForm.username || (!editingCamera.value && !cameraForm.password)) {
    return ElMessage.warning('请完整填写 IP、账号和密码')
  }
  testing.value = true
  try {
    const res = await testCameraDeviceConnection({
      camera_id: editingCamera.value ? String(editingCamera.value.id) : undefined,
      ip_address: cameraForm.ip_address,
      rtsp_port: cameraForm.rtsp_port,
      username: cameraForm.username,
      password: cameraForm.password,
    })
    if (res.data?.connected) {
      verifiedKey.value = connectionKey.value
      ElMessage.success(`连接成功，已识别为${res.data.brand === 'hikvision' ? '海康' : '大华'}设备`)
    } else {
      ElMessage.error(res.data?.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '连接失败')
  } finally {
    testing.value = false
  }
}

async function saveCamera() {
  if (!cameraForm.camera_name || !cameraForm.ip_address || !cameraForm.username) return ElMessage.warning('请填写名称、IP 和账号')
  if (!connectionVerified.value) return ElMessage.warning('请先测试连接')
  saving.value = true
  try {
    const payload = { ...cameraForm }
    if (editingCamera.value && !payload.password) delete payload.password
    if (editingCamera.value) await updateCameraDevice(String(editingCamera.value.id), payload)
    else await createCameraDevice(payload)
    cameraDialog.value = false
    ElMessage.success('摄像头已保存')
    await loadCurrent()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeCamera(row) {
  try {
    await ElMessageBox.confirm(`确认删除“${row.name}”？`, '删除摄像头', { type: 'warning' })
    await deleteCameraDevice(String(row.id))
    ElMessage.success('摄像头已删除')
    await loadCurrent()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function toggleCameraEnabled(row, enabled) {
  const previous = row.enabled !== false
  enabledLoading.value = { ...enabledLoading.value, [row.id]: true }
  row.enabled = enabled
  try {
    await updateCameraDevice(String(row.id), { enabled })
    ElMessage.success(enabled ? '设备已启用' : '设备已停用')
    await loadCurrent()
  } catch (error) {
    row.enabled = previous
    ElMessage.error(error.response?.data?.detail || '状态更新失败')
  } finally {
    enabledLoading.value = { ...enabledLoading.value, [row.id]: false }
  }
}

function connectionPassword(row) {
  if (!row.has_password) return '--'
  return passwordValues.value[row.id] || '********'
}

async function toggleConnection(row) {
  const id = row.id
  if (connectionVisible.value[id]) {
    connectionVisible.value = { ...connectionVisible.value, [id]: false }
    return
  }
  if (row.has_password && !passwordValues.value[id]) {
    passwordLoading.value = { ...passwordLoading.value, [id]: true }
    try {
      const res = await getCameraDevicePassword(String(id))
      passwordValues.value = { ...passwordValues.value, [id]: res.data?.password || '' }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '密码读取失败')
    } finally {
      passwordLoading.value = { ...passwordLoading.value, [id]: false }
    }
  }
  connectionVisible.value = { ...connectionVisible.value, [id]: true }
}

function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(loadCurrent)
</script>

<style scoped>
.device-admin {
  min-height: 100%;
  padding: 18px 22px 22px;
  color: #d9e8f8;
  background: #071422;
}
.admin-header,
.panel-head,
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.admin-header {
  min-height: 74px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}
.admin-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}
.title-block {
  min-width: 0;
  display: grid;
  gap: 8px;
}
.title-block p {
  margin: 0;
  color: #8aa9c3;
  font-size: 13px;
  line-height: 1.35;
}
h2,
h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}
h2 {
  font-size: 25px;
  line-height: 1.1;
}
.panel-head {
  margin-bottom: 0;
}
.panel-toolbar {
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: nowrap;
}
.panel-toolbar :deep(.el-button) {
  flex: 0 0 auto;
  min-width: 120px;
  height: 36px;
  margin-left: 0;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 600;
}
.data-panel {
  margin-top: 16px;
  padding: 18px 22px;
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
}
.camera-toolbar-card {
  min-height: 82px;
  display: flex;
  align-items: center;
}
.camera-toolbar-card .panel-head {
  width: 100%;
}
.camera-list-card {
  padding: 0;
  overflow: hidden;
}
.status-filter {
  flex: 0 0 auto;
  display: inline-flex;
  padding: 2px;
  border: 1px solid rgba(84, 148, 193, .28);
  border-radius: 8px;
  background: #0d2740;
}
.status-filter :deep(.el-radio-button__inner) {
  min-width: 62px;
  height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  color: #a7c0d3;
  background: transparent;
  line-height: 32px;
  box-shadow: none;
}
.status-filter :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  color: #061827;
  background: #8fd4df;
  box-shadow: none;
}
.camera-list {
  min-width: 1240px;
  overflow: hidden;
  border: 0;
  border-radius: 8px 8px 0 0;
  background: #081b2d;
}
.camera-list-header-row,
.camera-row {
  display: grid;
  grid-template-columns: minmax(170px, .95fr) minmax(270px, 1.35fr) minmax(300px, 1.35fr) 140px 106px 96px 148px;
  align-items: center;
  gap: 16px;
}
.camera-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}
.camera-row {
  min-height: 72px;
  padding: 12px 20px;
  border-top: 1px solid rgba(149, 190, 220, .10);
  color: #d7e8f8;
  background: #092034;
  transition: background .18s ease;
}
.camera-row:hover {
  background: #102940;
}
.col-name,
.col-description,
.col-connection,
.col-status {
  min-width: 0;
  display: grid;
  gap: 6px;
  justify-items: center;
  text-align: center;
}
.col-name strong {
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-description span {
  display: -webkit-box;
  overflow: hidden;
  color: #a9c0d2;
  font-size: 13px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.col-name small,
.col-status small {
  overflow: hidden;
  color: #8fa8bf;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.connection-cell {
  grid-template-columns: auto 34px;
  align-items: center;
  justify-content: center;
}
.connection-chips {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}
.connection-chips span {
  min-width: 0;
  max-width: 120px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  overflow: hidden;
  border: 1px solid rgba(74, 153, 191, .20);
  border-radius: 5px;
  color: #d7e8f8;
  background: rgba(7, 31, 49, .72);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.connection-chips b {
  flex: 0 0 auto;
  color: #7fa4bc;
  font-weight: 700;
}
.connection-masked {
  width: fit-content;
  max-width: 100%;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 9px;
  overflow: hidden;
  border: 1px solid rgba(87, 145, 181, .22);
  border-radius: 5px;
  color: #c3d5e3;
  background: rgba(9, 34, 55, .62);
  font-size: 13px;
}
.connection-masked span {
  flex: 0 0 auto;
  color: #d8e7f1;
  font-weight: 700;
}
.connection-masked small {
  min-width: 0;
  overflow: hidden;
  color: #819daf;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.connection-eye {
  width: 32px;
  height: 32px;
  padding: 0;
  border-color: rgba(52, 142, 182, .42);
  color: #cde8f8;
  background: #103954;
}
.col-console,
.col-status,
.col-enabled {
  justify-items: center;
  color: #8fa8bf;
  font-size: 13px;
  text-align: center;
}
.col-actions,
.action-buttons {
  justify-content: center;
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
.col-enabled :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, .34);
  background: rgba(96, 118, 134, .38);
}
.col-enabled :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(83, 193, 151, .52);
  background: rgba(48, 154, 118, .72);
}
.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}
.action-buttons :deep(.el-button) {
  width: auto;
  height: 32px;
  margin: 0;
  padding: 0 13px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.action-buttons :deep(.edit-action) {
  border-color: rgba(66, 164, 224, .50);
  color: #d5f0ff;
  background: rgba(29, 91, 133, .70);
}
.action-buttons :deep(.delete-action) {
  border-color: rgba(226, 88, 109, .46);
  color: #ffb1bd;
  background: rgba(128, 36, 54, .48);
}
.list-pagination {
  min-height: 58px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, .10);
  background: #092034;
}
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 44px;
  height: 38px;
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
.form-grid {
  display: grid;
  gap: 14px;
}
.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.advanced-collapse {
  margin-bottom: 12px;
  border: 1px solid rgba(70, 145, 190, .35);
  border-radius: 6px;
  overflow: hidden;
  background: #102f4d;
}
.advanced-collapse :deep(.el-collapse) {
  border: 0;
}
.advanced-collapse :deep(.el-collapse-item__header) {
  height: 46px;
  padding: 0 14px;
  border-bottom-color: rgba(70, 145, 190, .35);
  color: #e4f1fb;
  background: #123858;
  font-weight: 700;
}
.advanced-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
  background: #102f4d;
}
.advanced-collapse :deep(.el-collapse-item__content) {
  padding: 16px 14px 18px;
  color: #d7e8f8;
}
.advanced-collapse :deep(.el-input-number) {
  width: 100%;
}
.advanced-collapse :deep(.el-input-number__decrease),
.advanced-collapse :deep(.el-input-number__increase) {
  border-color: rgba(70, 145, 190, .45);
  color: #d7e8f8;
  background: #173a59;
}
:global(.camera-config-dialog.el-dialog) {
  border: 1px solid rgba(97, 167, 214, .40);
  border-radius: 10px;
  background: #1d426a;
}
:global(.camera-config-dialog .el-dialog__header) {
  margin: 0;
  padding: 20px 24px 12px;
}
:global(.camera-config-dialog .el-dialog__title) {
  color: #eef7ff;
  font-size: 22px;
  font-weight: 800;
}
:global(.camera-config-dialog .el-dialog__close) {
  color: #c8d9e7;
}
:global(.camera-config-dialog .el-form-item__label) {
  margin-bottom: 8px;
  color: #d3e3f0;
  font-size: 15px;
  font-weight: 700;
}
:global(.camera-config-dialog .el-input__wrapper),
:global(.camera-config-dialog .el-textarea__inner) {
  background: #092034;
  box-shadow: inset 0 0 0 1px rgba(36, 128, 176, .46);
  color: #f4fbff;
}
:global(.camera-config-dialog .el-input__inner),
:global(.camera-config-dialog .el-textarea__inner),
:global(.camera-config-dialog .el-input-number .el-input__inner) {
  color: #f4fbff;
}
:global(.camera-config-dialog .el-input__inner::placeholder) {
  color: #a5b8c7;
}
:global(.camera-config-dialog .el-checkbox__label) {
  color: #d8e8f4;
}
@media (max-width: 1100px) {
  .data-panel {
    overflow-x: auto;
  }
}
@media (max-width: 900px) {
  .admin-header {
    padding: 14px;
  }
  .panel-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .panel-toolbar {
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }
  .title-block {
    width: 100%;
  }
  .form-grid.two {
    grid-template-columns: 1fr;
  }
  .device-admin {
    padding: 12px;
  }
  .camera-toolbar-card {
    min-height: 108px;
  }
}
</style>
