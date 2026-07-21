<template>
  <div class="document-viewer">
    <!-- 工具栏 -->
    <div class="viewer-toolbar">
      <div class="toolbar-left">
        <el-icon class="file-icon" :class="fileTypeClass"><Document /></el-icon>
        <span class="file-name">{{ fileName }}</span>
        <el-tag :type="fileTypeTag" size="small">{{ fileTypeLabel }}</el-tag>
      </div>
      <div class="toolbar-right">
        <el-button-group>
          <el-button @click="zoomOut" :disabled="scale <= 0.5">
            <el-icon><ZoomOut /></el-icon>
          </el-button>
          <el-button disabled>{{ Math.round(scale * 100) }}%</el-button>
          <el-button @click="zoomIn" :disabled="scale >= 2">
            <el-icon><ZoomIn /></el-icon>
          </el-button>
        </el-button-group>
        <el-button @click="fitWidth">适合宽度</el-button>
        <el-button @click="downloadFile">
          <el-icon><Download /></el-icon>
          下载
        </el-button>
      </div>
    </div>

    <!-- 文档内容区域 -->
    <div class="viewer-content" ref="contentRef">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>文档加载中...</span>
      </div>

      <!-- 错误提示 -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        closable
        @close="error = ''"
      />

      <!-- PDF 预览 -->
      <div v-if="fileType === 'pdf' && !loading" class="pdf-container">
        <iframe
          :src="pdfUrl"
          class="pdf-viewer"
          @load="onPdfLoad"
        ></iframe>
      </div>

      <!-- 图片预览 -->
      <div v-else-if="isImage && !loading" class="image-container">
        <img
          :src="fileUrl"
          :style="{ transform: `scale(${scale})` }"
          class="preview-image"
          @load="onImageLoad"
        />
      </div>

      <!-- 文本预览 -->
      <div v-else-if="isText && !loading" class="text-container">
        <pre class="text-content">{{ textContent }}</pre>
      </div>

      <!-- 不支持的格式提示 -->
      <div v-else-if="!loading && !error" class="unsupported-container">
        <el-icon class="unsupported-icon"><Warning /></el-icon>
        <h3>此文件格式不支持在线预览</h3>
        <p>请下载文件后使用相应软件打开</p>
        <el-button type="primary" @click="downloadFile">
          <el-icon><Download /></el-icon>
          下载文件
        </el-button>
      </div>
    </div>

    <!-- 页面信息（PDF） -->
    <div v-if="fileType === 'pdf'" class="page-info">
      <span>PDF 文档</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Document, ZoomIn, ZoomOut, Download, Loading, Warning } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  // 文件 URL
  fileUrl: {
    type: String,
    required: true
  },
  // 文件名称
  fileName: {
    type: String,
    default: '文档'
  },
  // 文件类型（可选，自动检测）
  fileType: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['load', 'error', 'download'])

// 状态
const loading = ref(true)
const error = ref('')
const scale = ref(1)
const textContent = ref('')
const contentRef = ref(null)

// 计算文件类型
const detectedFileType = computed(() => {
  if (props.fileType) return props.fileType.toLowerCase()

  const url = props.fileUrl.toLowerCase()
  if (url.includes('.pdf')) return 'pdf'
  if (url.includes('.docx') || url.includes('.doc')) return 'word'
  if (url.includes('.xlsx') || url.includes('.xls')) return 'excel'
  if (url.includes('.pptx') || url.includes('.ppt')) return 'powerpoint'
  if (url.includes('.jpg') || url.includes('.jpeg') || url.includes('.png') || url.includes('.gif')) return 'image'
  if (url.includes('.txt') || url.includes('.log')) return 'text'
  return 'unknown'
})

// 是否为图片
const isImage = computed(() => {
  return ['image'].includes(detectedFileType.value)
})

// 是否为文本
const isText = computed(() => {
  return ['text'].includes(detectedFileType.value)
})

// 文件类型样式类
const fileTypeClass = computed(() => {
  const classMap = {
    'pdf': 'pdf-icon',
    'word': 'word-icon',
    'excel': 'excel-icon',
    'powerpoint': 'ppt-icon',
    'image': 'image-icon',
    'text': 'text-icon'
  }
  return classMap[detectedFileType.value] || 'default-icon'
})

// 文件类型标签样式
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

// PDF URL（添加预览参数）
const pdfUrl = computed(() => {
  if (detectedFileType.value === 'pdf') {
    // 使用 PDF.js 或浏览器内置预览
    return props.fileUrl
  }
  return ''
})

// 加载文本内容
const loadTextContent = async () => {
  if (!isText.value) return

  try {
    const response = await axios.get(props.fileUrl, { responseType: 'text' })
    textContent.value = response.data
  } catch (err) {
    error.value = '加载文本文件失败'
    console.error('加载文本失败:', err)
  }
}

// 缩放控制
const zoomIn = () => {
  if (scale.value < 2) {
    scale.value = Math.min(2, scale.value + 0.1)
  }
}

const zoomOut = () => {
  if (scale.value > 0.5) {
    scale.value = Math.max(0.5, scale.value - 0.1)
  }
}

const fitWidth = () => {
  scale.value = 1
}

// 下载文件
const downloadFile = () => {
  const link = document.createElement('a')
  link.href = props.fileUrl
  link.download = props.fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  emit('download')
}

// 事件处理
const onPdfLoad = () => {
  loading.value = false
  emit('load')
}

const onImageLoad = () => {
  loading.value = false
  emit('load')
}

// 初始化
onMounted(() => {
  if (isText.value) {
    loadTextContent()
  } else {
    // 非文本文件，延迟隐藏加载状态
    setTimeout(() => {
      loading.value = false
    }, 1000)
  }
})

// 监听 URL 变化
watch(() => props.fileUrl, () => {
  loading.value = true
  error.value = ''
  if (isText.value) {
    loadTextContent()
  }
})
</script>

<style scoped>
.document-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.viewer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-icon {
  font-size: 24px;
}

.pdf-icon { color: #f40f02; }
.word-icon { color: #2b579a; }
.excel-icon { color: #217346; }
.ppt-icon { color: #d24726; }
.image-icon { color: #67c23a; }
.text-icon { color: #909399; }
.default-icon { color: #909399; }

.file-name {
  font-weight: 500;
  color: #303133;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.viewer-content {
  flex: 1;
  overflow: auto;
  position: relative;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #909399;
}

.loading-icon {
  font-size: 48px;
  margin-bottom: 16px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.pdf-container {
  width: 100%;
  height: 100%;
}

.pdf-viewer {
  width: 100%;
  height: 100%;
  border: none;
}

.image-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  min-height: 400px;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.3s ease;
}

.text-container {
  padding: 20px;
  overflow: auto;
}

.text-content {
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}

.unsupported-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #606266;
}

.unsupported-icon {
  font-size: 64px;
  color: #e6a23c;
  margin-bottom: 20px;
}

.unsupported-container h3 {
  margin: 0 0 10px 0;
  font-size: 18px;
}

.unsupported-container p {
  margin: 0 0 20px 0;
  color: #909399;
}

.page-info {
  display: flex;
  justify-content: center;
  padding: 8px 16px;
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
  color: #909399;
}
</style>
