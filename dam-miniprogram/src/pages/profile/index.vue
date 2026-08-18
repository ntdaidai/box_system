<template>
  <view class="page profile-page">
    <!-- 未登录：扫码登录引导 -->
    <view v-if="!loggedIn" class="profile-panel login-panel">
      <view class="login-icon">◎</view>
      <view class="login-title">现场处置员</view>
      <text class="login-desc">扫描管理员提供的登录码即可完成身份认证，登录后长期有效</text>
      <button class="primary-btn login-btn" @tap="handleScanLogin">扫码登录</button>
    </view>

    <!-- 已登录：人员信息与处理记录 -->
    <template v-else>
      <view class="profile-panel">
        <view class="profile-top">
          <image v-if="staff.avatar_url" class="avatar-img" :src="staff.avatar_url" mode="aspectFill" />
          <view v-else class="avatar">{{ avatarText }}</view>
          <view class="profile-main">
            <view>{{ staff.display_name || '现场处置员' }}</view>
            <text>{{ staff.staff_no || '--' }}</text>
          </view>
          <view class="group-tag">{{ staff.group_name || '--' }}</view>
        </view>

        <button class="danger-btn logout-btn" @tap="handleLogout">退出登录</button>
      </view>

      <view class="filter-panel">
        <picker mode="selector" :range="cameraOptions" :value="selectedPointIndex" @change="onPointPick">
          <view class="filter-select">{{ pointFilterLabel }}</view>
        </picker>
        <picker mode="date" :value="filters.date" @change="onDateChange">
          <view class="filter-select">{{ filters.date || '发生日期' }}</view>
        </picker>
        <view class="filter-actions">
          <button class="filter-btn" @tap="reload">筛选</button>
          <button class="clear-btn" @tap="clearFilters">清空</button>
        </view>
      </view>

      <view class="handled-panel">
        <view class="section-head">
          <text>我的处理</text>
          <text>共 {{ total }} 条</text>
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
            <view class="item-main">
              <view>{{ item.event_name || item.event_type }}</view>
              <text>{{ item.monitor_point }}</text>
            </view>
            <view class="item-side">
              <text>{{ item.business_status_label }}</text>
              <text>{{ item.completedText }}</text>
            </view>
          </view>
        </view>

        <pager :page="page" :total-pages="totalPages" @change="goPage" />
      </view>
    </template>
  </view>
</template>

<script>
import { request } from '../../utils/request'
import { formatDateTime, riskClass } from '../../utils/format'
import { readCache, writeCache } from '../../utils/cache'
import { isLoggedIn, scanQrLogin, logout } from '../../utils/auth'
import Pager from '../../components/pager/pager.vue'

const PAGE_SIZE = 10

export default {
  components: {
    Pager
  },

  data() {
    return {
      staff: {},
      handledEvents: [],
      filters: {
        point: '',
        date: ''
      },
      cameraOptions: ['全部点位'],
      selectedPointIndex: 0,
      page: 1,
      total: 0,
      hasMore: false,
      loading: false
    }
  },

  computed: {
    loggedIn() {
      return isLoggedIn()
    },

    avatarText() {
      return String(this.staff.display_name || '巡').slice(0, 1)
    },

    pointFilterLabel() {
      return this.cameraOptions[this.selectedPointIndex] || '全部点位'
    },

    // 总页数，每页 10 条
    totalPages() {
      return Math.max(1, Math.ceil(this.total / PAGE_SIZE))
    }
  },

  onShow() {
    this.refreshProfile()
  },

  onPullDownRefresh() {
    this.reload().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    // 刷新个人资料：未登录仅展示扫码引导，登录后拉取最新人员信息
    refreshProfile() {
      this.staff = readCache('mini-staff', {})
      this.handledEvents = readCache('handled-events', [])
      if (!isLoggedIn()) return
      this.ensureStaff().then(() => Promise.all([this.loadCameraOptions(), this.reload()]))
    },

    // 扫码登录入口
    handleScanLogin() {
      scanQrLogin()
        .then(() => {
          uni.showToast({ title: '登录成功', icon: 'success' })
          this.refreshProfile()
        })
        .catch((error) => {
          uni.showToast({ title: error.message || '扫码失败', icon: 'none' })
        })
    },

    // 退出登录
    handleLogout() {
      uni.showModal({
        title: '退出登录',
        content: '确认退出当前账号？',
        success: (res) => {
          if (!res.confirm) return
          logout()
          this.staff = {}
          this.handledEvents = []
          writeCache('mini-staff', {})
          this.reload()
        }
      })
    },

    ensureStaff() {
      // 已登录优先走 token 解析；未登录老版本用 staff_id 回落
      const query = isLoggedIn() || !this.staff?.staff_id ? '' : `?staff_id=${this.staff.staff_id}`
      return request({ url: `/staff/me${query}` })
        .then((data) => {
          this.staff = data.staff || {}
          writeCache('mini-staff', this.staff)
        })
    },

    queryParams() {
      return [
        'status=all',
        'mine=true',
        `page=${this.page}`,
        `page_size=${PAGE_SIZE}`,
        this.staff?.staff_id ? `staff_id=${encodeURIComponent(this.staff.staff_id)}` : '',
        this.filters.point ? `point=${encodeURIComponent(this.filters.point)}` : '',
        this.filters.date ? `date=${encodeURIComponent(this.filters.date)}` : ''
      ].filter(Boolean).join('&')
    },

    loadCameraOptions() {
      return request({ url: '/cameras' })
        .then((data) => {
          const names = (data.items || [])
            .map((item) => item.camera_name || item.name || item.id)
            .filter(Boolean)
          this.cameraOptions = ['全部点位', ...names]
          const currentIndex = this.cameraOptions.indexOf(this.filters.point)
          this.selectedPointIndex = currentIndex > -1 ? currentIndex : 0
        })
        .catch(() => {
          this.cameraOptions = ['全部点位']
          this.selectedPointIndex = 0
        })
    },

    reload() {
      this.page = 1
      return this.loadHandledEvents(false)
    },

    // 切换分页：直接加载指定页码，每页 10 条
    goPage(target) {
      if (target === this.page || this.loading) return
      this.page = target
      this.loadHandledEvents(false).then(() => {
        uni.pageScrollTo({ scrollTop: 0, duration: 200 })
      })
    },

    loadHandledEvents(append) {
      this.loading = true
      return request({ url: `/events?${this.queryParams()}` })
        .then((data) => {
          const rows = (data.items || []).map(this.decorateEvent)
          this.handledEvents = append ? this.handledEvents.concat(rows) : rows
          this.total = Number(data.total || 0)
          this.hasMore = Boolean(data.has_more)
          writeCache('handled-events', this.handledEvents)
        })
        .catch((error) => {
          if (!append) this.handledEvents = readCache('handled-events', [])
          uni.showToast({ title: error.message || '处理记录加载失败', icon: 'none' })
        })
        .finally(() => { this.loading = false })
    },

    decorateEvent(item) {
      return {
        ...item,
        riskClass: riskClass(item.risk_level),
        completedText: item.completed_at ? formatDateTime(item.completed_at) : '--'
      }
    },

    onPointPick(event) {
      const index = Number(event.detail.value || 0)
      this.selectedPointIndex = index
      this.filters.point = index > 0 ? this.cameraOptions[index] : ''
      this.reload()
    },

    onDateChange(event) {
      this.filters.date = event.detail.value
      this.reload()
    },

    clearFilters() {
      this.filters.point = ''
      this.filters.date = ''
      this.selectedPointIndex = 0
      this.reload()
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

.login-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56rpx 32rpx 44rpx;
  text-align: center;
}

.login-icon {
  width: 120rpx;
  height: 120rpx;
  line-height: 120rpx;
  border-radius: 50%;
  background: #eaf3f5;
  color: #0f4c5c;
  font-size: 64rpx;
  font-weight: 800;
  margin-bottom: 22rpx;
}

.login-title {
  color: #172026;
  font-size: 36rpx;
  font-weight: 800;
  margin-bottom: 10rpx;
}

.login-desc {
  color: #6c7a80;
  font-size: 25rpx;
  line-height: 40rpx;
  margin-bottom: 32rpx;
}

.login-btn {
  width: 320rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 30rpx;
}

.logout-btn {
  margin-top: 22rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 28rpx;
  font-weight: 700;
}

.profile-panel,
.filter-panel,
.handled-panel {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.filter-panel,
.handled-panel {
  margin-top: 20rpx;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) 228rpx;
  gap: 12rpx;
  align-items: center;
  padding: 18rpx;
}

.profile-top {
  display: flex;
  align-items: flex-start;
  gap: 18rpx;
  margin-bottom: 22rpx;
}

.avatar,
.avatar-img {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.avatar {
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
  flex: 1;
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

.group-tag {
  flex-shrink: 0;
  padding: 6rpx 16rpx;
  border-radius: 8rpx;
  background: #eaf3f5;
  color: #0f4c5c;
  font-size: 22rpx;
  font-weight: 700;
}

.filter-select {
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 20rpx;
  border-radius: 8rpx;
  background: #f2f6f7;
  color: #172026;
  font-size: 25rpx;
  box-sizing: border-box;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10rpx;
}

.filter-btn,
.clear-btn {
  height: 72rpx;
  line-height: 72rpx;
  margin: 0;
  padding: 0;
  border-radius: 8rpx;
  font-size: 23rpx;
  font-weight: 700;
  box-sizing: border-box;
}

@media (max-width: 360px) {
  .filter-panel {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .filter-actions {
    grid-column: 1 / -1;
    grid-template-columns: 1fr 1fr;
    gap: 12rpx;
  }
}

.clear-btn {
  background: #e7eff1;
  color: #52656c;
}

.filter-btn {
  background: #0f6b7a;
  color: #fff;
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
  min-height: 82rpx;
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

.item-main {
  min-width: 0;
  flex: 1;
}

.item-main view {
  color: #172026;
  font-weight: 700;
  margin-bottom: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-main text,
.item-side text:last-child {
  color: #6c7a80;
  font-size: 23rpx;
}

.item-side {
  flex-shrink: 0;
  text-align: right;
}

.item-side text {
  display: block;
}

.item-side text:first-child {
  color: #0f6b7a;
  font-size: 24rpx;
  margin-bottom: 4rpx;
}

</style>
