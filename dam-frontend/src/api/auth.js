/**
 * Python 后端认证接口
 */
import request from '@/utils/request'

/**
 * 静默登录（自动获取 token）
 * @param {string} username
 * @param {string} password
 */
export function silentLogin(username = 'admin', password = 'hhu@4208') {
  return request.post('/auth/login', { username, password })
}
