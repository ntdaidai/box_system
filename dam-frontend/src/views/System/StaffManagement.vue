<template>
  <div class="staff-page">
    <header class="page-header">
      <div>
        <h2>现场人员</h2>
        <p>维护小程序现场处置人员，扫码登录后长期有效，删除人员即登录失效</p>
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
          <el-input
            v-model.trim="filters.keyword"
            class="keyword-input"
            clearable
            placeholder="姓名 / 编号 / OpenID"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
          <el-select v-model="filters.group" class="group-select" placeholder="所属组别" clearable @change="applyFilters">
            <el-option v-for="item in groups" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="filters.online" class="status-select" placeholder="状态" @change="applyFilters">
            <el-option label="全部" value="" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
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
          <div class="col-group">组别</div>
          <div class="col-status">状态</div>
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
          <div class="col-group group-cell">
            <span>{{ row.group_name || '--' }}</span>
          </div>
          <div class="col-status">
            <el-tooltip
              :content="row.is_online
                ? `最后活跃：${formatDateTime(row.last_active_at)}`
                : (row.last_active_at ? `最后活跃：${formatDateTime(row.last_active_at)}` : '从未活跃')"
              placement="top"
            >
              <span class="status-pill" :class="row.is_online ? 'is-online' : 'is-offline'">
                {{ row.is_online ? '在线' : '离线' }}
              </span>
            </el-tooltip>
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
      <el-form ref="staffFormRef" label-position="top" class="staff-form">
        <el-form-item label="人员名称" required>
          <el-input v-model.trim="staffForm.display_name" maxlength="128" placeholder="请输入人员名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="staffForm.description"
            type="textarea"
            :rows="3"
            maxlength="255"
            show-word-limit
            placeholder="人员职责、备注等信息（可选）"
          />
        </el-form-item>
        <el-form-item label="所属组别">
          <el-select
            v-model="staffForm.group_name"
            class="dialog-group-select"
            allow-create
            filterable
            default-first-option
            placeholder="选择或输入新组别"
          >
            <el-option v-for="item in groups" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
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
        <div class="qr-countdown" :class="{ 'is-expired': qrCountdown <= 0 }">
          {{ qrCountdown > 0 ? `剩余 ${formatCountdown(qrCountdown)}` : '已过期，请刷新' }}
        </div>
        <p class="qr-tip">5 分钟内有效，单次使用；人员用小程序扫此码即可登录，登录后长期有效</p>
      </div>
      <template #footer>
        <el-button type="primary" :loading="qrRefreshing" @click="refreshLoginCode">刷新登录码</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import {
  createStaff,
  deleteStaff,
  getStaffList,
  getStaffLoginCode,
  staffQrCodeUrl,
  updateStaff,
} from '@/api/staff'

const loading = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const groups = ref([])
const rows = ref([])
const filters = reactive({
  keyword: '',
  group: '',
  online: '',
})

const staffRows = computed(() => rows.value)

onMounted(() => {
  loadStaff()
})

onUnmounted(() => {
  clearQrTimer()
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
    groups.value = data.data?.groups || data.groups || groups.value
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  loadStaff()
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleString('zh-CN', { hour12: false })
}

// ── 新增 / 编辑 ──────────────────────────────────────────────
const staffDialogVisible = ref(false)
const saving = ref(false)
const staffForm = reactive({
  id: null,
  staff_no: '',
  display_name: '',
  description: '',
  group_name: '',
  phone: '',
  openid_bound: false,
})

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
}

async function submitStaff() {
  if (!staffForm.display_name?.trim()) {
    ElMessage.warning('请填写人员名称')
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

// ── 登录码（二维码）──────────────────────────────────────────
const qrVisible = ref(false)
const qrRefreshing = ref(false)
const qrStaff = ref(null)
const qrTicket = ref('')
const qrExpiresAt = ref(0)
const qrCountdown = ref(0)
let qrTimer = null

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
    qrExpiresAt.value = Number(data.data?.expires_at ?? data.expires_at ?? 0)
    startQrTimer()
  } finally {
    qrRefreshing.value = false
  }
}

function startQrTimer() {
  clearQrTimer()
  updateCountdown()
  qrTimer = setInterval(updateCountdown, 1000)
}

function updateCountdown() {
  qrCountdown.value = Math.max(0, Math.ceil(qrExpiresAt.value - Date.now() / 1000))
  if (qrCountdown.value <= 0) clearQrTimer()
}

function clearQrTimer() {
  if (qrTimer) {
    clearInterval(qrTimer)
    qrTimer = null
  }
}

function formatCountdown(sec) {
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function closeQrDialog() {
  clearQrTimer()
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

.keyword-input {
  width: 230px;
}

.group-select {
  width: 150px;
}

.status-select {
  width: 112px;
}

.keyword-input :deep(.el-input__wrapper),
.group-select :deep(.el-select__wrapper),
.status-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, .36) inset;
}

.keyword-input :deep(.el-input__inner),
.keyword-input :deep(.el-input__inner::placeholder),
.group-select :deep(.el-select__selected-item),
.group-select :deep(.el-select__placeholder),
.status-select :deep(.el-select__selected-item),
.status-select :deep(.el-select__placeholder) {
  color: #d7edf6;
  font-weight: 700;
}

.staff-list-card {
  padding: 0;
  overflow-x: auto;
}

.staff-list {
  min-width: 1320px;
  overflow: hidden;
  border-radius: 8px 8px 0 0;
  background: #081b2d;
}

.staff-list-header-row,
.staff-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(300px, 1.45fr) 150px 112px 320px;
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
.col-group,
.col-status,
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

.status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  height: 24px;
  padding: 0 10px;
  justify-content: center;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}

.status-pill.is-online {
  border: 1px solid rgba(92, 215, 154, .34);
  color: #81efad;
  background: rgba(48, 154, 118, .18);
}

.status-pill.is-offline {
  border: 1px solid rgba(235, 124, 133, .34);
  color: #ffabb5;
  background: rgba(142, 48, 62, .18);
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
  border-color: rgba(224, 96, 104, .46);
  color: #ffb9bf;
  background: rgba(112, 40, 46, .42);
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
  border-color: rgba(224, 96, 104, .72);
  color: #ffe3e6;
  background: rgba(140, 48, 55, .55);
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

/* ── 弹窗样式（对齐广播页深色主题）────────────────────────── */
.staff-config-dialog :deep(.el-dialog),
.qr-dialog :deep(.el-dialog) {
  border: 1px solid rgba(96, 151, 191, .28);
  border-radius: 10px;
  background: #0d2136;
}

.staff-config-dialog :deep(.el-dialog__header),
.qr-dialog :deep(.el-dialog__header) {
  padding: 18px 22px 10px;
  border-bottom: 1px solid rgba(96, 151, 191, .16);
}

.staff-config-dialog :deep(.el-dialog__title),
.qr-dialog :deep(.el-dialog__title) {
  color: #f3f8fd;
  font-size: 17px;
  font-weight: 700;
}

.staff-config-dialog :deep(.el-dialog__body),
.qr-dialog :deep(.el-dialog__body) {
  padding: 20px 22px;
}

.staff-config-dialog :deep(.el-dialog__footer),
.qr-dialog :deep(.el-dialog__footer) {
  padding: 12px 22px 18px;
}

.staff-form :deep(.el-form-item__label) {
  color: #d9ecfa;
  font-size: 14px;
  font-weight: 700;
}

.staff-form :deep(.el-form-item__label::before) {
  color: #ff7b85;
}

.staff-form :deep(.el-input__wrapper),
.staff-form :deep(.el-textarea__inner),
.dialog-group-select :deep(.el-select__wrapper) {
  border-radius: 6px;
  background: #0a1f35;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, .30) inset;
  color: #e6f4ff;
}

.staff-form :deep(.el-input__inner),
.staff-form :deep(.el-textarea__inner) {
  color: #e6f4ff;
  font-weight: 600;
}

.staff-form :deep(.el-input__inner::placeholder),
.staff-form :deep(.el-textarea__inner::placeholder) {
  color: #5f82a0;
  font-weight: 400;
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

.qr-countdown {
  color: #79d4a8;
  font-size: 14px;
  font-weight: 700;
}

.qr-countdown.is-expired {
  color: #ffabb5;
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
