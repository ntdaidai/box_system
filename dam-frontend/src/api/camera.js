// dai
/**
 * 摄像头与检测 API
 */
import request from '@/utils/request'

// 获取摄像头列表
export function getCameraList(config = {}) {
  return request.get('/v1/camera/devices', { localCache: false, ...config })
}

// 获取摄像头状态
export function getCameraStatus(cameraId) {
  return request.get(`/v1/camera/${cameraId}/status`, {
    localCache: false,
    silentError: true,
    timeout: 5000,
  })
}

export function getCameraDevices() {
  return request.get('/v1/camera/devices', { localCache: false })
}

export function createCameraDevice(data) {
  return request.post('/v1/camera/devices', data)
}

export function updateCameraDevice(cameraId, data) {
  return request.put(`/v1/camera/devices/${encodeURIComponent(cameraId)}`, data)
}

export function deleteCameraDevice(cameraId) {
  return request.delete(`/v1/camera/devices/${encodeURIComponent(cameraId)}`)
}

export function testCameraDeviceConnection(data) {
  return request.post('/v1/camera/devices/test-connection', data, {
    timeout: 15000,
    silentError: true,
  })
}

export function getCameraDevicePassword(cameraId) {
  return request.get(`/v1/camera/devices/${encodeURIComponent(cameraId)}/password`, {
    localCache: false,
  })
}

// 切换检测开关
export function setDetectionEnabled(cameraId, enabled, options = {}) {
  return request.post(`/v1/camera/${cameraId}/detection/toggle`, {
    enabled,
    ...options,
  })
}

// 截图并检测
export function snapshotDetect(cameraId, confidence = 0.5, taskType = 'detect') {
  return request.post(`/v1/camera/${cameraId}/snapshot`, null, {
    params: { confidence, task_type: taskType },
  })
}

// 上传图片检测
export function detectImage(imageBase64, confidence = 0.5, taskType = 'detect') {
  return request.post('/v1/camera/detect/image', {
    image: imageBase64,
    confidence,
    task_type: taskType,
  })
}

// 将浏览器采集的关键帧作为指定摄像头画面送入 Qwen -> ECA 链路。
export function simulateCameraScreening(cameraId, frames, options = {}) {
  const formData = new FormData()
  frames.forEach((frame, index) => {
    formData.append('frames', frame, `frame_${index + 1}.jpg`)
  })
  return request.post(
    `/v1/camera/${encodeURIComponent(cameraId)}/screening/simulate`,
    formData,
    {
      params: { window_seconds: options.windowSeconds ?? 10 },
      timeout: options.timeout ?? 120000,
      silentError: true,
    },
  )
}

// 将本地视频作为摄像头模拟输入送入 Qwen -> ECA 链路；抽帧由后端服务完成。
export function simulateCameraVideoScreening(cameraId, file, options = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (options.supplementalContext) {
    formData.append('supplemental_context', JSON.stringify(options.supplementalContext))
  }
  return request.post(
    `/v1/camera/${encodeURIComponent(cameraId)}/screening/simulate-video`,
    formData,
    {
      params: { window_seconds: options.windowSeconds ?? 10 },
      timeout: options.timeout ?? 180000,
      silentError: true,
      onUploadProgress: options.onUploadProgress,
    },
  )
}

// 获取模型状态
export function getModelStatus(config = {}) {
  return request.get('/v1/camera/model/status', { localCache: false, ...config })
}

// 重新加载模型
export function reloadModel(modelPath, taskType = 'detect') {
  return request.post('/v1/camera/model/reload', null, {
    params: {
      task_type: taskType,
      ...(modelPath ? { model_path: modelPath } : {}),
    },
  })
}

// 签发短时视频票据，避免把登录 JWT 放进 <img> URL。
export function createStreamTicket(cameraId, detected = false) {
  return request.post(`/v1/camera/stream/${cameraId}/ticket`, { detected })
}

// WebRTC 信令始终经认证后端代理，浏览器不会接触 RTSP 凭据。
export function getWebRtcIceConfig(cameraId) {
  return request.get(`/v1/camera/${encodeURIComponent(cameraId)}/webrtc/ice`, {
    localCache: false,
    silentError: true,
  })
}

export function createWebRtcSession(cameraId, peerId, offer) {
  return request.post(
    `/v1/camera/${encodeURIComponent(cameraId)}/webrtc/session`,
    { peer_id: peerId, offer },
    { timeout: 30000, silentError: true },
  )
}

export function addWebRtcIceCandidate(cameraId, peerId, candidate) {
  return request.post(
    `/v1/camera/${encodeURIComponent(cameraId)}/webrtc/session/${encodeURIComponent(peerId)}/candidate`,
    candidate,
    { silentError: true },
  )
}

export function getWebRtcIceCandidates(cameraId, peerId) {
  return request.get(
    `/v1/camera/${encodeURIComponent(cameraId)}/webrtc/session/${encodeURIComponent(peerId)}/candidates`,
    { localCache: false, silentError: true },
  )
}

export function closeWebRtcSession(cameraId, peerId) {
  return request.delete(
    `/v1/camera/${encodeURIComponent(cameraId)}/webrtc/session/${encodeURIComponent(peerId)}`,
    { silentError: true },
  )
}

export function getCameraZones(cameraId, config = {}) {
  return request.get(`/v1/camera/${encodeURIComponent(cameraId)}/zones`, {
    localCache: false,
    ...config,
  })
}

export function saveCameraZones(cameraId, zones) {
  return request.put(`/v1/camera/${encodeURIComponent(cameraId)}/zones`, { zones })
}

export function getTodaySafetyReport(params = {}) {
  return request.get('/v1/integration/patrol-report/today', {
    params,
    localCache: false,
  })
}

export function getLatestDetection(cameraId) {
  return request.get(`/v1/camera/${cameraId}/detections/latest`, {
    localCache: false,
  })
}

/**
 * 获取视频流 URL（直接用于 <img> 标签的 src）
 * 注意：此接口不需要认证 token，直接返回 URL 字符串
 */
export function getStreamUrl(cameraId, ticket, withDetection = false) {
  const base = `/api/v1/camera/stream/${encodeURIComponent(cameraId)}`
  const path = withDetection ? `${base}/detected` : base
  return `${path}?ticket=${encodeURIComponent(ticket)}`
}
