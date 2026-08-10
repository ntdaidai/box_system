<template>
  <div class="device-admin">
    <header class="admin-header">
      <div class="title-block">
        <h2>数据源管理</h2>
        <p>统一维护摄像头接入、控制台入口和点位信息</p>
      </div>
    </header>

    <section class="data-panel camera-data-panel" v-loading="loading">
      <div class="panel-head">
        <div>
          <h3>摄像头接入</h3>
          <p>维护视频源、控制台入口和在线状态</p>
        </div>
        <div class="panel-toolbar">
          <el-button type="primary" :icon="Plus" @click="openCreate">
            {{ createButtonText }}
          </el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadCurrent">刷新</el-button>
        </div>
      </div>
      <el-table :data="cameras" row-key="id" empty-text="暂无摄像头设备" class="camera-table">
        <el-table-column label="名称" min-width="190">
          <template #default="{ row }">
            <div class="name-cell"><strong>{{ row.name }}</strong><small>{{ row.description || '暂无描述' }}</small></div>
          </template>
        </el-table-column>
        <el-table-column label="连接信息" min-width="240">
          <template #default="{ row }">
            <div class="connection-cell">
              <span>IP：{{ row.ip_address }}</span>
              <span>账户：{{ row.username || '--' }}</span>
              <span class="password-line">
                密码：{{ passwordLabel(row) }}
                <el-button
                  v-if="row.has_password"
                  link
                  type="primary"
                  class="password-toggle"
                  :icon="passwordVisible[row.id] ? Hide : View"
                  :loading="passwordLoading[row.id]"
                  title="显示/隐藏密码"
                  @click="togglePassword(row)"
                />
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Web 控制台" min-width="125">
          <template #default="{ row }">
            <el-link v-if="row.web_console_url" :href="row.web_console_url" target="_blank" type="primary">打开控制台</el-link>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="设备状态" min-width="155">
          <template #default="{ row }">
            <div class="status-cell">
              <span class="status-pill" :class="row.connected ? 'is-online' : 'is-offline'">{{ row.connected ? '在线' : '离线' }}</span>
              <small v-if="!row.connected && row.last_online_at">最后在线：{{ formatDateTime(row.last_online_at) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="112" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button :icon="Edit" title="编辑" @click="openCameraEdit(row)" />
              <el-button type="danger" :icon="Delete" title="删除" @click="removeCamera(row)" />
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="map-panel">
      <header><h3>摄像头点位地图</h3></header>
      <div class="map-stage">
        <img src="/dammap.png" alt="大坝摄像头点位地图" />
      </div>
    </section>

    <el-dialog v-model="cameraDialog" :title="editingCamera ? '编辑摄像头' : '添加摄像头'" width="680px" class="camera-config-dialog" destroy-on-close>
      <el-form label-position="top">
        <div class="form-grid two"><el-form-item label="名称"><el-input v-model.trim="cameraForm.camera_name" maxlength="128" /></el-form-item><el-form-item label="IP 地址"><el-input v-model.trim="cameraForm.ip_address" /></el-form-item></div>
        <div class="form-grid two"><el-form-item label="登录账号"><el-input v-model.trim="cameraForm.username" autocomplete="off" /></el-form-item><el-form-item label="登录密码"><el-input v-model="cameraForm.password" type="password" show-password autocomplete="new-password" :placeholder="editingCamera ? '留空则保留原密码' : ''" /></el-form-item></div>
        <el-form-item label="描述"><el-input v-model.trim="cameraForm.description" type="textarea" :rows="2" maxlength="1000" /></el-form-item>
        <el-collapse class="advanced-collapse"><el-collapse-item title="高级设置（选填）" name="advanced">
          <el-form-item label="安装地址"><el-input v-model.trim="cameraForm.install_address" /></el-form-item>
          <div class="form-grid two"><el-form-item label="纬度"><el-input-number v-model="cameraForm.latitude" :controls="false" :min="-90" :max="90" :precision="6" /></el-form-item><el-form-item label="经度"><el-input-number v-model="cameraForm.longitude" :controls="false" :min="-180" :max="180" :precision="6" /></el-form-item></div>
          <div class="form-grid two"><el-form-item label="RTSP 端口"><el-input-number v-model="cameraForm.rtsp_port" :min="1" :max="65535" /></el-form-item><el-form-item label="Web 端口"><el-input-number v-model="cameraForm.web_port" :min="1" :max="65535" /></el-form-item></div>
        </el-collapse-item></el-collapse>
        <el-form-item><el-checkbox v-model="cameraForm.enabled">启用设备</el-checkbox></el-form-item>
      </el-form>
      <template #footer><el-button @click="cameraDialog = false">取消</el-button><el-button :icon="Connection" :loading="testing" @click="testConnection">测试连接</el-button><el-button type="primary" :icon="Check" :loading="saving" :disabled="!connectionVerified" @click="saveCamera">保存</el-button></template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Connection, Delete, Edit, Hide, Plus, Refresh, View } from '@element-plus/icons-vue'
import { createCameraDevice, deleteCameraDevice, getCameraDevicePassword, getCameraDevices, testCameraDeviceConnection, updateCameraDevice } from '@/api/camera'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const cameras = ref([])
const cameraDialog = ref(false)
const editingCamera = ref(null)
const verifiedKey = ref('')
const passwordVisible = ref({})
const passwordLoading = ref({})
const passwordValues = ref({})

const cameraForm = reactive({ camera_name: '', ip_address: '', username: '', password: '', description: '', install_address: '', latitude: undefined, longitude: undefined, rtsp_port: 554, web_port: 80, enabled: true })
const createButtonText = computed(() => '添加摄像头')
const connectionKey = computed(() => JSON.stringify([cameraForm.ip_address, cameraForm.rtsp_port, cameraForm.username, cameraForm.password]))
const connectionVerified = computed(() => !needsTest.value || verifiedKey.value === connectionKey.value)
const needsTest = computed(() => !editingCamera.value || connectionKey.value !== editingCamera.value.connectionKey)
async function loadCameras() { const res = await getCameraDevices(); cameras.value = res.data?.cameras || [] }
async function loadCurrent() { loading.value = true; try { await loadCameras() } catch (error) { ElMessage.error(error.response?.data?.detail || '数据加载失败') } finally { loading.value = false } }

function resetCameraForm() { Object.assign(cameraForm, { camera_name: '', ip_address: '', username: '', password: '', description: '', install_address: '', latitude: undefined, longitude: undefined, rtsp_port: 554, web_port: 80, enabled: true }); verifiedKey.value = '' }
function openCreate() { editingCamera.value = null; resetCameraForm(); cameraDialog.value = true }
function openCameraEdit(row) { editingCamera.value = { ...row, connectionKey: JSON.stringify([row.ip_address, Number(row.rtsp_port) || 554, row.username || '', '']) }; Object.assign(cameraForm, { camera_name: row.name, ip_address: row.ip_address, username: row.username || '', password: '', description: row.description || '', install_address: row.install_address || '', latitude: row.latitude ?? undefined, longitude: row.longitude ?? undefined, rtsp_port: Number(row.rtsp_port) || 554, web_port: Number(row.web_port) || 80, enabled: Boolean(row.enabled) }); verifiedKey.value = ''; cameraDialog.value = true }
async function testConnection() { if (!cameraForm.ip_address || !cameraForm.username || (!editingCamera.value && !cameraForm.password)) return ElMessage.warning('请完整填写 IP、账号和密码'); testing.value = true; try { const res = await testCameraDeviceConnection({ camera_id: editingCamera.value ? String(editingCamera.value.id) : undefined, ip_address: cameraForm.ip_address, rtsp_port: cameraForm.rtsp_port, username: cameraForm.username, password: cameraForm.password }); if (res.data?.connected) { verifiedKey.value = connectionKey.value; ElMessage.success(`连接成功，已识别为${res.data.brand === 'hikvision' ? '海康' : '大华'}设备`) } else ElMessage.error(res.data?.message || '连接失败') } catch (error) { ElMessage.error(error.response?.data?.detail || '连接失败') } finally { testing.value = false } }
async function saveCamera() { if (!cameraForm.camera_name || !cameraForm.ip_address || !cameraForm.username) return ElMessage.warning('请填写名称、IP 和账号'); if (!connectionVerified.value) return ElMessage.warning('请先测试连接'); saving.value = true; try { const payload = { ...cameraForm }; if (editingCamera.value && !payload.password) delete payload.password; if (editingCamera.value) await updateCameraDevice(String(editingCamera.value.id), payload); else await createCameraDevice(payload); cameraDialog.value = false; ElMessage.success('摄像头已保存'); await loadCurrent() } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function removeCamera(row) { try { await ElMessageBox.confirm(`确认删除“${row.name}”？`, '删除摄像头', { type: 'warning' }); await deleteCameraDevice(String(row.id)); ElMessage.success('摄像头已删除'); await loadCurrent() } catch (error) { if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败') } }

function passwordLabel(row) {
  if (!row.has_password) return '--'
  if (!passwordVisible.value[row.id]) return '********'
  return passwordValues.value[row.id] || '********'
}

async function togglePassword(row) {
  const id = row.id
  if (passwordVisible.value[id]) {
    passwordVisible.value = { ...passwordVisible.value, [id]: false }
    return
  }
  if (!passwordValues.value[id]) {
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
  passwordVisible.value = { ...passwordVisible.value, [id]: true }
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
.device-admin { min-height: 100%; padding: 18px 22px 22px; color: #d9e8f8; background: #071422; }
.admin-header, .panel-head, .panel-toolbar, .map-panel header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.admin-header {
  min-height: 74px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}
.title-block {
  min-width: 0;
  display: grid;
  gap: 8px;
}
.title-block p { margin: 0; color: #8aa9c3; font-size: 13px; line-height: 1.35; }
h2, h3 { margin: 0; color: #f3f8fd; letter-spacing: 0; }
h2 { font-size: 25px; line-height: 1.1; }
.panel-head { margin-bottom: 16px; }
.panel-head p { margin: 7px 0 0; color: #829bb3; font-size: 12px; line-height: 1.35; }
.panel-toolbar { flex: 0 0 auto; justify-content: flex-end; gap: 10px; }
.panel-toolbar :deep(.el-button) {
  min-width: 84px;
  height: 32px;
  margin-left: 0;
  padding: 0 14px;
  font-size: 14px;
  font-weight: 600;
}
.mode-switch { display: inline-flex; align-items: center; gap: 4px; padding: 4px; border: 1px solid rgba(84, 148, 193, .34); border-radius: 8px; background: #0d2740; }
.mode-switch button { min-width: 82px; height: 34px; padding: 0 18px; border: 0; border-radius: 6px; color: #9fbbd3; background: transparent; font-size: 14px; font-weight: 700; cursor: pointer; }
.mode-switch button.active { color: #061827; background: #38d7de; box-shadow: 0 0 18px rgba(39, 194, 214, .28); }
.mode-switch button:focus-visible { outline: 2px solid #63e3ff; outline-offset: 2px; }
.data-panel, .map-panel { margin-top: 16px; padding: 18px 22px 20px; border: 1px solid rgba(96, 151, 191, .24); border-radius: 8px; background: #0b1d30; }
.data-panel { min-height: 310px; }
.camera-data-panel { min-height: 420px; }
.camera-table { border-radius: 6px; overflow: hidden; background: #0a1d30; }
.camera-table :deep(.el-table__inner-wrapper::before) { background: rgba(149, 190, 220, .12); }
.camera-table :deep(th.el-table__cell) { height: 52px; background: #122b45; color: #d6e8f8; font-size: 14px; font-weight: 700; }
.camera-table :deep(tr), .camera-table :deep(td.el-table__cell) { background: #0a1d30; color: #d7e8f8; }
.camera-table :deep(th.el-table__cell), .camera-table :deep(td.el-table__cell) { border-bottom-color: rgba(149, 190, 220, .12); }
.camera-table :deep(td.el-table__cell) { height: 82px; border-bottom-width: 1px; }
.camera-table :deep(.el-table__row:hover > td.el-table__cell) { background: #102940; }
.name-cell, .connection-cell, .status-cell { display: grid; gap: 7px; }
.name-cell strong { color: #f3f8fd; font-size: 15px; }
.name-cell small, .muted, .map-panel header span { color: #829bb3; font-size: 12px; }
.description-cell { display: block; overflow: hidden; color: #cfe1ef; line-height: 1.55; text-overflow: ellipsis; white-space: nowrap; }
.connection-cell { color: #cfe1ef; line-height: 1.45; }
.password-line { display: inline-flex; align-items: center; gap: 3px; min-height: 22px; }
.password-toggle { width: 24px; height: 24px; padding: 0; font-size: 15px; }
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
  border: 1px solid rgba(103, 194, 58, .32);
  color: #67e873;
  background: rgba(103, 194, 58, .13);
}
.status-pill.is-offline {
  border: 1px solid rgba(245, 108, 108, .34);
  color: #ff9f9f;
  background: rgba(245, 108, 108, .13);
}
.status-cell small { color: #8fa8bf; font-size: 12px; line-height: 1.4; }
.speaker-cell { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #d7e8f8; }
.speaker-cell > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.speaker-cell :deep(.el-button) { flex: 0 0 auto; border-color: #1b7fa5; color: #dcefff; background: #103954; }
.action-buttons { display: flex; align-items: center; gap: 8px; }
.action-buttons :deep(.el-button) { width: 32px; height: 32px; margin: 0; padding: 0; border-color: #1b7fa5; color: #dcefff; background: #103954; }
.action-buttons :deep(.el-button--danger) { border-color: rgba(220, 92, 111, .42); color: #ff9aa9; background: rgba(122, 30, 48, .34); }
.broadcast-tabs { margin-top: 16px; }
.broadcast-tabs .data-panel { margin-top: 0; }
.map-stage { position: relative; height: clamp(340px, 44vw, 620px); margin-top: 14px; overflow: hidden; border: 1px solid rgba(96, 151, 191, .2); border-radius: 6px; background: #02090f; }
.map-stage > img { width: 100%; height: 100%; object-fit: contain; }
.form-grid { display: grid; gap: 14px; }.form-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.advanced-collapse { margin-bottom: 12px; }
.camera-config-dialog :deep(.el-dialog), :deep(.camera-config-dialog.el-dialog) { background: #183b62; border: 1px solid rgba(97, 167, 214, .35); }
.camera-config-dialog :deep(.el-dialog__title), .camera-config-dialog :deep(.el-form-item__label) { color: #e7f4ff; }
.camera-config-dialog :deep(.el-form-item__label) { font-weight: 600; }
.camera-config-dialog :deep(.el-input__wrapper), .camera-config-dialog :deep(.el-textarea__inner) { background: #092034; box-shadow: inset 0 0 0 1px rgba(36, 128, 176, .42); color: #f4fbff; }
.camera-config-dialog :deep(.el-input__inner), .camera-config-dialog :deep(.el-textarea__inner), .camera-config-dialog :deep(.el-input-number .el-input__inner) { color: #f4fbff; }
.camera-config-dialog :deep(.el-input__inner::placeholder) { color: #93a8bb; }
.camera-config-dialog :deep(.el-checkbox__label) { color: #d6e8f8; }
.advanced-collapse { border: 1px solid rgba(70, 145, 190, .35); border-radius: 6px; overflow: hidden; background: #102f4d; }
.advanced-collapse :deep(.el-collapse) { border: 0; }
.advanced-collapse :deep(.el-collapse-item__header) { height: 46px; padding: 0 14px; border-bottom-color: rgba(70, 145, 190, .35); color: #e7f4ff; background: #123858; font-weight: 700; }
.advanced-collapse :deep(.el-collapse-item__wrap) { border-bottom: 0; background: #102f4d; }
.advanced-collapse :deep(.el-collapse-item__content) { padding: 16px 14px 18px; color: #d7e8f8; }
.advanced-collapse :deep(.el-input-number) { width: 100%; }
.advanced-collapse :deep(.el-input-number__decrease), .advanced-collapse :deep(.el-input-number__increase) { border-color: rgba(70, 145, 190, .45); color: #d7e8f8; background: #173a59; }
@media (max-width: 900px) { .admin-header { padding: 14px; }.panel-head { align-items: flex-start; flex-direction: column; }.panel-toolbar { width: 100%; flex-wrap: wrap; justify-content: flex-start; }.title-block { width: 100%; }.form-grid.two { grid-template-columns: 1fr; }.device-admin { padding: 12px; }.data-panel { overflow-x: auto; }.camera-data-panel { min-height: 460px; }.camera-table { min-width: 820px; } }
</style>
