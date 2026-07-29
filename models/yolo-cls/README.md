# YOLO26 灾害分类 API 服务

基于 YOLO26x 的灾害类型分类服务，支持从 MinIO 获取图片和视频进行分类推理。

## 功能特性

- 支持单张图片分类
- 支持视频分类（抽帧）
- 从 MinIO 获取文件
- 返回 Top-K 分类结果
- 健康检查和模型信息接口

## 分类类别

- earthquake（地震）
- flood（洪水）
- landslide（滑坡）
- mudslide（泥石流）

## 快速开始

### 1. 构建镜像

```bash
cd /home/jetson/jjq/yolo-docker
docker-compose build
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 模型信息
curl http://localhost:8000/model/info
```

## API 接口

### 健康检查

```
GET /health
```

响应示例：

```json
{
  "status": "healthy",
  "model_loaded": true
}
```

### 模型信息

```
GET /model/info
```

响应示例：

```json
{
  "classes": ["earthquake", "flood", "landslide", "mudslide"],
  "input_size": 256,
  "device": "0",
  "weights_path": "/app/models/yolo26x_cls_acc_96.pt"
}
```

### 单张图片分类

```
POST /classify/image
Content-Type: application/json

{
  "bucket": "images",
  "object_key": "earthquake/001.jpg"
}
```

响应示例：

```json
{
  "class": "earthquake",
  "confidence": 0.95,
  "top_k": [
    {"class_id": 0, "class_name": "earthquake", "confidence": 0.95},
    {"class_id": 1, "class_name": "flood", "confidence": 0.03},
    {"class_id": 2, "class_name": "landslide", "confidence": 0.02}
  ]
}
```

### 视频分类

```
POST /classify/video
Content-Type: application/json

{
  "bucket": "videos",
  "object_key": "flood/001.mp4",
  "frame_interval": 30
}
```

响应示例：

```json
{
  "main_class": "flood",
  "total_frames": 300,
  "sampled_frames": 10,
  "frame_interval": 30,
  "frames": [
    {
      "frame_id": 0,
      "class": "flood",
      "confidence": 0.92,
      "top_k": [...]
    }
  ]
}
```

## 使用示例

### 使用 curl

```bash
# 单张图片分类
curl -X POST http://localhost:8000/classify/image \
  -H "Content-Type: application/json" \
  -d '{"bucket": "images", "object_key": "earthquake/001.jpg"}'

# 视频分类
curl -X POST http://localhost:8000/classify/video \
  -H "Content-Type: application/json" \
  -d '{"bucket": "videos", "object_key": "flood/001.mp4", "frame_interval": 30}'
```

### 使用 Python

```python
import requests

# 单张图片分类
response = requests.post(
    "http://localhost:8000/classify/image",
    json={"bucket": "images", "object_key": "earthquake/001.jpg"}
)
print(response.json())

# 视频分类
response = requests.post(
    "http://localhost:8000/classify/video",
    json={"bucket": "videos", "object_key": "flood/001.mp4", "frame_interval": 30}
)
print(response.json())
```

## 配置说明

### 环境变量

| 变量名           | 说明                | 默认值                            |
| ---------------- | ------------------- | --------------------------------- |
| MINIO_ENDPOINT   | MinIO 服务地址      | localhost:9000                    |
| MINIO_ACCESS_KEY | MinIO 访问密钥      | minioadmin                        |
| MINIO_SECRET_KEY | MinIO 秘密密钥      | minioadmin                        |
| MINIO_SECURE     | 是否使用 HTTPS      | false                             |
| MODEL_WEIGHTS    | 模型权重文件路径    | /app/models/yolo26x_cls_acc_96.pt |
| DEVICE           | 推理设备            | 0                                 |
| IMG_SIZE         | 输入图片尺寸        | 256                               |
| TOP_K            | 返回的 top-k 结果数 | 3                                 |
| HOST             | 服务监听地址        | 0.0.0.0                           |
| PORT             | 服务监听端口        | 8000                              |
| WORKERS          | 工作进程数          | 1                                 |

## 目录结构

```
yolo-docker/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 主应用
│   ├── config.py            # 配置管理
│   ├── minio_client.py      # MinIO 客户端
│   ├── yolo_service.py      # YOLO 推理服务
│   └── models.py            # 数据模型
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## 依赖服务

- MinIO 服务（默认端口 9000）
- NVIDIA GPU（Jetson 设备）

## 注意事项

1. 确保 MinIO 服务正在运行
2. 确保 Jetson 设备有足够的 GPU 内存
3. 模型文件需要挂载到容器中
4. 网络配置需要允许容器访问 MinIO 服务
