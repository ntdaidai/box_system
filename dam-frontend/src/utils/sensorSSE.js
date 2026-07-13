/**
 * 传感器数据 SSE (Server-Sent Events) 客户端
 * 用于实时接收传感器数据推送
 */
class SensorSSE {
  /**
   * @param {string} url - SSE 端点
   */
  constructor(url) {
    this.url = url
    this.eventSource = null
    this.handlers = new Map()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectInterval = 3000
    this._closed = false
  }

  /**
   * 连接 SSE
   */
  connect() {
    if (this.eventSource) {
      this.eventSource.close()
    }

    this._closed = false
    this.eventSource = new EventSource(this.url)

    this.eventSource.onopen = () => {
      console.log('SSE 连接成功')
      this.reconnectAttempts = 0
    }

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const handler = this.handlers.get(data.type)
        if (handler) {
          handler(data)
        }
      } catch (e) {
        console.error('SSE 数据解析失败:', e)
      }
    }

    this.eventSource.onerror = (error) => {
      console.error('SSE 连接错误:', error)
      // 如果连接已关闭，不重连
      if (this._closed) return
      this.reconnect()
    }
  }

  /**
   * 重连
   */
  reconnect() {
    if (this._closed) return
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`SSE 重连中... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
      setTimeout(() => {
        if (!this._closed) {
          this.connect()
        }
      }, this.reconnectInterval)
    } else {
      console.error('SSE 重连次数已达上限，停止重连')
    }
  }

  /**
   * 注册事件处理器
   * @param {string} type - 事件类型
   * @param {Function} handler - 处理函数
   */
  on(type, handler) {
    this.handlers.set(type, handler)
  }

  /**
   * 关闭连接
   */
  close() {
    this._closed = true
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }
}

export default SensorSSE
