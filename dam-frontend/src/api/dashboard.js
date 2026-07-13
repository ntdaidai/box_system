/**
 * 系统概览 Dashboard API
 * 封装系统状态、传感器、告警等接口
 */
import request from '@/utils/request'

/**
 * 获取系统运行状态（CPU、内存、磁盘、服务状态等）
 */
export function getSystemInfo() {
  return request.get('/v1/system/info')
}

/**
 * 获取所有传感器实时数据（复用 sensor API）
 */
export { getAllSensorRealtime, getSensorHistory, getDeviceStatus } from './sensor'

/**
 * 获取告警统计和列表（复用 alarm API）
 */
export { getAlarmStatistics, getAlarmList } from './alarm'
