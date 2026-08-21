<script>
import { isLoggedIn, scanQrLogin } from './utils/auth'
import { prepareDemoVideo } from './utils/demo-video'

export default {
  onLaunch(options) {
    prepareDemoVideo().catch((error) => {
      console.error('[demo-video] launch prepare failed', error)
    })
    const eventId = options?.query?.event_id
    if (!isLoggedIn()) {
      this.promptScanLogin()
    }
    if (eventId) {
      uni.navigateTo({
        url: `/pages/detail/index?event_id=${encodeURIComponent(eventId)}`
      })
    }
  },
  methods: {
    promptScanLogin() {
      uni.showModal({
        title: '请扫码登录',
        content: '使用前请扫描管理员提供的登录码完成身份认证',
        confirmText: '去扫码',
        cancelText: '暂不',
        success: (res) => {
          if (res.confirm) {
            scanQrLogin()
              .then(() => {
                uni.showToast({ title: '登录成功', icon: 'success' })
              })
              .catch((err) => {
                uni.showToast({ title: err.message || '扫码失败', icon: 'none' })
              })
          }
        }
      })
    }
  }
}
</script>

<style>
page {
  min-height: 100%;
  background: #f4f7f8;
  color: #172026;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  font-size: 28rpx;
}

button {
  border-radius: 8rpx;
  font-weight: 600;
}

button::after {
  border: 0;
}

.page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 24rpx;
}

.risk-low {
  background: #fff4c2;
  color: #7a5a00;
}

.risk-medium {
  background: #ffe1bf;
  color: #9a4d00;
}

.risk-high {
  background: #ffd4d4;
  color: #9f1d1d;
}

.primary-btn {
  background: #0f6b7a;
  color: #fff;
}

.danger-btn {
  background: #d63d3d;
  color: #fff;
}

.ghost-btn {
  background: #e7eff1;
  color: #0f4c5c;
}
</style>
