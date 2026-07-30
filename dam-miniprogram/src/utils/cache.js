const PREFIX = 'dam_mini_cache:'

export function readCache(key, fallback) {
  try {
    const value = uni.getStorageSync(`${PREFIX}${key}`)
    return value || fallback
  } catch (error) {
    return fallback
  }
}

export function writeCache(key, value) {
  try {
    uni.setStorageSync(`${PREFIX}${key}`, value)
  } catch (error) {
    // Ignore storage quota or privacy-mode failures.
  }
}
