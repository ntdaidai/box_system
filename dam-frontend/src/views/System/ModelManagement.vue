<template>
  <div class="model-page">
    <header class="page-head">
      <div>
        <h2>模型管理</h2>
        <p>查看边缘推理模型加载状态，必要时手动刷新或重新加载。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadStatus">刷新状态</el-button>
    </header>

    <section class="status-band" :class="{ online: overallLoaded, offline: !overallLoaded }">
      <div class="status-icon"><el-icon><Cpu /></el-icon></div>
      <div>
        <span>模型服务</span>
        <strong>{{ overallLoaded ? '运行中' : '未就绪' }}</strong>
      </div>
      <small>{{ statusText }}</small>
    </section>

    <section class="model-grid">
      <article v-for="model in modelItems" :key="model.key" class="model-card">
        <header>
          <div>
            <span>{{ model.taskLabel }}</span>
            <strong>{{ model.name }}</strong>
          </div>
          <b :class="{ loaded: model.loaded }">{{ model.loaded ? '已加载' : '未加载' }}</b>
        </header>
        <dl>
          <div>
            <dt>模型路径</dt>
            <dd>{{ model.path || '--' }}</dd>
          </div>
          <div>
            <dt>设备</dt>
            <dd>{{ model.device || '--' }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ model.updatedAt || '--' }}</dd>
          </div>
        </dl>
        <div class="card-actions">
          <el-input v-model.trim="reloadPaths[model.key]" clearable placeholder="自定义模型路径，可留空" />
          <el-button :loading="reloadingKey === model.key" @click="reload(model)">重新加载</el-button>
        </div>
      </article>
    </section>

    <el-empty v-if="!loading && !modelItems.length" description="暂无模型状态数据" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, Refresh } from '@element-plus/icons-vue'
import { getModelStatus, reloadModel } from '@/api/camera'

const loading = ref(false)
const modelStatus = ref({ loaded: false, models: {} })
const reloadPaths = ref({})
const reloadingKey = ref('')

const taskLabels = {
  detect: '目标检测',
  classify: '图片分类',
  video: '视频分析',
}

const overallLoaded = computed(() => Boolean(modelStatus.value.loaded))
const statusText = computed(() => modelStatus.value.message || modelStatus.value.status || '状态来自模型服务接口')
const modelItems = computed(() => {
  const models = modelStatus.value.models || {}
  return Object.entries(models).map(([key, value]) => ({
    key,
    taskLabel: taskLabels[key] || key,
    name: value?.name || value?.model_name || `${taskLabels[key] || key}模型`,
    loaded: Boolean(value?.loaded),
    path: value?.path || value?.model_path || '',
    device: value?.device || value?.provider || '',
    updatedAt: value?.updated_at || value?.loaded_at || '',
  }))
})

async function loadStatus() {
  loading.value = true
  try {
    const response = await getModelStatus()
    modelStatus.value = response.data || { loaded: false, models: {} }
  } catch (error) {
    ElMessage.error('获取模型状态失败')
  } finally {
    loading.value = false
  }
}

async function reload(model) {
  reloadingKey.value = model.key
  try {
    await reloadModel(reloadPaths.value[model.key], model.key)
    ElMessage.success('模型重新加载完成')
    await loadStatus()
  } catch (error) {
    ElMessage.error('模型重新加载失败')
  } finally {
    reloadingKey.value = ''
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.model-page {
  min-height: 100%;
  padding: 22px;
  color: #e9f7ff;
  background: linear-gradient(145deg, #071522, #091b2d 58%, #071522);
}

.page-head,
.status-band,
.model-card {
  border: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 8px;
  background: rgba(9, 30, 48, 0.88);
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.page-head h2 {
  margin: 0;
  font-size: 22px;
}

.page-head p {
  margin: 6px 0 0;
  color: #8fa8b8;
}

.status-band {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
  padding: 18px 20px;
}

.status-band.online { border-color: rgba(81, 230, 190, 0.36); }
.status-band.offline { border-color: rgba(255, 109, 123, 0.34); }

.status-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  color: #51e6be;
  border-radius: 8px;
  background: rgba(81, 230, 190, 0.12);
}

.status-band span,
.model-card span,
dt {
  color: #8fa8b8;
  font-size: 13px;
}

.status-band strong {
  display: block;
  margin-top: 4px;
  font-size: 24px;
}

.status-band small {
  margin-left: auto;
  color: #9eb3ba;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.model-card {
  padding: 16px;
}

.model-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.model-card strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
}

.model-card b {
  flex: 0 0 auto;
  padding: 5px 10px;
  border-radius: 6px;
  color: #ff9ca7;
  background: rgba(255, 93, 108, 0.14);
}

.model-card b.loaded {
  color: #51e6be;
  background: rgba(81, 230, 190, 0.13);
}

dl {
  display: grid;
  gap: 10px;
  margin: 18px 0;
}

dd {
  margin: 4px 0 0;
  color: #dcebed;
  word-break: break-all;
}

.card-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}
</style>
