<template>
  <div class="online-doc-editor">
    <el-dialog
      v-model="visible"
      :title="dialogTitle"
      width="90%"
      fullscreen
      :close-on-click-modal="false"
      @close="handleClose"
    >
      <div class="editor-container">
        <!-- Google Docs 嵌入 -->
        <iframe
          v-if="editorType === 'google'"
          :src="googleDocsUrl"
          class="editor-iframe"
          frameborder="0"
          allowfullscreen
        ></iframe>

        <!-- Microsoft Office Online 嵌入 -->
        <iframe
          v-else-if="editorType === 'microsoft'"
          :src="officeOnlineUrl"
          class="editor-iframe"
          frameborder="0"
          allowfullscreen
        ></iframe>

        <!-- 本地预览 -->
        <div v-else class="local-preview">
          <DocumentViewer
            :file-url="fileUrl"
            :file-name="fileName"
            :file-type="fileType"
          />
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleClose">关闭</el-button>
          <el-button type="primary" @click="openInNewTab">
            <el-icon><Link /></el-icon>
            在新标签页打开
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Link } from '@element-plus/icons-vue'
import DocumentViewer from './DocumentViewer.vue'

const props = defineProps({
  // 是否显示对话框
  modelValue: {
    type: Boolean,
    default: false
  },
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
  // 文件类型
  fileType: {
    type: String,
    default: ''
  },
  // 编辑器类型：google | microsoft | local
  editorType: {
    type: String,
    default: 'local'
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

// 对话框可见性
const visible = ref(props.modelValue)

// 监听 modelValue 变化
watch(() => props.modelValue, (val) => {
  visible.value = val
})

// 监听 visible 变化
watch(visible, (val) => {
  emit('update:modelValue', val)
})

// 对话框标题
const dialogTitle = computed(() => {
  return `编辑文档 - ${props.fileName}`
})

// Google Docs 编辑器 URL
const googleDocsUrl = computed(() => {
  if (!props.fileUrl) return ''
  // 使用 Google Docs Viewer 嵌入文档
  return `https://docs.google.com/gview?url=${encodeURIComponent(props.fileUrl)}&embedded=true`
})

// Microsoft Office Online URL
const officeOnlineUrl = computed(() => {
  if (!props.fileUrl) return ''
  // 使用 Office Online Viewer 嵌入文档
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(props.fileUrl)}`
})

// 在新标签页打开
const openInNewTab = () => {
  let url = props.fileUrl

  // 根据编辑器类型选择在线服务
  if (props.editorType === 'google') {
    url = `https://docs.google.com/gview?url=${encodeURIComponent(props.fileUrl)}`
  } else if (props.editorType === 'microsoft') {
    url = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(props.fileUrl)}`
  }

  window.open(url, '_blank')
}

// 关闭对话框
const handleClose = () => {
  visible.value = false
  emit('close')
}
</script>

<style scoped>
.online-doc-editor {
  width: 100%;
}

.editor-container {
  height: calc(100vh - 150px);
  overflow: hidden;
}

.editor-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.local-preview {
  width: 100%;
  height: 100%;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
