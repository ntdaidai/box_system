<template>
  <view class="page events-page">
    <view class="tabs">
      <view
        class="tab"
        :class="{ active: activeTab === 'ongoing' }"
        @tap="switchEventStatus('ongoing')"
      >
        进行中
      </view>
      <view
        class="tab"
        :class="{ active: activeTab === 'resolved' }"
        @tap="switchEventStatus('resolved')"
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
      <button class="ghost-btn retry-btn" @tap="loadEvents">重新加载</button>
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
  </view>
</template>

<script>
import { request } from '../../utils/request'
import { API_BASE_URL } from '../../utils/config'
import { formatDuration, riskClass } from '../../utils/format'
import { subscribeRiskAlert } from '../../utils/subscribe'
import { readCache, writeCache } from '../../utils/cache'

export default {
  data() {
    return {
      activeTab: 'ongoing',
      events: [],
      highCount: 0,
      manualCount: 0,
      loading: false,
      loadError: '',
      subscribingAlerts: false
    }
  },

  computed: {
    apiBaseText() {
      return `接口地址：${API_BASE_URL}`
    }
  },

  onLoad() {
    this.restoreCachedEvents()
    this.loadEvents()
  },

  onPullDownRefresh() {
    this.loadEvents().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedEvents() {
      const cachedEvents = readCache(`events:${this.activeTab}`, [])
      if (!cachedEvents.length) return
      this.events = cachedEvents
      this.updateCounters(cachedEvents)
    },

    switchEventStatus(tab) {
      if (tab === this.activeTab) return
      this.activeTab = tab
      this.events = readCache(`events:${tab}`, [])
      this.updateCounters(this.events)
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
          this.updateCounters(events)
          writeCache(`events:${this.activeTab}`, events)
        })
        .catch((error) => {
          const cached = readCache(`events:${this.activeTab}`, [])
          if (cached.length) {
            this.events = cached
            this.updateCounters(cached)
            this.loadError = ''
            uni.showToast({ title: error.message || '已显示缓存数据', icon: 'none' })
            return
          }
          this.loadError = error.message || '网络错误'
          uni.showToast({ title: this.loadError, icon: 'none' })
        })
        .finally(() => {
          this.loading = false
        })
    },

    updateCounters(events) {
      this.highCount = events.filter((item) => item.risk_level === 'HIGH' && item.mini_status !== 'RESOLVED').length
      this.manualCount = events.filter((item) => item.mini_status === 'MANUAL_PROCESSING').length
    },

    decorateEvent(item) {
      return {
        ...item,
        riskClass: riskClass(item.risk_level),
        durationText: formatDuration(item.duration_seconds)
      }
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

.event-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.event-card {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
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
</style>
