<template>
  <div class="document-hub">
    <!-- 页面头部 -->
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

    <!-- 统计卡片 -->
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
            <span class="stat-label">最近访问</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 搜索和筛选 -->
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

    <!-- 文档列表 -->
    <div class="document-grid">
      <el-card
        v-for="doc in filteredDocuments"
        :key="doc.id"
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
        <div class="card-body" @click="previewDoc(doc)">
          <h4 class="doc-name">{{ doc.name }}</h4>
          <p class="doc-meta">
            <span>{{ formatSize(doc.size) }}</span>
            <span>{{ doc.updatedAt }}</span>
          </p>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredDocuments.length === 0" class="empty-state">
      <el-icon class="empty-icon"><FolderOpened /></el-icon>
      <h3>暂无文档</h3>
      <p>点击上方"上传文档"按钮开始上传</p>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="500px">
      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="handleFileChange"
        multiple
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 Word、Excel、PPT、PDF、图片等格式
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <OnlineDocEditor
      v-model="previewDialogVisible"
      :file-url="previewFile.url"
      :file-name="previewFile.name"
      :file-type="previewFile.type"
      editor-type="local"
      @close="previewDialogVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, UploadFilled, Search, Document, FolderOpened,
  Clock, MoreFilled, View, Edit, Download, Delete
} from '@element-plus/icons-vue'
import OnlineDocEditor from '@/components/OnlineDocEditor.vue'

// 文档列表
const documents = ref([
  {
    id: 1,
    name: '巡检报告模板.docx',
    type: 'word',
    size: 25600,
    category: '模板',
    updatedAt: '2024-07-20',
    url: '/documents/template.docx'
  },
  {
    id: 2,
    name: '设备维护记录.xlsx',
    type: 'excel',
    size: 51200,
    category: '记录',
    updatedAt: '2024-07-19',
    url: '/documents/maintenance.xlsx'
  },
  {
    id: 3,
    name: '系统操作手册.pdf',
    type: 'pdf',
    size: 1024000,
    category: '文档',
    updatedAt: '2024-07-18',
    url: '/documents/manual.pdf'
  }
])

// 搜索和筛选
const searchQuery = ref('')
const selectedCategory = ref('')
const sortBy = ref('updated')

// 上传相关
const uploadDialogVisible = ref(false)
const uploadFileList = ref([])

// 预览相关
const previewDialogVisible = ref(false)
const previewFile = ref({ url: '', name: '', type: '' })

// 计算属性
const categories = computed(() => {
  const cats = new Set(documents.value.map(d => d.category))
  return Array.from(cats)
})

const recentCount = computed(() => {
  const now = new Date()
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  return documents.value.filter(d => new Date(d.updatedAt) >= weekAgo).length
})

const filteredDocuments = computed(() => {
  let result = [...documents.value]

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(d => d.name.toLowerCase().includes(query))
  }

  // 分类过滤
  if (selectedCategory.value) {
    result = result.filter(d => d.category === selectedCategory.value)
  }

  // 排序
  result.sort((a, b) => {
    if (sortBy.value === 'name') return a.name.localeCompare(b.name)
    if (sortBy.value === 'size') return b.size - a.size
    return new Date(b.updatedAt) - new Date(a.updatedAt)
  })

  return result
})

// 工具函数
const getIconClass = (type) => {
  const classMap = {
    'word': 'word-icon',
    'excel': 'excel-icon',
    'powerpoint': 'ppt-icon',
    'pdf': 'pdf-icon',
    'image': 'image-icon'
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

// 操作函数
const showUploadDialog = () => {
  uploadFileList.value = []
  uploadDialogVisible.value = true
}

const handleFileChange = (file, fileList) => {
  uploadFileList.value = fileList
}

const handleUpload = () => {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  // 模拟上传
  uploadFileList.value.forEach(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    let type = 'unknown'
    if (['doc', 'docx'].includes(ext)) type = 'word'
    else if (['xls', 'xlsx'].includes(ext)) type = 'excel'
    else if (['ppt', 'pptx'].includes(ext)) type = 'powerpoint'
    else if (ext === 'pdf') type = 'pdf'
    else if (['jpg', 'jpeg', 'png', 'gif'].includes(ext)) type = 'image'

    documents.value.unshift({
      id: Date.now() + Math.random(),
      name: file.name,
      type,
      size: file.size,
      category: '未分类',
      updatedAt: new Date().toISOString().split('T')[0],
      url: URL.createObjectURL(file.raw)
    })
  })

  ElMessage.success('上传成功')
  uploadDialogVisible.value = false
}

const previewDoc = (doc) => {
  previewFile.value = {
    url: doc.url,
    name: doc.name,
    type: doc.type
  }
  previewDialogVisible.value = true
}

const editDoc = (doc) => {
  // 根据文件类型选择编辑方式
  if (['word', 'excel', 'powerpoint'].includes(doc.type)) {
    // 使用在线编辑服务
    const officeUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(doc.url)}`
    window.open(officeUrl, '_blank')
  } else {
    previewDoc(doc)
  }
}

const downloadDoc = (doc) => {
  const link = document.createElement('a')
  link.href = doc.url
  link.download = doc.name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const deleteDoc = async (doc) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${doc.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    documents.value = documents.value.filter(d => d.id !== doc.id)
    ElMessage.success('删除成功')
  } catch {
    // 取消
  }
}

onMounted(() => {
  // 可以在这里加载文档列表
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
.image-icon { color: #67c23a; }
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
