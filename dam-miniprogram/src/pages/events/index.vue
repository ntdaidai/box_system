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

    <view v-if="loading" class="empty">加载中...</view>
    <view v-else-if="events.length === 0" class="empty">
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
import { formatDuration, riskClass } from '../../utils/format'

export default {
  data() {
    return {
      activeTab: 'ongoing',
      events: [],
      highCount: 0,
      manualCount: 0,
      loading: false
    }
  },

  onLoad() {
    this.loadEvents()
  },

  onShow() {
    this.loadEvents()
  },

  onPullDownRefresh() {
    this.loadEvents().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    switchTab(tab) {
      if (tab === this.activeTab) return
      this.activeTab = tab
      this.events = []
      this.loadEvents()
    },

    loadEvents() {
      this.loading = true
      return request({
        url: `/events?status=${this.activeTab}&page_size=50`
      })
        .then((data) => {
          const events = (data.items || []).map((item) => ({
            ...item,
            riskClass: riskClass(item.risk_level),
            durationText: formatDuration(item.duration_seconds)
          }))
          this.events = events
          this.highCount = events.filter((item) => item.risk_level === 'HIGH' && item.mini_status !== 'RESOLVED').length
          this.manualCount = events.filter((item) => item.mini_status === 'MANUAL_PROCESSING').length
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
        .finally(() => {
          this.loading = false
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
  padding: 120rpx 20rpx;
  color: #7b8b91;
  text-align: center;
}
</style>
