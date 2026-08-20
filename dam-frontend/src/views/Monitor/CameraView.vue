<!-- dai -->
<template>
  <div class="vision-page">
    <header v-if="showLiveChrome" class="command-header surface-card">
      <div class="title-block">
        <div class="title-icon"><el-icon><Monitor /></el-icon></div>
        <div>
          <h1>智能视频监控</h1>
          <p class="title-description">Jetson 边缘推理 · 多路视频源 · 实时目标感知</p>
        </div>
      </div>

      <div class="header-status">
        <div class="camera-connection-status" :class="currentCamera?.connected ? 'online' : 'offline'">
          <div class="connection-main">
            <i class="connection-dot" aria-hidden="true"></i>
            <span>{{ currentCamera?.connected ? '在线' : '离线' }}</span>
          </div>
          <div class="connection-time">
            最后通讯: {{ formatDeviceCommTime(currentCamera?.last_frame_time) }}
          </div>
        </div>
      </div>
    </header>

    <section v-if="!isMediaAnalysisRoute" class="command-monitor">
      <main class="ops-layout" :class="{ 'multi-mode': isMultiCameraMode }">
        <aside class="ops-camera-rail">
          <section class="rail-card camera-list-card">
            <header class="camera-list-header">
              <div class="camera-list-title">
                <h3>摄像头</h3>
                <span>{{ connectedPointCount }}/9</span>
              </div>
              <el-select
                :model-value="cameraViewMode"
                class="rail-view-select"
                popper-class="vision-select-popper"
                @change="setCameraViewMode"
              >
                <el-option
                  v-for="mode in cameraViewModes"
                  :key="mode.value"
                  :label="mode.label"
                  :value="mode.value"
                />
              </el-select>
            </header>
            <div class="rail-camera-list">
              <button
                v-for="point in cameraPointSlots"
                :key="point.no"
                type="button"
                :class="{ active: point.no === selectedPointNo, empty: !point.camera }"
                @click="selectPointFromPanel(point.no)"
              >
                <b>{{ point.no.toString().padStart(2, '0') }}</b>
                <span>{{ point.camera?.name || `${point.no}号监测点` }}</span>
                <em :class="{ online: point.camera?.connected }">
                  <i></i>{{ pointStatusText(point) }}
                </em>
              </button>
            </div>
          </section>

          <section class="camera-point-actions">
            <button type="button" class="map-nav-entry" @click="mapDialogVisible = true">
              <el-icon><Aim /></el-icon>
              <strong>查看点位图</strong>
            </button>

            <el-tooltip
              :disabled="!broadcastUnavailableReason"
              :content="broadcastUnavailableReason"
              placement="right"
            >
              <div class="talk-action-wrap">
                <button
                  type="button"
                  class="primary-talk-button"
                  :disabled="Boolean(broadcastUnavailableReason)"
                  @click="openEmergencyBroadcast"
                >
                  <el-icon><Microphone /></el-icon>
                  <span>一键喊话</span>
                </button>
              </div>
            </el-tooltip>

            <div class="assist-setting">
              <div class="assist-setting-row">
                <strong>显示辅助框</strong>
                <el-switch
                  :model-value="assistOverlayVisible"
                  size="small"
                  @change="toggleAssistOverlay"
                />
              </div>
              <el-select
                v-if="assistOverlayVisible"
                v-model="assistZoneId"
                class="assist-zone-select"
                :disabled="!assistZoneOptions.length"
                :placeholder="assistZoneOptions.length ? '请选择辅助框' : '当前摄像头未配置辅助框'"
                popper-class="vision-select-popper"
              >
                <el-option
                  v-for="zone in assistZoneOptions"
                  :key="zone.id"
                  :label="zone.zone_name || zone.name || zoneTypeLabel(zone.type)"
                  :value="zone.id"
                />
              </el-select>
            </div>
          </section>
        </aside>

        <article v-if="isMultiCameraMode" class="ops-video-panel multi-video-panel">
          <div class="multi-camera-layout" :class="`mode-${cameraViewMode}`">
            <article
              v-for="slot in gridSlots"
              :key="slot.slotKey"
              class="multi-camera-tile"
              :class="{
                online: slot.camera?.connected,
                empty: !slot.camera,
                active: isActiveGridSlot(slot),
              }"
              role="button"
              tabindex="0"
              @click="activateGridSlot(slot)"
              @keydown.enter.prevent="activateGridSlot(slot)"
              @keydown.space.prevent="activateGridSlot(slot)"
            >
              <div class="tile-video-box">
                <video
                  v-if="slot.camera && gridStreamModes[slot.camera.id] === 'webrtc'"
                  :ref="(el) => setGridVideoRef(slot.camera.id, el)"
                  class="tile-video"
                  autoplay
                  muted
                  playsinline
                  :controls="false"
                  disablepictureinpicture
                  controlslist="nodownload noplaybackrate noremoteplayback nofullscreen"
                  @loadedmetadata="handleGridVideoLoad(slot.camera.id, $event)"
                  @playing="handleGridVideoLoad(slot.camera.id, $event)"
                ></video>
                <img
                  v-if="slot.camera && gridStreamModes[slot.camera.id] === 'mjpeg' && gridStreamUrls[slot.camera.id]"
                  :src="gridStreamUrls[slot.camera.id]"
                  :alt="`${slot.camera.name || slot.camera.id}实时画面`"
                  class="tile-video"
                  @load="handleGridImageLoad(slot.camera.id, $event)"
                  @error="handleGridStreamError(slot.camera.id)"
                />
                <svg
                  v-if="gridZoneOverlayVisible(slot)"
                  class="tile-zone-overlay"
                  :viewBox="`0 0 ${gridOverlaySize(slot.camera.id).width} ${gridOverlaySize(slot.camera.id).height}`"
                  preserveAspectRatio="xMidYMid meet"
                >
                  <g v-for="zone in gridAssistZonesForCamera(slot.camera.id)" :key="zone.id">
                    <polygon
                      class="ops-zone-polygon"
                      :points="zonePolygonPointsForSize(zone, gridOverlaySize(slot.camera.id).width, gridOverlaySize(slot.camera.id).height)"
                      :stroke="zoneStroke(zone)"
                      :fill="zoneAssistFill(zone)"
                      :stroke-width="Math.max(2, gridOverlaySize(slot.camera.id).width / 520)"
                    />
                    <text
                      class="ops-zone-label"
                      :x="zoneLabelPointForSize(zone, gridOverlaySize(slot.camera.id).width, gridOverlaySize(slot.camera.id).height).x"
                      :y="zoneLabelPointForSize(zone, gridOverlaySize(slot.camera.id).width, gridOverlaySize(slot.camera.id).height).y"
                      :fill="zoneStroke(zone)"
                    >
                      {{ zone.zone_name || zone.name || zoneTypeLabel(zone.type) }}
                    </text>
                  </g>
                </svg>
                <div v-if="!gridSlotHasStream(slot)" class="tile-empty">
                  <el-icon><VideoCamera /></el-icon>
                  <span>{{ gridSlotEmptyText(slot) }}</span>
                </div>
              </div>
            </article>
          </div>
        </article>

        <article v-else class="ops-video-panel">
          <div v-if="false" class="single-camera-select-wrap">
            <el-select
              :model-value="singleCameraSelectValue"
              class="single-camera-select"
              placeholder="不展示摄像头"
              popper-class="vision-select-popper"
              @change="handleSingleCameraSelection"
            >
              <el-option label="不展示摄像头" value="" />
              <el-option
                v-for="camera in cameras"
                :key="camera.id"
                :label="camera.name || camera.id"
                :value="camera.id"
              />
            </el-select>
          </div>
          <div v-if="canRenderCurrentStream" class="video-stage ops-video-stage" :class="riskThemeClass(overallRiskLevel)">
            <video
              v-show="streamMode === 'webrtc'"
              ref="liveVideoRef"
              class="video-stream"
              autoplay
              muted
              playsinline
              :controls="false"
              disablepictureinpicture
              controlslist="nodownload noplaybackrate noremoteplayback nofullscreen"
              @loadeddata="streamLoading = false"
              @playing="streamLoading = false"
            ></video>
            <img
              v-if="streamMode === 'mjpeg' && streamUrl"
              :key="streamUrl"
              ref="liveImageRef"
              :src="streamUrl"
              class="video-stream"
              alt="摄像头实时画面"
              @load="streamLoading = false"
              @error="handleStreamError"
            />

            <svg
              v-if="analysisTask === 'detect' && detectionEnabled && imageWidth > 0 && imageHeight > 0"
              class="box-overlay ops-box-overlay"
              :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <g v-for="(detection, index) in visibleDetections" :key="boxKey(detection, index)">
                <rect
                  class="ops-detection-box"
                  :x="detection.bbox.x1"
                  :y="detection.bbox.y1"
                  :width="detection.bbox.x2 - detection.bbox.x1"
                  :height="detection.bbox.y2 - detection.bbox.y1"
                  :stroke="detectionRiskColor(index)"
                  :stroke-width="boxStrokeWidth"
                />
                <rect
                  v-if="detectionOverlayText(detection, index)"
                  :x="detection.bbox.x1"
                  :y="labelY(detection, labelHeight)"
                  :width="labelWidthForText(detectionOverlayText(detection, index), labelFontSize, labelPadding)"
                  :height="labelHeight"
                  :fill="detectionRiskColor(index)"
                  rx="3"
                />
                <text
                  v-if="detectionOverlayText(detection, index)"
                  :x="detection.bbox.x1 + labelPadding"
                  :y="labelY(detection, labelHeight) + labelHeight * 0.72"
                  :font-size="labelFontSize"
                  class="ops-detection-label"
                >
                  {{ detectionOverlayText(detection, index) }}
                </text>
              </g>
            </svg>

            <svg
              v-if="analysisTask === 'detect' && editableZoneOverlayVisible"
              class="zone-overlay ops-zone-overlay visible"
              :class="{ editing: zoneConfigVisible, drawing: zoneDrawing }"
              :viewBox="`0 0 ${overlayWidth} ${overlayHeight}`"
              preserveAspectRatio="xMidYMid meet"
              @click="handleConfigZoneOverlayClick"
              @mousemove="dragConfigVertex"
              @mouseup="endConfigVertexDrag"
              @mouseleave="endConfigVertexDrag"
            >
              <g
                v-for="zone in visibleZonesForOverlay"
                :key="zone.id"
                class="editable-zone"
                :class="{ selected: zone.id === selectedZoneId, disabled: !zone.enabled }"
                @click.stop="handleConfigZoneClick(zone.id, $event)"
              >
                <polygon
                  v-if="zone.polygon_points.length >= 3"
                  class="ops-zone-polygon"
                  :points="zonePolygonPoints(zone)"
                  :stroke="zoneStroke(zone)"
                  :fill="zoneAssistFill(zone)"
                  :stroke-width="Math.max(2, overlayWidth / 520)"
                />
                <polyline
                  v-else-if="zone.polygon_points.length"
                  class="ops-zone-polyline"
                  :points="zonePolygonPoints(zone)"
                  :stroke="zoneStroke(zone)"
                />
                <text
                  v-if="zone.polygon_points.length"
                  class="ops-zone-label"
                  :x="zoneLabelPoint(zone).x"
                  :y="zoneLabelPoint(zone).y"
                  :fill="zoneStroke(zone)"
                >
                  {{ zone.zone_name || zone.name || zoneTypeLabel(zone.type) }}
                </text>
                <g
                  v-for="(point, index) in zone.polygon_points"
                  v-show="showConfigZoneAnchors(zone)"
                  :key="`${zone.id}-vertex-${index}`"
                  class="ops-zone-vertex"
                  @click.stop.prevent
                >
                  <circle
                    class="ops-zone-anchor"
                    :cx="point.x * overlayWidth"
                    :cy="point.y * overlayHeight"
                    :r="zoneVertexAnchorRadius"
                    @mousedown.stop.prevent="startConfigVertexDrag(zone.id, index)"
                  />
                  <text
                    class="ops-zone-vertex-label"
                    :x="vertexLabelPoint(point).x"
                    :y="vertexLabelPoint(point).y"
                    :font-size="zoneVertexFontSize"
                  >
                    {{ index + 1 }}
                  </text>
                </g>
              </g>
            </svg>

            <div v-if="false" class="video-topline">
              <span>#{{ currentCamera.id }}</span>
              <strong>{{ currentCamera.name || '未命名监控点' }}</strong>
              <em>{{ sourceTypeLabel(currentCamera.source_type) }}</em>
            </div>

            <div v-if="false" class="risk-banner" :class="riskThemeClass(overallRiskLevel)">
              <span>{{ overallRiskText }}</span>
              <strong>{{ primaryRiskEvent ? primaryRiskEvent.event_type : '坝区巡查正常' }}</strong>
              <em>{{ primaryRiskEvent ? `已持续 ${formatDuration(primaryRiskEvent.duration_seconds)}` : '系统自动值守中' }}</em>
            </div>

            <div v-if="streamLoading" class="stage-loading">
              <el-icon class="is-loading" :size="34"><Loading /></el-icon>
              <span>正在建立实时视频链路</span>
            </div>
            <div v-if="zoneConfigVisible && zoneDrawing" class="zone-draw-tip">
              点击视频画面添加顶点，拖动白色锚点微调位置
            </div>
          </div>

          <div v-else class="video-empty ops-video-empty">
            <div class="empty-orbit">
              <span></span>
              <el-icon :size="52"><VideoCamera /></el-icon>
            </div>
            <template v-if="currentCamera">
              <h3>{{ currentCamera.name }} 暂未连接</h3>
              <p>请检查摄像头供电、RTSP 地址、边缘节点网络和设备映射。</p>
              <code v-if="currentCamera.last_error">{{ currentCamera.last_error }}</code>
            </template>
            <template v-else>
              <h3>暂无摄像头设备</h3>
              <p>请先在设备管理中添加并启用摄像头。</p>
            </template>
          </div>

          <div v-if="debugMode" class="debug-panel">
            <div><small>FPS</small><strong>{{ currentCamera?.fps || 0 }}</strong></div>
            <div><small>推理耗时</small><strong>{{ formatSeconds(latestDetection.process_time) }}</strong></div>
            <div><small>端到端延迟</small><strong>{{ latestDetection.latency_ms || 0 }} ms</strong></div>
            <div><small>帧序号</small><strong>#{{ latestDetection.frame_sequence || 0 }}</strong></div>
            <div class="debug-targets">
              <span v-for="(detection, index) in visibleDetections" :key="boxKey(detection, index)">
                {{ detectionName(detection) }} · {{ confidencePercent(detection) }}% · {{ detection.track_id || `#${index + 1}` }}
              </span>
            </div>
          </div>
        </article>

      </main>
    </section>

    <section v-if="false && !isMediaAnalysisRoute" class="live-workspace">
      <article class="live-card surface-card">
        <div v-if="showLiveChrome" class="card-heading">
          <div>
            <h2>{{ currentCamera?.name || '实时视频窗口' }}</h2>
          </div>
          <div class="feed-metrics">
            <span><small>采集帧率</small><b>{{ currentCamera?.fps || 0 }} FPS</b></span>
            <span><small>分析模式</small><b>{{ detectionEnabled ? analysisTaskLabel : '原始画面' }}</b></span>
            <span><small>播放链路</small><b>{{ streamMode === 'webrtc' ? 'WebRTC' : 'MJPEG' }}</b></span>
          </div>
        </div>

        <div v-if="currentCamera?.connected" class="video-stage">
          <video
            v-show="streamMode === 'webrtc'"
            ref="liveVideoRef"
            class="video-stream"
            autoplay
            muted
            playsinline
            @loadeddata="streamLoading = false"
            @playing="streamLoading = false"
          ></video>
          <img
            v-if="streamMode === 'mjpeg' && streamUrl"
            :key="streamUrl"
            ref="liveImageRef"
            :src="streamUrl"
            class="video-stream"
            alt="摄像头实时画面"
            @load="streamLoading = false"
            @error="handleStreamError"
          />
          <svg
            v-if="analysisTask === 'detect' && detectionEnabled && imageWidth > 0 && imageHeight > 0"
            class="box-overlay"
            :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <g v-for="(detection, index) in visibleDetections" :key="boxKey(detection, index)">
              <rect
                class="detection-box"
                :x="detection.bbox.x1"
                :y="detection.bbox.y1"
                :width="detection.bbox.x2 - detection.bbox.x1"
                :height="detection.bbox.y2 - detection.bbox.y1"
                :stroke="getClassColor(detection.class_id)"
                :stroke-width="boxStrokeWidth"
              />
              <rect
                :x="detection.bbox.x1"
                :y="labelY(detection, labelHeight)"
                :width="labelWidth(detection, labelFontSize, labelPadding)"
                :height="labelHeight"
                :fill="getClassColor(detection.class_id)"
                rx="3"
              />
              <text
                :x="detection.bbox.x1 + labelPadding"
                :y="labelY(detection, labelHeight) + labelHeight * 0.72"
                :font-size="labelFontSize"
                class="detection-label"
              >
                {{ detectionLabel(detection) }}
              </text>
            </g>
          </svg>

          <svg
            v-if="analysisTask === 'detect'"
            class="zone-overlay"
            :class="{ visible: showZoneOverlay }"
            :viewBox="`0 0 ${overlayWidth} ${overlayHeight}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <g v-for="zone in zonesForOverlay" :key="zone.id">
              <polygon
                class="zone-polygon"
                :points="zonePolygonPoints(zone)"
                :stroke="zoneStroke(zone)"
                :fill="zoneFill(zone)"
                :stroke-width="Math.max(2, overlayWidth / 520)"
              />
              <text
                class="zone-label"
                :x="zoneLabelPoint(zone).x"
                :y="zoneLabelPoint(zone).y"
                :fill="zoneStroke(zone)"
              >
                  {{ zone.zone_name || zone.name || zoneTypeLabel(zone.type) }}
              </text>
            </g>
          </svg>

          <div class="scan-grid"></div>
          <span class="corner corner-tl"></span><span class="corner corner-tr"></span>
          <span class="corner corner-bl"></span><span class="corner corner-br"></span>
          <div v-if="streamLoading" class="stage-loading">
            <el-icon class="is-loading" :size="34"><Loading /></el-icon>
            <span>正在建立 {{ streamMode === 'webrtc' ? 'WebRTC' : '兼容' }} 视频链路</span>
          </div>
          <div class="stage-badge left-badge">
            <i :class="{ active: currentCamera.connected }"></i>
            {{ streamMode === 'webrtc' ? '低延迟实时' : '兼容模式' }}
          </div>
          <div class="stage-badge right-badge">
            {{ sourceTypeLabel(currentCamera.source_type) }} / #{{ currentCamera.id }}
          </div>
          <div v-if="liveAlerts.length" class="alert-ribbon">
            <strong>{{ liveAlerts[0].message }}</strong>
            <span>{{ liveAlerts[0].zone_name }} · {{ detectionName(liveAlerts[0]) }} {{ confidencePercent(liveAlerts[0]) }}%</span>
          </div>
        </div>

        <div v-else class="video-empty">
          <div class="empty-orbit">
            <span></span>
            <el-icon :size="52"><VideoCamera /></el-icon>
          </div>
          <template v-if="currentCamera">
            <h3>{{ currentCamera.name }} 暂未连接</h3>
            <p>Jetson 正在后台重连，请检查视频源地址、设备映射和网络。</p>
            <code v-if="currentCamera.last_error">{{ currentCamera.last_error }}</code>
          </template>
            <template v-else>
            <h3>暂无摄像头设备</h3>
            <p>请先在设备管理中添加并启用摄像头。</p>
          </template>
        </div>
      </article>

      <aside class="telemetry-card surface-card">
        <div class="card-heading telemetry-heading">
          <div>
            <h2>{{ analysisTask === 'detect' ? '实时检测列表' : '实时分类结果' }}</h2>
          </div>
          <span v-if="analysisTask === 'detect'" class="target-count">{{ detections.length }}<small>目标</small></span>
          <span v-else class="target-count">{{ confidencePercent(livePrediction) }}<small>%</small></span>
        </div>

        <div class="telemetry-grid">
          <div><small>分析状态</small><strong :class="detectionStatusClass">{{ detectionStatusText }}</strong></div>
          <div><small>端到端延迟</small><strong>{{ latestDetection.latency_ms || 0 }} ms</strong></div>
          <div><small>推理耗时</small><strong>{{ formatSeconds(latestDetection.process_time) }}</strong></div>
          <div><small>分析帧</small><strong>#{{ latestDetection.frame_sequence || 0 }}</strong></div>
        </div>

        <div v-if="analysisTask === 'detect'" class="zone-panel">
          <div class="zone-panel-heading">
            <span>风险区域</span>
            <b>{{ detectionZones.length }}</b>
          </div>
          <div v-if="detectionZones.length" class="zone-list">
            <article
              v-for="zone in detectionZones"
              :key="zone.id"
              class="zone-item"
              :class="{ alerting: liveAlertZoneIds.has(zone.id) }"
            >
              <span class="zone-chip" :style="{ '--zone-color': zoneStroke(zone) }"></span>
              <div>
                <strong>{{ zone.name || zoneTypeLabel(zone.type) }}</strong>
                <small>{{ zoneTypeLabel(zone.type) }}</small>
              </div>
              <span class="zone-risk">{{ zone.risk_level || 'LOW' }}</span>
            </article>
          </div>
          <p v-else>暂无区域配置。实时监控仅显示启用区域，不显示编辑锚点。</p>
          <el-button class="zone-config-link" @click="goZoneConfig">
            <el-icon><Crop /></el-icon>区域配置
          </el-button>
        </div>

        <div v-if="liveAlerts.length" class="alert-list">
          <article v-for="(alert, index) in liveAlerts" :key="`${alert.zone_id}-${index}`">
            <strong>{{ alert.message }}</strong>
            <span>{{ alert.zone_name }} · {{ detectionName(alert) }} {{ confidencePercent(alert) }}%</span>
          </article>
        </div>

        <div v-if="analysisTask === 'detect' && detectionEnabled && detections.length" class="target-list">
          <article
            v-for="(detection, index) in detections"
            :key="boxKey(detection, index)"
            class="target-item"
          >
            <span class="target-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="target-swatch" :style="{ '--target-color': getClassColor(detection.class_id) }"></span>
            <div class="target-copy">
              <strong>{{ detectionName(detection) }}</strong>
              <small>{{ detection.class_name || `CLASS ${detection.class_id}` }}</small>
            </div>
            <div class="confidence-ring" :style="{ '--confidence': `${confidencePercent(detection) * 3.6}deg`, '--ring-color': getClassColor(detection.class_id) }">
              <span>{{ confidencePercent(detection) }}</span>
            </div>
          </article>
        </div>
        <div v-else-if="analysisTask === 'classify' && detectionEnabled && liveClassifications.length" class="target-list classification-list">
          <article
            v-for="(item, index) in liveClassifications"
            :key="`live-class-${item.class_id}`"
            class="target-item"
            :class="{ primary: index === 0 }"
          >
            <span class="target-index">{{ index === 0 ? 'TOP' : String(index + 1).padStart(2, '0') }}</span>
            <span class="target-swatch" :style="{ '--target-color': getClassColor(item.class_id) }"></span>
            <div class="target-copy">
              <strong>{{ detectionName(item) }}</strong>
              <small>{{ item.class_name }}</small>
            </div>
            <div class="confidence-ring" :style="{ '--confidence': `${confidencePercent(item) * 3.6}deg`, '--ring-color': getClassColor(item.class_id) }">
              <span>{{ confidencePercent(item) }}</span>
            </div>
          </article>
        </div>
        <div v-else class="telemetry-empty">
          <el-icon :size="38"><DataAnalysis /></el-icon>
          <p>{{ telemetryEmptyText }}</p>
        </div>
        <p v-if="latestDetection.error" class="inline-error">{{ latestDetection.error }}</p>
      </aside>
    </section>

    <section v-if="isMediaAnalysisRoute" class="media-lab surface-card">
      <div class="lab-heading">
        <el-button class="media-back-button" @click="backToCameraView">
          <el-icon><ArrowLeft /></el-icon>返回
        </el-button>
        <div>
          <h2>模拟分析</h2>
        </div>
        <div class="media-control-group">
          <label class="media-control">
            <span>分析方式</span>
            <el-select
              v-model="analysisTask"
              class="media-select"
              :disabled="detectionToggling"
              popper-class="vision-select-popper"
              @change="handleAnalysisTaskChange"
            >
              <el-option label="目标检测" value="detect" />
              <el-option label="图片分类" value="classify" />
            </el-select>
          </label>
        </div>
      </div>

      <div v-show="mediaTab === 'image'" class="lab-content image-lab">
        <el-upload
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept="image/*"
          class="drop-zone"
          :on-change="handleFileUpload"
        >
          <div class="upload-symbol"><el-icon :size="32"><UploadFilled /></el-icon></div>
          <h3>{{ imageUploading ? '正在执行图片推理' : `拖入一张图片开始${analysisTaskLabel}` }}</h3>
          <p>支持 JPG、PNG、WEBP，单张不超过 10MB</p>
        </el-upload>
        <div class="media-result image-result" :class="{ 'has-result': uploadResult }">
          <template v-if="uploadResult">
            <div class="image-preview-wrap">
              <img :src="`data:image/jpeg;base64,${uploadResult.result_image_base64}`" alt="图片分析结果" />
              <div class="result-caption">
                <span v-if="uploadResult.task_type === 'detect'">识别到 <b>{{ imageDetections.length }}</b> 个目标</span>
                <span v-else>分类结果 <b>{{ detectionName(imagePrediction) }}</b></span>
                <span>耗时 {{ formatSeconds(uploadResult.process_time) }}</span>
              </div>
            </div>
            <aside class="image-target-panel">
              <div class="image-target-heading">
                <div>
                  <small>{{ uploadResult.task_type === 'detect' ? '检测结果' : '分类结果' }}</small>
                  <strong>{{ uploadResult.task_type === 'detect' ? '目标明细' : '类别置信度' }}</strong>
                </div>
                <span>{{ uploadResult.task_type === 'detect' ? imageDetections.length : `${confidencePercent(imagePrediction)}%` }}</span>
              </div>
              <div v-if="uploadResult.task_type === 'detect' && imageDetections.length" class="image-target-list">
                <article
                  v-for="(detection, index) in imageDetections"
                  :key="`image-${detection.class_id}-${index}`"
                  class="image-target-item"
                  :style="{ '--target-color': getClassColor(detection.class_id) }"
                >
                  <div class="image-target-index">{{ String(index + 1).padStart(2, '0') }}</div>
                  <div class="image-target-copy">
                    <strong>{{ detectionName(detection) }}</strong>
                    <small>类别 {{ detection.class_id }} · {{ detection.class_name || '目标' }}</small>
                  </div>
                  <div class="image-confidence">
                    <strong>{{ confidencePercent(detection) }}%</strong>
                    <small>置信度</small>
                  </div>
                </article>
              </div>
              <div v-else-if="uploadResult.task_type === 'classify' && imageClassifications.length" class="image-target-list">
                <article
                  v-for="(item, index) in imageClassifications"
                  :key="`image-class-${item.class_id}`"
                  class="image-target-item"
                  :class="{ primary: index === 0 }"
                  :style="{ '--target-color': getClassColor(item.class_id) }"
                >
                  <div class="image-target-index">{{ index === 0 ? 'TOP' : String(index + 1).padStart(2, '0') }}</div>
                  <div class="image-target-copy">
                    <strong>{{ detectionName(item) }}</strong>
                    <small>{{ item.class_name }}</small>
                  </div>
                  <div class="image-confidence">
                    <strong>{{ confidencePercent(item) }}%</strong>
                    <small>置信度</small>
                  </div>
                </article>
              </div>
              <div v-else class="image-target-empty">
                <el-icon><DataAnalysis /></el-icon>
                <strong>{{ uploadResult.task_type === 'classify' ? '暂无分类结果' : '未发现目标' }}</strong>
                <span>{{ uploadResult.task_type === 'classify' ? '可以更换图片后重试' : '可以更换图片或降低检测阈值后重试' }}</span>
              </div>
            </aside>
          </template>
          <div v-else class="result-placeholder"><el-icon><Picture /></el-icon><span>分析结果预览区</span></div>
        </div>
      </div>

    </section>

    <el-dialog
      v-model="mapDialogVisible"
      class="camera-map-dialog"
      title="摄像头点位图"
      width="92vw"
      top="5vh"
      @open="syncMapRegionSelection"
    >
      <div class="expanded-map-stage">
        <img src="/dam.png" alt="大藤峡摄像头点位总览" />
        <svg
          v-if="selectedMapRegionPath"
          class="expanded-map-region-layer"
          viewBox="0 0 2168 725"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <filter id="camera-region-glow" x="-14%" y="-18%" width="128%" height="136%">
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
          <path class="expanded-region-fill" :d="selectedMapRegionPath" />
          <path class="expanded-region-halo" :d="selectedMapRegionPath" />
          <path class="expanded-region-line" :d="selectedMapRegionPath" />
          <g v-if="selectedMapRegionCallout" class="expanded-region-callout">
            <rect
              :x="selectedMapRegionCallout.x"
              :y="selectedMapRegionCallout.y"
              :width="selectedMapRegionCallout.width"
              :height="34"
              rx="5"
            />
            <text
              :x="selectedMapRegionCallout.x + selectedMapRegionCallout.width / 2"
              :y="selectedMapRegionCallout.y + 22"
            >
              {{ selectedMapRegionCallout.label }}
            </text>
          </g>
        </svg>
        <button
          v-for="point in cameraPointSlots"
          :key="`expanded-map-point-${point.no}`"
          type="button"
          class="expanded-map-point"
          :class="{ active: point.no === selectedPointNo, offline: !point.camera?.connected, empty: !point.camera }"
          :style="cameraPointStyle(point)"
          :title="point.camera?.name || `${point.no}号监测点暂未接入`"
          @click="toggleMapPointRegion(point.no)"
        >
          <span>{{ point.no }}</span>
        </button>
      </div>
    </el-dialog>

    <BroadcastDialog
      v-model="broadcastDialogVisible"
      :event="broadcastTargetEvent"
      @played="handleBroadcastPlayed"
    />
    <el-drawer
      v-model="reportDrawerVisible"
      title="巡查报告"
      size="520px"
      class="patrol-report-drawer"
    >
      <div v-if="patrolReport && patrolReport.available === false" class="report-pending-state">
        <el-icon><Files /></el-icon>
        <strong>巡查报告模板调整中</strong>
        <span>当前接口已经预留报告生成入口，但后端返回模板未完成状态，暂时不会生成正式报告。</span>
      </div>
      <div v-else-if="patrolReport" class="patrol-report">
        <header>
          <span>{{ patrolReport.date }}</span>
          <strong>{{ patrolReport.camera_id || '全部摄像头' }}</strong>
        </header>
        <div class="report-stats">
          <div><small>事件总数</small><b>{{ patrolReport.total_events || 0 }}</b></div>
          <div><small>已闭环</small><b>{{ patrolReport.resolved_events || 0 }}</b></div>
          <div><small>未闭环</small><b>{{ patrolReport.open_events || 0 }}</b></div>
        </div>
        <div class="report-risk-grid">
          <div class="risk-low"><span>低风险</span><b>{{ reportRiskCounts.LOW || 0 }}</b></div>
          <div class="risk-medium"><span>中风险</span><b>{{ reportRiskCounts.MEDIUM || 0 }}</b></div>
          <div class="risk-high"><span>高风险</span><b>{{ reportRiskCounts.HIGH || 0 }}</b></div>
        </div>
        <section class="report-section">
          <h3>联动动作</h3>
          <p v-if="!Object.keys(reportActionCounts).length">今日暂无联动动作</p>
          <div v-else class="action-count-list">
            <span v-for="[type, count] in Object.entries(reportActionCounts)" :key="type">
              {{ actionTypeText(type) }} <b>{{ count }}</b>
            </span>
          </div>
        </section>
        <section class="report-section">
          <h3>事件明细</h3>
          <p v-if="!reportEvents.length">今日暂无安全事件</p>
          <article v-for="event in reportEvents" :key="event.event_id" class="report-event">
            <b :class="riskThemeClass(event.risk_level)">{{ riskLevelText(event.risk_level) }}</b>
            <div>
              <strong>{{ eventTypeFromZoneType(event.zone_type) }}</strong>
              <small>{{ event.event_id }}</small>
              <small>{{ formatEventTime(event.started_at) }} / {{ stateText(event.state) }}</small>
            </div>
          </article>
        </section>
      </div>
      <el-empty v-else description="暂无报告数据" />
      <template #footer>
        <el-button @click="reportDrawerVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="patrolReport?.available === false" :loading="reportSaving" @click="openPatrolReport(true)">
          保存到报告库
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Aim, ArrowLeft, Camera, Crop, DataAnalysis, Delete, Files, FullScreen, Loading, Microphone, Monitor,
  Hide, Picture, UploadFilled, VideoCamera, View,
} from '@element-plus/icons-vue'
import {
  createStreamTicket,
  detectImage, getCameraList, getCameraStatus, getCameraZones, getModelStatus,
  getTodaySafetyReport,
  saveCameraZones,
  snapshotDetect,
} from '@/api/camera'
import {
  classColor as getClassColor, confidencePercent, detectionName,
  detectionInZone, formatDeviceCommTime, isValidDetection,
  normalizeClassifications, normalizeDetections, normalizeZones, primaryClassification,
  shouldStartLiveStreamOnStatus, zoneTypeLabel,
} from '@/utils/cameraDetectionView'
import { camerasFromPayload, readCameraListSnapshot, writeCameraListSnapshot } from '@/utils/cameraSnapshots'
import { CameraWebRtcPlayer } from '@/utils/cameraWebRtc'
import { subscribeDetectionEvents } from '@/utils/detectionEvents'
import BroadcastDialog from '@/components/BroadcastDialog.vue'

const cameras = ref([])
const route = useRoute()
const router = useRouter()
const showLiveChrome = false
const currentCameraId = ref('')
const currentCamera = ref(null)
const selectedPointNo = ref(9)
const mapRegionPointNo = ref(9)
const modelStatus = ref({ loaded: false, models: {} })
const analysisTask = ref('detect')
const detectionEnabled = ref(false)
const detectionToggling = ref(false)
const detectionConnectionState = ref('closed')
const latestDetection = ref({ detections: [], count: 0 })
const detections = ref([])
const detectionZones = ref([])
const debugMode = ref(false)
const nowTick = ref(Date.now())
const eventActionState = ref({})
const broadcastDialogVisible = ref(false)
const broadcastTargetEvent = ref(null)
const reportDrawerVisible = ref(false)
const mapDialogVisible = ref(false)
const reportLoading = ref(false)
const reportSaving = ref(false)
const patrolReport = ref(null)
const zoneOptions = [
  { label: '禁闯入区', value: 'PERSON_LOW' },
  { label: '禁亲水区', value: 'PERSON_MEDIUM' },
  { label: '禁涉水区', value: 'PERSON_HIGH' },
  { label: '禁捕区', value: 'FISHING' },
]
const activeZoneType = ref('PERSON_LOW')
const zoneDrawing = ref(false)
const zoneConfigVisible = ref(false)
const selectedZoneId = ref('')
const zoneVertexDragging = ref(null)
const zoneSaving = ref(false)
const liveVideoRef = ref(null)
const liveImageRef = ref(null)
const streamMode = ref('webrtc')
const streamUrl = ref('')
const streamLoading = ref(false)
const cameraViewMode = ref('single')
const gridStreamUrls = ref({})
const gridStreamModes = ref({})
const gridStreamStates = ref({})
const gridSlotCameraIds = ref([])
const activeGridSlotIndex = ref(0)
const gridCameraZones = ref({})
const gridImageMetrics = ref({})
const assistOverlayVisible = ref(false)
const assistZoneId = ref('')
const singleCameraHidden = ref(false)
const cameraPointDefinitions = [
  { no: 1, x: 17.3410, y: 40.8304 },
  { no: 2, x: 7.3988, y: 15.2249 },
  { no: 3, x: 41.8497, y: 74.0484 },
  { no: 4, x: 47.3988, y: 38.0623 },
  { no: 5, x: 49.2486, y: 38.0623 },
  { no: 6, x: 66.3584, y: 52.5952 },
  { no: 7, x: 68.2081, y: 52.5952 },
  { no: 8, x: 57.3410, y: 75.4325 },
  { no: 9, x: 91.7919, y: 24.2215 },
]
const cameraViewModes = [
  { label: '单画面', value: 'single' },
  { label: '四宫格', value: 'quad' },
  { label: '九宫格', value: 'nine' },
]
const cameraRegionPaths = {
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

const imageUploading = ref(false)
const uploadResult = ref(null)

let statusTimer = null
let clockTimer = null
let streamRetryTimer = null
let closeDetectionEvents = null
let streamRequestGeneration = 0
let cameraMutationRevision = 0
let statusRefreshing = false
let webRtcPlayer = null
const gridVideoRefs = new Map()
const gridWebRtcPlayers = new Map()
let gridStreamRefreshAt = 0
let gridStreamGeneration = 0
let cameraFallbackNoticeAt = 0

const imageWidth = computed(() => Number(latestDetection.value.image_width) || 0)
const imageHeight = computed(() => Number(latestDetection.value.image_height) || 0)
const overlayWidth = computed(() => (
  imageWidth.value
  || Number(liveVideoRef.value?.videoWidth)
  || Number(liveImageRef.value?.naturalWidth)
  || 1920
))
const overlayHeight = computed(() => (
  imageHeight.value
  || Number(liveVideoRef.value?.videoHeight)
  || Number(liveImageRef.value?.naturalHeight)
  || 1080
))
const labelFontSize = computed(() => Math.max(14, imageWidth.value / 55))
const labelPadding = computed(() => labelFontSize.value * 0.35)
const labelHeight = computed(() => labelFontSize.value * 1.35)
const boxStrokeWidth = computed(() => Math.max(2, imageWidth.value / 500))
const visibleDetections = computed(() => detections.value.filter(isValidDetection))
const personDetections = computed(() => visibleDetections.value.filter(isPersonDetection))
const liveAlerts = computed(() => Array.isArray(latestDetection.value.alerts) ? latestDetection.value.alerts : [])
const liveAlertZoneIds = computed(() => new Set(liveAlerts.value.map((alert) => alert.zone_id)))
const zonesForOverlay = computed(() => detectionZones.value)
const showZoneOverlay = computed(() => zoneDrawing.value || detectionZones.value.length > 0)
const assistZoneOptions = computed(() => {
  if (!isMultiCameraMode.value) return zonesForOverlay.value
  const activeCameraId = gridSlots.value[activeGridSlotIndex.value]?.camera?.id || currentCameraId.value
  return activeCameraId ? gridZonesForCamera(activeCameraId) : []
})
const assistZonesForOverlay = computed(() => (
  assistZoneOptions.value.filter((zone) => zone.id === assistZoneId.value)
))
const visibleZonesForOverlay = computed(() => (
  zoneConfigVisible.value || zoneDrawing.value ? zonesForOverlay.value : assistZonesForOverlay.value
))
const streamZoneOverlayVisible = computed(() => assistOverlayVisible.value && assistZonesForOverlay.value.length > 0)
const editableZoneOverlayVisible = computed(() => (
  zoneConfigVisible.value
  || zoneDrawing.value
  || streamZoneOverlayVisible.value
))
const assistOverlayLabel = computed(() => assistOverlayVisible.value ? '隐藏区域辅助框' : '显示区域辅助框')
const selectedZone = computed(() => detectionZones.value.find((zone) => zone.id === selectedZoneId.value) || null)
const zoneVertexAnchorRadius = computed(() => Math.max(6, Math.min(24, overlayWidth.value * 0.006)))
const zoneVertexFontSize = computed(() => Math.max(12, Math.min(34, overlayWidth.value * 0.014)))
const singleCameraSelectValue = computed(() => (singleCameraHidden.value ? '' : currentCameraId.value))
const analysisTaskLabel = computed(() => taskTypeLabel(analysisTask.value))
const selectedModelReady = computed(() => Boolean(modelStatus.value.models?.[analysisTask.value]?.loaded))
const canToggleDetection = computed(() => Boolean(currentCamera.value?.configured || currentCamera.value?.connected))
const canRenderCurrentStream = computed(() => Boolean(currentCamera.value?.configured || currentCamera.value?.connected))
const emergencyBroadcastCamera = computed(() => {
  if (isMultiCameraMode.value) return gridSlots.value[activeGridSlotIndex.value]?.camera || currentCamera.value || null
  return selectedPointSlot.value?.camera || currentCamera.value || null
})
const broadcastUnavailableReason = computed(() => {
  const camera = emergencyBroadcastCamera.value
  if (!camera) return '当前点位未接入摄像头'
  if (!camera.connected) return '当前摄像头离线'
  return ''
})
const isMultiCameraMode = computed(() => cameraViewMode.value !== 'single')
const gridCameraLimit = computed(() => cameraViewMode.value === 'nine' ? 9 : 4)
const cameraById = computed(() => new Map(cameras.value.map((camera) => [camera.id, camera])))
const cameraPointSlots = computed(() => buildCameraPointSlots())
const connectedPointCount = computed(() => cameraPointSlots.value.filter((point) => point.camera).length)
const selectedPointSlot = computed(() => cameraPointSlots.value.find((point) => point.no === selectedPointNo.value) || cameraPointSlots.value[0])
const selectedPointTitle = computed(() => selectedPointSlot.value?.camera?.name || `${selectedPointNo.value}号监测点`)
const selectedMapRegionPath = computed(() => {
  if (!mapRegionPointNo.value) return ''
  const point = cameraPointSlots.value.find((item) => item.no === mapRegionPointNo.value)
  return cameraRegionPaths[mapRegionPointNo.value] || regionPathFromPoint(point)
})
const selectedMapRegionCallout = computed(() => (
  mapRegionPointNo.value ? regionCalloutFromPath(selectedMapRegionPath.value, mapRegionPointNo.value) : null
))
const gridSlots = computed(() => Array.from({ length: gridCameraLimit.value }, (_, index) => {
  const cameraId = gridSlotCameraIds.value[index]
  const camera = cameraId ? cameraById.value.get(cameraId) : null
  return {
    index,
    camera: camera || null,
    slotKey: `slot-${index}-${camera?.id || 'empty'}`,
  }
}))
const normalizedSafetyEvents = computed(() => buildRiskEvents())
const activeRiskEvents = computed(() => normalizedSafetyEvents.value.filter((event) => event.risk_level !== 'NONE' && event.state !== 'RESOLVED'))
const primaryRiskEvent = computed(() => activeRiskEvents.value[0] || null)
const overallRiskLevel = computed(() => activeRiskEvents.value.reduce((level, event) => (
  riskRank(event.risk_level) > riskRank(level) ? event.risk_level : level
), 'NONE'))
const overallRiskText = computed(() => (overallRiskLevel.value === 'NONE' ? '安全' : riskLevelText(overallRiskLevel.value)))
const imageDetections = computed(() => normalizeDetections(uploadResult.value))
const liveClassifications = computed(() => normalizeClassifications(latestDetection.value))
const livePrediction = computed(() => primaryClassification(latestDetection.value))
const imageClassifications = computed(() => normalizeClassifications(uploadResult.value))
const imagePrediction = computed(() => primaryClassification(uploadResult.value))
const reportRiskCounts = computed(() => patrolReport.value?.risk_counts || {})
const reportActionCounts = computed(() => patrolReport.value?.action_counts || {})
const reportEvents = computed(() => Array.isArray(patrolReport.value?.events) ? patrolReport.value.events : [])
const engineEventCount = computed(() => (
  Array.isArray(latestDetection.value.safety_events) ? latestDetection.value.safety_events.length : 0
))
const watersideHitCount = computed(() => liveAlerts.value.filter((alert) => isZoneType(alert, ['PERSON_MEDIUM'])).length)
const wadingHitCount = computed(() => liveAlerts.value.filter((alert) => isZoneType(alert, ['PERSON_HIGH'])).length)
const latestDetectionTimeText = computed(() => latestDetection.value.timestamp ? formatDeviceCommTime(latestDetection.value.timestamp) : '--')
const latestDetectionClasses = computed(() => {
  if (!visibleDetections.value.length) return '--'
  return visibleDetections.value
    .slice(0, 4)
    .map((detection) => `${detectionName(detection)} ${confidencePercent(detection)}%`)
    .join(' / ')
})
const zoneHitSummary = computed(() => {
  if (!liveAlerts.value.length) return '暂无区域命中'
  return liveAlerts.value
    .slice(0, 3)
    .map((alert) => `${alert.zone_name || zoneTypeLabel(alert.zone_type || alert.type)} ${riskLevelText(alert.risk_level || 'LOW')}`)
    .join(' / ')
})
const diagnosticItems = computed(() => [
  {
    label: '检测到人员',
    value: String(personDetections.value.length),
    hint: `总目标 ${visibleDetections.value.length}`,
    tone: personDetections.value.length ? 'ok' : 'muted',
  },
  {
    label: '区域命中',
    value: String(liveAlerts.value.length),
    hint: zoneHitSummary.value,
    tone: liveAlerts.value.length ? 'warn' : 'muted',
  },
  {
    label: '中/高风险',
    value: `${watersideHitCount.value}/${wadingHitCount.value}`,
    hint: '中风险命中 / 高风险命中',
    tone: wadingHitCount.value ? 'high' : watersideHitCount.value ? 'medium' : 'muted',
  },
  {
    label: '事件引擎',
    value: String(engineEventCount.value),
    hint: activeRiskEvents.value.length ? `${overallRiskText.value} ${activeRiskEvents.value.length} 起` : '暂无风险事件',
    tone: activeRiskEvents.value.length ? riskThemeClass(overallRiskLevel.value).replace('risk-', '') : 'muted',
  },
  {
    label: '结果通道',
    value: detectionEnabled.value ? detectionStatusText.value : '未开启',
    hint: analysisTask.value === 'detect' ? '目标检测模式' : '当前不是目标检测',
    tone: detectionEnabled.value && analysisTask.value === 'detect' ? 'ok' : 'muted',
  },
])
const riskSummaryItems = computed(() => [
  {
    label: '检测人员',
    value: String(personDetections.value.length),
    hint: `总目标 ${visibleDetections.value.length}`,
    tone: personDetections.value.length ? 'ok' : 'muted',
  },
  {
    label: '区域命中',
    value: String(liveAlerts.value.length),
    hint: liveAlerts.value.length ? zoneHitSummary.value : '暂无命中',
    tone: liveAlerts.value.length ? 'warn' : 'muted',
  },
  {
    label: '中/高风险',
    value: `${watersideHitCount.value}/${wadingHitCount.value}`,
    hint: '中风险 / 高风险',
    tone: wadingHitCount.value ? 'high' : watersideHitCount.value ? 'medium' : 'muted',
  },
  {
    label: '分析状态',
    value: detectionEnabled.value ? detectionStatusText.value : '未开启',
    hint: analysisTask.value === 'detect' ? '目标检测模式' : '图片分类模式',
    tone: detectionEnabled.value && analysisTask.value === 'detect' ? 'ok' : 'muted',
  },
])
const telemetryEmptyText = computed(() => {
  if (!detectionEnabled.value) return `启动${analysisTaskLabel.value}后在此显示实时结果`
  return analysisTask.value === 'detect'
    ? '正在分析画面，当前未发现目标'
    : '正在分析画面，等待分类结果'
})

const detectionStatusText = computed(() => {
  if (!detectionEnabled.value) return '待机'
  if (detectionConnectionState.value === 'connected') return '分析中'
  if (detectionConnectionState.value === 'reconnecting') return '结果重连'
  return '启动中'
})
const detectionStatusClass = computed(() => detectionEnabled.value ? 'metric-active' : '')
const isMediaAnalysisRoute = computed(() => ['image', 'video'].includes(route.meta.mediaTab))
const mediaTab = computed(() => route.meta.mediaTab === 'video' ? 'video' : 'image')

function openMediaAnalysisPage() {
  router.push('/monitor/camera/image')
}

function backToCameraView() {
  router.push('/monitor/camera')
}

function riskRank(level) {
  return ({ NONE: 0, LOW: 1, MEDIUM: 2, HIGH: 3 })[level] || 0
}

function isPersonDetection(detection) {
  const classId = Number(detection?.class_id)
  const name = String(detection?.class_name || '').toLowerCase()
  const nameCn = String(detection?.class_name_cn || '')
  return [1, 2, 3].includes(classId)
    || name.includes('person')
    || nameCn.includes('人员')
    || nameCn.includes('人')
}

function isZoneType(alert, candidates) {
  const values = [
    String(alert?.zone_type || ''),
    String(alert?.type || ''),
  ]
  return values.some((value) => candidates.includes(value))
}

function riskLevelText(level) {
  return ({
    NONE: '安全',
    LOW: '低风险',
    MEDIUM: '中风险',
    HIGH: '高风险',
  })[level] || '安全'
}

function riskThemeClass(level) {
  return ({
    NONE: 'risk-none',
    LOW: 'risk-low',
    MEDIUM: 'risk-medium',
    HIGH: 'risk-high',
  })[level] || 'risk-none'
}

function eventTypeFromZoneType(type) {
  return ({
    PERSON_LOW: '人员闯入',
    PERSON_MEDIUM: '人员亲水',
    PERSON_HIGH: '人员涉水',
    FISHING: '非法捕鱼',
  })[type] || '区域风险事件'
}

function stateText(state) {
  return ({
    DETECTED: '持续观察',
    LOW_RISK: '低风险预警',
    MEDIUM_RISK: '风险升级',
    HIGH_RISK: '紧急告警',
    RESOLVED: '已离开',
  })[state] || '待确认'
}

function actionText(event, actionType) {
  const local = eventActionState.value[event.event_id]?.[actionType]
  if (local) return local
  if (actionType === 'broadcast') return event.risk_level === 'LOW' ? '已自动喊话' : '已自动广播'
  if (actionType === 'disposal') return disposalStatusText(event.disposal_status || (event.risk_level === 'HIGH' ? 'WAITING_MANUAL' : 'AUTO_HANDLING'))
  return '待处理'
}

function targetStatusText(status) {
  return ({
    IN_DANGER: '仍在风险区',
    LEFT: '已离开',
  })[status] || status || '仍在风险区'
}

function disposalStatusText(status) {
  return ({
    MONITORING: '持续监测',
    AUTO_HANDLING: '系统自动处理中',
    DEVICE_HANDLING: '无人设备自动处置中',
    WAITING_MANUAL: '等待工作人员接单',
    MANUAL_HANDLING: '人工处置中',
    RESOLVED: '已解除',
    FAILED: '处置失败',
  })[status] || status || '待处理'
}

function buildRiskEvents() {
  const events = Array.isArray(latestDetection.value.safety_events)
    ? latestDetection.value.safety_events
    : []
  const mapped = events.map((event, index) => {
    const eventId = event.event_id || `evt_live_${index}`
    const riskLevel = event.risk_level || 'NONE'
    const startedAt = Number(event.started_at || event.danger_started_at || event.first_seen_at || latestDetection.value.timestamp || Date.now() / 1000)
    return {
      instance_id: event.instance_id || event.id,
      event_id: eventId,
      risk_level: riskLevel,
      event_type: eventTypeFromZoneType(event.zone_roles?.[0]),
      camera_id: event.camera_id || currentCameraId.value,
      camera_name: currentCamera.value?.name || currentCameraId.value,
      started_at: startedAt,
      duration_seconds: Math.max(0, Math.floor(nowTick.value / 1000 - startedAt)),
      state: event.state || 'DETECTED',
      state_text: stateText(event.state),
      handling_mode: event.handling_mode,
      raw_disposal_status: event.disposal_status,
      target_status: targetStatusText(event.target_status || (event.state === 'RESOLVED' ? 'LEFT' : 'IN_DANGER')),
      broadcast_status: actionText({ event_id: eventId, risk_level: riskLevel }, 'broadcast'),
      disposal_status: actionText({ event_id: eventId, risk_level: riskLevel, disposal_status: event.disposal_status }, 'disposal'),
      snapshot_path: event.snapshot_path,
    }
  })

  if (mapped.some((event) => event.risk_level !== 'NONE')) {
    return mapped.sort((a, b) => riskRank(b.risk_level) - riskRank(a.risk_level))
  }

  return liveAlerts.value.map((alert, index) => {
    const riskLevel = alert.risk_level || (alert.type === 'PERSON_HIGH' ? 'HIGH' : alert.type === 'PERSON_MEDIUM' ? 'MEDIUM' : 'LOW')
    const eventId = `evt_${alert.zone_id || 'zone'}_${alert.detection_index ?? index}`
    const startedAt = Number(latestDetection.value.timestamp || Date.now() / 1000)
    return {
      event_id: eventId,
      risk_level: riskLevel,
      event_type: eventTypeFromZoneType(alert.zone_type || alert.type),
      camera_id: currentCameraId.value,
      camera_name: currentCamera.value?.name || currentCameraId.value,
      started_at: startedAt,
      duration_seconds: Math.max(0, Math.floor(nowTick.value / 1000 - startedAt)),
      state: `${riskLevel}_RISK`,
      state_text: riskLevelText(riskLevel),
      handling_mode: riskLevel === 'HIGH' ? 'MANUAL' : riskLevel === 'MEDIUM' ? 'AUTO_DEVICE' : 'AUTO',
      raw_disposal_status: riskLevel === 'HIGH' ? 'WAITING_MANUAL' : riskLevel === 'MEDIUM' ? 'DEVICE_HANDLING' : 'AUTO_HANDLING',
      target_status: '仍在风险区',
      broadcast_status: actionText({ event_id: eventId, risk_level: riskLevel }, 'broadcast'),
      disposal_status: actionText({
        event_id: eventId,
        risk_level: riskLevel,
        disposal_status: riskLevel === 'HIGH' ? 'WAITING_MANUAL' : riskLevel === 'MEDIUM' ? 'DEVICE_HANDLING' : 'AUTO_HANDLING',
      }, 'disposal'),
    }
  }).sort((a, b) => riskRank(b.risk_level) - riskRank(a.risk_level))
}

function alertForDetection(index) {
  return liveAlerts.value.find((alert) => alert.detection_index === index)
}

function detectionRiskColor(index) {
  const alert = alertForDetection(index)
  const risk = alert?.risk_level || primaryRiskEvent.value?.risk_level || 'NONE'
  return ({
    NONE: '#62d7b1',
    LOW: '#f1c45b',
    MEDIUM: '#f08a3c',
    HIGH: '#ff4d5e',
  })[risk] || '#62d7b1'
}

function detectionOverlayText(detection, index) {
  if (debugMode.value) {
    return `${detectionName(detection)} ${confidencePercent(detection)}% ${detection.track_id || ''}`.trim()
  }
  const alert = alertForDetection(index)
  if (!alert) return ''
  const risk = alert.risk_level || primaryRiskEvent.value?.risk_level || 'LOW'
  const duration = primaryRiskEvent.value ? ` ${formatDuration(primaryRiskEvent.value.duration_seconds)}` : ''
  return `${riskLevelText(risk)}${duration}`
}

function labelWidthForText(text, fontSize, padding) {
  return String(text || '').length * fontSize * 0.72 + padding * 2
}

function formatDuration(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes <= 0) return `${rest}秒`
  return `${minutes}分${String(rest).padStart(2, '0')}秒`
}

function formatEventTime(timestamp) {
  const numeric = Number(timestamp)
  if (!Number.isFinite(numeric) || numeric <= 0) return '--'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(numeric * 1000))
}

function setEventAction(event, key, value) {
  eventActionState.value = {
    ...eventActionState.value,
    [event.event_id]: {
      ...(eventActionState.value[event.event_id] || {}),
      [key]: value,
    },
  }
}

function manualBroadcast(event) {
  broadcastTargetEvent.value = event
  broadcastDialogVisible.value = true
}

function handleBroadcastPlayed({ event, result }) {
  setEventAction(event, 'broadcast', result === 'PARTIAL_SUCCESS' ? '部分喊话成功' : '人工喊话已执行')
}

function openEmergencyBroadcast() {
  const camera = emergencyBroadcastCamera.value
  if (!camera) return
  broadcastTargetEvent.value = {
    event_id: null,
    camera_id: camera.id,
    camera_name: camera.name || camera.camera_name || camera.id,
    event_type: '一键喊话',
    risk_level: overallRiskLevel.value === 'NONE' ? 'LOW' : overallRiskLevel.value,
  }
  broadcastDialogVisible.value = true
}

async function toggleAssistOverlay(value) {
  assistOverlayVisible.value = Boolean(value)
  if (!assistOverlayVisible.value) return
  await ensureAssistZoneOptions()
  syncAssistZoneSelection()
}

async function openPatrolReport(persist = false) {
  if (persist) reportSaving.value = true
  else reportLoading.value = true
  try {
    const response = await getTodaySafetyReport({
      camera_id: currentCameraId.value || undefined,
      persist,
    })
    patrolReport.value = response.data || null
    reportDrawerVisible.value = true
    if (persist) ElMessage.success('巡查报告已保存到报告库')
  } finally {
    reportLoading.value = false
    reportSaving.value = false
  }
}

function actionTypeText(type) {
  return ({
    event_created: '事件创建',
    risk_changed: '风险变化',
    broadcast_requested: '广播驱离',
    push_requested: '告警推送',
    drone_dispatch_requested: '无人机派飞',
    staff_task_requested: '现场处置',
    event_resolved: '事件关闭',
  })[type] || type
}

function sourceTypeLabel(type) {
  return ({ rtsp: 'RTSP', usb: 'USB / V4L2' })[type] || 'VIDEO'
}

function taskTypeLabel(taskType) {
  return taskType === 'classify' ? '图片分类' : '目标检测'
}

async function fetchModelStatus() {
  try {
    const response = await getModelStatus({ silentError: true })
    modelStatus.value = response.data || { loaded: false, models: {} }
  } catch {
    modelStatus.value = { loaded: false, models: {} }
  }
}

function applyCameraList(nextCameras) {
  cameras.value = nextCameras
  if (!currentCameraId.value && cameras.value.length && !singleCameraHidden.value) {
    currentCameraId.value = cameras.value[0].id
  }
  currentCamera.value = cameras.value.find((item) => item.id === currentCameraId.value) || null
  syncSelectedPointFromCamera(currentCamera.value)
  syncGridSlots()
}

function notifyCameraListFallback(message) {
  const now = Date.now()
  if (now - cameraFallbackNoticeAt < 10000) return
  cameraFallbackNoticeAt = now
  ElMessage.warning(message)
}

async function fetchCameras(options = {}) {
  try {
    const response = await getCameraList({ silentError: true })
    const nextCameras = camerasFromPayload(response.data)
    applyCameraList(nextCameras)
    writeCameraListSnapshot(nextCameras)
    return true
  } catch (error) {
    const fallback = cameras.value.length ? cameras.value : readCameraListSnapshot()
    if (fallback.length) {
      applyCameraList(fallback)
      if (!options.silent) notifyCameraListFallback('后端暂时不可达，已保留上次摄像头列表')
      return false
    }
    if (!options.silent) ElMessage.error('摄像头列表暂时不可达，请检查后端服务')
    return false
  }
}

function cameraPointNo(camera) {
  const direct = Number(camera?.point_no ?? camera?.pointNo ?? camera?.monitor_point_no)
  if (Number.isInteger(direct) && direct >= 1 && direct <= 9) return direct
  const text = [
    camera?.name,
    camera?.camera_name,
    camera?.install_address,
    camera?.description,
  ].filter(Boolean).join(' ')
  const match = text.match(/([1-9])\s*号/)
  return match ? Number(match[1]) : null
}

function buildCameraPointSlots() {
  const assigned = new Map()
  const unassigned = []
  cameras.value.forEach((camera) => {
    const no = cameraPointNo(camera)
    if (no && !assigned.has(no)) assigned.set(no, camera)
    else unassigned.push(camera)
  })
  if (!assigned.has(9) && unassigned.length) assigned.set(9, unassigned[0])
  return cameraPointDefinitions.map((point) => {
    return { ...point, camera: assigned.get(point.no) || null }
  })
}

function syncSelectedPointFromCamera(camera) {
  const no = cameraPointNo(camera)
  if (no) {
    selectedPointNo.value = no
    return
  }
  const fallbackPoint = cameraPointSlots.value.find((point) => point.camera?.id === camera?.id)
  if (fallbackPoint) selectedPointNo.value = fallbackPoint.no
}

function pointStatusText(point) {
  if (!point.camera) return '未接入'
  return point.camera.connected ? '在线' : '离线'
}

async function selectPointFromPanel(pointNo) {
  const slot = cameraPointSlots.value.find((point) => point.no === pointNo)
  selectedPointNo.value = pointNo
  if (!slot?.camera) {
    ElMessage.info(`${pointNo}号监测点暂未接入摄像头`)
    return
  }
  currentCameraId.value = slot.camera.id
  currentCamera.value = slot.camera
  if (isMultiCameraMode.value) {
    await setGridSlotCamera(activeGridSlotIndex.value, slot.camera.id)
    return
  }
  await selectCameraFromPanel(slot.camera.id)
}

function syncMapRegionSelection() {
  mapRegionPointNo.value = selectedPointNo.value || null
}

async function toggleMapPointRegion(pointNo) {
  if (mapRegionPointNo.value === pointNo) {
    mapRegionPointNo.value = null
    return
  }
  mapRegionPointNo.value = pointNo
  await selectPointFromPanel(pointNo)
}

function syncGridSlots() {
  const limit = gridCameraLimit.value
  activeGridSlotIndex.value = Math.min(activeGridSlotIndex.value, limit - 1)
  const orderedCameras = cameraPointSlots.value.map((point) => point.camera).filter(Boolean)
  const validIds = new Set(cameras.value.map((camera) => camera.id))
  const nextSlots = gridSlotCameraIds.value
    .slice(0, limit)
    .map((cameraId) => {
      if (cameraId === '') return ''
      return validIds.has(cameraId) ? cameraId : null
    })
  const usedIds = new Set(nextSlots.filter(Boolean))
  let cameraIndex = 0

  for (let index = 0; index < limit; index += 1) {
    if (nextSlots[index] !== null && nextSlots[index] !== undefined) continue
    while (cameraIndex < orderedCameras.length && usedIds.has(orderedCameras[cameraIndex].id)) {
      cameraIndex += 1
    }
    const cameraId = orderedCameras[cameraIndex]?.id || ''
    nextSlots[index] = cameraId
    if (cameraId) usedIds.add(cameraId)
  }

  while (nextSlots.length < limit) {
    const camera = orderedCameras.find((item) => !usedIds.has(item.id))
    nextSlots.push(camera?.id || '')
    if (camera) usedIds.add(camera.id)
  }

  gridSlotCameraIds.value = nextSlots
}

async function fetchCameraZones(cameraId = currentCameraId.value) {
  if (!cameraId) {
    detectionZones.value = []
    return
  }
  const response = await getCameraZones(cameraId, { silentError: true })
  const zones = normalizeZones(response.data)
  gridCameraZones.value = {
    ...gridCameraZones.value,
    [cameraId]: zones,
  }
  if (cameraId === currentCameraId.value) {
    detectionZones.value = zones
    selectedZoneId.value = zones.find((zone) => zone.id === selectedZoneId.value)?.id || zones[0]?.id || ''
    syncAssistZoneSelection(zones)
  }
}

function buildZoneAlert(zone, detection, index) {
  return {
    zone_id: zone.id,
    zone_name: zone.name || zoneTypeLabel(zone.type),
    type: zone.type,
    message: zoneTypeLabel(zone.type),
    detection_index: index,
    class_id: detection.class_id,
    class_name: detection.class_name,
    class_name_cn: detection.class_name_cn,
    confidence: detection.confidence,
    bbox: detection.bbox,
  }
}

function enrichDetectionPayload(payload) {
  const normalized = normalizeDetections(payload)
  const backendAlerts = Array.isArray(payload?.alerts) ? payload.alerts : []
  const alertKeys = new Set(backendAlerts.map((item) => `${item.zone_id}-${item.detection_index}`))
  const localAlerts = []
  normalized.forEach((detection, index) => {
    detectionZones.value.forEach((zone) => {
      if (!zone.enabled || !detectionInZone(detection, zone, Number(payload.image_width), Number(payload.image_height))) return
      const key = `${zone.id}-${index}`
      if (!alertKeys.has(key)) localAlerts.push(buildZoneAlert(zone, detection, index))
    })
  })
  const alerts = [...backendAlerts, ...localAlerts]
  return { ...payload, alerts, alert_count: alerts.length }
}

function stopLiveStream() {
  clearTimeout(streamRetryTimer)
  streamRequestGeneration += 1
  streamUrl.value = ''
  streamLoading.value = false
  const player = webRtcPlayer
  webRtcPlayer = null
  player?.close()
}

function stopGridStreams() {
  gridStreamGeneration += 1
  gridWebRtcPlayers.forEach((player) => player.close())
  gridWebRtcPlayers.clear()
  gridVideoRefs.clear()
  gridStreamUrls.value = {}
  gridStreamModes.value = {}
  gridStreamStates.value = {}
  gridStreamRefreshAt = 0
}

function stopGridCameraStream(cameraId) {
  const player = gridWebRtcPlayers.get(cameraId)
  if (player) {
    player.close()
    gridWebRtcPlayers.delete(cameraId)
  }
  gridVideoRefs.delete(cameraId)
  const { [cameraId]: _url, ...nextUrls } = gridStreamUrls.value
  const { [cameraId]: _mode, ...nextModes } = gridStreamModes.value
  const { [cameraId]: _state, ...nextStates } = gridStreamStates.value
  gridStreamUrls.value = nextUrls
  gridStreamModes.value = nextModes
  gridStreamStates.value = nextStates
}

function setGridVideoRef(cameraId, element) {
  if (!cameraId) return
  if (element) gridVideoRefs.set(cameraId, element)
  else gridVideoRefs.delete(cameraId)
}

function handleGridImageLoad(cameraId, event) {
  const image = event.target
  gridImageMetrics.value = {
    ...gridImageMetrics.value,
    [cameraId]: {
      width: Number(image?.naturalWidth) || 1920,
      height: Number(image?.naturalHeight) || 1080,
    },
  }
}

function handleGridVideoLoad(cameraId, event) {
  const video = event.target
  gridImageMetrics.value = {
    ...gridImageMetrics.value,
    [cameraId]: {
      width: Number(video?.videoWidth) || 1920,
      height: Number(video?.videoHeight) || 1080,
    },
  }
}

function gridOverlaySize(cameraId) {
  return gridImageMetrics.value[cameraId] || { width: 1920, height: 1080 }
}

function gridZonesForCamera(cameraId) {
  const zones = gridCameraZones.value[cameraId]
  return Array.isArray(zones) ? zones : []
}

function gridAssistZonesForCamera(cameraId) {
  const activeCameraId = gridSlots.value[activeGridSlotIndex.value]?.camera?.id || currentCameraId.value
  if (cameraId !== activeCameraId) return []
  return gridZonesForCamera(cameraId).filter((zone) => zone.id === assistZoneId.value)
}

function syncAssistZoneSelection(zones = assistZoneOptions.value) {
  const availableZones = Array.isArray(zones) ? zones : []
  assistZoneId.value = availableZones.find((zone) => zone.id === assistZoneId.value)?.id || ''
}

async function ensureAssistZoneOptions() {
  if (isMultiCameraMode.value) {
    const activeCameraId = gridSlots.value[activeGridSlotIndex.value]?.camera?.id || currentCameraId.value
    if (activeCameraId) await ensureGridCameraZones(activeCameraId)
    return
  }
  if (currentCameraId.value && !detectionZones.value.length) await fetchCameraZones(currentCameraId.value)
}

function gridZoneOverlayVisible(slot) {
  const camera = slot?.camera
  return Boolean(
    assistOverlayVisible.value
    && slot?.index === activeGridSlotIndex.value
    && camera?.id
    && gridSlotHasStream({ camera })
    && gridAssistZonesForCamera(camera.id).length,
  )
}

function gridSlotHasStream(slot) {
  const cameraId = slot.camera?.id
  if (!cameraId) return false
  const mode = gridStreamModes.value[cameraId]
  if (mode === 'webrtc') return gridStreamStates.value[cameraId] !== 'failed'
  return mode === 'mjpeg' && Boolean(gridStreamUrls.value[cameraId])
}

async function ensureGridCameraZones(cameraId) {
  if (!cameraId || Object.prototype.hasOwnProperty.call(gridCameraZones.value, cameraId)) return
  try {
    const response = await getCameraZones(cameraId, { silentError: true })
    gridCameraZones.value = {
      ...gridCameraZones.value,
      [cameraId]: normalizeZones(response.data),
    }
  } catch {
    gridCameraZones.value = {
      ...gridCameraZones.value,
      [cameraId]: [],
    }
  }
}

async function startGridMjpegStream(cameraId) {
  const generation = gridStreamGeneration
  const player = gridWebRtcPlayers.get(cameraId)
  if (player) {
    player.close()
    gridWebRtcPlayers.delete(cameraId)
  }
  gridStreamModes.value = {
    ...gridStreamModes.value,
    [cameraId]: 'mjpeg',
  }
  gridStreamStates.value = {
    ...gridStreamStates.value,
    [cameraId]: 'connecting',
  }
  try {
    const response = await createStreamTicket(cameraId, false)
    if (!isMultiCameraMode.value || generation !== gridStreamGeneration || !gridSlotCameraIds.value.includes(cameraId)) return
    gridStreamUrls.value = {
      ...gridStreamUrls.value,
      [cameraId]: response.data.stream_url,
    }
    gridStreamStates.value = {
      ...gridStreamStates.value,
      [cameraId]: 'connected',
    }
  } catch {
    if (generation !== gridStreamGeneration || !gridSlotCameraIds.value.includes(cameraId)) return
    gridStreamStates.value = {
      ...gridStreamStates.value,
      [cameraId]: 'failed',
    }
  }
}

function handleGridWebRtcStreamFailure(cameraId, generation = gridStreamGeneration) {
  if (generation !== gridStreamGeneration || !gridSlotCameraIds.value.includes(cameraId)) return
  const player = gridWebRtcPlayers.get(cameraId)
  if (player) {
    player.close()
    gridWebRtcPlayers.delete(cameraId)
  }
  gridStreamModes.value = {
    ...gridStreamModes.value,
    [cameraId]: 'webrtc',
  }
  gridStreamStates.value = {
    ...gridStreamStates.value,
    [cameraId]: 'failed',
  }
  if (isMultiCameraMode.value) {
    startGridMjpegStream(cameraId).catch(() => null)
  }
}

async function startGridWebRtcStream(camera) {
  const generation = gridStreamGeneration
  const cameraId = camera?.id
  if (!cameraId || !camera.connected) return
  if (camera.source_type !== 'rtsp') {
    await startGridMjpegStream(cameraId)
    return
  }
  // 复用条件：已有连接、模式为 webrtc、且播放器绑定的 video 元素与当前 DOM 元素一致。
  // 四宫格中点击点位会把该摄像头移到首位，格子 key 变化导致 video 元素重建，
  // 若直接复用旧播放器则新元素没有画面（黑屏），必须在新元素上重新建立连接。
  const existingPlayer = gridWebRtcPlayers.get(cameraId)
  const currentVideoElement = gridVideoRefs.get(cameraId)
  if (existingPlayer
    && gridStreamModes.value[cameraId] === 'webrtc'
    && currentVideoElement
    && existingPlayer.videoElement === currentVideoElement) {
    return
  }

  const boundVideoElement = currentVideoElement || null
  stopGridCameraStream(cameraId)
  if (boundVideoElement) gridVideoRefs.set(cameraId, boundVideoElement)
  gridStreamModes.value = {
    ...gridStreamModes.value,
    [cameraId]: 'webrtc',
  }
  gridStreamStates.value = {
    ...gridStreamStates.value,
    [cameraId]: 'connecting',
  }
  await nextTick()
  if (generation !== gridStreamGeneration || !gridSlotCameraIds.value.includes(cameraId)) return

  const videoElement = gridVideoRefs.get(cameraId)
  if (!videoElement) {
    handleGridWebRtcStreamFailure(cameraId, generation)
    return
  }

  const player = new CameraWebRtcPlayer(videoElement, cameraId, {
    onConnected() {
      if (generation !== gridStreamGeneration || gridWebRtcPlayers.get(cameraId) !== player || !isMultiCameraMode.value) return
      gridStreamStates.value = {
        ...gridStreamStates.value,
        [cameraId]: 'connected',
      }
    },
    onError() {
      if (generation !== gridStreamGeneration || gridWebRtcPlayers.get(cameraId) !== player || !isMultiCameraMode.value) return
      handleGridWebRtcStreamFailure(cameraId, generation)
    },
  })
  gridWebRtcPlayers.set(cameraId, player)
  try {
    await player.connect()
  } catch {
    if (gridWebRtcPlayers.get(cameraId) === player && isMultiCameraMode.value) {
      handleGridWebRtcStreamFailure(cameraId, generation)
    }
  }
}

async function startMjpegStream() {
  const player = webRtcPlayer
  webRtcPlayer = null
  player?.close()
  streamMode.value = 'mjpeg'
  streamLoading.value = true
  await nextTick()
  await refreshStreamTicket()
}

function handleWebRtcStreamFailure(error) {
  const player = webRtcPlayer
  webRtcPlayer = null
  player?.close()
  streamMode.value = 'webrtc'
  streamUrl.value = ''
  streamLoading.value = false
  ElMessage.error(error?.message || 'WebRTC 实时视频连接失败')
}

async function startLiveStream() {
  const cameraId = currentCameraId.value
  if (!cameraId || !canRenderCurrentStream.value) return
  if (currentCamera.value.source_type !== 'rtsp') {
    await startMjpegStream()
    return
  }

  streamMode.value = 'webrtc'
  streamUrl.value = ''
  streamLoading.value = true
  await nextTick()
  const player = new CameraWebRtcPlayer(liveVideoRef.value, cameraId, {
    onConnected() {
      if (webRtcPlayer === player && cameraId === currentCameraId.value) streamLoading.value = false
    },
    onError(error) {
      if (webRtcPlayer !== player || cameraId !== currentCameraId.value) return
      handleWebRtcStreamFailure(error)
    },
  })
  webRtcPlayer = player
  try {
    await player.connect()
  } catch (error) {
    if (webRtcPlayer === player && cameraId === currentCameraId.value) {
      handleWebRtcStreamFailure(error)
    }
  }
}

async function activateCamera(cameraId) {
  stopDetectionSubscription()
  stopLiveStream()
  detections.value = []
  latestDetection.value = { detections: [], count: 0 }
  detectionZones.value = []
  assistZoneId.value = ''
  zoneDrawing.value = false
  selectedZoneId.value = ''
  zoneVertexDragging.value = null
  currentCamera.value = cameras.value.find((camera) => camera.id === cameraId) || null
  syncSelectedPointFromCamera(currentCamera.value)
  detectionEnabled.value = false
  stopDetectionSubscription()
  await fetchCameraZones(cameraId).catch(() => {
    const zones = normalizeZones({ zones: currentCamera.value?.detection_zones || [] })
    detectionZones.value = zones
    syncAssistZoneSelection(zones)
    if (cameraId) {
      gridCameraZones.value = {
        ...gridCameraZones.value,
        [cameraId]: zones,
      }
    }
  })
  if (isMediaAnalysisRoute.value) return
  if (cameraViewMode.value === 'single') {
    if (canRenderCurrentStream.value) startLiveStream().catch(() => null)
  } else {
    await refreshGridStreams(true)
  }
}

async function refreshStreamTicket() {
  const cameraId = currentCameraId.value
  if (!cameraId || !canRenderCurrentStream.value) return
  const generation = ++streamRequestGeneration
  streamLoading.value = true
  try {
    const response = await createStreamTicket(cameraId, false)
    if (generation === streamRequestGeneration && cameraId === currentCameraId.value) {
      streamUrl.value = response.data.stream_url
    }
  } catch {
    if (generation === streamRequestGeneration) {
      streamLoading.value = false
      clearTimeout(streamRetryTimer)
      streamRetryTimer = setTimeout(refreshStreamTicket, 2000)
    }
  }
}

async function refreshGridStreams(force = false) {
  if (!isMultiCameraMode.value) {
    stopGridStreams()
    return
  }
  const generation = gridStreamGeneration
  const now = Date.now()
  if (!force && now - gridStreamRefreshAt < 15000) return
  gridStreamRefreshAt = now
  await fetchCameras({ silent: true }).catch(() => null)
  if (generation !== gridStreamGeneration) return
  const gridCameras = gridSlots.value
    .map((slot) => slot.camera)
    .filter((camera, index, list) => camera && list.findIndex((item) => item?.id === camera.id) === index)
  const visibleCameraIds = new Set(gridCameras.map((camera) => camera.id))
  Array.from(gridWebRtcPlayers.keys()).forEach((cameraId) => {
    if (!visibleCameraIds.has(cameraId)) stopGridCameraStream(cameraId)
  })
  Object.keys(gridStreamModes.value).forEach((cameraId) => {
    if (!visibleCameraIds.has(cameraId)) stopGridCameraStream(cameraId)
  })
  await Promise.allSettled(gridCameras.map(async (camera) => {
    await ensureGridCameraZones(camera.id)
    if (!camera.id || !camera.connected) {
      stopGridCameraStream(camera.id)
      return
    }
    // 强制刷新时仅重建没有有效画面的 MJPEG 流，已有画面的保留，避免点击点位后闪黑
    if (force && gridStreamModes.value[camera.id] === 'mjpeg' && !gridStreamUrls.value[camera.id]) stopGridCameraStream(camera.id)
    await startGridWebRtcStream(camera)
  }))
}

function handleGridStreamError(cameraId) {
  gridStreamUrls.value = {
    ...gridStreamUrls.value,
    [cameraId]: '',
  }
  gridStreamStates.value = {
    ...gridStreamStates.value,
    [cameraId]: 'failed',
  }
  setTimeout(() => {
    const camera = cameras.value.find((item) => item.id === cameraId)
    if (isMultiCameraMode.value && camera?.source_type !== 'rtsp') startGridMjpegStream(cameraId).catch(() => null)
  }, 1200)
}

async function setCameraViewMode(mode) {
  if (cameraViewMode.value === mode) return
  cameraViewMode.value = mode
  syncGridSlots()
  if (mode === 'single') {
    stopGridStreams()
    if (!currentCameraId.value && cameras.value.length && !singleCameraHidden.value) {
      currentCameraId.value = cameras.value[0].id
    }
    if (currentCameraId.value) await activateCamera(currentCameraId.value)
  } else {
    stopLiveStream()
    stopDetectionSubscription()
    await refreshGridStreams(true)
    syncAssistZoneSelection()
  }
}

async function handleSingleCameraSelection(cameraId) {
  singleCameraHidden.value = !cameraId
  await activateCamera(cameraId || '')
}

async function selectCameraFromPanel(cameraId) {
  if (!cameraId || cameraId === currentCameraId.value) return
  singleCameraHidden.value = false
  currentCameraId.value = cameraId
  await activateCamera(cameraId)
}

function cameraPointStyle(point) {
  const camera = point.camera
  const x = Number(camera?.map_x ?? camera?.mapX ?? camera?.point_x ?? camera?.longitude_percent ?? point.x)
  const y = Number(camera?.map_y ?? camera?.mapY ?? camera?.point_y ?? camera?.latitude_percent ?? point.y)
  if (Number.isFinite(x) && Number.isFinite(y)) {
    return { left: `${Math.max(4, Math.min(96, x))}%`, top: `${Math.max(6, Math.min(94, y))}%` }
  }
  return { left: '50%', top: '50%' }
}

function regionPathFromPoint(point) {
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

function pointsFromRegionPath(path) {
  const values = String(path || '').match(/-?\d+(\.\d+)?/g)?.map(Number) || []
  const points = []
  for (let index = 0; index < values.length; index += 2) {
    points.push({ x: values[index], y: values[index + 1] })
  }
  return points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
}

function regionCalloutFromPath(path, pointNo) {
  const points = pointsFromRegionPath(path)
  if (!points.length) return null
  const minX = Math.min(...points.map((point) => point.x))
  const maxX = Math.max(...points.map((point) => point.x))
  const minY = Math.min(...points.map((point) => point.y))
  const label = `${pointNo}号摄像头监测区域`
  const width = Math.max(170, label.length * 14)
  return {
    label,
    width,
    x: Math.max(16, Math.min(2168 - width - 16, (minX + maxX) / 2 - width / 2)),
    y: Math.max(18, minY - 58),
  }
}

function gridSlotEmptyText(slot) {
  if (!slot.camera) return '未接入'
  if (gridStreamStates.value[slot.camera.id] === 'failed') {
    return gridStreamModes.value[slot.camera.id] === 'webrtc' ? 'WebRTC 连接失败' : '视频连接失败'
  }
  if (slot.camera.connected) return '正在建立视频链路'
  return slot.camera.last_error || '无视频接入'
}

async function setGridSlotCamera(slotIndex, cameraId) {
  gridStreamGeneration += 1
  const previousCameraId = gridSlotCameraIds.value[slotIndex] || ''
  const nextSlots = Array.from({ length: gridCameraLimit.value }, (_, index) => gridSlotCameraIds.value[index] || '')
  const duplicateSlotIndex = cameraId
    ? nextSlots.findIndex((item, index) => index !== slotIndex && item === cameraId)
    : -1
  if (duplicateSlotIndex >= 0) nextSlots[duplicateSlotIndex] = previousCameraId
  nextSlots[slotIndex] = cameraId || ''
  gridSlotCameraIds.value = nextSlots.map((item, index) => {
    if (index === slotIndex || index === duplicateSlotIndex) return item
    return item || ''
  })
  activeGridSlotIndex.value = slotIndex
  if (cameraId) {
    await activateGridCamera(cameraId)
  } else if (previousCameraId && previousCameraId === currentCameraId.value) {
    const nextActiveSlot = gridSlots.value.find((slot) => slot.camera)
    currentCameraId.value = nextActiveSlot?.camera?.id || ''
    currentCamera.value = currentCameraId.value
      ? cameras.value.find((camera) => camera.id === currentCameraId.value) || null
      : null
  }
  await refreshGridStreams(true)
  syncAssistZoneSelection()
}

async function activateGridCamera(cameraId) {
  currentCameraId.value = cameraId
  currentCamera.value = cameras.value.find((camera) => camera.id === cameraId) || null
  syncSelectedPointFromCamera(currentCamera.value)
  if (cameraViewMode.value === 'single') await activateCamera(cameraId)
}

async function activateGridSlot(slot) {
  activeGridSlotIndex.value = slot.index
  if (!slot.camera) return
  await activateGridCamera(slot.camera.id)
  await ensureGridCameraZones(slot.camera.id)
  syncAssistZoneSelection(gridZonesForCamera(slot.camera.id))
}

function isActiveGridSlot(slot) {
  return slot.index === activeGridSlotIndex.value
}

function handleStreamError() {
  if (streamMode.value !== 'mjpeg') return
  streamLoading.value = true
  streamUrl.value = ''
  clearTimeout(streamRetryTimer)
  streamRetryTimer = setTimeout(refreshStreamTicket, 1200)
}

function startDetectionSubscription() {
  stopDetectionSubscription()
  const cameraId = currentCameraId.value
  if (!cameraId || !detectionEnabled.value) return
  closeDetectionEvents = subscribeDetectionEvents(cameraId, {
    onDetection(payload) {
      if (payload.camera_id !== currentCameraId.value) return
      if (payload.task_type && payload.task_type !== analysisTask.value) return
      const enriched = enrichDetectionPayload(payload)
      latestDetection.value = enriched
      detections.value = normalizeDetections(enriched)
      if (payload.enabled === false) detectionEnabled.value = false
    },
    onState(state) { detectionConnectionState.value = state },
    onError(error) {
      if (error?.status === 401) detectionConnectionState.value = 'closed'
    },
  })
}

function stopDetectionSubscription() {
  closeDetectionEvents?.()
  closeDetectionEvents = null
  detectionConnectionState.value = 'closed'
}

async function toggleLiveDetection() {
  if (!canToggleDetection.value || detectionToggling.value) return
  detectionToggling.value = true
  cameraMutationRevision += 1
  try {
    detectionEnabled.value = false
    currentCamera.value = {
      ...currentCamera.value,
      detection_enabled: false,
      detection_running: false,
    }
    updateCameraInList(currentCamera.value)
    latestDetection.value = { detections: [], count: 0 }
    detections.value = []
    stopDetectionSubscription()
    ElMessage.info('实时 AI 检测功能正在重新设计，暂未启用')
  } finally {
    cameraMutationRevision += 1
    detectionToggling.value = false
  }
}

async function handleAnalysisTaskChange(taskType) {
  const previousTask = currentCamera.value?.analysis_task || 'detect'
  if (!modelStatus.value.models?.[taskType]?.loaded) {
    analysisTask.value = previousTask
    ElMessage.warning(`${taskTypeLabel(taskType)}模型未加载`)
    return
  }
  detectionToggling.value = true
  cameraMutationRevision += 1
  try {
    latestDetection.value = { task_type: taskType, detections: [], classifications: [] }
    detections.value = []
    uploadResult.value = null
    if (!detectionEnabled.value || !currentCameraId.value) return
    detectionEnabled.value = false
    currentCamera.value = {
      ...currentCamera.value,
      detection_enabled: false,
      detection_running: false,
    }
    stopDetectionSubscription()
    updateCameraInList(currentCamera.value)
    ElMessage.info('实时 AI 检测功能正在重新设计，暂未启用')
  } catch {
    analysisTask.value = previousTask
    ElMessage.error('分析方式切换失败，已恢复原模型')
  } finally {
    cameraMutationRevision += 1
    detectionToggling.value = false
  }
}

async function refreshCameraStatus() {
  if (!currentCameraId.value) return
  if (statusRefreshing) return
  statusRefreshing = true
  const statusRevision = cameraMutationRevision
  try {
    const response = await getCameraStatus(currentCameraId.value)
    if (detectionToggling.value || statusRevision !== cameraMutationRevision) return
    const previousConnected = Boolean(currentCamera.value?.connected)
    const backendDetectionEnabled = Boolean(response.data.detection_enabled)
    currentCamera.value = { ...response.data, id: String(response.data.id) }
    if (!detectionZones.value.length && response.data.detection_zones?.length) {
      detectionZones.value = normalizeZones({ zones: response.data.detection_zones })
      gridCameraZones.value = {
        ...gridCameraZones.value,
        [response.data.camera_device_id]: detectionZones.value,
      }
    }
    updateCameraInList(response.data)
    if (shouldStartLiveStreamOnStatus({
      mediaAnalysis: isMediaAnalysisRoute.value,
      viewMode: cameraViewMode.value,
      previousConnected,
      connected: response.data.connected,
      canRender: canRenderCurrentStream.value,
    })) startLiveStream().catch(() => null)
    if (cameraViewMode.value === 'single' && previousConnected && !response.data.connected && !canRenderCurrentStream.value) stopLiveStream()
    if (isMultiCameraMode.value) refreshGridStreams()
    if (backendDetectionEnabled || detectionEnabled.value) {
      detectionEnabled.value = false
      stopDetectionSubscription()
      detections.value = []
    }
  } catch {
    // Keep the active video connection during a transient status request failure.
  } finally {
    statusRefreshing = false
  }
}

function updateCameraInList(camera) {
  const normalized = { ...camera, id: String(camera.id) }
  const index = cameras.value.findIndex((item) => item.id === normalized.id)
  if (index >= 0) cameras.value[index] = normalized
}

function resetStatusTimer() {
  clearInterval(statusTimer)
  statusTimer = setInterval(refreshCameraStatus, isMediaAnalysisRoute.value ? 10000 : 3000)
}

async function takeSnapshot() {
  if (route.path !== '/monitor/camera/image') await router.push('/monitor/camera/image')
  const response = await snapshotDetect(currentCameraId.value, 0.5, analysisTask.value)
  uploadResult.value = { ...response.data, result_image_base64: response.data.image_base64 }
  if (response.data.task_type === 'detect') {
    ElMessage.success(`截图检测完成，发现 ${response.data.count} 个目标`)
  } else {
    ElMessage.success(`截图分类完成：${detectionName(response.data.prediction)}`)
  }
}

async function handleFileUpload(file) {
  const rawFile = file.raw
  if (!rawFile?.type.startsWith('image/')) return ElMessage.error('请选择图片文件')
  if (rawFile.size > 10 * 1024 * 1024) return ElMessage.error('图片大小不能超过 10MB')
  imageUploading.value = true
  try {
    const encoded = await fileToBase64(rawFile)
    const response = await detectImage(encoded, 0.5, analysisTask.value)
    uploadResult.value = response.data
    if (response.data.task_type === 'detect') {
      ElMessage.success(`图片检测完成，发现 ${response.data.count} 个目标`)
    } else {
      ElMessage.success(`图片分类完成：${detectionName(response.data.prediction)}`)
    }
  } finally {
    imageUploading.value = false
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function zonePolygonPoints(zone) {
  return zonePolygonPointsForSize(zone, overlayWidth.value, overlayHeight.value)
}

function zonePolygonPointsForSize(zone, width, height) {
  const points = Array.isArray(zone?.polygon_points) ? zone.polygon_points : []
  return points
    .map((point) => `${point.x * width},${point.y * height}`)
    .join(' ')
}

function zoneLabelPoint(zone) {
  return zoneLabelPointForSize(zone, overlayWidth.value, overlayHeight.value)
}

function zoneLabelPointForSize(zone, width, height) {
  const points = Array.isArray(zone?.polygon_points) ? zone.polygon_points : []
  const first = points[0] || { x: 0, y: 0 }
  return {
    x: Math.max(10, first.x * width + 8),
    y: Math.max(20, first.y * height + 18),
  }
}

async function goZoneConfig() {
  await openZoneConfigPanel()
}

async function openZoneConfigPanel() {
  if (!currentCameraId.value && cameras.value[0]?.id) {
    singleCameraHidden.value = false
    currentCameraId.value = cameras.value[0].id
  }
  if (!currentCameraId.value) return
  if (isMultiCameraMode.value) await setCameraViewMode('single')
  if (!currentCamera.value || currentCamera.value.id !== currentCameraId.value) {
    await activateCamera(currentCameraId.value)
  }
  if (!detectionZones.value.length) await fetchCameraZones(currentCameraId.value).catch(() => null)
  selectedZoneId.value = selectedZoneId.value || detectionZones.value[0]?.id || ''
  assistOverlayVisible.value = true
  zoneConfigVisible.value = true
}

async function toggleZoneConfigPanel() {
  if (zoneConfigVisible.value) {
    zoneConfigVisible.value = false
    zoneDrawing.value = false
    zoneVertexDragging.value = null
    return
  }
  await openZoneConfigPanel()
}

function handleZonePanelClosed() {
  zoneDrawing.value = false
  zoneVertexDragging.value = null
}

function formatZoneTime(zone) {
  const value = zone?.update_time
    || zone?.updated_at
    || zone?.config_time
    || zone?.configured_at
    || zone?.create_time
    || zone?.created_at
  if (!value) return '--'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function selectConfigZone(zoneId) {
  selectedZoneId.value = zoneId
}

function createConfigZone() {
  const zoneType = 'PERSON_LOW'
  const id = `${zoneType}_${Date.now()}`
  const name = `${zoneTypeLabel(zoneType)} ${detectionZones.value.length + 1}`
  const zone = {
    id,
    zone_name: name,
    name,
    zone_type: zoneType,
    type: zoneType,
    polygon_points: [],
    enabled: true,
  }
  detectionZones.value = [...detectionZones.value, zone]
  selectedZoneId.value = id
  return zone
}

function startNewConfigZone() {
  if (!currentCameraId.value) return
  createConfigZone()
  zoneDrawing.value = true
  assistOverlayVisible.value = true
}

function exitZoneDrawing() {
  zoneDrawing.value = false
}

function pointerToUnitPoint(event) {
  const pixel = pointerToImagePoint(event)
  if (!pixel) return null
  return {
    x: Math.max(0, Math.min(1, pixel.x / overlayWidth.value)),
    y: Math.max(0, Math.min(1, pixel.y / overlayHeight.value)),
  }
}

function appendPointToSelectedZone(point) {
  if (!selectedZone.value || !point) return
  if (selectedZone.value.polygon_points.length >= 15) {
    ElMessage.warning('单个区域最多支持 15 个顶点')
    return
  }
  selectedZone.value.polygon_points = [
    ...selectedZone.value.polygon_points,
    { ...point },
  ]
}

function handleConfigZoneOverlayClick(event) {
  if (!zoneDrawing.value) return
  if (!selectedZone.value) createConfigZone()
  appendPointToSelectedZone(pointerToUnitPoint(event))
}

function handleConfigZoneClick(zoneId, event) {
  if (zoneDrawing.value) {
    handleConfigZoneOverlayClick(event)
    return
  }
  selectConfigZone(zoneId)
}

function showConfigZoneAnchors(zone) {
  return zoneConfigVisible.value && zone.id === selectedZoneId.value
}

function startConfigVertexDrag(zoneId, index) {
  selectedZoneId.value = zoneId
  zoneVertexDragging.value = { zoneId, index }
}

function dragConfigVertex(event) {
  if (!zoneVertexDragging.value) return
  const point = pointerToUnitPoint(event)
  const zone = detectionZones.value.find((item) => item.id === zoneVertexDragging.value.zoneId)
  if (!zone || !point) return
  zone.polygon_points[zoneVertexDragging.value.index] = point
}

function endConfigVertexDrag() {
  zoneVertexDragging.value = null
}

function deleteConfigZone(zoneId) {
  detectionZones.value = detectionZones.value.filter((zone) => zone.id !== zoneId)
  selectedZoneId.value = detectionZones.value[0]?.id || ''
  if (!selectedZoneId.value) zoneDrawing.value = false
}

function deleteConfigPoint(index) {
  if (!selectedZone.value) return
  selectedZone.value.polygon_points.splice(index, 1)
}

function appendConfigVertex() {
  if (!selectedZone.value) createConfigZone()
  const points = selectedZone.value?.polygon_points || []
  const lastPoint = points[points.length - 1]
  appendPointToSelectedZone(lastPoint
    ? {
      x: Math.max(0, Math.min(1, lastPoint.x + 0.03)),
      y: Math.max(0, Math.min(1, lastPoint.y + 0.03)),
    }
    : { x: 0.5, y: 0.5 })
}

function applyConfigZoneTypeDefaults(zoneType) {
  if (!selectedZone.value) return
  selectedZone.value.type = zoneType
  selectedZone.value.name = selectedZone.value.zone_name || zoneTypeLabel(zoneType)
}

function pointCoordinateX(point) {
  return Number((point.x * overlayWidth.value).toFixed(3))
}

function pointCoordinateY(point) {
  return Number(((1 - point.y) * overlayHeight.value).toFixed(3))
}

function updatePointCoordinate(index, axis, value) {
  if (!selectedZone.value || !Number.isFinite(Number(value))) return
  const point = selectedZone.value.polygon_points[index]
  if (!point) return
  if (axis === 'x') {
    point.x = Math.max(0, Math.min(1, Number(value) / overlayWidth.value))
  } else {
    point.y = Math.max(0, Math.min(1, 1 - (Number(value) / overlayHeight.value)))
  }
}

function vertexLabelPoint(point) {
  const anchorX = point.x * overlayWidth.value
  const anchorY = point.y * overlayHeight.value
  const offset = zoneVertexAnchorRadius.value + zoneVertexFontSize.value * 0.82
  const rightX = anchorX + offset
  const leftX = anchorX - offset * 1.35
  const belowY = anchorY + offset
  const aboveY = anchorY - offset * 0.72

  return {
    x: rightX < overlayWidth.value - offset ? rightX : Math.max(12, leftX),
    y: anchorY < offset ? belowY : Math.max(zoneVertexFontSize.value, aboveY),
  }
}

async function saveZoneConfig() {
  if (!currentCameraId.value) return false
  const invalidZone = detectionZones.value.find((zone) => zone.polygon_points.length < 3 || zone.polygon_points.length > 15)
  if (invalidZone) {
    selectedZoneId.value = invalidZone.id
    ElMessage.warning('多边形区域必须包含 3 到 15 个顶点')
    return false
  }
  zoneSaving.value = true
  try {
    const payload = detectionZones.value.map((zone) => ({
      id: zone.id,
      zone_name: zone.zone_name,
      zone_type: zone.zone_type,
      polygon_points: zone.polygon_points,
      enabled: zone.enabled,
    }))
    const response = await saveCameraZones(currentCameraId.value, payload)
    detectionZones.value = normalizeZones(response.data)
    selectedZoneId.value = detectionZones.value.find((zone) => zone.id === selectedZoneId.value)?.id || detectionZones.value[0]?.id || ''
    gridCameraZones.value = {
      ...gridCameraZones.value,
      [currentCameraId.value]: detectionZones.value,
    }
    currentCamera.value = { ...currentCamera.value, detection_zones: detectionZones.value }
    updateCameraInList(currentCamera.value)
    latestDetection.value = enrichDetectionPayload(latestDetection.value)
    ElMessage.success(response.data.message || '区域配置已保存')
    return true
  } finally {
    zoneSaving.value = false
  }
}

function pointerToImagePoint(event) {
  const svg = event.currentTarget?.ownerSVGElement
    || event.currentTarget?.closest?.('svg')
    || event.currentTarget
  if (!svg || overlayWidth.value <= 0 || overlayHeight.value <= 0) return null
  if (svg.createSVGPoint) {
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const matrix = svg.getScreenCTM()
    if (matrix) {
      const mapped = point.matrixTransform(matrix.inverse())
      return {
        x: Math.max(0, Math.min(overlayWidth.value, mapped.x)),
        y: Math.max(0, Math.min(overlayHeight.value, mapped.y)),
      }
    }
  }
  const rect = svg.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(overlayWidth.value, (event.clientX - rect.left) / rect.width * overlayWidth.value)),
    y: Math.max(0, Math.min(overlayHeight.value, (event.clientY - rect.top) / rect.height * overlayHeight.value)),
  }
}

function zoneStroke(zone) {
  if (liveAlertZoneIds.value.has(zone.id)) return '#ff5d6c'
  return ({
    PERSON_LOW: '#48d8ff',
    PERSON_MEDIUM: '#ffbd65',
    PERSON_HIGH: '#ff5d6c',
    FISHING: '#51e6be',
  })[zone.type] || '#48d8ff'
}

function zoneFill(zone) {
  if (zone.enabled === false) return 'rgba(120, 139, 153, 0.12)'
  if (liveAlertZoneIds.value.has(zone.id)) return 'rgba(255, 93, 108, 0.20)'
  return ({
    PERSON_LOW: 'rgba(72, 216, 255, 0.10)',
    PERSON_MEDIUM: 'rgba(255, 189, 101, 0.12)',
    PERSON_HIGH: 'rgba(255, 93, 108, 0.12)',
    FISHING: 'rgba(81, 230, 190, 0.10)',
  })[zone.type] || 'rgba(72, 216, 255, 0.10)'
}

function zoneAssistFill(zone) {
  if (zoneConfigVisible.value || zoneDrawing.value || liveAlertZoneIds.value.has(zone.id)) return zoneFill(zone)
  return 'transparent'
}

function detectionLabel(detection) {
  return `${detectionName(detection)} ${confidencePercent(detection)}%`
}
function labelWidth(detection, fontSize, padding) {
  return detectionLabel(detection).length * fontSize * 0.72 + padding * 2
}
function labelY(detection, height) { return Math.max(0, detection.bbox.y1 - height) }
function boxKey(detection, index) {
  return `${latestDetection.value.frame_sequence || 0}-${detection.class_id}-${index}`
}
function formatSeconds(value) {
  const seconds = Number(value || 0)
  return seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(2)} s`
}

onMounted(async () => {
  clockTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
  try {
    await Promise.allSettled([fetchModelStatus(), fetchCameras()])
    if (currentCameraId.value) await activateCamera(currentCameraId.value)
  } catch {
    // Authentication interceptor handles an expired login and redirects once.
  }
  resetStatusTimer()
})

watch(isMediaAnalysisRoute, async (mediaMode) => {
  resetStatusTimer()
  if (mediaMode) {
    zoneConfigVisible.value = false
    zoneDrawing.value = false
    stopLiveStream()
    stopGridStreams()
    stopDetectionSubscription()
    return
  }
  if (currentCameraId.value) await activateCamera(currentCameraId.value)
})

onBeforeUnmount(() => {
  clearInterval(statusTimer)
  clearInterval(clockTimer)
  stopLiveStream()
  stopGridStreams()
  stopDetectionSubscription()
})
</script>

<style scoped>
.vision-page {
  --cyan: #48d8ff;
  --mint: #51e6be;
  --amber: #ffbd65;
  --muted: #7f9bb0;
  min-height: 100%;
  overflow: visible;
  padding: 0;
  color: #e9f7ff;
  background:
    radial-gradient(circle at 15% 0%, rgba(33, 126, 190, 0.18), transparent 30%),
    linear-gradient(145deg, #071522, #091b2d 58%, #071522);
}

.surface-card {
  border: 1px solid rgba(93, 184, 225, 0.17);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(13, 38, 59, 0.94), rgba(8, 26, 43, 0.94));
  box-shadow: 0 18px 42px rgba(0, 7, 18, 0.2), inset 0 1px rgba(255, 255, 255, 0.025);
}

.command-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 18px 22px; }
.title-block { display: flex; align-items: center; gap: 16px; }
.title-icon { width: 50px; height: 50px; display: grid; place-items: center; color: var(--cyan); border: 1px solid rgba(72, 216, 255, 0.26); border-radius: 14px; background: rgba(32, 118, 158, 0.13); }
h1, h2, h3, p { margin-top: 0; }
.title-block h1 { margin: 0; font-size: 24px; letter-spacing: 0.04em; }
.title-description { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.header-status { display: flex; align-items: center; justify-content: flex-end; }
.camera-connection-status {
  min-width: 152px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  text-align: right;
}
.connection-main {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.25;
}
.connection-dot { width: 10px; height: 10px; flex: 0 0 10px; border-radius: 50%; }
.camera-connection-status.online .connection-main { color: var(--success-color, #67c23a); }
.camera-connection-status.online .connection-dot { background: var(--success-color, #67c23a); box-shadow: 0 0 6px var(--success-color, #67c23a); }
.camera-connection-status.offline .connection-main { color: var(--danger-color, #f56c6c); }
.camera-connection-status.offline .connection-dot { background: var(--danger-color, #f56c6c); box-shadow: 0 0 6px var(--danger-color, #f56c6c); }
.connection-time {
  color: #8aa8c7;
  font-size: 11px;
  font-weight: 400;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
}

.source-toolbar { display: grid; grid-template-columns: minmax(280px, 1fr) 220px auto; align-items: center; gap: 18px; margin-top: 12px; padding: 12px 16px; }
.source-toolbar.analysis-toolbar { grid-template-columns: minmax(280px, 1fr) 220px; }
.source-control, .task-control, .toolbar-actions { min-width: 0; display: flex; align-items: center; gap: 10px; }
.control-label { color: #7d9bb0; font-size: 12px; }
.camera-select { width: min(100%, 320px); }
.task-control { padding: 0 14px; border-left: 1px solid rgba(93, 184, 225, 0.13); border-right: 1px solid rgba(93, 184, 225, 0.13); }
.task-select { width: 132px; }
.camera-select :deep(.el-select__wrapper),
.task-select :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 8px;
  background: rgba(6, 28, 44, 0.88);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.26) inset;
}
.camera-select :deep(.el-select__wrapper.is-focused),
.task-select :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--cyan) inset, 0 0 14px rgba(72, 216, 255, 0.12);
}
.camera-select :deep(.el-select__selected-item),
.task-select :deep(.el-select__selected-item) { color: #e6f7ff; font-weight: 600; }
.camera-select :deep(.el-select__caret),
.task-select :deep(.el-select__caret) { color: #8ddcf0; }
:global(.vision-select-popper.el-select__popper) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  background: #082033;
  box-shadow: 0 16px 36px rgba(0, 7, 18, 0.38);
}
:global(.vision-select-popper .el-select-dropdown__item) {
  color: #aecdde;
}
:global(.vision-select-popper .el-select-dropdown__item.is-hovering) {
  color: #e9fbff;
  background: rgba(72, 216, 255, 0.12);
}
:global(.vision-select-popper .el-select-dropdown__item.is-selected) {
  color: #50e1d0;
  font-weight: 800;
}
.camera-option { display: flex; justify-content: space-between; gap: 18px; width: 100%; }
.option-meta { color: #7993a7; font-size: 11px; }
.ghost-button, .detect-button { border-radius: 9px; }
.ghost-button { color: #b4d0df; border-color: rgba(100, 180, 216, 0.21); background: rgba(18, 63, 88, 0.32); }
.ghost-button.active { color: #061b23; border-color: rgba(72, 216, 255, 0.62); background: linear-gradient(110deg, var(--cyan), var(--mint)); font-weight: 800; }
.detect-button { color: #061b23; border: none; font-weight: 700; background: linear-gradient(105deg, #35c8ea, #52e5bd); box-shadow: 0 8px 22px rgba(50, 201, 209, 0.15); }
.detect-button.active { color: #ffe4c3; background: rgba(177, 103, 37, 0.28); box-shadow: inset 0 0 0 1px rgba(255, 181, 89, 0.32); }
.zone-type-select { width: 136px; }
.zone-type-select :deep(.el-select__wrapper) {
  min-height: 32px;
  border-radius: 8px;
  background: rgba(6, 28, 44, 0.88);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.18) inset;
}

.live-workspace { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0; margin-top: 0; }
.live-card { min-height: min(760px, calc(100vh - 132px)); padding: 0; }
.telemetry-card { display: none; }
.card-heading { min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-heading h2, .lab-heading h2 { margin: 0; font-size: 16px; }
.feed-metrics { display: flex; gap: 10px; }
.feed-metrics span { min-width: 104px; display: flex; flex-direction: column; padding: 8px 12px; text-align: left; border: 1px solid rgba(81, 174, 210, 0.13); border-radius: 9px; background: rgba(4, 21, 34, 0.45); }
.feed-metrics small, .telemetry-grid small, .job-title small { color: #607f94; font-size: 9px; letter-spacing: 0.08em; }
.feed-metrics small { font-size: 11px; }
.feed-metrics b { margin-top: 5px; color: #d5f2fc; font-family: monospace; font-size: 16px; line-height: 1.2; }

.video-stage, .video-empty { position: relative; height: min(760px, calc(100vh - 132px)); min-height: 520px; overflow: hidden; border: 0; border-radius: 8px; background: #030b12; }
.video-stream, .box-overlay, .zone-overlay { position: absolute; inset: 0; width: 100%; height: 100%; }
.video-stream {
  /* Keep the camera's native aspect ratio; never stretch a 4:3/16:9 feed to the stage. */
  object-fit: contain !important;
  object-position: center;
  background: #030b12;
}
.video-stream::-webkit-media-controls,
.video-stream::-webkit-media-controls-enclosure,
.video-stream::-webkit-media-controls-panel,
.video-stream::-webkit-media-controls-overlay-play-button,
.video-stream::-webkit-media-controls-start-playback-button {
  display: none !important;
  opacity: 0 !important;
  pointer-events: none !important;
}
.box-overlay { z-index: 3; pointer-events: none; }
.zone-overlay { z-index: 4; pointer-events: none; }
.zone-overlay.drawing { cursor: crosshair; pointer-events: auto; }
.detection-box { fill: none; vector-effect: non-scaling-stroke; filter: drop-shadow(0 0 3px currentColor); }
.detection-label { fill: #04131b; font-weight: 800; }
.zone-polygon {
  vector-effect: non-scaling-stroke;
  stroke-dasharray: 10 6;
  opacity: 0.78;
  filter: drop-shadow(0 0 3px currentColor);
}
.zone-label {
  font-size: 16px;
  font-weight: 800;
  paint-order: stroke;
  stroke: rgba(3, 12, 18, 0.9);
  stroke-width: 4px;
}
.scan-grid { position: absolute; inset: 0; z-index: 2; pointer-events: none; opacity: 0.12; background: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(66, 210, 245, 0.12) 4px); }
.video-stage > .box-overlay,
.video-stage > .zone-overlay,
.video-stage > .scan-grid,
.video-stage > .corner,
.video-stage > .stage-badge,
.video-stage > .alert-ribbon {
  display: none;
}
.video-stage > .zone-overlay.visible {
  display: block;
}
.zone-dock {
  position: absolute;
  z-index: 8;
  left: 14px;
  bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid rgba(101, 184, 212, 0.22);
  border-radius: 8px;
  background: rgba(4, 16, 25, 0.78);
  box-shadow: 0 10px 28px rgba(0, 8, 18, 0.24);
  backdrop-filter: blur(8px);
}
.zone-dock-select { width: 116px; }
.zone-dock-select :deep(.el-select__wrapper) {
  min-height: 32px;
  border-radius: 7px;
  background: rgba(6, 28, 44, 0.9);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.2) inset;
}
.zone-icon-button {
  width: 32px;
  height: 32px;
  padding: 0;
  color: #b8d6e4;
  border-color: rgba(101, 184, 212, 0.22);
  border-radius: 7px;
  background: rgba(20, 64, 86, 0.42);
}
.zone-icon-button.active {
  color: #061b23;
  border-color: rgba(72, 216, 255, 0.58);
  background: linear-gradient(110deg, var(--cyan), var(--mint));
}
.zone-icon-button.danger:not(.is-disabled):hover {
  color: #ffd5d9;
  border-color: rgba(255, 93, 108, 0.42);
  background: rgba(96, 24, 34, 0.56);
}
.zone-count {
  min-width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  color: #061b23;
  font: 800 12px monospace;
  border-radius: 6px;
  background: var(--cyan);
}
.corner { position: absolute; z-index: 4; width: 25px; height: 25px; border-color: rgba(72, 216, 255, 0.55); }
.corner-tl { left: 12px; top: 12px; border-left: 2px solid; border-top: 2px solid; }
.corner-tr { right: 12px; top: 12px; border-right: 2px solid; border-top: 2px solid; }
.corner-bl { left: 12px; bottom: 12px; border-left: 2px solid; border-bottom: 2px solid; }
.corner-br { right: 12px; bottom: 12px; border-right: 2px solid; border-bottom: 2px solid; }
.stage-loading { position: absolute; inset: 0; z-index: 6; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #8ddcf0; background: rgba(3, 14, 23, 0.76); backdrop-filter: blur(3px); pointer-events: none; }
.stage-badge { position: absolute; z-index: 5; top: 14px; padding: 6px 9px; color: #89a7b9; font-family: monospace; font-size: 10px; border-radius: 5px; background: rgba(2, 13, 21, 0.76); }
.left-badge { left: 16px; }.right-badge { right: 16px; }
.stage-badge i { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #71808a; }
.stage-badge i.active { background: #ff5f68; box-shadow: 0 0 8px #ff5f68; }
.alert-ribbon {
  position: absolute;
  z-index: 7;
  left: 16px;
  right: 16px;
  bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 13px;
  color: #ffe8e9;
  border: 1px solid rgba(255, 93, 108, 0.42);
  border-radius: 8px;
  background: rgba(82, 15, 24, 0.78);
  box-shadow: 0 0 22px rgba(255, 93, 108, 0.18);
}
.alert-ribbon strong { color: #ffadb5; font-size: 15px; }
.alert-ribbon span { min-width: 0; overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.video-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 30px; text-align: center; color: #718da1; background: radial-gradient(circle, rgba(25, 100, 139, 0.13), transparent 50%), #06121c; }
.empty-orbit { width: 110px; height: 110px; position: relative; display: grid; place-items: center; margin-bottom: 18px; color: var(--cyan); border: 1px solid rgba(72, 216, 255, 0.17); border-radius: 50%; }
.empty-orbit span { position: absolute; inset: 10px; border: 1px dashed rgba(81, 230, 190, 0.22); border-radius: 50%; }
.video-empty h3 { margin-bottom: 8px; color: #c6dce8; }
.video-empty p { max-width: 520px; margin-bottom: 16px; }
.video-empty code { max-width: 80%; padding: 6px 10px; color: #ff8f9a; border-radius: 5px; background: rgba(112, 33, 47, 0.2); }

.telemetry-heading { align-items: center; }
.target-count { display: flex; align-items: baseline; gap: 4px; color: var(--cyan); font: 700 26px monospace; }
.target-count small { color: #658399; font: 10px sans-serif; }
.telemetry-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0 12px; }
.telemetry-grid div { display: flex; flex-direction: column; padding: 10px; border: 1px solid rgba(87, 165, 199, 0.1); border-radius: 8px; background: rgba(3, 18, 29, 0.36); }
.telemetry-grid strong { margin-top: 5px; color: #a9c9da; font: 600 12px monospace; }
.telemetry-grid .metric-active { color: var(--mint); }
.zone-panel {
  margin-bottom: 10px;
  padding: 10px;
  border: 1px solid rgba(87, 165, 199, 0.12);
  border-radius: 9px;
  background: rgba(3, 18, 29, 0.36);
}
.zone-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #8fb0c2;
  font-size: 11px;
}
.zone-panel-heading b { color: var(--cyan); font: 800 16px monospace; }
.zone-list { display: flex; flex-direction: column; gap: 7px; margin-top: 8px; }
.zone-item {
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 8px;
  border: 1px solid rgba(85, 166, 201, 0.12);
  border-radius: 7px;
  background: rgba(8, 31, 47, 0.58);
}
.zone-item.alerting {
  border-color: rgba(255, 93, 108, 0.38);
  background: rgba(93, 21, 32, 0.36);
}
.zone-chip { width: 4px; height: 30px; border-radius: 2px; background: var(--zone-color); box-shadow: 0 0 9px var(--zone-color); }
.zone-item strong { display: block; overflow: hidden; color: #d9edf6; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.zone-item small { color: #6f8da0; font-size: 10px; }
.zone-delete { color: #8bb0c3; }
.zone-risk {
  padding: 3px 6px;
  color: #cfe5ee;
  font: 800 10px monospace;
  border-radius: 5px;
  background: rgba(93, 174, 208, 0.13);
}
.zone-panel p { margin: 8px 0 0; color: #607f94; font-size: 11px; line-height: 1.5; }
.zone-config-link {
  width: 100%;
  margin-top: 10px;
  color: #061b23;
  border: none;
  background: linear-gradient(110deg, var(--cyan), var(--mint));
}
.alert-list { display: flex; flex-direction: column; gap: 7px; margin-bottom: 10px; }
.alert-list article {
  padding: 9px 10px;
  border: 1px solid rgba(255, 93, 108, 0.35);
  border-radius: 8px;
  background: rgba(93, 21, 32, 0.32);
}
.alert-list strong { display: block; color: #ffadb5; font-size: 12px; }
.alert-list span { display: block; margin-top: 4px; color: #d8b7bd; font-size: 11px; }
.target-list { max-height: 342px; overflow-y: auto; padding-right: 3px; }
.target-item { display: grid; grid-template-columns: 28px 4px minmax(0, 1fr) 40px; align-items: center; gap: 10px; margin-bottom: 7px; padding: 10px; border: 1px solid rgba(93, 174, 208, 0.1); border-radius: 9px; background: rgba(7, 28, 43, 0.62); }
.target-item.primary, .image-target-item.primary { border-color: rgba(81, 230, 190, 0.34); background: rgba(27, 89, 81, 0.24); }
.target-index { color: #496b82; font: 10px monospace; }
.target-swatch { width: 3px; height: 28px; border-radius: 2px; background: var(--target-color); box-shadow: 0 0 8px var(--target-color); }
.target-copy { min-width: 0; display: flex; flex-direction: column; }
.target-copy strong { overflow: hidden; color: #d9edf6; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.target-copy small { margin-top: 3px; color: #58758a; font-size: 9px; text-transform: uppercase; }
.confidence-ring { width: 37px; height: 37px; display: grid; place-items: center; border-radius: 50%; background: conic-gradient(var(--ring-color) var(--confidence), rgba(75, 112, 132, 0.16) 0); }
.confidence-ring::before { content: ''; grid-area: 1 / 1; width: 29px; height: 29px; border-radius: 50%; background: #0b2335; }
.confidence-ring span { z-index: 1; grid-area: 1 / 1; color: #bcd7e3; font: 9px monospace; }
.telemetry-empty { min-height: 230px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #58788d; text-align: center; }
.telemetry-empty p { max-width: 220px; margin: 12px 0 0; font-size: 12px; line-height: 1.6; }
.inline-error { margin: 10px 0 0; color: #ff8792; font-size: 11px; }

.command-monitor {
  min-height: calc(100vh - 64px);
  display: flex;
  align-items: center;
  padding: 22px 12px 20px;
  color: #e9f7ff;
  background:
    linear-gradient(90deg, rgba(29, 49, 55, 0.72), rgba(9, 25, 35, 0.92)),
    #07131a;
}
.ops-header {
  min-height: 66px;
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(137, 174, 184, 0.18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(19, 42, 48, 0.94), rgba(9, 25, 33, 0.94));
  box-shadow: 0 16px 36px rgba(0, 5, 10, 0.22);
}
.section-kicker {
  display: block;
  color: #8fa8ad;
  font-size: 11px;
  letter-spacing: 0;
}
.monitor-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.monitor-title-row h1 {
  margin: 0;
  color: #f1fbff;
  font-size: 22px;
  font-weight: 800;
}
.ops-mode-select,
.ops-camera-select {
  width: 240px;
}
.ops-mode-select {
  width: 152px;
}
.mode-control-icon {
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 34px;
  color: #62d7b1;
  border: 1px solid rgba(98, 215, 177, 0.28);
  border-radius: 7px;
  background: rgba(98, 215, 177, 0.08);
  box-shadow: inset 0 1px rgba(255, 255, 255, 0.04);
}
.ops-mode-select :deep(.el-select__wrapper),
.ops-camera-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 7px;
  background: rgba(2, 12, 16, 0.72);
  box-shadow: 0 0 0 1px rgba(137, 174, 184, 0.22) inset;
}
.ops-mode-select :deep(.el-select__selected-item),
.ops-mode-select :deep(.el-select__caret) {
  color: #e9f7ff;
  font-weight: 800;
}
.ops-camera-option {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.ops-camera-option span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ops-camera-option b {
  flex: 0 0 auto;
  color: #7895a0;
  font-size: 11px;
}
.ops-camera-option.active span,
.ops-camera-option.active b {
  color: #50e1d0;
  font-weight: 900;
}
.event-state-grid small,
.debug-panel small {
  color: #7f969b;
  font-size: 10px;
}
.ops-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
.ops-simulation-tools {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding-left: 10px;
  border-left: 1px solid rgba(137, 174, 184, 0.14);
}
.view-mode-switch {
  display: inline-flex;
  align-items: center;
  height: 36px;
  padding: 3px;
  border: 1px solid rgba(137, 174, 184, 0.22);
  border-radius: 7px;
  background: rgba(2, 12, 16, 0.68);
}
.view-mode-switch button {
  height: 28px;
  min-width: 58px;
  padding: 0 10px;
  border: 0;
  border-radius: 5px;
  color: #91adb2;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.view-mode-switch button.active {
  color: #041417;
  background: #48d8ff;
}
.ops-ghost-button,
.action-button {
  color: #c7d8dc;
  border-color: rgba(137, 174, 184, 0.2);
  border-radius: 7px;
  background: rgba(16, 45, 49, 0.62);
}
.ops-ghost-button.active {
  color: #061412;
  border-color: rgba(98, 215, 177, 0.62);
  background: #62d7b1;
}
.ops-primary-button {
  color: #041417;
  border: 0;
  border-radius: 7px;
  background: #62d7b1;
}
.ops-layout {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(270px, 320px) minmax(0, 1fr);
  align-items: stretch;
  gap: 14px;
  margin-top: 0;
}
.ops-camera-rail {
  min-width: 0;
  height: min(740px, calc(100vh - 112px));
  min-height: 540px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rail-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, 0.14);
  border-radius: 8px;
  background: rgba(5, 24, 34, 0.72);
}
.rail-card > header {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(137, 174, 184, 0.1);
}
.rail-card h3 {
  margin: 0;
  color: #e0f3fb;
  font-size: 17px;
}
.rail-card header span {
  color: #7897a8;
  font-size: 12px;
}
.camera-list-card {
  min-height: 0;
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
}
.camera-list-header {
  align-items: center;
}
.camera-list-title {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.camera-list-title span {
  color: #73a6bc;
  font-size: 12px;
  font-weight: 800;
}
.rail-view-select {
  width: 98px;
  flex: 0 0 auto;
}
.rail-view-select :deep(.el-select__wrapper) {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 6px;
  background: rgba(2, 12, 16, 0.72);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.2) inset;
}
.rail-view-select :deep(.el-select__selected-item),
.rail-view-select :deep(.el-select__placeholder) {
  color: #d7edf6;
  font-size: 12px;
  font-weight: 800;
}
.rail-view-select :deep(.el-select__caret) {
  color: #8ddcf0;
}
.rail-camera-list {
  min-height: 0;
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 10px 10px 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 142, 158, 0.28) transparent;
}
.rail-camera-list::-webkit-scrollbar {
  width: 4px;
}
.rail-camera-list::-webkit-scrollbar-track {
  background: transparent;
}
.rail-camera-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(100, 142, 158, 0.22);
}
.rail-camera-list:hover::-webkit-scrollbar-thumb {
  background: rgba(100, 180, 210, 0.42);
}
.rail-camera-list button {
  width: 100%;
  min-height: 58px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding: 0 14px;
  border: 0;
  border-left: 4px solid transparent;
  border-radius: 7px;
  color: #bdd5e1;
  background: rgba(3, 18, 25, 0.34);
  cursor: pointer;
  transition: background .18s ease, border-color .18s ease, transform .18s ease;
}
.rail-camera-list button:hover,
.rail-camera-list button.active {
  background: rgba(18, 68, 88, 0.62);
}
.rail-camera-list button.active {
  border-left-color: #48d8ff;
  box-shadow: inset 0 0 0 1px rgba(72, 216, 255, .1);
}
.rail-camera-list button.empty {
  color: #829aa5;
  background: rgba(3, 18, 25, 0.18);
}
.rail-camera-list b {
  color: #7ebbd0;
  font: 900 12px/1 "Consolas", "Monaco", monospace;
}
.rail-camera-list button.empty b {
  color: #6f8791;
}
.rail-camera-list span {
  min-width: 0;
  overflow: hidden;
  color: #bdd5e1;
  font-size: 16px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail-camera-list em {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #7f9bad;
  font-size: 13px;
  font-style: normal;
}
.rail-camera-list em i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #607985;
}
.rail-camera-list em.online {
  color: #62d7b1;
}
.rail-camera-list em.online i {
  background: #62d7b1;
  box-shadow: 0 0 6px rgba(98, 215, 177, 0.64);
}
:global(.camera-map-dialog.el-dialog) {
  border: 1px solid rgba(72, 216, 255, 0.24);
  border-radius: 8px;
  background: #07131a;
  box-shadow: 0 24px 60px rgba(0, 7, 18, 0.46);
}
:global(.camera-map-dialog .el-dialog__header) {
  margin: 0;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(137, 174, 184, 0.14);
}
:global(.camera-map-dialog .el-dialog__title) {
  color: #e9f7ff;
  font-weight: 900;
}
:global(.camera-map-dialog .el-dialog__body) {
  padding: 14px;
}
.expanded-map-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 2168 / 725;
  max-height: 78vh;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: #02080d;
}
.expanded-map-stage img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  filter: saturate(1.08) contrast(1.06) brightness(.76);
}
.expanded-map-region-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.expanded-region-fill {
  fill: rgba(67, 220, 255, .14);
  stroke: transparent;
}
.expanded-region-halo {
  fill: none;
  stroke: rgba(81, 229, 255, .48);
  stroke-width: 13;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#camera-region-glow);
}
.expanded-region-line {
  fill: none;
  stroke: rgba(126, 238, 255, .96);
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
  filter: url(#camera-region-glow);
}
.expanded-region-callout rect {
  fill: rgba(7, 42, 55, .86);
  stroke: rgba(126, 238, 255, .74);
  stroke-width: 1.5;
  filter: drop-shadow(0 0 8px rgba(72, 216, 255, .5));
}
.expanded-region-callout text {
  fill: #e9f7ff;
  font-size: 18px;
  font-weight: 900;
  text-anchor: middle;
}
.expanded-map-point {
  position: absolute;
  z-index: 3;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  margin: -14px 0 0 -14px;
  border: 2px solid rgba(255, 255, 255, 0.62);
  border-radius: 50%;
  color: #fff;
  background: #d93a4b;
  box-shadow: 0 0 0 8px rgba(217, 58, 75, 0.18), 0 0 16px rgba(217, 58, 75, 0.72);
  font: 900 14px/1 "Consolas", "Monaco", monospace;
  cursor: pointer;
}
.expanded-map-point.offline {
  background: #526977;
  box-shadow: 0 0 0 7px rgba(82, 105, 119, 0.16);
}
.expanded-map-point.active {
  width: 34px;
  height: 34px;
  margin: -17px 0 0 -17px;
  color: #041417;
  border-color: rgba(230, 250, 255, 0.92);
  background: #48d8ff;
  box-shadow: 0 0 0 10px rgba(72, 216, 255, 0.24), 0 0 24px rgba(72, 216, 255, 0.88);
}
.camera-point-actions {
  flex: 0 0 auto;
  display: grid;
  gap: 12px;
  padding: 0;
}
.talk-action-wrap {
  width: 100%;
}
.primary-talk-button {
  width: 100%;
  min-height: 58px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border: 0;
  border-radius: 8px;
  color: #061412;
  background: linear-gradient(135deg, #48d8ff, #62d7b1);
  font-size: 15px;
  font-weight: 900;
  cursor: pointer;
  box-shadow: 0 12px 26px rgba(72, 216, 255, 0.2);
  transition: filter .18s ease, transform .18s ease, box-shadow .18s ease;
}
.primary-talk-button:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}
.primary-talk-button:active:not(:disabled) {
  transform: translateY(0);
}
.primary-talk-button:disabled {
  cursor: not-allowed;
  opacity: .46;
  filter: grayscale(.35);
  box-shadow: none;
}
.primary-talk-button .el-icon {
  font-size: 20px;
}
.assist-setting-row {
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 14px;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(4, 20, 28, 0.62);
}
.assist-setting-row strong {
  display: block;
  color: #c6dce6;
  font-size: 14px;
  font-weight: 800;
}
.assist-setting-row :deep(.el-switch__core) {
  min-width: 42px;
  height: 22px;
}
.assist-setting {
  display: grid;
  gap: 8px;
}
.assist-zone-select {
  width: 100%;
}
.assist-zone-select :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 8px;
  background: rgba(4, 20, 28, 0.62);
  box-shadow: 0 0 0 1px rgba(137, 174, 184, 0.16) inset;
}
.assist-zone-select :deep(.el-select__selected-item) {
  color: #c6dce6;
  font-size: 13px;
  font-weight: 700;
}
.assist-zone-select :deep(.el-select__caret) {
  color: #8ddcf0;
}
.map-nav-entry {
  width: 100%;
  min-height: 88px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 18px 18px;
  border: 1px solid rgba(72, 216, 255, 0.26);
  border-radius: 8px;
  color: #d7edf6;
  background:
    linear-gradient(135deg, rgba(20, 77, 96, .78), rgba(8, 35, 45, .82)),
    rgba(4, 20, 28, 0.72);
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(213, 247, 255, .05), 0 10px 24px rgba(0, 7, 18, .18);
  transition: border-color .18s ease, transform .18s ease, background .18s ease;
}
.map-nav-entry:hover {
  color: #e0f3fb;
  border-color: rgba(72, 216, 255, 0.52);
  background:
    linear-gradient(135deg, rgba(28, 99, 122, .82), rgba(9, 44, 56, .86)),
    rgba(4, 20, 28, 0.72);
  transform: translateY(-1px);
}
.map-nav-entry .el-icon {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  border-radius: 8px;
  color: #48d8ff;
  background: rgba(72, 216, 255, .12);
  font-size: 18px;
}
.map-nav-entry strong {
  color: #e9f7ff;
  font-size: 21px;
  line-height: 1.2;
  white-space: nowrap;
}
.multi-camera-layout {
  position: relative;
  display: grid;
  gap: 12px;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 0;
}
.view-mode-select-wrap {
  position: absolute;
  z-index: 12;
  top: 14px;
  right: 14px;
  width: 112px;
}
.multi-camera-layout > .view-mode-select-wrap {
  top: 10px;
  right: 10px;
}
.view-mode-select {
  width: 112px;
}
.view-mode-select :deep(.el-select__wrapper) {
  min-height: 32px;
  border-radius: 7px;
  background: rgba(2, 12, 16, 0.82);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.32) inset;
  backdrop-filter: blur(6px);
}
.view-mode-select :deep(.el-select__selected-item) {
  color: #e9f7ff;
  font-size: 12px;
  font-weight: 800;
}
.view-mode-select :deep(.el-select__caret) {
  color: #8ddcf0;
}
.multi-camera-layout.mode-quad {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
}
.multi-camera-layout.mode-nine {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(3, minmax(0, 1fr));
}
.multi-camera-tile {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(7, 20, 25, 0.86);
  box-shadow: 0 14px 32px rgba(0, 5, 10, 0.2);
  cursor: pointer;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.multi-camera-tile:hover {
  border-color: rgba(72, 216, 255, 0.42);
  box-shadow: 0 16px 34px rgba(0, 5, 10, 0.24), inset 0 0 0 1px rgba(72, 216, 255, 0.08);
}
.multi-camera-tile.active {
  border-color: rgba(72, 216, 255, 0.62);
  box-shadow: 0 18px 38px rgba(0, 5, 10, 0.28), inset 0 0 0 3px rgba(72, 216, 255, 0.46);
}
.multi-camera-tile:focus-visible {
  border-color: rgba(72, 216, 255, 0.72);
  box-shadow: 0 0 0 2px rgba(72, 216, 255, 0.18), 0 16px 34px rgba(0, 5, 10, 0.24);
}
.multi-camera-tile.empty {
  border-style: dashed;
  background: rgba(7, 20, 25, 0.68);
}
.tile-video-box {
  position: relative;
  height: 100%;
  min-height: 0;
  background:
    linear-gradient(90deg, rgba(72, 216, 255, 0.035) 1px, transparent 1px),
    linear-gradient(0deg, rgba(72, 216, 255, 0.035) 1px, transparent 1px),
    #030b12;
  background-size: 28px 28px;
}
.tile-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  display: block;
}
.tile-zone-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.tile-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  color: #88a7b4;
  text-align: center;
  font-size: 13px;
}
.tile-empty span {
  max-width: 86%;
  line-height: 1.5;
}
.tile-empty .el-icon {
  color: #48d8ff;
  font-size: 34px;
}
.multi-camera-tile.empty .tile-empty .el-icon {
  color: #5f7e91;
}
.ops-video-panel,
.risk-panel {
  min-width: 0;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(7, 20, 25, 0.86);
  box-shadow: 0 16px 40px rgba(0, 5, 10, 0.24);
}
.ops-video-panel {
  position: relative;
  height: min(740px, calc(100vh - 112px));
  min-height: 540px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.single-camera-select-wrap {
  position: absolute;
  z-index: 12;
  top: 14px;
  left: 14px;
  width: min(260px, calc(100% - 28px));
}
.single-camera-select {
  width: 100%;
}
.single-camera-select :deep(.el-select__wrapper) {
  min-height: 36px;
  border-radius: 7px;
  background: rgba(2, 12, 16, 0.78);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.32) inset;
  backdrop-filter: blur(6px);
}
.single-camera-select :deep(.el-select__selected-item),
.single-camera-select :deep(.el-select__placeholder) {
  color: #e9f7ff;
  font-weight: 900;
}
.single-camera-select :deep(.el-select__caret) {
  color: #8ddcf0;
}
.ops-video-stage,
.ops-video-empty {
  flex: 1 1 auto;
  height: 100%;
  min-height: 0;
  border-radius: 8px;
}
.ops-video-stage {
  outline: 1px solid rgba(137, 174, 184, 0.12);
}
.ops-video-stage.risk-low { outline-color: rgba(241, 196, 91, 0.55); }
.ops-video-stage.risk-medium { outline-color: rgba(240, 138, 60, 0.62); }
.ops-video-stage.risk-high { outline-color: rgba(255, 77, 94, 0.72); }
.ops-video-stage > .ops-box-overlay,
.ops-video-stage > .ops-zone-overlay {
  display: block;
}
.ops-video-stage > .scan-grid,
.ops-video-stage > .corner,
.ops-video-stage > .stage-badge,
.ops-video-stage > .alert-ribbon,
.ops-video-stage > .video-topline,
.ops-video-stage > .risk-banner {
  display: none;
}
.ops-detection-box,
.ops-zone-polygon {
  fill-opacity: 0.14;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 3px currentColor);
}
.ops-detection-label {
  fill: #071014;
  font-weight: 900;
}
.ops-zone-polygon {
  stroke-dasharray: 9 7;
  opacity: 0.72;
}
.ops-zone-polyline {
  fill: none;
  stroke-width: 3px;
  stroke-dasharray: 9 7;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 3px currentColor);
}
.ops-zone-label {
  font-size: 15px;
  font-weight: 900;
  paint-order: stroke;
  stroke: rgba(3, 9, 12, 0.92);
  stroke-width: 4px;
}
.ops-zone-overlay.editing {
  cursor: default;
  pointer-events: auto;
}
.ops-zone-overlay.drawing {
  cursor: crosshair;
}
.editable-zone.disabled {
  opacity: 0.42;
}
.ops-zone-anchor {
  fill: #f7fbff;
  stroke: #061b23;
  stroke-width: 2.5px;
  vector-effect: non-scaling-stroke;
  cursor: grab;
  filter: drop-shadow(0 0 5px rgba(72, 216, 255, 0.88));
}
.ops-zone-vertex-label {
  fill: #ffffff;
  font-weight: 900;
  paint-order: stroke;
  pointer-events: none;
  stroke: rgba(3, 12, 18, 0.95);
  stroke-width: 3px;
  text-anchor: middle;
  dominant-baseline: central;
  user-select: none;
}
.zone-draw-tip {
  position: absolute;
  z-index: 8;
  left: 14px;
  bottom: 14px;
  padding: 8px 11px;
  color: #d7edf6;
  border: 1px solid rgba(245, 251, 255, 0.22);
  border-radius: 7px;
  background: rgba(4, 16, 25, 0.82);
  pointer-events: none;
}
.video-topline {
  position: absolute;
  z-index: 8;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 9px;
  max-width: calc(100% - 24px);
  padding: 8px 10px;
  border: 1px solid rgba(137, 174, 184, 0.18);
  border-radius: 7px;
  background: rgba(3, 11, 14, 0.76);
  backdrop-filter: blur(7px);
}
.video-topline span,
.video-topline em {
  color: #91aab0;
  font-size: 11px;
  font-style: normal;
}
.video-topline strong {
  overflow: hidden;
  color: #edf8fa;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-banner {
  position: absolute;
  z-index: 8;
  right: 12px;
  bottom: 12px;
  left: 12px;
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(98, 215, 177, 0.26);
  border-radius: 8px;
  background: rgba(5, 19, 21, 0.82);
  backdrop-filter: blur(8px);
}
.risk-banner span {
  display: inline-grid;
  place-items: center;
  min-height: 30px;
  border-radius: 6px;
  color: #061412;
  font-size: 14px;
  font-weight: 900;
  background: #62d7b1;
}
.risk-banner strong {
  overflow: hidden;
  color: #f1fbff;
  font-size: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-banner em {
  color: #a9bdc1;
  font-style: normal;
  font-size: 13px;
}
.risk-banner.risk-low { border-color: rgba(241, 196, 91, 0.58); }
.risk-banner.risk-low span { background: #f1c45b; }
.risk-banner.risk-medium { border-color: rgba(240, 138, 60, 0.62); }
.risk-banner.risk-medium span { background: #f08a3c; }
.risk-banner.risk-high { border-color: rgba(255, 77, 94, 0.72); box-shadow: 0 0 28px rgba(255, 77, 94, 0.18); }
.risk-banner.risk-high span { color: #fff; background: #ff4d5e; }
.debug-panel {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 10px;
  border-top: 1px solid rgba(137, 174, 184, 0.14);
  background: rgba(3, 11, 14, 0.82);
}
.debug-panel div {
  padding: 8px;
  border-radius: 6px;
  background: rgba(17, 38, 42, 0.78);
}
.debug-panel strong {
  display: block;
  margin-top: 4px;
  color: #dbecee;
  font-family: monospace;
}
.debug-targets {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.debug-targets span {
  padding: 4px 7px;
  color: #a8bdc2;
  border-radius: 5px;
  background: rgba(137, 174, 184, 0.1);
  font-size: 11px;
}
.risk-panel {
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  grid-template-rows: auto minmax(180px, auto);
  align-items: stretch;
  gap: 12px;
  padding: 14px;
}
.risk-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 92px;
  padding: 14px;
  border: 1px solid rgba(98, 215, 177, 0.14);
  border-radius: 8px;
  background: rgba(25, 69, 58, 0.18);
}
.risk-panel-heading h2 {
  margin: 4px 0 0;
  color: #f1fbff;
  font-size: 22px;
}
.risk-panel-heading b {
  padding: 5px 9px;
  border-radius: 6px;
  color: #061412;
  background: #62d7b1;
}
.risk-panel-heading b.risk-low { background: #f1c45b; }
.risk-panel-heading b.risk-medium { background: #f08a3c; }
.risk-panel-heading b.risk-high { color: #fff; background: #ff4d5e; }
.risk-diagnostics {
  margin-top: 0;
  padding: 14px;
  border: 1px solid rgba(137, 174, 184, 0.14);
  border-radius: 8px;
  background: rgba(4, 16, 20, 0.74);
}
.diagnostic-heading,
.diagnostic-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.diagnostic-heading span {
  color: #edf8fa;
  font-size: 13px;
  font-weight: 800;
}
.diagnostic-heading small,
.diagnostic-foot span {
  color: #7d969c;
  font-size: 11px;
}
.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(116px, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.diagnostic-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(137, 174, 184, 0.1);
  border-radius: 7px;
  background: rgba(9, 28, 33, 0.68);
}
.diagnostic-item small,
.diagnostic-item span {
  display: block;
  overflow: hidden;
  color: #809ba1;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.diagnostic-item strong {
  display: block;
  margin: 4px 0 3px;
  color: #dcebed;
  font: 800 18px/1 "Consolas", "Monaco", monospace;
}
.diagnostic-item.ok strong { color: #62d7b1; }
.diagnostic-item.warn strong,
.diagnostic-item.medium strong { color: #f08a3c; }
.diagnostic-item.high strong { color: #ff4d5e; }
.diagnostic-item.low strong { color: #f1c45b; }
.diagnostic-item.muted strong { color: #8fa8ad; }
.diagnostic-foot {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(137, 174, 184, 0.1);
}
.diagnostic-foot strong {
  min-width: 0;
  overflow: hidden;
  color: #c9dde2;
  font-size: 11px;
  font-weight: 700;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-event-list {
  grid-column: 1 / -1;
  min-height: 0;
  overflow-x: auto;
  overflow-y: hidden;
  display: flex;
  flex-direction: row;
  gap: 12px;
  padding: 2px 2px 4px;
}
.risk-event-card {
  width: 390px;
  flex: 0 0 390px;
  padding: 13px;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-left-width: 4px;
  border-radius: 8px;
  background: rgba(9, 24, 28, 0.92);
}
.risk-event-card.risk-low { border-left-color: #f1c45b; }
.risk-event-card.risk-medium { border-left-color: #f08a3c; }
.risk-event-card.risk-high { border-left-color: #ff4d5e; background: rgba(39, 16, 18, 0.92); }
.event-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.event-card-header span {
  overflow: hidden;
  color: #8fa8ad;
  font: 11px monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-card-header b { color: #f1fbff; font-size: 14px; }
.event-main {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.event-snapshot {
  height: 62px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 4px;
  color: #8fa8ad;
  border: 1px solid rgba(137, 174, 184, 0.13);
  border-radius: 7px;
  background: linear-gradient(145deg, rgba(34, 58, 57, 0.56), rgba(6, 17, 20, 0.86));
  font-size: 11px;
}
.event-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}
.event-copy strong {
  overflow: hidden;
  color: #edf8fa;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-copy small {
  overflow: hidden;
  color: #8fa8ad;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-state-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  margin-top: 10px;
}
.event-state-grid div {
  padding: 8px;
  border-radius: 6px;
  background: rgba(3, 14, 17, 0.54);
}
.event-state-grid strong {
  display: block;
  margin-top: 3px;
  color: #dbecee;
  font-size: 12px;
}
.event-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  margin-top: 10px;
}
.event-actions .el-button + .el-button { margin-left: 0; }
.event-no-manual {
  grid-column: 1 / -1;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(98, 215, 177, 0.2);
  border-radius: 6px;
  color: #b9e7d6;
  background: rgba(25, 69, 58, 0.38);
  font-size: 12px;
  font-weight: 700;
}
.action-button {
  height: 32px;
  padding: 0 8px;
  justify-content: center;
  font-size: 12px;
}
.action-button.warn {
  color: #061412;
  border-color: transparent;
  background: #f1c45b;
}
.action-button.danger {
  color: #ffd8dc;
  border-color: rgba(255, 77, 94, 0.34);
  background: rgba(95, 23, 29, 0.72);
}
.risk-empty-state {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  min-height: 156px;
  padding: 18px 22px;
  border: 1px solid rgba(137, 174, 184, 0.14);
  border-radius: 8px;
  color: #8fa8ad;
  text-align: left;
  background: rgba(4, 16, 20, 0.62);
}
.safe-mark {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  color: #62d7b1;
  border: 1px solid rgba(98, 215, 177, 0.28);
  border-radius: 50%;
  background: rgba(98, 215, 177, 0.08);
}
.risk-empty-state h3 {
  margin: 0;
  color: #dcebed;
  font-size: 18px;
}
.risk-empty-state p {
  grid-column: 2;
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
}

.media-lab { margin-top: 12px; padding: 18px; }
.lab-heading {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(83, 159, 191, 0.13);
}
.lab-heading h2 { margin: 0; color: #f0f9ff; font-size: 22px; letter-spacing: 0; }
.media-back-button {
  flex: 0 0 auto;
  align-self: center;
  color: #c7d8dc;
  border-color: rgba(137, 174, 184, 0.2);
  border-radius: 7px;
  background: rgba(16, 45, 49, 0.62);
}
.media-control-group { display: flex; align-items: center; gap: 12px; }
.media-control { display: flex; align-items: center; gap: 8px; color: #7d9bb0; font-size: 12px; white-space: nowrap; }
.media-select { width: 142px; }
.media-select :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 8px;
  background: rgba(9, 35, 54, 0.72);
  box-shadow: 0 0 0 1px rgba(72, 187, 225, 0.26) inset;
}
.media-select :deep(.el-select__placeholder),
.media-select :deep(.el-select__selected-item) {
  color: #bfeaff;
  font-weight: 700;
}
.lab-content { display: grid; gap: 14px; padding-top: 16px; }
.image-lab { grid-template-columns: minmax(360px, 0.34fr) minmax(0, 1fr); align-items: stretch; }
.drop-zone :deep(.el-upload), .drop-zone :deep(.el-upload-dragger) { width: 100%; height: 100%; }
.drop-zone :deep(.el-upload-dragger) { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px dashed rgba(77, 202, 233, 0.28); border-radius: 12px; background: rgba(5, 25, 39, 0.46); }
.drop-zone :deep(.el-upload-dragger:hover) { border-color: var(--cyan); background: rgba(14, 62, 82, 0.4); }
.upload-symbol { width: 58px; height: 58px; display: grid; place-items: center; margin-bottom: 14px; color: var(--cyan); border-radius: 16px; background: rgba(58, 183, 217, 0.1); }
.drop-zone h3 { margin-bottom: 7px; color: #c6dce7; font-size: 14px; }
.drop-zone p { max-width: 280px; margin: 0; color: #668397; font-size: 10px; }
.media-result { min-height: 360px; overflow: hidden; position: relative; border: 1px solid rgba(80, 165, 200, 0.12); border-radius: 12px; background: #05111b; }
.image-result.has-result { display: grid; grid-template-columns: minmax(0, 1fr) 320px; min-height: 520px; }
.image-preview-wrap { min-width: 0; min-height: 520px; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #020a11; }
.image-preview-wrap img { display: block; width: 100%; height: 520px; object-fit: contain; }
.result-caption { position: absolute; right: 10px; bottom: 10px; left: 10px; display: flex; justify-content: space-between; padding: 8px 12px; color: #94b4c6; font-size: 11px; border-radius: 7px; background: rgba(3, 16, 25, 0.82); }
.result-caption b { color: var(--mint); }
.image-target-panel { min-width: 0; display: flex; flex-direction: column; padding: 16px; border-left: 1px solid rgba(75, 175, 211, 0.16); background: linear-gradient(180deg, rgba(10, 39, 57, 0.82), rgba(5, 24, 38, 0.92)); }
.image-target-heading { display: flex; align-items: center; justify-content: space-between; padding-bottom: 13px; border-bottom: 1px solid rgba(81, 167, 201, 0.14); }
.image-target-heading > div { display: flex; flex-direction: column; gap: 4px; }
.image-target-heading small { color: #6e93a8; font-size: 10px; }
.image-target-heading strong { color: #e1f3fa; font-size: 15px; }
.image-target-heading > span { min-width: 38px; height: 38px; display: grid; place-items: center; color: #071b24; font: 800 17px monospace; border-radius: 11px; background: var(--cyan); box-shadow: 0 0 18px rgba(72, 216, 255, 0.2); }
.image-target-list { min-height: 0; overflow-y: auto; margin-top: 12px; padding-right: 3px; }
.image-target-item { position: relative; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: 10px; margin-bottom: 8px; padding: 12px 10px; overflow: hidden; border: 1px solid rgba(87, 174, 206, 0.14); border-radius: 9px; background: rgba(7, 29, 44, 0.78); }
.image-target-item::before { position: absolute; inset: 0 auto 0 0; width: 3px; content: ''; background: var(--target-color); box-shadow: 0 0 10px var(--target-color); }
.image-target-index { color: #587b90; font: 11px monospace; }
.image-target-copy { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.image-target-copy strong { overflow: hidden; color: #f0faff; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
.image-target-copy small { overflow: hidden; color: #6d90a4; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.image-confidence { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
.image-confidence strong { color: var(--target-color); font: 800 16px monospace; }
.image-confidence small { color: #58768a; font-size: 9px; }
.image-target-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #55798f; text-align: center; }
.image-target-empty .el-icon { font-size: 30px; }
.image-target-empty strong { color: #a7c6d6; font-size: 14px; }
.image-target-empty span { max-width: 190px; font-size: 10px; line-height: 1.6; }
.result-placeholder { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #4f7186; }
.result-placeholder .el-icon { font-size: 42px; }

.dialog-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.source-type-group { width: 100%; }
.source-type-group :deep(.el-radio-button) { flex: 1; }
.source-type-group :deep(.el-radio-button__inner) { width: 100%; }
.source-help { margin: -6px 0 0; color: #71899a; font-size: 11px; line-height: 1.6; }

.drawer-zone-summary,
.drawer-zone-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.drawer-zone-summary {
  padding: 12px;
  border: 1px solid rgba(83, 159, 191, 0.15);
  border-radius: 8px;
  background: rgba(6, 25, 37, 0.82);
}
.drawer-zone-summary > div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.drawer-zone-summary span {
  overflow: hidden;
  color: #8fb0c2;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drawer-zone-summary strong {
  color: #f1fbff;
  font-size: 18px;
}
.drawer-save-button {
  color: #061b23;
  border: none;
  font-weight: 900;
  background: linear-gradient(110deg, var(--cyan), var(--mint));
}
.drawer-zone-actions span {
  min-width: 0;
  color: #8fb0c2;
  font-size: 12px;
  line-height: 1.5;
  text-align: right;
}
.drawer-tool-button {
  color: #b9d2df;
  border-color: rgba(101, 184, 212, 0.22);
  background: rgba(20, 64, 86, 0.42);
}
.drawer-tool-button.active {
  color: #061b23;
  border-color: transparent;
  background: linear-gradient(110deg, var(--cyan), var(--mint));
  font-weight: 900;
}
.drawer-zone-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.drawer-zone-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px 12px;
  padding: 11px;
  border: 1px solid rgba(85, 166, 201, 0.14);
  border-radius: 8px;
  background: rgba(7, 29, 43, 0.76);
  cursor: pointer;
}
.drawer-zone-item:hover,
.drawer-zone-item.selected {
  border-color: rgba(72, 216, 255, 0.5);
  background: rgba(9, 43, 65, 0.82);
}
.drawer-zone-item.disabled {
  opacity: 0.58;
}
.drawer-zone-main {
  min-width: 0;
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr);
  align-items: center;
  gap: 9px;
}
.drawer-zone-main > i {
  width: 4px;
  height: 36px;
  border-radius: 2px;
  box-shadow: 0 0 9px currentColor;
}
.drawer-zone-main strong,
.drawer-zone-main span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drawer-zone-main strong {
  color: #e9f7ff;
  font-size: 14px;
}
.drawer-zone-main span {
  margin-top: 4px;
  color: #7f9bb0;
  font-size: 11px;
}
.drawer-enable-toggle {
  min-width: 82px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid rgba(127, 155, 176, 0.28);
  border-radius: 999px;
  color: #9bbbd0;
  background: rgba(15, 39, 55, 0.72);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.drawer-enable-toggle i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7f9bb0;
}
.drawer-enable-toggle.active {
  color: #061b23;
  border-color: transparent;
  background: linear-gradient(110deg, var(--cyan), var(--mint));
}
.drawer-enable-toggle.active i {
  background: #061b23;
}
.drawer-zone-row-control,
.drawer-zone-row-actions {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 9px;
}
.drawer-zone-row-control {
  padding-top: 8px;
  border-top: 1px solid rgba(137, 174, 184, 0.12);
}
.drawer-zone-row-control > span {
  color: #8fb0c2;
  font-size: 12px;
  font-weight: 800;
}
.drawer-zone-row-control em {
  color: #8ddcf0;
  font-style: normal;
  font-size: 12px;
  font-weight: 900;
}
.drawer-zone-row-control :deep(.el-input-number) { width: 104px; }
.drawer-zone-row-control :deep(.el-input__wrapper),
.drawer-point-row :deep(.el-input__wrapper) {
  min-height: 30px;
  border-radius: 7px;
  background: rgba(3, 18, 29, 0.66);
  box-shadow: 0 0 0 1px rgba(72, 216, 255, 0.18) inset;
}
.drawer-zone-row-control :deep(.el-input__inner),
.drawer-point-row :deep(.el-input__inner) {
  color: #dff5ff;
  font-weight: 800;
}
.drawer-zone-row-actions {
  justify-content: flex-end;
}
.drawer-zone-row-actions button,
.drawer-point-row button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(81, 230, 190, 0.36);
  border-radius: 6px;
  color: #51e6be;
  background: rgba(11, 73, 78, 0.44);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.drawer-zone-row-actions button.danger,
.drawer-point-row button {
  color: #ff9ca7;
  border-color: rgba(255, 93, 108, 0.32);
  background: rgba(72, 32, 48, 0.54);
}
.drawer-zone-empty {
  min-height: 84px;
  display: grid;
  place-items: center;
  color: #6f8da0;
  border: 1px dashed rgba(54, 221, 212, 0.28);
  border-radius: 8px;
  background: rgba(5, 22, 34, 0.42);
}
.drawer-zone-empty.large {
  min-height: 160px;
}
.drawer-point-panel {
  padding: 12px;
  border: 1px solid rgba(54, 221, 212, 0.34);
  border-radius: 8px;
  background: rgba(8, 30, 48, 0.72);
}
.point-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.point-panel-heading strong {
  color: #e9f7ff;
  font-size: 15px;
}
.point-panel-heading b {
  min-width: 62px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.42);
  border-radius: 999px;
  background: rgba(4, 45, 55, 0.72);
  font-size: 12px;
}
.drawer-zone-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 142px;
  gap: 10px;
}
.drawer-zone-form :deep(.el-form-item) {
  margin-bottom: 10px;
}
.drawer-zone-form :deep(.el-form-item__label) {
  color: #8fb0c2;
  font-size: 12px;
}
.drawer-zone-select { width: 100%; }
.drawer-point-table {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.drawer-point-head,
.drawer-point-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) minmax(0, 1fr) 58px;
  align-items: center;
  gap: 7px;
}
.drawer-point-head {
  color: #9bbbd0;
  font-size: 12px;
  font-weight: 900;
}
.drawer-point-row {
  padding: 7px;
  border: 1px solid rgba(54, 221, 212, 0.24);
  border-radius: 8px;
  background: rgba(7, 40, 55, 0.6);
}
.drawer-point-row strong {
  height: 30px;
  display: inline-grid;
  place-items: center;
  color: #51e6be;
  border: 1px solid rgba(81, 230, 190, 0.32);
  border-radius: 6px;
  background: rgba(17, 82, 91, 0.64);
  font: 800 12px monospace;
}
.drawer-point-row :deep(.el-input-number) {
  width: 100%;
}
.drawer-point-empty {
  min-height: 50px;
  display: grid;
  place-items: center;
  color: #6f8da0;
  border: 1px dashed rgba(54, 221, 212, 0.28);
  border-radius: 8px;
}
.drawer-add-point {
  width: 100%;
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 10px;
  border: 1px dashed rgba(81, 230, 190, 0.68);
  border-radius: 8px;
  color: #51e6be;
  background: rgba(5, 29, 43, 0.62);
  font: inherit;
  font-weight: 900;
  cursor: pointer;
}
.drawer-add-point:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

:global(.patrol-report-drawer.el-drawer) {
  color: #dbeaf1;
  border-left: 1px solid rgba(72, 216, 255, 0.32);
  background:
    radial-gradient(circle at 100% 0%, rgba(72, 216, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(11, 35, 49, 0.98), rgba(3, 14, 23, 0.98));
  box-shadow: -18px 0 46px rgba(0, 5, 10, 0.34);
}

:global(.patrol-report-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 22px 24px 16px;
  color: #f1fbff;
  border-bottom: 1px solid rgba(137, 174, 184, 0.16);
}

:global(.patrol-report-drawer .el-drawer__title) {
  color: #f1fbff;
  font-size: 20px;
  font-weight: 800;
}

:global(.patrol-report-drawer .el-drawer__close-btn) {
  color: #9fc4d2;
}

:global(.patrol-report-drawer .el-drawer__body) {
  padding: 20px 24px;
}

:global(.patrol-report-drawer .el-drawer__footer) {
  padding: 16px 24px 22px;
  border-top: 1px solid rgba(137, 174, 184, 0.16);
}

:global(.patrol-report-drawer .el-empty__description p) {
  color: #8fa8ad;
}

:global(.patrol-report-drawer .el-button:not(.el-button--primary)) {
  color: #dbeaf1;
  border-color: rgba(137, 174, 184, 0.24);
  background: rgba(16, 45, 49, 0.62);
}

.patrol-report {
  display: grid;
  gap: 14px;
  color: #dbeaf1;
}
.patrol-report header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #061927;
}
.patrol-report header span {
  color: #84a8ba;
  font: 700 13px monospace;
}
.patrol-report header strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-stats,
.report-risk-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.report-stats div,
.report-risk-grid div {
  padding: 12px;
  border: 1px solid rgba(83, 159, 191, 0.14);
  border-radius: 8px;
  background: #081f30;
}
.report-stats small,
.report-risk-grid span {
  display: block;
  color: #7898aa;
  font-size: 11px;
}
.report-stats b,
.report-risk-grid b {
  display: block;
  margin-top: 6px;
  color: #eefaff;
  font: 800 22px monospace;
}
.report-risk-grid .risk-low b { color: #f1c45b; }
.report-risk-grid .risk-medium b { color: #f08a3c; }
.report-risk-grid .risk-high b { color: #ff4d5e; }
.report-section {
  padding: 12px;
  border: 1px solid rgba(83, 159, 191, 0.14);
  border-radius: 8px;
  background: #061927;
}
.report-section h3 {
  margin: 0 0 10px;
  color: #eefaff;
  font-size: 14px;
}
.report-section p {
  margin: 0;
  color: #7898aa;
  font-size: 12px;
}
.action-count-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.action-count-list span {
  padding: 6px 9px;
  color: #b9d6e4;
  border-radius: 6px;
  background: rgba(39, 91, 114, 0.38);
}
.action-count-list b {
  margin-left: 5px;
  color: var(--cyan);
}
.report-event {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid rgba(83, 159, 191, 0.12);
}
.report-event:first-of-type { border-top: none; }
.report-event > b {
  align-self: start;
  padding: 5px 7px;
  text-align: center;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
}
.report-event > b.risk-low { color: #f1c45b; }
.report-event > b.risk-medium { color: #f08a3c; }
.report-event > b.risk-high { color: #ff4d5e; }
.report-event div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.report-event strong,
.report-event small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-event small {
  color: #7898aa;
  font-size: 11px;
}
.report-pending-state {
  min-height: 280px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  padding: 28px;
  color: #8fa8ad;
  text-align: center;
  border: 1px dashed rgba(137, 174, 184, 0.22);
  border-radius: 8px;
  background: rgba(4, 16, 20, 0.56);
}
.report-pending-state .el-icon {
  color: #62d7b1;
  font-size: 38px;
}
.report-pending-state strong {
  color: #edf8fa;
  font-size: 18px;
}
.report-pending-state span {
  max-width: 360px;
  line-height: 1.7;
  font-size: 13px;
}

.zone-config-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(137, 174, 184, 0.16);
  border-radius: 8px;
  background: rgba(7, 20, 25, 0.86);
  box-shadow: 0 16px 40px rgba(0, 5, 10, 0.2);
}
.zone-config-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 10px;
}
.zone-config-panel-header h2 {
  margin: 4px 0 0;
  color: #f1fbff;
  font-size: 20px;
}
.zone-config-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.zone-total-pill {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  color: #061b23;
  border-radius: 7px;
  background: linear-gradient(110deg, var(--cyan), var(--mint));
  font-size: 13px;
  font-weight: 900;
}
.zone-origin-note {
  margin-bottom: 12px;
  padding: 9px 11px;
  color: #a9bdc1;
  border: 1px solid rgba(98, 215, 177, 0.14);
  border-radius: 7px;
  background: rgba(25, 69, 58, 0.16);
  font-size: 12px;
}
.inline-zone-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.38fr);
  gap: 12px;
  align-items: start;
}
.inline-zone-list {
  min-width: 0;
  overflow-x: auto;
}
.inline-zone-table-head,
.inline-zone-row {
  min-width: 920px;
  display: grid;
  grid-template-columns: minmax(180px, 1.35fr) 122px 118px 110px 160px 118px;
  align-items: center;
  gap: 12px;
}
.inline-zone-table-head {
  min-height: 36px;
  padding: 0 12px;
  color: #8fb0c2;
  border-bottom: 1px solid rgba(137, 174, 184, 0.14);
  font-size: 12px;
  font-weight: 900;
}
.inline-zone-row {
  min-height: 58px;
  margin-top: 8px;
  padding: 8px 12px;
  color: #cfe5ee;
  border: 1px solid rgba(85, 166, 201, 0.14);
  border-radius: 8px;
  background: rgba(8, 31, 47, 0.58);
  cursor: pointer;
}
.inline-zone-row:hover,
.inline-zone-row.selected {
  border-color: rgba(72, 216, 255, 0.48);
  background: rgba(9, 43, 65, 0.72);
}
.inline-zone-row.disabled {
  opacity: 0.58;
}
.inline-zone-row strong {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.inline-zone-row strong i {
  width: 4px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: 2px;
}
.drawer-zone-row-control.compact {
  grid-column: auto;
  justify-content: flex-start;
  padding-top: 0;
  border-top: none;
}
.inline-zone-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.inline-zone-actions button {
  min-width: 50px;
  height: 30px;
  border: 1px solid rgba(81, 230, 190, 0.36);
  border-radius: 6px;
  color: #51e6be;
  background: rgba(11, 73, 78, 0.44);
  font: inherit;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.inline-zone-actions button.danger {
  color: #ff9ca7;
  border-color: rgba(255, 93, 108, 0.32);
  background: rgba(72, 32, 48, 0.54);
}
.inline-point-panel {
  margin: 0;
}

 .risk-overview-panel {
  display: grid;
  grid-template-columns: minmax(220px, 0.22fr) minmax(0, 1fr) minmax(260px, 0.26fr);
  gap: 0;
  padding: 0;
  overflow: hidden;
  border-color: rgba(137, 174, 184, 0.14);
  background: rgba(4, 15, 18, 0.72);
}
.risk-status-bar {
  min-width: 0;
  min-height: 104px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-right: 1px solid rgba(137, 174, 184, 0.12);
  background: rgba(12, 37, 32, 0.48);
}
.risk-status-main {
  min-width: 0;
}
.risk-status-main span {
  display: block;
  color: #8fa8ad;
  font-size: 12px;
  font-weight: 700;
}
.risk-status-main strong {
  display: block;
  margin-top: 8px;
  color: #f1fbff;
  font-size: 26px;
  line-height: 1.08;
  white-space: nowrap;
}
.risk-status-bar b {
  min-width: 48px;
  height: 36px;
  display: inline-grid;
  place-items: center;
  padding: 0 12px;
  border-radius: 7px;
  color: #061412;
  background: #62d7b1;
  font-size: 15px;
}
.risk-status-bar.risk-low b { background: #f1c45b; }
.risk-status-bar.risk-medium b { background: #f08a3c; }
.risk-status-bar.risk-high b { color: #fff; background: #ff4d5e; }
.risk-summary-strip {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-right: 1px solid rgba(137, 174, 184, 0.12);
}
.risk-summary-item {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  min-height: 104px;
  padding: 16px 18px;
  border-left: 1px solid rgba(137, 174, 184, 0.1);
}
.risk-summary-item:first-child {
  border-left: none;
}
.risk-summary-item span,
.risk-summary-item small {
  display: block;
  overflow: hidden;
  color: #809ba1;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-summary-item strong {
  color: #dcebed;
  font: 900 24px/1 "Consolas", "Monaco", monospace;
}
.risk-summary-item.ok strong { color: #62d7b1; }
.risk-summary-item.warn strong,
.risk-summary-item.medium strong { color: #f08a3c; }
.risk-summary-item.high strong { color: #ff4d5e; }
.risk-summary-item.low strong { color: #f1c45b; }
.risk-summary-item.muted strong { color: #9eb3ba; }
.risk-latest-target {
  min-width: 0;
  min-height: 104px;
  display: grid;
  align-content: center;
  gap: 7px;
  padding: 16px 18px;
}
.risk-latest-target span,
.risk-latest-target em {
  color: #809ba1;
  font-size: 12px;
  font-style: normal;
}
.risk-latest-target strong {
  min-width: 0;
  overflow: hidden;
  color: #dcebed;
  font-size: 13px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-quiet-line {
  grid-column: 1 / -1;
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  color: #8fa8ad;
  border-top: 1px solid rgba(137, 174, 184, 0.12);
  background: rgba(4, 16, 20, 0.42);
}
.risk-quiet-line .el-icon {
  color: #62d7b1;
  font-size: 24px;
}
.risk-quiet-line span {
  color: #dcebed;
  font-size: 15px;
  font-weight: 900;
}
.risk-quiet-line strong {
  min-width: 0;
  overflow: hidden;
  color: #8fa8ad;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.compact-events {
  grid-column: 1 / -1;
  border-top: 1px solid rgba(137, 174, 184, 0.12);
}

@media (max-width: 1200px) {
  .ops-header { grid-template-columns: 1fr; align-items: stretch; }
  .ops-header-actions { justify-content: space-between; }
  .ops-layout { grid-template-columns: 1fr; }
  .ops-camera-rail {
    height: auto;
    min-height: 0;
  }
  .risk-panel {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    min-height: 0;
  }
  .risk-panel-heading {
    padding-right: 0;
    padding-bottom: 14px;
  }
  .diagnostic-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .risk-overview-panel {
    grid-template-columns: 1fr;
  }
  .risk-status-bar,
  .risk-summary-strip {
    border-right: none;
    border-bottom: 1px solid rgba(137, 174, 184, 0.12);
  }
  .risk-latest-target {
    min-height: 76px;
  }
  .multi-camera-layout.mode-nine {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-template-rows: repeat(5, minmax(220px, 1fr));
    height: auto;
  }
  .live-workspace { grid-template-columns: minmax(0, 1fr) 300px; }
  .image-result.has-result { grid-template-columns: minmax(0, 1fr) 250px; }
  .source-toolbar,
  .source-toolbar.analysis-toolbar { grid-template-columns: 1fr; align-items: flex-start; }
  .toolbar-actions { flex-wrap: wrap; justify-content: flex-end; }
}
@media (max-width: 900px) {
  .command-monitor { padding: 8px; }
  .monitor-title-row,
  .ops-header-actions { align-items: stretch; flex-direction: column; }
  .ops-simulation-tools {
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
    padding-left: 0;
    border-left: none;
  }
  .ops-mode-select,
  .ops-camera-select {
    width: 100%;
  }
  .view-mode-switch { width: 100%; }
  .view-mode-switch button { flex: 1; }
  .view-mode-select-wrap {
    top: 10px;
    right: 10px;
  }
  .risk-panel {
    gap: 8px;
    padding: 10px;
  }
  .risk-panel-heading {
    min-height: 0;
  }
  .diagnostic-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .risk-summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .risk-summary-item {
    min-height: 86px;
  }
  .risk-quiet-line {
    align-items: flex-start;
    flex-direction: column;
    justify-content: center;
    min-height: 86px;
    padding: 14px 16px;
  }
  .risk-empty-state {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }
  .risk-empty-state p {
    grid-column: 1;
  }
  .multi-camera-layout.mode-quad,
  .multi-camera-layout.mode-nine {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    height: auto;
    min-height: 0;
  }
  .multi-camera-tile {
    min-height: 260px;
  }
  .risk-banner { grid-template-columns: 1fr; align-items: flex-start; }
  .event-actions { grid-template-columns: 1fr; }
  .debug-panel { grid-template-columns: 1fr 1fr; }
  .vision-page { padding: 10px; }
  .command-header, .source-toolbar, .lab-heading { align-items: stretch; flex-direction: column; }
  .header-status { align-self: flex-end; }
  .header-status, .source-control, .task-control, .toolbar-actions { flex-wrap: wrap; }
  .task-control { padding: 0; border: none; }
  .media-control-group { align-items: stretch; flex-direction: column; }
  .media-control { align-items: flex-start; flex-direction: column; gap: 5px; }
  .live-workspace, .image-lab { grid-template-columns: 1fr; }
  .image-result.has-result { grid-template-columns: 1fr; }
  .image-target-panel { min-height: 250px; border-top: 1px solid rgba(75, 175, 211, 0.16); border-left: none; }
  .telemetry-card { min-height: 420px; }
  .media-select, .camera-select { width: 100%; }
}
</style>
