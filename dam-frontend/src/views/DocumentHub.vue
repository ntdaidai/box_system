<template>
  <div class="document-hub">
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
      <div class="filter-field">
        <span class="filter-label">文档分类</span>
        <el-select v-model="selectedCategory" placeholder="全部分类" clearable class="category-select">
          <el-option
            v-for="cat in categories"
            :key="cat"
            :label="cat"
            :value="cat"
          />
        </el-select>
      </div>
      <div class="filter-field">
        <span class="filter-label">业务类型</span>
        <el-select v-model="selectedBusinessType" placeholder="全部业务类型" clearable class="business-type-select">
          <el-option
            v-for="type in businessTypes"
            :key="type.value"
            :label="type.label"
            :value="type.value"
          />
        </el-select>
      </div>
      <div class="filter-field">
        <span class="filter-label">排序方式</span>
        <el-select v-model="sortBy" placeholder="排序方式" class="sort-select">
          <el-option label="最近修改" value="updated" />
          <el-option label="文件名称" value="name" />
          <el-option label="文件大小" value="size" />
        </el-select>
      </div>
      <div class="filter-actions">
        <el-button type="primary" class="upload-button" @click="showUploadDialog">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <div class="stats-cards">
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon" style="color: #409eff"><Document /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ documents.length }}</span>
            <span class="stat-label">文档总数</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon" style="color: #67c23a"><FolderOpened /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ categories.length }}</span>
            <span class="stat-label">文档分类</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon" style="color: #e6a23c"><Clock /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ currentMonthCount }}</span>
            <span class="stat-label">本月文档</span>
          </div>
        </div>
      </el-card>
    </div>

    <div class="batch-toolbar">
      <div class="batch-status">
        已选择 <strong>{{ selectedDocumentIds.length }}</strong> 个文档
      </div>
      <el-button
        class="batch-button"
        :disabled="selectedDocumentIds.length === 0"
        :loading="exportingSelected"
        @click="exportSelectedDocuments"
      >
        <el-icon><Download /></el-icon>
        导出勾选文档
      </el-button>
      <div class="month-export">
        <el-date-picker
          v-model="exportMonth"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择月份"
          class="month-picker"
          popper-class="document-month-popper"
        />
        <el-button
          class="batch-button"
          :disabled="!exportMonth"
          :loading="exportingMonth"
          @click="exportMonthDocuments"
        >
          <el-icon><Download /></el-icon>
          导出该月
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="document-list">
      <div class="document-header">
        <div class="row-select">
          <el-checkbox
            :model-value="isCurrentPageAllSelected"
            :indeterminate="isCurrentPageIndeterminate"
            @change="toggleCurrentPageSelection"
          />
        </div>
        <div class="row-index">序号</div>
        <div class="row-name">原始文件名</div>
        <div class="row-type">文件类型</div>
        <div class="row-size">文件大小</div>
        <div class="row-date">创建时间</div>
        <div class="row-date">最后更新时间</div>
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
          <span class="doc-name" :title="doc.name">{{ doc.name }}</span>
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

    <div v-if="!loading && filteredDocuments.length > 0" class="pagination-bar">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredDocuments.length"
        background
        layout="prev, pager, next"
      />
    </div>

    <div v-if="!loading && filteredDocuments.length === 0" class="empty-state">
      <el-icon class="empty-icon"><FolderOpened /></el-icon>
      <h3>暂无文档</h3>
      <p>点击右上方“上传文档”按钮开始上传</p>
    </div>

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

    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="500px">
      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="handleFileChange"
        :before-upload="beforeUpload"
        accept=".docx,.doc,.xlsx,.xls,.pptx,.ppt,.pdf,.odt,.ods,.odp,.csv,.txt"
        multiple
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 Word、Excel、PPT、PDF 等格式，单个文件不超过 50MB
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传</el-button>
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
  Upload, UploadFilled, Search, Document, FolderOpened,
  Clock, Download, ArrowLeft
} from '@element-plus/icons-vue'
import axios from 'axios'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const uploading = ref(false)
const exportingSelected = ref(false)
const exportingMonth = ref(false)
const deletingDocumentIds = ref([])
const documents = ref([])
const searchQuery = ref('')
const selectedCategory = ref('')
const selectedBusinessType = ref('')
const sortBy = ref('updated')
const currentPage = ref(1)
const pageSize = 10
const selectedDocumentIds = ref([])
const exportMonth = ref('')
const exportFormatDialogVisible = ref(false)
const selectedExportFormat = ref('source')

const uploadDialogVisible = ref(false)
const uploadFileList = ref([])

const previewDialogVisible = ref(false)
const previewTitle = ref('')
const previewConfig = ref(null)

const currentUser = ref({
  id: 'user_001',
  name: '管理员'
})

const businessTypes = [
  { label: '全部文档', value: '' },
  { label: '巡查文档', value: 'inspection' },
  { label: '监测文档', value: 'monitoring' }
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
    result = result.filter((doc) => doc.name.toLowerCase().includes(query))
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
    if (sortBy.value === 'name') return a.name.localeCompare(b.name)
    if (sortBy.value === 'size') return b.size - a.size
    return new Date(b.updatedAt) - new Date(a.updatedAt)
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
  const inspectionKeywords = ['巡查', '巡检', 'patrol', 'inspection']
  const monitoringKeywords = ['监测', '监控', '传感器', 'sensor', 'monitor']
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

const normalizeDocument = (doc) => ({
  ...doc,
  id: doc.document_id,
  name: doc.title || doc.document_id || '未命名文档',
  type: getDisplayType(doc.file_type),
  category: getCategory(doc.file_type),
  businessType: detectBusinessType(doc.title || doc.document_id),
  size: doc.file_size,
  updatedAt: doc.updated_at
})

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
      documents.value = response.data.data.documents.map(normalizeDocument)
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

const showUploadDialog = () => {
  uploadFileList.value = []
  uploadDialogVisible.value = true
}

const handleFileChange = (file, fileList) => {
  uploadFileList.value = fileList
}

const beforeUpload = (file) => {
  const maxSize = 50 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

const handleUpload = async () => {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文档')
    return
  }

  try {
    uploading.value = true

    for (const file of uploadFileList.value) {
      const formData = new FormData()
      formData.append('file', file.raw)
      formData.append('user_id', currentUser.value.id)
      formData.append('user_name', currentUser.value.name)

      const response = await axios.post('/api/onlyoffice/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      if (!response.data.success) {
        throw new Error(response.data.detail || response.data.message || `${file.name} 上传失败`)
      }
    }

    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    currentPage.value = 1
    await loadDocuments()
  } catch (error) {
    console.error('上传失败:', error)
    const message = error.response?.data?.detail || error.response?.data?.message || error.message || '上传失败'
    ElMessage.error(message)
  } finally {
    uploading.value = false
  }
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
      previewTitle.value = doc.name
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
      title: doc.name,
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
      `确定要删除“${doc.name}”吗？此操作不可恢复。`,
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
  padding: 20px;
  background: transparent;
  min-height: 100%;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  font-size: 40px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--text-muted);
}

.filter-section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  gap: 6px;
  min-width: 180px;
}

.search-field {
  min-width: 260px;
}

.filter-label {
  font-size: 12px;
  line-height: 1;
  color: var(--text-muted);
}

.search-input {
  width: 300px;
}

.category-select,
.business-type-select,
.sort-select {
  width: 260px;
}

.filter-section :deep(.el-input__wrapper),
.filter-section :deep(.el-select__wrapper) {
  min-height: 48px;
  border-radius: 6px;
  background: rgba(9, 30, 56, 0.88);
  box-shadow: 0 0 0 1px rgba(77, 145, 210, 0.32) inset;
}

.filter-section :deep(.el-input__wrapper.is-focus),
.filter-section :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px #3da4ff inset, 0 0 0 2px rgba(61, 164, 255, 0.16);
}

.filter-section :deep(.el-input__inner),
.filter-section :deep(.el-select__selected-item),
.filter-section :deep(.el-select__placeholder) {
  color: #dce9fa;
}

.filter-section :deep(.el-input__inner::placeholder) {
  color: #8ea8c9;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
  white-space: nowrap;
}

.upload-button {
  height: 48px;
  min-width: 150px;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 700;
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: rgba(16, 38, 72, 0.42);
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.batch-status {
  color: var(--text-secondary);
  font-size: 14px;
  white-space: nowrap;
}

.batch-status strong {
  color: var(--accent-color);
}

.batch-button {
  height: 34px;
  color: var(--text-primary);
  background: rgba(0, 200, 255, 0.12);
  border-color: rgba(0, 200, 255, 0.32);
}

.month-export {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.month-picker {
  width: 150px;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
}

.document-header,
.document-row {
  display: grid;
  grid-template-columns: 34px 48px minmax(260px, 3fr) 80px 104px 150px 150px 210px;
  align-items: center;
  gap: 16px;
}

.document-header {
  min-height: 54px;
  padding: 0 22px;
  color: var(--text-primary);
  background: #24527e;
  border-radius: 2px;
  border: 1px solid rgba(0, 200, 255, 0.18);
  font-size: 15px;
  font-weight: 700;
}

.document-header .row-name,
.document-header .row-type,
.document-header .row-size,
.document-header .row-date,
.document-header .row-actions {
  cursor: default;
  color: var(--text-primary);
}

.document-header .row-actions {
  justify-content: center;
}

.document-header .row-index,
.document-header .row-size,
.document-header .row-date {
  color: var(--text-primary);
}

.document-row {
  min-height: 82px;
  padding: 14px 22px;
  color: #d8e7ff;
  background: #213e64;
  border-radius: 2px;
  box-shadow: inset 0 0 0 1px rgba(103, 164, 217, 0.08);
}

.document-row:nth-child(even) {
  background: #25466f;
}

.row-index,
.row-size,
.row-date {
  font-size: 14px;
  font-weight: 600;
  color: #d7e4f7;
  overflow-wrap: anywhere;
}

.row-index {
  color: #f2f7ff;
}

.row-name {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  cursor: pointer;
}

.row-select {
  display: flex;
  justify-content: center;
}

.doc-icon {
  flex: 0 0 auto;
  font-size: 26px;
}

.word-icon { color: #3d8cff; }
.excel-icon { color: #58d36f; }
.ppt-icon { color: #f0a043; }
.pdf-icon { color: #ff5967; }
.default-icon { color: #9bb6d5; }

.doc-name {
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  color: #f3f600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-type {
  display: flex;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 30px;
  padding: 0 12px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  color: #fff;
}

.word-badge { background: #3977dc; }
.excel-badge { background: #2f9e5a; }
.ppt-badge { background: #d9852f; }
.pdf-badge { background: #ff4057; }
.default-badge { background: #617a99; }

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
  border: 1px solid rgba(127, 178, 221, 0.24);
  border-radius: 6px;
  font-weight: 600;
  color: #dce9fa;
  background: rgba(37, 70, 106, 0.62);
}

.edit-button {
  color: #dce9fa;
}

.download-button {
  color: #c8f0ff;
}

.preview-button {
  color: #35e5f2;
  border-color: rgba(53, 229, 242, 0.34);
  background: rgba(7, 148, 166, 0.26);
}

.delete-button {
  color: #ffb8ca;
  border-color: rgba(255, 92, 128, 0.35);
  background: rgba(189, 49, 95, 0.24);
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
  padding: 80px 20px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.empty-icon {
  font-size: 64px;
  color: #c0c4cc;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.empty-state p {
  margin: 0;
  color: var(--text-muted);
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 14px;
  padding: 8px 12px;
  background: transparent;
  border: 0;
}

.pagination-bar :deep(.el-pagination.is-background .btn-prev),
.pagination-bar :deep(.el-pagination.is-background .btn-next),
.pagination-bar :deep(.el-pagination.is-background .el-pager li) {
  min-width: 38px;
  height: 34px;
  margin: 0 5px;
  color: var(--text-secondary);
  background: rgba(16, 54, 87, 0.62);
  border: 1px solid rgba(80, 165, 200, 0.58);
  border-radius: 4px;
}

.pagination-bar :deep(.el-pagination.is-background .el-pager li.is-active) {
  color: #fff;
  background: rgba(64, 158, 255, 0.8);
  border-color: rgba(94, 180, 255, 0.95);
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

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  min-height: 220px;
  background: rgba(10, 30, 48, 0.88);
  border: 1px dashed rgba(0, 200, 255, 0.45);
  border-radius: 8px;
}

.upload-area :deep(.el-upload-dragger:hover) {
  border-color: var(--accent-color);
  background: rgba(12, 39, 65, 0.94);
}

.upload-area :deep(.el-icon--upload) {
  color: rgba(174, 202, 245, 0.78);
}

.upload-area :deep(.el-upload__text) {
  color: var(--text-secondary);
}

.upload-area :deep(.el-upload__text em) {
  color: var(--accent-color);
}

.upload-area :deep(.el-upload__tip) {
  color: var(--text-secondary);
}

.document-list :deep(.el-loading-mask) {
  background: rgba(8, 20, 38, 0.72);
}

.document-list :deep(.el-loading-spinner .path) {
  stroke: var(--accent-color);
}

.document-list :deep(.el-loading-spinner .el-loading-text) {
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

@media (max-width: 768px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }

  .filter-section {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field,
  .search-field {
    width: 100%;
    min-width: 0;
  }

  .search-input {
    width: 100%;
  }

  .category-select,
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

  .batch-toolbar,
  .month-export {
    flex-direction: column;
    align-items: stretch;
  }

  .month-export {
    width: 100%;
    margin-left: 0;
  }

  .month-picker,
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
