<template>
  <div class="indexBox" :class="{ 'dashboard-shell': isDashboard }">
    <!-- 顶栏 -->
    <header class="headBox row">
      <div class="logo fl">库坝应急巡查智能感知系统</div>
      <div class="flexBox fr">
        <ul class="menu flexBox">
          <li class="flexBox"
              v-for="(item, idx) in navList"
              :class="{ active: currentNav === item.path }"
              :key="item.path"
              @click="handleNavClick(item)">
            <el-icon :size="16"><component :is="item.icon" /></el-icon>
            <span class="txt">{{ item.name }}</span>
          </li>
        </ul>
        <div class="avatar flexBox">
          <el-icon :size="20"><UserFilled /></el-icon>
          <span class="txt">{{ userStore.userInfo.username || 'admin' }}</span>
          <el-icon :size="12"><ArrowDown /></el-icon>
        </div>
      </div>
    </header>

    <div class="main-container">
      <!-- 左侧菜单 -->
      <aside v-if="showSiderbar" class="siderBox">
        <el-menu
          :default-active="sidebarActivePath"
          router
          :style="{ '--el-menu-level-padding': '0px' }"
        >
          <template v-for="item in currentMenu" :key="item.path || item.name">
            <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.name">
              <template #title>
                <el-icon :size="16"><component :is="item.icon" /></el-icon>
                <span class="menu-text">{{ item.name }}</span>
              </template>
              <el-menu-item
                v-for="child in item.children"
                :key="child.path"
                :index="child.path"
              >
                <el-icon :size="14"><component :is="child.icon" /></el-icon>
                {{ child.name }}
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon :size="16"><component :is="item.icon" /></el-icon>
              <span class="menu-text">{{ item.name }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </aside>

      <!-- 内容区 -->
      <main class="contentBox flexBox">
        <div class="routerBox flexBox">
          <el-icon :size="14"><HomeFilled /></el-icon>
          <span>
            <span v-for="(item, index) in breadcrumbs" :key="index">
              {{ item }}
              <span v-if="index !== breadcrumbs.length - 1"> / </span>
            </span>
          </span>
        </div>
        <div class="viewBox">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores'
import { HomeFilled, UserFilled, ArrowDown, Monitor, DataAnalysis, Warning, Setting, VideoCamera, Cpu, Sunny, WindPower, Cloudy, Odometer, Bell, Document, Upload, Picture, VideoPlay } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 顶部导航配置
const navList = [
  { name: '系统概览', path: '/dashboard', icon: HomeFilled },
  { name: '实时监控', path: '/monitor', icon: Monitor },
  { name: '告警管理', path: '/alarm', icon: Warning },
  { name: '文档管理', path: '/document', icon: Document },
]

// 各模块对应的菜单
const menuMap = {
  '/dashboard': [
    { name: '首页', path: '/dashboard', icon: HomeFilled },
  ],
  '/monitor': [
    {
      name: '监控总览',
      path: '/monitor/overview',
      icon: Monitor,
    },
    {
      name: '传感器监测',
      icon: Cpu,
      children: [
        { name: '综合传感器页', path: '/monitor/sensors', icon: Cpu },
        { name: '温湿度传感器', path: '/monitor/temp', icon: Sunny },
        { name: '风速风向传感器', path: '/monitor/wind', icon: WindPower },
        { name: '雨量传感器', path: '/monitor/rain', icon: Cloudy },
        { name: '振动传感器', path: '/monitor/vibration', icon: Odometer },
      ],
    },
    {
      name: '视频监控',
      path: '/monitor/camera',
      icon: VideoCamera,
    },
    {
      name: '图片/视频分析',
      path: '/monitor/camera/image',
      icon: DataAnalysis,
    },
  ],
  '/alarm': [
    {
      name: '告警管理',
      icon: Bell,
      children: [
        { name: '告警列表', path: '/alarm/list', icon: Bell },
        { name: '告警配置', path: '/alarm/config', icon: Setting },
      ],
    },
  ],
  '/document': [
    {
      name: '文档管理',
      icon: Document,
      children: [
        { name: '文档中心', path: '/document/hub', icon: Document },
        { name: '文档上传', path: '/document/upload', icon: Upload },
      ],
    },
  ],
}

// 当前导航
const currentNav = computed(() => {
  const path = route.path
  for (const nav of navList) {
    if (path.startsWith(nav.path)) {
      return nav.path
    }
  }
  return '/dashboard'
})

const isDashboard = computed(() => route.path === '/dashboard')

// 需要显示侧边栏的模块
const showSiderbar = computed(() => {
  const path = route.path
  return path.startsWith('/monitor') || path.startsWith('/rule') || path.startsWith('/document')
})

// 当前菜单
const currentMenu = computed(() => {
  return menuMap[currentNav.value] || []
})

const sidebarActivePath = computed(() => {
  if (route.path === '/monitor/camera/video') return '/monitor/camera/image'
  return route.path
})

// 面包屑
const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta && item.meta.title)
  return matched.map((item) => item.meta.title)
})

// 导航点击
const handleNavClick = (item) => {
  router.push(item.path)
}
</script>

<style scoped>
@import url("../styles/layout.css");
</style>
