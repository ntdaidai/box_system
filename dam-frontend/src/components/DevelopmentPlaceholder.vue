<template>
  <section class="development-page" role="status" :aria-label="`${pageTitle}正在开发`">
    <div class="development-card">
      <div class="visual" aria-hidden="true">
        <span class="orbit orbit-outer"></span>
        <span class="orbit orbit-inner"></span>
        <span class="visual-glow"></span>
        <el-icon class="tool-icon"><Tools /></el-icon>
      </div>

      <span class="status-badge">
        <i aria-hidden="true"></i>
        开发中
      </span>
      <h1>{{ pageTitle }}功能正在开发</h1>
      <p>该功能正在规划与完善中，敬请期待。</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Tools } from '@element-plus/icons-vue'

const route = useRoute()
const pageTitle = computed(() => route.meta.title || '当前')
</script>

<style scoped>
.development-page {
  display: grid;
  min-height: 100%;
  padding: 20px;
  place-items: center;
  color: #e7f3ff;
  background:
    radial-gradient(circle at 50% 42%, rgba(0, 200, 255, 0.1), transparent 32%),
    #071422;
}

.development-card {
  width: min(100%, 620px);
  padding: 56px 32px 60px;
  text-align: center;
  background: linear-gradient(145deg, rgba(13, 37, 61, 0.9), rgba(7, 24, 41, 0.82));
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 12px;
  box-shadow: 0 24px 64px rgba(0, 7, 14, 0.28);
}

.visual {
  position: relative;
  display: grid;
  width: 132px;
  height: 132px;
  margin: 0 auto 28px;
  place-items: center;
}

.orbit,
.visual-glow {
  position: absolute;
  border-radius: 50%;
}

.orbit-outer {
  inset: 0;
  border: 1px solid rgba(87, 214, 255, 0.22);
}

.orbit-outer::before,
.orbit-inner::before {
  position: absolute;
  width: 8px;
  height: 8px;
  content: '';
  background: #52dbff;
  border-radius: 50%;
  box-shadow: 0 0 14px rgba(82, 219, 255, 0.9);
}

.orbit-outer::before {
  top: 11px;
  right: 22px;
}

.orbit-inner {
  inset: 17px;
  border: 1px dashed rgba(81, 230, 190, 0.34);
  animation: rotate 12s linear infinite;
}

.orbit-inner::before {
  bottom: 1px;
  left: 19px;
  width: 6px;
  height: 6px;
  background: #51e6be;
  box-shadow: 0 0 12px rgba(81, 230, 190, 0.85);
}

.visual-glow {
  inset: 34px;
  background: rgba(0, 200, 255, 0.1);
  box-shadow: 0 0 38px rgba(0, 200, 255, 0.18);
}

.tool-icon {
  z-index: 1;
  color: #7de7ff;
  font-size: 40px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  gap: 8px;
  color: #77e7cb;
  background: rgba(81, 230, 190, 0.08);
  border: 1px solid rgba(81, 230, 190, 0.24);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.status-badge i {
  width: 7px;
  height: 7px;
  background: #51e6be;
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(81, 230, 190, 0.8);
}

h1 {
  margin: 18px 0 10px;
  color: #f3f8fd;
  font-size: clamp(24px, 3vw, 30px);
  line-height: 1.35;
}

p {
  margin: 0;
  color: #8faac1;
  font-size: 15px;
  line-height: 1.7;
}

@keyframes rotate {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .development-page { padding: 12px; }
  .development-card { padding: 42px 20px 46px; }
  .visual { transform: scale(0.88); }
}

@media (prefers-reduced-motion: reduce) {
  .orbit-inner { animation: none; }
}
</style>
