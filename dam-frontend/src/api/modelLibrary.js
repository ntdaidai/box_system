import request from '@/utils/request'

function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
}

export function getModelLibrary(params = {}) {
  return request.get('/v1/model-library/models', {
    params: cleanParams(params),
    localCache: false,
    timeout: 10000,
  })
}

export function getModelLibraryDetail(modelId) {
  return request.get(`/v1/model-library/models/${encodeURIComponent(modelId)}`, {
    localCache: false,
    timeout: 10000,
  })
}

export function checkModelHealth(modelId) {
  return request.post(`/v1/model-library/models/${encodeURIComponent(modelId)}/health-check`, null, {
    timeout: 10000,
    silentError: true,
  })
}

export function startModel(modelId) {
  return request.post(`/v1/model-library/models/${encodeURIComponent(modelId)}/start`, null, {
    timeout: 60000,
    silentError: true,
  })
}

export function stopModel(modelId) {
  return request.post(`/v1/model-library/models/${encodeURIComponent(modelId)}/stop`, null, {
    timeout: 60000,
    silentError: true,
  })
}
