<template>
  <div class="overview-container">
    <div class="title">智能感知监测中心</div>
    <div class="sensor-grid">
      <div
        v-for="sensor in sensors"
        :key="sensor.name"
        class="sensor-card"
      >
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
import { getCameraList } from '@/api/camera'
import { getDeviceStatus } from '@/api/sensor'
import tempIcon from '@/assets/images/sensors/temp_humidity.png'
import windIcon from '@/assets/images/sensors/wind.png'
import rainIcon from '@/assets/images/sensors/rain.png'
import vibrationIcon from '@/assets/images/sensors/vibration.png'
import cameraIcon from '@/assets/images/sensors/camera.png'

const deviceStatus = ref({})

const sensors = [
  { name: '温湿度传感器', key: 'temp_humidity', icon: tempIcon },
  { name: '风速风向传感器', key: 'wind', icon: windIcon },
  { name: '雨量计', key: 'rain', icon: rainIcon },
  { name: '振动传感器', key: 'vibration', icon: vibrationIcon },
  { name: '视频监控', key: 'camera', icon: cameraIcon },
  { name: 'AGX 边缘计算盒', key: 'agx', icon: '/agx.jpg' },
]

const getStatusClass = (key) => {
  if (key === 'agx') return deviceStatus.value.agx?.status || 'online'
  const status = deviceStatus.value[key]?.status
  if (status === 'online') return 'online'
  if (status === 'partial') return 'partial'
  return 'offline'
}

const getStatusText = (key) => {
  if (key === 'agx') return deviceStatus.value.agx?.status === 'offline' ? '离线' : '在线'
  const status = deviceStatus.value[key]?.status
  if (key === 'camera') {
    const item = deviceStatus.value.camera || {}
    return `${item.online || 0}/${item.total || 0} 通道在线`
  }
  if (status === 'online') return '在线'
  return '离线'
}

const defaultStatus = {
  temp_humidity: { status: 'online' },
  wind: { status: 'online' },
  rain: { status: 'online' },
  vibration: { status: 'online' },
  camera: { status: 'offline' },
  agx: { status: 'online' },
}

const fetchStatus = async () => {
  try {
    const res = await getDeviceStatus()
    if (res.code === 200) {
      deviceStatus.value = { ...defaultStatus, ...(res.data || {}) }
    } else {
      deviceStatus.value = { ...defaultStatus }
    }
  } catch (error) {
    deviceStatus.value = { ...defaultStatus }
  }

  try {
    const res = await getCameraList()
    const cameras = res.data?.cameras || []
    const onlineCount = cameras.filter(camera => camera.connected).length
    deviceStatus.value = {
      ...deviceStatus.value,
      camera: {
        status: onlineCount === 0 ? 'offline' : (onlineCount === cameras.filter(camera => camera.enabled).length ? 'online' : 'partial'),
        online: onlineCount,
        total: cameras.filter(camera => camera.enabled).length,
      },
    }
  } catch (error) {
    deviceStatus.value = {
      ...deviceStatus.value,
      camera: { status: 'offline', online: 0, total: 0 },
    }
  }
}

onMounted(() => {
  fetchStatus()
})
</script>

<style scoped>
.overview-container {
  width: 100%;
  min-height: 100%;
  background: radial-gradient(ellipse at center, #0a1a2f 0%, #050d18 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow-y: auto;
  overflow-x: hidden;
  padding: clamp(28px, 5vh, 56px) 20px;
  box-sizing: border-box;
}

.title {
  font-size: 40px;
  font-weight: bold;
  color: var(--accent-color);
  text-shadow: 0 0 30px var(--accent-glow), 0 0 60px rgba(0, 229, 255, 0.3);
  margin: 0 0 clamp(28px, 5vh, 56px);
  letter-spacing: 8px;
  line-height: 1.2;
  text-align: center;
}

.sensor-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 300px));
  gap: clamp(24px, 4vw, 50px);
  width: min(100%, 1000px);
  justify-content: center;
}

.sensor-card {
  width: 100%;
  aspect-ratio: 1 / 1;
  min-height: 220px;
  max-height: 300px;
  background: rgba(0, 40, 80, 0.4);
  border: 1px solid rgba(0, 200, 255, 0.4);
  box-shadow: 0 0 20px rgba(0, 150, 255, 0.6), inset 0 0 30px rgba(0, 100, 200, 0.1);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.sensor-card:hover {
  box-shadow: 0 0 26px rgba(0, 170, 255, 0.45), inset 0 0 30px rgba(0, 100, 200, 0.14);
  border-color: rgba(0, 220, 255, 0.52);
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

.sensor-status.online {
  color: var(--success-color);
}

.sensor-status.partial { color: #e6a23c; }

.sensor-status.offline {
  color: var(--danger-color);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: var(--success-color);
  box-shadow: 0 0 8px var(--success-color);
}

.status-dot.partial { background: #e6a23c; box-shadow: 0 0 8px rgba(230, 162, 60, .8); }

.status-dot.offline {
  background: var(--danger-color);
  box-shadow: 0 0 8px var(--danger-color);
}

@media (max-width: 1180px) {
  .overview-container {
    padding: 48px 20px;
  }

  .sensor-grid {
    grid-template-columns: repeat(2, minmax(220px, 260px));
    gap: 30px;
  }
}

@media (max-width: 680px) {
  .title {
    font-size: 28px;
    letter-spacing: 4px;
    margin-bottom: 32px;
  }

  .sensor-grid {
    grid-template-columns: minmax(0, min(300px, calc(100vw - 56px)));
  }

  .sensor-card {
    min-height: 220px;
  }
}
</style>
