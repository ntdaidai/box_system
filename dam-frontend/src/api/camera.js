// dai
/**
 * 摄像头与检测 API
 */
import request from '@/utils/request'

// 获取摄像头列表
export function getCameraList() {
  return request.get('/v1/camera/list', { localCache: false })
}

// 获取摄像头状态
export function getCameraStatus(cameraId) {
  return request.get(`/v1/camera/${cameraId}/status`, { localCache: false })
}

// 添加摄像头
export function addCamera(data) {
  return request.post('/v1/camera/add', data)
}

// 删除摄像头
export function removeCamera(cameraId) {
  return request.delete(`/v1/camera/${cameraId}`)
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

// 创建临时视频检测任务，视频本体不会进入历史记录。
export function createVideoDetection(file, options = {}) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/v1/camera/detect/video', formData, {
    params: {
      confidence: options.confidence ?? 0.5,
      sample_fps: options.sampleFps ?? 2,
      task_type: options.taskType ?? 'detect',
    },
    timeout: 120000,
    onUploadProgress: options.onUploadProgress,
  })
}

export function getVideoDetectionStatus(jobId) {
  return request.get(`/v1/camera/detect/video/${encodeURIComponent(jobId)}/status`, {
    localCache: false,
  })
}

export function getVideoDetectionResult(jobId) {
  return request.get(`/v1/camera/detect/video/${encodeURIComponent(jobId)}/result`, {
    localCache: false,
    timeout: 60000,
  })
}

export function deleteVideoDetectionJob(jobId) {
  return request.delete(`/v1/camera/detect/video/${encodeURIComponent(jobId)}`)
}

// 获取模型状态
export function getModelStatus() {
  return request.get('/v1/camera/model/status', { localCache: false })
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
