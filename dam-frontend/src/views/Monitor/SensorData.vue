<template>
  <div class="sensor-data">
    <!-- 页面标题 -->
    <div class="page-title">传感器监测中心</div>

    <el-row :gutter="16">
      <!-- 温湿度卡片 -->
      <el-col :span="6">
        <div class="data-card" @click="handleCardClick('temp_humidity')">
          <div class="card-content">
            <div class="card-img-wrapper">
              <img src="@/assets/images/sensors/temp_humidity.png" class="card-img" />
            </div>
            <div class="card-info">
              <div class="card-name">温湿度传感器</div>
              <div class="card-status">
                <span class="dot" :class="getStatusClass('temp_humidity')"></span>
                {{ getStatusText('temp_humidity') }}
              </div>
            </div>
          </div>
          <div class="card-data">
            <div class="data-item">
              <span class="data-label">温度</span>
              <span class="data-value">{{ sensorData.temp_humidity?.data?.temperature?.toFixed(1) || '--' }}<i>℃</i></span>
            </div>
            <div class="data-item">
              <span class="data-label">湿度</span>
              <span class="data-value">{{ sensorData.temp_humidity?.data?.humidity?.toFixed(1) || '--' }}<i>%</i></span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 风速风向卡片 -->
      <el-col :span="6">
        <div class="data-card" @click="handleCardClick('wind')">
          <div class="card-content">
            <div class="card-img-wrapper">
              <img src="@/assets/images/sensors/wind.png" class="card-img" />
            </div>
            <div class="card-info">
              <div class="card-name">风速风向传感器</div>
              <div class="card-status">
                <span class="dot" :class="getStatusClass('wind')"></span>
                {{ getStatusText('wind') }}
              </div>
            </div>
          </div>
          <div class="card-data">
            <div class="data-item">
              <span class="data-label">风速</span>
              <span class="data-value">{{ sensorData.wind?.data?.wind_speed_ms?.toFixed(1) || '--' }}<i>m/s</i></span>
            </div>
            <div class="data-item">
              <span class="data-label">风向</span>
              <span class="data-value">{{ sensorData.wind?.data?.wind_direction || '--' }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 雨量计卡片 -->
      <el-col :span="6">
        <div class="data-card" @click="handleCardClick('rain')">
          <div class="card-content">
            <div class="card-img-wrapper">
              <img src="@/assets/images/sensors/rain.png" class="card-img" />
            </div>
            <div class="card-info">
              <div class="card-name">雨量计</div>
              <div class="card-status">
                <span class="dot" :class="getStatusClass('rain')"></span>
                {{ getStatusText('rain') }}
              </div>
            </div>
          </div>
          <div class="card-data">
            <div class="data-item">
              <span class="data-label">当天</span>
              <span class="data-value">{{ sensorData.rain?.data?.today_rain?.toFixed(1) || '--' }}<i>mm</i></span>
            </div>
            <div class="data-item">
              <span class="data-label">小时</span>
              <span class="data-value">{{ sensorData.rain?.data?.hour_rain?.toFixed(1) || '--' }}<i>mm</i></span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 振动传感器卡片 -->
      <el-col :span="6">
        <div class="data-card" @click="handleCardClick('vibration')">
          <div class="card-content">
            <div class="card-img-wrapper">
              <img src="@/assets/images/sensors/vibration.png" class="card-img" />
            </div>
            <div class="card-info">
              <div class="card-name">振动传感器</div>
              <div class="card-status">
                <span class="dot" :class="getStatusClass('vibration')"></span>
                {{ getStatusText('vibration') }}
              </div>
            </div>
          </div>
          <div class="card-data">
            <div class="data-item">
              <span class="data-label">加速度X</span>
              <span class="data-value">{{ sensorData.vibration?.data?.['加速度X']?.toFixed(4) || '--' }}<i>g</i></span>
            </div>
            <div class="data-item">
              <span class="data-label">温度</span>
              <span class="data-value">{{ sensorData.vibration?.data?.['温度']?.toFixed(1) || '--' }}<i>℃</i></span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 底部状态栏 -->
    <div class="status-bar">
      <div class="status-left">
        <span class="status-dot" :class="sseConnected ? 'online' : 'offline'"></span>
        <span>SSE {{ sseConnected ? '已连接' : '未连接' }}</span>
        <el-button size="small" type="primary" @click="connectSSE" :disabled="sseConnected">连接</el-button>
        <el-button size="small" @click="disconnectSSE" :disabled="!sseConnected">断开</el-button>
      </div>
      <div class="status-right">
        最后更新: {{ lastUpdateTime }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getAllSensorRealtime, getDeviceStatus } from '@/api/sensor'
import SensorSSE from '@/utils/sensorSSE'

const sensorData = ref({})
const deviceStatus = ref({})
const sseConnected = ref(false)
const lastUpdateTime = ref('--')
let sseClient = null

const fetchData = async () => {
  try {
    const res = await getAllSensorRealtime()
    if (res.code === 200) {
      sensorData.value = res.data || {}
      lastUpdateTime.value = new Date().toLocaleTimeString()
    }
    const statusRes = await getDeviceStatus()
    if (statusRes.code === 200) {
      deviceStatus.value = statusRes.data || {}
    }
  } catch (error) {
    lastUpdateTime.value = new Date().toLocaleTimeString()
  }
}

const connectSSE = () => {
  if (sseClient) sseClient.close()
  sseClient = new SensorSSE('/api/v1/sensor/stream')
  sseClient.on('sensor_update', (event) => {
    sensorData.value = event.data || {}
    lastUpdateTime.value = new Date().toLocaleTimeString()
    sseConnected.value = true
  })
  sseClient.connect()
}

const disconnectSSE = () => {
  if (sseClient) { sseClient.close(); sseClient = null }
  sseConnected.value = false
}

const handleCardClick = (name) => {
  console.log('点击卡片:', name)
}

const getStatusClass = (deviceName) => {
  const status = deviceStatus.value[deviceName]?.status
  if (status === 'online') return 'online'
  if (status === 'offline') return 'offline'
  return 'unknown'
}

const getStatusText = (deviceName) => {
  const status = deviceStatus.value[deviceName]?.status
  if (status === 'online') return '在线'
  if (status === 'offline') return '离线'
  return '未知'
}

onMounted(() => { fetchData(); connectSSE() })
onUnmounted(() => { disconnectSSE() })
</script>

<style scoped>
.sensor-data {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 页面标题 */
.page-title {
  text-align: center;
  font-size: 22px;
  font-weight: bold;
  color: #00e5ff;
  margin-bottom: 20px;
  text-shadow: 0 0 15px rgba(0, 229, 255, 0.5);
  letter-spacing: 4px;
}

/* 数据卡片 - 参考截图的设备卡片样式 */
.data-card {
  background: rgba(20, 40, 70, 0.6);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

/* 卡片发光边框效果 */
.data-card::before {
  content: '';
  position: absolute;
  top: -1px;
  left: -1px;
  right: -1px;
  bottom: -1px;
  border-radius: 12px;
  background: linear-gradient(135deg,
    rgba(0, 200, 255, 0.4) 0%,
    rgba(0, 200, 255, 0.1) 50%,
    rgba(0, 200, 255, 0.4) 100%
  );
  z-index: -1;
  opacity: 0;
  transition: opacity 0.3s;
}

.data-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 200, 255, 0.2);
  border-color: rgba(0, 200, 255, 0.6);
}

.data-card:hover::before {
  opacity: 1;
}

/* 卡片内容区 */
.card-content {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.1);
}

.card-img-wrapper {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  flex-shrink: 0;
}

.card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-info {
  flex: 1;
}

.card-name {
  font-size: 16px;
  font-weight: 600;
  color: #E2F0FE;
  margin-bottom: 8px;
}

.card-status {
  font-size: 12px;
  color: #AECAF5;
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.card-status .dot.online {
  background: #67c23a;
  box-shadow: 0 0 6px #67c23a;
}

.card-status .dot.offline {
  background: #f56c6c;
  box-shadow: 0 0 6px #f56c6c;
}

.card-status .dot.unknown {
  background: #909399;
}

/* 卡片数据区 */
.card-data {
  padding: 12px 20px;
}

.data-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.data-label {
  color: #AECAF5;
  font-size: 13px;
}

.data-value {
  color: #E2F0FE;
  font-size: 16px;
  font-weight: 600;
}

.data-value i {
  font-style: normal;
  font-size: 11px;
  color: rgba(174, 202, 245, 0.6);
  margin-left: 3px;
}

/* 底部状态栏 */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: rgba(30, 58, 95, 0.5);
  border: 1px solid rgba(0, 200, 255, 0.15);
  border-radius: 8px;
  margin-top: auto;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #AECAF5;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: #67c23a;
  box-shadow: 0 0 8px #67c23a;
}

.status-dot.offline {
  background: #f56c6c;
  box-shadow: 0 0 8px #f56c6c;
}

.status-right {
  color: #AECAF5;
  font-size: 13px;
}
</style>
