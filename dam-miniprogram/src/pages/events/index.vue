<template>
  <view class="page events-page">
    <view class="tabs">
      <view
        class="tab"
        :class="{ active: activeTab === 'ongoing' }"
        @tap="switchTab('ongoing')"
      >
        进行中
      </view>
      <view
        class="tab"
        :class="{ active: activeTab === 'resolved' }"
        @tap="switchTab('resolved')"
      >
        已完成
      </view>
    </view>

    <view v-if="activeTab === 'ongoing' && !loading" class="priority-strip">
      <view>
        <text>高风险</text>
        <text>{{ highCount }}</text>
      </view>
      <view>
        <text>人工处理中</text>
        <text>{{ manualCount }}</text>
      </view>
    </view>

    <view v-if="activeTab === 'ongoing'" class="notify-panel">
      <view>
        <text>服务通知</text>
        <text>订阅后，有低/中/高风险时会收到微信提醒</text>
      </view>
      <button
        class="ghost-btn notify-btn"
        :loading="subscribingAlerts"
        :disabled="subscribingAlerts"
        @tap="handleSubscribeRiskAlerts"
      >
        订阅提醒
      </button>
    </view>

    <view class="section-head">
      <text>风险事件</text>
      <text>{{ events.length }} 条</text>
    </view>

    <view v-if="loading" class="empty compact">加载中...</view>
    <view v-else-if="loadError" class="error-panel">
      <view>事件加载失败</view>
      <text>{{ loadError }}</text>
      <text>{{ apiBaseText }}</text>
      <button class="ghost-btn retry-btn" @tap="loadHome">重新加载</button>
    </view>
    <view v-else-if="events.length === 0" class="empty compact">
      {{ activeTab === 'ongoing' ? '暂无进行中事件' : '暂无已完成事件' }}
    </view>

    <view v-else class="event-list">
      <view
        v-for="item in events"
        :key="item.event_id"
        class="event-card"
        @tap="openDetail(item.event_id)"
      >
        <view class="card-top">
          <view class="risk-pill" :class="item.riskClass">{{ item.risk_level_label }}</view>
          <view class="status-text">{{ item.mini_status_label }}</view>
        </view>
        <view class="event-type">{{ item.event_type }}</view>
        <view v-if="item.risk_level === 'HIGH' && item.can_start_manual" class="urgent-line">
          需要尽快现场处理
        </view>
        <button
          v-if="item.risk_level === 'HIGH' && item.can_start_manual && item.latitude && item.longitude"
          class="ghost-btn card-nav-btn"
          @tap.stop="openMapNavigation(item)"
        >
          导航到点位
        </button>
        <view class="meta-line">
          <text>监控点</text>
          <text>{{ item.monitor_point }}</text>
        </view>
        <view class="meta-line">
          <text>持续时间</text>
          <text>{{ item.durationText }}</text>
        </view>
        <view class="action-text">{{ item.system_action_text }}</view>
      </view>
    </view>

    <view class="video-panel">
      <view class="section-head inner">
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
          <text>暂无可选摄像头</text>
        </view>
      </view>

      <view v-if="liveExpanded" class="video-box">
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
          :class="{ single: !liveExpanded }"
          :disabled="!selectedCamera.camera_id"
          @tap="toggleLiveVideo"
        >
          {{ liveExpanded ? '收起视频' : '进入实时视频' }}
        </button>
        <button
          v-if="liveExpanded"
          class="ghost-btn action-btn"
          :loading="videoLoading"
          :disabled="videoLoading"
          @tap="refreshCameraSnapshot(true)"
        >
          刷新画面
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

    <view class="profile-panel">
      <view class="profile-top">
        <view class="avatar">巡</view>
        <view class="profile-main">
          <view>微信小程序工作人员</view>
          <text>大藤峡安全巡查</text>
        </view>
      </view>
      <view class="section-head inner profile-title">
        <text>我的处理</text>
        <text>{{ handledEvents.length }} 条</text>
      </view>
      <view v-if="handledEvents.length === 0" class="handled-empty">暂无人工处理记录</view>
      <view v-else class="handled-list">
        <view
          v-for="item in handledEvents"
          :key="item.event_id"
          class="handled-item"
          @tap="openDetail(item.event_id)"
        >
          <view>
            <text>{{ item.event_type }}</text>
            <text>{{ item.monitor_point }}</text>
          </view>
          <text>{{ item.mini_status_label }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { absoluteUrl, request } from '../../utils/request'
import { API_BASE_URL } from '../../utils/config'
import { formatDuration, riskClass } from '../../utils/format'
import { subscribeRiskAlert } from '../../utils/subscribe'
import { readCache, writeCache } from '../../utils/cache'

export default {
  data() {
    return {
      activeTab: 'ongoing',
      events: [],
      handledEvents: [],
      cameras: [],
      selectedCameraIndex: 0,
      highCount: 0,
      manualCount: 0,
      loading: false,
      loadError: '',
      videoLoading: false,
      liveExpanded: false,
      snapshotUrl: '',
      videoText: '选择点位后进入实时视频',
      cameraBroadcasting: false,
      subscribingAlerts: false,
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
    },

    apiBaseText() {
      return `接口地址：${API_BASE_URL}`
    }
  },

  onLoad() {
    this.restoreCachedHome()
    this.loadHome()
  },

  onShow() {
    this.loadEvents()
    this.loadHandledEvents()
  },

  onHide() {
    this.stopLiveRefresh()
  },

  onUnload() {
    this.stopLiveRefresh()
  },

  onPullDownRefresh() {
    this.loadHome().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedHome() {
      const cachedEvents = readCache(`events:${this.activeTab}`, [])
      const cachedHandled = readCache('handled-events', [])
      const cachedCameras = readCache('cameras', [])
      if (cachedEvents.length) {
        this.events = cachedEvents
        this.highCount = cachedEvents.filter((item) => item.risk_level === 'HIGH' && item.mini_status !== 'RESOLVED').length
        this.manualCount = cachedEvents.filter((item) => item.mini_status === 'MANUAL_PROCESSING').length
      }
      if (cachedHandled.length) this.handledEvents = cachedHandled
      if (cachedCameras.length) this.cameras = cachedCameras
    },

    loadHome() {
      return Promise.all([
        this.loadEvents(),
        this.loadCameras(),
        this.loadHandledEvents()
      ])
    },

    switchTab(tab) {
      if (tab === this.activeTab) return
      this.activeTab = tab
      this.events = []
      this.loadEvents()
    },

    loadEvents() {
      this.loading = true
      this.loadError = ''
      return request({
        url: `/events?status=${this.activeTab}&page_size=50`
      })
        .then((data) => {
          const events = (data.items || []).map(this.decorateEvent)
          this.events = events
          writeCache(`events:${this.activeTab}`, events)
          this.highCount = events.filter((item) => item.risk_level === 'HIGH' && item.mini_status !== 'RESOLVED').length
          this.manualCount = events.filter((item) => item.mini_status === 'MANUAL_PROCESSING').length
        })
        .catch((error) => {
          const cached = readCache(`events:${this.activeTab}`, [])
          if (cached.length) {
            this.events = cached
          }
          this.loadError = error.message || '网络错误'
          uni.showToast({ title: error.message, icon: 'none' })
        })
        .finally(() => {
          this.loading = false
        })
    },

    loadHandledEvents() {
      return request({
        url: '/events?status=all&page_size=80'
      })
        .then((data) => {
          this.handledEvents = (data.items || [])
            .filter((item) => item.mini_status === 'MANUAL_PROCESSING' || item.mini_status === 'RESOLVED' || item.ack_operator || item.resolved_operator)
            .map(this.decorateEvent)
            .slice(0, 6)
          writeCache('handled-events', this.handledEvents)
        })
        .catch(() => {
          this.handledEvents = readCache('handled-events', [])
        })
    },

    loadCameras() {
      return request({ url: '/cameras' })
        .then((data) => {
          this.cameras = data.items || []
          writeCache('cameras', this.cameras)
          if (this.selectedCameraIndex >= this.cameras.length) {
            this.selectedCameraIndex = 0
          }
          if (this.liveExpanded) {
            this.refreshCameraSnapshot(false)
          }
        })
        .catch((error) => {
          this.cameras = readCache('cameras', [])
          this.snapshotUrl = ''
          this.videoText = error.message
        })
    },

    decorateEvent(item) {
      return {
        ...item,
        riskClass: riskClass(item.risk_level),
        durationText: formatDuration(item.duration_seconds)
      }
    },

    selectCamera(event) {
      this.selectedCameraIndex = Number(event.detail.value || 0)
      this.snapshotUrl = ''
      this.videoText = '正在切换点位'
      if (this.liveExpanded) {
        this.refreshCameraSnapshot(true)
        this.startLiveRefresh()
      }
    },

    toggleLiveVideo() {
      if (!this.selectedCamera.camera_id) return
      this.liveExpanded = !this.liveExpanded
      if (this.liveExpanded) {
        this.refreshCameraSnapshot(true)
        this.startLiveRefresh()
        return
      }
      this.stopLiveRefresh()
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
      }, 3500)
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

    handleSubscribeRiskAlerts() {
      if (this.subscribingAlerts) return
      this.subscribingAlerts = true
      subscribeRiskAlert()
        .then((data) => {
          const quota = Number(data.remaining_quota || 1)
          uni.showToast({
            title: `已订阅${quota > 1 ? quota + '次' : ''}`,
            icon: 'success'
          })
        })
        .catch((error) => {
          uni.showToast({ title: error.message || '订阅失败', icon: 'none' })
        })
        .finally(() => {
          this.subscribingAlerts = false
        })
    },

    openMapNavigation(item) {
      uni.navigateTo({
        url: `/pages/map/index?camera_id=${encodeURIComponent(item.camera_id || '')}&event_id=${encodeURIComponent(item.event_id || '')}`
      })
    },

    openDetail(eventId) {
      uni.navigateTo({
        url: `/pages/detail/index?event_id=${encodeURIComponent(eventId)}`
      })
    }
  }
}
</script>

<style>
.events-page {
  padding-top: 20rpx;
  padding-bottom: 48rpx;
}

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.tab {
  height: 76rpx;
  line-height: 76rpx;
  text-align: center;
  border-radius: 8rpx;
  background: #e7eff1;
  color: #53666d;
  font-weight: 600;
}

.tab.active {
  background: #0f4c5c;
  color: #fff;
}

.priority-strip {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.priority-strip view {
  min-height: 88rpx;
  padding: 14rpx 18rpx;
  box-sizing: border-box;
  border-radius: 8rpx;
  background: #fff;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
}

.priority-strip text {
  display: block;
}

.priority-strip text:first-child {
  color: #6c7a80;
  font-size: 24rpx;
}

.priority-strip text:last-child {
  color: #172026;
  font-size: 36rpx;
  font-weight: 800;
}

.notify-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 20rpx;
  border-radius: 8rpx;
  background: #fff;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
}

.notify-panel view {
  flex: 1;
  min-width: 0;
}

.notify-panel text {
  display: block;
}

.notify-panel text:first-child {
  color: #172026;
  font-weight: 800;
  margin-bottom: 6rpx;
}

.notify-panel text:last-child {
  color: #6c7a80;
  font-size: 24rpx;
  line-height: 34rpx;
}

.notify-btn {
  width: 168rpx;
  height: 64rpx;
  line-height: 64rpx;
  padding: 0;
  font-size: 24rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 12rpx 4rpx 14rpx;
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

.section-head.inner {
  margin: 0 0 18rpx;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.event-card,
.video-panel,
.profile-panel {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.event-card {
  margin-bottom: 0;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 18rpx;
}

.risk-pill {
  min-width: 96rpx;
  height: 52rpx;
  line-height: 52rpx;
  text-align: center;
  border-radius: 8rpx;
  font-weight: 700;
}

.status-text {
  color: #263940;
  font-size: 26rpx;
  text-align: right;
}

.event-type {
  font-size: 34rpx;
  font-weight: 700;
  margin-bottom: 16rpx;
}

.urgent-line {
  margin-bottom: 14rpx;
  padding: 12rpx 14rpx;
  border-radius: 8rpx;
  background: #fff0f0;
  color: #b42323;
  font-weight: 700;
}

.card-nav-btn {
  height: 64rpx;
  line-height: 64rpx;
  margin: 0 0 14rpx;
  font-size: 24rpx;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  gap: 24rpx;
  color: #52656c;
  line-height: 44rpx;
}

.meta-line text:last-child {
  color: #172026;
  text-align: right;
}

.action-text {
  margin-top: 16rpx;
  padding: 16rpx;
  border-radius: 8rpx;
  background: #f2f6f7;
  color: #24474f;
  line-height: 40rpx;
}

.empty {
  color: #7b8b91;
  text-align: center;
}

.empty.compact {
  padding: 54rpx 20rpx 42rpx;
}

.error-panel {
  padding: 24rpx;
  border-radius: 8rpx;
  background: #fff5f5;
  color: #9f1d1d;
  margin-bottom: 18rpx;
}

.error-panel view {
  font-size: 30rpx;
  font-weight: 800;
  margin-bottom: 10rpx;
}

.error-panel text {
  display: block;
  color: #7f2a2a;
  font-size: 24rpx;
  line-height: 38rpx;
  word-break: break-all;
}

.retry-btn {
  height: 68rpx;
  line-height: 68rpx;
  margin-top: 16rpx;
  font-size: 26rpx;
}

.video-panel {
  margin-top: 22rpx;
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
}

.video-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-top: 18rpx;
}

.action-btn.single {
  grid-column: 1 / 3;
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

.profile-panel {
  margin-top: 22rpx;
}

.profile-top {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-bottom: 18rpx;
}

.avatar {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  background: #0f4c5c;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34rpx;
  font-weight: 800;
}

.profile-main {
  min-width: 0;
}

.profile-main view {
  color: #172026;
  font-size: 32rpx;
  font-weight: 800;
  margin-bottom: 6rpx;
}

.profile-main text {
  color: #6c7a80;
  font-size: 24rpx;
}

.profile-title {
  padding-top: 14rpx;
  border-top: 1rpx solid #e5eef0;
}

.handled-empty {
  padding: 28rpx 0 6rpx;
  color: #7b8b91;
  text-align: center;
}

.handled-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.handled-item {
  min-height: 76rpx;
  padding: 14rpx 0;
  border-bottom: 1rpx solid #edf3f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.handled-item:last-child {
  border-bottom: 0;
}

.handled-item view {
  min-width: 0;
}

.handled-item view text {
  display: block;
}

.handled-item view text:first-child {
  color: #172026;
  font-weight: 700;
  margin-bottom: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.handled-item view text:last-child {
  color: #6c7a80;
  font-size: 23rpx;
}

.handled-item > text {
  color: #0f6b7a;
  font-size: 24rpx;
  flex-shrink: 0;
}
</style>
