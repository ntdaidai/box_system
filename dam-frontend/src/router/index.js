import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // dai: Camera and upload APIs are authenticated. A dedicated login route
  // prevents direct links from rendering a page full of raw HTTP 401 errors.
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login/index.vue'),
    meta: { title: '用户登录' },
  },
  {
    path: '/',
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard/index.vue'),
        meta: { title: '系统概览' }
      },
      // ========== 实时监控模块 ==========
      {
        path: 'monitor',
        redirect: '/monitor/overview',
        meta: { title: '实时监控' },
        children: [
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
            path: 'camera',
            name: 'CameraView',
            component: () => import('@/views/Monitor/CameraView.vue'),
            meta: { title: '视频监控', requiresAuth: true }
          },
          {
            path: 'camera/image',
            name: 'CameraImageAnalysis',
            component: () => import('@/views/Monitor/CameraView.vue'),
            meta: { title: '图片/视频分析', requiresAuth: true, mediaTab: 'image' }
          },
          {
            path: 'camera/video',
            name: 'CameraVideoAnalysis',
            component: () => import('@/views/Monitor/CameraView.vue'),
            meta: { title: '视频分析', requiresAuth: true, mediaTab: 'video' }
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
        redirect: '/alarm/list',
        meta: { title: '告警管理' },
        children: [
          {
            path: 'list',
            name: 'AlarmList',
            component: () => import('@/views/Alarm/AlarmList.vue'),
            meta: {}
          },
          {
            path: 'config',
            name: 'AlarmConfig',
            component: () => import('@/views/Alarm/AlarmConfig.vue'),
            meta: { title: '告警配置' }
          },
        ],
      },
      // ========== 规则配置 ==========
      {
        path: 'rule',
        name: 'RuleConfig',
        component: () => import('@/views/Rule/RuleConfig.vue'),
        meta: { title: '规则配置' }
      },
      // ========== 文档管理 ==========
      {
        path: 'document',
        redirect: '/document/hub',
        meta: { title: '文档管理' },
        children: [
          {
            path: 'hub',
            name: 'DocumentHub',
            component: () => import('@/views/DocumentHub.vue'),
            meta: { title: '文档中心' }
          },
          {
            path: 'upload',
            name: 'DocumentUpload',
            component: () => import('@/views/DocumentUpload.vue'),
            meta: { title: '文档上传' }
          },
          {
            path: 'list',
            name: 'DocumentList',
            component: () => import('@/views/DocumentManagement.vue'),
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
            component: () => import('@/views/DocumentTest.vue'),
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

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && token) {
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/dashboard'
    return redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/dashboard'
  }
  return true
})

export default router
