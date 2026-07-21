<template>
  <div class="document-upload">
    <div class="upload-header">
      <h2>文档上传</h2>
      <p>上传文档到 MinIO 对象存储</p>
    </div>

    <!-- 上传区域 -->
    <div class="upload-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>选择文件</span>
            <el-select v-model="selectedCategory" placeholder="选择分类" style="width: 200px">
              <el-option
                v-for="cat in categories"
                :key="cat.name"
                :label="cat.name"
                :value="cat.name"
              />
            </el-select>
          </div>
        </template>

        <el-upload
          class="upload-dragger"
          drag
          :auto-upload="false"
          :file-list="fileList"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          multiple
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.txt,.csv,.zip"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处，或 <em>点击选择</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 PDF、Word、Excel、PPT、图片、文本等格式，单个文件不超过 50MB
            </div>
          </template>
        </el-upload>

        <div class="upload-actions">
          <el-button type="primary" @click="handleUpload" :loading="uploading" :disabled="fileList.length === 0">
            <el-icon><Upload /></el-icon>
            上传 {{ fileList.length > 0 ? `(${fileList.length} 个文件)` : '' }}
          </el-button>
          <el-button @click="clearFiles" :disabled="fileList.length === 0">
            清空列表
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 上传进度 -->
    <div v-if="uploadProgress.length > 0" class="progress-section">
      <el-card>
        <template #header>
          <span>上传进度</span>
        </template>
        <div class="progress-list">
          <div v-for="(item, index) in uploadProgress" :key="index" class="progress-item">
            <div class="file-info">
              <el-icon :class="getFileIconClass(item.name)">
                <Document />
              </el-icon>
              <span class="file-name">{{ item.name }}</span>
            </div>
            <div class="progress-bar">
              <el-progress
                :percentage="item.progress"
                :status="item.status"
                :stroke-width="10"
              />
            </div>
            <div class="status-text">
              <span v-if="item.status === 'success'" class="success-text">上传成功</span>
              <span v-else-if="item.status === 'exception'" class="error-text">上传失败</span>
              <span v-else class="pending-text">{{ item.progress }}%</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 最近上传 -->
    <div class="recent-section">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>最近上传</span>
            <el-button link @click="loadRecentDocs">刷新</el-button>
          </div>
        </template>

        <el-table :data="recentDocs" v-loading="loading" stripe>
          <el-table-column label="文件名" min-width="200">
            <template #default="{ row }">
              <div class="file-name-cell">
                <el-icon :class="getFileIconClass(row.name)">
                  <Document />
                </el-icon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">
              {{ formatSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column label="分类" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.category || '未分类' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="180">
            <template #default="{ row }">
              {{ row.created_at }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="previewFile(row)">预览</el-button>
              <el-button link type="danger" @click="deleteFile(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" :title="previewFile.name" width="80%" fullscreen>
      <div class="preview-container">
        <iframe
          v-if="previewFile.url"
          :src="previewFile.url"
          class="preview-iframe"
        ></iframe>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Upload, Document } from '@element-plus/icons-vue'
import axios from 'axios'

// 状态
const uploading = ref(false)
const loading = ref(false)
const fileList = ref([])
const selectedCategory = ref('未分类')
const uploadProgress = ref([])
const recentDocs = ref([])
const previewVisible = ref(false)
const previewFile = ref({ name: '', url: '' })

// 分类列表
const categories = ref([
  { name: '巡检报告', icon: 'Document', color: '#409eff' },
  { name: '设备文档', icon: 'Setting', color: '#67c23a' },
  { name: '规章制度', icon: 'Document', color: '#e6a23c' },
  { name: '培训资料', icon: 'Document', color: '#f56c6c' },
  { name: '未分类', icon: 'Document', color: '#909399' },
])

// 文件图标样式
const getFileIconClass = (filename) => {
  const ext = filename.split('.').pop().toLowerCase()
  const iconMap = {
    'pdf': 'pdf-icon',
    'doc': 'word-icon', 'docx': 'word-icon',
    'xls': 'excel-icon', 'xlsx': 'excel-icon',
    'ppt': 'ppt-icon', 'pptx': 'ppt-icon',
    'jpg': 'image-icon', 'jpeg': 'image-icon', 'png': 'image-icon', 'gif': 'image-icon',
    'txt': 'text-icon', 'csv': 'text-icon',
    'zip': 'archive-icon', 'rar': 'archive-icon',
  }
  return iconMap[ext] || 'default-icon'
}

// 格式化文件大小
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

// 文件选择变化
const handleFileChange = (file, files) => {
  fileList.value = files
}

// 文件移除
const handleFileRemove = (file, files) => {
  fileList.value = files
}

// 清空文件列表
const clearFiles = () => {
  fileList.value = []
  uploadProgress.value = []
}

// 上传文件
const handleUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  uploading.value = true
  uploadProgress.value = fileList.value.map(f => ({
    name: f.name,
    progress: 0,
    status: ''
  }))

  let successCount = 0
  let failCount = 0

  for (let i = 0; i < fileList.value.length; i++) {
    const file = fileList.value[i]
    try {
      const formData = new FormData()
      formData.append('file', file.raw)
      formData.append('category', selectedCategory.value)

      // 模拟进度
      uploadProgress.value[i].progress = 30

      const response = await axios.post('/api/document/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          uploadProgress.value[i].progress = Math.min(90, percent)
        }
      })

      if (response.data.success) {
        uploadProgress.value[i].progress = 100
        uploadProgress.value[i].status = 'success'
        successCount++
      } else {
        uploadProgress.value[i].status = 'exception'
        failCount++
      }
    } catch (error) {
      console.error('上传失败:', error)
      uploadProgress.value[i].status = 'exception'
      failCount++
    }
  }

  uploading.value = false

  if (successCount > 0) {
    ElMessage.success(`成功上传 ${successCount} 个文件`)
    loadRecentDocs()
  }
  if (failCount > 0) {
    ElMessage.error(`${failCount} 个文件上传失败`)
  }
}

// 加载最近文档
const loadRecentDocs = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/document/list', {
      params: { page: 1, page_size: 10 }
    })
    if (response.data.success) {
      recentDocs.value = response.data.data
    }
  } catch (error) {
    console.error('加载文档列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 预览文件
const previewFile = (doc) => {
  previewFile.value = {
    name: doc.name,
    url: doc.url
  }
  previewVisible.value = true
}

// 删除文件
const deleteFile = async (doc) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${doc.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )

    const response = await axios.delete(`/api/document/${doc.object_name}`)
    if (response.data.success) {
      ElMessage.success('删除成功')
      loadRecentDocs()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 页面加载时获取最近文档
onMounted(() => {
  loadRecentDocs()
})
</script>

<style scoped>
.document-upload {
  padding: 20px;
}

.upload-header {
  margin-bottom: 24px;
}

.upload-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.upload-header p {
  margin: 0;
  color: #909399;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-dragger {
  width: 100%;
}

.upload-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.progress-section {
  margin-top: 24px;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 200px;
}

.file-name {
  font-weight: 500;
}

.progress-bar {
  flex: 1;
}

.status-text {
  min-width: 80px;
  text-align: right;
}

.success-text {
  color: #67c23a;
}

.error-text {
  color: #f56c6c;
}

.pending-text {
  color: #909399;
}

.recent-section {
  margin-top: 24px;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 文件图标颜色 */
.pdf-icon { color: #f40f02; }
.word-icon { color: #2b579a; }
.excel-icon { color: #217346; }
.ppt-icon { color: #d24726; }
.image-icon { color: #67c23a; }
.text-icon { color: #909399; }
.archive-icon { color: #e6a23c; }
.default-icon { color: #909399; }

.preview-container {
  height: calc(100vh - 150px);
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
