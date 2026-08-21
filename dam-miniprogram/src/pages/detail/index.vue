<template>
  <view class="page detail-page">
    <view v-if="event" class="summary">
      <view class="summary-top">
        <view class="status-text">{{ event.business_status_label || event.mini_status_label }}</view>
        <view class="risk-pill" :class="riskClassName">{{ event.risk_level_label }}</view>
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
        <live-player
          v-if="streamUrl && !liveFallback"
          :key="livePlayerKey"
          class="video-frame"
          :src="streamUrl"
          mode="live"
          autoplay
          muted
          object-fit="contain"
          :min-cache="0.5"
          :max-cache="1.5"
          @statechange="handleLiveStateChange"
          @error="handleLiveError"
        />
        <image v-else-if="snapshotUrl" class="video-frame" :src="snapshotUrl" mode="aspectFit" />
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

    <view class="section">
      <view class="section-title">现场证据</view>
      <view v-if="evidence.length === 0" class="timeline-empty">暂无现场证据</view>
      <scroll-view v-else class="evidence-row" scroll-x>
        <view
          v-for="item in evidence"
          :key="item.id"
          class="evidence-item"
          @tap="previewEvidence(item)"
        >
          <image v-if="isImageEvidence(item)" :src="absoluteEvidenceUrl(item.url)" mode="aspectFill" />
          <video
            v-else-if="isVideoEvidence(item)"
            class="evidence-video"
            :src="absoluteEvidenceUrl(item.url)"
            controls
            show-center-play-btn
            object-fit="contain"
          />
          <view v-else class="evidence-file">{{ item.evidence_type }}</view>
          <text>{{ item.description || '现场证据' }}</text>
        </view>
      </scroll-view>
    </view>

    <view class="section">
      <view class="section-title">联动执行线路</view>
      <view v-if="linkageLines.length === 0" class="timeline-empty">暂无联动线路</view>
      <view v-else class="linkage-list">
        <view v-for="item in linkageLines" :key="item.id" class="linkage-item">
          <view>{{ item.type_label }}</view>
          <text>{{ item.target }}{{ item.route ? ' / ' + item.route : '' }}</text>
        </view>
      </view>
    </view>

    <button
      class="primary-btn broadcast-btn"
      :loading="broadcasting"
      @tap="handleBroadcast"
    >
      {{ recordingBroadcast ? '结束喊话' : '一键喊话' }}
    </button>

    <view v-if="event && event.can_start_manual" class="manual-panel high">
      <view class="manual-title">需要人工现场处理</view>
      <button
        class="ghost-btn subscribe-btn"
        :loading="subscribingAlert"
        :disabled="subscribingAlert"
        @tap="handleSubscribeEventAlert"
      >
        订阅事件提醒
      </button>
      <button
        class="ghost-btn navigate-btn"
        :disabled="!canNavigate"
        @tap="openMapNavigation"
      >
        导航到点位
      </button>
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
import { absoluteUrl, request, uploadBroadcastAudio } from '../../utils/request'
import { formatDateTime, formatDuration, formatTime, riskClass } from '../../utils/format'
import { subscribeRiskAlert } from '../../utils/subscribe'
import { WS_BASE_URL } from '../../utils/config'
import { readCache, writeCache } from '../../utils/cache'

export default {
  data() {
    return {
      eventId: '',
      event: null,
      staff: null,
      timeline: [],
      evidence: [],
      linkageLines: [],
      riskClassName: '',
      startTime: '--',
      durationText: '--',
      snapshotUrl: '',
      streamUrl: '',
      liveFallback: false,
      livePlayerKey: 0,
      videoText: '正在连接实时视频',
      broadcasting: false,
      recordingBroadcast: false,
      broadcastRecorder: null,
      startingManual: false,
      subscribingAlert: false,
      socketTask: null
    }
  },

  computed: {
    canNavigate() {
      return Boolean(this.event && Number(this.event.latitude) && Number(this.event.longitude))
    }
  },

  onLoad(options) {
    this.eventId = options?.event_id || ''
    this.staff = readCache('mini-staff', null)
    this.restoreCachedDetail()
    this.loadDetail()
    this.loadVideo()
    this.connectEventSocket()
    this.prepareBroadcastRecorder()
  },

  onUnload() {
    if (this.socketTask) {
      this.socketTask.close()
      this.socketTask = null
    }
    if (this.recordingBroadcast) this.broadcastRecorder?.stop()
  },

  onPullDownRefresh() {
    Promise.all([this.loadDetail(), this.loadVideo()]).finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedDetail() {
      if (!this.eventId) return
      const cached = readCache(`event-detail:${this.eventId}`, null)
      if (!cached) return
      this.applyDetailData(cached)
    },

    applyDetailData(data) {
      const event = data.event
      const timeline = (data.timeline || []).map((item) => ({
        ...item,
        timeText: item.timeText || formatTime(item.created_at)
      }))
      this.event = event
      this.staff = data.staff || this.staff
      if (this.staff) writeCache('mini-staff', this.staff)
      this.timeline = timeline
      this.evidence = data.evidence || []
      this.linkageLines = data.linkage_lines || []
      this.riskClassName = riskClass(event.risk_level)
      this.startTime = formatDateTime(event.started_at)
      this.durationText = formatDuration(event.duration_seconds)
    },

    loadDetail() {
      if (!this.eventId) return Promise.resolve()
      return request({ url: `/events/${encodeURIComponent(this.eventId)}` })
        .then((data) => {
          this.applyDetailData(data)
          writeCache(`event-detail:${this.eventId}`, data)
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
          this.streamUrl = data.stream_url || ''
          this.liveFallback = !this.streamUrl
          this.livePlayerKey += 1
          this.videoText = this.streamUrl ? '正在连接实时视频流' : '实时快照模式'
        })
        .catch(() => {
          this.snapshotUrl = `${absoluteUrl(`/api/miniprogram/v1/events/${encodeURIComponent(this.eventId)}/snapshot.jpg`)}?t=${Date.now()}`
          this.streamUrl = ''
          this.liveFallback = true
          this.videoText = '实时视频不可用，已切换快照预览'
        })
    },

    refreshSnapshot() {
      this.loadVideo()
    },

    absoluteEvidenceUrl(url) {
      return absoluteUrl(url || '')
    },

    isImageEvidence(item) {
      return String(item.evidence_type || '').toUpperCase() === 'IMAGE'
    },

    isVideoEvidence(item) {
      return String(item.evidence_type || '').toUpperCase() === 'VIDEO'
    },

    previewEvidence(item) {
      if (!this.isImageEvidence(item) || !item.url) return
      uni.previewImage({
        urls: this.evidence.filter(this.isImageEvidence).map((row) => this.absoluteEvidenceUrl(row.url)),
        current: this.absoluteEvidenceUrl(item.url)
      })
    },

    handleLiveStateChange(event) {
      const code = Number(event?.detail?.code || 0)
      if (code === 2004) {
        this.liveFallback = false
        this.videoText = '实时视频已连接'
      } else if (code === 2103) {
        this.videoText = '实时视频正在重连'
      } else if (code < 0) {
        this.enableSnapshotFallback('实时视频中断，已切换快照预览')
      }
    },

    handleLiveError() {
      this.enableSnapshotFallback('实时视频播放失败，已切换快照预览')
    },

    enableSnapshotFallback(message) {
      this.liveFallback = true
      this.videoText = message
      if (this.eventId) {
        this.snapshotUrl = `${absoluteUrl(`/api/miniprogram/v1/events/${encodeURIComponent(this.eventId)}/snapshot.jpg`)}?t=${Date.now()}`
      }
    },

    connectEventSocket() {
      if (!this.eventId) return
      this.socketTask = uni.connectSocket({
        url: `${WS_BASE_URL}/api/v1/integration/safety-events/ws`,
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
      if (this.recordingBroadcast) {
        this.broadcastRecorder?.stop()
        return
      }
      this.broadcastRecorder?.start({ duration: 60000, format: 'mp3', sampleRate: 16000, numberOfChannels: 1 })
    },

    prepareBroadcastRecorder() {
      this.broadcastRecorder = uni.getRecorderManager()
      this.broadcastRecorder.onStart(() => {
        this.recordingBroadcast = true
        uni.showToast({ title: '请开始喊话，再次点击结束', icon: 'none' })
      })
      this.broadcastRecorder.onStop(({ tempFilePath }) => {
        this.recordingBroadcast = false
        this.broadcasting = true
        uploadBroadcastAudio({ filePath: tempFilePath, eventId: this.eventId })
          .then((result) => {
            uni.showToast({
              title: result.result === 'PARTIAL_SUCCESS' ? '部分设备播放成功' : '喊话已播放',
              icon: result.result === 'PARTIAL_SUCCESS' ? 'none' : 'success'
            })
            this.loadDetail()
          })
          .catch((error) => uni.showToast({ title: error.message, icon: 'none' }))
          .finally(() => { this.broadcasting = false })
      })
      this.broadcastRecorder.onError((error) => {
        this.recordingBroadcast = false
        this.broadcasting = false
        uni.showToast({ title: error.errMsg || '无法录音', icon: 'none' })
      })
    },

    startManual() {
      if (!this.eventId || this.startingManual) return
      this.startingManual = true
      request({
        url: `/events/${encodeURIComponent(this.eventId)}/accept`,
        method: 'POST',
        data: {
          staff_id: this.staff?.staff_id,
          remark: '小程序接受任务'
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

    handleSubscribeEventAlert() {
      if (!this.eventId || this.subscribingAlert) return
      this.subscribingAlert = true
      subscribeRiskAlert(this.eventId)
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
          this.subscribingAlert = false
        })
    },

    openMapNavigation() {
      if (!this.event) return
      uni.navigateTo({
        url: `/pages/map/index?camera_id=${encodeURIComponent(this.event.camera_id || '')}&event_id=${encodeURIComponent(this.eventId)}`
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
  text-align: left;
  min-width: 0;
  flex: 1;
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

.evidence-row {
  width: 100%;
  white-space: nowrap;
}

.evidence-item {
  display: inline-block;
  width: 220rpx;
  margin-right: 14rpx;
  vertical-align: top;
}

.evidence-item image,
.evidence-item video,
.evidence-file {
  width: 220rpx;
  height: 150rpx;
  border-radius: 8rpx;
  background: #eef4f5;
}

.evidence-file {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #52656c;
  font-weight: 700;
}

.evidence-item text {
  display: block;
  margin-top: 8rpx;
  color: #52656c;
  font-size: 23rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.linkage-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.linkage-item {
  padding: 16rpx;
  border-radius: 8rpx;
  background: #f2f6f7;
}

.linkage-item view {
  color: #172026;
  font-weight: 700;
  margin-bottom: 6rpx;
}

.linkage-item text {
  color: #52656c;
  font-size: 24rpx;
  line-height: 34rpx;
  word-break: break-all;
}

.manual-panel.high {
  border-left: 8rpx solid #d63d3d;
}

.manual-title {
  font-size: 30rpx;
  font-weight: 700;
  margin-bottom: 18rpx;
}

.subscribe-btn {
  margin-bottom: 14rpx;
}

.navigate-btn {
  margin-bottom: 14rpx;
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
