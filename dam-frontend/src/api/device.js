import request from '@/utils/request'

/**
 * 获取设备列表
 */
export function getDeviceList(params) {
  return request.get('/device/list', { params })
}

/**
 * 获取设备详情
 */
export function getDeviceDetail(id) {
  return request.get(`/device/${id}`)
}

/**
 * 添加设备
 */
export function addDevice(data) {
  return request.post('/device', data)
}

/**
 * 更新设备
 */
export function updateDevice(id, data) {
  return request.put(`/device/${id}`, data)
}

/**
 * 删除设备
 */
export function deleteDevice(id) {
  return request.delete(`/device/${id}`)
}

/**
 * 获取设备状态
 */
export function getDeviceStatus(id) {
  return request.get(`/device/${id}/status`)
}
