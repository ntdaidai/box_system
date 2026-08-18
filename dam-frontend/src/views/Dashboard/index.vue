<template>
  <main class="bigscreen-page">
    <div class="ambient-grid"></div>

    <section class="screen-grid">
      <aside class="left-column">
        <section class="screen-panel today-panel">
          <div class="panel-heading">
            <h2>今日态势</h2>
          </div>
          <div class="today-strip-list">
            <article
              v-for="metric in todayMetrics"
              :key="metric.key"
              class="today-card"
              :class="[metric.tone, metric.kind, { 'has-breakdown': metric.breakdown }]"
            >
              <template v-if="metric.kind === 'category'">
                <span class="metric-icon" aria-hidden="true">
                  <component :is="metric.icon" />
                </span>
                <span class="metric-label">{{ metric.label }}</span>
                <strong class="metric-value">{{ metric.value }}<small>次</small></strong>
                <em class="metric-compare">
                  <span>较昨日</span>
                  <i :class="metric.trend.tone">
                    <span class="metric-trend-arrow">{{ metric.trend.icon }}</span>
                    <span class="metric-trend-value">{{ metric.trend.delta }}</span>
                  </i>
                </em>
              </template>
              <template v-else>
                <div class="handling-title">
                  <span class="metric-icon" aria-hidden="true">
                    <component :is="metric.icon" />
                  </span>
                  <span class="metric-label">{{ metric.label }}</span>
                </div>
                <div class="metric-breakdown">
                  <span v-for="item in metric.breakdown" :key="item.key">
                    <em>{{ item.label }}</em>
                    <strong>{{ item.value }}<small>次</small></strong>
                    <b>
                      较昨日
                      <i :class="item.trend.tone">
                        <span class="metric-trend-arrow">{{ item.trend.icon }}</span>
                        <span class="metric-trend-value">{{ item.trend.delta }}</span>
                      </i>
                    </b>
                  </span>
                </div>
              </template>
            </article>
          </div>
        </section>

        <section class="screen-panel risk-panel">
          <div class="panel-heading">
            <h2>风险分布</h2>
            <div class="risk-switch">
              <button
                v-for="item in riskModes"
                :key="item.key"
                :class="{ active: activeRiskModeKey === item.key }"
                @click="handleRiskModeClick(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div class="risk-showcase">
            <div class="risk-chart-wrap">
              <div ref="riskChartRef" class="risk-main-chart echarts-chart"></div>
              <div class="risk-center">
                <strong>{{ formatNumber(activeRiskCount) }}</strong>
                <span :class="`risk-level-${activeRiskLevel.key}`">{{ activeRiskLevel.shortLabel }}</span>
              </div>
            </div>
            <div class="risk-summary">
              <span>{{ activeRiskMode.label }}</span>
              <strong :class="`risk-level-${activeRiskLevel.key}`">{{ activeRiskLevel.label }}</strong>
              <em>
                {{ activeRiskMode.compareLabel }}
                <b :class="activeRiskTrend.tone">{{ activeRiskTrend.icon }} {{ activeRiskTrend.delta }}</b>
              </em>
            </div>
          </div>
        </section>

        <section class="screen-panel trend-panel">
          <div class="panel-heading">
            <h2>安全事件记录</h2>
            <div class="segmented">
              <button
                v-for="item in trendModes"
                :key="item.key"
                :class="{ active: trendMode === item.key }"
                @click="trendMode = item.key"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
          <div class="trend-legend">
            <span @mouseenter="onTrendLegendEnter('人员入侵')" @mouseleave="onTrendLegendLeave"><i class="person"></i>人员入侵</span>
            <span @mouseenter="onTrendLegendEnter('船只捕鱼')" @mouseleave="onTrendLegendLeave"><i class="boat"></i>船只捕鱼</span>
            <span @mouseenter="onTrendLegendEnter('自然灾害')" @mouseleave="onTrendLegendLeave"><i class="disaster"></i>自然灾害</span>
            <span @mouseenter="onTrendLegendEnter('极端天气')" @mouseleave="onTrendLegendLeave"><i class="weather"></i>极端天气</span>
          </div>
          <div ref="trendChartRef" class="line-chart echarts-chart" aria-label="人员入侵和船只捕鱼安全事件记录"></div>
        </section>
      </aside>

      <main class="center-column">
        <section class="map-panel">
          <div
            ref="mapBoardRef"
            class="map-board"
            @wheel.prevent="handleMapWheel"
            @pointerdown="startMapDrag"
            @pointermove="moveMapDrag"
            @pointerup="endMapDrag"
            @pointercancel="endMapDrag"
          >
            <div class="map-scene" :style="mapSceneStyle">
              <img class="satellite-image" src="/dam.png" alt="大藤峡水电站卫星地图" />
              <div class="map-shade"></div>
              <svg
                v-if="selectedRegionPath"
                class="camera-region-layer"
                viewBox="0 0 2168 725"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <defs>
                  <filter id="selected-region-glow" x="-14%" y="-18%" width="128%" height="136%">
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
                <path
                  class="selected-region selected-region-fill"
                  :class="selectedGroup.type"
                  :d="selectedRegionPath"
                />
                <path
                  class="selected-region selected-region-halo"
                  :class="selectedGroup.type"
                  :d="selectedRegionPath"
                />
                <path
                  class="selected-region selected-region-line"
                  :class="selectedGroup.type"
                  :d="selectedRegionPath"
                />
                <path
                  class="selected-region selected-region-scan"
                  :class="selectedGroup.type"
                  :d="selectedRegionPath"
                />
                <g
                  v-if="selectedRegionCallout"
                  class="region-callout"
                  :class="selectedGroup.type"
                >
                  <path class="callout-line" :d="selectedRegionCallout.linePath" />
                  <rect
                    class="callout-box"
                    :x="selectedRegionCallout.x"
                    :y="selectedRegionCallout.y"
                    :width="selectedRegionCallout.width"
                    :height="selectedRegionCallout.height"
                    rx="4"
                    ry="4"
                  />
                  <text
                    class="callout-text"
                    :x="selectedRegionCallout.textX"
                    :y="selectedRegionCallout.textY"
                  >
                    {{ selectedRegionCallout.label }}
                  </text>
                </g>
              </svg>
              <button
                v-for="point in cameraPoints"
                :key="point.no"
                class="camera-point"
                :class="{ active: selectedPointNo === point.no }"
                :style="{ left: `${point.x}%`, top: `${point.y}%` }"
                :title="`${point.no}号摄像头`"
                @pointerdown.stop
                @click.stop="selectPoint(point.no)"
              >
                <span>{{ point.no }}</span>
              </button>
            </div>
            <aside class="map-rank-card" aria-label="区域告警排行" @pointerdown.stop>
              <div class="map-rank-head">
                <span>区域告警排行</span>
                <em>TOP 5</em>
              </div>
              <ol class="map-rank-list">
                <li v-for="item in alarmRegionRanking" :key="item.key">
                  <i>{{ item.rank }}</i>
                  <div class="map-rank-main">
                    <div>
                      <span>{{ item.name }}</span>
                      <strong>{{ item.count }}<small>次</small></strong>
                    </div>
                    <b><em :style="{ width: `${item.percent}%` }"></em></b>
                  </div>
                </li>
              </ol>
            </aside>
            <div class="map-controls" aria-label="地图控制" @pointerdown.stop>
              <div class="zoom-cluster" :class="{ visible: showZoomTrack }">
                <button type="button" class="zoom-button" title="放大" @click.stop="zoomMapBy(1.18)">+</button>
                <div
                  class="zoom-track"
                  :style="zoomTrackStyle"
                  role="slider"
                  :aria-valuemin="Math.round(minMapScale * 100)"
                  :aria-valuemax="Math.round(maxMapScale * 100)"
                  :aria-valuenow="Math.round(mapScale * 100)"
                  aria-label="地图缩放"
                  @pointerdown.stop.prevent="startZoomDrag"
                >
                  <span class="zoom-track-line">
                    <i></i>
                  </span>
                </div>
                <button type="button" class="zoom-button" title="缩小" @click.stop="zoomMapBy(0.84)">−</button>
              </div>
              <button type="button" class="locate" title="定位当前点位" @click.stop="focusSelectedMapPoint" aria-label="定位当前点位">
                <span></span>
              </button>
            </div>
          </div>
        </section>

        <section class="selected-detail">
          <div class="selected-title">
            <div>
              <span>当前监测点位</span>
              <h2>{{ selectedPoint.no }}号摄像头 · {{ selectedGroup.typeLabel }}</h2>
            </div>
          </div>
          <div class="analytics-grid">
            <article class="analytics-card hourly-card">
              <div class="sub-heading">
                <h3>告警记录</h3>
                <div class="mini-segmented">
                  <button
                    v-for="item in trendModes"
                    :key="item.key"
                    :class="{ active: detailTrendMode === item.key }"
                    @click="detailTrendMode = item.key"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>
              <div ref="hourlyChartRef" class="bar-chart echarts-chart"></div>
            </article>

            <article class="analytics-card composition-card">
              <div class="sub-heading">
                <h3>风险构成</h3>
              </div>
              <div ref="compositionChartRef" class="risk-composition echarts-chart"></div>
            </article>

            <article class="analytics-card disposal-card">
              <div class="sub-heading">
                <h3>告警状态</h3>
              </div>
              <div class="disposal-body">
                <div class="disposal-ring-wrap">
                  <div ref="disposalChartRef" class="disposal-ring echarts-chart"></div>
                  <div class="disposal-center">
                    <strong>{{ formatNumber(disposalStats.total) }}</strong>
                    <span>告警总数</span>
                  </div>
                </div>
                <div class="disposal-list">
                  <span><i class="handled"></i>已处置 {{ disposalStats.handled }}</span>
                  <span><i class="processing"></i>处理中 {{ disposalStats.processing }}</span>
                  <span><i class="pending"></i>未处置 {{ disposalStats.pending }}</span>
                </div>
              </div>
            </article>
          </div>
        </section>
      </main>

      <aside class="right-column">
        <section
          class="screen-panel progress-panel"
          @mouseenter="handleProgressPanelEnter"
          @mouseleave="handleProgressPanelLeave"
        >
          <div class="panel-heading progress-heading">
            <h2>实时告警进度</h2>
            <div class="clock-block progress-clock">
              <span>{{ currentShortDate }} {{ currentWeek }}</span>
              <strong>{{ currentTime }}</strong>
            </div>
          </div>
          <div v-if="displayedPriorityAlert" class="priority-summary">
            <div class="priority-topline">
              <strong :class="riskClass(displayedPriorityAlert)">{{ riskLabel(displayedPriorityAlert) }}</strong>
              <button type="button" class="detail-button" @click.stop="handleAlarmDetailClick">查看详情</button>
            </div>
            <span>{{ alertTitle(displayedPriorityAlert) }}</span>
            <small>
              <i>开始 {{ formatDateTime(displayedPriorityAlert.started_at || displayedPriorityAlert.last_observed_at) }}</i>
              <b :class="statusClass(displayedPriorityAlert.status)">{{ statusLabel(displayedPriorityAlert.status) }}</b>
            </small>
          </div>
          <div v-else class="priority-summary empty">
            <span>当前无未处理告警</span>
          </div>
          <div v-if="!displayedPriorityAlert" class="alarm-idle flow-idle-visual">
            <div class="idle-orbit">
              <span></span>
              <i></i>
            </div>
            <div class="idle-copy">
              <strong>告警监听中</strong>
              <span>告警触发后将在此同步处置进度</span>
            </div>
          </div>
          <ol
            ref="flowTimelineRef"
            class="progress-timeline flow-timeline"
            :class="{ idle: !displayedPriorityAlert }"
            @wheel.passive="handleFlowTimelineUserScroll"
            @touchmove.passive="handleFlowTimelineUserScroll"
          >
            <li
              v-for="item in alarmFlowSteps"
              :key="item.key"
              :class="[item.tone, item.state, item.connectorClass, { active: item.active }]"
            >
              <i class="flow-node-icon">
                <component :is="item.icon" />
              </i>
              <article>
                <header>
                  <strong :title="item.label">{{ item.label }}</strong>
                  <time>{{ item.time }}</time>
                </header>
                <p :title="item.message">{{ item.message }}</p>
                <ul v-if="item.active && item.logs.length" class="flow-node-logs">
                  <li v-for="log in item.logs" :key="log.key">
                    <b :title="log.title">{{ log.title }}</b>
                    <span :title="log.message">{{ log.message }}</span>
                  </li>
                </ul>
                <footer>
                  <span>{{ item.operator }}</span>
                  <b :class="item.statusClass">{{ item.statusText }}</b>
                </footer>
              </article>
            </li>
          </ol>
        </section>

        <section class="screen-panel device-panel" :class="{ warning: deviceOffline > 0 }">
          <div class="panel-heading">
            <h2>设备状态</h2>
          </div>
          <div class="device-state">
            <div class="device-gauge-wrap">
              <div ref="deviceChartRef" class="device-ring echarts-chart"></div>
              <div class="device-center">
                <strong>{{ deviceRate }}%</strong>
                <span>在线率</span>
              </div>
            </div>
            <div class="device-counts">
              <div class="device-count-row">
                <article class="online">
                  <span>在线</span>
                  <strong>{{ deviceOnline }}</strong>
                </article>
                <article class="offline">
                  <span>离线</span>
                  <strong>{{ deviceOffline }}</strong>
                </article>
              </div>
              <p class="device-report" :class="{ warning: deviceOffline > 0 }">{{ deviceReportText }}</p>
            </div>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { BellFilled, CircleCheckFilled, Connection, Pouring, Promotion, Ship, UserFilled, WarningFilled } from '@element-plus/icons-vue'
import { getUnifiedSafetyEventDetail, getUnifiedSafetyEventStatistics, getUnifiedSafetyEvents } from '@/api/integration'
import { getDeviceStatus } from '@/api/sensor'
import { getCameraList } from '@/api/camera'

const cameraPoints = [
  { no: 1, cameraId: 4, dataSourceId: 8, x: 17.3410, y: 40.8304, areaType: 'boatForbidden', regionKey: 'boat-1' },
  { no: 2, x: 7.3988, y: 15.2249, areaType: 'boatForbidden', regionKey: 'boat-2' },
  { no: 3, cameraId: 6, dataSourceId: 10, x: 41.8497, y: 74.0484, areaType: 'boatForbidden', regionKey: 'boat-3' },
  { no: 4, x: 47.3988, y: 38.0623, areaType: 'boatForbidden', regionKey: 'boat-4' },
  { no: 5, x: 49.2486, y: 38.0623, areaType: 'boatForbidden', regionKey: 'boat-5' },
  { no: 6, x: 66.3584, y: 52.5952, areaType: 'boatForbidden', regionKey: 'boat-6' },
  { no: 7, x: 68.2081, y: 52.5952, areaType: 'boatForbidden', regionKey: 'boat-7' },
  { no: 8, x: 57.3410, y: 75.4325, areaType: 'boatForbidden', regionKey: 'boat-8' },
  { no: 9, cameraId: 1, dataSourceId: 6, x: 91.7919, y: 24.2215, areaType: 'personForbidden', regionKey: 'person-9' },
]

const regionGroups = [
  { key: 'boat-1', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-3', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-4', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-5', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-6', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-7', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'boat-8', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
  { key: 'person-9', type: 'personForbidden', typeLabel: '人员禁入区', category: 'PERSON_SAFETY' },
  { key: 'boat-2', type: 'boatForbidden', typeLabel: '禁船区', category: 'ILLEGAL_FISHING' },
]

const cameraRegionPaths = {
  'boat-1': 'M371 317 L297 320 L259 324 L230 336 L191 363 L176 386 L179 425 L179 453 L181 487 L178 536 L200 549 L214 554 L231 554 L244 557 L262 556 L272 560 L295 557 L298 558 L327 560 L351 567 L372 570 L374 577 L383 583 L395 581 L408 578 L422 576 L436 571 L449 569 L463 561 L477 555 L489 552 L502 553 L511 546 L521 535 L524 521 L540 510 L538 492 L542 483 L539 466 L539 450 L538 433 L541 425 L542 406 L542 391 L539 380 L539 368 L537 358 L536 347 L531 340 L524 334 L514 332 L494 330 L470 339 L448 339 L427 343 L416 339 Z',
  'boat-2': 'M105 161 L134 169 L189 180 L247 191 L286 196 L307 201 L312 213 L304 222 L300 231 L294 242 L276 260 L260 263 L222 264 L188 256 L162 252 L130 241 L121 236 L110 231 L98 228 L96 212 L84 208 L76 199 L78 191 L84 177 Z',
  'boat-3': 'M847 460 L831 450 L830 424 L972 423 L1032 430 L1051 456 L1047 477 L1044 504 L1030 518 L1024 525 L927 544 L856 533 L852 523 L844 524 Z',
  'boat-4': 'M844 255 L847 296 L831 304 L829 413 L867 415 L968 415 L1031 422 L1043 405 L1046 376 L1044 355 L1043 335 L1038 319 L1039 302 L1033 291 L1006 276 L952 262 L928 257 Z',
  'boat-5': 'M1058 300 L1053 328 L1054 339 L1054 360 L1053 376 L1053 395 L1051 413 L1066 428 L1089 437 L1136 439 L1226 447 L1256 442 L1258 435 L1266 416 L1274 393 L1276 379 L1276 364 L1272 358 L1221 351 L1194 346 L1159 337 Z',
  'boat-6': 'M1439 335 L1383 352 L1367 353 L1355 361 L1343 365 L1332 368 L1318 362 L1299 361 L1288 361 L1283 379 L1282 396 L1279 415 L1279 436 L1279 445 L1279 466 L1283 483 L1283 495 L1286 510 L1296 514 L1304 516 L1318 510 L1334 512 L1367 508 L1367 497 L1390 486 L1398 488 L1424 476 L1432 468 L1441 471 L1464 457 Z',
  'boat-7': 'M1447 335 L1576 287 L1617 282 L1649 283 L1730 280 L1749 271 L1778 271 L1792 263 L1799 278 L1804 299 L1812 330 L1809 360 L1809 374 L1798 385 L1781 393 L1671 406 L1589 415 L1519 444 L1514 441 L1474 450 Z',
  'boat-8': 'M1273 520 L1259 521 L1230 526 L1193 540 L1178 541 L1165 530 L1147 545 L1049 523 L1049 513 L1051 498 L1054 486 L1055 467 L1061 456 L1073 445 L1090 444 L1126 445 L1165 451 L1199 452 L1224 454 L1249 456 L1261 453 L1269 461 L1274 479 L1279 503 L1280 517 Z',
  'person-9': 'M2127 373 L2108 370 L2104 375 L2084 378 L2066 375 L2030 377 L1984 376 L1944 378 L1915 379 L1897 381 L1872 384 L1843 385 L1836 385 L1826 389 L1823 398 L1824 408 L1838 418 L1877 412 L1898 408 L1922 411 L1944 415 L1974 419 L2005 422 L2025 412 L2041 409 L2056 407 L2066 410 L2088 410 L2104 408 L2121 410 L2134 406 L2142 393 L2141 381 L2142 373 Z',
}

const riskModes = [
  { key: 'today', label: '今日', compareLabel: '较昨日' },
  { key: 'week', label: '本周', compareLabel: '较上周' },
  { key: 'month', label: '本月', compareLabel: '较上月' },
]

const riskLevels = [
  { key: 'LOW', label: '低风险', shortLabel: '低风险' },
  { key: 'MEDIUM', label: '中风险', shortLabel: '中风险' },
  { key: 'HIGH', label: '高风险', shortLabel: '高风险' },
]

const todayMetricIcons = {
  person: markRaw(UserFilled),
  boat: markRaw(Ship),
  disaster: markRaw(Pouring),
  other: markRaw(BellFilled),
  handled: markRaw(CircleCheckFilled),
  unhandled: markRaw(WarningFilled),
}

const todayMetricTones = {
  person: 'warning',
  boat: 'boat',
  disaster: 'storm',
  other: 'purple',
}

const alarmFlowDefinitions = [
  { key: 'trigger', label: '事件触发', idleText: '等待事件触发', icon: markRaw(WarningFilled), logTypes: ['TRIGGER', 'RISK_CHANGE'], tone: 'is-primary' },
  { key: 'route', label: '智能路由', idleText: '等待匹配处置流程', icon: markRaw(Promotion), logTypes: ['DAM_WORKFLOW', 'WORKFLOW'], tone: 'is-warning' },
  { key: 'linkage', label: '联动处理', idleText: '等待联动动作执行', icon: markRaw(Connection), logTypes: ['ACTION', 'MANUAL', 'REPORT'], tone: 'is-success' },
  { key: 'archive', label: '闭环归档', idleText: '等待闭环归档', icon: markRaw(CircleCheckFilled), logTypes: ['RESOLVE'], tone: 'is-info' },
]

const trendModes = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'year', label: '今年' },
]

const riskColors = { LOW: '#38D59C', MEDIUM: '#FFB648', HIGH: '#FF5B68' }
const chartTextColor = '#8fc8f2'
const chartGridColor = 'rgba(143, 200, 242, .16)'
// 大屏图表文字随视口宽度缩放：笔记本（vw≈1707）取基准值，大屏显示器放大，上限约 1.25 倍
const rfs = (base) => {
  const vw = Math.max(window.innerWidth || 0, 1)
  return Math.round(base * Math.min(1.25, Math.max(1, vw / 1707)))
}
const chartTooltip = {
  appendToBody: true,
  confine: true,
  enterable: false,
  className: 'bigscreen-chart-tooltip',
  backgroundColor: 'rgba(2, 14, 28, .96)',
  borderColor: 'rgba(67, 200, 255, .36)',
  textStyle: { color: '#dff5ff', fontSize: rfs(13) },
  extraCssText: 'max-width:240px;white-space:normal;word-break:break-word;border-radius:8px;box-shadow:0 10px 28px rgba(0,0,0,.28);z-index:99999;',
}
const router = useRouter()
const mapFocusScale = 1.38
const maxMapScale = 4
const selectedPointNo = ref(9)
const activeRiskModeKey = ref('today')
const riskFocusIndex = ref(2)
const trendMode = ref('today')
const detailTrendMode = ref('today')
const currentDate = ref('--')
const currentTime = ref('--:--:--')
const currentWeek = ref('--')
const loading = ref(false)
const eventStats = ref({})
const events = ref([])
const priorityDetail = ref({ id: null, timeline: [] })
const displayedPriorityAlert = ref(null)
const deviceStatus = ref({})
const cameraSummary = ref({ online: 0, total: 0 })
const mapBoardRef = ref(null)
const riskChartRef = ref(null)
const trendChartRef = ref(null)
const hourlyChartRef = ref(null)
const compositionChartRef = ref(null)
const disposalChartRef = ref(null)
const deviceChartRef = ref(null)
const flowTimelineRef = ref(null)
const mapBaseSize = ref({ width: 0, height: 0 })
const mapScale = ref(1)
const mapOffset = ref({ x: 120, y: 0 })
const minMapScale = ref(1)
const showZoomTrack = ref(false)
const progressPanelHovered = ref(false)
const flowTimelineUserScrolled = ref(false)
const chartInstances = new Map()

const mapDragState = {
  active: false,
  moved: false,
  startX: 0,
  startY: 0,
  startOffsetX: 0,
  startOffsetY: 0,
}

const zoomDragState = {
  active: false,
}

let clockTimer
let refreshTimer
let riskTimer
let riskResumeTimer
let zoomTrackTimer
let displayedAlertClearTimer
let displayedAlertClearId = null
let mapResizeObserver
let currentPriorityDetailId = null
let mapInitialFocused = false
let fetchDataInFlight = false
const completedAlertVisibleMs = 5000

const weekLabels = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const selectedPoint = computed(() => cameraPoints.find((point) => point.no === selectedPointNo.value) || cameraPoints[0])
const selectedGroup = computed(() => regionGroups.find((group) => group.key === selectedPoint.value.regionKey) || regionGroups[0])
const selectedCameraId = computed(() => Number(selectedPoint.value.cameraId || 0) || null)
const selectedCameraDataSourceId = computed(() => Number(selectedPoint.value.dataSourceId || 0) || null)
const selectedRegionPath = computed(() => smoothClosedPath(cameraRegionPaths[selectedGroup.value.key]))
const selectedRegionCallout = computed(() => regionCalloutForRegion(selectedGroup.value.key, selectedPoint.value.no))
const activeRiskLevel = computed(() => riskLevels[riskFocusIndex.value] || riskLevels[0])
const activeRiskMode = computed(() => riskModes.find((mode) => mode.key === activeRiskModeKey.value) || riskModes[0])
const currentShortDate = computed(() => currentDate.value && currentDate.value !== '--' ? currentDate.value.slice(5) : '--')
const mapSceneStyle = computed(() => ({
  width: `${mapBaseSize.value.width}px`,
  height: `${mapBaseSize.value.height}px`,
  transform: `translate3d(-50%, -50%, 0) translate3d(${mapOffset.value.x}px, ${mapOffset.value.y}px, 0) scale(${mapScale.value})`,
}))
const zoomTrackStyle = computed(() => {
  const range = Math.max(maxMapScale - minMapScale.value, 0.01)
  const progress = Math.max(0, Math.min(1, (mapScale.value - minMapScale.value) / range))
  return {
    '--zoom-progress': `${progress * 100}%`,
    '--zoom-thumb-top': `${(1 - progress) * 100}%`,
  }
})

const todayEvents = computed(() => eventsInWindow('today'))
const yesterdayEvents = computed(() => eventsInWindow('yesterday'))

const todayMetrics = computed(() => {
  const today = todayEvents.value
  const yesterday = yesterdayEvents.value
  const todayHandled = today.filter(isHandled)
  const yesterdayHandled = yesterday.filter(isHandled)
  const todayUnhandled = today.filter(isEventUnhandled)
  const yesterdayUnhandled = yesterday.filter(isEventUnhandled)
  return [
    buildTodayMetric('person', '人员告警', today, yesterday),
    buildTodayMetric('boat', '船只告警', today, yesterday),
    buildTodayMetric('disaster', '自然灾害告警', today, yesterday),
    buildTodayMetric('other', '极端天气告警', today, yesterday),
    buildHandlingMetric('handled', '已处理告警', todayHandled, yesterdayHandled, 'success'),
    buildHandlingMetric('unhandled', '未处理告警', todayUnhandled, yesterdayUnhandled, 'danger'),
  ]
})

const riskDistribution = computed(() => {
  const build = (currentKey, previousKey) => {
    const current = eventsInWindow(currentKey)
    const previous = eventsInWindow(previousKey)
    const rows = ['LOW', 'MEDIUM', 'HIGH'].map((level) => {
      const count = current.filter((event) => riskLevel(event) === level).length
      const previousCount = previous.filter((event) => riskLevel(event) === level).length
      return {
        key: level,
        label: riskLevelLabel(level),
        count,
        trend: compareNumber(count, previousCount),
      }
    })
    return { rows, total: rows.reduce((sum, item) => sum + item.count, 0) }
  }
  return {
    today: build('today', 'yesterday'),
    week: build('week', 'lastWeek'),
    month: build('month', 'lastMonth'),
  }
})

const activeRiskStats = computed(() => riskDistribution.value[activeRiskModeKey.value] || { rows: [], total: 0 })
const activeRiskRow = computed(() => activeRiskStats.value.rows.find((row) => row.key === activeRiskLevel.value.key) || { count: 0, trend: compareNumber(0, 0) })
const activeRiskCount = computed(() => activeRiskRow.value.count || 0)
const activeRiskTrend = computed(() => activeRiskRow.value.trend || compareNumber(0, 0))

const intrusionTrend = computed(() => {
  const currentMode = trendMode.value
  const labels = trendLabels(currentMode)
  const person = trendBuckets(currentMode, 'person')
  const boat = trendBuckets(currentMode, 'boat')
  const disaster = trendBuckets(currentMode, 'disaster')
  const weather = trendBuckets(currentMode, 'weather')
  return {
    labels,
    person,
    boat,
    disaster,
    weather,
  }
})

const selectedCameraEvents = computed(() => {
  const cameraId = selectedCameraId.value
  const dataSourceId = selectedCameraDataSourceId.value
  if (!cameraId && !dataSourceId) return []
  return events.value.filter((event) => {
    const sourceType = String(event?.source_type || '').toLowerCase()
    if (sourceType !== 'camera') return false
    if (dataSourceId && event?.data_source_id != null) {
      return Number(event.data_source_id) === dataSourceId
    }
    return Number(event?.source_id) === cameraId
  })
})

const selectedSensorEventsForNine = computed(() => {
  if (selectedPointNo.value !== 9) return []
  return events.value.filter((event) => String(event?.source_type || '').toLowerCase() === 'sensor')
})

const selectedEvents = computed(() => [
  ...selectedCameraEvents.value,
  ...selectedSensorEventsForNine.value,
])

const alarmRegionRanking = computed(() => {
  const rows = cameraPoints.map((point) => {
    const group = regionGroups.find((item) => item.key === point.regionKey)
    const count = eventsForCameraPoint(point).length
    return {
      key: point.regionKey,
      pointNo: point.no,
      name: `${point.no}号${group?.typeLabel || '监测区'}`,
      count,
    }
  })
    .sort((a, b) => b.count - a.count || a.pointNo - b.pointNo)
    .slice(0, 5)
  const max = Math.max(...rows.map((item) => item.count), 1)
  return rows.map((item, index) => ({
    ...item,
    rank: index + 1,
    percent: item.count ? Math.max(8, Math.round((item.count / max) * 100)) : 3,
  }))
})

const selectedData = computed(() => {
  const timeline = eventTimelineBuckets(selectedEvents.value, detailTrendMode.value)
  return {
    total: timeline.total.reduce((sum, value) => sum + value, 0),
    labels: timeline.labels,
    totalCounts: timeline.total,
    risk: timeline.risk,
  }
})

const riskCompositionData = computed(() => {
  const cameraSource = selectedCameraEvents.value
  const rows = [
    { name: '安全事件', events: cameraSource.filter((event) => ['person', 'boat'].includes(getOverviewCategory(event))) },
    { name: '自然灾害', events: cameraSource.filter((event) => getOverviewCategory(event) === 'disaster') },
    {
      name: '极端天气',
      events: [
        ...cameraSource.filter((event) => getOverviewCategory(event) === 'other'),
        ...selectedSensorEventsForNine.value,
      ],
    },
  ]
  return {
    labels: rows.map((row) => row.name),
    risk: ['LOW', 'MEDIUM', 'HIGH'].reduce((acc, level) => {
      acc[level] = rows.map((row) => {
        if (row.name === '自然灾害' && !row.events.length) return 0
        return row.events.filter((event) => riskLevel(event) === level).length
      })
      return acc
    }, {}),
  }
})

const disposalStats = computed(() => {
  const source = selectedEvents.value
  const total = source.length
  const handled = source.filter(isHandled).length
  const processing = source.filter((event) => event.status === 'PROCESSING').length
  const pending = Math.max(total - handled - processing, 0)
  return { total, handled, processing, pending }
})

const alarmFlowSteps = computed(() => {
  const rows = priorityDetail.value.timeline || []
  const alert = displayedPriorityAlert.value
  const grouped = alarmFlowDefinitions.map((definition) => {
    const logs = rows
      .filter((row) => definition.logTypes.includes(String(row.log_type || '').toUpperCase()))
      .map((row, index) => ({
        key: row.id || `${definition.key}-${row.create_time || row.created_at || index}`,
        title: row.title || logTypeLabel(row.log_type),
        status: String(row.status || '').toUpperCase(),
        statusText: timelineStatusLabel(row.status),
        message: row.message || row.action || row.title || '暂无处理说明',
        time: row.create_time || row.created_at,
        operator: operatorLabel(row.operator),
      }))
    return { definition, logs }
  })
  const hasAnyLog = grouped.some((item) => item.logs.length)
  const pendingIndex = grouped.findIndex((item) => item.logs.some((log) => ['PENDING', 'PROCESSING', 'RUNNING'].includes(log.status)))
  const failedIndex = grouped.findIndex((item) => item.logs.some((log) => ['FAILED', 'ERROR'].includes(log.status)))
  const firstEmptyIndex = grouped.findIndex((item) => !item.logs.length)
  const activeIndex = !alert
    ? -1
    : isHandled(alert)
      ? -1
      : failedIndex >= 0
      ? failedIndex
      : pendingIndex >= 0
        ? pendingIndex
        : firstEmptyIndex >= 0
          ? firstEmptyIndex
          : -1
  const flowEndIndex = !alert
    ? -1
    : activeIndex >= 0
      ? activeIndex
      : grouped.length

  return grouped.map(({ definition, logs }, index) => {
    const latest = logs[logs.length - 1]
    const hasLog = logs.length > 0
    const active = index === activeIndex
    const failed = logs.some((log) => ['FAILED', 'ERROR'].includes(log.status))
    const done = hasLog && !active && !failed
    const idle = !alert
    const state = idle ? 'idle' : failed ? 'failed' : active ? 'running' : done ? 'done' : 'pending'
    const fallbackMessage = alert
      ? index === 0
        ? (alert.summary || alertTitle(alert))
        : definition.idleText
      : definition.idleText
    const summaryMessage = done ? `已完成${definition.label}` : fallbackMessage
    const message = active || failed
      ? (latest?.message || fallbackMessage)
      : summaryMessage
    const connectorClass = !alert
      ? 'connector-idle'
      : index < flowEndIndex - 1
        ? 'connector-done'
        : index === flowEndIndex - 1
          ? 'connector-running'
          : 'connector-pending'
    return {
      key: definition.key,
      label: definition.label,
      icon: definition.icon,
      tone: failed ? 'is-failed' : definition.tone,
      state,
      connectorClass,
      active,
      logs,
      time: latest?.time ? formatDateTime(latest.time) : alert && index === 0 ? formatDateTime(alert.started_at || alert.last_observed_at) : '--',
      message,
      operator: latest?.operator || (hasAnyLog ? '系统自动' : '待机监听'),
      statusText: idle ? '待机' : failed ? '异常' : active ? '执行中' : done ? '已完成' : '未开始',
      statusClass: idle || !hasLog ? 'is-muted' : failed ? 'is-failed' : active ? 'is-processing' : 'is-success',
    }
  })
})

const deviceRows = computed(() => {
  const grouped = new Map()
  Object.entries(deviceStatus.value || {}).forEach(([key, item]) => {
    const groupKey = deviceGroupKey(key, item)
    if (groupKey === 'camera' && cameraSummary.value.total > 0) return
    const status = String(item?.status || '').toLowerCase()
    const onlineCount = Number(item?.online_count)
    const online = status === 'online' || onlineCount > 0
    const row = grouped.get(groupKey) || { key: groupKey, total: 0, online: 0 }
    row.total += 1
    if (online) row.online += 1
    grouped.set(groupKey, row)
  })
  const rows = Array.from(grouped.values())
  if (cameraSummary.value.total > 0 || Object.prototype.hasOwnProperty.call(deviceStatus.value, 'camera')) {
    const index = rows.findIndex((row) => row.key === 'camera')
    const camera = {
      key: 'camera',
      online: cameraSummary.value.online,
      total: cameraSummary.value.total || 1,
    }
    if (index >= 0) rows.splice(index, 1, camera)
    else rows.push(camera)
  }
  if (!rows.some((row) => row.key === 'agx')) {
    rows.push({ key: 'agx', total: 1, online: 1 })
  }
  return rows
})

const deviceOnline = computed(() => deviceRows.value.reduce((sum, item) => sum + item.online, 0))
const deviceTotal = computed(() => deviceRows.value.reduce((sum, item) => sum + item.total, 0))
const deviceOffline = computed(() => Math.max(deviceTotal.value - deviceOnline.value, 0))
const deviceRate = computed(() => deviceTotal.value ? Math.round((deviceOnline.value / deviceTotal.value) * 100) : 0)
const offlineDeviceNames = computed(() => deviceRows.value
  .filter((item) => item.total > item.online)
  .map((item) => deviceTypeLabel(item.key)))
const deviceReportText = computed(() => {
  if (!deviceTotal.value) return '暂无设备状态数据'
  if (!deviceOffline.value) return '所有设备正常运行'
  const names = offlineDeviceNames.value.length ? offlineDeviceNames.value.join('、') : '部分设备'
  return `${names}离线，请及时检查`
})

function buildTodayMetric(key, label, today, yesterday) {
  const matchMetric = (event) => {
    const category = getOverviewCategory(event)
    if (key === 'other') return category === 'other'
    return category === key
  }
  const value = today.filter(matchMetric).length
  const previous = yesterday.filter(matchMetric).length
  return {
    key,
    label,
    icon: todayMetricIcons[key],
    kind: 'category',
    value: formatNumber(value),
    tone: todayMetricTones[key] || 'purple',
    trend: compareNumber(value, previous),
  }
}

function buildHandlingMetric(key, label, today, yesterday, tone) {
  const todaySplit = splitDispositionMode(today)
  const yesterdaySplit = splitDispositionMode(yesterday)
  const yesterdayTotal = yesterday.length
  return {
    key,
    label,
    icon: todayMetricIcons[key],
    kind: 'handling',
    value: formatNumber(today.length),
    tone,
    breakdown: [
      {
        key: 'auto',
        label: '自动',
        value: formatNumber(todaySplit.auto),
        trend: compareNumber(todaySplit.auto, yesterdaySplit.auto),
      },
      {
        key: 'manual',
        label: '人工',
        value: formatNumber(todaySplit.manual),
        trend: compareNumber(todaySplit.manual, yesterdaySplit.manual),
      },
    ],
    trend: compareNumber(today.length, yesterdayTotal),
  }
}

function splitDispositionMode(rows) {
  return rows.reduce((acc, event) => {
    if (isManualDisposition(event)) acc.manual += 1
    else acc.auto += 1
    return acc
  }, { auto: 0, manual: 0 })
}

function isManualDisposition(event) {
  const text = [
    event?.handling_mode,
    event?.process_mode,
    event?.disposal_mode,
    event?.handler_type,
    event?.operator,
    event?.processor,
    event?.assignee,
    event?.assigned_to,
    event?.resolved_by,
    event?.dispatch_operator,
  ].filter(Boolean).join(' ').toLowerCase()
  if (/人工|手动|manual|user|admin|operator|staff|人员|人工处置/.test(text)) return true
  if (/自动|系统|auto|system|workflow|eca|model/.test(text)) return false
  return false
}

function eventsForCameraPoint(point) {
  const cameraId = Number(point?.cameraId || 0) || null
  const dataSourceId = Number(point?.dataSourceId || 0) || null
  const cameraEvents = !cameraId && !dataSourceId
    ? []
    : events.value.filter((event) => {
      if (String(event?.source_type || '').toLowerCase() !== 'camera') return false
      if (dataSourceId && event?.data_source_id != null) {
        return Number(event.data_source_id) === dataSourceId
      }
      return Number(event?.source_id) === cameraId
    })
  if (point?.no !== 9) return cameraEvents
  return [
    ...cameraEvents,
    ...events.value.filter((event) => String(event?.source_type || '').toLowerCase() === 'sensor'),
  ]
}

function getChart(el, key) {
  if (!el) return null
  let chart = chartInstances.get(key)
  if (!chart) {
    chart = echarts.init(el, null, {
      renderer: 'canvas',
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight, 1),
    })
    chartInstances.set(key, chart)
  }
  resizeChartToElement(chart, el)
  return chart
}

function resizeChartToElement(chart, el) {
  const width = Math.max(el?.clientWidth || 0, 1)
  const height = Math.max(el?.clientHeight || 0, 1)
  chart.resize({ width, height })
}

function renderRiskCharts() {
  const chart = getChart(riskChartRef.value, 'risk-distribution-main')
  if (!chart) return
  const rows = activeRiskStats.value.rows || []
  const total = rows.reduce((sum, row) => sum + row.count, 0)
  const activeDataIndex = rows.findIndex((row) => row.key === activeRiskLevel.value.key)
  const data = total
    ? rows.map((row) => ({
      name: row.label,
      value: row.count,
      itemStyle: {
        color: riskColors[row.key],
        opacity: .86,
      },
    }))
    : [{ name: '暂无数据', value: 1, itemStyle: { color: 'rgba(143, 200, 242, .16)' } }]
  chart.setOption({
    tooltip: { ...chartTooltip, trigger: 'item', formatter: '{b}<br/>{c} 次，占比 {d}%' },
    series: [{
      type: 'pie',
      radius: ['58%', '78%'],
      center: ['50%', '50%'],
      selectedOffset: 0,
      minAngle: total ? 5 : 360,
      padAngle: 1,
      avoidLabelOverlap: true,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: { borderColor: '#06182b', borderWidth: 1, borderRadius: 4 },
      emphasis: {
        scale: true,
        scaleSize: 5,
        focus: 'self',
        itemStyle: {
          opacity: 1,
          shadowBlur: 18,
          shadowOffsetY: 8,
          shadowColor: 'rgba(0, 0, 0, .38)',
        },
      },
      blur: {
        itemStyle: {
          opacity: .18,
        },
      },
      data,
    }],
  }, true)
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  if (total && activeDataIndex >= 0) {
    chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: activeDataIndex })
  }
}

function renderTrendChart() {
  const el = trendChartRef.value
  const chart = getChart(el, 'intrusion-trend')
  if (!chart) return
  chart.setOption({
    color: ['#ff6873', '#41c8ff', '#ffb648', '#38d59c'],
    tooltip: { ...chartTooltip, trigger: 'axis' },
    grid: { left: 28, right: 10, top: 16, bottom: 24 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: intrusionTrend.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: chartTextColor, fontSize: rfs(10), interval: 'auto', margin: 8 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: rfs(10) },
    },
    series: buildTrendSeries(),
  }, true)
}

// 折线 series 列表：人员入侵 / 船只捕鱼 / 自然灾害 / 极端天气
function buildTrendSeries() {
  return [
    buildLineSeries('人员入侵', intrusionTrend.value.person, '#ff6873'),
    buildLineSeries('船只捕鱼', intrusionTrend.value.boat, '#41c8ff'),
    buildLineSeries('自然灾害', intrusionTrend.value.disaster, '#ffb648'),
    buildLineSeries('极端天气', intrusionTrend.value.weather, '#38d59c'),
  ]
}

// 悬停图例：复刻"悬停线上"的效果——该线高亮加粗、其他线淡出、并显示对应数据点提示
function onTrendLegendEnter(name) {
  const chart = getChart(trendChartRef.value, 'intrusion-trend')
  if (!chart) return
  const index = buildTrendSeries().findIndex((item) => item.name === name)
  if (index < 0) return
  chart.dispatchAction({ type: 'highlight', seriesIndex: index })
  // 找到该系列最后一个非零数据点，在那里显示提示，与悬停线上的 tooltip 一致
  const key = ['person', 'boat', 'disaster', 'weather'][index]
  const data = (intrusionTrend.value[key] || []).filter((v) => typeof v === 'number')
  let dataIndex = Math.max(0, data.length - 1)
  for (let i = data.length - 1; i >= 0; i--) {
    if (data[i] > 0) {
      dataIndex = i
      break
    }
  }
  chart.dispatchAction({ type: 'showTip', seriesIndex: index, dataIndex })
}

function onTrendLegendLeave() {
  const chart = getChart(trendChartRef.value, 'intrusion-trend')
  if (!chart) return
  // 恢复全部系列的默认状态并隐藏提示
  buildTrendSeries().forEach((_, index) => {
    chart.dispatchAction({ type: 'downplay', seriesIndex: index })
  })
  chart.dispatchAction({ type: 'hideTip' })
}

function buildLineSeries(name, data, color) {
  return {
    name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    showSymbol: true,
    emphasis: {
      focus: 'series',
      scale: true,
      scaleSize: 2,
    },
    lineStyle: {
      width: 2.2,
      color,
      shadowBlur: 3,
      shadowColor: `${color}55`,
    },
    itemStyle: {
      color: '#061421',
      borderColor: color,
      borderWidth: 2,
      shadowBlur: 3,
      shadowColor: `${color}66`,
    },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: `${color}30` },
        { offset: 1, color: `${color}00` },
      ]),
    },
    data,
  }
}

function renderHourlyChart() {
  const chart = getChart(hourlyChartRef.value, 'selected-alarm-trend')
  if (!chart) return
  const counts = selectedData.value.totalCounts
  chart.setOption({
    color: ['#52dcff'],
    tooltip: {
      ...chartTooltip,
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(82, 220, 255, .34)', width: 1, type: 'dashed' },
      },
      formatter: (params) => {
        const row = Array.isArray(params) ? params[0] : params
        return `${row.axisValue}<br/><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#52dcff;margin-right:6px;"></span>告警次数&nbsp;&nbsp;<b>${row.value || 0} 次</b>`
      },
    },
    grid: { left: 34, right: 12, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: selectedData.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: chartTextColor, fontSize: rfs(10), interval: 'auto' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: rfs(10) },
    },
    series: [{
      name: '告警次数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: true,
      lineStyle: {
        width: 2.3,
        color: '#52dcff',
        shadowBlur: 3,
        shadowColor: 'rgba(82, 220, 255, .28)',
      },
      itemStyle: {
        color: '#061421',
        borderColor: '#52dcff',
        borderWidth: 2,
        shadowBlur: 4,
        shadowColor: 'rgba(82, 220, 255, .4)',
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(82, 220, 255, .24)' },
          { offset: 1, color: 'rgba(82, 220, 255, 0)' },
        ]),
      },
      emphasis: {
        scale: true,
        scaleSize: 2,
        itemStyle: {
          color: '#e8fbff',
          borderColor: '#52dcff',
          borderWidth: 2,
          shadowBlur: 8,
          shadowColor: 'rgba(82, 220, 255, .58)',
        },
      },
      data: counts,
    }],
  }, true)
}

function renderCompositionChart() {
  const chart = getChart(compositionChartRef.value, 'risk-composition')
  if (!chart) return
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value) => `${value} 次`,
    },
    legend: {
      right: 4,
      top: 0,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 12,
      textStyle: { color: chartTextColor, fontSize: rfs(12) },
      data: ['低风险', '中风险', '高风险'],
    },
    grid: { left: 36, right: 12, top: 30, bottom: 24 },
    xAxis: {
      type: 'category',
      data: riskCompositionData.value.labels,
      axisLine: { lineStyle: { color: chartGridColor } },
      axisTick: { show: false },
      axisLabel: { color: '#bdeaff', fontSize: rfs(12), interval: 0 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: chartGridColor, type: 'dashed' } },
      axisLabel: { color: chartTextColor, fontSize: rfs(10) },
    },
    series: ['LOW', 'MEDIUM', 'HIGH'].map((level) => ({
      name: riskLevelLabel(level),
      type: 'bar',
      stack: 'risk',
      barWidth: '38%',
      itemStyle: { color: riskColors[level], borderRadius: level === 'HIGH' ? [2, 2, 0, 0] : 0 },
      emphasis: { focus: 'series' },
      data: riskCompositionData.value.risk[level],
    })),
  }, true)
}

function renderDisposalChart() {
  const chart = getChart(disposalChartRef.value, 'disposal')
  if (!chart) return
  const stats = disposalStats.value
  // 每个扇区在"0 值占位"基础上增加真实面积，保证有值时不会比 0 值占位更小
  const visibleUnit = Math.max(stats.total * .018, .22)
  const data = [
    { name: '已处置', value: (stats.handled || 0) + visibleUnit, realValue: stats.handled, itemStyle: { color: '#38D59C' } },
    { name: '处理中', value: (stats.processing || 0) + visibleUnit, realValue: stats.processing, itemStyle: { color: '#FFB648' } },
    { name: '未处置', value: (stats.pending || 0) + visibleUnit, realValue: stats.pending, itemStyle: { color: '#FF5B68' } },
  ]
  if (!stats.total) data.splice(0, data.length, { name: '暂无数据', value: 1, realValue: 0, itemStyle: { color: 'rgba(143, 200, 242, .16)' } })
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'item',
      formatter: (params) => `${params.name}<br/>${params.data?.realValue ?? params.value} 次`,
    },
    series: [{
      type: 'pie',
      radius: ['72%', '86%'],
      center: ['50%', '50%'],
      padAngle: 1.5,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: { borderColor: '#06182b', borderWidth: 2, borderRadius: 8 },
      emphasis: { scale: true, scaleSize: 4 },
      data,
    }],
  }, true)
}

function renderDeviceChart() {
  const chart = getChart(deviceChartRef.value, 'device')
  if (!chart) return
  const total = Math.max(deviceTotal.value, 0)
  // 每个扇区在"0 值占位"基础上增加真实面积，保证有值时不会比 0 值占位更小
  const visibleUnit = total ? Math.max(total * .018, .18) : 0
  const onlineValue = total ? (deviceOnline.value || 0) + visibleUnit : 0
  const offlineValue = total ? (deviceOffline.value || 0) + visibleUnit : 0
  const data = total
    ? [
      { name: '在线', value: onlineValue, realValue: deviceOnline.value, itemStyle: { color: '#38D59C' } },
      { name: '离线', value: offlineValue, realValue: deviceOffline.value, itemStyle: { color: '#FF5B68' } },
    ]
    : [
      { name: '暂无数据', value: 1, realValue: 0, itemStyle: { color: 'rgba(143, 200, 242, .18)' } },
    ]
  chart.setOption({
    tooltip: {
      ...chartTooltip,
      trigger: 'item',
      formatter: (params) => `${params.name}<br/>${params.data?.realValue ?? params.value} 台`,
    },
    series: [{
      type: 'pie',
      radius: ['62%', '82%'],
      center: ['50%', '50%'],
      startAngle: 90,
      clockwise: true,
      avoidLabelOverlap: false,
      padAngle: 1.5,
      selectedOffset: 0,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: {
        borderColor: '#06182b',
        borderWidth: 1,
        borderRadius: 8,
      },
      emphasis: { scale: true, scaleSize: 2 },
      data,
    }],
  }, true)
}

function renderAllCharts() {
  renderRiskCharts()
  renderTrendChart()
  renderHourlyChart()
  renderCompositionChart()
  renderDisposalChart()
  renderDeviceChart()
}

function resizeCharts() {
  renderAllCharts()
}

function formatNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? String(Math.max(0, number)).padStart(2, '0') : '--'
}

function pointsFromPath(path) {
  if (!path) return []
  const matches = path.matchAll(/[-+]?\d*\.?\d+/g)
  const values = Array.from(matches, (item) => Number(item[0])).filter(Number.isFinite)
  const points = []
  for (let index = 0; index < values.length; index += 2) {
    if (Number.isFinite(values[index]) && Number.isFinite(values[index + 1])) {
      points.push({ x: values[index], y: values[index + 1] })
    }
  }
  return points
}

function smoothClosedPath(path) {
  const points = pointsFromPath(path)
  if (points.length < 3) return path || ''
  const tension = .68
  const commands = [`M${points[0].x} ${points[0].y}`]
  points.forEach((point, index) => {
    const previous = points[(index - 1 + points.length) % points.length]
    const current = point
    const next = points[(index + 1) % points.length]
    const afterNext = points[(index + 2) % points.length]
    const cp1 = {
      x: current.x + (next.x - previous.x) / 6 * tension,
      y: current.y + (next.y - previous.y) / 6 * tension,
    }
    const cp2 = {
      x: next.x - (afterNext.x - current.x) / 6 * tension,
      y: next.y - (afterNext.y - current.y) / 6 * tension,
    }
    commands.push(`C${roundPathValue(cp1.x)} ${roundPathValue(cp1.y)} ${roundPathValue(cp2.x)} ${roundPathValue(cp2.y)} ${next.x} ${next.y}`)
  })
  return `${commands.join(' ')} Z`
}

function roundPathValue(value) {
  return Math.round(value * 10) / 10
}

function regionCalloutForRegion(regionKey, pointNo) {
  const points = pointsFromPath(cameraRegionPaths[regionKey])
  if (!points.length) return null
  const imageWidth = 2168
  const imageHeight = 725
  const width = 188
  const height = 38
  const bounds = points.reduce((result, point) => ({
    minX: Math.min(result.minX, point.x),
    maxX: Math.max(result.maxX, point.x),
    minY: Math.min(result.minY, point.y),
    maxY: Math.max(result.maxY, point.y),
  }), {
    minX: Infinity,
    maxX: -Infinity,
    minY: Infinity,
    maxY: -Infinity,
  })
  const centerX = (bounds.minX + bounds.maxX) / 2
  const centerY = (bounds.minY + bounds.maxY) / 2
  const dotX = roundPathValue(centerX)
  const dotY = roundPathValue(centerY)
  const candidates = [
    { side: 'right', rawX: bounds.maxX + 54, rawY: centerY - height / 2 },
    { side: 'left', rawX: bounds.minX - width - 54, rawY: centerY - height / 2 },
    { side: 'above', rawX: centerX - width / 2, rawY: bounds.minY - height - 34 },
    { side: 'below', rawX: centerX - width / 2, rawY: bounds.maxY + 34 },
  ]
    .map((item) => {
      const x = Math.max(22, Math.min(imageWidth - width - 22, item.rawX))
      const y = Math.max(22, Math.min(imageHeight - height - 22, item.rawY))
      const rect = { x, y, width, height }
      const overlapCount = cameraPoints.filter((point) => pointOverlapsCallout(point, rect)).length
      const overflowPenalty = Math.abs(x - item.rawX) + Math.abs(y - item.rawY)
      const distance = Math.hypot((x + width / 2) - centerX, (y + height / 2) - centerY)
      return {
        ...item,
        x,
        y,
        score: overlapCount * 100000 + overflowPenalty * 80 + distance,
      }
    })
    .sort((a, b) => a.score - b.score)
  const selected = candidates[0]
  const { x, y } = selected
  const anchorX = selected.side === 'left' ? x + width : selected.side === 'right' ? x : x + width / 2
  const anchorY = selected.side === 'above' ? y + height : selected.side === 'below' ? y : y + height / 2
  const elbowX = selected.side === 'left'
    ? Math.min(bounds.minX - 20, anchorX)
    : selected.side === 'right'
      ? Math.max(bounds.maxX + 20, anchorX)
      : anchorX
  const elbowY = selected.side === 'above'
    ? Math.min(bounds.minY - 16, anchorY)
    : selected.side === 'below'
      ? Math.max(bounds.maxY + 16, anchorY)
      : anchorY
  return {
    x: roundPathValue(x),
    y: roundPathValue(y),
    width,
    height,
    dotX,
    dotY,
    textX: roundPathValue(x + width / 2),
    textY: roundPathValue(y + 24),
    label: `${pointNo}号摄像头监测区域`,
    linePath: `M${dotX} ${dotY} L${roundPathValue(elbowX)} ${roundPathValue(elbowY)} L${roundPathValue(anchorX)} ${roundPathValue(anchorY)}`,
  }
}

function pointOverlapsCallout(point, rect) {
  const x = point.x / 100 * 2168
  const y = point.y / 100 * 725
  const padding = 22
  return x >= rect.x - padding
    && x <= rect.x + rect.width + padding
    && y >= rect.y - padding
    && y <= rect.y + rect.height + padding
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  const pad = (number) => String(number).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function compareNumber(current, previous) {
  const delta = Number(current || 0) - Number(previous || 0)
  if (delta > 0) return { icon: '↑', delta: delta, tone: 'up' }
  if (delta < 0) return { icon: '↓', delta: Math.abs(delta), tone: 'down' }
  return { icon: '−', delta: 0, tone: 'flat' }
}

function eventTimestamp(event) {
  const time = Date.parse(event?.started_at || event?.last_observed_at || '')
  return Number.isFinite(time) ? time : 0
}

function riskLevel(event) {
  return ['LOW', 'MEDIUM', 'HIGH'].includes(event?.max_risk_level) ? event.max_risk_level : event?.risk_level
}

function riskRank(event) {
  return ({ LOW: 1, MEDIUM: 2, HIGH: 3 })[riskLevel(event)] || 0
}

function riskLevelLabel(level) {
  return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险' })[level] || '未知'
}

function riskLabel(event) {
  return riskLevelLabel(riskLevel(event))
}

function riskClass(event) {
  return ({ LOW: 'low', MEDIUM: 'medium', HIGH: 'high' })[riskLevel(event)] || 'unknown'
}

function statusLabel(value) {
  return ({ PENDING: '待处理', PROCESSING: '处理中', COMPLETED: '已完成', FALSE_ALARM: '误报' })[value] || value || '--'
}

function statusClass(value) {
  return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', COMPLETED: 'is-completed', FALSE_ALARM: 'is-false-alarm' })[value] || ''
}

function deviceTypeLabel(key) {
  return ({
    camera: '摄像头',
    sensor: '传感器',
    sensors: '传感器',
    rain: '雨量计',
    wind: '风速风向',
    vibration: '振动传感器',
    temp_humidity: '温湿度传感器',
    temperature_humidity: '温湿度传感器',
    drone: '无人机',
    agx: 'AGX边缘计算盒',
  })[key] || key || '设备'
}

function deviceGroupKey(key, item) {
  const raw = String(key || item?.device_id || '').toLowerCase()
  if (raw.includes('temp') || raw.includes('humidity')) return 'temp_humidity'
  if (raw.includes('wind')) return 'wind'
  if (raw.includes('rain')) return 'rain'
  if (raw.includes('vib')) return 'vibration'
  if (raw.includes('camera')) return 'camera'
  if (raw.includes('agx')) return 'agx'
  return raw || 'device'
}

function isHandled(event) {
  return event?.state === 'RESOLVED' || ['COMPLETED', 'FALSE_ALARM'].includes(event?.status)
}

function isEventUnhandled(event) {
  return !isHandled(event)
}

function getOverviewCategory(event) {
  const category = String(event?.event_category || '').toUpperCase()
  const text = `${event?.event_name || ''} ${event?.summary || ''}`.toUpperCase()
  if (category === 'PERSON_SAFETY' || category.includes('PERSON')) return 'person'
  if (category === 'ILLEGAL_FISHING' || category.includes('FISH') || category.includes('BOAT')) return 'boat'
  if (
    category.includes('FLOOD')
    || category.includes('EARTHQUAKE')
    || category.includes('LANDSLIDE')
    || category.includes('DEBRIS')
    || /洪水|地震|泥石流|滑坡/.test(text)
  ) return 'disaster'
  if (
    category === 'ENVIRONMENT'
    || category.includes('WEATHER')
    || /极端天气|台风|暴雨|大风|高温|低温/.test(text)
  ) return 'weather'
  return 'other'
}

function isOtherOverviewEvent(event) {
  const category = getOverviewCategory(event)
  return category !== 'person' && category !== 'boat'
}

function rangeStart(type) {
  const now = new Date()
  const start = new Date(now)
  if (type === 'today' || type === 'yesterday') start.setHours(0, 0, 0, 0)
  if (type === 'yesterday') start.setDate(start.getDate() - 1)
  if (type === 'week' || type === 'lastWeek') {
    const day = (start.getDay() + 6) % 7
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() - day)
    if (type === 'lastWeek') start.setDate(start.getDate() - 7)
  }
  if (type === 'month' || type === 'lastMonth') {
    start.setHours(0, 0, 0, 0)
    start.setDate(1)
    if (type === 'lastMonth') start.setMonth(start.getMonth() - 1)
  }
  if (type === 'year') {
    start.setHours(0, 0, 0, 0)
    start.setDate(1)
    start.setMonth(0)
  }
  return start
}

function rangeEnd(type) {
  const end = new Date()
  if (type === 'yesterday') {
    end.setDate(end.getDate() - 1)
    end.setHours(23, 59, 59, 999)
  }
  if (type === 'lastWeek') {
    const start = rangeStart('week')
    return start
  }
  if (type === 'lastMonth') {
    const start = rangeStart('month')
    return start
  }
  return end
}

function eventsInWindow(type) {
  const start = rangeStart(type).getTime()
  const end = rangeEnd(type).getTime()
  return events.value.filter((event) => {
    const time = eventTimestamp(event)
    return time >= start && time <= end
  })
}

function trendLabels(mode) {
  if (mode === 'today') return Array.from({ length: 24 }, (_, index) => `${String(index).padStart(2, '0')}:00`)
  if (mode === 'year') {
    const start = rangeStart('year')
    const end = new Date()
    const labels = []
    const cursor = new Date(start)
    while (cursor.getFullYear() === start.getFullYear() && cursor <= end) {
      labels.push(`${cursor.getMonth() + 1}月`)
      cursor.setMonth(cursor.getMonth() + 1)
    }
    return labels.length ? labels : ['--']
  }
  const start = rangeStart(mode)
  const end = new Date()
  const labels = []
  const cursor = new Date(start)
  while (cursor <= end) {
    labels.push(`${cursor.getMonth() + 1}/${cursor.getDate()}`)
    cursor.setDate(cursor.getDate() + 1)
  }
  return labels.length ? labels : ['--']
}

function trendBuckets(mode, category) {
  const labels = trendLabels(mode)
  const buckets = Array.from({ length: labels.length }, () => 0)
  const start = rangeStart(mode)
  const source = eventsInWindow(mode).filter((event) => getOverviewCategory(event) === category)
  source.forEach((event) => {
    const date = new Date(eventTimestamp(event))
    const index = mode === 'today'
      ? date.getHours()
      : mode === 'year'
        ? date.getMonth()
        : Math.floor((date - start) / (24 * 60 * 60 * 1000))
    if (index >= 0 && index < buckets.length) buckets[index] += 1
  })
  return buckets
}

function eventTimelineBuckets(sourceEvents, mode) {
  const labels = trendLabels(mode)
  const start = rangeStart(mode)
  const end = rangeEnd(mode)
  const total = Array.from({ length: labels.length }, () => 0)
  const risk = {
    LOW: Array.from({ length: labels.length }, () => 0),
    MEDIUM: Array.from({ length: labels.length }, () => 0),
    HIGH: Array.from({ length: labels.length }, () => 0),
  }
  sourceEvents.forEach((event) => {
    const time = eventTimestamp(event)
    if (time < start.getTime() || time > end.getTime()) return
    const date = new Date(time)
    const index = mode === 'today'
      ? date.getHours()
      : mode === 'year'
        ? date.getMonth()
        : Math.floor((date - start) / (24 * 60 * 60 * 1000))
    if (index < 0 || index >= labels.length) return
    const level = riskLevel(event)
    total[index] += 1
    if (risk[level]) risk[level][index] += 1
  })
  return { labels, total, risk }
}

function alertTitle(event) {
  return event?.event_name || event?.summary || '安全告警事件'
}

function logTypeLabel(value) {
  return ({ TRIGGER: '事件触发', RISK_CHANGE: '风险变化', ACTION: '执行动作', DAM_WORKFLOW: 'DAM_WORKFLOW', MANUAL: '人工操作', REPORT: 'REPORT', RESOLVE: '事件闭环', SYSTEM: '系统记录' })[value] || value || '系统记录'
}

function timelineTone(value) {
  return ({ TRIGGER: 'is-primary', RISK_CHANGE: 'is-warning', ACTION: 'is-success', DAM_WORKFLOW: 'is-warning', REPORT: 'is-info', RESOLVE: 'is-success' })[value] || 'is-info'
}

function timelineStatusLabel(value) {
  return ({ PENDING: '待处理', PROCESSING: '处理中', SUCCESS: '已完成', COMPLETED: '已完成', FAILED: '失败', FALSE_ALARM: '误报' })[value] || value || '已记录'
}

function timelineStatusClass(value) {
  return ({ PENDING: 'is-pending', PROCESSING: 'is-processing', SUCCESS: 'is-success', COMPLETED: 'is-success', FAILED: 'is-failed', FALSE_ALARM: 'is-muted' })[value] || 'is-muted'
}

function operatorLabel(value) {
  if (!value) return '系统记录'
  return value === 'SYSTEM' ? '系统自动' : value
}

function handleAlarmDetailClick() {
  const id = displayedPriorityAlert.value?.id
  if (!id) return
  router.push({ name: 'AlarmSafetyEventDetail', params: { id } })
}

function riskAutoSequence() {
  return riskModes.flatMap((mode) => riskLevels.map((_, levelIndex) => ({
    modeKey: mode.key,
    levelIndex,
  })))
}

function currentRiskAutoIndex() {
  const sequence = riskAutoSequence()
  const index = sequence.findIndex((item) => item.modeKey === activeRiskModeKey.value && item.levelIndex === riskFocusIndex.value)
  return index >= 0 ? index : 0
}

function applyRiskAutoStep(index) {
  const sequence = riskAutoSequence()
  const item = sequence[((index % sequence.length) + sequence.length) % sequence.length]
  activeRiskModeKey.value = item.modeKey
  riskFocusIndex.value = item.levelIndex
}

function advanceRiskAuto() {
  applyRiskAutoStep(currentRiskAutoIndex() + 1)
}

function restartRiskTimer() {
  window.clearInterval(riskTimer)
  riskTimer = window.setInterval(advanceRiskAuto, 3000)
}

function scheduleRiskAutoResume() {
  window.clearInterval(riskTimer)
  window.clearTimeout(riskResumeTimer)
  riskResumeTimer = window.setTimeout(() => {
    advanceRiskAuto()
    restartRiskTimer()
  }, 3000)
}

function handleRiskModeClick(modeKey) {
  activeRiskModeKey.value = modeKey
  riskFocusIndex.value = 0
  scheduleRiskAutoResume()
}

function clampMapOffset() {
  const board = mapBoardRef.value
  const { width, height } = mapBaseSize.value
  if (!board || !width || !height) return
  const rect = board.getBoundingClientRect()
  const maxX = Math.max((width * mapScale.value - rect.width) / 2, 0)
  const maxY = Math.max((height * mapScale.value - rect.height) / 2, 0)
  mapOffset.value = {
    x: Math.max(-maxX, Math.min(maxX, mapOffset.value.x)),
    y: Math.max(-maxY, Math.min(maxY, mapOffset.value.y)),
  }
}

function focusMapPoint(no, options = {}) {
  const point = cameraPoints.find((item) => item.no === no)
  const { width, height } = mapBaseSize.value
  if (!point || !width || !height) return
  const targetScale = Math.max(minMapScale.value, Math.min(maxMapScale, options.scale || mapFocusScale))
  const pointX = (point.x / 100 - .5) * width
  const pointY = (point.y / 100 - .5) * height
  mapScale.value = targetScale
  mapOffset.value = {
    x: -pointX * targetScale,
    y: -pointY * targetScale,
  }
  clampMapOffset()
}

function focusSelectedMapPoint() {
  focusMapPoint(selectedPointNo.value, { scale: mapFocusScale })
}

function zoomMapBy(ratio) {
  revealZoomTrack()
  const nextScale = Math.max(minMapScale.value, Math.min(maxMapScale, mapScale.value * ratio))
  if (nextScale === mapScale.value) return
  const scaleRatio = nextScale / mapScale.value
  mapScale.value = nextScale
  mapOffset.value = {
    x: mapOffset.value.x * scaleRatio,
    y: mapOffset.value.y * scaleRatio,
  }
  clampMapOffset()
}

function setMapScaleFromZoomPointer(event) {
  const track = event.currentTarget?.querySelector?.('.zoom-track-line')
    || document.querySelector('.zoom-track-line')
  if (!track) return
  const rect = track.getBoundingClientRect()
  const ratio = 1 - Math.max(0, Math.min(1, (event.clientY - rect.top) / Math.max(rect.height, 1)))
  const nextScale = minMapScale.value + (maxMapScale - minMapScale.value) * ratio
  mapScale.value = Math.max(minMapScale.value, Math.min(maxMapScale, nextScale))
  clampMapOffset()
}

function startZoomDrag(event) {
  zoomDragState.active = true
  revealZoomTrack()
  event.currentTarget.setPointerCapture?.(event.pointerId)
  setMapScaleFromZoomPointer(event)
  window.addEventListener('pointermove', moveZoomDrag)
  window.addEventListener('pointerup', endZoomDrag, { once: true })
  window.addEventListener('pointercancel', endZoomDrag, { once: true })
}

function moveZoomDrag(event) {
  if (!zoomDragState.active) return
  revealZoomTrack()
  setMapScaleFromZoomPointer(event)
}

function endZoomDrag() {
  zoomDragState.active = false
  window.removeEventListener('pointermove', moveZoomDrag)
  window.removeEventListener('pointerup', endZoomDrag)
  window.removeEventListener('pointercancel', endZoomDrag)
  revealZoomTrack()
}

function revealZoomTrack() {
  showZoomTrack.value = true
  window.clearTimeout(zoomTrackTimer)
  if (zoomDragState.active) return
  zoomTrackTimer = window.setTimeout(() => {
    showZoomTrack.value = false
  }, 950)
}

function updateMapBaseSize() {
  const board = mapBoardRef.value
  if (!board) return
  const rect = board.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const fitScale = Math.max(rect.width / 2168, rect.height / 725)
  const width = Math.ceil(2168 * fitScale)
  const height = Math.ceil(725 * fitScale)
  mapBaseSize.value = { width, height }
  minMapScale.value = Math.min(1, rect.width / width, rect.height / height)
  if (mapScale.value < minMapScale.value) mapScale.value = minMapScale.value
  if (!mapInitialFocused) {
    mapInitialFocused = true
    focusMapPoint(selectedPointNo.value, { scale: mapFocusScale })
  } else {
    clampMapOffset()
  }
}

function handleMapWheel(event) {
  if (!mapBaseSize.value.width) return
  revealZoomTrack()
  const board = mapBoardRef.value
  const rect = board.getBoundingClientRect()
  const nextScale = Math.max(minMapScale.value, Math.min(maxMapScale, mapScale.value * (event.deltaY > 0 ? 0.9 : 1.1)))
  if (nextScale === mapScale.value) return
  const pointerX = event.clientX - rect.left - rect.width / 2
  const pointerY = event.clientY - rect.top - rect.height / 2
  const ratio = nextScale / mapScale.value
  mapOffset.value = {
    x: pointerX - (pointerX - mapOffset.value.x) * ratio,
    y: pointerY - (pointerY - mapOffset.value.y) * ratio,
  }
  mapScale.value = nextScale
  clampMapOffset()
}

function startMapDrag(event) {
  if (event.button !== 0) return
  mapDragState.active = true
  mapDragState.moved = false
  mapDragState.startX = event.clientX
  mapDragState.startY = event.clientY
  mapDragState.startOffsetX = mapOffset.value.x
  mapDragState.startOffsetY = mapOffset.value.y
  event.currentTarget.setPointerCapture?.(event.pointerId)
}

function moveMapDrag(event) {
  if (!mapDragState.active) return
  const deltaX = event.clientX - mapDragState.startX
  const deltaY = event.clientY - mapDragState.startY
  if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) mapDragState.moved = true
  mapOffset.value = {
    x: mapDragState.startOffsetX + deltaX,
    y: mapDragState.startOffsetY + deltaY,
  }
  clampMapOffset()
}

function endMapDrag(event) {
  if (!mapDragState.active) return
  event.currentTarget.releasePointerCapture?.(event.pointerId)
  mapDragState.active = false
  window.setTimeout(() => {
    mapDragState.moved = false
  }, 0)
}

function selectPoint(no) {
  if (mapDragState.moved) return
  selectedPointNo.value = no
}

function updateClock() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  currentDate.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  currentTime.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  currentWeek.value = weekLabels[now.getDay()]
}

async function fetchPriorityDetail() {
  const rawId = displayedPriorityAlert.value?.id
  const id = normalizeEventId(rawId)
  if (!id) {
    currentPriorityDetailId = null
    priorityDetail.value = { id: null, timeline: [] }
    return
  }
  const sameEvent = id === currentPriorityDetailId && priorityDetail.value.id === id
  try {
    const res = await getUnifiedSafetyEventDetail(rawId)
    const incomingTimeline = res.data?.timeline || []
    const previousTimeline = sameEvent ? (priorityDetail.value.timeline || []) : []
    currentPriorityDetailId = id
    priorityDetail.value = {
      id,
      timeline: sameEvent ? mergePriorityTimeline(previousTimeline, incomingTimeline) : incomingTimeline,
    }
  } catch {
    if (priorityDetail.value.timeline?.length) return
    priorityDetail.value = { id, timeline: [] }
  }
}

function normalizeEventId(id) {
  return id == null || id === '' ? null : String(id)
}

function mergePriorityTimeline(previousRows = [], incomingRows = []) {
  if (!previousRows.length) return incomingRows
  if (!incomingRows.length) return previousRows
  const merged = new Map()
  previousRows.forEach((row, index) => {
    merged.set(timelineRowKey(row, index), row)
  })
  incomingRows.forEach((row, index) => {
    merged.set(timelineRowKey(row, index), row)
  })
  return Array.from(merged.values()).sort((a, b) => timelineRowTimestamp(a) - timelineRowTimestamp(b))
}

function timelineRowKey(row, index) {
  if (row?.id != null) return `id:${row.id}`
  const key = [
    row?.log_type || 'log',
    row?.create_time || row?.created_at || '',
    row?.title || '',
    row?.message || row?.action || '',
  ].join('|')
  return key === 'log|||' ? `fallback:${index}` : key
}

function timelineRowTimestamp(row) {
  const value = row?.create_time || row?.created_at
  const timestamp = value ? new Date(value).getTime() : 0
  return Number.isFinite(timestamp) ? timestamp : 0
}

async function fetchData() {
  if (fetchDataInFlight) return
  fetchDataInFlight = true
  loading.value = true
  try {
    const [statsResult, eventsResult, statusResult, cameraResult] = await Promise.allSettled([
      getUnifiedSafetyEventStatistics(),
      fetchOverviewEvents(),
      getDeviceStatus(),
      getCameraList(),
    ])

    if (statsResult.status === 'fulfilled' && statsResult.value?.data) {
      eventStats.value = statsResult.value.data || {}
    }
    if (eventsResult.status === 'fulfilled') {
      events.value = dedupeEvents(eventsResult.value || []).sort((a, b) => eventTimestamp(b) - eventTimestamp(a))
      syncDisplayedPriorityAlert()
    }
    if (statusResult.status === 'fulfilled' && statusResult.value?.data) {
      deviceStatus.value = statusResult.value.data || {}
    }
    if (cameraResult.status === 'fulfilled') {
      const cameras = cameraResult.value?.data?.cameras || []
      // 总数统计全部摄像头（含关闭的），在线只统计启用且连接的
      cameraSummary.value = {
        online: cameras.filter((camera) => camera.enabled !== false && camera.connected).length,
        total: cameras.length,
      }
    }
    await fetchPriorityDetail()
    await nextTick()
    renderAllCharts()
  } finally {
    loading.value = false
    fetchDataInFlight = false
  }
}

function syncDisplayedPriorityAlert() {
  const activeAlert = events.value
    .filter((event) => !isHandled(event))
    .slice()
    .sort((a, b) => riskRank(b) - riskRank(a) || eventTimestamp(b) - eventTimestamp(a))[0] || null

  if (activeAlert) {
    window.clearTimeout(displayedAlertClearTimer)
    displayedAlertClearId = null
    displayedPriorityAlert.value = activeAlert
    return
  }

  const currentId = normalizeEventId(displayedPriorityAlert.value?.id)
  if (!currentId) {
    clearDisplayedAlert()
    return
  }

  const updatedCurrent = events.value.find((event) => normalizeEventId(event.id) === currentId)
  displayedPriorityAlert.value = updatedCurrent || displayedPriorityAlert.value

  if (!displayedAlertClearId || displayedAlertClearId !== currentId) {
    displayedAlertClearId = currentId
    window.clearTimeout(displayedAlertClearTimer)
    displayedAlertClearTimer = window.setTimeout(() => {
      if (normalizeEventId(displayedPriorityAlert.value?.id) === currentId) {
        clearDisplayedAlert()
      }
    }, completedAlertVisibleMs)
  }
}

function clearDisplayedAlert() {
  displayedPriorityAlert.value = null
  displayedAlertClearId = null
  priorityDetail.value = { id: null, timeline: [] }
  currentPriorityDetailId = null
  flowTimelineUserScrolled.value = false
  window.clearTimeout(displayedAlertClearTimer)
}

function handleProgressPanelEnter() {
  progressPanelHovered.value = true
}

function handleProgressPanelLeave() {
  progressPanelHovered.value = false
  if (!flowTimelineUserScrolled.value) return
  flowTimelineUserScrolled.value = false
  nextTick(() => scrollActiveFlowNodeIntoView({ force: true }))
}

function handleFlowTimelineUserScroll() {
  if (!displayedPriorityAlert.value) return
  flowTimelineUserScrolled.value = true
}

function scrollActiveFlowNodeIntoView(options = {}) {
  if (!options.force && progressPanelHovered.value && flowTimelineUserScrolled.value) return
  const container = flowTimelineRef.value
  if (!container || !displayedPriorityAlert.value || container.classList.contains('idle')) return
  const activeNode = container.querySelector('li.running, li.active')
  if (!activeNode) return

  const padding = 12
  const containerRect = container.getBoundingClientRect()
  const nodeRect = activeNode.getBoundingClientRect()
  const nodeTop = nodeRect.top - containerRect.top + container.scrollTop
  const nodeHeight = activeNode.offsetHeight
  const nodeBottom = nodeTop + nodeHeight
  const maxScroll = Math.max(container.scrollHeight - container.clientHeight, 0)
  if (!maxScroll) return

  const centeredTop = nodeTop - ((container.clientHeight - nodeHeight) / 2)
  let targetTop = Math.min(Math.max(centeredTop, 0), maxScroll)

  const targetBottom = targetTop + container.clientHeight
  if (nodeBottom > targetBottom - padding) {
    targetTop = Math.min(nodeBottom - container.clientHeight + padding, maxScroll)
  }
  if (nodeTop < targetTop + padding) {
    targetTop = Math.max(nodeTop - padding, 0)
  }

  if (Math.abs(targetTop - container.scrollTop) < 3) return
  container.scrollTo({ top: targetTop, behavior: 'smooth' })
}

async function fetchOverviewEvents() {
  const pageSize = 100
  const baseParams = { page_size: pageSize, sort_by: 'index', sort_order: 'desc' }
  const first = await getUnifiedSafetyEvents({ ...baseParams, page: 1 })
  const data = first?.data || {}
  const items = data.items || []
  const total = Number(data.total || items.length)
  const pageCount = Math.ceil(total / pageSize)
  if (pageCount <= 1) return items

  const restResults = await Promise.allSettled(
    Array.from({ length: pageCount - 1 }, (_, index) => getUnifiedSafetyEvents({
      ...baseParams,
      page: index + 2,
    })),
  )
  restResults.forEach((result) => {
    if (result.status === 'fulfilled') items.push(...(result.value?.data?.items || []))
  })
  return items
}

function dedupeEvents(source = []) {
  const map = new Map()
  source.forEach((event) => {
    const key = event?.id == null ? event?.instance_no : event.id
    if (key == null || key === '') return
    map.set(String(key), event)
  })
  return Array.from(map.values())
}

watch(
  [riskDistribution, activeRiskModeKey, activeRiskLevel, intrusionTrend, selectedData, riskCompositionData, disposalStats, deviceRate],
  () => nextTick(renderAllCharts),
  { deep: true }
)

watch(
  [alarmFlowSteps, displayedPriorityAlert],
  () => nextTick(scrollActiveFlowNodeIntoView),
  { deep: true }
)

onMounted(() => {
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  updateMapBaseSize()
  if (window.ResizeObserver && mapBoardRef.value) {
    mapResizeObserver = new ResizeObserver(updateMapBaseSize)
    mapResizeObserver.observe(mapBoardRef.value)
  }
  restartRiskTimer()
  fetchData()
  refreshTimer = window.setInterval(fetchData, 1000)
  window.addEventListener('resize', resizeCharts)
  nextTick(renderAllCharts)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  window.clearInterval(refreshTimer)
  window.clearInterval(riskTimer)
  window.clearTimeout(riskResumeTimer)
  window.clearTimeout(zoomTrackTimer)
  window.clearTimeout(displayedAlertClearTimer)
  window.removeEventListener('resize', resizeCharts)
  window.removeEventListener('pointermove', moveZoomDrag)
  window.removeEventListener('pointerup', endZoomDrag)
  window.removeEventListener('pointercancel', endZoomDrag)
  mapResizeObserver?.disconnect()
  chartInstances.forEach((chart) => chart.dispose())
  chartInstances.clear()
})
</script>

<style scoped>
:global(.bigscreen-chart-tooltip) {
  max-width: 240px !important;
  white-space: normal !important;
  word-break: break-word !important;
  border-radius: 8px !important;
  z-index: 99999 !important;
  pointer-events: none;
}

.bigscreen-page {
  --panel-radius: 8px;
  --panel-border: rgba(74, 163, 214, .24);
  --panel-border-soft: rgba(74, 163, 214, .16);
  --panel-bg: linear-gradient(180deg, rgba(6, 28, 49, .94), rgba(3, 18, 33, .96));
  --panel-glow: 0 12px 28px rgba(0, 0, 0, .26), inset 0 1px 0 rgba(185, 229, 255, .045);
  --card-bg: linear-gradient(180deg, rgba(8, 35, 61, .68), rgba(4, 23, 42, .7));
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  color: #eef7ff;
  background:
    radial-gradient(circle at 50% 30%, rgba(38, 119, 170, 0.08), transparent 38%),
    linear-gradient(135deg, #020812 0%, #061827 54%, #020a13 100%);
  font-family: "Bahnschrift", "DIN Alternate", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.ambient-grid {
  position: absolute;
  inset: 0;
  opacity: .08;
  pointer-events: none;
  background:
    linear-gradient(rgba(67, 200, 255, .08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67, 200, 255, .06) 1px, transparent 1px);
  background-size: 44px 44px;
}

.screen-header,
.screen-grid {
  position: relative;
  z-index: 1;
}

.screen-header {
  height: 86px;
  display: grid;
  grid-template-columns: minmax(560px, 1fr) minmax(360px, 1fr) minmax(230px, 1fr);
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(74, 163, 214, .18);
  background: linear-gradient(180deg, rgba(2, 12, 24, .92), rgba(2, 12, 24, .72));
}

.brand-block,
.clock-block {
  display: flex;
  align-items: center;
}

.brand-block {
  gap: 11px;
  min-width: 0;
}

.brand-mark {
  width: 28px;
  height: 28px;
  clip-path: polygon(18% 0, 100% 0, 72% 42%, 100% 100%, 20% 72%, 0 38%);
  background: linear-gradient(135deg, #52d8ff, #2679ff);
  box-shadow: none;
}

.brand-block strong {
  flex: 0 0 auto;
  color: #cbe7ff;
  font-size: 16px;
  letter-spacing: 1px;
}

.screen-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-left: 18px;
}

.screen-nav span {
  height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 0 14px;
  border: 1px solid transparent;
  color: #748da3;
  font-size: 13px;
  white-space: nowrap;
}

.screen-nav span.active {
  border-color: rgba(67, 200, 255, .58);
  color: #bdeaff;
  background: rgba(35, 119, 204, .16);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .05);
}

.screen-title h1 {
  margin: 0;
  color: #f4fbff;
  font-size: 28px;
  letter-spacing: 6px;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.clock-block {
  width: 100%;
  height: 100%;
  justify-content: space-between;
  gap: 10px;
}

.clock-block span {
  color: #88a9c1;
  font-size: 12px;
  white-space: nowrap;
}

.clock-block strong {
  color: #fff;
  font-size: 23px;
  letter-spacing: 1px;
  line-height: 1;
}

.clock-block em {
  display: inline-flex;
  align-items: center;
  color: #38d59c;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.clock-block i,
.online-badge i {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 6px currentColor;
}

.screen-grid {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 20fr) minmax(760px, 62fr) minmax(230px, 18fr);
  gap: 10px;
  padding: 10px 14px 12px;
  overflow: hidden;
}

.left-column,
.center-column,
.right-column {
  min-height: 0;
  display: grid;
  gap: 10px;
  overflow: hidden;
}

.left-column {
  grid-template-rows: minmax(0, 35.5fr) minmax(0, 24fr) minmax(0, 32.5fr);
}

.center-column {
  grid-template-rows: minmax(0, 65fr) minmax(240px, 35fr);
}

.right-column {
  grid-template-rows: minmax(0, 1fr) 202px;
}

.progress-panel {
  display: flex;
  flex-direction: column;
  container: progressPanel / inline-size;
}

.screen-panel,
.map-panel,
.selected-detail {
  min-width: 0;
  min-height: 0;
  position: relative;
  border: 1px solid var(--panel-border);
  border-radius: var(--panel-radius);
  background: var(--panel-bg);
  box-shadow: var(--panel-glow);
  overflow: hidden;
  box-sizing: border-box;
}

.screen-panel::before,
.map-panel::before,
.selected-detail::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255, 255, 255, .045), transparent 26%);
  opacity: .55;
}

.screen-panel,
.selected-detail {
  padding: 14px;
}

.clock-panel {
  padding: 12px 14px;
}

.clock-panel .clock-block {
  position: relative;
  z-index: 1;
  align-items: center;
  border-radius: 8px;
  background: linear-gradient(90deg, rgba(10, 45, 73, .5), rgba(3, 22, 40, .22));
  padding: 0 4px;
}

.progress-heading {
  align-items: flex-start;
  gap: 10px;
}

.progress-heading h2 {
  flex: 0 0 auto;
}

.progress-clock {
  width: auto;
  height: auto;
  flex: 1 1 auto;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
  padding-top: 1px;
}

.progress-clock span {
  overflow: hidden;
  color: #87abc5;
  font-size: clamp(12px, .73vw, 16px);
  text-overflow: ellipsis;
}

.progress-clock strong {
  flex: 0 0 auto;
  font-size: clamp(18px, 1.05vw, 22px);
  letter-spacing: .5px;
  font-variant-numeric: tabular-nums;
}

.progress-clock em {
  flex: 0 0 auto;
  font-size: clamp(11px, .63vw, 14px);
}

.panel-heading,
.sub-heading,
.selected-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-heading h2,
.selected-title h2,
.sub-heading h3 {
  margin: 0;
  color: #eef7ff;
  font-size: clamp(20px, 1.17vw, 26px);
  font-weight: 800;
  letter-spacing: 0;
  text-shadow: none;
}

.sub-heading h3 {
  font-size: clamp(16px, .93vw, 20px);
}

.sub-heading span,
.selected-title span {
  color: #9ed3f5;
  font-size: clamp(12px, .73vw, 16px);
}

.disposal-card .sub-heading span {
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
}

.segmented {
  display: flex;
  padding: 2px;
  border: 1px solid rgba(67, 200, 255, .24);
  border-radius: 6px;
  background: rgba(2, 16, 31, .78);
  box-shadow: none;
}

.segmented button,
.mini-segmented button {
  height: clamp(24px, 1.35vw, 30px);
  padding: 0 clamp(10px, .6vw, 14px);
  border: 0;
  color: #88a9c1;
  background: transparent;
  font-size: clamp(12px, .73vw, 15px);
  cursor: pointer;
  border-radius: 4px;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}

.segmented button.active,
.mini-segmented button.active {
  color: #e9f8ff;
  background: linear-gradient(180deg, rgba(67, 200, 255, .26), rgba(37, 116, 204, .18));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .06);
}

.mini-segmented {
  display: flex;
  flex: 0 0 auto;
  padding: 1px;
  border: 1px solid rgba(67, 200, 255, .24);
  border-radius: 6px;
  background: rgba(2, 16, 31, .62);
}

.mini-segmented button {
  height: clamp(22px, 1.25vw, 27px);
  padding: 0 clamp(8px, .5vw, 12px);
  font-size: clamp(10px, .6vw, 13px);
}

.today-panel {
  container: todayPanel / inline-size;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: clamp(6px, .3vw, 8px);
  padding-bottom: clamp(12px, .6vw, 16px);
}

.today-strip-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(54px, .86fr)) repeat(2, minmax(58px, .92fr));
  column-gap: clamp(6px, .3vw, 8px);
  row-gap: clamp(8px, .4vw, 11px);
  min-height: 0;
  padding-bottom: clamp(4px, .22vw, 6px);
  box-sizing: border-box;
}

.today-card {
  --metric-color: #43c8ff;
  min-height: 0;
  position: relative;
  border: 1px solid rgba(74, 163, 214, .22);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(7, 33, 57, .82), rgba(4, 22, 40, .86));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
  overflow: hidden;
}

.today-card.category {
  display: grid;
  grid-template-columns: clamp(31px, 1.78vw, 40px) minmax(0, 1fr) max-content;
  grid-template-rows: auto auto;
  align-items: center;
  align-content: center;
  column-gap: clamp(8px, .48vw, 11px);
  row-gap: clamp(5px, .3vw, 7px);
  padding: clamp(6px, .34vw, 8px) clamp(8px, .48vw, 11px);
}

.today-card.handling {
  --handling-gap: clamp(8px, .5vw, 12px);
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(132px, .36fr) minmax(236px, .64fr);
  align-items: center;
  gap: var(--handling-gap);
  padding: clamp(7px, .4vw, 9px) clamp(10px, .6vw, 14px);
}

.today-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 13px;
  bottom: 13px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--metric-color);
  opacity: .9;
}

.handling-title {
  min-width: 0;
  display: grid;
  align-items: center;
  gap: clamp(7px, .45vw, 10px);
}

.handling-title {
  grid-template-columns: clamp(32px, 1.85vw, 42px) minmax(0, 1fr);
}

.metric-icon {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border-radius: 9px;
  color: var(--metric-color);
  background: rgba(12, 44, 72, .72);
  border: 1px solid rgba(143, 200, 242, .18);
}

.today-card.category > .metric-icon {
  grid-row: 1 / 3;
  grid-column: 1;
  align-self: center;
}

.today-card.category > .metric-label {
  grid-column: 2 / 4;
  grid-row: 1;
  align-self: center;
}

.today-card.category > .metric-value {
  grid-column: 2;
  grid-row: 2;
  align-self: center;
  justify-self: center;
  transform: translateX(clamp(2px, .25vw, 5px));
}

.today-card.category > .metric-compare {
  grid-column: 3;
  grid-row: 2;
  align-self: center;
  justify-self: end;
  transform: translateY(clamp(2px, .16vw, 4px));
}

.metric-icon :deep(svg) {
  width: 54%;
  height: 54%;
  display: block;
}

.metric-label {
  min-width: 0;
  color: #b7e5ff;
  font-size: clamp(15px, .86vw, 18px);
  font-weight: 800;
  line-height: 1.22;
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  word-break: keep-all;
  overflow-wrap: normal;
}

.metric-value {
  min-width: 0;
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-start;
  margin: 0;
  color: #fff;
  font-size: clamp(18px, 1.03vw, 23px);
  line-height: 1;
  white-space: nowrap;
  letter-spacing: 0;
  font-variant-numeric: tabular-nums;
}

.metric-value small,
.metric-breakdown strong small {
  margin-left: 2px;
  font-size: .5em;
  font-weight: 700;
}

.metric-breakdown {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  justify-self: end;
  width: 100%;
  max-width: clamp(250px, 17vw, 340px);
  gap: var(--handling-gap);
}

.metric-breakdown > span {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: auto auto;
  align-items: center;
  row-gap: clamp(4px, .22vw, 6px);
  column-gap: clamp(6px, .36vw, 9px);
  padding: clamp(6px, .34vw, 8px) clamp(8px, .48vw, 10px);
  border: 1px solid rgba(82, 177, 230, .16);
  border-radius: 6px;
  background: rgba(2, 15, 28, .28);
}

.metric-breakdown em {
  color: #95cbed;
  font-size: clamp(13px, .76vw, 16px);
  font-style: normal;
  line-height: 1;
  white-space: nowrap;
}

.metric-breakdown strong {
  color: #fff;
  font-size: clamp(21px, 1.18vw, 28px);
  white-space: nowrap;
  line-height: 1;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.metric-breakdown b {
  grid-column: 1 / -1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: clamp(4px, .24vw, 6px);
  overflow: hidden;
  color: #9ed3f5;
  font-size: clamp(12px, .7vw, 15px);
  font-style: normal;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

.metric-breakdown b i {
  display: inline-flex;
  min-width: clamp(38px, 2.2vw, 50px);
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
  font-style: normal;
  font-size: clamp(14px, .8vw, 18px);
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.metric-breakdown b small {
  font-size: .72em;
  line-height: 1;
}

.metric-compare {
  width: clamp(68px, 3.9vw, 86px);
  min-width: clamp(68px, 3.9vw, 86px);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  white-space: nowrap;
  text-align: left;
  font-style: normal;
}

.metric-compare > span {
  color: #9ed3f5;
  font-size: clamp(12px, .68vw, 14px);
  line-height: 1;
  font-style: normal;
}

.metric-compare i {
  display: inline-flex;
  min-width: clamp(22px, 1.35vw, 30px);
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
  margin-right: 0;
  font-style: normal;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  font-size: clamp(17px, 1vw, 22px);
  font-weight: 800;
}

.metric-trend-arrow {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  height: 1em;
  color: currentColor;
  font-size: .86em;
  font-weight: inherit;
  line-height: 1;
}

.metric-trend-value {
  display: inline-flex;
  align-items: center;
  height: 1em;
  color: currentColor;
  line-height: 1;
}

.today-card em,
.today-card i {
  font-style: normal;
}

.today-card.danger { --metric-color: #ff6873; }
.today-card.warning { --metric-color: #FFB648; }
.today-card.boat { --metric-color: #41c8ff; }
.today-card.storm { --metric-color: #76b7ff; }
.today-card.purple { --metric-color: #9b73ff; }
.today-card.cyan { --metric-color: #43c8ff; }
.today-card.success { --metric-color: #38d59c; }

.today-card.handling .metric-label {
  font-size: clamp(16px, .92vw, 20px);
  white-space: nowrap;
}

@container todayPanel (max-width: 470px) {
  .today-strip-list {
    grid-template-rows: repeat(2, minmax(54px, .86fr)) repeat(2, minmax(58px, .92fr));
    column-gap: 8px;
    row-gap: 8px;
    padding-bottom: 6px;
  }

  .today-card.category {
    grid-template-columns: 30px minmax(0, 1fr) max-content;
    grid-template-rows: auto auto;
    align-content: center;
    column-gap: 7px;
    row-gap: 5px;
    padding: 6px 8px;
  }

  .today-card.handling {
    --handling-gap: 6px;
    grid-template-columns: minmax(116px, .35fr) minmax(210px, .65fr);
    gap: var(--handling-gap);
    padding: 6px 8px;
  }

  .handling-title {
    grid-template-columns: 30px minmax(0, 1fr);
    gap: 6px;
  }

  .metric-label {
    font-size: 14px;
    line-height: 1.2;
    white-space: nowrap;
  }

  .today-card.handling .metric-label {
    font-size: 15px;
  }

  .metric-value {
    font-size: 18px;
  }

  .metric-compare > span {
    font-size: 12px;
  }

  .metric-compare i {
    font-size: 16px;
  }

  .metric-breakdown {
    width: 100%;
    max-width: 250px;
    gap: 6px;
  }

  .metric-breakdown > span {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    row-gap: 3px;
    column-gap: 5px;
    padding: 5px 7px;
  }

  .metric-breakdown em {
    font-size: 12px;
  }

  .metric-breakdown strong {
    font-size: 19px;
  }

  .metric-breakdown b {
    grid-column: 1 / -1;
    justify-content: space-between;
    font-size: 11px;
  }

  .metric-breakdown b i {
    font-size: 14px;
    min-width: 34px;
  }
}

@container todayPanel (max-width: 405px) {
  .today-card.category {
    grid-template-columns: 28px minmax(0, 1fr) max-content;
    grid-template-rows: auto auto;
    padding: 6px;
    column-gap: 6px;
    row-gap: 4px;
  }

  .today-card.handling {
    --handling-gap: 5px;
    grid-template-columns: minmax(104px, .35fr) minmax(188px, .65fr);
    padding: 6px;
    gap: var(--handling-gap);
  }

  .handling-title {
    grid-template-columns: 28px minmax(0, 1fr);
    gap: 5px;
  }

  .metric-label {
    font-size: 13px;
    line-height: 1.18;
  }

  .today-card.handling .metric-label {
    font-size: 14px;
  }

  .metric-value {
    font-size: 17px;
  }

  .metric-breakdown {
    width: 100%;
    max-width: 224px;
    gap: 4px;
  }

  .metric-breakdown > span {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    padding: 4px 6px;
  }

  .metric-breakdown em {
    font-size: 11px;
  }

  .metric-breakdown strong {
    font-size: 18px;
  }

  .metric-breakdown b {
    font-size: 10px;
  }

  .metric-breakdown b i {
    font-size: 13px;
    min-width: 32px;
  }

  .metric-compare i {
    font-size: 16px;
  }
}

@container todayPanel (max-width: 340px) {
  .today-strip-list {
    grid-template-rows: repeat(2, minmax(56px, .86fr)) repeat(2, minmax(64px, .96fr));
    column-gap: 6px;
    row-gap: 12px;
    padding-bottom: 8px;
  }

  .today-card.category > .metric-compare {
    width: auto;
    min-width: 0;
  }

  .today-card.category > .metric-compare > span {
    display: none;
  }

  .today-card.handling {
    --handling-gap: 4px;
    grid-template-columns: minmax(94px, .38fr) minmax(0, .62fr);
    gap: var(--handling-gap);
  }

  .metric-breakdown {
    max-width: none;
  }

  .metric-breakdown > span {
    padding: 4px 5px;
  }

  .metric-breakdown b i {
    min-width: 28px;
  }

  .today-card.handling .metric-label {
    font-size: 12px;
  }
}

.up,
.down,
.flat {
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.up { color: #ff5b68; }
.down { color: #38d59c; }
.flat { color: #88a9c1; }

.echarts-chart {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.risk-panel {
  display: grid;
  grid-template-rows: 34px minmax(0, 1fr);
  gap: 8px;
}

.risk-switch {
  display: flex;
  flex: 0 0 auto;
  padding: 2px;
  border: 1px solid rgba(74, 163, 214, .22);
  border-radius: 6px;
  background: rgba(3, 20, 36, .72);
}

.risk-switch button {
  height: clamp(24px, 1.4vw, 30px);
  padding: 0 clamp(12px, .7vw, 16px);
  border: 0;
  color: #88a9c1;
  background: transparent;
  font-size: clamp(12px, .7vw, 15px);
  cursor: pointer;
  border-radius: 4px;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease;
}

.risk-switch button.active {
  color: #e9f8ff;
  background: rgba(42, 111, 157, .36);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .06);
}

.risk-showcase {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(128px, 1.05fr) minmax(106px, .95fr);
  align-items: center;
  align-content: center;
  gap: 14px;
}

.risk-chart-wrap {
  position: relative;
  width: min(clamp(150px, 9vw, 200px), 100%);
  aspect-ratio: 1;
  justify-self: center;
}

.risk-main-chart {
  width: 100%;
  height: 100%;
}

.risk-center {
  position: absolute;
  left: 50%;
  top: 50%;
  width: clamp(76px, 4.5vw, 100px);
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  gap: clamp(4px, .2vw, 6px);
  pointer-events: none;
  text-align: center;
}

.risk-center strong {
  color: #fff;
  font-size: clamp(32px, 1.8vw, 42px);
  font-weight: 800;
  line-height: 1;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.risk-center span {
  color: #8fc8f2;
  font-size: clamp(12px, .7vw, 15px);
  line-height: 1;
  white-space: nowrap;
}

.risk-center span.risk-level-LOW,
.risk-summary strong.risk-level-LOW {
  color: #38d59c;
}

.risk-center span.risk-level-MEDIUM,
.risk-summary strong.risk-level-MEDIUM {
  color: #ffb648;
}

.risk-center span.risk-level-HIGH,
.risk-summary strong.risk-level-HIGH {
  color: #ff5b68;
}

.risk-summary {
  min-width: 0;
  display: grid;
  gap: clamp(9px, .5vw, 14px);
  color: #8fc8f2;
}

.risk-summary span {
  font-size: clamp(14px, .85vw, 18px);
}

.risk-summary strong {
  min-width: clamp(74px, 4.3vw, 96px);
  height: clamp(32px, 1.85vw, 42px);
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  justify-self: start;
  padding: 1px clamp(11px, .7vw, 16px) 0;
  border: 1px solid rgba(93, 183, 232, .26);
  border-radius: 6px;
  color: #eef7ff;
  background: rgba(14, 58, 92, .34);
  font-size: clamp(15px, .9vw, 19px);
  line-height: clamp(30px, 1.75vw, 40px);
  font-weight: 800;
  box-shadow: none;
  text-align: center;
}

.risk-summary em {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: clamp(6px, .3vw, 8px);
  padding: clamp(4px, .25vw, 6px) clamp(8px, .45vw, 12px);
  border-radius: 6px;
  color: #c4e8fb;
  background: rgba(67, 200, 255, .07);
  font-size: clamp(14px, .85vw, 18px);
  font-style: normal;
  line-height: 1;
}

.risk-summary em b {
  display: inline-flex;
  min-width: clamp(32px, 1.7vw, 42px);
  align-items: center;
  justify-content: flex-start;
  margin-left: 0;
  font-weight: 700;
  font-size: clamp(17px, 1vw, 22px);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.trend-legend span {
  cursor: pointer;
}

.trend-legend i {
  display: inline-block;
  width: clamp(8px, .45vw, 10px);
  height: clamp(8px, .45vw, 10px);
  margin-right: clamp(5px, .3vw, 8px);
  border-radius: 50%;
}

.trend-panel {
  display: grid;
  grid-template-rows: 34px 18px minmax(0, 1fr);
  align-items: stretch;
  gap: clamp(4px, .25vw, 6px);
}

.trend-panel .panel-heading {
  height: 34px;
  min-height: 0;
  gap: 8px;
}

/* 标题自适应：占满剩余空间，按钮组保持完整不被挤压 */
.trend-panel .panel-heading h2 {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  font-size: clamp(14px, .92vw, 20px);
}

.trend-panel .segmented {
  flex-shrink: 0;
}

.trend-panel .segmented button {
  height: clamp(22px, 1.22vw, 28px);
  padding: 0 clamp(8px, .48vw, 10px);
  font-size: clamp(11px, .66vw, 13px);
}

.trend-legend {
  display: flex;
  height: clamp(17px, 1vw, 22px);
  min-height: 0;
  align-items: center;
  justify-content: flex-end;
  gap: clamp(8px, .45vw, 12px);
  margin: 0;
  color: #a4d2ee;
  font-size: clamp(11px, .62vw, 14px);
  overflow: hidden;
}

.trend-legend i.person {
  background: #ff6873;
}

.trend-legend i.boat {
  background: #41c8ff;
}

.trend-legend i.disaster {
  background: #ffb648;
}

.trend-legend i.weather {
  background: #38d59c;
}

/* 告警记录：标题自适应，按钮组不被挤压 */
.hourly-card .sub-heading {
  gap: 8px;
}

.hourly-card .sub-heading h3 {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  font-size: clamp(13px, .85vw, 17px);
}

.hourly-card .mini-segmented {
  flex-shrink: 0;
}

.hourly-card .mini-segmented button {
  height: clamp(20px, 1.15vw, 25px);
  padding: 0 clamp(6px, .4vw, 9px);
  font-size: clamp(10px, .6vw, 12px);
}

.line-chart {
  width: 100%;
  height: 100%;
  min-height: 0;
  margin-top: 0;
  overflow: hidden;
}

.person-path { stroke: #ff6873; }
.boat-path { stroke: #41c8ff; }

.map-panel {
  overflow: hidden;
}

.map-board {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  background: #051323;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.map-board:active {
  cursor: grabbing;
}

.map-rank-card {
  position: absolute;
  left: clamp(12px, .9vw, 18px);
  bottom: clamp(12px, .9vw, 18px);
  z-index: 5;
  width: clamp(136px, 8.1vw, 168px);
  padding: clamp(6px, .38vw, 8px);
  border: 1px solid rgba(105, 205, 255, .16);
  border-radius: 6px;
  background:
    linear-gradient(135deg, rgba(8, 42, 70, .18), rgba(4, 19, 34, .13)),
    rgba(3, 16, 29, .1);
  box-shadow: 0 8px 18px rgba(0, 0, 0, .14), inset 0 1px 0 rgba(255, 255, 255, .04);
  backdrop-filter: blur(2px);
  pointer-events: auto;
}

.map-rank-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: clamp(5px, .3vw, 7px);
}

.map-rank-head span {
  color: #eef9ff;
  font-size: clamp(10px, .56vw, 12px);
  font-weight: 800;
  line-height: 1;
}

.map-rank-head em {
  padding: 1px 4px;
  border-radius: 4px;
  color: #7bddff;
  background: rgba(72, 183, 255, .08);
  font-size: clamp(8px, .45vw, 10px);
  font-style: normal;
  font-weight: 800;
  letter-spacing: .04em;
}

.map-rank-list {
  display: grid;
  gap: clamp(4px, .22vw, 6px);
  margin: 0;
  padding: 0;
  list-style: none;
}

.map-rank-list li {
  display: grid;
  grid-template-columns: clamp(14px, .74vw, 16px) minmax(108px, 1fr);
  align-items: center;
  gap: clamp(5px, .28vw, 7px);
  min-width: 0;
}

.map-rank-list li > i {
  display: grid;
  place-items: center;
  width: clamp(14px, .74vw, 16px);
  height: clamp(14px, .74vw, 16px);
  border-radius: 50%;
  color: #dff8ff;
  background: rgba(75, 177, 238, .1);
  border: 1px solid rgba(109, 213, 255, .15);
  font-size: clamp(8px, .45vw, 10px);
  font-style: normal;
  font-weight: 800;
}

.map-rank-list li:nth-child(1) > i {
  color: #fff2d1;
  background: rgba(255, 179, 72, .2);
  border-color: rgba(255, 190, 79, .36);
}

.map-rank-list li:nth-child(2) > i {
  color: #dff8ff;
  background: rgba(68, 201, 255, .16);
  border-color: rgba(68, 201, 255, .32);
}

.map-rank-list li:nth-child(3) > i {
  color: #f0e7ff;
  background: rgba(151, 108, 255, .16);
  border-color: rgba(151, 108, 255, .32);
}

.map-rank-main {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.map-rank-main > div {
  display: grid;
  grid-template-columns: minmax(72px, 1fr) max-content;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.map-rank-main span {
  min-width: 0;
  overflow: hidden;
  color: #bfe8ff;
  font-size: clamp(9px, .52vw, 11px);
  font-weight: 700;
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-rank-main strong {
  flex: 0 0 auto;
  color: #fff;
  font-size: clamp(10px, .58vw, 12px);
  line-height: 1;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.map-rank-main small {
  margin-left: 2px;
  color: #8fc8f2;
  font-size: .68em;
  font-weight: 700;
}

.map-rank-main b {
  position: relative;
  display: block;
  height: 2px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(91, 169, 214, .1);
}

.map-rank-main b em {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #43d59d, #44c9ff 62%, #ff5b68);
  box-shadow: 0 0 10px rgba(68, 201, 255, .28);
}

.map-controls {
  position: absolute;
  right: 18px;
  bottom: 18px;
  z-index: 6;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: auto;
}

.zoom-cluster {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(5px, .42vw, 8px);
  opacity: 0;
  transform: translateY(5px);
  pointer-events: none;
  transition: opacity .22s ease, transform .22s ease;
}

.zoom-cluster.visible {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.map-controls .zoom-button {
  width: clamp(20px, 1.3vw, 27px);
  height: clamp(20px, 1.3vw, 27px);
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: clamp(4px, .32vw, 6px);
  color: #07111c;
  background: rgba(247, 249, 252, .55);
  box-shadow: 0 4px 10px rgba(1, 9, 18, .14);
  font-size: clamp(14px, .95vw, 18px);
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: background .18s ease, transform .18s ease, box-shadow .18s ease;
}

.map-controls .zoom-button:hover {
  background: rgba(247, 249, 252, .85);
  box-shadow: 0 10px 22px rgba(1, 9, 18, .24);
  transform: translateY(-1px);
}

.zoom-track {
  width: clamp(24px, 1.75vw, 36px);
  height: clamp(78px, 6vw, 118px);
  display: grid;
  place-items: center;
  cursor: pointer;
  pointer-events: auto;
  touch-action: none;
}

.zoom-track-line {
  position: relative;
  width: clamp(5px, .42vw, 8px);
  height: clamp(70px, 5.5vw, 108px);
  border-radius: 999px;
  background:
    linear-gradient(
      to top,
      rgba(74, 145, 226, .55) 0 var(--zoom-progress),
      rgba(246, 249, 253, .52) var(--zoom-progress) 100%
    );
  box-shadow: inset 0 0 0 1px rgba(226, 235, 246, .36);
}

.zoom-track-line i {
  position: absolute;
  left: 50%;
  top: var(--zoom-thumb-top);
  width: clamp(13px, .9vw, 18px);
  height: clamp(13px, .9vw, 18px);
  border-radius: 50%;
  background: rgba(74, 145, 226, .8);
  border: 1px solid rgba(45, 123, 205, .6);
  box-shadow: 0 4px 10px rgba(55, 139, 232, .28);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.map-controls .locate {
  position: relative;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(96, 190, 244, .32);
  border-radius: 6px;
  color: #e6f8ff;
  background: rgba(4, 24, 43, .78);
  box-shadow: 0 8px 20px rgba(0, 0, 0, .22), inset 0 1px 0 rgba(255, 255, 255, .08);
  font-size: 0;
  cursor: pointer;
  transition: background .18s ease, border-color .18s ease, color .18s ease, transform .18s ease;
}

.map-controls .locate:hover {
  border-color: rgba(111, 214, 255, .72);
  color: #fff;
  background: rgba(19, 71, 111, .82);
  transform: translateY(-1px);
}

.map-controls .locate::before,
.map-controls .locate::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.map-controls .locate::before {
  width: 12px;
  height: 12px;
  border: 1px solid currentColor;
  border-radius: 50%;
  box-shadow: none;
}

.map-controls .locate::after {
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: currentColor;
  box-shadow:
    0 -8px 0 -1px currentColor,
    0 8px 0 -1px currentColor,
    -8px 0 0 -1px currentColor,
    8px 0 0 -1px currentColor;
}

.map-controls .locate span {
  position: absolute;
  inset: 0;
}

.map-controls .locate span::before,
.map-controls .locate span::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  background: currentColor;
  transform: translate(-50%, -50%);
}

.map-controls .locate span::before {
  width: 18px;
  height: 1px;
}

.map-controls .locate span::after {
  width: 1px;
  height: 18px;
}

.map-scene {
  position: absolute;
  top: 50%;
  left: 50%;
  transform-origin: center center;
  will-change: transform;
}

.satellite-image,
.map-shade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.satellite-image {
  object-fit: fill;
  filter: saturate(1.08) contrast(1.06) brightness(.72);
  pointer-events: none;
  user-select: none;
}

.map-shade {
  pointer-events: none;
  background:
    radial-gradient(circle at 48% 50%, transparent 48%, rgba(0, 9, 20, .34)),
    linear-gradient(180deg, rgba(0, 17, 35, .04), rgba(0, 12, 25, .08));
}

.camera-region-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 2;
  overflow: visible;
}

.selected-region {
  vector-effect: non-scaling-stroke;
  transform-box: fill-box;
  transform-origin: center;
}

.selected-region-fill {
  fill: rgba(67, 220, 255, .12);
  stroke: transparent;
}

.selected-region-fill.personForbidden {
  fill: rgba(54, 154, 255, .1);
}

.selected-region-halo {
  fill: none;
  stroke: rgba(81, 229, 255, .42);
  stroke-width: 13;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#selected-region-glow);
  opacity: .88;
  animation: regionBreath 2.8s ease-in-out infinite;
}

.selected-region-halo.personForbidden {
  stroke: rgba(54, 154, 255, .38);
}

.selected-region-line {
  fill: none;
  stroke: rgba(126, 238, 255, .96);
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#selected-region-glow);
}

.selected-region-line.personForbidden {
  stroke: rgba(93, 181, 255, .98);
}

.selected-region-scan.personForbidden {
  stroke: rgba(190, 230, 255, .92);
}

.selected-region-scan {
  fill: none;
  stroke: rgba(219, 255, 255, .88);
  stroke-width: 1.4;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-dasharray: 38 520;
  animation: regionDash 4.2s linear infinite;
  opacity: .82;
}

.region-callout {
  animation: calloutIn .36s ease-out both;
}

.region-callout .callout-line {
  fill: none;
  stroke: rgba(131, 239, 255, .88);
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 7 5;
  vector-effect: non-scaling-stroke;
  filter: url(#selected-region-glow);
}

.region-callout .callout-box {
  fill: rgba(4, 25, 43, .78);
  stroke: rgba(131, 239, 255, .72);
  stroke-width: 1.2;
  vector-effect: non-scaling-stroke;
  filter: url(#selected-region-glow);
}

.region-callout .callout-text {
  fill: #e8fbff;
  font-size: clamp(17px, 1vw, 21px);
  font-weight: 800;
  letter-spacing: 0;
  text-anchor: middle;
  paint-order: stroke;
  stroke: rgba(2, 12, 22, .88);
  stroke-width: 3px;
  stroke-linejoin: round;
}

.region-callout.personForbidden .callout-line {
  stroke: rgba(93, 181, 255, .9);
}

.region-callout.personForbidden .callout-box {
  stroke: rgba(93, 181, 255, .76);
  fill: rgba(7, 28, 58, .76);
}

.camera-point {
  position: absolute;
  width: clamp(22px, 1.3vw, 30px);
  height: clamp(22px, 1.3vw, 30px);
  padding: 0;
  border: 1px solid rgba(255, 172, 178, .9);
  border-radius: 50%;
  color: #fff;
  background: radial-gradient(circle, #ff6b72 0 42%, rgba(167, 30, 38, .92) 43% 100%);
  box-shadow: 0 0 0 4px rgba(255, 91, 104, .12), 0 4px 14px rgba(0, 0, 0, .28);
  transform: translate(-50%, -50%);
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease;
  animation: pointPulse 2.4s ease-in-out infinite;
  z-index: 3;
}

.camera-point::before,
.camera-point::after {
  content: "";
  position: absolute;
  inset: -7px;
  border-radius: 50%;
  border: 1px solid rgba(255, 122, 128, .28);
  opacity: 0;
  transform: scale(.78);
  pointer-events: none;
}

.camera-point::after {
  inset: -13px;
  border-color: rgba(255, 255, 255, .2);
}

.camera-point span {
  position: relative;
  z-index: 1;
  display: block;
  font-size: clamp(12px, .7vw, 15px);
  font-weight: 800;
  line-height: clamp(20px, 1.2vw, 28px);
}

.camera-point:hover,
.camera-point.active {
  transform: translate(-50%, -50%) scale(1.12);
}

.camera-point.active {
  border-color: #fff;
  background:
    radial-gradient(circle at 50% 48%, #ff7a82 0 34%, #ee3f4d 35% 62%, rgba(143, 16, 25, .98) 63% 100%);
  box-shadow:
    0 0 0 6px rgba(255, 91, 104, .18),
    0 0 24px rgba(255, 91, 104, .58),
    0 6px 18px rgba(0, 0, 0, .34);
  animation: activePointGlow 1.35s ease-in-out infinite;
  z-index: 4;
}

.camera-point.active::before {
  opacity: 1;
  border-color: rgba(255, 135, 143, .48);
  animation: pointRing 1.5s ease-out infinite;
}

.camera-point.active::after {
  opacity: 1;
  border-color: rgba(255, 255, 255, .3);
  animation: pointRing 1.5s ease-out .28s infinite;
}

.selected-detail {
  min-height: 0;
  padding: 12px 16px 14px;
}

.selected-title {
  height: clamp(40px, 2.3vw, 50px);
  margin-bottom: 6px;
  align-items: flex-start;
}

.selected-title > div {
  display: grid;
  gap: 5px;
}

.selected-title span {
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1;
  letter-spacing: .5px;
}

.selected-title h2 {
  width: fit-content;
  max-width: 100%;
  margin: 0;
  color: #f2fbff;
  font-size: clamp(21px, 1.22vw, 27px);
  line-height: 1.12;
  letter-spacing: 0;
  text-shadow: none;
}

.selected-title h2::after {
  content: none;
}

.analytics-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.18fr .98fr;
  gap: clamp(10px, .6vw, 16px);
  height: calc(100% - clamp(46px, 2.7vw, 56px));
  min-height: 0;
}

.analytics-card {
  min-width: 0;
  min-height: 0;
  padding: clamp(11px, .7vw, 16px) clamp(13px, .8vw, 18px);
  border: 1px solid rgba(67, 200, 255, .2);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(9, 37, 65, .66), rgba(1, 17, 32, .58));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
  overflow: hidden;
}

.analytics-card .sub-heading {
  height: clamp(26px, 1.6vw, 34px);
  align-items: flex-start;
}

.analytics-card .sub-heading h3 {
  color: #f2fbff;
  font-size: clamp(17px, .98vw, 21px);
  line-height: 1.1;
  font-weight: 800;
}

.analytics-card .sub-heading span {
  color: #8ecaf1;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1.1;
}

.bar-chart {
  height: calc(100% - clamp(32px, 2vw, 40px));
  min-height: 0;
  margin-top: 6px;
}

.risk-composition {
  height: calc(100% - clamp(32px, 2vw, 40px));
  min-height: 0;
  margin-top: 6px;
  overflow: hidden;
}

.disposal-body {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, .55vw, 14px);
  height: calc(100% - clamp(32px, 2vw, 40px));
  margin-top: 6px;
}

.disposal-ring-wrap {
  position: relative;
  width: min(clamp(132px, 8vw, 178px), 100%);
  aspect-ratio: 1;
  justify-self: center;
}

.disposal-ring {
  width: 100%;
  height: 100%;
}

.disposal-center {
  position: absolute;
  left: 50%;
  top: 50%;
  width: clamp(86px, 4.9vw, 108px);
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  gap: clamp(2px, .15vw, 4px);
  pointer-events: none;
  text-align: center;
}

.disposal-center strong {
  color: #fff;
  font-size: clamp(31px, 1.76vw, 40px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
  text-shadow: 0 1px 0 rgba(255, 255, 255, .12);
}

.disposal-center span {
  color: #8fc8f2;
  font-size: clamp(13px, .73vw, 17px);
  line-height: 1;
  white-space: nowrap;
}

.disposal-list {
  display: grid;
  gap: clamp(13px, .7vw, 19px);
  min-width: 0;
  flex: 0 1 auto;
  color: #d8eefc;
  font-size: clamp(15px, .83vw, 19px);
}

.disposal-list i {
  display: inline-block;
  width: clamp(8px, .4vw, 11px);
  height: clamp(8px, .4vw, 11px);
  margin-right: clamp(8px, .45vw, 12px);
  border-radius: 50%;
  box-shadow: none;
}

.disposal-list span {
  display: flex;
  align-items: center;
  min-width: 0;
  white-space: nowrap;
  line-height: 1.15;
}

.disposal-list .handled { background: #38d59c; }
.disposal-list .processing { background: #ffb648; }
.disposal-list .pending { background: #ff5b68; }

.priority-summary {
  display: grid;
  gap: 9px;
  margin-top: 12px;
  padding: 12px 13px;
  border: 1px solid rgba(255, 91, 104, .34);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(255, 91, 104, .14), rgba(10, 36, 58, .42));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .045);
}

.priority-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.priority-summary strong {
  font-size: clamp(14px, .83vw, 18px);
  line-height: 1;
  white-space: nowrap;
}

.priority-summary strong.low { color: #38d59c; }
.priority-summary strong.medium { color: #ffb648; }
.priority-summary strong.high { color: #ff5b68; }

.priority-summary span {
  color: #eef7ff;
  font-size: clamp(15px, .88vw, 19px);
  line-height: 1.35;
  font-weight: 700;
}

.priority-summary small {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.priority-summary small i {
  min-width: 0;
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
  font-style: normal;
  white-space: nowrap;
}

.priority-summary small b,
.progress-timeline footer b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: clamp(22px, 1.25vw, 28px);
  padding: 0 clamp(8px, .5vw, 12px);
  border-radius: 999px;
  color: #9ed3f5;
  background: rgba(143, 200, 242, .08);
  font-size: clamp(12px, .73vw, 15px);
  font-weight: 700;
  white-space: nowrap;
}

.priority-summary small b.is-pending,
.progress-timeline footer b.is-pending {
  color: #ffcf78;
  background: rgba(255, 182, 72, .12);
}

.priority-summary small b.is-processing,
.progress-timeline footer b.is-processing {
  color: #64dfff;
  background: rgba(67, 200, 255, .12);
}

.priority-summary small b.is-completed,
.priority-summary small b.is-success,
.progress-timeline footer b.is-success {
  color: #48e6ae;
  background: rgba(56, 213, 156, .12);
}

.priority-summary small b.is-false-alarm,
.progress-timeline footer b.is-muted {
  color: #a6b8c8;
  background: rgba(166, 184, 200, .1);
}

.progress-timeline footer b.is-failed {
  color: #ff7f88;
  background: rgba(255, 91, 104, .13);
}

.detail-button {
  flex: 0 0 auto;
  height: clamp(28px, 1.6vw, 34px);
  padding: 0 clamp(11px, .65vw, 15px);
  border: 1px solid rgba(67, 200, 255, .36);
  border-radius: 6px;
  color: #cceeff;
  background: rgba(22, 84, 134, .32);
  font-size: clamp(12px, .73vw, 15px);
  cursor: pointer;
  transition: background .18s ease, border-color .18s ease;
}

.detail-button:hover {
  border-color: rgba(67, 200, 255, .58);
  background: rgba(34, 112, 176, .42);
}

.priority-summary.empty {
  border-color: rgba(56, 213, 156, .24);
  background: rgba(56, 213, 156, .06);
}

.alarm-idle {
  display: grid;
  grid-template-columns: 74px 1fr;
  gap: 14px;
  align-items: center;
  margin-top: 18px;
  padding: 16px;
  border: 1px solid rgba(67, 200, 255, .16);
  border-radius: 8px;
  background:
    radial-gradient(circle at 36px 40px, rgba(56, 213, 156, .13), transparent 58px),
    rgba(5, 24, 43, .46);
}

.flow-idle-visual {
  flex: 0 0 auto;
  grid-template-columns: clamp(52px, 3vw, 68px) minmax(0, 1fr);
  gap: clamp(10px, .6vw, 16px);
  margin-top: 12px;
  padding: clamp(11px, .7vw, 15px) clamp(12px, .75vw, 17px);
  border-color: rgba(67, 200, 255, .14);
  background:
    radial-gradient(circle at 34px 36px, rgba(56, 213, 156, .12), transparent 54px),
    linear-gradient(135deg, rgba(7, 40, 65, .5), rgba(3, 18, 33, .38));
}

.flow-idle-visual .idle-orbit {
  width: clamp(48px, 2.8vw, 62px);
  height: clamp(48px, 2.8vw, 62px);
}

.flow-idle-visual .idle-copy strong {
  font-size: clamp(15px, .88vw, 19px);
}

.flow-idle-visual .idle-copy span {
  font-size: clamp(12px, .73vw, 16px);
}

.idle-orbit {
  position: relative;
  width: clamp(58px, 3.4vw, 76px);
  height: clamp(58px, 3.4vw, 76px);
  border: 1px solid rgba(67, 200, 255, .22);
  border-radius: 50%;
  background: rgba(3, 18, 33, .58);
}

.idle-orbit::before,
.idle-orbit::after {
  content: "";
  position: absolute;
  border-radius: 50%;
}

.idle-orbit::before {
  inset: 15px;
  border: 2px solid rgba(56, 213, 156, .72);
}

.idle-orbit::after {
  left: 50%;
  top: 50%;
  width: 8px;
  height: 8px;
  transform: translate(-50%, -50%);
  background: #38d59c;
  box-shadow: 0 0 12px rgba(56, 213, 156, .72);
}

.idle-orbit span {
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  border-top: 2px solid rgba(67, 200, 255, .72);
  border-right: 2px solid transparent;
  animation: idleSpin 3.8s linear infinite;
}

.idle-orbit i {
  position: absolute;
  right: 8px;
  top: 12px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #43c8ff;
}

.idle-copy {
  min-width: 0;
  display: grid;
  gap: 7px;
}

.idle-copy strong {
  color: #e9f8ff;
  font-size: clamp(16px, .93vw, 20px);
  line-height: 1;
}

.idle-copy span {
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1.35;
}

.idle-status-grid {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.idle-status-grid span {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 9px 8px;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 6px;
  color: #7faeca;
  font-size: 11px;
  background: rgba(2, 14, 28, .36);
}

.idle-status-grid i {
  color: #cceeff;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.progress-timeline {
  --flow-gap: clamp(8px, 1.05vh, 12px);
  position: relative;
  flex: 1 1 auto;
  display: grid;
  grid-template-rows: repeat(4, minmax(min-content, 1fr));
  align-content: start;
  gap: var(--flow-gap);
  margin: 12px 0 0;
  padding: 0 2px 10px 22px;
  list-style: none;
  overflow: auto;
  min-height: 0;
  scroll-padding: 12px 0;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(67, 200, 255, .36) transparent;
}

.progress-timeline::before {
  content: "";
  position: absolute;
  top: 13px;
  bottom: 13px;
  left: 7px;
  width: 1px;
  background: linear-gradient(180deg, rgba(255, 91, 104, .86), rgba(255, 182, 72, .64), rgba(104, 161, 200, .22));
}

.progress-timeline li {
  position: relative;
  min-height: 0;
  min-width: 0;
  color: #cfe2f0;
}

.progress-timeline > li > i {
  position: absolute;
  left: -20px;
  top: 16px;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(136, 169, 193, .58);
  border-radius: 50%;
  background: #071a2f;
  z-index: 1;
}

.progress-timeline li.is-primary > i {
  border-color: #43c8ff;
  background: #08243a;
}

.progress-timeline li.is-warning > i {
  border-color: #ffb648;
  background: #2c210d;
}

.progress-timeline li.is-success > i {
  border-color: #38d59c;
  background: #0a2d29;
}

.progress-timeline li.active > i {
  border-color: #ff5b68;
  box-shadow: 0 0 0 4px rgba(255, 91, 104, .12);
}

.progress-timeline article {
  height: 100%;
  min-width: 0;
  padding: 10px 11px;
  box-sizing: border-box;
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 8px;
  background: rgba(4, 20, 36, .48);
}

.progress-timeline li.active article {
  border-color: rgba(255, 91, 104, .32);
  background: linear-gradient(135deg, rgba(255, 91, 104, .1), rgba(4, 20, 36, .54));
}

.progress-timeline header,
.progress-timeline footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.progress-timeline header strong {
  min-width: 0;
  overflow: hidden;
  color: #f1fbff;
  font-size: clamp(14px, .83vw, 18px);
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-timeline time,
.progress-timeline footer span {
  flex: 0 0 auto;
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1;
  white-space: nowrap;
}

.progress-timeline p {
  display: -webkit-box;
  margin: 8px 0 10px;
  overflow: hidden;
  color: #b7d0e3;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1.45;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.flow-timeline {
  --flow-rail-center: -27px;
  --flow-icon-size: clamp(32px, 1.9vw, 42px);
  --flow-icon-top: 9px;
  margin-top: 12px;
  padding-left: 52px;
}

.flow-timeline::before {
  content: none;
  display: none;
}

.flow-timeline > li:not(:last-child)::after {
  content: "";
  position: absolute;
  left: var(--flow-rail-center);
  top: calc(var(--flow-icon-top) + var(--flow-icon-size));
  bottom: calc(-1 * (var(--flow-gap) + var(--flow-icon-top)));
  width: 4px;
  border-radius: 999px;
  transform: translateX(-50%);
  background: linear-gradient(180deg, rgba(143, 200, 242, .16), rgba(143, 200, 242, .06));
  pointer-events: none;
  z-index: 0;
}

.flow-timeline > li.connector-done:not(:last-child)::after {
  background: linear-gradient(180deg, rgba(67, 200, 255, .58), rgba(56, 213, 156, .38));
}

.flow-timeline > li.connector-running:not(:last-child)::after {
  background:
    linear-gradient(180deg, transparent, rgba(100, 223, 255, .98), transparent) 0 -80px / 100% 80px no-repeat,
    linear-gradient(180deg, rgba(67, 200, 255, .58), rgba(100, 223, 255, .28));
  animation: flowLineScan 1.7s linear infinite;
}

.flow-timeline > li.connector-pending:not(:last-child)::after,
.flow-timeline.idle > li:not(:last-child)::after {
  background:
    linear-gradient(180deg, rgba(143, 200, 242, .2), rgba(143, 200, 242, .08));
  animation: none;
}

.progress-timeline > li > .flow-node-icon {
  left: var(--flow-rail-center);
  top: var(--flow-icon-top);
  width: var(--flow-icon-size);
  height: var(--flow-icon-size);
  display: grid;
  place-items: center;
  transform: translateX(-50%);
  border: 1px solid rgba(143, 200, 242, .22);
  border-radius: 9px;
  color: #8fc8f2;
  background: #082038;
  box-shadow: none;
  z-index: 2;
}

.flow-node-icon :deep(svg) {
  width: clamp(17px, 1vw, 22px);
  height: clamp(17px, 1vw, 22px);
}

.flow-timeline li.done > .flow-node-icon,
.flow-timeline li.is-success.done > .flow-node-icon {
  color: #48e6ae;
  border-color: rgba(72, 230, 174, .32);
  background: rgba(9, 45, 41, .92);
}

.flow-timeline li.running > .flow-node-icon {
  color: #64dfff;
  border-color: rgba(100, 223, 255, .68);
  animation: flowNodePulse 1.6s ease-in-out infinite;
  box-shadow: 0 0 0 3px rgba(100, 223, 255, .08), 0 0 14px rgba(100, 223, 255, .24);
}

.flow-timeline li.failed > .flow-node-icon,
.flow-timeline li.is-failed > .flow-node-icon {
  color: #ff7f88;
  border-color: rgba(255, 91, 104, .58);
  background: rgba(50, 18, 30, .9);
}

.flow-timeline li.idle > .flow-node-icon,
.flow-timeline li.pending > .flow-node-icon {
  opacity: .72;
}

.flow-timeline li.running article {
  position: relative;
  border-color: rgba(100, 223, 255, .44);
  background:
    linear-gradient(90deg, rgba(67, 200, 255, .12), rgba(4, 20, 36, .54) 48%, rgba(67, 200, 255, .08)),
    rgba(4, 20, 36, .52);
  overflow: hidden;
  z-index: 1;
}

.flow-timeline li.running article::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(100, 223, 255, .16), transparent);
  transform: translateX(-100%);
  animation: flowScan 2.2s ease-in-out infinite;
  pointer-events: none;
}

.flow-timeline.idle article {
  border-color: rgba(67, 200, 255, .1);
  background: rgba(4, 20, 36, .36);
}

.flow-timeline.idle {
  flex: 1 1 0;
  align-content: stretch;
  padding-bottom: 0;
  overflow: hidden;
}

.flow-timeline.idle > li {
  min-height: 0;
}

.flow-timeline.idle > li > .flow-node-icon {
  top: calc(50% - var(--flow-icon-size) / 2);
}

.flow-timeline.idle > li:not(:last-child)::after {
  top: calc(50% + var(--flow-icon-size) / 2);
  bottom: calc(-50% + var(--flow-icon-size) / 2 - var(--flow-gap));
}

.flow-timeline.idle article {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, auto) auto;
  align-content: center;
  padding: clamp(7px, 1.2vh, 10px) 11px;
  box-sizing: border-box;
}

.flow-timeline.idle header strong,
.flow-timeline.idle p {
  color: #88a9c1;
}

.flow-timeline.idle p {
  margin: clamp(5px, .9vh, 8px) 0 clamp(6px, .9vh, 10px);
  line-height: 1.35;
  -webkit-line-clamp: 1;
  line-clamp: 1;
}

.flow-node-logs {
  display: grid;
  gap: 6px;
  margin: 8px 0 10px;
  padding: 0;
  list-style: none;
}

.flow-node-logs li {
  min-width: 0;
  display: grid;
  gap: 4px;
  padding: 8px 9px;
  border-radius: 6px;
  color: #b8d4e8;
  background: rgba(2, 13, 25, .34);
}

.flow-node-logs b {
  min-width: 0;
  overflow: hidden;
  color: #e7f7ff;
  font-size: clamp(12px, .73vw, 15px);
  font-weight: 800;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-node-logs span {
  min-width: 0;
  display: -webkit-box;
  overflow: hidden;
  color: #9ed3f5;
  font-size: clamp(11px, .63vw, 14px);
  line-height: 1.35;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.device-panel {
  /* 纵向布局：标题行在上，内容区 flex:1 撑满剩余空间并垂直居中，避免内容贴底溢出 */
  display: flex;
  flex-direction: column;
}

.device-panel.warning {
  border-color: rgba(255, 91, 104, .34);
}

.device-state {
  display: grid;
  grid-template-columns: minmax(118px, .9fr) minmax(0, 1.1fr);
  gap: 14px;
  align-items: center;
  min-height: 0;
  flex: 1 1 auto;
  margin-top: 10px;
}

.device-gauge-wrap {
  position: relative;
  min-width: 0;
  min-height: 0;
  width: min(clamp(118px, 7.4vw, 158px), 100%);
  aspect-ratio: 1;
  justify-self: center;
  border: 0;
  border-radius: 0;
  background: transparent;
  overflow: visible;
}

.device-gauge-wrap::after {
  content: none;
}

.device-ring {
  position: absolute;
  inset: 0;
}

.device-center {
  position: absolute;
  left: 50%;
  top: 50%;
  display: grid;
  place-items: center;
  gap: clamp(3px, .2vw, 6px);
  width: clamp(58px, 3.4vw, 78px);
  transform: translate(-50%, -50%);
  pointer-events: none;
  text-align: center;
}

.device-center strong {
  color: #fff;
  font-size: clamp(19px, 1.1vw, 23px);
  line-height: 1;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.device-center span {
  color: #8fc8f2;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1;
  white-space: nowrap;
}

.device-counts {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.device-count-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.device-counts article {
  position: relative;
  min-width: 0;
  display: grid;
  grid-template-rows: clamp(13px, .8vw, 18px) clamp(22px, 1.3vw, 30px);
  place-items: center;
  gap: clamp(3px, .2vw, 6px);
  padding: clamp(7px, .45vw, 11px) clamp(9px, .55vw, 13px);
  border: 1px solid rgba(67, 200, 255, .14);
  border-radius: 7px;
  background: rgba(2, 16, 30, .32);
  text-align: center;
}

.device-counts span {
  color: #a4d2ee;
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1;
}

.device-counts strong {
  display: grid;
  place-items: center;
  color: #38d59c;
  font-size: clamp(22px, 1.27vw, 28px);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.device-counts .offline strong {
  color: #ff5b68;
}

.device-report {
  min-height: clamp(44px, 2.6vw, 58px);
  display: flex;
  align-items: center;
  margin: 0;
  padding: clamp(7px, .45vw, 11px) clamp(9px, .55vw, 13px);
  border-radius: 7px;
  color: #cfe6f5;
  background: rgba(56, 213, 156, .07);
  font-size: clamp(12px, .73vw, 16px);
  line-height: 1.35;
}

.device-report.warning {
  color: #ffd6d9;
  background: rgba(255, 91, 104, .08);
}

@keyframes pointPulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(255, 91, 104, .12), 0 4px 14px rgba(0, 0, 0, .28); }
  50% { box-shadow: 0 0 0 7px rgba(255, 91, 104, .04), 0 6px 16px rgba(0, 0, 0, .32); }
}

@keyframes activePointGlow {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1.12);
    box-shadow:
      0 0 0 5px rgba(255, 91, 104, .18),
      0 0 20px rgba(255, 91, 104, .5),
      0 6px 18px rgba(0, 0, 0, .34);
  }
  50% {
    transform: translate(-50%, -50%) scale(1.2);
    box-shadow:
      0 0 0 8px rgba(255, 91, 104, .12),
      0 0 30px rgba(255, 91, 104, .68),
      0 8px 20px rgba(0, 0, 0, .36);
  }
}

@keyframes pointRing {
  0% {
    opacity: .82;
    transform: scale(.74);
  }
  100% {
    opacity: 0;
    transform: scale(1.62);
  }
}

@keyframes pointOrbit {
  to { transform: rotate(360deg); }
}

@keyframes regionBreath {
  0%, 100% {
    opacity: .58;
    stroke-width: 11;
  }
  50% {
    opacity: .95;
    stroke-width: 15;
  }
}

@keyframes regionDash {
  to { stroke-dashoffset: -558; }
}

@keyframes calloutIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes idleSpin {
  to { transform: rotate(360deg); }
}

@keyframes flowNodePulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(100, 223, 255, .18);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(100, 223, 255, .08);
  }
}

@keyframes flowScan {
  0% { transform: translateX(-100%); }
  55%, 100% { transform: translateX(100%); }
}

@keyframes flowLineScan {
  from { background-position: 0 -90px, 0 0; }
  to { background-position: 0 100%, 0 0; }
}

@container progressPanel (max-width: 460px) {
  .progress-clock {
    gap: 8px;
  }

  .progress-clock span {
    flex: 0 1 auto;
    font-size: 11px;
    max-width: 94px;
  }

  .progress-clock strong {
    font-size: 17px;
  }
}

@container progressPanel (max-width: 360px) {
  .progress-clock span {
    max-width: 78px;
  }
}

@media (max-height: 820px) {
  .flow-idle-visual {
    grid-template-columns: 46px minmax(0, 1fr);
    gap: 10px;
    padding: 10px 12px;
  }

  .flow-idle-visual .idle-orbit {
    width: 44px;
    height: 44px;
  }

  .flow-idle-visual .idle-copy strong {
    font-size: 14px;
  }

  .flow-idle-visual .idle-copy span {
    font-size: 11px;
  }

  .flow-timeline.idle {
    gap: 8px;
  }

  .flow-timeline.idle article {
    padding: 7px 10px;
  }

  .flow-timeline.idle header strong {
    font-size: 13px;
  }

  .flow-timeline.idle time,
  .flow-timeline.idle footer span,
  .flow-timeline.idle p {
    font-size: 11px;
  }

  .flow-timeline.idle footer b {
    height: 20px;
    padding: 0 7px;
    font-size: 11px;
  }
}

@media (max-height: 720px) {
  .priority-summary {
    gap: 7px;
    margin-top: 9px;
    padding: 10px 12px;
  }

  .alarm-idle {
    margin-top: 9px;
  }

  .flow-timeline.idle {
    margin-top: 9px;
    gap: 6px;
  }

  .flow-timeline.idle article {
    padding: 6px 9px;
  }

  .flow-timeline.idle header strong {
    font-size: 12px;
  }

  .flow-timeline.idle p {
    margin: 4px 0 5px;
  }
}

@media (max-width: 1280px) {
  .screen-grid {
    grid-template-columns: minmax(230px, 23fr) minmax(520px, 54fr) minmax(230px, 23fr);
    padding: 8px 10px 10px;
  }

  .screen-panel,
  .selected-detail {
    padding: 11px;
  }

  .analytics-grid {
    gap: 8px;
  }
}
</style>
