<template>
  <div class="device-admin">
    <header class="admin-header">
      <div>
        <p class="eyebrow">视频监测 / 设备管理</p>
        <h2>摄像头设备管理</h2>
      </div>
      <div class="admin-actions">
        <button type="button" class="primary-action" @click="openCreate">
          <el-icon><Plus /></el-icon>
          添加设备
        </button>
        <button type="button" class="ghost-action" :class="{ loading }" @click="fetchDevices">
          <el-icon><Refresh /></el-icon>
          刷新
        </button>
      </div>
    </header>

    <section class="device-panel">
      <div class="device-table" v-loading="loading">
        <div class="table-head">
          <span>设备ID</span>
          <span>设备名称</span>
          <span>设备信息</span>
          <span>Web控制台</span>
          <span>设备状态</span>
          <span>操作</span>
        </div>
        <div v-if="cameraDevices.length === 0" class="empty-state">
          暂无摄像头设备，点击“添加设备”接入。
        </div>
        <div v-for="device in cameraDevices" :key="device.camera_id" class="table-row">
          <strong class="device-id">{{ device.camera_id }}</strong>
          <div class="device-name">
            <strong>{{ device.camera_name || device.name || '--' }}</strong>
            <small>{{ device.description || '--' }}</small>
          </div>
          <div class="device-info" :class="{ revealed: visibleDeviceInfo[device.camera_id] }">
            <div v-if="visibleDeviceInfo[device.camera_id]" class="device-info-lines">
              <span>IP：{{ device.ip_address || '--' }}</span>
              <span>账户：{{ device.username || '--' }}</span>
              <span>密码：{{ devicePasswordValue(device) }}</span>
            </div>
            <div v-else class="device-info-placeholder">
              <span>设备信息已隐藏</span>
              <small>点击右侧图标查看</small>
            </div>
            <button
              type="button"
              class="inline-icon info-eye"
              :title="visibleDeviceInfo[device.camera_id] ? '隐藏设备信息' : '显示设备信息'"
              @click="toggleDeviceInfo(device)"
            >
              <el-icon><component :is="visibleDeviceInfo[device.camera_id] ? Hide : View" /></el-icon>
            </button>
          </div>
          <a
            v-if="device.web_console_url"
            class="console-link"
            :href="device.web_console_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            打开控制台
          </a>
          <span v-else class="muted">--</span>
          <div class="status-cell">
            <span class="status-pill" :class="device.connected ? 'online' : 'offline'">
              {{ device.connected ? '在线' : '离线' }}
            </span>
            <small v-if="!device.connected">最后在线：{{ lastOnlineText(device) }}</small>
          </div>
          <span class="row-actions">
            <button type="button" title="编辑" @click="openEdit(device)">
              <el-icon><Edit /></el-icon>
            </button>
            <button type="button" class="danger" title="删除" @click="removeDevice(device)">
              <el-icon><Delete /></el-icon>
            </button>
          </span>
        </div>
      </div>
    </section>

    <section class="map-panel">
      <header>
        <h3>摄像头点位地图</h3>
      </header>
      <div
        class="map-stage"
        @wheel.prevent="onMapWheel"
        @mousedown="onMapMouseDown"
        @mousemove="onMapMouseMove"
        @mouseup="onMapMouseUp"
        @mouseleave="onMapMouseUp"
        @dblclick="resetMapView"
      >
        <div class="map-transform" :style="mapTransformStyle">
          <img src="/dammap.png" alt="大藤峡摄像头点位地图" class="site-map" draggable="false" />
        </div>
      </div>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editingDevice ? '编辑摄像头设备' : '添加摄像头设备'"
      width="720px"
      class="camera-device-dialog"
      destroy-on-close
    >
      <el-form label-position="top" class="device-form">
        <el-form-item v-if="editingDevice" label="设备ID">
          <el-input v-model.trim="form.camera_id" disabled />
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model.trim="form.camera_name" />
        </el-form-item>
        <el-form-item label="安装地址">
          <div class="location-row">
            <el-input v-model.trim="form.install_address" />
            <button type="button" class="ghost-action location-action" @click="locationPickerVisible = !locationPickerVisible">
              <el-icon><Location /></el-icon>
              地图选点
            </button>
          </div>
        </el-form-item>
        <div v-if="locationPickerVisible" class="location-picker">
          <div class="location-picker-head">
            <strong>摄像头点位</strong>
            <button type="button" class="inline-icon" title="关闭地图" @click="locationPickerVisible = false">
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <div class="location-map-stage" @click="pickLocationOnMap">
            <img src="/dam-map.png" alt="大藤峡点位地图" class="location-map-image" draggable="false" />
            <span v-if="hasLocationPoint" class="location-marker" :style="selectedLocationStyle"></span>
          </div>
        </div>
        <div class="form-grid two">
          <el-form-item label="纬度">
            <el-input-number v-model="form.latitude" :min="-90" :max="90" :precision="6" :controls="false" />
          </el-form-item>
          <el-form-item label="经度">
            <el-input-number v-model="form.longitude" :min="-180" :max="180" :precision="6" :controls="false" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model.trim="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid three">
          <el-form-item label="品牌">
            <el-select v-model="form.brand">
              <el-option label="大华" value="dahua" />
              <el-option label="海康" value="hikvision" />
            </el-select>
          </el-form-item>
          <el-form-item label="RTSP端口">
            <el-input-number v-model="form.rtsp_port" :min="1" :max="65535" :controls="false" />
          </el-form-item>
          <el-form-item label="Web端口">
            <el-input-number v-model="form.web_port" :min="1" :max="65535" :controls="false" />
          </el-form-item>
        </div>
        <el-form-item label="摄像头IP">
          <el-input v-model.trim="form.ip_address" />
        </el-form-item>
        <div class="form-grid two">
          <el-form-item label="Web账号">
            <el-input v-model.trim="form.username" autocomplete="off" />
          </el-form-item>
          <el-form-item label="Web密码">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              autocomplete="new-password"
              :placeholder="editingDevice ? '留空则保留原密码' : ''"
            />
          </el-form-item>
        </div>
        <el-form-item>
          <el-checkbox v-model="form.enabled">启用设备</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <button type="button" class="ghost-action" @click="dialogVisible = false">取消</button>
        <button type="button" class="ghost-action" :disabled="testing" @click="testConnection">
          <el-icon><Connection /></el-icon>
          测试连接
        </button>
        <button type="button" class="primary-action" :disabled="saving" @click="saveDevice">
          <el-icon><Check /></el-icon>
          保存
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close, Connection, Delete, Edit, Hide, Location, Plus, Refresh, View } from '@element-plus/icons-vue'
import {
  createCameraDevice,
  deleteCameraDevice,
  getCameraDevicePassword,
  getCameraDevices,
  testCameraDeviceConnection,
  updateCameraDevice,
} from '@/api/camera'
import { camerasFromPayload, readCameraDeviceSnapshot, writeCameraDeviceSnapshot } from '@/utils/cameraSnapshots'

const cameraDevices = ref([])
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const dialogVisible = ref(false)
const editingDevice = ref(null)
const locationPickerVisible = ref(false)
const verifiedConnectionKey = ref('')
const originalConnectionKey = ref('')
const visibleDeviceInfo = reactive({})
const passwordCache = reactive({})
const mapScale = ref(1)
const mapX = ref(0)
const mapY = ref(0)
const mapDragging = ref(false)
const mapDragStart = reactive({ x: 0, y: 0, mapX: 0, mapY: 0 })
let deviceFallbackNoticeAt = 0

const MAP_BOUNDS = {
  lngMin: 110.72,
  lngMax: 110.8,
  latMin: 23.96,
  latMax: 24.02,
}

const mapTransformStyle = computed(() => ({
  transform: `translate(${mapX.value}px, ${mapY.value}px) scale(${mapScale.value})`,
}))

const hasLocationPoint = computed(() => Number.isFinite(Number(form.latitude)) && Number.isFinite(Number(form.longitude)))

const selectedLocationStyle = computed(() => {
  if (!hasLocationPoint.value) return {}
  const longitude = Number(form.longitude)
  const latitude = Number(form.latitude)
  const left = ((longitude - MAP_BOUNDS.lngMin) / (MAP_BOUNDS.lngMax - MAP_BOUNDS.lngMin)) * 100
  const top = ((MAP_BOUNDS.latMax - latitude) / (MAP_BOUNDS.latMax - MAP_BOUNDS.latMin)) * 100
  return {
    left: `${Math.min(100, Math.max(0, left))}%`,
    top: `${Math.min(100, Math.max(0, top))}%`,
  }
})

const form = reactive({
  camera_id: '',
  camera_name: '',
  install_address: '',
  latitude: undefined,
  longitude: undefined,
  description: '',
  brand: 'dahua',
  ip_address: '',
  rtsp_port: 554,
  web_port: 80,
  username: '',
  password: '',
  enabled: true,
})

function resetForm() {
  form.camera_id = ''
  form.camera_name = ''
  form.install_address = ''
  form.latitude = undefined
  form.longitude = undefined
  form.description = ''
  form.brand = 'dahua'
  form.ip_address = ''
  form.rtsp_port = 554
  form.web_port = 80
  form.username = ''
  form.password = ''
  form.enabled = true
  verifiedConnectionKey.value = ''
  originalConnectionKey.value = ''
  locationPickerVisible.value = false
}

function openCreate() {
  editingDevice.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(device) {
  editingDevice.value = device
  form.camera_id = device.camera_id || ''
  form.camera_name = device.camera_name || device.name || ''
  form.install_address = device.install_address || ''
  form.latitude = device.latitude ?? undefined
  form.longitude = device.longitude ?? undefined
  form.description = device.description || ''
  form.brand = device.brand || 'dahua'
  form.ip_address = device.ip_address || ''
  form.rtsp_port = Number(device.rtsp_port) || 554
  form.web_port = Number(device.web_port) || 80
  form.username = device.username || ''
  form.password = ''
  form.enabled = Boolean(device.enabled)
  verifiedConnectionKey.value = ''
  originalConnectionKey.value = connectionKey()
  locationPickerVisible.value = false
  dialogVisible.value = true
}

function applyDeviceList(devices, persist = true) {
  cameraDevices.value = devices
  if (persist) writeCameraDeviceSnapshot(devices)
  preloadPasswords(cameraDevices.value)
}

function notifyDeviceListFallback(message) {
  const now = Date.now()
  if (now - deviceFallbackNoticeAt < 10000) return
  deviceFallbackNoticeAt = now
  ElMessage.warning(message)
}

async function fetchDevices() {
  loading.value = true
  try {
    const res = await getCameraDevices()
    if (res.code === 200) {
      applyDeviceList(camerasFromPayload(res.data))
    } else {
      ElMessage.error(res.message || '摄像头设备列表加载失败')
    }
  } catch (error) {
    const fallback = cameraDevices.value.length ? cameraDevices.value : readCameraDeviceSnapshot()
    if (fallback.length) {
      applyDeviceList(fallback, false)
      notifyDeviceListFallback('后端暂时不可达，已保留上次设备列表')
    } else {
      ElMessage.error(error.response?.data?.detail || error.message || '摄像头设备列表加载失败')
    }
  } finally {
    loading.value = false
  }
}

function zoomMap(delta) {
  const nextScale = Math.min(3, Math.max(1, Number((mapScale.value + delta).toFixed(2))))
  mapScale.value = nextScale
  if (nextScale === 1) {
    mapX.value = 0
    mapY.value = 0
  }
}

function onMapWheel(event) {
  zoomMap(event.deltaY < 0 ? 0.12 : -0.12)
}

function onMapMouseDown(event) {
  if (mapScale.value <= 1) return
  mapDragging.value = true
  mapDragStart.x = event.clientX
  mapDragStart.y = event.clientY
  mapDragStart.mapX = mapX.value
  mapDragStart.mapY = mapY.value
}

function onMapMouseMove(event) {
  if (!mapDragging.value) return
  mapX.value = mapDragStart.mapX + event.clientX - mapDragStart.x
  mapY.value = mapDragStart.mapY + event.clientY - mapDragStart.y
}

function onMapMouseUp() {
  mapDragging.value = false
}

function resetMapView() {
  mapScale.value = 1
  mapX.value = 0
  mapY.value = 0
}

function pickLocationOnMap(event) {
  const image = event.currentTarget.querySelector('.location-map-image')
  if (!image) return
  const rect = image.getBoundingClientRect()
  const naturalRatio = image.naturalWidth && image.naturalHeight ? image.naturalWidth / image.naturalHeight : rect.width / rect.height
  const boxRatio = rect.width / rect.height
  const visible = { left: rect.left, top: rect.top, width: rect.width, height: rect.height }
  if (boxRatio > naturalRatio) {
    visible.width = rect.height * naturalRatio
    visible.left = rect.left + (rect.width - visible.width) / 2
  } else {
    visible.height = rect.width / naturalRatio
    visible.top = rect.top + (rect.height - visible.height) / 2
  }
  const xRatio = (event.clientX - visible.left) / visible.width
  const yRatio = (event.clientY - visible.top) / visible.height
  if (xRatio < 0 || xRatio > 1 || yRatio < 0 || yRatio > 1) return
  form.longitude = Number((MAP_BOUNDS.lngMin + xRatio * (MAP_BOUNDS.lngMax - MAP_BOUNDS.lngMin)).toFixed(6))
  form.latitude = Number((MAP_BOUNDS.latMax - yRatio * (MAP_BOUNDS.latMax - MAP_BOUNDS.latMin)).toFixed(6))
}

function validateForm() {
  if (!form.camera_name) return '请填写设备名称'
  if (!form.ip_address) return '请填写摄像头IP'
  if (!form.username) return '请填写Web账号'
  if (!editingDevice.value && !form.password) return '请填写Web密码'
  return ''
}

function formPayload(includeEmptyPassword = false) {
  const payload = {
    camera_name: form.camera_name,
    install_address: form.install_address,
    latitude: form.latitude,
    longitude: form.longitude,
    description: form.description,
    brand: form.brand,
    ip_address: form.ip_address,
    rtsp_port: Number(form.rtsp_port) || 554,
    web_port: Number(form.web_port) || 80,
    username: form.username,
    enabled: form.enabled,
  }
  if (!editingDevice.value && form.camera_id) payload.camera_id = form.camera_id
  if (includeEmptyPassword || form.password) payload.password = form.password
  return payload
}

function connectionKey() {
  return JSON.stringify({
    brand: form.brand,
    ip_address: form.ip_address,
    rtsp_port: Number(form.rtsp_port) || 554,
    web_port: Number(form.web_port) || 80,
    username: form.username,
    password: form.password ? `typed:${form.password}` : (editingDevice.value?.has_password ? '__stored__' : ''),
  })
}

function needsConnectionTest() {
  if (!editingDevice.value) return true
  return connectionKey() !== originalConnectionKey.value
}

function hasVerifiedConnection() {
  return verifiedConnectionKey.value === connectionKey()
}

async function testConnection() {
  if (!form.ip_address) {
    ElMessage.warning('请填写摄像头IP')
    return
  }
  if (!form.username) {
    ElMessage.warning('请填写Web账号')
    return
  }
  const password = form.password || await savedPasswordForCurrentDevice()
  if (!password && (!editingDevice.value || editingDevice.value?.has_password)) {
    ElMessage.warning('测试连接需要输入密码')
    return
  }
  testing.value = true
  try {
    const res = await testCameraDeviceConnection({
      brand: form.brand,
      ip_address: form.ip_address,
      rtsp_port: Number(form.rtsp_port) || 554,
      username: form.username,
      password,
    })
    if (res.data?.connected) {
      verifiedConnectionKey.value = connectionKey()
      ElMessage.success(res.data.message || '连接成功，可以保存设备')
    }
    else ElMessage.error(res.data?.message || res.message || '连接失败')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '连接失败，请检查IP、账号、密码和网络')
  } finally {
    testing.value = false
  }
}

async function savedPasswordForCurrentDevice() {
  if (!editingDevice.value || !editingDevice.value?.has_password || !form.camera_id) return ''
  if (Object.prototype.hasOwnProperty.call(passwordCache, form.camera_id)) {
    return passwordCache[form.camera_id] || ''
  }
  try {
    const res = await getCameraDevicePassword(form.camera_id)
    passwordCache[form.camera_id] = res.data?.password || ''
  } catch (error) {
    passwordCache[form.camera_id] = ''
  }
  return passwordCache[form.camera_id] || ''
}

async function saveDevice() {
  const message = validateForm()
  if (message) {
    ElMessage.warning(message)
    return
  }
  if (needsConnectionTest() && !hasVerifiedConnection()) {
    ElMessage.warning('请先测试连接成功后再保存')
    return
  }
  saving.value = true
  try {
    if (editingDevice.value) {
      const payload = formPayload(false)
      delete payload.camera_id
      await updateCameraDevice(form.camera_id, payload)
      ElMessage.success('摄像头设备已更新')
    } else {
      await createCameraDevice(formPayload(true))
      ElMessage.success('摄像头设备已添加')
    }
    dialogVisible.value = false
    await fetchDevices()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '保存失败，请检查后端服务')
  } finally {
    saving.value = false
  }
}

async function removeDevice(device) {
  try {
    await ElMessageBox.confirm(`确认删除“${device.camera_name || device.camera_id}”？`, '删除摄像头设备', { type: 'warning' })
    await deleteCameraDevice(device.camera_id)
    ElMessage.success('摄像头设备已删除')
    await fetchDevices()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

function devicePasswordValue(device) {
  if (Object.prototype.hasOwnProperty.call(passwordCache, device.camera_id)) {
    return passwordCache[device.camera_id] || '--'
  }
  return device.has_password ? '读取中' : '--'
}

function toggleDeviceInfo(device) {
  visibleDeviceInfo[device.camera_id] = !visibleDeviceInfo[device.camera_id]
}

async function preloadPasswords(devices) {
  const targets = devices.filter(device => device.has_password && !passwordCache[device.camera_id])
  await Promise.allSettled(targets.map(async (device) => {
    try {
      const res = await getCameraDevicePassword(device.camera_id)
      passwordCache[device.camera_id] = res.data?.password || ''
    } catch (error) {
      passwordCache[device.camera_id] = ''
    }
  }))
}

function lastOnlineText(device) {
  const value = device.last_online_at || (device.last_frame_time ? Number(device.last_frame_time) * 1000 : 0)
  if (!value) return '--'
  const date = typeof value === 'number' ? new Date(value) : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleString('zh-CN', { hour12: false })
}

onMounted(fetchDevices)
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

.admin-header {
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

.admin-header h2 {
  margin: 0;
  color: #f4f8ff;
  font-size: 28px;
}

.primary-action,
.ghost-action {
  box-sizing: border-box;
  height: 38px;
  padding: 0 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: 8px;
  border: 1px solid transparent;
  font: inherit;
  cursor: pointer;
}

.primary-action {
  color: #061425;
  background: linear-gradient(135deg, #31d9ff, #6effbd);
  font-weight: 800;
}

.primary-action:disabled,
.ghost-action:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.ghost-action {
  border-color: rgba(120, 155, 211, 0.24);
  color: #cfe3fa;
  background: rgba(32, 57, 92, 0.58);
}

.ghost-action.loading .el-icon {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.device-panel,
.map-panel {
  margin-top: 22px;
  padding: 16px 22px;
  overflow: hidden;
  border: 1px solid rgba(83, 151, 210, 0.24);
  border-radius: 8px;
  background: rgba(11, 29, 52, 0.74);
  box-shadow: 0 18px 36px rgba(0, 8, 22, 0.22);
}

.device-table {
  min-height: 520px;
}

.device-table :deep(.el-loading-mask) {
  background: rgba(4, 14, 26, 0.76);
  backdrop-filter: blur(2px);
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 0.7fr 1.15fr 1.35fr 1.15fr 0.9fr 0.45fr;
  align-items: center;
  gap: 16px;
}

.table-head {
  min-height: 42px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(143, 181, 225, 0.14);
  color: #8ea8c9;
  font-size: 12px;
  font-weight: 800;
}

.table-row {
  min-height: 96px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(143, 181, 225, 0.1);
  color: #d8e7fb;
}

.device-id,
.device-name strong {
  color: #f4f8ff;
}

.device-name small,
.status-cell small,
.muted {
  display: block;
  margin-top: 5px;
  color: #8ea8c9;
  font-size: 12px;
}

.device-info {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  gap: 10px;
  color: #bcd1ec;
  font-size: 13px;
}

.device-info-lines {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.device-info-lines span,
.device-info-placeholder span,
.device-info-placeholder small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-info-lines span {
  color: #d8e7fb;
}

.device-info-placeholder {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.device-info-placeholder span {
  color: #d8e7fb;
  font-weight: 700;
}

.device-info-placeholder small {
  color: #7f9bb0;
  font-size: 12px;
}

.inline-icon {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 5px;
  color: #8ee8ff;
  background: rgba(49, 217, 255, 0.12);
  cursor: pointer;
}

.info-eye {
  width: 30px;
  height: 30px;
  justify-self: end;
}

.console-link {
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  color: #8ee8ff;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
}

.console-link:hover {
  text-decoration: underline;
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
  width: 32px;
  height: 32px;
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

.map-panel header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.map-panel h3 {
  margin: 0;
  color: #f4f8ff;
  font-size: 16px;
}

.map-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  height: clamp(360px, 44vw, 640px);
  overflow: hidden;
  border: 1px solid rgba(143, 181, 225, 0.16);
  border-radius: 8px;
  background: #030b12;
  cursor: grab;
  user-select: none;
}

.map-stage:active {
  cursor: grabbing;
}

.map-transform {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transform-origin: center center;
  transition: transform 0.08s ease-out;
  will-change: transform;
}

.site-map {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.device-form {
  display: grid;
  gap: 2px;
}

.location-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.location-action {
  min-width: 110px;
}

.location-picker {
  margin: 0 0 14px;
  overflow: hidden;
  border: 1px solid rgba(120, 155, 211, 0.24);
  border-radius: 8px;
  background: rgba(4, 14, 26, 0.74);
}

.location-picker-head {
  min-height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #dce9fa;
  border-bottom: 1px solid rgba(143, 181, 225, 0.12);
}

.location-map-stage {
  position: relative;
  width: 100%;
  max-height: 360px;
  aspect-ratio: 865 / 289;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #030b12;
  cursor: crosshair;
  user-select: none;
}

.location-map-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
}

.location-marker {
  position: absolute;
  width: 18px;
  height: 18px;
  border: 3px solid #061425;
  border-radius: 50%;
  background: #ffdf45;
  box-shadow: 0 0 0 3px rgba(255, 223, 69, 0.32), 0 0 18px rgba(255, 223, 69, 0.72);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid.two {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.form-grid.three {
  grid-template-columns: minmax(0, 1fr) 120px 120px;
}

.form-grid :deep(.el-input-number),
.form-grid :deep(.el-select) {
  width: 100%;
}

:global(.camera-device-dialog .el-dialog) {
  background:
    radial-gradient(circle at 100% 0%, rgba(49, 217, 255, 0.11), transparent 30%),
    linear-gradient(180deg, #0d2137 0%, #081827 100%);
  border: 1px solid rgba(49, 217, 255, 0.28);
}

:global(.camera-device-dialog .el-dialog__title),
:global(.camera-device-dialog .el-form-item__label),
:global(.camera-device-dialog .el-checkbox__label) {
  color: #dce9fa;
}

:global(.camera-device-dialog .el-dialog__body) {
  padding: 18px 24px 4px;
}

:global(.camera-device-dialog .el-dialog__footer) {
  padding: 14px 24px 20px;
  border-top: 1px solid rgba(143, 181, 225, 0.12);
}

:global(.camera-device-dialog .dialog-footer),
:global(.camera-device-dialog .el-dialog__footer) {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:global(.camera-device-dialog .el-input__wrapper),
:global(.camera-device-dialog .el-textarea__inner),
:global(.camera-device-dialog .el-select__wrapper),
:global(.camera-device-dialog .el-input-number .el-input__wrapper) {
  color: #f4f8ff;
  background: rgba(6, 22, 38, 0.76);
  box-shadow: 0 0 0 1px rgba(120, 155, 211, 0.24) inset;
}

:global(.camera-device-dialog .el-input__inner),
:global(.camera-device-dialog .el-textarea__inner),
:global(.camera-device-dialog .el-select__selected-item) {
  color: #f4f8ff;
}

@media (max-width: 1180px) {
  .table-head,
  .table-row {
    grid-template-columns: 0.8fr 1.1fr 1.2fr 1fr 0.9fr 0.5fr;
  }
}

@media (max-width: 980px) {
  .admin-header,
  .map-panel header {
    align-items: flex-start;
    flex-direction: column;
  }

  .table-head {
    display: none;
  }

  .table-row {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .form-grid.two,
  .form-grid.three,
  .location-row {
    grid-template-columns: 1fr;
  }

  .location-action {
    width: 100%;
  }
}
</style>
