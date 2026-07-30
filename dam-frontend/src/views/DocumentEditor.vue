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
        @document-state-change="onDocumentStateChange"
        @error="onEditorError"
      />
    </div>

    <div v-if="closingAndSaving" class="saving-overlay">
      <div class="saving-panel">
        <div class="saving-spinner"></div>
        <div class="saving-title">正在退出并保存文档</div>
        <div class="saving-text">OnlyOffice 正在生成最终文件，请稍候...</div>
      </div>
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
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import OnlyOfficeEditor from '@/components/OnlyOfficeEditor.vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

// 编辑器引用
const editorRef = ref(null)

// 状态
const documentUrl = ref('')
const documentType = ref('word')
const editorConfig = ref(null)
const editorMode = ref('edit')
const collaborators = ref([])
const returning = ref(false)
const hasDocumentChanges = ref(false)
const closingAndSaving = ref(false)

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

// 编辑器错误
const onEditorError = (error) => {
  console.error('编辑器错误:', error)
  ElMessage.error(error)
}

// 这里只记录是否编辑过，用于返回时展示保存中状态，不做自动保存。
const onDocumentStateChange = (event) => {
  if (event?.data) {
    hasDocumentChanges.value = true
  }
}

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

const fetchLatestUpdatedAt = async () => {
  if (!documentInfo.value.document_id) return ''
  const response = await axios.get(`/api/onlyoffice/editor-config/${documentInfo.value.document_id}`, {
    params: {
      user_id: currentUser.value.id,
      user_name: currentUser.value.name,
      mode: editorMode.value
    }
  })
  return response.data?.success ? response.data.data?.updated_at || '' : ''
}

const waitForSaveCallback = async (previousUpdatedAt) => {
  for (let index = 0; index < 18; index += 1) {
    await sleep(1000)
    const latestUpdatedAt = await fetchLatestUpdatedAt()
    if (latestUpdatedAt && latestUpdatedAt !== previousUpdatedAt) {
      return true
    }
  }
  return false
}

// 返回上一页
const goBack = async () => {
  if (returning.value) return
  returning.value = true
  closingAndSaving.value = hasDocumentChanges.value
  const previousUpdatedAt = documentInfo.value.updated_at

  if (editorRef.value) {
    editorRef.value.destroy()
  }

  if (!hasDocumentChanges.value) {
    router.back()
    return
  }

  const saved = await waitForSaveCallback(previousUpdatedAt)
  closingAndSaving.value = false
  if (saved) {
    ElMessage.success('文档已保存')
  } else {
    ElMessage.warning('已退出编辑，OnlyOffice 仍在后台保存，可稍后刷新列表')
  }
  router.back()
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

.saving-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 16, 29, 0.72);
  backdrop-filter: blur(3px);
}

.saving-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(360px, calc(100vw - 40px));
  padding: 28px 24px;
  color: #dce9fa;
  background: #102640;
  border: 1px solid rgba(74, 155, 230, 0.42);
  border-radius: 8px;
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.34);
}

.saving-spinner {
  width: 34px;
  height: 34px;
  margin-bottom: 18px;
  border: 3px solid rgba(144, 196, 255, 0.28);
  border-top-color: #46a7ff;
  border-radius: 50%;
  animation: saving-rotate 0.9s linear infinite;
}

.saving-title {
  margin-bottom: 8px;
  font-size: 18px;
  font-weight: 700;
}

.saving-text {
  font-size: 14px;
  color: #9eb8d7;
}

@keyframes saving-rotate {
  to {
    transform: rotate(360deg);
  }
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

  .header-left {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .page-title {
    max-width: 100%;
  }
}
</style>
