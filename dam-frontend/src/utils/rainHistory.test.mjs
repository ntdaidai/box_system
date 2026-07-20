import assert from 'node:assert/strict'
import * as rainHistory from './rainHistory.js'
import {
  buildDailyRainChartValues,
  buildDailyRainRows,
  buildRainChartValues,
  rainLegendLabel,
  resolveRainCalendarSelection,
  toRainNumber,
} from './rainHistory.js'

{
  assert.equal(toRainNumber(0), 0)
  assert.equal(toRainNumber('0'), 0)
  assert.equal(toRainNumber(null), null)
  assert.equal(toRainNumber(undefined), null)
  assert.equal(toRainNumber(''), null)
  assert.equal(toRainNumber(false), null)
}

{
  assert.equal(typeof rainHistory.rainBarMinHeight, 'function')
  assert.equal(rainHistory.rainBarMinHeight([0, 0, null]), 2)
  assert.equal(rainHistory.rainBarMinHeight([0, 0.2, null]), 0)
  assert.equal(rainHistory.rainBarMinHeight([null, null]), 0)
}

{
  assert.equal(typeof rainHistory.buildRainTrendParams, 'function')
  assert.deepEqual(rainHistory.buildRainTrendParams({ view: 'recent24h' }), { view: 'recent24h' })
  assert.deepEqual(
    rainHistory.buildRainTrendParams({ view: 'calendar', year: 2026, month: 7 }),
    { view: 'calendar', year: 2026, month: 7 },
  )
  assert.deepEqual(
    rainHistory.buildRainTrendParams({ view: 'rolling12', year: 2025, month: 3 }),
    { view: 'rolling12' },
  )
}

{
  const history = [
    { timestamp: 100, data: { rain_increment: 0 } },
    { timestamp: 200, data: {} },
    { timestamp: 300, data: { rain_increment: 1.25 } },
  ]

  assert.deepEqual(buildRainChartValues(history, 'recent24h'), [0, null, 1.25])
  assert.deepEqual(buildRainChartValues(history, 'calendar'), [null, null, null])
  assert.equal(rainLegendLabel('recent24h'), '30分钟新增雨量')
  assert.equal(rainLegendLabel('calendar'), '逐日雨量')
  assert.equal(rainLegendLabel('rolling12'), '逐日雨量')
}

{
  const history = [
    { date: '2026-07-01', data: { daily_rain: 0 } },
    { date: '2026-07-02', data: {} },
    { date: '2026-07-03', data: { daily_rain: 12.5 } },
  ]

  assert.deepEqual(buildDailyRainChartValues(history), [0, null, 12.5])
  assert.deepEqual(
    buildDailyRainRows(history).map(row => [row.date, row.value]),
    [['2026-07-01', 0], ['2026-07-03', 12.5]],
  )
}

{
  const periods = [{ year: 2026, months: [6, 7] }, { year: 2025, months: [12] }]
  assert.deepEqual(resolveRainCalendarSelection(periods, 2027, 7), { year: 2026, month: 'all' })
  assert.deepEqual(resolveRainCalendarSelection(periods, 2026, 5), { year: 2026, month: 'all' })
  assert.deepEqual(resolveRainCalendarSelection(periods, 2026, 7), { year: 2026, month: 7 })
}
