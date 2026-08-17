<template>
  <div class="workspace-page">
    <!-- 内容区：渲染当前子模块，切换由侧边栏菜单驱动 -->
    <router-view />
  </div>
</template>

<style scoped>
.workspace-page {
  height: 100%;
  background: #071422;
}
</style>
