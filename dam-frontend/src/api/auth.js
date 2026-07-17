// dai
/** Authentication API used by the direct-link login flow. */
import request from '@/utils/request'

export function login(username, password) {
  return request.post('/auth/login', { username, password }, { timeout: 15000 })
}
