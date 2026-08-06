<template>
  <div class="model-page">
    <header class="page-head">
      <div>
        <h2>模型管理</h2>
        <p>查看平台当前可使用的智能分析能力。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadModels">刷新</el-button>
    </header>

    <section class="summary-grid">
      <div class="summary-item">
        <span>全部能力</span>
        <strong>{{ summary.total }}</strong>
      </div>
      <div class="summary-item available">
        <span>可直接使用</span>
        <strong>{{ summary.running }}</strong>
      </div>
      <div class="summary-item">
        <span>图像分析</span>
        <strong>{{ summary.vision }}</strong>
      </div>
      <div class="summary-item attention">
        <span>需要检查</span>
        <strong>{{ summary.attention }}</strong>
      </div>
    </section>

    <section class="toolbar">
      <el-input
        v-model.trim="filters.keyword"
        clearable
        :prefix-icon="Search"
        placeholder="搜索能力名称或用途"
        @clear="loadModels"
      />
      <el-select v-model="filters.capability" clearable placeholder="能力类型">
        <el-option v-for="item in capabilityOptions" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.availability" clearable placeholder="使用状态">
        <el-option label="可使用" value="available" />
        <el-option label="需检查" value="attention" />
      </el-select>
    </section>

    <section v-loading="loading" class="model-list">
      <article v-for="model in filteredModels" :key="model.id" class="model-card">
        <header>
          <div class="model-icon" :class="modelIconClass(model)">
            <el-icon><component :is="modelIcon(model)" /></el-icon>
          </div>
          <div class="model-headline">
            <h3>{{ model.name }}</h3>
            <p>{{ userDescription(model) }}</p>
          </div>
          <el-tag :type="model.status_level" effect="dark" round>
            {{ model.status_label }}
          </el-tag>
        </header>

        <div class="scenario-band">
          <span>{{ model.capability }}</span>
          <strong>{{ scenarioText(model) }}</strong>
        </div>

        <footer>
          <el-button :icon="View" @click="openDetail(model)">查看用途</el-button>
          <el-button
            type="primary"
            plain
            :icon="Connection"
            :loading="checkingId === model.id"
            @click="testHealth(model)"
          >
            检查可用性
          </el-button>
        </footer>
      </article>

      <el-empty v-if="!loading && !filteredModels.length" :description="emptyText" />
    </section>

    <el-drawer v-model="detailVisible" size="480px" custom-class="model-detail-drawer" :with-header="false">
      <div v-if="selectedModel" class="detail-panel">
        <header>
          <div>
            <span>{{ selectedModel.capability }}</span>
            <h3>{{ selectedModel.name }}</h3>
          </div>
          <el-tag :type="selectedModel.status_level" effect="dark" round>
            {{ selectedModel.status_label }}
          </el-tag>
        </header>

        <section class="detail-section purpose">
          <h4>主要用途</h4>
          <p>{{ userDescription(selectedModel) }}</p>
        </section>

        <section class="detail-section">
          <h4>适合处理</h4>
          <div class="plain-tags">
            <span v-for="item in scenarioTags(selectedModel)" :key="item">{{ item }}</span>
          </div>
        </section>

        <section class="detail-section">
          <h4>当前状态</h4>
          <p>{{ statusExplain(selectedModel) }}</p>
        </section>

        <section class="detail-section" v-if="selectedModel.inputs?.length || selectedModel.outputs?.length">
          <h4>输入输出</h4>
          <div class="io-summary">
            <div>
              <span>需要提供</span>
              <strong>{{ inputText(selectedModel) }}</strong>
            </div>
            <div>
              <span>可以得到</span>
              <strong>{{ outputText(selectedModel) }}</strong>
            </div>
          </div>
        </section>

        <el-button
          type="primary"
          class="detail-action"
          :icon="Connection"
          :loading="checkingId === selectedModel.id"
          @click="testHealth(selectedModel)"
        >
          检查可用性
        </el-button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Connection, Picture, Refresh, Search, View, Warning } from '@element-plus/icons-vue'
import { checkModelHealth, getModelLibrary, getModelLibraryDetail } from '@/api/modelLibrary'

const loading = ref(false)
const models = ref([])
const selectedModel = ref(null)
const detailVisible = ref(false)
const checkingId = ref(null)
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
      scenarioText(model),
    ].some((value) => String(value || '').toLowerCase().includes(keyword))
    const matchesCapability = !filters.capability || model.capability === filters.capability
    const isAvailable = model.runtime_status === 'running'
    const matchesAvailability = !filters.availability
      || (filters.availability === 'available' && isAvailable)
      || (filters.availability === 'attention' && !isAvailable)
    return matchesKeyword && matchesCapability && matchesAvailability
  })
})

const summary = computed(() => {
  const total = filteredModels.value.length
  const running = filteredModels.value.filter((item) => item.runtime_status === 'running').length
  const vision = filteredModels.value.filter((item) => ['图像分类', '目标检测', '图文理解'].includes(item.capability)).length
  const attention = filteredModels.value.filter((item) => item.runtime_status !== 'running').length
  return { total, running, vision, attention }
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
  if (model.capability === '图文理解') return '用于结合图片和文字进行现场情况分析。'
  if (model.capability === '文本推理') return '用于生成研判说明、处置建议和报告内容。'
  if (model.capability === '图像分类') return '用于判断图片或视频画面中的灾害类别。'
  if (model.capability === '目标检测') return '用于识别画面中的重点目标或异常区域。'
  return '用于辅助平台完成智能分析。'
}

function scenarioText(model) {
  const text = `${model.name || ''} ${model.description || ''}`
  if (/默认|ImageNet/i.test(text)) return '模型对照与通用识别'
  if (/灾害|滑坡|泥石流|洪水|地震/.test(text)) return '灾害巡查与风险识别'
  if (/报告|推理|语言|LLM/i.test(text)) return '风险研判与报告生成'
  if (/视觉|多模态|VLM/i.test(text)) return '现场图片理解'
  return '智能分析辅助'
}

function scenarioTags(model) {
  const scenario = scenarioText(model)
  if (scenario === '灾害巡查与风险识别') return ['巡查图片', '灾害分类', '风险初筛']
  if (scenario === '风险研判与报告生成') return ['事件研判', '处置建议', '报告生成']
  if (scenario === '现场图片理解') return ['图片理解', '文字提问', '现场分析']
  if (scenario === '模型对照与通用识别') return ['通用识别', '模型对照', '效果参考']
  return ['智能分析', '辅助判断']
}

function statusExplain(model) {
  if (model.runtime_status === 'running') return '当前可以直接调用。'
  if (model.runtime_status === 'error') return '当前不可用，需要管理员检查服务。'
  if (['starting', 'stopping'].includes(model.runtime_status)) return '服务状态正在变化，请稍后刷新。'
  return '当前未启动，需要管理员启用后才能调用。'
}

function fieldTypes(fields = []) {
  const types = new Set(fields.map((field) => field.type))
  const labels = []
  if (types.has('image')) labels.push('图片')
  if (types.has('text')) labels.push('文字')
  if (types.has('json')) labels.push('结构化信息')
  if (types.has('float') || types.has('integer')) labels.push('参数')
  return labels.length ? labels.join('、') : '按场景提供输入'
}

function inputText(model) {
  return fieldTypes(model.inputs)
}

function outputText(model) {
  return fieldTypes(model.outputs).replace('参数', '分析结果')
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

async function testHealth(model) {
  checkingId.value = model.id
  try {
    const response = await checkModelHealth(model.id)
    const result = response.data || {}
    const nextStatus = {
      runtime_status: result.runtime_status,
      status_label: result.status_label,
      status_level: result.status_level,
      health_state: result.health_state,
    }
    models.value = models.value.map((item) => (item.id === model.id ? { ...item, ...nextStatus } : item))
    if (selectedModel.value?.id === model.id) {
      selectedModel.value = { ...selectedModel.value, ...nextStatus }
    }
    ElMessage[result.healthy ? 'success' : 'warning'](result.healthy ? '当前可以使用' : '当前不可用，需要检查')
  } catch (error) {
    ElMessage.error('可用性检查失败')
  } finally {
    checkingId.value = null
  }
}

onMounted(loadModels)
</script>

<style scoped>
.model-page {
  min-height: 100%;
  padding: 22px;
  color: #e9f7ff;
  background: linear-gradient(145deg, #071522, #0c2131 58%, #071522);
}

.page-head,
.summary-grid,
.toolbar,
.model-card {
  border: 1px solid rgba(93, 184, 225, 0.18);
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
  color: #9ab3c0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 12px;
  margin-top: 14px;
  padding: 14px;
}

.summary-item {
  min-height: 82px;
  padding: 14px 16px;
  border: 1px dashed rgba(120, 177, 216, 0.22);
  border-radius: 8px;
  background: rgba(35, 85, 124, 0.2);
}

.summary-item span,
.detail-panel header span,
.detail-section h4,
.io-summary span {
  color: #93acbc;
  font-size: 13px;
}

.summary-item strong {
  display: block;
  margin-top: 10px;
  font-size: 26px;
}

.summary-item.available strong {
  color: #51e6be;
}

.summary-item.attention strong {
  color: #f3c64e;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 150px 150px;
  gap: 10px;
  margin-top: 14px;
  padding: 12px;
}

.model-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.model-card {
  padding: 18px;
}

.model-card header {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: flex-start;
  gap: 12px;
}

.model-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
}

.model-icon.is-ready {
  color: #51e6be;
  background: rgba(81, 230, 190, 0.12);
}

.model-icon.is-idle {
  color: #8db6d0;
  background: rgba(141, 182, 208, 0.12);
}

.model-icon.is-error {
  color: #ff9ca7;
  background: rgba(255, 108, 123, 0.12);
}

.model-headline {
  min-width: 0;
}

.model-headline h3 {
  margin: 0;
  font-size: 19px;
  line-height: 1.25;
  word-break: break-word;
}

.model-headline p {
  display: -webkit-box;
  margin: 7px 0 0;
  overflow: hidden;
  color: #9fb7c5;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.scenario-band {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid rgba(112, 183, 221, 0.18);
  border-radius: 8px;
  background: rgba(35, 85, 124, 0.18);
}

.scenario-band span {
  display: block;
  color: #8fb4c8;
  font-size: 13px;
}

.scenario-band strong {
  display: block;
  margin-top: 6px;
  color: #eef8ff;
  font-size: 16px;
}

.model-card footer {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.detail-panel {
  color: #e9f7ff;
}

.detail-panel header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-panel h3 {
  margin: 6px 0 0;
  font-size: 23px;
  line-height: 1.3;
}

.detail-section {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid rgba(112, 183, 221, 0.18);
  border-radius: 8px;
  background: rgba(9, 30, 48, 0.74);
}

.detail-section h4 {
  margin: 0 0 8px;
  font-weight: 600;
}

.detail-section p {
  margin: 0;
  color: #d7e8f2;
  line-height: 1.7;
}

.plain-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.plain-tags span {
  padding: 5px 10px;
  border: 1px solid rgba(112, 183, 221, 0.22);
  border-radius: 8px;
  color: #b9cfdd;
  background: rgba(48, 103, 139, 0.18);
}

.io-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.io-summary div {
  min-height: 64px;
  padding: 10px 12px;
  border: 1px dashed rgba(120, 177, 216, 0.22);
  border-radius: 8px;
}

.io-summary strong {
  display: block;
  margin-top: 6px;
  color: #eef8ff;
  line-height: 1.4;
}

.detail-action {
  width: 100%;
  margin-top: 16px;
}

:deep(.model-detail-drawer) {
  background: #071522;
}

@media (max-width: 900px) {
  .summary-grid,
  .toolbar,
  .model-list,
  .io-summary {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .model-card header {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .model-card header .el-tag {
    grid-column: 1 / -1;
    justify-self: start;
  }
}
</style>
