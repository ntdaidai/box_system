# Qwen-VL-4B 本地推理服务

边缘侧灾害巡查智能分析模型服务，基于 vLLM 部署的 Qwen-VL-4B 模型。

## 架构说明

```
客户端 → 本地推理服务 (localhost:9901) → vLLM 服务 (localhost:8001) → Qwen-VL-4B 模型
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
| 请求超时      | `TIMEOUT`       | `60`                    | 请求超时时间（秒）        |
| 服务端口      | -                 | `9901`                  | 服务监听端口              |

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
