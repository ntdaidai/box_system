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

export function simulateSensorEvent(data, options = {}) {
  const formData = new FormData()
  formData.append('event_id', data.eventId)
  formData.append('sensor_name', data.sensorName || 'sensor')
  formData.append('sensor_data_json', JSON.stringify(data.sensorData || {}))
  formData.append('force', data.force !== false ? 'true' : 'false')
  if (data.cameraId) formData.append('camera_id', data.cameraId)
  if (data.file) formData.append('file', data.file)

  return request.post('/v1/eca/sensor/simulate', formData, {
    timeout: options.timeout ?? 180000,
    silentError: true,
    onUploadProgress: options.onUploadProgress,
  })
}
