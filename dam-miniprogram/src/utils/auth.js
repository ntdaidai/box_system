import { readCache, writeCache } from './cache'
import { request } from './request'

const TOKEN_KEY = 'mini-token'
const STAFF_KEY = 'mini-staff'

export function getToken() {
  return readCache(TOKEN_KEY, '')
}

export function setToken(token) {
  writeCache(TOKEN_KEY, token || '')
}

export function getStaff() {
  return readCache(STAFF_KEY, null)
}

export function setStaff(staff) {
  writeCache(STAFF_KEY, staff || null)
}

export function isLoggedIn() {
  return Boolean(getToken() && getStaff()?.staff_id)
}

export function logout() {
  setToken('')
  setStaff(null)
}

/**
 * 解析扫码结果中的登录码 ticket。
 * 二维码内容格式：damqrlogin://login?ticket=<ticket>
 */
export function parseTicket(qrText) {
  const match = String(qrText || '').match(/[?&]ticket=([A-Za-z0-9_-]+)/)
  return match ? match[1] : String(qrText || '').trim()
}

/**
 * 扫码登录：扫管理员提供的登录码 → uni.login 换 code → 兑换长期 token。
 * 登录后长期有效，除非该人员被管理员删除。
 */
export function scanQrLogin() {
  return new Promise((resolve, reject) => {
    uni.scanCode({
      success: async (res) => {
        try {
          const ticket = parseTicket(res.result)
          const code = await new Promise((ok, no) => {
            uni.login({
              provider: 'weixin',
              success: (r) => ok(r.code),
              fail: no,
            })
          })
          const data = await request({
            url: '/auth/qr-login',
            method: 'POST',
            data: { ticket, code },
          })
          setToken(data.token)
          setStaff(data.staff)
          try {
            uni.setStorageSync('mini_openid', data.staff?.openid || '')
          } catch (error) {
            // 忽略存储失败
          }
          resolve(data.staff)
        } catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}
