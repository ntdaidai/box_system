<template>
  <div class="staff-page">
    <header class="admin-header">
      <div class="title-block">
        <h2>现场人员管理</h2>
        <p>维护小程序人工处置人员、所属组别和微信绑定状态</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadStaff">刷新</el-button>
    </header>

    <section class="data-panel staff-toolbar-card">
      <div class="panel-head">
        <div>
          <h3>人员列表</h3>
          <span>共 {{ total }} 人</span>
        </div>
        <div class="panel-toolbar">
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
      </div>
    </section>

    <section class="data-panel staff-list-card" v-loading="loading">
      <div class="staff-list" :class="{ 'is-empty': !staffRows.length }">
        <div v-if="staffRows.length" class="staff-list-header-row">
          <div class="col-name">人员名称</div>
          <div class="col-group">所属组别</div>
          <div class="col-wechat">小程序身份</div>
          <div class="col-account">账号信息</div>
          <div class="col-login">最近登录</div>
          <div class="col-status">状态</div>
          <div class="col-actions">操作</div>
        </div>

        <article v-for="row in staffRows" :key="row.id" class="staff-row" :class="row.status === 'ACTIVE' ? 'is-active' : 'is-inactive'">
          <div class="col-name name-cell">
            <span class="avatar" :style="{ background: avatarColor(row) }">{{ avatarText(row) }}</span>
            <div>
              <strong>{{ row.display_name || '--' }}</strong>
              <small>{{ row.staff_no || '--' }}</small>
            </div>
          </div>
          <div class="col-group">
            <strong>{{ row.group_name || '默认处置组' }}</strong>
            <small>{{ row.group_id || 'default' }}</small>
          </div>
          <div class="col-wechat">
            <span class="bind-pill" :class="row.openid_bound ? 'is-bound' : 'is-unbound'">
              {{ row.openid_bound ? '已绑定' : '未绑定' }}
            </span>
            <small>{{ row.nickname || '大藤峡安全巡查' }}</small>
          </div>
          <div class="col-account account-cell">
            <span><b>账号</b>{{ row.username || '未设置' }}</span>
            <span><b>密码</b>{{ row.has_password ? '已设置' : '未设置' }}</span>
          </div>
          <div class="col-login">
            <strong>{{ formatDateTime(row.last_login_at) }}</strong>
            <small>创建：{{ formatDate(row.create_time) }}</small>
          </div>
          <div class="col-status">
            <span class="status-pill" :class="row.status === 'ACTIVE' ? 'is-active' : 'is-inactive'">
              {{ row.status_label || statusLabel(row.status) }}
            </span>
          </div>
          <div class="col-actions action-buttons">
            <el-button class="edit-action" disabled>编辑</el-button>
            <el-button class="qr-action" disabled>登录码</el-button>
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

function avatarText(row) {
  return String(row.display_name || row.staff_no || '人').slice(0, 1)
}

function avatarColor(row) {
  const palette = ['#1d8fb8', '#219f7a', '#a66a1d', '#8a6be8']
  const seed = String(row.staff_no || row.id || '').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return palette[seed % palette.length]
}
</script>

<style scoped>
.staff-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}

.admin-header,
.panel-head,
.panel-toolbar {
  display: flex;
  align-items: center;
}

.admin-header {
  justify-content: space-between;
  gap: 18px;
}

.title-block p,
.panel-head span {
  margin: 6px 0 0;
  color: #79acd0;
  font-size: 13px;
}

h2,
h3 {
  margin: 0;
  color: #f3f8fd;
  letter-spacing: 0;
}

h2 {
  font-size: 25px;
  line-height: 1.1;
}

h3 {
  font-size: 18px;
}

.data-panel {
  margin-top: 16px;
  padding: 18px 22px;
  border: 1px solid rgba(96, 151, 191, .18);
  border-radius: 8px;
  background: #0b1d30;
}

.staff-toolbar-card {
  min-height: 82px;
  display: flex;
  align-items: center;
}

.staff-toolbar-card .panel-head {
  width: 100%;
  justify-content: space-between;
  gap: 18px;
}

.panel-toolbar {
  flex: 0 0 auto;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: nowrap;
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
  min-height: 36px;
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
  overflow: hidden;
}

.staff-list {
  min-width: 1180px;
  overflow: hidden;
  border-radius: 8px 8px 0 0;
  background: #081b2d;
}

.staff-list-header-row,
.staff-row {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(160px, .8fr) minmax(170px, .8fr) minmax(210px, 1fr) minmax(180px, .9fr) 100px 150px;
  align-items: center;
  gap: 16px;
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
  min-height: 78px;
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
.col-group,
.col-wechat,
.col-account,
.col-login,
.col-status,
.col-actions {
  min-width: 0;
  display: grid;
  gap: 6px;
  justify-items: center;
  text-align: center;
}

.name-cell {
  grid-template-columns: 42px minmax(0, 1fr);
  justify-items: start;
  text-align: left;
}

.avatar {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #f6fcff;
  font-weight: 800;
}

strong {
  overflow: hidden;
  max-width: 100%;
  color: #f3f8fd;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

small {
  overflow: hidden;
  max-width: 100%;
  color: #8fa8bf;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bind-pill,
.status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-width: 62px;
  height: 26px;
  justify-content: center;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}

.bind-pill.is-bound,
.status-pill.is-active {
  border: 1px solid rgba(50, 210, 138, .36);
  color: #7df2b2;
  background: rgba(34, 161, 104, .22);
}

.bind-pill.is-unbound,
.status-pill.is-inactive {
  border: 1px solid rgba(255, 122, 146, .34);
  color: #ff8fa3;
  background: rgba(177, 54, 86, .22);
}

.account-cell {
  display: flex;
  justify-content: center;
  gap: 6px;
}

.account-cell span {
  max-width: 96px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  overflow: hidden;
  border: 1px solid rgba(74, 153, 191, .20);
  border-radius: 5px;
  color: #d7e8f8;
  background: rgba(7, 31, 49, .72);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-cell b {
  flex: 0 0 auto;
  color: #7fa4bc;
  font-weight: 700;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.edit-action,
.qr-action {
  min-width: 62px;
  height: 34px;
  margin-left: 0;
  border-radius: 6px;
  color: #cde8f8;
  background: #103954;
  border-color: rgba(52, 142, 182, .42);
}

.empty-list {
  min-height: 180px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #8fa8bf;
}

.empty-list strong {
  color: #d7e8f8;
  font-size: 16px;
}

.list-pagination {
  padding: 14px 0;
  justify-content: center;
  background: #081b2d;
}

.list-pagination :deep(.el-pager li),
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next) {
  border: 1px solid rgba(75, 137, 181, .34);
  border-radius: 5px;
  color: #8fb6d0;
  background: #0b2740;
}

.list-pagination :deep(.el-pager li.is-active) {
  color: #ffffff;
  background: #2e9bdd;
}

@media (max-width: 1280px) {
  .staff-page {
    overflow-x: auto;
  }
}
</style>
