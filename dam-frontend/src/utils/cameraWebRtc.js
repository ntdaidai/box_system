// Authenticated WebRTC player for mpromonet/webrtc-streamer. All signaling is
// proxied by the Python API, so RTSP credentials never enter browser state.

import {
  addWebRtcIceCandidate,
  closeWebRtcSession,
  createWebRtcSession,
  getWebRtcIceCandidates,
  getWebRtcIceConfig,
} from '@/api/camera'

export function createWebRtcPeerId() {
  const uuid = globalThis.crypto?.randomUUID?.()
  if (uuid) return `dam-${uuid}`
  return `dam-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export class CameraWebRtcPlayer {
  constructor(videoElement, cameraId, handlers = {}) {
    this.videoElement = videoElement
    this.cameraId = cameraId
    this.handlers = handlers
    this.peerConnection = null
    this.peerId = ''
    this.remoteDescriptionReady = false
    this.earlyCandidates = []
    this.remoteCandidateKeys = new Set()
    this.generation = 0
    this.closed = true
    this.failed = false
    this.connectionTimer = null
    this.disconnectTimer = null
  }

  async connect() {
    if (!this.videoElement) throw new Error('WebRTC video element is missing')
    if (typeof RTCPeerConnection === 'undefined') throw new Error('当前浏览器不支持 WebRTC')

    this.close(false)
    this.closed = false
    this.failed = false
    const generation = ++this.generation
    this.peerId = createWebRtcPeerId()
    this.handlers.onState?.('connecting')

    try {
      const iceResponse = await getWebRtcIceConfig(this.cameraId)
      if (!this._isCurrent(generation)) return

      const pc = new RTCPeerConnection(iceResponse.data || { iceServers: [] })
      this.peerConnection = pc
      this._configurePeerConnection(pc, generation)
      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      const sessionResponse = await createWebRtcSession(
        this.cameraId,
        this.peerId,
        { type: offer.type, sdp: offer.sdp },
      )
      if (!this._isCurrent(generation)) return

      const answer = sessionResponse.data?.answer
      if (!answer?.type || !answer?.sdp) throw new Error('WebRTC 服务未返回有效 SDP')
      await pc.setRemoteDescription(answer)
      this.remoteDescriptionReady = true

      const pending = this.earlyCandidates.splice(0)
      await Promise.allSettled(pending.map((candidate) => this._sendCandidate(candidate, generation)))
      this._pollRemoteCandidates(generation)
      this.connectionTimer = setTimeout(() => {
        if (this._isCurrent(generation) && !['connected', 'completed'].includes(pc.iceConnectionState)) {
          this._fail(new Error('WebRTC 媒体连接超时'))
        }
      }, 12000)
    } catch (error) {
      if (this._isCurrent(generation)) this._fail(error)
      throw error
    }
  }

  _configurePeerConnection(pc, generation) {
    pc.ontrack = (event) => {
      if (!this._isCurrent(generation)) return
      if (event.streams?.[0]) {
        this._attachStream(event.streams[0])
      } else {
        const stream = this.videoElement.srcObject instanceof MediaStream
          ? this.videoElement.srcObject
          : new MediaStream()
        stream.addTrack(event.track)
        this._attachStream(stream)
      }
    }
    // Compatibility with the version bundled in the supplied image.
    pc.onaddstream = (event) => {
      if (this._isCurrent(generation)) this._attachStream(event.stream)
    }
    pc.onicecandidate = (event) => {
      if (!event.candidate || !this._isCurrent(generation)) return
      const candidate = event.candidate.toJSON?.() || event.candidate
      if (this.remoteDescriptionReady) this._sendCandidate(candidate, generation).catch(() => null)
      else this.earlyCandidates.push(candidate)
    }
    pc.oniceconnectionstatechange = () => {
      if (!this._isCurrent(generation)) return
      const state = pc.iceConnectionState
      this.handlers.onState?.(state)
      if (['connected', 'completed'].includes(state)) {
        clearTimeout(this.connectionTimer)
        clearTimeout(this.disconnectTimer)
        this.handlers.onConnected?.()
      } else if (state === 'failed') {
        this._fail(new Error('WebRTC ICE 连接失败'))
      } else if (state === 'disconnected') {
        clearTimeout(this.disconnectTimer)
        this.disconnectTimer = setTimeout(() => {
          if (this._isCurrent(generation) && pc.iceConnectionState === 'disconnected') {
            this._fail(new Error('WebRTC 媒体连接已断开'))
          }
        }, 2500)
      }
    }
  }

  _attachStream(stream) {
    this.videoElement.srcObject = stream
    const playPromise = this.videoElement.play()
    playPromise?.catch(() => {
      this.videoElement.controls = true
    })
  }

  async _sendCandidate(candidate, generation) {
    if (!this._isCurrent(generation)) return
    await addWebRtcIceCandidate(this.cameraId, this.peerId, candidate)
  }

  async _pollRemoteCandidates(generation) {
    const delays = [0, 150, 350, 700, 1200, 2000]
    for (const delay of delays) {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay))
      if (!this._isCurrent(generation)) return
      if (['connected', 'completed'].includes(this.peerConnection?.iceConnectionState)) return
      try {
        const response = await getWebRtcIceCandidates(this.cameraId, this.peerId)
        const candidates = response.data?.candidates || []
        for (const candidate of candidates) {
          const key = `${candidate.candidate}|${candidate.sdpMid}|${candidate.sdpMLineIndex}`
          if (this.remoteCandidateKeys.has(key)) continue
          this.remoteCandidateKeys.add(key)
          await this.peerConnection?.addIceCandidate(candidate)
        }
      } catch {
        // A later poll may still succeed while the gateway gathers candidates.
      }
    }
  }

  _fail(error) {
    if (this.failed || this.closed) return
    this.failed = true
    this.handlers.onError?.(error instanceof Error ? error : new Error(String(error)))
  }

  _isCurrent(generation) {
    return !this.closed && generation === this.generation
  }

  close(signalGateway = true) {
    const cameraId = this.cameraId
    const peerId = this.peerId
    this.closed = true
    this.generation += 1
    clearTimeout(this.connectionTimer)
    clearTimeout(this.disconnectTimer)
    this.connectionTimer = null
    this.disconnectTimer = null
    this.earlyCandidates = []
    this.remoteCandidateKeys.clear()
    this.remoteDescriptionReady = false

    const pc = this.peerConnection
    this.peerConnection = null
    if (pc) {
      pc.ontrack = null
      pc.onaddstream = null
      pc.onicecandidate = null
      pc.oniceconnectionstatechange = null
      try { pc.close() } catch { /* already closed */ }
    }
    const stream = this.videoElement?.srcObject
    stream?.getTracks?.().forEach((track) => track.stop())
    if (this.videoElement) this.videoElement.srcObject = null
    if (signalGateway && peerId) closeWebRtcSession(cameraId, peerId).catch(() => null)
    this.peerId = ''
    this.handlers.onState?.('closed')
  }
}

