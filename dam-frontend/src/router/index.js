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
            meta: { title: '视频监控' }
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
