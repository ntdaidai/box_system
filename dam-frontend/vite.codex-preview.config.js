import { mergeConfig } from 'vite'
import baseConfig from './vite.config.js'

export default mergeConfig(baseConfig, {
  cacheDir: '/tmp/dam-frontend-vite-cache'
})
