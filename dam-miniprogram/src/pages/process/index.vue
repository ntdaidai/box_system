<template>
  <view class="page process-page">
    <view v-if="event" class="event-strip">
      <view class="risk-pill" :class="riskClassName">{{ event.risk_level_label }}</view>
      <view class="strip-main">
        <view>{{ event.event_type }}</view>
        <text>{{ event.monitor_point }}</text>
      </view>
    </view>

    <view class="section">
      <view class="section-title">现场照片</view>
      <view v-if="photoPath" class="photo-preview">
        <image :src="photoPath" mode="aspectFill" />
      </view>
      <view v-else class="photo-empty">到达现场后拍摄处置照片</view>
      <button
        class="ghost-btn"
        :loading="watermarking"
        :disabled="watermarking || submitting"
        @tap="choosePhoto"
      >
        拍照上传
      </button>
    </view>

    <view class="section">
      <view class="section-title">处置结果</view>
      <radio-group @change="selectResult">
        <label v-for="item in resultOptions" :key="item.value" class="result-option">
          <radio :value="item.value" :checked="result === item.value" color="#0f6b7a" />
          <text>{{ item.label }}</text>
        </label>
      </radio-group>
    </view>

    <view class="section">
      <view class="section-title">简单备注</view>
      <textarea
        class="remark"
        maxlength="500"
        placeholder="填写现场情况"
        :value="remark"
        @input="onRemarkInput"
      />
    </view>

    <button
      class="primary-btn submit-btn"
      :loading="submitting"
      :disabled="submitting || !photoPath"
      @tap="submitResult"
    >
      提交处理结果
    </button>

    <canvas
      canvas-id="watermarkCanvas"
      id="watermarkCanvas"
      class="watermark-canvas"
      :style="{ width: watermarkCanvasWidth + 'px', height: watermarkCanvasHeight + 'px' }"
    />
  </view>
</template>

<script>
import { request, uploadFieldResult } from '../../utils/request'
import { riskClass } from '../../utils/format'

export default {
  data() {
    return {
      eventId: '',
      event: null,
      riskClassName: '',
      photoPath: '',
      result: 'DRIVEN_AWAY',
      remark: '',
      submitting: false,
      watermarking: false,
      watermarkCanvasWidth: 320,
      watermarkCanvasHeight: 240,
      resultOptions: [
        { value: 'DRIVEN_AWAY', label: '已完成驱离' },
        { value: 'LEFT_BY_SELF', label: '人员自行离开' },
        { value: 'OTHER', label: '其他' }
      ]
    }
  },

  onLoad(options) {
    this.eventId = options?.event_id || ''
    this.loadDetail()
  },

  methods: {
    loadDetail() {
      if (!this.eventId) return
      request({ url: `/events/${encodeURIComponent(this.eventId)}` })
        .then((data) => {
          const event = data.event
          this.event = event
          this.riskClassName = riskClass(event.risk_level)
          if (event.mini_status === 'RESOLVED') {
            uni.showToast({ title: '事件已完成', icon: 'none' })
            uni.redirectTo({
              url: `/pages/detail/index?event_id=${encodeURIComponent(this.eventId)}`
            })
          }
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
    },

    choosePhoto() {
      uni.chooseMedia({
        count: 1,
        mediaType: ['image'],
        sourceType: ['camera', 'album'],
        success: (res) => {
          const file = res.tempFiles && res.tempFiles[0]
          if (file && file.tempFilePath) {
            this.watermarking = true
            this.applyPhotoWatermark(file.tempFilePath)
              .then((path) => {
                this.photoPath = path
              })
              .catch(() => {
                this.photoPath = file.tempFilePath
                uni.showToast({ title: '水印生成失败，已保留原图', icon: 'none' })
              })
              .finally(() => {
                this.watermarking = false
              })
          }
        }
      })
    },

    applyPhotoWatermark(filePath) {
      return new Promise((resolve, reject) => {
        uni.getImageInfo({
          src: filePath,
          success: (info) => {
            const maxSide = 1600
            const scale = Math.min(1, maxSide / Math.max(info.width, info.height))
            const width = Math.max(1, Math.round(info.width * scale))
            const height = Math.max(1, Math.round(info.height * scale))
            this.watermarkCanvasWidth = width
            this.watermarkCanvasHeight = height
            this.$nextTick(() => {
              const ctx = uni.createCanvasContext('watermarkCanvas', this)
              ctx.drawImage(filePath, 0, 0, width, height)
              const fontSize = Math.max(22, Math.round(width / 32))
              const padding = Math.max(18, Math.round(width / 45))
              const lineHeight = Math.round(fontSize * 1.45)
              const lines = this.watermarkLines()
              const panelHeight = padding * 2 + lineHeight * lines.length
              ctx.setFillStyle('rgba(0, 0, 0, 0.48)')
              ctx.fillRect(0, height - panelHeight, width, panelHeight)
              ctx.setFillStyle('#ffffff')
              ctx.setFontSize(fontSize)
              lines.forEach((line, index) => {
                ctx.fillText(line, padding, height - panelHeight + padding + lineHeight * (index + 0.72))
              })
              ctx.draw(false, () => {
                setTimeout(() => {
                  uni.canvasToTempFilePath({
                    canvasId: 'watermarkCanvas',
                    destWidth: width,
                    destHeight: height,
                    fileType: 'jpg',
                    quality: 0.9,
                    success: (res) => resolve(res.tempFilePath),
                    fail: reject
                  }, this)
                }, 80)
              })
            })
          },
          fail: reject
        })
      })
    },

    watermarkLines() {
      const event = this.event || {}
      const now = new Date()
      const time = `${now.getFullYear()}-${this.pad(now.getMonth() + 1)}-${this.pad(now.getDate())} ${this.pad(now.getHours())}:${this.pad(now.getMinutes())}`
      return [
        `事件：${event.event_type || '风险事件'}`,
        `点位：${event.monitor_point || event.camera_name || event.camera_id || '--'}`,
        `位置：${event.install_address || '未填写安装地址'}`,
        `时间：${time}`
      ]
    },

    pad(value) {
      return String(value).padStart(2, '0')
    },

    selectResult(event) {
      this.result = event.detail.value
    },

    onRemarkInput(event) {
      this.remark = event.detail.value
    },

    submitResult() {
      if (this.submitting) return
      if (!this.photoPath) {
        uni.showToast({ title: '请先拍照上传', icon: 'none' })
        return
      }
      this.submitting = true
      uploadFieldResult({
        eventId: this.eventId,
        filePath: this.photoPath,
        result: this.result,
        remark: this.remark,
        operator: '微信小程序工作人员'
      })
        .then(() => {
          uni.showToast({ title: '已提交', icon: 'success' })
          uni.redirectTo({
            url: `/pages/detail/index?event_id=${encodeURIComponent(this.eventId)}`
          })
        })
        .catch((error) => {
          uni.showToast({ title: error.message, icon: 'none' })
        })
        .finally(() => {
          this.submitting = false
        })
    }
  }
}
</script>

<style>
.process-page {
  padding-bottom: 48rpx;
}

.event-strip,
.section {
  background: #fff;
  border-radius: 8rpx;
  padding: 22rpx;
  margin-bottom: 18rpx;
  box-shadow: 0 6rpx 18rpx rgba(20, 45, 52, 0.07);
}

.event-strip {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.risk-pill {
  min-width: 96rpx;
  height: 52rpx;
  line-height: 52rpx;
  text-align: center;
  border-radius: 8rpx;
  font-weight: 700;
}

.strip-main {
  flex: 1;
  min-width: 0;
}

.strip-main view {
  font-size: 32rpx;
  font-weight: 700;
  margin-bottom: 6rpx;
}

.strip-main text {
  color: #6c7a80;
  font-size: 24rpx;
}

.section-title {
  font-weight: 700;
  font-size: 30rpx;
  margin-bottom: 16rpx;
}

.photo-preview,
.photo-empty {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 8rpx;
  overflow: hidden;
  background: #eef4f5;
  margin-bottom: 16rpx;
}

.photo-preview image {
  width: 100%;
  height: 100%;
}

.photo-empty {
  color: #6c7a80;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-option {
  min-height: 72rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  color: #172026;
}

.remark {
  width: 100%;
  min-height: 180rpx;
  padding: 18rpx;
  box-sizing: border-box;
  border-radius: 8rpx;
  background: #f2f6f7;
  color: #172026;
  line-height: 40rpx;
}

.submit-btn {
  margin-top: 24rpx;
}

.submit-btn[disabled] {
  background: #b8c8cd;
  color: #fff;
}

.watermark-canvas {
  position: fixed;
  left: -9999px;
  top: -9999px;
  opacity: 0;
  pointer-events: none;
}
</style>
