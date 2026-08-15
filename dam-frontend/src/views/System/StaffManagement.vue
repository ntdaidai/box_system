<template>
  <div class="staff-page">
    <header class="page-header">
      <div>
        <h2>现场人员</h2>
        <p>维护小程序现场处置人员、所属组别和微信绑定状态</p>
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
          <el-select v-model="filters.status" class="status-select" placeholder="状态" @change="applyFilters">
            <el-option label="全部" value="all" />
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
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
          <div class="col-status">状态</div>
          <div class="col-enabled">启用状态</div>
          <div class="col-actions">操作</div>
        </div>

        <article v-for="row in staffRows" :key="row.id" class="staff-row" :class="row.status === 'ACTIVE' ? 'is-active' : 'is-inactive'">
          <div class="col-name name-cell">
            <div>
              <strong>{{ row.display_name || '--' }}</strong>
            </div>
          </div>
          <div class="col-description staff-description">
            <span>{{ staffDescription(row) }}</span>
          </div>
          <div class="col-status">
            <span class="status-pill" :class="row.status === 'ACTIVE' ? 'is-active' : 'is-inactive'">
              {{ row.status_label || statusLabel(row.status) }}
            </span>
          </div>
          <div class="col-enabled">
            <el-switch :model-value="row.status === 'ACTIVE'" disabled />
          </div>
          <div class="col-actions action-buttons list-actions">
            <el-button class="test-action" @click="showPendingAction('登录码')">登录码</el-button>
            <el-button class="edit-action" @click="showPendingAction('编辑')">编辑</el-button>
          </div>
        </article>

        <div v-if="!staffRows.length" class="empty-list">
          <strong>暂无现场人员</strong>
          <span>可先在后端人员表维护基础人员信息</span>
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { getMiniProgramStaff } from '@/api/miniprogramStaff'

const loading = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const groups = ref([])
const rows = ref([])
const filters = reactive({
  keyword: '',
  group: '',
  status: 'all',
})

const staffRows = computed(() => rows.value)

onMounted(() => {
  loadStaff()
})

async function loadStaff() {
  loading.value = true
  try {
    const data = await getMiniProgramStaff({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword || undefined,
      group: filters.group || undefined,
      status: filters.status || 'all',
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

function formatDate(value) {
  if (!value) return '--'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleDateString('zh-CN')
}

function statusLabel(status) {
  return status === 'ACTIVE' ? '启用' : '停用'
}

function staffDescription(row) {
  const bindText = row.openid_bound ? '已绑定小程序' : '未绑定小程序'
  const accountText = row.username ? `账号 ${row.username}` : '账号未设置'
  const groupText = row.group_name || '默认处置组'
  const staffNo = row.staff_no || '--'
  return `${staffNo} / ${groupText} / ${bindText} / ${accountText}`
}

function avatarText(row) {
  return String(row.display_name || row.staff_no || '人').slice(0, 1)
}

function avatarColor(row) {
  const palette = ['#1d8fb8', '#219f7a', '#a66a1d', '#8a6be8']
  const seed = String(row.staff_no || row.id || '').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return palette[seed % palette.length]
}

function showPendingAction(label) {
  ElMessage.info(`${label}功能待接入`)
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
  grid-template-columns: minmax(240px, 1.15fr) minmax(320px, 1.45fr) 124px 132px 220px;
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
.col-status,
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

strong {
  overflow: hidden;
  max-width: 100%;
  color: #f3f8fd;
  font-size: 15px;
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

.status-pill.is-active {
  border: 1px solid rgba(92, 215, 154, .34);
  color: #81efad;
  background: rgba(48, 154, 118, .18);
}

.status-pill.is-inactive {
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

.col-enabled :deep(.el-switch.is-disabled) {
  opacity: 1;
}

.col-enabled :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, .34);
  background: rgba(96, 118, 134, .38);
}

.col-enabled :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, .66);
  background: #409eff;
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

@media (max-width: 1280px) {
  .staff-page {
    overflow-x: auto;
  }
}
</style>
