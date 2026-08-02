<template>
  <view class="page profile-page">
    <view class="profile-panel">
      <view class="profile-top">
        <view class="avatar">巡</view>
        <view class="profile-main">
          <view>微信小程序工作人员</view>
          <text>大藤峡安全巡查</text>
        </view>
      </view>

      <view class="stats-grid">
        <view>
          <text>{{ handledEvents.length }}</text>
          <text>我的处理</text>
        </view>
        <view>
          <text>{{ resolvedCount }}</text>
          <text>已完成</text>
        </view>
      </view>
    </view>

    <view class="handled-panel">
      <view class="section-head">
        <text>我的处理</text>
        <text>{{ handledEvents.length }} 条</text>
      </view>
      <view v-if="loading" class="handled-empty">加载中...</view>
      <view v-else-if="handledEvents.length === 0" class="handled-empty">暂无人工处理记录</view>
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
import { request } from '../../utils/request'
import { formatDuration, riskClass } from '../../utils/format'
import { readCache, writeCache } from '../../utils/cache'

export default {
  data() {
    return {
      handledEvents: [],
      loading: false
    }
  },

  computed: {
    resolvedCount() {
      return this.handledEvents.filter((item) => item.mini_status === 'RESOLVED').length
    }
  },

  onLoad() {
    this.restoreCachedHandledEvents()
    this.loadHandledEvents()
  },

  onPullDownRefresh() {
    this.loadHandledEvents().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedHandledEvents() {
      const cached = readCache('handled-events', [])
      if (cached.length) this.handledEvents = cached
    },

    loadHandledEvents() {
      this.loading = true
      return request({
        url: '/events?status=all&page_size=80'
      })
        .then((data) => {
          this.handledEvents = (data.items || [])
            .filter((item) => item.mini_status === 'MANUAL_PROCESSING' || item.mini_status === 'RESOLVED' || item.ack_operator || item.resolved_operator)
            .map(this.decorateEvent)
            .slice(0, 20)
          writeCache('handled-events', this.handledEvents)
        })
        .catch((error) => {
          this.handledEvents = readCache('handled-events', [])
          uni.showToast({ title: error.message || '处理记录加载失败', icon: 'none' })
        })
        .finally(() => {
          this.loading = false
        })
    },

    decorateEvent(item) {
      return {
        ...item,
        riskClass: riskClass(item.risk_level),
        durationText: formatDuration(item.duration_seconds)
      }
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
.profile-page {
  padding-top: 20rpx;
  padding-bottom: 48rpx;
}

.profile-panel,
.handled-panel {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.handled-panel {
  margin-top: 20rpx;
}

.profile-top {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-bottom: 22rpx;
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

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
}

.stats-grid view {
  min-height: 92rpx;
  padding: 14rpx 18rpx;
  border-radius: 8rpx;
  background: #f2f6f7;
  box-sizing: border-box;
}

.stats-grid text {
  display: block;
}

.stats-grid text:first-child {
  color: #172026;
  font-size: 36rpx;
  font-weight: 800;
  margin-bottom: 4rpx;
}

.stats-grid text:last-child {
  color: #6c7a80;
  font-size: 24rpx;
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

.handled-empty {
  padding: 34rpx 0 16rpx;
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
