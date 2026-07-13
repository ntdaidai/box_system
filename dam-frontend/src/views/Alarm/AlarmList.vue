<template>
  <div>
    <!-- 报告详情页 -->
    <AlarmReport
      v-if="reportVisible"
      :alarm="currentAlarm"
      @close="reportVisible = false"
    />

    <!-- 告警列表页 -->
    <div class="alarm-page" v-else>
    <!-- 顶部统计卡片 -->
    <div class="alarm-stats-row">
      <div class="alarm-stat-card" v-for="stat in statCards" :key="stat.label">
        <div class="stat-icon" :style="{ background: stat.color + '25' }">
          <el-icon :size="22" :style="{ color: stat.color }"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 + 表格 -->
    <div class="alarm-panel">
      <div class="panel-header">
        <div class="filter-group">
          <select v-model="filterLevel" class="custom-select">
            <option value="">全部级别</option>
            <option value="3">紧急</option>
            <option value="2">中等</option>
            <option value="1">低</option>
          </select>
          <select v-model="filterType" class="custom-select">
            <option value="">全部类型</option>
            <option value="threshold">阈值触发</option>
            <option value="ai">AI检测</option>
            <option value="manual">手动触发</option>
          </select>
          <select v-model="filterStatus" class="custom-select">
            <option value="">全部状态</option>
            <option value="0">未处理</option>
            <option value="1">已处理</option>
          </select>
        </div>
        <button class="refresh-btn" @click="fetchAlarms">
          <el-icon><Refresh /></el-icon> 刷新
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="filteredList.length === 0" class="empty-container">
        <el-icon :size="48" color="rgba(224,240,255,0.3)"><Bell /></el-icon>
        <div class="empty-text">暂无告警记录</div>
      </div>

      <!-- 告警列表 -->
      <div v-else class="alarm-list">
        <div class="alarm-list-header">
          <div class="col-time">告警时间</div>
          <div class="col-level">级别</div>
          <div class="col-type">类型</div>
          <div class="col-content">告警内容</div>
          <div class="col-status">状态</div>
          <div class="col-action">操作</div>
        </div>
        <div
          v-for="row in filteredList"
          :key="row.id"
          class="alarm-item"
          :class="{ 'is-unhandled': row.handle_status === 0 }"
        >
          <div class="col-time">{{ formatTime(row.alarm_time) }}</div>
          <div class="col-level">
            <span class="level-tag" :class="'level-' + row.alarm_level">
              {{ levelText(row.alarm_level) }}
            </span>
          </div>
          <div class="col-type">
            <span class="type-tag" :class="'type-' + row.alarm_type">
              {{ typeText(row.alarm_type) }}
            </span>
          </div>
          <div class="col-content">
            <span class="report-link" @click="openReport(row)">查看分析报告</span>
          </div>
          <div class="col-status">
            <span class="status-tag" :class="row.handle_status === 1 ? 'handled' : 'unhandled'">
              {{ row.handle_status === 1 ? '已处理' : '未处理' }}
            </span>
          </div>
          <div class="col-action">
            <button
              v-if="row.handle_status === 0"
              class="handle-btn"
              @click="openHandleDialog(row)"
            >
              处理
            </button>
            <span v-else class="handled-user">{{ row.handle_user || '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination-bar">
        <span class="pagination-info">共 {{ total }} 条</span>
        <div class="pagination-btns">
          <button
            class="page-btn"
            :disabled="currentPage <= 1"
            @click="currentPage--; fetchAlarms()"
          >
            &lt;
          </button>
          <span class="page-current">{{ currentPage }}</span>
          <button
            class="page-btn"
            :disabled="currentPage * pageSize >= total"
            @click="currentPage++; fetchAlarms()"
          >
            &gt;
          </button>
        </div>
      </div>
    </div>

    <!-- 处理告警对话框 -->
    <div v-if="handleDialogVisible" class="dialog-overlay" @click.self="handleDialogVisible = false">
      <div class="dialog-box">
        <div class="dialog-header">
          <div class="dialog-title">
            <el-icon><Check /></el-icon>
            <span>处理告警</span>
          </div>
          <button class="dialog-close" @click="handleDialogVisible = false">
            <el-icon><Close /></el-icon>
          </button>
        </div>
        <div class="dialog-body">
          <div class="alarm-info-card">
            <div class="info-badges">
              <span class="level-tag" :class="'level-' + currentAlarm.alarm_level">
                {{ levelText(currentAlarm.alarm_level) }}
              </span>
              <span class="type-tag" :class="'type-' + currentAlarm.alarm_type">
                {{ typeText(currentAlarm.alarm_type) }}
              </span>
              <span class="time-tag">{{ formatTime(currentAlarm.alarm_time) }}</span>
            </div>
            <div class="info-content">{{ currentAlarm.alarm_content }}</div>
          </div>
          <div class="remark-section">
            <div class="remark-label">处理备注</div>
            <textarea
              v-model="handleRemark"
              class="remark-input"
              rows="4"
              placeholder="请输入处理情况说明..."
              maxlength="200"
            ></textarea>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="handleDialogVisible = false">取消</button>
          <button class="confirm-btn" :disabled="handleLoading" @click="submitHandle">
            <el-icon v-if="!handleLoading"><Check /></el-icon>
            <span>{{ handleLoading ? '处理中...' : '确认处理' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, Warning, WarningFilled, CircleCheck, Refresh, Check, Close } from '@element-plus/icons-vue'
import { getAlarmList, getAlarmStatistics, handleAlarm as handleAlarmApi } from '@/api/alarm'
import AlarmReport from './AlarmReport.vue'

// 路由
const route = useRoute()
const router = useRouter()

// 报告页面
const reportVisible = ref(false)

// 统计数据
const stats = ref({ total: 0, high_level: 0, unhandled: 0, handled: 0 })

// 列表数据
const allAlarms = ref([])
const loading = ref(true)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

// 筛选条件
const filterLevel = ref('')
const filterType = ref('')
const filterStatus = ref('')

// 处理对话框
const handleDialogVisible = ref(false)
const currentAlarm = ref({})
const handleRemark = ref('')
const handleLoading = ref(false)

// 统计卡片
const statCards = computed(() => [
  { label: '累计告警', value: stats.value.total, icon: Bell, color: '#e6a23c' },
  { label: '紧急告警', value: stats.value.high_level, icon: WarningFilled, color: '#f56c6c' },
  { label: '未处理', value: stats.value.unhandled, icon: Warning, color: '#e6a23c' },
  { label: '已处理', value: stats.value.handled, icon: CircleCheck, color: '#67c23a' },
])

// 前端筛选
const filteredList = computed(() => {
  let list = allAlarms.value
  if (filterLevel.value !== '') {
    list = list.filter(item => item.alarm_level === Number(filterLevel.value))
  }
  if (filterType.value !== '') {
    list = list.filter(item => item.alarm_type === filterType.value)
  }
  if (filterStatus.value !== '') {
    list = list.filter(item => item.handle_status === Number(filterStatus.value))
  }
  return list
})

// 获取统计数据
const fetchStats = async () => {
  try {
    const res = await getAlarmStatistics()
    if (res.code === 200) {
      stats.value = res.data
    }
  } catch (e) {
    console.error('获取告警统计失败', e)
  }
}

// 获取告警列表
const fetchAlarms = async () => {
  loading.value = true
  try {
    const res = await getAlarmList({ page_num: currentPage.value, page_size: pageSize.value })
    if (res.code === 200) {
      allAlarms.value = res.data.records || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('获取告警列表失败', e)
  } finally {
    loading.value = false
  }
}

// 打开处理对话框
const openHandleDialog = (row) => {
  currentAlarm.value = row
  handleRemark.value = '已确认并处理'
  handleDialogVisible.value = true
}

// 打开报告详情
const openReport = (row) => {
  currentAlarm.value = row
  reportVisible.value = true
}

// 提交处理
const submitHandle = async () => {
  handleLoading.value = true
  try {
    const res = await handleAlarmApi(currentAlarm.value.id, {
      handle_status: 1,
      handle_remark: handleRemark.value || '已处理',
    })
    if (res.code === 200) {
      handleDialogVisible.value = false
      await Promise.all([fetchStats(), fetchAlarms()])
    }
  } catch (e) {
    console.error('处理失败', e)
  } finally {
    handleLoading.value = false
  }
}

// 格式化时间
const formatTime = (t) => {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

// 级别文字
const levelText = (level) => {
  if (level === 3) return '紧急'
  if (level === 2) return '中等'
  return '低'
}

// 类型文字
const typeText = (type) => {
  const map = { threshold: '阈值触发', ai: 'AI检测', manual: '手动触发' }
  return map[type] || type || '--'
}

// 初始化
onMounted(async () => {
  fetchStats()
  await fetchAlarms()

  // 从 Dashboard 点击"查看分析报告"跳转过来，自动打开报告
  const reportId = route.query.report
  if (reportId) {
    const target = allAlarms.value.find(a => String(a.id) === String(reportId))
    if (target) {
      currentAlarm.value = target
      reportVisible.value = true
    }
    // 清除 query 参数，避免刷新重复打开
    router.replace({ path: '/alarm/list' })
  }
})
</script>

<style scoped>
.alarm-page {
  padding: 20px;
  min-height: 100%;
  background: #0a1929;
  color: #e0f0ff;
}

/* 统计卡片 */
.alarm-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
  max-width: 1200px;
  margin-left: auto;
  margin-right: auto;
}

.alarm-stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: rgba(0, 50, 80, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(0, 200, 255, 0.15);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: rgba(224, 240, 255, 0.6);
  margin-top: 4px;
}

/* 面板 */
.alarm-panel {
  max-width: 1200px;
  margin: 0 auto;
  background: rgba(0, 50, 80, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(0, 200, 255, 0.15);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
}

.filter-group {
  display: flex;
  gap: 12px;
}

/* 自定义下拉框 */
.custom-select {
  padding: 8px 12px;
  background: rgba(0, 30, 50, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 6px;
  color: #e0f0ff;
  font-size: 13px;
  cursor: pointer;
  outline: none;
  min-width: 100px;
}

.custom-select:focus {
  border-color: #00a8ff;
  box-shadow: 0 0 0 2px rgba(0, 168, 255, 0.2);
}

.custom-select option {
  background: #0d2137;
  color: #e0f0ff;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(0, 168, 255, 0.3);
  border: 1px solid rgba(0, 168, 255, 0.5);
  border-radius: 6px;
  color: #e0f0ff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background: rgba(0, 168, 255, 0.5);
}

/* 加载状态 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  background: rgba(0, 30, 50, 0.5);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(0, 200, 255, 0.2);
  border-top-color: #00a8ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 16px;
  color: rgba(224, 240, 255, 0.6);
  font-size: 14px;
}

/* 空状态 */
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  background: rgba(0, 30, 50, 0.5);
}

.empty-text {
  margin-top: 16px;
  color: rgba(224, 240, 255, 0.4);
  font-size: 14px;
}

/* 告警列表 */
.alarm-list-header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: rgba(0, 100, 150, 0.3);
  font-size: 13px;
  font-weight: 600;
  color: rgba(224, 240, 255, 0.7);
}

.alarm-item {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.06);
  transition: background 0.2s;
}

.alarm-item:hover {
  background: rgba(0, 200, 255, 0.08);
}

.alarm-item.is-unhandled {
  background: rgba(245, 108, 108, 0.05);
}

.col-time {
  flex: 1;
  font-size: 13px;
  color: rgba(224, 240, 255, 0.7);
  text-align: center;
}

.col-level {
  flex: 1;
  text-align: center;
}

.col-type {
  flex: 1;
  text-align: center;
}

.col-content {
  flex: 1;
  font-size: 13px;
  text-align: center;
}

.report-link {
  color: #00a8ff;
  cursor: pointer;
  transition: all 0.2s;
}

.report-link:hover {
  color: #40c0ff;
  text-decoration: underline;
}

.col-status {
  flex: 1;
  text-align: center;
}

.col-action {
  flex: 1;
  text-align: center;
}

/* 标签样式 */
.level-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.level-3 { background: rgba(245, 108, 108, 0.2); color: #f56c6c; }
.level-2 { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
.level-1 { background: rgba(144, 147, 153, 0.2); color: #909399; }

.type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.type-ai { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }
.type-threshold { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }
.type-manual { background: rgba(144, 147, 153, 0.15); color: #909399; }

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-tag.handled { background: rgba(103, 194, 58, 0.15); color: #67c23a; }
.status-tag.unhandled { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }

.handle-btn {
  padding: 4px 12px;
  background: rgba(0, 168, 255, 0.3);
  border: 1px solid rgba(0, 168, 255, 0.5);
  border-radius: 4px;
  color: #e0f0ff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.handle-btn:hover {
  background: rgba(0, 168, 255, 0.5);
}

.handled-user {
  font-size: 12px;
  color: rgba(224, 240, 255, 0.5);
}

/* 分页 */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid rgba(0, 200, 255, 0.1);
}

.pagination-info {
  font-size: 13px;
  color: rgba(224, 240, 255, 0.6);
}

.pagination-btns {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-btn {
  width: 32px;
  height: 32px;
  background: rgba(0, 50, 80, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 6px;
  color: #e0f0ff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  background: rgba(0, 168, 255, 0.3);
  border-color: #00a8ff;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-current {
  font-size: 14px;
  font-weight: 600;
  color: #00a8ff;
  min-width: 24px;
  text-align: center;
}

/* 对话框 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.dialog-box {
  width: 520px;
  max-height: 80vh;
  background: linear-gradient(180deg, #0d2137 0%, #0a1929 100%);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: rgba(0, 60, 90, 0.5);
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
}

.dialog-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 600;
  color: #e0f0ff;
}

.dialog-title .el-icon {
  color: #00a8ff;
}

.dialog-close {
  width: 32px;
  height: 32px;
  background: rgba(0, 200, 255, 0.1);
  border: 1px solid rgba(0, 200, 255, 0.2);
  color: rgba(224, 240, 255, 0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s;
}

.dialog-close:hover {
  background: rgba(245, 108, 108, 0.2);
  border-color: rgba(245, 108, 108, 0.4);
  color: #f56c6c;
}

.dialog-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.alarm-info-card {
  background: rgba(0, 40, 60, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.12);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 24px;
}

.info-badges {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.info-content {
  color: rgba(224, 240, 255, 0.85);
  font-size: 14px;
  line-height: 1.7;
  max-height: 120px;
  overflow-y: auto;
}

.time-tag {
  font-size: 12px;
  color: rgba(224, 240, 255, 0.5);
  margin-left: auto;
}

.remark-section {
  margin-top: 4px;
}

.remark-label {
  color: #e0f0ff;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

.remark-input {
  width: 100%;
  padding: 14px 16px;
  background: rgba(0, 20, 40, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 10px;
  color: #e0f0ff;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  transition: all 0.2s;
}

.remark-input:focus {
  border-color: #00a8ff;
  box-shadow: 0 0 0 3px rgba(0, 168, 255, 0.15);
}

.remark-input::placeholder {
  color: rgba(224, 240, 255, 0.25);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  background: rgba(0, 40, 60, 0.5);
  border-top: 1px solid rgba(0, 200, 255, 0.1);
}

.cancel-btn, .confirm-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn {
  background: transparent;
  border: 1px solid rgba(0, 200, 255, 0.25);
  color: rgba(224, 240, 255, 0.8);
}

.cancel-btn:hover {
  background: rgba(0, 200, 255, 0.1);
  border-color: rgba(0, 200, 255, 0.4);
}

.confirm-btn {
  background: linear-gradient(135deg, #00a8ff 0%, #0066cc 100%);
  border: none;
  color: #fff;
}

.confirm-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 168, 255, 0.3);
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
