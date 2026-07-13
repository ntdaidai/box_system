/**
 * WebSocket 封装
 */
class WebSocketClient {
  constructor(url) {
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectInterval = 3000
    this.handlers = new Map()
  }

  connect() {
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      console.log('WebSocket 连接成功')
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const handler = this.handlers.get(data.type)
        if (handler) {
          handler(data)
        }
      } catch (e) {
        console.error('WebSocket 消息解析失败:', e)
      }
    }

    this.ws.onclose = () => {
      console.log('WebSocket 连接关闭')
      this.reconnect()
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
    }
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`WebSocket 重连中... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
      setTimeout(() => this.connect(), this.reconnectInterval)
    }
  }

  on(type, handler) {
    this.handlers.set(type, handler)
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  close() {
    if (this.ws) {
      this.ws.close()
    }
  }
}

export default WebSocketClient
