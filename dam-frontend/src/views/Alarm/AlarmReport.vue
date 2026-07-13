<template>
  <div class="report-page" v-if="alarm">
    <!-- 报告内容 -->
    <div class="report-container">
      <!-- 标题区域 -->
      <div class="report-hero">
        <button class="back-btn" @click="$emit('close')">
          <el-icon><ArrowLeft /></el-icon>
          <span>返回告警列表</span>
        </button>
        <div class="hero-icon">
          <el-icon :size="28"><Notebook /></el-icon>
        </div>
        <h1 class="hero-title">分析报告</h1>
        <div class="hero-meta">
          <span class="level-tag" :class="'level-' + alarm.alarm_level">
            {{ levelText(alarm.alarm_level) }}
          </span>
          <span class="type-tag" :class="'type-' + alarm.alarm_type">
            {{ typeText(alarm.alarm_type) }}
          </span>
          <span class="status-tag" :class="alarm.handle_status === 1 ? 'handled' : 'unhandled'">
            {{ alarm.handle_status === 1 ? '已处理' : '待处理' }}
          </span>
          <span class="meta-time">{{ formatTime(alarm.alarm_time) }}</span>
        </div>
      </div>

      <!-- 双栏布局 -->
      <div class="report-grid">
        <!-- 左栏：环境数据 -->
        <div class="report-left">
          <div class="card">
            <div class="card-header">
              <el-icon><DataLine /></el-icon>
              <span>环境监测数据</span>
            </div>
            <div class="card-body">
              <div class="data-list">
                <div class="data-item" v-for="(item, index) in sensorDataList" :key="index">
                  <div class="data-icon" :style="{ background: item.color + '15', color: item.color }">
                    <el-icon><component :is="item.icon" /></el-icon>
                  </div>
                  <div class="data-info">
                    <div class="data-label">{{ item.label }}</div>
                    <div class="data-value">{{ item.value }} <span class="data-unit">{{ item.unit }}</span></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 处理记录卡片 -->
          <div class="card" v-if="alarm.handle_status === 1">
            <div class="card-header">
              <el-icon><Finished /></el-icon>
              <span>处理记录</span>
            </div>
            <div class="card-body">
              <div class="handle-record">
                <div class="record-item">
                  <span class="record-label">处理人</span>
                  <span class="record-value">{{ alarm.handle_user || '--' }}</span>
                </div>
                <div class="record-item">
                  <span class="record-label">处理时间</span>
                  <span class="record-value">{{ formatTime(alarm.handle_time) }}</span>
                </div>
                <div class="record-item">
                  <span class="record-label">处理备注</span>
                  <span class="record-value">{{ alarm.handle_remark || '--' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：分析内容 -->
        <div class="report-right">
          <div class="card analysis-card">
            <div class="card-header">
              <el-icon><Notebook /></el-icon>
              <span>AI 智能分析</span>
            </div>
            <div class="card-body">
              <div class="analysis-content" v-html="formattedContent"></div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  ArrowLeft, DataLine, Notebook,
  Finished, Warning, Sunny, Cloudy, Monitor
} from '@element-plus/icons-vue'

const props = defineProps({
  alarm: { type: Object, required: true }
})

defineEmits(['close'])

// 提取告警标题：取 alarm_content 第一行，去掉 Qwen 分析部分
const alarmTitle = computed(() => {
  const content = props.alarm?.alarm_content || ''
  const firstLine = content.replace(/\\n/g, '\n').split('\n')[0].trim()
  return firstLine || '大坝安全监测分析报告'
})

// 解析传感器数据
const sensorDataList = computed(() => {
  const data = []
  const content = (props.alarm?.alarm_content || '').replace(/\\n/g, '\n')

  const windMatch = content.match(/风速[：:]*\s*([\d.]+)\s*m\/s/) || content.match(/([\d.]+)\s*m\/s/)
  const tempMatch = content.match(/温度[：:]*\s*([\d.]+)\s*℃/) || content.match(/([\d.]+)\s*℃/)
  const humidMatch = content.match(/湿度[：:]*\s*([\d.]+)\s*%/) || content.match(/([\d.]+)\s*%/)
  const rainMatch = content.match(/雨量[：:]*\s*([\d.]+)\s*mm/) || content.match(/([\d.]+)\s*mm/)

  if (windMatch) data.push({ label: '风速', value: windMatch[1], unit: 'm/s', icon: 'Sunny', color: '#409eff' })
  if (tempMatch) data.push({ label: '温度', value: tempMatch[1], unit: '℃', icon: 'Monitor', color: '#e6a23c' })
  if (humidMatch) data.push({ label: '湿度', value: humidMatch[1], unit: '%', icon: 'Cloudy', color: '#67c23a' })
  if (rainMatch) data.push({ label: '雨量', value: rainMatch[1], unit: 'mm', icon: 'Warning', color: '#f56c6c' })

  if (data.length === 0) {
    data.push(
      { label: '风速', value: '--', unit: 'm/s', icon: 'Sunny', color: '#409eff' },
      { label: '温度', value: '--', unit: '℃', icon: 'Monitor', color: '#e6a23c' },
      { label: '湿度', value: '--', unit: '%', icon: 'Cloudy', color: '#67c23a' }
    )
  }

  return data
})

// 格式化分析内容
const formattedContent = computed(() => {
  let content = props.alarm?.alarm_content || ''
  content = content.replace(/\\n/g, '\n')

  const qwenMatch = content.match(/Qwen分析结果[：:]\s*([\s\S]*)/)
  if (qwenMatch) {
    content = qwenMatch[1]
  }

  content = content
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
    .replace(/^---$/gm, '<hr>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, function(match) {
      return '<ul>' + match + '</ul>'
    })
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')

  if (!content.startsWith('<')) {
    content = '<p>' + content + '</p>'
  }

  return content
})

const formatTime = (t) => {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

const levelText = (level) => {
  if (level === 3) return '紧急'
  if (level === 2) return '中等'
  return '低'
}

const typeText = (type) => {
  const map = { threshold: '阈值触发', ai: 'AI检测', manual: '手动触发' }
  return map[type] || type || '--'
}
</script>

<style scoped>
.report-page {
  min-height: 100vh;
  background: #0a1929;
  color: #e0f0ff;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: rgba(0, 200, 255, 0.08);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 6px;
  color: #00c8ff;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 20px;
  position: absolute;
  left: 0;
}

.back-btn:hover {
  background: rgba(0, 200, 255, 0.15);
  border-color: rgba(0, 200, 255, 0.3);
  color: #40d4ff;
}

/* 报告容器 */
.report-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* 标题区域 */
.report-hero {
  text-align: center;
  padding: 32px 0;
  margin-bottom: 24px;
  position: relative;
}

.hero-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  background: rgba(0, 168, 255, 0.12);
  border: 1px solid rgba(0, 168, 255, 0.25);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #00a8ff;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 16px 0;
  letter-spacing: 4px;
  background: linear-gradient(135deg, #00c8ff, #e0f0ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 13px;
}

/* 标签样式（与告警列表统一） */
.level-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.level-3 { background: rgba(245, 108, 108, 0.2); color: #f56c6c; }
.level-2 { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
.level-1 { background: rgba(144, 147, 153, 0.2); color: #909399; }

.type-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.type-ai { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }
.type-threshold { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }
.type-manual { background: rgba(144, 147, 153, 0.15); color: #909399; }

.status-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.status-tag.handled { background: rgba(103, 194, 58, 0.15); color: #67c23a; }
.status-tag.unhandled { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }

.meta-time {
  font-size: 13px;
  color: rgba(224, 240, 255, 0.5);
}

/* 双栏布局 */
.report-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 24px;
}

/* 卡片样式 */
.card {
  background: rgba(0, 40, 60, 0.8);
  border: 1px solid rgba(0, 200, 255, 0.12);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  background: rgba(0, 60, 90, 0.5);
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
  font-size: 15px;
  font-weight: 600;
  color: #e0f0ff;
}

.card-body {
  padding: 20px;
}

/* 数据列表 */
.data-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.data-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
  background: rgba(0, 20, 40, 0.5);
  border-radius: 8px;
}

.data-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.data-label {
  font-size: 13px;
  color: rgba(224, 240, 255, 0.5);
  margin-bottom: 4px;
}

.data-value {
  font-size: 22px;
  font-weight: 700;
  color: #e0f0ff;
}

.data-unit {
  font-size: 14px;
  font-weight: 400;
  color: rgba(224, 240, 255, 0.5);
}

/* 处理记录 */
.handle-record {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.06);
}

.record-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.record-label {
  font-size: 13px;
  color: rgba(224, 240, 255, 0.5);
}

.record-value {
  font-size: 14px;
  color: #e0f0ff;
}

/* 分析内容 */
.analysis-card .card-body {
  min-height: 400px;
}

.analysis-content {
  font-size: 15px;
  line-height: 1.8;
  color: rgba(224, 240, 255, 0.85);
}

.analysis-content :deep(h1),
.analysis-content :deep(h2),
.analysis-content :deep(h3) {
  color: #e0f0ff;
  margin: 24px 0 12px 0;
}

.analysis-content :deep(h1) { font-size: 20px; }
.analysis-content :deep(h2) { font-size: 18px; }
.analysis-content :deep(h3) { font-size: 16px; }

.analysis-content :deep(strong) {
  color: #00c8ff;
  font-weight: 600;
}

.analysis-content :deep(ul),
.analysis-content :deep(ol) {
  padding-left: 20px;
  margin: 12px 0;
}

.analysis-content :deep(li) {
  margin: 8px 0;
  line-height: 1.6;
}

.analysis-content :deep(hr) {
  border: none;
  border-top: 1px solid rgba(0, 200, 255, 0.1);
  margin: 24px 0;
}

.analysis-content :deep(p) {
  margin: 12px 0;
}
</style>
