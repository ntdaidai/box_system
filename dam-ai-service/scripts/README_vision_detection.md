# 视觉检测触发系统

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     两层触发架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  第一层：风速等级告警（单源触发）                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 风速传感器 → ECA引擎 → 风速等级事件 → 告警通知            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  第二层：风灾导致的异常（多源触发）                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 风速传感器 ──┐                                            │   │
│  │              ├→ ECA引擎 → 风灾异常事件 → 专业检测+分析    │   │
│  │ 摄像头AI ───┘                                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 数据流

```
摄像头AI检测
    │
    │ POST /api/v1/vision/detect/report
    ▼
VisionDetector
    │
    ├─ 存储检测结果
    └─ 触发回调
         │
         ▼
ECA引擎.on_vision_detection_updated()
    │
    ├─ 构建传感器快照（物理传感器+视觉检测）
    ├─ 检查事件条件
    └─ 触发满足的事件
         │
         ▼
执行响应流程（YOLO+SAM+Qwen+告警）
```

## API 接口

### 1. 上报检测结果

```bash
# 单个检测结果
curl -X POST http://localhost:8090/api/v1/vision/detect/report \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "camera_001",
    "detection_type": "crack",
    "detected": true,
    "confidence": 0.95,
    "details": {
      "crack_length": 15.5,
      "crack_width": 2.3
    }
  }'

# 批量检测结果
curl -X POST http://localhost:8090/api/v1/vision/detect/report/batch \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "camera_001",
    "detections": [
      {"detection_type": "crack", "detected": true, "confidence": 0.95},
      {"detection_type": "seepage", "detected": false, "confidence": 0.1}
    ]
  }'
```

### 2. 查询检测结果

```bash
# 获取最新结果
curl "http://localhost:8090/api/v1/vision/detect/latest?camera_id=camera_001" \
  -H "Authorization: Bearer <token>"

# 获取快照（ECA引擎格式）
curl http://localhost:8090/api/v1/vision/detect/snapshot \
  -H "Authorization: Bearer <token>"

# 获取历史
curl "http://localhost:8090/api/v1/vision/detect/history?limit=50" \
  -H "Authorization: Bearer <token>"

# 获取检测类型
curl http://localhost:8090/api/v1/vision/detect/types \
  -H "Authorization: Bearer <token>"
```

## 检测类型

| 类型 | 变量名 | 模型 | 说明 |
|------|--------|------|------|
| crack | crack_detected | CrackDetection-v1 | 裂缝检测 |
| seepage | seepage_detected | SeepageDetection-v1 | 渗水检测 |
| slope_damage | slope_damage_detected | YOLOv8 | 护坡损坏检测 |
| gate_deform | gate_deform_detected | YOLOv8 | 闸门变形检测 |

## 触发条件示例

### 风灾裂缝事件

```sql
-- 条件1：风速达到8级
wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8

-- 条件2：检测到裂缝
crack_detected = 1

-- 触发逻辑：条件1 AND 条件2 → 风灾裂缝事件
```

### ECA引擎数据快照格式

```json
{
  "wind_speed_ms": 18.5,
  "wind_level": 8,
  "temperature": 28.5,
  "humidity": 80,
  "crack_detected": 1,
  "seepage_detected": 0,
  "slope_damage_detected": 0,
  "gate_deform_detected": 0,
  "crack_confidence": 0.95,
  "crack_length": 15.5,
  "crack_width": 2.3
}
```

## 测试脚本

```bash
cd /home/jetson/box_system/dam-ai-service

# 运行测试
python scripts/test_vision_detection.py
```

## 完整触发流程示例

### 场景：风灾导致大坝裂缝

1. **风速传感器**检测到风速 18.5 m/s（8级大风）
   - 风速数据更新到 sensor_collector
   - 触发第一层：大风警报事件

2. **摄像头AI**检测到大坝裂缝
   - 调用 POST /api/v1/vision/detect/report
   - 视觉检测结果存储到 vision_detector
   - 触发 ECA 引擎检查多源事件

3. **ECA引擎**检查风灾裂缝事件
   - 条件1：wind_speed_ms >= 17.2 ✓
   - 条件2：crack_detected = 1 ✓
   - 触发"风灾裂缝"事件

4. **执行响应流程**
   - 步骤1：CrackDetection 精确检测裂缝（priority=1）
   - 步骤2：SAM 分割裂缝区域（priority=2）
   - 步骤3：Qwen 分析风险（priority=3）
   - 步骤4：发送紧急告警（priority=1）

5. **资源感知调度**
   - GPU 低负载：执行全部4步
   - GPU 中负载：跳过 Qwen 分析
   - GPU 高负载：只执行检测+告警

## 代码文件

| 文件 | 说明 |
|------|------|
| app/services/vision_detector.py | 视觉检测结果管理服务 |
| app/services/eca_engine.py | ECA引擎（支持视觉数据源） |
| app/api/vision_detect.py | 视觉检测API接口 |
| app/main.py | 应用入口（注册回调） |
