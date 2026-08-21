import request from '@/utils/request'

export function getIntegrationConfig() {
  return request.get('/v1/integration/config', { localCache: false })
}

export function updateConditionConfig(id, data) {
  return request.put(`/v1/integration/config/conditions/${id}`, data)
}

export function updateEventConfig(id, data) {
  return request.put(`/v1/integration/config/events/${id}`, data)
}

export function updateFlowConfig(id, data) {
  return request.put(`/v1/integration/config/flows/${id}`, data)
}

export function updateActionConfig(id, data) {
  return request.put(`/v1/integration/config/actions/${id}`, data)
}

export function createActionConfig(data) {
  return request.post('/v1/integration/config/actions', data)
}

export function deleteActionConfig(id) {
  return request.delete(`/v1/integration/config/actions/${id}`)
}

export function getUnifiedSafetyEvents(params = {}, config = {}) {
  return request.get('/v1/integration/safety-events', { params, localCache: false, ...config })
}

export function getUnifiedSafetyEventCategories() {
  return request.get('/v1/integration/safety-events/categories', { localCache: false })
}

export function getUnifiedSafetyEventStatistics() {
  return request.get('/v1/integration/safety-events/statistics', { localCache: false })
}

export function getUnifiedSafetyEventDetail(id) {
  return request.get(`/v1/integration/safety-events/${id}`, { localCache: false })
}

export function operateUnifiedSafetyEvent(id, data) {
  return request.post(`/v1/integration/safety-events/${id}/operation`, data)
}

export function reviewUnifiedSafetyEventFalseAlarm(id, data) {
  return request.post(`/v1/integration/safety-events/${id}/false-alarm-review`, data)
}

export function getFalseAlarmSamples(params = {}) {
  return request.get('/v1/integration/false-alarm-samples', { params, localCache: false })
}

export function saveFalseAlarmSampleAnnotation(data) {
  return request.post('/v1/integration/false-alarm-samples/annotations', data)
}

export function falseAlarmSampleImageUrl(sourcePath) {
  return `/api/v1/integration/false-alarm-samples/image?path=${encodeURIComponent(sourcePath)}`
}

// 现场人工处置的演示下发：事件类型须与处置场景保持一致。
export const STAFF_TASK_EVENT_TYPES = Object.freeze([
  { value: 'PERSON_WADING', label: '人员涉水事件' },
  { value: 'NIGHT_FISHING', label: '夜间捕鱼事件' },
  { value: 'NATURAL_DISASTER_EVENT', label: '自然灾害事件' },
  { value: 'EXTREME_WEATHER_EVENT', label: '极端天气事件' },
])

export function dispatchStaffTask(id, data) {
  return request.post(`/v1/integration/safety-events/${id}/staff-task/dispatch`, data)
}

export function submitStaffTaskResult(id, formData) {
  return request.post(`/v1/integration/safety-events/${id}/staff-task/result`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export function submitSafetyEventSupplementalContext(id, data) {
  return request.post(`/v1/integration/safety-events/${id}/supplemental-context`, data, {
    timeout: 60000,
    silentError: true,
  })
}
