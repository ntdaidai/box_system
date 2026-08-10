<template>
  <div class="linkage-page">
    <header class="page-header">
      <div>
        <p>系统管理 / 联动系统</p>
        <h2>{{ pageTitle }}</h2>
      </div>
      <el-button v-if="activeModule === 'devices'" :icon="Refresh" :loading="loading" @click="refreshCurrent">刷新</el-button>
    </header>

    <template v-if="activeModule === 'devices'">
      <section class="summary-grid">
        <article class="summary-card">
          <span>广播设备</span>
          <strong>{{ broadcastDevices.length }}</strong>
          <em>{{ onlineBroadcastCount }} 在线</em>
        </article>
        <article class="summary-card">
          <span>广播模板</span>
          <strong>{{ broadcastTemplates.length }}</strong>
          <em>{{ enabledTemplateCount }} 启用</em>
        </article>
      </section>

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
    </template>

    <InformationConfig v-else embedded />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import InformationConfig from '@/views/Monitor/InformationConfig.vue'
import { getBroadcastDevices, getBroadcastTemplates } from '@/api/broadcast'

const route = useRoute()

function routeLinkageModule() {
  if (route.meta?.linkageModule) return route.meta.linkageModule
  return route.path.endsWith('/rules') ? 'rules' : 'devices'
}

const activeModule = ref(routeLinkageModule())
const loading = ref(false)
const broadcastDevices = ref([])
const broadcastTemplates = ref([])

const onlineBroadcastCount = computed(() => broadcastDevices.value.filter(item => item.status === 'ONLINE').length)
const enabledTemplateCount = computed(() => broadcastTemplates.value.filter(item => item.enabled !== false).length)
const pageTitle = computed(() => activeModule.value === 'rules' ? '联动规则' : '联动设备')

async function refreshCurrent() {
  if (activeModule.value === 'rules') return
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

watch(() => route.path, () => {
  const nextModule = routeLinkageModule()
  if (activeModule.value !== nextModule) activeModule.value = nextModule
  if (nextModule === 'devices') refreshCurrent()
})

onMounted(() => {
  if (activeModule.value === 'devices') refreshCurrent()
})
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
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(170px, 1fr)); gap: 12px; margin: 16px 0 14px; }
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
.linkage-page :deep(.el-button) { min-height: 36px; font-weight: 700; }
@media (max-width: 900px) {
  .linkage-page { padding: 12px; }
  .page-header,
  .panel-header { align-items: flex-start; flex-direction: column; }
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
