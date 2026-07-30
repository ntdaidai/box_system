<template>
  <view class="page detail-page">
    <view v-if="event" class="summary">
      <view class="summary-top">
        <view class="risk-pill" :class="riskClassName">{{ event.risk_level_label }}</view>
        <view class="status-text">{{ event.mini_status_label }}</view>
      </view>
      <view class="event-title">{{ event.event_type }}</view>
      <view class="info-grid">
        <view>
          <text>监控点</text>
          <text>{{ event.monitor_point }}</text>
        </view>
        <view>
          <text>开始时间</text>
          <text>{{ startTime }}</text>
        </view>
        <view>
          <text>持续时间</text>
          <text>{{ durationText }}</text>
        </view>
        <view>
          <text>当前状态</text>
          <text>{{ event.mini_status_label }}</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-title">实时视频</view>
      <view class="video-box">
        <image v-if="snapshotUrl" class="video-frame" :src="snapshotUrl" mode="aspectFit" />
        <view v-else class="video-empty">正在建立视频链路</view>
      </view>
      <view class="video-footer">
        <text>{{ videoText }}</text>
        <button class="mini-btn" @tap="refreshSnapshot">刷新画面</button>
      </view>
    </view>

    <view v-if="event" class="section">
      <view class="section-title">当前系统动作</view>
      <view class="action-panel">{{ event.system_action_text }}</view>
    </view>

    <button
      class="primary-btn broadcast-btn"
      :loading="broadcasting"
      :disabled="broadcasting"
      @tap="handleBroadcast"
    >
      一键喊话
    </button>

    <view v-if="event && event.can_start_manual" class="manual-panel high">
      <view class="manual-title">需要人工现场处理</view>
      <button
        class="danger-btn"
        :loading="startingManual"
        :disabled="startingManual"
        @tap="startManual"
      >
        我去处理
      </button>
    </view>

    <view v-else-if="event && event.can_submit_result" class="manual-panel">
      <view class="manual-title">正在人工处理</view>
      <button class="ghost-btn" @tap="openProcess">进入现场处理</button>
    </view>

    <view v-if="event && event.mini_status === 'AUTO_HANDLING'" class="auto-panel">
      <view v-if="event.risk_level === 'LOW'">
        <view>系统自动处理中</view>
        <view>已自动喊话</view>
        <view>无需人工处理</view>
      </view>
      <view v-else-if="event.risk_level === 'MEDIUM'">
        <view>系统自动处理中</view>
        <view>已再次自动喊话</view>
        <view>无人机自动派飞/取证中</view>
        <view>无需人工处理</view>
      </view>
    </view>

    <view class="section">
      <view class="section-title">处置过程</view>
      <view v-if="timeline.length === 0" class="timeline-empty">暂无处置记录</view>
      <view v-else class="timeline">
        <view v-for="item in timeline" :key="item.action_id" class="timeline-item">
          <view class="dot"></view>
          <view class="timeline-time">{{ item.timeText }}</view>
          <view class="timeline-message">{{ item.message }}</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { absoluteUrl, request } from '../../utils/request'
import { formatDateTime, formatDuration, formatTime, riskClass } from '../../utils/format'
import { subscribeHighEvent } from '../../utils/subscribe'
import { WS_BASE_URL } from '../../utils/config'

export default {
  data() {
    return {
      eventId: '',
      event: null,
      timeline: [],
      riskClassName: '',
      startTime: '--',
      durationText: '--',
      snapshotUrl: '',
      streamUrl: '',
      videoText: 'V1兼容预览，PC端WebRTC链路不受影响',
      broadcasting: false,
      startingManual: false,
      socketTask: null
    }
  },

  onLoad(options) {
    this.eventId = options?.event_id || ''
    this.loadDetail()
    this.loadVideo()
    this.connectEventSocket()
  },

  onUnload() {
    if (this.socketTask) {
      this.socketTask.close()
      this.socketTask = null
    }
  },

  onPullDownRefresh() {
    Promise.all([this.loadDetail(), this.loadVideo()]).finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    loadDetail() {
      if (!this.eventId) return Promise.resolve()
      return request({ url: `/events/${encodeURIComponent(this.eventId)}` })
        .then((data) => {
          const event = data.event
          const timeline = (data.timeline || []).map((item) => ({
            ...item,
            timeText: formatTime(item.created_at)
          }))
          this.event = event
          this.timeline = timeline
          this.riskClassName = riskClass(event.risk_level)
          this.startTime = formatDateTime(event.started_at)
          this.durationText = formatDuration(event.duration_seconds)
          if (event.risk_level === 'HIGH') {
            subscribeHighEvent(event.event_id).catch(() => null)
          }
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
    },

    loadVideo() {
      if (!this.eventId) return Promise.resolve()
      return request({ url: `/events/${encodeURIComponent(this.eventId)}/video` })
        .then((data) => {
          this.snapshotUrl = `${absoluteUrl(data.snapshot_url)}?t=${Date.now()}`
          this.streamUrl = absoluteUrl(data.stream_url)
          this.videoText = data.compatibility?.adapter || 'V1兼容预览，PC端WebRTC链路不受影响'
        })
        .catch(() => {
          this.snapshotUrl = ''
          this.streamUrl = ''
          this.videoText = '当前摄像头暂未返回实时画面'
        })
    },

    refreshSnapshot() {
      this.loadVideo()
    },

    connectEventSocket() {
      if (!this.eventId) return
      this.socketTask = uni.connectSocket({
        url: `${WS_BASE_URL}/api/v1/camera/safety/ws`,
        complete: () => {}
      })
      this.socketTask.onMessage((message) => {
        let payload = {}
        try {
          payload = JSON.parse(message.data || '{}')
        } catch (error) {
          return
        }
        const eventId = payload.data && payload.data.event_id
        if (eventId === this.eventId) {
          this.loadDetail()
          this.loadVideo()
        }
      })
    },

    handleBroadcast() {
      if (!this.eventId || this.broadcasting) return
      this.broadcasting = true
      request({
        url: `/events/${encodeURIComponent(this.eventId)}/broadcast`,
        method: 'POST',
        data: {
          operator: '微信小程序工作人员'
        }
      })
        .then(() => {
          uni.showToast({ title: '喊话已下发', icon: 'success' })
          this.loadDetail()
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
        .finally(() => {
          this.broadcasting = false
        })
    },

    startManual() {
      if (!this.eventId || this.startingManual) return
      this.startingManual = true
      request({
        url: `/events/${encodeURIComponent(this.eventId)}/start-manual`,
        method: 'POST',
        data: {
          operator: '微信小程序工作人员'
        }
      })
        .then(() => {
          uni.navigateTo({
            url: `/pages/process/index?event_id=${encodeURIComponent(this.eventId)}`
          })
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
          this.loadDetail()
        })
        .finally(() => {
          this.startingManual = false
        })
    },

    openProcess() {
      uni.navigateTo({
        url: `/pages/process/index?event_id=${encodeURIComponent(this.eventId)}`
      })
    }
  }
}
</script>

<style>
.detail-page {
  padding-bottom: 48rpx;
}

.summary,
.section,
.manual-panel,
.auto-panel {
  background: #fff;
  border-radius: 8rpx;
  padding: 22rpx;
  margin-bottom: 18rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
}

.summary-top {
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
  font-weight: 600;
  text-align: right;
}

.event-title {
  font-size: 36rpx;
  font-weight: 700;
  margin-bottom: 18rpx;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx 18rpx;
}

.info-grid view {
  min-height: 84rpx;
  padding: 14rpx;
  border-radius: 8rpx;
  background: #f2f6f7;
  box-sizing: border-box;
}

.info-grid text {
  display: block;
}

.info-grid text:first-child {
  color: #6c7a80;
  font-size: 24rpx;
  margin-bottom: 8rpx;
}

.info-grid text:last-child {
  color: #172026;
  font-size: 26rpx;
  line-height: 34rpx;
  word-break: break-all;
}

.section-title {
  font-weight: 700;
  font-size: 30rpx;
  margin-bottom: 16rpx;
}

.video-box {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 8rpx;
  overflow: hidden;
  background: #07161a;
}

.video-frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.video-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b6c8ce;
}

.video-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 14rpx;
}

.video-footer text {
  flex: 1;
  min-width: 0;
  color: #6c7a80;
  font-size: 24rpx;
  line-height: 34rpx;
}

.mini-btn {
  width: 156rpx;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  background: #e7eff1;
  color: #0f4c5c;
  font-size: 24rpx;
}

.action-panel,
.auto-panel {
  color: #24474f;
  line-height: 44rpx;
}

.broadcast-btn {
  margin-bottom: 18rpx;
}

.manual-panel.high {
  border-left: 8rpx solid #d63d3d;
}

.manual-title {
  font-size: 30rpx;
  font-weight: 700;
  margin-bottom: 18rpx;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.timeline-item {
  position: relative;
  padding-left: 30rpx;
}

.dot {
  position: absolute;
  left: 0;
  top: 10rpx;
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: #0f6b7a;
}

.timeline-time {
  color: #6c7a80;
  font-size: 24rpx;
  margin-bottom: 4rpx;
}

.timeline-message {
  color: #172026;
  line-height: 42rpx;
  white-space: pre-line;
}

.timeline-empty {
  color: #7b8b91;
  text-align: center;
  padding: 36rpx 0;
}
</style>
