<template>
  <div
    class="indexBox"
    :class="{
      'dashboard-shell': isDashboard,
      'bigscreen-shell': isBigScreenPreview,
      'annotator-shell': isRegionAnnotator
    }"
  >
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
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
            <span class="txt">{{ item.name }}</span>
          </li>
        </ul>
        <div class="avatar flexBox">
          <el-icon :size="20"><UserOperatorIcon /></el-icon>
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
          :default-openeds="sidebarDefaultOpeneds"
          router
          :style="{ '--el-menu-level-padding': '0px' }"
        >
          <template v-for="item in currentMenu" :key="item.path || item.name">
            <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.name">
              <template #title>
                <el-icon :size="20"><component :is="item.icon" /></el-icon>
                <span class="menu-text">{{ item.name }}</span>
              </template>
              <el-menu-item
                v-for="child in item.children"
                :key="child.path"
                :index="child.path"
              >
                <el-icon v-if="typeof child.icon !== 'string'" :size="18"><component :is="child.icon" /></el-icon>
                <el-icon v-else :size="18" class="custom-menu-icon-wrap">
                  <img :src="getCustomIcon(child.icon)" class="custom-menu-icon" />
                </el-icon>
                {{ child.name }}
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon v-if="typeof item.icon !== 'string'" :size="20"><component :is="item.icon" /></el-icon>
              <el-icon v-else :size="20" class="custom-menu-icon-wrap">
                <img :src="getCustomIcon(item.icon)" class="custom-menu-icon" />
              </el-icon>
              <span class="menu-text">{{ item.name }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </aside>

      <!-- 内容区 -->
      <main class="contentBox flexBox">
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
import {
  ArrowDown, Connection, DataAnalysis, Setting, VideoCamera,
} from '@element-plus/icons-vue'
import {
  AlarmTriangleIcon,
  DocumentSheetIcon,
  RealtimeMonitorIcon,
  SensorChipIcon,
  SystemOverviewIcon,
  UserOperatorIcon,
  VideoMonitorIcon,
} from '@/components/SystemIcons'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 自定义图标映射
const customIconMap = {
  'drone-custom-icon': '/drone-menu-icon.png',
}

// 获取自定义图标路径
function getCustomIcon(iconKey) {
  return customIconMap[iconKey] || ''
}

// 顶部导航配置
const navList = [
  { name: '综合态势', path: '/dashboard', icon: SystemOverviewIcon },
  { name: '感知监测', path: '/monitor', icon: RealtimeMonitorIcon },
  { name: '告警管理', path: '/alarm', icon: AlarmTriangleIcon },
  { name: '数据管理', path: '/document', icon: DocumentSheetIcon },
  { name: '系统管理', path: '/system', icon: Setting },
]

// 各模块对应的菜单
const menuMap = {
  '/dashboard': [
    { name: '首页', path: '/dashboard', icon: SystemOverviewIcon },
  ],
  '/monitor': [
    {
      name: '监控总览',
      path: '/monitor/overview',
      icon: RealtimeMonitorIcon,
    },
    {
      name: '传感器监测',
      path: '/monitor/sensors',
      icon: SensorChipIcon,
    },
    {
      name: '视频监测',
      path: '/monitor/camera',
      icon: VideoMonitorIcon,
    },
    {
      name: '系统监测',
      path: '/monitor/system',
      icon: SystemOverviewIcon,
    },
  ],
  '/alarm': [
    {
      name: '告警管理',
      path: '/alarm/safety-events',
      icon: AlarmTriangleIcon,
    },
  ],
  '/system': [
    { name: '数据源管理', path: '/system/devices', icon: Setting },
    {
      name: '规则管理',
      icon: DataAnalysis,
      children: [
        { name: '事件配置', path: '/system/rules/events', icon: DataAnalysis },
        { name: '区域配置', path: '/system/rules/zones', icon: VideoCamera },
      ],
    },
    {
      name: '联动系统',
      icon: Setting,
      children: [
        { name: '广播设备', path: '/system/linkage/broadcast', icon: Connection },
        { name: '无人机设备', path: '/system/linkage/drone', icon: 'drone-custom-icon' },
        { name: '机器狗设备', path: '/system/linkage/machine-dog', icon: Setting },
        { name: '现场人员管理', path: '/system/linkage/staff', icon: SensorChipIcon },
      ],
    },
    { name: '模型管理', path: '/system/models', icon: DataAnalysis },
    {
      name: '场景测试',
      icon: DataAnalysis,
      children: [
        { name: '视频测试', path: '/system/video-detection', icon: VideoCamera },
        { name: '传感器测试', path: '/system/sensor-event-test', icon: SensorChipIcon },
      ],
    },
  ],
  '/document': [
    { name: '文档管理', path: '/document/hub', icon: DocumentSheetIcon },
    { name: '知识库', path: '/document/knowledge', icon: DataAnalysis },
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
const isBigScreenPreview = computed(() => route.path === '/dashboard')
const isRegionAnnotator = computed(() => route.path === '/overview-camera-region-annotator')

// 需要显示侧边栏的模块
const showSiderbar = computed(() => {
  const path = route.path
  return path.startsWith('/monitor') || path.startsWith('/alarm') || path.startsWith('/system') || path.startsWith('/document')
})

// 当前菜单
const currentMenu = computed(() => {
  return menuMap[currentNav.value] || []
})

const sidebarActivePath = computed(() => {
  if (route.path === '/monitor/camera/image' || route.path === '/monitor/camera/video') return '/monitor/camera'
  if (route.path.startsWith('/alarm/safety-events')) return '/alarm/safety-events'
  return route.path
})

const sidebarDefaultOpeneds = computed(() => {
  return currentMenu.value
    .filter(item => item.children?.some(child => child.path === sidebarActivePath.value))
    .map(item => item.name)
})

// 导航点击
const handleNavClick = (item) => {
  router.push(item.path)
}

</script>

<style scoped>
@import url("../styles/layout.css");

/* 自定义菜单图标 */
.custom-menu-icon-wrap {
  line-height: 1;
}

.custom-menu-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
  display: block;
}

.siderBox :deep(.el-menu-item),
.siderBox :deep(.el-sub-menu__title) {
  font-size: 18px;
  font-weight: 600;
}

.siderBox :deep(.el-menu > .el-menu-item),
.siderBox :deep(.el-menu > .el-sub-menu > .el-sub-menu__title) {
  padding-left: 22px !important;
  padding-right: 22px !important;
}

.siderBox :deep(.el-menu > .el-menu-item > .el-icon),
.siderBox :deep(.el-menu > .el-sub-menu > .el-sub-menu__title > .el-icon) {
  width: 22px;
  margin-right: 16px;
}

.siderBox :deep(.el-menu > .el-sub-menu > .el-sub-menu__title .el-sub-menu__icon-arrow) {
  right: 18px;
  margin-top: -6px;
}

.siderBox :deep(.el-sub-menu .el-menu-item) {
  height: 48px !important;
  line-height: 48px !important;
  padding-left: 70px !important;
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 6px;
  background: transparent !important;
}

.siderBox :deep(.el-sub-menu .el-menu-item .el-icon) {
  margin-right: 12px;
  font-size: 18px;
}

.siderBox :deep(.el-sub-menu .el-menu-item.is-active) {
  font-weight: 600;
}
</style>
