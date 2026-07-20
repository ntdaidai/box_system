// dai
import assert from 'node:assert/strict'
import test from 'node:test'

import {
  classColor,
  confidencePercent,
  detectionName,
  findVideoSample,
  isValidDetection,
  normalizeClassifications,
  normalizeDetections,
  primaryClassification,
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
