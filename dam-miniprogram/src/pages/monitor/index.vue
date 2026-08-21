<template>
  <view class="page monitor-page">
    <view class="video-panel">
      <view class="section-head">
        <text>点位监控画面</text>
        <text>{{ selectedCameraStatus }}</text>
      </view>

      <picker
        v-if="cameras.length"
        mode="selector"
        :range="cameraNames"
        :value="selectedCameraIndex"
        @change="selectCamera"
      >
        <view class="camera-selector">
          <view>
            <text>当前点位</text>
            <text>{{ selectedCamera.camera_name }}</text>
          </view>
          <text>切换</text>
        </view>
      </picker>
      <view v-else class="camera-selector disabled">
        <view>
          <text>当前点位</text>
          <text>{{ loadError || '暂无可选摄像头' }}</text>
        </view>
      </view>

      <view class="video-box">
        <view v-if="streamUrl" class="video-crop-layer">
          <video
            :key="livePlayerKey"
            class="video-frame"
            :src="streamUrl"
            autoplay
            loop
            muted
            :controls="false"
            :show-center-play-btn="false"
            :show-play-btn="false"
            :show-fullscreen-btn="false"
            :show-mute-btn="false"
            :show-progress="false"
            :enable-progress-gesture="false"
            :vslide-gesture="false"
            object-fit="cover"
            @play="handleVideoPlay"
            @error="handleVideoError"
          />
          <view v-if="showAssistBox && selectedCamera.id" class="assist-overlay">
            <view
              v-for="zone in assistZones"
              :key="zone.id || zone.zone_name"
              class="assist-zone"
              :style="assistZoneStyle(zone)"
            />
          </view>
        </view>
        <view v-else class="video-empty">{{ videoText }}</view>
        <view v-if="videoError" class="video-error">{{ videoError }}</view>
      </view>

      <view class="video-actions">
        <button
          class="ghost-btn action-btn"
          :loading="videoLoading"
          :disabled="videoLoading || !selectedCamera.id"
          @tap="loadLiveStream(true)"
        >
          刷新页面
        </button>
        <button
          class="ghost-btn action-btn"
          :disabled="!selectedCamera.id"
          @tap="openMapNavigation"
        >
          点位导航
        </button>
        <picker
          class="assist-picker"
          mode="selector"
          :range="assistZoneNames"
          :value="selectedAssistZoneIndex"
          :disabled="!availableAssistZones.length"
          @change="selectAssistZone"
        >
          <button class="ghost-btn action-btn" :disabled="!availableAssistZones.length">
            {{ assistControlLabel }}
          </button>
        </picker>
      </view>

      <button
        class="primary-btn broadcast-btn"
        :loading="cameraBroadcasting"
        :disabled="cameraBroadcasting || !selectedCamera.id"
        @tap="handleCameraBroadcast"
      >
        <text class="broadcast-icon">▶</text>
        <text>{{ recordingBroadcast ? '结束喊话' : '一键喊话' }}</text>
      </button>
      <view class="broadcast-note">
        {{ broadcastDeviceText }}
      </view>
    </view>

    <view class="camera-list">
      <view class="section-head list-head">
        <text>摄像头点位</text>
        <text>{{ cameras.length }} 个</text>
      </view>
      <view v-if="loading" class="empty compact">加载中...</view>
      <view v-else-if="cameras.length === 0" class="empty compact">
        {{ loadError || '暂无摄像头点位' }}
      </view>
      <view
        v-for="(item, index) in cameras"
        :key="item.id"
        class="camera-item"
        :class="{ active: index === selectedCameraIndex }"
        @tap="selectCameraByIndex(index)"
      >
        <view>
          <text>{{ item.camera_name || item.id }}</text>
          <text>{{ item.install_address || item.description || '未填写安装地址' }}</text>
        </view>
        <text>{{ item.online ? '在线' : '待连接' }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { request, uploadBroadcastAudio } from '../../utils/request'
import { readCache, writeCache } from '../../utils/cache'
import { prepareDemoVideo } from '../../utils/demo-video'

export default {
  data() {
    return {
      cameras: [],
      selectedCameraIndex: 0,
      loading: false,
      loadError: '',
      videoLoading: false,
      streamUrl: '',
      livePlayerKey: 0,
      videoText: '正在准备监控录像',
      videoError: '',
      cameraBroadcasting: false,
      recordingBroadcast: false,
      broadcastRecorder: null,
      selectedAssistZoneId: ''
    }
  },

  computed: {
    cameraNames() {
      return this.cameras.map((item) => item.camera_name || item.id)
    },

    selectedCamera() {
      return this.cameras[this.selectedCameraIndex] || {}
    },

    selectedCameraStatus() {
      if (!this.selectedCamera.id) return '未配置'
      return this.selectedCamera.online ? '在线' : '待连接'
    },

    broadcastDeviceText() {
      const count = Number(this.selectedCamera.broadcast_device_count || 0)
      if (count > 0) return `可用 ${count} 个喊话设备`
      return '暂无可用喊话设备'
    },

    availableAssistZones() {
      return (this.selectedCamera.detection_zones || []).filter((zone) => zone && zone.enabled !== false)
    },

    assistZoneOptions() {
      return [{ id: '', zone_name: '不显示辅助框' }, ...this.availableAssistZones]
    },

    assistZoneNames() {
      return this.assistZoneOptions.map((zone) => zone.zone_name || zone.name || this.zoneTypeLabel(zone.zone_type))
    },

    selectedAssistZoneIndex() {
      const index = this.assistZoneOptions.findIndex((zone) => String(zone.id) === String(this.selectedAssistZoneId))
      return index > -1 ? index : 0
    },

    selectedAssistZone() {
      return this.availableAssistZones.find((zone) => String(zone.id) === String(this.selectedAssistZoneId)) || null
    },

    assistZones() {
      return this.selectedAssistZone ? [this.selectedAssistZone] : []
    },

    showAssistBox() {
      return Boolean(this.selectedAssistZone)
    },

    assistControlLabel() {
      if (!this.availableAssistZones.length) return '暂无辅助框'
      if (!this.selectedAssistZone) return '选择辅助框'
      const name = this.selectedAssistZone.zone_name || this.selectedAssistZone.name || this.zoneTypeLabel(this.selectedAssistZone.zone_type)
      return `辅助框：${name}`
    }
  },

  onLoad() {
    this.restoreCachedCameras()
    this.prepareMonitorVideo()
    this.loadCameras(true)
    this.prepareBroadcastRecorder()
  },

  onUnload() {
    if (this.recordingBroadcast) this.broadcastRecorder?.stop()
  },

  onPullDownRefresh() {
    this.loadCameras(true).finally(() => uni.stopPullDownRefresh())
  },

  methods: {
    restoreCachedCameras() {
      const cached = readCache('cameras', [])
      if (!cached.length) return
      this.cameras = cached
    },

    loadCameras(autoStart = false) {
      this.loading = true
      this.loadError = ''
      return request({ url: '/cameras' })
        .then((data) => {
          this.cameras = data.items || []
          writeCache('cameras', this.cameras)
          if (this.selectedCameraIndex >= this.cameras.length) {
            this.selectedCameraIndex = 0
          }
          this.syncAssistZoneSelection()
          if (autoStart) {
            this.openSelectedCamera(false)
          }
        })
        .catch((error) => {
          const cached = readCache('cameras', [])
          this.cameras = cached
          this.loadError = error.message || '摄像头加载失败'
          this.videoText = cached.length ? '正在使用缓存点位连接画面' : this.loadError
          if (cached.length && autoStart) {
            this.openSelectedCamera(false)
          }
        })
        .finally(() => {
          this.loading = false
        })
    },

    selectCamera(event) {
      this.selectCameraByIndex(Number(event.detail.value || 0))
    },

    selectCameraByIndex(index) {
      if (index === this.selectedCameraIndex && this.streamUrl) return
      this.selectedCameraIndex = index
      this.selectedAssistZoneId = ''
      this.openSelectedCamera(true)
    },

    openSelectedCamera(showToast) {
      return this.loadLiveStream(showToast)
    },

    loadLiveStream(showToast = false) {
      if (this.videoLoading) return Promise.resolve()
      this.videoLoading = true
      this.videoError = ''
      return prepareDemoVideo()
        .then((filePath) => {
          this.streamUrl = filePath
          this.livePlayerKey += 1
          this.videoText = '监控录像循环播放'
          if (showToast) uni.showToast({ title: '画面已刷新', icon: 'none' })
        })
        .catch((error) => {
          this.streamUrl = ''
          this.videoText = error.message || '监控录像初始化失败'
          this.videoError = this.videoText
        })
        .finally(() => {
          this.videoLoading = false
        })
    },

    prepareMonitorVideo() {
      return this.loadLiveStream(false)
    },

    handleVideoPlay() {
      this.videoError = ''
    },

    handleVideoError(event) {
      const message = event?.detail?.errMsg || '监控录像播放失败'
      this.videoError = message
      console.error('[monitor-video] playback failed', event?.detail || event)
    },

    selectAssistZone(event) {
      const index = Number(event.detail.value || 0)
      const selected = this.assistZoneOptions[index] || this.assistZoneOptions[0]
      this.selectedAssistZoneId = selected?.id || ''
      uni.showToast({
        title: this.selectedAssistZoneId ? '辅助框已切换' : '辅助框已隐藏',
        icon: 'none'
      })
    },

    syncAssistZoneSelection() {
      const exists = this.availableAssistZones.some((zone) => String(zone.id) === String(this.selectedAssistZoneId))
      if (!exists) this.selectedAssistZoneId = ''
    },

    zoneTypeLabel(type) {
      return {
        PERSON_LOW: '低风险区',
        PERSON_MEDIUM: '中风险区',
        PERSON_HIGH: '高风险区',
        FISHING: '垂钓区'
      }[type] || '辅助区域'
    },

    zoneColor(type) {
      return {
        PERSON_LOW: '#38d9a9',
        PERSON_MEDIUM: '#ffd166',
        PERSON_HIGH: '#ff5c75',
        FISHING: '#53a8ff'
      }[type] || '#38d9a9'
    },

    zoneFill(type) {
      return {
        PERSON_LOW: 'rgba(56, 217, 169, 0.12)',
        PERSON_MEDIUM: 'rgba(255, 209, 102, 0.12)',
        PERSON_HIGH: 'rgba(255, 92, 117, 0.14)',
        FISHING: 'rgba(83, 168, 255, 0.12)'
      }[type] || 'rgba(56, 217, 169, 0.12)'
    },

    assistZoneStyle(zone) {
      const points = Array.isArray(zone.polygon_points) ? zone.polygon_points : []
      const normalized = points
        .map((point) => {
          if (Array.isArray(point)) return { x: Number(point[0]), y: Number(point[1]) }
          return { x: Number(point?.x), y: Number(point?.y) }
        })
        .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
      const fallback = [
        { x: 0.18, y: 0.18 },
        { x: 0.82, y: 0.18 },
        { x: 0.82, y: 0.66 },
        { x: 0.18, y: 0.66 }
      ]
      const usable = normalized.length >= 3 ? normalized : fallback
      const xs = usable.map((point) => Math.max(0, Math.min(1, point.x)))
      const ys = usable.map((point) => Math.max(0, Math.min(1, point.y)))
      const minX = Math.min(...xs)
      const maxX = Math.max(...xs)
      const minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      const color = this.zoneColor(zone.zone_type)
      return [
        `left:${minX * 100}%`,
        `top:${minY * 100}%`,
        `width:${Math.max(0.08, maxX - minX) * 100}%`,
        `height:${Math.max(0.08, maxY - minY) * 100}%`,
        `border-color:${color}`,
        `color:${color}`,
        `background-color:${this.zoneFill(zone.zone_type)}`
      ].join(';')
    },

    handleCameraBroadcast() {
      const cameraId = this.selectedCamera.id
      if (!cameraId || this.cameraBroadcasting) return
      if (this.recordingBroadcast) {
        this.broadcastRecorder?.stop()
        return
      }
      this.broadcastRecorder?.start({ duration: 60000, format: 'mp3', sampleRate: 16000, numberOfChannels: 1 })
    },

    prepareBroadcastRecorder() {
      this.broadcastRecorder = uni.getRecorderManager()
      this.broadcastRecorder.onStart(() => {
        this.recordingBroadcast = true
        uni.showToast({ title: '请开始喊话，再次点击结束', icon: 'none' })
      })
      this.broadcastRecorder.onStop(({ tempFilePath }) => {
        this.recordingBroadcast = false
        this.cameraBroadcasting = true
        uploadBroadcastAudio({ filePath: tempFilePath, cameraId: this.selectedCamera.id })
          .then((result) => uni.showToast({
            title: result.result === 'PARTIAL_SUCCESS' ? '部分设备播放成功' : '喊话已播放',
            icon: result.result === 'PARTIAL_SUCCESS' ? 'none' : 'success'
          }))
          .catch((error) => uni.showToast({ title: error.message, icon: 'none' }))
          .finally(() => { this.cameraBroadcasting = false })
      })
      this.broadcastRecorder.onError((error) => {
        this.recordingBroadcast = false
        this.cameraBroadcasting = false
        uni.showToast({ title: error.errMsg || '无法录音', icon: 'none' })
      })
    },

    openMapNavigation() {
      const cameraId = this.selectedCamera.id || ''
      uni.navigateTo({
        url: `/pages/map/index?camera_id=${encodeURIComponent(cameraId)}`
      })
    }
  }
}
</script>

<style>
.monitor-page {
  padding-top: 20rpx;
  padding-bottom: 48rpx;
}

.video-panel,
.camera-list {
  border-radius: 8rpx;
  background: #fff;
  padding: 22rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.08);
}

.camera-list {
  margin-top: 20rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}

.section-head text:first-child {
  color: #172026;
  font-size: 30rpx;
  font-weight: 800;
}

.section-head text:last-child {
  color: #728187;
  font-size: 24rpx;
}

.list-head {
  margin-bottom: 12rpx;
}

.camera-selector {
  min-height: 92rpx;
  padding: 16rpx 18rpx;
  box-sizing: border-box;
  border-radius: 8rpx;
  background: #f2f6f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.camera-selector view {
  min-width: 0;
}

.camera-selector view text {
  display: block;
}

.camera-selector view text:first-child {
  color: #6c7a80;
  font-size: 23rpx;
  margin-bottom: 6rpx;
}

.camera-selector view text:last-child {
  color: #172026;
  font-size: 30rpx;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camera-selector > text {
  color: #0f6b7a;
  font-size: 26rpx;
  font-weight: 700;
  flex-shrink: 0;
}

.camera-selector.disabled > text {
  display: none;
}

.video-box {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  margin-top: 18rpx;
  border-radius: 8rpx;
  overflow: hidden;
  background: #172026;
}

.video-frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: #172026;
}

.video-crop-layer {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
}

.video-empty {
  width: 100%;
  height: 100%;
  color: #d8e5e8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  text-align: center;
  padding: 0 24rpx;
  box-sizing: border-box;
}

.video-error {
  position: absolute;
  left: 24rpx;
  right: 24rpx;
  bottom: 20rpx;
  z-index: 5;
  padding: 10rpx 14rpx;
  border-radius: 6rpx;
  background: rgba(130, 22, 22, 0.82);
  color: #fff;
  font-size: 22rpx;
  line-height: 32rpx;
  text-align: center;
}

.video-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-top: 18rpx;
}

.action-btn {
  height: 74rpx;
  line-height: 74rpx;
  font-size: 25rpx;
}

.assist-picker {
  min-width: 0;
}

.assist-picker .action-btn {
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.broadcast-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  height: 84rpx;
  line-height: 84rpx;
  margin-top: 16rpx;
  font-size: 30rpx;
}

.broadcast-icon {
  width: 38rpx;
  height: 38rpx;
  line-height: 38rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 22rpx;
  text-align: center;
}

.assist-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
}

.assist-zone {
  position: absolute;
  border: 4rpx solid #31d6a0;
  border-radius: 6rpx;
  box-sizing: border-box;
  box-shadow: 0 0 18rpx rgba(49, 214, 160, 0.35);
}

.broadcast-note {
  color: #6c7a80;
  font-size: 23rpx;
  line-height: 36rpx;
  margin-top: 10rpx;
}

.camera-item {
  min-height: 86rpx;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #edf3f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.camera-item:last-child {
  border-bottom: 0;
}

.camera-item.active {
  padding-left: 16rpx;
  border-left: 8rpx solid #0f6b7a;
}

.camera-item view {
  min-width: 0;
}

.camera-item view text {
  display: block;
}

.camera-item view text:first-child {
  color: #172026;
  font-weight: 700;
  margin-bottom: 4rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camera-item view text:last-child {
  color: #6c7a80;
  font-size: 23rpx;
  line-height: 34rpx;
}

.camera-item > text {
  color: #0f6b7a;
  font-size: 24rpx;
  flex-shrink: 0;
}

.empty {
  color: #7b8b91;
  text-align: center;
}

.empty.compact {
  padding: 44rpx 20rpx 34rpx;
}
</style>
