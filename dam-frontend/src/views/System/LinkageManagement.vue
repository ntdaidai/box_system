<template>
  <div class="linkage-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 联动系统</p>
        <h2>联动系统</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
    </header>

    <el-tabs v-model="activeModule" class="module-tabs" @tab-change="refreshCurrent">
      <el-tab-pane label="联动设备" name="devices">
        <section class="summary-grid">
          <article class="summary-card">
            <span>广播设备</span>
            <strong>{{ broadcastDevices.length }}</strong>
            <em>{{ onlineBroadcastCount }} 在线</em>
          </article>
          <article class="summary-card">
            <span>无人机</span>
            <strong>{{ droneDevices.length }}</strong>
            <em>{{ onlineDroneCount }} 在线</em>
          </article>
          <article class="summary-card">
            <span>广播模板</span>
            <strong>{{ broadcastTemplates.length }}</strong>
            <em>{{ enabledTemplateCount }} 启用</em>
          </article>
        </section>

        <el-tabs v-model="activeDevice" class="sub-tabs">
          <el-tab-pane label="广播" name="broadcast">
            <section class="panel" v-loading="loading">
              <header class="panel-header">
                <div>
                  <h3>广播设备</h3>
                  <span>用于一键喊话、自动播报和事件处置动作</span>
                </div>
              </header>
              <el-table :data="broadcastDevices" row-key="id" empty-text="暂无广播设备" class="data-table">
                <el-table-column label="设备名称" min-width="180">
                  <template #default="{ row }">
                    <div class="name-cell">
                      <strong>{{ row.name }}</strong>
                      <small>{{ row.description || '暂无描述' }}</small>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="运行状态" width="130">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'ONLINE' ? 'success' : 'danger'">
                      {{ row.status === 'ONLINE' ? '在线' : '离线' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="启用状态" width="130">
                  <template #default="{ row }">
                    <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </section>

            <section class="sub-panel">
              <header class="panel-header compact">
                <div>
                  <h3>播报模板</h3>
                  <span>规则触发后可复用的播报内容</span>
                </div>
              </header>
              <el-table :data="broadcastTemplates" row-key="id" empty-text="暂无广播模板" class="data-table compact-table">
                <el-table-column prop="name" label="模板名称" min-width="160" />
                <el-table-column prop="content" label="播报文本" min-width="300" show-overflow-tooltip />
                <el-table-column label="启用状态" width="110">
                  <template #default="{ row }">{{ row.enabled === false ? '停用' : '启用' }}</template>
                </el-table-column>
              </el-table>
            </section>
          </el-tab-pane>

          <el-tab-pane label="无人机" name="drone">
            <section class="panel" v-loading="loading">
              <header class="panel-header">
                <div>
                  <h3>无人机</h3>
                  <span>{{ workspaceLabel }}</span>
                </div>
                <el-button plain @click="goDroneMonitor">进入无人机监测</el-button>
              </header>

              <el-table :data="droneDevices" row-key="device_sn" empty-text="暂无无人机设备" class="data-table">
                <el-table-column label="设备名称" min-width="190">
                  <template #default="{ row }">
                    <div class="name-cell">
                      <strong>{{ row.nickname || row.device_name || '未命名无人机' }}</strong>
                      <small>{{ row.device_sn || '--' }}</small>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="设备类型" min-width="150">
                  <template #default="{ row }">{{ droneTypeLabel(row.domain) }}</template>
                </el-table-column>
                <el-table-column label="运行状态" width="130">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'online' ? 'success' : 'danger'">
                      {{ row.status === 'online' ? '在线' : '离线' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="固件版本" min-width="140">
                  <template #default="{ row }">{{ row.firmware_version || '--' }}</template>
                </el-table-column>
                <el-table-column label="工作空间" min-width="180">
                  <template #default="{ row }">{{ row.workspace_name || workspaceName || '--' }}</template>
                </el-table-column>
              </el-table>

              <el-alert
                v-if="droneError"
                class="service-alert"
                type="warning"
                :closable="false"
                show-icon
                :title="droneError"
              />
            </section>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <el-tab-pane label="联动规则" name="rules">
        <InformationConfig embedded />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import InformationConfig from '@/views/Monitor/InformationConfig.vue'
import { getBroadcastDevices, getBroadcastTemplates } from '@/api/broadcast'
import {
  dijLogin,
  getBoundDevices,
  getCurrentWorkspace,
  getDroneDevices,
} from '@/api/drone'

const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'

const router = useRouter()
const activeModule = ref('devices')
const activeDevice = ref('broadcast')
const loading = ref(false)
const broadcastDevices = ref([])
const broadcastTemplates = ref([])
const droneDevices = ref([])
const workspaceId = ref('')
const workspaceName = ref('')
const droneError = ref('')

const onlineBroadcastCount = computed(() => broadcastDevices.value.filter(item => item.status === 'ONLINE').length)
const enabledTemplateCount = computed(() => broadcastTemplates.value.filter(item => item.enabled !== false).length)
const onlineDroneCount = computed(() => droneDevices.value.filter(item => item.status === 'online').length)
const workspaceLabel = computed(() => workspaceName.value ? `DJI 工作空间：${workspaceName.value}` : '从 DJI 项目读取已绑定和在线无人机')

async function refreshCurrent() {
  if (activeModule.value === 'rules') return
  loading.value = true
  try {
    await Promise.all([loadBroadcast(), loadDrones()])
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

async function ensureDijSession() {
  if (localStorage.getItem('dij_token')) return
  const res = await dijLogin(DIJ_USERNAME, DIJ_PASSWORD)
  const token = res.data?.access_token || res.data?.token
  if (token) localStorage.setItem('dij_token', token)
}

async function loadDrones() {
  droneError.value = ''
  try {
    await ensureDijSession()
    const workspaceRes = await getCurrentWorkspace()
    const workspace = workspaceRes.data || {}
    workspaceId.value = workspace.workspace_id || workspace.id || ''
    workspaceName.value = workspace.workspace_name || workspace.name || ''
    if (!workspaceId.value) throw new Error('未获取到 DJI 工作空间')

    const topoRes = await getDroneDevices(workspaceId.value)
    const topology = Array.isArray(topoRes.data) ? topoRes.data : []
    const drones = extractDrones(topology)
    if (drones.length) {
      droneDevices.value = drones
      return
    }

    const boundRes = await getBoundDevices(workspaceId.value, { page: 1, page_size: 50, domain: 0 })
    droneDevices.value = (boundRes.data?.list || []).map(normalizeDrone)
  } catch (error) {
    droneDevices.value = []
    droneError.value = error.message || 'DJI 设备信息暂时不可达，请检查 dij 后端服务'
  }
}

function extractDrones(topology) {
  const map = new Map()
  for (const node of topology) {
    addDroneIfNeeded(map, node)
    const child = node?.children
    if (Array.isArray(child)) {
      child.forEach(item => addDroneIfNeeded(map, item))
    } else if (child && typeof child === 'object') {
      addDroneIfNeeded(map, child)
    }
    if (node?.child_device_sn && !map.has(node.child_device_sn)) {
      addDroneIfNeeded(map, {
        device_sn: node.child_device_sn,
        device_name: `${node.device_name || '遥控器'} 飞行器`,
        nickname: node.nickname || node.device_name,
        domain: 0,
        status: node.status,
        firmware_version: node.firmware_version,
        workspace_id: node.workspace_id,
        workspace_name: node.workspace_name,
      })
    }
  }
  return Array.from(map.values())
}

function addDroneIfNeeded(map, item) {
  if (!item) return
  const isDrone = Number(item.domain) === 0
  const sn = item.device_sn || item.sn
  if (!isDrone || !sn || map.has(sn)) return
  map.set(sn, normalizeDrone(item))
}

function normalizeDrone(item) {
  return {
    ...item,
    device_sn: item.device_sn || item.sn || '',
    status: item.status === true || item.status === 'online' || item.status === 'ONLINE' ? 'online' : 'offline',
  }
}

function droneTypeLabel(domain) {
  const value = Number(domain)
  if (value === 0) return '飞行器'
  if (value === 2) return '遥控器'
  if (value === 3) return '机场'
  return '无人机设备'
}

function goDroneMonitor() {
  router.push('/system/drone')
}

watch(activeDevice, () => {
  if (activeModule.value === 'devices') refreshCurrent()
})

onMounted(refreshCurrent)
</script>

<style scoped>
.linkage-page { min-height: 100%; padding: 22px; color: #d9e8f8; background: #071422; }
.page-header,
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }
.page-header h2,
.panel-header h3 { margin: 0; color: #f3f8fd; letter-spacing: 0; }
.page-header h2 { font-size: 25px; }
.panel-header h3 { font-size: 18px; }
.panel-header span { display: block; margin-top: 6px; color: #8fa8bf; font-size: 13px; }
.module-tabs { margin-top: 16px; }
.module-tabs :deep(.el-tabs__item) { color: #9fb8ce; font-size: 16px; font-weight: 700; }
.module-tabs :deep(.el-tabs__item.is-active) { color: #74d7ff; }
.module-tabs :deep(.el-tabs__active-bar) { height: 3px; border-radius: 999px; background-color: #43c7f4; }
.module-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: rgba(96,151,191,.2); }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(170px, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card {
  min-height: 104px;
  padding: 16px 18px;
  display: grid;
  align-content: center;
  gap: 6px;
  border: 1px solid rgba(96,151,191,.24);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(14, 39, 62, .92), rgba(8, 26, 43, .92));
}
.summary-card span { color: #91aec6; font-size: 13px; }
.summary-card strong { color: #f3f8fd; font-size: 30px; line-height: 34px; }
.summary-card em { color: #6fe3d0; font-style: normal; font-size: 13px; }
.sub-tabs { margin-top: 4px; }
.sub-tabs :deep(.el-tabs__header) { margin: 0 0 14px; }
.sub-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.sub-tabs :deep(.el-tabs__nav) {
  padding: 4px;
  border: 1px solid rgba(84, 148, 193, .34);
  border-radius: 8px;
  background: #0d2740;
}
.sub-tabs :deep(.el-tabs__item) {
  min-width: 92px;
  height: 34px;
  padding: 0 18px;
  color: #9fbbd3;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 700;
}
.sub-tabs :deep(.el-tabs__item.is-active) { color: #061827; background: #38d7de; }
.sub-tabs :deep(.el-tabs__active-bar) { display: none; }
.panel,
.sub-panel {
  padding: 20px 22px;
  border: 1px solid rgba(96,151,191,.24);
  border-radius: 8px;
  background: #0b1d30;
}
.sub-panel { margin-top: 16px; padding-top: 16px; }
.panel-header.compact { margin-bottom: 12px; }
.data-table { margin-top: 16px; border-radius: 6px; overflow: hidden; background: #0a1d30; }
.compact-table { margin-top: 12px; }
.data-table :deep(.el-table__inner-wrapper::before) { background: rgba(149, 190, 220, .12); }
.data-table :deep(th.el-table__cell) { height: 52px; background: #122b45; color: #d6e8f8; font-size: 14px; font-weight: 700; }
.data-table :deep(tr),
.data-table :deep(td.el-table__cell) { background: #0a1d30; color: #d7e8f8; }
.data-table :deep(th.el-table__cell),
.data-table :deep(td.el-table__cell) { border-bottom-color: rgba(149, 190, 220, .12); }
.data-table :deep(td.el-table__cell) { height: 78px; }
.data-table :deep(.el-table__row:hover > td.el-table__cell) { background: #102940; }
.name-cell { display: grid; gap: 6px; }
.name-cell strong { color: #f3f8fd; font-size: 15px; }
.name-cell small { color: #829bb3; font-size: 12px; }
.service-alert { margin-top: 14px; }
.linkage-page :deep(.el-button) { min-height: 36px; font-weight: 700; }
@media (max-width: 900px) {
  .linkage-page { padding: 12px; }
  .page-header,
  .panel-header { align-items: flex-start; flex-direction: column; }
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
