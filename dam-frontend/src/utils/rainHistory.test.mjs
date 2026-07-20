import assert from 'node:assert/strict'
import {
  buildDailyRainChartValues,
  buildDailyRainRows,
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
