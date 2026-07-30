import { createSSRApp } from 'vue'
import App from './App.vue'

export function createApp() {
  const app = createSSRApp(App)
  app.config.globalProperties.$operatorName = '微信小程序工作人员'
  return {
    app
  }
}
