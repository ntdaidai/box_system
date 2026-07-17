// dai
import assert from 'node:assert/strict'
import test from 'node:test'

import { createSseParser } from './detectionEvents.js'


test('SSE parser handles chunk boundaries, CRLF, and heartbeat comments', () => {
  const events = []
  const parser = createSseParser((event) => events.push(event))

  parser.push(': keep-alive\n\n')
  parser.push('id: 7\r\nevent: det')
  parser.push('ection\r\ndata: {"camera_id":"camera_1",')
  parser.push('"count":1}\r\n\r\n')

  assert.equal(events.length, 1)
  assert.deepEqual(events[0], {
    event: 'detection',
    id: '7',
    data: '{"camera_id":"camera_1","count":1}',
  })
})


test('SSE parser joins multiple data lines and emits multiple events', () => {
  const events = []
  const parser = createSseParser((event) => events.push(event))
  parser.push(
    'event: detection\ndata: {"enabled":true,\ndata: "count":0}\n\n'
      + 'data: second\n\n',
  )

  assert.equal(events.length, 2)
  assert.equal(events[0].data, '{"enabled":true,\n"count":0}')
  assert.equal(events[1].event, 'message')
  assert.equal(events[1].data, 'second')
})
