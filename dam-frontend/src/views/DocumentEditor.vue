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
        <el-button type="primary" class="save-button" @click="handleSave" :loading="saving">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
      </div>
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
import { ArrowLeft, Check } from '@element-plus/icons-vue'
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
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  min-height: 0;
  padding: 0;
  background: #071625;
  overflow: hidden;
}

.page-header {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 60px;
  padding: 0 18px;
  background: #0b2138;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.back-button {
  flex: 0 0 auto;
  height: 36px;
  color: #dce9fa;
  background: rgba(10, 30, 48, 0.68);
  border-color: rgba(88, 156, 222, 0.42);
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
  max-width: min(52vw, 860px);
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

.save-button {
  min-width: 96px;
  height: 36px;
  font-weight: 700;
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

.editor-container {
  flex: 1 1 auto;
  min-height: 0;
  background: #eef2f6;
  border: 0;
  border-radius: 0;
  box-shadow: none;
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
    height: 100vh;
    padding: 0;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
    min-height: 110px;
    padding: 12px;
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
