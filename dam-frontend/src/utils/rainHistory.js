export const toRainNumber = (value) => {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

export const buildDailyRainRows = (history = []) => history
  .map(row => ({ ...row, value: toRainNumber(row?.data?.daily_rain) }))
  .filter(row => row.value !== null)

export const buildDailyRainChartValues = (history = []) => history
  .map(row => toRainNumber(row?.data?.daily_rain))

export const buildRainChartValues = (history = [], view = 'calendar') => history
  .map(row => toRainNumber(row?.data?.[view === 'recent24h' ? 'rain_increment' : 'daily_rain']))

export const rainLegendLabel = view => view === 'recent24h' ? '30分钟新增雨量' : '逐日雨量'

export const rainBarMinHeight = (values = []) => {
  const numeric = values.map(toRainNumber).filter(value => value !== null)
  return numeric.length > 0 && numeric.every(value => value === 0) ? 2 : 0
}

export const buildRainTrendParams = ({ view = 'recent24h', year, month } = {}) => {
  const params = { view }
  if (view === 'calendar' && year != null) params.year = year
  if (view === 'calendar' && month != null && month !== 'all') params.month = month
  return params
}

export const resolveRainCalendarSelection = (
  periods = [],
  selectedYear,
  selectedMonth = 'all',
) => {
  if (!Array.isArray(periods) || !periods.length) {
    return { year: Number(selectedYear), month: selectedMonth }
  }

  const selected = periods.find(item => Number(item.year) === Number(selectedYear))
  if (!selected) {
    return { year: Number(periods[0].year), month: 'all' }
  }

  const month = selectedMonth === 'all' ? 'all' : Number(selectedMonth)
  const availableMonths = (selected.months || []).map(Number)
  return {
    year: Number(selected.year),
    month: month === 'all' || availableMonths.includes(month) ? month : 'all',
  }
}
