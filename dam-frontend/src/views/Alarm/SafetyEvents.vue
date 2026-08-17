<template>
  <div class="events-page">
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
      <el-select v-model="query.source_type" placeholder="请选择事件来源" @change="onSourceTypeChange">
        <el-option label="全部事件来源" value="all" />
        <el-option label="摄像头" value="camera" />
        <el-option label="传感器" value="sensor" />
      </el-select>
      <el-select
        v-if="query.source_type === 'camera'"
        v-model="query.source_id"
        placeholder="选择摄像头"
        clearable
        @change="onCameraChange"
      >
        <el-option
          v-for="camera in cameraOptions"
          :key="camera.id"
          :label="camera.camera_name || camera.name || camera.id"
          :value="camera.id"
        />
      </el-select>
      <el-select
        v-if="query.source_type === 'sensor' || (query.source_type === 'camera' && query.source_id)"
        v-model="query.event_category"
        placeholder="全部事件类型"
        @change="onCategoryChange"
      >
        <el-option label="全部事件类型" value="all" />
        <el-option
          v-for="event in categoryOptions"
          :key="event.value"
          :label="event.label"
          :value="event.value"
        />
      </el-select>
      <el-select
        v-if="hasCategory"
        v-model="query.risk_level"
        placeholder="全部风险等级"
        @change="onRiskChange"
      >
        <el-option label="全部风险等级" value="all" />
        <el-option label="低风险" value="LOW" />
        <el-option label="中风险" value="MEDIUM" />
        <el-option label="高风险" value="HIGH" />
      </el-select>
      <el-select
        v-if="hasRisk"
        v-model="query.status"
        placeholder="全部处置状态"
        @change="reloadFromFirstPage"
      >
        <el-option label="全部处置状态" value="all" />
        <el-option label="待处理" value="PENDING" />
        <el-option label="处理中" value="PROCESSING" />
        <el-option label="已完成" value="COMPLETED" />
        <el-option label="误报" value="FALSE_ALARM" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        class="date-range-picker"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        popper-class="alarm-date-popper"
        clearable
        @change="onDateRangeChange"
      />
      <el-input
        v-model.trim="query.keyword"
        clearable
        placeholder="搜索事件名称、摘要或来源"
        @clear="reloadFromFirstPage"
        @keyup.enter="reloadFromFirstPage"
      />
      <el-button type="primary" :icon="Search" @click="reloadFromFirstPage">查询</el-button>
      <el-button class="refresh-button" :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button>
    </section>

    <section class="table-panel" :class="{ 'is-empty': !items.length }" v-loading="loading">
      <el-table
        v-if="items.length"
        class="events-table"
        :data="items"
        row-key="id"
        :default-sort="{ prop: 'started_at', order: 'descending' }"
        @sort-change="handleSortChange"
      >
        <el-table-column label="事件编号" prop="id" min-width="176" sortable="custom" align="center" header-align="center">
          <template #default="{ row }">
            <span class="event-no">{{ displayEventNo(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="事件名称" min-width="160" align="center" header-align="center">
          <template #default="{ row }">
            <strong class="event-name">{{ row.event_name || '未命名事件' }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" prop="risk_level" min-width="116" sortable="custom" align="center" header-align="center">
          <template #default="{ row }">
            <el-tag :type="riskTag(row.risk_level)" effect="dark">{{ riskLevelLabel(row.risk_level, row.risk_label) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="108" align="center" header-align="center">
          <template #default="{ row }">
            <span class="source-pill" :class="`is-${row.source_type || 'unknown'}`">{{ sourceLabel(row.source_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="160" align="center" header-align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="isLongSummary(row.summary)"
              :content="row.summary"
              placement="top-start"
            >
              <span class="event-summary">{{ shortSummary(row.summary) }}</span>
            </el-tooltip>
            <span v-else class="event-summary">{{ row.summary || '暂无摘要' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="处置状态" min-width="126" align="center" header-align="center">
          <template #default="{ row }">
            <span class="event-status" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" prop="started_at" min-width="190" sortable="custom" align="center" header-align="center">
          <template #default="{ row }">
            <time class="event-time">{{ formatTime(row.started_at) }}</time>
          </template>
        </el-table-column>
        <el-table-column label="最后完成时间" prop="resolved_at" min-width="190" sortable="custom" align="center" header-align="center">
          <template #default="{ row }">
            <time class="event-time">{{ formatTime(row.resolved_at) }}</time>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="96" fixed="right" align="center" header-align="center">
          <template #default="{ row }">
            <button class="detail-link" type="button" @click="openDetail(row)">
              <span>详情</span>
              <el-icon><ArrowRight /></el-icon>
            </button>
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
import { ArrowRight, BellFilled, Clock, Finished, Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import { getCameraList } from '@/api/camera'
import { getUnifiedSafetyEventCategories, getUnifiedSafetyEvents } from '@/api/integration'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const eventTypeOptions = ref([])
const cameraOptions = ref([])
const dateRange = ref([])
const total = ref(0)
const overview = ref({
  pending: 0,
  high: 0,
  medium: 0,
  low: 0,
  closed: 0,
})
const query = reactive({
  status: 'all',
  risk_level: 'all',
  source_type: 'all',
  event_category: 'all',
  event_date: '',
  source_id: '',
  start_time: '',
  end_time: '',
  keyword: '',
  sort_by: 'time',
  sort_order: 'desc',
  page: 1,
  page_size: 10,
})

const hasActiveFilters = computed(() => {
  return ['status', 'risk_level', 'source_type', 'event_category', 'source_id', 'start_time', 'end_time', 'keyword']
    .some((key) => Boolean(normalizedQueryValue(query[key])))
})
const overviewHint = computed(() => hasActiveFilters.value ? '当前筛选范围' : '全部告警累计')
const overviewCards = computed(() => [
  { label: '事件总数', value: total.value, hint: overviewHint.value, icon: BellFilled, tone: 'tone-total' },
  { label: '待确认', value: overview.value.pending, hint: overviewHint.value, icon: Clock, tone: 'tone-pending' },
  { label: '高风险', value: overview.value.high, hint: overviewHint.value, icon: WarningFilled, tone: 'tone-high' },
  { label: '中风险', value: overview.value.medium, hint: overviewHint.value, icon: WarningFilled, tone: 'tone-medium' },
  { label: '低风险', value: overview.value.low, hint: overviewHint.value, icon: WarningFilled, tone: 'tone-low' },
  { label: '已处置', value: overview.value.closed, hint: overviewHint.value, icon: Finished, tone: 'tone-closed' },
])

async function loadEvents() {
  loading.value = true
  try {
    const [listResult, overviewResult] = await Promise.allSettled([
      getUnifiedSafetyEvents(buildEventQueryParams(), { silentError: true }),
      fetchOverviewCounts(),
    ])
    if (listResult.status === 'rejected') throw listResult.reason
    items.value = listResult.value.data?.items || []
    total.value = listResult.value.data?.total || 0
    if (overviewResult.status === 'fulfilled') {
      overview.value = overviewResult.value
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '告警数据暂时不可达，请检查后端服务')
  } finally {
    loading.value = false
  }
}

function buildEventQueryParams(overrides = {}) {
  return Object.fromEntries(
    Object.entries({ ...query, ...overrides })
      .map(([key, value]) => [key, normalizedQueryValue(value)])
      .filter(([, value]) => value !== '' && value !== null && value !== undefined),
  )
}

function normalizedQueryValue(value) {
  return value === 'all' ? '' : value
}

async function fetchEventCount(overrides = {}) {
  const params = buildEventQueryParams({ ...overrides, page: 1, page_size: 1 })
  const res = await getUnifiedSafetyEvents(params, { silentError: true })
  return Number(res.data?.total || 0)
}

async function fetchOverviewCounts() {
  const statusFilter = normalizedQueryValue(query.status)
  const riskFilter = normalizedQueryValue(query.risk_level)
  const pendingPromise = statusFilter && statusFilter !== 'PENDING'
    ? Promise.resolve(0)
    : fetchEventCount({ status: 'PENDING' })

  const highPromise = riskFilter && riskFilter !== 'HIGH'
    ? Promise.resolve(0)
    : fetchEventCount({ risk_level: 'HIGH' })

  const mediumPromise = riskFilter && riskFilter !== 'MEDIUM'
    ? Promise.resolve(0)
    : fetchEventCount({ risk_level: 'MEDIUM' })

  const lowPromise = riskFilter && riskFilter !== 'LOW'
    ? Promise.resolve(0)
    : fetchEventCount({ risk_level: 'LOW' })

  const closedPromise = statusFilter === 'COMPLETED' || statusFilter === 'FALSE_ALARM'
    ? fetchEventCount({ status: statusFilter })
    : statusFilter
      ? Promise.resolve(0)
      : Promise.all([
        fetchEventCount({ status: 'COMPLETED' }),
        fetchEventCount({ status: 'FALSE_ALARM' }),
      ]).then(([completed, falseAlarm]) => completed + falseAlarm)

  const [pending, high, medium, low, closed] = await Promise.all([
    pendingPromise,
    highPromise,
    mediumPromise,
    lowPromise,
    closedPromise,
  ])
  return { pending, high, medium, low, closed }
}

function reloadFromFirstPage() {
  query.page = 1
  loadEvents()
}

// 事件类型选项：传感器分支仅「极端天气」，摄像头分支按接口动态列表
const categoryOptions = computed(() =>
  query.source_type === 'sensor'
    ? [{ value: 'environment', label: '极端天气' }]
    : eventTypeOptions.value,
)

// 下一级筛选框是否出现：上一级已选择时逐级展开
const hasCategory = computed(() => query.event_category && query.event_category !== 'all')
const hasRisk = computed(() => query.risk_level && query.risk_level !== 'all')

// 级联：选择上一级时清空所有下游筛选并回到第一页
function onSourceTypeChange() {
  query.source_id = ''
  query.event_category = 'all'
  query.risk_level = 'all'
  query.status = 'all'
  reloadFromFirstPage()
}

function onCameraChange() {
  query.event_category = 'all'
  query.risk_level = 'all'
  query.status = 'all'
  reloadFromFirstPage()
}

function onCategoryChange() {
  query.risk_level = 'all'
  query.status = 'all'
  reloadFromFirstPage()
}

function onRiskChange() {
  query.status = 'all'
  reloadFromFirstPage()
}

// 时间范围：写入起止日期后回到第一页
function onDateRangeChange() {
  const [start, end] = dateRange.value || []
  query.start_time = start || ''
  query.end_time = end || ''
  reloadFromFirstPage()
}

function openDetail(row) {
  if (!row?.id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id: row.id } })
}

function handleSortChange({ prop, order }) {
  if (!order) {
    query.sort_by = 'time'
    query.sort_order = 'desc'
    reloadFromFirstPage()
    return
  }
  const sortMap = { id: 'index', risk_level: 'risk', started_at: 'time', resolved_at: 'resolved' }
  query.sort_by = sortMap[prop] || 'time'
  query.sort_order = order === 'ascending' ? 'asc' : 'desc'
  reloadFromFirstPage()
}

function displayEventNo(row) {
  if (!row) return ''
  return row.display_instance_no || normalizeInstanceNo(row.instance_no, row.started_at)
}

function normalizeInstanceNo(value, fallbackDate) {
  const text = String(value || '').trim()
  const date = dateToken(text) || dateToken(fallbackDate)
  if (!date) return text
  const numericSequence = instanceSequence(text)
  const sequence = numericSequence || 1
  return `EVT_${date}_${String(sequence).padStart(3, '0')}`
}

function dateToken(value) {
  if (!value) return ''
  const direct = String(value).match(/20\d{6}/)
  if (direct) return direct[0]
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

function instanceSequence(value) {
  const matched = String(value || '').match(/_(\d{1,4})$/)
  return matched?.[1] || ''
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

function sourceLabel(value) {
  return ({ sensor: '传感器', camera: '摄像头' })[String(value || '').toLowerCase()] || '--'
}

function shortSummary(value) {
  const text = String(value || '')
  return text.length > 15 ? `${text.slice(0, 15)}...` : text
}

function isLongSummary(value) {
  return String(value || '').length > 15
}

function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

async function loadEventTypes() {
  try {
    const res = await getUnifiedSafetyEventCategories()
    const rows = res.data?.items || []
    eventTypeOptions.value = rows
      .filter((item) => item.value && item.label)
      .sort((a, b) => String(a.label).localeCompare(String(b.label), 'zh-CN'))
  } catch (error) {
    eventTypeOptions.value = []
  }
}

async function loadCameras() {
  try {
    const res = await getCameraList()
    cameraOptions.value = res.data?.cameras || []
  } catch (error) {
    cameraOptions.value = []
  }
}

loadEventTypes()
loadCameras()
loadEvents()
</script>

<style scoped>
.events-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.alarm-overview {
  display: grid;
  grid-template-columns: repeat(6, minmax(160px, 1fr));
  gap: 16px;
}
.alarm-overview article {
  position: relative;
  min-height: 124px;
  padding: 18px 18px 16px;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  overflow: hidden;
  border: 1px solid rgba(104, 161, 200, .26);
  border-radius: 8px;
  background:
    linear-gradient(145deg, rgba(28, 68, 103, .72), rgba(8, 25, 42, .92)),
    #0b1d30;
  box-shadow: 0 18px 34px rgba(0, 0, 0, .22);
}
.alarm-overview article::after {
  content: "";
  position: absolute;
  inset: auto 16px 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: #48d8ff;
  opacity: .72;
}
.alarm-overview .el-icon {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  color: #48d8ff;
  background: rgba(72, 216, 255, .12);
  font-size: 25px;
  box-shadow: inset 0 0 0 1px rgba(72, 216, 255, .18);
}
.alarm-overview article.tone-pending::after {
  background: #f0c75d;
}
.alarm-overview article.tone-pending .el-icon {
  color: #f0c75d;
  background: rgba(240, 199, 93, .13);
  box-shadow: inset 0 0 0 1px rgba(240, 199, 93, .22);
}
.alarm-overview article.tone-high::after {
  background: #ff6b76;
}
.alarm-overview article.tone-high .el-icon {
  color: #ff6b76;
  background: rgba(255, 77, 94, .14);
  box-shadow: inset 0 0 0 1px rgba(255, 77, 94, .24);
}
.alarm-overview article.tone-medium::after {
  background: #FFB648;
}
.alarm-overview article.tone-medium .el-icon {
  color: #FFB648;
  background: rgba(255, 182, 72, .14);
  box-shadow: inset 0 0 0 1px rgba(255, 182, 72, .24);
}
.alarm-overview article.tone-low::after {
  background: #38D59C;
}
.alarm-overview article.tone-low .el-icon {
  color: #38D59C;
  background: rgba(56, 213, 156, .13);
  box-shadow: inset 0 0 0 1px rgba(56, 213, 156, .22);
}
.alarm-overview article.tone-closed::after {
  background: #62d7b1;
}
.alarm-overview article.tone-closed .el-icon {
  color: #62d7b1;
  background: rgba(98, 215, 177, .12);
  box-shadow: inset 0 0 0 1px rgba(98, 215, 177, .22);
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
  font-size: 34px;
  line-height: 36px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
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
.filters .date-range-picker {
  width: 228px;
}
.filters .el-input {
  max-width: 360px;
}
.filters :deep(.el-select),
.filters :deep(.el-date-editor),
.filters :deep(.el-input) {
  height: 44px;
  border: 0;
  background: transparent;
}
.filters :deep(.el-select__wrapper),
.filters :deep(.el-input__wrapper) {
  min-height: 44px;
  border-radius: 6px;
  background: rgba(6, 25, 42, .82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, .46) !important;
}
.filters :deep(.el-select__wrapper:hover),
.filters :deep(.el-input__wrapper:hover),
.filters :deep(.el-select__wrapper.is-focused),
.filters :deep(.el-select__wrapper.is-focus),
.filters :deep(.el-input__wrapper.is-focused),
.filters :deep(.el-input__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px rgba(87, 190, 255, .82), 0 0 0 2px rgba(72, 216, 255, .08) !important;
}
.filters :deep(.el-input__inner) {
  color: #d9e8f8;
  font-weight: 500;
}
.filters :deep(.el-select__selected-item),
.filters :deep(.el-select__placeholder) {
  color: #d9e8f8;
  font-weight: 500;
}
.filters :deep(.el-select__caret),
.filters :deep(.el-input__suffix) {
  color: #6faed1;
}
.filters :deep(.el-input__inner::placeholder) {
  color: #d9e8f8;
}
.refresh-button {
  margin-left: auto;
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
.table-panel :deep(th.el-table__cell .cell) {
  line-height: 22px;
}
.table-panel :deep(.el-table__row) {
  height: 72px;
}
.table-panel :deep(td.el-table__cell) {
  padding: 12px 0;
  border-bottom-color: rgba(104, 161, 200, .1);
}
.event-no,
.event-name {
  color: #f3f8fd;
}
.event-no {
  display: inline-block;
  white-space: nowrap;
}
.event-summary,
.event-time {
  color: #9cb6ca;
}
.event-summary {
  display: inline-block;
  max-width: 100%;
  vertical-align: middle;
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
.source-pill {
  display: inline-flex;
  align-items: center;
  min-width: 58px;
  height: 26px;
  justify-content: center;
  border: 1px solid rgba(72, 216, 255, .22);
  border-radius: 5px;
  color: #aee8ff;
  background: rgba(72, 216, 255, .08);
  font-size: 13px;
  font-weight: 700;
}
.source-pill.is-sensor {
  border-color: rgba(98, 215, 177, .24);
  color: #b8f3dc;
  background: rgba(98, 215, 177, .08);
}
.detail-link {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  color: #7dd7ff;
  background: transparent;
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
}
.detail-link .el-icon {
  font-size: 15px;
  transition: transform .16s ease;
}
.detail-link:hover {
  color: #c7f0ff;
}
.detail-link:hover .el-icon {
  transform: translateX(2px);
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
  .filters {
    align-items: stretch;
    flex-direction: column;
  }
  .alarm-overview {
    grid-template-columns: 1fr;
  }
  .filters .el-select,
  .filters .event-date-picker,
  .filters .el-input {
    width: 100%;
    max-width: none;
  }
  .refresh-button {
    margin-left: 0;
  }
}
</style>
