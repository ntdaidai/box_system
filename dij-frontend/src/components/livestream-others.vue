<template>
  <div class="flex-column flex-justify-start flex-align-center">
    <video
      :style="{ width: '720px', height: '480px' }"
      id="video-webrtc"
      ref="videowebrtc"
      controls
      autoplay
      class="mt20"
    ></video>
    <p class="fz24">Live streaming source selection</p>

    <div class="flex-row flex-justify-center flex-align-center mt10">
      <template v-if="liveState && isDockLive">
        <span class="mr10">Lens:</span>
        <a-radio-group v-model:value="lensSelected" button-style="solid">
          <a-radio-button v-for="lens in lensList" :key="lens" :value="lens">{{lens}}</a-radio-button>
        </a-radio-group>
      </template>
      <template v-else>
      <a-select
        class="ml10"
        style="width:150px"
        placeholder="Select Drone"
        v-model:value="droneSelected"
      >
        <a-select-option
          v-for="item in droneList"
          :key="item.value"
          :value="item.value"
          @click="onDroneSelect(item)"
          >{{ item.label }}</a-select-option
        >
      </a-select>
      <a-select
        class="ml10"
        style="width:150px"
        placeholder="Select Camera"
        v-model:value="cameraSelected"
      >
        <a-select-option
          v-for="item in cameraList"
          :key="item.value"
          :value="item.value"
          @click="onCameraSelect(item)"
          >{{ item.label }}</a-select-option
        >
      </a-select>
      <!-- <a-select
        class="ml10"
        style="width:150px"
        placeholder="Select Lens"
        v-model:value="videoSelected"
      >
        <a-select-option
          v-for="item in videoList"
          :key="item.value"
          :value="item.value"
          @click="onVideoSelect(item)"
          >{{ item.label }}</a-select-option
        >
      </a-select> -->
      </template>
      <a-select
        class="ml10"
        style="width:150px"
        placeholder="Select Clarity"
        @select="onClaritySelect"
        v-model:value="claritySelected"
      >
        <a-select-option
          v-for="item in clarityList"
          :key="item.value"
          :value="item.value"
          >{{ item.label }}</a-select-option
        >
      </a-select>
    </div>
    <div class="mt20">
    </div>
    <div class="mt10 flex-row flex-justify-center flex-align-center">
      <a-button v-if="liveState && isDockLive" type="primary" large @click="onSwitch">Switch Lens</a-button>
      <a-button v-else type="primary" large @click="onStart">Play</a-button>
      <a-button class="ml20" type="primary" large @click="onStop"
        >Stop</a-button
      >
      <a-button class="ml20" type="primary" large @click="onUpdateQuality"
        >Update Clarity</a-button
      >
      <a-button v-if="!liveState || !isDockLive" class="ml20" type="primary" large @click="onRefresh"
        >Refresh Live Capacity</a-button
      >
    </div>
  </div>
</template>

<script lang="ts" setup>
import { message } from 'ant-design-vue'
import { onMounted, reactive, ref } from 'vue'
import { CURRENT_CONFIG as config } from '/@/api/http/config'
import { changeLivestreamLens, getLiveCapacity, setLivestreamQuality, startLivestream, stopLivestream } from '/@/api/manage'
import { getRoot } from '/@/root'

const root = getRoot()

interface SelectOption {
  value: any,
  label: string,
  more?: any
}

const clarityList: SelectOption[] = [
  {
    value: 0,
    label: 'Adaptive'
  },
  {
    value: 1,
    label: 'Smooth'
  },
  {
    value: 2,
    label: 'Standard'
  },
  {
    value: 3,
    label: 'HD'
  },
  {
    value: 4,
    label: 'Super Clear'
  }
]

const videowebrtc = ref(null)
const livestreamSource = ref()
const droneList = ref()
const cameraList = ref()
const videoList = ref()
const droneSelected = ref()
const cameraSelected = ref()
const videoSelected = ref()
const claritySelected = ref(2) // 默认标清
const videoId = ref()
const liveState = ref<boolean>(false)
const livetypeSelected = ref(1) // 默认 RTMP
const lensList = ref<string[]>([])
const lensSelected = ref<String>()
const isDockLive = ref(false)
const nonSwitchable = 'normal'
let webrtc: any = null

const onRefresh = async () => {
  droneList.value = []
  cameraList.value = []
  videoList.value = []
  droneSelected.value = null
  cameraSelected.value = null
  videoSelected.value = null
  await getLiveCapacity({})
    .then(res => {
      console.log(res)
      if (res.code === 0) {
        if (res.data === null) {
          console.warn('warning: get live capacity is null!!!')
          return
        }
        const resData: Array<[]> = res.data
        console.log('live_capacity:', resData)
        livestreamSource.value = resData

        const temp: Array<SelectOption> = []
        if (livestreamSource.value) {
          livestreamSource.value.forEach((ele: any) => {
            temp.push({ label: ele.name + '-' + ele.sn, value: ele.sn, more: ele.cameras_list })
          })
          droneList.value = temp

          // 自动选择第一个无人机
          if (droneList.value.length === 1) {
            const firstDrone = droneList.value[0]
            droneSelected.value = firstDrone.value
            onDroneSelect(firstDrone)
          }
        }
      }
    })
    .catch(error => {
      message.error(error)
      console.error(error)
    })
}

onMounted(() => {
  onRefresh()
})
const onStart = async () => {
  console.log(
    'Param:',
    livetypeSelected.value,
    droneSelected.value,
    cameraSelected.value,
    videoSelected.value,
    claritySelected.value
  )
  const timestamp = new Date().getTime().toString()
  if (
    livetypeSelected.value == null ||
    droneSelected.value == null ||
    cameraSelected.value == null ||
    claritySelected.value == null
  ) {
    message.warn('waring: not select live para!!!')
    return
  }
  videoId.value =
    droneSelected.value + '/' + cameraSelected.value + '/' + (videoSelected.value || nonSwitchable + '-0')
  console.log('=== DEBUG videoId ===', JSON.stringify(videoId.value), typeof videoId.value)
  console.log('=== DEBUG droneSelected ===', JSON.stringify(droneSelected.value), typeof droneSelected.value)
  console.log('=== DEBUG cameraSelected ===', JSON.stringify(cameraSelected.value), typeof cameraSelected.value)
  console.log('=== DEBUG livetypeSelected ===', JSON.stringify(livetypeSelected.value), typeof livetypeSelected.value)
  console.log('=== DEBUG claritySelected ===', JSON.stringify(claritySelected.value), typeof claritySelected.value)

  // RTMP 直播
  const liveURL = config.rtmpURL + timestamp

  await startLivestream({
    video_id: videoId.value,
    url_type: 1, // 固定 RTMP
    video_quality: claritySelected.value
  })
    .then(res => {
      if (res.code !== 0) {
        return
      }
      const videoElement = videowebrtc.value
      console.log('start live:', videoElement)
      // 等待无人机开始推流（3秒延迟）
      message.loading({ content: 'Waiting for stream...', duration: 3 })
      setTimeout(() => {
        // 使用 WebRtcStreamer 播放 RTSP 流
        const rtspUrl = `rtsp://127.0.0.1:8555/live/${droneSelected.value}-88-0-0`
        playWithWebRTCStreamer(rtspUrl)
      }, 3000)
      liveState.value = true
    })
    .catch(err => {
      console.error(err)
    })
}
const onStop = () => {
  videoId.value =
    droneSelected.value + '/' + cameraSelected.value + '/' + (videoSelected.value || nonSwitchable + '-0')

  stopLivestream({
    video_id: videoId.value
  }).then(res => {
    if (res.code === 0) {
      message.success(res.message)
      liveState.value = false
      lensSelected.value = undefined
      console.log('stop play livestream')
    }
  })
}

const onUpdateQuality = () => {
  if (!liveState.value) {
    message.info('Please turn on the livestream first.')
    return
  }
  setLivestreamQuality({
    video_id: videoId.value,
    video_quality: claritySelected.value
  }).then(res => {
    if (res.code === 0) {
      message.success('Set the clarity to ' + clarityList[claritySelected.value].label)
    }
  })
}

const onDroneSelect = (val: SelectOption) => {
  droneSelected.value = val.value
  const temp: Array<SelectOption> = []
  cameraList.value = []
  cameraSelected.value = undefined
  videoSelected.value = undefined
  videoList.value = []
  lensList.value = []
  if (!val.more) {
    return
  }
  val.more.forEach((ele: any) => {
    temp.push({ label: ele.name, value: ele.index, more: ele.videos_list })
  })
  cameraList.value = temp

  // 自动选择第一个摄像头
  if (cameraList.value.length === 1) {
    const firstCamera = cameraList.value[0]
    cameraSelected.value = firstCamera.value
    onCameraSelect(firstCamera)
  }
}
const onCameraSelect = (val: SelectOption) => {
  cameraSelected.value = val.value
  const result: Array<SelectOption> = []
  videoSelected.value = undefined
  videoList.value = []
  lensList.value = []
  if (!val.more) {
    return
  }

  val.more.forEach((ele: any) => {
    result.push({ label: ele.type, value: ele.index, more: ele.switch_video_types })
  })
  videoList.value = result
  if (videoList.value.length === 0) {
    return
  }
  const firstVideo: SelectOption = videoList.value[0]
  videoSelected.value = firstVideo.value
  lensList.value = firstVideo.more
  lensSelected.value = firstVideo.label
  isDockLive.value = lensList.value?.length > 0
}
const onVideoSelect = (val: SelectOption) => {
  videoSelected.value = val.value
  lensList.value = val.more
  lensSelected.value = val.label
}
const onClaritySelect = (val: any) => {
  claritySelected.value = val
}
const onSwitch = () => {
  if (lensSelected.value === undefined || lensSelected.value === nonSwitchable) {
    message.info('The ' + nonSwitchable + ' lens cannot be switched, please select the lens to be switched.', 8)
    return
  }
  changeLivestreamLens({
    video_id: videoId.value,
    video_type: lensSelected.value
  }).then(res => {
    if (res.code === 0) {
      message.success('Switching live camera successfully.')
    }
  })
}

// 使用 WebRtcStreamer 播放 RTSP 流
const playWithWebRTCStreamer = (rtspUrl: string) => {
  const videoElement = videowebrtc.value
  if (!videoElement) return

  const webrtcBase = `${window.location.protocol}//${window.location.host}/webrtc`

  const connectWebrtc = () => {
    if (webrtc) {
      try { webrtc.disconnect() } catch (e) {}
    }
    webrtc = new (window as any).WebRtcStreamer(videoElement, webrtcBase)
    videoElement.muted = true
    videoElement.autoplay = true
    const options = 'rtptransport=tcp&timeout=5000'
    webrtc.connect(rtspUrl, null, options)
    videoElement.play().catch((err: any) => console.warn('播放被阻止:', err))
  }

  if (!(window as any).WebRtcStreamer) {
    const script = document.createElement('script')
    script.src = `${webrtcBase}/webrtcstreamer.js`
    script.onload = connectWebrtc
    document.body.appendChild(script)
  } else {
    connectWebrtc()
  }
}
</script>

<style lang="scss" scoped>
@import '/@/styles/index.scss';
</style>
