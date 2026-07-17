<!-- dai -->
<template>
  <main class="login-page">
    <div class="ambient ambient-one"></div>
    <div class="ambient ambient-two"></div>

    <section class="brand-panel">
      <div class="brand-mark">
        <span class="brand-ring"></span>
        <el-icon :size="34"><Monitor /></el-icon>
      </div>
      <p class="eyebrow">DAM INTELLIGENT PERCEPTION</p>
      <h1>库坝应急巡查<br />智能感知系统</h1>
      <p class="brand-copy">
        汇聚实时视频、边缘 AI 与多源传感数据，构建面向现场的智能巡查工作台。
      </p>
      <div class="signal-row">
        <span><i></i> Jetson Edge AI</span>
        <span><i></i> Secure Access</span>
        <span><i></i> Real-time Vision</span>
      </div>
    </section>

    <section class="login-card">
      <div class="card-heading">
        <span class="secure-badge"><el-icon><Lock /></el-icon> 安全认证</span>
        <h2>欢迎回来</h2>
        <p>登录后进入视频监控与智能检测中心</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submitLogin">
        <el-form-item prop="username">
          <el-input v-model.trim="form.username" size="large" placeholder="用户名" autocomplete="username">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
            show-password
            @keyup.enter="submitLogin"
          >
            <template #prefix><el-icon><Key /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button class="login-button" type="primary" native-type="submit" :loading="loading">
          进入系统
          <el-icon class="button-arrow"><Right /></el-icon>
        </el-button>
      </el-form>

      <p class="login-footnote">
        <el-icon><InfoFilled /></el-icon>
        使用系统管理员分配的账号登录
      </p>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { InfoFilled, Key, Lock, Monitor, Right, User } from '@element-plus/icons-vue'
import { login } from '@/api/auth'
import { useUserStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function safeRedirect() {
  const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
  return target.startsWith('/') && !target.startsWith('//') ? target : '/dashboard'
}

async function submitLogin() {
  if (loading.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const response = await login(form.username, form.password)
    userStore.setToken(response.data.token)
    userStore.setUserInfo(response.data.user || {})
    await router.replace(safeRedirect())
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  --cyan: #44d7ff;
  --mint: #61efc2;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(440px, 1.15fr) minmax(380px, 0.85fr);
  align-items: center;
  gap: clamp(40px, 8vw, 130px);
  padding: clamp(40px, 7vw, 110px);
  color: #e9f7ff;
  background:
    linear-gradient(rgba(61, 206, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(61, 206, 255, 0.045) 1px, transparent 1px),
    radial-gradient(circle at 16% 20%, rgba(29, 125, 210, 0.28), transparent 34%),
    linear-gradient(135deg, #061221 0%, #081c31 52%, #071422 100%);
  background-size: 42px 42px, 42px 42px, auto, auto;
}

.ambient { position: absolute; border-radius: 50%; filter: blur(2px); opacity: 0.45; }
.ambient-one { width: 360px; height: 360px; right: 8%; top: -180px; background: rgba(68, 215, 255, 0.18); }
.ambient-two { width: 260px; height: 260px; left: -120px; bottom: -80px; background: rgba(97, 239, 194, 0.12); }

.brand-panel, .login-card { position: relative; z-index: 1; }
.brand-mark {
  width: 72px; height: 72px; position: relative; display: grid; place-items: center;
  color: var(--cyan); border: 1px solid rgba(68, 215, 255, 0.4); border-radius: 20px;
  background: rgba(8, 42, 67, 0.72); box-shadow: 0 0 38px rgba(68, 215, 255, 0.16);
}
.brand-ring { position: absolute; inset: -7px; border: 1px solid rgba(97, 239, 194, 0.14); border-radius: 25px; }
.eyebrow { margin: 34px 0 14px; color: var(--mint); font-size: 12px; letter-spacing: 0.24em; }
.brand-panel h1 { margin: 0; font-size: clamp(42px, 5vw, 72px); line-height: 1.14; letter-spacing: 0.02em; }
.brand-copy { max-width: 610px; margin: 24px 0 30px; color: #96aec2; font-size: 16px; line-height: 1.85; }
.signal-row { display: flex; flex-wrap: wrap; gap: 20px; color: #7997ad; font-size: 12px; }
.signal-row span { display: inline-flex; align-items: center; gap: 8px; }
.signal-row i { width: 6px; height: 6px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 10px var(--mint); }

.login-card {
  width: min(100%, 470px); justify-self: end; padding: 42px;
  border: 1px solid rgba(117, 205, 244, 0.2); border-radius: 24px;
  background: linear-gradient(145deg, rgba(16, 43, 67, 0.92), rgba(8, 27, 46, 0.94));
  box-shadow: 0 28px 80px rgba(0, 5, 16, 0.42), inset 0 1px rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(18px);
}
.secure-badge { display: inline-flex; align-items: center; gap: 6px; color: var(--mint); font-size: 12px; }
.card-heading h2 { margin: 18px 0 8px; font-size: 30px; }
.card-heading p { margin: 0 0 32px; color: #829db2; }
.login-card :deep(.el-input__wrapper) {
  min-height: 50px; border-radius: 12px; background: rgba(5, 20, 34, 0.72);
  box-shadow: 0 0 0 1px rgba(113, 188, 222, 0.18) inset;
}
.login-card :deep(.el-input__inner) { color: #e9f7ff; }
.login-button {
  width: 100%; height: 50px; margin-top: 8px; border: none; border-radius: 12px;
  font-weight: 700; letter-spacing: 0.08em;
  background: linear-gradient(100deg, #168fd2, #23b9cf 60%, #45d8ba);
  box-shadow: 0 12px 30px rgba(30, 178, 211, 0.22);
}
.button-arrow { margin-left: 8px; }
.login-footnote { display: flex; align-items: center; justify-content: center; gap: 6px; margin: 24px 0 0; color: #66849a; font-size: 12px; }

@media (max-width: 920px) {
  .login-page { grid-template-columns: 1fr; padding: 32px 22px; gap: 34px; }
  .brand-panel h1 { font-size: 38px; }
  .brand-copy, .signal-row { display: none; }
  .login-card { justify-self: stretch; width: 100%; padding: 30px 24px; }
}
</style>
