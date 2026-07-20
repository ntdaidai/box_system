import test from 'node:test'
import assert from 'node:assert/strict'

import {
  formatWindSource,
  normalizeLegacyWindTrend,
  resolveWindLevel,
  shanghaiDateKey,
  windDirectionByDate,
  windForceFromKmh,
  windForceFromMs,
} from './windHistory.js'

test('wind level prefers measured value and rounds daily averages', () => {
  assert.equal(resolveWindLevel({ wind_level: 2.6, wind_speed_kmh: 4 }), 3)
  assert.equal(resolveWindLevel({ wind_level: 15 }), 12)
})

test('wind level falls back to Beaufort thresholds', () => {
  assert.equal(windForceFromKmh(0), 0)
  assert.equal(windForceFromKmh(4.5), 1)
  assert.equal(windForceFromKmh(5), 1)
  assert.equal(windForceFromKmh(6), 2)
  assert.equal(windForceFromKmh(11), 2)
  assert.equal(windForceFromKmh(19), 3)
  assert.equal(windForceFromKmh(117), 11)
  assert.equal(windForceFromKmh(118), 12)
  assert.equal(windForceFromKmh(-0.1), null)
  assert.equal(windForceFromMs(5.4), 3)
  assert.equal(windForceFromMs(5.5), 4)
  assert.equal(resolveWindLevel({ wind_speed_ms: 5.5 }), 4)
  assert.equal(resolveWindLevel({}), null)
})

test('wind source wording follows the supplied UI copy', () => {
  assert.equal(formatWindSource('西'), '来自西方')
  assert.equal(formatWindSource('东南'), '来自东南方向')
  assert.equal(formatWindSource(null), '--')
})

test('calendar helpers retain Shanghai dates and daily directions', () => {
  assert.equal(shanghaiDateKey('2026-01-14T16:00:00.000Z'), '2026-01-15')
  const directions = windDirectionByDate([
    { date: '2026-01-15', data: { wind_direction: '东' } },
    { date: '2026-01-16', data: {} },
  ])
  assert.equal(directions.get('2026-01-15'), '东')
  assert.equal(directions.has('2026-01-16'), false)
})

test('legacy history fallback keeps recent data inside the open-start window', () => {
  const normalized = normalizeLegacyWindTrend({
    window: { start: 100, end: 300 },
    max_point_count: 2,
    history: [
      { timestamp: 100, data: { wind_speed_kmh: 1 } },
      { timestamp: 200, data: { wind_speed_kmh: 2 } },
      { timestamp: 300, data: { wind_speed_kmh: 3 } },
    ],
  }, { view: 'recent24h' })

  assert.deepEqual(normalized.history.map(point => point.timestamp), [200, 300])
  assert.equal(normalized.point_count, 2)
})

test('legacy daily history is materialized without connecting missing days', () => {
  const bucketEnd = new Date('2026-07-02T00:00:00+08:00').getTime() / 1000
  const normalized = normalizeLegacyWindTrend({
    history: [{ timestamp: bucketEnd, data: { wind_speed_kmh: 3.6, wind_direction: '东' } }],
  }, { view: 'calendar', year: 2026, month: 7 })

  assert.equal(normalized.history.length, 31)
  assert.equal(normalized.history[0].date, '2026-07-01')
  assert.equal(normalized.history[0].data.wind_speed_kmh, 3.6)
  assert.deepEqual(normalized.history[1].data, {})
  assert.equal(normalized.point_count, 1)
})

test('legacy calendar fallback preserves leap day windows', () => {
  const normalized = normalizeLegacyWindTrend({ history: [] }, {
    view: 'calendar', year: 2024, month: 2,
  })

  assert.equal(normalized.history.length, 29)
  assert.equal(normalized.history[0].date, '2024-02-01')
  assert.equal(normalized.history.at(-1).date, '2024-02-29')
  assert.equal(normalized.window.end, new Date('2024-03-01T00:00:00+08:00').getTime() / 1000)
})

test('rolling fallback converts daily bucket-end timestamps to local dates', () => {
  const bucketEnd = new Date('2026-07-02T00:00:00+08:00').getTime() / 1000
  const normalized = normalizeLegacyWindTrend({
    window: { end: new Date('2026-07-19T00:00:00+08:00').getTime() / 1000 },
    history: [{ timestamp: bucketEnd, data: { wind_speed_kmh: 2 } }],
  }, { view: 'rolling12', now: '2026-07-19T08:00:00+08:00' })

  assert.equal(normalized.view, 'rolling12')
  assert.equal(normalized.history[0].date, '2025-08-01')
  assert.equal(normalized.history.at(-1).date, '2026-07-31')
  assert.equal(normalized.history.find(row => row.date === '2026-07-01').data.wind_speed_kmh, 2)
  assert.equal(normalized.history.find(row => row.date === '2026-06-30').data.wind_speed_kmh, undefined)
  assert.equal(normalized.point_count, 1)
  assert.equal(normalized.max_point_count, 365)
  assert.equal(normalized.window.start, new Date('2025-08-01T00:00:00+08:00').getTime() / 1000)
  assert.equal(normalized.window.end, new Date('2026-08-01T00:00:00+08:00').getTime() / 1000)
})
