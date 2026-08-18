// 统一主机地址：由 docker-compose 注入 VITE_PUBLIC_HOST（来源于 .env 的 PUBLIC_HOST）。
// 换网络 / 改 IP 时只需修改 box_system/.env 里的 PUBLIC_HOST，然后重建容器即可。
const PUBLIC_HOST = import.meta.env.VITE_PUBLIC_HOST || '192.168.31.52'

export const CURRENT_CONFIG = {

  // license
  appId: '190692', // DJI Cloud API App ID
  appKey: '37268bf4705405690a68390d5252369', // DJI Cloud API App Key
  appLicense: 'q1jbHkoD+xy3X2nLtcmANbkEqDl67j1VsAfPPsiRRT2TD8F9z5jrQ9bLE/ziKqfTTx2mY5AhjGgTSv5SajyUiiE2tR8WfN8lkqI8THre2DaNZgLOYyH7nFh9cawhJ5bwFGb+YvXufcus0OqwqfOY06mmsJHx6ZtDBwiRqKDPVaw=', // DJI Cloud API App License

  // http
  baseURL: `http://${PUBLIC_HOST}:6790`, // 后端服务地址（宿主机 IP + 映射端口，不要尾部斜杠）
  websocketURL: `ws://${PUBLIC_HOST}:6790/api/v1/ws`, // WebSocket 地址

  // livestreaming
  // RTMP  Note: This IP is the address of the streaming server. If you want to see livestream on web page, you need to convert the RTMP stream to WebRTC stream.
  rtmpURL: `rtmp://${PUBLIC_HOST}:1936/live/`, // RTMP 推流地址
  // GB28181 Note:If you don't know what these parameters mean, you can go to Pilot2 and select the GB28181 page in the cloud platform. Where the parameters same as these parameters.
  gbServerIp: 'Please enter the server ip.',
  gbServerPort: 'Please enter the server port.',
  gbServerId: 'Please enter the server id.',
  gbAgentId: 'Please enter the agent id',
  gbPassword: 'Please enter the agent password',
  gbAgentPort: 'Please enter the local port.',
  gbAgentChannel: 'Please enter the channel.',
  // RTSP
  rtspUserName: '',
  rtspPassword: '',
  rtspPort: '8554',
  // Agora
  agoraAPPID: 'Please enter the agora app id.',
  agoraToken: 'Please enter the agora temporary token.',
  agoraChannel: 'Please enter the agora channel.',

  // map
  // You can apply on the AMap website.
  amapKey: 'Please enter the amap key.',

}
