<template>
  <div class="event-config-page">
    <header class="page-header system-page-header">
      <div class="title-block">
        <h2>事件配置</h2>
        <p>统一维护系统预置事件、触发参数和联动流程</p>
      </div>
      <div class="status-summary" aria-label="事件配置统计">
        <div class="metric">
          <i class="dot total"></i>
          <strong class="metric-num">{{ events.length }}</strong>
          <span class="metric-label">总数</span>
        </div>
        <div class="metric">
          <i class="dot online"></i>
          <strong class="metric-num">{{ eventOnlineCount }}</strong>
          <span class="metric-label">在线</span>
        </div>
        <div class="metric">
          <i class="dot offline"></i>
          <strong class="metric-num">{{ eventOfflineCount }}</strong>
          <span class="metric-label">离线</span>
        </div>
      </div>
    </header>

    <section class="filter-bar" :class="{ 'with-visual-category': sourceFilter === 'camera' }">
      <el-select v-model="sourceFilter" class="event-filter-select" placeholder="事件类型">
        <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        v-if="sourceFilter === 'camera'"
        v-model="visualCategoryFilter"
        class="event-filter-select visual-category-filter"
        placeholder="视觉事件分类"
      >
        <el-option v-for="item in visualCategoryOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="riskFilter" class="event-filter-select" placeholder="风险等级">
        <el-option v-for="item in riskOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="enabledFilter" class="event-filter-select" placeholder="启用状态">
        <el-option v-for="item in enabledOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-input
        v-model.trim="keyword"
        :prefix-icon="Search"
        clearable
        placeholder="搜索事件"
        class="event-search"
      />
    </section>

    <section class="event-list-panel" v-loading="loading">
      <div class="config-table" role="table" aria-label="事件配置列表">
        <div class="config-table-head" role="row">
          <span>事件名称</span>
          <span>事件类型</span>
          <span>风险等级</span>
          <span>触发规则</span>
          <span class="header-with-help">
            持续时间
            <el-tooltip content="触发规则连续满足达到该时长后，系统才会创建事件。" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </span>
          <span class="header-with-help">
            恢复时间
            <el-tooltip content="触发规则恢复正常并持续达到该时长后，事件可自动闭环。" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </span>
          <span>是否启用</span>
          <span>操作</span>
        </div>

        <div
          v-for="event in pagedEvents"
          :key="event.id"
          class="config-row"
          :class="{ editing: editingEventId === event.id }"
          role="row"
        >
          <div class="event-name-cell">
            <strong>{{ event.name }}</strong>
          </div>
          <div><span class="source-pill" :class="`is-${event.source_type || 'unknown'}`">{{ compactSourceLabel(event) }}</span></div>
          <div><el-tag :type="riskTagType(event.risk_level, event.risk_label)" effect="dark">{{ riskLabel(event.risk_level, event.risk_label) }}</el-tag></div>

          <div class="rule-cell">
            <template v-if="editingEventId === event.id">
              <div v-if="isVisualEvent(event)" class="visual-inline-editor">
                <span>{{ listRuleSummary(event) }}</span>
                <el-button class="zone-entry-action" :icon="View" @click="goZoneConfig">查看/编辑区域</el-button>
              </div>
              <div v-else class="condition-editor">
                <strong>{{ parseCondition(event.conditions?.[0]).metricLabel }}</strong>
                <b>{{ parseCondition(event.conditions?.[0]).operatorLabel }}</b>
                <el-input
                  v-if="parseCondition(event.conditions?.[0]).editableThreshold"
                  v-model.number="ruleForm.threshold"
                  type="number"
                >
                  <template #append>{{ parseCondition(event.conditions?.[0]).unit || '数值' }}</template>
                </el-input>
                <strong v-else>{{ parseCondition(event.conditions?.[0]).valueText }}</strong>
              </div>
            </template>
            <span v-else>{{ listRuleSummary(event) }}</span>
          </div>

          <div class="duration-cell">
            <el-input
              v-if="editingEventId === event.id"
              v-model.number="ruleForm.duration"
              type="number"
              min="0"
              max="3600"
            >
              <template #append>秒</template>
            </el-input>
            <span v-else>{{ durationText(event) }}</span>
          </div>

          <div class="duration-cell">
            <el-input
              v-if="editingEventId === event.id"
              v-model.number="ruleForm.recovery_duration"
              type="number"
              min="0"
              max="3600"
            >
              <template #append>秒</template>
            </el-input>
            <span v-else>{{ recoveryText(event) }}</span>
          </div>

          <div class="status-cell">
            <el-switch
              :model-value="event.enabled"
              :loading="savingEventId === event.id"
              @change="toggleListEvent(event, $event)"
            />
          </div>
          <div class="row-actions">
            <template v-if="editingEventId === event.id">
              <el-button class="cancel-rule-action" plain size="small" @click="cancelInlineRuleEdit">取消</el-button>
              <el-button class="save-rule-action" size="small" :loading="savingRule" @click="saveInlineRule(event)">保存</el-button>
            </template>
            <template v-else>
              <el-button class="edit-rule-action" @click="startInlineRuleEdit(event)">编辑规则</el-button>
              <el-button class="view-flow-action" @click="openFlowWorkspace(event)">查看联动</el-button>
            </template>
          </div>
        </div>

        <div v-if="!filteredEvents.length" class="empty-list">暂无匹配事件</div>
      </div>
      <el-pagination
        v-if="filteredEvents.length"
        v-model:current-page="eventPage"
        class="list-pagination"
        :page-size="pageSize"
        :total="filteredEvents.length"
        layout="prev, pager, next"
      />
    </section>

    <AppDialog
      v-model="flowDialogVisible"
      class="flow-workspace-dialog"
      width="min(1400px, 90vw)"
      top="6vh"
      :show-close="false"
      destroy-on-close
      @closed="closeFlowWorkspace"
    >
      <template #header>
        <div class="flow-dialog-header">
          <div>
            <h3>{{ currentEvent?.name }}</h3>
          </div>
          <div class="flow-dialog-actions" v-if="!flowEditMode">
            <el-button class="flow-edit-entry" :icon="EditPen" @click="enterFlowEdit">编辑流程</el-button>
            <el-button plain @click="flowDialogVisible = false">关闭页面</el-button>
          </div>
          <div class="flow-dialog-actions" v-else>
            <el-button :icon="Plus" type="primary" plain @click="addNodeDialogVisible = true">添加动作</el-button>
            <el-button :icon="RefreshRight" plain @click="autoLayoutDraft">自动布局</el-button>
            <el-button plain @click="cancelFlowEdit">取消</el-button>
            <el-button class="flow-save-action" type="primary" :loading="savingFlow" @click="saveFlow">保存流程</el-button>
          </div>
        </div>
      </template>

      <div class="flow-workspace-body" :class="{ 'with-inspector': editingNode?.action }">
        <div
          ref="canvasRef"
          class="flow-canvas"
          :class="{ editing: flowEditMode }"
          @pointermove="handleCanvasPointerMove"
          @pointerup="finishDrag"
          @pointerleave="finishDrag"
          @click="clearFlowSelection"
        >
          <div class="flow-stage" :style="flowStageStyle">
            <svg
              class="flow-edges"
              :viewBox="`0 0 ${FLOW_STAGE_WIDTH} ${flowStageHeight}`"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <marker id="event-flow-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                  <path d="M 0 0 L 8 4 L 0 8 z" />
                </marker>
              </defs>
              <path
                v-for="edge in flowEdgesForView"
                :key="edge.id"
                :d="edgePathForRender(edge)"
                class="flow-edge"
                :class="{ active: edge.active, selected: flowEditMode && selectedEdgeId === edge.id }"
                @click.stop="selectEdge(edge.id)"
              />
            </svg>

            <article
              v-for="node in flowNodesForView"
              :key="node.id"
              class="canvas-node"
              :class="[node.kind, node.role, { selected: selectedNodeId === node.id, disabled: node.disabled, editable: flowEditMode }]"
              :style="nodeStyle(node)"
              @click.stop="selectNode(node)"
              @pointerdown.stop="startNodeDrag(node, $event)"
            >
              <button
                v-if="flowEditMode"
                type="button"
                class="node-handle target"
                :class="{ ready: connectingFromId && connectingFromId !== node.id }"
                @pointerdown.stop
                @click.stop="completeConnection(node)"
              ></button>
              <el-icon class="node-main-icon"><component :is="node.icon" /></el-icon>
              <div class="node-copy">
                <strong :title="node.title">{{ node.title }}</strong>
                <span :title="node.subtitle">{{ node.subtitle }}</span>
                <em v-if="flowEditMode && node.detail" :title="node.detail">{{ node.detail }}</em>
              </div>
              <div v-if="node.configurable || (flowEditMode && node.kind === 'action' && !node.locked)" class="node-tools">
                <button
                  v-if="node.configurable"
                  type="button"
                  class="node-config"
                  title="配置"
                  @pointerdown.stop
                  @click.stop="openNodeConfig(node)"
                >
                  <el-icon><Setting /></el-icon>
                </button>
                <button
                  v-if="flowEditMode && node.kind === 'action' && !node.locked"
                  type="button"
                  class="node-delete"
                  title="删除动作"
                  @pointerdown.stop
                  @click.stop="deleteFlowNode(node)"
                >
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
              <button
                v-if="flowEditMode"
                type="button"
                class="node-handle source"
                :class="{ active: connectingFromId === node.id }"
                @pointerdown.stop
                @click.stop="startConnection(node)"
              ></button>
            </article>
          </div>
        </div>

        <aside v-if="editingNode?.action" class="action-inspector">
          <header class="action-inspector-header">
            <div class="inspector-title">
              <span>{{ inspectorMode === 'edit' ? '配置动作' : '动作详情' }}</span>
              <strong>{{ actionBusinessLabel(editingNode.action) }}</strong>
              <small>{{ actionBusinessSummary(editingNode.action) }}</small>
            </div>
            <button type="button" @click="closeInspector">×</button>
          </header>

          <div v-if="inspectorMode === 'view'" class="action-readonly">
            <div class="readonly-caption">当前联动动作配置</div>
            <div v-for="field in actionReadonlyFields(editingNode.action)" :key="field.label" class="readonly-field">
              <span>{{ field.label }}</span>
              <strong :title="field.value">{{ field.value }}</strong>
            </div>
            <div v-if="actionBusinessDetail(editingNode.action)" class="readonly-summary">
              {{ actionBusinessDetail(editingNode.action) }}
            </div>
          </div>

          <el-form v-else class="inspector-form" label-position="top">
            <template v-if="editingNode.action.action_type === 'broadcast'">
              <section class="inspector-section">
                <div class="section-heading">
                  <strong>广播内容</strong>
                  <span>选择事件触发后使用的设备与模板</span>
                </div>
                <el-form-item label="广播设备" required>
                  <el-select v-model="actionForm.broadcast_device_id" popper-class="flow-inspector-popper" placeholder="请选择广播设备" clearable>
                    <el-option v-for="item in enabledBroadcastDevices" :key="item.id" :label="item.name" :value="item.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="播报模板" required>
                  <el-select v-model="actionForm.template_id" popper-class="flow-inspector-popper" placeholder="请选择播报模板" clearable>
                    <el-option v-for="item in enabledBroadcastTemplates" :key="item.id" :label="item.name" :value="item.id" />
                  </el-select>
                </el-form-item>
              </section>
              <section class="inspector-section">
                <div class="section-heading">
                  <strong>执行方式</strong>
                  <span>单次播报或按间隔重复播报</span>
                </div>
                <el-radio-group v-model="actionForm.repeat_mode" class="repeat-mode-control">
                  <el-radio-button label="once">单次</el-radio-button>
                  <el-radio-button label="repeat">周期</el-radio-button>
                </el-radio-group>
                <div v-if="actionForm.repeat_mode === 'repeat'" class="repeat-grid">
                  <el-form-item label="间隔">
                    <el-input v-model.number="actionForm.repeat_interval_seconds" type="number" min="1" max="86400">
                      <template #append>秒</template>
                    </el-input>
                  </el-form-item>
                  <el-form-item label="最多">
                    <el-input v-model.number="actionForm.max_executions" type="number" min="2" max="100">
                      <template #append>次</template>
                    </el-input>
                  </el-form-item>
                </div>
              </section>
            </template>

            <template v-else-if="editingNode.action.action_type === 'drone_dispatch'">
              <section class="inspector-section">
                <div class="section-heading">
                  <strong>无人机任务</strong>
                  <span>设置响应事件的设备与巡查航线</span>
                </div>
                <el-form-item label="无人机型号" required>
                  <el-select v-model="actionForm.drone_id" popper-class="flow-inspector-popper" filterable allow-create default-first-option placeholder="选择无人机型号">
                    <el-option v-for="item in droneOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="航线" required>
                  <el-select v-model="actionForm.route_id" popper-class="flow-inspector-popper" placeholder="请选择巡查航线">
                    <el-option v-for="item in routeOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </section>
            </template>

            <template v-else-if="editingNode.action.action_type === 'machine_dog_dispatch'">
              <section class="inspector-section">
                <div class="section-heading">
                  <strong>机器狗任务</strong>
                  <span>当前设备固定执行 9号检测区域巡检路线并返回 4 张取证图</span>
                </div>
                <el-form-item label="机器狗型号" required>
                  <el-select v-model="actionForm.machine_dog_id" popper-class="flow-inspector-popper" placeholder="请选择机器狗型号" clearable>
                    <el-option v-for="item in machineDogOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="巡检路线" required>
                  <el-select v-model="actionForm.route_id" popper-class="flow-inspector-popper" placeholder="请选择巡检路线" clearable>
                    <el-option v-for="item in machineDogRouteOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </section>
            </template>

            <template v-else-if="editingNode.action.action_type === 'staff_task'">
              <section class="inspector-section">
                <div class="section-heading">
                  <strong>人工处置</strong>
                  <span>设置负责接收任务的处置工作组</span>
                </div>
                <el-form-item label="处置工作组">
                  <el-select v-model="actionForm.staff_group" popper-class="flow-inspector-popper" filterable allow-create default-first-option placeholder="选择或输入处置组">
                    <el-option v-for="item in staffGroupOptions" :key="item" :label="item" :value="item" />
                  </el-select>
                </el-form-item>
                <el-form-item label="处置事件类型">
                  <el-select v-model="actionForm.staff_event_type" popper-class="flow-inspector-popper" clearable placeholder="自动按当前事件识别">
                    <el-option label="人员涉水事件" value="PERSON_WADING" />
                    <el-option label="夜间捕鱼事件" value="NIGHT_FISHING" />
                    <el-option label="洪水事件" value="FLOOD_EVENT" />
                  </el-select>
                </el-form-item>
                <el-form-item label="演示自动闭环">
                  <el-switch v-model="actionForm.staff_demo" active-text="启用" inactive-text="关闭" />
                </el-form-item>
                <el-form-item label="任务说明">
                  <el-input v-model.trim="actionForm.staff_note" maxlength="500" show-word-limit placeholder="可选：留空则使用系统默认说明" />
                </el-form-item>
              </section>
            </template>

            <div class="inspector-actions">
              <el-button
                v-if="canDeleteInspectorNode"
                plain
                type="danger"
                @click="deleteInspectorNode"
              >
                删除动作
              </el-button>
              <el-button plain @click="closeInspector">取消</el-button>
              <el-button class="apply-action" @click="saveNodeConfig">应用到流程</el-button>
            </div>
          </el-form>
        </aside>
      </div>
    </AppDialog>

    <AppDialog v-model="addNodeDialogVisible" title="添加联动动作" width="460px" destroy-on-close>
      <div class="add-action-grid">
        <button v-for="item in addActionOptions" :key="item.type" type="button" @click="addActionNode(item.type)">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim,
  Bell,
  Connection,
  Delete,
  EditPen,
  Finished,
  Plus,
  Promotion,
  QuestionFilled,
  RefreshRight,
  Search,
  Setting,
  User,
  VideoCamera,
  View,
  Warning,
} from '@element-plus/icons-vue'
import {
  createActionConfig,
  deleteActionConfig,
  getIntegrationConfig,
  updateActionConfig,
  updateConditionConfig,
  updateEventConfig,
} from '@/api/integration'
import {
  dijLogin,
  getBoundDevices,
  getCurrentWorkspace,
  getDroneDevices,
} from '@/api/drone'
import { getStaffList } from '@/api/staff'

const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'
const DEFAULT_STAFF_GROUP = '安全巡查组'
const FALLBACK_DRONE_OPTIONS = [
  { value: 'mock-drone-001', label: '御3行业版-1号' },
  { value: 'mock-drone-002', label: 'M350 RTK-2号' },
  { value: 'mock-drone-003', label: '精灵4 RTK-3号' },
]
const FALLBACK_DRONE_ROUTE_OPTIONS = [
  { value: 'fishing', label: '禁渔航线' },
  { value: 'wading', label: '禁涉水航线' },
]

const FLOW_STAGE_WIDTH = 1180
const FLOW_STAGE_PADDING = 54
const LAST_EVENT_KEY = 'dam.eventConfig.lastSelectedEventId'
const FLOW_LAYOUT_PREFIX = 'dam.eventConfig.flowLayout.'

const route = useRoute()
const router = useRouter()
const canvasRef = ref(null)

const loading = ref(false)
const savingRule = ref(false)
const savingFlow = ref(false)
const savingEventId = ref(null)
const keyword = ref('')
const sourceFilter = ref('all')
const visualCategoryFilter = ref('all')
const riskFilter = ref('all')
const enabledFilter = ref('all')
const sortFilter = ref('risk')
const eventPage = ref(1)
const pageSize = 10
const selectedEventId = ref(null)
const editingEventId = ref(null)
const flowDialogVisible = ref(false)
const addNodeDialogVisible = ref(false)
const flowEditMode = ref(false)
const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const connectingFromId = ref('')
const editingNode = ref(null)
const inspectorMode = ref('view')
const dragging = ref(null)
const deletedActionIds = ref([])
const flowLayoutVersion = ref(0)
const canvasSize = reactive({ width: 0, height: 0 })
const fitTransform = reactive({ scale: 1, x: 0, y: 0 })
let canvasResizeObserver = null

const config = reactive({
  events: [],
  action_configs: [],
  broadcast_devices: [],
  broadcast_templates: [],
})

const configuredDroneOptions = ref([...FALLBACK_DRONE_OPTIONS])
const configuredStaffGroups = ref([])

const ruleForm = reactive({
  threshold: '',
  duration: 0,
  recovery_duration: 0,
  zone: '',
  target: '',
})

const actionForm = reactive({
  broadcast_device_id: null,
  template_id: '',
  repeat_mode: 'once',
  repeat_interval_seconds: 60,
  max_executions: 1,
  drone_id: '',
  route_id: '',
  machine_dog_id: '',
  staff_group: '',
  staff_event_type: '',
  staff_demo: false,
  staff_note: '',
})

const flowDraft = reactive({
  nodes: [],
  edges: [],
})

const sourceOptions = [
  { label: '全部事件类型', value: 'all' },
  { label: '视觉事件', value: 'camera' },
  { label: '传感器事件', value: 'sensor' },
]

const visualCategoryOptions = [
  { label: '全部视觉事件', value: 'all' },
  { label: '禁涉水事件', value: 'wading' },
  { label: '禁渔事件', value: 'fishing' },
  { label: '自然灾害事件', value: 'natural_disaster' },
]

const riskOptions = [
  { label: '全部风险等级', value: 'all' },
  { label: '低风险', value: 'low' },
  { label: '中风险', value: 'medium' },
  { label: '高风险', value: 'high' },
]

const enabledOptions = [
  { label: '全部启用状态', value: 'all' },
  { label: '已启用', value: 'enabled' },
  { label: '已停用', value: 'disabled' },
]

const metricMap = {
  wind_speed_ms: { label: '风速', unit: 'm/s' },
  wind_speed: { label: '风速', unit: 'm/s' },
  rainfall: { label: '降雨量', unit: 'mm' },
  rain: { label: '降雨量', unit: 'mm' },
  hour_rain: { label: '小时雨量', unit: 'mm' },
  today_rain: { label: '当日雨量', unit: 'mm' },
  daily_rain: { label: '日雨量', unit: 'mm' },
  instant_rain: { label: '瞬时雨量', unit: 'mm' },
  rain_increment: { label: '时段雨量', unit: 'mm' },
  total_rain: { label: '累计雨量', unit: 'mm' },
  temperature: { label: '温度', unit: '℃' },
  humidity: { label: '湿度', unit: '%' },
  vibration: { label: '振动', unit: '' },
  person_present: { label: '人员', unit: '' },
  boat_present: { label: '船只', unit: '' },
}

const operatorMap = {
  '>=': '≥',
  '<=': '≤',
  '>': '>',
  '<': '<',
  '==': '=',
}

const actionIconMap = {
  broadcast: Bell,
  drone_dispatch: Promotion,
  machine_dog_dispatch: Aim,
  staff_task: User,
  report: Finished,
}

const actionLabelMap = {
  broadcast: '广播驱离',
  drone_dispatch: '无人机巡查',
  machine_dog_dispatch: '机器狗任务',
  staff_task: '人工处置',
}

const addActionOptions = [
  { label: '广播任务', type: 'broadcast', icon: Bell },
  { label: '无人机任务', type: 'drone_dispatch', icon: Promotion },
  { label: '机器狗任务', type: 'machine_dog_dispatch', icon: Aim },
  { label: '人工处置', type: 'staff_task', icon: User },
]

const machineDogOptions = [
  { value: 'dog-01', label: '绝影 Lite 3' },
]

const machineDogRouteOptions = [
  { value: 'all', label: '9号检测区域巡检路线' },
]

const events = computed(() => config.events)
const eventOnlineCount = computed(() => events.value.filter((event) => event.enabled !== false).length)
const eventOfflineCount = computed(() => events.value.length - eventOnlineCount.value)
const filteredEvents = computed(() => {
  const text = keyword.value.toLowerCase()
  const list = events.value.filter((event) => {
    if (sourceFilter.value !== 'all' && event.source_type !== sourceFilter.value) return false
    if (
      sourceFilter.value === 'camera'
      && visualCategoryFilter.value !== 'all'
      && visualEventCategory(event) !== visualCategoryFilter.value
    ) return false
    if (riskFilter.value !== 'all' && riskKey(event) !== riskFilter.value) return false
    if (enabledFilter.value === 'enabled' && !event.enabled) return false
    if (enabledFilter.value === 'disabled' && event.enabled) return false
    if (!text) return true
    return `${event.name || ''} ${event.category_label || ''}`.toLowerCase().includes(text)
  })
  return list.sort((first, second) => {
    if (sortFilter.value === 'name') return String(first.name || '').localeCompare(String(second.name || ''), 'zh-CN')
    if (sortFilter.value === 'enabled') return Number(second.enabled) - Number(first.enabled) || riskWeight(second) - riskWeight(first)
    return riskWeight(second) - riskWeight(first) || String(first.name || '').localeCompare(String(second.name || ''), 'zh-CN')
  })
})
const pagedEvents = computed(() => {
  const start = (eventPage.value - 1) * pageSize
  return filteredEvents.value.slice(start, start + pageSize)
})
const currentEvent = computed(() => events.value.find((event) => event.id === selectedEventId.value) || null)
const currentActions = computed(() => {
  if (!currentEvent.value) return []
  return config.action_configs
    .filter((action) => action.event_id === currentEvent.value.id)
    .slice()
    .sort((a, b) => (a.step_order || 0) - (b.step_order || 0) || (a.id || 0) - (b.id || 0))
})
const primaryCondition = computed(() => currentEvent.value?.conditions?.[0] || null)
const triggerDuration = computed(() => Number(primaryCondition.value?.duration ?? 0))
const recoveryDuration = computed(() => Number(currentEvent.value?.recovery_duration ?? 0))
const parsedCondition = computed(() => parseCondition(primaryCondition.value))
const defaultSourceName = computed(() => isVisualEvent(currentEvent.value) ? '摄像头视觉识别' : '传感器数据源')
const enabledBroadcastDevices = computed(() => config.broadcast_devices.filter((item) => item.enabled !== false))
const enabledBroadcastTemplates = computed(() => config.broadcast_templates.filter((item) => item.enabled !== false))
const droneOptions = computed(() => mergeConfiguredOptions(
  configuredDroneOptions.value,
  uniqueActionValues('drone_id').map((value) => ({ value, label: value })),
))
// ECA 后端只支持两条预置航线。不能把历史保存值或 DJI 文件列表直接
// 拼进下拉框，否则旧中文名称和内部 key（如 wading）会显示成重复航线。
const routeOptions = computed(() => FALLBACK_DRONE_ROUTE_OPTIONS)
const staffGroupOptions = computed(() => {
  const values = [
    DEFAULT_STAFF_GROUP,
    ...configuredStaffGroups.value,
    ...config.action_configs
    .filter((item) => item.action_type === 'staff_task')
    .map((item) => item.route_id)
    .filter(Boolean),
  ]
  return Array.from(new Set(values))
})
const canDeleteInspectorNode = computed(() => {
  if (!flowEditMode.value || !editingNode.value) return false
  const node = flowDraft.nodes.find((item) => item.id === editingNode.value.id)
  return Boolean(node && !node.locked && node.kind === 'action')
})

const visualTargetLabel = computed(() => {
  const expr = primaryCondition.value?.expression || currentEvent.value?.code || currentEvent.value?.name || ''
  const text = expr.toLowerCase()
  if (text.includes('boat') || text.includes('船')) return '船只'
  if (text.includes('person') || text.includes('人员')) return '人员'
  return '目标'
})
const visualZoneLabel = computed(() => {
  if (`${currentEvent.value?.code || ''}`.toLowerCase().includes('fishing')) return '禁捕区 A'
  return '检测区域'
})
const visualTriggerText = computed(() => `${visualTargetLabel.value}持续出现 ≥ ${triggerDuration.value} 秒`)
const visualRuleExpression = computed(() => {
  const zone = visualZoneLabel.value && visualZoneLabel.value !== '检测区域' ? `${visualZoneLabel.value} · ` : ''
  return `${zone}${visualTargetLabel.value}持续出现 ≥ ${triggerDuration.value} 秒`
})
const ruleDirty = computed(() => {
  if (!currentEvent.value) return false
  const durationDirty = Number(ruleForm.duration) !== triggerDuration.value
  const recoveryDirty = Number(ruleForm.recovery_duration) !== recoveryDuration.value
  const thresholdDirty = parsedCondition.value.editableThreshold
    && Number(ruleForm.threshold) !== Number(parsedCondition.value.value)
  return Boolean(durationDirty || recoveryDirty || thresholdDirty)
})
const readableRuleSummary = computed(() => {
  if (!currentEvent.value) return ''
  if (isVisualEvent(currentEvent.value)) return `${visualTriggerText.value}时触发，恢复 ${recoveryDuration.value} 秒后自动闭环。`
  const condition = parsedCondition.value
  return `${condition.metricLabel} ${condition.operatorLabel} ${condition.valueText} 时触发，恢复 ${recoveryDuration.value} 秒后自动闭环。`
})
const flowDisplayModel = computed(() => {
  flowLayoutVersion.value
  return applySavedFlowLayout(buildAutoFlowModel(currentActions.value))
})
const flowNodesForView = computed(() => flowEditMode.value ? flowDraft.nodes : flowDisplayModel.value.nodes)
const flowEdgesForView = computed(() => flowEditMode.value ? flowDraft.edges : flowDisplayModel.value.edges)
const flowBounds = computed(() => calculateFlowBounds(flowNodesForView.value))
const flowStageHeight = computed(() => Math.max(620, Math.ceil(flowBounds.value.rawMaxY + FLOW_STAGE_PADDING)))
const flowStageStyle = computed(() => ({
  width: `${FLOW_STAGE_WIDTH}px`,
  height: `${flowStageHeight.value}px`,
  transform: `translate(${fitTransform.x}px, ${fitTransform.y}px) scale(${fitTransform.scale})`,
}))
watch(filteredEvents, (list) => {
  const maxPage = Math.max(1, Math.ceil(list.length / pageSize))
  if (eventPage.value > maxPage) eventPage.value = maxPage
  if (!list.length || flowEditMode.value || ruleDirty.value) return
  if (!list.some((event) => event.id === selectedEventId.value)) selectEvent(list[0].id)
})

watch(sourceFilter, (value) => {
  if (value !== 'camera') visualCategoryFilter.value = 'all'
})

watch([keyword, sourceFilter, visualCategoryFilter, riskFilter, enabledFilter, sortFilter], () => {
  eventPage.value = 1
})

watch(
  [flowNodesForView, flowEdgesForView, () => canvasSize.width, () => canvasSize.height, flowEditMode],
  () => nextTick(fitFlowView),
  { deep: true },
)

watch(currentEvent, () => {
  resetRuleForm()
  nextTick(() => {
    setupCanvasObserver()
    updateCanvasSize()
    fitFlowView()
  })
})

async function loadConfig() {
  loading.value = true
  try {
    const res = await getIntegrationConfig()
    const data = res.data || {}
    config.events = (data.events || []).map(normalizeEvent)
    config.action_configs = data.action_configs || []
    config.broadcast_devices = data.broadcast_devices || []
    config.broadcast_templates = data.broadcast_templates || []
    ensureSelectedEvent()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '事件配置加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStaffGroups() {
  try {
    const res = await getStaffList({ page: 1, page_size: 100 })
    const groups = res.data?.groups || res.groups || []
    if (Array.isArray(groups)) configuredStaffGroups.value = groups.filter(Boolean)
  } catch {
    // 组别加载失败时保留已有动作中的组别，避免覆盖当前配置。
  }
}

async function loadDroneLinkageOptions() {
  try {
    const loginRes = await dijLogin(DIJ_USERNAME, DIJ_PASSWORD)
    const token = loginRes.data?.access_token
    if (token) localStorage.setItem('dij_token', token)
    const workspaceRes = await getCurrentWorkspace()
    const workspaceId = workspaceRes.data?.workspace_id || workspaceRes.data?.id || '0'

    const topologyRes = await getDroneDevices(workspaceId)
    const topology = (topologyRes.data?.list || topologyRes.data || []).map((item) => ({
      ...item,
      device_sn: item.device_sn || item.sn || item.device_id,
    }))
    let devices = []
    try {
      const boundRes = await getBoundDevices(workspaceId, { page: 1, page_size: 100, domain: 0 })
      devices = (boundRes.data?.list || boundRes.data?.items || []).map((item) => ({
        ...item,
        device_sn: item.device_sn || item.sn || item.device_id,
      }))
    } catch {
      devices = topology.filter((item) => item.domain === 0 || item.device_type === 0)
    }
    const deviceOptions = devices
      .filter((item) => item.device_sn)
      .map((item) => {
        const name = item.nickname || item.device_name || item.deviceCallsign || item.device_sn
        return { value: item.device_sn, label: name }
      })
    if (deviceOptions.length) configuredDroneOptions.value = mergeConfiguredOptions(deviceOptions)

  } catch {
    // DJI 服务不可用时使用与无人机页面一致的演示选项。
  }
}

function normalizeEvent(row) {
  const conditions = Array.isArray(row.conditions) ? row.conditions : []
  const primary = conditions[0] || {}
  return {
    ...row,
    conditions,
    enabled: row.enabled !== false,
    source_type: primary.source_type || inferSourceType(row),
  }
}

function inferSourceType(row) {
  const text = `${row.category || ''} ${row.category_label || ''} ${row.code || ''} ${row.name || ''}`.toLowerCase()
  if (text.includes('person') || text.includes('boat') || text.includes('camera') || text.includes('视觉')) return 'camera'
  return 'sensor'
}

function visualEventCategory(event) {
  const code = String(event?.code || '').toUpperCase()
  const name = String(event?.name || '')
  if (code.startsWith('PERSON_') || /^人员/.test(name)) return 'wading'
  if (code.startsWith('BOAT_') || /^船只/.test(name)) return 'fishing'
  return 'natural_disaster'
}

function ensureSelectedEvent() {
  const routeEventId = Number(route.query.eventId)
  const storedEventId = Number(localStorage.getItem(LAST_EVENT_KEY))
  const preferredId = [routeEventId, storedEventId].find((id) => events.value.some((event) => event.id === id))
  const enabledEvent = events.value.find((event) => event.enabled)
  const firstEvent = events.value[0]
  const nextId = preferredId || enabledEvent?.id || firstEvent?.id || null
  if (nextId) selectEvent(nextId, { replaceQuery: !route.query.eventId })
}

function selectEvent(id, options = {}) {
  selectedEventId.value = id
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  editingNode.value = null
  inspectorMode.value = 'view'
  resetRuleForm()
  localStorage.setItem(LAST_EVENT_KEY, String(id))
  if (options.replaceQuery === false) return
  router.replace({ query: { ...route.query, eventId: id } }).catch(() => null)
}

async function openFlowWorkspace(event) {
  if (editingEventId.value && ruleDirty.value) {
    try {
      await ElMessageBox.confirm('当前规则修改尚未保存，是否放弃并查看联动？', '查看联动', { type: 'warning' })
    } catch {
      return
    }
    editingEventId.value = null
  }
  selectEvent(event.id)
  resetRuleForm()
  flowDialogVisible.value = true
  flowEditMode.value = false
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  editingNode.value = null
  await nextTick()
  updateCanvasSize()
  setupCanvasObserver()
  fitFlowView()
}

function closeFlowWorkspace() {
  if (flowEditMode.value) cancelFlowEdit()
  editingNode.value = null
  inspectorMode.value = 'view'
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  connectingFromId.value = ''
  teardownCanvasObserver()
}

async function toggleListEvent(event, nextEnabled) {
  if (flowEditMode.value && event.id === selectedEventId.value) {
    try {
      await ElMessageBox.confirm('当前流程修改尚未保存，是否继续修改事件状态？', '事件状态', { type: 'warning' })
    } catch {
      return
    }
  }
  if (!nextEnabled) {
    try {
      await ElMessageBox.confirm('停用后，该事件规则将不再参与触发判断。', '停用事件', { type: 'warning' })
    } catch {
      return
    }
  }
  savingEventId.value = event.id
  try {
    await updateEventConfig(event.id, { enabled: nextEnabled })
    for (const condition of event.conditions || []) {
      await updateConditionConfig(condition.id, { enabled: nextEnabled })
    }
    ElMessage.success(nextEnabled ? '事件已启用' : '事件已停用')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '状态更新失败')
  } finally {
    savingEventId.value = null
  }
}

function parseCondition(condition) {
  const fallback = {
    metricLabel: condition?.name || '系统规则',
    operatorLabel: '',
    key: '',
    operator: '',
    value: '',
    unit: '',
    valueText: '系统预置条件',
    editableThreshold: false,
  }
  const expression = condition?.expression || ''
  const match = expression.match(/([a-zA-Z_][\w.]*)\s*(>=|<=|==|>|<)\s*([0-9.]+)/)
  if (!match) return fallback
  const [, key, operator, value] = match
  const metric = metricMap[key] || inferMetricMeta(key, condition?.name)
  const operatorLabel = operatorMap[operator] || operator
  const isBooleanPresence = ['person_present', 'boat_present'].includes(key) && operator === '==' && Number(value) === 1
  return {
    metricLabel: metric.label,
    operatorLabel,
    key,
    operator,
    value,
    unit: metric.unit,
    valueText: isBooleanPresence ? '出现' : `${value}${metric.unit ? ` ${metric.unit}` : ''}`,
    editableThreshold: !isBooleanPresence,
  }
}

function inferMetricMeta(key, name = '') {
  const text = `${key || ''} ${name || ''}`.toLowerCase()
  if (text.includes('rain') || text.includes('雨')) return { label: name || '降雨量', unit: 'mm' }
  if (text.includes('wind') || text.includes('风')) return { label: name || '风速', unit: 'm/s' }
  if (text.includes('temp') || text.includes('温')) return { label: name || '温度', unit: '℃' }
  if (text.includes('humid') || text.includes('湿')) return { label: name || '湿度', unit: '%' }
  return { label: name || key, unit: '' }
}

function sourceLabel(event) {
  if (event?.source_type === 'camera') return '视觉事件'
  if (event?.source_type === 'sensor') return '传感器事件'
  return event?.source_type || '未绑定数据源'
}

function compactSourceLabel(event) {
  if (event?.source_type === 'camera') return '视觉'
  if (event?.source_type === 'sensor') return '传感器'
  return event?.source_type || '未知'
}

function riskLabel(level, fallback = '') {
  return ({ 1: '低风险', 2: '中风险', 3: '高风险', LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[level] || fallback || '未知风险'
}

function riskTagType(level, fallback = '') {
  const label = riskLabel(level, fallback)
  if (label.includes('高')) return 'danger'
  if (label.includes('中')) return 'warning'
  if (label.includes('低')) return 'success'
  return 'info'
}

function riskKey(event) {
  const label = riskLabel(event?.risk_level, event?.risk_label)
  if (label.includes('高')) return 'high'
  if (label.includes('中')) return 'medium'
  if (label.includes('低')) return 'low'
  return 'unknown'
}

function riskWeight(event) {
  const label = riskLabel(event?.risk_level, event?.risk_label)
  if (label.includes('高')) return 3
  if (label.includes('中')) return 2
  if (label.includes('低')) return 1
  return 0
}

function listRuleSummary(event) {
  const condition = event?.conditions?.[0] || null
  if (isVisualEvent(event)) {
    const text = `${condition?.expression || event?.code || event?.name || ''}`.toLowerCase()
    const target = text.includes('boat') || text.includes('船') ? '船只' : text.includes('person') || text.includes('人员') ? '人员' : '目标'
    const zone = `${event?.code || ''}`.toLowerCase().includes('fishing') ? '禁捕区 · ' : ''
    return `${zone}${target}持续出现 ≥ ${Number(condition?.duration ?? 0)} 秒`
  }
  const parsed = parseCondition(condition)
  return parsed.operatorLabel ? `${parsed.metricLabel} ${parsed.operatorLabel} ${parsed.valueText}` : parsed.valueText
}

function durationText(event) {
  return `${Number(event?.conditions?.[0]?.duration ?? 0)} 秒`
}

function recoveryText(event) {
  return `${Number(event?.recovery_duration ?? 0)} 秒`
}

function isVisualEvent(event) {
  return event?.source_type === 'camera'
}

function resetRuleForm() {
  ruleForm.threshold = ''
  ruleForm.duration = triggerDuration.value
  ruleForm.recovery_duration = recoveryDuration.value
  ruleForm.zone = visualZoneLabel.value
  ruleForm.target = visualTargetLabel.value
  if (parsedCondition.value.editableThreshold) {
    ruleForm.threshold = parsedCondition.value.value
  }
}

async function startInlineRuleEdit(event) {
  if (editingEventId.value && editingEventId.value !== event.id && ruleDirty.value) {
    try {
      await ElMessageBox.confirm('当前规则修改尚未保存，是否放弃？', '切换编辑行', { type: 'warning' })
    } catch {
      return
    }
  }
  selectedEventId.value = event.id
  editingEventId.value = event.id
  resetRuleForm()
}

function cancelInlineRuleEdit() {
  editingEventId.value = null
  resetRuleForm()
}

async function saveInlineRule(event) {
  selectedEventId.value = event.id
  await saveRule()
  editingEventId.value = null
}

async function saveRule() {
  if (!currentEvent.value) return
  savingRule.value = true
  try {
    const duration = clampNumber(ruleForm.duration, 0, 3600)
    const recoveryDurationValue = clampNumber(ruleForm.recovery_duration, 0, 3600)
    await updateEventConfig(currentEvent.value.id, { recovery_duration: recoveryDurationValue })
    if (primaryCondition.value?.id) {
      const payload = { duration }
      if (parsedCondition.value.editableThreshold) {
        payload.expression = expressionWithThreshold(primaryCondition.value.expression, ruleForm.threshold)
      }
      await updateConditionConfig(primaryCondition.value.id, payload)
    }
    ElMessage.success('事件规则已保存')
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingRule.value = false
  }
}

function expressionWithThreshold(expression, threshold) {
  const nextValue = Number(threshold)
  if (!Number.isFinite(nextValue)) return expression
  const formatted = Number.isInteger(nextValue) ? String(nextValue) : String(Number(nextValue.toFixed(3)))
  return String(expression || '').replace(/([a-zA-Z_][\w.]*\s*(?:>=|<=|==|>|<)\s*)([0-9.]+)/, `$1${formatted}`)
}

function goZoneConfig() {
  router.push({ path: '/system/rules/zones', query: currentEvent.value ? { fromEventId: currentEvent.value.id } : {} })
}

function buildAutoFlowModel(actions) {
  if (!currentEvent.value) return { nodes: [], edges: [] }
  const actionCount = actions.length
  const sourceW = 200
  const judgeW = 220
  const routeW = 196
  const eventW = 238
  const closeW = 190
  const archiveW = 176
  const nodeH = 96
  const eventH = 110
  const topY = 64
  const x = {
    source: 70,
    judge: 316,
    route: 574,
    event: 552,
    close: 552,
    archive: 792,
  }
  const sourceIcon = isVisualEvent(currentEvent.value) ? VideoCamera : Connection
  const nodes = [
    baseNode('source', 'source', x.source, topY, sourceW, nodeH, sourceIcon, primaryCondition.value?.source_name || defaultSourceName.value, sourceLabel(currentEvent.value), '', true, 'source-node'),
    baseNode('judge', 'system', x.judge, topY, judgeW, nodeH, Warning, isVisualEvent(currentEvent.value) ? '规则判断' : '阈值判断', isVisualEvent(currentEvent.value) ? visualRuleExpression.value : `${parsedCondition.value.metricLabel} ${parsedCondition.value.operatorLabel} ${parsedCondition.value.valueText}`, '', true, 'rule-node'),
    baseNode('route', 'system', x.route, topY, routeW, nodeH, Setting, '风险路由', riskLabel(currentEvent.value.risk_level, currentEvent.value.risk_label), '', true, 'route-node'),
    baseNode('event', 'system', x.event, 228, eventW, eventH, Bell, '安全事件创建', '进入处置流程', readableRuleSummary.value, true, 'event-node'),
  ]
  const edges = [
    edge('source', 'judge'),
    edge('judge', 'route'),
    edge('route', 'event'),
  ]

  if (!actions.length) {
    nodes.push(
      baseNode('auto-close', 'system', x.close, 404, closeW, 92, Finished, '自动闭环', `恢复 ${recoveryDuration.value} 秒`, '', true, 'close-node'),
      baseNode('archive', 'system close', x.archive, 404, archiveW, 92, Finished, '归档', '证据留痕', '', true, 'archive-node'),
    )
    edges.push(edge('event', 'auto-close'), edge('auto-close', 'archive'))
    return { nodes, edges }
  }

  const actionW = 206
  const actionH = 100
  const columns = Math.min(3, Math.max(1, actionCount))
  const rows = Math.ceil(actionCount / columns)
  const columnGap = 54
  const rowGap = 34
  const totalActionWidth = columns * actionW + (columns - 1) * columnGap
  const actionStartX = Math.round((FLOW_STAGE_WIDTH - totalActionWidth) / 2)
  const actionStartY = 414
  const actionX = (index) => actionStartX + (index % columns) * (actionW + columnGap)
  const actionY = (index) => actionStartY + Math.floor(index / columns) * (actionH + rowGap)
  const closeY = actionStartY + rows * (actionH + rowGap) + 26

  actions.forEach((action, index) => {
    const nodeId = actionNodeId(action)
    const node = baseNode(
      nodeId,
      'action',
      actionX(index),
      actionY(index),
      actionW,
      actionH,
      actionIcon(action.action_type),
      actionBusinessLabel(action),
      actionBusinessSummary(action),
      actionBusinessDetail(action),
      false,
    )
    node.action = { ...action }
    node.configurable = isConfigurableAction(action)
    node.disabled = action.enabled === false
    node.temp = Boolean(action.temp)
    nodes.push(node)
    edges.push(edge('event', node.id, action.enabled !== false), edge(node.id, 'auto-close', action.enabled !== false))
  })

  nodes.push(
    baseNode('auto-close', 'system', x.close, closeY, closeW, 92, Finished, '自动闭环', `恢复 ${recoveryDuration.value} 秒`, '', true, 'close-node'),
    baseNode('archive', 'system close', x.archive, closeY, archiveW, 92, Finished, '归档', '证据留痕', '', true, 'archive-node'),
  )
  edges.push(edge('auto-close', 'archive'))
  return { nodes, edges }
}

function baseNode(id, kind, x, y, w, h, icon, title, subtitle, detail = '', locked = false, role = '') {
  return { id, kind, role, x, y, w, h, icon, title, subtitle, detail, locked, configurable: false, disabled: false }
}

function edge(from, to, active = true) {
  return { id: `${from}-${to}`, from, to, active }
}

function applySavedFlowLayout(model) {
  const saved = readFlowLayout()
  if (!saved) return model
  const nodeMap = new Map(model.nodes.map((node) => [node.id, node]))
  for (const savedNode of saved.nodes || []) {
    const node = nodeMap.get(savedNode.id)
    if (node) {
      node.x = Number(savedNode.x) || node.x
      node.y = Number(savedNode.y) || node.y
    }
  }
  if (Array.isArray(saved.edges)) {
    const validIds = new Set(model.nodes.map((node) => node.id))
    const edges = saved.edges
      .filter((item) => validIds.has(item.from) && validIds.has(item.to))
      .map((item) => edge(item.from, item.to, item.active !== false))
    if (edges.length) model.edges = edges
  }
  return model
}

function readFlowLayout() {
  if (!currentEvent.value) return null
  try {
    return JSON.parse(localStorage.getItem(`${FLOW_LAYOUT_PREFIX}${currentEvent.value.id}`) || 'null')
  } catch {
    return null
  }
}

function writeFlowLayout(nodes, edges) {
  if (!currentEvent.value) return
  const payload = {
    nodes: nodes.map(({ id, x, y }) => ({ id, x: Math.round(x), y: Math.round(y) })),
    edges: edges.map(({ from, to, active }) => ({ from, to, active })),
  }
  localStorage.setItem(`${FLOW_LAYOUT_PREFIX}${currentEvent.value.id}`, JSON.stringify(payload))
  flowLayoutVersion.value += 1
}

function enterFlowEdit() {
  const model = cloneFlowModel(flowDisplayModel.value)
  flowDraft.nodes = model.nodes
  flowDraft.edges = model.edges
  editingNode.value = null
  inspectorMode.value = 'view'
  deletedActionIds.value = []
  flowEditMode.value = true
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  connectingFromId.value = ''
  nextTick(fitFlowView)
}

function cancelFlowEdit() {
  flowEditMode.value = false
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  connectingFromId.value = ''
  editingNode.value = null
  inspectorMode.value = 'view'
  deletedActionIds.value = []
  flowDraft.nodes = []
  flowDraft.edges = []
  nextTick(fitFlowView)
}

function cloneFlowModel(model) {
  return {
    nodes: model.nodes.map((node) => ({ ...node, action: node.action ? { ...node.action } : null })),
    edges: model.edges.map((item) => ({ ...item })),
  }
}

function selectNode(node) {
  if (!node) return
  if (!flowEditMode.value && node.action && node.configurable && editingNode.value?.id === node.id) {
    closeInspector()
    return
  }
  selectedNodeId.value = node.id
  selectedEdgeId.value = ''
  if (!flowEditMode.value && node.action && node.configurable) openNodeViewer(node)
}

function selectEdge(id) {
  if (!flowEditMode.value) return
  selectedEdgeId.value = id
  selectedNodeId.value = ''
}

function clearFlowSelection() {
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  connectingFromId.value = ''
  closeInspector()
}

function startNodeDrag(node, event) {
  if (!flowEditMode.value || event.button !== 0) return
  selectedNodeId.value = node.id
  selectedEdgeId.value = ''
  dragging.value = { id: node.id, startX: event.clientX, startY: event.clientY, nodeX: node.x, nodeY: node.y }
}

function handleCanvasPointerMove(event) {
  if (!dragging.value || !canvasRef.value) return
  const node = flowDraft.nodes.find((item) => item.id === dragging.value.id)
  if (!node) return
  const scale = fitTransform.scale || 1
  node.x = clampNumber(dragging.value.nodeX + (event.clientX - dragging.value.startX) / scale, 8, FLOW_STAGE_WIDTH - node.w - 8)
  node.y = clampNumber(dragging.value.nodeY + (event.clientY - dragging.value.startY) / scale, 38, flowStageHeight.value - node.h - 8)
}

function finishDrag() {
  dragging.value = null
}

function startConnection(node) {
  if (!flowEditMode.value) return
  connectingFromId.value = node.id
}

function completeConnection(node) {
  if (!flowEditMode.value || !connectingFromId.value || connectingFromId.value === node.id) return
  const from = connectingFromId.value
  const to = node.id
  flowDraft.edges = flowDraft.edges.filter((item) => !(item.from === from && item.to === to))
  flowDraft.edges.push(edge(from, to, true))
  connectingFromId.value = ''
}

function deleteSelectedEdge() {
  if (!selectedEdgeId.value) return
  flowDraft.edges = flowDraft.edges.filter((item) => item.id !== selectedEdgeId.value)
  selectedEdgeId.value = ''
}

function deleteSelectedNode() {
  const node = flowDraft.nodes.find((item) => item.id === selectedNodeId.value)
  if (!node || node.locked || node.kind !== 'action') return
  if (node.action?.id && !node.temp) deletedActionIds.value.push(node.action.id)
  flowDraft.nodes = flowDraft.nodes.filter((item) => item.id !== node.id)
  flowDraft.edges = flowDraft.edges.filter((item) => item.from !== node.id && item.to !== node.id)
  selectedNodeId.value = ''
}

function deleteFlowNode(node) {
  if (!node || node.locked || node.kind !== 'action') return
  selectedNodeId.value = node.id
  deleteSelectedNode()
  if (editingNode.value?.id === node.id) closeInspector()
}

function autoLayoutDraft() {
  const actions = flowDraft.nodes.filter((node) => node.kind === 'action').map((node) => node.action)
  const model = buildAutoFlowModel(actions)
  flowDraft.nodes = model.nodes
  flowDraft.edges = model.edges
  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  nextTick(fitFlowView)
}

function addActionNode(type) {
  const tempId = `temp-${Date.now()}`
  const action = defaultAction(type, tempId)
  const base = insertionBaseNode()
  const node = actionNodeFromAction(action, base)
  flowDraft.nodes.push(node)
  insertActionEdges(node, base)
  selectedNodeId.value = node.id
  addNodeDialogVisible.value = false
  nextTick(fitFlowView)
}

function insertionBaseNode() {
  if (selectedEdgeId.value) {
    const selectedEdge = flowDraft.edges.find((item) => item.id === selectedEdgeId.value)
    const fromNode = flowDraft.nodes.find((item) => item.id === selectedEdge?.from)
    const toNode = flowDraft.nodes.find((item) => item.id === selectedEdge?.to)
    if (fromNode && toNode) {
      return {
        edge: selectedEdge,
        x: Math.round((fromNode.x + fromNode.w + toNode.x) / 2 - 103),
        y: Math.round((fromNode.y + toNode.y) / 2 + 118),
      }
    }
  }
  const selectedNode = flowDraft.nodes.find((item) => item.id === selectedNodeId.value)
  const fallback = flowDraft.nodes.find((item) => item.id === 'event')
  return selectedNode || fallback || { id: 'event', x: 520, y: 228, w: 238, h: 110 }
}

function actionNodeFromAction(action, base) {
  const actionW = 206
  const actionH = 92
  const preferredX = Number(base?.x ?? 0) + Number(base?.w ?? 0) + 72
  const nextX = preferredX + actionW < FLOW_STAGE_WIDTH - FLOW_STAGE_PADDING
    ? preferredX
    : Math.max(FLOW_STAGE_PADDING, Number(base?.x ?? 0))
  const nextY = preferredX + actionW < FLOW_STAGE_WIDTH - FLOW_STAGE_PADDING
    ? Number(base?.y ?? 0)
    : Number(base?.y ?? 0) + Number(base?.h ?? 92) + 56
  const node = baseNode(
    actionNodeId(action),
    'action',
    clampNumber(nextX, FLOW_STAGE_PADDING, FLOW_STAGE_WIDTH - actionW - FLOW_STAGE_PADDING),
    Math.max(86, Math.round(nextY)),
    actionW,
    actionH,
    actionIcon(action.action_type),
    actionBusinessLabel(action),
    actionBusinessSummary(action),
    actionBusinessDetail(action),
    false,
  )
  node.action = { ...action }
  node.configurable = isConfigurableAction(action)
  node.temp = true
  return node
}

function insertActionEdges(node, base) {
  if (base?.edge) {
    flowDraft.edges = flowDraft.edges.filter((item) => item.id !== base.edge.id)
    flowDraft.edges.push(edge(base.edge.from, node.id), edge(node.id, base.edge.to))
    selectedEdgeId.value = ''
    return
  }
  const fromId = base?.id && base.id !== 'archive' && base.id !== 'auto-close' ? base.id : 'event'
  flowDraft.edges.push(edge(fromId, node.id))
  if (!flowDraft.edges.some((item) => item.from === node.id)) {
    flowDraft.edges.push(edge(node.id, 'auto-close'))
  }
}

function defaultAction(type, tempId) {
  return {
    id: tempId,
    temp: true,
    event_id: currentEvent.value?.id,
    action_type: type,
    action_name: actionLabelMap[type] || '联动动作',
    enabled: true,
    step_order: flowDraft.nodes.filter((item) => item.kind === 'action').length + 1,
    timeout_seconds: 60,
    failure_strategy: 'continue',
    retry_count: 0,
    repeat_interval_seconds: 60,
    max_executions: 1,
    broadcast_device_id: null,
    template_id: null,
    drone_id: '',
    route_id: '',
  }
}

function openNodeConfig(node) {
  if (!node?.configurable) return
  if (!flowEditMode.value) {
    enterFlowEdit()
    node = flowDraft.nodes.find((item) => item.id === node.id) || node
  }
  selectedNodeId.value = node.id
  inspectorMode.value = 'edit'
  editingNode.value = node
  const action = node.action
  actionForm.broadcast_device_id = action.broadcast_device_id ?? null
  actionForm.template_id = action.template_id || ''
  actionForm.repeat_mode = Number(action.max_executions || 1) > 1 ? 'repeat' : 'once'
  actionForm.repeat_interval_seconds = Number(action.repeat_interval_seconds || 60)
  actionForm.max_executions = Math.max(1, Number(action.max_executions || 1))
  actionForm.drone_id = action.drone_id || ''
  actionForm.route_id = action.action_type === 'drone_dispatch'
    ? normalizeDroneRouteId(action.route_id)
    : action.action_type === 'machine_dog_dispatch'
      ? normalizeMachineDogRouteId(action.route_id)
      : (action.route_id || '')
  actionForm.machine_dog_id = action.config_json?.machine_dog_id || ''
  actionForm.staff_group = action.action_type === 'staff_task'
    ? (action.route_id || DEFAULT_STAFF_GROUP)
    : ''
  actionForm.staff_event_type = action.action_type === 'staff_task'
    ? (action.config_json?.event_type || '')
    : ''
  actionForm.staff_demo = action.action_type === 'staff_task' && action.config_json?.demo === true
  actionForm.staff_note = action.action_type === 'staff_task'
    ? (action.config_json?.note || '')
    : ''
}

function openNodeViewer(node) {
  if (!node?.action || !node.configurable) return
  selectedNodeId.value = node.id
  selectedEdgeId.value = ''
  inspectorMode.value = 'view'
  editingNode.value = node
}

function closeInspector() {
  editingNode.value = null
  inspectorMode.value = 'view'
  if (!flowEditMode.value) selectedNodeId.value = ''
}

function actionReadonlyFields(action) {
  if (!action) return []
  if (action.action_type === 'broadcast') {
    return [
      { label: '广播设备', value: findBroadcastDevice(action.broadcast_device_id)?.name || '未选择广播设备' },
      { label: '播报模板', value: findBroadcastTemplate(action.template_id)?.name || '未选择播报模板' },
      { label: '执行方式', value: Number(action.max_executions || 1) > 1 ? `周期 · ${action.repeat_interval_seconds || 60} 秒 × ${action.max_executions} 次` : '单次播报' },
    ]
  }
  if (action.action_type === 'drone_dispatch') {
    return [
      { label: '无人机型号', value: findConfiguredOption(droneOptions.value, action.drone_id)?.label || action.drone_id || '未选择无人机型号' },
      { label: '航线', value: findConfiguredOption(routeOptions.value, normalizeDroneRouteId(action.route_id))?.label || action.route_id || '未选择航线' },
    ]
  }
  if (action.action_type === 'machine_dog_dispatch') {
    return [
      { label: '机器狗型号', value: findMachineDog(action.config_json?.machine_dog_id)?.label || '未选择机器狗型号' },
      { label: '巡检路线', value: findMachineDogRoute(normalizeMachineDogRouteId(action.route_id))?.label || action.route_id || '未选择巡检路线' },
    ]
  }
  if (action.action_type === 'staff_task') {
    return [
      { label: '处置工作组', value: action.route_id || '未选择处置组' },
      { label: '事件类型', value: action.config_json?.event_type === 'NIGHT_FISHING' ? '夜间捕鱼事件' : action.config_json?.event_type === 'PERSON_WADING' ? '人员涉水事件' : action.config_json?.event_type === 'FLOOD_EVENT' ? '洪水事件' : '自动识别' },
      { label: '执行方式', value: action.config_json?.demo === true ? '演示自动闭环' : '等待人工处置' },
    ]
  }
  return []
}

function saveNodeConfig() {
  if (!editingNode.value?.action) return
  const action = editingNode.value.action
  if (action.action_type === 'broadcast') {
    if (!actionForm.broadcast_device_id || !actionForm.template_id) {
      ElMessage.warning('请先选择广播设备和播报模板')
      return
    }
    action.broadcast_device_id = actionForm.broadcast_device_id
    action.template_id = actionForm.template_id || null
    action.repeat_interval_seconds = actionForm.repeat_mode === 'repeat' ? clampNumber(actionForm.repeat_interval_seconds, 1, 86400) : 60
    action.max_executions = actionForm.repeat_mode === 'repeat' ? clampNumber(actionForm.max_executions, 2, 100) : 1
  } else if (action.action_type === 'drone_dispatch') {
    if (!actionForm.drone_id || !actionForm.route_id) {
      ElMessage.warning('请先选择无人机型号和航线')
      return
    }
    action.drone_id = actionForm.drone_id || null
    action.route_id = normalizeDroneRouteId(actionForm.route_id) || null
  } else if (action.action_type === 'machine_dog_dispatch') {
    if (!actionForm.machine_dog_id || !actionForm.route_id) {
      ElMessage.warning('请先选择机器狗型号和巡检路线')
      return
    }
    action.route_id = normalizeMachineDogRouteId(actionForm.route_id) || null
    action.config_json = {
      ...(action.config_json || {}),
      machine_dog_id: actionForm.machine_dog_id || null,
    }
  } else if (action.action_type === 'staff_task') {
    action.route_id = actionForm.staff_group || DEFAULT_STAFF_GROUP
    action.config_json = {
      ...(action.config_json || {}),
      event_type: actionForm.staff_event_type || null,
      demo: actionForm.staff_demo === true,
      note: actionForm.staff_note || null,
    }
  }
  editingNode.value.title = actionBusinessLabel(action)
  editingNode.value.subtitle = actionBusinessSummary(action)
  editingNode.value.detail = actionBusinessDetail(action)
  ElMessage.success('动作配置已应用')
}

function deleteInspectorNode() {
  if (!canDeleteInspectorNode.value) return
  selectedNodeId.value = editingNode.value.id
  deleteSelectedNode()
  closeInspector()
}

async function saveFlow() {
  if (!currentEvent.value) return
  if (!validateFlowDraft()) return
  savingFlow.value = true
  try {
    for (const id of deletedActionIds.value) await deleteActionConfig(id)
    const actionNodes = flowDraft.nodes.filter((node) => node.kind === 'action')
    for (let index = 0; index < actionNodes.length; index += 1) {
      const node = actionNodes[index]
      const payload = actionPayloadForSave(node.action, index + 1)
      if (node.temp) {
        const res = await createActionConfig(payload)
        const created = res.data || {}
        const oldId = node.id
        node.action = { ...node.action, ...created, id: created.id, temp: false }
        node.id = actionNodeId(node.action)
        node.temp = false
        flowDraft.edges = flowDraft.edges.map((item) => ({
          ...item,
          id: item.id.replace(oldId, node.id),
          from: item.from === oldId ? node.id : item.from,
          to: item.to === oldId ? node.id : item.to,
        }))
      } else {
        await updateActionConfig(node.action.id, payload)
      }
    }
    writeFlowLayout(flowDraft.nodes, flowDraft.edges)
    ElMessage.success('联动流程已保存')
    flowEditMode.value = false
    closeInspector()
    await loadConfig()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingFlow.value = false
  }
}

function validateFlowDraft() {
  const invalidBroadcast = flowDraft.nodes.find((node) => (
    node.kind === 'action'
    && node.action?.action_type === 'broadcast'
    && (!node.action.broadcast_device_id || !node.action.template_id)
  ))
  if (invalidBroadcast) {
    selectedNodeId.value = invalidBroadcast.id
    openNodeConfig(invalidBroadcast)
    ElMessage.warning('请完善广播动作的设备和播报模板')
    return false
  }
  const invalidDrone = flowDraft.nodes.find((node) => (
    node.kind === 'action'
    && node.action?.action_type === 'drone_dispatch'
    && (!node.action?.drone_id || !node.action?.route_id)
  ))
  if (invalidDrone) {
    selectedNodeId.value = invalidDrone.id
    openNodeConfig(invalidDrone)
    ElMessage.warning('请完善无人机任务的型号和航线')
    return false
  }
  const invalidMachineDog = flowDraft.nodes.find((node) => (
    node.kind === 'action'
    && node.action?.action_type === 'machine_dog_dispatch'
    && (!node.action?.config_json?.machine_dog_id || !node.action?.route_id)
  ))
  if (invalidMachineDog) {
    selectedNodeId.value = invalidMachineDog.id
    openNodeConfig(invalidMachineDog)
    ElMessage.warning('请完善机器狗任务的型号和巡检路线')
    return false
  }
  return true
}

function actionPayloadForSave(action, stepOrder) {
  return {
    event_id: currentEvent.value.id,
    enabled: action.enabled !== false,
    step_order: stepOrder,
    action_type: action.action_type,
    action_name: action.action_name || actionLabelMap[action.action_type] || '联动动作',
    timeout_seconds: action.timeout_seconds || 60,
    failure_strategy: action.failure_strategy || 'continue',
    retry_count: action.retry_count || 0,
    broadcast_device_id: action.broadcast_device_id ?? null,
    template_id: action.template_id || null,
    drone_id: action.drone_id || null,
    route_id: action.route_id || null,
    config_json: action.config_json || null,
    repeat_interval_seconds: action.repeat_interval_seconds || 60,
    max_executions: action.max_executions || 1,
  }
}

function actionNodeId(action) {
  return action.temp ? `action-${action.id}` : `action-${action.id}`
}

function actionIcon(type) {
  return actionIconMap[type] || Setting
}

function actionBusinessLabel(action) {
  if (!action) return ''
  return actionLabelMap[action.action_type] || action.action_label || action.action_name || '联动动作'
}

function actionBusinessSummary(action) {
  if (!action) return ''
  if (action.enabled === false) return '当前动作已停用'
  if (action.action_type === 'broadcast') {
    const device = findBroadcastDevice(action.broadcast_device_id)
    return device?.name || '未选择广播设备'
  }
  if (action.action_type === 'drone_dispatch') {
    return findConfiguredOption(droneOptions.value, action.drone_id)?.label || action.drone_id || '未选择无人机型号'
  }
  if (action.action_type === 'machine_dog_dispatch') {
    return findMachineDog(action.config_json?.machine_dog_id)?.label || '未选择机器狗型号'
  }
  if (action.action_type === 'staff_task') return action.route_id || '未选择处置组'
  return action.action_name || '业务动作'
}

function actionBusinessDetail(action) {
  if (!action || action.enabled === false) return ''
  if (action.action_type === 'broadcast') {
    const template = findBroadcastTemplate(action.template_id)
    const templateText = template?.name || '未选择模板'
    return Number(action.max_executions || 1) > 1
      ? `${templateText} · ${action.repeat_interval_seconds || 60}s × ${action.max_executions}`
      : `${templateText} · 单次`
  }
  if (action.action_type === 'drone_dispatch') {
    return findConfiguredOption(routeOptions.value, normalizeDroneRouteId(action.route_id))?.label || action.route_id || '未选择航线'
  }
  if (action.action_type === 'machine_dog_dispatch') {
    return findMachineDogRoute(normalizeMachineDogRouteId(action.route_id))?.label || '未选择巡检路线'
  }
  return ''
}

function isConfigurableAction(action) {
  return ['broadcast', 'drone_dispatch', 'machine_dog_dispatch', 'staff_task'].includes(action?.action_type)
}

function findBroadcastDevice(id) {
  return config.broadcast_devices.find((item) => item.id === id)
}

function findBroadcastTemplate(id) {
  return config.broadcast_templates.find((item) => item.id === id)
}

function findMachineDog(id) {
  return machineDogOptions.find((item) => item.value === id)
}

function findMachineDogRoute(id) {
  return machineDogRouteOptions.find((item) => item.value === id)
}

function normalizeDroneRouteId(routeId) {
  const value = String(routeId || '').trim().toLowerCase()
  const aliases = {
    fishing: 'fishing',
    '禁渔': 'fishing',
    '禁渔航线': 'fishing',
    wading: 'wading',
    '涉水': 'wading',
    '禁涉水': 'wading',
    '禁涉水航线': 'wading',
  }
  return aliases[value] || value
}

function normalizeMachineDogRouteId(routeId) {
  const value = String(routeId || '').trim().toLowerCase()
  const aliases = {
    all: 'all',
    '机器狗全路线': 'all',
    '9号检测区域巡检路线': 'all',
    '巡检路线': 'all',
    'route-a': 'all',
    'route-b': 'all',
    '岸线由西向东巡检': 'all',
    '岸线由东向西巡检': 'all',
  }
  return aliases[value] || value
}

function uniqueActionValues(field) {
  return Array.from(new Set(config.action_configs.map((item) => item[field]).filter(Boolean)))
}

function mergeConfiguredOptions(...lists) {
  const options = []
  const seen = new Set()
  for (const list of lists) {
    for (const item of list || []) {
      const option = typeof item === 'string' ? { value: item, label: item } : item
      if (!option?.value || seen.has(option.value)) continue
      seen.add(option.value)
      options.push({ value: option.value, label: option.label || option.value })
    }
  }
  return options
}

function findConfiguredOption(options, value) {
  return options.find((item) => item.value === value)
}

function edgePathForRender(edgeItem) {
  const from = flowNodesForView.value.find((node) => node.id === edgeItem.from)
  const to = flowNodesForView.value.find((node) => node.id === edgeItem.to)
  if (!from || !to) return ''
  const fromCenterX = from.x + from.w / 2
  const fromCenterY = from.y + from.h / 2
  const toCenterX = to.x + to.w / 2
  const toCenterY = to.y + to.h / 2

  if (to.y > from.y + from.h + 18) {
    const sx = fromCenterX
    const sy = from.y + from.h
    const tx = toCenterX
    const ty = to.y
    const dy = Math.max(54, Math.abs(ty - sy) * 0.48)
    return `M ${sx} ${sy} C ${sx} ${sy + dy}, ${tx} ${ty - dy}, ${tx} ${ty}`
  }

  if (from.y > to.y + to.h + 18) {
    const sx = fromCenterX
    const sy = from.y
    const tx = toCenterX
    const ty = to.y + to.h
    const dy = Math.max(54, Math.abs(sy - ty) * 0.48)
    return `M ${sx} ${sy} C ${sx} ${sy - dy}, ${tx} ${ty + dy}, ${tx} ${ty}`
  }

  if (toCenterX >= fromCenterX) {
    const sx = from.x + from.w
    const sy = fromCenterY
    const tx = to.x
    const ty = toCenterY
    const dx = Math.max(58, Math.abs(tx - sx) * 0.44)
    return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`
  }

  const sx = from.x
  const sy = fromCenterY
  const tx = to.x + to.w
  const ty = toCenterY
  const dx = Math.max(58, Math.abs(sx - tx) * 0.44)
  return `M ${sx} ${sy} C ${sx - dx} ${sy}, ${tx + dx} ${ty}, ${tx} ${ty}`
}

function nodeStyle(node) {
  return {
    left: `${node.x}px`,
    top: `${node.y}px`,
    width: `${node.w}px`,
    minHeight: `${node.h}px`,
  }
}

function calculateFlowBounds(nodes) {
  if (!nodes.length) {
    return { x: 0, y: 0, width: FLOW_STAGE_WIDTH, height: 300, rawMaxY: 300 }
  }
  const minX = Math.min(...nodes.map((node) => node.x))
  const minY = Math.min(...nodes.map((node) => node.y))
  const maxX = Math.max(...nodes.map((node) => node.x + node.w))
  const maxY = Math.max(...nodes.map((node) => node.y + node.h))
  const x = Math.max(0, minX - FLOW_STAGE_PADDING)
  const y = Math.max(0, minY - FLOW_STAGE_PADDING)
  const right = Math.min(FLOW_STAGE_WIDTH, maxX + FLOW_STAGE_PADDING)
  const bottom = maxY + FLOW_STAGE_PADDING
  return {
    x,
    y,
    width: Math.max(1, right - x),
    height: Math.max(1, bottom - y),
    rawMaxY: bottom,
  }
}

function fitFlowView() {
  if (!canvasRef.value || !canvasSize.width || !canvasSize.height) return
  const bounds = flowBounds.value
  const padding = canvasSize.width < 900 ? 32 : 44
  const availableWidth = Math.max(1, canvasSize.width - padding * 2)
  const availableHeight = Math.max(1, canvasSize.height - padding * 2)
  const rawScale = Math.min(availableWidth / bounds.width, availableHeight / bounds.height)
  const maxZoom = flowEditMode.value ? 1.08 : 1.12
  const minZoom = flowEditMode.value ? 0.34 : 0.32
  const nextScale = clampFloat(rawScale, minZoom, maxZoom)
  fitTransform.scale = nextScale
  fitTransform.x = Math.round((canvasSize.width - bounds.width * nextScale) / 2 - bounds.x * nextScale)
  fitTransform.y = Math.round((canvasSize.height - bounds.height * nextScale) / 2 - bounds.y * nextScale)
}

function updateCanvasSize() {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  canvasSize.width = Math.round(rect.width)
  canvasSize.height = Math.round(rect.height)
}

function setupCanvasObserver() {
  if (!canvasRef.value || canvasResizeObserver) return
  updateCanvasSize()
  if ('ResizeObserver' in window) {
    canvasResizeObserver = new ResizeObserver(() => {
      updateCanvasSize()
      nextTick(fitFlowView)
    })
    canvasResizeObserver.observe(canvasRef.value)
  } else {
    window.addEventListener('resize', updateCanvasSize)
  }
}

function teardownCanvasObserver() {
  if (canvasResizeObserver) {
    canvasResizeObserver.disconnect()
    canvasResizeObserver = null
  }
}

function clampNumber(value, min, max) {
  const next = Number(value)
  if (!Number.isFinite(next)) return min
  return Math.min(max, Math.max(min, Math.round(next)))
}

function clampFloat(value, min, max) {
  const next = Number(value)
  if (!Number.isFinite(next)) return min
  return Math.min(max, Math.max(min, next))
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadStaffGroups(), loadDroneLinkageOptions()])
  await nextTick()
  setupCanvasObserver()
  fitFlowView()
})

onBeforeUnmount(() => {
  teardownCanvasObserver()
  window.removeEventListener('resize', updateCanvasSize)
})
</script>

<style scoped>
.event-config-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}

.page-header,
.condition-editor {
  display: flex;
  align-items: center;
}

.page-header {
  justify-content: space-between;
  min-height: 74px;
  margin-bottom: 18px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}

.status-summary { display: flex; justify-content: flex-end; align-items: center; }
.metric { min-width: 96px; display: inline-flex; align-items: baseline; gap: 8px; padding: 8px 18px; white-space: nowrap; }
.metric + .metric { border-left: 1px solid rgba(96, 151, 191, .18); }
.metric .dot { width: 8px; height: 8px; flex: 0 0 auto; align-self: center; border-radius: 50%; background: #8db2c8; }
.metric .dot.total { box-shadow: 0 0 8px rgba(141, 178, 200, .75); }
.metric .dot.online { background: #48e6bf; box-shadow: 0 0 8px rgba(72, 230, 191, .75); }
.metric .dot.offline { background: #ff5b68; box-shadow: 0 0 8px rgba(255, 91, 104, .72); }
.metric-num { color: #f2fbff; font-size: 22px; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.metric-label { color: #8db2c8; font-size: 12px; }

.title-block {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.page-header p {
  margin: 0;
  color: #8aa9c3;
  font-size: 13px;
  line-height: 1.35;
}

.page-header h2 {
  margin: 0;
  color: #f3f8fd;
  font-size: 25px;
  line-height: 1.1;
  letter-spacing: 0;
}

.page-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}

.source-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 26px;
  padding: 0 12px;
  border: 1px solid rgba(143, 174, 198, .22);
  border-radius: 5px;
  color: #9fb7c8;
  background: rgba(143, 174, 198, .08);
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 1;
}

.source-pill.is-camera,
.source-pill.is-unknown {
  border-color: rgba(72, 216, 255, .22);
  color: #aee8ff;
  background: rgba(72, 216, 255, .08);
}

.source-pill.is-sensor {
  border-color: rgba(98, 215, 177, .24);
  color: #b8f3dc;
  background: rgba(98, 215, 177, .08);
}

.event-config-page :deep(.el-tag) {
  min-width: 66px;
  justify-content: center;
  border-radius: 5px;
  font-weight: 800;
}

.condition-editor :deep(.el-input) {
  width: 210px;
}

.condition-editor :deep(.el-input__wrapper) {
  min-height: 36px;
}

.condition-editor :deep(.el-input-group__append) {
  width: 52px;
  justify-content: center;
  padding: 0;
  color: #9db8ca;
  background: rgba(17, 39, 58, .95);
  box-shadow: 0 0 0 1px rgba(112, 157, 190, .16) inset;
}

.condition-editor {
  gap: 10px;
  justify-content: center;
  min-width: 0;
}

.condition-editor b {
  color: #2fd6c4;
  font-size: 18px;
}

.flow-canvas {
  flex: 1;
  position: relative;
  min-height: 530px;
  overflow: hidden;
  border: 1px solid rgba(112, 157, 190, .18);
  border-radius: 8px;
  background:
    radial-gradient(circle, rgba(126, 173, 205, .07) 1px, transparent 1px) 0 0 / 20px 20px,
    linear-gradient(180deg, rgba(8, 27, 44, .94), rgba(5, 18, 31, .98));
}

.flow-canvas.editing {
  border-color: rgba(47, 214, 196, .34);
}

.flow-stage {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}

.flow-edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.flow-canvas.editing .flow-edges {
  pointer-events: auto;
}

.flow-edge {
  fill: none;
  stroke: rgba(104, 151, 177, .44);
  stroke-width: 2;
  marker-end: url(#event-flow-arrow);
  cursor: pointer;
}

.flow-edge.active {
  stroke: rgba(73, 206, 194, .78);
  stroke-dasharray: 8 10;
  animation: flow-dash 4.6s linear infinite;
}

.flow-edge.selected {
  stroke: #f0bd58;
  stroke-width: 3;
}

.flow-edges marker path {
  fill: rgba(73, 206, 194, .86);
}

.canvas-node {
  position: absolute;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(112, 157, 190, .24);
  border-radius: 8px;
  background: rgba(10, 29, 47, .96);
  box-shadow: 0 14px 28px rgba(0, 0, 0, .18);
}

.canvas-node::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(104, 190, 214, .08), transparent 46%);
  pointer-events: none;
}

.canvas-node.editable {
  cursor: grab;
}

.canvas-node.editable:active {
  cursor: grabbing;
}

.canvas-node .node-main-icon {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #bff6ef;
  background: rgba(47, 214, 196, .12);
  font-size: 23px;
}

.canvas-node.source {
  border-color: rgba(78, 164, 210, .34);
}

.canvas-node.source .node-main-icon {
  color: #bfe6ff;
  background: rgba(78, 164, 210, .14);
}

.canvas-node.rule-node {
  border-color: rgba(240, 189, 88, .28);
}

.canvas-node.rule-node .node-main-icon,
.canvas-node.route-node .node-main-icon {
  color: #ffe0a0;
  background: rgba(240, 189, 88, .13);
}

.canvas-node.event-node {
  grid-template-columns: 48px minmax(0, 1fr);
  border-color: rgba(47, 214, 196, .48);
  background: rgba(13, 45, 62, .98);
  box-shadow: 0 0 0 1px rgba(47, 214, 196, .12), 0 18px 36px rgba(0, 0, 0, .24);
}

.canvas-node.event-node .node-main-icon {
  width: 48px;
  height: 48px;
  font-size: 26px;
}

.canvas-node.action {
  grid-template-columns: 42px minmax(0, 1fr);
  padding-right: 48px;
  border-color: rgba(102, 186, 170, .32);
  background: rgba(10, 38, 51, .97);
}

.canvas-node.action.selected,
.canvas-node.action:hover {
  border-color: rgba(87, 215, 196, .52);
  background: rgba(12, 45, 58, .98);
}

.canvas-node.close-node,
.canvas-node.archive-node {
  opacity: .94;
}

.canvas-node.selected {
  border-color: #f0bd58;
  box-shadow: 0 0 0 1px rgba(240, 189, 88, .3), 0 16px 32px rgba(0, 0, 0, .2);
}

.canvas-node.disabled {
  opacity: .58;
}

.node-copy {
  min-width: 0;
}

.node-copy strong {
  display: block;
  overflow: hidden;
  color: #f2f8ff;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.22;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-copy span,
.node-copy em {
  display: block;
  overflow: hidden;
  margin-top: 6px;
  color: #9bb6c8;
  font-size: 12px;
  font-style: normal;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-copy em {
  color: #74d8cf;
}

.node-tools {
  position: absolute;
  right: 12px;
  top: 50%;
  z-index: 4;
  display: flex;
  flex-direction: column;
  gap: 7px;
  transform: translateY(-50%);
}

.node-config,
.node-delete {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(116, 216, 207, .24);
  border-radius: 6px;
  background: rgba(6, 20, 34, .72);
  color: #74d8cf;
  cursor: pointer;
}

.node-config .el-icon,
.node-delete .el-icon {
  width: auto;
  height: auto;
  border-radius: 0;
  background: transparent;
  font-size: 16px;
}

.node-config:hover {
  border-color: rgba(116, 216, 207, .52);
  color: #d7fffb;
  background: rgba(19, 86, 82, .68);
}

.node-delete {
  border: 1px solid rgba(255, 127, 143, .26);
  background: rgba(80, 26, 38, .58);
  color: #ffabb5;
}

.node-delete:hover {
  border-color: rgba(255, 127, 143, .52);
  color: #ffd7dd;
  background: rgba(112, 34, 50, .76);
}

.node-handle {
  position: absolute;
  z-index: 3;
  width: 13px;
  height: 13px;
  border: 2px solid #2fd6c4;
  border-radius: 50%;
  background: #092238;
  opacity: 0;
  cursor: crosshair;
}

.flow-canvas.editing .canvas-node:hover .node-handle,
.flow-canvas.editing .canvas-node.selected .node-handle,
.node-handle.active,
.node-handle.ready {
  opacity: 1;
}

.node-handle.source {
  right: -7px;
  top: calc(50% - 7px);
}

.node-handle.target {
  left: -7px;
  top: calc(50% - 7px);
}

.node-handle.active {
  background: #2fd6c4;
}

.node-handle.ready {
  border-color: #f0bd58;
}

.add-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.add-action-grid button {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid rgba(112, 157, 190, .2);
  border-radius: 8px;
  background: #0b1d30;
  color: #d9e8f8;
  cursor: pointer;
}

.add-action-grid button:hover {
  border-color: rgba(47, 214, 196, .44);
}

@keyframes flow-dash {
  to {
    stroke-dashoffset: -36;
  }
}

.event-list-panel {
  min-height: calc(100vh - 214px);
  margin-top: 18px;
  padding: 0;
  border: 1px solid rgba(104, 161, 200, .18);
  border-radius: 8px;
  background: #0b1d30;
  overflow: hidden;
}

.filter-bar {
  min-height: 72px;
  display: grid;
  grid-template-columns: 180px 180px 180px minmax(260px, 1fr);
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid rgba(104, 161, 200, .22);
  border-radius: 8px;
  background: #0b1d30;
}

.filter-bar.with-visual-category {
  grid-template-columns: 180px 180px 180px 180px minmax(260px, 1fr);
}

.filter-bar .event-search :deep(.el-input__wrapper),
.filter-bar .event-filter-select :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 6px;
  background: rgba(6, 25, 42, .82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, .46) !important;
}

.filter-bar .event-search :deep(.el-input__wrapper:hover),
.filter-bar .event-filter-select :deep(.el-select__wrapper:hover),
.filter-bar .event-search :deep(.el-input__wrapper.is-focused),
.filter-bar .event-filter-select :deep(.el-select__wrapper.is-focused),
.filter-bar .event-filter-select :deep(.el-select__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px rgba(87, 190, 255, .82), 0 0 0 2px rgba(72, 216, 255, .08) !important;
}

.filter-bar :deep(.el-input__inner),
.filter-bar :deep(.el-select__selected-item),
.filter-bar :deep(.el-select__placeholder) {
  color: #d9e8f8;
}

.filter-bar :deep(.el-input__inner::placeholder) {
  color: #7898ad;
}

.config-table {
  overflow-x: auto;
  background: #0a1d30;
}

.config-table-head,
.config-row {
  min-width: 1375px;
  display: grid;
  grid-template-columns: minmax(160px, max-content) 108px 108px minmax(320px, 420px) 104px 104px 88px 224px;
  align-items: center;
  gap: 14px;
  justify-content: space-between;
  text-align: center;
}

.config-table-head {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  background: #15314d;
  font-size: 14px;
  font-weight: 800;
}

.config-row {
  min-height: 72px;
  padding: 12px 20px;
  color: #d8e7ff;
  border-top: 1px solid rgba(104, 161, 200, .1);
  background: #092034;
  transition: background .16s ease, box-shadow .16s ease;
}

.config-row:hover {
  background: #102940;
}

.config-row.editing {
  min-height: 72px;
  background: #102940;
  box-shadow: inset 3px 0 0 #48d8ff;
}

.config-table-head > span,
.config-row > div {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-with-help {
  gap: 5px;
}

.header-with-help .el-icon {
  color: #83a9c4;
  font-size: 14px;
}

.event-name-cell strong {
  display: block;
  max-width: 100%;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 14px;
  font-weight: 750;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-cell {
  min-width: 0;
  text-align: center;
}

.rule-cell > span {
  display: block;
  overflow: hidden;
  color: #9cb6ca;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.visual-inline-editor {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  height: 36px;
}

.visual-inline-editor > span {
  overflow: hidden;
  color: #9cb6ca;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.duration-cell {
  color: #9cb6ca;
  font-size: 14px;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
}

.duration-cell :deep(.el-input) {
  width: 90px;
}

.condition-editor :deep(.el-input__wrapper),
.duration-cell :deep(.el-input__wrapper),
.visual-inline-editor :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 5px;
  background: rgba(6, 25, 42, .86);
  box-shadow: inset 0 0 0 1px rgba(83, 153, 197, .36) !important;
}

.condition-editor :deep(.el-input-group__append),
.duration-cell :deep(.el-input-group__append) {
  width: 34px;
  justify-content: center;
  padding: 0;
  border-radius: 0 5px 5px 0;
  color: #9ec4dd;
  background: rgba(14, 44, 68, .92);
  box-shadow: inset 0 0 0 1px rgba(83, 153, 197, .28);
}

.condition-editor :deep(.el-input__inner),
.duration-cell :deep(.el-input__inner) {
  color: #eaf6ff;
  font-weight: 700;
  text-align: center;
}

.status-cell :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, .34);
  background: rgba(96, 118, 134, .38);
}

.status-cell :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, .66);
  background: #409eff;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}

.row-actions :deep(.el-button) {
  min-width: 86px;
  height: 32px;
  margin: 0;
  padding: 0 10px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}

.row-actions :deep(.edit-rule-action),
.zone-entry-action {
  border-color: rgba(66, 164, 224, .42) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .54) !important;
}

.row-actions :deep(.view-flow-action) {
  border-color: rgba(92, 215, 154, .34) !important;
  color: #c5f5dd !important;
  background: rgba(38, 110, 86, .42) !important;
}

.row-actions :deep(.cancel-rule-action) {
  border-color: rgba(145, 171, 190, .28) !important;
  color: #c6d7e5 !important;
  background: rgba(82, 102, 119, .28) !important;
}

.row-actions :deep(.save-rule-action) {
  border-color: rgba(64, 158, 255, .50) !important;
  color: #f0f8ff !important;
  background: rgba(64, 158, 255, .78) !important;
}

.row-actions :deep(.edit-rule-action:hover),
.zone-entry-action:hover {
  border-color: rgba(66, 164, 224, .66) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .72) !important;
}

.row-actions :deep(.cancel-rule-action:hover) {
  border-color: rgba(145, 171, 190, .46) !important;
  color: #eef7ff !important;
  background: rgba(96, 118, 136, .42) !important;
}

.row-actions :deep(.save-rule-action:hover) {
  border-color: rgba(96, 184, 255, .74) !important;
  background: rgba(55, 142, 226, .9) !important;
}

.row-actions :deep(.view-flow-action:hover) {
  border-color: rgba(92, 215, 154, .58) !important;
  color: #edfff6 !important;
  background: rgba(44, 128, 99, .56) !important;
}

.empty-list {
  display: grid;
  min-height: 180px;
  place-items: center;
  color: #789bb4;
  font-size: 13px;
}

.list-pagination {
  min-height: 58px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, .10);
  background: #092034;
}

.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 44px;
  height: 38px;
  margin: 0 4px;
  border: 1px solid rgba(70, 145, 190, .34);
  border-radius: 5px;
  color: #8fb6d1;
  background: #0b2238;
  font-weight: 700;
}

.list-pagination :deep(.el-pager li.is-active) {
  border-color: #4ba7e6;
  color: #fff;
  background: #3f95d7;
}

.list-pagination :deep(.btn-prev:disabled),
.list-pagination :deep(.btn-next:disabled) {
  color: rgba(143, 182, 209, .35);
  background: #0b2238;
}

:global(.flow-workspace-dialog) {
  height: min(820px, 88vh);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(112, 157, 190, .2);
  border-radius: 10px;
  background: #071422;
}

:global(.flow-workspace-dialog .app-dialog__header) {
  flex: none;
  padding: 14px 16px;
  margin: 0;
  border-bottom: 1px solid rgba(112, 157, 190, .16);
}

:global(.flow-workspace-dialog .app-dialog__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
}

.flow-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.flow-dialog-header h3 {
  margin: 0;
  color: #f3f8fd;
  font-size: 18px;
  letter-spacing: 0;
}

.flow-dialog-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.flow-dialog-actions :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-radius: 5px;
  font-weight: 800;
}

.flow-dialog-actions :deep(.flow-edit-entry) {
  border-color: rgba(47, 214, 196, .46) !important;
  color: #e5fffb !important;
  background: rgba(28, 112, 102, .52) !important;
}

.flow-dialog-actions :deep(.flow-save-action) {
  border-color: rgba(111, 232, 255, .92) !important;
  color: #041522 !important;
  background: linear-gradient(135deg, #5ce5ff 0%, #2bc9c0 100%) !important;
  box-shadow: 0 0 0 1px rgba(111, 232, 255, .22), 0 8px 20px rgba(31, 196, 205, .20);
}

.flow-dialog-actions :deep(.flow-save-action:hover) {
  border-color: #b8f5ff !important;
  background: linear-gradient(135deg, #8ceeff 0%, #55e0ce 100%) !important;
}

.flow-workspace-body {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0;
}

.flow-workspace-body.with-inspector {
  grid-template-columns: minmax(0, 1fr) 380px;
}

.flow-workspace-body .flow-canvas {
  min-height: 0;
  height: 100%;
  border: 0;
  border-radius: 0;
}

.action-inspector {
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
  border-left: 1px solid rgba(112, 157, 190, .16);
  background: linear-gradient(180deg, #0b2136 0%, #071a2c 100%);
}

.action-inspector-header {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 22px 22px 18px;
  border-bottom: 1px solid rgba(112, 157, 190, .14);
  background: rgba(18, 48, 76, .48);
}

.inspector-title {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.inspector-title span {
  color: #88a9bf;
  font-size: 12px;
  font-weight: 800;
}

.inspector-title strong {
  overflow: hidden;
  color: #f3f8fd;
  font-size: 22px;
  line-height: 1.12;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inspector-title small {
  overflow: hidden;
  color: #91b3c8;
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-inspector-header button {
  flex: none;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(123, 160, 184, .18);
  border-radius: 6px;
  background: rgba(7, 23, 38, .78);
  color: #9fc1d6;
  cursor: pointer;
  font-size: 18px;
}

.action-inspector-header button:hover {
  border-color: rgba(104, 190, 214, .38);
  color: #e7f8ff;
}

.action-readonly {
  flex: 1;
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 0;
  padding: 22px;
  overflow: auto;
}

.readonly-caption {
  margin-bottom: 14px;
  color: #789bb4;
  font-size: 13px;
  font-weight: 700;
}

.readonly-field {
  display: grid;
  gap: 7px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(112, 157, 190, .14);
}

.readonly-field span {
  color: #789bb4;
  font-size: 12px;
}

.readonly-field strong {
  overflow: hidden;
  color: #eaf6ff;
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readonly-summary {
  margin-top: 18px;
  padding: 12px 14px;
  border: 1px solid rgba(83, 153, 197, .18);
  border-radius: 7px;
  color: #8fb5ca;
  background: rgba(7, 25, 42, .72);
  font-size: 13px;
  line-height: 1.5;
}

.inspector-form :deep(.el-select),
.inspector-form :deep(.el-input) {
  width: 100%;
}

/* 自定义弹窗层级高于 Element 默认浮层，下拉菜单必须显式浮在弹窗之上。 */
:global(.flow-inspector-popper) {
  z-index: 3501 !important;
}

.inspector-form {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 18px 22px 0;
  overflow: auto;
}

.inspector-section {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid rgba(83, 153, 197, .18);
  border-radius: 8px;
  background: rgba(7, 25, 42, .72);
}

.section-heading {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.section-heading strong {
  color: #eaf6ff;
  font-size: 15px;
}

.section-heading span {
  color: #789bb4;
  font-size: 12px;
  line-height: 1.35;
}

.inspector-form :deep(.el-form-item) {
  margin-bottom: 15px;
}

.inspector-form :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.inspector-form :deep(.el-form-item__label) {
  margin-bottom: 7px;
  color: #91b3c8;
  font-weight: 700;
}

.inspector-form :deep(.el-select__wrapper),
.inspector-form :deep(.el-input__wrapper) {
  min-height: 42px;
  border-radius: 6px;
  background: rgba(6, 25, 42, .82);
  box-shadow: inset 0 0 0 1px rgba(60, 150, 214, .40) !important;
}

.inspector-form :deep(.el-select__wrapper:hover),
.inspector-form :deep(.el-input__wrapper:hover),
.inspector-form :deep(.el-select__wrapper.is-focused),
.inspector-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px rgba(87, 190, 255, .78), 0 0 0 2px rgba(72, 216, 255, .08) !important;
}

.inspector-form :deep(.el-input__inner),
.inspector-form :deep(.el-select__selected-item),
.inspector-form :deep(.el-select__placeholder) {
  color: #d9e8f8;
  font-size: 14px;
}

.repeat-mode-control {
  width: 100%;
  margin-bottom: 14px;
}

.repeat-mode-control :deep(.el-radio-button) {
  flex: 1;
}

.repeat-mode-control :deep(.el-radio-button__inner) {
  width: 100%;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-color: rgba(83, 153, 197, .34) !important;
  background: rgba(8, 28, 46, .88) !important;
  font-weight: 800;
}

.repeat-mode-control :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  color: #062236 !important;
  background: #31d8f4 !important;
  border-color: #31d8f4 !important;
}

.repeat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.repeat-grid :deep(.el-input-group__append) {
  min-width: 42px;
  justify-content: center;
  padding: 0 8px;
  color: #9ec4dd;
  background: rgba(14, 44, 68, .92);
  box-shadow: inset 0 0 0 1px rgba(83, 153, 197, .28);
}

.repeat-grid :deep(.el-input__inner) {
  text-align: center;
  font-weight: 800;
}

.inspector-actions {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: auto -22px 0;
  padding: 16px 22px 18px;
  border-top: 1px solid rgba(112, 157, 190, .14);
  background: rgba(7, 20, 34, .96);
}

.inspector-actions :deep(.el-button) {
  min-width: 88px;
  height: 36px;
  margin: 0;
  border-radius: 5px;
  font-weight: 800;
}

.inspector-actions :deep(.apply-action) {
  border-color: rgba(64, 158, 255, .56) !important;
  color: #f0f8ff !important;
  background: rgba(64, 158, 255, .82) !important;
}

@media (max-width: 1280px) {
  .config-table-head,
  .config-row {
    min-width: 1260px;
    grid-template-columns: minmax(140px, max-content) 92px 96px minmax(280px, 360px) 88px 88px 74px 190px;
    gap: 8px;
  }
}

@media (max-width: 960px) {
  .filter-bar,
  .filter-bar.with-visual-category {
    height: auto;
    grid-template-columns: 1fr 1fr;
  }

  .config-table {
    overflow-x: auto;
  }

  .config-table-head,
  .config-row {
    min-width: 1260px;
  }

  .flow-workspace-body.with-inspector {
    grid-template-columns: 1fr;
  }

  .action-inspector {
    border-left: 0;
    border-top: 1px solid rgba(112, 157, 190, .16);
  }
}
</style>
