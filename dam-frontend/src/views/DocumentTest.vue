<template>
  <div class="document-test">
    <div class="test-header">
      <h2>文档预览测试</h2>
      <p>测试文档上传和预览功能</p>
    </div>

    <!-- 上传区域 -->
    <div class="upload-section">
      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :show-file-list="false"
        accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.jpg,.jpeg,.png,.gif,.txt"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 PDF、Word、Excel、PPT、图片、文本等格式
          </div>
        </template>
      </el-upload>
    </div>

    <!-- 文件信息 -->
    <div v-if="selectedFile" class="file-info">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="文件名称">
          {{ selectedFile.name }}
        </el-descriptions-item>
        <el-descriptions-item label="文件大小">
          {{ formatFileSize(selectedFile.size) }}
        </el-descriptions-item>
        <el-descriptions-item label="文件类型">
          <el-tag :type="fileTypeTag">{{ fileTypeLabel }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="action-buttons">
        <el-button type="primary" @click="previewFile">
          <el-icon><View /></el-icon>
          预览
        </el-button>
        <el-button @click="clearFile">
          <el-icon><Delete /></el-icon>
          清除
        </el-button>
      </div>
    </div>

    <!-- 预览区域 -->
    <div v-if="previewUrl" class="preview-section">
      <div class="preview-header">
        <h3>文档预览</h3>
        <el-button @click="closePreview">
          <el-icon><Close /></el-icon>
          关闭预览
        </el-button>
      </div>
      <div class="preview-container">
        <DocumentViewer
          :file-url="previewUrl"
          :file-name="selectedFile?.name || '文档'"
          :file-type="detectedFileType"
          @load="onPreviewLoad"
          @error="onPreviewError"
        />
      </div>
    </div>

    <!-- 示例文档 -->
    <div class="examples-section">
      <h3>示例文档</h3>
      <div class="examples-grid">
        <div
          v-for="example in exampleDocuments"
          :key="example.name"
          class="example-card"
          @click="loadExample(example)"
        >
          <el-icon class="example-icon" :class="example.iconClass">
            <Document />
          </el-icon>
          <div class="example-info">
            <span class="example-name">{{ example.name }}</span>
            <span class="example-type">{{ example.type }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, View, Delete, Close, Document } from '@element-plus/icons-vue'
import DocumentViewer from '@/components/DocumentViewer.vue'

// 状态
const selectedFile = ref(null)
const previewUrl = ref('')
const fileUrl = ref('')

// 示例文档列表
const exampleDocuments = [
  {
    name: '示例 PDF',
    type: 'PDF 文档',
    url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
    iconClass: 'pdf-icon'
  },
  {
    name: '示例图片',
    type: 'JPG 图片',
    url: 'https://picsum.photos/800/600',
    iconClass: 'image-icon'
  },
  {
    name: '示例文本',
    type: 'TXT 文本',
    url: 'data:text/plain;charset=utf-8,Hello%20World!%0AThis%20is%20a%20test%20file.',
    iconClass: 'text-icon'
  }
]

// 计算文件类型
const detectedFileType = computed(() => {
  if (!selectedFile.value) return ''
  const name = selectedFile.value.name.toLowerCase()
  if (name.endsWith('.pdf')) return 'pdf'
  if (name.endsWith('.docx') || name.endsWith('.doc')) return 'word'
  if (name.endsWith('.xlsx') || name.endsWith('.xls')) return 'excel'
  if (name.endsWith('.pptx') || name.endsWith('.ppt')) return 'powerpoint'
  if (name.match(/\.(jpg|jpeg|png|gif)$/)) return 'image'
  if (name.endsWith('.txt')) return 'text'
  return 'unknown'
})

// 文件类型标签
const fileTypeTag = computed(() => {
  const tagMap = {
    'pdf': 'danger',
    'word': 'primary',
    'excel': 'success',
    'powerpoint': 'warning',
    'image': 'info',
    'text': 'info'
  }
  return tagMap[detectedFileType.value] || 'info'
})

// 文件类型显示名称
const fileTypeLabel = computed(() => {
  const labelMap = {
    'pdf': 'PDF',
    'word': 'Word',
    'excel': 'Excel',
    'powerpoint': 'PPT',
    'image': '图片',
    'text': '文本'
  }
  return labelMap[detectedFileType.value] || '文档'
})

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`
}

// 文件选择
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  previewUrl.value = ''
}

// 预览文件
const previewFile = () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  // 创建本地 URL
  previewUrl.value = URL.createObjectURL(selectedFile.value)
}

// 清除文件
const clearFile = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  selectedFile.value = null
  previewUrl.value = ''
}

// 关闭预览
const closePreview = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
}

// 加载示例文档
const loadExample = (example) => {
  selectedFile.value = { name: example.name, size: 0 }
  previewUrl.value = example.url
}

// 预览加载完成
const onPreviewLoad = () => {
  ElMessage.success('文档加载完成')
}

// 预览错误
const onPreviewError = (error) => {
  ElMessage.error(error)
}
</script>

<style scoped>
.document-test {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.test-header {
  text-align: center;
  margin-bottom: 30px;
}

.test-header h2 {
  margin: 0 0 10px 0;
  font-size: 24px;
  color: #303133;
}

.test-header p {
  margin: 0;
  color: #909399;
}

.upload-section {
  margin-bottom: 30px;
}

.upload-area {
  width: 100%;
}

.file-info {
  margin-bottom: 30px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.preview-section {
  margin-bottom: 30px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.preview-header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.preview-container {
  height: 600px;
}

.examples-section {
  margin-top: 40px;
}

.examples-section h3 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #303133;
}

.examples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.example-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.example-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.example-icon {
  font-size: 32px;
}

.pdf-icon { color: #f40f02; }
.image-icon { color: #67c23a; }
.text-icon { color: #909399; }

.example-info {
  display: flex;
  flex-direction: column;
}

.example-name {
  font-weight: 500;
  color: #303133;
}

.example-type {
  font-size: 12px;
  color: #909399;
}
</style>
