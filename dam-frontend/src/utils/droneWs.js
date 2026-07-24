/**
 * DJI Cloud API WebSocket 客户端
 * 用于实时接收无人机遥测数据（OSD）
 */

const RECONNECT_DELAY_MIN = 3000
const RECONNECT_DELAY_MAX = 20000
const MAX_RETRIES = 10

// WebSocket 连接状态
export const WS_STATE = {
  CLOSED: 'closed',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
}

/**
 * 建立 dij WebSocket 连接
 * @param {object} options
 * @param {string} [options.host] - dij 后端地址（直连模式，如 192.168.31.52:6790）
 * @param {string} [options.wsUrl] - 完整 WebSocket URL（代理模式优先使用）
 * @param {string} options.token - JWT token
 * @param {function} options.onDeviceOsd - 飞行器 OSD 回调 (data) => void
 * @param {function} options.onGatewayOsd - 遥控器 OSD 回调
 * @param {function} options.onDockOsd - 机场 OSD 回调
 * @param {function} options.onDeviceOnline - 设备上线回调
 * @param {function} options.onDeviceOffline - 设备下线回调
 * @param {function} options.onDeviceHms - HMS 告警回调
 * @param {function} options.onState - 连接状态回调 (state) => void
 * @param {function} options.onError - 错误回调
 * @returns {function} 关闭连接的函数
 */
export function connectDroneWs(options) {
  const {
    host,
    wsUrl,
    token,
    onDeviceOsd,
    onGatewayOsd,
    onDockOsd,
    onDeviceOnline,
    onDeviceOffline,
    onDeviceHms,
    onState,
    onError,
  } = options

  let ws = null
  let retryCount = 0
  let retryTimer = null
  let closed = false

  function setState(state) {
    onState?.(state)
  }

  function getRetryDelay() {
    return Math.min(
      RECONNECT_DELAY_MIN * Math.pow(1.5, retryCount),
      RECONNECT_DELAY_MAX
    )
  }

  function connect() {
    if (closed) return
    setState(retryCount === 0 ? WS_STATE.CONNECTING : WS_STATE.RECONNECTING)

    const finalWsUrl = wsUrl
      ? `${wsUrl}?x-auth-token=${encodeURIComponent(token)}`
      : `ws://${host || '127.0.0.1:6790'}/api/v1/ws?x-auth-token=${encodeURIComponent(token)}`

    try {
      ws = new WebSocket(finalWsUrl)
    } catch (err) {
      onError?.(err)
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      retryCount = 0
      setState(WS_STATE.CONNECTED)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const bizCode = msg.biz_code
        // dij 后端消息格式: { biz_code, data: { host: { ...实际数据 } } }
        const data = msg.data?.host || msg.data

        switch (bizCode) {
          case 'device_osd':
            onDeviceOsd?.(data)
            break
          case 'gateway_osd':
            onGatewayOsd?.(data)
            break
          case 'dock_osd':
            onDockOsd?.(data)
            break
          case 'device_online':
            onDeviceOnline?.(data)
            break
          case 'device_offline':
            onDeviceOffline?.(data)
            break
          case 'device_hms':
            onDeviceHms?.(data)
            break
          default:
            // 其他消息类型忽略
            break
        }
      } catch {
        // 解析失败忽略
      }
    }

    ws.onerror = (err) => {
      onError?.(err)
    }

    ws.onclose = () => {
      ws = null
      if (!closed) {
        scheduleReconnect()
      }
    }
  }

  function scheduleReconnect() {
    if (closed) return
    const delay = getRetryDelay()
    retryCount++
    setState(WS_STATE.RECONNECTING)
    retryTimer = setTimeout(connect, delay)
  }

  // 启动连接
  connect()

  // 返回关闭函数
  return function close() {
    closed = true
    clearTimeout(retryTimer)
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    setState(WS_STATE.CLOSED)
  }
}

/**
 * 解析飞行模式代码为中文
 * @param {number} modeCode
 * @returns {string}
 */
export function parseFlightMode(modeCode) {
  const modes = {
    0: '待机',
    1: '准备中',
    2: '就绪',
    3: '手动飞行',
    4: '自动飞行',
    5: '航点飞行',
    6: '返航中',
    7: '降落中',
    8: '降落',
    9: '已降落',
    10: '悬停',
    11: '三桨叶降落',
    12: '固件升级中',
    13: '无 GPS 手动',
    14: '强制返航',
    15: '找机中',
    16: '避障悬停',
    17: '迫降',
    18: '动力下降',
    19: '校准中',
    20: '低电量返航',
    21: '限高限远',
    22: 'APAS',
    23: '跟随模式',
    24: '智能飞行',
    25: '航线飞行',
  }
  return modes[modeCode] || `模式${modeCode}`
}

/**
 * 解析档位代码
 * @param {number} gear
 * @returns {string}
 */
export function parseGear(gear) {
  const gears = {
    0: 'A', 1: 'P', 2: 'NAV', 3: 'FPV',
    4: 'FARM', 5: 'S', 6: 'F', 7: 'M',
    8: 'G', 9: 'T', 10: 'FARM_S',
  }
  return gears[gear] || '--'
}
