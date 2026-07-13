import request from '@/utils/request'

/**
 * 获取所有传感器实时数据
 */
export function getAllSensorRealtime() {
  return request.get('/v1/sensor/realtime')
}

/**
 * 获取指定传感器实时数据
 */
export function getSensorRealtime(deviceName) {
  return request.get(`/v1/sensor/realtime/${deviceName}`)
}

/**
 * 获取设备在线状态
 */
export function getDeviceStatus() {
  return request.get('/v1/sensor/status')
}

/**
 * 获取传感器历史数据
 * @param {string} deviceName 设备名称
 * @param {string} range 时间范围: 1h / 6h / 1d / 7d / 6mo
 */
const HISTORY_CACHE_MAX_AGE = {
  '1h': 60 * 1000,
  '6h': 10 * 60 * 1000,
  '1d': 30 * 60 * 1000,
  '7d': 60 * 60 * 1000,
  '6mo': 24 * 60 * 60 * 1000,
}

export function getSensorHistory(deviceName, range = '1h') {
  return request.get(`/v1/sensor/history/${deviceName}`, {
    params: { range },
    timeout: 60000,
    silentError: true,
    localCacheMaxAge: HISTORY_CACHE_MAX_AGE[range] ?? HISTORY_CACHE_MAX_AGE['1h'],
  })
}
