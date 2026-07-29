const CAMERA_LIST_KEY = 'dam:camera:list:last-good:v1'
const CAMERA_DEVICE_KEY = 'dam:camera:devices:last-good:v1'

function storage() {
  if (typeof window !== 'undefined' && window.localStorage) return window.localStorage
  return null
}

function normalizeCameraArray(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.cameras)) return payload.cameras
  return []
}

function readSnapshot(key) {
  try {
    const raw = storage()?.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return normalizeCameraArray(parsed?.items)
  } catch {
    return []
  }
}

function writeSnapshot(key, items) {
  const normalized = normalizeCameraArray(items)
  if (!normalized.length) return
  try {
    storage()?.setItem(key, JSON.stringify({
      version: 1,
      updatedAt: Date.now(),
      items: normalized,
    }))
  } catch {
    // Best-effort UI fallback only.
  }
}

export function camerasFromPayload(payload) {
  return normalizeCameraArray(payload)
}

export function readCameraListSnapshot() {
  return readSnapshot(CAMERA_LIST_KEY)
}

export function writeCameraListSnapshot(items) {
  writeSnapshot(CAMERA_LIST_KEY, items)
}

export function readCameraDeviceSnapshot() {
  return readSnapshot(CAMERA_DEVICE_KEY)
}

export function writeCameraDeviceSnapshot(items) {
  writeSnapshot(CAMERA_DEVICE_KEY, items)
}
