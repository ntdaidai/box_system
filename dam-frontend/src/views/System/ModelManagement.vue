<template>
  <div class="model-page">
    <header class="page-head">
      <div>
        <h2>模型管理</h2>
        <p>模型服务运行控制与能力归类。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadModels">刷新状态</el-button>
    </header>

    <section class="summary-grid">
      <article class="summary-item tone-total">
        <el-icon class="summary-icon"><Files /></el-icon>
        <div class="summary-info">
          <span>模型总数</span>
          <strong>{{ summary.total }}</strong>
        </div>
      </article>
      <article class="summary-item tone-running">
        <el-icon class="summary-icon"><VideoPlay /></el-icon>
        <div class="summary-info">
          <span>运行中</span>
          <strong>{{ summary.running }}</strong>
        </div>
      </article>
      <article class="summary-item tone-framework">
        <el-icon class="summary-icon"><Grid /></el-icon>
        <div class="summary-info">
          <span>框架数量</span>
          <strong>{{ summary.frameworks }}</strong>
        </div>
      </article>
      <article class="summary-item tone-stopped">
        <el-icon class="summary-icon"><VideoPause /></el-icon>
        <div class="summary-info">
          <span>已停止</span>
          <strong>{{ summary.standby }}</strong>
        </div>
      </article>
    </section>

    <section class="toolbar">
      <el-input v-model.trim="filters.keyword" clearable :prefix-icon="Search" placeholder="搜索模型名称或类型" />
      <el-select v-model="filters.capability" clearable placeholder="能力类型">
        <el-option v-for="item in capabilityOptions" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.availability" clearable placeholder="使用状态">
        <el-option label="运行中" value="available" />
        <el-option label="已停止" value="standby" />
      </el-select>
    </section>

    <section v-loading="loading" class="model-list">
      <article v-for="model in paginatedModels" :key="model.id" class="model-card">
        <header>
          <div class="model-icon" :class="modelIconClass(model)">
            <el-icon><component :is="modelIcon(model)" /></el-icon>
          </div>
          <div class="model-headline">
            <h3>{{ model.name }}</h3>
            <div class="model-meta">
              <span v-for="tag in modelBadges(model)" :key="tag.key" :class="`is-${tag.tone}`">
                {{ tag.label }}
              </span>
            </div>
          </div>
          <div class="model-status" :class="modelIconClass(model)">
            <i></i>
            <span>{{ runtimeLabel(model) }}</span>
          </div>
        </header>

        <dl class="model-fields">
          <div>
            <dt>模型架构</dt>
            <dd>{{ model.architecture || '未配置' }}</dd>
          </div>
          <div>
            <dt>业务标签</dt>
            <dd>{{ registryTags(model).length ? `${registryTags(model).length} 个` : '未配置' }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ shortDate(model.updated_at) }}</dd>
          </div>
        </dl>

        <footer>
          <el-button :icon="View" @click="openDetail(model)">详情</el-button>
          <el-button
            type="success"
            :icon="VideoPlay"
            :loading="isActioning(model, 'start')"
            :disabled="!canStart(model) || isAnyActioning(model)"
            @click="controlModel(model, 'start')"
          >
            运行
          </el-button>
          <el-button
            type="danger"
            plain
            :icon="VideoPause"
            :loading="isActioning(model, 'stop')"
            :disabled="!canStop(model) || isAnyActioning(model)"
            @click="controlModel(model, 'stop')"
          >
            停止
          </el-button>
        </footer>
      </article>

      <el-empty v-if="!loading && !filteredModels.length" :description="emptyText" />
    </section>

    <div v-if="filteredModels.length > pageSize" class="model-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        background
        layout="prev, pager, next"
        :page-size="pageSize"
        :total="filteredModels.length"
      />
    </div>

    <el-drawer v-model="detailVisible" size="520px" custom-class="model-detail-drawer" :with-header="false">
      <div v-if="selectedModel" class="detail-panel">
        <header class="detail-head">
          <div class="detail-title">
            <div class="detail-icon" :class="modelIconClass(selectedModel)">
              <el-icon><component :is="modelIcon(selectedModel)" /></el-icon>
            </div>
            <div>
              <span>{{ selectedModel.capability }}</span>
              <h3>{{ selectedModel.name }}</h3>
            </div>
          </div>
          <button class="drawer-close" type="button" @click="detailVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </header>

        <div class="detail-status-row">
          <span class="model-status" :class="modelIconClass(selectedModel)">
            <i></i>
            <span>{{ runtimeLabel(selectedModel) }}</span>
          </span>
          <span v-for="tag in modelBadges(selectedModel)" :key="tag.key">{{ tag.label }}</span>
        </div>

        <section class="detail-section detail-summary">
          <h4>模型说明</h4>
          <p>{{ userDescription(selectedModel) }}</p>
        </section>

        <section class="detail-section">
          <h4>基础信息</h4>
          <dl class="detail-list">
            <div>
              <dt>模型类型</dt>
              <dd>{{ selectedModel.model_type || selectedModel.capability || '通用模型' }}</dd>
            </div>
            <div>
              <dt>运行框架</dt>
              <dd>{{ selectedModel.framework || '未配置' }}</dd>
            </div>
            <div>
              <dt>模型架构</dt>
              <dd>{{ selectedModel.architecture || '未配置' }}</dd>
            </div>
            <div>
              <dt>当前状态</dt>
              <dd>{{ statusExplain(selectedModel) }}</dd>
            </div>
          </dl>
        </section>

        <section class="detail-section" v-if="modelBadges(selectedModel).length">
          <h4>注册标签</h4>
          <div class="detail-tags">
            <span v-for="tag in modelBadges(selectedModel, 12)" :key="tag.key" :class="`is-${tag.tone}`">
              {{ tag.label }}
            </span>
          </div>
        </section>

        <section class="detail-section" v-if="selectedModel.endpoint || selectedModel.container_name || selectedModel.image_name">
          <h4>服务信息</h4>
          <dl class="detail-list">
            <div v-if="selectedModel.endpoint">
              <dt>调用入口</dt>
              <dd>{{ selectedModel.endpoint }}</dd>
            </div>
            <div v-if="selectedModel.container_name">
              <dt>容器</dt>
              <dd>{{ selectedModel.container_name }}</dd>
            </div>
            <div v-if="selectedModel.image_name">
              <dt>镜像</dt>
              <dd>{{ selectedModel.image_name }}</dd>
            </div>
          </dl>
        </section>

        <section class="detail-section" v-if="selectedModel.inputs?.length || selectedModel.outputs?.length">
          <h4>输入输出</h4>
          <dl class="detail-list">
            <div>
              <dt>需要提供</dt>
              <dd>{{ inputText(selectedModel) }}</dd>
            </div>
            <div>
              <dt>可以得到</dt>
              <dd>{{ outputText(selectedModel) }}</dd>
            </div>
          </dl>
        </section>

        <div class="detail-actions">
          <el-button
            type="danger"
            plain
            :icon="VideoPause"
            :loading="isActioning(selectedModel, 'stop')"
            :disabled="!canStop(selectedModel) || isAnyActioning(selectedModel)"
            @click="controlModel(selectedModel, 'stop')"
          >
            停止
          </el-button>
           <el-button
            type="success"
            :icon="VideoPlay"
            :loading="isActioning(selectedModel, 'start')"
            :disabled="!canStart(selectedModel) || isAnyActioning(selectedModel)"
            @click="controlModel(selectedModel, 'start')"
          >
            运行
          </el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatLineRound,
  Close,
  Files,
  Grid,
  Picture,
  Refresh,
  Search,
  VideoPause,
  VideoPlay,
  View,
  Warning,
} from '@element-plus/icons-vue'
import {
  getModelLibrary,
  getModelLibraryDetail,
  startModel,
  stopModel,
} from '@/api/modelLibrary'

const loading = ref(false)
const models = ref([])
const selectedModel = ref(null)
const detailVisible = ref(false)
const currentPage = ref(1)
const pageSize = 8
const actionState = reactive({
  id: null,
  type: '',
})
const loadError = ref('')

const filters = reactive({
  keyword: '',
  capability: '',
  availability: '',
})

const capabilityOptions = computed(() => {
  return [...new Set(models.value.map((item) => item.capability).filter(Boolean))].sort()
})

const filteredModels = computed(() => {
  const keyword = filters.keyword.toLowerCase()
  return models.value.filter((model) => {
    const matchesKeyword = !keyword || [
      model.name,
      model.description,
      model.capability,
      model.model_type,
      model.framework,
      model.architecture,
    ].some((value) => String(value || '').toLowerCase().includes(keyword))
    const matchesCapability = !filters.capability || model.capability === filters.capability
    const isAvailable = model.runtime_status === 'running'
    const matchesAvailability = !filters.availability
      || (filters.availability === 'available' && isAvailable)
      || (filters.availability === 'standby' && !isAvailable)
    return matchesKeyword && matchesCapability && matchesAvailability
  })
})

const summary = computed(() => {
  const total = filteredModels.value.length
  const running = filteredModels.value.filter((item) => item.runtime_status === 'running').length
  const frameworks = new Set(filteredModels.value.map((item) => item.framework).filter(Boolean)).size
  const standby = filteredModels.value.filter((item) => item.runtime_status !== 'running').length
  return { total, running, frameworks, standby }
})

const paginatedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredModels.value.slice(start, start + pageSize)
})

const emptyText = computed(() => loadError.value || '暂无模型能力')

function modelIcon(model) {
  if (model.capability === '文本推理') return ChatLineRound
  if (model.runtime_status === 'error') return Warning
  return Picture
}

function modelIconClass(model) {
  if (model.runtime_status === 'running') return 'is-ready'
  if (model.runtime_status === 'error') return 'is-error'
  return 'is-idle'
}

function userDescription(model) {
  const text = model.description || ''
  if (text && text !== '暂无说明') return text
  if (model.capability === '视觉语言模型') return '用于结合图片和文字进行现场情况分析。'
  if (model.capability === '文本推理') return '用于生成研判说明、处置建议和报告内容。'
  if (model.capability === '图像分类') return '用于判断图片或视频画面中的灾害类别。'
  if (model.capability === '目标检测') return '用于识别画面中的重点目标或异常区域。'
  return '用于辅助平台完成智能分析。'
}

function statusExplain(model) {
  if (model.runtime_status === 'running') return '当前可以直接调用。'
  if (model.runtime_status === 'error') return '当前不可用，需要管理员检查服务。'
  if (['starting', 'stopping'].includes(model.runtime_status)) return '服务状态正在变化，请稍后刷新。'
  return '当前未启动，需要管理员启用后才能调用。'
}

function runtimeLabel(model) {
  if (model.runtime_status === 'running') return '运行中'
  if (model.runtime_status === 'starting') return '启动中'
  if (model.runtime_status === 'stopping') return '停止中'
  if (model.runtime_status === 'error') return '异常'
  return '已停止'
}

function registryTags(model) {
  const value = model?.tags
  if (Array.isArray(value)) return value.filter(Boolean).map((item) => String(item).trim()).filter(Boolean)
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .filter(([, enabled]) => enabled !== false && enabled !== null && enabled !== undefined)
      .map(([key, label]) => (typeof label === 'string' ? label : key))
      .map((item) => String(item).trim())
      .filter(Boolean)
  }
  return []
}

function tagLabel(value) {
  const text = String(value || '').trim()
  const labels = {
    person_event: '人员事件',
    object_detection: '目标检测',
    specialized: '专用模型',
    baseline: '基线模型',
    coco: 'COCO',
    boat: '船只',
    swimmer: '涉水人员',
    person: '人员',
    crowd: '人群',
  }
  return labels[text] || text
}

function modelBadges(model, limit = 6) {
  const source = [
    { key: 'type', label: model?.model_type || model?.capability, tone: 'type' },
    { key: 'framework', label: model?.framework, tone: 'framework' },
    { key: 'architecture', label: model?.architecture, tone: 'architecture' },
    { key: 'size', label: model?.model_size, tone: 'size' },
    ...registryTags(model).map((tag, index) => ({
      key: `tag-${index}-${tag}`,
      label: tagLabel(tag),
      tone: 'custom',
    })),
  ]

  const seen = new Set()
  const badges = source.filter((item) => {
    const label = String(item.label || '').trim()
    const normalized = label.toLowerCase()
    if (!label || seen.has(normalized)) return false
    seen.add(normalized)
    item.label = label
    return true
  })

  if (badges.length <= limit) return badges
  return [
    ...badges.slice(0, limit - 1),
    { key: 'more', label: `+${badges.length - limit + 1}`, tone: 'more' },
  ]
}

function shortDate(value) {
  if (!value) return '未记录'
  const text = String(value)
  const matched = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (matched) return `${matched[2]}-${matched[3]}`
  return text.slice(0, 10) || '未记录'
}

function canStart(model) {
  return Boolean(model?.has_binding) && !['running', 'starting', 'stopping'].includes(model?.runtime_status)
}

function canStop(model) {
  return Boolean(model?.has_binding) && ['running', 'starting', 'error'].includes(model?.runtime_status)
}

function isActioning(model, type) {
  return actionState.id === model?.id && actionState.type === type
}

function isAnyActioning(model) {
  return actionState.id === model?.id && Boolean(actionState.type)
}

function fieldTypes(fields = []) {
  const types = new Set(fields.map((field) => field.type))
  const labels = []
  if (types.has('image')) labels.push('图片')
  if (types.has('text')) labels.push('文字')
  if (types.has('json')) labels.push('结构化信息')
  if (types.has('float') || types.has('integer')) labels.push('参数')
  return labels.length ? labels.join('、') : '未配置'
}

function inputText(model) {
  return fieldTypes(model.inputs)
}

function outputText(model) {
  return fieldTypes(model.outputs).replace('参数', '分析结果')
}

function normalizeStatusPayload(result = {}) {
  return {
    runtime_status: result.runtime_status,
    status_label: result.status_label,
    status_level: result.status_level,
    health_state: result.health_state,
    container_status: result.container_status,
    endpoint: result.endpoint || result.inference_url,
  }
}

function updateModelStatus(modelId, nextStatus) {
  const cleanStatus = Object.fromEntries(
    Object.entries(nextStatus).filter(([, value]) => value !== undefined && value !== null),
  )
  models.value = models.value.map((item) => (item.id === modelId ? { ...item, ...cleanStatus } : item))
  if (selectedModel.value?.id === modelId) {
    selectedModel.value = { ...selectedModel.value, ...cleanStatus }
  }
}

async function loadModels() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getModelLibrary({ page_size: 100 })
    const payload = response.data
    models.value = Array.isArray(payload) ? payload : (payload?.records || response.records || [])
  } catch (error) {
    loadError.value = '模型库接口暂时不可用'
    ElMessage.error('模型库读取失败')
  } finally {
    loading.value = false
  }
}

async function openDetail(model) {
  detailVisible.value = true
  selectedModel.value = model
  try {
    const response = await getModelLibraryDetail(model.id)
    selectedModel.value = response.data || model
  } catch (error) {
    ElMessage.warning('详情读取失败，已显示基础信息')
  }
}

async function controlModel(model, type) {
  actionState.id = model.id
  actionState.type = type
  try {
    const response = type === 'start' ? await startModel(model.id) : await stopModel(model.id)
    const result = response.data || {}
    updateModelStatus(model.id, normalizeStatusPayload(result))
    ElMessage.success(type === 'start' ? '模型已启动' : '模型已停止')
  } catch (error) {
    ElMessage.error(type === 'start' ? '模型启动失败' : '模型停止失败')
  } finally {
    actionState.id = null
    actionState.type = ''
  }
}

watch(
  () => [filters.keyword, filters.capability, filters.availability],
  () => {
    currentPage.value = 1
  },
)

watch(
  () => filteredModels.value.length,
  (total) => {
    const maxPage = Math.max(1, Math.ceil(total / pageSize))
    if (currentPage.value > maxPage) {
      currentPage.value = maxPage
    }
  },
)

onMounted(loadModels)
</script>

<style scoped>
.model-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}

.page-head,
.toolbar,
.model-card {
  border: 1px solid rgba(21, 160, 218, 0.18);
  border-radius: 8px;
  background: rgba(8, 29, 43, 0.9);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
}

.page-head h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.page-head p {
  margin: 6px 0 0;
  color: #93bad0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.summary-item {
  position: relative;
  min-height: 104px;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  overflow: hidden;
  padding: 16px 18px;
  border: 1px solid rgba(104, 161, 200, 0.26);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(28, 68, 103, 0.72), rgba(8, 25, 42, 0.92)),
    #0b1d30;
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.22);
}

.summary-item::after {
  content: "";
  position: absolute;
  inset: auto 16px 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: #48d8ff;
  opacity: 0.72;
}

.summary-icon {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  color: #48d8ff;
  background: rgba(72, 216, 255, 0.12);
  font-size: 25px;
  box-shadow: inset 0 0 0 1px rgba(72, 216, 255, 0.18);
}

.summary-item.tone-running::after {
  background: #62d7b1;
}

.summary-item.tone-running .summary-icon {
  color: #62d7b1;
  background: rgba(98, 215, 177, 0.12);
  box-shadow: inset 0 0 0 1px rgba(98, 215, 177, 0.22);
}

.summary-item.tone-framework::after {
  background: #f0c75d;
}

.summary-item.tone-framework .summary-icon {
  color: #f0c75d;
  background: rgba(240, 199, 93, 0.13);
  box-shadow: inset 0 0 0 1px rgba(240, 199, 93, 0.22);
}

.summary-item.tone-stopped::after {
  background: #8ab7ff;
}

.summary-item.tone-stopped .summary-icon {
  color: #8ab7ff;
  background: rgba(138, 183, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(138, 183, 255, 0.2);
}

.summary-info {
  min-width: 0;
}

.summary-item span,
.detail-head span,
.detail-section h4,
.detail-list dt {
  color: #8fb6cb;
  font-size: 13px;
}

.summary-item strong {
  display: block;
  margin-top: 6px;
  color: #f6fbff;
  font-size: 34px;
  font-weight: 700;
  line-height: 36px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 150px 150px;
  gap: 12px;
  margin-top: 18px;
  padding: 14px;
  border-color: rgba(104, 161, 200, 0.22);
  background: #0b1d30;
}

.model-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.model-pagination {
  display: flex;
  justify-content: center;
  margin-top: 14px;
  padding: 18px;
}

.model-pagination :deep(.el-pagination) {
  gap: 12px;
  justify-content: center;
}

.model-pagination :deep(.el-pagination .btn-prev),
.model-pagination :deep(.el-pagination .btn-next),
.model-pagination :deep(.el-pager li) {
  width: 48px;
  height: 42px;
  min-width: 48px;
  margin: 0;
  border: 1px solid #214766;
  border-radius: 5px;
  color: #7893aa;
  background: #0a1a2c;
}

.model-pagination :deep(.el-pager) {
  display: flex;
  gap: 10px;
}

.model-pagination :deep(.el-pager li.is-active) {
  border-color: #61b5ff;
  color: #fff;
  background: #3d8ed8;
}

.model-pagination :deep(.el-pagination .btn-prev:disabled),
.model-pagination :deep(.el-pagination .btn-next:disabled) {
  border-color: rgba(33, 71, 102, 0.55);
  color: rgba(120, 147, 170, 0.45);
  background: rgba(10, 26, 44, 0.58);
}

.model-card {
  display: flex;
  min-height: 214px;
  flex-direction: column;
  padding: 16px;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.model-card:hover {
  border-color: rgba(22, 192, 255, 0.34);
  background: rgba(9, 35, 52, 0.94);
  transform: translateY(-1px);
}

.model-card header {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  grid-template-areas:
    "icon title status"
    "icon meta meta";
  align-items: start;
  gap: 12px;
}

.model-icon {
  grid-area: icon;
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  font-size: 20px;
}

.model-icon.is-ready {
  color: #4fe5b7;
  background: rgba(79, 229, 183, 0.12);
}

.model-icon.is-idle {
  color: #91b9cf;
  background: rgba(84, 154, 196, 0.14);
}

.model-icon.is-error {
  color: #ff9ca7;
  background: rgba(255, 108, 123, 0.12);
}

.model-headline {
  display: contents;
  min-width: 0;
}

.model-headline h3 {
  grid-area: title;
  margin: 0;
  overflow: hidden;
  font-size: 18px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-word;
}

.model-meta {
  grid-area: meta;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
  max-height: 58px;
  overflow: hidden;
}

.model-meta span {
  flex: 0 1 max-content;
  max-width: 160px;
  min-width: 0;
  padding: 4px 9px;
  overflow: hidden;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 8px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.52);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-meta span.is-type,
.detail-tags span.is-type {
  color: #dff6ff;
  background: rgba(18, 113, 153, 0.5);
}

.model-meta span.is-framework,
.detail-tags span.is-framework {
  color: #b8e6ff;
}

.model-meta span.is-architecture,
.detail-tags span.is-architecture {
  color: #b9d2ff;
}

.model-meta span.is-size,
.detail-tags span.is-size {
  color: #c8e7d7;
}

.model-meta span.is-custom,
.detail-tags span.is-custom {
  color: #cbd8e5;
  background: rgba(8, 41, 64, 0.62);
}

.model-meta span.is-more,
.detail-tags span.is-more {
  color: #fff;
  background: rgba(61, 142, 216, 0.42);
}

.model-status {
  grid-area: status;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 8px;
  color: #91b9cf;
  background: rgba(16, 63, 94, 0.42);
  font-size: 13px;
  white-space: nowrap;
}

.model-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.model-status.is-ready {
  border-color: rgba(79, 229, 183, 0.24);
  color: #4fe5b7;
  background: rgba(24, 106, 89, 0.32);
}

.model-status.is-error {
  border-color: rgba(255, 156, 167, 0.28);
  color: #ff9ca7;
  background: rgba(117, 43, 56, 0.28);
}

.model-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 0;
}

.model-fields div {
  min-width: 0;
  min-height: 66px;
  padding: 10px 11px;
  border: 1px solid rgba(84, 175, 222, 0.14);
  border-radius: 8px;
  background: rgba(4, 19, 31, 0.34);
}

.model-fields dt {
  color: #91bdd5;
  font-size: 13px;
}

.model-fields dd {
  margin-top: 6px;
  margin-left: 0;
  overflow: hidden;
  color: #f0faff;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-card footer {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  align-items: center;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid rgba(84, 175, 222, 0.14);
}

.detail-panel {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  color: #e9f7ff;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(84, 175, 222, 0.16);
}

.detail-title {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.detail-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  font-size: 20px;
}

.detail-icon.is-ready {
  color: #4fe5b7;
  background: rgba(79, 229, 183, 0.12);
}

.detail-icon.is-idle {
  color: #91b9cf;
  background: rgba(84, 154, 196, 0.14);
}

.detail-icon.is-error {
  color: #ff9ca7;
  background: rgba(255, 108, 123, 0.12);
}

.detail-panel h3 {
  margin: 6px 0 0;
  overflow: hidden;
  font-size: 22px;
  line-height: 1.3;
  text-overflow: ellipsis;
}

.drawer-close {
  width: 34px;
  height: 34px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 8px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.42);
  cursor: pointer;
}

.drawer-close:hover {
  border-color: rgba(22, 192, 255, 0.34);
  color: #e9f7ff;
}

.detail-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 0 2px;
}

.detail-status-row > span:not(.model-status) {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 8px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.42);
  font-size: 13px;
}

.detail-section {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(21, 160, 218, 0.18);
  border-radius: 8px;
  background: rgba(8, 29, 43, 0.8);
}

.detail-section h4 {
  margin: 0 0 8px;
  font-weight: 600;
}

.detail-summary p {
  margin: 0;
  color: #d9edf7;
  font-size: 15px;
  line-height: 1.65;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tags span {
  max-width: 100%;
  padding: 5px 10px;
  overflow: hidden;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 8px;
  color: #bdd9e9;
  background: rgba(16, 63, 94, 0.52);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-list {
  margin: 0;
}

.detail-list div {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 12px;
  min-height: 38px;
  align-items: center;
  padding: 9px 0;
  border-top: 1px solid rgba(84, 175, 222, 0.12);
}

.detail-list div:first-child {
  border-top: 0;
}

.detail-list dd {
  margin: 0;
  overflow: hidden;
  color: #eef9ff;
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
}

.detail-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: auto;
  padding-top: 16px;
}

:deep(.model-detail-drawer) {
  background: #081824;
}

:deep(.detail-actions .el-button) {
  margin-left: 0;
}

@media (max-width: 1500px) {
  .model-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .model-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .summary-grid,
  .toolbar,
  .model-fields,
  .detail-actions {
    grid-template-columns: 1fr;
  }

  .model-list {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .model-card header {
    grid-template-columns: 42px minmax(0, 1fr);
    grid-template-areas:
      "icon title"
      "meta meta"
      "status status";
  }

  .model-status {
    justify-self: start;
  }

  .model-meta {
    flex-wrap: wrap;
  }

  .detail-list div {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .model-card footer {
    align-items: stretch;
    flex-direction: column;
  }

  .model-card footer .el-button {
    width: 100%;
    margin-left: 0;
  }

  .model-pagination {
    justify-content: center;
  }
}
</style>
