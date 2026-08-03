<template>
  <div class="device-admin">
    <header class="admin-header">
      <div class="title-block">
        <div class="mode-switch" aria-label="设备类型切换">
          <button
            v-for="option in modeOptions"
            :key="option.value"
            type="button"
            :class="{ active: deviceMode === option.value }"
            @click="deviceMode = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <div>
          <p>视频监测 / 设备管理</p>
          <h2>{{ deviceMode === 'camera' ? '摄像头设备管理' : '广播管理' }}</h2>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="openCreate">
          {{ createButtonText }}
        </el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadCurrent">刷新</el-button>
      </div>
    </header>

    <template v-if="deviceMode === 'camera'">
      <section class="data-panel camera-data-panel" v-loading="loading">
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
                <div class="status-tags">
                  <el-tag :type="row.connected ? 'success' : 'danger'">{{ row.connected ? '在线' : '离线' }}</el-tag>
                  <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
                </div>
                <small v-if="!row.connected && row.last_online_at">最后在线：{{ formatDateTime(row.last_online_at) }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="绑定扬声器" min-width="190">
            <template #default="{ row }">
              <div class="speaker-cell">
                <span v-if="row.broadcast_devices?.length">{{ row.broadcast_devices.map(item => item.name).join('、') }}</span>
                <span v-else class="muted">未绑定</span>
                <el-button size="small" :icon="Link" title="绑定扬声器" @click="openBinding(row)">绑定</el-button>
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
    </template>

    <template v-else>
      <el-tabs v-model="broadcastTab" class="broadcast-tabs" @tab-change="loadBroadcast">
        <el-tab-pane label="广播设备" name="devices">
          <section class="data-panel" v-loading="loading">
            <el-table :data="broadcastDevices" row-key="id" empty-text="暂无广播设备">
              <el-table-column prop="name" label="设备名称" min-width="180" />
              <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
              <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.status === 'ONLINE' ? 'success' : 'danger'">{{ row.status === 'ONLINE' ? '在线' : '离线' }}</el-tag></template></el-table-column>
              <el-table-column label="是否启用" width="110"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" :icon="Edit" title="编辑" @click="openBroadcastEdit(row)" /><el-button link type="danger" :icon="Delete" title="删除" @click="removeBroadcast(row)" /></template></el-table-column>
            </el-table>
          </section>
        </el-tab-pane>
        <el-tab-pane label="广播模板" name="templates">
          <section class="data-panel" v-loading="loading">
            <el-table :data="templates" row-key="id" empty-text="暂无广播模板">
              <el-table-column prop="name" label="模板名称" min-width="170" />
              <el-table-column label="场景类型" width="130"><template #default="{ row }">{{ sceneLabel(row.scene_type) }}</template></el-table-column>
              <el-table-column label="风险等级" width="110"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)">{{ riskLabel(row.risk_level) }}</el-tag></template></el-table-column>
              <el-table-column prop="content" label="播报文本" min-width="320" show-overflow-tooltip />
              <el-table-column label="是否启用" width="100"><template #default="{ row }">{{ row.enabled === false ? '停用' : '启用' }}</template></el-table-column>
              <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" :icon="Edit" title="编辑" @click="openTemplateEdit(row)" /><el-button link type="danger" :icon="Delete" title="删除" @click="removeTemplate(row)" /></template></el-table-column>
            </el-table>
          </section>
        </el-tab-pane>
      </el-tabs>
    </template>

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

    <el-dialog v-model="bindingDialog" title="绑定扬声器" width="500px">
      <el-checkbox-group v-model="selectedDeviceIds" class="binding-list">
        <el-checkbox v-for="device in enabledBroadcastDevices" :key="device.id" :value="device.id">{{ device.name }}<small>{{ device.description || 'USB/本地播放设备' }}</small></el-checkbox>
      </el-checkbox-group>
      <el-empty v-if="!enabledBroadcastDevices.length" description="暂无可用广播设备" :image-size="64" />
      <template #footer><el-button @click="bindingDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveBinding">保存绑定</el-button></template>
    </el-dialog>

    <el-dialog v-model="broadcastDialog" :title="editingBroadcast ? '编辑广播设备' : '添加广播设备'" width="520px">
      <el-form label-position="top"><el-form-item label="名称"><el-input v-model.trim="broadcastForm.name" maxlength="128" /></el-form-item><el-form-item label="描述"><el-input v-model.trim="broadcastForm.description" type="textarea" :rows="3" maxlength="500" /></el-form-item><el-form-item><el-checkbox v-model="broadcastForm.enabled">启用设备</el-checkbox></el-form-item></el-form>
      <template #footer><el-button @click="broadcastDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveBroadcast">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="templateDialog" :title="editingTemplate ? '编辑广播模板' : '添加广播模板'" width="600px">
      <el-form label-position="top"><div class="form-grid two"><el-form-item label="模板名称"><el-input v-model.trim="templateForm.name" /></el-form-item><el-form-item label="场景类型"><el-select v-model="templateForm.scene_type"><el-option label="人员安全" value="PERSON" /><el-option label="非法捕鱼" value="FISHING" /><el-option label="通用" value="GENERAL" /></el-select></el-form-item></div><el-form-item label="风险等级"><el-radio-group v-model="templateForm.risk_level"><el-radio-button value="LOW">低风险</el-radio-button><el-radio-button value="MEDIUM">中风险</el-radio-button><el-radio-button value="HIGH">高风险</el-radio-button></el-radio-group></el-form-item><el-form-item label="播报文本"><el-input v-model.trim="templateForm.content" type="textarea" :rows="4" maxlength="500" show-word-limit /></el-form-item><el-form-item><el-checkbox v-model="templateForm.enabled">启用模板</el-checkbox></el-form-item></el-form>
      <template #footer><el-button @click="templateDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveTemplate">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Connection, Delete, Edit, Hide, Link, Plus, Refresh, View } from '@element-plus/icons-vue'
import { createCameraDevice, deleteCameraDevice, getCameraDevicePassword, getCameraDevices, testCameraDeviceConnection, updateCameraDevice } from '@/api/camera'
import {
  bindCameraBroadcastDevices, createBroadcastDevice, createBroadcastTemplate,
  deleteBroadcastDevice, deleteBroadcastTemplate, getBroadcastDevices, getBroadcastTemplates,
  updateBroadcastDevice, updateBroadcastTemplate,
} from '@/api/broadcast'

const deviceMode = ref('camera')
const modeOptions = [{ label: '摄像头', value: 'camera' }, { label: '广播', value: 'broadcast' }]
const broadcastTab = ref('devices')
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const cameras = ref([])
const broadcastDevices = ref([])
const templates = ref([])
const cameraDialog = ref(false)
const broadcastDialog = ref(false)
const templateDialog = ref(false)
const bindingDialog = ref(false)
const editingCamera = ref(null)
const editingBroadcast = ref(null)
const editingTemplate = ref(null)
const bindingCamera = ref(null)
const selectedDeviceIds = ref([])
const verifiedKey = ref('')
const passwordVisible = ref({})
const passwordLoading = ref({})
const passwordValues = ref({})

const cameraForm = reactive({ camera_name: '', ip_address: '', username: '', password: '', description: '', install_address: '', latitude: undefined, longitude: undefined, rtsp_port: 554, web_port: 80, enabled: true })
const broadcastForm = reactive({ name: '', description: '', enabled: true })
const templateForm = reactive({ name: '', scene_type: 'PERSON', risk_level: 'LOW', content: '', enabled: true })
const createButtonText = computed(() => deviceMode.value === 'camera' ? '添加摄像头' : (broadcastTab.value === 'devices' ? '添加广播设备' : '添加广播模板'))
const enabledBroadcastDevices = computed(() => broadcastDevices.value.filter(item => item.enabled))
const connectionKey = computed(() => JSON.stringify([cameraForm.ip_address, cameraForm.rtsp_port, cameraForm.username, cameraForm.password]))
const connectionVerified = computed(() => !needsTest.value || verifiedKey.value === connectionKey.value)
const needsTest = computed(() => !editingCamera.value || connectionKey.value !== editingCamera.value.connectionKey)

async function loadCameras() { const res = await getCameraDevices(); cameras.value = res.data?.cameras || [] }
async function loadBroadcast() { const [deviceRes, templateRes] = await Promise.all([getBroadcastDevices(), getBroadcastTemplates()]); broadcastDevices.value = deviceRes.data || []; templates.value = templateRes.data || [] }
async function loadCurrent() { loading.value = true; try { if (deviceMode.value === 'camera') await Promise.all([loadCameras(), loadBroadcast()]); else await loadBroadcast() } catch (error) { ElMessage.error(error.response?.data?.detail || '数据加载失败') } finally { loading.value = false } }
watch(deviceMode, loadCurrent)

function resetCameraForm() { Object.assign(cameraForm, { camera_name: '', ip_address: '', username: '', password: '', description: '', install_address: '', latitude: undefined, longitude: undefined, rtsp_port: 554, web_port: 80, enabled: true }); verifiedKey.value = '' }
function openCreate() { if (deviceMode.value === 'camera') { editingCamera.value = null; resetCameraForm(); cameraDialog.value = true } else if (broadcastTab.value === 'devices') openBroadcastEdit(null); else openTemplateEdit(null) }
function openCameraEdit(row) { editingCamera.value = { ...row, connectionKey: JSON.stringify([row.ip_address, Number(row.rtsp_port) || 554, row.username || '', '']) }; Object.assign(cameraForm, { camera_name: row.name, ip_address: row.ip_address, username: row.username || '', password: '', description: row.description || '', install_address: row.install_address || '', latitude: row.latitude ?? undefined, longitude: row.longitude ?? undefined, rtsp_port: Number(row.rtsp_port) || 554, web_port: Number(row.web_port) || 80, enabled: Boolean(row.enabled) }); verifiedKey.value = ''; cameraDialog.value = true }
async function testConnection() { if (!cameraForm.ip_address || !cameraForm.username || (!editingCamera.value && !cameraForm.password)) return ElMessage.warning('请完整填写 IP、账号和密码'); testing.value = true; try { const res = await testCameraDeviceConnection({ ip_address: cameraForm.ip_address, rtsp_port: cameraForm.rtsp_port, username: cameraForm.username, password: cameraForm.password }); if (res.data?.connected) { verifiedKey.value = connectionKey.value; ElMessage.success(`连接成功，已识别为${res.data.brand === 'hikvision' ? '海康' : '大华'}设备`) } else ElMessage.error(res.data?.message || '连接失败') } catch (error) { ElMessage.error(error.response?.data?.detail || '连接失败') } finally { testing.value = false } }
async function saveCamera() { if (!cameraForm.camera_name || !cameraForm.ip_address || !cameraForm.username) return ElMessage.warning('请填写名称、IP 和账号'); if (!connectionVerified.value) return ElMessage.warning('请先测试连接'); saving.value = true; try { const payload = { ...cameraForm }; if (editingCamera.value && !payload.password) delete payload.password; if (editingCamera.value) await updateCameraDevice(String(editingCamera.value.id), payload); else await createCameraDevice(payload); cameraDialog.value = false; ElMessage.success('摄像头已保存'); await loadCurrent() } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function removeCamera(row) { try { await ElMessageBox.confirm(`确认删除“${row.name}”？`, '删除摄像头', { type: 'warning' }); await deleteCameraDevice(String(row.id)); ElMessage.success('摄像头已删除'); await loadCurrent() } catch (error) { if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败') } }

async function openBinding(row) { bindingCamera.value = row; if (!broadcastDevices.value.length) await loadBroadcast(); selectedDeviceIds.value = (row.broadcast_devices || []).map(item => item.id); bindingDialog.value = true }
async function saveBinding() { saving.value = true; try { await bindCameraBroadcastDevices(String(bindingCamera.value.id), selectedDeviceIds.value); bindingDialog.value = false; ElMessage.success('绑定已保存'); await loadCameras() } catch (error) { ElMessage.error(error.response?.data?.detail || '绑定失败') } finally { saving.value = false } }

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

function openBroadcastEdit(row) { editingBroadcast.value = row; Object.assign(broadcastForm, row ? { name: row.name, description: row.description || '', enabled: Boolean(row.enabled) } : { name: '', description: '', enabled: true }); broadcastDialog.value = true }
async function saveBroadcast() { if (!broadcastForm.name) return ElMessage.warning('请填写设备名称'); saving.value = true; try { if (editingBroadcast.value) await updateBroadcastDevice(editingBroadcast.value.id, broadcastForm); else await createBroadcastDevice(broadcastForm); broadcastDialog.value = false; ElMessage.success('广播设备已保存'); await loadBroadcast() } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function removeBroadcast(row) { try { await ElMessageBox.confirm(`确认删除“${row.name}”？`, '删除广播设备', { type: 'warning' }); await deleteBroadcastDevice(row.id); await loadBroadcast() } catch (error) { if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败') } }

function openTemplateEdit(row) { editingTemplate.value = row; Object.assign(templateForm, row ? { name: row.name, scene_type: row.scene_type || 'GENERAL', risk_level: row.risk_level || 'LOW', content: row.content, enabled: row.enabled !== false } : { name: '', scene_type: 'PERSON', risk_level: 'LOW', content: '', enabled: true }); templateDialog.value = true }
async function saveTemplate() { if (!templateForm.name || !templateForm.content) return ElMessage.warning('请填写模板名称和播报文本'); saving.value = true; try { if (editingTemplate.value) await updateBroadcastTemplate(editingTemplate.value.id, templateForm); else await createBroadcastTemplate(templateForm); templateDialog.value = false; ElMessage.success('广播模板已保存'); await loadBroadcast() } catch (error) { ElMessage.error(error.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function removeTemplate(row) { try { await ElMessageBox.confirm(`确认删除“${row.name}”？`, '删除广播模板', { type: 'warning' }); await deleteBroadcastTemplate(row.id); await loadBroadcast() } catch (error) { if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '删除失败') } }

function riskLabel(value) { return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[value] || '通用' }
function riskTag(value) { return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[value] || 'info' }
function sceneLabel(value) { return ({ PERSON: '人员安全', FISHING: '非法捕鱼', GENERAL: '通用' })[value] || value }
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
.device-admin { min-height: 100%; padding: 22px; color: #d9e8f8; background: #071422; }
.admin-header, .title-block, .header-actions, .map-panel header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.title-block { justify-content: flex-start; }
.title-block p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
h2, h3 { margin: 0; color: #f3f8fd; letter-spacing: 0; }
h2 { font-size: 25px; }
.mode-switch { display: inline-flex; align-items: center; gap: 4px; padding: 4px; border: 1px solid rgba(84, 148, 193, .34); border-radius: 8px; background: #0d2740; }
.mode-switch button { min-width: 82px; height: 34px; padding: 0 18px; border: 0; border-radius: 6px; color: #9fbbd3; background: transparent; font-size: 14px; font-weight: 700; cursor: pointer; }
.mode-switch button.active { color: #061827; background: #38d7de; box-shadow: 0 0 18px rgba(39, 194, 214, .28); }
.mode-switch button:focus-visible { outline: 2px solid #63e3ff; outline-offset: 2px; }
.data-panel, .map-panel { margin-top: 18px; padding: 22px 24px; border: 1px solid rgba(96, 151, 191, .24); border-radius: 8px; background: #0b1d30; }
.data-panel { min-height: 310px; }
.camera-data-panel { min-height: 600px; }
.camera-table { border-radius: 6px; overflow: hidden; background: #0a1d30; }
.camera-table :deep(.el-table__inner-wrapper::before) { background: rgba(149, 190, 220, .12); }
.camera-table :deep(th.el-table__cell) { height: 56px; background: #142d49; color: #d6e8f8; font-size: 14px; font-weight: 700; }
.camera-table :deep(tr), .camera-table :deep(td.el-table__cell) { background: #0a1d30; color: #d7e8f8; }
.camera-table :deep(th.el-table__cell), .camera-table :deep(td.el-table__cell) { border-bottom-color: rgba(149, 190, 220, .12); }
.camera-table :deep(td.el-table__cell) { height: 122px; border-bottom-width: 1px; }
.camera-table :deep(.el-table__row:hover > td.el-table__cell) { background: #102940; }
.name-cell, .connection-cell, .status-cell { display: grid; gap: 7px; }
.name-cell strong { color: #f3f8fd; font-size: 15px; }
.name-cell small, .muted, .map-panel header span { color: #829bb3; font-size: 12px; }
.connection-cell { color: #cfe1ef; line-height: 1.45; }
.password-line { display: inline-flex; align-items: center; gap: 3px; min-height: 22px; }
.password-toggle { width: 24px; height: 24px; padding: 0; font-size: 15px; }
.status-tags { display: flex; flex-wrap: wrap; gap: 8px; }
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
.binding-list { display: grid; gap: 10px; }.binding-list :deep(.el-checkbox) { height: auto; margin: 0; padding: 12px; border: 1px solid rgba(96, 151, 191, .22); border-radius: 6px; }.binding-list small { display: block; margin-top: 3px; color: #839cb4; }
@media (max-width: 900px) { .admin-header { align-items: flex-start; flex-direction: column; }.title-block { align-items: flex-start; flex-direction: column; }.form-grid.two { grid-template-columns: 1fr; }.device-admin { padding: 12px; }.camera-data-panel { min-height: 460px; } }
</style>
