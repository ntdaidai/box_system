const CACHE_NAMESPACE = 'dam:api-cache:v2'
const DEFAULT_MAX_AGE = 24 * 60 * 60 * 1000
const URL_MAX_AGE = [
  [/^\/v1\/sensor\/realtime/, 15 * 1000],
  [/^\/v1\/sensor\/status$/, 30 * 1000],
  [/^\/v1\/system\/info$/, 30 * 1000],
  [/^\/alarm\/statistics$/, 60 * 1000],
  [/^\/alarm\/list$/, 2 * 60 * 1000],
  [/^\/v1\/sensor\/history\//, 10 * 60 * 1000],
  [/^\/device\//, 5 * 60 * 1000],
  [/^\/rule\//, 5 * 60 * 1000],
  [/^\/analysis\//, 5 * 60 * 1000],
]
const URL_STALE_MAX_AGE = []

const memoryStorage = new Map()

function getStorage() {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }

  return {
    getItem: (key) => memoryStorage.get(key) ?? null,
    setItem: (key, value) => memoryStorage.set(key, value),
    removeItem: (key) => memoryStorage.delete(key),
    key: (index) => Array.from(memoryStorage.keys())[index] ?? null,
    get length() {
      return memoryStorage.size
    },
  }
}

function stableStringify(value) {
  if (value == null) return ''
  if (typeof value !== 'object') return String(value)
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`
  }

  return Object.keys(value)
    .sort()
    .map((key) => `${encodeURIComponent(key)}=${stableStringify(value[key])}`)
    .join('&')
}

function normalizeParams(url, params) {
  if (/^\/v1\/sensor\/history\//.test(url) && !params?.range) {
    return { ...(params || {}), range: '1h' }
  }
  return params
}

function getDefaultMaxAge(url = '') {
  const match = URL_MAX_AGE.find(([pattern]) => pattern.test(url))
  return match ? match[1] : DEFAULT_MAX_AGE
}

function getDefaultStaleMaxAge(url = '') {
  const match = URL_STALE_MAX_AGE.find(([pattern]) => pattern.test(url))
  return match ? match[1] : 0
}

export function isCacheableRequest(config = {}) {
  const method = (config.method || 'get').toLowerCase()
  return method === 'get' && config.localCache !== false
}

export function buildCacheKey(config = {}) {
  const method = (config.method || 'get').toLowerCase()
  const baseURL = config.baseURL || ''
  const url = config.url || ''
  const params = stableStringify(normalizeParams(url, config.params))
  return `${CACHE_NAMESPACE}:${method}:${baseURL}${url}?${params}`
}

export function readCachedResponse(config = {}, now = Date.now()) {
  if (!isCacheableRequest(config)) return null

  const storage = getStorage()
  const key = buildCacheKey(config)
  const raw = storage.getItem(key)
  if (!raw) return null

  try {
    const cached = JSON.parse(raw)
    const age = now - cached.updatedAt
    const maxAge = Number(config.localCacheMaxAge ?? getDefaultMaxAge(config.url))
    const staleMaxAge = Number(config.localCacheStaleMaxAge ?? getDefaultStaleMaxAge(config.url))
    if (!cached || cached.version !== 1) {
      storage.removeItem(key)
      return null
    }

    if (age > maxAge) {
      if (config.localCacheAllowStale === true && age <= staleMaxAge) {
        return {
          key,
          data: cached.data,
          updatedAt: cached.updatedAt,
          stale: true,
        }
      }
      storage.removeItem(key)
      return null
    }

    return {
      key,
      data: cached.data,
      updatedAt: cached.updatedAt,
      stale: false,
    }
  } catch {
    storage.removeItem(key)
    return null
  }
}

export function writeCachedResponse(config = {}, data, now = Date.now()) {
  if (!isCacheableRequest(config)) return null

  const storage = getStorage()
  const key = buildCacheKey(config)
  const payload = JSON.stringify({
    version: 1,
    updatedAt: now,
    data,
  })

  try {
    storage.setItem(key, payload)
    return { key, data, updatedAt: now }
  } catch {
    return null
  }
}

export function clearResponseCache() {
  const storage = getStorage()
  const keys = []
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i)
    if (key?.startsWith(`${CACHE_NAMESPACE}:`)) keys.push(key)
  }
  keys.forEach((key) => storage.removeItem(key))
  return keys.length
}

export function notifyCacheUpdated(detail) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent('dam-api-cache-updated', { detail }))
}
