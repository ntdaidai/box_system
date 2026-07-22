// dai
import assert from 'node:assert/strict'
import test from 'node:test'
import * as cameraDetectionView from './cameraDetectionView.js'

import {
  classColor,
  confidencePercent,
  detectionInZone,
  detectionName,
  findVideoSample,
  isValidDetection,
  normalizeClassifications,
  normalizeDetections,
  normalizeZones,
  primaryClassification,
  zoneTypeLabel,
} from './cameraDetectionView.js'


test('normalizes valid boxes and rejects malformed detector output', () => {
  const valid = {
    class_id: 0,
    confidence: 0.916,
    bbox: { x1: 10, y1: 20, x2: 80, y2: 90 },
  }
  const reversed = {
    class_id: 1,
    bbox: { x1: 80, y1: 20, x2: 10, y2: 90 },
  }
  const notFinite = {
    class_id: 2,
    bbox: { x1: 1, y1: Number.NaN, x2: 3, y2: 4 },
  }

  assert.equal(isValidDetection(valid), true)
  assert.deepEqual(normalizeDetections({ detections: [valid, reversed, notFinite] }), [valid])
  assert.deepEqual(normalizeDetections({ detections: null }), [])
})


test('finds the nearest sampled video result at or before playback time', () => {
  const timeline = [{ time: 0 }, { time: 0.5 }, { time: 1 }, { time: 1.5 }]
  assert.equal(findVideoSample(timeline, -1), timeline[0])
  assert.equal(findVideoSample(timeline, 0.99), timeline[1])
  assert.equal(findVideoSample(timeline, 1), timeline[2])
  assert.equal(findVideoSample(timeline, 99), timeline[3])
  assert.equal(findVideoSample([], 1), null)
})


test('supports current Chinese labels and future model classes', () => {
  assert.equal(detectionName({ class_id: 0, class_name: 'boat', class_name_cn: '船只' }), '船只')
  assert.equal(detectionName({ class_id: 9, class_name: 'future_damage' }), 'future_damage')
  assert.equal(detectionName({ class_id: 11 }), '类别 11')
  assert.equal(confidencePercent({ confidence: 0.916 }), 92)
  assert.equal(confidencePercent({ confidence: 3 }), 100)
  assert.match(classColor(11), /^hsl\(/)
})


test('normalizes whole-image classifications without requiring bounding boxes', () => {
  const flood = {
    class_id: 1,
    class_name: 'flood',
    class_name_cn: '洪水',
    confidence: 0.94,
  }
  const invalid = { class_id: 2, confidence: 'unknown' }
  const payload = { prediction: flood, classifications: [flood, invalid] }

  assert.deepEqual(normalizeClassifications(payload), [flood])
  assert.equal(primaryClassification(payload), flood)
  assert.equal(primaryClassification({ classifications: [flood] }), flood)
  assert.equal(primaryClassification(null), null)
})


test('formats camera communication timestamps as fixed Shanghai month-day time', () => {
  assert.equal(typeof cameraDetectionView.formatDeviceCommTime, 'function')
  const timestampMs = Date.UTC(2026, 6, 20, 3, 11, 12)
  assert.equal(cameraDetectionView.formatDeviceCommTime(timestampMs / 1000), '07/20 11:11:12')
  assert.equal(cameraDetectionView.formatDeviceCommTime(timestampMs), '07/20 11:11:12')
  assert.equal(cameraDetectionView.formatDeviceCommTime(0), '--')
})


test('normalizes virtual zones and matches detector anchors inside areas', () => {
  const zones = normalizeZones({
    zones: [
      {
        id: 'fish_area',
        type: 'illegal_fishing',
        rect: { x: 0.1, y: 0.1, width: 0.5, height: 0.5 },
      },
      { id: 'bad', type: 'unknown', rect: { x: 0, y: 0, width: 1, height: 1 } },
    ],
  })
  const boat = {
    class_id: 0,
    class_name: 'boat',
    bbox: { x1: 100, y1: 100, x2: 200, y2: 200 },
  }
  const person = {
    class_id: 3,
    class_name: 'normal_person',
    bbox: { x1: 100, y1: 100, x2: 200, y2: 500 },
  }

  assert.equal(zones.length, 1)
  assert.equal(zoneTypeLabel(zones[0].type), '违规捕鱼')
  assert.equal(detectionInZone(boat, zones[0], 1000, 1000), true)
  assert.equal(detectionInZone(person, zones[0], 1000, 1000), false)
  assert.equal(
    detectionInZone(
      person,
      { ...zones[0], type: 'person_intrusion', rect: { x: 0.1, y: 0.4, width: 0.2, height: 0.2 } },
      1000,
      1000,
    ),
    true,
  )
})
