<template>
  <view class="page map-page">
    <map
      class="camera-map"
      :latitude="centerLatitude"
      :longitude="centerLongitude"
      :scale="16"
      :markers="markers"
      show-location
      @markertap="handleMarkerTap"
    />

    <view class="camera-list">
      <view class="section-title">摄像头点位</view>
      <view v-if="cameras.length === 0" class="empty">暂无可导航点位</view>
      <view
        v-for="item in cameras"
        :key="item.id"
        class="camera-item"
        :class="{ active: String(item.id) === selectedCameraId }"
        @tap="openLocation(item)"
      >
        <view>
          <text>{{ item.camera_name || item.id }}</text>
          <text>{{ item.install_address || '未填写安装地址' }}</text>
        </view>
        <button class="ghost-btn mini-btn" @tap.stop="openLocation(item)">导航</button>
      </view>
    </view>
  </view>
</template>

<script>
import { request } from '../../utils/request'
import { readCache, writeCache } from '../../utils/cache'

const DEFAULT_LATITUDE = 32.055156
const DEFAULT_LONGITUDE = 118.75809

export default {
  data() {
    return {
      cameras: [],
      selectedCameraId: '',
      centerLatitude: DEFAULT_LATITUDE,
      centerLongitude: DEFAULT_LONGITUDE
    }
  },

  computed: {
    markers() {
      return this.cameras.map((item, index) => ({
        id: index + 1,
        camera_device_id: item.id,
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        title: item.camera_name || item.id,
        callout: {
          content: item.camera_name || item.id,
          color: '#172026',
          fontSize: 13,
          borderRadius: 6,
          bgColor: '#ffffff',
          padding: 6,
          display: String(item.id) === this.selectedCameraId ? 'ALWAYS' : 'BYCLICK'
        }
      }))
    }
  },

  onLoad(options) {
    this.selectedCameraId = options?.camera_id || ''
    this.restoreCachedCameras()
    this.loadCameras()
  },

  methods: {
    restoreCachedCameras() {
      this.applyCameras(readCache('cameras', []))
    },

    loadCameras() {
      request({ url: '/cameras' })
        .then((data) => {
          const cameras = data.items || []
          writeCache('cameras', cameras)
          this.applyCameras(cameras)
        })
        .catch((error) => {
          uni.showToast({ title: error.message || '点位加载失败', icon: 'none' })
        })
    },

    applyCameras(items) {
      this.cameras = (items || [])
        .filter((item) => Number(item.latitude) && Number(item.longitude))
        .map((item) => ({
          ...item,
          latitude: Number(item.latitude),
          longitude: Number(item.longitude)
        }))
      const selected = this.cameras.find((item) => String(item.id) === this.selectedCameraId) || this.cameras[0]
      if (selected) {
        this.selectedCameraId = String(selected.id)
        this.centerLatitude = selected.latitude
        this.centerLongitude = selected.longitude
      }
    },

    handleMarkerTap(event) {
      const markerId = Number(event.detail.markerId)
      const marker = this.markers.find((item) => item.id === markerId)
      const camera = marker && this.cameras.find((item) => item.id === marker.camera_device_id)
      if (camera) {
        this.selectedCameraId = String(camera.id)
        this.centerLatitude = camera.latitude
        this.centerLongitude = camera.longitude
        this.openLocation(camera)
      }
    },

    openLocation(camera) {
      const latitude = Number(camera.latitude)
      const longitude = Number(camera.longitude)
      if (!latitude || !longitude) {
        uni.showToast({ title: '该点位未配置坐标', icon: 'none' })
        return
      }
      uni.openLocation({
        latitude,
        longitude,
        name: camera.camera_name || camera.id,
        address: camera.install_address || camera.description || '',
        scale: 18
      })
    }
  }
}
</script>

<style>
.map-page {
  padding: 0;
  background: #f4f7f8;
}

.camera-map {
  width: 100%;
  height: 58vh;
}

.camera-list {
  padding: 20rpx 24rpx 36rpx;
}

.section-title {
  font-weight: 800;
  font-size: 30rpx;
  margin-bottom: 14rpx;
}

.empty {
  color: #7b8b91;
  text-align: center;
  padding: 44rpx 0;
}

.camera-item {
  min-height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 14rpx;
  border-radius: 8rpx;
  background: #fff;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
  box-sizing: border-box;
}

.camera-item.active {
  border-left: 8rpx solid #0f6b7a;
}

.camera-item view {
  flex: 1;
  min-width: 0;
}

.camera-item text {
  display: block;
}

.camera-item text:first-child {
  color: #172026;
  font-weight: 800;
  margin-bottom: 6rpx;
}

.camera-item text:last-child {
  color: #6c7a80;
  font-size: 24rpx;
  line-height: 34rpx;
}

.mini-btn {
  width: 120rpx;
  height: 60rpx;
  line-height: 60rpx;
  padding: 0;
  font-size: 24rpx;
}
</style>
