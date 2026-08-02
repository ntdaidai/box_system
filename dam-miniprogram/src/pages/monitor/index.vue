<template>
  <view class="page monitor-page">
    <view class="video-panel">
      <view class="section-head">
        <text>点位实时视频</text>
        <text>{{ selectedCameraStatus }}</text>
      </view>

      <picker
        v-if="cameras.length"
        mode="selector"
        :range="cameraNames"
        :value="selectedCameraIndex"
        @change="selectCamera"
      >
        <view class="camera-selector">
          <view>
            <text>当前点位</text>
            <text>{{ selectedCamera.camera_name }}</text>
          </view>
          <text>切换</text>
        </view>
      </picker>
      <view v-else class="camera-selector disabled">
        <view>
          <text>当前点位</text>
          <text>{{ loadError || '暂无可选摄像头' }}</text>
        </view>
      </view>

      <view class="video-box">
        <image
          v-if="snapshotUrl"
          class="video-frame"
          :src="snapshotUrl"
          mode="aspectFit"
          @error="handleSnapshotError"
        />
        <view v-else class="video-empty">{{ videoText }}</view>
      </view>

      <view class="video-actions">
        <button
          class="ghost-btn action-btn"
          :loading="videoLoading"
          :disabled="videoLoading || !selectedCamera.camera_id"
          @tap="refreshCameraSnapshot(true)"
        >
          刷新画面
        </button>
        <button
          class="ghost-btn action-btn"
          :disabled="!selectedCamera.camera_id"
          @tap="openMapNavigation"
        >
          点位导航
        </button>
      </view>

      <button
        class="primary-btn broadcast-btn"
        :loading="cameraBroadcasting"
        :disabled="cameraBroadcasting || !selectedCamera.camera_id"
        @tap="handleCameraBroadcast"
      >
        一键喊话
      </button>
      <view class="broadcast-note">
        {{ broadcastDeviceText }}
      </view>
    </view>

    <view class="camera-list">
      <view class="section-head list-head">
        <text>摄像头点位</text>
        <text>{{ cameras.length }} 个</text>
      </view>
      <view v-if="loading" class="empty compact">加载中...</view>
      <view v-else-if="cameras.length === 0" class="empty compact">
        {{ loadError || '暂无摄像头点位' }}
      </view>
      <view
        v-for="(item, index) in cameras"
        :key="item.camera_id"
        class="camera-item"
        :class="{ active: index === selectedCameraIndex }"
        @tap="selectCameraByIndex(index)"
      >
        <view>
          <text>{{ item.camera_name || item.camera_id }}</text>
          <text>{{ item.install_address || item.description || '未填写安装地址' }}</text>
        </view>
        <text>{{ item.online ? '在线' : '待连接' }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { absoluteUrl, request } from '../../utils/request'
import { readCache, writeCache } from '../../utils/cache'

export default {
  data() {
    return {
      cameras: [],
      selectedCameraIndex: 0,
      loading: false,
      loadError: '',
      videoLoading: false,
      snapshotUrl: '',
      videoText: '正在加载摄像头',
      cameraBroadcasting: false,
      liveTimer: null
    }
  },

  computed: {
    cameraNames() {
      return this.cameras.map((item) => item.camera_name || item.camera_id)
    },

    selectedCamera() {
      return this.cameras[this.selectedCameraIndex] || {}
    },

    selectedCameraStatus() {
      if (!this.selectedCamera.camera_id) return '未配置'
      return this.selectedCamera.online ? '在线' : '待连接'
    },

    broadcastDeviceText() {
      const count = Number(this.selectedCamera.broadcast_device_count || 0)
      if (count > 0) return `已绑定 ${count} 个喊话设备`
      return '当前点位未检测到绑定喊话设备'
    }
  },

  onLoad() {
    this.restoreCachedCameras()
    this.loadCameras(true)
  },

  onShow() {
    if (this.selectedCamera.camera_id && !this.liveTimer) {
      this.startLiveRefresh()
    }
  },

  onHide() {
    this.stopLiveRefresh()
  },

  onUnload() {
    this.stopLiveRefresh()
  },

  onPullDownRefresh() {
    this.loadCameras(true).finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedCameras() {
      const cached = readCache('cameras', [])
      if (!cached.length) return
      this.cameras = cached
      this.videoText = '正在连接实时画面'
    },

    loadCameras(autoStart = false) {
      this.loading = true
      this.loadError = ''
      return request({ url: '/cameras' })
        .then((data) => {
          this.cameras = data.items || []
          writeCache('cameras', this.cameras)
          if (this.selectedCameraIndex >= this.cameras.length) {
            this.selectedCameraIndex = 0
          }
          if (autoStart) {
            this.openSelectedCamera(false)
          }
        })
        .catch((error) => {
          const cached = readCache('cameras', [])
          this.cameras = cached
          this.loadError = error.message || '摄像头加载失败'
          this.videoText = cached.length ? '正在使用缓存点位连接画面' : this.loadError
          if (cached.length && autoStart) {
            this.openSelectedCamera(false)
          }
        })
        .finally(() => {
          this.loading = false
        })
    },

    selectCamera(event) {
      this.selectCameraByIndex(Number(event.detail.value || 0))
    },

    selectCameraByIndex(index) {
      if (index === this.selectedCameraIndex && this.snapshotUrl) return
      this.selectedCameraIndex = index
      this.snapshotUrl = ''
      this.videoText = '正在切换点位'
      this.openSelectedCamera(true)
    },

    openSelectedCamera(showToast) {
      if (!this.selectedCamera.camera_id) {
        this.stopLiveRefresh()
        this.snapshotUrl = ''
        this.videoText = this.loadError || '暂无可选摄像头'
        return Promise.resolve()
      }
      this.startLiveRefresh()
      return this.refreshCameraSnapshot(showToast)
    },

    refreshCameraSnapshot(showToast = false) {
      const cameraId = this.selectedCamera.camera_id
      if (!cameraId || this.videoLoading) return Promise.resolve()
      this.videoLoading = true
      return request({ url: `/cameras/${encodeURIComponent(cameraId)}/video` })
        .then((data) => {
          this.snapshotUrl = `${absoluteUrl(data.snapshot_url)}?t=${Date.now()}`
          this.videoText = '实时画面已连接'
        })
        .catch((error) => {
          this.snapshotUrl = ''
          this.videoText = error.message || '当前摄像头暂未返回实时画面'
          if (showToast) {
            uni.showToast({ title: this.videoText, icon: 'none' })
          }
        })
        .finally(() => {
          this.videoLoading = false
        })
    },

    handleSnapshotError() {
      this.snapshotUrl = ''
      this.videoText = '当前摄像头暂未返回实时画面'
    },

    startLiveRefresh() {
      this.stopLiveRefresh()
      this.liveTimer = setInterval(() => {
        this.refreshCameraSnapshot(false)
      }, 2500)
    },

    stopLiveRefresh() {
      if (this.liveTimer) {
        clearInterval(this.liveTimer)
        this.liveTimer = null
      }
    },

    handleCameraBroadcast() {
      const cameraId = this.selectedCamera.camera_id
      if (!cameraId || this.cameraBroadcasting) return
      this.cameraBroadcasting = true
      request({
        url: `/cameras/${encodeURIComponent(cameraId)}/broadcast`,
        method: 'POST',
        data: {
          operator: '微信小程序工作人员'
        }
      })
        .then(() => {
          uni.showToast({ title: '喊话已下发', icon: 'success' })
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
        .finally(() => {
          this.cameraBroadcasting = false
        })
    },

    openMapNavigation() {
      const cameraId = this.selectedCamera.camera_id || ''
      uni.navigateTo({
        url: `/pages/map/index?camera_id=${encodeURIComponent(cameraId)}`
      })
    }
  }
}
</script>

<style>
.monitor-page {
  padding-top: 20rpx;
  padding-bottom: 48rpx;
}

.video-panel,
.camera-list {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.camera-list {
  margin-top: 20rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}

.section-head text:first-child {
  color: #172026;
  font-size: 30rpx;
  font-weight: 800;
}

.section-head text:last-child {
  color: #728187;
  font-size: 24rpx;
}

.list-head {
  margin-bottom: 12rpx;
}

.camera-selector {
  min-height: 92rpx;
  padding: 16rpx 18rpx;
  box-sizing: border-box;
  border-radius: 8rpx;
  background: #f2f6f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.camera-selector view {
  min-width: 0;
}

.camera-selector view text {
  display: block;
}

.camera-selector view text:first-child {
  color: #6c7a80;
  font-size: 23rpx;
  margin-bottom: 6rpx;
}

.camera-selector view text:last-child {
  color: #172026;
  font-size: 30rpx;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camera-selector > text {
  color: #0f6b7a;
  font-size: 26rpx;
  font-weight: 700;
  flex-shrink: 0;
}

.camera-selector.disabled > text {
  display: none;
}

.video-box {
  width: 100%;
  aspect-ratio: 16 / 9;
  margin-top: 18rpx;
  border-radius: 8rpx;
  overflow: hidden;
  background: #172026;
}

.video-frame {
  width: 100%;
  height: 100%;
  background: #172026;
}

.video-empty {
  width: 100%;
  height: 100%;
  color: #d8e5e8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  text-align: center;
  padding: 0 24rpx;
  box-sizing: border-box;
}

.video-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-top: 18rpx;
}

.action-btn {
  height: 74rpx;
  line-height: 74rpx;
  font-size: 27rpx;
}

.broadcast-btn {
  height: 84rpx;
  line-height: 84rpx;
  margin-top: 16rpx;
  font-size: 30rpx;
}

.broadcast-note {
  color: #6c7a80;
  font-size: 23rpx;
  line-height: 36rpx;
  margin-top: 10rpx;
}

.camera-item {
  min-height: 86rpx;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #edf3f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.camera-item:last-child {
  border-bottom: 0;
}

.camera-item.active {
  padding-left: 16rpx;
  border-left: 8rpx solid #0f6b7a;
}

.camera-item view {
  min-width: 0;
}

.camera-item view text {
  display: block;
}

.camera-item view text:first-child {
  color: #172026;
  font-weight: 700;
  margin-bottom: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camera-item view text:last-child {
  color: #6c7a80;
  font-size: 23rpx;
  line-height: 34rpx;
}

.camera-item > text {
  color: #0f6b7a;
  font-size: 24rpx;
  flex-shrink: 0;
}

.empty {
  color: #7b8b91;
  text-align: center;
}

.empty.compact {
  padding: 44rpx 20rpx 34rpx;
}
</style>
