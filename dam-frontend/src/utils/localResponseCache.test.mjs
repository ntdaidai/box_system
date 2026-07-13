import assert from 'node:assert/strict'
import {
  buildCacheKey,
  clearResponseCache,
  isCacheableRequest,
  readCachedResponse,
  writeCachedResponse,
} from './localResponseCache.js'

{
  assert.equal(isCacheableRequest({ method: 'get', url: '/v1/sensor/history/temp' }), true)
  assert.equal(isCacheableRequest({ method: 'post', url: '/device' }), false)
  assert.equal(isCacheableRequest({ method: 'get', url: '/device', localCache: false }), false)
}

{
  const left = buildCacheKey({
    method: 'get',
    baseURL: '/api',
    url: '/alarm/list',
    params: { page_size: 5, page_num: 1 },
  })
  const right = buildCacheKey({
    method: 'get',
    baseURL: '/api',
    url: '/alarm/list',
    params: { page_num: 1, page_size: 5 },
  })
  assert.equal(left, right)
}

{
  const implicitOneHour = buildCacheKey({
    method: 'get',
    baseURL: '/api',
    url: '/v1/sensor/history/temp_humidity',
  })
  const explicitOneHour = buildCacheKey({
    method: 'get',
    baseURL: '/api',
    url: '/v1/sensor/history/temp_humidity',
    params: { range: '1h' },
  })
  assert.equal(implicitOneHour, explicitOneHour)
}

{
  clearResponseCache()
  const config = {
    method: 'get',
    baseURL: '/api',
    url: '/v1/sensor/history/temp_humidity',
    params: { range: '1h' },
  }
  const cached = writeCachedResponse(config, { code: 200, data: { value: 1 } }, 1000)
  assert.equal(typeof cached.key, 'string')

  const hit = readCachedResponse(config, 1200)
  assert.deepEqual(hit.data, { code: 200, data: { value: 1 } })
  assert.equal(hit.updatedAt, 1000)
}

{
  clearResponseCache()
  const config = {
    method: 'get',
    url: '/v1/sensor/realtime',
  }
  writeCachedResponse(config, { code: 200, data: { stale: true } }, 1000)

  assert.deepEqual(readCachedResponse(config, 15_999).data, { code: 200, data: { stale: true } })
  assert.equal(readCachedResponse(config, 17_000), null)
}

{
  clearResponseCache()
  const config = {
    method: 'get',
    url: '/v1/sensor/history/wind',
    params: { range: '7d' },
    localCacheAllowStale: true,
  }
  writeCachedResponse(config, { code: 200, data: { stale: true } }, 1000)

  assert.equal(readCachedResponse(config, 20 * 60 * 1000), null)
}

{
  clearResponseCache()
  const config = {
    method: 'get',
    url: '/v1/sensor/realtime',
    localCacheMaxAge: 100,
  }
  writeCachedResponse(config, { code: 200, data: { stale: true } }, 1000)

  assert.equal(readCachedResponse(config, 1201), null)
}

{
  clearResponseCache()
  writeCachedResponse({ method: 'get', url: '/a' }, { code: 200 }, 1000)
  writeCachedResponse({ method: 'get', url: '/b' }, { code: 200 }, 1000)
  assert.equal(clearResponseCache(), 2)
  assert.equal(readCachedResponse({ method: 'get', url: '/a' }), null)
}
