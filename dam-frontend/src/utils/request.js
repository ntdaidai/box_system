import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  buildCacheKey,
  clearResponseCache,
  notifyCacheUpdated,
  readCachedResponse,
  writeCachedResponse,
} from './localResponseCache'

const service = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

const pendingRefreshes = new Map()
let authRedirecting = false

function withRequestDefaults(url, config = {}) {
  const next = { ...config }
  if (/^\/v1\/sensor\/history\//.test(url)) {
    next.timeout = next.timeout ?? 60000
    next.silentError = next.silentError ?? true
    next.localCacheAllowStale = next.localCacheAllowStale ?? false
  }
  return next
}

function withCacheDefaults(url, config = {}) {
  return {
    ...config,
    method: 'get',
    baseURL: config.baseURL ?? service.defaults.baseURL,
    url,
  }
}

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    const method = (response.config?.method || 'get').toLowerCase()
    if (method === 'get') {
      writeCachedResponse(response.config, res)
    } else {
      clearResponseCache()
    }

    return res
  },
  (error) => {
    // dai: Convert an expired/missing token into one clear login flow. This
    // also clears cached authenticated responses before leaving the page.
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      clearResponseCache()
      const detail = error.response?.data?.detail || '登录状态已失效，请重新登录'
      if (window.location.pathname !== '/login' && !authRedirecting) {
        authRedirecting = true
        ElMessage.warning(detail)
        const redirect = encodeURIComponent(
          `${window.location.pathname}${window.location.search}${window.location.hash}`,
        )
        window.setTimeout(() => window.location.replace(`/login?redirect=${redirect}`), 250)
      } else if (window.location.pathname === '/login' && !error.config?.silentError) {
        ElMessage.error(detail)
      }
      return Promise.reject(error)
    }
    if (!error.config?.silentError) {
      ElMessage.error(error.response?.data?.detail || error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

const networkGet = service.get.bind(service)

function refreshCachedGet(url, config, cacheKey) {
  if (pendingRefreshes.has(cacheKey)) return

  const refreshConfig = {
    ...config,
    silentError: true,
  }

  const pending = networkGet(url, refreshConfig)
    .then((data) => {
      notifyCacheUpdated({ key: cacheKey, url, params: config?.params, data })
      return data
    })
    .catch(() => null)
    .finally(() => {
      pendingRefreshes.delete(cacheKey)
    })

  pendingRefreshes.set(cacheKey, pending)
}

service.get = function cachedGet(url, config = {}) {
  const requestConfig = withRequestDefaults(url, config)
  const cacheConfig = withCacheDefaults(url, requestConfig)
  const cached = readCachedResponse(cacheConfig)

  if (cached) {
    refreshCachedGet(url, requestConfig, cached.key)
    return Promise.resolve(cached.data)
  }

  const cacheKey = buildCacheKey(cacheConfig)
  if (pendingRefreshes.has(cacheKey)) {
    return pendingRefreshes.get(cacheKey)
  }

  const pending = networkGet(url, requestConfig)
    .finally(() => {
      pendingRefreshes.delete(cacheKey)
    })
  pendingRefreshes.set(cacheKey, pending)
  return pending
}

export default service
