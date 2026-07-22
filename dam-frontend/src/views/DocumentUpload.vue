<template>
  <div class="document-upload-redirect">
    <el-empty description="文档上传已合并到文档列表" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/document/list')
})
</script>

<style scoped>
.document-upload-redirect {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
