# Qwen-VL-4B 本地推理服务

边缘侧灾害巡查智能分析模型服务，基于 vLLM 部署的 Qwen-VL-4B 模型。

## 架构说明

```
客户端/工作流 → 本地推理服务 (localhost:9901)
                 ├─ 知识库检索 (dam-backend/Qdrant)
                 └─ vLLM 服务 (localhost:8001) → Qwen-VL-4B 模型
```

## 目录结构

```
qwen4B-service/
├── app/
│   └── main.py              # FastAPI 主程序
├── docker-compose.yml        # Docker Compose 配置
├── Dockerfile                # Docker 镜像构建文件
├── register.sh               # 模型库注册脚本
├── requirements.txt          # Python 依赖
└── README.md                 # 项目说明文档
```

## 前置条件

1. **vLLM 服务已启动**：Qwen-VL-4B 模型需要通过 vLLM 部署在 `localhost:8001`

   ```bash
   # 启动 vLLM 服务（示例）
   sudo docker run -d \
     --runtime=nvidia --gpus all \
     --network host \
     --ipc=host \
     --shm-size=8g \
     -v /home/jetson/.cache/modelscope/hub/models/Qwen/Qwen3-VL-4B-Instruct:/models \
     -v /home/jetson/vllm_cache:/root/.cache/vllm \
     --name vllm-qwen4b \
     -e TZ=Asia/Shanghai \
     ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin \
     python3 -m vllm.entrypoints.openai.api_server \
     --model /models \
     --served-model-name "qwen4B" \
     --gpu-memory-utilization 0.25 \
     --max-model-len 8192 \
     --trust-remote-code \
     --kv-cache-dtype auto \
     --enable-prefix-caching
   ```
2. **Docker 环境**：已安装 Docker 和 Docker Compose
3. **知识库服务可用**：dam-backend 与 Qdrant 已启动，默认访问 `http://localhost:8090/api/v1/knowledge`

## 快速启动

### 方式一：Docker Compose 启动（推荐）

```bash
cd /home/jetson/box_system/models/qwen4B-service
docker compose up -d
```

### 方式二：直接运行（开发模式）

```bash
cd /home/jetson/box_system/models/qwen4B-service
pip install -r requirements.txt
python app/main.py
```

## 验证服务

```bash
# 健康检查
curl http://localhost:9901/health

# 推理测试
curl -X POST http://localhost:9901/api/v1/local-inference \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_20260730_001",
    "task_type": "landslide_detection",
    "image_inputs": [
      {"path": "/path/to/image.jpg"}
    ],
    "detection_result": {
      "model_name": "YOLOv26-disaster",
      "objects": [
        {
          "class": "landslide",
          "confidence": 0.91,
          "bbox": [120, 86, 680, 510]
        }
      ]
    },
    "sensor_data": {
      "rainfall_1h": 48.6,
      "rainfall_24h": 126.4,
      "temperature": 26.5,
      "humidity": 91.2,
      "vibration": 0.83
    },
    "task_context": {
      "location": "库区右岸边坡",
      "mission": "应急巡查",
      "target": "灾害风险评估"
    }
  }'
```

## 注册到模型库

```bash
bash register.sh
```

## 配置参数

| 参数          | 环境变量          | 默认值                    | 说明                      |
| ------------- | ----------------- | ------------------------- | ------------------------- |
| vLLM 服务地址 | `VLLM_BASE_URL` | `http://localhost:8001` | vLLM OpenAI 兼容 API 地址 |
| 模型名称      | `MODEL_NAME`    | `qwen4B`                | vLLM 中注册的模型名称     |
| 最大 token 数 | `MAX_TOKENS`    | `2048`                  | 模型输出的最大 token 数   |
| 温度参数      | `TEMPERATURE`   | `0.15`                  | 生成温度，越低越确定      |
| 请求超时      | `TIMEOUT`       | `240`                   | 请求超时时间（秒），视频理解建议不低于 180 |
| 服务端口      | -                 | `9901`                  | 服务监听端口              |
| 上传媒体到云端 | `UPLOAD_MEDIA_TO_CLOUD` | `true` | `/infer` 是否把图片/视频转存到云端 MinIO |
| 上传失败是否中断 | `STRICT_MEDIA_UPLOAD` | `false` | `true` 时上传失败直接返回错误 |
| 边缘 MinIO 地址 | `EDGE_MINIO_ENDPOINT` | `localhost:9000` | AGX 本地 MinIO |
| 边缘 MinIO 桶 | `EDGE_MINIO_BUCKET` | `dam` | 输入路径未带 bucket 时使用 |
| 云端 MinIO 地址 | `CLOUD_MINIO_ENDPOINT` | `10.196.85.11:9469` | A100 云端 MinIO |
| 云端 MinIO 桶 | `CLOUD_MINIO_BUCKET` | `cloud-tasks` | 上传后供 35B 读取的 bucket |
| 云端对象前缀 | `CLOUD_MEDIA_PREFIX` | `workflow-media` | 上传对象路径前缀 |
| 知识库检索开关 | `KNOWLEDGE_RETRIEVAL_ENABLED` | `true` | `/infer` 推理前是否自动检索知识库 |
| 知识库 API 地址 | `KNOWLEDGE_API_BASE` | `http://localhost:8090/api/v1/knowledge` | dam-backend 知识库接口地址 |
| 知识命中数量 | `KNOWLEDGE_TOP_K` | `4` | 每次检索注入 prompt 的片段数量 |
| 知识最低分数 | `KNOWLEDGE_MIN_SCORE` | `0.1` | 低于该相似度分数的片段不注入 |

## 接口说明

### 健康检查

```
GET /health
```

响应示例：

```json
{
  "status": "healthy",
  "service": "qwen4b-local",
  "model": "qwen4B",
  "vllm_url": "http://localhost:8001",
  "vllm_reachable": true
}
```

### 本地推理

```
POST /api/v1/local-inference
```

请求参数：

```json
{
  "task_id": "任务唯一编号",
  "task_type": "任务类型",
  "image_inputs": [{"path": "图像路径", "base64": "base64编码"}],
  "detection_result": {"model_name": "模型名", "objects": [...]},
  "sensor_data": {"rainfall_1h": 0, "temperature": 0, ...},
  "task_context": {"location": "位置", "mission": "任务", "target": "目标"}
}
```

响应示例：

```json
{
  "task_id": "task_20260730_001",
  "status": "success",
  "scene_analysis": {
    "scene_type": "库区边坡",
    "suspected_event": "滑坡",
    "risk_level": "medium",
    "confidence": 0.76,
    "evidence": ["坡面存在异常裸土区域", "检测模型发现疑似滑移区域"],
    "uncertainties": ["部分区域存在遮挡"]
  },
  "cloud_enhancement": true
}
```

## 云端增强判断逻辑

当满足以下任一条件时，`cloud_enhancement` 返回 `true`：

1. 风险等级为 `high`
2. 模型置信度 < 0.7
3. 不确定因素 > 2 个
4. 任务类型为高风险（landslide_detection, flood_detection, dam_break_detection）

## 与 dam-backend 集成

dam-backend 中的 `local_inference_service` 已配置为调用此服务：

```python
# app/core/config.py
LOCAL_LLM_URL = "http://localhost:8001"  # vLLM 服务地址
LOCAL_LLM_MODEL_NAME = "qwen4B"
```

如需修改为调用本服务（代理模式），可将 `LOCAL_LLM_URL` 改为 `http://localhost:9901`。

### DAG `/infer` 媒体转存

模型库工作流调用 `POST /infer` 或 `POST /predict` 时，服务会从请求里的
`images`、`videos`、`media_objects`、`inputs`、`sensor_data` 汇总媒体路径：

- 本地文件路径：直接读取并上传云端 MinIO
- `bucket/object`：从 AGX 本地 MinIO 下载后上传
- `minio://bucket/object` 或 `s3://bucket/object`：按指定 bucket/object 下载后上传
- `http(s)://...`：下载后上传

### DAG `/infer` 知识库增强

`/infer` 会在调用 Qwen-VL-4B 之前自动构造知识检索问题，调用
`POST /api/v1/knowledge/search` 获取库坝巡查规范，并把命中的片段作为“知识库依据”
注入模型 prompt。检索问题优先使用请求中的 `knowledge_query`，为空时会从
`prompt`、`event_type`、`sensor_data`、`inputs`、`images`、`videos` 自动汇总。

请求可用以下字段控制：

```json
{
  "enable_knowledge_retrieval": true,
  "knowledge_query": "禁航区发现船只闯入如何处置",
  "knowledge_context": {
    "results": [],
    "prompt_context": "上游节点已经检索好的知识文本"
  }
}
```

响应会额外返回：

```json
{
  "knowledge_context": {
    "enabled": true,
    "query": "禁航区发现船只闯入如何处置",
    "total": 4,
    "source": "knowledge_api"
  },
  "knowledge_sources": [
    {
      "chunk_id": "knowledge:11:0",
      "document_id": 11,
      "score": 0.82,
      "document_title": "02_禁航区域船只闯入处置规范",
      "filename": "02_禁航区域船只闯入处置规范.docx"
    }
  ]
}
```

响应会包含给 35B 使用的云端对象引用：

```json
{
  "status": "success",
  "response": "{\"scene_type\":\"坝区边坡\",\"suspected_event\":\"滑坡\",\"risk_level\":\"high\",\"confidence\":0.88}",
  "report": "本地初步研判：场景为坝区边坡，疑似事件为滑坡，风险等级高风险，置信度0.88。",
  "preliminary_report": "本地初步研判：场景为坝区边坡，疑似事件为滑坡，风险等级高风险，置信度0.88。",
  "final_report": {
    "disaster_type": "滑坡",
    "risk_level": "high",
    "confidence": 0.88,
    "scene_analysis": "本地初步研判：场景为坝区边坡，疑似事件为滑坡，风险等级高风险，置信度0.88。",
    "evidence": ["视频显示坡面异常"],
    "impact_assessment": "本地模型仅完成初步研判，影响范围需结合云端模型或人工复核确认。",
    "recommendations": ["立即通知值班人员复核现场", "将视频和本地初判结果提交云端增强研判", "持续关注相关传感器变化"],
    "result_source": "local_qwen4b"
  },
  "template_id": "dam_patrol_daily_report",
  "template_data": {
    "report_date": "2026-08-04",
    "generated_at": "2026-08-04 16:30:00",
    "stats": {
      "total_events": 1,
      "low_count": 0,
      "medium_count": 0,
      "high_count": 1,
      "person_event_count": 0,
      "boat_fishing_event_count": 0,
      "auto_broadcast_count": 0,
      "manual_broadcast_count": 0,
      "closed_count": 0,
      "unclosed_count": 1,
      "closed_rate": "0.0%",
      "avg_response_time": "—",
      "avg_disposal_time": "—"
    },
    "event_rows": [
      {
        "occur_time": "16:20:01",
        "camera_name": "右岸边坡摄像头",
        "scene_type": "滑坡",
        "risk_level": "高风险",
        "broadcast_status": "未触发",
        "operator": "智能巡检系统",
        "disposal_result": "本地初步研判：场景为坝区边坡，疑似事件为滑坡，风险等级高风险，置信度0.88。",
        "completed_at": "—"
      }
    ],
    "high_event_rows": [],
    "data_sources": "SafetyEventInstance, SafetyEventTimelineLog, SafetyEventEvidence, VisualEventDetail, SensorData, Qwen-VL-4B"
  },
  "template_fields": {
    "report_date": "2026-08-04",
    "generated_at": "2026-08-04 16:30:00",
    "stats.total_events": 1
  },
  "template_tables": {
    "event_rows": [],
    "high_event_rows": []
  },
  "docx_context": {},
  "media_objects": [
    {
      "type": "video",
      "bucket": "cloud-tasks",
      "object_name": "workflow-media/EVT_001/videos/01_clip.mp4",
      "object_key": "workflow-media/EVT_001/videos/01_clip.mp4",
      "path": "cloud-tasks/workflow-media/EVT_001/videos/01_clip.mp4"
    }
  ],
  "cloud_media_objects": [
    {
      "type": "video",
      "bucket": "cloud-tasks",
      "object_name": "workflow-media/EVT_001/videos/01_clip.mp4",
      "object_key": "workflow-media/EVT_001/videos/01_clip.mp4",
      "path": "cloud-tasks/workflow-media/EVT_001/videos/01_clip.mp4"
    }
  ],
  "minio_context": {
    "endpoint": "http://10.196.85.11:9469",
    "bucket": "cloud-tasks",
    "objects": [{"type": "video", "object_name": "workflow-media/EVT_001/videos/01_clip.mp4"}]
  },
  "media_upload": {
    "enabled": true,
    "bucket": "cloud-tasks",
    "objects": [],
    "errors": []
  }
}
```

后续 35B 节点会优先使用上游 qwen4B 输出的 `media_objects/cloud_media_objects`，
因此它读取的是云端 MinIO 对象，而不是 AGX 本地路径。

`template_data`、`template_fields`、`template_tables`、`docx_context` 与 35B `/infer`
保持同一响应结构；如果云端模型不可用，后端可以直接使用 qwen4B 的这些字段填充
OnlyOffice/docxtpl 模板。
