<template>
  <view class="page events-page">
    <view class="stats-grid">
      <view class="stat-card is-today">
        <text>今日高风险</text>
        <text>{{ summary.today_high }}</text>
      </view>
      <view class="stat-card is-month">
        <text>本月高风险</text>
        <text>{{ summary.month_high }}</text>
      </view>
      <view class="stat-card is-processing">
        <text>人工处理中</text>
        <text>{{ summary.processing }}</text>
      </view>
      <view class="stat-card is-pending">
        <text>待处理</text>
        <text>{{ summary.pending }}</text>
      </view>
    </view>

    <view class="filter-panel">
      <picker mode="selector" :range="cameraOptions" :value="selectedPointIndex" @change="onPointPick">
        <view class="filter-select">{{ pointFilterLabel }}</view>
      </picker>
      <picker mode="date" :value="filters.date" @change="onDateChange">
        <view class="filter-select">{{ filters.date || '发生日期' }}</view>
      </picker>
      <view class="filter-actions">
        <button class="filter-btn" @tap="applyFilters">筛选</button>
        <button class="clear-btn" @tap="clearFilters">清空</button>
      </view>
    </view>

    <view class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        class="tab"
        :class="{ active: activeTab === tab.value }"
        @tap="switchTab(tab.value)"
      >
        {{ tab.label }}
      </view>
    </view>

    <view class="section-head">
      <text>风险事件</text>
      <text>共 {{ total }} 条</text>
    </view>

    <view v-if="loading" class="empty compact">加载中...</view>
    <view v-else-if="loadError" class="error-panel">
      <view>事件加载失败</view>
      <text>{{ loadError }}</text>
      <button class="ghost-btn retry-btn" @tap="reload">重新加载</button>
    </view>
    <view v-else-if="events.length === 0" class="empty compact">暂无{{ currentTabLabel }}事件</view>

    <view v-else class="event-list">
      <view
        v-for="item in events"
        :key="item.event_id"
        class="event-card"
        :class="{ mine: item.is_my_task, demo: item.is_demo }"
        @tap="openDetail(item.event_id)"
      >
        <view class="card-head">
          <view class="event-title-wrap">
            <view class="event-title">{{ item.event_name || item.event_type }}</view>
            <text>事件编号：{{ item.event_no }}</text>
          </view>
          <view class="risk-wrap">
            <view class="risk-pill" :class="item.riskClass">{{ item.risk_level_label }}</view>
            <text>{{ item.business_status_label }}</text>
          </view>
        </view>

        <view v-if="item.is_demo" class="demo-tag">演示数据</view>

        <view class="meta-line">
          <text>监测点</text>
          <text>{{ item.monitor_point }}</text>
        </view>
        <view class="meta-line">
          <text>开始时间</text>
          <text>{{ item.startText }}</text>
        </view>
        <view v-if="item.assigned_group_name" class="meta-line">
          <text>任务组</text>
          <text>{{ item.assigned_group_name }}</text>
        </view>
        <view v-if="activeTab === 'completed'" class="meta-line">
          <text>持续时间</text>
          <text>{{ item.durationText }}</text>
        </view>
        <view v-if="activeTab === 'completed'" class="meta-line">
          <text>完成时间</text>
          <text>{{ item.completedText }}</text>
        </view>
        <view v-if="activeTab !== 'pending'" class="meta-line">
          <text>处理人</text>
          <text>{{ item.handler_name || '--' }}</text>
        </view>

        <view v-if="activeTab === 'processing' && item.is_my_assignee" class="mine-tag">我的处理中</view>
        <view v-if="activeTab === 'pending' && item.is_my_group_task" class="mine-tag">本组待处理</view>
        <view v-if="activeTab === 'pending' && item.can_accept" class="card-actions">
          <button class="primary-btn card-btn" @tap.stop="acceptEvent(item)">接受任务</button>
          <button class="ghost-btn card-btn" @tap.stop="markFalseAlarm(item)">标记误报</button>
        </view>
      </view>
    </view>

    <pager :page="page" :total-pages="totalPages" @change="goPage" />
  </view>
</template>

<script>
import { request } from '../../utils/request'
import { formatDateTime, formatDuration, riskClass } from '../../utils/format'
import { readCache, writeCache } from '../../utils/cache'
import { isLoggedIn } from '../../utils/auth'
import { subscribeRiskAlert } from '../../utils/subscribe'
import { DEMO_EVENT_TARGETS, ENABLE_DEMO_EVENTS } from '../../utils/config'
import Pager from '../../components/pager/pager.vue'

const PAGE_SIZE = 10
const NOTIFY_PROMPT_KEY = 'mini_notify_prompted'

export default {
  components: {
    Pager
  },

  data() {
    return {
      tabs: [
        { value: 'pending', label: '待处理' },
        { value: 'processing', label: '进行中' },
        { value: 'completed', label: '已完成' }
      ],
      activeTab: 'pending',
      filters: {
        point: '',
        date: ''
      },
      cameraOptions: ['全部点位'],
      selectedPointIndex: 0,
      summary: {
        today_high: 0,
        month_high: 0,
        processing: 0,
        pending: 0
      },
      events: [],
      staff: null,
      page: 1,
      total: 0,
      hasMore: false,
      loading: false,
      loadError: '',
      subscribingAlerts: false
    }
  },

  computed: {
    currentTabLabel() {
      return (this.tabs.find((item) => item.value === this.activeTab) || {}).label || ''
    },

    pointFilterLabel() {
      return this.cameraOptions[this.selectedPointIndex] || '全部点位'
    },

    // 总页数，每页 10 条
    totalPages() {
      return Math.max(1, Math.ceil(this.total / PAGE_SIZE))
    }
  },

  onLoad() {
    this.restoreCached()
    this.bootstrap()
    // 进入页面后引导勾选服务通知
    this.promptRiskAlert()
  },

  onPullDownRefresh() {
    this.reload().finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCached() {
      const cached = readCache(this.cacheKey(), null)
      if (!cached) return
      const cachedItems = cached.items || []
      this.events = ENABLE_DEMO_EVENTS ? cachedItems : cachedItems.filter((item) => !item.is_demo)
      this.total = cached.total || 0
      this.hasMore = Boolean(cached.hasMore)
      this.summary = cached.summary || this.summary
      this.staff = cached.staff || readCache('mini-staff', null)
    },

    cacheKey() {
      return `events:${this.activeTab}:${this.filters.point}:${this.filters.date}`
    },

    bootstrap() {
      this.ensureStaff()
        .then(() => {
          return Promise.all([
            this.loadSummary().catch(() => null),
            this.loadEvents(false)
          ])
        })
        .catch(() => this.loadEvents(false))
        .catch(() => null)
      this.loadCameraOptions().catch(() => null)
    },

    ensureStaff() {
      const cached = readCache('mini-staff', null)
      // 已登录优先走 token 解析；未登录老版本用 staff_id 回落
      const query = !isLoggedIn() && cached?.staff_id ? `?staff_id=${cached.staff_id}` : ''
      return request({ url: `/staff/me${query}` })
        .then((data) => {
          this.staff = data.staff
          writeCache('mini-staff', data.staff)
        })
    },

    staffQuery() {
      return this.staff?.staff_id ? `&staff_id=${encodeURIComponent(this.staff.staff_id)}` : ''
    },

    loadSummary() {
      const params = [
        this.filters.point ? `point=${encodeURIComponent(this.filters.point)}` : '',
        this.filters.date ? `date=${encodeURIComponent(this.filters.date)}` : '',
        this.staff?.staff_id ? `staff_id=${encodeURIComponent(this.staff.staff_id)}` : ''
      ].filter(Boolean).join('&')
      return request({ url: `/events/summary${params ? '?' + params : ''}` })
        .then((data) => {
          this.summary = {
            today_high: Number(data.today_high || 0),
            month_high: Number(data.month_high || 0),
            processing: Number(data.processing || 0),
            pending: Number(data.pending || 0)
          }
          this.applyDemoSummary()
        })
    },

    applyDemoSummary() {
      if (!ENABLE_DEMO_EVENTS) return
      this.summary.pending = Math.max(this.summary.pending, DEMO_EVENT_TARGETS.pending)
      this.summary.processing = Math.max(this.summary.processing, DEMO_EVENT_TARGETS.processing)
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
      return this.loadEvents(false)
    },

    // 切换分页：直接加载指定页码，每页 10 条
    goPage(target) {
      if (target === this.page || this.loading) return
      this.page = target
      this.loadEvents(false).then(() => {
        uni.pageScrollTo({ scrollTop: 0, duration: 200 })
      })
    },

    loadEvents(append) {
      this.loading = true
      this.loadError = ''
      const params = [
        `status=${this.activeTab}`,
        `page=${this.page}`,
        `page_size=${PAGE_SIZE}`,
        this.filters.point ? `point=${encodeURIComponent(this.filters.point)}` : '',
        this.filters.date ? `date=${encodeURIComponent(this.filters.date)}` : '',
        this.staff?.staff_id ? `staff_id=${encodeURIComponent(this.staff.staff_id)}` : ''
      ].filter(Boolean).join('&')
      return request({ url: `/events?${params}` })
        .then((data) => {
          const realRows = (data.items || []).map(this.decorateEvent)
          const demoRows = this.demoEventsFor(this.activeTab)
          const target = this.page === 1 ? Number(DEMO_EVENT_TARGETS[this.activeTab] || 0) : 0
          const demoCount = Math.max(0, target - Number(data.total || 0))
          const rows = this.sortEventRows(realRows.concat(demoRows.slice(0, demoCount)))
          this.events = append ? this.events.concat(rows) : rows
          this.total = Number(data.total || 0) + demoCount
          this.hasMore = Boolean(data.has_more) || this.page * PAGE_SIZE < this.total
          this.applyDemoSummary()
          writeCache(this.cacheKey(), {
            items: this.events,
            total: this.total,
            hasMore: this.hasMore,
            summary: this.summary,
            staff: this.staff
          })
        })
        .catch((error) => {
          const cached = readCache(this.cacheKey(), null)
          if (cached && !append) {
            this.events = cached.items || []
            this.total = cached.total || 0
            this.hasMore = Boolean(cached.hasMore)
            this.loadError = ''
            return
          }
          this.loadError = error.message || '网络错误'
          uni.showToast({ title: this.loadError, icon: 'none' })
        })
        .finally(() => { this.loading = false })
    },

    decorateEvent(item) {
      return {
        ...item,
        riskClass: riskClass(item.risk_level),
        startText: formatDateTime(item.started_at),
        completedText: formatDateTime(item.completed_at),
        durationText: formatDuration(item.duration_seconds)
      }
    },

    sortEventRows(rows) {
      if (!['pending', 'processing'].includes(this.activeTab)) return rows
      const rank = (item) => {
        if (this.activeTab === 'pending') return item.is_my_group_task ? 0 : 1
        return item.is_my_assignee ? 0 : 1
      }
      return rows
        .map((item, index) => ({ item, index }))
        .sort((left, right) => rank(left.item) - rank(right.item) || left.index - right.index)
        .map(({ item }) => item)
    },

    demoEventsFor(status) {
      if (!ENABLE_DEMO_EVENTS || !['pending', 'processing'].includes(status)) return []
      const now = Math.floor(Date.now() / 1000)
      const currentGroup = this.staff?.group_name || '九号点位组'
      const otherGroup = currentGroup === '九号点位组' ? '三号点位组' : '九号点位组'
      const currentName = this.staff?.display_name || '现场处置员'
      const sameGroupName = currentName === '九号点位值班员' ? '一号点位值班员' : '组内其他处置员'
      const base = (eventId, title, groupName, extra = {}) => ({
        id: eventId,
        event_id: eventId,
        instance_no: eventId,
        event_no: eventId,
        event_name: title,
        event_type: title,
        monitor_point: extra.monitor_point || '9号监测点',
        camera_id: '1',
        risk_level: extra.risk_level || 'HIGH',
        risk_level_label: extra.risk_level === 'MEDIUM' ? '中' : '高',
        business_status: status,
        business_status_label: status === 'pending' ? '待处理' : '处理中',
        mini_status: status === 'pending' ? 'WAITING_MANUAL' : 'MANUAL_PROCESSING',
        mini_status_label: status === 'pending' ? '等待人工处理' : '正在人工处理',
        started_at: now - (extra.age || 900),
        duration_seconds: status === 'processing' ? extra.duration || 420 : 0,
        assigned_group_id: groupName,
        assigned_group_name: groupName,
        handler_name: extra.handler_name || null,
        assignee: extra.assignee || null,
        is_demo: true,
        can_accept: status === 'pending' && groupName === currentGroup,
        can_false_alarm: status === 'pending' && groupName === currentGroup,
        can_submit_result: status === 'processing' && extra.assignee === currentName,
        is_my_group_task: status === 'pending' && groupName === currentGroup,
        is_my_assignee: status === 'processing' && extra.assignee === currentName,
        is_my_task: status === 'pending' ? groupName === currentGroup : extra.assignee === currentName,
        ...extra
      })

      if (status === 'pending') {
        return [
          base('DEMO_PENDING_GROUP_01', '人员进入高风险区域（演示）', currentGroup, { age: 480 }),
          base('DEMO_PENDING_GROUP_02', '船只靠近禁入水域（演示）', currentGroup, { risk_level: 'MEDIUM', age: 960 }),
          base('DEMO_PENDING_OTHER_GROUP', '夜间非法捕鱼告警（演示）', otherGroup, { age: 1440 })
        ].map(this.decorateEvent)
      }

      return [
        base('DEMO_PROCESSING_ME', '人员涉水处置中（演示）', currentGroup, {
          assignee: currentName,
          handler_name: currentName,
          age: 360,
          duration: 180
        }),
        base('DEMO_PROCESSING_GROUP', '库区船只核查中（演示）', currentGroup, {
          assignee: sameGroupName,
          handler_name: sameGroupName,
          age: 720,
          duration: 540
        }),
        base('DEMO_PROCESSING_OTHER_GROUP', '坝区人员巡查中（演示）', otherGroup, {
          assignee: '三号点位值班员',
          handler_name: '三号点位值班员',
          age: 1080,
          duration: 780
        })
      ].map(this.decorateEvent)
    },

    switchTab(tab) {
      if (tab === this.activeTab) return
      this.activeTab = tab
      this.events = []
      this.total = 0
      this.restoreCached()
      this.reload()
    },

    onPointPick(event) {
      const index = Number(event.detail.value || 0)
      this.selectedPointIndex = index
      this.filters.point = index > 0 ? this.cameraOptions[index] : ''
      this.applyFilters()
    },

    onDateChange(event) {
      this.filters.date = event.detail.value
      this.applyFilters()
    },

    applyFilters() {
      this.loadSummary().catch(() => null)
      this.reload()
    },

    clearFilters() {
      this.filters.point = ''
      this.filters.date = ''
      this.selectedPointIndex = 0
      this.applyFilters()
    },

    acceptEvent(item) {
      if (item.is_demo) {
        uni.showToast({ title: '演示任务，仅用于展示', icon: 'none' })
        return
      }
      request({
        url: `/events/${encodeURIComponent(item.event_id)}/accept`,
        method: 'POST',
        data: {
          staff_id: this.staff?.staff_id,
          remark: '小程序接受任务'
        }
      })
        .then(() => {
          uni.showToast({ title: '已接受任务', icon: 'success' })
          this.loadSummary().catch(() => null)
          this.reload()
        })
        .catch((error) => uni.showToast({ title: error.message, icon: 'none' }))
    },

    markFalseAlarm(item) {
      uni.showModal({
        title: '标记误报',
        content: '确认将该事件标记为误报？',
        success: (res) => {
          if (!res.confirm) return
          request({
            url: `/events/${encodeURIComponent(item.event_id)}/false-alarm`,
            method: 'POST',
            data: {
              staff_id: this.staff?.staff_id,
              remark: '小程序标记误报'
            }
          })
            .then(() => {
              uni.showToast({ title: '已标记误报', icon: 'success' })
              this.loadSummary().catch(() => null)
              this.reload()
            })
            .catch((error) => uni.showToast({ title: error.message, icon: 'none' }))
        }
      })
    },

    // 进入页面后引导勾选服务通知（只提示一次，避免每次进入都打扰）
    promptRiskAlert() {
      const prompted = readCache(NOTIFY_PROMPT_KEY, false)
      if (prompted) return
      writeCache(NOTIFY_PROMPT_KEY, true)
      uni.showModal({
        title: '开启服务通知',
        content: '订阅后，有低/中/高风险时会收到微信提醒',
        confirmText: '去开启',
        cancelText: '暂不',
        success: (res) => {
          if (!res.confirm) return
          this.handleSubscribeRiskAlerts()
        }
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

    openDetail(eventId) {
      if (String(eventId).startsWith('DEMO_')) {
        uni.showToast({ title: '演示事件暂无详情', icon: 'none' })
        return
      }
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

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.stat-card {
  position: relative;
  min-height: 96rpx;
  padding: 16rpx 18rpx;
  border-radius: 8rpx;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
  box-sizing: border-box;
}

.stat-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 8rpx;
  height: 100%;
  background: #0f6b7a;
}

.stat-card.is-today {
  background: linear-gradient(135deg, #fff3f2, #ffffff);
}

.stat-card.is-today::before {
  background: #e34d59;
}

.stat-card.is-month {
  background: linear-gradient(135deg, #fff8e7, #ffffff);
}

.stat-card.is-month::before {
  background: #d69b20;
}

.stat-card.is-processing {
  background: linear-gradient(135deg, #eaf6ff, #ffffff);
}

.stat-card.is-processing::before {
  background: #2389c9;
}

.stat-card.is-pending {
  background: linear-gradient(135deg, #eaf8f2, #ffffff);
}

.stat-card.is-pending::before {
  background: #15936a;
}

.stat-card text {
  display: block;
}

.stat-card text:first-child {
  color: #6c7a80;
  font-size: 24rpx;
}

.stat-card text:last-child {
  color: #172026;
  font-size: 38rpx;
  font-weight: 800;
  margin-top: 4rpx;
}

.filter-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) 228rpx;
  gap: 12rpx;
  align-items: center;
  padding: 18rpx;
  border-radius: 8rpx;
  background: #fff;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
  margin-bottom: 18rpx;
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

.filter-btn {
  background: #0f6b7a;
  color: #fff;
}

.clear-btn {
  background: #e7eff1;
  color: #0f4c5c;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.tab {
  height: 72rpx;
  line-height: 72rpx;
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

.section-head,
.card-head,
.meta-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.section-head {
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
  position: relative;
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.event-card.mine {
  border-left: 8rpx solid #0f6b7a;
}

.event-card.demo {
  border-top: 2rpx dashed #a6c8cf;
}

.demo-tag {
  display: inline-block;
  margin-bottom: 10rpx;
  padding: 6rpx 12rpx;
  border-radius: 6rpx;
  background: #edf5f6;
  color: #36717b;
  font-size: 21rpx;
}

.card-head {
  align-items: flex-start;
  margin-bottom: 18rpx;
}

.event-title-wrap {
  min-width: 0;
  flex: 1;
}

.event-title {
  color: #172026;
  font-size: 32rpx;
  font-weight: 800;
  margin-bottom: 6rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-title-wrap text {
  color: #6c7a80;
  font-size: 22rpx;
}

.risk-wrap {
  flex-shrink: 0;
  text-align: right;
}

.risk-pill {
  min-width: 96rpx;
  height: 52rpx;
  line-height: 52rpx;
  text-align: center;
  border-radius: 8rpx;
  font-weight: 700;
}

.risk-wrap text {
  display: block;
  margin-top: 6rpx;
  color: #52656c;
  font-size: 23rpx;
}

.meta-line {
  color: #52656c;
  line-height: 44rpx;
}

.meta-line text:first-child {
  flex-shrink: 0;
}

.meta-line text:last-child {
  color: #172026;
  text-align: right;
  word-break: break-all;
}

.mine-tag {
  margin-top: 14rpx;
  padding: 10rpx 14rpx;
  border-radius: 8rpx;
  background: #e8f6f3;
  color: #0f6b5a;
  font-size: 24rpx;
  font-weight: 700;
}

.card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-top: 18rpx;
}

.card-btn {
  height: 68rpx;
  line-height: 68rpx;
  font-size: 25rpx;
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
