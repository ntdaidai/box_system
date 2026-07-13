export const normalizeWindAngle = (angle) => {
  if (angle == null) return null
  const value = Number(angle)
  if (!Number.isFinite(value)) return null
  return ((value % 360) + 360) % 360
}

export const formatWindAngle = (angle) => {
  const normalized = normalizeWindAngle(angle)
  return normalized == null ? '--' : `${normalized.toFixed(1)}°`
}

export const getWindCompassState = (windData = {}) => {
  const angle = normalizeWindAngle(windData.wind_angle)
  const direction = angle == null ? '--' : (windData.wind_direction || '--')

  return {
    direction,
    angle,
    angleText: formatWindAngle(angle),
    footerDirection: direction === '--' ? '--' : `${direction}风`,
    pointerStyle: {
      transform: `rotate(${angle ?? 0}deg)`,
    },
  }
}
