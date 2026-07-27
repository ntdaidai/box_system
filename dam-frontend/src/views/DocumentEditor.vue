<template>
  <div class="document-editor-page">
    <div class="page-header">
      <div class="header-left">
        <el-button class="back-button" @click="goBack" :icon="ArrowLeft">返回</el-button>
        <div class="title-stack">
          <span class="page-kicker">文档编辑</span>
          <h2 class="page-title" :title="documentInfo.title">
            {{ documentInfo.title || '未命名文档' }}
          </h2>
        </div>
      </div>
      <div class="header-right">
        <span class="save-state" :class="saveStateClass">{{ saveStateLabel }}</span>
        <el-button type="primary" @click="handleSave" :loading="saving">
          <el-icon><Check /></el-icon>
          保存到文档库
        </el-button>
        <el-button @click="handleReload">
          <el-icon><Refresh /></el-icon>
          重新加载
        </el-button>
      </div>
    </div>

    <div class="document-meta-bar">
      <span class="meta-pill">
        <span>类型</span>
        <strong>{{ getFileTypeLabel(documentInfo.file_type) }}</strong>
      </span>
      <span class="meta-pill">
        <span>大小</span>
        <strong>{{ formatFileSize(documentInfo.file_size) }}</strong>
      </span>
      <span class="meta-pill">
        <span>最后修改</span>
        <strong>{{ formatDateTime(documentInfo.updated_at) }}</strong>
      </span>
      <span v-if="lastSavedAt" class="meta-pill">
        <span>本次保存</span>
        <strong>{{ lastSavedAt }}</strong>
      </span>
    </div>

    <div class="editor-container">
      <OnlyOfficeEditor
        ref="editorRef"
        :document-url="documentUrl"
        :document-title="documentInfo.title"
        :document-type="documentType"
        :config="editorConfig"
        :mode="editorMode"
        editor-height="100%"
        :user="currentUser"
        :callback-url="callbackUrl"
        @ready="onEditorReady"
        @document-state-change="onDocumentStateChange"
        @error="onEditorError"
      />
    </div>

    <!-- 协同编辑用户列表（可选） -->
    <div v-if="collaborators.length > 0" class="collaborators-bar">
      <span class="collaborators-label">协同编辑中：</span>
      <el-tag
        v-for="user in collaborators"
        :key="user.id"
        :type="user.id === currentUser.id ? 'primary' : 'info'"
        class="collaborator-tag"
      >
        {{ user.name }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Check, Refresh } from '@element-plus/icons-vue'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

// 编辑器引用
const editorRef = ref(null)

// 状态
const saving = ref(false)
const documentUrl = ref('')
const documentType = ref('word')
const editorConfig = ref(null)
const editorMode = ref('edit')
const collaborators = ref([])
const isDocumentModified = ref(false)
const editorReady = ref(false)
const lastSavedAt = ref('')

// 文档信息
const documentInfo = ref({
  document_id: '',
  title: '',
  file_type: '',
  file_size: 0,
  updated_at: ''
})

// 当前用户信息（实际应该从登录状态获取）
const currentUser = ref({
  id: 'user_001',
  name: '管理员'
})

// 回调 URL 由后端完整 OnlyOffice config 提供，这里仅保留兼容兜底。
const callbackUrl = computed(() => editorConfig.value?.editorConfig?.callbackUrl || '')

const saveStateLabel = computed(() => {
  if (saving.value) return '正在保存'
  if (!editorReady.value) return '编辑器加载中'
  if (isDocumentModified.value) return '有未保存修改'
  return '已同步'
})

const saveStateClass = computed(() => {
  if (saving.value) return 'is-saving'
  if (!editorReady.value) return 'is-loading'
  if (isDocumentModified.value) return 'is-dirty'
  return 'is-saved'
})

// 获取文档类型显示名称
const getFileTypeLabel = (type) => {
  const ext = String(type || '').toLowerCase()
  const labelMap = {
    'docx': 'Word 文档',
    'doc': 'Word 文档',
    'xlsx': 'Excel 表格',
    'xls': 'Excel 表格',
    'pptx': 'PPT 演示',
    'ppt': 'PPT 演示',
    'pdf': 'PDF 文档'
  }
  return labelMap[ext] || ext.toUpperCase() || '-'
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

const formatDateTime = (value) => {
  if (!value) return '-'
  const raw = String(value).replace('T', ' ')
  const [date = '-', time = ''] = raw.split(' ')
  return time ? `${date} ${time.slice(0, 5)}` : date
}

const formatNowTime = () => {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

// 加载文档信息
const loadDocumentInfo = async () => {
  try {
    const documentId = route.params.documentId || route.query.documentId

    if (!documentId) {
      ElMessage.error('缺少文档 ID')
      router.back()
      return
    }

    // 获取编辑器配置
    const response = await axios.get(`/api/onlyoffice/editor-config/${documentId}`, {
      params: {
        user_id: currentUser.value.id,
        user_name: currentUser.value.name,
        mode: editorMode.value
      }
    })

    if (response.data.success) {
      const data = response.data.data

      // 设置文档信息
      documentInfo.value = {
        document_id: documentId,
        title: data.document.title,
        file_type: data.document.fileType,
        file_size: data.file_size || 0,
        updated_at: data.updated_at || ''
      }

      editorConfig.value = data

      // 设置文档 URL
      documentUrl.value = data.document.url

      // 设置文档类型
      documentType.value = data.documentType
    } else {
      ElMessage.error('获取文档信息失败')
      router.back()
    }

  } catch (error) {
    console.error('加载文档信息失败:', error)
    ElMessage.error('加载文档信息失败')
    router.back()
  }
}

// 编辑器准备就绪
const onEditorReady = () => {
  console.log('OnlyOffice 编辑器已准备就绪')
  editorReady.value = true
}

// 文档状态变化
const onDocumentStateChange = (event) => {
  console.log('文档状态变化:', event)
  isDocumentModified.value = Boolean(event?.data)
}

// 编辑器错误
const onEditorError = (error) => {
  console.error('编辑器错误:', error)
  ElMessage.error(error)
}

// 保存文档
const handleSave = async () => {
  try {
    if (!documentInfo.value.document_id) {
      ElMessage.warning('文档信息还未加载完成')
      return
    }

    if (!isDocumentModified.value) {
      lastSavedAt.value = formatNowTime()
      ElMessage.success('当前没有新的修改')
      return
    }

    saving.value = true

    const response = await axios.post(`/api/onlyoffice/force-save/${documentInfo.value.document_id}`, {
      user_id: currentUser.value.id
    })

    if (response.data?.already_saved) {
      ElMessage.success('文档已是最新')
    } else {
      ElMessage.success('保存请求已提交')
    }
    lastSavedAt.value = formatNowTime()
    isDocumentModified.value = false

  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// 刷新文档
const handleReload = async () => {
  try {
    if (isDocumentModified.value) {
      await ElMessageBox.confirm(
        '重新加载会丢弃当前未保存的修改。是否继续？',
        '确认重新加载',
        {
          confirmButtonText: '重新加载',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
    }

    if (editorRef.value) {
      editorRef.value.reload()
      isDocumentModified.value = false
      editorReady.value = false
    }

  } catch {
    // 用户取消
  }
}

// 返回上一页
const goBack = () => {
  if (isDocumentModified.value) {
    ElMessageBox.confirm(
      '文档尚未保存，是否确定离开？',
      '确认离开',
      {
        confirmButtonText: '确定离开',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      router.back()
    }).catch(() => {
      // 用户取消
    })
  } else {
    router.back()
  }
}

// 页面加载时获取文档信息
onMounted(() => {
  loadDocumentInfo()
})

// 页面卸载前清理
onBeforeUnmount(() => {
  // 清理编辑器
  if (editorRef.value) {
    editorRef.value.destroy()
  }
})
</script>

<style scoped>
.document-editor-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 92px);
  min-height: 640px;
  padding: 12px 20px 16px;
  background: transparent;
  overflow: hidden;
}

.page-header {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: inset 0 0 18px rgba(0, 200, 255, 0.025);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.back-button {
  flex: 0 0 auto;
}

.title-stack {
  min-width: 0;
}

.page-kicker {
  display: block;
  margin-bottom: 3px;
  font-size: 12px;
  color: var(--text-muted);
}

.page-title {
  margin: 0;
  max-width: min(46vw, 720px);
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
}

.save-state {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 10px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
  font-size: 13px;
  color: var(--text-secondary);
  background: rgba(10, 30, 48, 0.65);
}

.save-state.is-dirty {
  color: #ffe5a3;
  border-color: rgba(230, 162, 60, 0.45);
}

.save-state.is-saved {
  color: #9df0bd;
  border-color: rgba(103, 194, 58, 0.42);
}

.save-state.is-saving,
.save-state.is-loading {
  color: var(--accent-color);
}

.document-meta-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: rgba(16, 38, 72, 0.42);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow-x: auto;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 10px;
  white-space: nowrap;
  border-radius: 4px;
  background: rgba(10, 30, 48, 0.58);
  border: 1px solid rgba(0, 200, 255, 0.12);
}

.meta-pill span {
  font-size: 12px;
  color: var(--text-muted);
}

.meta-pill strong {
  font-size: 13px;
  color: var(--text-secondary);
}

.editor-container {
  flex: 1 1 auto;
  min-height: 0;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}

.editor-container :deep(.onlyoffice-editor),
.editor-container :deep(#onlyoffice-editor),
.editor-container :deep(iframe) {
  height: 100% !important;
}

.editor-container :deep(.onlyoffice-editor) {
  border: 0;
  border-radius: 0;
}

.collaborators-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 -2px 12px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 100;
}

.collaborators-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.collaborator-tag {
  margin-right: 8px;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .document-editor-page {
    height: calc(100vh - 72px);
    min-height: 0;
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .header-left,
  .header-right {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .page-title {
    max-width: 100%;
  }

  .save-state {
    width: 100%;
    justify-content: center;
  }
}
</style>
