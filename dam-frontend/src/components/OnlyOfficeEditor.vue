<template>
  <div class="onlyoffice-editor">
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

    <!-- OnlyOffice 编辑器容器 -->
    <div ref="editorContainer" id="onlyoffice-editor" :style="{ height: editorHeight }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'

// Props 定义
const props = defineProps({
  // 文档 URL（必填）
  documentUrl: {
    type: String,
    required: true
  },
  // 文档标题
  documentTitle: {
    type: String,
    default: '未命名文档'
  },
  // 文档类型：word | cell | slide
  documentType: {
    type: String,
    default: 'word',
    validator: (value) => ['word', 'cell', 'slide'].includes(value)
  },
  // 编辑器模式：edit | view | fillForms
  mode: {
    type: String,
    default: 'edit',
    validator: (value) => ['edit', 'view', 'fillForms'].includes(value)
  },
  // 编辑器高度
  editorHeight: {
    type: String,
    default: '600px'
  },
  // 文档 key（用于协同编辑，相同 key 的用户会进入同一编辑会话）
  documentKey: {
    type: String,
    default: ''
  },
  // 用户信息
  user: {
    type: Object,
    default: () => ({
      id: 'user_001',
      name: '用户'
    })
  },
  // 回调 URL（文档保存时调用）
  callbackUrl: {
    type: String,
    default: ''
  },
  // 语言
  lang: {
    type: String,
    default: 'zh-CN'
  },
  // 是否显示标题栏
  showTitleBar: {
    type: Boolean,
    default: true
  }
})

// Emits 定义
const emit = defineEmits([
  'ready',
  'documentStateChange',
  'error',
  'save',
  'close'
])

// 响应式状态
const editorContainer = ref(null)
const loading = ref(true)
const error = ref('')
let docEditor = null

// 计算文档 key（如果没有提供，使用时间戳生成唯一 key）
const getDocumentKey = () => {
  if (props.documentKey) {
    return props.documentKey
  }
  // 使用文档 URL 的 hash 作为 key，确保同一文档同一会话
  return `doc_${hashString(props.documentUrl)}_${Date.now()}`
}

// 简单字符串哈希函数
const hashString = (str) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // 转换为 32 位整数
  }
  return Math.abs(hash).toString(36)
}

// 获取文档扩展名
const getDocumentExtension = () => {
  const url = props.documentUrl
  const lastDot = url.lastIndexOf('.')
  if (lastDot === -1) return 'docx'
  return url.substring(lastDot + 1).toLowerCase()
}

// 获取文档图标 URL（可选，显示在标题栏）
const getDocumentIconUrl = () => {
  const ext = getDocumentExtension()
  const iconMap = {
    'docx': '/assets/icons/docx.svg',
    'doc': '/assets/icons/doc.svg',
    'xlsx': '/assets/icons/xlsx.svg',
    'xls': '/assets/icons/xls.svg',
    'pptx': '/assets/icons/pptx.svg',
    'ppt': '/assets/icons/ppt.svg',
    'pdf': '/assets/icons/pdf.svg'
  }
  return iconMap[ext] || '/assets/icons/doc.svg'
}

// 初始化 OnlyOffice 编辑器
const initEditor = async () => {
  try {
    loading.value = true
    error.value = ''

    // 检查 OnlyOffice API 是否已加载
    if (!window.DocsAPI) {
      // 动态加载 OnlyOffice API 脚本
      await loadOnlyOfficeScript()
    }

    // 等待 DOM 更新
    await nextTick()

    // 清理旧实例
    if (docEditor) {
      docEditor.destroyEditor()
      docEditor = null
    }

    // 配置编辑器选项
    const config = {
      document: {
        fileType: getDocumentExtension(),
        key: getDocumentKey(),
        title: props.documentTitle,
        url: props.documentUrl,
        permissions: {
          comment: props.mode === 'edit',
          download: true,
          edit: props.mode === 'edit',
          fillForms: props.mode === 'fillForms' || props.mode === 'edit',
          print: true,
          review: props.mode === 'edit'
        }
      },
      documentType: getDocumentType(),
      editorConfig: {
        callbackUrl: props.callbackUrl || undefined,
        lang: props.lang,
        mode: props.mode,
        user: {
          id: props.user.id,
          name: props.user.name
        },
        customization: {
          forcesave: true, // 强制保存
          compactHeader: !props.showTitleBar,
          toolbarNoTabs: false,
          hideRightMenu: false,
          hideRulers: false,
          macros: false,
          plugins: true
        }
      },
      height: props.editorHeight,
      width: '100%',
      type: 'desktop', // desktop 或 mobile
      events: {
        onAppReady: () => {
          loading.value = false
          emit('ready')
        },
        onDocumentStateChange: (event) => {
          emit('documentStateChange', event)
        },
        onError: (event) => {
          const errorMsg = `编辑器错误: ${event.data || '未知错误'}`
          error.value = errorMsg
          emit('error', errorMsg)
        }
      }
    }

    // 创建编辑器实例
    // 注意：需要替换为你的 OnlyOffice Document Server 地址
    const onlyofficeServerUrl = import.meta.env.VITE_ONLYOFFICE_URL || 'http://localhost:8080'
    docEditor = new window.DocsAPI.DocEditor('onlyoffice-editor', config)

  } catch (err) {
    const errorMsg = `初始化编辑器失败: ${err.message}`
    error.value = errorMsg
    emit('error', errorMsg)
    loading.value = false
  }
}

// 加载 OnlyOffice API 脚本
const loadOnlyOfficeScript = () => {
  return new Promise((resolve, reject) => {
    // 检查是否已加载
    if (window.DocsAPI) {
      resolve()
      return
    }

    // 动态创建 script 标签
    const script = document.createElement('script')
    const onlyofficeServerUrl = import.meta.env.VITE_ONLYOFFICE_URL || 'http://localhost:8080'
    script.src = `${onlyofficeServerUrl}/web-apps/apps/api/documents/api.js`
    script.async = true
    script.onload = () => {
      resolve()
    }
    script.onerror = () => {
      reject(new Error('无法加载 OnlyOffice API 脚本'))
    }
    document.head.appendChild(script)
  })
}

// 获取文档类型
const getDocumentType = () => {
  const ext = getDocumentExtension()
  const typeMap = {
    'docx': 'word',
    'doc': 'word',
    'odt': 'word',
    'rtf': 'word',
    'txt': 'word',
    'html': 'word',
    'xlsx': 'cell',
    'xls': 'cell',
    'ods': 'cell',
    'csv': 'cell',
    'pptx': 'slide',
    'ppt': 'slide',
    'odp': 'slide',
    'pdf': 'word' // PDF 使用 word 类型查看
  }
  return typeMap[ext] || props.documentType
}

// 销毁编辑器
const destroyEditor = () => {
  if (docEditor) {
    docEditor.destroyEditor()
    docEditor = null
  }
}

// 监听 props 变化，重新初始化编辑器
watch(
  () => [props.documentUrl, props.documentKey],
  () => {
    if (props.documentUrl) {
      destroyEditor()
      initEditor()
    }
  }
)

// 组件挂载时初始化
onMounted(() => {
  if (props.documentUrl) {
    initEditor()
  }
})

// 组件卸载前清理
onBeforeUnmount(() => {
  destroyEditor()
})

// 暴露方法给父组件
defineExpose({
  // 获取编辑器实例
  getEditor: () => docEditor,
  // 强制保存
  save: () => {
    if (docEditor) {
      docEditor.save()
    }
  },
  // 重新加载文档
  reload: () => {
    destroyEditor()
    initEditor()
  },
  // 销毁编辑器
  destroy: destroyEditor
})
</script>

<style scoped>
.onlyoffice-editor {
  width: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
}

.loading-icon {
  font-size: 32px;
  margin-bottom: 12px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

#onlyoffice-editor {
  width: 100%;
  min-height: 400px;
}
</style>
