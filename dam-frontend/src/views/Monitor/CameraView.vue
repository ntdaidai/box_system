<!-- dai -->
<template>
  <div class="vision-page">
    <header v-if="!isMediaAnalysisRoute" class="command-header surface-card">
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

    <section class="source-toolbar surface-card" :class="{ 'analysis-toolbar': isMediaAnalysisRoute }">
      <div class="source-control">
        <span class="control-label">当前视频源</span>
        <el-select
          v-model="currentCameraId"
          class="camera-select"
          placeholder="选择已配置的视频源"
          popper-class="vision-select-popper"
          @change="activateCamera"
        >
          <el-option
            v-for="camera in cameras"
            :key="camera.camera_id"
            :label="camera.name"
            :value="camera.camera_id"
          >
            <div class="camera-option">
              <span>{{ camera.name }}</span>
              <span class="option-meta">
                {{ sourceTypeLabel(camera.source_type) }} · {{ camera.connected ? '在线' : '离线' }}
              </span>
            </div>
          </el-option>
        </el-select>
      </div>

      <div class="task-control">
        <span class="control-label">分析方式</span>
        <el-select
          v-model="analysisTask"
          class="task-select"
          :disabled="detectionToggling"
          popper-class="vision-select-popper"
          @change="handleAnalysisTaskChange"
        >
          <el-option label="目标检测" value="detect" />
          <el-option label="图片分类" value="classify" />
        </el-select>
      </div>

      <div v-if="!isMediaAnalysisRoute" class="toolbar-actions">
        <el-button class="ghost-button" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>接入视频源
        </el-button>
        <el-button
          class="detect-button"
          :class="{ active: detectionEnabled }"
          :loading="detectionToggling"
          :disabled="!canToggleDetection"
          @click="toggleLiveDetection"
        >
          <el-icon><Aim /></el-icon>{{ detectionEnabled ? '停止 AI 分析' : '启动 AI 分析' }}
        </el-button>
        <el-select
          v-model="activeZoneType"
          class="zone-type-select"
          :disabled="zoneDrawing"
          popper-class="vision-select-popper"
        >
          <el-option label="人员入侵区" value="person_intrusion" />
          <el-option label="禁捕监管区" value="illegal_fishing" />
        </el-select>
        <el-button
          class="ghost-button"
          :class="{ active: zoneDrawing }"
          :disabled="analysisTask !== 'detect' || imageWidth <= 0 || imageHeight <= 0"
          @click="zoneDrawing = !zoneDrawing"
        >
          <el-icon><Crop /></el-icon>{{ zoneDrawing ? '结束标框' : '绘制区域' }}
        </el-button>
        <el-button
          class="ghost-button"
          :disabled="!currentCamera?.connected || !selectedModelReady"
          @click="takeSnapshot"
        >
          <el-icon><Camera /></el-icon>截图分析
        </el-button>
      </div>
    </section>

    <section v-if="!isMediaAnalysisRoute" class="live-workspace">
      <article class="live-card surface-card">
        <div class="card-heading">
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
            v-if="analysisTask === 'detect' && imageWidth > 0 && imageHeight > 0"
            class="zone-overlay"
            :class="{ drawing: zoneDrawing }"
            :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
            preserveAspectRatio="xMidYMid meet"
            @mousedown.prevent="startZoneDraw"
            @mousemove.prevent="updateZoneDraw"
            @mouseup.prevent="finishZoneDraw"
            @mouseleave="finishZoneDraw"
          >
            <g v-for="zone in zonesForOverlay" :key="zone.id">
              <rect
                class="zone-rect"
                :x="zonePixelRect(zone).x"
                :y="zonePixelRect(zone).y"
                :width="zonePixelRect(zone).width"
                :height="zonePixelRect(zone).height"
                :stroke="zoneStroke(zone)"
                :fill="zoneFill(zone)"
                :stroke-width="Math.max(2, imageWidth / 520)"
                rx="4"
              />
              <text
                class="zone-label"
                :x="zonePixelRect(zone).x + 8"
                :y="Math.max(18, zonePixelRect(zone).y + 18)"
                :fill="zoneStroke(zone)"
              >
                {{ zone.name || zoneTypeLabel(zone.type) }}
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
            {{ sourceTypeLabel(currentCamera.source_type) }} / {{ currentCamera.camera_id }}
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
            <h3>等待接入视频源</h3>
            <p>支持海康 RTSP 与 Jetson USB / UVC 摄像头。</p>
            <el-button class="detect-button" @click="showAddDialog = true">
              <el-icon><Connection /></el-icon>现在接入
            </el-button>
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
            <span>虚拟检测区域</span>
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
              <el-button text class="zone-delete" @click="removeZone(zone.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </article>
          </div>
          <p v-else>启动目标检测后，在画面上绘制人员入侵区或禁捕监管区。</p>
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
        <div>
          <h2>{{ mediaHeadingTitle }}</h2>
          <p>{{ mediaHeadingDescription }}</p>
        </div>
        <div class="media-mode-switch" role="tablist" aria-label="图片视频分析切换">
          <button
            type="button"
            role="tab"
            :aria-selected="mediaTab === 'image'"
            :class="{ active: mediaTab === 'image' }"
            @click="switchMediaTab('image')"
          >
            <el-icon><Picture /></el-icon>图片分析
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="mediaTab === 'video'"
            :class="{ active: mediaTab === 'video' }"
            @click="switchMediaTab('video')"
          >
            <el-icon><VideoPlay /></el-icon>视频分析
          </button>
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

      <div v-show="mediaTab === 'video'" class="lab-content video-lab">
        <div class="video-upload-column">
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="false"
            accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,video/x-matroska,.m4v"
            class="drop-zone video-drop"
            :on-change="handleVideoUpload"
          >
            <div class="upload-symbol video-symbol"><el-icon :size="32"><Files /></el-icon></div>
            <h3>拖入视频文件进行{{ analysisTaskLabel }}</h3>
            <p>支持 MP4、MOV、AVI、MKV、WEBM、M4V，最大 200MB / 10分钟</p>
          </el-upload>

          <div v-if="videoJob" class="job-panel">
            <div class="job-title">
              <div><small>当前任务</small><strong>{{ videoJob.filename }}</strong></div>
              <span :class="['job-state', videoJob.state]">{{ videoStateText }}</span>
            </div>
            <el-progress
              :percentage="videoProgress"
              :stroke-width="8"
              :show-text="false"
              color="#42d9c3"
            />
            <div class="job-meta">
              <span>{{ videoProgress }}%</span>
              <span>已分析 {{ videoJob.processed_samples || 0 }} 个采样帧</span>
            </div>
            <p v-if="videoJob.error" class="inline-error">{{ videoJob.error }}</p>
          </div>

          <div v-if="videoResult" class="video-summary">
            <div><small>视频时长</small><strong>{{ videoResult.duration_s.toFixed(1) }}s</strong></div>
            <div><small>采样帧数</small><strong>{{ videoResult.processed_samples }}</strong></div>
            <div><small>{{ videoResult.task_type === 'detect' ? '目标出现次数' : '分类采样数' }}</small><strong>{{ videoResult.total_occurrences }}</strong></div>
          </div>
        </div>

        <div class="video-analysis-stage">
          <div v-if="videoPreviewUrl" class="uploaded-video-wrap">
            <video
              ref="uploadedVideoRef"
              :src="videoPreviewUrl"
              controls
              playsinline
              @timeupdate="syncVideoDetection"
              @seeked="syncVideoDetection"
            ></video>
            <svg
              v-if="videoSample?.task_type === 'detect' && videoWidth > 0 && videoHeight > 0"
              class="box-overlay uploaded-overlay"
              :viewBox="`0 0 ${videoWidth} ${videoHeight}`"
              preserveAspectRatio="xMidYMid meet"
            >
              <g v-for="(detection, index) in videoDetections" :key="`video-${videoSample.time}-${index}`">
                <rect
                  class="detection-box"
                  :x="detection.bbox.x1"
                  :y="detection.bbox.y1"
                  :width="detection.bbox.x2 - detection.bbox.x1"
                  :height="detection.bbox.y2 - detection.bbox.y1"
                  :stroke="getClassColor(detection.class_id)"
                  :stroke-width="videoBoxStrokeWidth"
                />
                <rect
                  :x="detection.bbox.x1"
                  :y="labelY(detection, videoLabelHeight)"
                  :width="labelWidth(detection, videoLabelFontSize, videoLabelPadding)"
                  :height="videoLabelHeight"
                  :fill="getClassColor(detection.class_id)"
                  rx="3"
                />
                <text
                  :x="detection.bbox.x1 + videoLabelPadding"
                  :y="labelY(detection, videoLabelHeight) + videoLabelHeight * 0.72"
                  :font-size="videoLabelFontSize"
                  class="detection-label"
                >{{ detectionLabel(detection) }}</text>
              </g>
            </svg>
            <div v-if="videoJob && !videoResult" class="video-processing-overlay">
              <el-icon class="is-loading" :size="34"><Loading /></el-icon>
              <span>{{ videoStateText }} {{ videoProgress }}%</span>
            </div>
          </div>
          <div v-else class="result-placeholder video-placeholder-result">
            <el-icon><VideoPlay /></el-icon><span>上传后可立即预览，分析完成后随播放同步显示结果</span>
          </div>

          <div v-if="videoResult" class="playback-targets">
            <div class="playback-heading">
              <span>当前播放位置{{ videoResult.task_type === 'detect' ? '检测' : '分类' }}</span>
              <b v-if="videoResult.task_type === 'detect'">{{ videoDetections.length }} 个目标</b>
              <b v-else>{{ detectionName(videoPrediction) }} {{ confidencePercent(videoPrediction) }}%</b>
            </div>
            <div v-if="videoDetections.length" class="playback-list">
              <span v-for="(item, index) in videoDetections" :key="index" :style="{ '--item-color': getClassColor(item.class_id) }">
                {{ detectionName(item) }} {{ confidencePercent(item) }}%
              </span>
            </div>
            <div v-else-if="videoClassifications.length" class="playback-list classification-playback">
              <span v-for="item in videoClassifications" :key="item.class_id" :style="{ '--item-color': getClassColor(item.class_id) }">
                {{ detectionName(item) }} {{ confidencePercent(item) }}%
              </span>
            </div>
            <p v-else>当前采样画面暂无分析结果</p>
          </div>
        </div>
      </div>
    </section>

    <el-dialog v-model="showAddDialog" title="接入 Jetson 视频源" width="560px" class="source-dialog">
      <el-form :model="addForm" label-position="top">
        <div class="dialog-grid">
          <el-form-item label="摄像头 ID" required>
            <el-input v-model.trim="addForm.camera_id" placeholder="例如 camera_east" maxlength="50" />
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model.trim="addForm.name" placeholder="例如 坝体东侧" maxlength="100" />
          </el-form-item>
        </div>
        <el-form-item label="接入方式" required>
          <el-radio-group v-model="addForm.source_type" class="source-type-group" @change="applySourceDefault">
            <el-radio-button value="rtsp">海康 RTSP</el-radio-button>
            <el-radio-button value="usb">Jetson USB</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="视频源" required>
          <el-input
            v-model.trim="addForm.source"
            type="textarea"
            :rows="3"
            :placeholder="sourcePlaceholder"
          />
        </el-form-item>
        <p class="source-help">{{ sourceHelp }}</p>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addingCamera" @click="handleAddCamera">保存并连接</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Aim, Camera, Connection, Crop, DataAnalysis, Delete, Files, Loading, Monitor,
  Picture, Plus, UploadFilled, VideoCamera, VideoPlay,
} from '@element-plus/icons-vue'
import {
  addCamera, createStreamTicket, createVideoDetection, deleteVideoDetectionJob,
  detectImage, getCameraList, getCameraStatus, getCameraZones, getModelStatus,
  getVideoDetectionResult, getVideoDetectionStatus, saveCameraZones,
  setDetectionEnabled, snapshotDetect,
} from '@/api/camera'
import {
  classColor as getClassColor, confidencePercent, detectionName,
  detectionInZone, findVideoSample, formatDeviceCommTime, isValidDetection,
  normalizeClassifications, normalizeDetections, normalizeZones, primaryClassification,
  zoneTypeLabel,
} from '@/utils/cameraDetectionView'
import { CameraWebRtcPlayer } from '@/utils/cameraWebRtc'
import { subscribeDetectionEvents } from '@/utils/detectionEvents'

const cameras = ref([])
const route = useRoute()
const router = useRouter()
const currentCameraId = ref('')
const currentCamera = ref(null)
const modelStatus = ref({ loaded: false, models: {} })
const analysisTask = ref('detect')
const detectionEnabled = ref(false)
const detectionToggling = ref(false)
const detectionConnectionState = ref('closed')
const latestDetection = ref({ detections: [], count: 0 })
const detections = ref([])
const detectionZones = ref([])
const activeZoneType = ref('person_intrusion')
const zoneDrawing = ref(false)
const draftZone = ref(null)
const liveVideoRef = ref(null)
const streamMode = ref('webrtc')
const streamUrl = ref('')
const streamLoading = ref(false)
const showAddDialog = ref(false)
const addingCamera = ref(false)
const addForm = ref({ camera_id: '', name: '', source_type: 'rtsp', source: '' })

const imageUploading = ref(false)
const uploadResult = ref(null)
const videoPreviewUrl = ref('')
const uploadedVideoRef = ref(null)
const videoJob = ref(null)
const videoResult = ref(null)
const videoSample = ref(null)
const videoDetections = ref([])
const videoUploadProgress = ref(0)

let statusTimer = null
let streamRetryTimer = null
let videoPollTimer = null
let closeDetectionEvents = null
let streamRequestGeneration = 0
let cameraMutationRevision = 0
let webRtcPlayer = null

const imageWidth = computed(() => Number(latestDetection.value.image_width) || 0)
const imageHeight = computed(() => Number(latestDetection.value.image_height) || 0)
const labelFontSize = computed(() => Math.max(14, imageWidth.value / 55))
const labelPadding = computed(() => labelFontSize.value * 0.35)
const labelHeight = computed(() => labelFontSize.value * 1.35)
const boxStrokeWidth = computed(() => Math.max(2, imageWidth.value / 500))
const visibleDetections = computed(() => detections.value.filter(isValidDetection))
const liveAlerts = computed(() => Array.isArray(latestDetection.value.alerts) ? latestDetection.value.alerts : [])
const liveAlertZoneIds = computed(() => new Set(liveAlerts.value.map((alert) => alert.zone_id)))
const zonesForOverlay = computed(() => [...detectionZones.value, ...(draftZone.value ? [draftZone.value] : [])])
const analysisTaskLabel = computed(() => taskTypeLabel(analysisTask.value))
const selectedModelReady = computed(() => Boolean(modelStatus.value.models?.[analysisTask.value]?.loaded))
const canToggleDetection = computed(() => Boolean(currentCamera.value?.connected && selectedModelReady.value))
const videoWidth = computed(() => Number(videoSample.value?.image_width) || 0)
const videoHeight = computed(() => Number(videoSample.value?.image_height) || 0)
const videoLabelFontSize = computed(() => Math.max(14, videoWidth.value / 55))
const videoLabelPadding = computed(() => videoLabelFontSize.value * 0.35)
const videoLabelHeight = computed(() => videoLabelFontSize.value * 1.35)
const videoBoxStrokeWidth = computed(() => Math.max(2, videoWidth.value / 500))
const imageDetections = computed(() => normalizeDetections(uploadResult.value))
const liveClassifications = computed(() => normalizeClassifications(latestDetection.value))
const livePrediction = computed(() => primaryClassification(latestDetection.value))
const imageClassifications = computed(() => normalizeClassifications(uploadResult.value))
const imagePrediction = computed(() => primaryClassification(uploadResult.value))
const videoClassifications = computed(() => normalizeClassifications(videoSample.value))
const videoPrediction = computed(() => primaryClassification(videoSample.value))
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
const videoProgress = computed(() => {
  if (videoJob.value?.state === 'uploading') return videoUploadProgress.value
  return Number(videoJob.value?.progress || 0)
})
const videoStateText = computed(() => ({
  uploading: '正在上传', queued: '等待推理', processing: 'AI 分析中',
  completed: '分析完成', failed: '分析失败', cancelled: '已取消',
}[videoJob.value?.state] || '准备中'))
const sourcePlaceholder = computed(() => ({
  rtsp: 'rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/102',
  usb: '/dev/video0',
}[addForm.value.source_type]))
const sourceHelp = computed(() => ({
  rtsp: '海康网络摄像头接在 Jetson 网口或同一网络后，填写摄像头 RTSP 地址。',
  usb: 'USB/UVC 摄像头需同时在 .env 设置 CAMERA_DEVICE=/dev/video0。',
}[addForm.value.source_type]))
const isMediaAnalysisRoute = computed(() => ['image', 'video'].includes(route.meta.mediaTab))
const mediaTab = computed(() => route.meta.mediaTab === 'video' ? 'video' : 'image')
const mediaHeadingTitle = computed(() => mediaTab.value === 'video' ? '视频分析' : '图片分析')
const mediaHeadingDescription = computed(() => (
  mediaTab.value === 'video'
    ? '上传视频仅用于本次分析；结果为临时时间轴，不进入历史或告警流程。'
    : '上传图片仅用于本次分析；检测或分类结果不进入历史或告警流程。'
))

function sourceTypeLabel(type) {
  return ({ rtsp: 'RTSP', usb: 'USB / V4L2' })[type] || 'VIDEO'
}

function taskTypeLabel(taskType) {
  return taskType === 'classify' ? '图片分类' : '目标检测'
}

async function fetchModelStatus() {
  const response = await getModelStatus()
  modelStatus.value = response.data || { loaded: false, models: {} }
}

async function fetchCameras() {
  const response = await getCameraList()
  cameras.value = response.data?.cameras || []
  if (!currentCameraId.value && cameras.value.length) currentCameraId.value = cameras.value[0].camera_id
  currentCamera.value = cameras.value.find((item) => item.camera_id === currentCameraId.value) || null
}

async function fetchCameraZones(cameraId = currentCameraId.value) {
  if (!cameraId) {
    detectionZones.value = []
    return
  }
  const response = await getCameraZones(cameraId)
  if (cameraId === currentCameraId.value) detectionZones.value = normalizeZones(response.data)
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

async function startMjpegFallback(error = null, notify = true) {
  const player = webRtcPlayer
  webRtcPlayer = null
  player?.close()
  streamMode.value = 'mjpeg'
  streamLoading.value = true
  await nextTick()
  await refreshStreamTicket()
  if (error && notify) ElMessage.warning('WebRTC 连接失败，已切换到 MJPEG 兼容画面')
}

async function startLiveStream() {
  const cameraId = currentCameraId.value
  if (!cameraId || !currentCamera.value?.connected) return
  if (currentCamera.value.source_type !== 'rtsp') {
    await startMjpegFallback(null, false)
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
      startMjpegFallback(error).catch(() => null)
    },
  })
  webRtcPlayer = player
  try {
    await player.connect()
  } catch (error) {
    if (webRtcPlayer === player && cameraId === currentCameraId.value) {
      await startMjpegFallback(error)
    }
  }
}

async function activateCamera(cameraId) {
  stopDetectionSubscription()
  stopLiveStream()
  detections.value = []
  latestDetection.value = { detections: [], count: 0 }
  detectionZones.value = []
  draftZone.value = null
  zoneDrawing.value = false
  currentCamera.value = cameras.value.find((camera) => camera.camera_id === cameraId) || null
  detectionEnabled.value = Boolean(currentCamera.value?.detection_enabled)
  if (detectionEnabled.value && currentCamera.value?.analysis_task) {
    analysisTask.value = currentCamera.value.analysis_task
  }
  await fetchCameraZones(cameraId).catch(() => {
    detectionZones.value = normalizeZones({ zones: currentCamera.value?.detection_zones || [] })
  })
  if (isMediaAnalysisRoute.value) return
  if (currentCamera.value?.connected) await startLiveStream()
  if (detectionEnabled.value) startDetectionSubscription()
}

async function refreshStreamTicket() {
  const cameraId = currentCameraId.value
  if (!cameraId || !currentCamera.value?.connected) return
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
      streamUrl.value = ''
    }
  }
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
    const response = await setDetectionEnabled(currentCameraId.value, !detectionEnabled.value, {
      task_type: analysisTask.value,
    })
    currentCamera.value = { ...currentCamera.value, ...response.data }
    detectionEnabled.value = Boolean(response.data.detection_enabled)
    updateCameraInList(currentCamera.value)
    latestDetection.value = { detections: [], count: 0 }
    detections.value = []
    if (detectionEnabled.value) startDetectionSubscription()
    else stopDetectionSubscription()
    ElMessage.success(response.data.message)
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
    await clearVideoJob()
    if (!detectionEnabled.value || !currentCameraId.value) return
    const response = await setDetectionEnabled(currentCameraId.value, true, {
      task_type: taskType,
    })
    currentCamera.value = { ...currentCamera.value, ...response.data }
    updateCameraInList(currentCamera.value)
    ElMessage.success(`实时分析已切换为${taskTypeLabel(taskType)}`)
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
  const statusRevision = cameraMutationRevision
  try {
    const response = await getCameraStatus(currentCameraId.value)
    if (detectionToggling.value || statusRevision !== cameraMutationRevision) return
    const previousConnected = Boolean(currentCamera.value?.connected)
    const backendDetectionEnabled = Boolean(response.data.detection_enabled)
    currentCamera.value = response.data
    if (!detectionZones.value.length && response.data.detection_zones?.length) {
      detectionZones.value = normalizeZones({ zones: response.data.detection_zones })
    }
    updateCameraInList(response.data)
    if (!isMediaAnalysisRoute.value && !previousConnected && response.data.connected) await startLiveStream()
    if (previousConnected && !response.data.connected) stopLiveStream()
    if (backendDetectionEnabled !== detectionEnabled.value) {
      detectionEnabled.value = backendDetectionEnabled
      if (!isMediaAnalysisRoute.value && backendDetectionEnabled) startDetectionSubscription()
      else { stopDetectionSubscription(); detections.value = [] }
    }
    if (backendDetectionEnabled && response.data.analysis_task !== analysisTask.value) {
      analysisTask.value = response.data.analysis_task || 'detect'
      latestDetection.value = { task_type: analysisTask.value, detections: [], classifications: [] }
      detections.value = []
    }
  } catch {
    // Keep the active MJPEG connection during a transient status request failure.
  }
}

function updateCameraInList(camera) {
  const index = cameras.value.findIndex((item) => item.camera_id === camera.camera_id)
  if (index >= 0) cameras.value[index] = camera
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

function switchMediaTab(tab) {
  const target = tab === 'video' ? '/monitor/camera/video' : '/monitor/camera/image'
  if (route.path !== target) router.push(target)
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

async function handleVideoUpload(file) {
  const rawFile = file.raw
  if (!rawFile) return
  const suffix = rawFile.name.split('.').pop()?.toLowerCase()
  if (!['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v'].includes(suffix)) {
    ElMessage.error('请选择 MP4、MOV、AVI、MKV、WEBM 或 M4V 视频')
    return
  }
  if (rawFile.size > 200 * 1024 * 1024) {
    ElMessage.error('视频大小不能超过 200MB')
    return
  }
  await clearVideoJob()
  if (route.path !== '/monitor/camera/video') router.push('/monitor/camera/video')
  videoPreviewUrl.value = URL.createObjectURL(rawFile)
  videoUploadProgress.value = 0
  videoJob.value = { filename: rawFile.name, state: 'uploading', progress: 0, processed_samples: 0 }
  try {
    const response = await createVideoDetection(rawFile, {
      confidence: 0.5,
      sampleFps: 2,
      taskType: analysisTask.value,
      onUploadProgress(event) {
        if (event.total) videoUploadProgress.value = Math.min(99, Math.round(event.loaded / event.total * 100))
      },
    })
    videoJob.value = response.data
    scheduleVideoPoll(300)
  } catch (error) {
    videoJob.value = { ...videoJob.value, state: 'failed', error: error?.response?.data?.detail || '视频上传失败' }
  }
}

function scheduleVideoPoll(delay = 800) {
  clearTimeout(videoPollTimer)
  videoPollTimer = setTimeout(pollVideoJob, delay)
}

async function pollVideoJob() {
  const jobId = videoJob.value?.job_id
  if (!jobId) return
  try {
    const response = await getVideoDetectionStatus(jobId)
    videoJob.value = response.data
    if (response.data.state === 'completed') {
      const result = await getVideoDetectionResult(jobId)
      videoResult.value = result.data
      syncVideoDetection()
      ElMessage.success(
        result.data.task_type === 'detect'
          ? '视频检测完成，可播放查看同步标框'
          : '视频分类完成，可播放查看各采样位置结果',
      )
      return
    }
    if (['failed', 'cancelled'].includes(response.data.state)) return
    scheduleVideoPoll()
  } catch {
    scheduleVideoPoll(1600)
  }
}

function syncVideoDetection() {
  const timeline = videoResult.value?.timeline
  if (!timeline?.length || !uploadedVideoRef.value) return
  const sample = findVideoSample(timeline, uploadedVideoRef.value.currentTime)
  videoSample.value = sample
  videoDetections.value = normalizeDetections(sample)
}

async function clearVideoJob() {
  clearTimeout(videoPollTimer)
  const jobId = videoJob.value?.job_id
  if (jobId) deleteVideoDetectionJob(jobId).catch(() => null)
  if (videoPreviewUrl.value) URL.revokeObjectURL(videoPreviewUrl.value)
  videoPreviewUrl.value = ''
  videoJob.value = null
  videoResult.value = null
  videoSample.value = null
  videoDetections.value = []
}

function applySourceDefault(type) {
  addForm.value.source = type === 'usb' ? '/dev/video0' : ''
}

async function handleAddCamera() {
  if (!/^[A-Za-z0-9_-]{1,50}$/.test(addForm.value.camera_id)) {
    return ElMessage.warning('摄像头 ID 只能包含字母、数字、下划线和短横线')
  }
  const source = addForm.value.source
  const validSource = /^rtsps?:\/\/[^\s]+$/i.test(source)
    || /^\/dev\/video\d+$/.test(source)
  if (!validSource) return ElMessage.warning('请填写有效的 RTSP 或 /dev/videoN 视频源')
  addingCamera.value = true
  try {
    const cameraId = addForm.value.camera_id
    await addCamera({ camera_id: cameraId, name: addForm.value.name, source })
    showAddDialog.value = false
    addForm.value = { camera_id: '', name: '', source_type: 'rtsp', source: '' }
    await fetchCameras()
    currentCameraId.value = cameraId
    await activateCamera(cameraId)
    ElMessage.success('视频源已保存，Jetson 正在建立连接')
  } finally {
    addingCamera.value = false
  }
}

function zonePixelRect(zone) {
  const rect = zone?.rect || {}
  return {
    x: rect.x * imageWidth.value,
    y: rect.y * imageHeight.value,
    width: rect.width * imageWidth.value,
    height: rect.height * imageHeight.value,
  }
}

function pointerToImagePoint(event) {
  const svg = event.currentTarget
  if (!svg || imageWidth.value <= 0 || imageHeight.value <= 0) return null
  if (svg.createSVGPoint) {
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const matrix = svg.getScreenCTM()
    if (matrix) {
      const mapped = point.matrixTransform(matrix.inverse())
      return {
        x: Math.max(0, Math.min(imageWidth.value, mapped.x)),
        y: Math.max(0, Math.min(imageHeight.value, mapped.y)),
      }
    }
  }
  const rect = svg.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(imageWidth.value, (event.clientX - rect.left) / rect.width * imageWidth.value)),
    y: Math.max(0, Math.min(imageHeight.value, (event.clientY - rect.top) / rect.height * imageHeight.value)),
  }
}

function startZoneDraw(event) {
  if (!zoneDrawing.value || imageWidth.value <= 0 || imageHeight.value <= 0) return
  const point = pointerToImagePoint(event)
  if (!point) return
  draftZone.value = {
    id: `draft_${Date.now()}`,
    name: zoneTypeLabel(activeZoneType.value),
    type: activeZoneType.value,
    enabled: true,
    rect: {
      x: point.x / imageWidth.value,
      y: point.y / imageHeight.value,
      width: 0,
      height: 0,
    },
    start: point,
  }
}

function updateZoneDraw(event) {
  if (!zoneDrawing.value || !draftZone.value) return
  const point = pointerToImagePoint(event)
  if (!point) return
  const start = draftZone.value.start
  const x1 = Math.min(start.x, point.x)
  const y1 = Math.min(start.y, point.y)
  const x2 = Math.max(start.x, point.x)
  const y2 = Math.max(start.y, point.y)
  draftZone.value = {
    ...draftZone.value,
    rect: {
      x: x1 / imageWidth.value,
      y: y1 / imageHeight.value,
      width: (x2 - x1) / imageWidth.value,
      height: (y2 - y1) / imageHeight.value,
    },
  }
}

async function finishZoneDraw() {
  if (!draftZone.value) return
  const { start, ...zone } = draftZone.value
  draftZone.value = null
  if (zone.rect.width < 0.01 || zone.rect.height < 0.01) return
  const nextZones = [
    ...detectionZones.value,
    {
      ...zone,
      id: `${zone.type}_${Date.now()}`,
      name: zoneTypeLabel(zone.type),
    },
  ]
  await persistZones(nextZones)
}

async function persistZones(zones) {
  const response = await saveCameraZones(currentCameraId.value, zones)
  detectionZones.value = normalizeZones(response.data)
  currentCamera.value = { ...currentCamera.value, detection_zones: detectionZones.value }
  updateCameraInList(currentCamera.value)
  latestDetection.value = enrichDetectionPayload(latestDetection.value)
  ElMessage.success(response.data.message || '检测区域已保存')
}

async function removeZone(zoneId) {
  await persistZones(detectionZones.value.filter((zone) => zone.id !== zoneId))
}

function zoneStroke(zone) {
  if (zone.id?.startsWith('draft_')) return '#ffffff'
  if (liveAlertZoneIds.value.has(zone.id)) return '#ff5d6c'
  return zone.type === 'illegal_fishing' ? '#ffbd65' : '#48d8ff'
}

function zoneFill(zone) {
  if (liveAlertZoneIds.value.has(zone.id)) return 'rgba(255, 93, 108, 0.20)'
  return zone.type === 'illegal_fishing' ? 'rgba(255, 189, 101, 0.12)' : 'rgba(72, 216, 255, 0.12)'
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
  try {
    await Promise.all([fetchModelStatus(), fetchCameras()])
    if (currentCameraId.value) await activateCamera(currentCameraId.value)
  } catch {
    // Authentication interceptor handles an expired login and redirects once.
  }
  resetStatusTimer()
})

watch(isMediaAnalysisRoute, async (mediaMode) => {
  resetStatusTimer()
  if (mediaMode) {
    stopLiveStream()
    stopDetectionSubscription()
    return
  }
  if (currentCameraId.value) await activateCamera(currentCameraId.value)
})

onBeforeUnmount(() => {
  clearInterval(statusTimer)
  stopLiveStream()
  stopDetectionSubscription()
  clearVideoJob()
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
  padding: 18px;
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

.live-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 12px; margin-top: 12px; }
.live-card, .telemetry-card { min-height: 520px; padding: 16px; }
.card-heading { min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-heading h2, .lab-heading h2 { margin: 0; font-size: 16px; }
.feed-metrics { display: flex; gap: 10px; }
.feed-metrics span { min-width: 104px; display: flex; flex-direction: column; padding: 8px 12px; text-align: left; border: 1px solid rgba(81, 174, 210, 0.13); border-radius: 9px; background: rgba(4, 21, 34, 0.45); }
.feed-metrics small, .telemetry-grid small, .video-summary small, .job-title small { color: #607f94; font-size: 9px; letter-spacing: 0.08em; }
.feed-metrics small { font-size: 11px; }
.feed-metrics b { margin-top: 5px; color: #d5f2fc; font-family: monospace; font-size: 16px; line-height: 1.2; }

.video-stage, .video-empty { position: relative; height: calc(100% - 64px); min-height: 430px; overflow: hidden; border: 1px solid rgba(73, 194, 232, 0.16); border-radius: 12px; background: #030b12; }
.video-stream, .box-overlay, .zone-overlay { position: absolute; inset: 0; width: 100%; height: 100%; }
.video-stream { object-fit: contain; }
.box-overlay { z-index: 3; pointer-events: none; }
.zone-overlay { z-index: 4; pointer-events: none; }
.zone-overlay.drawing { cursor: crosshair; pointer-events: auto; }
.detection-box { fill: none; vector-effect: non-scaling-stroke; filter: drop-shadow(0 0 3px currentColor); }
.detection-label { fill: #04131b; font-weight: 800; }
.zone-rect {
  vector-effect: non-scaling-stroke;
  stroke-dasharray: 10 6;
  filter: drop-shadow(0 0 5px currentColor);
}
.zone-label {
  font-size: 16px;
  font-weight: 800;
  paint-order: stroke;
  stroke: rgba(3, 12, 18, 0.9);
  stroke-width: 4px;
}
.scan-grid { position: absolute; inset: 0; z-index: 2; pointer-events: none; opacity: 0.12; background: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(66, 210, 245, 0.12) 4px); }
.corner { position: absolute; z-index: 4; width: 25px; height: 25px; border-color: rgba(72, 216, 255, 0.55); }
.corner-tl { left: 12px; top: 12px; border-left: 2px solid; border-top: 2px solid; }
.corner-tr { right: 12px; top: 12px; border-right: 2px solid; border-top: 2px solid; }
.corner-bl { left: 12px; bottom: 12px; border-left: 2px solid; border-bottom: 2px solid; }
.corner-br { right: 12px; bottom: 12px; border-right: 2px solid; border-bottom: 2px solid; }
.stage-loading, .video-processing-overlay { position: absolute; inset: 0; z-index: 6; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #8ddcf0; background: rgba(3, 14, 23, 0.76); backdrop-filter: blur(3px); }
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
  grid-template-columns: 4px minmax(0, 1fr) 28px;
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
.zone-panel p { margin: 8px 0 0; color: #607f94; font-size: 11px; line-height: 1.5; }
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

.media-lab { margin-top: 12px; padding: 18px; }
.lab-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; border-bottom: 1px solid rgba(83, 159, 191, 0.13); }
.lab-heading > div > p:last-child { margin: 6px 0 14px; color: #6e8ba0; font-size: 11px; }
.media-mode-switch { display: flex; gap: 6px; margin-bottom: 12px; padding: 4px; border: 1px solid rgba(72, 187, 225, 0.18); border-radius: 10px; background: rgba(3, 20, 33, 0.58); }
.media-mode-switch button {
  height: 34px;
  padding: 0 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: #9ab8c9;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.media-mode-switch button:hover { color: #e7f8ff; background: rgba(31, 101, 132, 0.26); }
.media-mode-switch button.active { color: #061b23; border-color: rgba(72, 216, 255, 0.62); background: linear-gradient(110deg, var(--cyan), var(--mint)); font-weight: 800; }
.media-tabs { width: 350px; padding: 5px; border: 1px solid rgba(72, 187, 225, 0.2); border-radius: 12px; background: rgba(3, 20, 33, 0.58); }
.media-tabs :deep(.el-tabs__header) { margin: 0; }
.media-tabs :deep(.el-tabs__content) { display: none; }
.media-tabs :deep(.el-tabs__nav-wrap::after), .media-tabs :deep(.el-tabs__active-bar) { display: none; }
.media-tabs :deep(.el-tabs__nav) { width: 100%; display: flex; gap: 6px; }
.media-tabs :deep(.el-tabs__item) { flex: 1; height: 46px; padding: 0 18px; color: #9ab8c9; font-size: 14px; border: 1px solid transparent; border-radius: 8px; transition: color 0.2s, border-color 0.2s, background 0.2s, box-shadow 0.2s; }
.media-tabs :deep(.el-tabs__item:hover) { color: #e7f8ff; background: rgba(31, 101, 132, 0.26); }
.media-tabs :deep(.el-tabs__item.is-active) { color: #effcff; font-weight: 700; border-color: rgba(72, 216, 255, 0.48); background: linear-gradient(110deg, rgba(30, 143, 190, 0.42), rgba(43, 184, 161, 0.25)); box-shadow: 0 0 18px rgba(49, 194, 221, 0.14), inset 0 1px rgba(255, 255, 255, 0.08); }
.media-tabs :deep(.el-tabs__item span) { display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.lab-content { display: grid; gap: 14px; padding-top: 16px; }
.image-lab { grid-template-columns: 340px minmax(0, 1fr); }
.video-lab { grid-template-columns: 360px minmax(0, 1fr); }
.drop-zone :deep(.el-upload), .drop-zone :deep(.el-upload-dragger) { width: 100%; height: 100%; }
.drop-zone :deep(.el-upload-dragger) { min-height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px dashed rgba(77, 202, 233, 0.28); border-radius: 12px; background: rgba(5, 25, 39, 0.46); }
.drop-zone :deep(.el-upload-dragger:hover) { border-color: var(--cyan); background: rgba(14, 62, 82, 0.4); }
.upload-symbol { width: 58px; height: 58px; display: grid; place-items: center; margin-bottom: 14px; color: var(--cyan); border-radius: 16px; background: rgba(58, 183, 217, 0.1); }
.video-symbol { color: var(--mint); background: rgba(64, 210, 169, 0.1); }
.drop-zone h3 { margin-bottom: 7px; color: #c6dce7; font-size: 14px; }
.drop-zone p { max-width: 280px; margin: 0; color: #668397; font-size: 10px; }
.media-result { min-height: 220px; overflow: hidden; position: relative; border: 1px solid rgba(80, 165, 200, 0.12); border-radius: 12px; background: #05111b; }
.image-result.has-result { display: grid; grid-template-columns: minmax(0, 1fr) 290px; min-height: 390px; }
.image-preview-wrap { min-width: 0; min-height: 390px; position: relative; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #020a11; }
.image-preview-wrap img { display: block; width: 100%; height: 430px; object-fit: contain; }
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
.result-placeholder { min-height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #4f7186; }
.result-placeholder .el-icon { font-size: 42px; }

.video-upload-column { display: flex; flex-direction: column; gap: 10px; }
.video-drop :deep(.el-upload-dragger) { min-height: 165px; }
.job-panel { padding: 12px; border: 1px solid rgba(74, 174, 204, 0.13); border-radius: 10px; background: rgba(4, 19, 31, 0.5); }
.job-title { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.job-title > div { min-width: 0; display: flex; flex-direction: column; }
.job-title strong { overflow: hidden; margin-top: 3px; color: #bdd5e1; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.job-state { height: 22px; padding: 4px 8px; color: #89a9bb; font-size: 9px; border-radius: 11px; background: rgba(65, 115, 140, 0.18); }
.job-state.processing, .job-state.completed { color: var(--mint); background: rgba(54, 181, 147, 0.14); }
.job-state.failed { color: #ff8792; }
.job-meta { display: flex; justify-content: space-between; margin-top: 7px; color: #5e7c91; font-size: 9px; }
.video-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.video-summary div { display: flex; flex-direction: column; padding: 10px; border-radius: 8px; background: rgba(10, 40, 57, 0.48); }
.video-summary strong { margin-top: 5px; color: #bde1ec; font: 12px monospace; }
.video-analysis-stage { min-width: 0; }
.uploaded-video-wrap { position: relative; min-height: 330px; overflow: hidden; border: 1px solid rgba(74, 178, 210, 0.14); border-radius: 12px; background: #02080d; }
.uploaded-video-wrap video { display: block; width: 100%; height: 430px; object-fit: contain; }
.uploaded-overlay { bottom: 48px; height: calc(100% - 48px); }
.video-processing-overlay { bottom: 48px; }
.video-placeholder-result { min-height: 330px; border: 1px solid rgba(70, 151, 180, 0.12); border-radius: 12px; background: rgba(4, 18, 29, 0.5); }
.playback-targets { margin-top: 9px; padding: 10px; border: 1px solid rgba(76, 160, 192, 0.12); border-radius: 9px; background: rgba(5, 22, 34, 0.55); }
.playback-heading { display: flex; justify-content: space-between; color: #7c9bae; font-size: 10px; }
.playback-heading b { color: var(--cyan); }
.playback-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.playback-list span { padding: 5px 8px; color: #c6dde7; font-size: 9px; border-left: 2px solid var(--item-color); border-radius: 4px; background: rgba(35, 77, 94, 0.28); }
.playback-targets p { margin: 8px 0 0; color: #58778b; font-size: 10px; }

.dialog-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.source-type-group { width: 100%; }
.source-type-group :deep(.el-radio-button) { flex: 1; }
.source-type-group :deep(.el-radio-button__inner) { width: 100%; }
.source-help { margin: -6px 0 0; color: #71899a; font-size: 11px; line-height: 1.6; }

@media (max-width: 1200px) {
  .live-workspace { grid-template-columns: minmax(0, 1fr) 300px; }
  .image-result.has-result { grid-template-columns: minmax(0, 1fr) 250px; }
  .source-toolbar,
  .source-toolbar.analysis-toolbar { grid-template-columns: 1fr; align-items: flex-start; }
  .toolbar-actions { flex-wrap: wrap; justify-content: flex-end; }
}
@media (max-width: 900px) {
  .vision-page { padding: 10px; }
  .command-header, .source-toolbar, .lab-heading { align-items: stretch; flex-direction: column; }
  .header-status { align-self: flex-end; }
  .header-status, .source-control, .task-control, .toolbar-actions { flex-wrap: wrap; }
  .task-control { padding: 0; border: none; }
  .media-mode-switch { width: 100%; }
  .media-mode-switch button { flex: 1; justify-content: center; }
  .live-workspace, .image-lab, .video-lab { grid-template-columns: 1fr; }
  .image-result.has-result { grid-template-columns: 1fr; }
  .image-target-panel { min-height: 250px; border-top: 1px solid rgba(75, 175, 211, 0.16); border-left: none; }
  .telemetry-card { min-height: 420px; }
  .media-tabs, .camera-select { width: 100%; }
  .uploaded-video-wrap video { height: 320px; }
}
</style>
