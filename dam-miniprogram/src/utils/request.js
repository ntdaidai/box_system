import { MINI_API_BASE, withApiOrigin } from './config'

export function request({ url, method = 'GET', data, header }) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${MINI_API_BASE}${url}`,
      method,
      data,
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
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

export function uploadFieldResult({ eventId, filePath, result, remark, operator }) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${MINI_API_BASE}/events/${encodeURIComponent(eventId)}/field-result`,
      filePath,
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
        reject(new Error(err.errMsg || '上传失败'))
      }
    })
  })
}

export const absoluteUrl = withApiOrigin
