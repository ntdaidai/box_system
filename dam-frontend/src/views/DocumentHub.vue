<template>
  <div class="document-hub">
    <div class="stats-cards">
      <article class="stat-card tone-total">
        <el-icon class="stat-icon"><Document /></el-icon>
        <div class="stat-info">
          <span class="stat-label">文档总数</span>
          <span class="stat-value">{{ documents.length }}</span>
          <small>当前文档中心</small>
        </div>
      </article>
      <article class="stat-card tone-category">
        <el-icon class="stat-icon"><FolderOpened /></el-icon>
        <div class="stat-info">
          <span class="stat-label">文档分类</span>
          <span class="stat-value">{{ categories.length }}</span>
          <small>按文件类型归档</small>
        </div>
      </article>
      <article class="stat-card tone-month">
        <el-icon class="stat-icon"><Clock /></el-icon>
        <div class="stat-info">
          <span class="stat-label">本月文档</span>
          <span class="stat-value">{{ currentMonthCount }}</span>
          <small>最近更新统计</small>
        </div>
      </article>
      <article class="stat-card tone-selected">
        <el-icon class="stat-icon"><Download /></el-icon>
        <div class="stat-info">
          <span class="stat-label">已选择</span>
          <span class="stat-value">{{ selectedDocumentIds.length }}</span>
          <small>可批量导出</small>
        </div>
      </article>
    </div>

    <div class="filter-section">
      <div class="filter-field search-field">
        <span class="filter-label">搜索</span>
        <el-input
          v-model="searchQuery"
          placeholder="输入文件名"
          :prefix-icon="Search"
          clearable
          class="search-input"
        />
      </div>
      <div class="filter-field month-field">
        <span class="filter-label">导出月份</span>
        <el-date-picker
          v-model="exportMonth"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择月份"
          class="month-picker"
          popper-class="document-month-popper"
        />
      </div>
      <div class="filter-actions">
        <el-button
          class="export-button"
          :disabled="!exportMonth"
          :loading="exportingMonth"
          @click="exportMonthDocuments"
        >
          <el-icon><Download /></el-icon>
          导出该月
        </el-button>
        <el-button
          type="primary"
          class="export-button export-selected-button"
          :disabled="selectedDocumentIds.length === 0"
          :loading="exportingSelected"
          @click="exportSelectedDocuments"
        >
          <el-icon><Download /></el-icon>
          导出勾选文档
        </el-button>
      </div>
    </div>

    <section class="document-table-panel" :class="{ 'is-empty': !filteredDocuments.length }" v-loading="loading">
      <div v-if="filteredDocuments.length" class="document-list">
        <div class="document-header">
          <div class="row-select">
            <el-checkbox
              :model-value="isCurrentPageAllSelected"
              :indeterminate="isCurrentPageIndeterminate"
              @change="toggleCurrentPageSelection"
            />
          </div>
          <button type="button" class="row-index sortable-header" @click="toggleSort('index')">
            序号 <span class="sort-caret" :class="sortClass('index')"></span>
          </button>
          <div class="row-name">文档</div>
          <div class="row-event-no">事件编号</div>
          <div class="row-type">文件类型</div>
          <div class="row-size">文件大小</div>
          <button type="button" class="row-date sortable-header" @click="toggleSort('created')">
            创建时间 <span class="sort-caret" :class="sortClass('created')"></span>
          </button>
          <button type="button" class="row-date sortable-header" @click="toggleSort('updated')">
            最后更新时间 <span class="sort-caret" :class="sortClass('updated')"></span>
          </button>
          <div class="row-actions">操作</div>
        </div>
        <div
          v-for="(doc, index) in paginatedDocuments"
          :key="doc.document_id"
          class="document-row"
        >
          <div class="row-select">
            <el-checkbox
              :model-value="selectedDocumentIds.includes(doc.document_id)"
              @change="(checked) => toggleDocumentSelection(doc.document_id, checked)"
            />
          </div>
          <div class="row-index">{{ pageStartIndex + index + 1 }}</div>
          <div class="row-name" @click="editDoc(doc)">
            <el-icon class="doc-icon" :class="getIconClass(doc.type)">
              <Document />
            </el-icon>
            <span class="doc-title-stack" :title="documentTitle(doc)">
              <strong class="doc-name">{{ documentTitle(doc) }}</strong>
            </span>
          </div>
          <div class="row-event-no" :class="{ 'is-empty-event': !eventNumberForDocument(doc) }" :title="eventNumberForDocument(doc) || '无关联编号'">
            <template v-if="eventNumberForDocument(doc)">{{ eventNumberForDocument(doc) }}</template>
            <template v-else>无关联编号</template>
          </div>
          <div class="row-type">
            <span class="type-badge" :class="getTypeBadgeClass(doc.type)">
              {{ getTypeLabel(doc.file_type) }}
            </span>
          </div>
          <div class="row-size">{{ formatSize(doc.size) }}</div>
          <div class="row-date">{{ formatDateTime(doc.created_at) }}</div>
          <div class="row-date">{{ formatDateTime(doc.updatedAt) }}</div>
          <div class="row-actions">
            <el-button class="action-button edit-button" size="small" @click="editDoc(doc)">编辑</el-button>
            <el-button class="action-button download-button" size="small" @click="downloadDoc(doc)">下载</el-button>
            <el-button class="action-button preview-button" size="small" @click="previewDoc(doc)">预览</el-button>
            <el-button
              class="action-button delete-button"
              size="small"
              :loading="deletingDocumentIds.includes(doc.document_id)"
              @click="deleteDoc(doc)"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>

      <div v-if="!loading && filteredDocuments.length === 0" class="empty-state">
        <el-icon class="empty-icon"><FolderOpened /></el-icon>
        <h3>暂无文档</h3>
        <p>暂无可导出的文档</p>
      </div>

      <div v-if="!loading && filteredDocuments.length > 0" class="pagination-bar">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredDocuments.length"
          background
          layout="prev, pager, next"
        />
      </div>
    </section>

    <el-dialog
      v-model="exportFormatDialogVisible"
      class="export-format-dialog"
      title="选择导出格式"
      width="460px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="!exportingSelected"
      :close-on-press-escape="!exportingSelected"
      :show-close="!exportingSelected"
    >
      <p class="export-dialog-intro">
        已选择 {{ selectedDocumentIds.length }} 个文件，请选择导出方式。
      </p>
      <el-radio-group
        v-model="selectedExportFormat"
        class="export-format-options"
        aria-label="导出文件格式"
        :disabled="exportingSelected"
      >
        <el-radio value="source" class="export-format-option">
          <span class="export-format-copy">
            <strong>导出源文件</strong>
            <small>保留 Word、Excel、PPT 或 PDF 的原始格式</small>
          </span>
        </el-radio>
        <el-radio value="pdf" class="export-format-option">
          <span class="export-format-copy">
            <strong>导出 PDF 文件</strong>
            <small>统一转换为 PDF；选择多个文件时自动打包</small>
          </span>
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button :disabled="exportingSelected" @click="exportFormatDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="exportingSelected" @click="confirmSelectedExport">
          开始导出
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      class="document-preview-dialog"
      fullscreen
      :show-close="false"
      destroy-on-close
      @closed="previewConfig = null"
    >
      <template #header>
        <div class="preview-header">
          <el-button class="preview-back-button" :icon="ArrowLeft" @click="closePreview">返回</el-button>
          <div class="preview-title-stack">
            <span class="preview-kicker">文档预览</span>
            <h2 class="preview-title" :title="previewTitle">{{ previewTitle }}</h2>
          </div>
        </div>
      </template>
      <div class="preview-editor-shell">
        <OnlyOfficeEditor
          v-if="previewConfig"
          :config="previewConfig"
          mode="view"
          editor-height="100%"
          :user="currentUser"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Document, FolderOpened,
  Clock, Download, ArrowLeft
} from '@element-plus/icons-vue'
import axios from 'axios'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const exportingSelected = ref(false)
const exportingMonth = ref(false)
const deletingDocumentIds = ref([])
const documents = ref([])
const searchQuery = ref('')
const selectedCategory = ref('')
const selectedBusinessType = ref('')
const sortBy = ref('updated')
const sortOrder = ref('desc')
const currentPage = ref(1)
const pageSize = 10
const selectedDocumentIds = ref([])
const exportMonth = ref('')
const exportFormatDialogVisible = ref(false)
const selectedExportFormat = ref('source')

const previewDialogVisible = ref(false)
const previewTitle = ref('')
const previewConfig = ref(null)

const currentUser = ref({
  id: 'user_001',
  name: '管理员'
})

const businessTypes = [
  { label: '全部文档', value: '' },
  { label: '事件报告', value: 'event' }
]

const categories = computed(() => {
  const cats = new Set(documents.value.map((doc) => doc.category))
  return Array.from(cats)
})

const currentMonthCount = computed(() => {
  const now = new Date()
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  return documents.value.filter((doc) => getDocumentMonth(doc.updatedAt) === currentMonth).length
})

const filteredDocuments = computed(() => {
  let result = [...documents.value]

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((doc) => doc.searchText.includes(query))
  }

  if (selectedCategory.value) {
    result = result.filter((doc) => doc.category === selectedCategory.value)
  }

  if (selectedBusinessType.value) {
    result = result.filter((doc) => doc.businessType === selectedBusinessType.value)
  }

  if (exportMonth.value) {
    result = result.filter((doc) => getDocumentMonth(doc.updatedAt) === exportMonth.value)
  }

  result.sort((a, b) => {
    const direction = sortOrder.value === 'asc' ? 1 : -1
    if (sortBy.value === 'index') return (a.sourceIndex - b.sourceIndex) * direction
    if (sortBy.value === 'created') return (dateValue(a.created_at) - dateValue(b.created_at)) * direction
    if (sortBy.value === 'updated') return (dateValue(a.updatedAt) - dateValue(b.updatedAt)) * direction
    if (sortBy.value === 'name') return a.name.localeCompare(b.name) * direction
    if (sortBy.value === 'size') return (a.size - b.size) * direction
    return 0
  })

  return result
})

const pageStartIndex = computed(() => (currentPage.value - 1) * pageSize)

const paginatedDocuments = computed(() => (
  filteredDocuments.value.slice(pageStartIndex.value, pageStartIndex.value + pageSize)
))

const currentPageIds = computed(() => paginatedDocuments.value.map((doc) => doc.document_id))

const isCurrentPageAllSelected = computed(() => (
  currentPageIds.value.length > 0 &&
  currentPageIds.value.every((id) => selectedDocumentIds.value.includes(id))
))

const isCurrentPageIndeterminate = computed(() => {
  const selectedCount = currentPageIds.value.filter((id) => selectedDocumentIds.value.includes(id)).length
  return selectedCount > 0 && selectedCount < currentPageIds.value.length
})

watch([searchQuery, selectedCategory, selectedBusinessType, sortBy, exportMonth], () => {
  currentPage.value = 1
})

watch(filteredDocuments, (docs) => {
  const maxPage = Math.max(1, Math.ceil(docs.length / pageSize))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})

const getDocumentType = (extension) => {
  const ext = String(extension || '').toLowerCase()
  const typeMap = {
    docx: 'word', doc: 'word', odt: 'word', rtf: 'word', txt: 'word',
    xlsx: 'cell', xls: 'cell', ods: 'cell', csv: 'cell',
    pptx: 'slide', ppt: 'slide', odp: 'slide',
    pdf: 'pdf'
  }
  return typeMap[ext] || 'word'
}

const getDisplayType = (extension) => {
  const documentType = getDocumentType(extension)
  if (documentType === 'cell') return 'excel'
  if (documentType === 'slide') return 'powerpoint'
  return documentType
}

const getCategory = (extension) => {
  const categoryMap = {
    word: 'Word 文档',
    excel: 'Excel 表格',
    powerpoint: 'PPT 演示',
    pdf: 'PDF 文档'
  }
  return categoryMap[getDisplayType(extension)] || '其他文档'
}

const detectBusinessType = (filename) => {
  const name = String(filename || '').toLowerCase()
  const eventKeywords = ['事件', '处置报告', 'event', 'dam_event_report']
  const inspectionKeywords = ['巡查', '巡检', 'patrol', 'inspection']
  const monitoringKeywords = ['监测', '监控', '传感器', 'sensor', 'monitor']
  if (eventKeywords.some((keyword) => name.includes(keyword))) return 'event'
  if (inspectionKeywords.some((keyword) => name.includes(keyword))) return 'inspection'
  if (monitoringKeywords.some((keyword) => name.includes(keyword))) return 'monitoring'
  return 'other'
}

const getIconClass = (type) => {
  const classMap = {
    word: 'word-icon',
    excel: 'excel-icon',
    powerpoint: 'ppt-icon',
    pdf: 'pdf-icon'
  }
  return classMap[type] || 'default-icon'
}

const getTypeBadgeClass = (type) => {
  const classMap = {
    word: 'word-badge',
    excel: 'excel-badge',
    powerpoint: 'ppt-badge',
    pdf: 'pdf-badge'
  }
  return classMap[type] || 'default-badge'
}

const getTypeLabel = (extension) => String(extension || '').toUpperCase() || 'FILE'

const eventReportTitle = (name) => {
  const text = String(name || '').trim()
  if (!text) return '事件处置报告'
  return text.includes('事件') ? `${text}处置报告` : `${text}事件处置报告`
}

const isEventReportDocument = (doc) => (
  doc?.businessType === 'event' ||
  String(doc?.document_id || '').startsWith('dam_event_report_')
)

const eventInstanceNoFromDocumentId = (documentId) => {
  const text = String(documentId || '')
  return text.startsWith('dam_event_report_') ? text.slice('dam_event_report_'.length) : ''
}

const dateToken = (value) => {
  if (!value) return ''
  const direct = String(value).match(/20\d{6}/)
  if (direct) return direct[0]
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

const instanceSequence = (value) => {
  const matched = String(value || '').match(/_(\d{1,4})$/)
  return matched?.[1] || ''
}

const formatEventDocumentId = (doc) => {
  const instanceNo = doc?.event_instance_no || eventInstanceNoFromDocumentId(doc?.document_id)
  if (!instanceNo) return ''
  const date = dateToken(doc?.event_started_at) || dateToken(instanceNo) || dateToken(doc?.created_at)
  if (!date) return instanceNo
  const sequence = instanceSequence(instanceNo) || doc?.event_instance_id
  return `${date}_${String(sequence || 1).padStart(2, '0')}`
}

const documentTitle = (doc) => {
  if (isEventReportDocument(doc)) {
    return eventReportTitle(doc?.event_name || doc?.event_summary || doc?.report_title)
  }
  return doc?.name || '未命名文档'
}

const eventNumberForDocument = (doc) => {
  // 仅事件处置报告有关联的事件编号，其余文档（如每日报告）无关联编号
  if (isEventReportDocument(doc)) {
    return formatEventDocumentId(doc) || ''
  }
  return ''
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

const buildExportFileName = (suffix) => `documents_${suffix}.zip`

const getResponseFilename = (response, fallback) => {
  const disposition = response.headers?.['content-disposition'] || ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  }
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  return plain || fallback
}

const getExportErrorMessage = async (error) => {
  const data = error.response?.data
  if (data instanceof Blob) {
    try {
      const payload = JSON.parse(await data.text())
      return payload.detail || payload.message || '导出失败'
    } catch {
      return '导出失败'
    }
  }
  return data?.detail || data?.message || '导出失败'
}

const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const parseDocumentDate = (value) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const dateValue = (value) => parseDocumentDate(value)?.getTime() || 0

const formatDateTime = (value) => {
  const date = parseDocumentDate(value)
  if (!date) return '-'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

const getDocumentMonth = (value) => {
  const date = parseDocumentDate(value)
  if (!date) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

const normalizeDocument = (doc, index = 0) => {
  const normalized = {
    ...doc,
    id: doc.document_id,
    sourceIndex: index,
    name: doc.title || doc.document_id || '未命名文档',
    type: getDisplayType(doc.file_type),
    category: getCategory(doc.file_type),
    businessType: detectBusinessType(doc.title || doc.document_id),
    size: doc.file_size,
    updatedAt: doc.updated_at
  }
  normalized.displayTitle = documentTitle(normalized)
  normalized.displayEventNo = eventNumberForDocument(normalized)
  normalized.searchText = [
    normalized.name,
    normalized.document_id,
    normalized.displayTitle,
    normalized.displayEventNo
  ].filter(Boolean).join(' ').toLowerCase()
  return normalized
}

const toggleSort = (field) => {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortBy.value = field
  sortOrder.value = field === 'index' ? 'asc' : 'desc'
}

const sortClass = (field) => {
  if (sortBy.value !== field) return ''
  return sortOrder.value === 'asc' ? 'is-asc' : 'is-desc'
}

const loadDocuments = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/onlyoffice/documents', {
      params: {
        user_id: currentUser.value.id,
        page: 1,
        page_size: 10000
      }
    })

    if (response.data.success) {
      documents.value = response.data.data.documents.map((doc, index) => normalizeDocument(doc, index))
      selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => (
        documents.value.some((doc) => doc.document_id === id)
      ))
    } else {
      ElMessage.error('加载文档列表失败')
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

const toggleDocumentSelection = (documentId, checked) => {
  if (checked) {
    if (!selectedDocumentIds.value.includes(documentId)) {
      selectedDocumentIds.value.push(documentId)
    }
  } else {
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => id !== documentId)
  }
}

const toggleCurrentPageSelection = (checked) => {
  if (checked) {
    const ids = new Set(selectedDocumentIds.value)
    currentPageIds.value.forEach((id) => ids.add(id))
    selectedDocumentIds.value = Array.from(ids)
  } else {
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => !currentPageIds.value.includes(id))
  }
}

const exportDocuments = async ({
  documentIds = [],
  month = '',
  outputFormat = 'source',
  filename,
  loadingRef
}) => {
  try {
    loadingRef.value = true
    const response = await axios.post('/api/onlyoffice/documents/export', {
      user_id: currentUser.value.id,
      document_ids: documentIds,
      month,
      output_format: outputFormat
    }, {
      responseType: 'blob'
    })
    downloadBlob(response.data, getResponseFilename(response, filename))
    ElMessage.success('导出成功')
    return true
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error(await getExportErrorMessage(error))
    return false
  } finally {
    loadingRef.value = false
  }
}

const exportSelectedDocuments = () => {
  if (selectedDocumentIds.value.length === 0) {
    ElMessage.warning('请先勾选要导出的文档')
    return
  }
  selectedExportFormat.value = 'source'
  exportFormatDialogVisible.value = true
}

const confirmSelectedExport = async () => {
  const outputFormat = selectedExportFormat.value
  const succeeded = await exportDocuments({
    documentIds: selectedDocumentIds.value,
    outputFormat,
    filename: buildExportFileName(`selected_${outputFormat}`),
    loadingRef: exportingSelected
  })
  if (succeeded) exportFormatDialogVisible.value = false
}

const exportMonthDocuments = async () => {
  if (!exportMonth.value) {
    ElMessage.warning('请选择要导出的月份')
    return
  }
  const documentIds = filteredDocuments.value.map((doc) => doc.document_id)
  if (documentIds.length === 0) {
    ElMessage.warning('当前筛选条件下没有可导出的文档')
    return
  }
  const suffix = selectedBusinessType.value
    ? `${exportMonth.value}_${selectedBusinessType.value}`
    : exportMonth.value
  await exportDocuments({
    documentIds,
    month: exportMonth.value,
    filename: buildExportFileName(suffix),
    loadingRef: exportingMonth
  })
}

const previewDoc = async (doc) => {
  try {
    const response = await axios.get(`/api/onlyoffice/editor-config/${doc.document_id}`, {
      params: {
        user_id: currentUser.value.id,
        user_name: currentUser.value.name,
        mode: 'view'
      }
    })

    if (response.data.success) {
      previewTitle.value = documentTitle(doc)
      previewConfig.value = response.data.data
      previewDialogVisible.value = true
    } else {
      ElMessage.error('打开预览失败')
    }
  } catch (error) {
    console.error('打开预览失败:', error)
    ElMessage.error('打开预览失败')
  }
}

const closePreview = () => {
  previewDialogVisible.value = false
}

const editDoc = (doc) => {
  router.push({
    name: 'DocumentEditor',
    params: { documentId: doc.document_id },
    query: {
      title: documentTitle(doc),
      type: doc.file_type
    }
  })
}

const downloadDoc = async (doc) => {
  try {
    const response = await axios.get(`/api/onlyoffice/document/${doc.document_id}`, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', doc.name)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

const deleteDoc = async (doc) => {
  let previousDocuments = null
  let previousSelection = null
  try {
    await ElMessageBox.confirm(
      `确定要删除“${documentTitle(doc)}”吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    previousDocuments = documents.value
    previousSelection = selectedDocumentIds.value
    deletingDocumentIds.value.push(doc.document_id)
    documents.value = documents.value.filter((item) => item.document_id !== doc.document_id)
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => id !== doc.document_id)

    const response = await axios.delete(`/api/onlyoffice/document/${doc.document_id}`)
    if (response.data.success) {
      ElMessage.success('删除成功')
    } else {
      documents.value = previousDocuments
      selectedDocumentIds.value = previousSelection
      ElMessage.error('删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      if (previousDocuments && previousSelection) {
        documents.value = previousDocuments
        selectedDocumentIds.value = previousSelection
      }
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  } finally {
    deletingDocumentIds.value = deletingDocumentIds.value.filter((id) => id !== doc.document_id)
  }
}

onMounted(() => {
  if (route.query.reportDate) {
    const date = String(route.query.reportDate)
    searchQuery.value = `坝区安全智能巡查日报_${date}`
  }
  loadDocuments()
})

onActivated(() => {
  loadDocuments()
})
</script>

<style scoped>
.document-hub {
  min-height: 100%;
  padding: 22px;
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

.stat-card.tone-category::after {
  background: #62d7b1;
}

.stat-card.tone-category .stat-icon {
  color: #62d7b1;
  background: rgba(98, 215, 177, .12);
  box-shadow: inset 0 0 0 1px rgba(98, 215, 177, .22);
}

.stat-card.tone-month::after {
  background: #f0c75d;
}

.stat-card.tone-month .stat-icon {
  color: #f0c75d;
  background: rgba(240, 199, 93, .13);
  box-shadow: inset 0 0 0 1px rgba(240, 199, 93, .22);
}

.stat-card.tone-selected::after {
  background: #8ab7ff;
}

.stat-card.tone-selected .stat-icon {
  color: #8ab7ff;
  background: rgba(138, 183, 255, .12);
  box-shadow: inset 0 0 0 1px rgba(138, 183, 255, .2);
}

.stat-info {
  min-width: 0;
}

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
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
  padding: 14px;
  border: 1px solid rgba(104, 161, 200, .22);
  border-radius: 8px;
  background: #0b1d30;
}

.filter-field {
  display: flex;
  flex: 0 0 auto;
  min-width: 0;
}

.search-field {
  min-width: 360px;
  flex: 1 1 420px;
}

.filter-label {
  display: none;
}

.search-input {
  width: 100%;
}

.category-select,
.business-type-select,
.sort-select {
  width: 150px;
}

.month-field {
  min-width: 240px;
}

.month-picker {
  width: 240px;
}

.filter-section :deep(.el-select),
.filter-section :deep(.el-date-editor),
.filter-section :deep(.el-input) {
  height: 44px;
  border: 0;
  background: transparent;
}

.filter-section :deep(.el-input__wrapper),
.filter-section :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 6px;
  background: rgba(6, 25, 42, .82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, .46) !important;
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
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.export-button {
  height: 44px;
  width: 168px;
  padding: 0 20px;
  justify-content: center;
  border-radius: 6px;
  font-weight: 700;
}

.export-selected-button {
  border-color: rgba(82, 181, 244, .72);
  color: #fff;
  background: #3d8ed8;
}

.export-selected-button:hover,
.export-selected-button:focus {
  border-color: #8cd5ff;
  background: #4aa0ed;
}

.export-button:not(.export-selected-button) {
  border-color: rgba(72, 216, 255, .32);
  color: #c8f0ff;
  background: rgba(72, 216, 255, .08);
}

.document-table-panel {
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid rgba(104, 161, 200, .18);
  border-radius: 8px;
  background: rgba(11, 29, 48, .72);
}

.document-table-panel.is-empty {
  min-height: 300px;
  border-color: transparent;
  background: transparent;
}

.document-list {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.document-header,
.document-row {
  display: grid;
  grid-template-columns: 34px 58px minmax(220px, 2fr) 150px 100px 112px 160px 160px 210px;
  align-items: center;
  gap: 12px;
}

.document-header {
  min-height: 50px;
  padding: 0 22px;
  color: #9fb4c5;
  background: rgba(30, 58, 95, .58);
  font-size: 13px;
  font-weight: 700;
}

.document-header .row-name,
.document-header .row-event-no,
.document-header .row-type,
.document-header .row-size,
.document-header .row-date,
.document-header .row-actions {
  cursor: default;
  color: #9fb4c5;
}

.document-header .row-actions {
  justify-content: center;
}

.document-header .row-index,
.document-header .row-event-no,
.document-header .row-size,
.document-header .row-date {
  color: #9fb4c5;
}

.document-row {
  min-height: 72px;
  padding: 12px 22px;
  color: #d8e7ff;
  border-top: 1px solid rgba(104, 161, 200, .1);
  background: rgba(10, 28, 47, .38);
  transition: background .16s ease;
}

.document-row:hover {
  background: rgba(30, 74, 112, .46);
}

.row-index,
.row-event-no,
.row-type,
.row-size,
.row-date,
.row-actions {
  display: flex;
  justify-content: center;
  text-align: center;
}

.row-index,
.row-size,
.row-date,
.row-event-no {
  font-size: 14px;
  font-weight: 500;
  color: #9cb6ca;
  overflow-wrap: anywhere;
}

.row-index {
  color: #f3f8fd;
  font-weight: 700;
}

.row-event-no.is-empty-event {
  color: #9cb6ca;
}

.row-name {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-width: 0;
  cursor: pointer;
}

.row-select {
  display: flex;
  justify-content: center;
}

.sortable-header {
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  cursor: pointer;
}

.sortable-header:hover {
  color: #d9e8f8;
}

.sort-caret {
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #6e879a;
  opacity: .65;
}

.sort-caret.is-asc {
  border-top: 0;
  border-bottom: 5px solid #48d8ff;
  opacity: 1;
}

.sort-caret.is-desc {
  border-top-color: #48d8ff;
  opacity: 1;
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

.doc-name {
  min-width: 0;
  font-size: 15px;
  font-weight: 700;
  color: #f3f8fd;
}

.doc-title-stack {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.doc-title-stack small {
  overflow: hidden;
  color: #8fb0c7;
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-name:hover .doc-name {
  color: #7dd7ff;
}

.row-type {
  display: flex;
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
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  color: #aee8ff;
  background: rgba(72, 216, 255, .08);
}

.word-badge {
  border-color: rgba(61, 140, 255, .3);
  color: #b9d5ff;
  background: rgba(61, 140, 255, .1);
}

.excel-badge {
  border-color: rgba(98, 215, 177, .24);
  color: #b8f3dc;
  background: rgba(98, 215, 177, .08);
}

.ppt-badge {
  border-color: rgba(240, 199, 93, .26);
  color: #ffe4a5;
  background: rgba(240, 199, 93, .1);
}

.pdf-badge {
  border-color: rgba(255, 107, 118, .3);
  color: #ffbdc4;
  background: rgba(255, 107, 118, .1);
}

.default-badge {
  border-color: rgba(126, 152, 170, .24);
  color: #b6c7d4;
  background: rgba(126, 152, 170, .08);
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  white-space: nowrap;
}

.row-actions .el-button + .el-button {
  margin-left: 0;
}

.action-button {
  min-width: 44px;
  height: 30px;
  padding: 0 9px;
  border: 1px solid rgba(127, 178, 221, .24);
  border-radius: 5px;
  font-weight: 600;
  color: #dce9fa;
  background: rgba(37, 70, 106, .38);
}

.edit-button {
  color: #dce9fa;
}

.download-button {
  color: #c8f0ff;
}

.preview-button {
  color: #35e5f2;
  border-color: rgba(53, 229, 242, .34);
  background: rgba(7, 148, 166, .18);
}

.delete-button {
  color: #ffb8ca;
  border-color: rgba(255, 92, 128, .35);
  background: rgba(189, 49, 95, .18);
}

.action-button:hover,
.action-button:focus {
  color: #fff;
  filter: brightness(1.08);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  color: #68849a;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 8px 0;
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

:global(.export-format-dialog) {
  max-width: calc(100vw - 32px);
  background: #0b2138;
  border: 1px solid rgba(88, 156, 222, 0.4);
  border-radius: 8px;
  box-shadow: 0 20px 56px rgba(0, 0, 0, 0.46);
}

:global(.export-format-dialog .el-dialog__header) {
  margin: 0;
  padding: 20px 22px 14px;
  border-bottom: 1px solid rgba(103, 164, 217, 0.18);
}

:global(.export-format-dialog .el-dialog__title) {
  color: #f0f6ff;
  font-size: 17px;
  font-weight: 700;
}

:global(.export-format-dialog .el-dialog__headerbtn:focus-visible) {
  outline: 2px solid #3da4ff;
  outline-offset: -4px;
}

:global(.export-format-dialog .el-dialog__close) {
  color: #b9cce5;
}

:global(.export-format-dialog .el-dialog__body) {
  padding: 20px 22px 10px;
}

:global(.export-format-dialog .el-dialog__footer) {
  padding: 16px 22px 20px;
}

.export-dialog-intro {
  margin: 0 0 14px;
  color: #b9cce5;
  font-size: 14px;
  line-height: 1.6;
}

.export-format-options {
  display: grid;
  gap: 10px;
  width: 100%;
}

.export-format-option.el-radio {
  width: 100%;
  height: auto;
  min-height: 66px;
  margin: 0;
  padding: 12px 14px;
  color: #e7f0fd;
  background: rgba(19, 53, 87, 0.76);
  border: 1px solid rgba(103, 164, 217, 0.32);
  border-radius: 6px;
}

.export-format-option.el-radio:hover,
.export-format-option.el-radio.is-checked {
  background: rgba(26, 77, 119, 0.86);
  border-color: #3da4ff;
}

.export-format-option.el-radio:has(.el-radio__original:focus-visible) {
  outline: 2px solid #7bc2ff;
  outline-offset: 2px;
}

.export-format-option :deep(.el-radio__label) {
  width: 100%;
  padding-left: 12px;
  white-space: normal;
}

.export-format-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.export-format-copy strong {
  color: #f4f8ff;
  font-size: 15px;
  line-height: 1.3;
}

.export-format-copy small {
  color: #a9bfdc;
  font-size: 13px;
  line-height: 1.45;
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

:global(.document-month-popper.el-picker__popper),
:global(.document-month-popper .el-picker-panel),
:global(.document-month-popper .el-date-picker) {
  color: var(--text-primary);
  background: #0a1e30 !important;
  border-color: rgba(0, 200, 255, 0.25) !important;
}

:global(.document-month-popper.el-popper.is-light),
:global(.document-month-popper.el-popper.is-pure) {
  background: #0a1e30 !important;
  border: 1px solid rgba(0, 200, 255, 0.25) !important;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
}

:global(.document-month-popper .el-popper__arrow::before) {
  background: #0a1e30 !important;
  border-color: rgba(0, 200, 255, 0.25) !important;
}

:global(.document-month-popper .el-picker-panel__body-wrapper),
:global(.document-month-popper .el-picker-panel__body),
:global(.document-month-popper .el-picker-panel__content) {
  background: #0a1e30 !important;
}

:global(.document-month-popper .el-date-picker__header),
:global(.document-month-popper .el-date-picker__header--bordered) {
  border-color: rgba(103, 164, 217, 0.18) !important;
}

:global(.document-month-popper .el-date-picker__header-label),
:global(.document-month-popper .el-picker-panel__icon-btn) {
  color: #dce9fa !important;
}

:global(.document-month-popper .el-month-table td .cell) {
  color: #dce9fa !important;
}

:global(.document-month-popper .el-month-table td.disabled .cell) {
  color: var(--text-secondary) !important;
}

:global(.document-month-popper .el-month-table td.current:not(.disabled) .cell) {
  color: #fff !important;
  background: #3da4ff !important;
  border-radius: 24px;
  font-weight: 700;
}

:global(.document-month-popper .el-month-table td .cell:hover) {
  color: #fff !important;
  background: rgba(0, 200, 255, 0.12);
}

.preview-editor-shell {
  width: 100%;
  height: calc(100vh - 60px);
  min-height: 520px;
  overflow: hidden;
  background: #eef2f6;
  border: 0;
  border-radius: 0;
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

:global(.document-preview-dialog.el-dialog.is-fullscreen) {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  margin: 0;
  border-radius: 0 !important;
}

:global(.document-preview-dialog .el-dialog__header) {
  flex: 0 0 auto;
  min-height: 60px;
  margin: 0;
  padding: 0 18px;
  background: #0b2138;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
}

:global(.document-preview-dialog .el-dialog__body) {
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
  background: rgba(10, 30, 48, 0.68);
  border-color: rgba(88, 156, 222, 0.42);
}

.preview-title-stack {
  min-width: 0;
}

.preview-kicker {
  display: block;
  margin-bottom: 3px;
  font-size: 12px;
  color: var(--text-muted);
}

.preview-title {
  max-width: min(62vw, 980px);
  margin: 0;
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .stats-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .document-hub {
    padding: 14px;
  }

  .stats-cards {
    grid-template-columns: 1fr;
  }

  .filter-section {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field,
  .month-field,
  .search-field {
    width: 100%;
    min-width: 0;
  }

  .search-input {
    width: 100%;
  }

  .category-select,
  .business-type-select,
  .month-picker,
  .sort-select {
    width: 100%;
  }

  .filter-actions {
    flex-direction: column;
    align-items: stretch;
    width: 100%;
    margin-left: 0;
  }

  .filter-actions .el-button {
    width: 100%;
  }

  .batch-button {
    width: 100%;
  }

  .document-header {
    display: none;
  }

  .document-row {
    grid-template-columns: 28px 32px minmax(0, 1fr);
    gap: 10px 12px;
    padding: 16px;
  }

  .row-type,
  .row-event-no,
  .row-size,
  .row-date,
  .row-actions {
    grid-column: 3;
  }

  .row-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .preview-editor-shell {
    height: calc(100vh - 56px);
    min-height: 0;
  }

  :global(.document-preview-dialog .el-dialog__body) {
    padding: 0;
  }
}
</style>
