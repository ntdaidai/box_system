import { MINI_API_BASE, withApiOrigin } from './config'

const TOKEN_STORAGE_KEY = 'dam_mini_cache:mini-token'
let unauthorizedPrompting = false

function readAuthToken() {
  try {
    return uni.getStorageSync(TOKEN_STORAGE_KEY) || ''
  } catch (error) {
    return ''
  }
}

function clearLoginState() {
  try {
    uni.removeStorageSync(TOKEN_STORAGE_KEY)
    uni.removeStorageSync('dam_mini_cache:mini-staff')
    uni.removeStorageSync('mini_openid')
  } catch (error) {
    // 忽略存储清理失败
  }
}

function handleUnauthorized() {
  clearLoginState()
  uni.$emit('mini-auth-changed', { loggedIn: false, staff: null })
  if (unauthorizedPrompting) return
  unauthorizedPrompting = true
  uni.showModal({
    title: '登录已失效',
    content: '原绑定人员可能已被管理员删除，本机登录已经清除。',
    confirmText: '前往登录',
    cancelText: '退出登录',
    success: (res) => {
      if (res.confirm) {
        uni.switchTab({ url: '/pages/profile/index' })
      }
    },
    complete: () => {
      unauthorizedPrompting = false
    }
  })
}

function miniApiUrl(path) {
  const rawPath = String(path || '').trim()
  const cleanPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
  return `${String(MINI_API_BASE).trim().replace(/\/+$/, '')}${cleanPath}`.trim()
}

function authHeader() {
  const authToken = readAuthToken()
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
}

export function request({ url, method = 'GET', data, header }) {
  const requestUrl = miniApiUrl(url)
  const authToken = readAuthToken()
  console.log('[mini-request]', requestUrl)
  return new Promise((resolve, reject) => {
    uni.request({
      url: requestUrl,
      method,
      data,
      timeout: 8000,
      header: {
        'content-type': 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(header || {})
      },
      success(res) {
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(new Error('登录已失效，请重新扫码登录'))
          return
        }
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

export function uploadFieldPhoto({ eventId, filePath, phase, eventType, operator }) {
  const requestUrl = miniApiUrl(`/events/${encodeURIComponent(eventId)}/field-photo`)
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: requestUrl,
      filePath,
      timeout: 15000,
      name: 'photo',
      header: authHeader(),
      formData: {
        phase,
        event_type: eventType,
        operator: operator || ''
      },
      success(res) {
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(new Error('登录已失效，请重新扫码登录'))
          return
        }
        let body = {}
        try {
          body = JSON.parse(res.data || '{}')
        } catch (error) {
          reject(new Error('现场照片响应无效'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 200) {
          resolve(body.data || {})
          return
        }
        reject(new Error(body.detail || body.message || `上传失败 ${res.statusCode}`))
      },
      fail(err) {
        reject(new Error(`${err.errMsg || '上传失败'}：${requestUrl}`))
      }
    })
  })
}

export function confirmFieldResult({ eventId, result, remark, operator, eventType, photoUrls }) {
  return request({
    url: `/events/${encodeURIComponent(eventId)}/field-result/confirm`,
    method: 'POST',
    data: {
      result,
      remark: remark || '',
      operator: operator || '',
      event_type: eventType,
      photo_urls: photoUrls
    }
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
      header: authHeader(),
      formData: {
        device_ids: '[]',
        operator: operator || '现场处置员'
      },
      success(res) {
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(new Error('登录已失效，请重新扫码登录'))
          return
        }
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
