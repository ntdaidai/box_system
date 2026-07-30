<template>
  <div class="safety-page">
    <section class="toolbar">
      <el-select v-model="query.disposal_status" clearable placeholder="处置状态" class="w-180">
        <el-option label="系统自动处理中" value="AUTO_HANDLING" />
        <el-option label="无人设备处置中" value="DEVICE_HANDLING" />
        <el-option label="等待人工接单" value="WAITING_MANUAL" />
        <el-option label="人工处置中" value="MANUAL_HANDLING" />
        <el-option label="已解除" value="RESOLVED" />
        <el-option label="处置失败" value="FAILED" />
      </el-select>
      <el-select v-model="query.risk_level" clearable placeholder="风险等级" class="w-140">
        <el-option label="低风险" value="LOW" />
        <el-option label="中风险" value="MEDIUM" />
        <el-option label="高风险" value="HIGH" />
      </el-select>
      <el-input v-model="query.keyword" clearable placeholder="事件编号 / 摄像头 / 类型" class="keyword" />
      <el-button type="primary" :icon="Search" @click="reload">查询</el-button>
      <el-button :icon="Refresh" @click="reset">重置</el-button>
      <div class="report-tools">
        <el-date-picker
          v-model="reportDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日报日期"
          class="report-date-picker"
          popper-class="safety-report-date-popper"
          :disabled-date="disableReportDate"
          :clearable="false"
        />
        <el-button
          class="report-generate-btn"
          :disabled="!reportDate"
          :loading="reportGenerating"
          @click="generateReport"
        >
          <el-icon><Document /></el-icon>
          生成巡查日报
        </el-button>
      </div>
    </section>

    <section class="metric-row">
      <div class="metric high"><span>高风险</span><b>{{ metrics.high }}</b></div>
      <div class="metric processing"><span>处置中</span><b>{{ metrics.processing }}</b></div>
      <div class="metric pending"><span>待确认</span><b>{{ metrics.pending }}</b></div>
      <div class="metric closed"><span>已闭环</span><b>{{ metrics.closed }}</b></div>
    </section>

    <el-table
      v-loading="loading"
      :data="events"
      height="calc(100vh - 315px)"
      class="event-table"
      @row-click="openDetail"
    >
      <el-table-column label="风险" width="110">
        <template #default="{ row }">
          <el-tag :type="riskTagType(row.risk_level)" effect="dark">{{ riskText(row.risk_level) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处置状态" width="150">
        <template #default="{ row }">
          <el-tag :type="disposalTagType(row.disposal_status)">{{ disposalStatusText(row.disposal_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="camera_name" label="摄像头" min-width="150" show-overflow-tooltip />
      <el-table-column prop="event_type" label="事件类型" min-width="150" show-overflow-tooltip />
      <el-table-column label="留证" width="92">
        <template #default="{ row }">
          <el-tag :type="videoStatusTagType(row.video_status, row.video_url)">
            {{ videoStatusText(row.video_status, row.video_url) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="170">
        <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="持续时间" width="110">
        <template #default="{ row }">{{ formatDuration(row.duration_seconds) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @change="loadEvents"
      />
    </div>

    <el-drawer v-model="drawerVisible" title="安全事件详情" size="860px" class="safety-drawer">
      <div v-if="currentEvent" class="detail">
        <section class="media-grid">
          <div class="media-box">
            <header>现场截图</header>
            <img v-if="currentEvent.snapshot_url" :src="assetUrl(currentEvent.snapshot_url)" alt="现场截图" />
            <el-empty v-else description="暂无截图" />
          </div>
          <div class="media-box">
            <header>
              <span>事件录像</span>
              <el-button
                v-if="currentEvent.video_url"
                link
                type="primary"
                :icon="Download"
                @click="downloadVideo"
              >
                下载
              </el-button>
            </header>
            <video v-if="currentEvent.video_url" :src="assetUrl(currentEvent.video_url)" controls />
            <el-empty v-else :description="videoEmptyText(currentEvent)" />
          </div>
        </section>

        <section class="info-grid">
          <div><span>风险等级</span><b :class="`risk-${currentEvent.risk_level}`">{{ riskText(currentEvent.risk_level) }}</b></div>
          <div><span>处置责任</span><b>{{ handlingModeText(currentEvent.handling_mode) }}</b></div>
          <div><span>处置状态</span><b>{{ disposalStatusText(currentEvent.disposal_status) }}</b></div>
          <div><span>目标状态</span><b>{{ targetStatusText(currentEvent.target_status) }}</b></div>
          <div><span>摄像头</span><b>{{ currentEvent.camera_name || currentEvent.camera_id }}</b></div>
          <div><span>事件类型</span><b>{{ currentEvent.event_type }}</b></div>
          <div><span>开始时间</span><b>{{ formatTime(currentEvent.started_at) }}</b></div>
          <div><span>持续时间</span><b>{{ formatDuration(currentEvent.duration_seconds) }}</b></div>
          <div><span>当前状态</span><b>{{ statusText(currentEvent.status) }}</b></div>
          <div><span>事件编号</span><b>{{ currentEvent.event_id }}</b></div>
          <div><span>操作人员</span><b>{{ operatorNames || '-' }}</b></div>
        </section>

        <section v-if="requiresManual" class="action-row">
          <el-button type="primary" :disabled="!canAck" :icon="Check" @click="ack">接受任务</el-button>
          <el-button :disabled="isClosed" :icon="Microphone" @click="broadcast">一键喊话</el-button>
          <el-button :disabled="isClosed" :icon="User" @click="complete">现场处置</el-button>
          <el-button type="warning" :disabled="isClosed" :icon="Warning" @click="falseAlarm">标记误报</el-button>
          <el-button type="success" :disabled="isClosed" :icon="CircleCheck" @click="resolve">确认解除</el-button>
        </section>
        <section v-else class="auto-note">
          {{ riskText(currentEvent.risk_level) }}事件由{{ handlingModeText(currentEvent.handling_mode) }}处理，无需人工处置
        </section>

        <section class="timeline">
          <h3>处置时间轴</h3>
          <el-timeline>
            <el-timeline-item
              v-for="item in timeline"
              :key="item.action_id"
              :timestamp="formatTime(item.created_at)"
              :type="timelineType(item.action_type)"
            >
              <div class="timeline-card">
                <strong>{{ actionText(item.action_type) }}</strong>
                <small>{{ item.operator || 'EventEngine' }} · {{ statusText(item.from_status) }} → {{ statusText(item.to_status) }}</small>
                <p>{{ item.message || '-' }}</p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </section>
      </div>
    </el-drawer>
    <BroadcastDialog
      v-model="broadcastDialogVisible"
      :event="broadcastTargetEvent"
      @played="handleBroadcastPlayed"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, CircleCheck, Document, Download, Microphone, Refresh, Search, User, Warning } from '@element-plus/icons-vue'
import axios from 'axios'
import BroadcastDialog from '@/components/BroadcastDialog.vue'
import {
  acceptSafetyEvent,
  completeSafetyEvent,
  getSafetyEventDetail,
  getSafetyEvents,
  markSafetyEventFalseAlarm,
  resolveSafetyEvent,
} from '@/api/camera'

const router = useRouter()
const loading = ref(false)
const broadcastDialogVisible = ref(false)
const broadcastTargetEvent = ref(null)
const events = ref([])
const total = ref(0)
const drawerVisible = ref(false)
const currentEvent = ref(null)
const timeline = ref([])
const tasks = ref([])
const ws = ref(null)
const closedByUser = ref(false)
const reportDate = ref(yesterdayString())
const reportGenerating = ref(false)
const currentUser = ref({
  id: 'user_001',
  name: '管理员',
})

const query = reactive({
  disposal_status: '',
  risk_level: '',
  keyword: '',
  page: 1,
  page_size: 20,
})

const metrics = computed(() => events.value.reduce((acc, event) => {
  if (event.risk_level === 'HIGH') acc.high += 1
  if (['DEVICE_HANDLING', 'MANUAL_HANDLING', 'AUTO_HANDLING'].includes(event.disposal_status)) acc.processing += 1
  if (event.disposal_status === 'WAITING_MANUAL') acc.pending += 1
  if (['RESOLVED', 'FAILED'].includes(event.disposal_status)) acc.closed += 1
  return acc
}, { high: 0, processing: 0, pending: 0, closed: 0 }))

const isClosed = computed(() => currentEvent.value && ['RESOLVED', 'FALSE_ALARM'].includes(currentEvent.value.status))
const requiresManual = computed(() => currentEvent.value?.risk_level === 'HIGH' || currentEvent.value?.handling_mode === 'MANUAL')
const canAck = computed(() => requiresManual.value && currentEvent.value?.disposal_status === 'WAITING_MANUAL')
const operatorNames = computed(() => {
  const names = new Set()
  timeline.value.forEach((item) => {
    if (item.operator) names.add(item.operator)
  })
  tasks.value.forEach((item) => {
    if (item.dispatch_operator) names.add(item.dispatch_operator)
    if (item.assignee) names.add(item.assignee)
  })
  return Array.from(names).join('、')
})

onMounted(() => {
  loadEvents()
  connectWs()
})

onBeforeUnmount(() => {
  closedByUser.value = true
  if (ws.value) ws.value.close()
})

async function loadEvents() {
  loading.value = true
  try {
    const res = await getSafetyEvents({ ...query })
    events.value = res.data?.items || res.data?.events || []
    total.value = res.data?.total || events.value.length
  } finally {
    loading.value = false
  }
}

function formatLocalDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function yesterdayString() {
  const date = new Date()
  date.setDate(date.getDate() - 1)
  return formatLocalDate(date)
}

function maxReportDateTime() {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  return date.getTime() - 1
}

function disableReportDate(date) {
  return date.getTime() > maxReportDateTime()
}

async function generateReport() {
  if (!reportDate.value) {
    ElMessage.warning('请选择昨天或更早的日报日期')
    return
  }

  if (new Date(`${reportDate.value}T00:00:00`).getTime() > maxReportDateTime()) {
    ElMessage.warning('日报日期只能选择昨天及以前')
    return
  }

  reportGenerating.value = true
  try {
    const response = await axios.post('/api/patrol-report/daily/generate', {
      report_date: reportDate.value,
      user_id: currentUser.value.id,
      user_name: currentUser.value.name,
    }, {
      timeout: 120000,
    })

    if (!response.data?.success) {
      throw new Error(response.data?.message || '生成巡查日报失败')
    }

    ElMessage.success('巡查日报已生成，DOCX 与 PDF 已进入文档中心')
    router.push({
      path: '/document/hub',
      query: {
        reportDate: reportDate.value,
        reportDoc: response.data.data?.docx?.document_id || '',
      },
    })
  } catch (error) {
    console.error('生成巡查日报失败:', error)
    ElMessage.error(error.response?.data?.detail || error.message || '生成巡查日报失败')
  } finally {
    reportGenerating.value = false
  }
}

function reload() {
  query.page = 1
  loadEvents()
}

function reset() {
  query.disposal_status = ''
  query.risk_level = ''
  query.keyword = ''
  query.page = 1
  loadEvents()
}

async function openDetail(row) {
  const res = await getSafetyEventDetail(row.event_id)
  currentEvent.value = res.data?.event || null
  timeline.value = res.data?.timeline || []
  tasks.value = res.data?.tasks || []
  drawerVisible.value = true
}

async function refreshCurrent() {
  await loadEvents()
  if (currentEvent.value?.event_id) {
    await openDetail(currentEvent.value)
  }
}

function payload(extra = {}) {
  return {
    version: currentEvent.value?.version,
    ...extra,
  }
}

async function ack() {
  await acceptSafetyEvent(currentEvent.value.event_id, payload({ remark: '工作人员接受人工处置任务' }))
  ElMessage.success('已接受任务')
  await refreshCurrent()
}

async function broadcast() {
  broadcastTargetEvent.value = currentEvent.value
  broadcastDialogVisible.value = true
}

async function handleBroadcastPlayed() {
  ElMessage.success('已执行人工语音喊话')
  await refreshCurrent()
}

async function complete() {
  const { value } = await ElMessageBox.prompt('请输入现场处置说明', '现场处置', {
    inputValue: '现场人员完成驱离处置',
    confirmButtonText: '记录完成',
    cancelButtonText: '取消',
  })
  await completeSafetyEvent(currentEvent.value.event_id, payload({ remark: value }))
  ElMessage.success('已记录现场处置完成')
  await refreshCurrent()
}

async function falseAlarm() {
  const { value } = await ElMessageBox.prompt('请输入误报原因', '标记误报', {
    inputValue: '现场复核为误报',
    confirmButtonText: '确认误报',
    cancelButtonText: '取消',
  })
  await markSafetyEventFalseAlarm(currentEvent.value.event_id, payload({ reason: value, remark: value }))
  ElMessage.success('已标记误报')
  await refreshCurrent()
}

async function resolve() {
  const { value } = await ElMessageBox.prompt('请输入解除说明', '确认解除', {
    inputValue: '危险目标已离开，现场确认无风险',
    confirmButtonText: '解除',
    cancelButtonText: '取消',
  })
  await resolveSafetyEvent(currentEvent.value.event_id, payload({ remark: value }))
  ElMessage.success('事件已解除')
  await refreshCurrent()
}

function connectWs() {
  closedByUser.value = false
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  ws.value = new WebSocket(`${protocol}://${window.location.host}/api/v1/camera/safety/ws`)
  ws.value.onmessage = (event) => {
    try {
      const payloadData = JSON.parse(event.data)
      if (payloadData.type === 'CONNECTED') return
      loadEvents()
      const eventId = payloadData.data?.event_id
      if (currentEvent.value?.event_id && eventId === currentEvent.value.event_id) {
        openDetail(currentEvent.value)
      }
    } catch (error) {
      console.warn('安全事件WebSocket消息解析失败', error)
    }
  }
  ws.value.onclose = () => {
    if (!closedByUser.value) setTimeout(connectWs, 3000)
  }
}

function assetUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//.test(url) || url.startsWith('/')) return url
  return `/${url}`
}

function downloadVideo() {
  if (!currentEvent.value?.video_url) return
  const link = document.createElement('a')
  link.href = assetUrl(currentEvent.value.video_url)
  link.download = `${currentEvent.value.event_id || 'safety-event'}.mp4`
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function riskText(level) {
  return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', NONE: '安全' })[level] || level || '-'
}

function statusText(status) {
  return ({
    PENDING: '待确认',
    PROCESSING: '处置中',
    RESOLVED: '已解除',
    FALSE_ALARM: '误报',
  })[status] || status || '-'
}

function handlingModeText(mode) {
  return ({
    AUTO: '系统自动',
    AUTO_DEVICE: '无人设备自动',
    MANUAL: '人工',
  })[mode] || mode || '-'
}

function disposalStatusText(status) {
  return ({
    MONITORING: '持续监测',
    AUTO_HANDLING: '系统自动处理中',
    DEVICE_HANDLING: '无人设备自动处置中',
    WAITING_MANUAL: '等待工作人员接单',
    MANUAL_HANDLING: '人工处置中',
    RESOLVED: '已解除',
    FAILED: '处置失败',
  })[status] || status || '-'
}

function targetStatusText(status) {
  return ({
    IN_DANGER: '仍在风险区',
    LEFT: '已离开',
  })[status] || status || '-'
}

function videoStatusText(status, url = '') {
  if (url) return '已留证'
  return ({
    PENDING: '待生成',
    GENERATING: '生成中',
    READY: '已留证',
    FAILED: '生成失败',
  })[status] || '待生成'
}

function videoStatusTagType(status, url = '') {
  if (url || status === 'READY') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'GENERATING') return 'warning'
  return 'info'
}

function videoEmptyText(event) {
  if (event?.video_status === 'FAILED') return event.video_error || '留证视频生成失败'
  if (event?.video_status === 'GENERATING') return '留证视频生成中'
  return '暂无录像'
}

function actionText(type) {
  return ({
    AI_DETECTED: 'AI检测',
    RISK_LOW: '低风险判定',
    RISK_MEDIUM: '中风险判定',
    RISK_HIGH: '高风险判定',
    AUTO_BROADCAST: '自动喊话',
    DRONE_DISPATCH: '无人机派飞',
    STAFF_DISPATCH: '创建人工任务',
    MANUAL_BROADCAST: '人工喊话',
    USER_ACK: '人工确认',
    STAFF_ACCEPTED: '工作人员接单',
    STAFF_COMPLETED: '现场处置完成',
    TASK_DISPATCH: '派现场人员',
    TARGET_LEFT: '目标离开',
    AUTO_RESOLVED: '自动解除',
    MANUAL_RESOLVED: '人工解除',
    FALSE_ALARM: '误报确认',
  })[type] || type || '-'
}

function riskTagType(level) {
  return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[level] || 'info'
}

function statusTagType(status) {
  return ({ PENDING: 'primary', PROCESSING: 'warning', RESOLVED: 'success', FALSE_ALARM: 'info' })[status] || 'info'
}

function disposalTagType(status) {
  return ({
    AUTO_HANDLING: 'success',
    DEVICE_HANDLING: 'warning',
    WAITING_MANUAL: 'danger',
    MANUAL_HANDLING: 'warning',
    RESOLVED: 'success',
    FAILED: 'danger',
  })[status] || 'info'
}

function timelineType(type) {
  if (['RISK_HIGH', 'FALSE_ALARM'].includes(type)) return 'danger'
  if (['RISK_MEDIUM', 'TASK_DISPATCH', 'MANUAL_BROADCAST'].includes(type)) return 'warning'
  if (['AUTO_RESOLVED', 'MANUAL_RESOLVED'].includes(type)) return 'success'
  return 'primary'
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(Number(value) * 1000)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(seconds) {
  const value = Number(seconds || 0)
  const h = Math.floor(value / 3600)
  const m = Math.floor((value % 3600) / 60)
  const s = value % 60
  if (h) return `${h}时${m}分${s}秒`
  if (m) return `${m}分${s}秒`
  return `${s}秒`
}
</script>

<style scoped>
.safety-page {
  height: 100%;
  padding: 18px;
  background:
    radial-gradient(circle at 18% 0%, rgba(27, 105, 150, 0.22), transparent 30%),
    linear-gradient(180deg, #071625 0%, #08121f 100%);
  color: #dce9fa;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid rgba(0, 200, 255, 0.16);
  border-radius: 8px;
  background: rgba(12, 31, 55, 0.82);
  box-shadow: inset 0 0 0 1px rgba(116, 201, 249, 0.04);
}

.w-140 {
  width: 140px;
}

.w-180 {
  width: 180px;
}

.keyword {
  width: 280px;
}

.report-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.report-date-picker {
  width: 170px;
}

.report-generate-btn {
  height: 36px;
  min-width: 148px;
  color: #dce9fa;
  background: rgba(22, 54, 93, 0.82);
  border-color: rgba(88, 156, 222, 0.42);
  font-weight: 700;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 76px;
  padding: 0 20px;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 6px;
  background: linear-gradient(145deg, rgba(16, 34, 61, 0.96), rgba(9, 23, 43, 0.96));
  box-shadow: inset 0 0 0 1px rgba(74, 182, 255, 0.05);
}

.metric span {
  color: #8ea8c9;
}

.metric b {
  font-size: 32px;
}

.metric.high b { color: #d93030; }
.metric.processing b { color: #c47a00; }
.metric.pending b { color: #1c6fd8; }
.metric.closed b { color: #1f8f53; }

.event-table {
  border: 1px solid rgba(88, 137, 205, 0.26);
  border-radius: 6px;
  background: rgba(12, 31, 55, 0.72);
  color: #dce9fa;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 14px 0 0;
}

.toolbar :deep(.el-select__wrapper),
.toolbar :deep(.el-input__wrapper) {
  min-height: 36px;
  border-radius: 6px;
  background: rgba(6, 20, 38, 0.9);
  box-shadow: 0 0 0 1px rgba(89, 155, 255, 0.28) inset;
}

.toolbar :deep(.el-select__wrapper.is-focused),
.toolbar :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px rgba(0, 214, 255, 0.72) inset;
}

.toolbar :deep(.el-select__placeholder),
.toolbar :deep(.el-input__inner) {
  color: #dce9fa;
}

.toolbar :deep(.el-input__inner::placeholder) {
  color: rgba(174, 202, 245, 0.62);
}

:global(.safety-report-date-popper.el-picker__popper),
:global(.safety-report-date-popper .el-picker-panel),
:global(.safety-report-date-popper .el-date-picker) {
  color: #dce9fa;
  background: #0a1e30 !important;
  border-color: rgba(0, 200, 255, 0.25) !important;
}

:global(.safety-report-date-popper.el-popper.is-light),
:global(.safety-report-date-popper.el-popper.is-pure) {
  background: #0a1e30 !important;
  border: 1px solid rgba(0, 200, 255, 0.25) !important;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
}

:global(.safety-report-date-popper .el-popper__arrow::before) {
  background: #0a1e30 !important;
  border-color: rgba(0, 200, 255, 0.25) !important;
}

:global(.safety-report-date-popper .el-picker-panel__body-wrapper),
:global(.safety-report-date-popper .el-picker-panel__body),
:global(.safety-report-date-popper .el-picker-panel__content) {
  background: #0a1e30 !important;
}

:global(.safety-report-date-popper .el-date-picker__header-label),
:global(.safety-report-date-popper .el-picker-panel__icon-btn),
:global(.safety-report-date-popper .el-date-table th),
:global(.safety-report-date-popper .el-date-table td .el-date-table-cell__text) {
  color: #dce9fa !important;
}

:global(.safety-report-date-popper .el-date-table td.disabled .el-date-table-cell__text) {
  color: rgba(142, 168, 201, 0.45) !important;
}

:global(.safety-report-date-popper .el-date-table td.current:not(.disabled) .el-date-table-cell__text) {
  color: #fff !important;
  background: #3da4ff !important;
}

.event-table :deep(.el-table__inner-wrapper::before),
.event-table :deep(.el-table__border-left-patch) {
  display: none;
}

.event-table :deep(.el-table__header-wrapper th),
.event-table :deep(.el-table__fixed-header-wrapper th) {
  background: rgba(18, 42, 72, 0.98);
  color: #b7d8ff;
  border-bottom-color: rgba(88, 137, 205, 0.22);
}

.event-table :deep(.el-table__body-wrapper tr),
.event-table :deep(.el-table__fixed-body-wrapper tr),
.event-table :deep(.el-table__body-wrapper td),
.event-table :deep(.el-table__fixed-body-wrapper td) {
  background: rgba(10, 25, 46, 0.96);
  color: #dce9fa;
  border-bottom-color: rgba(88, 137, 205, 0.14);
}

.event-table :deep(.el-table__body tr:hover > td),
.event-table :deep(.el-table__fixed-body-wrapper tr:hover > td) {
  background: rgba(28, 68, 110, 0.98);
}

.pager :deep(.el-pagination) {
  --el-pagination-bg-color: rgba(12, 31, 55, 0.86);
  --el-pagination-button-bg-color: rgba(12, 31, 55, 0.86);
  --el-pagination-text-color: #a8bdd8;
  --el-pagination-button-color: #dce9fa;
  --el-pagination-hover-color: #20d7ff;
}

.media-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.media-box {
  min-height: 236px;
  padding: 12px;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 6px;
  background: rgba(8, 22, 40, 0.72);
}

.media-box header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
  margin-bottom: 10px;
  color: #dce9fa;
  font-weight: 700;
}

.media-box img,
.media-box video {
  width: 100%;
  height: 190px;
  object-fit: contain;
  background: #101828;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  margin: 18px 0;
}

.info-grid div {
  min-height: 54px;
  padding: 8px 10px;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 6px;
  background: rgba(8, 22, 40, 0.72);
}

.info-grid span {
  display: block;
  color: #8ea8c9;
  font-size: 12px;
}

.info-grid b {
  display: block;
  margin-top: 5px;
  color: #f4f8ff;
}

.info-grid .risk-HIGH { color: #d93030; }
.info-grid .risk-MEDIUM { color: #b26a00; }
.info-grid .risk-LOW { color: #16824a; }

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 22px;
}

.auto-note {
  margin-bottom: 22px;
  padding: 10px 12px;
  border: 1px solid rgba(98, 215, 177, 0.2);
  border-radius: 6px;
  color: #b9e7d6;
  background: rgba(25, 69, 58, 0.38);
  font-weight: 700;
}

.timeline h3 {
  margin: 0 0 14px;
  color: #f4f8ff;
}

.timeline-card strong {
  display: block;
  color: #f4f8ff;
}

.timeline-card small {
  display: block;
  margin-top: 3px;
  color: #8ea8c9;
}

.timeline-card p {
  margin: 6px 0 0;
  color: #b7cae4;
}

:global(.safety-drawer.el-drawer) {
  background: linear-gradient(180deg, #0c1f37 0%, #081522 100%);
  color: #dce9fa;
}

:global(.safety-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(88, 137, 205, 0.24);
  color: #f4f8ff;
}

:global(.safety-drawer .el-drawer__body) {
  padding: 18px 22px;
}

:global(.safety-drawer .el-empty__description p) {
  color: #8ea8c9;
}
</style>
