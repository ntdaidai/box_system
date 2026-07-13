import assert from 'node:assert/strict'
import {
  cancelIdleTask,
  createSensorDetailStartup,
  preloadHistoryRanges,
  runWhenIdle,
} from './sensorDetailStartup.js'

{
  const calls = []
  const startup = createSensorDetailStartup({
    initChart: () => calls.push('initChart'),
    fetchRealtime: () => calls.push('fetchRealtime'),
    loadInitialHistory: async () => calls.push('loadInitialHistory'),
    renderHistory: () => calls.push('renderHistory'),
    scheduleHistoryRefresh: () => calls.push('scheduleHistoryRefresh'),
    preloadHistoryLater: () => calls.push('preloadHistoryLater'),
  })

  startup.start()

  assert.deepEqual(calls.slice(0, 2), ['initChart', 'fetchRealtime'])
  assert.equal(calls.includes('loadInitialHistory'), false)

  await startup.historyReady
  assert.deepEqual(calls, [
    'initChart',
    'fetchRealtime',
    'loadInitialHistory',
    'renderHistory',
    'scheduleHistoryRefresh',
    'preloadHistoryLater',
  ])
}

{
  const calls = []
  const id = runWhenIdle(() => calls.push('idle'), 1)
  cancelIdleTask(id)
  await new Promise(resolve => setTimeout(resolve, 20))
  assert.deepEqual(calls, [])
}

{
  const calls = []
  let active = 0
  let peakActive = 0

  await preloadHistoryRanges(['6h', '1d'], async (range) => {
    active += 1
    peakActive = Math.max(peakActive, active)
    calls.push(`start:${range}`)
    await new Promise(resolve => setTimeout(resolve, 1))
    calls.push(`end:${range}`)
    active -= 1
  })

  assert.equal(peakActive, 1)
  assert.deepEqual(calls, ['start:6h', 'end:6h', 'start:1d', 'end:1d'])
}
