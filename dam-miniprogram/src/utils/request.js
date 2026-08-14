import { MINI_API_BASE, withApiOrigin } from './config'

function miniApiUrl(path) {
  const rawPath = String(path || '').trim()
  const cleanPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
  return `${String(MINI_API_BASE).trim().replace(/\/+$/, '')}${cleanPath}`.trim()
}

export function request({ url, method = 'GET', data, header }) {
  const requestUrl = miniApiUrl(url)
  console.log('[mini-request]', requestUrl)
  return new Promise((resolve, reject) => {
    uni.request({
      url: requestUrl,
      method,
      data,
      timeout: 8000,
      header: {
        'content-type': 'application/json',
        ...(header || {})
      },
      success(res) {
        const body = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 200) {
          resolve(body.data || {})
          return
        }
        const message = body.detail || body.message || `请求失败 ${res.statusCode}`
        reject(new Error(message))
      },
      fail(err) {
        const message = err.errMsg && String(err.errMsg).includes('invalid url')
          ? '请求地址无效，请检查微信开发者工具是否已关闭合法域名校验，或改用 HTTPS 后端地址'
          : (err.errMsg || '网络错误')
        reject(new Error(`${message}：${requestUrl}`))
      }
    })
  })
}

export function uploadFieldResult({ eventId, filePath, result, remark, operator }) {
  const requestUrl = miniApiUrl(`/events/${encodeURIComponent(eventId)}/field-result`)
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: requestUrl,
      filePath,
      timeout: 15000,
      name: 'photo',
      formData: {
        result,
        remark: remark || '',
        operator: operator || ''
      },
      success(res) {
        let body = {}
        try {
          body = JSON.parse(res.data || '{}')
        } catch (error) {
          reject(new Error('处理结果响应无效'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 200) {
          resolve(body.data || {})
          return
        }
        reject(new Error(body.detail || body.message || `提交失败 ${res.statusCode}`))
      },
      fail(err) {
        reject(new Error(`${err.errMsg || '上传失败'}：${requestUrl}`))
      }
    })
  })
}

export function uploadBroadcastAudio({ filePath, eventId, cameraId, operator }) {
  const path = eventId
    ? `/events/${encodeURIComponent(eventId)}/broadcast/audio`
    : `/cameras/${encodeURIComponent(cameraId)}/broadcast/audio`
  const requestUrl = miniApiUrl(path)
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: requestUrl,
      filePath,
      timeout: 15000,
      name: 'audio',
      formData: {
        device_ids: '[]',
        operator: operator || '现场处置员'
      },
      success(res) {
        let body = {}
        try {
          body = JSON.parse(res.data || '{}')
        } catch (error) {
          reject(new Error('喊话响应无效'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 200) {
          const result = body.data || {}
          if (result.success !== true || result.result === 'FAILED') {
            const failedItem = Array.isArray(result.items)
              ? result.items.find((item) => item.result === 'FAILED')
              : null
            reject(new Error(failedItem?.message || body.message || '喊话播放失败'))
            return
          }
          resolve(result)
          return
        }
        reject(new Error(body.detail || body.message || `喊话失败 ${res.statusCode}`))
      },
      fail(err) {
        reject(new Error(`${err.errMsg || '录音上传失败'}：${requestUrl}`))
      }
    })
  })
}

export const absoluteUrl = withApiOrigin
