<template>
  <div class="events-page">
    <header class="page-header"><div><p>告警管理 / 安全事件</p><h2>安全事件实例</h2></div><el-button :icon="Refresh" :loading="loading" @click="loadEvents">刷新</el-button></header>
    <section class="filters"><el-select v-model="query.status" clearable placeholder="处置状态"><el-option label="待处理" value="PENDING" /><el-option label="处理中" value="PROCESSING" /><el-option label="已完成" value="COMPLETED" /><el-option label="误报" value="FALSE_ALARM" /></el-select><el-select v-model="query.risk_level" clearable placeholder="风险等级"><el-option label="低风险" value="LOW" /><el-option label="中风险" value="MEDIUM" /><el-option label="高风险" value="HIGH" /></el-select><el-input v-model.trim="query.keyword" clearable placeholder="事件编号、名称或摘要" @keyup.enter="loadEvents" /><el-button type="primary" :icon="Search" @click="loadEvents">查询</el-button></section>
    <section class="table-panel" :class="{ 'is-empty': !items.length }" v-loading="loading">
      <el-table v-if="items.length" class="events-table" :data="items" row-key="id">
        <el-table-column label="事件编号" min-width="190">
          <template #default="{ row }"><span class="event-no">{{ row.instance_no || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="事件名称" min-width="150">
          <template #default="{ row }"><strong class="event-name">{{ row.event_name || '未命名事件' }}</strong></template>
        </el-table-column>
        <el-table-column label="摘要" min-width="260" show-overflow-tooltip>
          <template #default="{ row }"><span class="event-summary">{{ row.summary || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="风险" width="100"><template #default="{ row }"><el-tag :type="riskTag(row.risk_level)">{{ row.risk_label }}</el-tag></template></el-table-column>
        <el-table-column label="处置状态" width="120"><template #default="{ row }"><span class="event-status" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span></template></el-table-column>
        <el-table-column label="开始时间" width="180"><template #default="{ row }"><time class="event-time">{{ formatTime(row.started_at) }}</time></template></el-table-column>
        <el-table-column label="操作" width="95" fixed="right"><template #default="{ row }"><el-button class="detail-link" link type="primary" @click="openDetail(row)">详情</el-button></template></el-table-column>
      </el-table>
      <div v-else-if="!loading" class="empty-state" role="status">
        <el-empty :image-size="72" description="暂无安全事件">
          <p>系统检测到的安全事件会显示在这里</p>
        </el-empty>
      </div>
      <div v-else class="loading-space" aria-hidden="true"></div>
      <el-pagination v-if="total > 0" v-model:current-page="query.page" v-model:page-size="query.page_size" layout="prev, pager, next" :total="total" @current-change="loadEvents" />
    </section>

    <el-drawer v-model="detailVisible" class="safety-detail-drawer" size="min(840px, 94vw)">
      <template #header>
        <div class="detail-drawer-heading">
          <div>
            <span class="detail-eyebrow">安全事件详情</span>
            <h2>{{ detail.event?.event_name || '事件详情' }}</h2>
          </div>
          <span v-if="detail.event?.instance_no" class="detail-event-no">{{ detail.event.instance_no }}</span>
        </div>
      </template>

      <div v-if="detail.event" class="detail-content">
        <section class="event-overview" :class="riskClass(detail.event.risk_level)">
          <div class="overview-copy">
            <span>事件摘要</span>
            <p>{{ detail.event.summary || '暂无事件摘要' }}</p>
          </div>
          <div class="overview-badges">
            <span class="risk-badge" :class="riskClass(detail.event.risk_level)">{{ detail.event.risk_label }}</span>
            <span class="status-badge" :class="statusClass(detail.event.status)">{{ statusLabel(detail.event.status) }}</span>
          </div>
          <dl class="overview-meta">
            <div><dt>事件来源</dt><dd>{{ detail.visual_detail?.camera_name || '传感器数据源' }}</dd></div>
            <div><dt>发生时间</dt><dd>{{ formatTime(detail.event.started_at) }}</dd></div>
            <div><dt>最近观测</dt><dd>{{ formatTime(detail.event.last_observed_at) }}</dd></div>
          </dl>
        </section>

        <section v-if="detail.visual_detail" class="detail-card">
          <header class="detail-section-heading">
            <div><span>识别结果</span><h3>视觉证据信息</h3></div>
            <span class="confidence-pill">置信度 {{ confidenceText(detail.visual_detail.confidence) }}</span>
          </header>
          <dl class="visual-info-grid">
            <div><dt>目标类型</dt><dd>{{ targetLabel(detail.visual_detail.target_type) }}</dd></div>
            <div><dt>目标轨迹</dt><dd>{{ detail.visual_detail.target_id || '--' }}</dd></div>
            <div><dt>检测区域</dt><dd>{{ detail.visual_detail.zone_name || '--' }}</dd></div>
            <div><dt>摄像头</dt><dd>{{ detail.visual_detail.camera_name || '--' }}</dd></div>
          </dl>
        </section>

        <section v-if="detail.evidence?.length" class="detail-card evidence-chain-section">
          <header class="detail-section-heading">
            <div><span>风险抓拍</span><h3>完整证据链</h3></div>
            <span class="section-count">{{ detail.evidence.length }} 份证据</span>
          </header>
          <div class="evidence-chain">
            <figure v-for="(item, index) in detail.evidence" :key="item.id" class="evidence-card">
              <div class="evidence-image-wrap">
                <el-image
                  :src="item.file_url"
                  fit="cover"
                  :preview-src-list="detail.evidence.map(evidence => evidence.file_url)"
                  :initial-index="index"
                  preview-teleported
                />
                <span class="evidence-sequence">证据 {{ String(index + 1).padStart(2, '0') }}</span>
                <span class="evidence-risk" :class="riskClass(evidenceRiskLevel(item))">{{ riskLevelLabel(evidenceRiskLevel(item)) }}</span>
              </div>
              <figcaption>
                <strong>{{ item.description || '风险抓拍证据' }}</strong>
                <span>{{ formatTime(item.captured_at) }} · {{ sourceLabel(item.source_type) }}</span>
              </figcaption>
            </figure>
          </div>
        </section>

        <section class="detail-card timeline-section">
          <header class="detail-section-heading">
            <div><span>处理过程</span><h3>事件时间线</h3></div>
            <span class="section-count">{{ detail.timeline.length }} 条记录</span>
          </header>
          <ol v-if="detail.timeline.length" class="event-timeline">
            <li v-for="item in detail.timeline" :key="item.id" :class="`is-${timelineType(item.log_type)}`">
              <div class="timeline-marker"><span></span></div>
              <article class="timeline-content">
                <header><strong>{{ logTypeLabel(item.log_type) }}</strong><time>{{ formatTime(item.create_time) }}</time></header>
                <p>{{ item.message || '暂无处理说明' }}</p>
                <footer>
                  <span>{{ item.operator === 'SYSTEM' ? '系统自动' : (item.operator || '未知操作人') }}</span>
                  <el-button v-if="item.has_evidence" class="evidence-link" link type="primary" :icon="Picture" @click="showEvidence(item.id)">查看证据</el-button>
                </footer>
              </article>
            </li>
          </ol>
          <p v-else class="detail-empty-text">暂无事件处理记录</p>
        </section>

        <section v-if="detail.tasks?.length" class="detail-card task-section">
          <header class="detail-section-heading">
            <div><span>人工协同</span><h3>处置任务</h3></div>
            <span class="section-count">{{ detail.tasks.length }} 个任务</span>
          </header>
          <el-table class="detail-task-table" :data="detail.tasks">
            <el-table-column label="处置人" min-width="150"><template #default="{ row }"><strong class="task-assignee">{{ row.assignee || '--' }}</strong></template></el-table-column>
            <el-table-column label="任务说明" min-width="220"><template #default="{ row }"><span>{{ row.note || '--' }}</span></template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{ row }"><span class="task-status" :class="taskStatusClass(row.status)">{{ taskStatusLabel(row.status) }}</span></template></el-table-column>
            <el-table-column label="处置结果" min-width="150"><template #default="{ row }"><span>{{ row.result_remark || '--' }}</span></template></el-table-column>
          </el-table>
        </section>
      </div>

      <template v-if="detail.event?.state === 'ACTIVE'" #footer>
        <div class="detail-drawer-footer">
          <div class="footer-hint"><strong>等待人工确认</strong><span>请根据现场情况选择处置结果</span></div>
          <div class="footer-actions">
            <el-button type="danger" plain @click="operate('UPGRADE')">升级风险</el-button>
            <el-button plain @click="operate('FALSE_ALARM')">标记误报</el-button>
            <el-button type="primary" @click="operate('RESOLVE')">完成并闭环</el-button>
          </div>
        </div>
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
function riskClass(v) { return ({ LOW: 'risk-low', MEDIUM: 'risk-medium', HIGH: 'risk-high' })[v] || 'risk-unknown' }
function riskLevelLabel(v) { return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[v] || '未知风险' }
function evidenceRiskLevel(item) { return item.risk_level || detail.timeline.find(log => log.id === item.timeline_log_id)?.risk_level || '' }
function statusLabel(v) { return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[v] || v }
function statusClass(v) { return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', COMPLETED: 'is-completed', FALSE_ALARM: 'is-false-alarm' })[v] || '' }
function logTypeLabel(v) { return ({ TRIGGER: '事件触发', RISK_CHANGE: '风险变化', ACTION: '执行动作', MANUAL: '人工操作', RESOLVE: '事件闭环', SYSTEM: '系统记录' })[v] || v }
function timelineType(v) { return ({ TRIGGER: 'primary', RISK_CHANGE: 'warning', ACTION: 'success', RESOLVE: 'success' })[v] || 'info' }
function targetLabel(v) { return ({ person: '人员', boat: '船只', vehicle: '车辆' })[v] || v }
function taskStatusLabel(v) { return ({ DISPATCHED: '已派单', ACCEPTED: '已接单', COMPLETED: '已完成' })[v] || v }
function taskStatusClass(v) { return ({ DISPATCHED: 'is-dispatched', ACCEPTED: 'is-accepted', COMPLETED: 'is-completed' })[v] || '' }
function sourceLabel(v) { return ({ CAMERA: '摄像头', DRONE: '无人机', STAFF: '工作人员' })[v] || v }
function confidenceText(v) { return Number.isFinite(Number(v)) ? `${(Number(v) * 100).toFixed(1)}%` : '--' }
function formatTime(v) { if (!v) return '--'; const d = new Date(v); return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString('zh-CN', { hour12: false }) }
loadEvents()
</script>

<style scoped>
.events-page { min-height: 100%; padding: 20px; color: #d9e8f8; background: #071422; }.page-header,.filters,.drawer-actions,.timeline-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.page-header p { margin: 0 0 5px; color: #79acd0; font-size: 13px; }.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; letter-spacing: 0; }.filters,.detail-section { margin-top: 16px; padding: 14px; border: 1px solid rgba(96,151,191,.24); border-radius: 8px; background: #0b1d30; }.filters { justify-content: flex-start; }.filters .el-select { width: 150px; }.filters .el-input { max-width: 330px; }.table-panel { margin-top: 16px; overflow: hidden; border-radius: 10px; background: rgba(11,29,48,.72); box-shadow: 0 12px 32px rgba(0,7,14,.2); }.table-panel.is-empty { border-radius: 0; background: transparent; box-shadow: none; }.table-panel :deep(.el-table__inner-wrapper::before),.table-panel :deep(.el-table__fixed-right::before) { display: none; }.table-panel :deep(th.el-table__cell) { border-bottom: 0; background: rgba(30,58,95,.58) !important; }.table-panel :deep(td.el-table__cell) { border-bottom-color: rgba(96,151,191,.1); }.table-panel .el-pagination { gap: 12px; padding: 16px; justify-content: flex-end; }.table-panel :deep(.el-pagination .btn-prev),.table-panel :deep(.el-pagination .btn-next),.table-panel :deep(.el-pager li) { width: 52px; height: 46px; min-width: 52px; margin: 0; border: 1px solid #214766; border-radius: 5px; color: #7893aa; background: #0a1a2c; font-size: 16px; transition: border-color .18s ease,color .18s ease,background .18s ease; }.table-panel :deep(.el-pager) { display: flex; gap: 12px; }.table-panel :deep(.el-pager li.is-active) { border-color: #61b5ff; color: #fff; background: #3d8ed8; }.table-panel :deep(.el-pagination button:not(:disabled):hover),.table-panel :deep(.el-pager li:not(.is-active):hover) { border-color: #3f83b8; color: #a8d5f7; background: #102a43; }.table-panel :deep(.el-pagination button:disabled) { border-color: #193b57; color: #35536b; background: #091827; opacity: 1; }.empty-state,.loading-space { display: grid; min-height: 280px; place-items: center; background: radial-gradient(circle at 50% 40%,rgba(29,78,111,.2),transparent 48%); }.empty-state :deep(.el-empty) { padding: 36px 20px; }.empty-state :deep(.el-empty__description) { margin-top: 12px; }.empty-state :deep(.el-empty__description p) { color: #9bb2c7; font-size: 15px; }.empty-state :deep(.el-empty__bottom) { margin-top: 6px; }.empty-state > :deep(.el-empty) > p,.empty-state :deep(.el-empty__bottom p) { margin: 0; color: #607d96; font-size: 13px; }.summary-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; }.summary-grid div { padding: 12px; border: 1px solid rgba(96,151,191,.2); border-radius: 6px; }.summary-grid span,.timeline-row small { display: block; color: #829bb3; font-size: 12px; }.summary-grid strong { display: block; margin-top: 6px; }.detail-section h3 { margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }.timeline-row { align-items: flex-start; }.timeline-row p { margin: 5px 0; }.drawer-actions { position: sticky; bottom: 0; margin-top: 18px; padding: 12px; justify-content: flex-end; background: #0b1d30; }.evidence-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }.evidence-grid figure { margin: 0; }.evidence-grid .el-image { width: 100%; aspect-ratio: 16/9; background: #02090f; }.evidence-grid figcaption { margin-top: 6px; color: #829bb3; font-size: 12px; }
/* 安全事件是用户扫描列表时的主信息，编号和时间保留为清晰的辅助信息。 */
.events-table {
  --el-table-bg-color: #0a1b2c;
  --el-table-tr-bg-color: #0a1b2c;
  --el-table-header-bg-color: #173653;
  --el-table-row-hover-bg-color: #102d46;
  --el-table-text-color: #d7e7f4;
  --el-table-header-text-color: #e4f1fb;
}
.table-panel :deep(.events-table th.el-table__cell) {
  height: 52px;
  border-bottom: 1px solid rgba(143, 190, 222, .2);
  color: #e4f1fb;
  background: #173653 !important;
  font-size: 14px;
  font-weight: 700;
}
.table-panel :deep(.events-table td.el-table__cell) {
  height: 52px;
  border-bottom: 1px solid rgba(143, 190, 222, .13);
  color: #d7e7f4;
  background: #0a1b2c !important;
  font-size: 14px;
}
.table-panel :deep(.events-table .el-table__row:hover > td.el-table__cell) {
  background: #102d46 !important;
}
.event-name {
  color: #f5fbff;
  font-weight: 700;
}
.event-no,
.event-time {
  color: #b7ccdc;
  font-variant-numeric: tabular-nums;
}
.event-summary { color: #cbddea; }
.event-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #dceaf5;
  font-weight: 600;
}
.event-status::before {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #9eb4c5;
  box-shadow: 0 0 0 3px rgba(158, 180, 197, .12);
  content: '';
}
.event-status.is-pending::before { background: #f0b35a; box-shadow: 0 0 0 3px rgba(240, 179, 90, .14); }
.event-status.is-processing::before { background: #63bdff; box-shadow: 0 0 0 3px rgba(99, 189, 255, .14); }
.event-status.is-completed::before { background: #73d59b; box-shadow: 0 0 0 3px rgba(115, 213, 155, .14); }
.event-status.is-false-alarm::before { background: #9eb4c5; }
.table-panel :deep(.detail-link.el-button) {
  color: #83ceff;
  font-weight: 700;
}
.table-panel :deep(.detail-link.el-button:hover),
.table-panel :deep(.detail-link.el-button:focus-visible) { color: #c4e9ff; }

/* 详情抽屉：按“事件结论 → 识别证据 → 处理过程 → 人工操作”组织信息。 */
:global(.safety-detail-drawer.el-drawer) {
  border-left: 1px solid #234159 !important;
  background: #081827 !important;
  box-shadow: -18px 0 48px rgba(0, 7, 14, .38) !important;
}
:global(.safety-detail-drawer .el-drawer__header) {
  min-height: 82px;
  margin: 0;
  padding: 18px 26px;
  border-bottom: 1px solid rgba(137, 184, 215, .14);
  color: #edf7ff;
}
:global(.safety-detail-drawer .el-drawer__close-btn) { color: #b9cddd; }
:global(.safety-detail-drawer .el-drawer__close-btn:hover) { color: #fff; }
:global(.safety-detail-drawer .el-drawer__body) {
  padding: 22px 26px 30px;
  background: #081827;
}
:global(.safety-detail-drawer .el-drawer__footer) {
  padding: 0;
  border-top: 1px solid rgba(137, 184, 215, .16);
  background: #0a1c2c;
}
.detail-drawer-heading {
  display: flex;
  min-width: 0;
  width: 100%;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}
.detail-eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #80a9c6;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .08em;
}
.detail-drawer-heading h2 {
  overflow: hidden;
  margin: 0;
  color: #f5faff;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-event-no {
  flex: 0 0 auto;
  padding: 5px 9px;
  border-radius: 6px;
  color: #a8bfd0;
  background: #10283b;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.detail-content { display: grid; gap: 18px; }
.event-overview {
  position: relative;
  overflow: hidden;
  padding: 20px;
  border: 1px solid rgba(125, 178, 214, .18);
  border-radius: 12px;
  background: linear-gradient(135deg, #102b40 0%, #0b2032 65%, #0a1c2c 100%);
}
.event-overview::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #7195ae;
  content: '';
}
.event-overview.risk-high::before { background: #ff6f7d; }
.event-overview.risk-medium::before { background: #f0ad4e; }
.event-overview.risk-low::before { background: #67cf91; }
.overview-copy { padding-right: 170px; }
.overview-copy > span,
.detail-section-heading > div > span {
  color: #8eacc1;
  font-size: 12px;
  font-weight: 700;
}
.overview-copy p {
  margin: 7px 0 0;
  color: #e3eff7;
  font-size: 15px;
  line-height: 1.65;
}
.overview-badges {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  gap: 8px;
}
.risk-badge,
.status-badge,
.confidence-pill,
.section-count,
.task-status {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.risk-badge.risk-high { color: #ffb2ba; background: rgba(186, 48, 66, .28); }
.risk-badge.risk-medium { color: #ffd18f; background: rgba(177, 106, 25, .27); }
.risk-badge.risk-low { color: #a7edc0; background: rgba(42, 132, 78, .28); }
.risk-badge.risk-unknown { color: #bdd0de; background: rgba(108, 137, 157, .22); }
.status-badge { color: #c8d9e5; background: rgba(119, 148, 169, .2); }
.status-badge.is-pending { color: #ffd18f; background: rgba(177, 106, 25, .23); }
.status-badge.is-processing { color: #a8ddff; background: rgba(35, 125, 191, .25); }
.status-badge.is-completed { color: #a7edc0; background: rgba(42, 132, 78, .25); }
.overview-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin: 18px 0 0;
  padding-top: 16px;
  border-top: 1px solid rgba(151, 190, 216, .13);
}
.overview-meta div { min-width: 0; padding-right: 16px; }
.overview-meta div + div { padding-left: 16px; border-left: 1px solid rgba(151, 190, 216, .13); }
.overview-meta dt,
.visual-info-grid dt {
  color: #8faabd;
  font-size: 12px;
}
.overview-meta dd {
  overflow: hidden;
  margin: 6px 0 0;
  color: #e0ecf5;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-card {
  padding: 20px;
  border: 1px solid rgba(125, 178, 214, .16);
  border-radius: 12px;
  background: #0b1e2f;
}
.detail-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.detail-section-heading h3 {
  margin: 3px 0 0;
  color: #f0f7fc;
  font-size: 17px;
  font-weight: 700;
}
.confidence-pill { color: #a9ddff; background: rgba(39, 129, 188, .22); }
.section-count { color: #9eb7c9; background: #102a3e; }
.visual-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}
.visual-info-grid div {
  min-width: 0;
  padding: 13px 15px;
  border-radius: 8px;
  background: #10283a;
}
.visual-info-grid dd {
  overflow: hidden;
  margin: 6px 0 0;
  color: #e6f1f8;
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-chain {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.evidence-card {
  min-width: 0;
  overflow: hidden;
  margin: 0;
  border: 1px solid rgba(126, 177, 209, .17);
  border-radius: 9px;
  background: #10283a;
}
.evidence-image-wrap { position: relative; overflow: hidden; aspect-ratio: 16 / 9; background: #06121e; }
.evidence-image-wrap :deep(.el-image) { width: 100%; height: 100%; cursor: zoom-in; transition: transform .2s ease; }
.evidence-card:hover .evidence-image-wrap :deep(.el-image) { transform: scale(1.025); }
.evidence-sequence,
.evidence-risk {
  position: absolute;
  top: 8px;
  z-index: 1;
  min-height: 23px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 23px;
  backdrop-filter: blur(6px);
}
.evidence-sequence { left: 8px; color: #e6f3fb; background: rgba(4, 19, 31, .74); }
.evidence-risk { right: 8px; color: #d6e5ef; background: rgba(80, 106, 124, .78); }
.evidence-risk.risk-low { color: #b6f2ca; background: rgba(24, 102, 56, .82); }
.evidence-risk.risk-medium { color: #ffe0a9; background: rgba(133, 78, 18, .84); }
.evidence-risk.risk-high { color: #ffc0c7; background: rgba(140, 36, 52, .84); }
.evidence-card figcaption { display: grid; gap: 5px; padding: 11px 12px 12px; }
.evidence-card figcaption strong {
  overflow: hidden;
  color: #edf7fd;
  font-size: 13px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-card figcaption span { color: #8faabd; font-size: 11px; line-height: 1.4; }
.event-timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}
.event-timeline li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
}
.timeline-marker { position: relative; display: flex; justify-content: flex-start; }
.timeline-marker::after {
  position: absolute;
  top: 15px;
  bottom: -15px;
  left: 5px;
  width: 1px;
  background: #2b4a61;
  content: '';
}
.event-timeline li:last-child .timeline-marker::after { display: none; }
.timeline-marker span {
  position: relative;
  z-index: 1;
  width: 11px;
  height: 11px;
  margin-top: 5px;
  border: 2px solid #0b1e2f;
  border-radius: 50%;
  background: #88a1b4;
  box-shadow: 0 0 0 3px rgba(136, 161, 180, .18);
}
.event-timeline .is-primary .timeline-marker span { background: #4daeff; box-shadow: 0 0 0 3px rgba(77, 174, 255, .18); }
.event-timeline .is-warning .timeline-marker span { background: #f0ad4e; box-shadow: 0 0 0 3px rgba(240, 173, 78, .18); }
.event-timeline .is-success .timeline-marker span { background: #67cf91; box-shadow: 0 0 0 3px rgba(103, 207, 145, .18); }
.timeline-content { padding: 0 0 20px; }
.timeline-content header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
}
.timeline-content header strong { color: #edf6fc; font-size: 14px; }
.timeline-content header time { flex: 0 0 auto; color: #8faabd; font-size: 12px; font-variant-numeric: tabular-nums; }
.timeline-content p { margin: 7px 0; color: #cadce8; font-size: 14px; line-height: 1.55; }
.timeline-content footer { display: flex; align-items: center; justify-content: space-between; min-height: 24px; color: #8faabd; font-size: 12px; }
.timeline-content :deep(.evidence-link.el-button) { height: 24px; padding: 0; color: #83ceff; font-weight: 700; }
.detail-empty-text { margin: 0; padding: 26px; color: #8faabd; text-align: center; }
.detail-task-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: #112b41;
  --el-table-row-hover-bg-color: #102b40;
  --el-table-text-color: #cfe0eb;
  --el-table-header-text-color: #b8cfdf;
  border-radius: 8px;
  overflow: hidden;
}
.detail-card :deep(.detail-task-table th.el-table__cell) {
  height: 44px;
  color: #bdd2e1;
  background: #112b41 !important;
  font-size: 13px;
  font-weight: 700;
}
.detail-card :deep(.detail-task-table td.el-table__cell) {
  height: 50px;
  border-bottom-color: rgba(139, 183, 211, .13);
  color: #cfe0eb;
  background: #0d2335 !important;
}
.detail-card :deep(.detail-task-table .el-table__row:hover > td.el-table__cell) { background: #102b40 !important; }
.task-assignee { color: #edf6fc; }
.task-status { min-height: 24px; color: #b9d2e3; background: rgba(99, 139, 166, .2); }
.task-status.is-dispatched { color: #a8ddff; background: rgba(35, 125, 191, .23); }
.task-status.is-accepted { color: #ffd18f; background: rgba(177, 106, 25, .23); }
.task-status.is-completed { color: #a7edc0; background: rgba(42, 132, 78, .25); }
.detail-drawer-footer {
  display: flex;
  min-height: 76px;
  padding: 14px 26px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  text-align: left;
}
.footer-hint { display: grid; gap: 3px; }
.footer-hint strong { color: #edf6fc; font-size: 14px; }
.footer-hint span { color: #8faabd; font-size: 12px; }
.footer-actions { display: flex; gap: 10px; }
.footer-actions :deep(.el-button) { min-width: 104px; height: 40px; margin: 0; border-radius: 7px; font-weight: 700; }
.footer-actions :deep(.el-button--primary) { border-color: #258fd2 !important; color: #fff !important; background: #258fd2 !important; }
.footer-actions :deep(.el-button--primary:hover) { border-color: #45a8e5 !important; background: #329edf !important; }
.footer-actions :deep(.el-button--danger.is-plain) { border-color: rgba(239, 104, 120, .48) !important; color: #ffadb7 !important; background: rgba(126, 35, 49, .2) !important; }

@media (max-width: 640px) {
  :global(.safety-detail-drawer .el-drawer__header),
  :global(.safety-detail-drawer .el-drawer__body) { padding-left: 16px; padding-right: 16px; }
  .detail-drawer-heading { align-items: flex-start; flex-direction: column; gap: 8px; }
  .overview-copy { padding-right: 0; }
  .overview-badges { position: static; margin-top: 14px; }
  .overview-meta { grid-template-columns: 1fr; }
  .overview-meta div,
  .overview-meta div + div { padding: 10px 0; border-left: 0; }
  .overview-meta div + div { border-top: 1px solid rgba(151, 190, 216, .13); }
  .visual-info-grid { grid-template-columns: 1fr; }
  .evidence-chain { grid-template-columns: 1fr; }
  .timeline-content header { align-items: flex-start; flex-direction: column; gap: 4px; }
  .detail-drawer-footer { align-items: stretch; flex-direction: column; }
  .footer-actions { display: grid; grid-template-columns: repeat(3, 1fr); }
  .footer-actions :deep(.el-button) { min-width: 0; padding: 0 8px; }
}
@media (max-width:900px){.events-page{padding:12px}.filters{align-items:stretch;flex-direction:column}.filters .el-select,.filters .el-input{width:100%;max-width:none}.summary-grid{grid-template-columns:repeat(2,1fr)}.evidence-grid{grid-template-columns:1fr}}
</style>
