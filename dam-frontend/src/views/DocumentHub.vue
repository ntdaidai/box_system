<template>
  <div class="document-hub">
    <div class="page-header">
      <div class="header-content">
        <h2 class="page-title">文档中心</h2>
        <p class="page-desc">上传、预览和管理您的文档</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showUploadDialog">
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
            <span class="stat-value">{{ recentCount }}</span>
            <span class="stat-label">最近修改</span>
          </div>
        </div>
      </el-card>
    </div>

    <div class="filter-section">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文档..."
        :prefix-icon="Search"
        clearable
        class="search-input"
      />
      <el-select v-model="selectedCategory" placeholder="文档分类" clearable>
        <el-option
          v-for="cat in categories"
          :key="cat"
          :label="cat"
          :value="cat"
        />
      </el-select>
      <el-select v-model="sortBy" placeholder="排序方式">
        <el-option label="最近修改" value="updated" />
        <el-option label="文件名称" value="name" />
        <el-option label="文件大小" value="size" />
      </el-select>
    </div>

    <div v-loading="loading" class="document-grid">
      <el-card
        v-for="doc in filteredDocuments"
        :key="doc.document_id"
        class="document-card"
        shadow="hover"
      >
        <div class="card-header">
          <el-icon class="doc-icon" :class="getIconClass(doc.type)">
            <Document />
          </el-icon>
          <el-dropdown trigger="click">
            <el-button link>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="previewDoc(doc)">
                  <el-icon><View /></el-icon>
                  预览
                </el-dropdown-item>
                <el-dropdown-item @click="editDoc(doc)">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-dropdown-item>
                <el-dropdown-item @click="downloadDoc(doc)">
                  <el-icon><Download /></el-icon>
                  下载
                </el-dropdown-item>
                <el-dropdown-item divided @click="deleteDoc(doc)">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="card-body" @click="editDoc(doc)">
          <h4 class="doc-name" :title="doc.name">{{ doc.name }}</h4>
          <p class="doc-meta">
            <span>{{ formatSize(doc.size) }}</span>
            <span>{{ formatDate(doc.updatedAt) }}</span>
          </p>
        </div>
      </el-card>
    </div>

    <div v-if="!loading && filteredDocuments.length === 0" class="empty-state">
      <el-icon class="empty-icon"><FolderOpened /></el-icon>
      <h3>暂无文档</h3>
      <p>点击上方“上传文档”按钮开始上传</p>
    </div>

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
      :title="previewTitle"
      width="80%"
      fullscreen
      @closed="previewConfig = null"
    >
      <OnlyOfficeEditor
        v-if="previewConfig"
        :config="previewConfig"
        mode="view"
        editor-height="calc(100vh - 150px)"
        :user="currentUser"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, UploadFilled, Search, Document, FolderOpened,
  Clock, MoreFilled, View, Edit, Download, Delete
} from '@element-plus/icons-vue'
import axios from 'axios'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'

const router = useRouter()

const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const searchQuery = ref('')
const selectedCategory = ref('')
const sortBy = ref('updated')

const uploadDialogVisible = ref(false)
const uploadFileList = ref([])

const previewDialogVisible = ref(false)
const previewTitle = ref('')
const previewConfig = ref(null)

const currentUser = ref({
  id: 'user_001',
  name: '管理员'
})

const categories = computed(() => {
  const cats = new Set(documents.value.map((doc) => doc.category))
  return Array.from(cats)
})

const recentCount = computed(() => {
  const now = new Date()
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  return documents.value.filter((doc) => new Date(doc.updatedAt) >= weekAgo).length
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

  result.sort((a, b) => {
    if (sortBy.value === 'name') return a.name.localeCompare(b.name)
    if (sortBy.value === 'size') return b.size - a.size
    return new Date(b.updatedAt) - new Date(a.updatedAt)
  })

  return result
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

const getIconClass = (type) => {
  const classMap = {
    word: 'word-icon',
    excel: 'excel-icon',
    powerpoint: 'ppt-icon',
    pdf: 'pdf-icon'
  }
  return classMap[type] || 'default-icon'
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

const formatDate = (value) => {
  if (!value) return '-'
  return String(value).slice(0, 10)
}

const normalizeDocument = (doc) => ({
  ...doc,
  id: doc.document_id,
  name: doc.title,
  type: getDisplayType(doc.file_type),
  category: getCategory(doc.file_type),
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
        page_size: 200
      }
    })

    if (response.data.success) {
      documents.value = response.data.data.documents.map(normalizeDocument)
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

    const response = await axios.delete(`/api/onlyoffice/document/${doc.document_id}`)
    if (response.data.success) {
      ElMessage.success('删除成功')
      await loadDocuments()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.document-hub {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: #fff;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-desc {
  margin: 0;
  opacity: 0.9;
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
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.filter-section {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
}

.search-input {
  width: 300px;
}

.document-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  min-height: 120px;
}

.document-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 8px;
}

.document-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.doc-icon {
  font-size: 32px;
}

.word-icon { color: #2b579a; }
.excel-icon { color: #217346; }
.ppt-icon { color: #d24726; }
.pdf-icon { color: #f40f02; }
.default-icon { color: #909399; }

.card-body {
  cursor: pointer;
}

.doc-name {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  display: flex;
  justify-content: space-between;
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  background: #fff;
  border-radius: 8px;
}

.empty-icon {
  font-size: 64px;
  color: #c0c4cc;
  margin-bottom: 20px;
}

.empty-state h3 {
  margin: 0 0 8px 0;
  color: #606266;
}

.empty-state p {
  margin: 0;
  color: #909399;
}

.upload-area {
  width: 100%;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }

  .stats-cards {
    grid-template-columns: 1fr;
  }

  .filter-section {
    flex-direction: column;
  }

  .search-input {
    width: 100%;
  }

  .document-grid {
    grid-template-columns: 1fr;
  }
}
</style>
