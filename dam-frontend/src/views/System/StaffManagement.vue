<template>
  <div class="staff-page">
    <header class="page-header staff-overview-bar">
      <div class="title-block">
        <h2>现场人员</h2>
        <p>维护小程序现场处置人员</p>
      </div>
      <div class="status-summary">
        <div class="metric">
          <i class="dot total"></i>
          <strong class="metric-num">{{ summary.total }}</strong>
          <span class="metric-label">总数</span>
        </div>
        <div class="metric">
          <i class="dot idle"></i>
          <strong class="metric-num">{{ summary.idle }}</strong>
          <span class="metric-label">空闲</span>
        </div>
        <div class="metric">
          <i class="dot working"></i>
          <strong class="metric-num">{{ summary.working }}</strong>
          <span class="metric-label">工作中</span>
        </div>
        <div class="metric">
          <i class="dot offline"></i>
          <strong class="metric-num">{{ summary.offline }}</strong>
          <span class="metric-label">离线</span>
        </div>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadStaff">刷新</el-button>
    </header>

    <section class="resource-control-card staff-toolbar-card">
      <header class="tab-header">
        <div>
          <h3>人员列表</h3>
          <span>共 {{ total }} 人</span>
        </div>
        <div class="tab-actions panel-toolbar">
          <el-button type="primary" :icon="Plus" @click="openStaffDialog()">新增人员</el-button>
          <el-select v-model="filters.group" class="group-filter-select" placeholder="所属组别" clearable @change="applyFilters">
            <el-option v-for="item in allGroups" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="applyFilters">筛选</el-button>
        </div>
      </header>
    </section>

    <section class="resource-list-card staff-list-card" v-loading="loading">
      <div class="staff-list" :class="{ 'is-empty': !staffRows.length }">
        <div v-if="staffRows.length" class="staff-list-header-row">
          <div class="col-name">人员名称</div>
          <div class="col-description">描述</div>
          <div class="col-phone">联系电话</div>
          <div class="col-group">组别</div>
          <div class="col-enabled">是否启用</div>
          <div class="col-actions">操作</div>
        </div>

        <article v-for="row in staffRows" :key="row.id" class="staff-row">
          <div class="col-name name-cell">
            <div class="name-main">
              <strong>{{ row.display_name || '--' }}</strong>
              <span class="staff-no">{{ row.staff_no }}</span>
            </div>
          </div>
          <div class="col-description staff-description">
            <span>{{ row.description || '--' }}</span>
          </div>
          <div class="col-phone staff-phone">
            <span>{{ row.phone || '--' }}</span>
          </div>
          <div class="col-group group-cell">
            <span>{{ row.group_name || '--' }}</span>
          </div>
          <div class="col-enabled">
            <el-switch
              :model-value="row.enabled !== false"
              :loading="enableLoading[row.id]"
              @change="(value) => toggleStaffEnabled(row, value)"
            />
          </div>
          <div class="col-actions action-buttons list-actions">
            <el-button class="test-action" @click="openLoginCodeDialog(row)">登录码</el-button>
            <el-button class="edit-action" @click="openStaffDialog(row)">编辑</el-button>
            <el-button class="delete-action" @click="confirmDeleteStaff(row)">删除</el-button>
          </div>
        </article>

        <div v-if="!staffRows.length" class="empty-list">
          <strong>暂无现场人员</strong>
          <span>点击「新增人员」创建处置人员，创建后可生成登录码供扫码登录</span>
        </div>
      </div>
      <el-pagination
        v-if="total"
        v-model:current-page="page"
        class="list-pagination"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadStaff"
      />
    </section>

    <!-- 新增 / 编辑人员弹窗 -->
    <el-dialog
      v-model="staffDialogVisible"
      class="staff-config-dialog"
      :title="staffForm.id ? '编辑人员' : '新增人员'"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="staffFormRef" :model="staffForm" :rules="staffRules" label-position="top" class="staff-form">
        <el-form-item label="人员名称" prop="display_name">
          <el-input v-model.trim="staffForm.display_name" maxlength="128" placeholder="请输入人员名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="staffForm.description"
            type="textarea"
            :rows="3"
            maxlength="255"
            show-word-limit
            placeholder="人员职责、备注等信息（可选）"
          />
        </el-form-item>
        <el-form-item label="所属组别" prop="group_name">
          <el-select
            v-model="staffForm.group_name"
            class="dialog-group-select"
            popper-class="staff-filter-popper"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="请选择组别，或输入新组名创建"
          >
            <el-option v-for="item in allGroups" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input v-model.trim="staffForm.phone" maxlength="32" placeholder="联系电话（可选）" />
        </el-form-item>
        <div v-if="staffForm.id" class="staff-meta">
          <span>编号：{{ staffForm.staff_no }}</span>
          <span>微信：{{ staffForm.openid_bound ? '已绑定' : '未绑定' }}</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="staffDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitStaff">保存</el-button>
      </template>
    </el-dialog>

    <!-- 登录码弹窗 -->
    <el-dialog
      v-model="qrVisible"
      class="qr-dialog"
      :title="`登录码 · ${qrStaff?.display_name || ''}`"
      width="420px"
      :close-on-click-modal="false"
      @closed="closeQrDialog"
    >
      <div class="qr-body">
        <div v-if="qrTicket" class="qr-canvas">
          <img :src="staffQrCodeUrl(qrStaff.id, qrTicket)" alt="登录二维码" class="qr-img" />
        </div>
        <div v-else class="qr-loading">生成中...</div>
        <div class="qr-permanent">永久有效</div>
        <p class="qr-tip">登录码永久有效；人员用小程序扫此码即可登录，登录后长期有效，删除人员即登录失效</p>
      </div>
      <template #footer>
        <el-button type="primary" :loading="qrRefreshing" @click="refreshLoginCode">刷新登录码</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
  createStaff,
  deleteStaff,
  getStaffList,
  getStaffLoginCode,
  staffQrCodeUrl,
  updateStaff,
  updateStaffEnabled,
} from '@/api/staff'

// 固定点位组：九号点位组、一号点位组、三号点位组
const GROUP_OPTIONS = ['九号点位组', '一号点位组', '三号点位组']

// 全部组别：固定三组 + 后端已存在的自定义组（列表筛选、弹窗下拉共用）
const allGroups = ref([...GROUP_OPTIONS])

function mergeGroups(serverGroups = []) {
  const seen = new Set(GROUP_OPTIONS)
  const merged = [...GROUP_OPTIONS]
  for (const g of serverGroups) {
    if (g && !seen.has(g)) {
      seen.add(g)
      merged.push(g)
    }
  }
  return merged
}

const loading = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const rows = ref([])
const enableLoading = reactive({})
const summary = ref({ total: 0, idle: 0, offline: 0, working: 0 })
const filters = reactive({
  keyword: '',
  group: '',
  online: '',
})

const staffRows = computed(() => rows.value)

onMounted(() => {
  loadStaff()
})

async function loadStaff() {
  loading.value = true
  try {
    const data = await getStaffList({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword || undefined,
      group: filters.group || undefined,
      online: filters.online || undefined,
    })
    rows.value = data.data?.items || data.items || []
    total.value = Number(data.data?.total ?? data.total ?? 0)
    summary.value = data.data?.summary || { total: 0, idle: 0, offline: 0, working: 0 }
    const serverGroups = data.data?.groups || data.groups
    if (Array.isArray(serverGroups)) {
      allGroups.value = mergeGroups(serverGroups)
    }
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  loadStaff()
}

// ── 新增 / 编辑 ──────────────────────────────────────────────
const staffDialogVisible = ref(false)
const saving = ref(false)
const staffFormRef = ref(null)
const staffForm = reactive({
  id: null,
  staff_no: '',
  display_name: '',
  description: '',
  group_name: '',
  phone: '',
  openid_bound: false,
})

const staffRules = {
  display_name: [{ required: true, message: '请输入人员名称', trigger: 'blur' }],
  group_name: [{ required: true, message: '请选择或输入所属组别', trigger: 'change' }],
}

function openStaffDialog(row) {
  if (row) {
    Object.assign(staffForm, {
      id: row.id,
      staff_no: row.staff_no,
      display_name: row.display_name || '',
      description: row.description || '',
      group_name: row.group_name || '',
      phone: row.phone || '',
      openid_bound: !!row.openid_bound,
    })
  } else {
    Object.assign(staffForm, {
      id: null,
      staff_no: '',
      display_name: '',
      description: '',
      group_name: '',
      phone: '',
      openid_bound: false,
    })
  }
  staffDialogVisible.value = true
  nextTick(() => staffFormRef.value?.clearValidate?.())
}

async function submitStaff() {
  try {
    await staffFormRef.value?.validate?.()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = {
      display_name: staffForm.display_name.trim(),
      description: staffForm.description || undefined,
      group_name: staffForm.group_name || undefined,
      phone: staffForm.phone || undefined,
    }
    if (staffForm.id) {
      await updateStaff(staffForm.id, payload)
      ElMessage.success('人员已更新')
    } else {
      await createStaff(payload)
      ElMessage.success('人员已新增')
    }
    staffDialogVisible.value = false
    loadStaff()
  } finally {
    saving.value = false
  }
}

// ── 删除 ─────────────────────────────────────────────────────
async function confirmDeleteStaff(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除人员「${row.display_name}」？删除后该人员小程序登录将立即失效。`,
      '删除人员',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      }
    )
    await deleteStaff(row.id)
    ElMessage.success('人员已删除')
    loadStaff()
  } catch (error) {
    /* 用户取消删除，忽略 */
  }
}

// ── 启用 / 停用 ───────────────────────────────────────────────
async function toggleStaffEnabled(row, enabled) {
  const previous = row.enabled !== false
  row.enabled = enabled
  enableLoading[row.id] = true
  try {
    const res = await updateStaffEnabled(row.id, enabled)
    ElMessage.success(res.message || (enabled ? '人员已启用' : '人员已停用'))
  } catch (error) {
    row.enabled = previous
    ElMessage.error(error.response?.data?.detail || '启用状态更新失败')
  } finally {
    enableLoading[row.id] = false
  }
}

// ── 登录码（二维码）──────────────────────────────────────────
const qrVisible = ref(false)
const qrRefreshing = ref(false)
const qrStaff = ref(null)
const qrTicket = ref('')

async function openLoginCodeDialog(row) {
  qrStaff.value = row
  qrTicket.value = ''
  qrVisible.value = true
  await refreshLoginCode()
}

async function refreshLoginCode() {
  if (!qrStaff.value) return
  qrRefreshing.value = true
  try {
    const data = await getStaffLoginCode(qrStaff.value.id)
    qrTicket.value = data.data?.ticket || data.ticket
  } finally {
    qrRefreshing.value = false
  }
}

function closeQrDialog() {
  qrStaff.value = null
  qrTicket.value = ''
}
</script>

<style scoped>
.staff-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}

.page-header,
.tab-header,
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header {
  min-height: 62px;
  margin-bottom: 14px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, .22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, .82) 0%, rgba(9, 29, 48, .72) 58%, rgba(7, 20, 34, .46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, .08);
}

/* 顶部概览：标题 + 统计卡片 + 刷新按钮（参考机器狗设备页） */
.staff-overview-bar {
  min-height: 96px;
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(460px, 1.8fr) auto;
  align-items: center;
  gap: 18px;
}

/* 顶部统计：紧凑发光圆点 + 大数字 + 小标签，细分割线分隔，融入 header 不突兀 */
.status-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  flex-wrap: nowrap;
}

.metric {
  min-width: 96px;
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 18px;
  white-space: nowrap;
}

.metric + .metric {
  border-left: 1px solid rgba(96, 151, 191, .18);
}

.metric .dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  align-self: center;
  border-radius: 50%;
  background: #8db2c8;
  box-shadow: 0 0 8px rgba(141, 178, 200, .75);
}

.metric .dot.idle { background: #48e6bf; box-shadow: 0 0 8px rgba(72, 230, 191, .75); }
.metric .dot.working { background: #43d4ff; box-shadow: 0 0 8px rgba(67, 212, 255, .75); }
.metric .dot.offline { background: #8494a3; box-shadow: none; }

.metric-num {
  color: #f2fbff;
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.metric-label {
  color: #8db2c8;
  font-size: 12px;
}

.page-header h2,
.tab-header h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}

.page-header h2 {
  font-size: 25px;
  line-height: 1.15;
}

.page-header p {
  margin: 7px 0 0;
  color: #87a5bb;
  font-size: 13px;
  line-height: 1.45;
}

.page-header :deep(.el-button) {
  min-width: 92px;
  height: 36px;
  border-color: #1b7fa5;
  color: #dcefff;
  background: #103954;
  font-weight: 700;
}

.tab-header span {
  margin: 6px 0 0;
  color: #79acd0;
  font-size: 13px;
}

.tab-header h3 {
  font-size: 18px;
}

.resource-control-card,
.resource-list-card {
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
}

.resource-control-card {
  min-height: 82px;
  display: flex;
  align-items: center;
  padding: 18px 20px;
}

.resource-control-card .tab-header {
  width: 100%;
}

.resource-list-card {
  margin-top: 16px;
  overflow: hidden;
}

.staff-toolbar-card {
  padding: 18px 20px;
}

.staff-toolbar-card .tab-header {
  width: 100%;
}

.tab-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: nowrap;
}

.tab-actions :deep(.el-button) {
  min-width: 108px;
  height: 36px;
  margin-left: 0;
  padding: 0 15px;
}

.tab-actions :deep(.el-button--primary) {
  border-color: #2f8cc2;
  color: #ffffff;
  background: #1b6a9c;
}

.group-filter-select {
  width: 180px;
}

.group-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, .36) inset;
}

.group-filter-select :deep(.el-select__selected-item),
.group-filter-select :deep(.el-select__placeholder) {
  color: #d7edf6;
  font-weight: 700;
}

.staff-list-card {
  padding: 0;
  overflow-x: auto;
}

.staff-list {
  min-width: 1380px;
  overflow: hidden;
  border-radius: 8px 8px 0 0;
  background: #081b2d;
}

.staff-list-header-row,
.staff-row {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(260px, 1.25fr) 140px 150px 112px 300px;
  align-items: center;
  gap: 14px;
}

.staff-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}

.staff-row {
  min-height: 72px;
  padding: 12px 20px;
  border-top: 1px solid rgba(149, 190, 220, .10);
  color: #d7e8f8;
  background: #092034;
  transition: background .18s ease;
}

.staff-row:hover {
  background: #102940;
}

.col-name,
.col-description,
.col-phone,
.col-group,
.col-enabled,
.col-actions {
  min-width: 0;
  display: grid;
  gap: 6px;
  justify-items: center;
  text-align: center;
}

.name-cell {
  justify-items: center;
  text-align: center;
}

.name-main {
  display: grid;
  gap: 3px;
  justify-items: center;
}

.staff-no {
  color: #5f82a0;
  font-size: 12px;
}

strong {
  overflow: hidden;
  max-width: 100%;
  color: #f3f8fd;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-cell span {
  overflow: hidden;
  max-width: 100%;
  color: #b9d2e6;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.staff-description span {
  display: -webkit-box;
  overflow: hidden;
  color: #a9c0d2;
  font-size: 15px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.staff-phone span {
  color: #b9d2e6;
  font-size: 14px;
  white-space: nowrap;
}

.list-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: nowrap;
}

.list-actions :deep(.el-button) {
  width: auto;
  height: 34px;
  min-height: 34px;
  margin-left: 0;
  padding: 0 16px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}

.list-actions :deep(.test-action) {
  border-color: rgba(82, 178, 143, .46);
  color: #b9f1d8;
  background: rgba(30, 103, 78, .38);
}

.list-actions :deep(.edit-action) {
  border-color: rgba(66, 164, 224, .50);
  color: #d5f0ff;
  background: rgba(29, 91, 133, .70);
}

.list-actions :deep(.delete-action) {
  border-color: rgba(226, 88, 109, .46);
  color: #ffb1bd;
  background: rgba(128, 36, 54, .48);
}

.list-actions :deep(.test-action:hover) {
  border-color: rgba(82, 178, 143, .7);
  color: #e3fff1;
  background: rgba(36, 123, 92, .52);
}

.list-actions :deep(.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72);
  color: #effaff;
  background: rgba(33, 107, 156, .82);
}

.list-actions :deep(.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68);
  color: #ffd5dd;
  background: rgba(144, 42, 62, .62);
}

/* 双保险：全局 + !important 覆盖（与广播列表一致，确保三色按钮必然生效） */
:global(.staff-page .list-actions .el-button.test-action) {
  border-color: rgba(82, 178, 143, .54) !important;
  color: #b9f1d8 !important;
  background: rgba(30, 103, 78, .42) !important;
}

:global(.staff-page .list-actions .el-button.edit-action) {
  border-color: rgba(66, 164, 224, .50) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .70) !important;
}

:global(.staff-page .list-actions .el-button.delete-action) {
  border-color: rgba(226, 88, 109, .46) !important;
  color: #ffb1bd !important;
  background: rgba(128, 36, 54, .48) !important;
}

:global(.staff-page .list-actions .el-button.test-action:hover) {
  border-color: rgba(82, 178, 143, .72) !important;
  color: #e3fff1 !important;
  background: rgba(36, 123, 92, .56) !important;
}

:global(.staff-page .list-actions .el-button.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .82) !important;
}

:global(.staff-page .list-actions .el-button.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68) !important;
  color: #ffd5dd !important;
  background: rgba(144, 42, 62, .62) !important;
}

.empty-list {
  min-height: 220px;
  display: grid;
  place-content: center;
  gap: 8px;
  color: #8fa8bf;
  text-align: center;
}

.empty-list strong {
  color: #e9f7ff;
  font-size: 16px;
}

.list-pagination {
  min-height: 46px;
  justify-content: center;
  border-top: 1px solid rgba(149, 190, 220, .10);
  background: #092034;
}

.list-pagination :deep(.el-pager li),
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next) {
  min-width: 34px;
  height: 32px;
  margin: 0 3px;
  border: 1px solid rgba(70, 145, 190, .34);
  border-radius: 5px;
  color: #8fb6d1;
  background: #0b2238;
  font-weight: 700;
}

.list-pagination :deep(.el-pager li.is-active) {
  border-color: #4ba7e6;
  color: #ffffff;
  background: #3f95d7;
}

.list-pagination :deep(.btn-prev:disabled),
.list-pagination :deep(.btn-next:disabled) {
  color: rgba(143, 182, 209, .35);
  background: #0b2238;
}

/* ── 弹窗样式（对齐广播页深色主题；el-dialog teleport 到 body，须用 :global）── */
:global(.staff-config-dialog.el-dialog) {
  border: 1px solid rgba(97, 167, 214, .40);
  border-radius: 10px;
  background: #1d426a;
}

:global(.staff-config-dialog .el-dialog__header) {
  position: relative;
  min-height: 58px;
  display: flex;
  align-items: center;
  margin: 0;
  padding: 18px 58px 10px 24px;
}

:global(.staff-config-dialog .el-dialog__title) {
  color: #eef7ff;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
}

:global(.staff-config-dialog .el-dialog__headerbtn) {
  top: 14px;
  right: 18px;
  width: 34px;
  height: 34px;
}

:global(.staff-config-dialog .el-dialog__close) {
  color: #c8d9e7;
}

:global(.staff-config-dialog .el-dialog__body) {
  padding: 12px 24px 8px;
}

:global(.staff-config-dialog .el-dialog__footer) {
  padding: 12px 24px 20px;
}

/* 表单 label：浅色大号加粗，对标广播 */
:global(.staff-config-dialog .el-form-item__label) {
  margin-bottom: 8px !important;
  color: #e2f0fb !important;
  font-size: 15px !important;
  font-weight: 700 !important;
}

/* 必填红星改到标签文字右侧（对标广播列表"红点在右边"细节） */
:global(.staff-config-dialog .el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::before) {
  display: none !important;
}

:global(.staff-config-dialog .el-form-item.is-required:not(.is-no-asterisk).asterisk-left > .el-form-item__label::after) {
  content: "*" !important;
  margin-left: 6px !important;
  color: #ff6b78 !important;
  font-size: 20px !important;
  font-weight: 900 !important;
  line-height: 1 !important;
  vertical-align: -2px !important;
}

/* 输入框 / 文本域 / 下拉框：深色内阴影，对标广播 */
:global(.staff-config-dialog .el-input__wrapper),
:global(.staff-config-dialog .el-textarea__inner),
:global(.staff-config-dialog .el-select__wrapper) {
  border-radius: 6px;
  background: #092034;
  box-shadow: inset 0 0 0 1px rgba(36, 128, 176, .46);
  color: #f4fbff;
}

:global(.staff-config-dialog .el-input__inner),
:global(.staff-config-dialog .el-textarea__inner) {
  color: #f4fbff;
}

:global(.staff-config-dialog .el-input__inner::placeholder),
:global(.staff-config-dialog .el-textarea__inner::placeholder) {
  color: #a5b8c7;
}

:global(.staff-config-dialog .el-select__selected-item),
:global(.staff-config-dialog .el-select__placeholder) {
  color: #f4fbff;
  font-weight: 600;
}

:global(.staff-config-dialog .el-input__count) {
  display: none;
}

/* 所属组别下拉（allow-create）popper 深色主题 */
:global(.staff-filter-popper.el-select__popper) {
  border: 1px solid rgba(72, 216, 255, .28);
  background: #082033;
  box-shadow: 0 16px 36px rgba(0, 7, 18, .38);
}

:global(.staff-filter-popper .el-select-dropdown__item) {
  color: #aecdde;
}

:global(.staff-filter-popper .el-select-dropdown__item.is-hovering),
:global(.staff-filter-popper .el-select-dropdown__item:hover) {
  color: #e9fbff;
  background: rgba(72, 216, 255, .12);
}

:global(.staff-filter-popper .el-select-dropdown__item.is-selected),
:global(.staff-filter-popper .el-select-dropdown__item.selected) {
  color: #50e1d0;
  font-weight: 800;
}

/* 二维码弹窗：同样用 :global 兜底深色主题 */
:global(.qr-dialog.el-dialog) {
  border: 1px solid rgba(96, 151, 191, .28);
  border-radius: 10px;
  background: #0d2136;
}

:global(.qr-dialog .el-dialog__header) {
  padding: 18px 22px 10px;
  border-bottom: 1px solid rgba(96, 151, 191, .16);
}

:global(.qr-dialog .el-dialog__title) {
  color: #f3f8fd;
  font-size: 17px;
  font-weight: 700;
}

:global(.qr-dialog .el-dialog__body) {
  padding: 20px 22px;
}

:global(.qr-dialog .el-dialog__footer) {
  padding: 12px 22px 18px;
}

.dialog-group-select {
  width: 100%;
}

.staff-meta {
  display: flex;
  gap: 18px;
  margin-top: 4px;
  padding: 10px 12px;
  border: 1px dashed rgba(96, 151, 191, .26);
  border-radius: 6px;
  color: #6f93ae;
  font-size: 12px;
  background: rgba(8, 27, 45, .5);
}

.qr-body {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 8px 0 2px;
}

.qr-canvas {
  width: 200px;
  height: 200px;
  display: grid;
  place-content: center;
  padding: 10px;
  border: 1px solid rgba(96, 151, 191, .3);
  border-radius: 8px;
  background: #ffffff;
}

.qr-img {
  width: 180px;
  height: 180px;
  display: block;
}

.qr-loading {
  width: 200px;
  height: 200px;
  display: grid;
  place-content: center;
  color: #6f93ae;
  font-size: 13px;
}

.qr-permanent {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border: 1px solid rgba(92, 215, 154, .34);
  border-radius: 12px;
  color: #81efad;
  background: rgba(48, 154, 118, .18);
  font-size: 13px;
  font-weight: 700;
}

.qr-tip {
  margin: 0;
  color: #6f93ae;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

@media (max-width: 1280px) {
  .staff-page {
    overflow-x: auto;
  }
}
</style>
