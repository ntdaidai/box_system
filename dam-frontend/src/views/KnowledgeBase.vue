<template>
  <div class="knowledge-base">
    <div class="stats-cards">
      <article class="stat-card tone-total">
        <el-icon class="stat-icon"><Collection /></el-icon>
        <div class="stat-info">
          <span class="stat-label">知识库</span>
          <span class="stat-value">{{ stats.baseCount }}</span>
          <small>当前启用范围</small>
        </div>
      </article>
      <article class="stat-card tone-category">
        <el-icon class="stat-icon"><Document /></el-icon>
        <div class="stat-info">
          <span class="stat-label">知识文档</span>
          <span class="stat-value">{{ stats.documentCount }}</span>
          <small>已导入文件</small>
        </div>
      </article>
      <article class="stat-card tone-month">
        <el-icon class="stat-icon"><Files /></el-icon>
        <div class="stat-info">
          <span class="stat-label">知识片段</span>
          <span class="stat-value">{{ stats.chunkCount }}</span>
          <small>可被模型检索</small>
        </div>
      </article>
      <article class="stat-card tone-selected">
        <el-icon class="stat-icon"><CircleCheck /></el-icon>
        <div class="stat-info">
          <span class="stat-label">索引完成率</span>
          <span class="stat-value">{{ indexedRate }}%</span>
          <small>{{ indexedCount }}/{{ documents.length }} 已索引</small>
        </div>
      </article>
    </div>

    <div class="filter-section">
      <div class="filter-field">
        <el-select v-model="selectedBaseId" placeholder="选择知识库" class="base-select" @change="handleBaseChange">
          <el-option
            v-for="base in bases"
            :key="base.id"
            :label="base.name"
            :value="base.id"
          />
        </el-select>
      </div>
      <div class="filter-field">
        <el-select v-model="selectedType" placeholder="全部类型" clearable class="type-select">
          <el-option
            v-for="type in fileTypes"
            :key="type"
            :label="type.toUpperCase()"
            :value="type"
          />
        </el-select>
      </div>
      <div class="filter-field">
        <el-select v-model="sortBy" placeholder="排序方式" class="sort-select" @change="handleSortChange">
          <el-option
            v-for="option in sortOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
      <div class="filter-field search-field">
        <el-input
          v-model="keyword"
          placeholder="搜索知识文档"
          :prefix-icon="Search"
          clearable
          class="search-input"
        />
      </div>
      <div class="filter-actions">
        <el-upload
          :show-file-list="false"
          :http-request="uploadKnowledge"
          accept=".txt,.md,.pdf,.docx,.xlsx,.xls,.csv,.json,.log"
        >
          <el-button class="upload-button" :loading="uploading">
            <el-icon><Upload /></el-icon>
            导入知识
          </el-button>
        </el-upload>
      </div>
    </div>

    <section class="document-table-panel" :class="{ 'is-empty': !filteredDocuments.length }" v-loading="loadingDocuments">
      <div v-if="filteredDocuments.length" class="document-list">
        <div class="document-header">
          <div class="row-index">序号</div>
          <div class="row-name">文档</div>
          <div class="row-type">类型</div>
          <div class="row-size">大小</div>
          <div class="row-chunks">片段数</div>
          <div class="row-sections">章节数</div>
          <div class="row-tokens">Token 量</div>
          <button type="button" class="row-date sortable-header" :class="sortClass('created')" @click="toggleSort('created')">
            <span>创建时间</span>
            <span class="caret-wrapper"><i class="sort-caret ascending"></i><i class="sort-caret descending"></i></span>
          </button>
          <div class="row-status">状态</div>
          <div class="row-actions">操作</div>
        </div>

        <div
          v-for="(doc, index) in paginatedDocuments"
          :key="doc.id"
          class="document-row"
        >
          <div class="row-index">{{ pageStartIndex + index + 1 }}</div>
          <div class="row-name" @click="openDocument(doc)">
            <el-icon class="doc-icon" :class="getIconClass(doc.file_type)">
              <Document />
            </el-icon>
            <span class="doc-title-stack" :title="doc.title">
              <strong class="doc-name">{{ doc.title }}</strong>
            </span>
          </div>
          <div class="row-type">
            <span class="type-badge" :class="getTypeBadgeClass(doc.file_type)">
              {{ getTypeLabel(doc.file_type) }}
            </span>
          </div>
          <div class="row-size">{{ formatFileSize(doc.file_size) }}</div>
          <div class="row-chunks">{{ doc.chunk_count ?? '-' }}</div>
          <div class="row-sections">{{ doc.section_count ?? '-' }}</div>
          <div class="row-tokens">{{ formatTokens(doc.token_count) }}</div>
          <div class="row-date">{{ formatTime(doc.create_time) }}</div>
          <div class="row-status">
            <span class="status-pill" :class="`status-${doc.status}`">
              {{ statusLabel(doc.status) }}
            </span>
          </div>
          <div class="row-actions">
            <el-button
              class="action-button preview-button"
              size="small"
              :disabled="!supportsOnlyOffice(doc)"
              @click="openDocument(doc)"
            >
              预览
            </el-button>
            <el-button
              class="action-button edit-button"
              size="small"
              :disabled="!supportsEditing(doc)"
              @click="openEditor(doc)"
            >
              编辑
            </el-button>
            <el-button
              class="action-button download-button"
              size="small"
              :disabled="isPdfDocument(doc)"
              @click="downloadDocument(doc)"
            >
              下载 Word
            </el-button>
            <el-button
              class="action-button download-pdf-button"
              size="small"
              :loading="downloadingPdfId === doc.id"
              @click="downloadPdf(doc)"
            >
              下载 PDF
            </el-button>
            <el-button class="action-button delete-button" size="small" @click="deleteDocument(doc)">
              删除
            </el-button>
          </div>
        </div>
      </div>

      <div v-if="!loadingDocuments && filteredDocuments.length === 0" class="empty-state">
        <el-icon class="empty-icon"><Collection /></el-icon>
        <h3>暂无知识文档</h3>
        <p>导入巡查规范、应急预案或设备手册后，模型即可检索引用。</p>
      </div>

      <div v-if="!loadingDocuments && filteredDocuments.length > 0" class="pagination-bar">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredDocuments.length"
          background
          layout="prev, pager, next"
        />
      </div>
    </section>

    <AppDialog
      v-model="previewDialogVisible"
      class="knowledge-preview-dialog"
      fullscreen
      :show-close="false"
      destroy-on-close
      @closed="resetPreview"
    >
      <template #header>
        <div class="preview-header">
          <el-button class="preview-back-button" :icon="ArrowLeft" @click="closePreview">返回</el-button>
          <div class="preview-title-stack">
            <span class="preview-kicker">{{ previewMode === 'edit' ? '知识文档编辑' : '知识文档预览' }}</span>
            <h2 class="preview-title" :title="previewTitle">{{ previewTitle }}</h2>
          </div>
        </div>
      </template>

      <div v-loading="previewLoading" class="preview-shell">
        <template v-if="previewDocument">
          <div v-loading="officeLoading" class="preview-editor-shell">
            <OnlyOfficeEditor
              v-if="officeConfig"
              :config="officeConfig"
              :mode="previewMode"
              editor-height="100%"
              @error="onOfficeError"
            />
            <el-empty v-else-if="officeError" :description="officeError" />
          </div>
        </template>
      </div>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  CircleCheck,
  Collection,
  Document,
  Files,
  Search,
  Upload,
} from '@element-plus/icons-vue'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'
import request from '@/utils/request'
import axios from 'axios'

const bases = ref([])
const selectedBaseId = ref(null)
const documents = ref([])
const keyword = ref('')
const selectedType = ref('')
const sortBy = ref('created')
const sortOrder = ref('desc')
const loadingDocuments = ref(false)
const uploading = ref(false)
const currentPage = ref(1)
const pageSize = 8

const sortOptions = [
  { value: 'created', label: '最近创建', order: 'desc' },
  { value: 'name', label: '文档名称', order: 'asc' },
  { value: 'size', label: '文档大小', order: 'desc' },
]

const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewDocument = ref(null)
const previewMode = ref('view') // 'view' 预览 | 'edit' 编辑
const officeLoading = ref(false)
const officeConfig = ref(null)
const officeError = ref('')

const onlyOfficeExtensions = new Set([
  'doc', 'docx', 'odt', 'rtf', 'txt',
  'xls', 'xlsx', 'ods', 'csv',
  'ppt', 'pptx', 'odp', 'pdf',
])

const stats = computed(() => bases.value.reduce(
  (acc, base) => {
    acc.baseCount += 1
    acc.documentCount += Number(base.document_count || 0)
    acc.chunkCount += Number(base.chunk_count || 0)
    return acc
  },
  { baseCount: 0, documentCount: 0, chunkCount: 0 }
))

const fileTypes = computed(() => Array.from(new Set(documents.value.map((doc) => doc.file_type).filter(Boolean))).sort())

const filteredDocuments = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  let rows = [...documents.value]
  if (query) {
    rows = rows.filter((doc) => `${doc.title} ${doc.filename}`.toLowerCase().includes(query))
  }
  if (selectedType.value) {
    rows = rows.filter((doc) => doc.file_type === selectedType.value)
  }
  rows.sort((a, b) => {
    const direction = sortOrder.value === 'asc' ? 1 : -1
    if (sortBy.value === 'name') return documentName(a).localeCompare(documentName(b), 'zh-CN') * direction
    if (sortBy.value === 'size') return (Number(a.file_size || 0) - Number(b.file_size || 0)) * direction
    if (sortBy.value === 'created') return (dateValue(a.create_time) - dateValue(b.create_time)) * direction
    return 0
  })
  return rows
})

const pageStartIndex = computed(() => (currentPage.value - 1) * pageSize)
const paginatedDocuments = computed(() => filteredDocuments.value.slice(pageStartIndex.value, pageStartIndex.value + pageSize))
const previewTitle = computed(() => previewDocument.value?.title || '知识文档')
const indexedCount = computed(() => documents.value.filter((doc) => doc.status === 'indexed').length)
const indexedRate = computed(() => {
  if (!documents.value.length) return 0
  return Math.round((indexedCount.value / documents.value.length) * 100)
})

watch([keyword, selectedType, sortBy, sortOrder], () => {
  currentPage.value = 1
})

watch(filteredDocuments, (rows) => {
  const maxPage = Math.max(1, Math.ceil(rows.length / pageSize))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})

onMounted(loadAll)

async function loadAll() {
  await loadBases()
  await loadDocuments()
}

async function loadBases() {
  const response = await request.get('/v1/knowledge/bases')
  bases.value = response.data || []
  if (!selectedBaseId.value && bases.value.length) {
    selectedBaseId.value = bases.value[0].id
  }
}

async function handleBaseChange() {
  await loadDocuments()
}

async function loadDocuments() {
  loadingDocuments.value = true
  try {
    const response = await request.get('/v1/knowledge/documents', {
      params: {
        base_id: selectedBaseId.value || undefined,
        page_size: 100,
      },
    })
    documents.value = response.data?.records || []
  } finally {
    loadingDocuments.value = false
  }
}

async function uploadKnowledge(options) {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', options.file)
    if (selectedBaseId.value) formData.append('base_id', selectedBaseId.value)
    formData.append('category', 'inspection')
    await request.post('/v1/knowledge/documents/upload', formData, {
      timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('知识文档已导入并完成索引')
    await loadAll()
  } catch (error) {
    options.onError?.(error)
  } finally {
    uploading.value = false
  }
}

async function openDocument(row) {
  await openWithMode(row, 'view')
}

// 打开编辑器（mode='edit'），保存后由后端回调写回并重新索引
async function openEditor(row) {
  if (!supportsEditing(row)) {
    ElMessage.warning('该文件类型暂不支持在线编辑')
    return
  }
  await openWithMode(row, 'edit')
}

async function openWithMode(row, mode) {
  if (!supportsOnlyOffice(row)) {
    ElMessage.warning('该文件类型暂不支持 OnlyOffice 原文预览，可下载后查看')
    return
  }
  previewMode.value = mode
  previewDialogVisible.value = true
  previewLoading.value = true
  previewDocument.value = null
  officeConfig.value = null
  officeError.value = ''
  try {
    const response = await request.get(`/v1/knowledge/documents/${row.id}`)
    previewDocument.value = response.data
    await loadOfficePreview(previewDocument.value.id, mode)
  } finally {
    previewLoading.value = false
  }
}

async function loadOfficePreview(documentId, mode) {
  if (!documentId || officeConfig.value || officeLoading.value) return
  officeLoading.value = true
  officeError.value = ''
  try {
    const response = await request.get(`/v1/knowledge/documents/${documentId}/onlyoffice-config`, {
      params: {
        user_id: 'knowledge_user',
        user_name: '知识库用户',
        mode: mode || 'view',
      },
      localCacheAllowStale: false,
    })
    officeConfig.value = response.data
  } catch (error) {
    officeError.value = error.response?.data?.detail || 'OnlyOffice 暂时无法预览该文档'
  } finally {
    officeLoading.value = false
  }
}

function closePreview() {
  previewDialogVisible.value = false
}

function resetPreview() {
  previewDocument.value = null
  officeConfig.value = null
  officeError.value = ''
  // 编辑模式下关闭后稍等保存回调落库，再刷新列表
  if (previewMode.value === 'edit') {
    setTimeout(loadAll, 2500)
  }
  previewMode.value = 'view'
}

function onOfficeError(error) {
  officeError.value = error || 'OnlyOffice 预览失败'
}

function supportsOnlyOffice(document) {
  return onlyOfficeExtensions.has(String(document?.file_type || '').toLowerCase())
}

// 在线编辑仅支持可被 OnlyOffice 编辑的办公文档（PDF 仅可预览/下载）
const editingExtensions = new Set([
  'doc', 'docx', 'odt', 'rtf', 'txt',
  'xls', 'xlsx', 'ods', 'csv',
  'ppt', 'pptx', 'odp',
])

function supportsEditing(document) {
  return editingExtensions.has(String(document?.file_type || '').toLowerCase())
}

function isPdfDocument(document) {
  const fileType = String(document?.file_type || '').trim().toLowerCase().replace(/^\./, '')
  if (fileType) return fileType === 'pdf'
  return /\.pdf$/i.test(String(document?.filename || document?.title || '').trim())
}

async function downloadDocument(row) {
  if (isPdfDocument(row)) {
    ElMessage.warning('PDF 文档不支持下载 Word 文件')
    return
  }
  const link = document.createElement('a')
  link.href = `/api/v1/knowledge/documents/${row.id}/file`
  link.download = row.filename || row.title || 'knowledge-document'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// 下载 PDF：走后端转换接口，返回 PDF 文件流
const downloadingPdfId = ref('')

async function downloadPdf(row) {
  downloadingPdfId.value = row.id
  try {
    const response = await axios.get(`/api/v1/knowledge/documents/${row.id}/export`, {
      responseType: 'blob',
    })
    const baseName = String(row.title || row.filename || 'knowledge-document').replace(/\.\w+$/, '')
    downloadBlob(response.data, `${baseName}.pdf`)
    ElMessage.success('PDF 下载完成')
  } catch (error) {
    console.error('PDF 下载失败:', error)
    ElMessage.error('PDF 下载失败')
  } finally {
    downloadingPdfId.value = ''
  }
}

async function deleteDocument(row) {
  await ElMessageBox.confirm(`确定删除「${row.title}」吗？`, '删除知识文档', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    customClass: 'delete-confirm-box',
  })
  await request.delete(`/v1/knowledge/documents/${row.id}`)
  ElMessage.success('知识文档已删除')
  await loadAll()
}

function getDisplayType(extension) {
  const ext = String(extension || '').toLowerCase()
  if (['doc', 'docx', 'odt', 'rtf', 'txt', 'md'].includes(ext)) return 'word'
  if (['xls', 'xlsx', 'ods', 'csv'].includes(ext)) return 'excel'
  if (['ppt', 'pptx', 'odp'].includes(ext)) return 'powerpoint'
  if (ext === 'pdf') return 'pdf'
  return 'default'
}

function getIconClass(extension) {
  return {
    word: 'word-icon',
    excel: 'excel-icon',
    powerpoint: 'ppt-icon',
    pdf: 'pdf-icon',
    default: 'default-icon',
  }[getDisplayType(extension)]
}

function getTypeBadgeClass(extension) {
  return {
    word: 'word-badge',
    excel: 'excel-badge',
    powerpoint: 'ppt-badge',
    pdf: 'pdf-badge',
    default: 'default-badge',
  }[getDisplayType(extension)]
}

function getTypeLabel(extension) {
  return String(extension || '').toUpperCase() || 'FILE'
}

function statusLabel(status) {
  return {
    uploaded: '待索引',
    indexed: '已索引',
    failed: '失败',
  }[status] || status
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 16)
}

function formatFileSize(value) {
  const size = Number(value || 0)
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

function formatTokens(value) {
  const count = Number(value || 0)
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
  return String(count)
}

function documentName(document) {
  return String(document?.title || document?.filename || '').trim()
}

function dateValue(value) {
  if (!value) return 0
  const date = new Date(String(value).replace('T', ' '))
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function toggleSort(field) {
  if (sortBy.value !== field) {
    sortBy.value = field
    sortOrder.value = 'desc'
    return
  }
  if (sortOrder.value === 'desc') {
    sortOrder.value = 'asc'
    return
  }
  sortBy.value = ''
  sortOrder.value = ''
}

function handleSortChange(value) {
  sortOrder.value = sortOptions.find((option) => option.value === value)?.order || 'desc'
}

function sortClass(field) {
  if (sortBy.value !== field) return ''
  return sortOrder.value === 'asc' ? 'ascending' : 'descending'
}
</script>

<style scoped>
.knowledge-base {
  min-height: 100%;
  padding: clamp(16px, 1.35vw, 26px) clamp(16px, 1.6vw, 32px) 28px;
  color: #d9e8f8;
  background: #071422;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 16px;
}

.stat-card {
  position: relative;
  min-height: 124px;
  padding: 18px 18px 16px;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  overflow: hidden;
  border: 1px solid rgba(104, 161, 200, .26);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(28, 68, 103, .72), rgba(8, 25, 42, .92)),
    #0b1d30;
  box-shadow: 0 18px 34px rgba(0, 0, 0, .22);
}

.stat-card::after {
  content: "";
  position: absolute;
  inset: auto 16px 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: #48d8ff;
  opacity: .72;
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  color: #48d8ff;
  background: rgba(72, 216, 255, .12);
  font-size: 25px;
  box-shadow: inset 0 0 0 1px rgba(72, 216, 255, .18);
}

.tone-category::after { background: #62d7b1; }
.tone-category .stat-icon { color: #62d7b1; background: rgba(98, 215, 177, .12); }
.tone-month::after { background: #f0c75d; }
.tone-month .stat-icon { color: #f0c75d; background: rgba(240, 199, 93, .13); }
.tone-selected::after { background: #8ab7ff; }
.tone-selected .stat-icon { color: #8ab7ff; background: rgba(138, 183, 255, .12); }

.stat-label,
.stat-info small {
  display: block;
  color: #8fb1c8;
  font-size: 13px;
}

.stat-value {
  display: block;
  margin: 4px 0;
  color: #f6fbff;
  font-size: 34px;
  font-weight: 700;
  line-height: 36px;
}

.filter-section {
  display: grid;
  grid-template-columns: minmax(230px, 1.25fr) minmax(140px, .72fr) minmax(140px, .72fr) minmax(320px, 3fr) auto;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 12px;
  border: 1px solid rgba(104, 161, 200, .22);
  border-radius: 10px;
  background: rgba(11, 29, 48, .86);
  box-shadow: 0 12px 28px rgba(0, 0, 0, .12);
}

.filter-field {
  display: flex;
  min-width: 0;
  width: 100%;
}

.base-select,
.type-select,
.sort-select { width: 100%; }
.search-field { min-width: 0; }
.search-input { width: 100%; }

.filter-section :deep(.el-select),
.filter-section :deep(.el-input) {
  height: 44px;
  border: 0;
  background: transparent;
}

.filter-section :deep(.el-input__wrapper),
.filter-section :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 8px;
  background: rgba(6, 25, 42, .82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, .38) !important;
}

.filter-section :deep(.el-input__wrapper:hover),
.filter-section :deep(.el-select__wrapper:hover),
.filter-section :deep(.el-input__wrapper.is-focus),
.filter-section :deep(.el-select__wrapper.is-focused),
.filter-section :deep(.el-select__wrapper.is-focus),
.filter-section :deep(.el-input__wrapper.is-focused) {
  box-shadow: inset 0 0 0 1px rgba(87, 190, 255, .82), 0 0 0 2px rgba(72, 216, 255, .08) !important;
}

.filter-section :deep(.el-input__inner),
.filter-section :deep(.el-select__selected-item),
.filter-section :deep(.el-select__placeholder),
.filter-section :deep(.el-range-input) {
  color: #d9e8f8;
}

.filter-section :deep(.el-input__inner::placeholder),
.filter-section :deep(.el-range-input::placeholder) {
  color: #7898ad;
}

.filter-section :deep(.el-input__prefix),
.filter-section :deep(.el-input__suffix),
.filter-section :deep(.el-select__caret) {
  color: #7898ad;
}

.filter-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  white-space: nowrap;
}

.filter-actions :deep(.el-upload) {
  display: flex;
}

.upload-button {
  height: 44px;
  min-width: 116px;
  border-radius: 8px;
  border-color: rgba(82, 181, 244, .72);
  color: #fff;
  background: #3d8ed8;
}

.upload-button:hover,
.upload-button:focus {
  border-color: #8cd5ff;
  background: #4aa0ed;
}

.document-table-panel {
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid rgba(104, 161, 200, .18);
  border-radius: 8px;
  background: rgba(11, 29, 48, .72);
  box-shadow: 0 16px 34px rgba(0, 0, 0, .1);
}

.document-table-panel.is-empty {
  min-height: 300px;
  border-color: transparent;
  background: transparent;
}

.document-table-panel :deep(.el-loading-mask) {
  background: rgba(8, 20, 38, 0.72);
}

.document-table-panel :deep(.el-loading-spinner .path) {
  stroke: var(--accent-color);
}

.document-table-panel :deep(.el-loading-spinner .el-loading-text) {
  color: var(--text-secondary);
}

.document-header,
.document-row {
  display: grid;
  grid-template-columns: 46px minmax(150px, 1.5fr) minmax(64px, .7fr) minmax(72px, .8fr) minmax(52px, .6fr) minmax(56px, .6fr) minmax(64px, .7fr) minmax(122px, 1.2fr) minmax(64px, .7fr) minmax(330px, 1.4fr);
  align-items: center;
  gap: 12px;
}

.document-list {
  width: 100%;
}

.document-header {
  min-height: 50px;
  padding: 0 20px;
  color: #9fb4c5;
  background: rgba(30, 58, 95, .58);
  font-size: 13px;
  font-weight: 700;
}

.document-header .row-name,
.document-header .row-type,
.document-header .row-size,
.document-header .row-chunks,
.document-header .row-sections,
.document-header .row-tokens,
.document-header .row-date,
.document-header .row-status,
.document-header .row-index,
.document-header .row-actions {
  cursor: default;
  color: #9fb4c5;
}

.document-header .row-name {
  justify-content: flex-start;
  text-align: left;
}

.document-header .row-actions {
  justify-content: center;
}

.document-row {
  min-height: 72px;
  padding: 12px 20px;
  color: #d8e7ff;
  border-top: 1px solid rgba(104, 161, 200, .1);
  background: rgba(10, 28, 47, .38);
  transition: background .16s ease;
}

.document-row:hover {
  background: rgba(30, 74, 112, .46);
}

.row-index,
.row-type,
.row-size,
.row-chunks,
.row-sections,
.row-tokens,
.row-date,
.row-status {
  display: flex;
  justify-content: center;
  text-align: center;
}

.row-index,
.row-size,
.row-chunks,
.row-sections,
.row-tokens,
.row-date {
  color: #9cb6ca;
  font-size: 14px;
  font-weight: 500;
}

.row-chunks,
.row-sections,
.row-tokens {
  white-space: nowrap;
}

.sortable-header {
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  cursor: pointer;
}

.sortable-header:hover {
  color: #d9e8f8;
}

.caret-wrapper {
  width: 24px;
  height: 14px;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  vertical-align: middle;
}

.sort-caret {
  width: 0;
  height: 0;
  position: absolute;
  left: 7px;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  opacity: .65;
}

.sort-caret.ascending {
  top: -5px;
  border-bottom-color: #7c96aa;
}

.sort-caret.descending {
  bottom: -3px;
  border-top-color: #7c96aa;
}

.sortable-header.ascending .sort-caret.ascending {
  border-bottom-color: #48d8ff;
  opacity: 1;
}

.sortable-header.descending .sort-caret.descending {
  border-top-color: #48d8ff;
  opacity: 1;
}

.document-row .row-size {
  width: fit-content;
  min-width: 58px;
  height: 26px;
  justify-self: center;
  align-items: center;
  padding: 0 12px;
  border: 1px solid rgba(72, 216, 255, .22);
  border-radius: 5px;
  color: #aee8ff;
  background: rgba(72, 216, 255, .08);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.row-index {
  color: #f3f8fd;
  font-weight: 700;
}

.row-name {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  cursor: pointer;
}

.doc-icon {
  flex: 0 0 auto;
  font-size: 24px;
}

.word-icon { color: #3d8cff; }
.excel-icon { color: #58d36f; }
.ppt-icon { color: #f0a043; }
.pdf-icon { color: #ff5967; }
.default-icon { color: #9bb6d5; }

.doc-title-stack {
  display: grid;
  min-width: 0;
  max-width: 100%;
}

.doc-name {
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-name:hover .doc-name {
  color: #7dd7ff;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 26px;
  padding: 0 12px;
  border: 1px solid rgba(72, 216, 255, .22);
  border-radius: 5px;
  color: #aee8ff;
  background: rgba(72, 216, 255, .08);
  font-size: 12px;
  font-weight: 700;
}

.word-badge { border-color: rgba(61, 140, 255, .3); color: #b9d5ff; background: rgba(61, 140, 255, .1); }
.excel-badge { border-color: rgba(98, 215, 177, .24); color: #b8f3dc; background: rgba(98, 215, 177, .08); }
.ppt-badge { border-color: rgba(240, 199, 93, .26); color: #ffe4a5; background: rgba(240, 199, 93, .1); }
.pdf-badge { border-color: rgba(255, 107, 118, .3); color: #ffbdc4; background: rgba(255, 107, 118, .1); }
.default-badge { border-color: rgba(126, 152, 170, .24); color: #b6c7d4; background: rgba(126, 152, 170, .08); }

.row-actions {
  display: flex;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
}

.row-actions .el-button + .el-button {
  margin-left: 0;
}

.action-button {
  flex-shrink: 0;
  min-width: 44px;
  height: 30px;
  padding: 0 9px;
  border: 1px solid rgba(127, 178, 221, .24);
  border-radius: 5px;
  color: #dce9fa;
  background: rgba(37, 70, 106, .38);
  font-weight: 600;
  white-space: nowrap;
}

.action-button:disabled {
  border-color: rgba(127, 178, 221, .16);
  color: #6e8799;
  background: rgba(37, 70, 106, .18);
  opacity: .72;
}

.download-button { color: #c8f0ff; }
.download-pdf-button { color: #ffd9a8; border-color: rgba(255, 179, 92, .34); background: rgba(166, 92, 7, .18); }
.preview-button { color: #35e5f2; border-color: rgba(53, 229, 242, .34); background: rgba(7, 148, 166, .18); }
.edit-button { color: #a8f0c8; border-color: rgba(85, 214, 143, .34); background: rgba(21, 132, 83, .18); }
.delete-button { color: #ffb8ca; border-color: rgba(255, 92, 128, .35); background: rgba(189, 49, 95, .18); }

/* 状态胶囊 */
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 24px;
  padding: 0 12px;
  border: 1px solid rgba(126, 152, 170, .24);
  border-radius: 999px;
  color: #b6c7d4;
  background: rgba(126, 152, 170, .08);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}
.status-uploaded { color: #ffe1a6; border-color: rgba(255, 191, 92, .35); background: rgba(166, 116, 7, .18); }
.status-indexed { color: #7df0c8; border-color: rgba(61, 204, 150, .35); background: rgba(31, 160, 108, .16); }
.status-failed { color: #ffb8ca; border-color: rgba(255, 92, 128, .35); background: rgba(189, 49, 95, .18); }

.empty-state {
  display: flex;
  min-height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #68849a;
  text-align: center;
}

.empty-icon {
  margin-bottom: 14px;
  color: #68849a;
  font-size: 52px;
}

.empty-state h3 {
  margin: 0 0 8px;
  color: #d9e8f8;
}

.empty-state p {
  margin: 0;
  color: #68849a;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding: 18px;
  background: transparent;
  border: 0;
}

.pagination-bar :deep(.el-pagination.is-background .btn-prev),
.pagination-bar :deep(.el-pagination.is-background .btn-next),
.pagination-bar :deep(.el-pagination.is-background .el-pager li) {
  width: 48px;
  height: 42px;
  min-width: 48px;
  margin: 0;
  border: 1px solid #214766;
  border-radius: 5px;
  color: #7893aa;
  background: #0a1a2c;
}

.pagination-bar :deep(.el-pager) {
  display: flex;
  gap: 10px;
}

.pagination-bar :deep(.el-pagination.is-background .el-pager li.is-active) {
  color: #fff;
  background: #3d8ed8;
  border-color: #61b5ff;
}

.pagination-bar :deep(.el-pagination.is-background .btn-prev:disabled),
.pagination-bar :deep(.el-pagination.is-background .btn-next:disabled) {
  opacity: 0.45;
}

.preview-shell,
.preview-editor-shell {
  width: 100%;
  height: calc(100vh - 60px);
  min-height: 520px;
  overflow: hidden;
  background: #eef2f6;
}

.preview-editor-shell :deep(.onlyoffice-editor),
.preview-editor-shell :deep(#onlyoffice-editor),
.preview-editor-shell :deep(iframe) {
  height: 100% !important;
}

.preview-editor-shell :deep(.onlyoffice-editor) {
  border: 0;
  border-radius: 0;
}

:global(.knowledge-preview-dialog.el-dialog.is-fullscreen) {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  margin: 0;
  border-radius: 0 !important;
}

:global(.knowledge-preview-dialog .el-dialog__header) {
  flex: 0 0 auto;
  min-height: 60px;
  margin: 0;
  padding: 0 18px;
  background: #0b2138;
  border-bottom: 1px solid rgba(0, 200, 255, .2);
  box-shadow: 0 10px 28px rgba(0, 0, 0, .24);
}

:global(.knowledge-preview-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  background: #071625;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 60px;
}

.preview-back-button {
  flex: 0 0 auto;
  height: 36px;
  color: #dce9fa;
  background: rgba(10, 30, 48, .68);
  border-color: rgba(88, 156, 222, .42);
}

.preview-title-stack {
  min-width: 0;
  flex: 1 1 auto;
}

.preview-kicker {
  display: block;
  margin-bottom: 3px;
  color: #8fb1c8;
  font-size: 12px;
}

.preview-title {
  max-width: min(52vw, 860px);
  margin: 0;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 17px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .document-header,
  .document-row {
    grid-template-columns: 40px minmax(120px, 1.5fr) minmax(64px, .7fr) minmax(72px, .8fr) minmax(52px, .6fr) minmax(122px, 1.2fr) minmax(64px, .7fr) minmax(330px, 1.4fr);
  }

  .document-header .row-sections,
  .document-header .row-tokens,
  .document-row .row-sections,
  .document-row .row-tokens {
    display: none;
  }
}

@media (max-width: 1200px) {
  .stats-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .filter-section {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .search-field,
  .filter-actions {
    grid-column: 1 / -1;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .document-header {
    display: none;
  }

  .document-row {
    grid-template-columns: 40px minmax(0, 1fr);
  }

  .row-type,
  .row-size,
  .row-chunks,
  .row-sections,
  .row-tokens,
  .row-date,
  .row-status,
  .row-actions {
    grid-column: 2;
  }

  .row-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .knowledge-base {
    padding: 14px;
  }

  .stats-cards {
    grid-template-columns: 1fr;
  }

  .filter-section {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .search-field,
  .filter-actions {
    grid-column: auto;
  }

  .base-select,
  .type-select,
  .sort-select {
    width: 100%;
  }

  .filter-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: stretch;
  }

  .filter-actions :deep(.el-upload),
  .upload-button {
    width: 100%;
  }
}
</style>
