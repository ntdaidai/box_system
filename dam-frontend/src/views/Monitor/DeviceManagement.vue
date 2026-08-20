<template>
  <div class="device-admin">
    <header class="admin-header">
      <div class="title-block">
        <h2>感知源管理</h2>
        <p>统一维护系统感知源设备和运行状态</p>
      </div>
      <div class="status-summary" aria-label="感知源统计">
        <div class="metric"><i class="dot total"></i><strong class="metric-num">{{ cameras.length }}</strong><span class="metric-label">总数</span></div>
        <div class="metric"><i class="dot online"></i><strong class="metric-num">{{ cameraOnlineCount }}</strong><span class="metric-label">在线</span></div>
        <div class="metric"><i class="dot offline"></i><strong class="metric-num">{{ cameraOfflineCount }}</strong><span class="metric-label">离线</span></div>
      </div>
    </header>

    <section class="data-panel camera-toolbar-card">
      <div class="panel-head">
        <div>
          <h3>摄像头列表</h3>
        </div>
        <div class="panel-toolbar">
          <button type="button" class="toolbar-map-entry" @click="openMapDialog">
            <el-icon><Aim /></el-icon>
            <span>查看点位图</span>
          </button>
          <el-button type="primary" :icon="Plus" @click="openCreate()">
            {{ createButtonText }}
          </el-button>
          <el-select
            v-model="statusFilter"
            class="status-filter-select"
            popper-class="camera-status-filter-popper"
            placeholder="全部状态"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
          </el-select>
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
          <div class="col-enabled">是否启用</div>
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

    <el-dialog
      v-model="mapDialogVisible"
      class="camera-map-dialog"
      title="摄像头点位图"
      width="95vw"
      top="3vh"
    >
      <div class="expanded-map-stage">
        <img src="/dam.png" alt="大藤峡摄像头点位总览" />
        <svg
          v-if="selectedMapRegionPath"
          class="expanded-map-region-layer"
          viewBox="0 0 2168 725"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <filter id="camera-device-region-glow" x="-14%" y="-18%" width="128%" height="136%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values="0 0 0 0 0.25 0 0 0 0 0.86 0 0 0 0 1 0 0 0 .88 0"
                result="cyanGlow"
              />
              <feMerge>
                <feMergeNode in="cyanGlow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path class="expanded-region-fill" :d="selectedMapRegionPath" />
          <path class="expanded-region-halo" :d="selectedMapRegionPath" />
          <path class="expanded-region-line" :d="selectedMapRegionPath" />
          <g v-if="selectedMapRegionCallout" class="expanded-region-callout">
            <rect
              :x="selectedMapRegionCallout.x"
              :y="selectedMapRegionCallout.y"
              :width="selectedMapRegionCallout.width"
              :height="34"
              rx="5"
            />
            <text
              :x="selectedMapRegionCallout.x + selectedMapRegionCallout.width / 2"
              :y="selectedMapRegionCallout.y + 22"
            >
              {{ selectedMapRegionCallout.label }}
            </text>
          </g>
        </svg>
        <button
          v-for="point in cameraPointSlots"
          :key="`expanded-map-point-${point.no}`"
          type="button"
          class="expanded-map-point"
          :class="{ active: point.no === selectedPointNo, offline: !point.camera?.connected, empty: !point.camera }"
          :style="cameraPointStyle(point)"
          :title="point.camera?.name || `${point.no}号监测点暂未接入`"
          @click="selectMapPoint(point.no)"
        >
          <span>{{ point.no }}</span>
        </button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Aim, Check, Connection, Hide, Plus, View } from '@element-plus/icons-vue'
import { createCameraDevice, deleteCameraDevice, getCameraDevicePassword, getCameraDevices, testCameraDeviceConnection, updateCameraDevice } from '@/api/camera'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const cameras = ref([])
const cameraDialog = ref(false)
const mapDialogVisible = ref(false)
const selectedPointNo = ref(9)
const editingCamera = ref(null)
const verifiedKey = ref('')
const statusFilter = ref('')
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
const cameraOnlineCount = computed(() => cameras.value.filter((camera) => camera.connected).length)
const cameraOfflineCount = computed(() => cameras.value.length - cameraOnlineCount.value)
const connectionKey = computed(() => JSON.stringify([cameraForm.ip_address, cameraForm.rtsp_port, cameraForm.username, cameraForm.password]))
const connectionVerified = computed(() => !needsTest.value || verifiedKey.value === connectionKey.value)
const needsTest = computed(() => !editingCamera.value || connectionKey.value !== editingCamera.value.connectionKey)
const cameraPointDefinitions = [
  { no: 1, x: 17.3410, y: 40.8304 },
  { no: 2, x: 7.3988, y: 15.2249 },
  { no: 3, x: 41.8497, y: 74.0484 },
  { no: 4, x: 47.3988, y: 38.0623 },
  { no: 5, x: 49.2486, y: 38.0623 },
  { no: 6, x: 66.3584, y: 52.5952 },
  { no: 7, x: 68.2081, y: 52.5952 },
  { no: 8, x: 57.3410, y: 75.4325 },
  { no: 9, x: 91.7919, y: 24.2215 },
]
const cameraRegionPaths = {
  1: 'M371 317 L297 320 L259 324 L230 336 L191 363 L176 386 L179 425 L179 453 L181 487 L178 536 L200 549 L214 554 L231 554 L244 557 L262 556 L272 560 L295 557 L298 558 L327 560 L351 567 L372 570 L374 577 L383 583 L395 581 L408 578 L422 576 L436 571 L449 569 L463 561 L477 555 L489 552 L502 553 L511 546 L521 535 L524 521 L540 510 L538 492 L542 483 L539 466 L539 450 L538 433 L541 425 L542 406 L542 391 L539 380 L539 368 L537 358 L536 347 L531 340 L524 334 L514 332 L494 330 L470 339 L448 339 L427 343 L416 339 Z',
  2: 'M105 161 L134 169 L189 180 L247 191 L286 196 L307 201 L312 213 L304 222 L300 231 L294 242 L276 260 L260 263 L222 264 L188 256 L162 252 L130 241 L121 236 L110 231 L98 228 L96 212 L84 208 L76 199 L78 191 L84 177 Z',
  3: 'M847 460 L831 450 L830 424 L972 423 L1032 430 L1051 456 L1047 477 L1044 504 L1030 518 L1024 525 L927 544 L856 533 L852 523 L844 524 Z',
  4: 'M844 255 L847 296 L831 304 L829 413 L867 415 L968 415 L1031 422 L1043 405 L1046 376 L1044 355 L1043 335 L1038 319 L1039 302 L1033 291 L1006 276 L952 262 L928 257 Z',
  5: 'M1058 300 L1053 328 L1054 339 L1054 360 L1053 376 L1053 395 L1051 413 L1066 428 L1089 437 L1136 439 L1226 447 L1256 442 L1258 435 L1266 416 L1274 393 L1276 379 L1276 364 L1272 358 L1221 351 L1194 346 L1159 337 Z',
  6: 'M1439 335 L1383 352 L1367 353 L1355 361 L1343 365 L1332 368 L1318 362 L1299 361 L1288 361 L1283 379 L1282 396 L1279 415 L1279 436 L1279 445 L1279 466 L1283 483 L1283 495 L1286 510 L1296 514 L1304 516 L1318 510 L1334 512 L1367 508 L1367 497 L1390 486 L1398 488 L1424 476 L1432 468 L1441 471 L1464 457 Z',
  7: 'M1447 335 L1576 287 L1617 282 L1649 283 L1730 280 L1749 271 L1778 271 L1792 263 L1799 278 L1804 299 L1812 330 L1809 360 L1809 374 L1798 385 L1781 393 L1671 406 L1589 415 L1519 444 L1514 441 L1474 450 Z',
  8: 'M1273 520 L1259 521 L1230 526 L1193 540 L1178 541 L1165 530 L1147 545 L1049 523 L1049 513 L1051 498 L1054 486 L1055 467 L1061 456 L1073 445 L1090 444 L1126 445 L1165 451 L1199 452 L1224 454 L1249 456 L1261 453 L1269 461 L1274 479 L1279 503 L1280 517 Z',
  9: 'M2127 373 L2108 370 L2104 375 L2084 378 L2066 375 L2030 377 L1984 376 L1944 378 L1915 379 L1897 381 L1872 384 L1843 385 L1836 385 L1826 389 L1823 398 L1824 408 L1838 418 L1877 412 L1898 408 L1922 411 L1944 415 L1974 419 L2005 422 L2025 412 L2041 409 L2056 407 L2066 410 L2088 410 L2104 408 L2121 410 L2134 406 L2142 393 L2141 381 L2142 373 Z',
}
const filteredCameras = computed(() => {
  return cameras.value.filter((camera) => {
    const status = camera.connected ? 'online' : 'offline'
    return !statusFilter.value || statusFilter.value === 'all' || statusFilter.value === status
  })
})
const pagedCameras = computed(() => {
  const start = (cameraPage.value - 1) * pageSize
  return filteredCameras.value.slice(start, start + pageSize)
})
const cameraPointSlots = computed(() => buildCameraPointSlots())
const selectedPointSlot = computed(() => cameraPointSlots.value.find((point) => point.no === selectedPointNo.value) || cameraPointSlots.value[0])
const selectedMapRegionPath = computed(() => cameraRegionPaths[selectedPointNo.value] || regionPathFromPoint(selectedPointSlot.value))
const selectedMapRegionCallout = computed(() => regionCalloutFromPath(selectedMapRegionPath.value, selectedPointNo.value))

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

function openMapDialog() {
  selectedPointNo.value = 9
  mapDialogVisible.value = true
}

function selectMapPoint(pointNo) {
  selectedPointNo.value = pointNo
}

function cameraPointNo(camera) {
  const direct = Number(camera?.point_no ?? camera?.pointNo ?? camera?.monitor_point_no)
  if (Number.isInteger(direct) && direct >= 1 && direct <= 9) return direct
  const text = [
    camera?.name,
    camera?.camera_name,
    camera?.install_address,
    camera?.description,
  ].filter(Boolean).join(' ')
  const match = text.match(/([1-9])\s*号/)
  return match ? Number(match[1]) : null
}

function buildCameraPointSlots() {
  const assigned = new Map()
  const unassigned = []
  cameras.value.forEach((camera) => {
    const no = cameraPointNo(camera)
    if (no && !assigned.has(no)) assigned.set(no, camera)
    else unassigned.push(camera)
  })
  if (!assigned.has(9) && unassigned.length) assigned.set(9, unassigned[0])
  return cameraPointDefinitions.map((point) => ({ ...point, camera: assigned.get(point.no) || null }))
}

function cameraPointStyle(point) {
  const camera = point.camera
  const x = Number(camera?.map_x ?? camera?.mapX ?? camera?.point_x ?? camera?.longitude_percent ?? point.x)
  const y = Number(camera?.map_y ?? camera?.mapY ?? camera?.point_y ?? camera?.latitude_percent ?? point.y)
  if (Number.isFinite(x) && Number.isFinite(y)) {
    return { left: `${Math.max(4, Math.min(96, x))}%`, top: `${Math.max(6, Math.min(94, y))}%` }
  }
  return { left: '50%', top: '50%' }
}

function regionPathFromPoint(point) {
  if (!point) return ''
  const centerX = Number(point.x) / 100 * 2168
  const centerY = Number(point.y) / 100 * 725
  if (!Number.isFinite(centerX) || !Number.isFinite(centerY)) return ''
  const width = 150
  const height = 76
  const left = Math.max(24, Math.min(2168 - width - 24, centerX - width / 2))
  const top = Math.max(24, Math.min(725 - height - 24, centerY - height / 2))
  const right = left + width
  const bottom = top + height
  return [
    `M${left} ${top + 18}`,
    `L${left + 18} ${top}`,
    `L${right - 26} ${top + 4}`,
    `L${right} ${top + 28}`,
    `L${right - 14} ${bottom - 8}`,
    `L${left + 32} ${bottom}`,
    `L${left} ${bottom - 22}`,
    'Z',
  ].join(' ')
}

function pointsFromRegionPath(path) {
  const values = String(path || '').match(/-?\d+(\.\d+)?/g)?.map(Number) || []
  const points = []
  for (let index = 0; index < values.length; index += 2) {
    points.push({ x: values[index], y: values[index + 1] })
  }
  return points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
}

function regionCalloutFromPath(path, pointNo) {
  const points = pointsFromRegionPath(path)
  if (!points.length) return null
  const minX = Math.min(...points.map((point) => point.x))
  const maxX = Math.max(...points.map((point) => point.x))
  const minY = Math.min(...points.map((point) => point.y))
  const label = `${pointNo}号摄像头监测区域`
  const width = Math.max(170, label.length * 14)
  return {
    label,
    width,
    x: Math.max(16, Math.min(2168 - width - 16, (minX + maxX) / 2 - width / 2)),
    y: Math.max(18, minY - 58),
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
.admin-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}
.status-summary { display: flex; justify-content: flex-end; align-items: center; }
.metric { min-width: 96px; display: inline-flex; align-items: baseline; gap: 8px; padding: 8px 18px; white-space: nowrap; }
.metric + .metric { border-left: 1px solid rgba(96, 151, 191, .18); }
.metric .dot { width: 8px; height: 8px; flex: 0 0 auto; align-self: center; border-radius: 50%; background: #8db2c8; }
.metric .dot.total { box-shadow: 0 0 8px rgba(141, 178, 200, .75); }
.metric .dot.online { background: #48e6bf; box-shadow: 0 0 8px rgba(72, 230, 191, .75); }
.metric .dot.offline { background: #8494a3; }
.metric-num { color: #f2fbff; font-size: 22px; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.metric-label { color: #8db2c8; font-size: 12px; }
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
  gap: 14px;
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
.toolbar-map-entry {
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
  background: linear-gradient(135deg, rgba(23, 116, 155, .88), rgba(10, 59, 88, .86));
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, .10), 0 0 18px rgba(72, 216, 255, .16);
  transition: border-color .18s ease, background .18s ease, color .18s ease;
}
.toolbar-map-entry:hover {
  border-color: rgba(126, 238, 255, .82);
  color: #ffffff;
  background: linear-gradient(135deg, rgba(30, 136, 181, .96), rgba(12, 72, 108, .92));
}
.toolbar-map-entry .el-icon {
  width: 26px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  color: #031825;
  background: #48d8ff;
  font-size: 18px;
}
.status-filter-select {
  width: 116px;
  flex: 0 0 auto;
}
.status-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, .36) inset;
}
.status-filter-select :deep(.el-select__selected-item),
.status-filter-select :deep(.el-select__placeholder) {
  color: #d7edf6;
  font-weight: 700;
}
.status-filter-select :deep(.el-select__caret) {
  color: #8fd4df;
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
  font-size: 15px;
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
  border-color: rgba(64, 158, 255, .66);
  background: #409eff;
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
.action-buttons :deep(.el-button.edit-action),
.action-buttons .edit-action {
  border-color: rgba(66, 164, 224, .50) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .70) !important;
}
.action-buttons :deep(.el-button.delete-action),
.action-buttons .delete-action {
  border-color: rgba(226, 88, 109, .46) !important;
  color: #ffb1bd !important;
  background: rgba(128, 36, 54, .48) !important;
}
.action-buttons :deep(.el-button.edit-action:hover),
.action-buttons .edit-action:hover {
  border-color: rgba(66, 164, 224, .72) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .82) !important;
}
.action-buttons :deep(.el-button.delete-action:hover),
.action-buttons .delete-action:hover {
  border-color: rgba(226, 88, 109, .68) !important;
  color: #ffd5dd !important;
  background: rgba(144, 42, 62, .62) !important;
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
:global(.camera-map-dialog.el-dialog) {
  border: 1px solid rgba(72, 216, 255, .24);
  border-radius: 8px;
  background: #07131a;
  box-shadow: 0 24px 60px rgba(0, 7, 18, .46);
}
:global(.camera-map-dialog .el-dialog__header) {
  margin: 0;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(137, 174, 184, .14);
}
:global(.camera-map-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-weight: 900;
}
:global(.camera-map-dialog .el-dialog__body) {
  padding: 12px;
}
.expanded-map-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 2168 / 725;
  max-height: 84vh;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, .16);
  border-radius: 8px;
  background: #02080d;
}
.expanded-map-stage img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  filter: saturate(1.08) contrast(1.06) brightness(.76);
}
.expanded-map-region-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.expanded-region-fill {
  fill: rgba(67, 220, 255, .14);
  stroke: transparent;
}
.expanded-region-halo {
  fill: none;
  stroke: rgba(81, 229, 255, .48);
  stroke-width: 13;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#camera-device-region-glow);
}
.expanded-region-line {
  fill: none;
  stroke: rgba(126, 238, 255, .96);
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#camera-device-region-glow);
}
.expanded-region-callout rect {
  fill: rgba(7, 42, 55, .86);
  stroke: rgba(126, 238, 255, .74);
  stroke-width: 1.5;
  filter: drop-shadow(0 0 8px rgba(72, 216, 255, .5));
}
.expanded-region-callout text {
  fill: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
  text-anchor: middle;
}
.expanded-map-point {
  position: absolute;
  z-index: 3;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  margin: -14px 0 0 -14px;
  border: 2px solid rgba(255, 255, 255, .62);
  border-radius: 50%;
  color: #fff;
  background: #d93a4b;
  box-shadow: 0 0 0 8px rgba(217, 58, 75, .18), 0 0 16px rgba(217, 58, 75, .72);
  font: 900 14px/1 "Consolas", "Monaco", monospace;
  cursor: pointer;
}
.expanded-map-point.offline {
  background: #526977;
  box-shadow: 0 0 0 7px rgba(82, 105, 119, .16);
}
.expanded-map-point.active {
  width: 34px;
  height: 34px;
  margin: -17px 0 0 -17px;
  color: #041417;
  border-color: rgba(230, 250, 255, .92);
  background: #48d8ff;
  box-shadow: 0 0 0 10px rgba(72, 216, 255, .24), 0 0 24px rgba(72, 216, 255, .88);
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
  position: relative;
  min-height: 58px;
  display: flex;
  align-items: center;
  margin: 0;
  padding: 18px 58px 10px 24px;
}
:global(.camera-config-dialog .el-dialog__title) {
  color: #eef7ff;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
}
:global(.camera-config-dialog .el-dialog__headerbtn) {
  top: 14px;
  right: 18px;
  width: 34px;
  height: 34px;
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
