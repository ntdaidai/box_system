<template>
  <div class="document-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">文档管理</h2>
        <el-tag type="info" size="small">{{ documents.length }} 个文档</el-tag>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showUploadDialog">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <div class="filter-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文档名称..."
        :prefix-icon="Search"
        clearable
        class="search-input"
      />
      <el-select v-model="filterType" placeholder="文档类型" clearable>
        <el-option label="Word 文档" value="word" />
        <el-option label="Excel 表格" value="cell" />
        <el-option label="PPT 演示" value="slide" />
        <el-option label="PDF 文档" value="pdf" />
      </el-select>
    </div>

    <!-- 文档列表 -->
    <div class="document-list">
      <el-table
        :data="filteredDocuments"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column label="文档名称" min-width="300">
          <template #default="{ row }">
            <div class="document-name">
              <el-icon class="document-icon" :class="getFileTypeClass(row.file_type)">
                <Document />
              </el-icon>
              <span class="name-text">{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getFileTypeTag(row.file_type)" size="small">
              {{ getFileTypeLabel(row.file_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>

        <el-table-column label="修改时间" width="180">
          <template #default="{ row }">
            {{ row.updated_at }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              @click="openEditor(row)"
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button
              type="success"
              link
              @click="openDocumentPreview(row)"
            >
              <el-icon><View /></el-icon>
              预览
            </el-button>
            <el-button
              type="info"
              link
              @click="downloadDocument(row)"
            >
              <el-icon><Download /></el-icon>
              下载
            </el-button>
            <el-button
              type="danger"
              link
              @click="deleteDocument(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传文档"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="handleFileChange"
        :before-upload="beforeUpload"
        accept=".docx,.doc,.xlsx,.xls,.pptx,.ppt,.pdf,.odt,.ods,.odp,.csv,.txt"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 Word、Excel、PPT、PDF 等格式，单个文件不超过 50MB
          </div>
        </template>
      </el-upload>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleUpload" :loading="uploading">
            上传
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewDocument.title"
      width="80%"
      fullscreen
    >
      <div class="preview-container">
        <OnlyOfficeEditor
          ref="previewEditorRef"
          :document-url="previewDocument.url"
          :document-title="previewDocument.title"
          :document-type="previewDocument.document_type"
          mode="view"
          editor-height="calc(100vh - 150px)"
          :user="currentUser"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, UploadFilled, Search, Document, Edit, View,
  Download, Delete
} from '@element-plus/icons-vue'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'
import axios from 'axios'

const router = useRouter()

// 状态
const loading = ref(false)
const uploading = ref(false)
const documents = ref([])
const searchQuery = ref('')
const filterType = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 上传相关
const uploadDialogVisible = ref(false)
const uploadRef = ref(null)
const uploadFileList = ref([])

// 预览相关
const previewDialogVisible = ref(false)
const previewEditorRef = ref(null)
const previewDocument = ref({
  document_id: '',
  title: '',
  url: '',
  document_type: 'word'
})

// 当前用户
const currentUser = ref({
  id: 'user_001',
  name: '管理员'
})

const apiPublicBase = import.meta.env.VITE_API_BASE_URL || 'http://192.168.31.52:8090'

// 过滤后的文档列表
const filteredDocuments = computed(() => {
  let result = documents.value

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(doc =>
      doc.title.toLowerCase().includes(query)
    )
  }

  // 类型过滤
  if (filterType.value) {
    result = result.filter(doc => {
      const docType = getDocumentType(doc.file_type)
      return docType === filterType.value
    })
  }

  return result
})

// 获取文档类型
const getDocumentType = (extension) => {
  const typeMap = {
    'docx': 'word', 'doc': 'word', 'odt': 'word', 'rtf': 'word', 'txt': 'word',
    'xlsx': 'cell', 'xls': 'cell', 'ods': 'cell', 'csv': 'cell',
    'pptx': 'slide', 'ppt': 'slide', 'odp': 'slide',
    'pdf': 'pdf'
  }
  return typeMap[extension] || 'word'
}

// 获取文件类型标签样式
const getFileTypeTag = (type) => {
  const tagMap = {
    'docx': 'primary', 'doc': 'primary',
    'xlsx': 'success', 'xls': 'success',
    'pptx': 'warning', 'ppt': 'warning',
    'pdf': 'info'
  }
  return tagMap[type] || 'info'
}

// 获取文件类型显示名称
const getFileTypeLabel = (type) => {
  const labelMap = {
    'docx': 'Word', 'doc': 'Word',
    'xlsx': 'Excel', 'xls': 'Excel',
    'pptx': 'PPT', 'ppt': 'PPT',
    'pdf': 'PDF'
  }
  return labelMap[type] || type.toUpperCase()
}

// 获取文件类型样式类
const getFileTypeClass = (type) => {
  const classMap = {
    'docx': 'word-icon', 'doc': 'word-icon',
    'xlsx': 'excel-icon', 'xls': 'excel-icon',
    'pptx': 'ppt-icon', 'ppt': 'ppt-icon',
    'pdf': 'pdf-icon'
  }
  return classMap[type] || 'default-icon'
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`
}

// 加载文档列表
const loadDocuments = async () => {
  try {
    loading.value = true

    const response = await axios.get('/api/onlyoffice/documents', {
      params: {
        user_id: currentUser.value.id,
        page: currentPage.value,
        page_size: pageSize.value
      }
    })

    if (response.data.success) {
      documents.value = response.data.data.documents
      total.value = response.data.data.total
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

// 显示上传对话框
const showUploadDialog = () => {
  uploadFileList.value = []
  uploadDialogVisible.value = true
}

// 文件选择变化
const handleFileChange = (file, fileList) => {
  uploadFileList.value = fileList
}

// 上传前验证
const beforeUpload = (file) => {
  // 验证文件大小（50MB）
  const maxSize = 50 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }

  // 验证文件类型
  const allowedTypes = [
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-powerpoint',
    'application/pdf',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
    'text/csv',
    'text/plain'
  ]

  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('不支持的文件类型')
    return false
  }

  return true
}

// 执行上传
const handleUpload = async () => {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
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
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      if (response.data.success) {
        ElMessage.success(`文件 ${file.name} 上传成功`)
      } else {
        ElMessage.error(`文件 ${file.name} 上传失败`)
      }
    }

    // 刷新列表
    uploadDialogVisible.value = false
    loadDocuments()

  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

// 打开编辑器
const openEditor = (doc) => {
  router.push({
    name: 'DocumentEditor',
    params: { documentId: doc.document_id },
    query: {
      title: doc.title,
      type: doc.file_type
    }
  })
}

// 预览文档
const openDocumentPreview = (doc) => {
  previewDocument.value = {
    document_id: doc.document_id,
    title: doc.title,
    url: `${apiPublicBase}/api/onlyoffice/document/${doc.document_id}`,
    document_type: getDocumentType(doc.file_type)
  }
  previewDialogVisible.value = true
}

// 下载文档
const downloadDocument = async (doc) => {
  try {
    const response = await axios.get(`/api/onlyoffice/document/${doc.document_id}`, {
      responseType: 'blob'
    })

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', doc.title)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

// 删除文档
const deleteDocument = async (doc) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.title}" 吗？此操作不可恢复。`,
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
      loadDocuments()
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

// 分页大小变化
const handleSizeChange = (val) => {
  pageSize.value = val
  loadDocuments()
}

// 页码变化
const handleCurrentChange = (val) => {
  currentPage.value = val
  loadDocuments()
}

// 页面加载时获取文档列表
onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.document-management {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.search-input {
  width: 300px;
}

.document-list {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.document-name {
  display: flex;
  align-items: center;
  gap: 12px;
}

.document-icon {
  font-size: 24px;
}

.word-icon {
  color: #2b579a;
}

.excel-icon {
  color: #217346;
}

.ppt-icon {
  color: #d24726;
}

.pdf-icon {
  color: #f40f02;
}

.default-icon {
  color: #909399;
}

.name-text {
  font-weight: 500;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.preview-container {
  height: calc(100vh - 150px);
}

/* 响应式布局 */
@media (max-width: 768px) {
  .document-management {
    padding: 12px;
  }

  .page-header,
  .filter-bar {
    flex-direction: column;
    gap: 12px;
  }

  .search-input {
    width: 100%;
  }
}
</style>
