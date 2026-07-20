import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as windHistoryModule from './windHistory.js'

import {
  formatWindSource,
  normalizeLegacyWindTrend,
  resolveWindLevel,
  shanghaiDateKey,
  windDirectionByDate,
  windForceFromKmh,
  windForceFromMs,
} from './windHistory.js'

test('wind calendar axis uses sparse date-only monthly labels', () => {
  assert.equal(typeof windHistoryModule.formatWindCalendarAxisLabel, 'function')
  assert.equal(typeof windHistoryModule.shouldShowWindCalendarLabel, 'function')

  assert.equal(windHistoryModule.formatWindCalendarAxisLabel('2026-07-01', true), '1日')
  assert.equal(windHistoryModule.formatWindCalendarAxisLabel('2026-07-29', true), '29日')
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(0, '2026-07-01', true, 1000, 0), true)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(1, '2026-07-02', true, 1000, 0), false)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(4, '2026-07-05', true, 1000, 0), true)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(28, '2026-07-29', true, 1000, 0), true)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(29, '2026-07-30', true, 1000, 0), false)
})

test('wind calendar axis retains month labels for annual views', () => {
  const firstMonthIndex = 2026 * 12 + 1

  assert.equal(windHistoryModule.formatWindCalendarAxisLabel('2026-01-01', false), '1月')
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(0, '2026-01-01', false, 1000, firstMonthIndex), true)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(1, '2026-01-02', false, 1000, firstMonthIndex), false)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(31, '2026-02-01', false, 320, firstMonthIndex), false)
  assert.equal(windHistoryModule.shouldShowWindCalendarLabel(59, '2026-03-01', false, 320, firstMonthIndex), true)
})

test('wind trend keeps data symbols hidden until hover', () => {
  const source = readFileSync(new URL('../views/Monitor/SensorWind.vue', import.meta.url), 'utf8')
  const seriesBlock = source.match(/id: 'wind-speed'[\s\S]*?smooth:/)?.[0] || ''

  assert.match(seriesBlock, /showSymbol:\s*false/)
  assert.doesNotMatch(seriesBlock, /showSymbol:\s*!recent/)
})

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
