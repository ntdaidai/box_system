import { request } from './request'

export const RISK_ALERT_TEMPLATE_ID = '5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA'

function login() {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success(res) {
        if (!res.code) {
          reject(new Error('微信登录失败'))
          return
        }
        request({
          url: '/auth/login',
          method: 'POST',
          data: { code: res.code }
        })
          .then((data) => {
            if (data.openid) {
              uni.setStorageSync('mini_openid', data.openid)
            }
            resolve(data.openid)
          })
          .catch(reject)
      },
      fail(err) {
        reject(new Error(err.errMsg || '微信登录失败'))
      }
    })
  })
}

function requestPermission() {
  return new Promise((resolve) => {
    uni.requestSubscribeMessage({
      tmplIds: [RISK_ALERT_TEMPLATE_ID],
      success(res) {
        const state = res[RISK_ALERT_TEMPLATE_ID]
        resolve(state === 'accept' || state === 'acceptWithAudio')
      },
      fail() {
        resolve(false)
      }
    })
  })
}

export async function subscribeRiskAlert(eventId) {
  const accepted = await requestPermission()
  if (!accepted) {
    throw new Error('未开启服务通知，暂时无法接收风险提醒')
  }
  const openid = await login()
  if (!openid) {
    throw new Error('未获取到微信用户标识')
  }
  return request({
    url: '/notifications/subscribe',
    method: 'POST',
    data: {
      openid,
      template_id: RISK_ALERT_TEMPLATE_ID,
      event_id: eventId || undefined,
      scope: eventId ? 'event' : 'risk_alerts'
    }
  })
}

export const subscribeHighEvent = subscribeRiskAlert
