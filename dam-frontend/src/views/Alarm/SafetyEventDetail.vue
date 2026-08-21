<template>
  <div class="event-workbench" v-loading="loading">
    <template v-if="event">
      <section class="major-flow" :class="{ 'is-resolved': isResolved }">
        <header class="flow-header">
          <button type="button" class="flow-back-button" @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回列表</span>
          </button>
          <span class="flow-header-divider" aria-hidden="true"></span>
          <h2 class="flow-heading">事件处理流程</h2>
        </header>
        <div class="flow-main">
          <ol class="flow-rail">
            <li
              v-for="(step, index) in mainFlowSteps"
              :key="step.key"
              :class="[step.state, { current: step.current }]"
              :title="step.detail"
            >
              <div class="flow-node">
                <el-icon><component :is="step.icon" /></el-icon>
              </div>
              <div class="flow-text">
                <strong>{{ step.title }}</strong>
                <span>{{ step.statusText }}</span>
                <time>{{ step.time }}</time>
              </div>
              <svg v-if="index < mainFlowSteps.length - 1" class="flow-connector" viewBox="0 0 220 28" aria-hidden="true">
                <path class="connector-base" d="M4 14 H216" />
                <path v-if="step.state === 'done' || step.state === 'running'" class="connector-fill" d="M4 14 H216" />
                <path class="connector-arrow" d="M216 14 L208 9 M216 14 L208 19" />
              </svg>
            </li>
          </ol>
        </div>
      </section>

      <section class="workspace-grid" :class="{ 'no-linkage': !showRightRail }">
        <main class="primary-stack">
          <section class="work-card detail-card">
            <header class="detail-hero">
              <div class="detail-title-block">
                <span>{{ eventKindLabel }} / 事件详情</span>
                <h2>{{ event.event_name || '安全事件详情' }}</h2>
                <p v-if="event.summary">{{ event.summary }}</p>
              </div>
              <div class="detail-status-block">
                <div class="detail-badges">
                  <span class="risk-badge" :class="riskClass(event.risk_level)">{{ riskLevelLabel(event.risk_level, event.risk_label) }}</span>
                  <span class="status-badge" :class="statusClass(event.status)">{{ statusLabel(event.status) }}</span>
                </div>
                <time>{{ formatTime(event.started_at) }}</time>
                <small>持续 {{ eventDuration }}</small>
              </div>
            </header>

            <dl class="detail-fields">
              <div v-for="field in detailFields" :key="field.key">
                <dt>{{ field.label }}</dt>
                <dd>{{ field.value }}</dd>
              </div>
            </dl>
          </section>

          <section class="work-card evidence-card linkage-evidence-card" :class="{ empty: !reviewFrames.length }">
            <header class="card-heading">
              <div>
                <span>现场证据</span>
              </div>
              <small>{{ reviewFrames.length }} / 8 帧</small>
            </header>

            <div v-if="reviewFrames.length" class="review-frame-strip">
              <button
                v-for="(item, index) in reviewFrames"
                :key="item.id"
                type="button"
                class="review-frame-item"
                :class="{ 'is-false-alarm': isFalseAlarmFrame(item) }"
                @click="openEvidenceItem(item)"
              >
                <el-image :src="normalizeMediaUrl(item.file_url)" fit="cover" />
                <span v-if="isFalseAlarmFrame(item)" class="false-alarm-frame-flag">误报样本</span>
                <footer>
                  <span>复核帧 {{ String(index + 1).padStart(2, '0') }}</span>
                </footer>
              </button>
              <div v-for="slot in Math.max(0, 8 - reviewFrames.length)" :key="`review-slot-${slot}`" class="review-frame-slot">
                <strong>{{ String(reviewFrames.length + slot).padStart(2, '0') }}</strong>
                <span>待归档</span>
              </div>
            </div>
            <div v-else class="linkage-evidence-empty">
              <el-icon><Picture /></el-icon>
              <div>
                <strong>暂无现场图片</strong>
                <span>暂无 Qwen4B 抽取帧</span>
              </div>
            </div>
          </section>

          <section class="work-card linkage-evidence-card">
            <header class="card-heading">
              <div><span>联动证据</span></div>
              <small>{{ linkageEvidenceCount }} 张</small>
            </header>

            <div v-if="linkageEvidenceItems.length" class="review-frame-strip linkage-evidence-strip">
              <button
                v-for="(item, index) in linkageEvidenceItems"
                :key="item.id"
                type="button"
                class="review-frame-item linkage-evidence-item"
                @click="openEvidenceItem(item)"
              >
                <el-image :src="normalizeMediaUrl(item.file_url)" fit="cover" />
                <footer>
                  <span><b :class="`linkage-source-${item.linkage_kind}`">{{ item.linkage_label }}</b>取证 {{ String(index + 1).padStart(2, '0') }}</span>
                  <time v-if="item.captured_at">{{ formatTime(item.captured_at) }}</time>
                </footer>
              </button>
            </div>
            <div v-else class="linkage-evidence-empty">
              <el-icon><Picture /></el-icon>
              <div>
                <strong>暂无联动图片</strong>
                <span>开始联动后将自动归档设备与人工处置图片</span>
              </div>
            </div>
          </section>

          <section class="work-card log-card">
            <header class="card-heading">
              <div>
                <span>处理日志</span>
                <h2>记录流</h2>
              </div>
              <small>{{ displayedTimeline.length }} 条</small>
            </header>

            <div v-if="displayedTimeline.length" class="log-stream">
              <article
                v-for="entry in timelineEntries"
                :key="entry.item.id"
                :class="[timelineTone(entry.item), timelineNodeClass(entry.item)]"
              >
                <span class="log-type">{{ logTypeLabel(entry.item.log_type, entry.item) }}</span>
                <div class="log-body">
                  <strong>{{ logTitle(entry.item) }}</strong>
                  <p v-if="logMessage(entry.item)">{{ logMessage(entry.item) }}</p>
                  <dl v-if="logDetailFields(entry.item).length" class="log-fields">
                    <div
                      v-for="field in logDetailFields(entry.item)"
                      :key="`${field.kind || field.label}-${field.value}`"
                      :class="{ 'log-field-note': field.kind === 'note' }"
                    >
                      <template v-if="field.kind === 'note'">
                        <dd class="log-field-note-text">{{ field.value }}</dd>
                      </template>
                      <template v-else>
                        <dt>{{ field.label }}</dt>
                        <dd>{{ field.value }}</dd>
                      </template>
                    </div>
                  </dl>
                  <div v-if="entry.dag" class="workflow-dag-block">
                    <div class="workflow-dag-heading">
                      <strong>处置流程图</strong>
                      <span>流程节点</span>
                    </div>
                    <div class="workflow-dag-canvas">
                      <svg
                        :viewBox="`0 0 ${entry.dag.width} ${entry.dag.height}`"
                        role="img"
                        aria-label="事件处置流程图"
                      >
                        <defs>
                          <marker
                            :id="`dag-arrow-${entry.item.id}`"
                            markerWidth="7"
                            markerHeight="7"
                            refX="6"
                            refY="3.5"
                            orient="auto"
                          >
                            <path d="M0 0 L7 3.5 L0 7 Z" fill="#5c8dab" />
                          </marker>
                        </defs>
                        <path
                          v-for="edge in entry.dag.edges"
                          :key="edge.key"
                          class="workflow-dag-edge"
                          :d="edge.path"
                          :marker-end="`url(#dag-arrow-${entry.item.id})`"
                        />
                        <g v-for="node in entry.dag.nodes" :key="node.id" class="workflow-dag-node" :class="node.tone">
                          <title>{{ node.fullLabel }}{{ node.modelFullLabel }}</title>
                          <rect :x="node.x" :y="node.y" :width="node.width" :height="node.height" rx="6" />
                          <text
                            :x="node.x + node.width / 2"
                            :y="node.y + (node.modelLabel ? 19 : node.height / 2)"
                            text-anchor="middle"
                            dominant-baseline="middle"
                          >{{ node.label }}</text>
                          <text
                            v-if="node.modelLabel"
                            class="workflow-dag-model"
                            :x="node.x + node.width / 2"
                            :y="node.y + 39"
                            text-anchor="middle"
                            dominant-baseline="middle"
                          >{{ node.modelLabel }}</text>
                        </g>
                      </svg>
                    </div>
                  </div>
                </div>
                <div class="log-source">
                  <span>{{ operatorLabel(entry.item.operator) }}</span>
                  <time>{{ formatTime(entry.item.create_time || entry.item.created_at) }}</time>
                </div>
              </article>
            </div>
            <div v-else class="compact-empty">
              <span>暂无处理日志</span>
            </div>
          </section>
        </main>

        <aside v-if="showRightRail" class="side-stack">
          <section v-if="actionModules.length" class="work-card linkage-card">
            <header class="card-heading">
              <div>
                <h2 class="linkage-heading-title">联动执行</h2>
              </div>
              <small class="linkage-count">{{ actionModules.length }} 项</small>
            </header>

            <div class="linkage-list">
              <article
                v-for="module in actionModules"
                :key="module.key"
                :class="[module.state, `linkage-${module.key}`, `linkage-meta-${module.meta.length}`]"
              >
                <div class="linkage-body">
                  <header>
                    <strong>{{ module.title }}</strong>
                    <div class="linkage-card-actions">
                      <el-button
                        v-if="module.canInspect"
                        class="linkage-process-button"
                        plain
                        size="small"
                        :icon="VideoCamera"
                        @click="openLinkageProcess(module)"
                      >
                        查看过程
                      </el-button>
                      <span>{{ module.statusText }}</span>
                    </div>
                  </header>
                  <dl>
                    <div v-for="meta in module.meta" :key="meta.label">
                      <dt>{{ meta.label }}</dt>
                      <dd>{{ meta.value }}</dd>
                    </div>
                  </dl>
                  <el-button
                    v-if="module.manualAction"
                    class="linkage-complete-button"
                    type="primary"
                    size="small"
                    @click="module.manualAction === 'SUBMIT_STAFF_RESULT' ? openStaffResultDialog() : operate(module.manualAction)"
                  >
                    {{ module.manualActionLabel }}
                  </el-button>
                  <p v-if="module.failureReason" class="failure-reason">失败原因：{{ module.failureReason }}</p>
                </div>
              </article>
            </div>
          </section>

          <section v-if="event.analysis_report_document_id" class="work-card report-card">
            <header class="card-heading">
              <div>
                <span>处置报告</span>
                <h2>报告归档</h2>
              </div>
              <small>DOCX</small>
            </header>
            <button class="report-card-link" type="button" @click="openReport">
              <el-icon><Document /></el-icon>
              <span class="report-card-copy">
                <strong>{{ reportTitle }}</strong>
                <small>{{ displayEventId }} · 点击查看</small>
              </span>
              <span class="report-open-text">查看</span>
            </button>
          </section>

          <section class="work-card operation-card">
            <header class="card-heading">
              <div>
                <span>处置操作</span>
                <h2>{{ event.state === 'ACTIVE' ? '人工决策' : '归档状态' }}</h2>
              </div>
            </header>
            <div class="action-context">
              <strong>{{ operationContext.title }}</strong>
              <p>{{ operationContext.hint }}</p>
            </div>
            <div class="decision-actions">
              <el-button
                v-for="button in secondaryActions"
                :key="button.action"
                plain
                :type="button.type"
                :disabled="button.disabled"
                @click="operate(button.action)"
              >
                {{ button.label }}
              </el-button>
            </div>
          </section>
        </aside>
      </section>
    </template>

    <el-empty v-else-if="!loading" description="未找到安全事件" />

    <el-drawer v-model="evidenceVisible" title="事件证据" class="evidence-drawer" size="560px">
      <div v-if="currentEvidence.length" class="evidence-drawer-list">
        <figure v-for="item in currentEvidence" :key="item.id">
          <el-image
            v-if="isImageEvidence(item)"
            :src="normalizeMediaUrl(item.file_url)"
            fit="cover"
            :preview-src-list="currentEvidence.filter(isImageEvidence).map((record) => normalizeMediaUrl(record.file_url))"
            preview-teleported
          />
          <div v-else class="drawer-file">
            <el-icon><Document /></el-icon>
            <a :href="normalizeMediaUrl(item.file_url)" target="_blank" rel="noreferrer">{{ normalizeMediaUrl(item.file_url) }}</a>
          </div>
          <figcaption>
            <strong>{{ item.description || evidenceTypeLabel(item.evidence_type) }}</strong>
            <span>{{ sourceLabel(item.source_type) }} · {{ formatTime(item.captured_at) }}</span>
            <small>关联动作：{{ relatedLogLabel(item.timeline_log_id) }}</small>
          </figcaption>
        </figure>
      </div>
      <div v-else class="compact-empty">当前节点暂无证据</div>
    </el-drawer>

    <AppDialog
      v-model="staffResultDialogVisible"
      class="staff-result-dialog"
      width="680px"
      align-center
      destroy-on-close
      :close-on-click-modal="false"
      title="提交现场处置结果"
      @closed="resetStaffResultForm"
    >
      <div class="staff-result-form">
        <div class="staff-result-hint">请分别上传驱离前、驱离后的现场照片，并填写本次处置说明。</div>

        <div class="staff-result-field">
          <label>事件类型</label>
          <el-select v-model="staffResultForm.eventType" class="staff-result-select">
            <el-option v-for="item in STAFF_TASK_EVENT_TYPES" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>

        <div class="staff-result-field">
          <label>处置结果</label>
          <el-select v-model="staffResultForm.result" class="staff-result-select">
            <el-option label="已完成驱离" value="DRIVEN_AWAY" />
            <el-option label="人员自行离开" value="LEFT_BY_SELF" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </div>

        <div class="staff-result-field">
          <label>现场照片</label>
          <div class="staff-result-photo-grid">
            <label v-for="(label, index) in ['驱离前照片', '驱离后照片']" :key="label" class="staff-result-photo-card">
              <input type="file" accept="image/jpeg,image/png,image/webp" @change="selectStaffResultPhoto(index, $event)" />
              <img v-if="staffResultPhotoPreviews[index]" :src="staffResultPhotoPreviews[index]" :alt="label" />
              <span v-else>{{ label }}<small>点击选择图片</small></span>
            </label>
          </div>
        </div>

        <div class="staff-result-field">
          <label>处置说明</label>
          <el-input v-model="staffResultForm.remark" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="填写现场处置情况" />
        </div>
      </div>
      <template #footer>
        <el-button @click="staffResultDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="staffResultSubmitting" @click="submitStaffResult">提交结果</el-button>
      </template>
    </AppDialog>

    <el-dialog
      v-model="falseAlarmDialogVisible"
      class="false-alarm-dialog"
      width="760px"
      align-center
      destroy-on-close
      :close-on-click-modal="false"
      title="标记误报"
      @closed="resetFalseAlarmSelection"
    >
      <div class="false-alarm-dialog-copy">请选择模型误判的现场证据。确认后将把原始图片归档为误报样本。</div>
      <div class="false-alarm-selection-grid">
        <button
          v-for="(item, index) in falseAlarmCandidates"
          :key="`false-alarm-${item.id}-${index}`"
          type="button"
          class="false-alarm-selection-item"
          :class="{ selected: isFalseAlarmSelected(item.file_url) }"
          @click="toggleFalseAlarmSelection(item.file_url)"
        >
          <el-image :src="normalizeMediaUrl(item.file_url)" fit="cover" />
          <span class="false-alarm-selection-check">{{ isFalseAlarmSelected(item.file_url) ? '✓' : '' }}</span>
          <strong>复核帧 {{ String(index + 1).padStart(2, '0') }}</strong>
        </button>
      </div>
      <div v-if="!falseAlarmCandidates.length" class="linkage-evidence-empty">
        <el-icon><Picture /></el-icon>
        <div><strong>暂无可标记图片</strong><span>当前事件没有可归档的现场图片</span></div>
      </div>
      <template #footer>
        <el-button @click="falseAlarmDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="falseAlarmSubmitting" :disabled="!selectedFalseAlarmUrls.length" @click="submitFalseAlarmReview">
          归档 {{ selectedFalseAlarmUrls.length }} 张误报图片
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="processDialogVisible"
      class="linkage-process-dialog drone-test-dialog"
      width="92%"
      align-center
      destroy-on-close
      :close-on-click-modal="false"
      :title="processDialogTitle"
      @closed="stopLinkageProcess"
    >
      <div v-if="processModule" class="test-layout">
        <div class="test-body">
          <div class="test-map wayline-map-stage test-wayline-map-stage" @selectstart.prevent @dragstart.prevent>
            <img src="/dam.png" alt="大藤峡航线图" draggable="false" />
            <svg v-if="processRoutePoints.length" class="wayline-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polyline class="wayline-map-route route-glow tone-0" :points="processRoutePolyline" />
              <polyline class="wayline-map-route tone-0" :points="processRoutePolyline" />
            </svg>
            <div class="process-wayline-landmark airport" style="left: 94.9%; top: 24.9%;">
              <span class="process-wayline-landmark-mark" aria-hidden="true"></span>
              <span>机场点</span>
            </div>
            <div class="process-wayline-landmark" style="left: 47.4%; top: 58.1%;">
              <span class="process-wayline-landmark-mark" aria-hidden="true"></span>
              <span>禁渔点</span>
            </div>
            <div class="process-wayline-landmark" style="left: 96.3%; top: 54.3%;">
              <span class="process-wayline-landmark-mark" aria-hidden="true"></span>
              <span>禁涉水点</span>
            </div>
            <div class="drone-marker process-unit-marker" :style="{ left: `${processMarkerPoint.x}%`, top: `${processMarkerPoint.y}%` }">
              <div class="marker-pulse"></div>
              <img :src="processModule.key === 'drone' ? '/drone-icon.png' : '/waypoint.png'" alt="执行设备" class="marker-icon" />
            </div>
            <div class="map-legend">
              <span class="legend-item"><i class="legend-line"></i>执行航线</span>
              <span class="legend-item process-current-position">● 当前位置</span>
            </div>
          </div>

          <div class="test-video">
            <div class="video-stage">
              <video
                :key="processRouteSelection"
                ref="processVideoRef"
                :src="processVideoSrc"
                class="video-stream demo-video-crop"
                autoplay
                muted
                loop
                preload="auto"
                playsinline
                @canplay="ensureProcessVideoPlayback"
              ></video>
              <div class="process-video-label"><strong>{{ processEventLabel }}</strong></div>
              <div class="scan-grid"></div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  CircleCheckFilled,
  Connection,
  Document,
  Microphone,
  Picture,
  Promotion,
  User,
  VideoCamera,
  WarningFilled,
} from '@element-plus/icons-vue'
import {
  getIntegrationConfig,
  getUnifiedSafetyEventDetail,
  operateUnifiedSafetyEvent,
  reviewUnifiedSafetyEventFalseAlarm,
  STAFF_TASK_EVENT_TYPES,
  submitStaffTaskResult,
} from '@/api/integration'
import { normalizeMediaUrl } from '@/utils/media'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const evidenceVisible = ref(false)
const currentEvidence = ref([])
const detail = reactive({
  event: null,
  visual_detail: null,
  timeline: [],
  evidence: [],
  review_frames: [],
  tasks: [],
})
const actionConfigs = ref([])
const processDialogVisible = ref(false)
const processModule = ref(null)
const processRunning = ref(false)
const processRouteSelection = ref('')
const processProgress = ref(0)
const processElapsed = ref(0)
const processVideoRef = ref(null)
let processTimer = null
const staffResultDialogVisible = ref(false)
const staffResultSubmitting = ref(false)
const falseAlarmDialogVisible = ref(false)
const falseAlarmSubmitting = ref(false)
const selectedFalseAlarmUrls = ref([])
const staffResultForm = reactive({
  eventType: 'PERSON_WADING',
  result: 'DRIVEN_AWAY',
  remark: '',
})
const staffResultPhotos = ref([null, null])
const staffResultPhotoPreviews = ref(['', ''])

const PROCESS_ROUTES = {
  '禁渔航线': [
    { x: 94.9, y: 24.9 }, { x: 47.4, y: 58.1 }, { x: 94.9, y: 24.9 },
  ],
  '禁涉水航线': [
    { x: 94.9, y: 24.9 }, { x: 96.3, y: 54.3 }, { x: 94.9, y: 24.9 },
  ],
  machine_dog: [
    { x: 82, y: 74 }, { x: 71, y: 65 }, { x: 61, y: 55 },
    { x: 49, y: 62 }, { x: 37, y: 48 }, { x: 26, y: 57 },
    { x: 17, y: 42 },
  ],
}

const event = computed(() => detail.event)
const visualDetail = computed(() => detail.visual_detail)
const timeline = computed(() => detail.timeline)
const displayedTimeline = computed(() => {
  const latestByAction = new Map()
  const order = []
  timeline.value.forEach((item) => {
    const key = item?.action_key || item?.action_id || `timeline:${item?.id}`
    if (!latestByAction.has(key)) order.push(key)
    latestByAction.set(key, item)
  })
  const entries = order
    .map((key) => latestByAction.get(key))
    .filter(Boolean)
  const riskReviews = entries.filter((item) => String(item?.log_type || '').toUpperCase() === 'RISK_REVIEW')
  const initiationReviews = riskReviews.filter(isRiskReviewInitiation)
  const latestInitiationReview = initiationReviews.reduce((latest, item) => {
    if (!latest) return item
    const latestTime = new Date(latest?.create_time || latest?.created_at || 0).getTime()
    const itemTime = new Date(item?.create_time || item?.created_at || 0).getTime()
    return itemTime >= latestTime ? item : latest
  }, null)
  const modelConclusions = entries.filter(isModelRiskConclusion)
  const latestModelConclusion = modelConclusions.reduce((latest, item) => {
    if (!latest) return item
    const latestTime = new Date(latest?.create_time || latest?.created_at || 0).getTime()
    const itemTime = new Date(item?.create_time || item?.created_at || 0).getTime()
    return itemTime >= latestTime ? item : latest
  }, null)
  return entries
    .filter((item) => !isLegacyDuplicateBroadcastLog(item, entries))
    // 发起记录与模型复核结论各保留一条，结论作为智能路由的最后一条独立记录。
    .filter((item) => {
      const type = String(item?.log_type || '').toUpperCase()
      if (type === 'RISK_REVIEW') {
        return isRiskReviewInitiation(item) ? item === latestInitiationReview : item === latestModelConclusion
      }
      if (isModelRiskConclusion(item)) return item === latestModelConclusion
      return true
    })
    .sort((left, right) => {
      const leftType = String(left?.log_type || '').toUpperCase()
      const rightType = String(right?.log_type || '').toUpperCase()
      const leftRiskReview = leftType === 'RISK_REVIEW'
      const rightRiskReview = rightType === 'RISK_REVIEW'
      if (leftRiskReview && rightRiskReview) {
        if (isRiskReviewInitiation(left) && !isRiskReviewInitiation(right)) return -1
        if (!isRiskReviewInitiation(left) && isRiskReviewInitiation(right)) return 1
      }
      if (leftRiskReview && isRiskReviewInitiation(left) && rightType === 'DAM_WORKFLOW') return -1
      if (leftType === 'DAM_WORKFLOW' && rightRiskReview && isRiskReviewInitiation(right)) return 1
      if (leftRiskReview && !isRiskReviewInitiation(left) && rightType === 'DAM_WORKFLOW') return 1
      if (leftType === 'DAM_WORKFLOW' && rightRiskReview && !isRiskReviewInitiation(right)) return -1
      const leftConclusion = isModelRiskConclusion(left)
      const rightConclusion = isModelRiskConclusion(right)
      if (leftConclusion && rightType === 'DAM_WORKFLOW') return 1
      if (leftType === 'DAM_WORKFLOW' && rightConclusion) return -1
      if (leftConclusion && ['ACTION', 'MANUAL', 'REPORT', 'RESOLVE'].includes(rightType)) return -1
      if (rightConclusion && ['ACTION', 'MANUAL', 'REPORT', 'RESOLVE'].includes(leftType)) return 1
      const leftReport = String(left?.log_type || '').toUpperCase() === 'REPORT'
      const rightReport = String(right?.log_type || '').toUpperCase() === 'REPORT'
      if (leftReport !== rightReport) return leftReport ? 1 : -1
      return new Date(left?.create_time || left?.created_at || 0).getTime()
        - new Date(right?.create_time || right?.created_at || 0).getTime()
    })
})
const timelineEntries = computed(() => displayedTimeline.value.map((item) => ({
  item,
  dag: workflowDag(item),
})))
const evidence = computed(() => detail.evidence)
const reviewFrames = computed(() => {
  const frames = Array.isArray(detail.review_frames) ? detail.review_frames : []
  const fallback = evidence.value.filter(isImageEvidence)
  return dedupeEvidenceFrames(frames.length ? frames : fallback).slice(0, 8)
})
const falseAlarmCandidates = computed(() => dedupeEvidenceFrames(reviewFrames.value))
const falseAlarmObjectKeys = computed(() => new Set(
  evidence.value
    .filter((item) => item.is_false_alarm)
    .flatMap((item) => [item.original_object_name, mediaObjectKey(item.file_url)])
    .filter(Boolean)
))
const linkageEvidenceDefinitions = [
  { key: 'drone', label: '无人机', limit: 4 },
  { key: 'machine_dog', label: '机器狗', limit: 4 },
  { key: 'manual', label: '人工处置', limit: 2 },
]
const linkageEvidenceItems = computed(() => linkageEvidenceDefinitions.flatMap((definition) => {
  return evidence.value
    .filter((item) => isImageEvidence(item) && linkageEvidenceKind(item) === definition.key)
    .slice(0, definition.limit)
    .map((item) => ({
      ...item,
      linkage_kind: definition.key,
      linkage_label: definition.label,
    }))
}))
const linkageEvidenceCount = computed(() => linkageEvidenceItems.value.length)
const latestTask = computed(() => detail.tasks[0] || null)
const isResolved = computed(() => event.value?.state === 'RESOLVED' || ['COMPLETED', 'FALSE_ALARM'].includes(event.value?.status))
const eventActionConfigs = computed(() => actionConfigs.value.filter((item) => item.event_id === event.value?.event_id && item.enabled))
const eventKind = computed(() => {
  if (String(event.value?.source_type || '').toLowerCase() === 'sensor') return 'sensor'
  if (visualDetail.value || String(event.value?.source_type || '').toLowerCase() === 'camera') return 'vision'
  return 'generic'
})
const eventKindLabel = computed(() => ({ vision: '视觉事件', sensor: '传感器事件', generic: '统一事件' })[eventKind.value])
const showRightRail = computed(() => Boolean(event.value))
const processEventText = computed(() => {
  const eventText = [
  event.value?.event_name,
  event.value?.summary,
  event.value?.event_code,
  event.value?.event_category,
  event.value?.event_type,
  visualDetail.value?.event_type,
  visualDetail.value?.target_type,
  ].filter(Boolean).join(' ').trim()
  return (eventText || processModule.value?.routeLabel || '').toLowerCase()
})
const processEventIsWading = computed(() => /涉水|wading|person/.test(processEventText.value))
const processEventRouteName = computed(() => processEventIsWading.value ? '禁涉水航线' : '禁渔航线')
const processEventLabel = computed(() => (
  event.value?.event_name
  || event.value?.summary
  || (processEventIsWading.value ? '禁涉水事件' : '禁渔事件')
))
const processRoutePoints = computed(() => {
  return PROCESS_ROUTES[processRouteSelection.value]
    || PROCESS_ROUTES[processModule.value?.key]
    || PROCESS_ROUTES['禁渔航线']
})
const processRoutePolyline = computed(() => processRoutePoints.value.map((point) => `${point.x},${point.y}`).join(' '))
const processMarkerPoint = computed(() => pointAtRoute(processRoutePoints.value, processProgress.value))
const processDialogTitle = computed(() => processModule.value?.key === 'machine_dog' ? '机器狗测试 · 路线巡检' : '无人机测试 · 航线巡检')
const processVideoSrc = computed(() => processEventIsWading.value ? '/demo/wading.mp4' : '/demo/fishing.mp4')
const processElapsedText = computed(() => {
  const minutes = Math.floor(processElapsed.value / 60)
  const seconds = String(processElapsed.value % 60).padStart(2, '0')
  return `${String(minutes).padStart(2, '0')}:${seconds}`
})

const eventDuration = computed(() => {
  if (!event.value?.started_at) return '--'
  const end = event.value.resolved_at || event.value.last_observed_at || new Date()
  return formatDuration(event.value.started_at, end)
})

const needsManual = computed(() => {
  if (latestTask.value) return true
  if (event.value?.risk_level === 'HIGH' && event.value?.state === 'ACTIVE') return true
  return logsForModule('manual').length > 0
})

const autoCloseText = computed(() => {
  if (!isResolved.value) return ''
  if (logsForModule('manual').length || latestTask.value) return '人工闭环'
  return '自动闭环'
})
const archivedReason = computed(() => {
  return localizeText(event.value?.resolve_reason) || '事件已闭环归档，不能继续执行人工操作'
})
const displayEventId = computed(() => formatDisplayEventId(event.value))
const reportTitle = computed(() => {
  const name = String(event.value?.event_name || event.value?.summary || '').trim()
  const baseTitle = name
    ? (name.includes('事件') ? `${name}处置报告` : `${name}事件处置报告`)
    : '事件处置报告'
  return displayEventId.value && !baseTitle.includes(displayEventId.value)
    ? `${baseTitle}_${displayEventId.value}`
    : baseTitle
})

const sensorSourceNames = {
  1: '温湿度传感器',
  2: '风速风向传感器',
  3: '雨量计',
  4: '振动传感器',
  temp_humidity: '温湿度传感器',
  wind: '风速风向传感器',
  rain: '雨量计',
  vibration: '振动传感器',
}

const detailSchemas = {
  vision: [
    ['camera', '摄像头 / 点位', () => visualDetail.value?.camera_name || event.value?.source_name || sourceLabel(event.value?.source_type)],
    ['target', '目标类型', () => targetLabel(visualDetail.value?.target_type)],
    ['zone', '检测区域', () => visualDetail.value?.zone_name],
    ['confidence', '置信度', () => confidenceText(visualDetail.value?.confidence)],
    ['started', '首次发现', () => formatTime(event.value?.started_at)],
    ['last', '最近观测', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['reason', '触发原因', () => event.value?.summary],
  ],
  sensor: [
    ['sensor', '传感器名称', () => sensorSourceName()],
    ['monitor', '监测类型', () => eventCategoryLabel(event.value?.event_category)],
    ['started', '首次触发', () => formatTime(event.value?.started_at)],
    ['last', '最近更新时间', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['area', '所属区域', () => event.value?.area_name || event.value?.zone_name],
    ['reason', '触发原因', () => event.value?.summary],
  ],
  generic: [
    ['source', '事件来源', () => sourceLabel(event.value?.source_type)],
    ['started', '首次触发', () => formatTime(event.value?.started_at)],
    ['last', '最近更新时间', () => formatTime(event.value?.last_observed_at)],
    ['duration', '持续时间', () => eventDuration.value],
    ['reason', '触发原因', () => event.value?.summary],
  ],
}

const detailFields = computed(() => {
  const schema = detailSchemas[eventKind.value] || detailSchemas.generic
  const fields = schema.map(([key, label, getter]) => ({ key, label, value: getter() })).filter((item) => hasValue(item.value))
  const common = [
    { key: 'instance', label: '事件 ID', value: displayEventId.value },
    { key: 'manual', label: '是否需要人工处置', value: needsManual.value ? '需要' : '不需要' },
    { key: 'closeMode', label: '闭环方式', value: autoCloseText.value },
  ].filter((item) => hasValue(item.value))
  return [...fields, ...common]
})

const mainFlowSteps = computed(() => {
  const failedAction = timeline.value.find((item) => isFailedStatus(item.status))
  const actionLog = firstLog((item) => item.log_type === 'ACTION')
  const manualLog = firstLog((item) => item.log_type === 'MANUAL')
  const resolveLog = firstLog((item) => item.log_type === 'RESOLVE')
  const hasLinkage = Boolean(actionLog || manualLog || latestTask.value)
  const linkageFailed = Boolean(failedAction)
  const linkageState = linkageFailed
    ? 'failed'
    : isResolved.value && hasLinkage
      ? 'done'
      : hasLinkage
        ? 'running'
        : eventActionConfigs.value.length
          ? 'pending'
          : 'skipped'
  const archiveState = isResolved.value ? 'done' : linkageState === 'failed' ? 'pending' : 'pending'
  const steps = [
    {
      key: 'trigger',
      title: '事件触发',
      state: 'done',
      statusText: '已触发',
      time: formatShortTime(event.value?.started_at),
      detail: event.value?.summary || '安全事件实例已创建',
      icon: WarningFilled,
    },
    {
      key: 'route',
      title: '智能路由',
      state: 'done',
      statusText: '已路由',
      time: formatShortTime(firstLog((item) => item.log_type === 'TRIGGER')?.create_time || event.value?.started_at),
      detail: event.value?.event_name || '系统已匹配事件定义',
      icon: Promotion,
    },
    {
      key: 'linkage',
      title: '联动处理',
      state: linkageState,
      statusText: stepStatusText(linkageState),
      time: formatShortTime((failedAction || actionLog || manualLog)?.create_time),
      detail: linkageFailed ? failedAction.message : hasLinkage ? '已产生联动或人工处置记录' : '当前事件未产生联动动作',
      icon: Connection,
    },
    {
      key: 'archive',
      title: '闭环归档',
      state: archiveState,
      statusText: isResolved.value ? '已处置' : '未开始',
      time: formatShortTime(resolveLog?.create_time || event.value?.resolved_at),
      detail: event.value?.resolve_reason || '等待事件闭环',
      icon: CircleCheckFilled,
    },
  ]
  const currentIndex = steps.findIndex((item) => item.state === 'running' || item.state === 'failed' || item.state === 'pending')
  return steps.map((item, index) => ({ ...item, current: index === currentIndex }))
})

const actionModules = computed(() => {
  const modules = [
    buildActionModule({
      key: 'broadcast',
      title: '广播设备',
      types: ['broadcast'],
      icon: Microphone,
      meta: [
        ['对象', (config, logs) => firstActionValue(config, logs, ['broadcast_device_name', 'device_name', 'object_name'])],
        ['模板', (config, logs) => firstActionValue(config, logs, ['template_name', 'template', 'template_title'])],
      ],
    }),
    buildActionModule({
      key: 'drone',
      title: '无人机设备',
      types: ['drone_dispatch', 'drone', 'uav'],
      icon: Connection,
      meta: [
        ['设备名称', (config, logs) => linkageDeviceName('drone', config, logs)],
        ['执行路径', (config, logs) => linkageRouteName('drone', config, logs)],
      ],
    }),
    buildActionModule({
      key: 'machine_dog',
      title: '机器狗设备',
      types: ['machine_dog_dispatch', 'machine_dog', 'dog_dispatch', 'robot_dog', 'robot_dispatch', 'quadruped'],
      icon: Connection,
      meta: [
        ['设备名称', (config, logs) => linkageDeviceName('machine_dog', config, logs)],
        ['执行路径', (config, logs) => linkageRouteName('machine_dog', config, logs)],
      ],
    }),
    buildActionModule({
      key: 'manual',
      title: '人工处置',
      types: ['staff_task'],
      icon: User,
      meta: [
        ['对象', (_config, logs) => latestTask.value?.assignee || firstActionValue(null, logs, ['assignee', 'operator', 'operator_name']) || '系统'],
        ['处置组别', () => latestTask.value?.assigned_group_name || '未分组'],
      ],
    }),
  ]
  return modules.filter(Boolean)
})

const operationContext = computed(() => {
  if (event.value?.status === 'FALSE_ALARM') return { title: '事件已标记为误报', hint: '误报图片已归档，可在后续标注页面用于完善模型。' }
  if (isResolved.value) return { title: '事件已归档', hint: '可继续复核现场图片并标记为误报。' }
  return { title: '人工决策', hint: '可升级风险、标记误报，或直接完成闭环。' }
})

const secondaryActions = computed(() => {
  const markedFalseAlarm = event.value?.status === 'FALSE_ALARM'
  return [
    { label: '升级风险', action: 'UPGRADE', type: 'warning', disabled: isResolved.value || event.value?.risk_level === 'HIGH' },
    { label: '完成闭环', action: 'RESOLVE', type: 'success', disabled: isResolved.value },
    { label: markedFalseAlarm ? '已标记误报' : '标记误报', action: 'FALSE_ALARM', type: 'danger', disabled: markedFalseAlarm },
  ]
})

async function loadDetail() {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    const [detailResult, configResult] = await Promise.allSettled([
      getUnifiedSafetyEventDetail(id),
      getIntegrationConfig(),
    ])
    if (detailResult.status === 'rejected') throw detailResult.reason
    const data = detailResult.value.data || {}
    detail.event = data.event || null
    detail.visual_detail = data.visual_detail || null
    detail.timeline = Array.isArray(data.timeline) ? data.timeline : []
    detail.evidence = Array.isArray(data.evidence) ? data.evidence : []
    detail.review_frames = Array.isArray(data.review_frames) ? data.review_frames : []
    detail.tasks = Array.isArray(data.tasks) ? data.tasks : []
    actionConfigs.value = configResult.status === 'fulfilled' && Array.isArray(configResult.value.data?.action_configs)
      ? configResult.value.data.action_configs
      : []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '安全事件详情暂时不可达')
  } finally {
    loading.value = false
  }
}

function buildActionModule(options) {
  const logs = logsForModule(options.key)
  if (!logs.length && !options.forceVisible) return null
  const failed = logs.find((item) => isFailedStatus(item.status))
  const last = logs[logs.length - 1]
  const config = configsForModule(options.types)[0]
  const taskStatus = options.key === 'manual' ? String(latestTask.value?.status || '').toUpperCase() : ''
  const isTaskRunning = ['ACCEPTED', 'PROCESSING'].includes(taskStatus)
  const isTaskWaiting = ['WAITING_ACCEPT', 'DISPATCHED'].includes(taskStatus)
  const isTaskDone = taskStatus === 'COMPLETED'
  const logStatus = normalizedLogStatus(last)
  const state = failed
    ? 'failed'
    : isTaskWaiting || isTaskRunning || logStatus === 'RUNNING'
      ? 'running'
      : isTaskDone || logStatus === 'DONE' || event.value?.state === 'RESOLVED'
        ? 'done'
        : last || (options.forceVisible && event.value?.state === 'ACTIVE')
          ? 'running'
          : 'done'
  const values = (options.meta || []).map(([label, getter]) => ({
    label,
    value: getter(config, logs) || '未记录',
  }))
  const objectValue = values.find((item) => ['对象', '设备名称'].includes(item.label))?.value || '未记录'
  const routeLabel = values.find((item) => ['航线', '路线', '执行路径'].includes(item.label))?.value || '未指定路线'
  const executionTime = options.key === 'manual'
    ? (
      latestTask.value?.accepted_at
      || logs.find((item) => String(parsePayload(item?.payload)?.operation || '').toUpperCase() === 'ACCEPT_TASK')?.create_time
      || latestTask.value?.completed_at
      || last?.create_time
      || last?.created_at
    )
    : (last?.create_time || last?.created_at)
  return {
    key: options.key,
    title: options.title,
    icon: options.icon,
    state,
    statusText: state === 'failed' ? '失败' : state === 'running' ? '处理中' : '已完成',
    objectValue,
    routeLabel,
    manualAction: options.key === 'manual' && (isTaskWaiting || isTaskRunning)
      ? (isTaskRunning ? 'SUBMIT_STAFF_RESULT' : 'ACCEPT_TASK')
      : null,
    manualActionLabel: isTaskRunning ? '提交现场结果' : '开始处置',
    canInspect: ['drone', 'machine_dog'].includes(options.key),
    failureReason: localizeText(failed?.message || ''),
    meta: [
      ...values,
      { label: '执行时间', value: formatTime(executionTime) },
    ].filter((item) => hasValue(item.value)),
  }
}

function configsForModule(types) {
  return eventActionConfigs.value.filter((config) => types.includes(config.action_type))
}

function logsForModule(key) {
  const actionTypes = {
    broadcast: ['broadcast', 'auto_broadcast', 'manual_broadcast', 'manual_one_touch_broadcast'],
    drone: ['drone_dispatch'],
    machine_dog: ['machine_dog_dispatch'],
    manual: ['staff_task'],
  }[key] || []
  return timeline.value.filter((item) => {
    const payload = parsePayload(item.payload)
    const types = [
      payload?.action_type,
      payload?.canonical_action_type,
      payload?.result?.action_type,
      payload?.actions?.action_type,
    ].filter(Boolean).map((value) => String(value).toLowerCase())
    if (types.some((type) => actionTypes.includes(type))) return true
    // 人工处置日志不一定带 action_type，但日志类型是确定的，不能再用描述文字模糊匹配。
    return key === 'manual' && String(item?.log_type || '').toUpperCase() === 'MANUAL'
  })
}

function firstActionValue(config, logs, keys) {
  const configPayload = parsePayload(config?.config_json)
  for (const key of keys) {
    if (hasValue(config?.[key])) return localizeText(config[key])
    if (hasValue(configPayload?.[key])) return localizeText(configPayload[key])
  }
  for (const item of [...(logs || [])].reverse()) {
    const payload = parsePayload(item?.payload)
    const sources = [
      payload,
      payload?.result,
      ...(Array.isArray(payload?.actions?.steps)
        ? payload.actions.steps.slice().reverse().flatMap((step) => [step, step?.result])
        : []),
    ]
    for (const source of sources) {
      for (const key of keys) {
        if (hasValue(source?.[key])) return localizeText(source[key])
      }
    }
  }
  return ''
}

function linkageDeviceName(kind, config, logs) {
  const named = firstActionValue(config, logs, kind === 'drone'
    ? ['drone_name', 'device_name', 'object_name']
    : ['machine_dog_name', 'dog_name', 'robot_name', 'device_name', 'object_name'])
  if (named) return named

  const identifier = firstActionValue(config, logs, kind === 'drone'
    ? ['drone_id', 'source_id']
    : ['machine_dog_id', 'dog_id', 'robot_id', 'source_id'])
  if (kind === 'machine_dog' && identifier === 'dog-01') return '绝影 Lite 3'
  return identifier || '未记录'
}

function linkageRouteName(kind, config, logs) {
  const named = firstActionValue(config, logs, ['route_name', 'wayline_name', 'path_name'])
  if (named) return named
  const routeId = firstActionValue(config, logs, ['route_id', 'wayline_id', 'path_id'])
  if (kind === 'drone') {
    return ({ fishing: '禁渔航线', wading: '禁涉水航线' })[String(routeId).toLowerCase()] || routeId || '未指定路径'
  }
  return ({
    all: '岸线由西向东巡检',
    'route-a': '岸线由西向东巡检',
    'route-b': '岸线由东向西巡检',
  })[String(routeId).toLowerCase()] || routeId || '未指定路径'
}

function firstLog(predicate) {
  return timeline.value.find(predicate)
}

function hasValue(value) {
  return value !== undefined && value !== null && value !== '' && value !== '--'
}

function stepStatusText(state) {
  return ({ done: '已完成', running: '进行中', pending: '未开始', skipped: '已跳过', failed: '异常' })[state] || state
}

function goBack() {
  router.push('/workspace/safety-events')
}

function pointAtRoute(points, progress) {
  if (!points.length) return { x: 50, y: 50 }
  if (points.length === 1) return points[0]
  const segments = []
  let total = 0
  points.forEach((point, index) => {
    if (!index) return
    const previous = points[index - 1]
    const length = Math.hypot(point.x - previous.x, point.y - previous.y)
    segments.push({ previous, point, length })
    total += length
  })
  let distance = Math.max(0, Math.min(1, progress)) * total
  for (const segment of segments) {
    if (distance <= segment.length) {
      const ratio = segment.length ? distance / segment.length : 0
      return {
        x: segment.previous.x + (segment.point.x - segment.previous.x) * ratio,
        y: segment.previous.y + (segment.point.y - segment.previous.y) * ratio,
      }
    }
    distance -= segment.length
  }
  return points[points.length - 1]
}

function openLinkageProcess(module) {
  processModule.value = module
  processRouteSelection.value = module.key === 'machine_dog' ? '巡检路线' : processEventRouteName.value
  processProgress.value = 0
  processElapsed.value = 0
  processDialogVisible.value = true
  startLinkageProcess()
}

function startLinkageProcess() {
  processRunning.value = true
  nextTick(() => ensureProcessVideoPlayback())
  clearInterval(processTimer)
  processTimer = setInterval(() => {
    processProgress.value = (processProgress.value + 0.006) % 1
    processElapsed.value += 1
  }, 1000)
}

function ensureProcessVideoPlayback() {
  if (!processRunning.value) return
  processVideoRef.value?.play?.().catch((error) => {
    console.warn('[事件详情] 演示视频播放失败:', error)
  })
}

function stopLinkageProcess() {
  processRunning.value = false
  processVideoRef.value?.pause?.()
  clearInterval(processTimer)
  processTimer = null
}

function openReport() {
  if (!event.value?.analysis_report_document_id) return
  router.push({
    name: 'DocumentEditor',
    params: { documentId: event.value.analysis_report_document_id },
    query: { mode: 'view', title: reportTitle.value },
  })
}

function evidenceForLog(logId) {
  return evidence.value.filter((item) => item.timeline_log_id === logId)
}

function openEvidence(logId) {
  const matched = logId ? evidenceForLog(logId) : []
  currentEvidence.value = matched.length ? matched : evidence.value
  evidenceVisible.value = true
}

function openEvidenceItem(item) {
  currentEvidence.value = item ? [item] : evidence.value
  evidenceVisible.value = true
}

function inferStaffEventType() {
  const existing = String(latestTask.value?.event_type || '').toUpperCase()
  if (['PERSON_WADING', 'NIGHT_FISHING', 'NATURAL_DISASTER_EVENT', 'EXTREME_WEATHER_EVENT'].includes(existing)) return existing
  const text = `${event.value?.event_name || ''} ${event.value?.summary || ''}`
  if (/暴雨|台风|极端天气|rainstorm|typhoon|weather/i.test(text)) return 'EXTREME_WEATHER_EVENT'
  if (/洪水|洪涝|flood|自然灾害/i.test(text)) return 'NATURAL_DISASTER_EVENT'
  return /捕鱼|禁渔|船只/.test(text) ? 'NIGHT_FISHING' : 'PERSON_WADING'
}

function revokeStaffPhotoPreview(index) {
  const preview = staffResultPhotoPreviews.value[index]
  if (preview && preview.startsWith('blob:')) URL.revokeObjectURL(preview)
  staffResultPhotoPreviews.value[index] = ''
}

function resetStaffResultForm() {
  for (let index = 0; index < 2; index += 1) revokeStaffPhotoPreview(index)
  staffResultPhotos.value = [null, null]
  staffResultForm.eventType = 'PERSON_WADING'
  staffResultForm.result = 'DRIVEN_AWAY'
  staffResultForm.remark = ''
}

function openStaffResultDialog() {
  resetStaffResultForm()
  staffResultForm.eventType = inferStaffEventType()
  staffResultDialogVisible.value = true
}

function selectStaffResultPhoto(index, changeEvent) {
  const file = changeEvent?.target?.files?.[0]
  if (!file) return
  revokeStaffPhotoPreview(index)
  staffResultPhotos.value[index] = file
  staffResultPhotoPreviews.value[index] = URL.createObjectURL(file)
}

async function submitStaffResult() {
  if (staffResultSubmitting.value) return
  if (staffResultPhotos.value.some((file) => !file)) {
    ElMessage.warning('请分别上传驱离前和驱离后两张照片')
    return
  }
  const formData = new FormData()
  formData.append('event_type', staffResultForm.eventType)
  formData.append('result', staffResultForm.result)
  formData.append('remark', staffResultForm.remark || '')
  staffResultPhotos.value.forEach((file) => formData.append('photos', file))
  staffResultSubmitting.value = true
  try {
    await submitStaffTaskResult(event.value.id, formData)
    ElMessage.success('现场处置结果已提交')
    staffResultDialogVisible.value = false
    await loadDetail()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '现场处置结果提交失败')
  } finally {
    staffResultSubmitting.value = false
  }
}

async function operate(action) {
  if (!event.value?.id) return
  if (action === 'FALSE_ALARM') {
    openFalseAlarmDialog()
    return
  }
  const riskLevel = action === 'UPGRADE'
    ? (event.value.risk_level === 'LOW' ? 'MEDIUM' : 'HIGH')
    : undefined
  const title = ({
    ACCEPT_TASK: '接受处置',
    COMPLETE_TASK: '完成现场处置',
    FALSE_ALARM: '标记误报',
    RESOLVE: '确认闭环',
    UPGRADE: '升级风险',
  })[action] || '事件操作'
  try {
    const { value: reason } = await ElMessageBox.prompt('请输入处置说明', title, {
      inputPlaceholder: '简要说明本次操作原因',
    })
    await operateUnifiedSafetyEvent(event.value.id, { action, risk_level: riskLevel, reason })
    ElMessage.success('事件状态已更新')
    await loadDetail()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.response?.data?.detail || '事件操作失败')
  }
}

function openFalseAlarmDialog() {
  if (!falseAlarmCandidates.value.length) {
    ElMessage.warning('当前事件没有可标记的现场图片')
    return
  }
  resetFalseAlarmSelection()
  falseAlarmDialogVisible.value = true
}

function resetFalseAlarmSelection() {
  selectedFalseAlarmUrls.value = []
}

function isFalseAlarmSelected(fileUrl) {
  return selectedFalseAlarmUrls.value.includes(fileUrl)
}

function toggleFalseAlarmSelection(fileUrl) {
  const current = selectedFalseAlarmUrls.value
  selectedFalseAlarmUrls.value = current.includes(fileUrl)
    ? current.filter((item) => item !== fileUrl)
    : [...current, fileUrl]
}

async function submitFalseAlarmReview() {
  if (!event.value?.id || !selectedFalseAlarmUrls.value.length || falseAlarmSubmitting.value) return
  falseAlarmSubmitting.value = true
  try {
    const result = await reviewUnifiedSafetyEventFalseAlarm(event.value.id, {
      file_urls: selectedFalseAlarmUrls.value,
    })
    ElMessage.success(result.message || '误报图片已归档')
    falseAlarmDialogVisible.value = false
    await loadDetail()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '误报图片归档失败')
  } finally {
    falseAlarmSubmitting.value = false
  }
}

onBeforeUnmount(() => {
  stopLinkageProcess()
  for (let index = 0; index < 2; index += 1) revokeStaffPhotoPreview(index)
})

function isFailedStatus(value) {
  return ['FAILED', 'FAIL', 'ERROR'].includes(String(value || '').toUpperCase())
}

function isImageEvidence(item) {
  const type = String(item?.evidence_type || '').toUpperCase()
  const url = String(item?.file_url || '').split('?')[0].toLowerCase()
  return type === 'IMAGE' || type.endsWith('_IMAGE') || /\.(png|jpe?g|webp|gif|bmp)$/.test(url)
}

function mediaObjectKey(url) {
  const clean = String(url || '').split('?')[0].replace(/^\/+/, '')
  const marker = '/dam/'
  const index = clean.indexOf(marker)
  if (index >= 0) return clean.slice(index + marker.length)
  return clean.replace(/^dam\//, '')
}

function isFalseAlarmFrame(item) {
  return falseAlarmObjectKeys.value.has(mediaObjectKey(item?.file_url))
}

function linkageEvidenceKind(item) {
  const source = String(item?.source_type || '').toUpperCase()
  const type = String(item?.evidence_type || '').toUpperCase()
  const text = `${item?.description || ''} ${item?.file_url || ''}`.toLowerCase()
  if (source === 'DRONE' || source === 'UAV' || type.includes('DRONE') || /无人机|drone|uav/.test(text)) return 'drone'
  if (
    ['ROBOT_DOG', 'ROBOT', 'MACHINE_DOG'].includes(source)
    || type.includes('ROBOT')
    || /机器狗|四足|robot.?dog|machine.?dog/.test(text)
  ) return 'machine_dog'
  if (['STAFF', 'MANUAL'].includes(source) || type.includes('STAFF') || /人工处置|现场处置|staff|manual/.test(text)) return 'manual'
  return ''
}

function dedupeEvidenceFrames(items) {
  const seen = new Set()
  return items.reduce((result, item, index) => {
    const url = String(item?.file_url || '').trim()
    if (!url || seen.has(url)) return result
    seen.add(url)
    result.push({
      ...item,
      id: item.id || `review-frame-${index + 1}`,
      evidence_type: item.evidence_type || 'IMAGE',
      source_type: item.source_type || 'SYSTEM',
    })
    return result
  }, [])
}

function riskClass(value) {
  return ({ LOW: 'risk-low', MEDIUM: 'risk-medium', HIGH: 'risk-high' })[value] || 'risk-unknown'
}

function riskLevelLabel(value, fallback) {
  return fallback || ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[value] || '--'
}

function statusLabel(value) {
  return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[value] || value || '--'
}

function statusClass(value) {
  return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', COMPLETED: 'is-completed', FALSE_ALARM: 'is-false-alarm' })[value] || ''
}

function logTypeLabel(value, item) {
  if (String(value || '').toUpperCase() === 'RISK_REVIEW') {
    return isRiskReviewInitiation(item) ? '事件触发' : '智能路由'
  }
  if (String(value || '').toUpperCase() === 'RISK_CHANGE' && isModelRiskConclusion(item)) return '智能路由'
  return ({
    TRIGGER: '事件触发',
    SUPPLEMENTAL_CONTEXT: '事件触发',
    RECOVERY: '条件恢复',
    WORKFLOW: '工作流',
    DAM_WORKFLOW: '智能路由',
    ACTION: '联动动作',
    REPORT: '闭环归档',
    MANUAL: '人工操作',
    RESOLVE: '闭环归档',
    SYSTEM: '系统记录',
    RISK_CHANGE: '风险变化',
  })[value] || localizeText(value) || '记录'
}

function logTitle(item) {
  const type = String(item?.log_type || '').toUpperCase()
  const status = normalizedLogStatus(item)
  const p = parsePayload(item?.payload)

  if (type === 'TRIGGER') {
    const eventName = String(p.event_name || item?.title || '安全事件').trim()
    const compactName = eventName.replace(/\s*[:：].*$/, '').replace(/\s*(已触发|触发完成)$/, '')
    return `${compactName || '安全事件'}已触发`
  }
  if (type === 'DAM_WORKFLOW') {
    if (isWorkflowPlanning(item)) return workflowStatusTitle('智能路由规划', status)
    return workflowStatusTitle('模型工作流执行', status)
  }
  if (type === 'REPORT') {
    if (status === 'RUNNING') return '事件处置报告生成中'
    if (status === 'FAILED') return '事件处置报告生成异常'
    return '事件处置报告已生成'
  }
  if (type === 'RISK_REVIEW') return isRiskReviewInitiation(item) ? '发起风险复核' : '风险复核'
  if (type === 'RISK_CHANGE' && isModelRiskConclusion(item)) return '风险复核'
  if (type === 'ACTION') {
    const action = actionTaskLabel(p)
    if (action) {
      if (status === 'RUNNING') return `${action}执行中`
      if (status === 'FAILED') return `${action}执行失败`
      return `${action}已完成`
    }
    if (status === 'RUNNING') return '联动动作执行中'
    if (status === 'FAILED') return '联动动作执行异常'
    return '所有联动动作已完成'
  }
  if (type === 'MANUAL') return status === 'FAILED' ? '人工处置异常' : '人工处置已记录'
  if (type === 'RESOLVE') {
    return String(p.operation || '').toUpperCase() === 'FALSE_ALARM'
      ? '事件已标记为误报'
      : '事件已完成闭环'
  }
  if (type === 'SUPPLEMENTAL_CONTEXT' || type === 'RISK_REVIEW') {
    return type === 'SUPPLEMENTAL_CONTEXT'
      ? '运行状态补充'
      : '风险依据复核'
  }
  return localizeText(item?.title || item?.message || item?.action || '事件记录')
}

function logMessage(item) {
  const type = String(item?.log_type || '').toUpperCase()
  const status = normalizedLogStatus(item)
  const p = parsePayload(item?.payload)

  if (type === 'SUPPLEMENTAL_CONTEXT') return ''

  if (type === 'RISK_REVIEW') {
    return ''
  }

  if (type === 'RISK_CHANGE' && isModelRiskConclusion(item)) return ''

  if (type === 'TRIGGER') {
    const source = p.source_name || p.camera_name || (eventKind.value === 'sensor' ? sensorSourceName() : sourceLabel(event.value?.source_type))
    const target = p.target_type ? targetLabel(p.target_type) : ''
    const risk = p.risk_level ? riskLevelLabel(p.risk_level) : riskLevelLabel(event.value?.risk_level)
    return `系统已从${source || '监测源'}识别${target ? `疑似${target}` : '异常情况'}，创建安全事件并评估为${risk}。`
  }
  if (type === 'DAM_WORKFLOW') {
    if (isWorkflowPlanning(item)) {
      const size = workflowSizeText(p)
      return size ? `系统已根据事件信息生成处置流程，包含${size}。` : '系统正在根据事件信息生成处置流程。'
    }
    if (status === 'RUNNING') return '系统正在执行已生成的处置流程，逐步完成分析任务。'
    if (status === 'FAILED') return '处置流程执行未完成，请检查当前节点的执行情况。'
    return ''
  }
  if (type === 'REPORT') {
    if (status === 'RUNNING') return '系统正在整理事件信息和处置结果，生成可归档的事件报告。'
    if (status === 'FAILED') return sanitizeLogText(item?.message) || '事件报告暂未生成，请检查报告生成过程。'
    return '事件处置报告已生成并归档，可在右侧打开查看。'
  }
  if (type === 'ACTION') {
    if (actionTaskLabel(p)) return ''
  }
  if (!item?.title || !item?.message) return ''
  const message = sanitizeLogText(item.message)
  return message === logTitle(item) ? '' : message
}

function timelineTone(item) {
  if (isFailedStatus(item?.status)) return 'is-failed'
  if (String(item?.log_type || '').toUpperCase() === 'RISK_REVIEW') {
    return isRiskReviewInitiation(item) ? 'is-trigger' : 'is-action'
  }
  if (String(item?.log_type || '').toUpperCase() === 'RISK_CHANGE' && isModelRiskConclusion(item)) return 'is-action'
  return ({
    TRIGGER: 'is-trigger',
    SUPPLEMENTAL_CONTEXT: 'is-trigger',
    RISK_REVIEW: 'is-trigger',
    DAM_WORKFLOW: 'is-action',
    WORKFLOW: 'is-action',
    RISK_CHANGE: 'is-warning',
    ACTION: 'is-action',
    REPORT: 'is-resolve',
    RESOLVE: 'is-resolve',
    MANUAL: 'is-manual',
  })[item?.log_type] || 'is-system'
}

function timelineNodeClass(item) {
  const type = String(item?.log_type || '').toUpperCase()
  if (type === 'RISK_REVIEW') return isRiskReviewInitiation(item) ? 'node-trigger' : 'node-routing'
  if (type === 'RISK_CHANGE' && isModelRiskConclusion(item)) return 'node-routing'
  if (['TRIGGER', 'SUPPLEMENTAL_CONTEXT'].includes(type)) return 'node-trigger'
  if (type === 'DAM_WORKFLOW' || type === 'WORKFLOW') return 'node-routing'
  if (type === 'ACTION' || type === 'MANUAL') return 'node-linkage'
  if (type === 'REPORT') return 'node-archive'
  if (type === 'RESOLVE') return 'node-archive'
  return 'node-system'
}

function normalizedLogStatus(item) {
  const status = String(item?.status || '').toUpperCase()
  if (['PROCESSING', 'RUNNING', 'PENDING'].includes(status)) return 'RUNNING'
  if (['FAILED', 'FAIL', 'ERROR'].includes(status)) return 'FAILED'
  if (['SUCCESS', 'COMPLETED', 'DONE'].includes(status)) return 'DONE'
  return status
}

function workflowStatusTitle(label, status) {
  if (status === 'RUNNING') return `${label}中`
  if (status === 'FAILED') return `${label}异常`
  return `${label}已完成`
}

function workflowSizeText(payload) {
  if (payload?.node_count == null) return ''
  return `${payload.node_count}个节点、${payload.edge_count ?? 0}条边`
}

function isRiskReviewInitiation(item) {
  if (String(item?.log_type || '').toUpperCase() !== 'RISK_REVIEW') return false
  const payload = parsePayload(item?.payload)
  const text = `${item?.title || ''} ${item?.message || ''}`
  return payload.pending_model_review === true
    || /待模型确认|提交.*模型复核|发起.*风险复核/.test(text)
}

function modelRiskReviewConclusionText() {
  const conclusion = timeline.value
    .filter(isModelRiskConclusion)
    .sort((left, right) => new Date(left?.create_time || left?.created_at || 0).getTime()
      - new Date(right?.create_time || right?.created_at || 0).getTime())
    .at(-1)
  if (!conclusion) return ''
  const payload = parsePayload(conclusion.payload)
  const risk = payload.model_risk_level || payload.risk_after
  if (!risk) return sanitizeLogText(conclusion.message || '')
  const label = riskLevelLabel(String(risk).toUpperCase())
  const upgraded = String(payload.escalation_source || '').includes('dam_model')
    && String(payload.risk_before || '').toUpperCase() !== String(risk).toUpperCase()
  if (!upgraded) return `${label} 未变化`
  return `${label} 已升级`
}

function isModelRiskUpgrade(item) {
  const payload = parsePayload(item?.payload)
  const risk = payload.model_risk_level || payload.risk_after
  return Boolean(risk)
    && String(payload.escalation_source || '').includes('dam_model')
    && String(payload.risk_before || '').toUpperCase() !== String(risk).toUpperCase()
}

function modelRiskReviewReason(item) {
  if (!isModelRiskUpgrade(item)) return ''
  const payload = parsePayload(item?.payload)
  return sanitizeLogText(payload.reason || '')
}

function isModelRiskConclusion(item) {
  const type = String(item?.log_type || '').toUpperCase()
  const payload = parsePayload(item?.payload)
  if (type === 'RISK_REVIEW') return !isRiskReviewInitiation(item)
  return type === 'RISK_CHANGE' && String(payload.escalation_source || '').includes('dam_model')
}

function isWorkflowPlanning(item) {
  return String(item?.log_type || '').toUpperCase() === 'DAM_WORKFLOW'
    && (/plan|规划/.test(`${item?.action_key || ''} ${item?.title || ''}`.toLowerCase()))
}

function sanitizeLogText(value) {
  let text = localizeText(value)
  text = text
    .replace(/\s*[（(]\s*(成功|失败|success|failed)\s*[）)]/gi, '')
    .replace(/\s*[（(]\s*报告编号\s*\d+\s*[）)]/g, '')
    .replace(/\s*报告编号\s*[:：]?\s*\d+/g, '')
    .replace(/\s*(Qwen[\w.-]*|云端增强分析|本地报告兜底)\s*/gi, ' ')
    .replace(/\s{2,}/g, ' ')
    .replace(/[：:，,。]\s*[：:，,。]/g, '。')
    .trim()
  return text
}

// 动作类型 -> 中文（覆盖人工操作 operation 与后端 action_type 两种命名）
function actionTypeLabel(value) {
  const labels = {
    ACKNOWLEDGE: '确认事件',
    DISPATCH_TASK: '派发任务',
    ACCEPT_TASK: '接受任务',
    COMPLETE_TASK: '完成任务',
    FALSE_ALARM: '标记误报',
    RESOLVE: '解除事件',
    UPGRADE: '风险升级',
    STAFF_COMPLETED: '现场处置完成',
    broadcast: '自动广播',
    AUTO_BROADCAST: '系统自动广播',
    MANUAL_BROADCAST: '人工广播',
    MANUAL_ONE_TOUCH_BROADCAST: '一键喊话',
    drone_dispatch: '无人机派飞',
    DRONE_DISPATCH: '系统自动派飞',
    staff_task: '人工处置任务',
    STAFF_DISPATCH: '创建处置任务',
    alert: '告警通知',
    camera_snapshot: '摄像头抓拍',
    llm: '大模型分析',
    http: 'HTTP 调用',
    script: '脚本执行',
  }
  return labels[value] || localizeText(value) || ''
}

function actionTaskLabel(payload) {
  return localizeText(
    payload?.step_name
    || payload?.action_name
    || payload?.action_label
    || (payload?.action_type ? actionTypeLabel(payload.action_type) : ''),
  )
}

function actionDeviceNames(payload) {
  const names = []
  const add = (value) => {
    if (value === undefined || value === null || String(value).trim() === '') return
    const name = localizeText(value).trim()
    if (name && !names.includes(name)) names.push(name)
  }
  const addList = (items) => {
    if (!Array.isArray(items)) return
    items.forEach((item) => {
      if (typeof item === 'string') add(item)
      else add(item?.device_name || item?.name || item?.device_id)
    })
  }

  add(payload?.device_name || payload?.broadcast_device_name)
  addList(payload?.device_names)
  addList(payload?.devices)
  addList(payload?.actions?.steps)
  add(payload?.result?.device_name)
  addList(payload?.result?.devices)
  return names.join('、')
}

// 模型库工作流执行状态 -> 中文
function executionStatusLabel(value) {
  return ({ success: '成功', failed: '失败', not_submitted: '未提交', SUCCESS: '成功', FAILED: '失败', NOT_SUBMITTED: '未提交' })[value] || value || ''
}

// payload 可能是对象或 JSON 字符串，统一转对象
function parsePayload(payload) {
  if (!payload) return {}
  if (typeof payload === 'object') return payload
  try {
    return JSON.parse(payload)
  } catch (e) {
    return {}
  }
}

function hasCloudReviewFailure(payload) {
  const nodeResults = payload?.execution_result?.node_results
  if (!Array.isArray(nodeResults)) return false
  return nodeResults.some((node) => {
    if (String(node?.node_id || '') !== 'action_report') return false
    return !['success', 'skipped'].includes(String(node?.status || '').toLowerCase())
  })
}

function workflowFallbackUsed(payload) {
  return payload?.fallback_used === true || payload?.fallback_used === 'true' || hasCloudReviewFailure(payload)
}

// 旧版 ECA 自动广播会同时写入广播服务记录和流程步骤记录；详情只保留后者。
function isLegacyDuplicateBroadcastLog(item, entries) {
  const key = String(item?.action_key || '')
  const payload = parsePayload(item?.payload)
  if (!key.startsWith('manual-broadcast:') || payload.action_type !== 'AUTO_BROADCAST') return false

  const timestamp = new Date(item?.create_time || item?.created_at || 0).getTime()
  return entries.some((candidate) => {
    const candidateKey = String(candidate?.action_key || '')
    const candidatePayload = parsePayload(candidate?.payload)
    if (!candidateKey.startsWith('eca-step:') || candidatePayload.action_type !== 'broadcast') return false
    const candidateTimestamp = new Date(candidate?.create_time || candidate?.created_at || 0).getTime()
    return Number.isFinite(timestamp)
      && Number.isFinite(candidateTimestamp)
      && Math.abs(candidateTimestamp - timestamp) <= 2 * 60 * 1000
  })
}

// 动作执行结果 -> 可读文本
function resultStatusText(result) {
  if (!result) return ''
  if (typeof result === 'string') return localizeText(result)
  if (typeof result === 'object') {
    const bits = []
    if (result.status) bits.push(localizeText(result.status))
    if (result.message) bits.push(result.message)
    return bits.join('：')
  }
  return ''
}

// 记录流每条日志下方的结构化明细区（按日志类型取 payload 字段）
function logDetailFields(item) {
  const p = parsePayload(item?.payload)
  const type = item?.log_type
  const fields = []
  const push = (label, value) => {
    if (value === undefined || value === null) return
    if (String(value).trim() === '') return
    fields.push({ label, value: String(value) })
  }
  const pushConclusion = (value) => {
    if (value === undefined || value === null) return
    if (String(value).trim() === '') return
    fields.push({
      label: isModelRiskUpgrade(item) ? '模型复核结论' : '复核结论',
      value: String(value),
    })
  }

  if (type === 'TRIGGER') {
    push('来源', p.source_name || p.camera_name || sensorSourceName())
    push('事件编号', p.instance_no)
    push('初判风险', p.risk_level ? riskLevelLabel(p.risk_level) : '')
    push('目标类型', p.target_type ? targetLabel(p.target_type) : '')
    if (p.confidence != null) push('置信度', Number(p.confidence).toFixed(2))
  } else if (type === 'DAM_WORKFLOW') {
    if (!isWorkflowPlanning(item) && (p.fallback_used != null || hasCloudReviewFailure(p))) {
      push(
        '处置结果来源',
        workflowFallbackUsed(p)
          ? '云端结果复核未成功返回，系统已启用本地备用分析路径继续生成处置结果。'
          : '已使用智能分析结果完成处置，未启用备用分析路径。',
      )
    }
  } else if (type === 'ACTION') {
    const actionType = String(p.action_type || p.result?.action_type || '').toLowerCase()
    const devices = actionDeviceNames(p)
    // 机器狗和无人机任务要明确展示实际设备与执行路径；其他动作沿用通用设备明细。
    if (actionType === 'machine_dog_dispatch') {
      push('设备名称', linkageDeviceName('machine_dog', null, [{ payload: p }]))
      push('执行路径', linkageRouteName('machine_dog', null, [{ payload: p }]))
    } else if (actionType === 'drone_dispatch') {
      push('设备名称', linkageDeviceName('drone', null, [{ payload: p }]))
      push('执行路径', linkageRouteName('drone', null, [{ payload: p }]))
    } else if (devices && actionTaskLabel(p)) {
      push('联动设备', devices)
    }
    if (p.total_count != null) {
      const failedText = p.failed_devices?.length ? `，失败：${p.failed_devices.join('、')}` : ''
      push('广播结果', `${p.success_count ?? 0}/${p.total_count} 台成功${failedText}`)
    }
    const nestedAction = p.actions && typeof p.actions === 'object' ? p.actions : p
    const nestedSteps = Array.isArray(nestedAction.steps) ? nestedAction.steps : []
    const resourceInfo = nestedAction.resource_info && typeof nestedAction.resource_info === 'object'
      ? nestedAction.resource_info
      : {}
    const nestedFailed = nestedSteps.filter((step) => step && step.success === false).length
    const stepCount = nestedSteps.length
      ? (resourceInfo.executed_steps_count ?? nestedSteps.length)
      : p.step_count
    const successfulCount = nestedSteps.length
      ? nestedSteps.filter((step) => step && step.success === true).length
      : (p.success_count ?? Math.max(0, Number(stepCount || 0) - Number(p.failure_count || 0) - Number(p.skipped_count || 0)))
    const skippedCount = nestedSteps.length || Object.keys(resourceInfo).length
      ? (resourceInfo.skipped_steps_count ?? p.skipped_count ?? 0)
      : p.skipped_count
    const failureCount = nestedSteps.length
      ? Math.max(nestedFailed, resourceInfo.failure_count ?? 0)
      : p.failure_count
    if (stepCount != null) push('执行统计', `成功 ${successfulCount} / 跳过 ${skippedCount ?? 0} / 失败 ${failureCount ?? 0}`)
    if (p.channels?.length) push('通知渠道', p.channels.join('、'))
    push('失败原因', p.error)
  } else if (type === 'SUPPLEMENTAL_CONTEXT') {
    const sc = p.supplemental_context || {}
    push('运行状态', sc.label)
    push('影响区域', sc.affected_area)
    push('备注', sc.note)
  } else if (type === 'RISK_CHANGE') {
    if (isModelRiskConclusion(item)) {
      pushConclusion(modelRiskReviewConclusionText())
      push('升级原因', modelRiskReviewReason(item))
    } else {
      if (p.risk_before || p.risk_after) push('风险变化', `${riskLevelLabel(p.risk_before)} → ${riskLevelLabel(p.risk_after)}`)
      push('变化原因', p.reason)
      push('触发方式', p.operation === 'UPGRADE' ? '人工升级' : (p.escalation_source === 'knowledge_base' ? '系统·知识库依据' : ''))
      if (p.from_status && p.to_status) push('状态流转', `${statusLabel(p.from_status)} → ${statusLabel(p.to_status)}`)
    }
  } else if (type === 'RISK_REVIEW') {
    if (!isRiskReviewInitiation(item)) {
      pushConclusion(modelRiskReviewConclusionText())
      push('升级原因', modelRiskReviewReason(item))
    }
  } else if (type === 'REPORT') {
    if (p.error) push('生成说明', p.error)
  } else if (type === 'MANUAL' || type === 'RESOLVE') {
    push('处置动作', p.operation ? actionTypeLabel(p.operation) : (p.canonical_action_type ? actionTypeLabel(p.canonical_action_type) : ''))
    if (p.from_status && p.to_status) push('状态流转', `${statusLabel(p.from_status)} → ${statusLabel(p.to_status)}`)
    if (p.false_alarm_evidence_count != null) push('误报图片', `${p.false_alarm_evidence_count} 张已归档`)
    push('责任人', p.assignee)
    push('任务编号', p.task_id)
    push('现场结果', p.result_label)
    push('处置说明', p.reason)
    push('备注', p.remark)
  }
  return fields
}

function workflowDag(item) {
  // 只在智能路由规划完成后展示一次流程图，其余日志保留文字摘要即可。
  if (!isWorkflowPlanning(item) || normalizedLogStatus(item) !== 'DONE') return null
  const ownPayload = parsePayload(item?.payload)
  const isWorkflowLog = ['DAM_WORKFLOW', 'WORKFLOW'].includes(String(item?.log_type || '').toUpperCase())
  if (!isWorkflowLog) return null

  let dag = ownPayload.final_dag || ownPayload.dag || ownPayload.workflow
  if (!dag || !Array.isArray(dag.nodes) || !dag.nodes.length) {
    const related = [...timeline.value].reverse().find((row) => {
      if (!['DAM_WORKFLOW', 'WORKFLOW'].includes(String(row?.log_type || '').toUpperCase())) return false
      const payload = parsePayload(row?.payload)
      const candidate = payload.final_dag || payload.dag || payload.workflow
      return Array.isArray(candidate?.nodes) && candidate.nodes.length
    })
    if (related) {
      const payload = parsePayload(related.payload)
      dag = payload.final_dag || payload.dag || payload.workflow
    }
  }
  if (!dag || !Array.isArray(dag.nodes) || !dag.nodes.length) return null

  const rawNodes = dag.nodes.filter((node) => node && (node.node_id || node.id || node.key))
  const nodeIds = rawNodes.map((node) => String(node.node_id || node.id || node.key))
  const nodeSet = new Set(nodeIds)
  const rawEdges = Array.isArray(dag.edges) ? dag.edges : []
  const edges = rawEdges
    .map((edge, index) => ({
      key: `${edge?.source || edge?.from || ''}-${edge?.target || edge?.to || ''}-${index}`,
      source: String(edge?.source || edge?.from || ''),
      target: String(edge?.target || edge?.to || ''),
    }))
    .filter((edge) => nodeSet.has(edge.source) && nodeSet.has(edge.target) && edge.source !== edge.target)

  const incoming = new Map(nodeIds.map((id) => [id, 0]))
  const outgoing = new Map(nodeIds.map((id) => [id, []]))
  edges.forEach((edge) => {
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1)
    outgoing.get(edge.source).push(edge.target)
  })

  const levels = []
  const levelById = new Map()
  let queue = nodeIds.filter((id) => incoming.get(id) === 0)
  if (!queue.length) queue = nodeIds.slice(0, 1)
  const visited = new Set()
  while (queue.length) {
    const current = queue.filter((id) => !visited.has(id))
    if (!current.length) break
    levels.push(current)
    current.forEach((id) => {
      visited.add(id)
      levelById.set(id, levels.length - 1)
    })
    const next = []
    current.forEach((id) => {
      outgoing.get(id).forEach((target) => {
        if (!visited.has(target) && !next.includes(target)) next.push(target)
      })
    })
    queue = next
  }
  const remaining = nodeIds.filter((id) => !visited.has(id))
  if (remaining.length) {
    levels.push(remaining)
    remaining.forEach((id) => levelById.set(id, levels.length - 1))
  }

  const nodeWidth = 124
  const nodeHeight = 54
  const levelGap = 28
  const rowGap = 14
  const sidePadding = 16
  const topPadding = 18
  const maxRows = Math.max(...levels.map((level) => level.length), 1)
  const width = Math.max(430, sidePadding * 2 + levels.length * nodeWidth + Math.max(0, levels.length - 1) * levelGap)
  const height = Math.max(86, topPadding * 2 + maxRows * nodeHeight + Math.max(0, maxRows - 1) * rowGap)
  const positions = new Map()
  const nodes = levels.flatMap((level, levelIndex) => level.map((id, rowIndex) => {
    const raw = rawNodes.find((node) => String(node.node_id || node.id || node.key) === id) || {}
    const x = sidePadding + levelIndex * (nodeWidth + levelGap)
    const y = topPadding + rowIndex * (nodeHeight + rowGap)
    const fullLabel = dagNodeLabel(raw, id, nodeIds.indexOf(id) + 1)
    const label = fullLabel.length > 10 ? `${fullLabel.slice(0, 9)}…` : fullLabel
    const modelLabel = dagModelLabel(raw, id)
    const modelFullLabel = dagModelFullLabel(raw, id)
    const node = {
      id,
      x,
      y,
      width: nodeWidth,
      height: nodeHeight,
      label,
      fullLabel,
      modelLabel,
      modelFullLabel,
      tone: dagNodeTone(raw.node_class || raw.node_type),
    }
    positions.set(id, node)
    return node
  }))

  return {
    width,
    height,
    nodes,
    edges: edges.map((edge) => {
      const source = positions.get(edge.source)
      const target = positions.get(edge.target)
      if (!source || !target) return null
      const x1 = source.x + source.width
      const y1 = source.y + source.height / 2
      const x2 = target.x
      const y2 = target.y + target.height / 2
      const bend = Math.max(18, (x2 - x1) / 2)
      return { ...edge, path: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}` }
    }).filter(Boolean),
  }
}

function dagNodeTone(value) {
  const type = String(value || '').toUpperCase()
  if (type === 'START') return 'is-start'
  if (type === 'END') return 'is-end'
  if (type.includes('MODEL') || type.includes('LLM')) return 'is-model'
  return 'is-task'
}

function dagNodeLabel(node, nodeId, index) {
  const fixedLabels = {
    action_reasoning: '边端场景理解',
    action_report: '云端结果复核',
    local_llm_0: '边端场景理解',
    cloud_llm_0: '云端结果复核',
  }
  if (fixedLabels[nodeId]) return fixedLabels[nodeId]

  const rawLabel = String(node?.node_name || node?.name || node?.title || node?.model_task || node?.node_type || '').trim()
  if (/[\u4e00-\u9fff]/.test(rawLabel)) return rawLabel

  const text = `${rawLabel} ${nodeId}`.toLowerCase()
  const aliases = [
    [/start|input|begin/, '开始处理'],
    [/classif|classify/, '目标分类'],
    [/scene|behavior|understand/, '场景理解'],
    [/risk|fusion|assess/, '风险研判'],
    [/review|final/, '结果复核'],
    [/detect|detection|track/, '目标检测'],
    [/report|generate|end/, '分析结果生成'],
    [/local/, '本地分析'],
    [/cloud|llm|model/, '智能分析'],
  ]
  const matched = aliases.find(([pattern]) => pattern.test(text))
  return matched ? matched[1] : `处置步骤${index}`
}

function dagModelFullLabel(node, nodeId) {
  const rawModel = String(node?.model_name || node?.model_label || node?.model_family || '').trim()
  if (rawModel) {
    return `（${localizeText(rawModel)}）`
  }

  const category = String(node?.model_category || '').toLowerCase()
  if (category === 'local_llm' || /reasoning|understanding|risk/.test(String(node?.model_task || '').toLowerCase())) {
    return '（端侧模型）'
  }
  if (category === 'cloud_llm' || /report|final|review/.test(String(node?.model_task || '').toLowerCase())) {
    return '（云端模型）'
  }
  if (String(nodeId).includes('classify') || String(nodeId).includes('detect')) return '（专用模型）'
  return ''
}

function dagModelLabel(node, nodeId) {
  const fullLabel = dagModelFullLabel(node, nodeId)
  return fullLabel.length > 12 ? `${fullLabel.slice(0, 11)}…）` : fullLabel
}

function targetLabel(value) {
  return ({
    person: '人员',
    boat: '船只',
    vehicle: '车辆',
    fire: '火点',
    qwen_camera_screening: '智能视觉复核',
    camera_screening: '视觉筛查',
  })[value] || localizeText(value) || ''
}

function sourceLabel(value) {
  return ({ CAMERA: '摄像头', DRONE: '无人机', STAFF: '人工上传', SYSTEM: '系统', camera: '摄像头', sensor: '传感器' })[value] || value || ''
}

function sensorSourceName() {
  const sourceName = event.value?.source_name
  if (sourceName && sourceName !== 'sensor') return sourceName
  const sourceId = event.value?.source_id
  if (sensorSourceNames[sourceId]) return sensorSourceNames[sourceId]
  return sensorSourceNames[String(sourceId)] || sourceLabel(event.value?.source_type)
}

function formatDisplayEventId(row) {
  if (!row) return ''
  if (row.display_instance_no) return row.display_instance_no
  const text = String(row.instance_no || '').trim()
  const date = dateToken(text) || dateToken(row.started_at)
  if (!date) return row.instance_no || ''
  const sequence = instanceSequence(text) || 1
  const shortSequence = String(sequence || 1).padStart(3, '0')
  return `EVT_${date}_${shortSequence}`
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
  const text = String(value || '')
  const matched = text.match(/_(\d{1,4})$/)
  return matched?.[1] || ''
}

function eventCategoryLabel(value) {
  return ({
    PERSON_SAFETY: '人员安全',
    ILLEGAL_FISHING: '非法捕捞',
    SENSOR: '传感器监测',
    ENVIRONMENT: '环境监测',
  })[value] || localizeText(value) || ''
}

function evidenceTypeLabel(value) {
  return ({ IMAGE: '图片证据', VIDEO: '视频证据', FILE: '文件证据' })[value] || value || '证据文件'
}

function operatorLabel(value) {
  if (!value) return '系统记录'
  return value === 'SYSTEM' ? '系统自动' : value
}

function localizeText(value) {
  if (!value) return ''
  let text = String(value)
  const replacements = [
    ['DAM_WORKFLOW', '智能路由'],
    ['qwen_camera_screening', '智能视觉复核'],
    ['camera_screening', '视觉筛查'],
    ['camera_condition_recovered', '摄像头条件已恢复'],
    ['condition_recovered', '触发条件已恢复'],
    ['PERSON_SAFETY', '人员安全'],
    ['ILLEGAL_FISHING', '非法捕捞'],
    ['TRIGGER', '事件触发'],
    ['RECOVERY', '条件恢复'],
    ['WORKFLOW', '工作流'],
    ['ACTION', '联动动作'],
    ['REPORT', '报告'],
    ['MANUAL', '人工操作'],
    ['RESOLVE', '闭环'],
    ['SYSTEM', '系统'],
    ['SUCCESS', '成功'],
    ['FAILED', '失败'],
    ['failed', '失败'],
    ['success', '成功'],
    ['PENDING', '待处理'],
    ['PROCESSING', '处理中'],
    ['COMPLETED', '已完成'],
    ['FALSE_ALARM', '误报'],
    ['broadcast', '广播'],
    ['drone_dispatch', '无人机派飞'],
    ['staff_task', '人工处置任务'],
    ['manual-operation', '人工操作'],
    ['manual operation', '人工操作'],
    ['eca flow completed', '事件处置流程已完成'],
  ]
  replacements.forEach(([from, to]) => {
    text = text.replaceAll(from, to)
  })
  return text.replaceAll('_', ' ')
}

function relatedLogLabel(logId) {
  const log = timeline.value.find((item) => item.id === logId)
  return log ? (log.title || logTypeLabel(log.log_type)) : '未关联日志'
}

function confidenceText(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : ''
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', { hour12: false })
}

function formatShortTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

function formatDuration(startValue, endValue) {
  const start = new Date(startValue)
  const end = new Date(endValue)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '--'
  const seconds = Math.max(0, Math.floor((end.getTime() - start.getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

loadDetail()
</script>

<style scoped>
.event-workbench {
  position: relative;
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background:
    radial-gradient(circle at 50% -20%, rgba(42, 111, 151, .22), transparent 34%),
    linear-gradient(180deg, #081827 0%, #050d18 100%);
}
.risk-badge,
.status-badge {
  min-width: 78px;
  padding: 7px 10px;
  border-radius: 6px;
  text-align: center;
  background: rgba(12, 34, 54, .95);
}
.risk-badge.risk-high {
  color: #ffd6da;
  background: rgba(150, 39, 54, .58);
}
.risk-badge.risk-medium {
  color: #ffe7ac;
  background: rgba(142, 102, 22, .5);
}
.risk-badge.risk-low {
  color: #c9f7e4;
  background: rgba(30, 111, 86, .5);
}
.status-badge.is-pending {
  color: #f0c75d;
}
.status-badge.is-processing {
  color: #69d8ff;
}
.status-badge.is-completed,
.status-badge.is-false-alarm {
  color: #7ee2bd;
}
.major-flow {
  position: sticky;
  top: 0;
  z-index: 20;
  margin-top: 0;
  min-height: 132px;
  padding: 20px 26px 22px;
  overflow: hidden;
  border: 1px solid rgba(51, 151, 204, .12);
  border-radius: 8px;
  display: block;
  background:
    linear-gradient(180deg, rgba(7, 28, 47, .82), rgba(4, 19, 34, .96)),
    rgba(8, 23, 39, .96);
  backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .08), 0 18px 38px rgba(0, 0, 0, .28);
}
.flow-header {
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 18px;
}
.flow-back-button {
  position: relative;
  z-index: 4;
  width: fit-content;
  height: 42px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 15px 0 13px;
  border: 1px solid rgba(104, 161, 200, .26);
  border-radius: 999px;
  color: #b4d0df;
  font-size: 14px;
  background: rgba(4, 16, 27, .34);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .03);
  cursor: pointer;
}
.flow-back-button:hover {
  color: #eff9ff;
  border-color: rgba(105, 216, 255, .42);
  background: rgba(10, 38, 60, .72);
  box-shadow: 0 0 18px rgba(72, 216, 255, .08), inset 0 1px 0 rgba(255, 255, 255, .05);
}
.flow-back-button .el-icon {
  font-size: 15px;
}
.flow-header-divider {
  width: 1px;
  height: 30px;
  flex: 0 0 1px;
  background: rgba(142, 190, 215, .42);
}
.flow-main {
  min-width: 0;
}
.flow-heading {
  margin: 0;
  color: #f5fbff;
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: .01em;
}
.flow-rail {
  position: relative;
  margin: 25px 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  list-style: none;
}
.flow-rail li {
  position: relative;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0;
  text-align: center;
}
.flow-node {
  position: relative;
  z-index: 2;
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(110, 160, 194, .34);
  border-radius: 12px;
  color: #93afc3;
  background: rgba(8, 25, 42, .9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .06),
    0 8px 18px rgba(0, 0, 0, .18);
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}
.flow-node::before {
  content: "";
  position: absolute;
  inset: auto auto 8px 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  opacity: .72;
  box-shadow: 0 0 10px currentColor;
}
.flow-node .el-icon {
  position: relative;
  z-index: 1;
  font-size: 24px;
}
.flow-text {
  position: relative;
  z-index: 2;
  margin-top: 10px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.flow-text strong,
.flow-text span,
.flow-text time {
  display: block;
}
.flow-text strong {
  color: #f5fbff;
  font-size: 19px;
  line-height: 1.2;
}
.flow-text span {
  width: fit-content;
  margin-top: 7px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(36, 226, 175, .28);
  color: #29f0bc;
  font-size: 13px;
  line-height: normal;
  background: rgba(11, 93, 78, .22);
  box-shadow: inset 0 0 10px rgba(21, 201, 159, .07);
}
.flow-text span::before {
  content: "";
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  vertical-align: 1px;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}
.flow-text time {
  margin-top: 5px;
  min-height: 17px;
  color: #9fb7c8;
  font-size: 12px;
}
.flow-rail li.done .flow-node {
  border-color: rgba(102, 215, 178, .48);
  color: #66d7b2;
  background: rgba(20, 74, 61, .34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 8px 18px rgba(0, 0, 0, .18);
}
.flow-rail li.running .flow-node {
  border-color: rgba(72, 216, 255, .58);
  color: #48d8ff;
  background: rgba(21, 79, 105, .34);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 10px 18px rgba(0, 0, 0, .18),
    0 0 0 3px rgba(72, 216, 255, .08);
  animation: subtlePulse 1.8s ease-in-out infinite;
}
.flow-rail li.pending .flow-node {
  border-color: rgba(120, 152, 173, .28);
  color: #7898ad;
  background: rgba(8, 25, 42, .86);
}
.flow-rail li.skipped .flow-node {
  border-color: rgba(120, 152, 173, .18);
  color: #6f8798;
  background: rgba(18, 32, 48, .72);
}
.flow-rail li.failed .flow-node {
  border-color: rgba(255, 107, 118, .56);
  color: #ff6b76;
  background: rgba(110, 34, 47, .38);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .08),
    0 10px 18px rgba(0, 0, 0, .18),
    0 0 0 3px rgba(255, 107, 118, .08);
}
.flow-rail li.current .flow-text strong {
  color: #69d8ff;
}
.flow-rail li.done .flow-text span,
.major-flow.is-resolved .flow-text span {
  color: #29f0bc;
  border-color: rgba(36, 226, 175, .28);
  background: rgba(11, 93, 78, .22);
}
.flow-rail li.running .flow-text span {
  color: #69d8ff;
  border-color: rgba(105, 216, 255, .28);
  background: rgba(21, 79, 105, .2);
}
.flow-rail li.failed .flow-text span {
  color: #ff8c98;
  border-color: rgba(255, 107, 118, .28);
  background: rgba(110, 34, 47, .22);
}
.flow-rail li.skipped .flow-text span,
.flow-rail li.pending .flow-text span {
  color: #8faabd;
  border-color: rgba(120, 152, 173, .2);
  background: rgba(126, 171, 202, .08);
}
.flow-connector {
  position: absolute;
  left: calc(50% + 27px);
  top: 13px;
  width: calc(100% - 54px);
  height: 28px;
  overflow: visible;
  pointer-events: none;
}
.flow-connector path {
  fill: none;
  stroke: rgba(120, 152, 173, .3);
  stroke-width: 1.5;
  stroke-linecap: round;
}
.connector-fill {
  stroke: #7ee2bd;
  stroke-width: 1.7 !important;
  stroke-dasharray: none;
  animation: none;
  filter: drop-shadow(0 0 2px rgba(126, 226, 189, .45));
}
.connector-arrow {
  stroke: rgba(142, 188, 207, .55) !important;
  stroke-width: 1.4 !important;
}
.flow-rail li.done .connector-arrow,
.flow-rail li.running .connector-arrow {
  stroke: rgba(126, 226, 189, .82) !important;
}
.major-flow.is-resolved .connector-fill {
  stroke-dasharray: none;
  animation: none;
}
.flow-rail li.failed .connector-fill {
  stroke: #d85667;
}
.flow-rail li.skipped .connector-fill {
  stroke: rgba(143, 164, 178, .42);
  stroke-dasharray: 4 8;
}
.workspace-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(320px, 24vw, 400px);
  gap: 16px;
  align-items: start;
}
.side-stack {
  position: sticky;
  top: 16px;
  display: grid;
  gap: 16px;
  align-self: start;
}
.workspace-grid.no-linkage {
  grid-template-columns: minmax(0, 1fr);
}
.primary-stack {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.work-card {
  min-width: 0;
  padding: 20px;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(13, 38, 60, .88), rgba(8, 25, 42, .88)),
    rgba(10, 29, 48, .88);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .07), 0 14px 34px rgba(0, 0, 0, .16);
}
.detail-card {
  position: relative;
  overflow: hidden;
}
.detail-card::after {
  content: "";
  position: absolute;
  top: 18px;
  right: 0;
  width: 4px;
  height: 150px;
  border-radius: 999px 0 0 999px;
  background: linear-gradient(180deg, #69d8ff, rgba(105, 216, 255, .08));
}
.detail-hero {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 20px;
  align-items: start;
  padding-bottom: 18px;
}
.detail-title-block {
  min-width: 0;
}
.detail-title-block span,
.card-heading span {
  display: block;
  color: #7fb1d4;
  font-size: 13px;
}
.detail-title-block h2 {
  margin: 6px 0 8px;
  color: #f9fdff;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: 0;
}
.detail-title-block p {
  margin: 0;
  color: #9fbed2;
  font-size: 15px;
  line-height: 1.55;
}
.detail-status-block {
  min-width: 230px;
  display: grid;
  justify-items: end;
  gap: 8px;
  color: #8faabd;
  font-size: 13px;
}
.detail-badges {
  display: flex;
  gap: 8px;
}
.detail-status-block time,
.detail-status-block small {
  display: block;
}
.card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.card-heading h2 {
  margin: 4px 0 0;
  color: #f4f9fd;
  font-size: 20px;
  letter-spacing: 0;
}
.card-heading small {
  color: #7f9eb3;
}
.evidence-card,
.log-card,
.linkage-card,
.linkage-evidence-card {
  background:
    linear-gradient(180deg, rgba(11, 34, 54, .82), rgba(7, 22, 37, .86)),
    rgba(8, 25, 42, .88);
}
.linkage-evidence-strip {
  margin-top: 16px;
}
.linkage-evidence-item {
  flex-basis: clamp(220px, 23vw, 320px);
}
.linkage-evidence-item footer span {
  color: #f2fbff;
}
.linkage-evidence-item footer b {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  margin-right: 6px;
  padding: 0 7px;
  border: 1px solid rgba(105, 216, 255, .28);
  border-radius: 999px;
  color: #9bdff6;
  background: rgba(6, 37, 55, .78);
  font-size: 11px;
  font-weight: 800;
  vertical-align: 1px;
}
.linkage-evidence-item footer b.linkage-source-machine_dog {
  border-color: rgba(126, 226, 189, .28);
  color: #94e4c2;
  background: rgba(10, 53, 48, .72);
}
.linkage-evidence-item footer b.linkage-source-manual {
  border-color: rgba(255, 189, 101, .28);
  color: #ffd09a;
  background: rgba(73, 47, 20, .68);
}
.linkage-evidence-empty {
  min-height: 112px;
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 24px;
  border: 1px dashed rgba(105, 216, 255, .3);
  border-radius: 8px;
  color: #8eb2c8;
  background: rgba(4, 15, 26, .26);
}
.linkage-evidence-empty .el-icon {
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid rgba(105, 216, 255, .34);
  border-radius: 10px;
  color: #69d8ff;
  background: rgba(8, 47, 68, .5);
  font-size: 21px;
}
.linkage-evidence-empty div {
  display: grid;
  gap: 5px;
}
.linkage-evidence-empty strong {
  color: #eaf7fc;
  font-size: 16px;
}
.linkage-evidence-empty span {
  color: #7fa5bd;
  font-size: 13px;
}
.linkage-card {
  padding: 22px;
}
.detail-fields {
  position: relative;
  z-index: 1;
  margin: 2px 0 0;
  padding-top: 18px;
  border-top: 1px solid rgba(126, 171, 202, .1);
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px 22px;
}
.detail-fields div {
  min-width: 0;
  padding: 12px 14px;
  border-radius: 7px;
  background: rgba(4, 14, 24, .32);
}
dt {
  color: #78a0ba;
  font-size: 12px;
}
dd {
  margin: 8px 0 0;
  overflow-wrap: anywhere;
  color: #eef7fc;
  font-size: 16px;
  line-height: 1.45;
}
.evidence-card.empty {
  padding-bottom: 20px;
}
.review-frame-strip {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 2px 8px 0;
  scroll-snap-type: x mandatory;
  scrollbar-width: thin;
  scrollbar-color: rgba(105, 216, 255, .42) rgba(4, 13, 22, .45);
}
.review-frame-item,
.review-frame-slot {
  flex: 0 0 clamp(220px, 23vw, 320px);
  aspect-ratio: 16 / 9;
  border: 1px solid rgba(105, 216, 255, .18);
  border-radius: 8px;
  scroll-snap-align: start;
}
.review-frame-item {
  position: relative;
  overflow: hidden;
  padding: 0;
  color: #e9f7ff;
  text-align: left;
  background: #020b13;
  cursor: pointer;
}
.review-frame-item .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.review-frame-item::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 42%, rgba(0, 0, 0, .78));
}
.review-frame-item:hover {
  border-color: rgba(105, 216, 255, .58);
}
.review-frame-item.is-false-alarm {
  border-color: rgba(255, 184, 74, .95);
  box-shadow: inset 0 0 0 1px rgba(255, 184, 74, .45), 0 0 18px rgba(255, 166, 53, .2);
}
.false-alarm-frame-flag {
  position: absolute;
  z-index: 2;
  top: 9px;
  right: 9px;
  padding: 4px 7px;
  border: 1px solid rgba(255, 225, 159, .88);
  border-radius: 4px;
  color: #3b2306;
  background: #ffbf4d;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .35);
  font-size: 11px;
  font-weight: 900;
}
.review-frame-item footer {
  position: absolute;
  z-index: 1;
  left: 10px;
  right: 10px;
  bottom: 10px;
}
.review-frame-item footer span,
.review-frame-item footer time {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.review-frame-item footer span {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.review-frame-item footer time {
  margin-top: 4px;
  color: #a9c5d6;
  font-size: 12px;
}
.review-frame-slot {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  color: #53758c;
  background: rgba(4, 13, 22, .42);
}
.review-frame-slot strong {
  color: #6f91a8;
  font-size: 18px;
}
.review-frame-slot span {
  color: #6f8798;
  font-size: 12px;
}
.evidence-grid {
  max-height: 440px;
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 14px;
  overflow-y: auto;
  padding-right: 2px;
}
.evidence-grid.single {
  grid-template-columns: minmax(320px, 520px);
}
.evidence-item {
  position: relative;
  height: 156px;
  overflow: hidden;
  border: 0;
  border-radius: 8px;
  color: #e9f7ff;
  text-align: left;
  background: linear-gradient(180deg, #082033, #061523);
  box-shadow: 0 10px 24px rgba(0, 0, 0, .18);
  cursor: pointer;
}
.evidence-grid.single .evidence-item {
  height: 260px;
}
.evidence-item .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.evidence-item::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 34%, rgba(0, 0, 0, .76));
}
.evidence-item:hover {
  outline: 2px solid rgba(105, 216, 255, .45);
}
.file-evidence {
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #bdd8e9;
}
.file-evidence .el-icon {
  font-size: 32px;
}
.evidence-item footer {
  position: absolute;
  z-index: 1;
  left: 12px;
  right: 12px;
  bottom: 12px;
}
.evidence-item footer span,
.evidence-item footer time {
  display: block;
}
.evidence-item footer span {
  overflow: hidden;
  color: #fff;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-item footer time {
  margin-top: 5px;
  color: #a9c5d6;
  font-size: 12px;
}
.compact-empty {
  min-height: 78px;
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #86a5ba;
  border-radius: 8px;
  background: rgba(4, 13, 22, .34);
}
.compact-empty .el-icon {
  font-size: 24px;
}
.linkage-list {
  min-width: 0;
  margin-top: 16px;
  display: grid;
  gap: 12px;
}
.linkage-heading-title {
  margin: 0;
  color: #f4f9fd;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: 0;
}
.linkage-count {
  padding-top: 2px;
  color: #c4dce9;
  font-size: 20px;
  font-weight: 700;
}
.linkage-list article {
  min-width: 0;
  min-height: 0;
  display: block;
  padding: 18px 20px;
  border-radius: 8px;
  background: rgba(4, 13, 22, .38);
  box-shadow: inset 0 1px 0 rgba(143, 200, 242, .05);
}
.linkage-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #08251d;
  background: #7ee2bd;
}
.linkage-list article.running .linkage-icon {
  color: #061927;
  background: #69d8ff;
}
.linkage-list article.failed .linkage-icon {
  color: #fff;
  background: #d85667;
}
.linkage-body header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.linkage-body {
  min-width: 0;
}
.linkage-body strong {
  color: #f4f9fd;
}
.linkage-body header span {
  padding: 4px 8px;
  border-radius: 5px;
  color: #a9e9d4;
  font-size: 14px;
  font-weight: 700;
  background: rgba(126, 226, 189, .1);
}
.linkage-list article.running .linkage-body header span {
  color: #8cddff;
  background: rgba(105, 216, 255, .1);
}
.linkage-list article.failed .linkage-body header span {
  color: #ffb8c1;
  background: rgba(216, 86, 103, .12);
}
.linkage-card-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.linkage-body strong {
  font-size: 19px;
  line-height: 1.35;
}
.linkage-body dl {
  margin: 16px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px 16px;
}
.linkage-body dd {
  overflow-wrap: anywhere;
}
.linkage-body p {
  margin: 12px 0 0;
  color: #95b1c4;
  line-height: 1.5;
}
.linkage-complete-button,
.linkage-process-button {
  margin: 0;
}
.linkage-complete-button {
  margin-top: 16px;
}
.linkage-complete-button {
  font-weight: 700;
}
.linkage-process-button {
  border-color: transparent !important;
  color: #85bdd6 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.linkage-card-actions .linkage-process-button:hover,
.linkage-card-actions .linkage-process-button:focus {
  border-color: transparent !important;
  color: #c9efff !important;
  background: transparent !important;
}
.failure-reason {
  color: #ffb8c1;
}
.log-stream {
  margin-top: 16px;
  display: grid;
  gap: 6px;
}
.log-stream article {
  display: grid;
  grid-template-columns: 126px minmax(0, 1fr) 164px auto;
  gap: 12px;
  align-items: center;
  min-height: 54px;
  padding: 10px 12px 10px 14px;
  border-radius: 7px;
  background: rgba(4, 13, 22, .34);
  box-shadow: inset 3px 0 0 rgba(126, 171, 202, .16);
}
.log-stream article.is-trigger {
  box-shadow: inset 3px 0 0 rgba(105, 216, 255, .55);
}
.log-stream article.is-action {
  box-shadow: inset 3px 0 0 rgba(105, 216, 255, .36);
}
.log-stream article.is-warning {
  box-shadow: inset 3px 0 0 rgba(240, 199, 93, .52);
}
.log-stream article.is-resolve,
.log-stream article.is-manual {
  box-shadow: inset 3px 0 0 rgba(126, 226, 189, .45);
}
.log-stream article.is-failed {
  box-shadow: inset 3px 0 0 rgba(216, 86, 103, .6);
}
.log-stream article.node-trigger {
  --log-node-color: #69d8ff;
  box-shadow: inset 3px 0 0 rgba(105, 216, 255, .72);
}
.log-stream article.node-routing {
  --log-node-color: #d6aa62;
  box-shadow: inset 3px 0 0 rgba(214, 170, 98, .78);
}
.log-stream article.node-linkage {
  --log-node-color: #63d6ad;
  box-shadow: inset 3px 0 0 rgba(99, 214, 173, .72);
}
.log-stream article.node-report {
  --log-node-color: #af9bff;
  box-shadow: inset 3px 0 0 rgba(175, 155, 255, .72);
}
.log-stream article.node-archive {
  --log-node-color: #7ea9c4;
  box-shadow: inset 3px 0 0 rgba(126, 169, 196, .7);
}
.log-stream article.node-system {
  --log-node-color: #93aebe;
}
.log-stream article.node-trigger .log-type,
.log-stream article.node-routing .log-type,
.log-stream article.node-linkage .log-type,
.log-stream article.node-report .log-type,
.log-stream article.node-archive .log-type,
.log-stream article.node-system .log-type {
  color: var(--log-node-color);
  background: color-mix(in srgb, var(--log-node-color) 10%, transparent);
}
.log-type {
  width: 100%;
  max-width: 126px;
  padding: 5px 8px;
  overflow: hidden;
  border-radius: 6px;
  color: #b8d1e2;
  font-size: 12px;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(126, 171, 202, .1);
}
.log-stream article.is-trigger .log-type,
.log-stream article.is-action .log-type {
  color: #91ddff;
}
.log-stream article.is-warning .log-type {
  color: #f0c75d;
}
.log-stream article.is-resolve .log-type,
.log-stream article.is-manual .log-type {
  color: #a9e9d4;
}
.log-stream article.is-failed .log-type {
  color: #ffb8c1;
}
.log-stream article.node-trigger .log-type { color: #69d8ff; background: rgba(105, 216, 255, .1); }
.log-stream article.node-routing .log-type { color: #f0c75d; background: rgba(240, 199, 93, .1); }
.log-stream article.node-linkage .log-type { color: #7ee2bd; background: rgba(126, 226, 189, .1); }
.log-stream article.node-report .log-type { color: #c2b3ff; background: rgba(175, 155, 255, .1); }
.log-stream article.node-archive .log-type { color: #9bc9df; background: rgba(126, 169, 196, .1); }
.log-stream article.node-system .log-type { color: #a8bfce; background: rgba(126, 171, 202, .1); }
.log-body strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: #f0f7fc;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.log-body p {
  margin: 5px 0 0;
  min-width: 0;
  overflow: hidden;
  color: #8eaabd;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.log-body dl.log-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 6px 14px;
  margin: 8px 0 0;
  padding: 8px 0 0;
  border-top: 1px dashed rgba(126, 171, 202, .16);
}
.log-fields dt {
  color: #6f92a8;
  font-size: 11px;
}
.log-fields dd {
  margin: 3px 0 0;
  overflow-wrap: anywhere;
  color: #c9dce9;
  font-size: 13px;
  line-height: 1.4;
}
.log-fields .log-field-note {
  grid-column: 1 / -1;
}
.log-fields .log-field-note-text {
  margin: 0;
  color: #a8bfce;
  font-size: 13px;
  line-height: 1.4;
}
.workflow-dag-block {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(126, 171, 202, .16);
}
.workflow-dag-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #c9e8fa;
  font-size: 13px;
}
.workflow-dag-heading span {
  padding: 2px 6px;
  border: 1px solid rgba(105, 216, 255, .24);
  border-radius: 4px;
  color: #72c9ec;
  font-size: 10px;
  letter-spacing: .08em;
}
.workflow-dag-canvas {
  margin-top: 8px;
  overflow-x: auto;
  padding: 8px 2px 4px;
  border-radius: 7px;
  background: rgba(2, 13, 24, .42);
}
.workflow-dag-canvas svg {
  width: 100%;
  min-width: 430px;
  height: auto;
  display: block;
}
.workflow-dag-edge {
  fill: none;
  stroke: #456a82;
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
}
.workflow-dag-node rect {
  fill: rgba(12, 39, 59, .92);
  stroke: rgba(105, 216, 255, .38);
  stroke-width: 1;
}
.workflow-dag-node text {
  fill: #d9effb;
  font-size: 12px;
  font-weight: 600;
}
.workflow-dag-node .workflow-dag-model {
  fill: #8eb6cc;
  font-size: 9px;
  font-weight: 400;
}
.workflow-dag-node.is-start rect {
  fill: rgba(17, 61, 76, .94);
  stroke: rgba(105, 216, 255, .72);
}
.workflow-dag-node.is-end rect {
  fill: rgba(25, 63, 59, .94);
  stroke: rgba(126, 226, 189, .68);
}
.workflow-dag-node.is-model rect {
  fill: rgba(56, 46, 68, .92);
  stroke: rgba(175, 155, 255, .62);
}
.workflow-dag-node.is-task rect {
  stroke: rgba(214, 170, 98, .58);
}
.log-source {
  color: #7f9eb3;
  font-size: 12px;
  text-align: right;
}
.log-source span,
.log-source time {
  display: block;
}
.log-source time {
  margin-top: 4px;
}
.operation-card {
  background:
    linear-gradient(180deg, rgba(14, 42, 64, .88), rgba(8, 24, 39, .92)),
    rgba(10, 29, 48, .9);
}
.report-card {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(17, 52, 79, .94), rgba(8, 25, 42, .9)),
    rgba(8, 25, 42, .88);
}
.report-card::after {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, #69d8ff, rgba(126, 226, 189, .55), transparent);
}
.report-card-link {
  position: relative;
  width: 100%;
  margin-top: 14px;
  padding: 14px 14px 14px 16px;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border: 1px solid rgba(105, 216, 255, .34);
  border-radius: 8px;
  color: #dcefff;
  text-align: left;
  background:
    linear-gradient(180deg, rgba(8, 28, 45, .86), rgba(4, 13, 22, .72)),
    rgba(4, 13, 22, .38);
  cursor: pointer;
}
.report-card-link:hover {
  border-color: rgba(105, 216, 255, .7);
  background:
    linear-gradient(180deg, rgba(13, 45, 70, .92), rgba(5, 18, 30, .76)),
    rgba(15, 49, 75, .62);
}
.report-card-link .el-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #061927;
  background: #69d8ff;
  font-size: 24px;
}
.report-card-copy,
.report-card-link strong,
.report-card-link small {
  display: block;
  min-width: 0;
}
.report-card-link strong {
  display: -webkit-box;
  color: #f4f9fd;
  font-size: 15px;
  line-height: 1.4;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.report-card-link small {
  margin-top: 5px;
  color: #8fd2f2;
  font-size: 12px;
}
.report-open-text {
  padding: 5px 10px;
  border-radius: 6px;
  color: #061927;
  background: #8bdcff;
  font-size: 12px;
  font-weight: 800;
}
.action-context span,
.action-context strong,
.action-context p {
  display: block;
}
.action-context span {
  color: #83b3d1;
  font-size: 13px;
}
.action-context strong {
  margin-top: 14px;
  color: #fff;
  font-size: 18px;
}
.action-context p {
  margin: 4px 0 0;
  color: #8faabd;
  font-size: 13px;
}
.decision-actions {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.decision-actions .el-button {
  width: 100%;
  min-width: 0;
  height: 38px;
  padding: 0 8px;
  margin-left: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(12px, .78vw, 14px);
  white-space: nowrap;
}
.decision-actions .el-button.archive-primary-action.is-disabled {
  --el-button-disabled-bg-color: #9ecfff;
  --el-button-disabled-border-color: #9ecfff;
  --el-button-disabled-text-color: #ffffff;
  color: #ffffff !important;
  border-color: #9ecfff !important;
  background: #9ecfff !important;
  opacity: 1;
}
.false-alarm-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}
.false-alarm-dialog-copy {
  color: #8fb4ca;
  font-size: 13px;
  line-height: 1.6;
}
.false-alarm-selection-grid {
  max-height: min(54vh, 430px);
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  overflow-y: auto;
  padding-right: 3px;
}
.false-alarm-selection-item {
  position: relative;
  min-width: 0;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  padding: 0;
  border: 1px solid rgba(105, 216, 255, .28);
  border-radius: 8px;
  color: #edf8ff;
  text-align: left;
  background: #020b13;
  cursor: pointer;
}
.false-alarm-selection-item .el-image {
  width: 100%;
  height: 100%;
  display: block;
}
.false-alarm-selection-item::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 52%, rgba(0, 0, 0, .74));
}
.false-alarm-selection-item:hover,
.false-alarm-selection-item.selected {
  border-color: #ffbd47;
  box-shadow: 0 0 0 2px rgba(255, 189, 71, .28), 0 0 18px rgba(255, 165, 51, .18);
}
.false-alarm-selection-item strong {
  position: absolute;
  z-index: 2;
  left: 9px;
  bottom: 8px;
  font-size: 12px;
}
.false-alarm-selection-check {
  position: absolute;
  z-index: 2;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(226, 249, 255, .7);
  border-radius: 50%;
  color: #13220d;
  background: rgba(6, 30, 45, .72);
  font-size: 16px;
  font-weight: 900;
}
.false-alarm-selection-item.selected .false-alarm-selection-check {
  border-color: #dcffd5;
  background: #8eea75;
}
.closed-note {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 7px;
  color: #91adbf;
  line-height: 1.5;
  background: rgba(4, 13, 22, .34);
}
.staff-result-form {
  display: grid;
  gap: 18px;
}
.staff-result-hint {
  padding: 12px 14px;
  border: 1px solid rgba(75, 191, 225, .2);
  border-radius: 7px;
  color: #9fc4d9;
  background: rgba(7, 29, 47, .72);
  line-height: 1.5;
}
.staff-result-field {
  display: grid;
  gap: 8px;
}
.staff-result-field > label {
  color: #d9edf8;
  font-size: 14px;
  font-weight: 700;
}
.staff-result-select {
  width: 100%;
}
.staff-result-photo-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.staff-result-photo-card {
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px dashed rgba(72, 216, 255, .42);
  border-radius: 8px;
  color: #8db8cf;
  background: rgba(5, 23, 38, .72);
  cursor: pointer;
  text-align: center;
}
.staff-result-photo-card:hover {
  border-color: rgba(126, 238, 255, .78);
  background: rgba(8, 39, 59, .82);
}
.staff-result-photo-card input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.staff-result-photo-card img {
  width: 100%;
  height: 180px;
  object-fit: cover;
}
.staff-result-photo-card span {
  display: grid;
  gap: 6px;
  font-weight: 700;
}
.staff-result-photo-card small {
  color: #6f9cb6;
  font-size: 12px;
  font-weight: 400;
}
:global(.evidence-drawer.el-drawer) {
  background: #0b1d30;
}
:global(.evidence-drawer .el-drawer__header) {
  margin: 0;
  padding: 18px;
  color: #f3f8fd;
  border-bottom: 1px solid rgba(104, 161, 200, .16);
}
.evidence-drawer-list {
  display: grid;
  gap: 14px;
}
.evidence-drawer-list figure {
  margin: 0;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(5, 19, 31, .56);
}
.evidence-drawer-list .el-image {
  width: 100%;
  aspect-ratio: 16 / 9;
  display: block;
  background: #02090f;
}
.drawer-file {
  min-height: 180px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  background: #061523;
}
.drawer-file .el-icon {
  font-size: 34px;
  color: #9bc1d8;
}
.drawer-file a {
  max-width: 90%;
  overflow: hidden;
  color: #69d8ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-drawer-list figcaption {
  padding: 12px;
}
.evidence-drawer-list figcaption strong,
.evidence-drawer-list figcaption span,
.evidence-drawer-list figcaption small {
  display: block;
}
.evidence-drawer-list figcaption span,
.evidence-drawer-list figcaption small {
  margin-top: 6px;
  color: #85a3b8;
  font-size: 12px;
}
:global(.linkage-process-dialog.el-dialog) {
  max-width: 1680px;
  overflow: hidden;
  border: 1px solid rgba(105, 216, 255, .35);
  border-radius: 10px;
  background: #102f50;
  box-shadow: 0 24px 70px rgba(0, 0, 0, .45);
}
:global(.linkage-process-dialog .el-dialog__header) {
  margin: 0;
  padding: 18px 22px;
  color: #edf8ff;
  border-bottom: 1px solid rgba(150, 202, 235, .16);
}
:global(.linkage-process-dialog .el-dialog__title) {
  color: #eaf6ff;
  font-size: 20px;
  font-weight: 700;
}
:global(.linkage-process-dialog .el-dialog__body) {
  padding: 16px 20px 20px;
}
.linkage-process-content {
  min-width: 0;
}
.process-dialog-toolbar,
.process-panel > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.process-dialog-toolbar {
  padding: 0 0 14px;
  color: #cfe6f5;
}
.process-dialog-toolbar strong,
.process-dialog-toolbar span {
  display: block;
}
.process-dialog-toolbar strong {
  color: #f3faff;
  font-size: 17px;
}
.process-dialog-toolbar span {
  margin-top: 5px;
  color: #8fb5cd;
  font-size: 13px;
}
.process-dialog-toolbar .process-runtime {
  margin: 0;
  color: #7ee2bd;
  white-space: nowrap;
}
.process-view-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 1fr);
  gap: 14px;
}
.process-panel {
  min-width: 0;
  padding: 12px;
  border: 1px solid rgba(105, 216, 255, .18);
  border-radius: 8px;
  background: rgba(4, 18, 31, .72);
}
.process-panel > header {
  padding: 0 2px 10px;
}
.process-panel > header span {
  color: #e6f6ff;
  font-size: 15px;
  font-weight: 700;
}
.process-panel > header small {
  color: #85acc4;
  font-size: 12px;
}
.process-map-stage,
.process-video-stage {
  position: relative;
  height: min(58vh, 560px);
  overflow: hidden;
  border: 1px solid rgba(105, 216, 255, .2);
  border-radius: 8px;
  background: #030d16;
}
.process-map-stage > img,
.process-map-stage > svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.process-map-stage > img {
  object-fit: cover;
}
.process-map-stage > svg {
  z-index: 2;
}
.process-route-glow,
.process-route-line {
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.process-route-glow {
  stroke: rgba(81, 225, 255, .28);
  stroke-width: 2.6;
  filter: blur(1.2px);
}
.process-route-line {
  stroke: #55dcff;
  stroke-width: .72;
  stroke-dasharray: 2 1.4;
  animation: flowMove 1.2s linear infinite;
}
.process-route-point {
  fill: #fff;
  stroke: #1ab8ed;
  stroke-width: .45;
}
.process-unit-marker {
  position: absolute;
  z-index: 4;
  width: 32px;
  height: 32px;
  transform: translate(-50%, -50%);
  transition: left .95s linear, top .95s linear;
  pointer-events: none;
}
.process-unit-marker span {
  position: absolute;
  inset: -7px;
  border: 2px solid rgba(126, 226, 189, .75);
  border-radius: 50%;
  animation: processMarkerPulse 1.6s ease-out infinite;
}
.process-unit-marker img {
  position: absolute;
  inset: 3px;
  width: 26px;
  height: 26px;
  object-fit: contain;
  filter: drop-shadow(0 2px 5px rgba(0, 0, 0, .65));
}
.process-map-legend {
  position: absolute;
  z-index: 5;
  left: 10px;
  bottom: 10px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border-radius: 6px;
  color: #b8d7e8;
  font-size: 12px;
  background: rgba(3, 16, 27, .82);
}
.process-map-legend i {
  width: 20px;
  height: 2px;
  background: #55dcff;
}
.process-map-legend span {
  margin-left: 8px;
  color: #7ee2bd;
}
.process-video-stage video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.process-video-overlay {
  position: absolute;
  z-index: 3;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #f1fbff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .7);
}
.process-video-overlay span {
  padding: 4px 7px;
  border-radius: 4px;
  color: #061927;
  background: #7ee2bd;
  font-size: 11px;
  font-weight: 800;
}
.process-video-overlay strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.process-scan-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(rgba(72, 216, 255, .06) 1px, transparent 1px), linear-gradient(90deg, rgba(72, 216, 255, .06) 1px, transparent 1px);
  background-size: 28px 28px;
}
:global(.drone-test-dialog.el-dialog) {
  max-width: calc(100vw - 32px);
  border: 1px solid rgba(72, 216, 255, .32);
  border-radius: 10px;
  background: #203f65;
  box-shadow: 0 24px 60px rgba(0, 7, 18, .46);
}
:global(.drone-test-dialog .el-dialog__header) {
  margin: 0;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(137, 174, 184, .14);
}
:global(.drone-test-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-size: 20px;
  font-weight: 900;
}
:global(.drone-test-dialog .el-dialog__body) {
  padding: 14px 22px 22px;
}
.test-layout {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.test-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.test-device {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.test-device strong {
  color: #f3f8fd;
  font-size: 17px;
}
.test-wayline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.toolbar-label {
  color: #a9c7de;
  font-size: 13px;
  font-weight: 700;
}
.wayline-select {
  width: 240px;
}
.test-body {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 10px;
  height: 420px;
  min-height: 420px;
}
.test-map {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(93, 184, 225, .17);
  border-radius: 10px;
  background: #030b12;
}
.wayline-map-stage {
  position: relative;
  width: 100%;
  overflow: hidden;
  background: #02080d;
}
.test-wayline-map-stage {
  min-height: 0;
}
.wayline-map-stage > img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: fill;
  pointer-events: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-user-drag: none;
  filter: saturate(1.08) contrast(1.06) brightness(.76);
}
.wayline-map-svg {
  position: absolute;
  inset: 0;
  z-index: 16;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.wayline-map-route {
  fill: none;
  stroke: #48d8ff;
  stroke-width: 1;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.3;
  vector-effect: non-scaling-stroke;
}
.wayline-map-route.route-glow {
  stroke-width: 3.8;
  stroke-dasharray: none;
  opacity: .4;
}
.wayline-map-point {
  fill: #eafcff;
  stroke: #48d8ff;
  stroke-width: .4;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, .75));
}
.process-wayline-landmark {
  position: absolute;
  z-index: 18;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 0;
  border: 0;
  color: #e9f7ff;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
  background: transparent;
  box-shadow: none;
}
.process-wayline-landmark.airport {
  color: #fff0bd;
}
.process-wayline-landmark-mark {
  position: relative;
  width: 23px;
  height: 23px;
  display: block;
  border: 2px solid #aaf5ff;
  border-radius: 50% 50% 50% 0;
  background: linear-gradient(145deg, #52e4ff, #087da8);
  box-shadow: 0 0 10px rgba(72, 216, 255, .8), 0 2px 5px rgba(0, 0, 0, .72);
  transform: rotate(-45deg);
}
.process-wayline-landmark-mark::after {
  content: '';
  position: absolute;
  top: 6px;
  left: 6px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #063747;
  box-shadow: 0 0 0 2px rgba(226, 252, 255, .82);
}
.process-wayline-landmark.airport .process-wayline-landmark-mark {
  border-color: #fff0b0;
  background: linear-gradient(145deg, #ffe184, #bd7710);
  box-shadow: 0 0 10px rgba(255, 209, 102, .82), 0 2px 5px rgba(0, 0, 0, .72);
}
.process-wayline-landmark.airport .process-wayline-landmark-mark::after {
  background: #6b4308;
  box-shadow: 0 0 0 2px rgba(255, 248, 218, .86);
}
.process-wayline-landmark > span:last-child {
  font-size: 11px;
  font-weight: 900;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .85);
}
.process-unit-marker {
  position: absolute;
  width: 32px;
  height: 32px;
  transform: translate(-50%, -50%);
  transition: left .95s linear, top .95s linear;
  z-index: 20;
}
.process-unit-marker .marker-pulse {
  position: absolute;
  top: -2px;
  left: -2px;
  width: 36px;
  height: 36px;
  border: 2px solid rgba(126, 226, 189, .72);
  border-radius: 50%;
  background: transparent;
  animation: processMarkerPulse 1.6s ease-out infinite;
}
.process-unit-marker .marker-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 28px;
  height: 28px;
  transform: translate(-50%, -50%);
  object-fit: contain;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, .6));
}
.process-current-position {
  color: #7ee2bd;
}
.test-map .map-legend {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 22;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  color: #9fc3da;
  font-size: 12px;
  background: rgba(4, 16, 26, .78);
}
.test-map .legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.test-map .legend-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  background: #48d8ff;
}
.test-video {
  display: flex;
  min-width: 0;
}
.video-stage {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(93, 184, 225, .17);
  border-radius: 10px;
  background: #040d16;
}
.video-stream {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: fill;
}
.video-stage .demo-video-crop {
  position: absolute;
  /* 演示素材的水印位于底部：保留上方画面，仅加大底部裁切。 */
  top: -12%;
  left: 0;
  width: 100%;
  height: 126%;
}
.process-video-label {
  position: absolute;
  z-index: 2;
  top: 14px;
  left: 14px;
  right: 14px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  color: #f3f8fd;
  text-shadow: 0 1px 3px rgba(0, 0, 0, .75);
}
.process-video-label span {
  padding: 4px 7px;
  border-radius: 4px;
  color: #062119;
  background: #7ee2bd;
  font-size: 11px;
  font-weight: 900;
}
.process-video-label strong {
  max-width: 65%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scan-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: linear-gradient(rgba(72, 216, 255, .05) 1px, transparent 1px), linear-gradient(90deg, rgba(72, 216, 255, .05) 1px, transparent 1px);
  background-size: 24px 24px;
}
@keyframes subtlePulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(105, 216, 255, .28);
  }
  50% {
    box-shadow: 0 0 0 9px rgba(105, 216, 255, 0);
  }
}
@keyframes processMarkerPulse {
  0% { transform: scale(.72); opacity: .9; }
  100% { transform: scale(1.5); opacity: 0; }
}
@keyframes flowMove {
  to {
    stroke-dashoffset: -20;
  }
}
@media (min-width: 1600px) {
  .event-workbench {
    max-width: 1720px;
    margin: 0 auto;
  }
}
@media (max-width: 1800px) and (min-width: 1281px) {
  .workspace-grid {
    grid-template-columns: minmax(0, 1fr) 340px;
  }
}
@media (max-width: 1280px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
  .side-stack {
    position: static;
  }
  .detail-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .major-flow {
    padding: 22px;
    min-height: 0;
  }
  .flow-header {
    min-height: 0;
    gap: 16px;
  }
  .flow-header-divider {
    height: 36px;
  }
  .flow-heading {
    font-size: 24px;
  }
  .detail-hero {
    grid-template-columns: 1fr;
  }
  .detail-status-block {
    min-width: 0;
    justify-items: start;
  }
  .flow-rail {
    grid-template-columns: 1fr;
    gap: 18px;
    margin-top: 32px;
  }
  .flow-rail li {
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr);
    gap: 14px;
    align-items: center;
    padding-right: 0;
  }
  .flow-node {
    width: 50px;
    height: 50px;
  }
  .flow-text {
    margin-top: 0;
    align-items: flex-start;
    text-align: left;
  }
  .flow-text strong {
    font-size: 20px;
    white-space: normal;
  }
  .flow-text span {
    margin-top: 6px;
    font-size: 13px;
  }
  .flow-text time {
    margin-top: 5px;
    font-size: 13px;
  }
  .flow-connector {
    display: none;
  }
  .log-stream article {
    grid-template-columns: 1fr;
  }
  .log-source {
    text-align: left;
  }
  .process-view-grid {
    grid-template-columns: 1fr;
  }
  .test-body {
    grid-template-columns: 1fr;
    min-height: 0;
  }
  .process-map-stage,
  .process-video-stage {
    height: 360px;
  }
}
@media (max-width: 640px) {
  .event-workbench {
    padding: 14px;
  }
  .detail-title-block h2 {
    font-size: 24px;
  }
  .detail-fields {
    grid-template-columns: 1fr;
  }
  .linkage-body dl {
    grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    gap: 8px;
  }
  .linkage-body dd {
    font-size: 14px;
  }
  .evidence-grid,
  .evidence-grid.single {
    grid-template-columns: 1fr;
  }
  .decision-actions .el-button {
    padding: 0 6px;
    font-size: 12px;
  }
  .linkage-count {
    font-size: 17px;
  }
  .process-dialog-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .process-dialog-toolbar .process-runtime {
    margin-top: 0;
  }
  .process-map-stage,
  .process-video-stage {
    height: 260px;
  }
  .staff-result-photo-grid {
    grid-template-columns: 1fr;
  }
}
</style>
