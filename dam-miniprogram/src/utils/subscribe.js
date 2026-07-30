import { request } from './request'

const HIGH_EVENT_TEMPLATE_ID = ''

export function subscribeHighEvent(eventId) {
  if (!HIGH_EVENT_TEMPLATE_ID) {
    return request({
      url: '/notifications/mock-subscribe',
      method: 'POST',
      data: {
        event_id: eventId,
        template_id: 'MOCK_HIGH_EVENT'
      }
    })
  }

  return new Promise((resolve) => {
    uni.requestSubscribeMessage({
      tmplIds: [HIGH_EVENT_TEMPLATE_ID],
      complete() {
        resolve(request({
          url: '/notifications/mock-subscribe',
          method: 'POST',
          data: {
            event_id: eventId,
            template_id: HIGH_EVENT_TEMPLATE_ID
          }
        }))
      }
    })
  })
}
