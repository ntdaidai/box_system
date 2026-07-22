<template>
  <div class="dashboard">
    <!-- 第一行：统计卡片 -->
    <el-row :gutter="14" class="stat-row">
      <el-col :span="6" v-for="item in statCards" :key="item.label">
        <div class="stat-card" :style="{ borderColor: item.color + '40' }">
          <div class="stat-icon" :style="{ background: item.color + '25' }">
            <el-icon :size="22" :style="{ color: item.color }"><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value" :style="{ color: item.color }">{{ item.value }}</div>
            <div class="stat-label">{{ item.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 第二行：传感器实时数据卡片 -->
    <div class="sensor-carousel" @mouseenter="pauseSensorCarousel" @mouseleave="resumeSensorCarousel">
      <button type="button" class="carousel-arrow left" @click.stop="scrollSensorCards(-1)">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <div ref="sensorTrackRef" class="sensor-row" aria-label="传感器实时数据">
        <div class="sensor-card-slot" v-for="s in sensorCards" :key="s.key">
          <div class="sensor-data-card" @click="router.push(s.path)">
            <div class="sensor-card-top">
              <img :src="s.icon" class="sensor-img" />
              <div class="sensor-card-info">
                <div class="sensor-card-name">{{ s.name }}</div>
              </div>
              <div class="sensor-card-status">
                <span class="status-dot" :class="getSensorOnline(s.key) ? 'online' : 'offline'"></span>
                {{ getSensorOnline(s.key) ? '在线' : '离线' }}
              </div>
            </div>
            <div class="sensor-card-values">
              <div class="sensor-value-grid" :class="{ 'two-col': s.values.length > 2 }">
                <div class="sensor-value-row" v-for="v in s.values" :key="v.label">
                  <span class="sensor-value-label">{{ v.label }}</span>
                  <span class="sensor-value-num">{{ formatSensorValue(s.key, v.field) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <button type="button" class="carousel-arrow right" @click.stop="scrollSensorCards(1)">
        <el-icon><ArrowRight /></el-icon>
      </button>
    </div>

    <!-- 第三行：系统状态 + 告警分布 -->
    <el-row :gutter="14" class="health-alarm-row">
      <el-col :span="14">
        <div class="data-panel system-health-panel">
          <div class="health-header">
            <div class="panel-title">系统运行状态</div>
            <div class="health-clock">{{ currentTime }}</div>
          </div>
          <!-- 顶部两个中卡片 -->
          <div class="health-top-row">
            <div class="health-item health-item-medium">
              <div class="health-icon" style="background: rgba(100,200,255,0.15);">
                <el-icon :size="22" color="#64c8ff"><Timer /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">平台服务运行时间</div>
                <div class="health-value">{{ formatUptime(systemInfo.service_uptime_hours) }}</div>
              </div>
            </div>
            <div class="health-item health-item-medium">
              <div class="health-icon" style="background: rgba(0,229,255,0.15);">
                <el-icon :size="22" color="#00e5ff"><Clock /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">主机连续运行时间</div>
                <div class="health-value">{{ formatUptime(systemInfo.system_uptime_hours) }}</div>
              </div>
            </div>
          </div>
          <!-- 下方六小卡片 2x3 -->
          <div class="health-grid">
            <!-- CPU 使用率 -->
            <div class="health-item">
              <div class="health-icon" style="background: rgba(103,194,58,0.15);">
                <el-icon :size="20" color="#67c23a"><Cpu /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">CPU 计算负载</div>
                <div class="health-value">
                  <el-progress :percentage="systemInfo.cpu_percent || 0" :stroke-width="8"
                    :color="cpuColor" :show-text="false" />
                  <span>{{ systemInfo.cpu_percent || '--' }}%</span>
                </div>
              </div>
            </div>
            <!-- 内存使用率 -->
            <div class="health-item">
              <div class="health-icon" style="background: rgba(230,162,60,0.15);">
                <el-icon :size="20" color="#e6a23c"><Menu /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">内存资源占用</div>
                <div class="health-value">
                  <el-progress :percentage="systemInfo.memory?.percent || 0" :stroke-width="8"
                    :color="memColor" :show-text="false" />
                  <span>{{ systemInfo.memory?.used_gb || '--' }} / {{ systemInfo.memory?.total_gb || '--' }} GB ({{ systemInfo.memory?.percent || 0 }}%)</span>
                </div>
              </div>
            </div>
            <!-- GPU 使用率 -->
            <div class="health-item">
              <div class="health-icon" style="background: rgba(118,185,0,0.15);">
                <el-icon :size="20" color="#76b900"><Odometer /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">
                  GPU 推理负载
                  <span class="gpu-vendor" v-if="systemInfo.gpu?.vendor && systemInfo.gpu.vendor !== 'unknown'">
                    ({{ systemInfo.gpu.vendor }})
                  </span>
                </div>
                <div class="health-value">
                  <el-progress :percentage="systemInfo.gpu?.utilization_percent || 0" :stroke-width="8"
                    :color="gpuColor" :show-text="false" />
                  <span>{{ systemInfo.gpu?.utilization_percent || 0 }}%</span>
                  <span class="gpu-meta" v-if="systemInfo.gpu?.available">
                    <i v-if="systemInfo.gpu.temperature_c">{{ systemInfo.gpu.temperature_c }}°C</i>
                    <i v-if="systemInfo.gpu.power_w">{{ systemInfo.gpu.power_w }}W</i>
                  </span>
                </div>
              </div>
            </div>
            <!-- 磁盘使用率 -->
            <div class="health-item">
              <div class="health-icon" style="background: rgba(245,108,108,0.15);">
                <el-icon :size="20" color="#f56c6c"><FolderOpened /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">存储空间占用</div>
                <div class="health-value">
                  <el-progress :percentage="systemInfo.disk?.percent || 0" :stroke-width="8"
                    :color="diskColor" :show-text="false" />
                  <span>{{ systemInfo.disk?.used_gb || '--' }} / {{ systemInfo.disk?.total_gb || '--' }} GB ({{ systemInfo.disk?.percent || 0 }}%)</span>
                </div>
              </div>
            </div>
            <!-- 边缘采集服务 -->
            <div class="health-item">
              <div class="health-icon" :style="{ background: systemInfo.sensor_collector_running ? 'rgba(103,194,58,0.15)' : 'rgba(245,108,108,0.15)' }">
                <el-icon :size="20" :color="systemInfo.sensor_collector_running ? '#67c23a' : '#f56c6c'"><Connection /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">边缘采集服务</div>
                <div class="health-value" :style="{ color: systemInfo.sensor_collector_running ? '#67c23a' : '#f56c6c' }">
                  {{ systemInfo.sensor_collector_running ? '运行中' : '已停止' }}
                </div>
              </div>
            </div>
            <!-- AI 模型服务 -->
            <div class="health-item">
              <div class="health-icon" :style="{ background: aiModelHealthy ? 'rgba(103,194,58,0.15)' : 'rgba(245,108,108,0.15)' }">
                <el-icon :size="20" :color="aiModelHealthy ? '#67c23a' : '#f56c6c'"><Aim /></el-icon>
              </div>
              <div class="health-body">
                <div class="health-label">AI模型推理服务</div>
                <div class="health-value" :style="{ color: aiModelHealthy ? '#67c23a' : '#f56c6c' }">
                  {{ aiModelStatusText }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="data-panel alarm-panel">
          <div class="panel-title">告警态势分布</div>
          <!-- 顶部状态条 -->
          <div class="alarm-status-bar" :class="alarmStatusLevel">
            <span class="alarm-status-dot"></span>
            <span class="alarm-status-text">{{ alarmStatusText }}</span>
          </div>
          <!-- 中间三个指标卡片 -->
          <div class="alarm-metrics">
            <div class="alarm-metric-card alarm-metric-high">
              <div class="alarm-metric-label">紧急告警</div>
              <div class="alarm-metric-value">{{ alarmHigh }}</div>
            </div>
            <div class="alarm-metric-card alarm-metric-warn">
              <div class="alarm-metric-label">一般告警</div>
              <div class="alarm-metric-value">{{ alarmTotal - alarmHigh }}</div>
            </div>
            <div class="alarm-metric-card alarm-metric-unhandled">
              <div class="alarm-metric-label">未处理</div>
              <div class="alarm-metric-value">{{ alarmUnhandled }}</div>
            </div>
          </div>
          <!-- 底部横向占比条 -->
          <div class="alarm-bar-section">
            <div class="alarm-bar">
              <div class="alarm-bar-seg alarm-bar-high" :style="{ width: alarmBarHigh + '%' }"></div>
              <div class="alarm-bar-seg alarm-bar-warn" :style="{ width: alarmBarWarn + '%' }"></div>
            </div>
            <div class="alarm-bar-legend">
              <span class="alarm-bar-legend-item" v-if="alarmHigh > 0"><i class="alarm-bar-legend-dot alarm-bar-high"></i>紧急 {{ alarmBarHigh }}%</span>
              <span class="alarm-bar-legend-item" v-if="(alarmTotal - alarmHigh) > 0"><i class="alarm-bar-legend-dot alarm-bar-warn"></i>一般 {{ alarmBarWarn }}%</span>
            </div>
          </div>
          <!-- 告警处理建议 -->
          <div class="alarm-tips">
            <div class="alarm-tips-title">告警处理建议</div>
            <template v-if="alarmHigh > 0">
              <div class="alarm-tips-item"><span class="alarm-tips-dot alarm-tips-dot-high"></span>存在紧急告警，请立即处理</div>
              <div class="alarm-tips-item"><span class="alarm-tips-dot"></span>优先查看告警设备位置和告警类型</div>
              <div class="alarm-tips-item"><span class="alarm-tips-dot"></span>必要时启动现场巡查和应急处置流程</div>
            </template>
            <template v-else-if="alarmTotal > 0">
              <div class="alarm-tips-item"><span class="alarm-tips-dot alarm-tips-dot-warn"></span>存在一般告警，请关注相关设备状态</div>
              <div class="alarm-tips-item"><span class="alarm-tips-dot"></span>建议核对传感器实时数据和历史记录</div>
              <div class="alarm-tips-item"><span class="alarm-tips-dot"></span>如告警持续，请安排人员复核现场情况</div>
            </template>
            <template v-else>
              <div class="alarm-tips-item"><span class="alarm-tips-dot alarm-tips-dot-ok"></span>当前系统运行正常，暂无告警事件</div>
              <div class="alarm-tips-item"><span class="alarm-tips-dot"></span>建议持续关注设备在线状态</div>
            </template>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 第五行：最近告警 -->
    <div class="data-panel alarm-recent-row">
      <div class="panel-title">
        最近告警
        <span class="link-btn" @click="router.push('/alarm/list')">查看全部</span>
      </div>
      <!-- 列表头 -->
      <div class="alarm-list-header" v-if="recentAlarms.length > 0">
        <div class="col-time sortable" @click="toggleSort('time')">
          告警时间
          <span class="sort-pill" :class="{ active: sortField === 'time' }">
            <span class="sort-icon">{{ sortIcon('time') }}</span>{{ sortText('time') }}
          </span>
        </div>
        <div class="col-level sortable" @click="toggleSort('level')">
          级别
          <span class="sort-pill" :class="{ active: sortField === 'level' }">
            <span class="sort-icon">{{ sortIcon('level') }}</span>{{ sortText('level') }}
          </span>
        </div>
        <div class="col-desc">描述</div>
        <div class="col-content">告警内容</div>
        <div class="col-status sortable" @click="toggleSort('status')">
          状态
          <span class="sort-pill" :class="{ active: sortField === 'status' }">
            <span class="sort-icon">{{ sortIcon('status') }}</span>{{ sortText('status') }}
          </span>
        </div>
      </div>
      <div class="alarm-preview-list">
        <div v-if="recentAlarms.length === 0" class="alarm-empty">暂无告警记录</div>
        <div
          v-for="row in sortedRecentAlarms"
          :key="row.id"
          class="alarm-item"
          :class="{ 'is-unhandled': row.handle_status === 0 }"
        >
          <div class="col-time">{{ formatAlarmTime(row.alarm_time) }}</div>
          <div class="col-level">
            <span class="level-tag" :class="'level-' + row.alarm_level">
              {{ alarmLevelText(row.alarm_level) }}
            </span>
          </div>
          <div class="col-desc">
            <span class="desc-text" @click="router.push({ path: '/alarm/list', query: { report: row.id } })">{{ row.alarm_content || '--' }}</span>
          </div>
          <div class="col-content">
            <span class="report-link" @click="router.push({ path: '/alarm/list', query: { report: row.id } })">查看分析报告</span>
          </div>
          <div class="col-status">
            <span class="status-tag" :class="row.handle_status === 1 ? 'handled' : 'unhandled'">
              {{ row.handle_status === 1 ? '已处理' : '未处理' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Monitor, CircleCheck, Warning, WarningFilled,
  Cpu, Clock, Timer, Connection, FolderOpened, Menu, Odometer, Aim,
  ArrowLeft, ArrowRight
} from '@element-plus/icons-vue'
import { getSystemInfo, getAllSensorRealtime, getDeviceStatus, getAlarmStatistics, getAlarmList } from '@/api/dashboard'
import { getVibrationProcessed } from '@/api/sensor'
import SensorSSE from '@/utils/sensorSSE'
import { readCachedResponse } from '@/utils/localResponseCache'
import { cancelIdleTask, runWhenIdle } from '@/utils/sensorDetailStartup'

// 传感器图标
import tempIcon from '@/assets/images/sensors/temp_humidity.png'
import windIcon from '@/assets/images/sensors/wind.png'
import rainIcon from '@/assets/images/sensors/rain.png'
import vibrationIcon from '@/assets/images/sensors/vibration.png'
import cameraIcon from '@/assets/images/sensors/camera.png'
import beidouIcon from '@/assets/images/sensors/beidou.png'

const router = useRouter()

// ==================== 响应式状态 ====================

// 统计卡片数据
const currentTime = ref('--')
let clockTimer = null

const deviceTotal = ref(0)
const deviceOnline = ref(0)
const alarmTotal = ref(0)
const alarmHigh = ref(0)
const alarmUnhandled = ref(0)

// 传感器数据
const sensorData = ref({})
const deviceStatus = ref({})
const vibrationProcessedData = ref({})

// 系统状态
const systemInfo = ref({
  cpu_percent: 0,
  memory: { total_gb: 0, used_gb: 0, percent: 0 },
  disk: { total_gb: 0, used_gb: 0, percent: 0 },
  gpu: { available: false, vendor: 'unknown', utilization_percent: 0, memory: {}, temperature_c: 0, power_w: 0 },
  system_uptime_hours: 0,
  service_uptime_hours: 0,
  sensor_collector_running: false,
  ai_model: 'unknown',
})

// 各区域加载状态
// trendLoading / pageLoading 已移除（趋势图区域已删除）

// 最近告警
const recentAlarms = ref([])

// 排序条件
const sortField = ref('')
const sortOrder = ref('')

// SSE 客户端
let sseClient = null
let pollTimer = null
let vibrationTimer = null
let cacheUpdateHandler = null
let sensorPagePreloadTask = null
let sensorCarouselFrame = null
let sensorCarouselPaused = false
const sensorTrackRef = ref(null)

// ==================== 传感器卡片配置 ====================

const sensorCards = [
  {
    key: 'temp_humidity', name: '温湿度传感器', path: '/monitor/temp', icon: tempIcon,
    values: [
      { label: '温度', field: 'temperature' },
      { label: '湿度', field: 'humidity' },
    ],
  },
  {
    key: 'wind', name: '风速风向传感器', path: '/monitor/wind', icon: windIcon,
    values: [
      { label: '风速', field: 'wind_speed_ms' },
      { label: '风向', field: 'wind_direction' },
    ],
  },
  {
    key: 'rain', name: '雨量计', path: '/monitor/rain', icon: rainIcon,
    values: [
      { label: '当天雨量', field: 'today_rain' },
      { label: '小时雨量', field: 'hour_rain' },
    ],
  },
  {
    key: 'vibration', name: '振动传感器', path: '/monitor/vibration', icon: vibrationIcon,
    values: [
      { label: 'RMS', field: 'total_rms' },
      { label: '主频', field: 'dominant_freq' },
      { label: '峰值因子', field: 'crest_factor' },
    ],
  },
  {
    key: 'camera', name: '摄像头设备', path: '/monitor/camera', icon: cameraIcon,
    values: [
      { label: '接入状态', field: 'device_status' },
      { label: '视频通道', field: 'channel_status' },
    ],
  },
  {
    key: 'beidou', name: '北斗通信', path: '/monitor/device', icon: beidouIcon,
    values: [
      { label: '链路状态', field: 'device_status' },
      { label: '定位状态', field: 'position_status' },
    ],
  },
]

// ==================== 计算属性 ====================

const statCards = computed(() => [
  { label: '感知设备总数', value: deviceTotal.value, icon: Monitor, color: '#409eff' },
  { label: '在线传感器', value: deviceOnline.value, icon: CircleCheck, color: '#67c23a' },
  { label: '累计告警事件', value: alarmTotal.value, icon: Warning, color: '#e6a23c' },
  { label: '紧急处置告警', value: alarmHigh.value, icon: WarningFilled, color: '#f56c6c' },
])

const aiModelHealthy = computed(() => systemInfo.value.ai_model === 'healthy')
const aiModelStatusText = computed(() => {
  const map = { healthy: '健康', unhealthy: '异常', unreachable: '无法连接', unknown: '未知' }
  return map[systemInfo.value.ai_model] || '未知'
})

const cpuColor = computed(() => {
  const v = systemInfo.value.cpu_percent || 0
  if (v > 80) return '#f56c6c'
  if (v > 50) return '#e6a23c'
  return '#67c23a'
})

const memColor = computed(() => {
  const v = systemInfo.value.memory?.percent || 0
  if (v > 80) return '#f56c6c'
  if (v > 50) return '#e6a23c'
  return '#409eff'
})

const diskColor = computed(() => {
  const v = systemInfo.value.disk?.percent || 0
  if (v > 80) return '#f56c6c'
  if (v > 50) return '#e6a23c'
  return '#409eff'
})

const gpuColor = computed(() => {
  const v = systemInfo.value.gpu?.utilization_percent || 0
  if (v > 80) return '#f56c6c'
  if (v > 50) return '#e6a23c'
  return '#76b900'
})

// 告警摘要计算属性
const alarmStatusText = computed(() => {
  if (alarmHigh.value > 0) return '存在紧急告警，请及时处理'
  if ((alarmTotal.value - alarmHigh.value) > 0) return '存在一般告警，请关注'
  return '当前无告警，系统运行正常'
})

// 排序后的最近告警
const sortedRecentAlarms = computed(() => {
  let list = recentAlarms.value.slice(0, 3)
  if (sortField.value) {
    list = [...list].sort((a, b) => {
      let comparison = 0
      if (sortField.value === 'time') {
        comparison = new Date(a.alarm_time) - new Date(b.alarm_time)
      } else if (sortField.value === 'level') {
        comparison = a.alarm_level - b.alarm_level
      } else if (sortField.value === 'status') {
        comparison = a.handle_status - b.handle_status
      }
      return sortOrder.value === 'asc' ? comparison : -comparison
    })
  }
  return list
})

// 排序切换
const toggleSort = (field) => {
  if (sortField.value === field) {
    if (sortOrder.value === 'asc') {
      sortOrder.value = 'desc'
    } else if (sortOrder.value === 'desc') {
      sortField.value = ''
      sortOrder.value = ''
    }
  } else {
    sortField.value = field
    sortOrder.value = 'asc'
  }
}

const sortIcon = (field) => {
  if (sortField.value !== field) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

const sortText = (field) => {
  if (sortField.value !== field) return '排序'
  return sortOrder.value === 'asc' ? '升序' : '降序'
}

const alarmStatusLevel = computed(() => {
  if (alarmHigh.value > 0) return 'level-high'
  if ((alarmTotal.value - alarmHigh.value) > 0) return 'level-warn'
  return 'level-ok'
})

// 占比计算（基于总数）
const alarmBarHigh = computed(() => {
  if (alarmTotal.value === 0) return 0
  return Math.round((alarmHigh.value / alarmTotal.value) * 100)
})
const alarmBarWarn = computed(() => {
  if (alarmTotal.value === 0) return 0
  return 100 - alarmBarHigh.value
})

// ==================== 数据获取 ====================

const apiCacheConfig = (url, params) => ({
  method: 'get',
  baseURL: '/api',
  url,
  params,
})

const applySensorRealtime = (data) => {
  if (data) sensorData.value = data
}

const applyDeviceStatus = (data) => {
  if (!data) return
  deviceStatus.value = data
  const keys = Object.keys(data)
  deviceTotal.value = keys.length
  deviceOnline.value = keys.filter(k => data[k]?.status === 'online').length
}

const applySystemInfo = (data) => {
  if (!data) return
  systemInfo.value = data
  if (data.sensor_count) {
    deviceTotal.value = data.sensor_count.total || deviceTotal.value
    deviceOnline.value = data.sensor_count.online || deviceOnline.value
  }
  if (data.sensor_status) {
    deviceStatus.value = { ...deviceStatus.value, ...data.sensor_status }
  }
}

const applyAlarmStats = (data) => {
  if (!data) return
  alarmTotal.value = data.total || 0
  alarmHigh.value = data.high_level || 0
  alarmUnhandled.value = data.unhandled || 0
}

const applyRecentAlarms = (data) => {
  if (data?.records) recentAlarms.value = data.records
}

const applyVibrationProcessed = (payload) => {
  if (!payload) return
  vibrationProcessedData.value = payload.data || payload
}

const readDashboardCache = (url, params) => readCachedResponse(apiCacheConfig(url, params))?.data

const hydrateDashboardFromCache = () => {
  const realtime = readDashboardCache('/v1/sensor/realtime')
  if (realtime?.code === 200) applySensorRealtime(realtime.data)

  const status = readDashboardCache('/v1/sensor/status')
  if (status?.code === 200) applyDeviceStatus(status.data)

  const system = readDashboardCache('/v1/system/info')
  if (system?.code === 200) applySystemInfo(system.data)

  const alarmStats = readDashboardCache('/alarm/statistics')
  if (alarmStats?.code === 200) applyAlarmStats(alarmStats.data)

  const alarms = readDashboardCache('/alarm/list', { page_num: 1, page_size: 5 })
  if (alarms?.code === 200) applyRecentAlarms(alarms.data)
}

const applyDashboardCacheUpdate = (event) => {
  const { url, params, data } = event.detail || {}
  if (!data || data.code !== 200) return

  if (url === '/v1/sensor/realtime') applySensorRealtime(data.data)
  if (url === '/v1/sensor/status') applyDeviceStatus(data.data)
  if (url === '/v1/system/info') applySystemInfo(data.data)
  if (url === '/alarm/statistics') applyAlarmStats(data.data)
  if (url === '/alarm/list' && params?.page_num === 1 && params?.page_size === 5) {
    applyRecentAlarms(data.data)
  }
}

/** 获取传感器实时数据 + 设备状态 */
const fetchSensorData = async () => {
  try {
    const res = await getAllSensorRealtime()
    if (res.code === 200 && res.data) {
      applySensorRealtime(res.data)
    }
  } catch (e) { /* 忽略错误，SSE 会补充 */ }

  try {
    const statusRes = await getDeviceStatus()
    if (statusRes.code === 200 && statusRes.data) {
      applyDeviceStatus(statusRes.data)
    }
  } catch (e) { /* 使用默认值 */ }
}

/** 获取振动处理后指标：RMS / 主频 / 峰值因子 */
const fetchVibrationProcessed = async () => {
  try {
    const res = await getVibrationProcessed()
    if (res.code === 200 && res.data) {
      applyVibrationProcessed(res.data)
    }
  } catch (e) { /* 保持上一次振动处理数据 */ }
}

/** 获取告警统计 */
const fetchAlarmStats = async () => {
  try {
    const res = await getAlarmStatistics()
    if (res.code === 200 && res.data) {
      applyAlarmStats(res.data)
    }
  } catch (e) { /* 保持上一次数据 */ }
}

/** 获取系统状态 */
const fetchSystemInfo = async () => {
  try {
    const res = await getSystemInfo()
    if (res.code === 200 && res.data) {
      applySystemInfo(res.data)
    }
  } catch (e) { /* 保持上一次数据 */ }
}

/** 获取最近告警列表 */
const fetchRecentAlarms = async () => {
  try {
    const res = await getAlarmList({ page_num: 1, page_size: 5 })
    if (res.code === 200 && res.data?.records) {
      applyRecentAlarms(res.data)
    }
  } catch (e) { /* 保持上一次数据 */ }
}

/**
 * 初始化加载数据 — 分两阶段
 *
 * 阶段一（首屏必出，3 个快接口）：实时数据 + 系统状态 + 设备状态
 /**
 * 初始化加载数据 — 分两阶段
 *
 * 阶段一（首屏必出，快接口）：实时数据 + 系统状态
 * 阶段二（首屏后异步）：告警统计 + 最近告警（不阻塞首屏）
 */
const initData = async () => {
  // 阶段一：先让页面渲染出来
  await Promise.all([
    fetchSensorData(),
    fetchSystemInfo(),
    fetchVibrationProcessed(),
  ])

  // 阶段二：异步加载告警数据，不阻塞 UI
  setTimeout(async () => {
    await Promise.all([
      fetchAlarmStats(),
      fetchRecentAlarms(),
    ])
  }, 0)
}

const preloadSensorPagesLater = () => {
  if (sensorPagePreloadTask) cancelIdleTask(sensorPagePreloadTask)
  sensorPagePreloadTask = runWhenIdle(() => {
    sensorPagePreloadTask = null
    Promise.allSettled([
      import('@/views/Monitor/SensorTemp.vue'),
      import('@/views/Monitor/SensorWind.vue'),
      import('@/views/Monitor/SensorRain.vue'),
      import('@/views/Monitor/SensorVibration.vue'),
    ])
  }, 6000)
}

const sensorCardStride = () => {
  const track = sensorTrackRef.value
  const firstCard = track?.querySelector?.('.sensor-card-slot')
  if (!track || !firstCard) return 430
  const gap = Number.parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap || '14')
  return firstCard.getBoundingClientRect().width + (Number.isFinite(gap) ? gap : 14)
}

const startSensorCarousel = () => {
  if (sensorCarouselFrame) cancelAnimationFrame(sensorCarouselFrame)
  const tick = () => {
    const track = sensorTrackRef.value
    if (track && !sensorCarouselPaused && track.scrollWidth > track.clientWidth + 4) {
      track.scrollLeft += 0.35
      if (track.scrollLeft >= track.scrollWidth - track.clientWidth - 2) {
        track.scrollTo({ left: 0, behavior: 'smooth' })
      }
    }
    sensorCarouselFrame = requestAnimationFrame(tick)
  }
  sensorCarouselFrame = requestAnimationFrame(tick)
}

const pauseSensorCarousel = () => {
  sensorCarouselPaused = true
}

const resumeSensorCarousel = () => {
  sensorCarouselPaused = false
}

const scrollSensorCards = (direction) => {
  pauseSensorCarousel()
  sensorTrackRef.value?.scrollBy({ left: sensorCardStride() * direction, behavior: 'smooth' })
}

// ==================== SSE 实时推送 ====================

const connectSSE = () => {
  if (sseClient) sseClient.close()
  sseClient = new SensorSSE('/api/v1/sensor/stream')
  sseClient.on('sensor_update', (event) => {
    if (event.data) {
      sensorData.value = { ...sensorData.value, ...event.data }
    }
  })
  sseClient.connect()
}

const disconnectSSE = () => {
  if (sseClient) { sseClient.close(); sseClient = null }
}

// ==================== 格式化工具 ====================

const getSensorOnline = (key) => {
  return deviceStatus.value[key]?.status === 'online'
}

const formatSensorValue = (key, field) => {
  if (field === 'device_status') return getSensorOnline(key) ? '在线' : '离线'
  if (field === 'channel_status') return getSensorOnline(key) ? '待检测' : '--'
  if (field === 'position_status') return getSensorOnline(key) ? '已接入' : '--'
  const d = key === 'vibration' ? vibrationProcessedData.value : sensorData.value[key]?.data
  if (!d || d[field] == null) return '--'
  const v = d[field]
  if (typeof v === 'number') {
    // 根据字段类型决定精度
    if (field === 'total_rms') return v.toFixed(4) + 'g'
    if (field === 'dominant_freq') return v.toFixed(1) + 'Hz'
    if (field === 'crest_factor') return v.toFixed(1)
    if (field === '温度' || field === 'temperature') return v.toFixed(1) + '℃'
    if (field === 'humidity') return v.toFixed(1) + '%'
    if (field === 'wind_speed_ms') return v.toFixed(1) + ' m/s'
    if (field === 'today_rain' || field === 'hour_rain') return v.toFixed(1) + ' mm'
    // 振动加速度：值通常很小（0.0001~0.05 g 级别），自动适配小数位
    if (field === '加速度X' || field === '加速度Y' || field === '加速度Z') {
      const abs = Math.abs(v)
      if (abs === 0) return '0.0000 g'
      if (abs < 0.001) return v.toFixed(6) + ' g'
      if (abs < 0.01) return v.toFixed(5) + ' g'
      if (abs < 0.1) return v.toFixed(4) + ' g'
      return v.toFixed(3) + ' g'
    }
    return v.toFixed(1)
  }
  return v
}

const formatUptime = (hours) => {
  if (!hours && hours !== 0) return '--'
  return hours.toFixed(1) + ' 小时'
}

const formatCurrentTime = () => {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

const formatAlarmTime = (t) => {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

const alarmLevelTag = (level) => {
  if (level === 3) return 'danger'
  if (level === 2) return 'warning'
  return 'info'
}

const alarmLevelText = (level) => {
  if (level === 3) return '紧急'
  if (level === 2) return '中等'
  return '低'
}

const alarmTypeText = (type) => {
  const typeMap = {
    'threshold': '阈值触发',
    'ai': 'AI检测',
    'manual': '手动触发'
  }
  return typeMap[type] || type || '--'
}

const alarmTypeTag = (type) => {
  const tagMap = {
    'threshold': 'warning',
    'ai': 'danger',
    'manual': 'info'
  }
  return tagMap[type] || 'info'
}

// ==================== 生命周期 ====================

hydrateDashboardFromCache()

onMounted(async () => {
  // 实时时钟
  currentTime.value = formatCurrentTime()
  clockTimer = setInterval(() => { currentTime.value = formatCurrentTime() }, 1000)

  cacheUpdateHandler = applyDashboardCacheUpdate
  window.addEventListener('dam-api-cache-updated', cacheUpdateHandler)

  // initData 内部已分阶段加载告警/历史，无需在这里 await 全部完成
  initData()

  // 立即建立 SSE 连接，让传感器数据秒级推送
  setTimeout(() => connectSSE(), 100)

  preloadSensorPagesLater()

  // 每 30 秒轮询系统状态和告警统计（CPU/内存/磁盘等变化慢）
  pollTimer = setInterval(async () => {
    await Promise.all([
      fetchSystemInfo(),
      fetchAlarmStats(),
      fetchRecentAlarms(),
    ])
  }, 30000)

  vibrationTimer = setInterval(fetchVibrationProcessed, 5000)
  startSensorCarousel()
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  disconnectSSE()
  if (pollTimer) clearInterval(pollTimer)
  if (vibrationTimer) clearInterval(vibrationTimer)
  if (cacheUpdateHandler) window.removeEventListener('dam-api-cache-updated', cacheUpdateHandler)
  if (sensorPagePreloadTask) cancelIdleTask(sensorPagePreloadTask)
  if (sensorCarouselFrame) cancelAnimationFrame(sensorCarouselFrame)
})
</script>

<style scoped>
.dashboard {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px;
}

/* 覆盖全局 .data-panel 的 margin-bottom，统一用 section-gap 控制间距 */
.dashboard :deep(.data-panel) {
  margin-bottom: 0;
}

/* ========== 统计卡片 ========== */
.stat-row {
  margin-bottom: 14px;
}

/* ========== 传感器卡片行 ========== */
.sensor-carousel {
  position: relative;
  margin-bottom: 14px;
}

.sensor-row {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(420px, 1fr);
  gap: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 2px;
  scroll-snap-type: x proximity;
  scroll-behavior: smooth;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.sensor-row::-webkit-scrollbar {
  display: none;
}

.sensor-card-slot {
  min-width: 0;
  scroll-snap-align: start;
}

.carousel-arrow {
  position: absolute;
  top: 50%;
  z-index: 6;
  width: 32px;
  height: 58px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(185, 176, 160, 0.58);
  border-radius: 5px;
  background: rgba(205, 195, 178, 0.88);
  color: #4a3d31;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
  cursor: pointer;
  opacity: 0;
  transform: translateY(-50%) scale(0.92);
  transition: opacity 0.18s ease, transform 0.18s ease, background 0.18s ease;
}

.carousel-arrow.left {
  left: 4px;
}

.carousel-arrow.right {
  right: 4px;
}

.sensor-carousel:hover .carousel-arrow {
  opacity: 1;
  transform: translateY(-50%) scale(1);
}

.carousel-arrow:hover {
  background: rgba(224, 216, 201, 0.96);
}

/* ========== 系统状态+告警分布行 ========== */
.health-alarm-row {
  margin-bottom: 14px;
  display: flex;
  align-items: stretch;
}

.health-alarm-row > .el-col {
  display: flex;
}

.health-alarm-row .data-panel {
  flex: 1;
}

/* ========== 最近告警 ========== */
.alarm-recent-row {
  margin-bottom: 14px;
  padding: 16px 0;
}

.alarm-recent-row .panel-title {
  padding-left: 20px;
  padding-right: 20px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 22px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: transform 0.3s, box-shadow 0.3s;
  cursor: default;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(0, 200, 255, 0.15);
}
.stat-icon {
  width: 58px;
  height: 58px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info {
  flex: 1;
  text-align: right;
}
.stat-value {
  font-size: 38px;
  font-weight: 800;
  line-height: 1.2;
  text-shadow: 0 0 12px currentColor;
}
.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* ========== 传感器数据卡片 ========== */
.sensor-card-row {
  margin-bottom: 0;
}

/* ========== 区域统一间距 ========== */
.sensor-data-card {
  background: rgba(20, 40, 70, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.sensor-data-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 200, 255, 0.2);
  border-color: rgba(0, 200, 255, 0.6);
}
.sensor-card-top {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
}
.sensor-img {
  width: 52px;
  height: 52px;
  object-fit: cover;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  flex-shrink: 0;
}
.sensor-card-info {
  flex: 1;
  min-width: 0;
}
.sensor-card-name {
  font-size: 16px;
  font-weight: 600;
  color: #E2F0FE;
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sensor-card-status {
  font-size: 15px;
  color: #AECAF5;
  display: flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.sensor-card-values {
  padding: 12px 16px 14px;
  flex: 1;
}

/* 数值网格：单列（默认）或两列（>2 个值时，如振动 X/Y/Z） */
.sensor-value-grid {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sensor-value-grid.two-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sensor-value-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}
.sensor-value-grid.two-col .sensor-value-row {
  align-items: center;
  flex-direction: row;
  gap: 8px;
  padding: 6px 0;
}
.sensor-value-label {
  color: #AECAF5;
  font-size: 13px;
}
.sensor-value-num {
  color: var(--accent-color);
  font-size: 15px;
  font-weight: 600;
  font-family: "Consolas", "Monaco", monospace;
}

/* ========== 系统运行状态面板 ========== */
.system-health-panel {
  min-height: 320px;
}

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.health-clock {
  font-size: 18px;
  color: var(--accent-color);
  font-family: "Consolas", "Monaco", monospace;
  padding: 4px 14px;
  background: rgba(0, 229, 255, 0.1);
  border: 1px solid rgba(0, 229, 255, 0.25);
  border-radius: 6px;
}

/* 顶部两个中卡片 */
.health-top-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.health-item-medium {
  padding: 22px 24px;
}

.health-item-medium .health-icon {
  width: 48px;
  height: 48px;
}

.health-item-medium .health-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-item-medium .health-label {
  font-size: 14px;
  margin-bottom: 0;
}

.health-item-medium .health-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: "Consolas", "Monaco", monospace;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.gpu-vendor {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 4px;
  font-weight: normal;
}

.gpu-meta {
  margin-left: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}
.gpu-meta i {
  font-style: normal;
  margin-right: 6px;
  padding: 1px 5px;
  background: rgba(0, 200, 255, 0.08);
  border-radius: 3px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  border: 1px solid rgba(0, 200, 255, 0.08);
}

.health-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.health-body {
  flex: 1;
  min-width: 0;
}

.health-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.health-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.health-value .el-progress {
  display: inline-block;
  width: 80px;
  margin-right: 8px;
  vertical-align: middle;
}

/* ========== 告警态势分布面板 ========== */

/* 顶部状态条 */
.alarm-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 14px;
}
.alarm-status-bar.level-ok {
  background: rgba(103,194,58,0.08);
  border: 1px solid rgba(103,194,58,0.15);
}
.alarm-status-bar.level-warn {
  background: rgba(230,162,60,0.08);
  border: 1px solid rgba(230,162,60,0.15);
}
.alarm-status-bar.level-high {
  background: rgba(255,92,92,0.08);
  border: 1px solid rgba(255,92,92,0.15);
}

.alarm-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.level-ok .alarm-status-dot { background: #67c23a; }
.level-warn .alarm-status-dot { background: #e6a23c; }
.level-high .alarm-status-dot { background: #ff5c5c; }

.alarm-status-text {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
}
.level-ok .alarm-status-text { color: #67c23a; }
.level-warn .alarm-status-text { color: #e6a23c; }
.level-high .alarm-status-text { color: #ff5c5c; }

/* 中间三个指标卡片 */
.alarm-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.alarm-metric-card {
  background: rgba(10,31,55,0.55);
  border: 1px solid rgba(0,216,255,0.12);
  border-radius: 6px;
  padding: 14px 12px;
  text-align: center;
  transition: border-color 0.2s;
}
.alarm-metric-card:hover {
  border-color: rgba(0,216,255,0.25);
}

.alarm-metric-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.alarm-metric-value {
  font-size: 26px;
  font-weight: 700;
  font-family: "Consolas", "Monaco", monospace;
  line-height: 1;
}
.alarm-metric-high .alarm-metric-value { color: #ff5c5c; }
.alarm-metric-warn .alarm-metric-value { color: #e6a23c; }
.alarm-metric-ok .alarm-metric-value { color: #67c23a; }

/* 底部横向占比条 */
.alarm-bar-section {
  margin-top: auto;
}

.alarm-bar {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: rgba(0,0,0,0.3);
  gap: 2px;
}

.alarm-bar-seg {
  height: 100%;
  border-radius: 5px;
  transition: width 0.4s ease;
  min-width: 0;
}
.alarm-bar-seg:first-child { border-radius: 5px 0 0 5px; }
.alarm-bar-seg:last-child { border-radius: 0 5px 5px 0; }
.alarm-bar-high { background: #ff5c5c; }
.alarm-bar-warn { background: #e6a23c; }
.alarm-bar-ok { background: #67c23a; opacity: 0.85; }

.alarm-bar-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.alarm-bar-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.alarm-bar-legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

/* ========== 告警处理建议 ========== */
.alarm-tips {
  margin-top: 14px;
  padding: 14px 16px;
  background: rgba(0, 20, 50, 0.5);
  border: 1px solid rgba(0, 200, 255, 0.12);
  border-radius: 8px;
}
.alarm-tips-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.alarm-tips-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 2px 0;
}
.alarm-tips-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 200, 255, 0.3);
  margin-top: 7px;
  flex-shrink: 0;
}
.alarm-tips-dot-high { background: #f56c6c; }
.alarm-tips-dot-warn { background: #e6a23c; }
.alarm-tips-dot-ok { background: #67c23a; }

/* ========== 最近告警列表（与告警管理页统一风格） ========== */

.alarm-list-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: rgba(0, 100, 150, 0.2);
  font-size: 12px;
  font-weight: 600;
  color: rgba(224, 240, 255, 0.5);
  border-bottom: 1px solid rgba(0, 200, 255, 0.08);
}

.alarm-list-header > div {
  justify-content: center;
  text-align: center;
}

.alarm-preview-list {
  display: flex;
  flex-direction: column;
}

.alarm-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.06);
  transition: background 0.2s;
}

.alarm-item:last-child {
  border-bottom: none;
}

.alarm-item:hover {
  background: rgba(0, 200, 255, 0.06);
}

.alarm-item.is-unhandled {
  background: rgba(245, 108, 108, 0.05);
}

.col-time {
  flex: 1;
  font-size: 12px;
  color: rgba(224, 240, 255, 0.6);
  text-align: center;
}

.col-level {
  flex: 1;
  text-align: center;
}

.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s, background 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 28px;
  border-radius: 6px;
}

.sortable:hover {
  color: #00a8ff;
  background: rgba(0, 168, 255, 0.08);
}

.sort-pill {
  min-width: 52px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border: 1px solid rgba(114, 163, 205, 0.24);
  border-radius: 999px;
  color: rgba(174, 202, 245, 0.72);
  background: rgba(4, 26, 44, 0.52);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  transition: all 0.2s;
}

.sortable:hover .sort-pill {
  color: #00a8ff;
  border-color: rgba(0, 168, 255, 0.42);
}

.sort-pill.active {
  color: #071b24;
  border-color: transparent;
  background: linear-gradient(110deg, #36d4ff, #52e5bd);
  box-shadow: 0 0 12px rgba(0, 168, 255, 0.22);
}

.sort-icon {
  font-size: 11px;
  line-height: 1;
}

.col-type {
  flex: 1;
  text-align: center;
}

.col-desc {
  flex: 2;
  font-size: 12px;
  color: rgba(224, 240, 255, 0.8);
  text-align: center;
  padding: 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desc-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.desc-text:hover {
  background: rgba(0, 168, 255, 0.15);
  color: #00a8ff;
}

.col-content {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
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

/* 级别标签 */
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

/* 类型标签 */
.type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.type-ai { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }
.type-threshold { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }
.type-manual { background: rgba(144, 147, 153, 0.15); color: #909399; }

/* 状态标签 */
.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-tag.handled { background: rgba(103, 194, 58, 0.15); color: #67c23a; }
.status-tag.unhandled { background: rgba(245, 108, 108, 0.15); color: #f56c6c; }

.alarm-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}

.link-btn {
  font-size: 13px;
  color: var(--accent-color);
  cursor: pointer;
}
.link-btn:hover {
  text-decoration: underline;
}

</style>
