import assert from 'node:assert/strict'
import {
  formatWindAngle,
  getWindCompassState,
  normalizeWindAngle,
} from './sensorWindView.js'

{
  assert.equal(normalizeWindAngle(318.1), 318.1)
  assert.equal(normalizeWindAngle(720), 0)
  assert.equal(normalizeWindAngle(-45), 315)
  assert.equal(normalizeWindAngle(null), null)
  assert.equal(normalizeWindAngle('not-a-number'), null)
}

{
  assert.equal(formatWindAngle(318.123), '318.1°')
  assert.equal(formatWindAngle(null), '--')
}

{
  const state = getWindCompassState({ wind_direction: '西北', wind_angle: 318.1 })
  assert.deepEqual(state, {
    direction: '西北',
    angle: 318.1,
    angleText: '318.1°',
    footerDirection: '西北风',
    pointerStyle: {
      transform: 'rotate(318.1deg)',
    },
  })
}

{
  const emptyState = getWindCompassState({})
  assert.deepEqual(emptyState, {
    direction: '--',
    angle: null,
    angleText: '--',
    footerDirection: '--',
    pointerStyle: {
      transform: 'rotate(0deg)',
    },
  })
}
