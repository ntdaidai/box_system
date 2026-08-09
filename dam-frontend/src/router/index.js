import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard/index.vue'),
        meta: { title: '综合态势' }
      },
      {
        path: 'overview-bigscreen-preview',
        name: 'OverviewBigScreenPreview',
        component: () => import('@/views/OverviewBigScreenPreview.vue'),
        meta: { title: '总览页数字大屏预览' }
      },
      // ========== 实时监控模块 ==========
      {
        path: 'monitor',
        redirect: '/monitor/overview',
        meta: { title: '感知监测' },
        children: [
          {
            path: 'system',
            name: 'SystemMonitor',
            component: () => import('@/views/Monitor/SystemMonitor.vue'),
            meta: { title: '系统监测' }
          },
          {
            path: 'overview',
            name: 'MonitorOverview',
            component: () => import('@/views/Monitor/Overview.vue'),
            meta: { title: '监控总览' }
          },
          {
            path: 'sensors',
            name: 'SensorUnified',
            component: () => import('@/views/Monitor/SensorUnified.vue'),
            meta: { title: '综合传感器' }
          },
          {
            path: 'temp',
            name: 'SensorTemp',
            component: () => import('@/views/Monitor/SensorTemp.vue'),
            meta: { title: '温湿度传感器' }
          },
          {
            path: 'wind',
            name: 'SensorWind',
            component: () => import('@/views/Monitor/SensorWind.vue'),
            meta: { title: '风速风向传感器' }
          },
          {
            path: 'rain',
            name: 'SensorRain',
            component: () => import('@/views/Monitor/SensorRain.vue'),
            meta: { title: '雨量计' }
          },
          {
            path: 'vibration',
            name: 'SensorVibration',
            component: () => import('@/views/Monitor/SensorVibration.vue'),
            meta: { title: '振动传感器' }
          },
          {
            path: 'config',
            name: 'MonitorInformationConfig',
            component: () => import('@/views/Monitor/InformationConfig.vue'),
            meta: { title: '联动规则' }
          },
          {
            path: 'camera',
            name: 'CameraView',
            component: () => import('@/views/Monitor/CameraView.vue'),
            meta: { title: '视频监控' }
          },
          {
            path: 'camera/devices',
            name: 'CameraDeviceManagement',
            component: () => import('@/views/Monitor/DeviceManagement.vue'),
            meta: { title: '数据源管理' }
          },
          {
            path: 'camera/zones',
            name: 'CameraZoneConfig',
            redirect: '/monitor/camera',
            meta: { title: '区域配置' }
          },
          {
            path: 'camera/image',
            name: 'CameraImageAnalysis',
            redirect: '/system/video-detection',
            meta: { title: '视频检测' }
          },
          {
            path: 'camera/video',
            name: 'CameraVideoAnalysis',
            redirect: '/system/video-detection',
            meta: { title: '视频检测' }
          },
          {
            path: 'drone',
            name: 'MonitorDroneRedirect',
            redirect: '/system/drone',
            meta: { title: '无人机监测' }
          },
          {
            path: 'device',
            name: 'DeviceStatus',
            component: () => import('@/views/Monitor/DeviceStatus.vue'),
            meta: { title: '设备状态' }
          },
        ],
      },
      // ========== 告警管理 ==========
      {
        path: 'alarm',
        redirect: '/alarm/safety-events',
        meta: {},
        children: [
          {
            path: 'list',
            name: 'AlarmListRedirect',
            redirect: '/alarm/safety-events',
            meta: {}
          },
          {
            path: 'safety-events',
            name: 'AlarmSafetyEvents',
            component: () => import('@/views/Alarm/SafetyEvents.vue'),
            meta: { title: '告警管理' }
          },
          {
            path: 'safety-events/:id',
            name: 'AlarmSafetyEventDetail',
            redirect: (to) => ({
              path: '/alarm/safety-events',
              query: { eventId: to.params.id },
            }),
            meta: { title: '安全事件详情' }
          },
        ],
      },
      // ========== 系统管理 ==========
      {
        path: 'system',
        redirect: '/system/devices',
        meta: { title: '系统管理' },
        children: [
          {
            path: 'devices',
            name: 'SystemDeviceManagement',
            component: () => import('@/views/Monitor/DeviceManagement.vue'),
            meta: { title: '数据源管理' }
          },
          {
            path: 'video-detection',
            name: 'SystemVideoDetection',
            component: () => import('@/views/System/VideoDetection.vue'),
            meta: { title: '视频检测' }
          },
          {
            path: 'config',
            name: 'SystemInformationConfig',
            redirect: '/system/linkage',
            meta: { title: '联动系统' }
          },
          {
            path: 'linkage',
            name: 'SystemLinkageManagement',
            component: () => import('@/views/System/LinkageManagement.vue'),
            meta: { title: '联动系统' }
          },
          {
            path: 'drone',
            name: 'SystemDroneView',
            component: () => import('@/views/Monitor/DroneView.vue'),
            meta: { title: '无人机监测' }
          },
          {
            path: 'models',
            name: 'SystemModelManagement',
            component: () => import('@/views/System/ModelManagement.vue'),
            meta: { title: '模型管理' }
          },
        ],
      },
      // ========== 数据管理 ==========
      {
        path: 'document',
        redirect: '/document/hub',
        meta: { title: '数据管理' },
        children: [
          {
            path: 'hub',
            name: 'DocumentHub',
            component: () => import('@/views/DocumentHub.vue'),
            meta: { title: '文档管理' }
          },
          {
            path: 'knowledge',
            name: 'KnowledgeBase',
            component: () => import('@/views/KnowledgeBase.vue'),
            meta: { title: '知识库' }
          },
          {
            path: 'upload',
            name: 'DocumentUpload',
            redirect: '/document/hub',
            meta: { title: '文档上传' }
          },
          {
            path: 'list',
            name: 'DocumentList',
            redirect: '/document/hub',
            meta: { title: '文档列表' }
          },
          {
            path: 'editor/:documentId',
            name: 'DocumentEditor',
            component: () => import('@/views/DocumentEditor.vue'),
            meta: { title: '文档编辑' }
          },
          {
            path: 'test',
            name: 'DocumentTest',
            redirect: '/document/hub',
            meta: { title: '文档测试' }
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
