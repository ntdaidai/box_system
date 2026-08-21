import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'
import fs from 'fs'

const machineDogVideoPath = path.resolve(__dirname, 'dist/demo/mashiondag_walking.mp4')

function serveMachineDogVideo() {
  return {
    name: 'serve-machine-dog-video',
    configureServer(server) {
      server.middlewares.use('/demo/mashiondag_walking.mp4', (req, res, next) => {
        if (!['GET', 'HEAD'].includes(req.method) || !fs.existsSync(machineDogVideoPath)) {
          next()
          return
        }

        const size = fs.statSync(machineDogVideoPath).size
        const range = req.headers.range
        const match = range && range.match(/bytes=(\d*)-(\d*)/)
        let start = 0
        let end = size - 1

        if (match) {
          if (match[1]) start = Number(match[1])
          if (match[2]) end = Number(match[2])
          if (!match[1] && match[2]) start = Math.max(0, size - Number(match[2]))
          end = Math.min(end, size - 1)
          if (start > end || start >= size) {
            res.statusCode = 416
            res.setHeader('Content-Range', `bytes */${size}`)
            res.end()
            return
          }
          res.statusCode = 206
          res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
        } else {
          res.statusCode = 200
        }

        res.setHeader('Content-Type', 'video/mp4')
        res.setHeader('Accept-Ranges', 'bytes')
        res.setHeader('Content-Length', String(end - start + 1))
        res.setHeader('Cache-Control', 'no-cache')
        if (req.method === 'HEAD') {
          res.end()
          return
        }
        fs.createReadStream(machineDogVideoPath, { start, end }).pipe(res)
      })
    },
  }
}

export default defineConfig({
  cacheDir: process.env.VITE_CACHE_DIR || 'node_modules/.vite',
  plugins: [
    serveMachineDogVideo(),
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
        ws: true,
        configure: (proxy) => {
          // Preserve the browser-facing host for generated OnlyOffice file URLs.
          proxy.on('proxyReq', (proxyReq, req) => {
            if (req.headers.host) proxyReq.setHeader('X-Forwarded-Host', req.headers.host)
            if (req.headers['x-forwarded-proto']) {
              proxyReq.setHeader('X-Forwarded-Proto', req.headers['x-forwarded-proto'])
            } else {
              proxyReq.setHeader('X-Forwarded-Proto', 'http')
            }
          })
        },
      },
      // DJI Cloud API 代理（dij 项目后端，Docker 映射 6790->6789）
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
        target: 'http://127.0.0.1:80',
        changeOrigin: true,
        ws: true,
        secure: false,
        timeout: 120000,
        proxyTimeout: 120000,
        rewrite: (path) => path.replace(/^\/onlyoffice/, ''),
      },
    },
  },
  // 部署目录中包含机器狗测试视频等外部静态资源，构建时不要清空 dist。
  build: {
    emptyOutDir: false,
  },
})
