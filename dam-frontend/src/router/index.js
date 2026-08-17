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
        path: 'overview-camera-region-annotator',
        name: 'OverviewCameraRegionAnnotator',
        component: () => import('@/views/OverviewCameraRegionAnnotator.vue'),
        meta: { title: '2号摄像头区域标注' }
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
            meta: { title: '感知源管理', hideBreadcrumbBar: true }
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
            redirect: '/system/linkage/drone',
            meta: { title: '无人机设备' }
          },
          {
            path: 'device',
            name: 'DeviceStatus',
            component: () => import('@/views/Monitor/DeviceStatus.vue'),
            meta: { title: '设备状态' }
          },
        ],
      },
      // ========== 旧告警路由兼容重定向 ==========
      {
        path: 'alarm',
        redirect: '/workspace/safety-events',
        meta: {},
        children: [
          {
            path: 'list',
            redirect: '/workspace/safety-events',
            meta: {}
          },
          {
            path: 'safety-events',
            redirect: '/workspace/safety-events',
            meta: { title: '告警管理' }
          },
          {
            path: 'safety-events/:id',
            redirect: (to) => ({ path: `/workspace/safety-events/${to.params.id}` }),
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
            component: () => import('@/views/Monitor/DeviceManagement.vue'),
            meta: { title: '感知源管理', hideBreadcrumbBar: true }
          },
          {
            path: 'devices/cameras',
            redirect: '/system/devices',
            meta: { title: '感知源管理' }
          },
          {
            path: 'video-detection',
            name: 'SystemVideoDetection',
            component: () => import('@/views/System/VideoDetection.vue'),
            meta: { title: '视频测试', hideBreadcrumbBar: true }
          },
          {
            path: 'sensor-event-test',
            name: 'SystemSensorEventTest',
            component: () => import('@/views/System/SensorEventTest.vue'),
            meta: { title: '传感器测试', hideBreadcrumbBar: true }
          },
          {
            path: 'config',
            name: 'SystemInformationConfig',
            redirect: '/system/rules/events',
            meta: { title: '规则管理' }
          },
          {
            path: 'rules',
            redirect: '/system/rules/events',
            meta: { title: '规则管理' }
          },
          {
            path: 'rules/events',
            name: 'SystemRuleEvents',
            component: () => import('@/views/System/EventConfig.vue'),
            meta: { title: '事件配置' }
          },
          {
            path: 'rules/actions',
            name: 'SystemRuleActions',
            redirect: '/system/rules/events?focus=flow',
            meta: { title: '事件配置' }
          },
          {
            path: 'rules/zones',
            name: 'SystemRuleZones',
            component: () => import('@/views/Monitor/ZoneConfig.vue'),
            meta: { title: '区域配置' }
          },
          {
            path: 'linkage',
            redirect: '/system/linkage/broadcast',
            meta: { title: '联动系统' }
          },
          {
            path: 'linkage/events',
            name: 'SystemLinkageEvents',
            redirect: '/system/rules/events',
            meta: { title: '事件配置' }
          },
          {
            path: 'linkage/actions',
            name: 'SystemLinkageActions',
            redirect: '/system/rules/events?focus=flow',
            meta: { title: '事件配置' }
          },
          {
            path: 'linkage/zones',
            name: 'SystemLinkageZones',
            redirect: '/system/rules/zones',
            meta: { title: '区域配置' }
          },
          {
            path: 'linkage/broadcast',
            name: 'SystemLinkageBroadcast',
            component: () => import('@/views/System/LinkageManagement.vue'),
            meta: { title: '广播设备', linkageModule: 'devices' }
          },
          {
            path: 'linkage/devices',
            name: 'SystemLinkageDevices',
            redirect: '/system/linkage/broadcast',
            meta: { title: '广播设备', linkageModule: 'devices' }
          },
          {
            path: 'linkage/rules',
            name: 'SystemLinkageRules',
            redirect: '/system/rules/events?focus=flow',
            meta: { title: '事件配置' }
          },
          {
            path: 'linkage/drone',
            name: 'SystemLinkageDroneView',
            component: () => import('@/views/System/DroneLinkage.vue'),
            meta: { title: '无人机设备' }
          },
          {
            path: 'linkage/machine-dog',
            name: 'SystemLinkageMachineDog',
            component: () => import('@/views/System/MachineDogDevice.vue'),
            meta: { title: '机器狗设备' }
          },
          {
            path: 'linkage/staff',
            name: 'SystemLinkageStaff',
            component: () => import('@/views/System/StaffManagement.vue'),
            meta: { title: '现场人员管理' }
          },
          {
            path: 'drone',
            name: 'SystemDroneViewRedirect',
            redirect: '/system/linkage/drone',
            meta: { title: '无人机设备' }
          },
          {
            path: 'models',
            name: 'SystemModelManagement',
            component: () => import('@/views/System/ModelManagement.vue'),
            meta: { title: '模型管理' }
          },
        ],
      },
      // ========== 业务管理（告警 + 数据） ==========
      {
        path: 'workspace',
        redirect: '/workspace/safety-events',
        meta: { title: '业务管理' },
        component: () => import('@/views/Workspace.vue'),
        children: [
          {
            path: 'safety-events',
            name: 'AlarmSafetyEvents',
            component: () => import('@/views/Alarm/SafetyEvents.vue'),
            meta: { title: '告警管理' }
          },
          {
            path: 'safety-events/:id',
            name: 'AlarmSafetyEventDetail',
            component: () => import('@/views/Alarm/SafetyEventDetail.vue'),
            meta: { title: '安全事件详情' }
          },
          {
            path: 'documents',
            name: 'DocumentHub',
            component: () => import('@/views/DocumentHub.vue'),
            meta: { title: '报告管理' }
          },
          {
            path: 'knowledge',
            name: 'KnowledgeBase',
            component: () => import('@/views/KnowledgeBase.vue'),
            meta: { title: '知识库' }
          },
          {
            path: 'editor/:documentId',
            name: 'DocumentEditor',
            component: () => import('@/views/DocumentEditor.vue'),
            meta: { title: '文档编辑' }
          },
        ],
      },
      // ========== 旧数据路由兼容重定向 ==========
      {
        path: 'document',
        redirect: '/workspace/documents',
        meta: { title: '数据管理' },
        children: [
          {
            path: 'hub',
            redirect: '/workspace/documents',
            meta: { title: '报告管理' }
          },
          {
            path: 'knowledge',
            redirect: '/workspace/knowledge',
            meta: { title: '知识库' }
          },
          {
            path: 'upload',
            redirect: '/workspace/documents',
            meta: { title: '文档上传' }
          },
          {
            path: 'list',
            redirect: '/workspace/documents',
            meta: { title: '文档列表' }
          },
          {
            path: 'test',
            redirect: '/workspace/documents',
            meta: { title: '文档测试' }
          },
          {
            path: 'editor/:documentId',
            redirect: (to) => ({ path: `/workspace/editor/${to.params.documentId}` }),
            meta: { title: '文档编辑' }
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
