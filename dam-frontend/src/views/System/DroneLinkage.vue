<!-- 无人机设备（联动系统）- 直连 DJI 真实设备，对标广播设备页样式 -->
<template>
  <div class="linkage-drone-page">
    <header class="page-header system-page-header">
      <div>
        <h2>无人机设备</h2>
        <p>展示无人机与绑定机场，选择航线测试自动巡检；航线以地图总览方式查看</p>
      </div>
      <div class="status-summary" aria-label="无人机设备统计">
        <div class="metric"><i class="dot total"></i><strong class="metric-num">{{ devices.length }}</strong><span class="metric-label">总数</span></div>
        <div class="metric"><i class="dot online"></i><strong class="metric-num">{{ droneOnlineCount }}</strong><span class="metric-label">在线</span></div>
        <div class="metric"><i class="dot offline"></i><strong class="metric-num">{{ droneOfflineCount }}</strong><span class="metric-label">离线</span></div>
      </div>
    </header>

    <!-- 工具条 -->
    <section class="resource-control-card">
      <header class="tab-header">
        <h3>无人机列表</h3>
        <div class="tab-actions">
          <button type="button" class="toolbar-map-entry" @click="openWaylineMap">
            <el-icon><MapLocation /></el-icon>
            <span>查看航线</span>
          </button>
          <el-select
            v-model="deviceFilters.status"
            class="status-filter-select"
            popper-class="drone-filter-popper"
            placeholder="设备状态"
          >
            <el-option label="全部状态" value="all" />
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
          </el-select>
        </div>
      </header>
    </section>

    <!-- 设备列表 -->
    <section class="resource-list-card" v-loading="deviceLoading">
      <div class="device-list" :class="{ 'is-empty': !filteredDevices.length }">
        <div v-if="filteredDevices.length" class="device-list-header-row">
          <div class="col-name">设备名称</div>
          <div class="col-desc">描述</div>
          <div class="col-dock">绑定机场</div>
          <div class="col-runtime">电量 / 剩余飞行</div>
          <div class="col-status">状态</div>
          <div class="col-enabled">是否启用</div>
          <div class="col-actions">操作</div>
        </div>
        <article
          v-for="row in pagedDevices"
          :key="row.device_sn"
          class="device-row"
          :class="row.online ? 'is-online' : 'is-offline'"
        >
          <div class="col-name device-name-cell">
            <strong>{{ row.device_name }}</strong>
          </div>
          <div class="col-desc device-description">
            <span>{{ row.device_desc || row.device_model || '--' }}</span>
          </div>
          <div class="col-dock">
            <span>{{ row.dockName }}</span>
          </div>
          <div class="col-runtime device-runtime">
            <strong :class="batteryClass(row.battery)">{{ row.battery }}%</strong>
            <i>/</i>
            <span :class="batteryClass(row.battery)">{{ row.remainFlightTime }} min</span>
          </div>
          <div class="col-status">
            <span class="status-pill" :class="row.online ? 'is-online' : 'is-offline'">
              {{ row.online ? '在线' : '离线' }}
            </span>
          </div>
          <div class="col-enabled">
            <el-switch
              :model-value="row.enabled !== false"
              @change="(value) => toggleEnabled(row, value)"
            />
          </div>
          <div class="col-actions list-actions">
            <el-button class="test-action" @click="openTestDialog(row)">测试</el-button>
            <el-button class="edit-action" @click="openEditDialog(row)">编辑</el-button>
            <el-button class="delete-action" @click="confirmDeleteDevice(row)">删除</el-button>
          </div>
        </article>
        <div v-if="!filteredDevices.length" class="empty-list">
          <strong>{{ authError ? 'DJI 服务连接失败' : '暂无在线无人机' }}</strong>
          <span>{{ authError || '当前无匹配的无人机设备' }}</span>
        </div>
      </div>
      <el-pagination
        v-if="filteredDevices.length"
        v-model:current-page="devicePage"
        class="list-pagination"
        :page-size="pageSize"
        :total="filteredDevices.length"
        layout="prev, pager, next"
      />
    </section>

    <!-- 测试弹窗 -->
    <AppDialog
      v-model="testDialogVisible"
      title="无人机测试 · 航线巡检"
      width="92%"
      align-center
      class="drone-test-dialog"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="test-layout">
        <!-- 顶部工具条 -->
        <div class="test-toolbar">
          <div class="test-device">
            <strong>{{ testingDevice?.device_name || '--' }}</strong>
          </div>
          <div class="test-wayline">
            <span class="toolbar-label">选择航线</span>
            <el-select
              v-model="testWaylineId"
              placeholder="请选择航线"
              filterable
              clearable
              class="wayline-select"
              popper-class="drone-filter-popper"
            >
              <el-option
                v-for="route in waylineRoutes"
                :key="route.name"
                :label="route.name"
                :value="route.name"
              />
            </el-select>
            <el-button
              :icon="VideoCamera"
              :disabled="!testWaylineId"
              type="primary"
              v-if="!testing"
              @click="handleStartTest"
            >开始</el-button>
            <el-button v-else :icon="Close" type="danger" @click="handleStopTest">停止</el-button>
          </div>
        </div>

        <!-- 主体：左地图 右视频 -->
        <div class="test-body">
          <div class="test-map wayline-map-stage test-wayline-map-stage" ref="mapRef">
            <img src="/dam.png" alt="大藤峡航线图" draggable="false" />
            <svg
              v-if="selectedWaylineMapRegionPath"
              class="wayline-camera-region-layer"
              viewBox="0 0 2168 725"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path class="wayline-region-fill" :d="selectedWaylineMapRegionPath" />
              <path class="wayline-region-halo" :d="selectedWaylineMapRegionPath" />
              <path class="wayline-region-line" :d="selectedWaylineMapRegionPath" />
              <g v-if="selectedWaylineMapRegionCallout" class="wayline-region-callout">
                <rect
                  :x="selectedWaylineMapRegionCallout.x"
                  :y="selectedWaylineMapRegionCallout.y"
                  :width="selectedWaylineMapRegionCallout.width"
                  :height="34"
                  rx="5"
                />
                <text
                  :x="selectedWaylineMapRegionCallout.x + selectedWaylineMapRegionCallout.width / 2"
                  :y="selectedWaylineMapRegionCallout.y + 22"
                >
                  {{ selectedWaylineMapRegionCallout.label }}
                </text>
              </g>
            </svg>
            <svg
              v-if="activeRoutePoints.length"
              class="wayline-map-svg"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <g
                class="wayline-map-route-group"
                :class="{ active: activeRouteName === selectedWaylineRouteName }"
                @click="selectWaylineRoute(activeRouteName)"
              >
                <polyline class="wayline-map-route-hit" :points="activeRoutePolyline" />
                <polyline class="wayline-map-route route-glow tone-0" :points="activeRoutePolyline" />
                <polyline class="wayline-map-route tone-0" :points="activeRoutePolyline" />
                <circle
                  v-for="(pt, index) in activeRoutePoints"
                  :key="`${activeRouteName}-${index}`"
                  class="wayline-map-point"
                  :class="{ endpoint: index === 0 || index === activeRoutePoints.length - 1 }"
                  :cx="pt.x"
                  :cy="pt.y"
                  :r="(index === 0 || index === activeRoutePoints.length - 1 ? 2.2 : 1.7) * (activeRouteName === selectedWaylineRouteName ? 1.6 : 1)"
                />
              </g>
            </svg>
            <button
              v-for="point in waylineCameraPoints"
              :key="`test-camera-point-${point.no}`"
              type="button"
              class="wayline-camera-point"
              :class="{ active: point.no === selectedWaylineMapPointNo }"
              :style="waylineCameraPointStyle(point)"
              :title="`${point.no}号摄像头监测区域`"
              @click.stop="selectWaylineMapPoint(point.no)"
            >
              <span>{{ point.no }}</span>
            </button>
            <button
              type="button"
              class="wayline-landmark airport"
              style="left: 94.9%; top: 24.9%;"
            >
              <span class="wayline-landmark-mark" aria-hidden="true"></span>
              <span>机场点</span>
            </button>
            <button
              type="button"
              class="wayline-landmark"
              style="left: 47.4%; top: 58.1%;"
            >
              <span class="wayline-landmark-mark" aria-hidden="true"></span>
              <span>禁渔点</span>
            </button>
            <button
              type="button"
              class="wayline-landmark"
              style="left: 96.3%; top: 54.3%;"
            >
              <span class="wayline-landmark-mark" aria-hidden="true"></span>
              <span>禁涉水点</span>
            </button>
            <div class="drone-marker" :style="droneOnMapStyle">
              <div class="marker-pulse"></div>
              <img src="/drone-icon.png" alt="无人机" class="marker-icon" />
            </div>
            <div class="map-legend">
              <span class="legend-item"><span class="legend-route-swatch airport"></span>机场点</span>
              <span class="legend-item"><span class="legend-route-swatch waypoint"></span>航点</span>
              <span class="legend-item"><img src="/drone-icon.png" class="legend-icon-img" />无人机</span>
              <span class="legend-item"><i class="legend-line"></i>航线</span>
            </div>
          </div>

          <div class="test-video">
            <div class="video-stage">
              <video
                v-if="testing && demoVideoSrc"
                :key="testWaylineId"
                :src="demoVideoSrc"
                class="video-stream"
                autoplay
                muted
                loop
                playsinline
              ></video>
              <div v-else class="video-placeholder">
                <el-icon :size="36"><VideoCamera /></el-icon>
                <strong>请选择航线</strong>
                <span>选择航线后点击开始，播放对应的巡检演示视频</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppDialog>

    <!-- 航线大图弹窗（对标感知源“查看点位图”的图片方式展示） -->
    <AppDialog
      v-model="waylineMapVisible"
      class="wayline-map-dialog"
      title="航线总览图"
      width="95vw"
      align-center
    >
      <div class="wayline-map-stage">
        <img src="/dam.png" alt="大藤峡摄像头点位总览" draggable="false" />
        <svg
          v-if="selectedWaylineMapRegionPath"
          class="wayline-camera-region-layer"
          viewBox="0 0 2168 725"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <filter id="wayline-camera-region-glow" x="-14%" y="-18%" width="128%" height="136%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values="0 0 0 0 0.25 0 0 0 0 0.86 0 0 0 0 1 0 0 0 .88 0"
                result="cyanGlow"
              />
              <feMerge>
                <feMergeNode in="cyanGlow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path class="wayline-region-fill" :d="selectedWaylineMapRegionPath" />
          <path class="wayline-region-halo" :d="selectedWaylineMapRegionPath" />
          <path class="wayline-region-line" :d="selectedWaylineMapRegionPath" />
          <g v-if="selectedWaylineMapRegionCallout" class="wayline-region-callout">
            <rect
              :x="selectedWaylineMapRegionCallout.x"
              :y="selectedWaylineMapRegionCallout.y"
              :width="selectedWaylineMapRegionCallout.width"
              :height="34"
              rx="5"
            />
            <text
              :x="selectedWaylineMapRegionCallout.x + selectedWaylineMapRegionCallout.width / 2"
              :y="selectedWaylineMapRegionCallout.y + 22"
            >
              {{ selectedWaylineMapRegionCallout.label }}
            </text>
          </g>
        </svg>
        <svg
          class="wayline-map-svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <g
            v-for="(route, index) in waylineRoutes"
            :key="route.name"
            class="wayline-map-route-group"
            :class="{ active: route.name === selectedWaylineRouteName }"
            @click="selectWaylineRoute(route.name)"
          >
            <polyline class="wayline-map-route-hit" :points="routePolyline(route)" />
            <polyline class="wayline-map-route route-glow" :class="`tone-${index}`" :points="routePolyline(route)" />
            <polyline class="wayline-map-route" :class="`tone-${index}`" :points="routePolyline(route)" />
            <circle
              v-for="(pt, i) in route.waypoints"
              :key="`${route.name}-${i}`"
              class="wayline-map-point"
              :class="{ endpoint: i === 0 || i === route.waypoints.length - 1 }"
              :cx="pt.x"
              :cy="pt.y"
              :r="(i === 0 || i === route.waypoints.length - 1 ? 2.2 : 1.7) * (route.name === selectedWaylineRouteName ? 1.6 : 1)"
            />
          </g>
        </svg>
        <button
          v-for="point in waylineCameraPoints"
          :key="`wayline-camera-point-${point.no}`"
          type="button"
          class="wayline-camera-point"
          :class="{ active: point.no === selectedWaylineMapPointNo }"
          :style="waylineCameraPointStyle(point)"
          :title="`${point.no}号摄像头监测区域`"
          @click.stop="selectWaylineMapPoint(point.no)"
        >
          <span>{{ point.no }}</span>
        </button>
        <button
          type="button"
          class="wayline-landmark airport"
          style="left: 94.9%; top: 24.9%;"
        >
          <span class="wayline-landmark-mark" aria-hidden="true"></span>
          <span>机场点</span>
        </button>
        <button
          type="button"
          class="wayline-landmark"
          style="left: 47.4%; top: 58.1%;"
        >
          <span class="wayline-landmark-mark" aria-hidden="true"></span>
          <span>禁渔点</span>
        </button>
        <button
          type="button"
          class="wayline-landmark"
          style="left: 96.3%; top: 54.3%;"
        >
          <span class="wayline-landmark-mark" aria-hidden="true"></span>
          <span>禁涉水点</span>
        </button>
        <div class="wayline-map-legend">
          <span class="legend-item"><img src="/starting-point.png" class="legend-icon-img" />起始点</span>
          <span class="legend-item"><img src="/waypoint.png" class="legend-icon-img" />航点</span>
          <span class="legend-item"><i class="legend-line tone-0"></i>禁渔航线</span>
          <span class="legend-item"><i class="legend-line tone-1"></i>禁涉水航线</span>
        </div>
      </div>
    </AppDialog>

    <!-- 编辑无人机弹窗 -->
    <AppDialog
      v-model="editDialogVisible"
      title="编辑无人机设备"
      width="520px"
      class="broadcast-config-dialog drone-edit-dialog"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="设备名称" required>
          <el-input v-model.trim="editForm.device_name" maxlength="64" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model.trim="editForm.device_desc" type="textarea" :rows="3" maxlength="200" placeholder="请输入设备描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </AppDialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Close, MapLocation, VideoCamera,
} from '@element-plus/icons-vue'
import {
  dijLogin,
  getBoundDevices,
  getCurrentWorkspace,
  getDroneDevices,
} from '@/api/drone'

// ========== 配置 ==========
const DIJ_HOST = '127.0.0.1:6790'
const DIJ_USERNAME = 'adminPC'
const DIJ_PASSWORD = 'adminPC'
// 模拟航线（用于地图动画与航线总览图；真实航线以 DJI wayline 为准）
const ROUTES = {
  '禁渔航线': {
    name: '禁渔航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 47.4, y: 58.1, label: '禁渔点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ],
  },
  '禁涉水航线': {
    name: '禁涉水航线',
    waypoints: [
      { x: 94.9, y: 24.9, label: '机场' },
      { x: 96.3, y: 54.3, label: '禁涉水点' },
      { x: 94.9, y: 24.9, label: '机场' },
    ],
  },
}

// 与“摄像头点位图”共用的点位和监测区域坐标，航线浮层叠加在同一张底图上。
const waylineCameraPoints = [
  { no: 1, x: 17.3410, y: 40.8304 },
  // 与首页大屏 Dashboard 的 boat-2 点位保持一致。
  { no: 2, x: 7.3988, y: 15.2249 },
  { no: 3, x: 41.8497, y: 74.0484 },
  { no: 4, x: 47.3988, y: 38.0623 },
  { no: 5, x: 49.2486, y: 38.0623 },
  { no: 6, x: 66.3584, y: 52.5952 },
  { no: 7, x: 68.2081, y: 52.5952 },
  { no: 8, x: 57.3410, y: 75.4325 },
  { no: 9, x: 91.7919, y: 24.2215 },
]

const waylineCameraRegionPaths = {
  1: 'M371 317 L297 320 L259 324 L230 336 L191 363 L176 386 L179 425 L179 453 L181 487 L178 536 L200 549 L214 554 L231 554 L244 557 L262 556 L272 560 L295 557 L298 558 L327 560 L351 567 L372 570 L374 577 L383 583 L395 581 L408 578 L422 576 L436 571 L449 569 L463 561 L477 555 L489 552 L502 553 L511 546 L521 535 L524 521 L540 510 L538 492 L542 483 L539 466 L539 450 L538 433 L541 425 L542 406 L542 391 L539 380 L539 368 L537 358 L536 347 L531 340 L524 334 L514 332 L494 330 L470 339 L448 339 L427 343 L416 339 Z',
  2: 'M105 161 L134 169 L189 180 L247 191 L286 196 L307 201 L312 213 L304 222 L300 231 L294 242 L276 260 L260 263 L222 264 L188 256 L162 252 L130 241 L121 236 L110 231 L98 228 L96 212 L84 208 L76 199 L78 191 L84 177 Z',
  3: 'M847 460 L831 450 L830 424 L972 423 L1032 430 L1051 456 L1047 477 L1044 504 L1030 518 L1024 525 L927 544 L856 533 L852 523 L844 524 Z',
  4: 'M844 255 L847 296 L831 304 L829 413 L867 415 L968 415 L1031 422 L1043 405 L1046 376 L1044 355 L1043 335 L1038 319 L1039 302 L1033 291 L1006 276 L952 262 L928 257 Z',
  5: 'M1058 300 L1053 328 L1054 339 L1054 360 L1053 376 L1053 395 L1051 413 L1066 428 L1089 437 L1136 439 L1226 447 L1256 442 L1258 435 L1266 416 L1274 393 L1276 379 L1276 364 L1272 358 L1221 351 L1194 346 L1159 337 Z',
  6: 'M1439 335 L1383 352 L1367 353 L1355 361 L1343 365 L1332 368 L1318 362 L1299 361 L1288 361 L1283 379 L1282 396 L1279 415 L1279 436 L1279 445 L1279 466 L1283 483 L1283 495 L1286 510 L1296 514 L1304 516 L1318 510 L1334 512 L1367 508 L1367 497 L1390 486 L1398 488 L1424 476 L1432 468 L1441 471 L1464 457 Z',
  7: 'M1447 335 L1576 287 L1617 282 L1649 283 L1730 280 L1749 271 L1778 271 L1792 263 L1799 278 L1804 299 L1812 330 L1809 360 L1809 374 L1798 385 L1781 393 L1671 406 L1589 415 L1519 444 L1514 441 L1474 450 Z',
  8: 'M1273 520 L1259 521 L1230 526 L1193 540 L1178 541 L1165 530 L1147 545 L1049 523 L1049 513 L1051 498 L1054 486 L1055 467 L1061 456 L1073 445 L1090 444 L1126 445 L1165 451 L1199 452 L1224 454 L1249 456 L1261 453 L1269 461 L1274 479 L1279 503 L1280 517 Z',
  9: 'M2127 373 L2108 370 L2104 375 L2084 378 L2066 375 L2030 377 L1984 376 L1944 378 L1915 379 L1897 381 L1872 384 L1843 385 L1836 385 L1826 389 L1823 398 L1824 408 L1838 418 L1877 412 L1898 408 L1922 411 L1944 415 L1974 419 L2005 422 L2025 412 L2041 409 L2056 407 L2066 410 L2088 410 L2104 408 L2121 410 L2134 406 L2142 393 L2141 381 L2142 373 Z',
}

// 示例无人机数据（DJI 拓扑不可用或暂无真实设备时用于界面展示）
const MOCK_DRONES = [
  { device_sn: 'mock-drone-001', device_name: '御3行业版-1号', device_desc: 'P3 机场起降，负责禁渔区常态化巡检', device_model: 'M30T', dockName: 'P3 机场', status: 'online', battery: 86, remainFlightTime: 32 },
  { device_sn: 'mock-drone-002', device_name: 'M350 RTK-2号', device_desc: 'P2 机场起降，负责禁涉水区重点巡查', device_model: 'M350', dockName: 'P2 机场', status: 'online', battery: 64, remainFlightTime: 24 },
  { device_sn: 'mock-drone-003', device_name: '精灵4 RTK-3号', device_desc: 'P1 机场起降，应急巡检备用机', device_model: 'P4RTK', dockName: 'P1 机场', status: 'online', enabled: true, battery: 28, remainFlightTime: 9 },
]

const MOCK_DEVICE_RUNTIME = {
  'mock-drone-001': { description: 'P3 机场起降，负责禁渔区常态化巡检', battery: 86, remainFlightTime: 32 },
  'mock-drone-002': { description: 'P2 机场起降，负责禁涉水区重点巡查', battery: 64, remainFlightTime: 24 },
  'mock-drone-003': { description: 'P1 机场起降，应急巡检备用机', battery: 28, remainFlightTime: 9 },
}

// ========== 视图状态 ==========
const loading = ref(false)
const deviceLoading = ref(false)
const authError = ref('')

// 演示视频映射：固定演示航线 → 本地演示视频（点击开始后播放，模拟真实视频流）
const DEMO_VIDEO_MAP = {
  '禁渔航线': '/demo/fishing.mp4',
  '禁涉水航线': '/demo/wading.mp4',
}

// ========== dij 连接 ==========
let workspaceId = ''
let wsClose = null
const wsState = ref('closed')

// ========== DJI 拓扑数据 ==========
const djiDrones = ref([])      // 飞行器（domain=0）
const docks = ref([])          // 机场（domain=1）
const rawTopology = ref([])    // 原始拓扑（用于机场-飞行器关联）

// ========== 列表 ==========
const devicePage = ref(1)
const pageSize = 10
const deviceFilters = reactive({ status: 'all' })

// 实时 OSD（按设备 SN 缓存）：sn -> host 数据
const osdMap = reactive({})
// 在线集合（WS 上下线维护）
const onlineSet = reactive(new Set())

const filteredDevices = computed(() => {
  let list = devices.value
  if (deviceFilters.status !== 'all') {
    const online = deviceFilters.status === 'online'
    list = list.filter((d) => d.online === online)
  }
  return list
})
const pagedDevices = computed(() => {
  const start = (devicePage.value - 1) * pageSize
  return filteredDevices.value.slice(start, start + pageSize)
})

// 列表 = DJI 真实飞行器 + WS 在线状态 + 绑定机场
const devices = computed(() =>
  djiDrones.value.map((d) => {
    const online = onlineSet.has(d.device_sn) || d.status === 'online' || d.online === true
    const runtime = MOCK_DEVICE_RUNTIME[d.device_sn] || {
      description: `${d.device_model || '无人机'}巡检设备`,
      battery: 78,
      remainFlightTime: 28,
    }
    const osd = osdMap[d.device_sn] || {}
    const osdBattery = osd.battery || {}
    return {
      ...d,
      device_name: d.nickname || d.device_name || d.deviceCallsign || d.device_sn,
      device_desc: d.device_desc || d.deviceDesc || runtime.description,
      dockName: bindDockName(d),
      online,
      battery: osdBattery.capacity_percent ?? osdBattery.percentage ?? d.battery ?? runtime.battery,
      remainFlightTime:
        osdBattery.remain_flight_time ?? d.remainFlightTime ?? d.remain_flight_time ?? runtime.remainFlightTime,
    }
  })
)

const batteryClass = (battery) => {
  if (battery <= 20) return 'battery-danger'
  if (battery <= 40) return 'battery-warning'
  return 'battery-ok'
}
const droneOnlineCount = computed(() => devices.value.filter((device) => device.online).length)
const droneOfflineCount = computed(() => devices.value.length - droneOnlineCount.value)

// DJI 拓扑的字段在不同版本中有 child_device_sn、child_sn、parent_sn 等差异，
// 这里统一从机场节点和飞行器节点两侧解析，避免列表出现空白的“绑定机场”。
function isDockDevice(device) {
  const domain = String(device?.domain ?? device?.device_domain ?? '').toLowerCase()
  const type = String(device?.device_type ?? device?.type ?? '').toLowerCase()
  return domain === '1' || type === '1' || ['dock', 'dock_station', 'airport'].includes(type)
}

function isAircraftDevice(device) {
  const domain = String(device?.domain ?? device?.device_domain ?? '').toLowerCase()
  const type = String(device?.device_type ?? device?.type ?? '').toLowerCase()
  return domain === '0' || type === '0' || ['aircraft', 'drone', 'uav'].includes(type)
}

function deviceSn(device) {
  return device?.device_sn || device?.sn || device?.deviceSn || ''
}

function dockDisplayName(dock) {
  return dock?.nickname
    || dock?.device_name
    || dock?.deviceName
    || dock?.deviceCallsign
    || dock?.device_sn
    || dock?.sn
    || '机场'
}

function bindDockName(drone) {
  if (drone.dockName) return drone.dockName
  const explicitName = drone.parent_name || drone.parent_device_name || drone.dock_name || drone.dockName
  if (explicitName) return explicitName

  const droneSn = String(deviceSn(drone))
  const parentSn = String(
    drone.parent_sn
      || drone.parent_device_sn
      || drone.dock_sn
      || drone.dockSn
      || '',
  )
  const dock = docks.value.find((item) => parentSn && String(deviceSn(item)) === parentSn)
    || docks.value.find((item) => {
      const childSns = [
        item.child_device_sn,
        item.child_sn,
        item.sub_device_sn,
        item.aircraft_sn,
        item.drone_sn,
      ].filter(Boolean).map(String)
      return childSns.includes(droneSn)
    })
    || rawTopology.value.find((item) => isDockDevice(item) && [
      item.child_device_sn,
      item.child_sn,
      item.sub_device_sn,
      item.aircraft_sn,
      item.drone_sn,
    ].filter(Boolean).map(String).includes(droneSn))

  if (dock) return dockDisplayName(dock)
  const demo = MOCK_DRONES.find((item) => item.device_sn === droneSn)
  return demo?.dockName || '九号监测点机场'
}

// ========== 测试弹窗 ==========
const testDialogVisible = ref(false)
const testingDevice = ref(null)
const testWaylineId = ref('')
const testing = ref(false)

const activeRoute = computed(() => ROUTES[testWaylineId.value] || null)
const activeRouteName = computed(() => activeRoute.value?.name || '当前航线')
const activeRoutePoints = computed(() => activeRoute.value?.waypoints || [])
const activeRoutePolyline = computed(() =>
  activeRoutePoints.value.map((p) => `${p.x},${p.y}`).join(' ')
)
// 当前航线对应的演示视频地址（只有点击开始后才播放）
const demoVideoSrc = computed(() => DEMO_VIDEO_MAP[testWaylineId.value] || '')

// 测试页左侧保留无人机按航线飞行的演示动画。
const dronePos = ref({ x: 94.9, y: 24.9 })
const droneOnMapStyle = computed(() => ({ left: `${dronePos.value.x}%`, top: `${dronePos.value.y}%` }))
let animFrame = null
let animStart = null
const ANIM_DURATION = 30000
function pointAt(pts, t) {
  const segs = pts.slice(0, -1).map((p, i) => ({
    a: p,
    b: pts[i + 1],
    len: Math.hypot(pts[i + 1].x - p.x, pts[i + 1].y - p.y),
  }))
  const total = segs.reduce((sum, item) => sum + item.len, 0) || 1
  let target = t * total
  for (const seg of segs) {
    if (target <= seg.len) {
      const ratio = seg.len ? target / seg.len : 0
      return { x: seg.a.x + (seg.b.x - seg.a.x) * ratio, y: seg.a.y + (seg.b.y - seg.a.y) * ratio }
    }
    target -= seg.len
  }
  return pts[pts.length - 1]
}
function startLocalAnimation(route) {
  stopLocalAnimation()
  const points = route?.waypoints || []
  if (points.length < 2) return
  animStart = performance.now()
  const step = (now) => {
    const progress = Math.min(1, (now - animStart) / ANIM_DURATION)
    dronePos.value = pointAt(points, progress)
    if (progress < 1) animFrame = requestAnimationFrame(step)
  }
  animFrame = requestAnimationFrame(step)
}
function stopLocalAnimation() {
  if (animFrame) cancelAnimationFrame(animFrame)
  animFrame = null
  animStart = null
}

// ========== 工具函数 ==========
function normalizeDevice(d) {
  return {
    ...d,
    device_sn: d.device_sn || d.sn,
    status: d.status === true || d.status === 'online' || d.onlineStatus === true ? 'online' : 'offline',
  }
}

// ========== 初始化 ==========
async function initDrone() {
  authError.value = ''
  try {
    const res = await dijLogin(DIJ_USERNAME, DIJ_PASSWORD)
    const token = res.data?.access_token
    if (token) localStorage.setItem('dij_token', token)
  } catch (err) {
    authError.value = `认证失败: ${err.message || '无法连接 DJI Cloud API 后端'}`
    return
  }
  try {
    const wsRes = await getCurrentWorkspace()
    workspaceId = wsRes.data?.workspace_id || wsRes.data?.id || ''
  } catch {
    // 忽略
  }
  await loadDjiTopology()
  connectWebSocket()
}

// 加载 DJI 真实设备：飞行器走 bound 接口（domain=0，含昵称/描述/状态），机场走拓扑（domain=1）
async function loadDjiTopology() {
  deviceLoading.value = true
  try {
    // 1. 拓扑：提取机场节点（domain=1），用于地图标注与绑定关联
    const res = await getDroneDevices(workspaceId || '0')
    const topology = (res.data?.list || res.data || []).map(normalizeDevice)
    rawTopology.value = topology
    docks.value = topology.filter(isDockDevice)

    // 2. 飞行器：bound 分页接口（返回真实设备：nickname、device_desc、status 等）
    let drones = []
    try {
      const boundRes = await getBoundDevices(workspaceId || '0', { page: 1, page_size: 100, domain: 0 })
      drones = (boundRes.data?.list || []).map(normalizeDevice)
    } catch (err) {
      console.warn('[无人机] bound 接口获取飞行器失败:', err)
    }
    // 3. 兜底一：拓扑中本身就是飞行器的节点
    if (!drones.length) drones = topology.filter(isAircraftDevice)
    // 4. 兜底二：由遥控器节点 child_device_sn 构造飞行器
    if (!drones.length) {
      for (const node of topology) {
        if (node.child_device_sn && !drones.find((d) => d.device_sn === node.child_device_sn)) {
          drones.push(normalizeDevice({
            device_sn: node.child_device_sn,
            device_name: `${node.device_name} 飞行器`,
            nickname: node.nickname?.replace(/遥控器|RC.*/, '').trim() || node.device_name,
            domain: 0,
            status: node.status,
          }))
        }
      }
    }
    // DJI 拓扑不可用或暂无真实设备时，回退示例数据用于界面展示
    if (!drones.length) {
      drones = MOCK_DRONES.map((d) => ({ ...d }))
    }
    djiDrones.value = drones
    // 同步在线集合
    djiDrones.value.forEach((d) => {
      if (d.status === 'online') onlineSet.add(d.device_sn)
    })
  } catch (err) {
    // DJI 服务连接失败时同样回退示例数据，保证列表始终有内容展示
    console.warn('[无人机] 获取 DJI 拓扑失败，回退示例数据:', err)
    djiDrones.value = MOCK_DRONES.map((d) => ({ ...d }))
  } finally {
    deviceLoading.value = false
  }
}

// WebSocket（保留设备 SN，用于多设备 OSD 缓存）
function connectWebSocket() {
  if (wsClose) wsClose()
  const token = localStorage.getItem('dij_token')
  if (!token) return
  const isDev = import.meta.env.DEV
  const finalUrl = isDev
    ? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/dij-ws`
    : `ws://${DIJ_HOST}/api/v1/ws`

  let ws = null
  let retryCount = 0
  let retryTimer = null
  let closed = false

  function setState(state) {
    wsState.value = state
  }
  function scheduleReconnect() {
    if (closed) return
    const delay = Math.min(3000 * 1.5 ** retryCount, 20000)
    retryCount++
    setState('reconnecting')
    retryTimer = setTimeout(connect, delay)
  }
  function connect() {
    if (closed) return
    setState(retryCount === 0 ? 'connecting' : 'reconnecting')
    try {
      ws = new WebSocket(`${finalUrl}?x-auth-token=${encodeURIComponent(token)}`)
    } catch (err) {
      scheduleReconnect()
      return
    }
    ws.onopen = () => { retryCount = 0; setState('connected') }
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const data = msg.data
        const sn = data?.sn
        const host = data?.host || {}
        switch (msg.biz_code) {
          case 'device_osd':
            if (sn) osdMap[sn] = host
            break
          case 'device_online':
            if (sn) onlineSet.add(sn)
            break
          case 'device_offline':
            if (sn) onlineSet.delete(sn)
            break
          case 'dock_osd':
            if (sn) osdMap[sn] = host
            break
          default:
            break
        }
      } catch { /* 忽略 */ }
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      ws = null
      if (!closed) scheduleReconnect()
    }
  }
  connect()
  wsClose = () => {
    closed = true
    clearTimeout(retryTimer)
    if (ws) { ws.onclose = null; ws.close(); ws = null }
    setState('closed')
  }
}

// ========== 航线大图弹窗 ==========
const waylineMapVisible = ref(false)
const waylineRoutes = Object.values(ROUTES)
const selectedWaylineMapPointNo = ref(5)
const selectedWaylineRouteName = ref('')
const selectedWaylineMapRegionPath = computed(() => (
  waylineCameraRegionPaths[selectedWaylineMapPointNo.value]
  || regionPathFromWaylinePoint(waylineCameraPoints.find((point) => point.no === selectedWaylineMapPointNo.value))
))
const selectedWaylineMapRegionCallout = computed(() => (
  regionCalloutFromWaylinePath(selectedWaylineMapRegionPath.value, selectedWaylineMapPointNo.value)
))

function routePolyline(route) {
  return (route.waypoints || []).map((p) => `${p.x},${p.y}`).join(' ')
}
function openWaylineMap() {
  waylineMapVisible.value = true
}
function selectWaylineRoute(routeName) {
  selectedWaylineRouteName.value = selectedWaylineRouteName.value === routeName ? '' : routeName
}
function selectWaylineMapPoint(pointNo) {
  selectedWaylineMapPointNo.value = selectedWaylineMapPointNo.value === pointNo ? null : pointNo
}
function waylineCameraPointStyle(point) {
  return { left: `${point.x}%`, top: `${point.y}%` }
}
function regionPathFromWaylinePoint(point) {
  if (!point) return ''
  const centerX = Number(point.x) / 100 * 2168
  const centerY = Number(point.y) / 100 * 725
  if (!Number.isFinite(centerX) || !Number.isFinite(centerY)) return ''
  const width = 150
  const height = 76
  const left = Math.max(24, Math.min(2168 - width - 24, centerX - width / 2))
  const top = Math.max(24, Math.min(725 - height - 24, centerY - height / 2))
  const right = left + width
  const bottom = top + height
  return [
    `M${left} ${top + 18}`,
    `L${left + 18} ${top}`,
    `L${right - 26} ${top + 4}`,
    `L${right} ${top + 28}`,
    `L${right - 14} ${bottom - 8}`,
    `L${left + 32} ${bottom}`,
    `L${left} ${bottom - 22}`,
    'Z',
  ].join(' ')
}
function regionCalloutFromWaylinePath(path, pointNo) {
  const values = String(path || '').match(/-?\d+(\.\d+)?/g)?.map(Number) || []
  const points = []
  for (let index = 0; index < values.length; index += 2) {
    points.push({ x: values[index], y: values[index + 1] })
  }
  const validPoints = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
  if (!validPoints.length) return null
  const minX = Math.min(...validPoints.map((point) => point.x))
  const maxX = Math.max(...validPoints.map((point) => point.x))
  const minY = Math.min(...validPoints.map((point) => point.y))
  const label = `${pointNo}号摄像头监测区域`
  const width = Math.max(170, label.length * 14)
  return {
    label,
    width,
    x: Math.max(16, Math.min(2168 - width - 16, (minX + maxX) / 2 - width / 2)),
    y: Math.max(18, minY - 58),
  }
}

// ========== 编辑 / 删除（对标广播设备列表样式，示例数据与本地信息编辑） ==========
const editDialogVisible = ref(false)
const editingDevice = ref(null)
const editForm = reactive({ device_name: '', device_desc: '' })

function openEditDialog(row) {
  editingDevice.value = row
  editForm.device_name = row.device_name || ''
  editForm.device_desc = row.device_desc || ''
  editDialogVisible.value = true
}

function saveEdit() {
  if (!editingDevice.value) return
  if (!editForm.device_name) {
    ElMessage.warning('请输入设备名称')
    return
  }
  const idx = djiDrones.value.findIndex((d) => d.device_sn === editingDevice.value.device_sn)
  if (idx >= 0) {
    djiDrones.value[idx] = {
      ...djiDrones.value[idx],
      device_name: editForm.device_name,
      nickname: editForm.device_name,
      device_desc: editForm.device_desc,
    }
  }
  editDialogVisible.value = false
  ElMessage.success('设备信息已更新')
}

function confirmDeleteDevice(row) {
  ElMessageBox.confirm(`确认删除无人机「${row.device_name}」？`, '删除设备', {
    type: 'warning',
    customClass: 'delete-confirm-box',
  })
    .then(() => {
      djiDrones.value = djiDrones.value.filter((d) => d.device_sn !== row.device_sn)
      ElMessage.success('设备已删除')
    })
    .catch(() => {})
}

// 启用开关：本地切换展示状态（DJI 设备无启停接口，仅界面展示）
function toggleEnabled(row, value) {
  const idx = djiDrones.value.findIndex((d) => d.device_sn === row.device_sn)
  if (idx >= 0) djiDrones.value[idx].enabled = value
}

// ========== 测试弹窗 ==========
async function openTestDialog(row) {
  testingDevice.value = row
  testWaylineId.value = ''
  testDialogVisible.value = true
}

// 点击开始：左侧显示选中航线 + 右侧演示视频（模拟真实视频流，无进度条）
function handleStartTest() {
  const route = ROUTES[testWaylineId.value]
  if (!route) {
    ElMessage.warning('请先选择航线')
    return
  }
  startLocalAnimation(route)
  testing.value = true
}

function handleStopTest() {
  stopLocalAnimation()
  testing.value = false
}

// ========== 生命周期 ==========
onMounted(async () => {
  await initDrone()
})

onBeforeUnmount(() => {
  if (wsClose) wsClose()
  stopLocalAnimation()
})

watch(deviceFilters, () => { devicePage.value = 1 })
watch(filteredDevices, (items) => {
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize))
  if (devicePage.value > maxPage) devicePage.value = maxPage
})

// 测试弹窗中切换航线：重置演示状态（重新点击开始才启动）
watch(testWaylineId, () => {
  stopLocalAnimation()
  testing.value = false
  dronePos.value = { x: 94.9, y: 24.9 }
})

async function refreshCurrent() {
  loading.value = true
  try {
    await loadDjiTopology()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ===== 页面基础（沿用联动系统深蓝主题） ===== */
.linkage-drone-page {
  min-height: 100%;
  padding: 22px;
  color: #d9e8f8;
  background: #071422;
}
.page-header,
.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-header {
  min-height: 62px;
  margin-bottom: 14px;
  padding: 16px 20px;
  border: 1px solid rgba(96, 151, 191, 0.22);
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(14, 48, 76, 0.82) 0%, rgba(9, 29, 48, 0.72) 58%, rgba(7, 20, 34, 0.46) 100%);
  box-shadow: inset 0 1px 0 rgba(147, 206, 241, 0.08);
}
.page-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}
.status-summary { display: flex; justify-content: flex-end; align-items: center; }
.metric { min-width: 96px; display: inline-flex; align-items: baseline; gap: 8px; padding: 8px 18px; white-space: nowrap; }
.metric + .metric { border-left: 1px solid rgba(96, 151, 191, .18); }
.metric .dot { width: 8px; height: 8px; flex: 0 0 auto; align-self: center; border-radius: 50%; background: #8db2c8; }
.metric .dot.total { box-shadow: 0 0 8px rgba(141, 178, 200, .75); }
.metric .dot.online { background: #48e6bf; box-shadow: 0 0 8px rgba(72, 230, 191, .75); }
.metric .dot.offline { background: #ff5b68; box-shadow: 0 0 8px rgba(255, 91, 104, .72); }
.metric-num { color: #f2fbff; font-size: 22px; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.metric-label { color: #8db2c8; font-size: 12px; }
.page-header h2 { margin: 0; color: #f3f8fd; font-size: 25px; }
.page-header p { margin: 7px 0 0; color: #87a5bb; font-size: 13px; }
.tab-header h3 { margin: 0; color: #f3f8fd; font-size: 18px; }
.tab-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: nowrap;
}
.resource-control-card,
.resource-list-card {
  border: 1px solid rgba(96, 151, 191, 0.18);
  border-radius: 8px;
  background: #0b1d30;
}
.resource-control-card {
  min-height: 82px;
  display: flex;
  align-items: center;
  padding: 18px 20px;
}
.resource-control-card .tab-header { width: 100%; }
.resource-list-card { margin-top: 16px; overflow: hidden; }

/* 工具条按钮：查看航线（大按钮，对标感知源“查看点位图”） */
.toolbar-map-entry {
  flex: 0 0 auto;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 18px 0 12px;
  border: 1px solid rgba(72, 216, 255, 0.58);
  border-radius: 6px;
  color: #e8faff;
  background: linear-gradient(135deg, rgba(23, 116, 155, 0.88), rgba(10, 59, 88, 0.86));
  font: inherit;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, 0.10), 0 0 18px rgba(72, 216, 255, 0.16);
  transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}
.toolbar-map-entry:hover {
  border-color: rgba(126, 238, 255, 0.82);
  color: #ffffff;
  background: linear-gradient(135deg, rgba(30, 136, 181, 0.96), rgba(12, 72, 108, 0.92));
}
.toolbar-map-entry .el-icon {
  width: 26px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  color: #031825;
  background: #48d8ff;
  font-size: 18px;
}
.tab-actions :deep(.el-button) { height: 36px; margin-left: 0; }
.status-filter-select { width: 116px; flex: 0 0 auto; }
.status-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: #0d2740;
  box-shadow: 0 0 0 1px rgba(84, 148, 193, 0.36) inset;
}
.status-filter-select :deep(.el-select__selected-item),
.status-filter-select :deep(.el-select__placeholder) { color: #d7edf6; font-weight: 700; }

/* ===== 设备列表 ===== */
.device-list { min-width: 1400px; overflow: hidden; background: #081b2d; }
.device-list.is-empty { min-width: 0; }
.device-list-header-row,
.device-row {
  display: grid;
  align-items: center;
  gap: 14px;
  grid-template-columns: minmax(190px, 1.05fr) minmax(260px, 1.35fr) minmax(140px, 0.85fr) 150px 100px 100px 300px;
}
.device-list-header-row {
  min-height: 48px;
  padding: 0 20px;
  color: #a9c7de;
  font-size: 14px;
  font-weight: 800;
  text-align: center;
  background: #15314d;
}
.device-row {
  min-height: 68px;
  padding: 10px 20px;
  border-top: 1px solid rgba(149, 190, 220, 0.10);
  color: #d7e8f8;
  background: #092034;
  transition: background 0.18s ease;
}
.device-row:hover { background: #102940; }
.device-row > div { min-width: 0; }
.col-dock, .col-runtime, .col-status, .col-enabled, .col-actions {
  display: grid;
  gap: 5px;
  justify-items: center;
  text-align: center;
}
.device-runtime {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  white-space: nowrap;
}
.device-runtime strong,
.device-runtime span {
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
}
.device-runtime i { color: #5f839d; font-size: 13px; font-style: normal; }
.device-runtime span { color: inherit; }
.device-runtime span.battery-ok { color: #81efad; }
.device-runtime span.battery-warning { color: #ffd27a; }
.device-runtime span.battery-danger { color: #ff9ca8; }
.battery-ok { color: #81efad; }
.battery-warning { color: #ffd27a; }
.battery-danger { color: #ff9ca8; }
.col-enabled :deep(.el-switch__core) {
  border-color: rgba(120, 153, 176, 0.34);
  background: rgba(96, 118, 134, 0.38);
}
.col-enabled :deep(.el-switch.is-checked .el-switch__core) {
  border-color: rgba(64, 158, 255, 0.66);
  background: #409eff;
}
.device-name-cell { display: grid; align-items: center; justify-items: center; text-align: center; }
.device-name-cell strong {
  display: block;
  overflow: hidden;
  color: #f3f8fd;
  font-size: 15px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.device-sn {
  color: #6d90a8;
  font-size: 11px;
  font-family: monospace;
}
.device-description {
  display: grid;
  justify-items: center;
  text-align: center;
}
.device-description span {
  display: -webkit-box;
  overflow: hidden;
  color: #a9c0d2;
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  padding: 0 10px;
  border: 1px solid rgba(235, 124, 133, 0.34);
  border-radius: 4px;
  background: rgba(142, 48, 62, 0.18);
  color: #ffabb5;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
}
.status-pill.is-online {
  border-color: rgba(92, 215, 154, 0.34);
  background: rgba(48, 154, 118, 0.18);
  color: #81efad;
}
.list-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: nowrap;
}
.list-actions :deep(.el-button) {
  width: auto;
  height: 34px;
  min-height: 34px;
  margin: 0;
  padding: 0 16px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 800;
}
.list-actions :deep(.test-action) { border-color: rgba(82, 178, 143, 0.46); color: #b9f1d8; background: rgba(30, 103, 78, 0.38); }
.list-actions :deep(.edit-action) { border-color: rgba(66, 164, 224, 0.50); color: #d5f0ff; background: rgba(29, 91, 133, 0.70); }
.list-actions :deep(.delete-action) { border-color: rgba(226, 88, 109, 0.46); color: #ffb1bd; background: rgba(128, 36, 54, 0.48); }
.list-actions :deep(.test-action:hover) { border-color: rgba(82, 178, 143, 0.70); color: #e3fff1; background: rgba(36, 123, 92, 0.52); }
.list-actions :deep(.edit-action:hover) { border-color: rgba(66, 164, 224, 0.72); color: #effaff; background: rgba(33, 107, 156, 0.82); }
.list-actions :deep(.delete-action:hover) { border-color: rgba(226, 88, 109, 0.68); color: #ffd5dd; background: rgba(144, 42, 62, 0.62); }
/* 与广播设备列表按钮样式严格对齐（!important 兜底，防止被 element-plus 默认样式覆盖） */
:global(.linkage-drone-page .list-actions .el-button.test-action) {
  border-color: rgba(82, 178, 143, .54) !important;
  color: #b9f1d8 !important;
  background: rgba(30, 103, 78, .42) !important;
}
:global(.linkage-drone-page .list-actions .el-button.edit-action) {
  border-color: rgba(66, 164, 224, .50) !important;
  color: #d5f0ff !important;
  background: rgba(29, 91, 133, .70) !important;
}
:global(.linkage-drone-page .list-actions .el-button.delete-action) {
  border-color: rgba(226, 88, 109, .46) !important;
  color: #ffb1bd !important;
  background: rgba(128, 36, 54, .48) !important;
}
:global(.linkage-drone-page .list-actions .el-button.test-action:hover) {
  border-color: rgba(82, 178, 143, .72) !important;
  color: #e3fff1 !important;
  background: rgba(36, 123, 92, .56) !important;
}
:global(.linkage-drone-page .list-actions .el-button.edit-action:hover) {
  border-color: rgba(66, 164, 224, .72) !important;
  color: #effaff !important;
  background: rgba(33, 107, 156, .82) !important;
}
:global(.linkage-drone-page .list-actions .el-button.delete-action:hover) {
  border-color: rgba(226, 88, 109, .68) !important;
  color: #ffd5dd !important;
  background: rgba(144, 42, 62, .62) !important;
}
.empty-list {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #7fa7bf;
  text-align: center;
}
.empty-list strong { color: #c8e9ff; font-size: 18px; }
.empty-list span { font-size: 14px; }
.list-pagination { min-height: 46px; justify-content: center; border-top: 1px solid rgba(149, 190, 220, 0.10); background: #092034; }
.list-pagination :deep(.btn-prev),
.list-pagination :deep(.btn-next),
.list-pagination :deep(.el-pager li) {
  min-width: 34px;
  height: 32px;
  margin: 0 3px;
  border: 1px solid rgba(70, 145, 190, 0.34);
  border-radius: 5px;
  color: #8fb6d1;
  background: #0b2238;
  font-weight: 700;
}
.list-pagination :deep(.el-pager li.is-active) { border-color: #4ba7e6; color: #fff; background: #3f95d7; }

/* ===== 测试弹窗 ===== */
.drone-test-dialog :deep(.el-dialog) {
  background: #0a1c2e;
  border: 1px solid rgba(93, 184, 225, 0.25);
  border-radius: 12px;
}
.drone-test-dialog :deep(.el-dialog__title) { color: #f3f8fd; font-weight: 800; }
.drone-test-dialog :deep(.el-dialog__header) { border-bottom: 1px solid rgba(93, 184, 225, 0.15); }
.test-layout { display: flex; flex-direction: column; gap: 10px; }

.test-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.test-device { display: flex; flex-direction: column; gap: 3px; }
.test-device strong { color: #f3f8fd; font-size: 16px; }
.test-device span { color: #7f9bb0; font-size: 12px; }
.test-wayline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-label { color: #a9c7de; font-size: 13px; font-weight: 700; }
.wayline-select { width: 240px; }
.test-body {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 10px;
  min-height: 420px;
}
.test-map {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  background: #030b12;
  border: 1px solid rgba(93, 184, 225, 0.17);
}
.map-image { width: 100%; height: 100%; object-fit: fill; display: block; }
.route-layer {
  position: absolute;
  inset: 0;
  z-index: 8;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}
.route-line {
  fill: none;
  stroke: #48d8ff;
  stroke-width: 0.7;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.2;
  vector-effect: non-scaling-stroke;
}
.route-line-glow {
  stroke: rgba(72, 216, 255, 0.28);
  stroke-width: 2.4;
  stroke-dasharray: none;
}
.route-point {
  fill: #eafcff;
  stroke: #48d8ff;
  stroke-width: 0.35;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.75));
}
.map-fixed-point {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  pointer-events: none;
}
.fixed-point-icon { width: 22px; height: 22px; object-fit: contain; }
.fixed-point-label {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: monospace;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}
.drone-marker { position: absolute; transform: translate(-50%, -50%); z-index: 10; pointer-events: none; }
.marker-pulse {
  position: absolute; top: 50%; left: 50%;
  width: 36px; height: 36px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(255, 93, 108, 0.3);
  animation: pulse 2s infinite;
}
.marker-icon {
  position: absolute; top: 50%; left: 50%;
  width: 28px; height: 28px;
  transform: translate(-50%, -50%);
  z-index: 2;
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.6));
}
@keyframes pulse {
  0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.9; }
  100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
}
.map-legend {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 14;
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(4, 16, 26, 0.78);
  font-size: 12px;
  color: #9fc3da;
}
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-icon-img { width: 14px; height: 14px; object-fit: contain; vertical-align: middle; }
.legend-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  background: #48d8ff;
  vertical-align: middle;
}

.test-video { display: flex; }
.video-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 10px;
  background: #040d16;
  border: 1px solid rgba(93, 184, 225, 0.17);
}
.video-stream { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #7fa7bf;
  text-align: center;
}
.video-placeholder strong { color: #c8e9ff; font-size: 16px; }
.video-placeholder span { font-size: 12px; }
/* ===== 航线大图弹窗（对标感知源“查看点位图”的图片方式） ===== */
:global(.wayline-map-dialog.el-dialog) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  border-radius: 8px;
  background: #07131a;
  box-shadow: 0 24px 60px rgba(0, 7, 18, 0.46);
}
:global(.wayline-map-dialog .el-dialog__header) {
  margin: 0;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(137, 174, 184, 0.14);
}
:global(.wayline-map-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-weight: 900;
}
:global(.wayline-map-dialog .el-dialog__body) {
  padding: 12px;
}
.wayline-map-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 2168 / 725;
  max-height: 84vh;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: #02080d;
}
.test-wayline-map-stage {
  height: 100%;
  min-height: 0;
  max-height: none;
  aspect-ratio: auto;
}
.wayline-map-stage > img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  filter: saturate(1.08) contrast(1.06) brightness(0.76);
}
.wayline-camera-region-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.wayline-region-fill { fill: rgba(67, 220, 255, .14); stroke: transparent; }
.wayline-region-halo {
  fill: none;
  stroke: rgba(81, 229, 255, .48);
  stroke-width: 13;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#wayline-camera-region-glow);
}
.wayline-region-line {
  fill: none;
  stroke: rgba(126, 238, 255, .96);
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#wayline-camera-region-glow);
}
.wayline-region-callout rect {
  fill: rgba(7, 42, 55, .86);
  stroke: rgba(126, 238, 255, .74);
  stroke-width: 1.5;
  filter: drop-shadow(0 0 8px rgba(72, 216, 255, .5));
}
.wayline-region-callout text {
  fill: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
  text-anchor: middle;
}
.wayline-map-svg {
  position: absolute;
  inset: 0;
  z-index: 16;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.wayline-map-route-hit {
  fill: none;
  stroke: rgba(0, 0, 0, .001);
  stroke-width: 14;
  stroke-linecap: round;
  stroke-linejoin: round;
  pointer-events: stroke;
  cursor: pointer;
}
.wayline-map-route {
  fill: none;
  stroke-width: 1;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2.2 1.3;
  vector-effect: non-scaling-stroke;
  pointer-events: stroke;
}
.wayline-map-route.route-glow {
  stroke-width: 3.8;
  stroke-dasharray: none;
  opacity: 0.4;
}
.wayline-map-route-group {
  pointer-events: auto;
  cursor: pointer;
}
.wayline-map-route-group.active .wayline-map-route {
  stroke-width: 1.7;
}
.wayline-map-route-group.active .wayline-map-route.route-glow {
  stroke-width: 5.2;
  opacity: 0.72;
}
.wayline-map-route.tone-0 { stroke: #48d8ff; }
.wayline-map-route.tone-1 { stroke: #ffd166; }
.wayline-map-point {
  fill: #eafcff;
  stroke: #48d8ff;
  stroke-width: 0.4;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.75));
  pointer-events: all;
}
.wayline-camera-point,
.wayline-landmark {
  position: absolute;
  /* 地标是可点击的最上层交互点，航线线条仍位于区域层之上。 */
  z-index: 20;
  appearance: none;
  -webkit-appearance: none;
  font-family: inherit;
}
.wayline-camera-point {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  margin: -14px 0 0 -14px;
  border: 2px solid rgba(255, 255, 255, .62);
  border-radius: 50%;
  color: #fff;
  background: #d93a4b;
  box-shadow: 0 0 0 8px rgba(217, 58, 75, .18), 0 0 16px rgba(217, 58, 75, .72);
  font: 900 14px/1 "Consolas", "Monaco", monospace;
  cursor: pointer;
}
.wayline-camera-point:hover,
.wayline-camera-point.active {
  width: 34px;
  height: 34px;
  margin: -17px 0 0 -17px;
  color: #041417;
  border-color: rgba(230, 250, 255, .92);
  background: #48d8ff;
  box-shadow: 0 0 0 10px rgba(72, 216, 255, .24), 0 0 24px rgba(72, 216, 255, .88);
}
.wayline-landmark {
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 92px;
  height: 92px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #e9faff;
  box-shadow: none;
  white-space: nowrap;
  cursor: default;
  transition: transform .2s ease;
}
.wayline-landmark::before {
  content: '';
  position: absolute;
  z-index: 0;
  top: 50%;
  left: 50%;
  width: 92px;
  height: 40px;
  transform: translate(-50%, -50%);
  border: 1px solid rgba(190, 249, 255, .72);
  border-radius: 50%;
  background: rgba(147, 239, 255, .72);
  box-shadow: inset 0 0 12px rgba(255, 255, 255, .42), 0 0 15px rgba(72, 216, 255, .68);
}
.wayline-landmark > * { position: relative; z-index: 1; }
.wayline-landmark-mark {
  position: relative;
  width: 68px;
  height: 68px;
  display: block;
  border: 2px solid rgba(88, 226, 255, .92);
  border-radius: 50%;
  background: radial-gradient(circle at 48% 35%, #154c61 0, #092d3d 52%, #031923 100%);
  box-shadow: 0 0 0 5px rgba(20, 140, 172, .24), 0 0 22px rgba(72, 216, 255, .92), 0 3px 8px rgba(0, 0, 0, .75);
}
.wayline-landmark-mark::before {
  content: '';
  position: absolute;
  top: 9px;
  left: 50%;
  width: 24px;
  height: 24px;
  transform: translateX(-50%) rotate(-45deg);
  border: 3px solid #78eaff;
  border-radius: 50% 50% 50% 0;
  background: transparent;
  box-shadow: 0 0 8px rgba(72, 216, 255, .76);
}
.wayline-landmark-mark::after {
  content: '';
  position: absolute;
  top: 17px;
  left: 50%;
  width: 7px;
  height: 7px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: #b8f7ff;
  box-shadow: 0 0 0 2px rgba(226, 252, 255, .82), 0 0 8px rgba(72, 216, 255, .92);
}
.wayline-landmark > span:not(.wayline-landmark-mark) {
  position: absolute;
  top: 53px;
  left: 50%;
  z-index: 2;
  transform: translateX(-50%);
  font-size: 13px;
  font-weight: 900;
  color: #f3fdff;
  text-shadow: 0 1px 4px rgba(0, 0, 0, .96);
}
.wayline-landmark:hover {
  transform: translate(-50%, -50%) scale(1.16);
}
.legend-route-swatch {
  width: 14px;
  height: 14px;
  display: inline-block;
  border-radius: 50%;
  border: 2px solid #aaf5ff;
  background: #16a8d2;
  box-shadow: 0 0 8px rgba(72, 216, 255, .7);
}
.legend-route-swatch.airport {
  border-color: #fff0b0;
  background: #d89b2b;
  box-shadow: 0 0 8px rgba(255, 209, 102, .72);
}
.legend-route-swatch.waypoint { background: #16a8d2; }
.wayline-map-fixed-point {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  pointer-events: none;
}
.wayline-map-fixed-point img { width: 22px; height: 22px; object-fit: contain; }
.wayline-map-fixed-point span {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: monospace;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}
.wayline-map-legend {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 14;
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(4, 16, 26, 0.78);
  font-size: 12px;
  color: #9fc3da;
}
.wayline-map-legend .legend-item { display: inline-flex; align-items: center; gap: 5px; }
.wayline-map-legend .legend-icon-img { width: 14px; height: 14px; object-fit: contain; vertical-align: middle; }
.wayline-map-legend .legend-line {
  display: inline-block;
  width: 20px;
  height: 2px;
  vertical-align: middle;
}
.wayline-map-legend .legend-line.tone-0 { background: #48d8ff; }
.wayline-map-legend .legend-line.tone-1 { background: #ffd166; }

/* ===== 编辑无人机弹窗 ===== */
.drone-edit-dialog :deep(.el-dialog) {
  background: #1d426a;
  border: 1px solid rgba(97, 167, 214, .40);
  border-radius: 10px;
}
.drone-edit-dialog :deep(.el-dialog__title) { color: #eef7ff; font-size: 22px; font-weight: 800; }
.drone-edit-dialog :deep(.el-form-item__label) { color: #e2f0fb !important; font-weight: 700; }
.drone-edit-dialog :deep(.el-input__wrapper),
.drone-edit-dialog :deep(.el-textarea__inner) {
  background: #092034;
  box-shadow: inset 0 0 0 1px rgba(36, 128, 176, .46);
  color: #f4fbff;
}
.drone-edit-dialog :deep(.el-input__inner),
.drone-edit-dialog :deep(.el-textarea__inner) { color: #f4fbff; }

/* 响应式 */
@media (max-width: 1280px) {
  .test-body { grid-template-columns: 1fr 1fr; }
}
</style>
