<template>
  <div class="annotation-workbench">
    <header class="task-bar">
      <div class="task-identity">
        <span>AI DATA REVIEW</span>
        <div><h2>误报数据处理</h2><em v-if="dirty" class="dirty-dot">● 有未保存修改</em><em v-else-if="lastSavedAt" class="saved-state">✓ 已保存 {{ lastSavedAt }}</em></div>
      </div>
      <div class="task-context">
        <label><span>当前模型</span><strong>{{ currentModelName }}</strong></label>
        <label><span>任务类型</span><strong class="mode-value">● {{ taskModeLabel }}</strong></label>
        <label><span>当前数据集</span><strong>{{ datasetName }}</strong></label>
      </div>
      <div class="task-progress">
        <div><span>处理进度</span><strong>{{ completedCount }} / {{ samples.length }}</strong><em>{{ progressPercent }}%</em></div>
        <p><i :style="{ width: `${progressPercent}%` }"></i></p><small>待处理 {{ pendingCount }} 张</small>
      </div>
      <div class="task-actions">
        <el-select v-model="quickFilter" size="small"><el-option label="全部图片" value="all" /><el-option label="只看未处理" value="pending" /><el-option label="只看已完成" value="completed" /></el-select>
        <el-button size="small" :loading="loading" @click="loadSamples">刷新</el-button>
        <el-button size="small" plain @click="exitTask">退出任务</el-button>
      </div>
    </header>

    <section class="workbench-body">
      <aside class="sample-queue">
        <div class="panel-heading"><div><strong>图片队列</strong><span>{{ filteredSamples.length }} / {{ samples.length }} 张</span></div><button type="button" @click="loadSamples">↻</button></div>
        <label class="search-box"><span>⌕</span><input v-model.trim="searchKeyword" placeholder="搜索文件名或事件编号" /></label>
        <div class="queue-tabs">
          <button v-for="filter in queueFilters" :key="filter.value" type="button" :class="{ active: quickFilter === filter.value }" @click="quickFilter = filter.value">{{ filter.label }}<span>{{ filter.count }}</span></button>
        </div>
        <div v-if="loading && !samples.length" class="queue-skeleton"><div v-for="n in 5" :key="n"><i></i><span></span></div></div>
        <div v-else-if="loadError && !samples.length" class="simple-state"><b>!</b><strong>队列加载失败</strong><small>{{ loadError }}</small><button @click="loadSamples">重新加载</button></div>
        <div v-else-if="filteredSamples.length" class="queue-list">
          <button v-for="(sample, index) in filteredSamples" :key="sample.source_path" type="button" class="queue-item" :class="{ active: selectedSample?.source_path === sample.source_path }" @click="requestSelectSample(sample)">
            <span class="queue-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="thumb"><img :src="falseAlarmSampleImageUrl(sample.source_path)" :alt="sample.filename" loading="lazy" /></span>
            <span class="queue-copy"><strong :title="sample.filename">{{ sample.filename }}</strong><small>原预测：{{ samplePrediction(sample).label }} {{ formatConfidence(samplePrediction(sample).confidence) }}</small><em :class="`status-${sampleStatus(sample).value}`"><i></i>{{ sampleStatus(sample).label }}</em></span>
          </button>
        </div>
        <div v-else class="simple-state"><b>▧</b><strong>暂无匹配图片</strong><small>请调整搜索词或筛选条件</small></div>
      </aside>

      <main class="image-workspace">
        <div class="canvas-header">
          <div><strong>{{ selectedSample?.filename || '未选择图片' }}</strong><span v-if="selectedSample">{{ selectedSample.event_no }} · {{ imageSizeLabel }}</span></div>
          <p><span v-if="isNegative" class="negative-text">✓ 无目标负样本</span><span v-else>{{ taskMode === 'detection' ? `${boxes.length} 个人工标注框` : (classificationLabel || '待选择分类') }}</span><em>{{ Math.round(zoom * 100) }}%</em></p>
        </div>
        <div ref="viewportRef" class="canvas-viewport" :class="`tool-${activeTool}`" @wheel.ctrl.prevent="handleWheelZoom">
          <div v-if="selectedSample && taskMode === 'detection'" class="floating-tools">
            <button title="选择工具 (V)" :class="{ active: activeTool === 'select' }" @click="activeTool = 'select'">↖<span>选择</span></button>
            <button title="矩形框 (R)" :class="{ active: activeTool === 'draw' }" @click="activeTool = 'draw'">▣<span>框选</span></button><i></i>
            <button title="放大" @click="changeZoom(.2)">＋<span>放大</span></button><button title="缩小" @click="changeZoom(-.2)">−<span>缩小</span></button>
            <button title="适应窗口 (Space)" @click="fitImage">⊙<span>适应</span></button><button title="原始比例" @click="originalImageScale">1:1<span>原图</span></button><i></i>
            <button title="删除选中框 (Delete)" class="danger" :disabled="selectedBoxIndex < 0" @click="deleteSelectedBox">⌫<span>删除</span></button>
          </div>
          <div v-if="imageStatus === 'loading'" class="image-state loading-state"><i></i><span>图片加载中…</span></div>
          <div v-else-if="imageStatus === 'error'" class="image-state"><b>!</b><strong>图片加载失败</strong><small>请检查图片服务或重新加载</small><button @click="retryImage">重新加载</button></div>
          <div v-else-if="!selectedSample" class="image-state"><b>▧</b><strong>选择一张误报图片开始处理</strong><small>选择后可立即重新框选或分类</small></div>
          <div v-show="selectedSample && imageStatus === 'ready'" ref="stageRef" class="image-stage" :style="stageStyle" @pointerdown="startStagePointer" @pointermove="moveStagePointer" @pointerup="finishStagePointer" @pointercancel="cancelStagePointer">
            <img :key="`${selectedSample?.source_path || ''}-${imageRetryKey}`" :src="selectedSample ? falseAlarmSampleImageUrl(selectedSample.source_path) : ''" :alt="selectedSample?.filename || ''" draggable="false" @load="handleImageLoad" @error="handleImageError" />
            <template v-if="showOriginalBoxes && taskMode === 'detection'"><div v-for="(box, index) in originalBoxes" :key="`original-${index}`" class="original-box" :style="boxStyle(box)"><span>原预测 · {{ box.label }}</span></div></template>
            <div v-for="(box, index) in boxes" :key="`box-${index}`" class="annotation-box" :class="{ selected: selectedBoxIndex === index }" :style="boxStyle(box)" @pointerdown.stop="beginMoveBox($event, index)" @click.stop="selectedBoxIndex = index">
              <span class="box-label">{{ box.label }} #{{ index + 1 }}</span>
              <template v-if="selectedBoxIndex === index && activeTool === 'select'"><i v-for="handle in resizeHandles" :key="handle" class="resize-handle" :class="`handle-${handle}`" @pointerdown.stop="beginResizeBox($event, index, handle)"></i></template>
            </div>
            <div v-if="drawingBox" class="annotation-box draft" :style="boxStyle(drawingBox)"></div>
            <div v-if="taskMode === 'classification' && classificationLabel" class="center-overlay"><span>人工分类</span><strong>✓ {{ classificationLabel }}</strong></div>
            <div v-if="isNegative" class="center-overlay negative-overlay"><span>NEGATIVE SAMPLE</span><strong>此图片中无有效目标</strong></div>
          </div>
          <div v-if="selectedSample && imageStatus === 'ready' && taskMode === 'detection' && !boxes.length && !isNegative" class="first-hint"><kbd>R</kbd> 拖动鼠标创建第一个目标框</div>
        </div>
      </main>

      <aside class="inspector-panel">
        <section class="inspector-section">
          <div class="section-title"><strong>当前任务</strong><span>{{ taskModeLabel }}</span></div>
          <div class="prediction-flow"><div><span>模型原始判断</span><strong>{{ currentPrediction.label }}</strong><small>置信度 {{ formatConfidence(currentPrediction.confidence) }}</small></div><i>→</i><div><span>人工纠正</span><strong>{{ correctionResult }}</strong><small>{{ dirty ? '尚未保存' : (selectedSample?.annotated ? '已完成' : '等待处理') }}</small></div></div>
          <label v-if="taskMode === 'detection'" class="original-switch"><span>显示原始检测框<small>{{ originalBoxes.length ? `${originalBoxes.length} 个` : '原框未归档' }}</small></span><el-switch v-model="showOriginalBoxes" size="small" :disabled="!originalBoxes.length" /></label>
        </section>
        <section class="inspector-section">
          <div class="section-title"><strong>{{ taskMode === 'detection' ? '可用标签' : '请选择正确分类' }}</strong><span>{{ labels.length }} 类</span></div>
          <label class="search-box label-search"><span>⌕</span><input v-model.trim="labelKeyword" placeholder="搜索标签" /></label>
          <div class="label-list" :class="{ classification: taskMode === 'classification' }">
            <button v-for="label in filteredLabels" :key="label.name" :class="{ active: taskMode === 'detection' ? activeLabel === label.name : classificationLabel === label.name }" :style="{ '--label-color': label.color }" @click="selectLabel(label.name)"><i></i><span>{{ label.name }}</span><em v-if="taskMode === 'detection'">{{ labelCount(label.name) }}</em><em v-else-if="classificationLabel === label.name">✓</em></button>
          </div>
          <p v-if="taskMode === 'detection'" class="active-label">当前标签：<strong>{{ activeLabel }}</strong>，新框自动使用该标签</p>
        </section>
        <section v-if="taskMode === 'detection'" class="inspector-section result-section">
          <div class="section-title"><strong>标注结果</strong><span>{{ boxes.length }} 个实例</span></div>
          <div v-if="boxes.length" class="result-list"><article v-for="(box, index) in boxes" :key="index" :class="{ active: selectedBoxIndex === index }" @click="focusBox(index)"><i :style="{ background: labelColor(box.label) }"></i><div><strong>{{ box.label }} #{{ index + 1 }}</strong><small>{{ boxPixelSummary(box) }}</small></div><select :value="box.label" @click.stop @change="changeBoxLabel(index, $event.target.value)"><option v-for="label in labels" :key="label.name" :value="label.name">{{ label.name }}</option></select><button title="删除" @click.stop="removeBox(index)">×</button></article></div>
          <p v-else class="result-empty">尚未创建人工标注框。若图片中没有有效目标，请标记为负样本。</p>
        </section>
        <section class="negative-action" :class="{ active: isNegative }"><button :disabled="!selectedSample" @click="toggleNegative"><span>{{ isNegative ? '✓' : '○' }}</span><div><strong>{{ isNegative ? '已标记为无目标' : '图片中无有效目标' }}</strong><small>作为 Negative Sample 加入训练数据集</small></div></button></section>
      </aside>
    </section>

    <footer class="operation-bar">
      <div class="navigation-actions"><button :disabled="!hasPrevious" @click="goPrevious">← 上一张 <kbd>A</kbd></button><span>{{ currentQueuePosition }} / {{ filteredSamples.length || 0 }}</span><button :disabled="!hasNext" @click="goNext">下一张 → <kbd>D</kbd></button></div>
      <div class="shortcut-guide"><span v-if="taskMode === 'detection'"><kbd>R</kbd> 框选</span><span><kbd>Del</kbd> 删除</span><span><kbd>Ctrl Z</kbd> 撤销</span><span><kbd>Ctrl Y</kbd> 重做</span><span><kbd>Space</kbd> 适应</span></div>
      <div class="save-actions"><button class="text-action" :disabled="!selectedSample" @click="skipCurrent">跳过</button><button class="secondary-action" :disabled="!canSave || saving" @click="saveCurrent(false)">{{ saving ? '保存中…' : '保存' }}</button><button class="primary-action" :disabled="!canSave || saving" @click="saveAndNext">保存并下一张 <kbd>Enter</kbd></button><button v-if="samples.length && completedCount === samples.length" class="complete-action" @click="completeDialogVisible = true">完成本次任务</button></div>
    </footer>

    <el-dialog v-model="completeDialogVisible" width="520px" title="完成本次标注任务" append-to-body>
      <div class="dataset-summary"><span class="dataset-check">✓</span><h3>{{ samples.length }} / {{ samples.length }} 张图片已处理</h3><p>确认后将生成新的训练数据集，本页面不会直接启动模型训练。</p><div class="dataset-stats"><div><strong>{{ detectionSavedCount }}</strong><span>目标检测标注</span></div><div><strong>{{ negativeSavedCount }}</strong><span>负样本</span></div><div><strong>{{ classificationSavedCount }}</strong><span>分类修正</span></div></div><label><span>训练数据集</span><strong>{{ datasetName }}</strong></label></div>
      <template #footer><el-button @click="completeDialogVisible = false">取消</el-button><el-button type="primary" @click="generateDataset">生成数据集</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { falseAlarmSampleImageUrl, getFalseAlarmSamples, saveFalseAlarmSampleAnnotation } from '@/api/integration'

const router = useRouter()
const labels = [
  { name: '人员', color: '#21d7ff' }, { name: '船只', color: '#4d8dff' },
  { name: '车辆', color: '#ffad43' }, { name: '漂浮物', color: '#a679ff' },
  { name: '施工机械', color: '#42d39b' }, { name: '其他', color: '#a6b9c9' },
]
const resizeHandles = ['nw', 'ne', 'sw', 'se']
const samples = ref([]), selectedSample = ref(null), boxes = ref([])
const loading = ref(false), saving = ref(false), loadError = ref('')
const searchKeyword = ref(''), labelKeyword = ref(''), quickFilter = ref('all')
const activeLabel = ref('人员'), classificationLabel = ref(''), isNegative = ref(false)
const dirty = ref(false), lastSavedAt = ref(''), activeTool = ref('draw')
const selectedBoxIndex = ref(-1), showOriginalBoxes = ref(false)
const imageStatus = ref('idle'), imageRetryKey = ref(0), zoom = ref(1)
const stageRef = ref(null), viewportRef = ref(null)
const imageNatural = reactive({ width: 0, height: 0 }), stageBase = reactive({ width: 0, height: 0 })
const completeDialogVisible = ref(false), undoStack = ref([]), redoStack = ref([])
const drawing = reactive({ active: false, startX: 0, startY: 0, x: 0, y: 0, pointerId: null })
const interaction = reactive({ active: false, type: '', index: -1, handle: '', startX: 0, startY: 0, original: null, before: null })

const taskMode = computed(() => inferTaskMode(selectedSample.value))
const taskModeLabel = computed(() => taskMode.value === 'classification' ? '图片分类' : '目标检测')
const currentPrediction = computed(() => samplePrediction(selectedSample.value))
const currentModelName = computed(() => selectedSample.value?.model_name || `${currentPrediction.value.label}识别模型`)
const datasetName = computed(() => selectedSample.value?.dataset_name || `${currentModelName.value} · 误报增强集_${new Date().toISOString().slice(0, 7).replace('-', '')}`)
const completedCount = computed(() => samples.value.filter(isSampleCompleted).length)
const pendingCount = computed(() => Math.max(0, samples.value.length - completedCount.value))
const progressPercent = computed(() => samples.value.length ? Math.round(completedCount.value / samples.value.length * 100) : 0)
const pendingFilterCount = computed(() => samples.value.filter(s => !isSampleCompleted(s) && s.uiStatus !== 'skipped').length)
const skippedFilterCount = computed(() => samples.value.filter(s => s.uiStatus === 'skipped').length)
const queueFilters = computed(() => [
  { label: '全部', value: 'all', count: samples.value.length },
  { label: '未处理', value: 'pending', count: pendingFilterCount.value },
  { label: '已完成', value: 'completed', count: completedCount.value },
  { label: '已跳过', value: 'skipped', count: skippedFilterCount.value },
])
const filteredSamples = computed(() => {
  const keyword = searchKeyword.value.toLowerCase()
  return samples.value.filter(sample => {
    if (keyword && !`${sample.filename} ${sample.event_no}`.toLowerCase().includes(keyword)) return false
    if (quickFilter.value === 'pending') return !isSampleCompleted(sample) && sample.uiStatus !== 'skipped'
    if (quickFilter.value === 'completed') return isSampleCompleted(sample)
    if (quickFilter.value === 'skipped') return sample.uiStatus === 'skipped'
    return true
  })
})
const currentQueueIndex = computed(() => filteredSamples.value.findIndex(s => s.source_path === selectedSample.value?.source_path))
const currentQueuePosition = computed(() => currentQueueIndex.value < 0 ? 0 : currentQueueIndex.value + 1)
const hasPrevious = computed(() => currentQueueIndex.value > 0)
const hasNext = computed(() => currentQueueIndex.value >= 0 && currentQueueIndex.value < filteredSamples.value.length - 1)
const filteredLabels = computed(() => labels.filter(label => label.name.includes(labelKeyword.value)))
const originalBoxes = computed(() => (selectedSample.value?.original_boxes || selectedSample.value?.original_annotations || []).map(box => normalizeBox({
  label: box.label || box.categoryName || currentPrediction.value.label,
  x: Number(box.x || 0), y: Number(box.y || 0), width: Number(box.width || 0), height: Number(box.height || 0),
})).filter(box => box.width && box.height))
const drawingBox = computed(() => drawing.active ? normalizeBox({ label: activeLabel.value, x: drawing.startX, y: drawing.startY, width: drawing.x - drawing.startX, height: drawing.y - drawing.startY }) : null)
const stageStyle = computed(() => ({ width: `${Math.max(1, stageBase.width * zoom.value)}px`, height: `${Math.max(1, stageBase.height * zoom.value)}px` }))
const imageSizeLabel = computed(() => imageNatural.width ? `${imageNatural.width} × ${imageNatural.height}` : '读取尺寸中')
const correctionResult = computed(() => {
  if (!selectedSample.value) return '—'
  if (isNegative.value) return '无有效目标'
  if (taskMode.value === 'classification') return classificationLabel.value || '待选择'
  return boxes.value.length ? `${[...new Set(boxes.value.map(b => b.label))].join('、')} · ${boxes.value.length} 个` : '待标注'
})
const canSave = computed(() => Boolean(selectedSample.value && (isNegative.value || (taskMode.value === 'classification' ? classificationLabel.value : boxes.value.length))))
const detectionSavedCount = computed(() => samples.value.filter(s => s.annotated && s.savedKind === 'detection').length)
const negativeSavedCount = computed(() => samples.value.filter(s => s.annotated && s.savedKind === 'negative').length)
const classificationSavedCount = computed(() => samples.value.filter(s => s.annotated && s.savedKind === 'classification').length)

function inferTaskMode(sample) {
  const type = `${sample?.task_type || sample?.model_type || ''}`.toLowerCase()
  if (type.includes('class') || type.includes('分类')) return 'classification'
  return /classification|classifier|分类/.test(`${sample?.source_path || ''} ${sample?.filename || ''}`.toLowerCase()) ? 'classification' : 'detection'
}
function samplePrediction(sample) {
  const prediction = sample?.original_prediction || sample?.prediction || {}
  const source = `${sample?.filename || ''} ${sample?.event_no || ''}`.toLowerCase()
  let fallback = '人员'
  if (/boat|ship|fish|fishing|船|渔/.test(source)) fallback = '船只'
  else if (/car|vehicle|车辆/.test(source)) fallback = '车辆'
  else if (/float|漂浮/.test(source)) fallback = '漂浮物'
  return { label: prediction.label || prediction.categoryName || sample?.predicted_label || fallback, confidence: Number(prediction.confidence ?? sample?.confidence ?? .864) }
}
function formatConfidence(value) { const n = Number(value || 0); return `${(n > 1 ? n : n * 100).toFixed(1)}%` }
function isSampleCompleted(sample) { return Boolean(sample?.annotated && sample?.uiStatus !== 'modified') }
function sampleStatus(sample) {
  if (selectedSample.value?.source_path === sample?.source_path && dirty.value) return isNegative.value ? { value: 'negative', label: '无目标' } : { value: 'modified', label: '有修改' }
  if (sample?.uiStatus === 'skipped') return { value: 'skipped', label: '已跳过' }
  if (sample?.uiStatus === 'negative') return { value: 'negative', label: '无目标' }
  return sample?.annotated ? { value: 'completed', label: '已完成' } : { value: 'pending', label: '待处理' }
}

async function loadSamples() {
  loading.value = true; loadError.value = ''
  try {
    const result = await getFalseAlarmSamples({ include_annotated: true })
    const states = new Map(samples.value.map(s => [s.source_path, { uiStatus: s.uiStatus, savedKind: s.savedKind }]))
    samples.value = (result.data?.items || []).map(s => ({ ...s, ...(states.get(s.source_path) || {}) }))
    if (!samples.value.some(s => s.source_path === selectedSample.value?.source_path)) selectSampleDirect(samples.value[0] || null)
  } catch (error) {
    loadError.value = error.response?.data?.detail || error.message || '未知错误'; ElMessage.error('误报图片队列加载失败')
  } finally { loading.value = false }
}
async function requestSelectSample(sample) {
  if (!sample || sample.source_path === selectedSample.value?.source_path) return
  if (!dirty.value) return selectSampleDirect(sample)
  try {
    await ElMessageBox.confirm('当前图片存在未保存修改，是否保存后切换？', '未保存修改', { confirmButtonText: '保存并切换', cancelButtonText: '放弃修改', distinguishCancelAndClose: true, closeOnClickModal: false, type: 'warning' })
    if (await saveCurrent(false)) selectSampleDirect(sample)
  } catch (action) { if (action === 'cancel') selectSampleDirect(sample) }
}
function selectSampleDirect(sample) {
  selectedSample.value = sample || null; boxes.value = []; classificationLabel.value = ''; isNegative.value = false
  dirty.value = false; selectedBoxIndex.value = -1; undoStack.value = []; redoStack.value = []; zoom.value = 1; showOriginalBoxes.value = false
  activeTool.value = inferTaskMode(sample) === 'classification' ? 'select' : 'draw'; imageStatus.value = sample ? 'loading' : 'idle'
  if (sample) activeLabel.value = samplePrediction(sample).label || labels[0].name
}
function snapshotState() { return { boxes: boxes.value.map(b => ({ ...b })), classificationLabel: classificationLabel.value, isNegative: isNegative.value } }
function applySnapshot(state) { boxes.value = state.boxes.map(b => ({ ...b })); classificationLabel.value = state.classificationLabel; isNegative.value = state.isNegative; selectedBoxIndex.value = -1; dirty.value = true }
function commitChange(mutator) { undoStack.value.push(snapshotState()); if (undoStack.value.length > 80) undoStack.value.shift(); redoStack.value = []; mutator(); dirty.value = true }
function undo() { const state = undoStack.value.pop(); if (!state) return; redoStack.value.push(snapshotState()); applySnapshot(state) }
function redo() { const state = redoStack.value.pop(); if (!state) return; undoStack.value.push(snapshotState()); applySnapshot(state) }

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }
function stagePoint(event) { const rect = stageRef.value?.getBoundingClientRect(); return rect?.width ? { x: clamp((event.clientX - rect.left) / rect.width, 0, 1), y: clamp((event.clientY - rect.top) / rect.height, 0, 1) } : null }
function startStagePointer(event) {
  if (event.button !== 0 || taskMode.value !== 'detection' || activeTool.value !== 'draw' || isNegative.value) return
  const p = stagePoint(event); if (!p) return
  selectedBoxIndex.value = -1; Object.assign(drawing, { active: true, startX: p.x, startY: p.y, x: p.x, y: p.y, pointerId: event.pointerId }); stageRef.value?.setPointerCapture?.(event.pointerId)
}
function moveStagePointer(event) {
  const p = stagePoint(event); if (!p) return
  if (drawing.active) { drawing.x = p.x; drawing.y = p.y; return }
  if (!interaction.active) return
  const dx = p.x - interaction.startX, dy = p.y - interaction.startY, box = interaction.original
  boxes.value[interaction.index] = interaction.type === 'move'
    ? { ...box, x: clamp(box.x + dx, 0, 1 - box.width), y: clamp(box.y + dy, 0, 1 - box.height) }
    : resizedBox(box, interaction.handle, dx, dy)
}
function finishStagePointer(event) {
  if (drawing.active) {
    const next = drawingBox.value; releasePointer(event.pointerId); drawing.active = false
    if (next?.width >= .01 && next?.height >= .01) commitChange(() => { boxes.value.push({ ...next, label: activeLabel.value }); selectedBoxIndex.value = boxes.value.length - 1 })
    return
  }
  if (interaction.active) {
    releasePointer(event.pointerId); const before = interaction.before; interaction.active = false
    if (before && JSON.stringify(before.boxes) !== JSON.stringify(boxes.value)) { undoStack.value.push(before); redoStack.value = []; dirty.value = true }
  }
}
function cancelStagePointer(event) { releasePointer(event.pointerId); if (interaction.active && interaction.before) applySnapshot(interaction.before); drawing.active = false; interaction.active = false }
function releasePointer(id) { try { stageRef.value?.releasePointerCapture?.(id) } catch { /* already released */ } }
function beginMoveBox(event, index) { selectedBoxIndex.value = index; if (activeTool.value === 'select' && event.button === 0) beginBoxInteraction(event, index, 'move', '') }
function beginResizeBox(event, index, handle) { if (event.button === 0) beginBoxInteraction(event, index, 'resize', handle) }
function beginBoxInteraction(event, index, type, handle) {
  const p = stagePoint(event); if (!p) return
  Object.assign(interaction, { active: true, type, index, handle, startX: p.x, startY: p.y, original: { ...boxes.value[index] }, before: snapshotState() }); stageRef.value?.setPointerCapture?.(event.pointerId)
}
function resizedBox(box, handle, dx, dy) {
  let left = box.x, top = box.y, right = box.x + box.width, bottom = box.y + box.height
  if (handle.includes('w')) left = clamp(left + dx, 0, right - .01); if (handle.includes('e')) right = clamp(right + dx, left + .01, 1)
  if (handle.includes('n')) top = clamp(top + dy, 0, bottom - .01); if (handle.includes('s')) bottom = clamp(bottom + dy, top + .01, 1)
  return { ...box, x: left, y: top, width: right - left, height: bottom - top }
}
function normalizeBox(box) {
  const x = Math.min(box.x, box.x + box.width), y = Math.min(box.y, box.y + box.height)
  return { label: box.label, x: clamp(x, 0, 1), y: clamp(y, 0, 1), width: clamp(Math.abs(box.width), 0, 1 - x), height: clamp(Math.abs(box.height), 0, 1 - y) }
}
function labelColor(name) { return labels.find(label => label.name === name)?.color || '#21d7ff' }
function boxStyle(box) { return { left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%`, '--box-color': labelColor(box.label) } }
function labelCount(name) { return boxes.value.filter(box => box.label === name).length }
function selectLabel(name) {
  if (!selectedSample.value) return
  if (taskMode.value === 'classification') return commitChange(() => { classificationLabel.value = name; isNegative.value = false })
  activeLabel.value = name; if (selectedBoxIndex.value >= 0 && activeTool.value === 'select') changeBoxLabel(selectedBoxIndex.value, name)
}
function changeBoxLabel(index, label) { if (boxes.value[index]?.label !== label) commitChange(() => { boxes.value[index] = { ...boxes.value[index], label } }) }
function removeBox(index) { if (boxes.value[index]) commitChange(() => { boxes.value.splice(index, 1); selectedBoxIndex.value = Math.min(index, boxes.value.length - 1) }) }
function deleteSelectedBox() { if (selectedBoxIndex.value >= 0) removeBox(selectedBoxIndex.value) }
function focusBox(index) { selectedBoxIndex.value = index; activeTool.value = 'select' }
function toggleNegative() { if (selectedSample.value) commitChange(() => { isNegative.value = !isNegative.value; if (isNegative.value) { boxes.value = []; classificationLabel.value = ''; selectedBoxIndex.value = -1 } }) }
function boxPixelSummary(box) { return `x ${Math.round(box.x * imageNatural.width)} · y ${Math.round(box.y * imageNatural.height)} · ${Math.round(box.width * imageNatural.width)} × ${Math.round(box.height * imageNatural.height)}` }

function handleImageLoad(event) { imageNatural.width = event.target.naturalWidth; imageNatural.height = event.target.naturalHeight; imageStatus.value = 'ready'; nextTick(fitImage) }
function handleImageError() { imageStatus.value = 'error' }
function retryImage() { imageRetryKey.value++; imageStatus.value = 'loading' }
function fitImage() {
  if (!imageNatural.width || !viewportRef.value) return
  const rect = viewportRef.value.getBoundingClientRect(), ratio = Math.min(Math.max(160, rect.width - 84) / imageNatural.width, Math.max(120, rect.height - 70) / imageNatural.height)
  stageBase.width = Math.round(imageNatural.width * ratio); stageBase.height = Math.round(imageNatural.height * ratio); zoom.value = 1; nextTick(centerViewport)
}
function originalImageScale() { if (stageBase.width) { zoom.value = clamp(imageNatural.width / stageBase.width, .4, 3); nextTick(centerViewport) } }
function changeZoom(delta) { zoom.value = clamp(Number((zoom.value + delta).toFixed(2)), .4, 3) }
function handleWheelZoom(event) { changeZoom(event.deltaY > 0 ? -.1 : .1) }
function centerViewport() { const v = viewportRef.value; if (v) { v.scrollLeft = Math.max(0, (v.scrollWidth - v.clientWidth) / 2); v.scrollTop = Math.max(0, (v.scrollHeight - v.clientHeight) / 2) } }

async function saveCurrent(showSuccess = true) {
  if (!selectedSample.value || saving.value) return false
  if (!canSave.value) { ElMessage.warning(taskMode.value === 'classification' ? '请选择正确分类或标记为无目标' : '请绘制目标框或标记为无目标'); return false }
  saving.value = true
  try {
    const annotations = isNegative.value ? [] : taskMode.value === 'classification' ? [{ label: classificationLabel.value, x: 0, y: 0, width: 1, height: 1 }] : boxes.value
    await saveFalseAlarmSampleAnnotation({ source_path: selectedSample.value.source_path, annotations })
    selectedSample.value.annotated = true; selectedSample.value.uiStatus = isNegative.value ? 'negative' : 'completed'; selectedSample.value.savedKind = isNegative.value ? 'negative' : taskMode.value
    dirty.value = false; undoStack.value = []; redoStack.value = []; lastSavedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    if (showSuccess) ElMessage.success(isNegative.value ? '负样本已保存' : '人工纠正结果已保存'); return true
  } catch (error) { ElMessage.error(error.response?.data?.detail || '标注保存失败'); return false } finally { saving.value = false }
}
async function saveAndNext() { if (await saveCurrent(false)) { ElMessage.success('已保存，进入下一张'); if (hasNext.value) selectSampleDirect(filteredSamples.value[currentQueueIndex.value + 1]) } }
function skipCurrent() { if (!selectedSample.value) return; if (dirty.value) return ElMessage.warning('当前图片有未保存修改，请先保存再跳过'); selectedSample.value.uiStatus = 'skipped'; hasNext.value ? selectSampleDirect(filteredSamples.value[currentQueueIndex.value + 1]) : ElMessage.info('已跳过当前图片') }
function goPrevious() { if (hasPrevious.value) requestSelectSample(filteredSamples.value[currentQueueIndex.value - 1]) }
function goNext() { if (hasNext.value) requestSelectSample(filteredSamples.value[currentQueueIndex.value + 1]) }
function exitTask() { if (!dirty.value || window.confirm('当前图片存在未保存修改，确定退出任务吗？')) router.push('/system/models') }
function generateDataset() { completeDialogVisible.value = false; ElMessage.success(`训练数据集“${datasetName.value}”已生成`) }
function handleKeydown(event) {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName) || event.target?.isContentEditable) return
  const key = event.key.toLowerCase()
  if ((event.ctrlKey || event.metaKey) && key === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); return }
  if ((event.ctrlKey || event.metaKey) && key === 'y') { event.preventDefault(); redo(); return }
  if (key === 'delete' || key === 'backspace') { event.preventDefault(); deleteSelectedBox() }
  else if (key === 'r' && taskMode.value === 'detection') activeTool.value = 'draw'
  else if (key === 'v' && taskMode.value === 'detection') activeTool.value = 'select'
  else if (key === 'a') goPrevious(); else if (key === 'd') goNext()
  else if (key === 'enter') { event.preventDefault(); saveAndNext() }
  else if (key === ' ') { event.preventDefault(); fitImage() }
}
function handleBeforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(() => !dirty.value || window.confirm('当前图片存在未保存修改，确定离开吗？'))
onMounted(() => { window.addEventListener('keydown', handleKeydown); window.addEventListener('beforeunload', handleBeforeUnload); window.addEventListener('resize', fitImage); loadSamples() })
onBeforeUnmount(() => { window.removeEventListener('keydown', handleKeydown); window.removeEventListener('beforeunload', handleBeforeUnload); window.removeEventListener('resize', fitImage) })
</script>
