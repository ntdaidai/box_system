/**
 * DJI Cloud API 接口层
 * 对接 /home/jetson/dij 后端服务
 */
import axios from 'axios'

// dij 后端独立 axios 实例（不走 box_system 的 /api 拦截器）
const dij = axios.create({
  baseURL: '/dij-api',
  timeout: 15000,
})

// 请求拦截：附加 dij token
dij.interceptors.request.use((config) => {
  const token = localStorage.getItem('dij_token')
  if (token) {
    config.headers['x-auth-token'] = token
  }
  return config
})

// 响应拦截
dij.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code !== 0) {
      return Promise.reject(new Error(res.message || 'dij 请求失败'))
    }
    return res
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('dij_token')
    }
    return Promise.reject(error)
  }
)

// ========== 认证 ==========

/**
 * dij 登录
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{token: string}>}
 */
export function dijLogin(username, password) {
  return dij.post('/manage/api/v1/login', {
    username,
    password,
    flag: 1, // 1=Web端
  })
}

// ========== 设备管理 ==========

/**
 * 获取工作空间内所有在线设备拓扑列表
 * @param {string} workspaceId
 */
export function getDroneDevices(workspaceId) {
  return dij.get(`/manage/api/v1/devices/${workspaceId}/devices`)
}

/**
 * 获取已绑定设备列表（分页）
 * @param {string} workspaceId
 * @param {object} params - { page, page_size, domain }
 */
export function getBoundDevices(workspaceId, params = {}) {
  return dij.get(`/manage/api/v1/devices/${workspaceId}/devices/bound`, { params })
}

/**
 * 获取单个设备信息
 * @param {string} workspaceId
 * @param {string} deviceSn
 */
export function getDeviceInfo(workspaceId, deviceSn) {
  return dij.get(`/manage/api/v1/devices/${workspaceId}/devices/${deviceSn}`)
}

/**
 * 获取设备 HMS 健康告警
 * @param {string} workspaceId
 * @param {object} params
 */
export function getDeviceHms(workspaceId, params = {}) {
  return dij.get(`/manage/api/v1/devices/${workspaceId}/devices/hms`, { params })
}

/**
 * 获取单个设备未读 HMS 消息
 * @param {string} workspaceId
 * @param {string} deviceSn
 */
export function getDeviceHmsDetail(workspaceId, deviceSn) {
  return dij.get(`/manage/api/v1/devices/${workspaceId}/devices/hms/${deviceSn}`)
}

// ========== 直播 ==========

/**
 * 获取所有无人机的直播能力
 */
export function getLiveCapacity() {
  return dij.get('/manage/api/v1/live/capacity')
}

/**
 * 开始推流
 * @param {object} data - LiveTypeDTO
 */
export function startLiveStream(data) {
  return dij.post('/manage/api/v1/live/streams/start', data)
}

/**
 * 停止推流
 * @param {object} data
 */
export function stopLiveStream(data) {
  return dij.post('/manage/api/v1/live/streams/stop', data)
}

/**
 * 切换直播镜头
 * @param {object} data
 */
export function switchLiveLens(data) {
  return dij.post('/manage/api/v1/live/streams/switch', data)
}

// ========== 飞行控制 ==========

/**
 * 获取飞行控制权
 * @param {string} sn - 设备 SN
 */
export function requestFlightAuthority(sn) {
  return dij.post(`/control/api/v1/devices/${sn}/authority/flight`)
}

/**
 * 飞向目标点
 * @param {string} sn
 * @param {object} data - { max_speed, points: [{latitude, longitude, height}] }
 */
export function flyToPoint(sn, data) {
  return dij.post(`/control/api/v1/devices/${sn}/jobs/fly-to-point`, data)
}

/**
 * 停止飞向目标点
 * @param {string} sn
 */
export function stopFlyToPoint(sn) {
  return dij.delete(`/control/api/v1/devices/${sn}/jobs/fly-to-point`)
}

/**
 * 一键起飞
 * @param {string} sn
 * @param {object} data
 */
export function takeoffToPoint(sn, data) {
  return dij.post(`/control/api/v1/devices/${sn}/jobs/takeoff-to-point`, data)
}

/**
 * 发送负载指令（拍照、录像等）
 * @param {string} sn
 * @param {object} data - PayloadCommandsBody
 */
export function sendPayloadCommand(sn, data) {
  return dij.post(`/control/api/v1/devices/${sn}/payload/commands`, data)
}

// ========== 工作空间 ==========

/**
 * 获取当前工作空间信息
 */
export function getCurrentWorkspace() {
  return dij.get('/manage/api/v1/workspaces/current')
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser() {
  return dij.get('/manage/api/v1/users/current')
}

// ========== 航线任务 ==========

/**
 * 获取飞行任务列表
 * @param {string} workspaceId
 * @param {object} params - { page, page_size }
 */
export function getFlightJobs(workspaceId, params = {}) {
  return dij.get(`/wayline/api/v1/workspaces/${workspaceId}/jobs`, { params })
}
