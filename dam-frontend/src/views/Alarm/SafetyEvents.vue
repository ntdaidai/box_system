<template>
  <div class="events-page">
    <header class="page-header"><div><p>告警管理 / 安全事件</p><h2>安全事件实例</h2></div><el-button :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button></header>
    <section class="filters"><el-select v-model="query.status" clearable placeholder="处置状态"><el-option label="待处理" value="PENDING" /><el-option label="处理中" value="PROCESSING" /><el-option label="已完成" value="COMPLETED" /><el-option label="误报" value="FALSE_ALARM" /></el-select><el-select v-model="query.risk_level" clearable placeholder="风险等级"><el-option label="低风险" value="LOW" /><el-option label="中风险" value="MEDIUM" /><el-option label="高风险" value="HIGH" /></el-select><el-input v-model.trim="query.keyword" clearable placeholder="事件编号、名称或摘要" @keyup.enter="loadEvents" /><el-button type="primary" :icon="Search" @click="loadEvents">查询</el-button></section>
    <section class="table-panel" v-loading="loading">
      <el-table :data="items" row-key="id" empty-text="暂无安全事件">
        <el-table-column prop="instance_no" label="事件编号" min-width="190" />
        <el-table-column prop="event_name" label="事件名称" width="150" />
        <el-table-column prop="summary" label="摘要" min-width="230" show-overflow-tooltip />
        <el-table-column label="风险" width="100"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)">{{ row.risk_label }}</el-tag></template></el-table-column>
        <el-table-column label="处置状态" width="110"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
        <el-table-column label="开始时间" width="175"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
        <el-table-column label="操作" width="95" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">详情</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" v-model:page-size="query.page_size" layout="total, prev, pager, next" :total="total" @current-change="loadEvents" />
    </section>

    <el-drawer v-model="detailVisible" title="安全事件详情" size="min(760px, 92vw)">
      <template v-if="detail.event">
        <div class="summary-grid"><div><span>事件</span><strong>{{ detail.event.event_name }}</strong></div><div><span>风险</span><strong>{{ detail.event.risk_label }}</strong></div><div><span>状态</span><strong>{{ statusLabel(detail.event.status) }}</strong></div><div><span>来源</span><strong>{{ detail.visual_detail?.camera_name || '传感器数据源' }}</strong></div></div>
        <section v-if="detail.visual_detail" class="detail-section"><h3>视觉信息</h3><el-descriptions :column="2" border><el-descriptions-item label="目标类型">{{ targetLabel(detail.visual_detail.target_type) }}</el-descriptions-item><el-descriptions-item label="目标轨迹">{{ detail.visual_detail.target_id || '--' }}</el-descriptions-item><el-descriptions-item label="区域">{{ detail.visual_detail.zone_name || '--' }}</el-descriptions-item><el-descriptions-item label="置信度">{{ confidenceText(detail.visual_detail.confidence) }}</el-descriptions-item></el-descriptions></section>
        <section class="detail-section"><h3>事件时间线</h3><el-timeline><el-timeline-item v-for="item in detail.timeline" :key="item.id" :timestamp="formatTime(item.create_time)" :type="timelineType(item.log_type)"><div class="timeline-row"><div><strong>{{ logTypeLabel(item.log_type) }}</strong><p>{{ item.message }}</p><small>{{ item.operator === 'SYSTEM' ? '系统自动' : item.operator }}</small></div><el-button v-if="item.has_evidence" link type="primary" :icon="Picture" @click="showEvidence(item.id)">查看证据</el-button></div></el-timeline-item></el-timeline></section>
        <section v-if="detail.tasks?.length" class="detail-section"><h3>人工处置任务</h3><el-table :data="detail.tasks"><el-table-column prop="assignee" label="处置人" /><el-table-column prop="note" label="任务说明" /><el-table-column label="状态"><template #default="{ row }">{{ taskStatusLabel(row.status) }}</template></el-table-column><el-table-column prop="result_remark" label="处置结果" /></el-table></section>
        <div v-if="detail.event.state === 'ACTIVE'" class="drawer-actions"><el-button type="warning" @click="operate('UPGRADE')">升级风险</el-button><el-button type="info" @click="operate('FALSE_ALARM')">标记误报</el-button><el-button type="success" @click="operate('RESOLVE')">人工闭环</el-button></div>
      </template>
    </el-drawer>

    <el-dialog v-model="evidenceVisible" title="图像证据" width="720px"><div class="evidence-grid"><figure v-for="item in currentEvidence" :key="item.id"><el-image :src="item.file_url" fit="contain" :preview-src-list="currentEvidence.map(e => e.file_url)" /><figcaption>{{ item.description || sourceLabel(item.source_type) }} · {{ formatTime(item.captured_at) }}</figcaption></figure></div></el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Refresh, Search } from '@element-plus/icons-vue'
import { getUnifiedSafetyEventDetail, getUnifiedSafetyEvents, operateUnifiedSafetyEvent } from '@/api/integration'

const loading = ref(false), items = ref([]), total = ref(0), detailVisible = ref(false), evidenceVisible = ref(false), currentEvidence = ref([])
const query = reactive({ status: '', risk_level: '', keyword: '', page: 1, page_size: 20 })
const detail = reactive({ event: null, visual_detail: null, timeline: [], evidence: [], tasks: [] })
async function loadEvents() { loading.value = true; try { const res = await getUnifiedSafetyEvents(query); items.value = res.data?.items || []; total.value = res.data?.total || 0 } catch (error) { ElMessage.error(error.response?.data?.detail || '事件加载失败') } finally { loading.value = false } }
async function openDetail(row) { const res = await getUnifiedSafetyEventDetail(row.id); Object.assign(detail, res.data || {}); detailVisible.value = true }
function showEvidence(logId) { currentEvidence.value = detail.evidence.filter(item => item.timeline_log_id === logId); evidenceVisible.value = true }
async function operate(action) { let risk_level; if (action === 'UPGRADE') risk_level = detail.event.risk_level === 'LOW' ? 'MEDIUM' : 'HIGH'; const { value: reason } = await ElMessageBox.prompt('请输入处置说明', action === 'FALSE_ALARM' ? '标记误报' : (action === 'RESOLVE' ? '人工闭环' : '升级风险'), { inputValue: '', inputPlaceholder: '简要说明原因' }); await operateUnifiedSafetyEvent(detail.event.id, { action, risk_level, reason }); ElMessage.success('事件状态已更新'); await openDetail({ id: detail.event.id }); await loadEvents() }
function riskTag(v) { return ({ LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' })[v] || 'info' }
function statusLabel(v) { return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[v] || v }
function logTypeLabel(v) { return ({ TRIGGER: '事件触发', RISK_CHANGE: '风险变化', ACTION: '执行动作', MANUAL: '人工操作', RESOLVE: '事件闭环', SYSTEM: '系统记录' })[v] || v }
function timelineType(v) { return ({ TRIGGER: 'primary', RISK_CHANGE: 'warning', ACTION: 'success', RESOLVE: 'success' })[v] || 'info' }
function targetLabel(v) { return ({ person: '人员', boat: '船只', vehicle: '车辆' })[v] || v }
function taskStatusLabel(v) { return ({ DISPATCHED: '已派单', ACCEPTED: '已接单', COMPLETED: '已完成' })[v] || v }
function sourceLabel(v) { return ({ CAMERA: '摄像头', DRONE: '无人机', STAFF: '工作人员' })[v] || v }
function confidenceText(v) { return Number.isFinite(Number(v)) ? `${(Number(v) * 100).toFixed(1)}%` : '--' }
function formatTime(v) { if (!v) return '--'; const d = new Date(v); return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString('zh-CN', { hour12: false }) }
loadEvents()
</script>

<style scoped>
.events-page { min-height: 100%; padding: 20px; color: #d9e8f8; background: #071422; }.page-header,.filters,.drawer-actions,.timeline-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }.filters,.table-panel,.detail-section { margin-top: 16px; padding: 14px; border: 1px solid rgba(96,151,191,.24); border-radius: 8px; background: #0b1d30; }.filters { justify-content: flex-start; }.filters .el-select { width: 150px; }.filters .el-input { max-width: 330px; }.table-panel .el-pagination { margin-top: 14px; justify-content: flex-end; }.summary-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; }.summary-grid div { padding: 12px; border: 1px solid rgba(96,151,191,.2); border-radius: 6px; }.summary-grid span,.timeline-row small { display: block; color: #829bb3; font-size: 12px; }.summary-grid strong { display: block; margin-top: 6px; }.detail-section h3 { margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }.timeline-row { align-items: flex-start; }.timeline-row p { margin: 5px 0; }.drawer-actions { position: sticky; bottom: 0; margin-top: 18px; padding: 12px; justify-content: flex-end; background: #0b1d30; }.evidence-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }.evidence-grid figure { margin: 0; }.evidence-grid .el-image { width: 100%; aspect-ratio: 16/9; background: #02090f; }.evidence-grid figcaption { margin-top: 6px; color: #829bb3; font-size: 12px; }
@media (max-width:900px){.events-page{padding:12px}.filters{align-items:stretch;flex-direction:column}.filters .el-select,.filters .el-input{width:100%;max-width:none}.summary-grid{grid-template-columns:repeat(2,1fr)}.evidence-grid{grid-template-columns:1fr}}
</style>
