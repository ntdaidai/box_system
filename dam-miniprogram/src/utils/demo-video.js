import { DEMO_MONITOR_VIDEO } from './config'

const USER_VIDEO_NAME = 'fixed-monitor-video-8e9d32a7.mp4'
const EXPECTED_VIDEO_SIZE = 860756
let preparePromise = null

/**
 * 微信原生 video 不稳定支持代码包路径。首次使用时把包内 MP4 复制到
 * USER_DATA_PATH，后续统一返回可直接播放的 wxfile:// 用户文件路径。
 */
export function prepareDemoVideo() {
  if (preparePromise) return preparePromise

  preparePromise = new Promise((resolve, reject) => {
    if (typeof wx === 'undefined' || !wx.getFileSystemManager || !wx.env?.USER_DATA_PATH) {
      resolve(DEMO_MONITOR_VIDEO)
      return
    }

    const fs = wx.getFileSystemManager()
    const sourcePaths = [
      String(DEMO_MONITOR_VIDEO).replace(/^\//, ''),
      String(DEMO_MONITOR_VIDEO).startsWith('/') ? DEMO_MONITOR_VIDEO : `/${DEMO_MONITOR_VIDEO}`
    ]
    const targetPath = `${wx.env.USER_DATA_PATH}/${USER_VIDEO_NAME}`

    try {
      const targetStat = fs.statSync(targetPath)
      if (Number(targetStat.size) === EXPECTED_VIDEO_SIZE) {
        resolve(targetPath)
        return
      }
      fs.unlinkSync(targetPath)
    } catch (error) {
      // 首次运行继续执行代码包文件复制。
    }

    try {
      let videoData = null
      let lastReadError = null
      for (const sourcePath of sourcePaths) {
        try {
          videoData = fs.readFileSync(sourcePath)
          break
        } catch (error) {
          lastReadError = error
        }
      }
      if (!videoData) throw lastReadError || new Error('代码包内未找到监控录像')
      fs.writeFileSync(targetPath, videoData)
      resolve(targetPath)
    } catch (error) {
      preparePromise = null
      console.error('[demo-video] prepare failed', error)
      reject(new Error(error?.errMsg || '监控录像初始化失败'))
    }
  })

  return preparePromise
}
