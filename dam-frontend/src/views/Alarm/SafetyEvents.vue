<template>
  <div class="events-page">
    <header class="page-header">
      <div>
        <p>告警管理</p>
        <h2>安全事件</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button>
    </header>

    <section class="alarm-overview">
      <article v-for="item in overviewCards" :key="item.label" :class="item.tone">
        <el-icon><component :is="item.icon" /></el-icon>
        <div>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </div>
      </article>
    </section>

    <section class="filters">
      <el-select v-model="query.status" clearable placeholder="处置状态" @change="reloadFromFirstPage">
        <el-option label="待处理" value="PENDING" />
        <el-option label="处理中" value="PROCESSING" />
        <el-option label="已完成" value="COMPLETED" />
        <el-option label="误报" value="FALSE_ALARM" />
      </el-select>
      <el-select v-model="query.risk_level" clearable placeholder="风险等级" @change="reloadFromFirstPage">
        <el-option label="低风险" value="LOW" />
        <el-option label="中风险" value="MEDIUM" />
        <el-option label="高风险" value="HIGH" />
      </el-select>
      <el-input
        v-model.trim="query.keyword"
        clearable
        placeholder="搜索事件名称、摘要或来源"
        @clear="reloadFromFirstPage"
        @keyup.enter="reloadFromFirstPage"
      />
      <el-button type="primary" :icon="Search" @click="reloadFromFirstPage">查询</el-button>
    </section>

    <section class="table-panel" :class="{ 'is-empty': !items.length }" v-loading="loading">
      <el-table v-if="items.length" class="events-table" :data="items" row-key="id">
        <el-table-column label="序号" width="86">
          <template #default="{ $index }">
            <span class="event-no">{{ (query.page - 1) * query.page_size + $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="事件名称" min-width="160">
          <template #default="{ row }">
            <strong class="event-name">{{ row.event_name || '未命名事件' }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="event-summary">{{ row.summary || '暂无摘要' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="108">
          <template #default="{ row }">
            <el-tag :type="riskTag(row.risk_level)" effect="dark">{{ riskLevelLabel(row.risk_level, row.risk_label) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处置状态" width="126">
          <template #default="{ row }">
            <span class="event-status" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.camera_name || row.source_name || row.source_type || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">
            <time class="event-time">{{ formatTime(row.started_at) }}</time>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="96" fixed="right">
          <template #default="{ row }">
            <el-button class="detail-link" link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else-if="!loading" class="empty-state" role="status">
        <el-empty :image-size="76" description="暂无安全事件">
          <p>系统识别到的告警事件会出现在这里</p>
        </el-empty>
      </div>
      <div v-else class="loading-space" aria-hidden="true"></div>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        layout="prev, pager, next"
        :total="total"
        @current-change="loadEvents"
      />
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, CircleCheck, Refresh, Search, Warning, WarningFilled } from '@element-plus/icons-vue'
import { getUnifiedSafetyEvents } from '@/api/integration'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const query = reactive({ status: '', risk_level: '', keyword: '', page: 1, page_size: 20 })

const overview = computed(() => ({
  pending: items.value.filter((item) => item.status === 'PENDING').length,
  processing: items.value.filter((item) => item.status === 'PROCESSING').length,
  high: items.value.filter((item) => item.risk_level === 'HIGH').length,
  closed: items.value.filter((item) => ['COMPLETED', 'FALSE_ALARM'].includes(item.status)).length,
}))

const overviewCards = computed(() => [
  { label: '事件总数', value: total.value, hint: '当前筛选范围', icon: Bell, tone: 'tone-total' },
  { label: '待确认', value: overview.value.pending, hint: '需要人工判断', icon: Warning, tone: 'tone-pending' },
  { label: '高风险', value: overview.value.high, hint: '优先处置对象', icon: WarningFilled, tone: 'tone-high' },
  { label: '已闭环', value: overview.value.closed, hint: '完成或误报', icon: CircleCheck, tone: 'tone-closed' },
])

async function loadEvents() {
  loading.value = true
  try {
    const res = await getUnifiedSafetyEvents(query, { silentError: true })
    items.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '告警数据暂时不可达，请检查后端服务')
  } finally {
    loading.value = false
  }
}

function reloadFromFirstPage() {
  query.page = 1
  loadEvents()
}

function openDetail(row) {
  if (!row?.id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id: row.id } })
}

function riskTag(value) {
  return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[value] || 'info'
}

function riskLevelLabel(value, fallback) {
  return fallback || ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[value] || '未知'
}

function statusLabel(value) {
  return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[value] || value || '--'
}

function statusClass(value) {
  return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', COMPLETED: 'is-completed', FALSE_ALARM: 'is-false-alarm' })[value] || ''
}

function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

loadEvents()
</script>

<style scoped>
.events-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.page-header,
.filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.page-header p {
  margin: 0 0 6px;
  color: #79acd0;
  font-size: 14px;
}
.page-header h2 {
  margin: 0;
  color: #f3f8fd;
  font-size: 28px;
  letter-spacing: 0;
}
.alarm-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 14px;
  margin-top: 18px;
}
.alarm-overview article {
  min-height: 118px;
  padding: 18px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  border: 1px solid rgba(104, 161, 200, .24);
  border-radius: 8px;
  background: #0b1d30;
}
.alarm-overview .el-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  color: #48d8ff;
  background: rgba(72, 216, 255, .12);
  font-size: 24px;
}
.alarm-overview article.tone-high .el-icon {
  color: #ff6b76;
  background: rgba(255, 77, 94, .14);
}
.alarm-overview article.tone-closed .el-icon {
  color: #62d7b1;
  background: rgba(98, 215, 177, .12);
}
.alarm-overview span,
.alarm-overview small {
  display: block;
  color: #8fb1c8;
  font-size: 13px;
}
.alarm-overview strong {
  display: block;
  margin: 4px 0;
  color: #f6fbff;
  font-size: 32px;
  line-height: 34px;
}
.filters {
  justify-content: flex-start;
  margin-top: 18px;
  padding: 14px;
  border: 1px solid rgba(104, 161, 200, .22);
  border-radius: 8px;
  background: #0b1d30;
}
.filters .el-select {
  width: 150px;
}
.filters .el-input {
  max-width: 360px;
}
.table-panel {
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid rgba(104, 161, 200, .18);
  border-radius: 8px;
  background: rgba(11, 29, 48, .72);
}
.table-panel.is-empty {
  border-color: transparent;
  background: transparent;
}
.table-panel :deep(.el-table__inner-wrapper::before),
.table-panel :deep(.el-table__fixed-right::before) {
  display: none;
}
.table-panel :deep(th.el-table__cell) {
  border-bottom: 0;
  background: rgba(30, 58, 95, .58) !important;
}
.table-panel :deep(td.el-table__cell) {
  border-bottom-color: rgba(104, 161, 200, .1);
}
.event-no,
.event-name {
  color: #f3f8fd;
}
.event-summary,
.event-time {
  color: #9cb6ca;
}
.event-status {
  color: #9cb6ca;
}
.event-status.is-pending {
  color: #f0c75d;
}
.event-status.is-processing {
  color: #48d8ff;
}
.event-status.is-completed {
  color: #62d7b1;
}
.event-status.is-false-alarm {
  color: #7e98aa;
}
.detail-link {
  font-weight: 700;
}
.empty-state,
.loading-space {
  min-height: 300px;
  display: grid;
  place-items: center;
}
.empty-state p {
  margin: 4px 0 0;
  color: #68849a;
  font-size: 13px;
}
.table-panel .el-pagination {
  gap: 12px;
  padding: 18px;
  justify-content: center;
}
.table-panel :deep(.el-pagination .btn-prev),
.table-panel :deep(.el-pagination .btn-next),
.table-panel :deep(.el-pager li) {
  width: 48px;
  height: 42px;
  min-width: 48px;
  margin: 0;
  border: 1px solid #214766;
  border-radius: 5px;
  color: #7893aa;
  background: #0a1a2c;
}
.table-panel :deep(.el-pager) {
  display: flex;
  gap: 10px;
}
.table-panel :deep(.el-pager li.is-active) {
  border-color: #61b5ff;
  color: #fff;
  background: #3d8ed8;
}
@media (max-width: 1200px) {
  .alarm-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .events-page {
    padding: 14px;
  }
  .page-header,
  .filters {
    align-items: stretch;
    flex-direction: column;
  }
  .alarm-overview {
    grid-template-columns: 1fr;
  }
  .filters .el-select,
  .filters .el-input {
    width: 100%;
    max-width: none;
  }
}
</style>
