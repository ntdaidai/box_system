import request from '@/utils/request'

export function getMiniProgramStaff(params = {}) {
  return request.get('/miniprogram/v1/staff', {
    params,
    localCache: false,
  })
}
