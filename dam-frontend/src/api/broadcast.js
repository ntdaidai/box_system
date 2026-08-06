import request from '@/utils/request'

export function getBroadcastTemplates() {
  return request.get('/broadcast/templates', { localCache: false })
}

export function getBroadcastDevices() {
  return request.get('/broadcast/devices', { localCache: false })
}

export function createBroadcastDevice(data) {
  return request.post('/broadcast/devices', data)
}

export function updateBroadcastDevice(id, data) {
  return request.put(`/broadcast/devices/${id}`, data)
}

export function deleteBroadcastDevice(id) {
  return request.delete(`/broadcast/devices/${id}`)
}

export function createBroadcastTemplate(data) {
  return request.post('/broadcast/templates', data)
}

export function updateBroadcastTemplate(id, data) {
  return request.put(`/broadcast/templates/${encodeURIComponent(id)}`, data)
}

export function deleteBroadcastTemplate(id) {
  return request.delete(`/broadcast/templates/${encodeURIComponent(id)}`)
}

export function previewBroadcast(data) {
  return request.post('/broadcast/preview', data)
}

export function playBroadcast(data) {
  return request.post('/broadcast/play', data, { timeout: 30000 })
}

export function playRecordedBroadcast(data) {
  return request.post('/broadcast/audio/play', data, { timeout: 120000 })
}
