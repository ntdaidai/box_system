import assert from 'node:assert/strict'
import {
  buildChartAxisWindow,
  buildHistoryWindow,
  buildTimeSeries,
  calcNiceYAxisRange,
  calcYAxisRange,
  formatChartAxisLabel,
  getNextHistoryRefreshMs,
  getHistoryRangeConfig,
  normalizeHistorySeries,
} from './sensorHistory.js'

const now = new Date('2026-07-01T21:17:35+08:00')

{
  const window = buildHistoryWindow('1h', now)
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T21:17:00+08:00').toISOString())
  assert.equal(new Date(window.startMs).toISOString(), new Date('2026-07-01T20:17:00+08:00').toISOString())
  assert.equal(getHistoryRangeConfig('1h').sampleMs, 60 * 1000)
  assert.equal(getHistoryRangeConfig('1h').majorTickMs, 10 * 60 * 1000)
}

{
  const window = buildHistoryWindow('1h', now)
  const axisWindow = buildChartAxisWindow(window)
  assert.equal(new Date(axisWindow.min).toISOString(), new Date('2026-07-01T20:15:00+08:00').toISOString())
  assert.equal(new Date(axisWindow.max).toISOString(), new Date('2026-07-01T21:19:00+08:00').toISOString())
  assert.equal(formatChartAxisLabel(axisWindow.min, '1h', window), '')
  assert.equal(formatChartAxisLabel(window.startMs, '1h', window), '20:17')
  assert.equal(formatChartAxisLabel(window.endMs, '1h', window), '21:17')
  assert.equal(formatChartAxisLabel(axisWindow.max, '1h', window), '')
}

{
  const window = buildHistoryWindow('6h', new Date('2026-07-01T21:50:00+08:00'))
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T21:50:00+08:00').toISOString())
  assert.equal(new Date(window.startMs).toISOString(), new Date('2026-07-01T15:50:00+08:00').toISOString())
  assert.equal(getHistoryRangeConfig('6h').sampleMs, 10 * 60 * 1000)
  assert.equal(getHistoryRangeConfig('6h').majorTickMs, 60 * 60 * 1000)
}

{
  const window = buildHistoryWindow('6h', new Date('2026-07-01T22:32:00+08:00'))
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T22:30:00+08:00').toISOString())
  assert.equal(new Date(window.startMs).toISOString(), new Date('2026-07-01T16:30:00+08:00').toISOString())
}

{
  const window = buildHistoryWindow('1d', now)
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T21:00:00+08:00').toISOString())
  assert.equal(new Date(window.startMs).toISOString(), new Date('2026-06-30T21:00:00+08:00').toISOString())
  assert.equal(getHistoryRangeConfig('1d').sampleMs, 30 * 60 * 1000)
  assert.equal(getHistoryRangeConfig('1d').majorTickMs, 4 * 60 * 60 * 1000)
}

{
  const window = buildHistoryWindow('7d', now)
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T21:00:00+08:00').toISOString())
  assert.equal(new Date(window.startMs).toISOString(), new Date('2026-06-24T21:00:00+08:00').toISOString())
  assert.equal(getHistoryRangeConfig('7d').sampleMs, 60 * 60 * 1000)
  assert.equal(getHistoryRangeConfig('7d').majorTickMs, 24 * 60 * 60 * 1000)
}

{
  const window = buildHistoryWindow('6mo', now)
  assert.equal(new Date(window.endMs).toISOString(), new Date('2026-07-01T00:00:00+08:00').toISOString())
  assert.equal(getHistoryRangeConfig('6mo').sampleMs, 24 * 60 * 60 * 1000)
  assert.equal(getHistoryRangeConfig('6mo').majorTickMs, 30 * 24 * 60 * 60 * 1000)
}

{
  const points = buildTimeSeries('1h', now)
  assert.equal(points.length, 60)
  assert.equal(new Date(points[0].start).toISOString(), new Date('2026-07-01T20:17:00+08:00').toISOString())
  assert.equal(new Date(points[0].time).toISOString(), new Date('2026-07-01T20:17:00+08:00').toISOString())
  assert.equal(new Date(points.at(-1).time).toISOString(), new Date('2026-07-01T21:16:00+08:00').toISOString())
}

{
  const history = [
    { timestamp: new Date('2026-07-01T20:17:20+08:00').getTime() / 1000, data: { temperature: 10 } },
    { timestamp: new Date('2026-07-01T20:17:45+08:00').getTime() / 1000, data: { temperature: 20 } },
    { timestamp: new Date('2026-07-01T20:18:10+08:00').getTime() / 1000, data: { temperature: 30 } },
  ]
  const result = normalizeHistorySeries(history, '1h', { temp: 'temperature' }, now)
  assert.deepEqual(result.series.temp[0], [new Date('2026-07-01T20:17:00+08:00').getTime(), 20])
  assert.deepEqual(result.series.temp[1], [new Date('2026-07-01T20:18:00+08:00').getTime(), 30])
  assert.equal(result.series.temp[2][1], null)
}

{
  const history = [
    { timestamp: new Date('2026-06-29T08:01:10+08:00').getTime() / 1000, data: { temperature: 24 } },
    { timestamp: new Date('2026-06-29T08:02:10+08:00').getTime() / 1000, data: { temperature: 25 } },
  ]
  const result = normalizeHistorySeries(history, '1h', { temp: 'temperature' }, now)
  const values = result.series.temp.map(point => point[1]).filter(value => value != null)
  assert.deepEqual(values, [])
  assert.equal(new Date(result.window.endMs).toISOString(), new Date('2026-07-01T21:17:00+08:00').toISOString())
}

{
  const backendWindow = {
    start: new Date('2026-06-29T08:00:00+08:00').getTime() / 1000,
    end: new Date('2026-06-29T08:10:00+08:00').getTime() / 1000,
  }
  const history = [
    { timestamp: new Date('2026-06-29T08:01:10+08:00').getTime() / 1000, data: { temperature: 24 } },
    { timestamp: new Date('2026-06-29T08:02:10+08:00').getTime() / 1000, data: { temperature: 25 } },
  ]
  const result = normalizeHistorySeries(
    history,
    '1h',
    { temp: 'temperature' },
    now,
    { window: backendWindow, sample_interval: 60 },
  )

  assert.equal(result.buckets.length, 10)
  assert.equal(new Date(result.window.startMs).toISOString(), new Date('2026-06-29T08:00:00+08:00').toISOString())
  assert.equal(new Date(result.window.endMs).toISOString(), new Date('2026-06-29T08:10:00+08:00').toISOString())
  assert.deepEqual(result.series.temp[1], [new Date('2026-06-29T08:01:00+08:00').getTime(), 24])
  assert.deepEqual(result.series.temp[2], [new Date('2026-06-29T08:02:00+08:00').getTime(), 25])
}

{
  const history = [
    { timestamp: new Date('2026-07-01T16:10:10+08:00').getTime() / 1000, data: { temperature: 16 } },
    { timestamp: new Date('2026-07-01T22:18:00+08:00').getTime() / 1000, data: { temperature: 22 } },
  ]
  const result = normalizeHistorySeries(history, '6h', { temp: 'temperature' }, new Date('2026-07-01T22:18:00+08:00'))
  assert.equal(new Date(result.window.startMs).toISOString(), new Date('2026-07-01T16:10:00+08:00').toISOString())
  assert.equal(new Date(result.window.endMs).toISOString(), new Date('2026-07-01T22:10:00+08:00').toISOString())
  assert.deepEqual(result.series.temp[0], [new Date('2026-07-01T16:10:00+08:00').getTime(), 16])
}

{
  const delay = getNextHistoryRefreshMs('1h', new Date('2026-07-01T22:21:00+08:00'))
  assert.equal(delay, 60 * 1000)
}

{
  const delay = getNextHistoryRefreshMs('6h', new Date('2026-07-01T22:32:00+08:00'))
  assert.equal(delay, 8 * 60 * 1000)
}

{
  const range = calcYAxisRange([[1, 26.5], [2, 27.8]], 0.2, { min: 10, max: 30 })
  assert.deepEqual(range, { min: 10, max: 30 })
}

{
  const range = calcYAxisRange([[1, 8], [2, 33]], 0.2, { min: 10, max: 30 })
  assert.deepEqual(range, { min: 3, max: 38 })
}

{
  const range = calcNiceYAxisRange(
    [[1, null], [2, 21.9], [3, 29.8], [4, undefined]],
    { min: 10, max: 30 },
    5,
  )
  assert.deepEqual(range, { min: 10, max: 30, interval: 5 })
}

{
  const range = calcNiceYAxisRange([21.9, 33.6], { min: 10, max: 30 }, 5)
  assert.deepEqual(range, { min: 10, max: 35, interval: 5 })
}

{
  const range = calcNiceYAxisRange([-3.6, 33.6], { min: 10, max: 30 }, 5)
  assert.deepEqual(range, { min: -10, max: 40, interval: 10 })
}
