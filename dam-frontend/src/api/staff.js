import request from '@/utils/request'

// 人员列表（含 online/offline 筛选）
export function getStaffList(params = {}) {
  return request.get('/miniprogram/v1/staff', {
    params,
    localCache: false,
  })
}

// 新增人员
export function createStaff(data) {
  return request.post('/miniprogram/v1/staff', data)
}

// 编辑人员
export function updateStaff(id, data) {
  return request.put(`/miniprogram/v1/staff/${id}`, data)
}

// 删除人员
export function deleteStaff(id) {
  return request.delete(`/miniprogram/v1/staff/${id}`)
}

// 启用 / 停用人员
export function updateStaffEnabled(id, enabled) {
  return request.put(`/miniprogram/v1/staff/${id}/enabled`, { enabled })
}

// 生成人员登录码（返回 { ticket, expires_at, qr_url }）
export function getStaffLoginCode(id) {
  return request.post(`/miniprogram/v1/staff/${id}/qrcode`)
}

// 登录码二维码图片地址（后端生成 PNG，<img> 直接引用）
export function staffQrCodeUrl(id, ticket) {
  return `/api/miniprogram/v1/staff/${id}/qrcode.png?ticket=${encodeURIComponent(ticket)}`
}
