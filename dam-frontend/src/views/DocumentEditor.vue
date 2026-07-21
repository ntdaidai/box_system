<template>
  <div class="document-editor-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
        <h2 class="page-title">文档编辑</h2>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleSave" :loading="saving">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
        <el-button @click="handleReload">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 文档信息栏 -->
    <div class="document-info">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="文档名称">
          {{ documentInfo.title || '未命名文档' }}
        </el-descriptions-item>
        <el-descriptions-item label="文档类型">
          <el-tag :type="getFileTypeTag(documentInfo.file_type)">
            {{ getFileTypeLabel(documentInfo.file_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="文件大小">
          {{ formatFileSize(documentInfo.file_size) }}
        </el-descriptions-item>
        <el-descriptions-item label="最后修改">
          {{ documentInfo.updated_at || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 编辑器组件 -->
    <div class="editor-container">
      <OnlyOfficeEditor
        ref="editorRef"
        :document-url="documentUrl"
        :document-title="documentInfo.title"
        :document-type="documentType"
        :mode="editorMode"
        editor-height="calc(100vh - 280px)"
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
const editorMode = ref('edit')
const collaborators = ref([])
const isDocumentModified = ref(false)

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

// 回调 URL
const callbackUrl = computed(() => {
  return `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8090'}/api/onlyoffice/callback`
})

// 获取文档类型标签
const getFileTypeTag = (type) => {
  const tagMap = {
    'docx': 'primary',
    'doc': 'primary',
    'xlsx': 'success',
    'xls': 'success',
    'pptx': 'warning',
    'ppt': 'warning',
    'pdf': 'info'
  }
  return tagMap[type] || 'info'
}

// 获取文档类型显示名称
const getFileTypeLabel = (type) => {
  const labelMap = {
    'docx': 'Word 文档',
    'doc': 'Word 文档',
    'xlsx': 'Excel 表格',
    'xls': 'Excel 表格',
    'pptx': 'PPT 演示',
    'ppt': 'PPT 演示',
    'pdf': 'PDF 文档'
  }
  return labelMap[type] || type.toUpperCase()
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
        file_size: 0, // 需要额外接口获取
        updated_at: ''
      }

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
}

// 文档状态变化
const onDocumentStateChange = (event) => {
  console.log('文档状态变化:', event)
  isDocumentModified.value = true
}

// 编辑器错误
const onEditorError = (error) => {
  console.error('编辑器错误:', error)
  ElMessage.error(error)
}

// 保存文档
const handleSave = async () => {
  try {
    saving.value = true

    if (editorRef.value) {
      editorRef.value.save()
      ElMessage.success('保存成功')
      isDocumentModified.value = false
    }

  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// 刷新文档
const handleReload = async () => {
  try {
    await ElMessageBox.confirm(
      '刷新将重新加载文档，未保存的修改将丢失。是否继续？',
      '确认刷新',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    if (editorRef.value) {
      editorRef.value.reload()
      isDocumentModified.value = false
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
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  gap: 12px;
}

.document-info {
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.editor-container {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.collaborators-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: #fff;
  box-shadow: 0 -2px 12px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 100;
}

.collaborators-label {
  font-size: 14px;
  color: #606266;
}

.collaborator-tag {
  margin-right: 8px;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .document-editor-page {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
  }

  .header-left,
  .header-right {
    width: 100%;
    justify-content: center;
  }
}
</style>
