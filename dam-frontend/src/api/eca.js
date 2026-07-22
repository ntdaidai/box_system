import request from '@/utils/request'

export function getDataSources(params = {}) {
  return request.get('/v1/eca/sources', {
    params,
    localCache: false,
  })
}

export function createDataSource(data) {
  return request.post('/v1/eca/sources', data)
}

export function updateDataSource(id, data) {
  return request.put(`/v1/eca/sources/${id}`, data)
}

export function deleteDataSource(id) {
  return request.delete(`/v1/eca/sources/${id}`)
}
