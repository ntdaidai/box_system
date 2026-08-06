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

export function getUnifiedSafetyEventStatistics() {
  return request.get('/v1/integration/safety-events/statistics', { localCache: false })
}

export function getUnifiedSafetyEventDetail(id) {
  return request.get(`/v1/integration/safety-events/${id}`, { localCache: false })
}

export function operateUnifiedSafetyEvent(id, data) {
  return request.post(`/v1/integration/safety-events/${id}/operation`, data)
}
