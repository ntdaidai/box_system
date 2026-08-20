<template>
  <div class="model-page">
    <header class="page-head">
      <div>
        <h2>模型管理</h2>
        <p>模型服务运行控制与能力归类。</p>
      </div>
      <div class="page-actions">
        <el-button
          class="import-model-button"
          type="primary"
          @click="openImportDrawer"
        >
          <el-icon class="import-button-icon"><FolderOpened /></el-icon>
          <span>导入模型</span>
        </el-button>
      </div>
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
      <el-select v-model="filters.availability" clearable placeholder="运行状态">
        <el-option label="运行中" value="available" />
        <el-option label="已停止" value="standby" />
      </el-select>
    </section>

    <section v-loading="loading" class="model-list">
      <article
        v-for="model in paginatedModels"
        :key="model.id"
        class="model-card"
        :class="modelIconClass(model)"
      >
        <header>
          <div class="model-icon" :class="modelIconClass(model)">
            <el-icon><component :is="modelIcon(model)" /></el-icon>
          </div>
          <div class="model-headline">
            <h3>{{ model.name }}</h3>
            <div class="model-meta">
              <div class="model-meta-row">
                <span
                  v-for="tag in modelBadgeGroups(model).core"
                  :key="tag.key"
                  :class="`is-${tag.tone}`"
                >
                  {{ tag.label }}
                </span>
              </div>
              <div v-if="modelBadgeGroups(model).business.length" class="model-meta-row is-business">
                <span class="model-meta-label">业务</span>
                <span
                  v-for="tag in visibleBusinessTags(model)"
                  :key="tag.key"
                  :class="`is-${tag.tone}`"
                >
                  {{ tag.label }}
                </span>
                <el-tooltip
                  v-if="hiddenBusinessTags(model).length"
                  :content="hiddenBusinessText(model)"
                  effect="dark"
                  placement="top"
                  popper-class="model-tag-tooltip"
                  :show-after="180"
                >
                  <span
                    class="model-meta-more"
                    tabindex="0"
                    :aria-label="`还有${hiddenBusinessTags(model).length}个业务标签`"
                  >
                    +{{ hiddenBusinessTags(model).length }}
                  </span>
                </el-tooltip>
              </div>
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
            type="danger"
            plain
            :icon="Delete"
            :loading="isActioning(model, 'delete')"
            :disabled="!canDelete(model) || isAnyActioning(model)"
            @click="deleteModelRecord(model)"
          >
            删除
          </el-button>
          <el-button
            :type="runtimeActionType(model) === 'stop' ? 'danger' : 'success'"
            :plain="runtimeActionType(model) === 'stop'"
            :icon="runtimeActionIcon(model)"
            :loading="isActioning(model, runtimeActionType(model))"
            :disabled="!canToggleModel(model) || isAnyActioning(model)"
            @click="toggleModel(model)"
          >
            {{ runtimeActionLabel(model) }}
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

    <el-drawer v-model="detailVisible" size="560px" class="model-detail-drawer" :with-header="false">
      <div v-if="selectedModel" class="detail-panel">
        <div class="drawer-scroll-content">
        <header class="detail-head">
          <div class="detail-title">
            <div class="detail-icon" :class="modelIconClass(selectedModel)">
              <el-icon><component :is="modelIcon(selectedModel)" /></el-icon>
            </div>
            <div class="detail-title-copy">
              <span class="detail-eyebrow">模型服务 · {{ selectedModel.capability }}</span>
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
          <span
            v-for="tag in modelBadges(selectedModel)"
            :key="tag.key"
            class="detail-chip"
            :class="`is-${tag.tone}`"
          >
            {{ tag.label }}
          </span>
        </div>

        <section class="detail-section detail-summary">
          <div class="detail-section-title">
            <h4>模型信息</h4>
            <el-button
              v-if="!metadataEditing"
              text
              :icon="Edit"
              @click="startMetadataEditing(selectedModel)"
            >
              编辑
            </el-button>
          </div>
          <template v-if="metadataEditing">
            <div class="metadata-edit-form">
              <label class="metadata-edit-field">
                <span>模型名称</span>
                <el-input
                  v-model.trim="editForm.name"
                  maxlength="128"
                  placeholder="请输入模型名称"
                  aria-label="模型名称"
                />
              </label>
              <label class="metadata-edit-field">
                <span>业务标签</span>
                <el-input
                  v-model="editForm.tagsText"
                  maxlength="512"
                  placeholder="多个标签用逗号分隔"
                  aria-label="业务标签"
                />
                <small>导入标识和目录标识会由系统自动保留。</small>
              </label>
              <label class="metadata-edit-field">
                <span>模型说明</span>
                <el-input
                  v-model.trim="editForm.description"
                  type="textarea"
                  :rows="4"
                  maxlength="512"
                  show-word-limit
                  placeholder="补充模型用途、适用场景或调用说明"
                  aria-label="模型说明"
                />
              </label>
            </div>
            <div class="description-actions">
              <el-button @click="cancelMetadataEditing">取消</el-button>
              <el-button type="primary" :loading="savingEdit" @click="saveModelMetadata">保存修改</el-button>
            </div>
          </template>
          <p v-else>{{ userDescription(selectedModel) }}</p>
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
        </div>

        <div class="detail-actions">
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :loading="isActioning(selectedModel, 'delete')"
            :disabled="!canDelete(selectedModel) || isAnyActioning(selectedModel)"
            @click="deleteModelRecord(selectedModel)"
          >
            删除
          </el-button>
          <el-button
            :type="runtimeActionType(selectedModel) === 'stop' ? 'danger' : 'success'"
            :plain="runtimeActionType(selectedModel) === 'stop'"
            :icon="runtimeActionIcon(selectedModel)"
            :loading="isActioning(selectedModel, runtimeActionType(selectedModel))"
            :disabled="!canToggleModel(selectedModel) || isAnyActioning(selectedModel)"
            @click="toggleModel(selectedModel)"
          >
            {{ runtimeActionLabel(selectedModel) }}
          </el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog
      v-model="deleteConfirmVisible"
      class="model-delete-dialog"
      width="460px"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      append-to-body
    >
      <template #header>
        <div class="delete-dialog-header">
          <div class="delete-dialog-icon">
            <el-icon><Warning /></el-icon>
          </div>
          <div class="delete-dialog-title">
            <span>危险操作</span>
            <h3>确认删除模型</h3>
          </div>
          <button class="delete-dialog-close" type="button" @click="cancelDelete">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </template>
      <div class="delete-dialog-body">
        <p>确定要删除「{{ deleteCandidate?.name }}」吗？</p>
        <div class="delete-dialog-warning">
          <el-icon><Warning /></el-icon>
          <span>注册记录和导入目录会删除，已构建镜像会保留用于后续快速重建。</span>
        </div>
        <ul class="delete-dialog-list">
          <li v-for="item in deleteConfirmationItems" :key="item">{{ item }}</li>
        </ul>
      </div>
      <template #footer>
        <div class="delete-dialog-actions">
          <el-button @click="cancelDelete">取消</el-button>
          <el-button type="danger" :loading="isActioning(deleteCandidate, 'delete')" @click="confirmDeleteModel">
            确认删除
          </el-button>
        </div>
      </template>
    </el-dialog>

    <input
      ref="folderInput"
      class="folder-input"
      type="file"
      webkitdirectory
      directory
      multiple
      @change="onFolderSelected"
    />

    <el-drawer v-model="importVisible" size="680px" class="model-import-drawer" :with-header="false">
      <div class="import-panel">
        <div class="drawer-scroll-content">
        <header class="detail-head">
          <div class="detail-title">
            <div class="detail-icon is-idle">
              <el-icon><FolderOpened /></el-icon>
            </div>
            <div class="import-title-copy">
              <h3>导入模型</h3>
              <span>完整模型服务目录 · 自动校验并注册</span>
            </div>
          </div>
          <button class="drawer-close" type="button" @click="importVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </header>

        <section class="import-section folder-picker" :class="{ 'has-folder': importSummary.fileCount }">
          <div class="folder-picker-icon">
            <el-icon><FolderOpened /></el-icon>
          </div>
          <div class="folder-picker-copy">
            <span class="import-step-label">01 · 模型目录</span>
            <h4>{{ importSummary.folderName || '选择模型文件夹' }}</h4>
            <p>{{ selectedFolderText || '选择包含 Dockerfile 和 docker-compose.yml 的完整服务目录' }}</p>
          </div>
          <el-button class="folder-select-button" :icon="FolderOpened" @click="triggerFolderPicker">
            {{ importSummary.fileCount ? '重新选择' : '选择文件夹' }}
          </el-button>
        </section>

        <section class="import-section">
          <div class="section-title">
            <div>
              <span class="import-step-label">02 · 自动检查</span>
              <h4>结构检查</h4>
            </div>
            <span class="import-status-pill" :class="{
              'is-success': localCheckPassed,
              'is-error': importChecks.length && !localCheckPassed,
            }">
              {{ !importChecks.length ? '待选择' : (localCheckPassed ? '已通过' : '需处理') }}
            </span>
          </div>
          <div v-if="!importChecks.length" class="check-empty">
            选择模型目录后，将自动检查目录结构、服务入口和模型文件。
          </div>
          <div v-else class="check-list">
            <div v-for="item in importChecks" :key="item.key" class="check-item" :class="`is-${item.level}`">
              <el-icon>
                <CircleCheck v-if="item.level === 'success'" />
                <Warning v-else-if="item.level === 'warning'" />
                <CircleClose v-else />
              </el-icon>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </section>

        <section class="import-section" v-if="serverValidation || validatingImport">
          <div class="section-title">
            <div>
              <span class="import-step-label">03 · 服务端校验</span>
              <h4>自动校验</h4>
            </div>
            <span class="import-status-pill" :class="{
              'is-success': serverValidation?.valid === true && !validatingImport,
              'is-error': serverValidation?.valid === false,
              'is-loading': validatingImport,
            }">
              <el-icon v-if="validatingImport" class="import-status-icon is-loading"><Loading /></el-icon>
              {{ validatingImport ? '检查中' : (serverValidation?.valid ? '通过' : '未通过') }}
            </span>
          </div>
          <div v-if="validatingImport" class="check-empty">
            正在进行服务端自动校验，请稍候…
          </div>
          <div v-else class="server-result">
            <p v-for="item in validationMessages" :key="item">{{ item }}</p>
          </div>
        </section>

        <section class="import-section registration-section">
          <div class="section-title registration-title">
            <div>
              <span class="import-step-label">04 · 信息确认</span>
              <h4>注册信息</h4>
            </div>
            <span class="registration-hint">可根据需要修改自动识别结果</span>
          </div>
          <el-form label-position="top" class="import-form">
            <el-form-item label="模型名称">
              <el-input v-model.trim="importForm.name" placeholder="默认取目录名" />
            </el-form-item>
            <el-form-item label="能力类型">
              <el-select v-model="importForm.capability" placeholder="请选择能力类型">
                <el-option v-for="item in capabilityChoices" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
            <div class="form-grid">
              <el-form-item label="运行框架">
                <el-input v-model.trim="importForm.framework" placeholder="如 PyTorch / FastAPI" />
              </el-form-item>
              <el-form-item label="模型架构">
                <el-input v-model.trim="importForm.architecture" placeholder="如 YOLO / RT-DETR" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="镜像名">
                <el-input v-model.trim="importForm.image_name" placeholder="从 compose 解析" />
              </el-form-item>
              <el-form-item label="容器名">
                <el-input v-model.trim="importForm.container_name" placeholder="从 compose 解析" />
              </el-form-item>
            </div>
            <div class="form-grid">
              <el-form-item label="服务端口">
                <el-input v-model.trim="importForm.host_port" placeholder="如 8012" />
              </el-form-item>
              <el-form-item label="推理入口">
                <el-input v-model.trim="importForm.endpoint" placeholder="如 /infer" />
              </el-form-item>
            </div>
            <el-form-item label="业务标签">
              <el-input v-model.trim="importForm.tags" placeholder="多个标签用逗号分隔" />
            </el-form-item>
            <el-form-item label="模型说明">
              <el-input v-model.trim="importForm.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
        </section>
        </div>

        <footer class="import-actions">
          <div class="import-action-status" :class="`is-${importActionStatus}`">
            <span class="import-action-dot"></span>
            <div class="import-action-copy">
              <span class="import-action-label">导入状态</span>
              <span>{{ importActionMessage }}</span>
            </div>
          </div>
          <div class="import-action-buttons">
            <el-button class="reset-import-button" @click="resetImport">重置导入</el-button>
            <el-button
              type="primary"
              :loading="registeringImport"
              :disabled="!canRegisterImport"
              @click="registerImport"
            >
              注册模型
            </el-button>
          </div>
        </footer>
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
  CircleCheck,
  CircleClose,
  Delete,
  Edit,
  Files,
  FolderOpened,
  Grid,
  Loading,
  Picture,
  Search,
  VideoPause,
  VideoPlay,
  View,
  Warning,
} from '@element-plus/icons-vue'
import {
  deleteModel,
  getModelLibrary,
  getModelLibraryDetail,
  registerImportedModel,
  startModel,
  stopModel,
  updateModel,
  validateModelImport,
} from '@/api/modelLibrary'

const loading = ref(false)
const models = ref([])
const selectedModel = ref(null)
const detailVisible = ref(false)
const metadataEditing = ref(false)
const currentPage = ref(1)
const pageSize = 8
const actionState = reactive({
  id: null,
  type: '',
})
const loadError = ref('')
const folderInput = ref(null)
const importVisible = ref(false)
const importFiles = ref([])
const importChecks = ref([])
const serverValidation = ref(null)
const validatingImport = ref(false)
const registeringImport = ref(false)
const deleteConfirmVisible = ref(false)
const deleteCandidate = ref(null)
const savingEdit = ref(false)
const editForm = reactive({
  id: null,
  name: '',
  description: '',
  tagsText: '',
})

const importSummary = reactive({
  folderName: '',
  fileCount: 0,
  totalSize: 0,
  rootCount: 0,
})

const importForm = reactive({
  name: '',
  capability: '',
  framework: '',
  architecture: '',
  image_name: '',
  container_name: '',
  host_port: '',
  endpoint: '',
  tags: '',
  description: '',
})

const filters = reactive({
  keyword: '',
  capability: '',
  availability: '',
})

const capabilityOptions = computed(() => {
  return [...new Set(models.value.map((item) => item.capability).filter(Boolean))].sort()
})

const capabilityChoices = ['目标检测', '图像分类', '视觉语言模型', '文本推理', '通用服务']

const selectedFolderText = computed(() => {
  if (!importSummary.fileCount) return ''
  return `${importSummary.fileCount} 个文件，${formatBytes(importSummary.totalSize)}`
})

const localCheckPassed = computed(() => {
  return importFiles.value.length > 0 && importChecks.value.every((item) => item.level !== 'error')
})

const validationMessages = computed(() => {
  if (!serverValidation.value) return []
  const errors = serverValidation.value.errors || []
  const warnings = serverValidation.value.warnings || []
  const messages = [...errors, ...warnings].map((item) => String(item))
  if (!messages.length) return ['服务端校验未发现阻断问题']
  return messages
})

const canRegisterImport = computed(() => {
  return localCheckPassed.value
    && !validatingImport.value
    && !registeringImport.value
    && Boolean(importForm.name && importForm.capability)
    && serverValidation.value?.valid === true
})

const importActionStatus = computed(() => {
  if (!importFiles.value.length) return 'idle'
  if (validatingImport.value) return 'loading'
  if (!localCheckPassed.value || serverValidation.value?.valid === false) return 'error'
  if (serverValidation.value?.valid === true) return 'success'
  return 'idle'
})

const importActionMessage = computed(() => {
  if (!importFiles.value.length) return '选择目录后将自动校验'
  if (validatingImport.value) return '正在进行服务端自动校验…'
  if (!localCheckPassed.value) return '请先处理目录结构问题'
  if (serverValidation.value?.valid === false) return '请根据校验结果修正目录'
  if (serverValidation.value?.valid === true) return '校验通过，可以注册模型'
  return '等待服务端校验'
})

const deleteConfirmationItems = computed(() => {
  if (deleteCandidate.value && registryTags(deleteCandidate.value).some((tag) => isInternalRegistryTag(tag))) {
    return ['删除模型注册记录', '清理关联容器', '删除该模型的导入目录及文件', '保留已构建镜像缓存']
  }
  return ['删除模型注册记录', '清理关联容器', '保留已构建镜像']
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
  if (model.runtime_status === 'building') return 'is-building'
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
  if (model.runtime_status === 'building') return '正在构建镜像并执行启动验证，请稍候。'
  if (model.runtime_status === 'error') return '当前不可用，需要管理员检查服务。'
  if (['starting', 'stopping'].includes(model.runtime_status)) return '服务状态正在变化，请稍后刷新。'
  return '当前未启动，需要管理员启用后才能调用。'
}

function runtimeLabel(model) {
  if (model.runtime_status === 'running') return '运行中'
  if (model.runtime_status === 'building') return '构建中'
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

function isInternalRegistryTag(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return normalized === 'imported' || normalized.startsWith('folder:')
}

function modelBadges(model, limit = 6) {
  const source = [
    { key: 'type', label: model?.model_type || model?.capability, tone: 'type' },
    { key: 'framework', label: model?.framework, tone: 'framework' },
    { key: 'architecture', label: model?.architecture, tone: 'architecture' },
    { key: 'size', label: model?.model_size, tone: 'size' },
    ...registryTags(model).filter((tag) => !isInternalRegistryTag(tag)).map((tag, index) => ({
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

function modelBadgeGroups(model) {
  const badges = modelBadges(model, Number.POSITIVE_INFINITY)
  const coreTones = new Set(['type', 'framework', 'architecture', 'size'])
  return {
    core: badges.filter((tag) => coreTones.has(tag.tone)),
    business: badges.filter((tag) => !coreTones.has(tag.tone)),
  }
}

function visibleBusinessTags(model) {
  return modelBadgeGroups(model).business.slice(0, 4)
}

function hiddenBusinessTags(model) {
  return modelBadgeGroups(model).business.slice(4)
}

function hiddenBusinessText(model) {
  return hiddenBusinessTags(model).map((tag) => tag.label).join('、')
}

function shortDate(value) {
  if (!value) return '未记录'
  const text = String(value)
  const matched = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (matched) return `${matched[1]}-${matched[2]}-${matched[3]}`
  return text.slice(0, 10) || '未记录'
}

function canStart(model) {
  return Boolean(model?.id) && !['building', 'running', 'starting', 'stopping'].includes(model?.runtime_status)
}

function canStop(model) {
  return Boolean(model?.id) && ['running', 'starting', 'error'].includes(model?.runtime_status)
}

function runtimeActionType(model) {
  return ['running', 'stopping'].includes(model?.runtime_status) ? 'stop' : 'start'
}

function runtimeActionLabel(model) {
  if (model?.runtime_status === 'building') return '构建中'
  if (model?.runtime_status === 'starting') return '启动中'
  if (model?.runtime_status === 'stopping') return '停止中'
  return runtimeActionType(model) === 'stop' ? '停止' : '运行'
}

function runtimeActionIcon(model) {
  return runtimeActionType(model) === 'stop' ? VideoPause : VideoPlay
}

function canToggleModel(model) {
  return runtimeActionType(model) === 'stop' ? canStop(model) : canStart(model)
}

function toggleModel(model) {
  if (!canToggleModel(model) || isAnyActioning(model)) return
  controlModel(model, runtimeActionType(model))
}

function canDelete(model) {
  return Boolean(model?.id) && ['stopped', 'error'].includes(model.runtime_status)
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

function openImportDrawer() {
  importVisible.value = true
}

function triggerFolderPicker() {
  folderInput.value?.click()
}

function resetImport() {
  importFiles.value = []
  importChecks.value = []
  serverValidation.value = null
  Object.assign(importSummary, {
    folderName: '',
    fileCount: 0,
    totalSize: 0,
    rootCount: 0,
  })
  Object.assign(importForm, {
    name: '',
    capability: '',
    framework: '',
    architecture: '',
    image_name: '',
    container_name: '',
    host_port: '',
    endpoint: '',
    tags: '',
    description: '',
  })
  if (folderInput.value) folderInput.value.value = ''
}

async function onFolderSelected(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) {
    if (event.target) event.target.value = ''
    return
  }
  resetImport()
  importFiles.value = files
  await inspectImportFolder(files)
  if (localCheckPassed.value) await validateImportWithServer()
}

function relativePath(file) {
  return file.webkitRelativePath || file.relativePath || file.name
}

function rootFolder(path) {
  return String(path || '').split('/').filter(Boolean)[0] || ''
}

function stripRoot(path, root) {
  const normalized = String(path || '')
  return normalized.startsWith(`${root}/`) ? normalized.slice(root.length + 1) : normalized
}

function formatBytes(value) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`
}

function addCheck(checks, key, passed, label, warning = false) {
  checks.push({
    key,
    label,
    level: passed ? 'success' : (warning ? 'warning' : 'error'),
  })
}

function findFile(paths, name) {
  return paths.find((path) => path === name || path.endsWith(`/${name}`))
}

function findWeightFiles(paths) {
  return paths.filter((path) => /\.(pt|onnx|engine|safetensors|bin)$/i.test(path))
}

function inferCapability(folderName, paths, composeText) {
  const text = `${folderName} ${paths.join(' ')} ${composeText}`.toLowerCase()
  if (text.includes('vllm_base_url') || text.includes('qwen')) return '视觉语言模型'
  if (text.includes('-od') || text.includes('detector') || text.includes('detect/image')) return '目标检测'
  if (text.includes('-cls') || text.includes('classifier') || text.includes('yolo_service')) return '图像分类'
  return '通用服务'
}

function inferArchitecture(folderName, paths, composeText) {
  const text = `${folderName} ${paths.join(' ')} ${composeText}`.toLowerCase()
  if (text.includes('rtdetr')) return 'RT-DETR'
  if (text.includes('yolo')) return 'YOLO'
  if (text.includes('repvit')) return 'RepVIT'
  if (text.includes('mobilenet')) return 'MobileNetV4'
  if (text.includes('qwen')) return 'Qwen'
  return ''
}

function inferEndpoint(paths, readmeText) {
  const text = `${paths.join(' ')} ${readmeText}`.toLowerCase()
  if (text.includes('/api/v1/local-inference')) return '/api/v1/local-inference'
  if (text.includes('/detect/image')) return '/detect/image'
  if (text.includes('/infer')) return '/infer'
  if (text.includes('/predict')) return '/predict'
  return ''
}

function extractComposeValue(composeText, key) {
  const pattern = new RegExp(`\\b${key}:\\s*["']?([^"'\\n]+)`, 'i')
  const matched = composeText.match(pattern)
  return matched?.[1]?.trim() || ''
}

function extractComposePort(composeText) {
  const matched = composeText.match(/-\s*["']?(\d{2,5}):(\d{2,5})/i)
  return matched?.[1] || ''
}

function extractServiceName(composeText) {
  const matched = composeText.match(/^ {2}([a-zA-Z0-9_.-]+):\s*$/m)
  return matched?.[1] || ''
}

async function inspectImportFolder(files) {
  const paths = files.map(relativePath)
  const roots = [...new Set(paths.map(rootFolder).filter(Boolean))]
  const root = roots[0] || ''
  const normalizedPaths = paths.map((path) => stripRoot(path, root))
  const totalSize = files.reduce((sum, file) => sum + file.size, 0)
  const checks = []
  const composeFile = files.find((file) => stripRoot(relativePath(file), root) === 'docker-compose.yml')
  const readmeFile = files.find((file) => stripRoot(relativePath(file), root).toLowerCase() === 'readme.md')
  const composeText = composeFile ? await composeFile.text() : ''
  const readmeText = readmeFile ? await readmeFile.text() : ''
  const weightFiles = findWeightFiles(normalizedPaths)
  const capability = inferCapability(root, normalizedPaths, composeText)

  Object.assign(importSummary, {
    folderName: root,
    fileCount: files.length,
    totalSize,
    rootCount: roots.length,
  })

  addCheck(checks, 'single-root', roots.length === 1, '只包含一个模型根目录')
  addCheck(checks, 'dockerfile', Boolean(findFile(normalizedPaths, 'Dockerfile')), '包含 Dockerfile')
  addCheck(checks, 'compose', Boolean(composeFile), '包含 docker-compose.yml')
  addCheck(checks, 'main', Boolean(findFile(normalizedPaths, 'app/main.py')), '包含 app/main.py 服务入口')
  addCheck(checks, 'requirements', Boolean(findFile(normalizedPaths, 'requirements.txt')), '包含 requirements.txt', true)
  addCheck(checks, 'readme', Boolean(readmeFile), '包含 README.md', true)
  addCheck(checks, 'unsafe-path', normalizedPaths.every((path) => !path.startsWith('/') && !path.includes('../')), '路径未包含越级或绝对路径')
  addCheck(
    checks,
    'cache',
    !normalizedPaths.some((path) => path.includes('__pycache__') || path.startsWith('.git/') || path.includes('/.git/') || path.includes('node_modules')),
    '未包含缓存或源码管理目录',
    true,
  )
  addCheck(checks, 'compose-parse', Boolean(composeText && extractServiceName(composeText)), '可解析 Compose 服务名')
  addCheck(checks, 'port', Boolean(composeText && extractComposePort(composeText)), '可解析服务端口')
  addCheck(checks, 'weights', capability === '视觉语言模型' || weightFiles.length > 0, '视觉模型包含权重文件')

  importChecks.value = checks
  Object.assign(importForm, {
    name: root || extractServiceName(composeText),
    capability,
    framework: capability === '视觉语言模型' ? 'vLLM Proxy / FastAPI' : 'PyTorch / FastAPI',
    architecture: inferArchitecture(root, normalizedPaths, composeText),
    image_name: extractComposeValue(composeText, 'image'),
    container_name: extractComposeValue(composeText, 'container_name'),
    host_port: extractComposePort(composeText),
    endpoint: inferEndpoint(normalizedPaths, readmeText),
    description: readmeText.split('\n').find((line) => line.trim() && !line.trim().startsWith('#'))?.trim() || '',
  })
}

function appendImportFiles(formData) {
  importFiles.value.forEach((file) => {
    formData.append('files', file, relativePath(file))
  })
}

function importMetadata() {
  return {
    ...importForm,
    folder_name: importSummary.folderName,
    file_count: importSummary.fileCount,
    total_size: importSummary.totalSize,
    tags: importForm.tags.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
  }
}

async function validateImportWithServer() {
  validatingImport.value = true
  serverValidation.value = null
  try {
    const formData = new FormData()
    appendImportFiles(formData)
    formData.append('metadata', JSON.stringify(importMetadata()))
    const response = await validateModelImport(formData)
    serverValidation.value = response.data || { valid: true }
    if (serverValidation.value.detected) {
      Object.assign(importForm, {
        name: serverValidation.value.detected.name || importForm.name,
        capability: serverValidation.value.detected.model_type || serverValidation.value.detected.capability || importForm.capability,
        framework: serverValidation.value.detected.framework || importForm.framework,
        architecture: serverValidation.value.detected.architecture || importForm.architecture,
        image_name: serverValidation.value.detected.image_name || importForm.image_name,
        container_name: serverValidation.value.detected.container_name || importForm.container_name,
        host_port: serverValidation.value.detected.host_port || importForm.host_port,
        endpoint: serverValidation.value.detected.endpoint || importForm.endpoint,
      })
    }
  } catch (error) {
    serverValidation.value = { valid: false, errors: ['模型目录后端校验失败'] }
  } finally {
    validatingImport.value = false
  }
}

async function registerImport() {
  registeringImport.value = true
  try {
    const formData = new FormData()
    appendImportFiles(formData)
    formData.append('metadata', JSON.stringify(importMetadata()))
    const response = await registerImportedModel(formData)
    ElMessage.success(response.message || '模型注册成功')
    importVisible.value = false
    resetImport()
    await loadModels()
  } catch (error) {
    ElMessage.error('模型注册失败')
  } finally {
    registeringImport.value = false
  }
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

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function monitorModelStatus(modelId, type, shouldStop) {
  const targetStatuses = type === 'start' ? ['running', 'error'] : ['stopped', 'error']

  for (let attempt = 0; attempt < 45; attempt += 1) {
    await wait(800)
    if (shouldStop()) return

    try {
      const response = await getModelLibraryDetail(modelId)
      const nextStatus = normalizeStatusPayload(response.data || {})
      updateModelStatus(modelId, nextStatus)
      if (targetStatuses.includes(nextStatus.runtime_status)) return
    } catch (error) {
      // The lifecycle request remains the source of truth; a temporary poll
      // failure should not interrupt the start/stop operation.
    }
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
  metadataEditing.value = false
  selectedModel.value = model
  try {
    const response = await getModelLibraryDetail(model.id)
    selectedModel.value = response.data || model
  } catch (error) {
    ElMessage.warning('详情读取失败，已显示基础信息')
  }
}

function startMetadataEditing(model) {
  editForm.id = model?.id || null
  editForm.name = model?.name || ''
  editForm.description = model?.description && model.description !== '暂无说明' ? model.description : ''
  editForm.tagsText = registryTags(model)
    .filter((tag) => !isInternalRegistryTag(tag))
    .join(', ')
  metadataEditing.value = true
}

function cancelMetadataEditing() {
  metadataEditing.value = false
  editForm.id = null
  editForm.name = ''
  editForm.description = ''
  editForm.tagsText = ''
}

function patchModel(modelId, patch) {
  models.value = models.value.map((item) => (item.id === modelId ? { ...item, ...patch } : item))
  if (selectedModel.value?.id === modelId) {
    selectedModel.value = { ...selectedModel.value, ...patch }
  }
}

function editableTags(value) {
  return [...new Set(
    String(value || '')
      .split(/[,，\n]/)
      .map((tag) => tag.trim())
      .filter(Boolean),
  )]
}

async function saveModelMetadata() {
  if (!editForm.id || savingEdit.value) return
  if (!editForm.name.trim()) {
    ElMessage.warning('模型名称不能为空')
    return
  }
  savingEdit.value = true
  try {
    const tags = editableTags(editForm.tagsText)
    const response = await updateModel(editForm.id, {
      name: editForm.name.trim(),
      description: editForm.description,
      tags,
    })
    const updated = response.data || {}
    patchModel(editForm.id, {
      name: updated.name ?? editForm.name.trim(),
      description: updated.description ?? editForm.description,
      tags: Array.isArray(updated.tags) ? updated.tags : tags,
    })
    ElMessage.success(response.message || '模型信息已更新')
    cancelMetadataEditing()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '模型信息更新失败')
  } finally {
    savingEdit.value = false
  }
}

async function deleteModelRecord(model) {
  if (!canDelete(model) || isAnyActioning(model)) return
  deleteCandidate.value = model
  deleteConfirmVisible.value = true
}

function cancelDelete() {
  if (isActioning(deleteCandidate.value, 'delete')) return
  deleteConfirmVisible.value = false
  deleteCandidate.value = null
}

async function confirmDeleteModel() {
  const model = deleteCandidate.value
  if (!model || !canDelete(model) || isAnyActioning(model)) return
  deleteConfirmVisible.value = false
  actionState.id = model.id
  actionState.type = 'delete'
  try {
    const response = await deleteModel(model.id)
    models.value = models.value.filter((item) => item.id !== model.id)
    if (selectedModel.value?.id === model.id) {
      selectedModel.value = null
      detailVisible.value = false
    }
    ElMessage.success(response.message || '模型已删除')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '模型删除失败')
  } finally {
    actionState.id = null
    actionState.type = ''
    deleteCandidate.value = null
  }
}

async function controlModel(model, type) {
  const previousStatus = model.runtime_status
  const pendingStatus = type === 'start' ? 'starting' : 'stopping'
  updateModelStatus(model.id, {
    runtime_status: pendingStatus,
    status_label: type === 'start' ? '启动中' : '停止中',
    status_level: 'info',
  })
  actionState.id = model.id
  actionState.type = type
  let operationFinished = false
  const monitorPromise = monitorModelStatus(model.id, type, () => operationFinished)

  try {
    const response = type === 'start' ? await startModel(model.id) : await stopModel(model.id)
    operationFinished = true
    await monitorPromise
    const result = response.data || {}
    updateModelStatus(model.id, normalizeStatusPayload(result))
    ElMessage.success(type === 'start' ? '模型已启动' : '模型已停止')
  } catch (error) {
    operationFinished = true
    await monitorPromise
    updateModelStatus(model.id, {
      runtime_status: previousStatus === 'running' && type === 'stop' ? 'running' : 'error',
      status_label: previousStatus === 'running' && type === 'stop' ? '运行中' : '异常',
      status_level: previousStatus === 'running' && type === 'stop' ? 'success' : 'error',
    })
    const detail = error?.response?.data?.detail
    ElMessage.error(detail || (type === 'start' ? '模型启动失败' : '模型停止失败'))
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
  background:
    radial-gradient(circle at 12% 0%, rgba(24, 93, 141, 0.16), transparent 34%),
    radial-gradient(circle at 96% 16%, rgba(0, 190, 232, 0.08), transparent 28%),
    #071422;
}

.page-head,
.toolbar,
.model-card {
  border: 1px solid rgba(21, 160, 218, 0.18);
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(14, 48, 75, 0.94), rgba(7, 27, 42, 0.96) 58%),
    #081d2b;
  box-shadow: 0 16px 34px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(136, 222, 255, 0.04);
}

.page-head {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
}

.page-head::after {
  content: "";
  position: absolute;
  right: 22px;
  bottom: 0;
  left: 22px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: linear-gradient(90deg, #22c9f2, rgba(34, 201, 242, 0.08));
  opacity: 0.7;
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.page-actions .el-button {
  margin-left: 0;
  border-radius: 9px;
  border-color: rgba(55, 174, 224, 0.34);
  color: #c7e9f8;
  background: rgba(16, 66, 100, 0.72);
  box-shadow: inset 0 1px 0 rgba(145, 225, 255, 0.06);
}

.page-actions .el-button:hover {
  border-color: rgba(72, 216, 255, 0.7);
  color: #f0fbff;
  background: rgba(20, 91, 132, 0.86);
}

.page-actions .el-button--primary {
  border-color: rgba(72, 216, 255, 0.62);
  color: #e9fbff;
  background: linear-gradient(135deg, rgba(18, 125, 166, 0.92), rgba(20, 83, 135, 0.92));
}

.page-actions .import-model-button {
  min-width: 156px;
  min-height: 48px;
  padding: 0 18px 0 12px;
  border: 1px solid rgba(77, 206, 239, 0.54);
  border-radius: 12px;
  color: #f2fdff;
  background:
    linear-gradient(135deg, rgba(18, 102, 143, 0.98), rgba(14, 63, 103, 0.98)),
    #104d76;
  box-shadow:
    0 8px 18px rgba(0, 0, 0, 0.18),
    inset 0 1px 0 rgba(223, 252, 255, 0.12);
  font-weight: 700;
  letter-spacing: 0.03em;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.import-button-icon {
  margin-right: 8px;
  color: #8feaff;
  font-size: 20px;
}

.page-actions .import-model-button:hover {
  border-color: rgba(105, 229, 255, 0.82);
  color: #ffffff;
  background: linear-gradient(135deg, #167fa7, #145b91);
  box-shadow:
    0 10px 24px rgba(0, 126, 180, 0.26),
    0 0 0 3px rgba(72, 216, 255, 0.1),
    inset 0 1px 0 rgba(236, 254, 255, 0.32);
  transform: translateY(-1px);
}

.page-actions .import-model-button:active {
  transform: translateY(0);
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
  border-radius: 12px;
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
  border-radius: 12px;
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
  background: linear-gradient(135deg, rgba(12, 40, 62, 0.94), rgba(7, 25, 40, 0.96));
}

.toolbar :deep(.el-input__wrapper),
.toolbar :deep(.el-select__wrapper) {
  min-height: 42px;
  border: 1px solid rgba(55, 174, 224, 0.24);
  border-radius: 999px;
  background: rgba(7, 29, 47, 0.78);
  box-shadow: inset 0 1px 0 rgba(145, 225, 255, 0.03);
}

.toolbar :deep(.el-input__wrapper:hover),
.toolbar :deep(.el-select__wrapper:hover) {
  border-color: rgba(72, 216, 255, 0.58);
}

.toolbar :deep(.el-input__wrapper.is-focus),
.toolbar :deep(.el-select__wrapper.is-focused) {
  border-color: #48d8ff;
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.18);
}

.toolbar :deep(.el-input__inner),
.toolbar :deep(.el-select__selected-item),
.toolbar :deep(.el-input__prefix) {
  color: #d7eff9;
}

.toolbar :deep(.el-select__selection) {
  justify-content: center;
  text-align: center;
}

.toolbar :deep(.el-select__placeholder),
.toolbar :deep(.el-select__selected-item) {
  display: block;
  width: 100%;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar :deep(.el-input__inner::placeholder) {
  color: #7698ac;
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
  position: relative;
  display: flex;
  min-height: 214px;
  flex-direction: column;
  overflow: hidden;
  padding: 18px;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.model-card::before {
  content: "";
  position: absolute;
  top: 0;
  right: 18px;
  left: 18px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background: #3c9fcb;
  opacity: 0.55;
}

.model-card.is-ready::before {
  background: #4fe5b7;
}

.model-card.is-building::before {
  background: #f0c75d;
}

.model-card.is-error::before {
  background: #ff7f8f;
}

.model-card:hover {
  border-color: rgba(22, 192, 255, 0.34);
  background: linear-gradient(135deg, rgba(13, 53, 79, 0.98), rgba(7, 29, 45, 0.98));
  box-shadow: 0 20px 38px rgba(0, 0, 0, 0.26), 0 0 24px rgba(22, 192, 255, 0.06);
  transform: translateY(-2px);
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
  border-radius: 12px;
  font-size: 20px;
}

.model-icon.is-ready {
  color: #4fe5b7;
  background: rgba(79, 229, 183, 0.12);
}

.model-icon.is-building {
  color: #f0c75d;
  background: rgba(194, 143, 42, 0.14);
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
  display: grid;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}

.model-meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.model-meta-row.is-business {
  flex-wrap: nowrap;
  overflow: hidden;
  gap: 5px;
  padding-top: 7px;
  border-top: 1px solid rgba(84, 175, 222, 0.18);
}

.model-meta-label {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 9px;
  border: 1px solid rgba(72, 216, 255, 0.3);
  border-radius: 999px;
  color: #8ee6fa;
  background: rgba(16, 93, 126, 0.42);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  line-height: 18px;
}

.model-meta-row > span:not(.model-meta-label) {
  flex: 0 1 max-content;
  max-width: 160px;
  min-width: 0;
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  overflow: hidden;
  border: 1px solid rgba(84, 175, 222, 0.28);
  border-radius: 999px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.68);
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-meta-row.is-business > span:not(.model-meta-label) {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 24px;
  padding: 2px 8px;
  color: #c8dcea;
  background: rgba(8, 41, 64, 0.78);
}

.model-meta-row.is-business > span:not(.model-meta-label),
.model-meta-row.is-business .model-meta-more {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-meta-more {
  flex: 0 0 auto !important;
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border: 1px solid rgba(72, 216, 255, 0.42);
  border-radius: 999px;
  color: #e7faff;
  background: linear-gradient(135deg, rgba(30, 122, 169, 0.78), rgba(25, 83, 140, 0.78));
  cursor: help;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  outline: none;
}

.model-meta-more:hover,
.model-meta-more:focus-visible {
  border-color: rgba(111, 231, 255, 0.82);
  background: linear-gradient(135deg, rgba(34, 151, 190, 0.9), rgba(36, 99, 160, 0.9));
  box-shadow: 0 0 0 3px rgba(72, 216, 255, 0.1);
}

.model-meta-row span.is-type,
.detail-tags span.is-type {
  color: #dff6ff;
  border-color: rgba(52, 190, 235, 0.46);
  background: linear-gradient(135deg, rgba(18, 132, 172, 0.78), rgba(15, 91, 130, 0.72));
}

.model-meta-row span.is-framework,
.detail-tags span.is-framework {
  color: #b8e6ff;
  border-color: rgba(53, 159, 215, 0.38);
  background: rgba(19, 82, 124, 0.64);
}

.model-meta-row span.is-architecture,
.detail-tags span.is-architecture {
  color: #b9d2ff;
  border-color: rgba(111, 132, 231, 0.38);
  background: rgba(49, 64, 126, 0.56);
}

.model-meta-row span.is-size,
.detail-tags span.is-size {
  color: #c8e7d7;
  border-color: rgba(83, 190, 157, 0.34);
  background: rgba(28, 100, 90, 0.48);
}

.model-meta-row span.is-custom,
.detail-tags span.is-custom {
  color: #cbd8e5;
  border-color: rgba(84, 175, 222, 0.24);
  background: rgba(8, 41, 64, 0.78);
}

.model-meta-row span.is-more,
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
  border-radius: 999px;
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

.model-status.is-building {
  border-color: rgba(240, 199, 93, 0.3);
  color: #f0d278;
  background: rgba(121, 91, 31, 0.24);
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
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(7, 28, 45, 0.74), rgba(4, 19, 31, 0.58));
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

.model-card footer :deep(.el-button) {
  min-height: 38px;
  margin-left: 0;
  border-radius: 9px;
  border-color: rgba(45, 161, 211, 0.34);
  color: #c6e7f6;
  background: linear-gradient(135deg, rgba(16, 67, 101, 0.9), rgba(10, 46, 73, 0.9));
  box-shadow: inset 0 1px 0 rgba(145, 225, 255, 0.05);
}

.model-card footer :deep(.el-button:hover) {
  border-color: rgba(72, 216, 255, 0.66);
  color: #f0fbff;
  background: linear-gradient(135deg, rgba(22, 99, 140, 0.94), rgba(14, 64, 99, 0.94));
}

.model-card footer :deep(.el-button--success) {
  border-color: rgba(79, 229, 183, 0.34);
  color: #aaf5d9;
  background: linear-gradient(135deg, rgba(27, 113, 103, 0.84), rgba(16, 77, 75, 0.88));
}

.model-card footer :deep(.el-button--danger.is-plain) {
  border-color: rgba(255, 117, 132, 0.34);
  color: #ffb0b8;
  background: rgba(104, 35, 52, 0.42);
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
  padding: 2px 0 18px;
  border-bottom: 1px solid rgba(84, 175, 222, 0.16);
}

.detail-title {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.detail-icon {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(84, 175, 222, 0.14);
  border-radius: 16px;
  font-size: 20px;
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.06), 0 10px 24px rgba(0, 0, 0, 0.12);
}

.detail-icon.is-ready {
  color: #4fe5b7;
  background: rgba(79, 229, 183, 0.12);
}

.detail-icon.is-building {
  color: #f0c75d;
  background: rgba(194, 143, 42, 0.14);
}

.detail-icon.is-idle {
  color: #91b9cf;
  background: rgba(84, 154, 196, 0.14);
}

.detail-icon.is-error {
  color: #ff9ca7;
  background: rgba(255, 108, 123, 0.12);
}

.detail-title-copy {
  min-width: 0;
}

.detail-eyebrow {
  display: block;
  overflow: hidden;
  color: #69cbe8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-panel h3 {
  margin: 6px 0 0;
  overflow: hidden;
  color: #f1fbff;
  font-size: 25px;
  font-weight: 760;
  letter-spacing: -0.02em;
  line-height: 1.22;
  text-overflow: ellipsis;
}

.drawer-close {
  width: 42px;
  height: 42px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(84, 175, 222, 0.18);
  border-radius: 14px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.42);
  cursor: pointer;
  transition: 160ms ease;
}

.drawer-close:hover {
  border-color: rgba(22, 192, 255, 0.34);
  color: #e9f7ff;
  background: rgba(20, 89, 126, 0.58);
  transform: translateY(-1px);
}

.detail-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 0 4px;
}

.detail-chip {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(84, 175, 222, 0.2);
  border-radius: 999px;
  color: #b8d6e7;
  background: rgba(16, 63, 94, 0.42);
  font-size: 13px;
  font-weight: 600;
}

.detail-chip.is-type,
.detail-tags span.is-type {
  border-color: rgba(62, 212, 247, 0.42);
  color: #a9f1ff;
  background: rgba(20, 139, 171, 0.3);
}

.detail-chip.is-framework,
.detail-tags span.is-framework {
  border-color: rgba(89, 194, 237, 0.28);
  color: #b9e5ff;
  background: rgba(26, 100, 143, 0.32);
}

.detail-chip.is-architecture,
.detail-tags span.is-architecture {
  border-color: rgba(141, 151, 255, 0.42);
  color: #c8ceff;
  background: rgba(80, 79, 173, 0.3);
}

.detail-chip.is-size,
.detail-tags span.is-size {
  border-color: rgba(79, 229, 183, 0.34);
  color: #b5f5df;
  background: rgba(27, 113, 103, 0.3);
}

.detail-chip.is-custom {
  border-color: rgba(84, 175, 222, 0.2);
  color: #bdd9e9;
  background: rgba(8, 41, 64, 0.72);
}

.detail-status-row .model-status {
  min-height: 30px;
  padding: 0 12px;
  font-weight: 700;
}

.detail-section {
  position: relative;
  overflow: hidden;
  margin-top: 16px;
  padding: 18px;
  border: 1px solid rgba(21, 160, 218, 0.22);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(10, 39, 58, 0.92), rgba(5, 23, 37, 0.9));
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.035), 0 12px 28px rgba(0, 0, 0, 0.1);
}

.detail-section::before {
  position: absolute;
  top: 0;
  right: 18px;
  left: 18px;
  height: 1px;
  border-radius: 1px;
  background: linear-gradient(90deg, rgba(72, 216, 255, 0.68), transparent 72%);
  content: "";
  opacity: 0.65;
}

.detail-summary {
  background: linear-gradient(145deg, rgba(11, 59, 81, 0.82), rgba(6, 30, 46, 0.94));
}

.detail-section > h4,
.detail-section-title h4 {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #a9d6e9;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: 0.01em;
}

.detail-section > h4::before,
.detail-section-title h4::before {
  width: 4px;
  height: 17px;
  flex: 0 0 auto;
  border-radius: 99px;
  background: linear-gradient(180deg, #55dfff, #2da2d4);
  box-shadow: 0 0 12px rgba(72, 216, 255, 0.3);
  content: "";
}

.detail-section h4 {
  margin-bottom: 12px;
}

.detail-summary p {
  color: #e0f2fa;
  font-size: 16px;
  line-height: 1.7;
}

.detail-list div {
  min-height: 46px;
  padding: 11px 0;
}

.detail-list dt {
  color: #8ebbd0;
  font-size: 14px;
  font-weight: 600;
}

.detail-list dd {
  color: #edf9ff;
  font-size: 15px;
  font-weight: 600;
}

.detail-tags {
  gap: 9px;
}

.detail-tags span {
  padding: 7px 12px;
  border-radius: 999px;
  font-weight: 600;
}

.detail-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  margin-top: auto;
  padding: 18px 0 2px;
  border-top: 1px solid rgba(84, 175, 222, 0.16);
  background: linear-gradient(180deg, rgba(8, 24, 36, 0), #081824 28%);
}

.detail-actions .el-button {
  min-height: 46px;
  border-radius: 12px;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.06);
}

.detail-actions .el-button--danger.is-plain {
  border-color: rgba(255, 117, 132, 0.34);
  color: #ffb0b8;
  background: rgba(104, 35, 52, 0.32);
}

.detail-actions .el-button--success {
  border-color: rgba(79, 229, 183, 0.44);
  color: #c4ffea;
  background: linear-gradient(135deg, rgba(27, 125, 112, 0.86), rgba(18, 86, 83, 0.92));
}

.detail-actions .el-button--success:hover {
  border-color: rgba(111, 247, 205, 0.72);
  background: linear-gradient(135deg, rgba(39, 157, 134, 0.96), rgba(23, 111, 105, 0.96));
}

.import-actions {
  margin-top: 20px;
  padding: 16px 0 4px;
  background: linear-gradient(180deg, rgba(8, 24, 36, 0), #081824 24%);
}

.import-action-status {
  padding: 9px 12px;
  border: 1px solid rgba(84, 175, 222, 0.16);
  border-radius: 12px;
  background: rgba(6, 29, 45, 0.78);
}

.import-action-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.import-action-copy > span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-action-label {
  color: #6fa4bc;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.1;
}

.import-action-buttons .el-button {
  min-height: 46px;
  border-radius: 12px;
  font-weight: 700;
}

.reset-import-button {
  border-color: rgba(84, 175, 222, 0.3) !important;
  color: #b8d6e7 !important;
  background: rgba(16, 63, 94, 0.5) !important;
}

.reset-import-button:hover {
  border-color: rgba(72, 216, 255, 0.6) !important;
  color: #effaff !important;
  background: rgba(20, 89, 126, 0.64) !important;
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

.detail-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.detail-section-title h4 {
  margin-bottom: 0;
}

.detail-section-title .el-button {
  margin-left: 0;
  padding: 4px 6px;
  color: #70cfff;
}

.detail-section-title .el-button:hover {
  color: #b9edff;
  background: rgba(72, 216, 255, 0.1);
}

.detail-summary :deep(.el-textarea__inner) {
  min-height: 118px !important;
  border: 1px solid rgba(84, 175, 222, 0.28);
  color: #f3fbff;
  background: #0e2639;
  box-shadow: none;
  resize: vertical;
}

.detail-summary :deep(.el-textarea__inner:hover) {
  border-color: rgba(72, 216, 255, 0.5);
}

.detail-summary :deep(.el-textarea__inner:focus) {
  border-color: #48d8ff;
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.2);
}

.detail-summary :deep(.el-textarea__inner::placeholder) {
  color: #6f95aa;
}

.detail-summary :deep(.el-input__count) {
  color: #7fa7bc;
  background: transparent;
}

.metadata-edit-form {
  display: grid;
  gap: 12px;
}

.metadata-edit-field {
  display: grid;
  gap: 6px;
  color: #a9d5e8;
  font-size: 13px;
  font-weight: 650;
}

.metadata-edit-field small {
  color: #7098ac;
  font-size: 12px;
  font-weight: 400;
}

.metadata-edit-field :deep(.el-input__wrapper),
.metadata-edit-field :deep(.el-textarea__inner) {
  border: 1px solid rgba(84, 175, 222, 0.28);
  color: #f3fbff;
  background: #0e2639;
  box-shadow: none;
}

.metadata-edit-field :deep(.el-input__wrapper:hover),
.metadata-edit-field :deep(.el-input__wrapper.is-focus),
.metadata-edit-field :deep(.el-textarea__inner:hover),
.metadata-edit-field :deep(.el-textarea__inner:focus) {
  border-color: #48d8ff;
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.2);
}

.description-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.description-actions .el-button {
  margin-left: 0;
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

.folder-input {
  display: none;
}

.import-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  color: #e9f7ff;
}

.import-title-copy {
  min-width: 0;
}

.import-title-copy h3 {
  margin: 0 0 4px;
  color: #effaff;
  font-size: 22px;
  font-weight: 750;
  line-height: 1.2;
}

.import-title-copy span {
  display: block;
  overflow: hidden;
  color: #8fb6cb;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-section {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid rgba(68, 164, 207, 0.18);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(10, 39, 58, 0.92), rgba(6, 25, 40, 0.9));
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.03);
}

.folder-picker {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 86px;
  padding: 14px;
  border-color: rgba(58, 190, 231, 0.34);
  background: linear-gradient(145deg, rgba(12, 61, 84, 0.82), rgba(7, 32, 50, 0.96));
}

.folder-picker.has-folder {
  border-color: rgba(79, 229, 183, 0.42);
}

.folder-picker-icon {
  width: 42px;
  height: 42px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(93, 218, 245, 0.24);
  border-radius: 10px;
  color: #74ddf5;
  background: rgba(33, 133, 166, 0.18);
  font-size: 21px;
}

.folder-picker-copy {
  min-width: 0;
  flex: 1;
}

.folder-picker-copy h4 {
  margin-top: 4px;
  overflow: hidden;
  color: #e5f6ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-picker-copy p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-select-button {
  flex: 0 0 auto;
  min-height: 38px;
  margin-left: auto;
  border-color: rgba(81, 204, 237, 0.38) !important;
  border-radius: 9px;
  color: #c8f3ff !important;
  background: rgba(17, 91, 126, 0.54) !important;
}

.folder-select-button:hover {
  border-color: rgba(105, 229, 255, 0.72) !important;
  background: rgba(18, 113, 151, 0.7) !important;
}

.import-section h4 {
  margin: 0;
  color: #d8edf8;
  font-size: 15px;
  font-weight: 700;
}

.import-section p {
  margin: 6px 0 0;
  color: #91bdd5;
  font-size: 13px;
  line-height: 1.45;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.section-title > div {
  min-width: 0;
}

.import-step-label {
  display: block;
  margin-bottom: 4px;
  color: #58c9e8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.2;
}

.import-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(128, 169, 190, 0.28);
  border-radius: 999px;
  color: #9bb7c8;
  background: rgba(67, 105, 124, 0.18);
  font-size: 12px;
  font-weight: 700;
}

.import-status-pill.is-success {
  border-color: rgba(79, 229, 183, 0.38);
  color: #8cf0c8;
  background: rgba(35, 130, 108, 0.2);
}

.import-status-pill.is-error {
  border-color: rgba(255, 142, 153, 0.38);
  color: #ffb4bd;
  background: rgba(140, 50, 66, 0.2);
}

.import-status-pill.is-loading {
  border-color: rgba(72, 216, 255, 0.42);
  color: #9beaff;
  background: rgba(30, 127, 163, 0.2);
}

.import-status-icon {
  margin-right: 5px;
}

.check-empty {
  padding: 12px;
  border: 1px dashed rgba(84, 175, 222, 0.22);
  border-radius: 9px;
  color: #789bad;
  background: rgba(4, 19, 31, 0.24);
  font-size: 13px;
  line-height: 1.5;
}

.check-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.check-item {
  min-width: 0;
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(84, 175, 222, 0.14);
  border-radius: 8px;
  background: rgba(4, 19, 31, 0.34);
  color: #bdd9e9;
  font-size: 13px;
  line-height: 1.35;
}

.check-item .el-icon {
  flex: 0 0 auto;
  font-size: 16px;
}

.check-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.check-item.is-success {
  color: #7ee8c5;
}

.check-item.is-warning {
  color: #f0c75d;
}

.check-item.is-error {
  color: #ff9ca7;
}

.server-result {
  display: grid;
  gap: 8px;
}

.server-result p {
  margin: 0;
  padding: 8px 10px;
  border: 1px solid rgba(84, 175, 222, 0.14);
  border-radius: 8px;
  background: rgba(4, 19, 31, 0.34);
}

.import-form {
  margin-top: 16px;
}

.import-form :deep(.el-form-item__label) {
  color: #a9cfe3;
  font-weight: 600;
}

.import-form :deep(.el-input__wrapper),
.import-form :deep(.el-textarea__inner),
.import-form :deep(.el-select__wrapper) {
  min-height: 40px;
  border: 1px solid rgba(84, 175, 222, 0.24);
  border-radius: 8px;
  background: #0e2639;
  box-shadow: none;
}

.import-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.import-form :deep(.el-form-item__label) {
  padding-bottom: 5px;
}

.import-form :deep(.el-textarea__inner) {
  min-height: 92px !important;
}

.import-form :deep(.el-input__wrapper:hover),
.import-form :deep(.el-textarea__inner:hover),
.import-form :deep(.el-select__wrapper:hover) {
  border-color: rgba(72, 216, 255, 0.48);
}

.import-form :deep(.el-input__wrapper.is-focus),
.import-form :deep(.el-textarea__inner:focus),
.import-form :deep(.el-select__wrapper.is-focused) {
  border-color: #48d8ff;
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.2);
}

.import-form :deep(.el-input__inner),
.import-form :deep(.el-textarea__inner),
.import-form :deep(.el-select__selected-item) {
  color: #f3fbff;
}

.import-form :deep(.el-input__inner::placeholder),
.import-form :deep(.el-textarea__inner::placeholder) {
  color: #6f95aa;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.import-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 16px;
  padding: 16px 0 2px;
  border-top: 1px solid rgba(84, 175, 222, 0.16);
  background: #081824;
}

.import-action-status {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #82a9bc;
  font-size: 12px;
}

.import-action-status > span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-action-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #7599ac;
  box-shadow: 0 0 0 4px rgba(117, 153, 172, 0.1);
}

.import-action-status.is-loading {
  color: #9beaff;
}

.import-action-status.is-loading .import-action-dot {
  background: #48d8ff;
  box-shadow: 0 0 0 4px rgba(72, 216, 255, 0.12), 0 0 12px rgba(72, 216, 255, 0.58);
  animation: import-status-pulse 1.2s ease-in-out infinite;
}

.import-action-status.is-success {
  color: #8cf0c8;
}

.import-action-status.is-success .import-action-dot {
  background: #4fe5b7;
  box-shadow: 0 0 0 4px rgba(79, 229, 183, 0.1), 0 0 12px rgba(79, 229, 183, 0.42);
}

.import-action-status.is-error {
  color: #ffb4bd;
}

.import-action-status.is-error .import-action-dot {
  background: #ff8e99;
  box-shadow: 0 0 0 4px rgba(255, 142, 153, 0.1);
}

.import-action-buttons {
  display: grid;
  grid-template-columns: minmax(112px, 0.8fr) minmax(156px, 1.2fr);
  gap: 10px;
  flex: 0 0 290px;
}

.import-actions .el-button {
  min-height: 42px;
  margin-left: 0;
  border-radius: 9px;
  font-weight: 600;
}

.import-actions .el-button--primary {
  border-color: rgba(79, 229, 183, 0.56);
  color: #dffff1;
  background: linear-gradient(135deg, rgba(30, 139, 119, 0.94), rgba(18, 99, 91, 0.96));
}

.import-actions .el-button--primary:not(.is-disabled):hover {
  border-color: rgba(111, 247, 205, 0.78);
  background: linear-gradient(135deg, #279d86, #176f69);
}

.import-actions .el-button.is-disabled {
  opacity: 0.46;
}

@keyframes import-status-pulse {
  0%, 100% { opacity: 0.55; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.12); }
}

.registration-title {
  align-items: flex-end;
}

.registration-hint {
  color: #7599ac;
  font-size: 12px;
}

:global(.model-detail-drawer .el-drawer__body),
:global(.model-import-drawer .el-drawer__body) {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  padding: 22px;
  background: #081824;
  overflow: hidden;
}

.detail-panel,
.import-panel {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.drawer-scroll-content {
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-color: rgba(72, 216, 255, 0.36) transparent;
  scrollbar-width: thin;
}

.drawer-scroll-content::-webkit-scrollbar {
  width: 6px;
}

.drawer-scroll-content::-webkit-scrollbar-thumb {
  border-radius: 99px;
  background: rgba(72, 216, 255, 0.34);
}

.detail-actions,
.import-actions {
  position: relative;
  bottom: auto;
  flex: 0 0 auto;
  margin-top: 0;
}

.detail-section {
  margin-top: 16px;
  padding: 18px;
  border-color: rgba(21, 160, 218, 0.22);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(10, 39, 58, 0.92), rgba(5, 23, 37, 0.9));
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.035), 0 12px 28px rgba(0, 0, 0, 0.1);
}

.detail-summary {
  background: linear-gradient(145deg, rgba(11, 59, 81, 0.82), rgba(6, 30, 46, 0.94));
}

.detail-section > h4,
.detail-section-title h4 {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #a9d6e9;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: 0.01em;
}

.detail-section > h4::before,
.detail-section-title h4::before {
  width: 4px;
  height: 17px;
  flex: 0 0 auto;
  border-radius: 99px;
  background: linear-gradient(180deg, #55dfff, #2da2d4);
  box-shadow: 0 0 12px rgba(72, 216, 255, 0.3);
  content: "";
}

.detail-section h4 {
  margin-bottom: 12px;
}

.detail-summary p {
  margin: 0;
  color: #e0f2fa;
  font-size: 16px;
  line-height: 1.7;
}

.detail-list div {
  min-height: 46px;
  padding: 11px 0;
}

.detail-list dt {
  color: #8ebbd0;
  font-size: 14px;
  font-weight: 600;
}

.detail-list dd {
  color: #edf9ff;
  font-size: 15px;
  font-weight: 600;
}

.detail-tags {
  gap: 9px;
}

.detail-tags span {
  padding: 7px 12px;
  border-radius: 999px;
  font-weight: 600;
}

.detail-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  margin-top: auto;
  padding: 18px 0 2px;
  border-top: 1px solid rgba(84, 175, 222, 0.16);
  background: linear-gradient(180deg, rgba(8, 24, 36, 0), #081824 28%);
}

.detail-actions .el-button {
  min-height: 46px;
  border-radius: 12px;
  font-weight: 700;
  box-shadow: inset 0 1px 0 rgba(163, 232, 255, 0.06);
}

.detail-actions .el-button--danger.is-plain {
  border-color: rgba(255, 117, 132, 0.34);
  color: #ffb0b8;
  background: rgba(104, 35, 52, 0.32);
}

.detail-actions .el-button--success {
  border-color: rgba(79, 229, 183, 0.44);
  color: #c4ffea;
  background: linear-gradient(135deg, rgba(27, 125, 112, 0.86), rgba(18, 86, 83, 0.92));
}

.detail-actions .el-button--success:hover {
  border-color: rgba(111, 247, 205, 0.72);
  background: linear-gradient(135deg, rgba(39, 157, 134, 0.96), rgba(23, 111, 105, 0.96));
}

.import-section {
  margin-top: 16px;
  padding: 18px;
  border-radius: 16px;
}

.folder-picker {
  min-height: 104px;
}

.registration-section {
  border-color: rgba(72, 216, 255, 0.25);
}

.import-actions {
  margin-top: 20px;
  padding: 16px 0 4px;
  background: linear-gradient(180deg, rgba(8, 24, 36, 0), #081824 24%);
}

.import-action-status {
  flex: 1 1 auto;
  padding: 9px 12px;
  border: 1px solid rgba(84, 175, 222, 0.16);
  border-radius: 12px;
  background: rgba(6, 29, 45, 0.78);
}

.import-action-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.import-action-copy > span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-action-label {
  color: #6fa4bc;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 1.1;
}

.import-action-buttons {
  flex: 0 0 300px;
}

.import-action-buttons .el-button {
  min-height: 46px;
  border-radius: 12px;
  font-weight: 700;
}

.reset-import-button {
  border-color: rgba(84, 175, 222, 0.3) !important;
  color: #b8d6e7 !important;
  background: rgba(16, 63, 94, 0.5) !important;
}

.reset-import-button:hover {
  border-color: rgba(72, 216, 255, 0.6) !important;
  color: #effaff !important;
  background: rgba(20, 89, 126, 0.64) !important;
}

:deep(.model-detail-drawer) {
  background: #081824;
}

:deep(.model-import-drawer) {
  background: #081824;
}

:deep(.model-detail-drawer.el-drawer),
:deep(.model-import-drawer.el-drawer) {
  top: 24px;
  right: 18px;
  bottom: 24px;
  height: auto;
  overflow: hidden;
  border: 1px solid rgba(72, 216, 255, 0.2);
  border-radius: 20px;
  box-shadow: -18px 0 48px rgba(0, 0, 0, 0.28), inset 1px 0 0 rgba(163, 232, 255, 0.04);
}

:global(.model-detail-drawer.el-drawer),
:global(.model-import-drawer.el-drawer) {
  top: 48px !important;
  right: 24px !important;
  bottom: 48px !important;
  height: auto !important;
  border-radius: 26px !important;
  box-shadow: -24px 0 64px rgba(0, 0, 0, 0.34), 0 18px 48px rgba(0, 0, 0, 0.24) !important;
}

/* 内容较长，但抽屉不应占满页面；超出部分由内部区域滚动。 */
:global(.model-detail-drawer.el-drawer),
:global(.model-import-drawer.el-drawer) {
  top: max(40px, calc((100vh - min(900px, calc(100vh - 80px))) / 2)) !important;
  bottom: auto !important;
  height: min(900px, calc(100vh - 80px)) !important;
}

:deep(.detail-actions .el-button) {
  margin-left: 0;
}

:deep(.model-tag-tooltip.el-popper.is-dark) {
  max-width: 280px;
  padding: 9px 12px;
  border: 1px solid rgba(72, 216, 255, 0.48) !important;
  border-radius: 10px;
  color: #e7faff !important;
  background: linear-gradient(135deg, #123b57, #0b263b) !important;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.34), 0 0 18px rgba(22, 192, 255, 0.1);
  font-size: 13px;
  line-height: 1.5;
}

:deep(.model-tag-tooltip.el-popper.is-dark .el-popper__arrow::before) {
  border: 1px solid rgba(72, 216, 255, 0.48) !important;
  background: #10344d !important;
}

:deep(.model-delete-dialog.el-dialog) {
  overflow: hidden;
  padding: 0;
  border: 1px solid rgba(255, 142, 153, 0.28);
  border-radius: 18px;
  background: linear-gradient(145deg, #102c3f, #081824);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.48), 0 0 26px rgba(255, 89, 108, 0.08);
}

:deep(.model-delete-dialog .el-dialog__header) {
  margin: 0;
  padding: 0;
}

:deep(.model-delete-dialog .el-dialog__body) {
  padding: 0 22px 20px;
}

:deep(.model-delete-dialog .el-dialog__footer) {
  padding: 0 22px 20px;
}

:global(.model-delete-dialog.el-dialog) {
  border-color: rgba(72, 216, 255, 0.24) !important;
  background: #0b1c2b !important;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.52), 0 0 26px rgba(72, 216, 255, 0.06) !important;
  color: #eaf8ff !important;
}

.delete-dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 22px 16px;
  border-bottom: 1px solid rgba(84, 175, 222, 0.14);
}

.delete-dialog-icon {
  width: 40px;
  height: 40px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(240, 199, 93, 0.38);
  border-radius: 12px;
  color: #f0c75d;
  background: rgba(150, 111, 35, 0.18);
  font-size: 19px;
}

.delete-dialog-title {
  min-width: 0;
  flex: 1;
}

.delete-dialog-title > span {
  color: #f0c75d;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.delete-dialog-title h3 {
  margin: 4px 0 0;
  color: #f0faff;
  font-size: 19px;
  font-weight: 760;
}

.delete-dialog-close {
  width: 32px;
  height: 32px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(84, 175, 222, 0.2);
  border-radius: 9px;
  color: #9bb7c8;
  background: rgba(16, 63, 94, 0.36);
  cursor: pointer;
}

.delete-dialog-close:hover {
  border-color: rgba(72, 216, 255, 0.5);
  color: #effaff;
  background: rgba(20, 89, 126, 0.56);
}

.delete-dialog-body {
  padding-top: 18px;
}

.delete-dialog-body > p {
  margin: 0 0 14px;
  color: #e5f5fc;
  font-size: 15px;
  font-weight: 650;
}

.delete-dialog-warning {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 12px;
  border: 1px solid rgba(240, 199, 93, 0.26);
  border-radius: 11px;
  color: #f1d992;
  background: rgba(126, 92, 28, 0.16);
  font-size: 13px;
  line-height: 1.5;
}

.delete-dialog-warning .el-icon {
  margin-top: 1px;
  flex: 0 0 auto;
}

.delete-dialog-list {
  display: grid;
  gap: 7px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.delete-dialog-list li {
  position: relative;
  padding-left: 16px;
  color: #a9c9d9;
  font-size: 13px;
  line-height: 1.45;
}

.delete-dialog-list li::before {
  position: absolute;
  top: 0.55em;
  left: 1px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #58d8ef;
  box-shadow: 0 0 8px rgba(88, 216, 239, 0.36);
  content: "";
}

.delete-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.delete-dialog-actions .el-button {
  min-width: 92px;
  min-height: 38px;
  margin-left: 0;
  border-radius: 10px;
  font-weight: 700;
}

.delete-dialog-actions .el-button--danger {
  border-color: rgba(255, 117, 132, 0.52);
  background: linear-gradient(135deg, #a44758, #7e3042);
}

.delete-dialog-actions .el-button--danger:hover {
  border-color: rgba(255, 176, 184, 0.76);
  background: linear-gradient(135deg, #bd5666, #963b4e);
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
    .detail-actions,
    .check-list,
    .form-grid,
    .import-action-buttons {
      grid-template-columns: 1fr;
    }

    .import-actions {
      align-items: stretch;
      flex-direction: column;
    }

    .import-action-status,
    .import-action-buttons {
      width: 100%;
      flex-basis: auto;
    }

  .model-list {
    grid-template-columns: 1fr;
  }

  .page-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .page-actions,
  .page-actions .el-button,
  .folder-picker,
  .folder-picker .el-button {
    width: 100%;
  }

  .folder-picker {
    align-items: stretch;
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

@media (max-width: 900px) {
  :global(.model-detail-drawer.el-drawer),
  :global(.model-import-drawer.el-drawer) {
    top: 32px !important;
    right: 12px !important;
    bottom: 32px !important;
    border-radius: 22px !important;
  }

  :global(.model-detail-drawer.el-drawer),
  :global(.model-import-drawer.el-drawer) {
    top: max(24px, calc((100vh - min(760px, calc(100vh - 48px))) / 2)) !important;
    bottom: auto !important;
    height: min(760px, calc(100vh - 48px)) !important;
  }

  :global(.model-detail-drawer .el-drawer__body),
  :global(.model-import-drawer .el-drawer__body) {
    padding: 16px;
  }
}
</style>
