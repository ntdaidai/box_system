<template>
  <div class="unified-sensors">
    <section class="live-carousel">
      <div class="live-grid">
        <button
          v-for="card in liveCards"
          :key="card.key"
          type="button"
          class="live-card"
          :class="[card.statusClass, { active: activeCardKey === card.key }]"
          @click="selectCard(card)"
        >
          <div class="card-head">
            <span class="card-title">
              <i class="card-accent" :class="card.key"></i>
              {{ card.title }}
            </span>
            <span v-if="card.key === 'wind'" class="wind-head-meta">
              <span class="card-state">{{ card.state }}</span>
            </span>
            <span v-else class="card-state">{{ card.state }}</span>
          </div>
          <div v-if="card.key === 'wind'" class="wind-card-body">
            <div class="wind-primary metric-cell">
              <strong>{{ card.metrics[0].value }}</strong>
              <span>{{ card.metrics[0].label }}</span>
            </div>
            <div class="wind-direction metric-cell">
              <div class="wind-direction-value">
                <strong>{{ card.directionText }}</strong>
                <span class="mini-compass" aria-hidden="true">
                  <b class="mini-n">N</b>
                  <b class="mini-e">E</b>
                  <b class="mini-s">S</b>
                  <b class="mini-w">W</b>
                  <i :style="{ transform: `translate(-50%, -50%) rotate(${card.angle}deg)` }"></i>
                </span>
              </div>
              <span>{{ card.metrics[1].label }}</span>
            </div>
          </div>
          <div v-else class="metric-row" :class="{ 'metric-columns': card.metrics.length > 2 }">
            <div v-for="metric in card.metrics" :key="metric.label" class="metric-cell">
              <strong>{{ metric.value }}</strong>
              <span>{{ metric.label }}</span>
            </div>
          </div>
          <div class="card-update">{{ card.updatedAgo }}</div>
          <div class="today-strip">
            <span v-for="item in card.todayInfo" :key="item.label">
              {{ item.label }} {{ item.value }}
            </span>
          </div>
        </button>
      </div>
    </section>

    <section class="yesterday-summary">
      <div class="yesterday-head">
        <h3>昨日摘要</h3>
        <span>{{ yesterdayLabel }}</span>
      </div>
      <div class="yesterday-grid">
        <div v-for="item in yesterdaySummary" :key="item.key" class="yesterday-card">
          <div class="yesterday-card-title">
            <span class="sensor-dot" :class="item.key"></span>
            <strong>{{ item.title }}</strong>
          </div>
          <div class="yesterday-main">
            <span>{{ item.primaryLabel }}</span>
            <strong>{{ item.primaryValue }}</strong>
          </div>
          <div class="yesterday-stat-pills">
            <span v-for="stat in item.stats" :key="stat.label">
              <small>{{ stat.label }}</small>
              <b>{{ stat.value }}</b>
            </span>
          </div>
          <div class="yesterday-change" :class="item.changeClass">
            <span>{{ item.changeLabel }}</span>
            <strong>{{ item.change }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="history-panel">
      <div class="history-header">
        <div class="history-title">
          <h3>历史记录</h3>
        </div>
      </div>

      <div class="history-nav">
        <div class="history-tabs" role="tablist" aria-label="传感器历史记录">
          <button
            v-for="tab in historyTabs"
            :key="tab.key"
            type="button"
            role="tab"
            :aria-selected="activeHistoryTab === tab.key"
            :class="{ active: activeHistoryTab === tab.key }"
            @click="selectHistoryTab(tab.key)"
          >
            <span class="sensor-dot" :class="tab.key"></span>{{ tab.label }}
          </button>
        </div>
        <div class="history-controls">
          <el-popover
            placement="bottom-end"
            trigger="click"
            width="360"
            popper-class="sensor-export-popover"
          >
            <template #reference>
              <button type="button" class="export-button">
                <el-icon><Download /></el-icon>
                导出数据
              </button>
            </template>
            <div class="export-panel">
              <div class="export-title">导出按天统计表</div>
              <div class="export-date-row">
                <label class="export-date-field">
                  <span>开始日期</span>
                  <input
                    type="date"
                    :value="exportRange?.[0] || ''"
                    @input="setExportRangeDate(0, $event.target.value)"
                  />
                </label>
                <span class="export-date-separator">-</span>
                <label class="export-date-field">
                  <span>结束日期</span>
                  <input
                    type="date"
                    :value="exportRange?.[1] || ''"
                    @input="setExportRangeDate(1, $event.target.value)"
                  />
                </label>
              </div>
              <button
                type="button"
                class="export-confirm"
                :disabled="exportLoading"
                @click="exportDailyCsv"
              >
                {{ exportLoading ? '导出中...' : '生成表格' }}
              </button>
            </div>
          </el-popover>
          <button
            type="button"
            class="period-button"
            :class="{ active: historyMode === 'recent24h' }"
            @click="selectRecent24h"
          >
            近24小时
          </button>
          <button
            type="button"
            class="period-button"
            :class="{ active: historyMode === 'overview' }"
            @click="selectOverview"
          >
            总览
          </button>
          <div class="calendar-controls" :class="{ active: historyMode === 'calendar' }" @click.capture="activateCalendarMode">
            <el-select v-model="selectedYear" class="history-select year-select" @change="onYearChange">
              <el-option
                v-for="year in yearOptions"
                :key="year"
                :label="`${year}年`"
                :value="year"
              />
            </el-select>
            <el-select v-model="selectedMonth" class="history-select month-select" @change="onMonthChange">
              <el-option label="所有月份" value="all" />
              <el-option
                v-for="month in monthOptions"
                :key="month"
                :label="`${month}月`"
                :value="month"
              />
            </el-select>
          </div>
        </div>
      </div>

      <div class="chart-shell">
        <div ref="chartRef" class="chart"></div>
        <div v-if="historyLoading" class="chart-overlay">
          <div class="spinner"></div>
          <span>正在读取历史数据...</span>
        </div>
        <div v-else-if="historyError && historyEmpty" class="chart-overlay">
          <span>{{ historyError }}</span>
          <button type="button" class="retry-button" @click="retryHistory">重新加载</button>
        </div>
        <div v-else-if="historyEmpty" class="chart-overlay hint">
          <span>当前范围暂无{{ activeTabMeta.label }}数据</span>
        </div>
        <div v-if="historyError && !historyEmpty" class="chart-error-banner">
          <span>{{ historyError }}，当前显示上一次成功加载的数据</span>
          <button type="button" @click="retryHistory">重试</button>
        </div>
      </div>

      <div v-if="activeHistoryTab === 'vibration'" class="threshold-toggles">
        <label>
          <input v-model="thresholdVisibility.warning" type="checkbox" @change="renderChart" />
          <span></span>预警线 0.10g
        </label>
        <label>
          <input v-model="thresholdVisibility.alarm" type="checkbox" @change="renderChart" />
          <span></span>报警线 0.15g
        </label>
      </div>
    </section>

    <section class="summary-grid">
      <div class="summary-card data-overview-card">
        <div class="summary-title overview">
          <h3>周期概览</h3>
          <div class="overview-title-meta">
            <span>{{ periodOverviewLabel }}</span>
            <b>{{ periodComparisonLabel }}</b>
            <el-tooltip
              :content="periodOverviewHelp"
              placement="top-end"
            >
              <button type="button" class="period-help" aria-label="周期说明">
                <el-icon><InfoFilled /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
        <div class="period-overview-grid">
          <div v-for="item in periodOverviewRows" :key="item.key" class="period-overview-card">
            <div class="period-overview-head">
              <span class="sensor-dot" :class="item.key"></span>
              <strong>{{ item.title }}</strong>
            </div>
            <div class="period-stat-list">
              <div v-for="metric in item.metrics" :key="metric.label">
                <span>{{ metric.label }}</span>
                <strong>{{ metric.value }}</strong>
              </div>
            </div>
            <span class="period-change" :class="item.changeClass">{{ item.change }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Download, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getAllSensorRealtime,
  getRainTrends,
  getTempHumidityTrends,
  getVibrationHistoryTrends,
  getVibrationProcessed,
  getVibrationTrends,
  getWindTrends,
} from '@/api/sensor'
import { calcNiceYAxisRange } from '@/utils/sensorHistory'
import * as echarts from 'echarts'

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const WARNING_RMS = 0.10
const ALARM_RMS = 0.15

const chartRef = ref(null)
const realtimeData = ref({})
const vibrationProcessed = ref({})
const activeCardKey = ref('temp_humidity')
const activeHistoryTab = ref('temperature')
const historyMode = ref('recent24h')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref('all')
const availablePeriods = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const chartData = ref({ view: 'recent24h', history: [], window: null })
const thresholdVisibility = reactive({ warning: false, alarm: false })
const exportRange = ref([])
const exportLoading = ref(false)
const nowTick = ref(Date.now())
const summaryData = reactive({
  tempRecent: [],
  rainRecent: [],
  windRecent: [],
  tempAll: [],
  rainAll: [],
  windAll: [],
  vibrationRecent: [],
  vibrationAll: [],
})

let chart = null
let realtimeTimer = null
let refreshTimer = null
let summaryTimer = null
let tickTimer = null
let resizeHandler = null
let requestSerial = 0
let isMounted = false
let lastPointerPixel = null

const dailyRowsCache = {
  temp: new Map(),
  rain: new Map(),
  wind: new Map(),
  vibration: new Map(),
}

const historyTabs = [
  { key: 'temperature', label: '气温', icon: '♨', subtitle: '温度变化趋势', unit: '℃', color: '#ff5b6e' },
  { key: 'humidity', label: '湿度', icon: '♧', subtitle: '湿度变化趋势', unit: '%', color: '#20a8ff' },
  { key: 'rain', label: '降水', icon: '◇', subtitle: '降水变化趋势', unit: 'mm', color: '#1fa6ff' },
  { key: 'wind', label: '风速', icon: '≋', subtitle: '风速变化趋势', unit: 'km/h', color: '#72cdf9' },
  { key: 'vibration', label: '振动', icon: '⌁', subtitle: '综合振动 RMS 趋势', unit: 'g', color: '#20d7ff' },
]

const activeTabMeta = computed(() => historyTabs.find(tab => tab.key === activeHistoryTab.value) || historyTabs[0])

const yearOptions = computed(() => {
  const years = availablePeriods.value.map(item => Number(item.year)).filter(Number.isFinite)
  const selected = Number(selectedYear.value)
  if (Number.isInteger(selected) && !years.includes(selected)) years.push(selected)
  return years.length ? [...new Set(years)].sort((a, b) => b - a) : [new Date().getFullYear()]
})

const monthOptions = computed(() => {
  const period = availablePeriods.value.find(item => Number(item.year) === Number(selectedYear.value))
  if (!period) return Array.from({ length: 12 }, (_, index) => index + 1)
  return (period.months || []).map(Number).filter(month => month >= 1 && month <= 12)
})

const historyEmpty = computed(() => chartValues().length === 0)

const liveCards = computed(() => {
  const temp = realtimeData.value.temp_humidity?.data || {}
  const rain = realtimeData.value.rain?.data || {}
  const wind = realtimeData.value.wind?.data || {}
  const vibration = vibrationProcessed.value || {}
  return [
    {
      key: 'temp_humidity',
      title: '温湿度',
      state: tempHumidityState(temp),
      statusClass: tempHumidityStatusClass(temp),
      note: '环境状态',
      time: formatCommTime(realtimeData.value.temp_humidity?.timestamp),
      updatedAgo: formatUpdatedAgo(realtimeData.value.temp_humidity?.timestamp),
      metrics: [
        { label: '温度', value: formatMetric(temp.temperature, 1, '℃') },
        { label: '湿度', value: formatMetric(temp.humidity, 1, '%') },
      ],
      todayInfo: tempTodayInfo(temp),
      tab: 'temperature',
    },
    {
      key: 'rain',
      title: '降水',
      state: rainState(rain),
      statusClass: rainStatusClass(rain),
      note: '瞬时 / 今日',
      time: formatCommTime(realtimeData.value.rain?.timestamp),
      updatedAgo: formatUpdatedAgo(realtimeData.value.rain?.timestamp),
      metrics: [
        { label: '瞬时', value: formatMetric(rain.instant_rain, 1, 'mm') },
        { label: '今日', value: formatMetric(rain.today_rain, 1, 'mm') },
      ],
      todayInfo: rainTodayInfo(rain),
      tab: 'rain',
    },
    {
      key: 'wind',
      title: '风速风向',
      state: windState(wind),
      statusClass: windStatusClass(wind),
      note: wind.wind_direction || '--',
      time: formatCommTime(realtimeData.value.wind?.timestamp),
      updatedAgo: formatUpdatedAgo(realtimeData.value.wind?.timestamp),
      angle: windDirectionAngle(wind),
      directionText: wind.wind_direction || '--',
      metrics: [
        { label: '风速', value: formatMetric(windSpeedKmh(wind), 1, 'km/h') },
        { label: '风向', value: wind.wind_direction || '--' },
      ],
      todayInfo: windTodayInfo(wind),
      tab: 'wind',
    },
    {
      key: 'vibration',
      title: '振动',
      state: vibration.alert_level || '正常',
      statusClass: vibrationStatusClass(vibration),
      note: 'RMS / 主频',
      time: formatCommTime(vibration.timestamp),
      updatedAgo: formatUpdatedAgo(vibration.timestamp),
      metrics: [
        { label: 'RMS', value: formatMetric(vibration.total_rms, 3, 'g') },
        { label: '主频', value: formatMetric(vibration.dominant_freq, 1, 'Hz') },
        { label: '峰值因子', value: formatMetric(vibration.crest_factor, 1, '') },
      ],
      todayInfo: vibrationTodayInfo(vibration),
      tab: 'vibration',
    },
  ]
})

const todayKey = computed(() => shanghaiDateKey(Date.now()))
const yesterdayKey = computed(() => offsetDateKey(todayKey.value, -1))
const priorDayKey = computed(() => offsetDateKey(todayKey.value, -2))

const yesterdayLabel = computed(() => displayDateKey(yesterdayKey.value))

const yesterdaySummary = computed(() => {
  const yesterday = daySnapshot(yesterdayKey.value)
  const prior = daySnapshot(priorDayKey.value)
  const tempDelta = buildDelta(tempAverage(yesterday.temp), tempAverage(prior.temp), 1, '℃')
  const humidityDelta = buildDelta(humidityAverage(yesterday.temp), humidityAverage(prior.temp), 1, '%')
  const rainDelta = buildDelta(rainTotal(yesterday.rain), rainTotal(prior.rain), 1, 'mm')
  const windDelta = buildDelta(windAverage(yesterday.wind), windAverage(prior.wind), 1, 'km/h')
  const vibrationDelta = buildDelta(vibrationAverage(yesterday.vibration), vibrationAverage(prior.vibration), 3, 'g')
  return [
    {
      key: 'temperature',
      title: '温度',
      primaryLabel: '平均',
      primaryValue: formatMetricOrZero(tempAverage(yesterday.temp), 1, '℃'),
      stats: [
        { label: '最高', value: formatMetricOrZero(tempMax(yesterday.temp), 1, '℃') },
        { label: '最低', value: formatMetricOrZero(tempMin(yesterday.temp), 1, '℃') },
      ],
      changeLabel: '较前日',
      change: tempDelta.text,
      changeClass: tempDelta.className,
    },
    {
      key: 'humidity',
      title: '湿度',
      primaryLabel: '平均',
      primaryValue: formatMetricOrZero(humidityAverage(yesterday.temp), 1, '%'),
      stats: [
        { label: '最高', value: formatMetricOrZero(humidityMax(yesterday.temp), 1, '%') },
        { label: '最低', value: formatMetricOrZero(humidityMin(yesterday.temp), 1, '%') },
      ],
      changeLabel: '较前日',
      change: humidityDelta.text,
      changeClass: humidityDelta.className,
    },
    {
      key: 'rain',
      title: '降水',
      primaryLabel: '累计',
      primaryValue: formatMetricOrZero(rainTotal(yesterday.rain), 1, 'mm'),
      stats: [
        { label: '降雨时长', value: formatRainDuration(yesterday.rain, true) },
      ],
      changeLabel: '较前日',
      change: rainDelta.text,
      changeClass: rainDelta.className,
    },
    {
      key: 'wind',
      title: '风速',
      primaryLabel: '平均',
      primaryValue: formatMetricOrZero(windAverage(yesterday.wind), 1, 'km/h'),
      stats: [
        { label: '最大风速', value: formatMetricOrZero(windMaxForSummary(yesterday.wind), 1, 'km/h') },
        { label: '主导风向', value: windDirection(yesterday.wind) },
      ],
      changeLabel: '较前日',
      change: windDelta.text,
      changeClass: windDelta.className,
    },
    {
      key: 'vibration',
      title: '振动',
      primaryLabel: '平均RMS',
      primaryValue: formatMetricOrZero(vibrationAverage(yesterday.vibration), 3, 'g'),
      stats: [
        { label: '最大值', value: formatMetricOrZero(vibrationMaxForSummary(yesterday.vibration), 3, 'g') },
      ],
      changeLabel: '较前日',
      change: vibrationDelta.text,
      changeClass: vibrationDelta.className,
    },
  ]
})

const periodOverviewLabel = computed(() => {
  const range = currentPeriodRange()
  if (historyMode.value === 'recent24h') return '当前周期: 今日'
  if (historyMode.value === 'overview') return '当前周期: 全部数据'
  if (selectedMonth.value === 'all') return `当前周期: ${selectedYear.value}年`
  return `当前周期: ${displayDateKey(range.startKey)} 至 ${displayDateKey(offsetDateKey(range.endKey, -1))}`
})

const periodComparisonLabel = computed(() => {
  if (historyMode.value === 'recent24h') return '对比: 昨日'
  if (historyMode.value === 'overview') return '不做周期对比'
  if (selectedMonth.value === 'all') return '对比: 上一年'
  return '对比: 上一月'
})

const periodOverviewHelp = computed(() => {
  if (historyMode.value === 'overview') {
    return '总览统计所有可用历史数据，只展示整体平均、累计和最大值，不计算涨跌。'
  }
  return '周期概览按当前选择范围统计；较上一周期使用相邻的同等时长范围。红色表示增加，绿色表示减少，灰色表示持平。'
})

const periodOverviewRows = computed(() => {
  const current = currentPeriodDailyRows()
  const previous = previousPeriodDailyRows()
  const windMaxValue = maximum(current.wind.map(windMaxForSummary))
  const vibrationMaxValue = maximum(current.vibration.map(vibrationMaxForSummary))
  const rows = [
    {
      key: 'temperature',
      title: '温度',
      icon: '♨',
      metrics: [
        { label: '平均值', value: formatMetricOrZero(average(current.temp.map(tempAverage)), 1, '℃') },
        { label: '最高', value: formatMetricOrZero(maximum(current.temp.map(tempMax)), 1, '℃') },
        { label: '最低', value: formatMetricOrZero(minimum(current.temp.map(tempMin)), 1, '℃') },
      ],
      changeValue: valueDelta(average(current.temp.map(tempAverage)), average(previous.temp.map(tempAverage))),
      decimals: 1,
      unit: '℃',
    },
    {
      key: 'humidity',
      title: '湿度',
      icon: '♧',
      metrics: [
        { label: '平均值', value: formatMetricOrZero(average(current.temp.map(humidityAverage)), 1, '%') },
        { label: '最高', value: formatMetricOrZero(maximum(current.temp.map(humidityMax)), 1, '%') },
        { label: '最低', value: formatMetricOrZero(minimum(current.temp.map(humidityMin)), 1, '%') },
      ],
      changeValue: valueDelta(average(current.temp.map(humidityAverage)), average(previous.temp.map(humidityAverage))),
      decimals: 1,
      unit: '%',
    },
    {
      key: 'rain',
      title: '降水',
      icon: '◇',
      metrics: [
        { label: '累计值', value: formatMetricOrZero(sum(current.rain.map(rainTotal)), 1, 'mm') },
      ],
      changeValue: valueDelta(sum(current.rain.map(rainTotal)), sum(previous.rain.map(rainTotal))),
      decimals: 1,
      unit: 'mm',
    },
    {
      key: 'wind',
      title: '风速',
      icon: '≋',
      metrics: [
        { label: '平均值', value: formatMetricOrZero(average(current.wind.map(windAverage)), 1, 'km/h') },
        { label: '最大值', value: formatMetricOrZero(windMaxValue, 1, 'km/h') },
      ],
      changeValue: valueDelta(average(current.wind.map(windAverage)), average(previous.wind.map(windAverage))),
      decimals: 1,
      unit: 'km/h',
    },
    {
      key: 'vibration',
      title: '振动',
      icon: '⌁',
      metrics: [
        { label: '平均RMS', value: formatMetricOrZero(average(current.vibration.map(vibrationAverage)), 3, 'g') },
        { label: '最大值', value: formatMetricOrZero(vibrationMaxValue, 3, 'g') },
      ],
      changeValue: valueDelta(average(current.vibration.map(vibrationAverage)), average(previous.vibration.map(vibrationAverage))),
      decimals: 3,
      unit: 'g',
    },
  ]
  return rows.map(row => ({
    ...row,
    change: formatOverviewDelta(row.changeValue, row.decimals, row.unit),
    changeClass: overviewDeltaClass(row.changeValue, row.decimals),
  }))
})

const toNumber = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatMetric = (value, decimals, unit) => {
  const numeric = toNumber(value)
  if (numeric === null) return '--'
  return `${numeric.toFixed(decimals)}${unit}`
}

const formatMetricOrZero = (value, decimals, unit) => {
  const numeric = toNumber(value)
  return `${(numeric ?? 0).toFixed(decimals)}${unit}`
}

const timestampMs = (timestamp) => {
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric) || numeric <= 0) return null
  return numeric > 1e12 ? numeric : numeric * 1000
}

const formatUpdatedAgo = (timestamp) => {
  const timeMs = timestampMs(timestamp)
  nowTick.value
  if (timeMs === null) return '暂无更新时间'
  const seconds = Math.max(0, Math.floor((Date.now() - timeMs) / 1000))
  if (seconds < 5) return '刚刚更新'
  if (seconds < 60) return `${seconds}秒前更新`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟前更新`
  const hours = Math.floor(minutes / 60)
  return `${hours}小时前更新`
}

const formatCommTime = (timestamp) => {
  const timeMs = timestampMs(timestamp)
  if (timeMs === null) return '--'
  return new Date(timeMs).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).replace(/\//g, '/')
}

const offsetDateKey = (dateKey, offsetDays) => {
  const date = new Date(`${dateKey}T00:00:00+08:00`)
  if (!Number.isFinite(date.getTime())) return ''
  date.setDate(date.getDate() + offsetDays)
  return shanghaiDateKey(date.getTime())
}

const displayDateKey = (dateKey) => {
  const date = new Date(`${dateKey}T00:00:00+08:00`)
  if (!Number.isFinite(date.getTime())) return '--'
  return date.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).replace(/\//g, '-')
}

const rowDateKey = (row) => {
  if (!row) return ''
  if (row.date) return row.date
  const timestamp = toNumber(row.timestamp)
  return timestamp === null ? '' : shanghaiDateKey(timestamp * 1000 - 1)
}

const rowsByDate = (rows = []) => {
  const map = new Map()
  rows.forEach(row => {
    const key = rowDateKey(row)
    if (key) map.set(key, row)
  })
  return map
}

const allDailyRows = () => ({
  temp: summaryData.tempAll.length ? summaryData.tempAll : summaryData.tempRecent,
  rain: summaryData.rainAll.length ? summaryData.rainAll : summaryData.rainRecent,
  wind: summaryData.windAll.length ? summaryData.windAll : summaryData.windRecent,
  vibration: summaryData.vibrationAll.length ? summaryData.vibrationAll : summaryData.vibrationRecent,
})

const daySnapshot = (dateKey) => {
  const all = allDailyRows()
  return {
    temp: rowsByDate(all.temp).get(dateKey) || null,
    rain: rowsByDate(all.rain).get(dateKey) || null,
    wind: rowsByDate(all.wind).get(dateKey) || null,
    vibration: rowsByDate(all.vibration).get(dateKey) || null,
  }
}

const dataValue = (row, fields = []) => {
  const data = row?.data || {}
  for (const field of fields) {
    const value = toNumber(data[field])
    if (value !== null) return value
  }
  return null
}

const firstTextValue = (row, fields = []) => {
  const data = row?.data || {}
  for (const field of fields) {
    const value = data[field]
    if (value !== null && value !== undefined && String(value).trim()) return String(value)
  }
  return '--'
}

const tempAverage = row => dataValue(row, ['temperature', 'temperature_avg'])
const tempMin = row => dataValue(row, ['temperature_min', 'temperature'])
const tempMax = row => dataValue(row, ['temperature_max', 'temperature'])
const humidityAverage = row => dataValue(row, ['humidity', 'humidity_avg'])
const humidityMin = row => dataValue(row, ['humidity_min', 'humidity'])
const humidityMax = row => dataValue(row, ['humidity_max', 'humidity'])
const rainTotal = row => dataValue(row, ['daily_rain', 'today_rain', 'rain_total'])
const rainDurationHours = (row) => {
  const hours = dataValue(row, ['rain_duration_hours', 'rain_hours', 'duration_hours', 'rain_duration'])
  if (hours !== null) return hours
  const minutes = dataValue(row, ['rain_duration_minutes', 'rain_minutes', 'rainy_minutes'])
  if (minutes !== null) return minutes / 60
  const seconds = dataValue(row, ['rain_duration_seconds', 'rain_seconds', 'rainy_seconds'])
  return seconds === null ? null : seconds / 3600
}
const windAverage = row => windSpeedKmh(row?.data || {})
const windMax = (row) => {
  const kmh = dataValue(row, ['wind_speed_kmh_max', 'wind_speed_max_kmh', 'max_wind_speed_kmh', 'max_wind_speed'])
  if (kmh !== null) return kmh
  const ms = dataValue(row, ['wind_speed_ms_max', 'max_wind_speed_ms'])
  return ms === null ? null : ms * 3.6
}
const windDirection = row => firstTextValue(row, ['dominant_wind_direction', 'wind_direction'])
const vibrationAverage = row => dataValue(row, ['rms', 'total_rms'])
const vibrationMax = row => dataValue(row, ['rms_max', 'total_rms_max', 'max_rms', 'peak_accel', 'peak_acceleration'])
const windMaxForSummary = row => windMax(row) ?? windAverage(row)
const vibrationMaxForSummary = row => vibrationMax(row) ?? vibrationAverage(row)

const normalizeNumbers = values => values.map(toNumber).filter(value => value !== null)
const average = values => {
  const numeric = normalizeNumbers(values)
  return numeric.length ? numeric.reduce((total, value) => total + value, 0) / numeric.length : null
}
const minimum = values => {
  const numeric = normalizeNumbers(values)
  return numeric.length ? Math.min(...numeric) : null
}
const maximum = values => {
  const numeric = normalizeNumbers(values)
  return numeric.length ? Math.max(...numeric) : null
}
const sum = values => {
  const numeric = normalizeNumbers(values)
  return numeric.length ? numeric.reduce((total, value) => total + value, 0) : null
}

const formatRange = (low, high, decimals, unit, highFirst = false) => {
  const first = highFirst ? high : low
  const second = highFirst ? low : high
  if (toNumber(first) === null && toNumber(second) === null) return '--'
  return `${formatMetric(first, decimals, unit)} ~ ${formatMetric(second, decimals, unit)}`
}

const valueDelta = (current, previous) => {
  const currentValue = toNumber(current)
  const previousValue = toNumber(previous)
  if (currentValue === null || previousValue === null) return null
  return currentValue - previousValue
}

const buildDelta = (current, previous, decimals, unit) => {
  const delta = valueDelta(current, previous)
  if (delta === null || Math.abs(delta) < 10 ** (-decimals)) {
    return { text: `持平 0${unit}`, className: 'neutral' }
  }
  return {
    text: `${delta > 0 ? '+' : ''}${delta.toFixed(decimals)}${unit}`,
    className: delta > 0 ? 'up' : 'down',
  }
}

const formatOverviewDelta = (delta, decimals, unit) => {
  if (delta === null) return '暂无对比'
  if (Math.abs(delta) < 10 ** (-decimals)) return `较上一周期 持平`
  return `较上一周期 ${delta > 0 ? '+' : ''}${delta.toFixed(decimals)}${unit}`
}

const overviewDeltaClass = (delta, decimals) => {
  if (delta === null || Math.abs(delta) < 10 ** (-decimals)) return 'neutral'
  return delta > 0 ? 'up' : 'down'
}

const formatHours = (value) => {
  const numeric = toNumber(value)
  return numeric === null ? '--' : `${numeric.toFixed(1)}h`
}

const formatRainDuration = (row, zeroFallback = false) => {
  const duration = rainDurationHours(row)
  if (duration !== null) return formatHours(duration)
  const total = rainTotal(row)
  return total === 0 || zeroFallback ? '0.0h' : '--'
}

const todayRow = sensorKey => daySnapshot(todayKey.value)[sensorKey]

const tempTodayInfo = (realtime = {}) => {
  const row = todayRow('temp')
  const tempNow = toNumber(realtime.temperature)
  const humidityNow = toNumber(realtime.humidity)
  return [
    { label: '今日温度', value: formatRange(tempMin(row) ?? tempNow, tempMax(row) ?? tempNow, 1, '℃') },
    { label: '今日湿度', value: formatRange(humidityMin(row) ?? humidityNow, humidityMax(row) ?? humidityNow, 1, '%') },
  ]
}

const rainTodayInfo = () => {
  const row = todayRow('rain')
  return [
    { label: '今日降雨时长', value: formatRainDuration(row, true) },
  ]
}

const windTodayInfo = (realtime = {}) => {
  const row = todayRow('wind')
  return [
    { label: '今日最大风速', value: formatMetric(windMaxForSummary(row) ?? windSpeedKmh(realtime), 1, 'km/h') },
    { label: '主导风向', value: windDirection(row) !== '--' ? windDirection(row) : (realtime.wind_direction || '--') },
  ]
}

const vibrationTodayInfo = (realtime = {}) => {
  const row = todayRow('vibration')
  return [
    { label: '今日最大值', value: formatMetric(vibrationMaxForSummary(row) ?? toNumber(realtime.peak_accel) ?? toNumber(realtime.total_rms), 3, 'g') },
  ]
}

const currentPeriodRange = () => {
  if (historyMode.value === 'recent24h') {
    return { startKey: todayKey.value, endKey: offsetDateKey(todayKey.value, 1) }
  }
  if (historyMode.value === 'overview') {
    return { startKey: null, endKey: null }
  }
  const year = Number(selectedYear.value)
  const month = selectedMonth.value === 'all' ? null : Number(selectedMonth.value)
  const start = new Date(`${year}-${String(month || 1).padStart(2, '0')}-01T00:00:00+08:00`)
  const end = new Date(start)
  if (month) end.setMonth(end.getMonth() + 1)
  else end.setFullYear(end.getFullYear() + 1)
  return { startKey: shanghaiDateKey(start.getTime()), endKey: shanghaiDateKey(end.getTime()) }
}

const previousPeriodRange = () => {
  const current = currentPeriodRange()
  if (!current.startKey || !current.endKey) return { startKey: null, endKey: null }
  const start = new Date(`${current.startKey}T00:00:00+08:00`)
  const end = new Date(`${current.endKey}T00:00:00+08:00`)
  const duration = end.getTime() - start.getTime()
  if (!Number.isFinite(duration) || duration <= 0) return { startKey: null, endKey: null }
  return {
    startKey: shanghaiDateKey(start.getTime() - duration),
    endKey: current.startKey,
  }
}

const rowsInDateRange = (rows = [], range) => {
  if (!range?.startKey || !range?.endKey) return rows.filter(row => rowDateKey(row))
  return rows.filter(row => {
    const key = rowDateKey(row)
    return key && key >= range.startKey && key < range.endKey
  })
}

const hasMetricRow = (rows = [], getter) => rows.some(row => getter(row) !== null)

const todayFallbackRows = () => {
  const temp = realtimeData.value.temp_humidity?.data || {}
  const rain = realtimeData.value.rain?.data || {}
  const wind = realtimeData.value.wind?.data || {}
  const vibration = vibrationProcessed.value || {}
  return {
    temp: {
      date: todayKey.value,
      data: {
        temperature: toNumber(temp.temperature),
        temperature_min: toNumber(temp.temperature),
        temperature_max: toNumber(temp.temperature),
        humidity: toNumber(temp.humidity),
        humidity_min: toNumber(temp.humidity),
        humidity_max: toNumber(temp.humidity),
      },
    },
    rain: {
      date: todayKey.value,
      data: { daily_rain: toNumber(rain.today_rain) },
    },
    wind: {
      date: todayKey.value,
      data: {
        wind_speed_kmh: windSpeedKmh(wind),
        wind_direction: wind.wind_direction,
      },
    },
    vibration: {
      date: todayKey.value,
      data: {
        rms: toNumber(vibration.total_rms),
        rms_max: toNumber(vibration.peak_accel) ?? toNumber(vibration.total_rms),
      },
    },
  }
}

const dailyRowsForRange = (range) => {
  const all = allDailyRows()
  const result = {
    temp: rowsInDateRange(all.temp, range),
    rain: rowsInDateRange(all.rain, range),
    wind: rowsInDateRange(all.wind, range),
    vibration: rowsInDateRange(all.vibration, range),
  }
  if (range?.startKey === todayKey.value && range?.endKey === offsetDateKey(todayKey.value, 1)) {
    const fallback = todayFallbackRows()
    if (!hasMetricRow(result.temp, tempAverage)) result.temp = [fallback.temp]
    if (!hasMetricRow(result.rain, rainTotal)) result.rain = [fallback.rain]
    if (!hasMetricRow(result.wind, windAverage)) result.wind = [fallback.wind]
    if (!hasMetricRow(result.vibration, vibrationAverage)) result.vibration = [fallback.vibration]
  }
  return result
}

const currentPeriodDailyRows = () => dailyRowsForRange(currentPeriodRange())
const previousPeriodDailyRows = () => historyMode.value === 'overview'
  ? { temp: [], rain: [], wind: [], vibration: [] }
  : dailyRowsForRange(previousPeriodRange())

const availableDateBounds = () => {
  const keys = Object.values(allDailyRows())
    .flat()
    .map(rowDateKey)
    .filter(Boolean)
    .sort()
  if (!keys.length) return null
  return { startKey: keys[0], endKey: keys.at(-1) }
}

const syncExportRange = () => {
  const range = currentPeriodRange()
  if (range.startKey && range.endKey) {
    exportRange.value = [range.startKey, offsetDateKey(range.endKey, -1)]
    return
  }
  const bounds = availableDateBounds()
  exportRange.value = bounds
    ? [bounds.startKey, bounds.endKey]
    : [yesterdayKey.value, todayKey.value]
}

const setExportRangeDate = (index, value) => {
  const next = [...(exportRange.value || [])]
  next[index] = value || ''
  exportRange.value = next
}

const cacheDailyRows = (kind, year, rows = []) => {
  if (!dailyRowsCache[kind]) return
  dailyRowsCache[kind].set(Number(year), rows)
}

const cacheDailyRowsByYear = (kind, rows = []) => {
  const grouped = new Map()
  rows.forEach(row => {
    const year = Number(rowDateKey(row).slice(0, 4))
    if (!Number.isInteger(year)) return
    if (!grouped.has(year)) grouped.set(year, [])
    grouped.get(year).push(row)
  })
  grouped.forEach((yearRows, year) => {
    if (!dailyRowsCache[kind]?.has(year)) cacheDailyRows(kind, year, yearRows)
  })
}

const fetchDailyRowsForYear = async (kind, year) => {
  if (dailyRowsCache[kind]?.has(Number(year))) return dailyRowsCache[kind].get(Number(year))
  const params = { view: 'calendar', year: Number(year), month: null }
  const request = kind === 'temp'
    ? getTempHumidityTrends(params)
    : kind === 'rain'
      ? getRainTrends(params)
      : kind === 'wind'
        ? getWindTrends(params)
        : fetchVibrationHistory(params)
  const res = await request
  const rows = res?.code === 200 ? (res.data?.history || []) : []
  cacheDailyRows(kind, year, rows)
  return rows
}

const yearsForInclusiveRange = (startKey, endKey) => {
  const startYear = Number(String(startKey).slice(0, 4))
  const endYear = Number(String(endKey).slice(0, 4))
  if (!Number.isInteger(startYear) || !Number.isInteger(endYear)) return []
  const years = []
  for (let year = startYear; year <= endYear; year += 1) years.push(year)
  return years
}

const exportRowsForRange = async (startKey, endKey) => {
  const years = yearsForInclusiveRange(startKey, endKey)
  const kinds = ['temp', 'rain', 'wind', 'vibration']
  const responses = await Promise.all(kinds.map(async kind => {
    const rows = (await Promise.all(years.map(year => fetchDailyRowsForYear(kind, year)))).flat()
    return [kind, rowsInDateRange(rows, { startKey, endKey: offsetDateKey(endKey, 1) })]
  }))
  return Object.fromEntries(responses)
}

const dateKeysBetween = (startKey, endKey) => {
  const keys = []
  let cursor = startKey
  while (cursor && cursor <= endKey && keys.length < 3700) {
    keys.push(cursor)
    cursor = offsetDateKey(cursor, 1)
  }
  return keys
}

const csvMetric = (value, decimals) => {
  const numeric = toNumber(value)
  return numeric === null ? '' : numeric.toFixed(decimals)
}

const csvMetricOrZero = (value, decimals) => {
  const numeric = toNumber(value)
  return (numeric ?? 0).toFixed(decimals)
}

const excelValue = (value) => {
  const text = value === null || value === undefined ? '' : String(value)
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const excelCell = (value, styleId = 'text') => {
  const numeric = toNumber(value)
  const type = styleId === 'number' && numeric !== null ? 'Number' : 'String'
  const content = type === 'Number' ? numeric : excelValue(value)
  return `<Cell ss:StyleID="${styleId}"><Data ss:Type="${type}">${content}</Data></Cell>`
}

const buildDailyWorkbook = (rowsByKind, startKey, endKey) => {
  const maps = {
    temp: rowsByDate(rowsByKind.temp),
    rain: rowsByDate(rowsByKind.rain),
    wind: rowsByDate(rowsByKind.wind),
    vibration: rowsByDate(rowsByKind.vibration),
  }
  const columns = [
    { label: '日期', width: 92, style: 'text' },
    { label: '温度平均(℃)', width: 92, style: 'number' },
    { label: '温度最高(℃)', width: 92, style: 'number' },
    { label: '温度最低(℃)', width: 92, style: 'number' },
    { label: '湿度平均(%)', width: 92, style: 'number' },
    { label: '湿度最高(%)', width: 92, style: 'number' },
    { label: '湿度最低(%)', width: 92, style: 'number' },
    { label: '降水累计(mm)', width: 92, style: 'number' },
    { label: '降雨时长(h)', width: 92, style: 'number' },
    { label: '风速平均(km/h)', width: 98, style: 'number' },
    { label: '风速最大(km/h)', width: 98, style: 'number' },
    { label: '主导风向', width: 88, style: 'text' },
    { label: '振动平均RMS(g)', width: 110, style: 'number' },
    { label: '振动最大值(g)', width: 100, style: 'number' },
    { label: '数据完整率', width: 88, style: 'text' },
  ]
  const header = `<Row>${columns.map(column => excelCell(column.label, 'header')).join('')}</Row>`
  const body = dateKeysBetween(startKey, endKey).map(dateKey => {
    const temp = maps.temp.get(dateKey)
    const rain = maps.rain.get(dateKey)
    const wind = maps.wind.get(dateKey)
    const vibration = maps.vibration.get(dateKey)
    const coverage = [
      tempAverage(temp),
      humidityAverage(temp),
      rainTotal(rain),
      windAverage(wind),
      vibrationAverage(vibration),
    ].filter(value => value !== null).length / 5
    const row = [
      dateKey,
      csvMetric(tempAverage(temp), 2),
      csvMetric(tempMax(temp), 2),
      csvMetric(tempMin(temp), 2),
      csvMetric(humidityAverage(temp), 2),
      csvMetric(humidityMax(temp), 2),
      csvMetric(humidityMin(temp), 2),
      csvMetric(rainTotal(rain), 2),
      csvMetricOrZero(rainDurationHours(rain), 2),
      csvMetric(windAverage(wind), 2),
      csvMetricOrZero(windMaxForSummary(wind), 2),
      windDirection(wind) === '--' ? '' : windDirection(wind),
      csvMetric(vibrationAverage(vibration), 4),
      csvMetricOrZero(vibrationMaxForSummary(vibration), 4),
      `${Math.round(coverage * 100)}%`,
    ]
    return `<Row>${row.map((value, index) => excelCell(value, columns[index].style)).join('')}</Row>`
  }).join('')

  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
  xmlns:o="urn:schemas-microsoft-com:office:office"
  xmlns:x="urn:schemas-microsoft-com:office:excel"
  xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Styles>
    <Style ss:ID="header">
      <Font ss:Bold="1"/>
      <Interior ss:Color="#DDEBFF" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      </Borders>
    </Style>
    <Style ss:ID="text">
      <NumberFormat ss:Format="@"/>
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
    </Style>
    <Style ss:ID="number">
      <Alignment ss:Horizontal="Right" ss:Vertical="Center"/>
    </Style>
  </Styles>
  <Worksheet ss:Name="按天统计">
    <Table>
      ${columns.map(column => `<Column ss:Width="${column.width}"/>`).join('')}
      ${header}
      ${body}
    </Table>
  </Worksheet>
</Workbook>`
}

const exportDailyCsv = async () => {
  const [startKey, endKey] = exportRange.value || []
  if (!startKey || !endKey) {
    ElMessage.warning('请选择导出日期范围')
    return
  }
  if (startKey > endKey) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return
  }
  exportLoading.value = true
  try {
    const rowsByKind = await exportRowsForRange(startKey, endKey)
    const workbook = buildDailyWorkbook(rowsByKind, startKey, endKey)
    const blob = new Blob([workbook], { type: 'application/vnd.ms-excel;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `综合传感器_按天统计_${startKey}_${endKey}.xls`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('已导出按天统计表')
  } catch (error) {
    console.warn('导出综合传感器日统计失败:', error)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exportLoading.value = false
  }
}

const tempHumidityState = (data) => {
  const temp = toNumber(data.temperature)
  const humidity = toNumber(data.humidity)
  if (temp === null && humidity === null) return '--'
  if (temp >= 35) return '高温'
  if (temp <= 0) return '低温'
  if (humidity !== null && humidity < 40) return '偏干'
  if (humidity !== null && humidity > 75) return '偏湿'
  return '适宜'
}

const tempHumidityStatusClass = data => ['高温', '低温', '偏干', '偏湿'].includes(tempHumidityState(data)) ? 'warn' : 'ok'

const rainState = (data) => {
  const value = toNumber(data.instant_rain)
  if (value === null || value <= 0) return '无雨'
  if (value < 10) return '小雨'
  if (value < 25) return '中雨'
  if (value < 50) return '大雨'
  return '暴雨'
}

const rainStatusClass = data => ['大雨', '暴雨'].includes(rainState(data)) ? 'danger' : (rainState(data) === '中雨' ? 'warn' : 'ok')

const windSpeedKmh = (data = {}) => {
  const kmh = toNumber(data.wind_speed_kmh)
  if (kmh !== null) return kmh
  const ms = toNumber(data.wind_speed_ms)
  return ms === null ? null : ms * 3.6
}

const windDirectionAngle = (data = {}) => {
  const angle = toNumber(data.wind_angle ?? data.wind_direction_angle ?? data.direction_angle)
  if (angle !== null) return angle
  const direction = String(data.wind_direction || '')
  const map = {
    北: 0,
    东北: 45,
    东: 90,
    东南: 135,
    南: 180,
    西南: 225,
    西: 270,
    西北: 315,
    东东北: 67.5,
    东东南: 112.5,
    西西南: 247.5,
    西西北: 292.5,
    北东北: 22.5,
    南东南: 157.5,
    南西南: 202.5,
    北西北: 337.5,
  }
  return map[direction] ?? 0
}

const windState = (data) => {
  const speed = windSpeedKmh(data)
  if (speed === null) return '--'
  if (speed < 22) return '微风'
  if (speed < 38) return '和风'
  if (speed < 54) return '大风'
  return '强风'
}

const windStatusClass = data => ['大风', '强风'].includes(windState(data)) ? 'warn' : 'ok'

const vibrationStatusClass = (data) => {
  if (data.alert_level === '报警') return 'danger'
  if (data.alert_level === '预警' || data.alert_level === '关注') return 'warn'
  return 'ok'
}

const queryKey = ({ tab, view, year, month }) => [tab, view, year || '', month || 'all'].join(':')

const currentQuery = () => historyMode.value === 'recent24h'
  ? { tab: activeHistoryTab.value, view: 'recent24h' }
  : historyMode.value === 'overview'
    ? { tab: activeHistoryTab.value, view: 'overview' }
    : {
      tab: activeHistoryTab.value,
      view: 'calendar',
      year: Number(selectedYear.value),
      month: selectedMonth.value === 'all' ? null : Number(selectedMonth.value),
    }

const syncAvailablePeriods = (periods = []) => {
  if (!Array.isArray(periods) || !periods.length) return
  availablePeriods.value = periods
  if (!periods.some(item => Number(item.year) === Number(selectedYear.value))) {
    selectedYear.value = Number(periods[0].year)
    selectedMonth.value = 'all'
  }
}

const fetchRealtime = async () => {
  try {
    const [allRes, vibrationRes] = await Promise.all([
      getAllSensorRealtime(),
      getVibrationProcessed(),
    ])
    if (allRes.code === 200 && allRes.data) realtimeData.value = allRes.data
    if (vibrationRes.code === 200 && vibrationRes.data) {
      const payload = vibrationRes.data.data || vibrationRes.data
      vibrationProcessed.value = {
        ...payload,
        timestamp: vibrationRes.data.timestamp || vibrationRes.data.data?.timestamp,
      }
    }
  } catch (error) {
    console.warn('加载实时传感器数据失败:', error)
  }
}

const fetchHistoryPayload = async (query) => {
  if (query.view === 'overview') return fetchOverviewPayload(query)
  const params = { view: query.view, year: query.year, month: query.month }
  if (query.tab === 'temperature' || query.tab === 'humidity') return getTempHumidityTrends(params)
  if (query.tab === 'rain') return getRainTrends(params)
  if (query.tab === 'wind') return getWindTrends(params)
  return fetchVibrationHistory(params)
}

const historyLoaderForTab = (tab) => {
  if (tab === 'temperature' || tab === 'humidity') return getTempHumidityTrends
  if (tab === 'rain') return getRainTrends
  if (tab === 'wind') return getWindTrends
  return fetchVibrationHistory
}

const fetchOverviewPayload = async (query) => {
  const loader = historyLoaderForTab(query.tab)
  const seedRes = await loader({ view: 'calendar', year: Number(selectedYear.value), month: null })
  if (seedRes.code !== 200 || !seedRes.data) return seedRes
  const periods = periodUnion(seedRes.data.available_periods || [{ year: selectedYear.value }])
  const history = await loadAllCalendarRows(periods, period => loader({ view: 'calendar', year: period.year, month: null }))
  return {
    code: 200,
    data: {
      ...seedRes.data,
      view: 'overview',
      history,
      available_periods: periods,
    },
  }
}

const fetchVibrationHistory = async (params) => {
  try {
    const res = await getVibrationHistoryTrends(params)
    if (res.code === 200 && res.data && Array.isArray(res.data.history)) return res
    throw new Error('vibration trends response invalid')
  } catch (error) {
    console.warn('振动新历史接口不可用，回退旧趋势接口:', error)
    return loadLegacyVibrationPayload(params)
  }
}

const loadLegacyVibrationPayload = async ({ view = 'recent24h', year, month } = {}) => {
  const res = await getVibrationTrends(view === 'recent24h' ? '1d' : '6mo')
  if (res.code !== 200 || !res.data) return res
  const sourceRows = Array.isArray(res.data.history) ? res.data.history : []
  const rows = sourceRows
    .map(row => normalizeLegacyVibrationRow(row))
    .filter(row => row && legacyRowInRange(row, view, year, month))
  const periods = buildPeriodsFromRows(rows)
  return {
    code: 200,
    data: {
      view,
      history: rows,
      window: res.data.window || legacyWindow(rows),
      available_periods: periods,
      fallback: true,
    },
  }
}

const applyHistoryPayload = (query, payload) => {
  const normalized = { ...payload, history: Array.isArray(payload.history) ? payload.history : [] }
  syncAvailablePeriods(normalized.available_periods)
  if (queryKey(query) === queryKey(currentQuery())) {
    chartData.value = normalized
    historyError.value = ''
  }
  return normalized
}

const loadHistory = async (query = currentQuery(), force = false) => {
  const key = queryKey(query)
  const requestId = ++requestSerial

  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await fetchHistoryPayload(query)
    if (res.code !== 200 || !res.data || !Array.isArray(res.data.history)) {
      throw new Error('历史数据响应无效')
    }
    if (!isMounted || requestId !== requestSerial || key !== queryKey(currentQuery())) return
    applyHistoryPayload(query, res.data)
    await nextTick()
    renderChart()
    scheduleHistoryRefresh()
  } catch (error) {
    console.warn('加载综合历史失败:', error)
    if (key === queryKey(currentQuery())) historyError.value = '历史数据服务暂时不可用，请稍后重试'
  } finally {
    if (key === queryKey(currentQuery())) historyLoading.value = false
  }
}

const scheduleHistoryRefresh = () => {
  if (refreshTimer) clearTimeout(refreshTimer)
  const delay = historyMode.value === 'recent24h' ? millisecondsToNextHalfHour() + 1000 : 30 * MINUTE
  refreshTimer = setTimeout(() => {
    if (!isMounted) return
    loadHistory(currentQuery(), true)
  }, delay)
}

const millisecondsToNextHalfHour = () => {
  const now = Date.now()
  const interval = 30 * MINUTE
  return Math.floor(now / interval) * interval + interval - now
}

const selectCard = (card) => {
  activeCardKey.value = card.key
  selectHistoryTab(card.tab)
}

const selectHistoryTab = (tab) => {
  if (activeHistoryTab.value === tab && !historyError.value) return
  activeHistoryTab.value = tab
  const relatedCard = liveCards.value.find(card => card.tab === tab)
  if (relatedCard) activeCardKey.value = relatedCard.key
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const selectRecent24h = () => {
  if (historyMode.value === 'recent24h' && !historyError.value) return
  historyMode.value = 'recent24h'
  syncExportRange()
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const selectOverview = () => {
  if (historyMode.value === 'overview' && !historyError.value) return
  historyMode.value = 'overview'
  selectedMonth.value = 'all'
  syncExportRange()
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const activateCalendarMode = () => {
  if (historyMode.value === 'calendar' && !historyError.value) return
  historyMode.value = 'calendar'
  syncExportRange()
  loadHistory(currentQuery(), Boolean(historyError.value))
}

const onYearChange = () => {
  historyMode.value = 'calendar'
  if (selectedMonth.value !== 'all' && !monthOptions.value.includes(Number(selectedMonth.value))) {
    selectedMonth.value = 'all'
  }
  syncExportRange()
  loadHistory(currentQuery())
}

const onMonthChange = () => {
  historyMode.value = 'calendar'
  syncExportRange()
  loadHistory(currentQuery())
}

const retryHistory = () => {
  loadHistory(currentQuery(), true)
}

const normalizeLegacyVibrationRow = (row = {}) => {
  const timestamp = toNumber(row.timestamp ?? row.time)
  if (timestamp === null) return null
  const timestampSeconds = timestamp > 1e12 ? timestamp / 1000 : timestamp
  const date = shanghaiDateKey(timestampSeconds * 1000)
  return {
    timestamp: timestampSeconds,
    date,
    data: {
      rms: toNumber(row.rms ?? row.total_rms ?? row.data?.rms ?? row.data?.total_rms),
      freq: toNumber(row.freq ?? row.dominant_freq ?? row.data?.freq ?? row.data?.dominant_freq),
      temperature: toNumber(row.temperature ?? row.data?.temperature),
    },
  }
}

const legacyRowInRange = (row, view, year, month) => {
  if (view === 'recent24h') return true
  const date = new Date(`${row.date}T00:00:00+08:00`)
  if (year != null && Number.isInteger(Number(year)) && date.getFullYear() !== Number(year)) return false
  if (month != null && Number.isInteger(Number(month)) && date.getMonth() + 1 !== Number(month)) return false
  return true
}

const shanghaiDateKey = (timeMs) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(timeMs))
  const value = Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, part.value]))
  return `${value.year}-${value.month}-${value.day}`
}

const buildPeriodsFromRows = (rows = []) => {
  const map = new Map()
  rows.forEach(row => {
    const date = row?.date ? new Date(`${row.date}T00:00:00+08:00`) : null
    if (!date || Number.isNaN(date.getTime())) return
    const year = date.getFullYear()
    const month = date.getMonth() + 1
    if (!map.has(year)) map.set(year, new Set())
    map.get(year).add(month)
  })
  return [...map.entries()]
    .map(([year, months]) => ({ year, months: [...months].sort((a, b) => a - b) }))
    .sort((a, b) => b.year - a.year)
}

const legacyWindow = (rows = []) => {
  const times = rows.map(row => toNumber(row.timestamp)).filter(value => value !== null)
  if (!times.length) return null
  return { start: Math.min(...times), end: Math.max(...times) }
}

const valueFromPoint = (point) => {
  const data = point?.data || {}
  if (activeHistoryTab.value === 'temperature') {
    const value = toNumber(data.temperature)
    if (value !== null) return value
    const min = toNumber(data.temperature_min)
    const max = toNumber(data.temperature_max)
    return min !== null && max !== null ? (min + max) / 2 : (min ?? max)
  }
  if (activeHistoryTab.value === 'humidity') return toNumber(data.humidity)
  if (activeHistoryTab.value === 'rain') return toNumber(historyMode.value === 'recent24h' ? data.rain_increment : data.daily_rain)
  if (activeHistoryTab.value === 'wind') return windSpeedKmh(data)
  return toNumber(data.rms)
}

const pointTime = (point) => {
  if (historyMode.value === 'recent24h') return Number(point.timestamp) * 1000
  if (point.date) return new Date(`${point.date}T00:00:00+08:00`).getTime()
  return Number(point.timestamp) * 1000
}

const chartSeriesData = () => (chartData.value.history || [])
  .map(point => [pointTime(point), valueFromPoint(point)])
  .filter(point => Number.isFinite(point[0]))
  .sort((a, b) => a[0] - b[0])

const chartValues = () => chartSeriesData().map(point => point[1]).filter(value => value !== null && Number.isFinite(value))

const visibleDaySpan = () => {
  const option = chart?.getOption?.()
  const zoom = option?.dataZoom?.[0]
  const startValue = Number(zoom?.startValue)
  const endValue = Number(zoom?.endValue)
  if (Number.isFinite(startValue) && Number.isFinite(endValue) && endValue > startValue) {
    return Math.ceil((endValue - startValue) / DAY)
  }
  const points = chartSeriesData()
  const first = points[0]?.[0]
  const last = points.at(-1)?.[0]
  return Number.isFinite(first) && Number.isFinite(last) ? Math.ceil((last - first) / DAY) : 365
}

const formatXAxisLabel = (value) => {
  const date = new Date(value)
  if (historyMode.value === 'recent24h') {
    return date.toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false })
  }
  if (historyMode.value === 'overview') {
    const span = visibleDaySpan()
    if (span <= 45) return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    if (span <= 400) {
      return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    }
    return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit' })
  }
  return selectedMonth.value === 'all'
    ? date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: '2-digit', month: 'numeric', day: 'numeric' })
    : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric' })
}

const formatZoomDateLabel = (value) => {
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).replace(/\//g, '-')
}

const tooltipFormatter = (params) => {
  const item = (Array.isArray(params) ? params : [params]).find(entry => entry.value?.[1] != null)
  if (!item) return ''
  const date = new Date(item.value[0])
  const heading = historyMode.value === 'recent24h'
    ? date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    : date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' })
  return `<div style="min-width:160px"><strong>${heading}</strong><div style="display:flex;justify-content:space-between;gap:24px;margin-top:8px"><span>${item.marker}${activeTabMeta.value.label}</span><strong>${Number(item.value[1]).toFixed(activeHistoryTab.value === 'vibration' ? 4 : 1)} ${activeTabMeta.value.unit}</strong></div></div>`
}

const yAxisFallback = (values) => {
  if (activeHistoryTab.value === 'vibration') return { min: 0, max: 0.2, ticks: 5 }
  if (activeHistoryTab.value === 'humidity') return { min: 0, max: 100, ticks: 5 }
  if (activeHistoryTab.value === 'temperature') return { min: 0, max: 35, ticks: 7 }
  if (activeHistoryTab.value === 'rain') return { min: 0, max: 15, ticks: 5 }
  if (activeHistoryTab.value === 'wind') return { min: 0, max: 20, ticks: 4 }
  const max = values.length ? Math.max(...values) : 0
  return { min: 0, max: max <= 35 ? 35 : Math.ceil(max / 5) * 5, ticks: 7 }
}

const zeroRainPoints = points => activeHistoryTab.value === 'rain'
  ? points.filter(point => point[1] === 0).map(point => [point[0], 0])
  : []

const restorePointerTooltip = () => {
  if (!chart || chart.isDisposed() || !lastPointerPixel || !chart.containPixel('grid', lastPointerPixel)) return
  const dataPoint = chart.convertFromPixel({ seriesIndex: 0 }, lastPointerPixel)
  const targetTime = Number(dataPoint?.[0])
  if (!Number.isFinite(targetTime)) return
  const points = chartSeriesData()
  if (!points.length) return
  let nearestIndex = -1
  let nearestDistance = Number.POSITIVE_INFINITY
  points.forEach((point, index) => {
    if (point[1] === null) return
    const distance = Math.abs(point[0] - targetTime)
    if (distance < nearestDistance) {
      nearestIndex = index
      nearestDistance = distance
    }
  })
  if (nearestIndex < 0) return
  chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: nearestIndex })
}

const thresholdMarkLines = () => {
  if (activeHistoryTab.value !== 'vibration') return []
  const data = []
  if (thresholdVisibility.warning) data.push({ yAxis: WARNING_RMS, lineStyle: { color: '#e6a23c', type: 'dashed' }, label: { show: false } })
  if (thresholdVisibility.alarm) data.push({ yAxis: ALARM_RMS, lineStyle: { color: '#f56c6c', type: 'dashed' }, label: { show: false } })
  return data
}

const fullChartOption = () => {
  const meta = activeTabMeta.value
  const points = chartSeriesData()
  const values = chartValues()
  const fallback = yAxisFallback(values)
  const thresholdValues = activeHistoryTab.value === 'vibration' ? [WARNING_RMS, ALARM_RMS] : []
  const yRange = calcNiceYAxisRange([...values, ...thresholdValues], fallback, fallback.ticks)
  const windowStart = Number(chartData.value.window?.start) * 1000
  const windowEnd = Number(chartData.value.window?.end) * 1000
  const recent = historyMode.value === 'recent24h'
  const overview = historyMode.value === 'overview'
  const dataStart = points[0]?.[0] ?? Date.now() - DAY
  const dataEnd = points.at(-1)?.[0] ?? Date.now()
  const zeroPoints = zeroRainPoints(points)
  const rainLegend = activeHistoryTab.value === 'rain'
    ? (recent ? '逐半小时新增雨量' : '逐日雨量')
    : meta.label
  const overviewZoom = overview
  const overviewZoomWindow = {
    startValue: dataStart,
    endValue: dataEnd,
    minValueSpan: 30 * DAY,
    filterMode: 'none',
  }
  return {
    animation: true,
    animationDuration: 850,
    animationDurationUpdate: 550,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: tooltipFormatter,
      backgroundColor: 'rgba(5, 11, 24, 0.95)',
      borderColor: 'rgba(89, 155, 255, 0.55)',
      borderWidth: 1,
      textStyle: { color: '#f1f6ff', fontSize: 13 },
      axisPointer: { type: activeHistoryTab.value === 'rain' ? 'shadow' : 'line' },
    },
    legend: activeHistoryTab.value === 'rain' ? {
      show: true,
      bottom: overview ? 58 : 4,
      left: 12,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: '#b7cae4', fontSize: 12 },
      data: [rainLegend],
    } : undefined,
    toolbox: { show: false },
    grid: { left: 46, right: 54, bottom: overview ? 104 : 48, top: 44, containLabel: true },
    dataZoom: overviewZoom
        ? [{
          type: 'inside',
          zoomOnMouseWheel: true,
          moveOnMouseWheel: false,
          moveOnMouseMove: true,
          preventDefaultMouseMove: true,
          ...overviewZoomWindow,
        }, {
          type: 'slider',
          height: 44,
          bottom: 14,
          borderColor: 'rgba(89, 155, 255, 0.42)',
          backgroundColor: 'rgba(4, 14, 30, 0.88)',
          fillerColor: 'rgba(47, 151, 255, 0.22)',
          showDataShadow: true,
          dataBackground: {
            lineStyle: { color: 'rgba(84, 163, 255, 0.5)', width: 1 },
            areaStyle: { color: 'rgba(84, 163, 255, 0.08)' },
          },
          selectedDataBackground: {
            lineStyle: { color: 'rgba(32, 215, 255, 0.72)', width: 1 },
            areaStyle: { color: 'rgba(32, 215, 255, 0.14)' },
          },
          handleSize: '90%',
          handleStyle: {
            color: '#b8dcff',
            borderColor: '#e6f4ff',
            borderWidth: 1,
            shadowBlur: 8,
            shadowColor: 'rgba(32, 215, 255, 0.36)',
          },
          moveHandleSize: 7,
          moveHandleStyle: { color: 'rgba(32, 215, 255, 0.72)' },
          emphasis: {
            handleStyle: { color: '#e6f4ff', borderColor: '#20d7ff' },
            moveHandleStyle: { color: '#20d7ff' },
          },
          textStyle: { color: '#9fb6d3', fontSize: 11 },
          labelFormatter: value => formatZoomDateLabel(value),
          brushSelect: true,
          realtime: true,
          ...overviewZoomWindow,
        }]
      : [],
    xAxis: {
      type: 'time',
      min: Number.isFinite(windowStart) && recent ? windowStart : dataStart,
      max: Number.isFinite(windowEnd) && recent ? windowEnd : dataEnd,
      interval: recent ? 3 * HOUR : (overview ? DAY : (selectedMonth.value === 'all' ? 30 * DAY : 5 * DAY)),
      minInterval: overview ? DAY : (recent ? 30 * MINUTE : DAY),
      name: recent ? '时间' : '日期',
      nameLocation: 'end',
      nameGap: 18,
      nameTextStyle: { color: '#b6c7df', fontSize: 12, padding: [22, 0, 0, 0] },
      axisLine: { show: true, symbol: ['none', 'arrow'], symbolSize: [8, 10], lineStyle: { color: 'rgba(121, 155, 202, 0.68)' } },
      axisTick: { show: false },
      axisLabel: { color: '#91a9ca', margin: 12, hideOverlap: true, formatter: formatXAxisLabel },
      splitLine: { show: true, lineStyle: { color: 'rgba(174, 202, 245, 0.12)', type: 'dashed' } },
    },
    yAxis: {
      type: 'value',
      min: yRange.min,
      max: yRange.max,
      interval: yRange.interval,
      name: meta.unit,
      nameLocation: 'end',
      nameGap: 18,
      nameTextStyle: { color: '#b6c7df', fontSize: 12, padding: [0, 36, 4, 0] },
      axisLine: { show: true, symbol: ['none', 'arrow'], symbolSize: [8, 10], lineStyle: { color: 'rgba(121, 155, 202, 0.68)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#b6c7df',
        margin: 12,
        formatter: value => activeHistoryTab.value === 'vibration'
          ? Number(value).toFixed(2)
          : String(Number(value).toFixed(Number.isInteger(value) ? 0 : 1)),
      },
      splitLine: { lineStyle: { color: 'rgba(174, 202, 245, 0.12)', width: 1, type: 'dashed' } },
    },
    series: [{
      id: `history-${activeHistoryTab.value}`,
      name: rainLegend,
      type: activeHistoryTab.value === 'rain' ? 'bar' : 'line',
      data: points,
      showSymbol: false,
      smooth: activeHistoryTab.value === 'rain' ? false : 0.48,
      connectNulls: false,
      clip: true,
      sampling: activeHistoryTab.value === 'rain' ? undefined : 'lttb',
      barMaxWidth: recent ? 18 : 9,
      lineStyle: {
        color: meta.color,
        width: activeHistoryTab.value === 'rain' ? 0 : 2,
        shadowBlur: activeHistoryTab.value === 'rain' ? 0 : 16,
        shadowColor: `${meta.color}8a`,
        shadowOffsetY: activeHistoryTab.value === 'rain' ? 0 : 8,
      },
      itemStyle: {
        color: meta.color,
        borderColor: '#ffffff',
        borderWidth: activeHistoryTab.value === 'rain' ? 0 : 1,
        borderRadius: activeHistoryTab.value === 'rain' ? [3, 3, 0, 0] : 0,
      },
      areaStyle: activeHistoryTab.value === 'rain' ? undefined : {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${meta.color}96` },
          { offset: 0.5, color: `${meta.color}48` },
          { offset: 1, color: `${meta.color}08` },
        ]),
        opacity: 0.95,
      },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        data: thresholdMarkLines(),
      },
    }, ...(zeroPoints.length ? [{
      id: 'rain-zero-markers',
      name: '0 mm',
      type: 'scatter',
      data: zeroPoints,
      symbol: 'roundRect',
      symbolSize: [12, 3],
      z: 5,
      tooltip: { show: false },
      itemStyle: { color: 'rgba(151, 190, 255, 0.72)' },
      emphasis: { disabled: true },
    }] : [])],
  }
}

const renderChart = () => {
  if (!chart || chart.isDisposed()) return
  chart.setOption(fullChartOption(), {
    notMerge: false,
    replaceMerge: ['legend', 'xAxis', 'yAxis', 'dataZoom', 'series'],
    lazyUpdate: true,
  })
}

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption(fullChartOption(), true)
  chart.getZr().on('mousemove', event => {
    lastPointerPixel = [event.offsetX, event.offsetY]
  })
  chart.on('datazoom', () => {
    window.requestAnimationFrame(restorePointerTooltip)
  })
  resizeHandler = () => {
    chart?.resize()
    renderChart()
  }
  window.addEventListener('resize', resizeHandler)
}

const loadSummary = async () => {
  const year = new Date().getFullYear()
  const previousYear = year - 1
  try {
    const [tempCurrent, tempPrevious, rainRecent, windRecent, vibrationCurrent, vibrationPrevious] = await Promise.allSettled([
      getTempHumidityTrends({ view: 'calendar', year, month: null }),
      getTempHumidityTrends({ view: 'calendar', year: previousYear, month: null }),
      getRainTrends({ view: 'rolling12' }),
      getWindTrends({ view: 'rolling12' }),
      fetchVibrationHistory({ view: 'calendar', year, month: null }),
      fetchVibrationHistory({ view: 'calendar', year: previousYear, month: null }),
    ])
    const tempCurrentRes = fulfilledResponse(tempCurrent)
    const tempPreviousRes = fulfilledResponse(tempPrevious)
    const rainRecentRes = fulfilledResponse(rainRecent)
    const windRecentRes = fulfilledResponse(windRecent)
    const vibrationCurrentRes = fulfilledResponse(vibrationCurrent)
    const vibrationPreviousRes = fulfilledResponse(vibrationPrevious)
    const tempRecentSource = [
      ...(tempPreviousRes?.data?.history || []),
      ...(tempCurrentRes?.data?.history || []),
    ]
    if (tempCurrentRes?.code === 200) cacheDailyRows('temp', year, tempCurrentRes.data?.history || [])
    if (tempPreviousRes?.code === 200) cacheDailyRows('temp', previousYear, tempPreviousRes.data?.history || [])
    if (tempCurrentRes?.code === 200 || tempPreviousRes?.code === 200) {
      summaryData.tempRecent = filterLast12Months(tempRecentSource)
    }
    if (rainRecentRes?.code === 200) {
      summaryData.rainRecent = rainRecentRes.data?.history || []
      cacheDailyRowsByYear('rain', summaryData.rainRecent)
    }
    if (windRecentRes?.code === 200) {
      summaryData.windRecent = windRecentRes.data?.history || []
      cacheDailyRowsByYear('wind', summaryData.windRecent)
    }
    const vibrationRecentSource = [
      ...(vibrationPreviousRes?.data?.history || []),
      ...(vibrationCurrentRes?.data?.history || []),
    ]
    if (vibrationCurrentRes?.code === 200) cacheDailyRows('vibration', year, vibrationCurrentRes.data?.history || [])
    if (vibrationPreviousRes?.code === 200) cacheDailyRows('vibration', previousYear, vibrationPreviousRes.data?.history || [])
    if (vibrationCurrentRes?.code === 200 || vibrationPreviousRes?.code === 200) {
      summaryData.vibrationRecent = filterLast12Months(vibrationRecentSource)
    }

    const [tempAll, rainAll, windAll, vibrationAll] = await Promise.allSettled([
      loadAllCalendarRows(
        periodUnion([
          ...(tempCurrentRes?.data?.available_periods || []),
          ...(tempPreviousRes?.data?.available_periods || []),
        ]),
        period => getTempHumidityTrends({ view: 'calendar', year: period.year, month: null }),
      ),
      rainRecentRes?.code === 200
        ? loadAllCalendarRows(
            rainRecentRes.data?.available_periods || [],
            period => getRainTrends({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
      windRecentRes?.code === 200
        ? loadAllCalendarRows(
            windRecentRes.data?.available_periods || [],
            period => getWindTrends({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
      (vibrationCurrentRes?.code === 200 || vibrationPreviousRes?.code === 200)
        ? loadAllCalendarRows(
            periodUnion([
              ...(vibrationCurrentRes?.data?.available_periods || []),
              ...(vibrationPreviousRes?.data?.available_periods || []),
            ]),
            period => fetchVibrationHistory({ view: 'calendar', year: period.year, month: null }),
          )
        : Promise.resolve([]),
    ])
    summaryData.tempAll = fulfilledValue(tempAll) || summaryData.tempRecent
    summaryData.rainAll = fulfilledValue(rainAll) || summaryData.rainRecent
    summaryData.windAll = fulfilledValue(windAll) || summaryData.windRecent
    summaryData.vibrationAll = fulfilledValue(vibrationAll) || summaryData.vibrationRecent
    cacheDailyRowsByYear('temp', summaryData.tempAll)
    cacheDailyRowsByYear('rain', summaryData.rainAll)
    cacheDailyRowsByYear('wind', summaryData.windAll)
    cacheDailyRowsByYear('vibration', summaryData.vibrationAll)
    syncExportRange()
  } catch (error) {
    console.warn('加载统计摘要失败:', error)
  }
}

const fulfilledResponse = result => result.status === 'fulfilled' ? result.value : null
const fulfilledValue = result => result.status === 'fulfilled' ? result.value : null

const filterLast12Months = (rows = []) => {
  const cutoff = new Date()
  cutoff.setFullYear(cutoff.getFullYear() - 1)
  const cutoffMs = cutoff.getTime()
  return rows.filter(row => {
    const time = row?.date
      ? new Date(`${row.date}T00:00:00+08:00`).getTime()
      : Number(row?.timestamp || 0) * 1000
    return Number.isFinite(time) && time >= cutoffMs
  })
}

const periodUnion = (periods = []) => {
  const map = new Map()
  periods.forEach(period => {
    const year = Number(period.year)
    if (Number.isInteger(year)) map.set(year, period)
  })
  return [...map.values()].sort((a, b) => Number(b.year) - Number(a.year))
}

const loadAllCalendarRows = async (periods = [], loader) => {
  const validPeriods = periodUnion(periods)
  if (!validPeriods.length) return []
  const responses = await Promise.allSettled(validPeriods.map(loader))
  return responses.flatMap(result => (
    result.status === 'fulfilled' && result.value?.code === 200
      ? (result.value.data?.history || [])
      : []
  ))
}

onMounted(async () => {
  isMounted = true
  initChart()
  syncExportRange()
  fetchRealtime()
  loadHistory(currentQuery())
  tickTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
  summaryTimer = window.setTimeout(() => {
    if (isMounted) loadSummary()
  }, 2200)
  realtimeTimer = setInterval(fetchRealtime, 5000)
})

onUnmounted(() => {
  isMounted = false
  requestSerial += 1
  if (realtimeTimer) clearInterval(realtimeTimer)
  if (tickTimer) clearInterval(tickTimer)
  if (refreshTimer) clearTimeout(refreshTimer)
  if (summaryTimer) clearTimeout(summaryTimer)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  if (chart && !chart.isDisposed()) chart.dispose()
  chart = null
})
</script>

<style scoped>
.unified-sensors {
  min-height: 100%;
  padding: 0;
  color: var(--text-primary);
}

.live-carousel {
  position: relative;
  margin-bottom: 12px;
  overflow: hidden;
  padding: 0;
}

.live-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  overflow-x: hidden;
  overflow-y: hidden;
}

.live-card {
  position: relative;
  min-width: 0;
  min-height: 190px;
  padding: 17px 21px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 14px;
  border: 1px solid rgba(88, 137, 205, 0.24);
  border-radius: 10px;
  background:
    linear-gradient(145deg, rgba(16, 34, 61, 0.98), rgba(9, 23, 43, 0.98));
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.live-card:hover,
.live-card.active {
  border-color: rgba(54, 151, 255, 0.72);
  background: linear-gradient(145deg, rgba(18, 42, 72, 0.98), rgba(10, 29, 52, 0.98));
  box-shadow: inset 0 0 0 1px rgba(74, 182, 255, 0.08);
}

.live-card.ok { border-top: 3px solid #67c23a; }
.live-card.warn { border-top: 3px solid #e6a23c; }
.live-card.danger { border-top: 3px solid #f56c6c; }

.card-head,
.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-size: 20px;
  font-weight: 700;
  color: #f4f8ff;
  line-height: 1.2;
}

.card-accent,
.sensor-dot {
  flex: 0 0 auto;
  display: inline-block;
  border-radius: 999px;
  background: #20a8ff;
  box-shadow: 0 0 12px rgba(32, 168, 255, 0.34);
}

.card-accent {
  width: 8px;
  height: 8px;
}

.sensor-dot {
  width: 7px;
  height: 7px;
}

.card-accent.temp_humidity,
.sensor-dot.temperature { background: #ff6b7a; box-shadow: 0 0 12px rgba(255, 107, 122, 0.34); }
.sensor-dot.humidity { background: #20a8ff; box-shadow: 0 0 12px rgba(32, 168, 255, 0.34); }
.card-accent.rain,
.sensor-dot.rain { background: #2dc8ff; box-shadow: 0 0 12px rgba(45, 200, 255, 0.34); }
.card-accent.wind,
.sensor-dot.wind { background: #72cdf9; box-shadow: 0 0 12px rgba(114, 205, 249, 0.34); }
.card-accent.vibration,
.sensor-dot.vibration { background: #8da2ff; box-shadow: 0 0 12px rgba(141, 162, 255, 0.34); }

.card-state {
  min-width: 44px;
  height: 26px;
  padding: 2px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(255, 216, 74, 0.16);
  color: #ffd84a;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.wind-head-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px;
  margin: 2px 0 0;
  align-items: start;
}

.metric-row.metric-columns {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-cell {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.metric-cell strong {
  min-height: 40px;
  display: flex;
  align-items: flex-end;
  color: #fff;
  font: 800 32px/1 "Consolas", "Monaco", monospace;
  white-space: nowrap;
  letter-spacing: 0;
}

.metric-columns .metric-cell strong {
  font-size: 28px;
}

.metric-cell span {
  display: block;
  margin-top: 9px;
  color: #8ea8c9;
  font-size: 16px;
  line-height: 1.2;
}

.wind-card-body {
  min-height: 72px;
  margin: 2px 0 0;
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  align-items: start;
  gap: 28px;
}

.wind-direction strong {
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 32px;
  letter-spacing: 0;
}

.wind-direction-value {
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.wind-direction-value strong {
  min-height: 42px;
  align-items: center;
  line-height: 1;
}

.wind-direction-value .mini-compass {
  display: block;
  flex: 0 0 auto;
  margin-top: 0;
  transform: translateY(1px);
}

.mini-compass {
  position: relative;
  width: 38px;
  height: 38px;
  border: 1px solid rgba(116, 201, 249, 0.62);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(38, 82, 128, 0.5), rgba(13, 31, 57, 0.42));
}

.mini-compass b {
  position: absolute;
  color: #8ea8c9;
  font-size: 8px;
  font-weight: 700;
  line-height: 1;
}
.mini-n { top: 3px; left: 50%; transform: translateX(-50%); color: #72cdf9 !important; }
.mini-e { top: 50%; right: 3px; transform: translateY(-50%); }
.mini-s { bottom: 3px; left: 50%; transform: translateX(-50%); }
.mini-w { top: 50%; left: 3px; transform: translateY(-50%); }

.mini-compass i {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 16px solid #72cdf9;
  transform-origin: 50% 70%;
  filter: drop-shadow(0 0 8px rgba(114, 205, 249, 0.45));
}

.card-foot {
  color: #7e97b9;
  font-size: 12px;
}

.card-update {
  min-height: 16px;
  margin-top: auto;
  align-self: flex-end;
  color: #7189aa;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.today-strip {
  min-height: 26px;
  margin-top: 0;
  padding-top: 9px;
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  border-top: 1px solid rgba(174, 202, 245, 0.11);
  color: #9fb6d3;
  font-size: 14px;
  line-height: 1.2;
}

.today-strip span {
  white-space: nowrap;
}

.today-strip .today-label {
  color: #ffd84a;
  font-weight: 700;
}

.history-panel,
.yesterday-summary,
.summary-card {
  border: 1px solid rgba(84, 130, 202, 0.25);
  border-radius: 10px;
  background:
    radial-gradient(circle at 100% 0%, rgba(50, 105, 200, 0.13), transparent 34%),
    linear-gradient(145deg, rgba(15, 31, 57, 0.98), rgba(10, 23, 43, 0.98));
  box-shadow: 0 14px 36px rgba(0, 8, 24, 0.18);
  overflow: hidden;
}

.history-header {
  min-height: 64px;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid rgba(124, 157, 207, 0.14);
}

.history-title h3,
.summary-title h3 {
  margin: 0;
  color: #f4f8ff;
  font-size: 20px;
  font-weight: 750;
}

.history-title span {
  display: block;
  margin-top: 4px;
  color: #8ea8c9;
  font-size: 12px;
}

.yesterday-summary {
  margin-bottom: 14px;
  padding: 18px;
}

.history-controls {
  display: flex;
  align-items: center;
  gap: 9px;
}

.export-button,
.period-button {
  height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(120, 155, 211, 0.24);
  border-radius: 8px;
  background: rgba(33, 57, 94, 0.55);
  color: #a8bddb;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.period-button {
  width: 92px;
}

.export-button {
  min-width: 102px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #dce9fa;
  border-color: rgba(32, 215, 255, 0.34);
  background: rgba(32, 95, 148, 0.38);
}

.export-button:hover {
  border-color: rgba(32, 215, 255, 0.68);
  color: #ffffff;
}

.period-button.active {
  color: #fff;
  border-color: #378cff;
  background: linear-gradient(135deg, #1d70e8, #245ac4);
}

.calendar-controls {
  display: flex;
  gap: 7px;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: 9px;
  opacity: 0.76;
}

.calendar-controls.active {
  opacity: 1;
  border-color: rgba(77, 141, 234, 0.28);
  background: rgba(26, 49, 83, 0.38);
}

.history-select.year-select { width: 112px; }
.history-select.month-select { width: 126px; }
.history-select :deep(.el-select__wrapper) {
  min-height: 28px;
  border: 0;
  border-radius: 7px;
  background: rgba(31, 53, 88, 0.82);
  box-shadow: 0 0 0 1px rgba(120, 155, 211, 0.18) inset;
}
.history-select :deep(.el-select__selected-item) { color: #dce9fa; font-size: 13px; }
.history-select :deep(.el-select__caret) { color: #91a8c9; }

.export-panel {
  display: grid;
  gap: 12px;
}

.export-title {
  color: #f4f8ff;
  font-size: 14px;
  font-weight: 750;
}

.export-date-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 10px;
}

.export-date-field {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.export-date-field span {
  color: #9fb3d1;
  font-size: 12px;
}

.export-date-field input {
  width: 100%;
  min-width: 0;
  height: 34px;
  box-sizing: border-box;
  border: 1px solid rgba(120, 155, 211, 0.26);
  border-radius: 8px;
  background: rgba(31, 53, 88, 0.82);
  color: #f4f8ff;
  color-scheme: dark;
  font: inherit;
  font-size: 13px;
  padding: 0 10px;
  outline: none;
}

.export-date-field input:focus {
  border-color: rgba(32, 215, 255, 0.7);
  box-shadow: 0 0 0 2px rgba(32, 215, 255, 0.14);
}

.export-date-separator {
  padding-bottom: 8px;
  color: #7991b4;
  font-weight: 700;
}

.export-confirm {
  height: 34px;
  border: 1px solid rgba(32, 215, 255, 0.42);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(29, 112, 232, 0.95), rgba(36, 90, 196, 0.95));
  color: #ffffff;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.export-confirm:disabled {
  opacity: 0.62;
  cursor: wait;
}

:global(.sensor-export-popover.el-popper) {
  border-color: rgba(84, 130, 202, 0.35);
  background: rgba(10, 23, 43, 0.98);
  box-shadow: 0 14px 36px rgba(0, 8, 24, 0.32);
}

:global(.sensor-export-popover .el-popper__arrow::before) {
  border-color: rgba(84, 130, 202, 0.35);
  background: rgba(10, 23, 43, 0.98);
}

.yesterday-head {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.yesterday-head h3 {
  margin: 0;
  color: #f4f8ff;
  font-size: 20px;
  font-weight: 750;
}

.yesterday-head span {
  color: #8ea8c9;
  font-size: 16px;
  font-weight: 750;
  letter-spacing: 0;
}

.yesterday-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.yesterday-card {
  min-width: 0;
  min-height: 154px;
  padding: 14px 15px;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(84, 130, 202, 0.18);
  border-radius: 8px;
  background: rgba(12, 30, 55, 0.68);
}

.yesterday-card-title {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #9fb6d3;
  font-size: 12px;
}

.yesterday-card-title strong {
  color: #dce9fa;
  font-size: 13px;
}

.yesterday-main {
  margin-top: 12px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: #8ea8c9;
  font-size: 12px;
  font-weight: 750;
  line-height: 1.2;
  white-space: nowrap;
}

.yesterday-main strong {
  color: #ffffff;
  font-size: 21px;
}

.yesterday-stat-pills {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.yesterday-stat-pills span {
  min-width: 72px;
  padding: 7px 8px;
  display: grid;
  gap: 4px;
  border-radius: 7px;
  background: rgba(34, 62, 100, 0.52);
}

.yesterday-stat-pills small {
  color: #7f98ba;
  font-size: 11px;
}

.yesterday-stat-pills b {
  color: #dce9fa;
  font-size: 13px;
  white-space: nowrap;
}

.yesterday-change {
  margin-top: auto;
  padding-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #9fb6d3;
  font-size: 12px;
}

.yesterday-change strong {
  font-size: 14px;
}

.yesterday-change.up strong { color: #ff5b6e; }
.yesterday-change.down strong { color: #67c23a; }
.yesterday-change.neutral strong { color: #9fb6d3; }

.yesterday-meta {
  margin-top: 9px;
  display: grid;
  gap: 5px;
  color: #8ea8c9;
  font-size: 12px;
  line-height: 1.2;
}

.yesterday-meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-nav {
  padding: 14px 18px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.history-tabs {
  display: flex;
  gap: 8px;
  padding: 0;
  flex-wrap: wrap;
}

.history-tabs button {
  height: 32px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #a8bddb;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.history-tabs button.active {
  color: #071426;
  background: linear-gradient(135deg, #ffd84a, #ffbc27);
  box-shadow: 0 4px 14px rgba(255, 190, 35, 0.24);
}

.chart-shell {
  position: relative;
  height: 392px;
  margin: 12px 18px 12px;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(232, 243, 255, 0.075), rgba(122, 167, 218, 0.035));
  box-shadow: inset 0 0 0 1px rgba(174, 202, 245, 0.08);
}

.chart {
  height: 100%;
}

.chart-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-radius: 8px;
  background: rgba(8, 22, 43, 0.78);
  color: #AECAF5;
  backdrop-filter: blur(3px);
}

.chart-overlay.hint {
  background: rgba(8, 22, 43, 0.5);
}

.spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(55, 140, 255, 0.18);
  border-top-color: #438fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.retry-button,
.chart-error-banner button {
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(255, 213, 138, 0.55);
  border-radius: 5px;
  background: rgba(255, 213, 138, 0.12);
  color: #ffe4b4;
  font: inherit;
  cursor: pointer;
}

.chart-error-banner {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 9;
  max-width: calc(100% - 20px);
  padding: 7px 11px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 190, 82, 0.35);
  border-radius: 6px;
  background: rgba(66, 43, 17, 0.9);
  color: #ffd58a;
  font-size: 12px;
}

.threshold-toggles {
  min-height: 38px;
  padding: 0 28px 12px;
  display: flex;
  align-items: center;
  gap: 20px;
  color: #b7cae4;
  font-size: 12px;
}

.threshold-toggles label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}

.threshold-toggles input {
  width: 15px;
  height: 15px;
  accent-color: #247ee8;
}

.threshold-toggles span {
  width: 18px;
  height: 3px;
  border-radius: 999px;
  background: #e6a23c;
}

.threshold-toggles label:nth-child(2) span {
  background: #f56c6c;
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr;
  margin-top: 14px;
}

.summary-title {
  min-height: 44px;
  padding: 12px 16px;
  display: grid;
  grid-template-columns: 1.4fr repeat(4, 1fr);
  align-items: center;
  gap: 12px;
  background: rgba(225, 237, 248, 0.08);
  color: #dce9fa;
  font-size: 13px;
  font-weight: 700;
}

.summary-title.overview {
  grid-template-columns: minmax(120px, 1fr) auto;
}

.summary-title.overview span {
  color: #8ea8c9;
  font-size: 12px;
  font-weight: 600;
}

.overview-title-meta {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.overview-title-meta b {
  color: #dce9fa;
  font-size: 12px;
  font-weight: 700;
}

.period-help {
  width: 26px;
  height: 26px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(120, 155, 211, 0.24);
  border-radius: 50%;
  background: rgba(31, 53, 88, 0.72);
  color: #9fb6d3;
  cursor: help;
}

.period-help:hover {
  color: #ffffff;
  border-color: rgba(32, 215, 255, 0.56);
}

.period-overview-grid {
  padding: 14px 16px 12px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  align-items: stretch;
  gap: 12px;
}

.period-overview-card {
  min-width: 0;
  min-height: 190px;
  padding: 13px 14px;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(84, 130, 202, 0.2);
  border-radius: 8px;
  background: rgba(12, 30, 55, 0.58);
}

.period-overview-head {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #9fb6d3;
  font-size: 12px;
}

.period-overview-head strong {
  color: #f4f8ff;
  font-size: 14px;
}

.period-stat-list {
  margin-top: 12px;
  flex: 1;
  display: grid;
  align-content: start;
  gap: 8px;
}

.period-stat-list div {
  min-height: 22px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #8ea8c9;
  font-size: 12px;
}

.period-stat-list strong {
  color: #ffffff;
  font-size: 14px;
  font-weight: 750;
  text-align: right;
  white-space: nowrap;
}

.period-change {
  min-height: 22px;
  margin-top: auto;
  padding-top: 12px;
  display: inline-flex;
  align-items: flex-end;
  color: #9fb6d3;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.period-change.up { color: #ff5b6e; }
.period-change.down { color: #67c23a; }
.period-change.neutral { color: #9fb6d3; }

.summary-table {
  padding: 0 16px;
}

.summary-row {
  min-height: 46px;
  display: grid;
  grid-template-columns: 1.4fr repeat(4, 1fr);
  align-items: center;
  gap: 12px;
  border-top: 1px solid rgba(174, 202, 245, 0.12);
  color: #dce9fa;
  font-size: 14px;
}

.summary-row.overview {
  grid-template-columns: minmax(150px, 1.25fr) repeat(4, minmax(96px, 1fr));
}

.summary-row span {
  display: flex;
  align-items: center;
  color: #f4f8ff;
}

.summary-row strong {
  color: #ffffff;
  font-weight: 700;
}

@media (max-width: 1280px) {
  .live-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .yesterday-grid,
  .period-overview-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .history-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-nav {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-tabs {
    width: 100%;
  }

  .history-controls {
    width: 100%;
    flex-wrap: wrap;
  }

  .yesterday-grid,
  .period-overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .live-grid {
    grid-template-columns: 1fr;
  }

  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .wind-card-body {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-cell strong,
  .wind-direction strong {
    font-size: 22px;
  }

  .calendar-controls {
    width: 100%;
  }

  .export-button,
  .period-button {
    flex: 1 1 auto;
  }

  .history-select.year-select,
  .history-select.month-select {
    flex: 1;
    width: auto;
  }

  .yesterday-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .yesterday-grid,
  .period-overview-grid {
    grid-template-columns: 1fr;
  }

  .chart-shell {
    height: 330px;
  }

  .summary-title.overview,
  .summary-row.overview {
    grid-template-columns: minmax(128px, 1.15fr) repeat(4, minmax(76px, 1fr));
    min-width: 560px;
  }

  .summary-card {
    overflow-x: auto;
  }
}
</style>
