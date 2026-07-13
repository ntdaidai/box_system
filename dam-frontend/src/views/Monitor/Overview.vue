<template>
  <div class="overview-container">
    <div class="title">智能感知监测中心</div>
    <div class="sensor-grid">
      <div v-for="sensor in sensors" :key="sensor.name"
           class="sensor-card"
           @click="goTo(sensor.path)">
        <img :src="sensor.icon" class="sensor-icon" />
        <div class="sensor-name">{{ sensor.name }}</div>
        <div class="sensor-status" :class="getStatusClass(sensor.key)">
          <span class="status-dot" :class="getStatusClass(sensor.key)"></span>
          {{ getStatusText(sensor.key) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDeviceStatus } from '@/api/sensor'
import tempIcon from '@/assets/images/sensors/temp_humidity.png'
import windIcon from '@/assets/images/sensors/wind.png'
import rainIcon from '@/assets/images/sensors/rain.png'
import vibrationIcon from '@/assets/images/sensors/vibration.png'
import cameraIcon from '@/assets/images/sensors/camera.png'
import beidouIcon from '@/assets/images/sensors/beidou.png'

const router = useRouter()
const deviceStatus = ref({})

const sensors = [
  { name: '温湿度传感器', key: 'temp_humidity', path: '/monitor/temp', icon: tempIcon },
  { name: '风速风向传感器', key: 'wind', path: '/monitor/wind', icon: windIcon },
  { name: '雨量计', key: 'rain', path: '/monitor/rain', icon: rainIcon },
  { name: '振动传感器', key: 'vibration', path: '/monitor/vibration', icon: vibrationIcon },
  { name: '视频监控', key: 'camera', path: '/monitor/camera', icon: cameraIcon },
  { name: '北斗通讯', key: 'beidou', path: '/monitor/device', icon: beidouIcon },
]

const goTo = (path) => router.push(path)

const getStatusClass = (key) => {
  const status = deviceStatus.value[key]?.status
  if (status === 'online') return 'online'
  return 'offline'
}

const getStatusText = (key) => {
  const status = deviceStatus.value[key]?.status
  if (status === 'online') return '在线'
  return '离线'
}

const fetchStatus = async () => {
  try {
    const res = await getDeviceStatus()
    if (res.code === 200) {
      deviceStatus.value = res.data || {}
    }
  } catch (error) {
    // 使用模拟状态
    deviceStatus.value = {
      temp_humidity: { status: 'online' },
      wind: { status: 'online' },
      rain: { status: 'online' },
      vibration: { status: 'online' },
      camera: { status: 'offline' },
      beidou: { status: 'offline' },
    }
  }
}

onMounted(() => { fetchStatus() })
</script>

<style scoped>
.overview-container {
  width: 100%;
  height: 100%;
  background: radial-gradient(ellipse at center, #0a1a2f 0%, #050d18 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow-y: auto;
}
.title {
  font-size: 40px;
  font-weight: bold;
  color: var(--accent-color);
  text-shadow: 0 0 30px var(--accent-glow), 0 0 60px rgba(0, 229, 255, 0.3);
  margin-bottom: 60px;
  letter-spacing: 8px;
}
.sensor-grid {
  display: grid;
  grid-template-columns: repeat(3, 300px);
  gap: 50px;
}
.sensor-card {
  width: 300px;
  height: 300px;
  background: rgba(0, 40, 80, 0.4);
  border: 1px solid rgba(0, 200, 255, 0.4);
  box-shadow: 0 0 20px rgba(0, 150, 255, 0.6), inset 0 0 30px rgba(0, 100, 200, 0.1);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
}
.sensor-card:hover {
  transform: scale(1.08);
  box-shadow: 0 0 40px rgba(0, 255, 255, 0.6), 0 0 80px rgba(0, 200, 255, 0.3);
  border-color: #00ffff;
}
.sensor-icon {
  width: 150px;
  height: 150px;
  object-fit: contain;
  filter: drop-shadow(0 0 12px rgba(0, 200, 255, 0.6));
  margin-bottom: 20px;
}
.sensor-name {
  font-size: 20px;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.sensor-status {
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sensor-status.online { color: var(--success-color); }
.sensor-status.offline { color: var(--danger-color); }
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.online { background: var(--success-color); box-shadow: 0 0 8px var(--success-color); }
.status-dot.offline { background: var(--danger-color); box-shadow: 0 0 8px var(--danger-color); }
</style>
