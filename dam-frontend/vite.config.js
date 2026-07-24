import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 9457,
    proxy: {
      '/api': {
        target: 'http://localhost:8090',  // Python 后端端口
        changeOrigin: true,
      },
      // DJI Cloud API 代理（dij 项目后端）
      '/dij-api': {
        target: 'http://127.0.0.1:6790',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/dij-api/, ''),
      },
      // dij WebSocket 代理
      '/dij-ws': {
        target: 'ws://127.0.0.1:6790',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/dij-ws/, '/api/v1/ws'),
      },
      // 无人机 WebRTC 代理（复用 dam-webrtc-streamer）
      '/drone-webrtc': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/drone-webrtc/, ''),
      },
      // MediaMTX WebRTC 代理（WHEP 协议，零转码低延迟）
      '/drone-mediamtx': {
        target: 'http://127.0.0.1:8890',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/drone-mediamtx/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // WHEP 需要 POST 方法和 SDP 内容类型
            if (req.method === 'POST') {
              proxyReq.setHeader('Content-Type', 'application/sdp')
            }
          })
        },
      },
      // OnlyOffice API 代理 - 解决跨域和端口访问问题
      '/onlyoffice': {
        target: 'http://localhost:80',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/onlyoffice/, ''),
      },
    },
  },
})
