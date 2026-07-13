import request from '@/utils/request'

/**
 * 获取告警列表
 */
export function getAlarmList(params) {
  return request.get('/alarm/list', { params })
}

/**
 * 获取告警详情
 */
export function getAlarmDetail(id) {
  return request.get(`/alarm/${id}`)
}

/**
 * 处理告警
 */
export function handleAlarm(id, data) {
  return request.put(`/alarm/${id}/handle`, data)
}

/**
 * 获取告警统计
 */
export function getAlarmStatistics(params) {
  return request.get('/alarm/statistics', { params })
}
