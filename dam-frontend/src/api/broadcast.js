import request from '@/utils/request'

export function getBroadcastTemplates() {
  return request.get('/broadcast/templates', { localCache: false })
}

export function getCameraBroadcastDevices(cameraId) {
  return request.get(`/broadcast/camera/${encodeURIComponent(cameraId)}/devices`, {
    localCache: false,
  })
}

export function previewBroadcast(data) {
  return request.post('/broadcast/preview', data)
}

export function playBroadcast(data) {
  return request.post('/broadcast/play', data, { timeout: 30000 })
}
