<template>
  <div class="machine-dog-page">
    <section class="developing-panel">
      <div class="icon-wrap">
        <el-icon :size="42"><Setting /></el-icon>
      </div>
      <p>系统管理 / 联动系统</p>
      <h2>机器狗设备</h2>
      <span>正在开发中</span>
    </section>
  </div>
</template>

<script setup>
import { Setting } from '@element-plus/icons-vue'
</script>

<style scoped>
.machine-dog-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}

.developing-panel {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  border: 1px solid rgba(96, 151, 191, .24);
  border-radius: 8px;
  background: #0b1d30;
  text-align: center;
}

.icon-wrap {
  width: 74px;
  height: 74px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #19d9ff;
  background: rgba(25, 217, 255, .1);
  border: 1px solid rgba(25, 217, 255, .24);
}

.developing-panel p {
  margin: 8px 0 0;
  color: #79acd0;
  font-size: 13px;
}

.developing-panel h2 {
  margin: 0;
  color: #f3f8fd;
  font-size: 25px;
  letter-spacing: 0;
}

.developing-panel span {
  color: #8fa8bf;
  font-size: 15px;
}
</style>
