# 库坝应急巡查多源触发智能感知系统

## 项目结构

```
box_system/
├── dam-frontend/          # Vue3 前端
│   ├── src/
│   │   ├── api/           # API接口
│   │   ├── layout/        # 布局组件
│   │   ├── router/        # 路由配置
│   │   ├── stores/        # Pinia状态管理
│   │   ├── utils/         # 工具函数
│   │   ├── views/         # 页面组件
│   │   └── styles/        # 样式文件
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── dam-ai-service/        # Python 后端服务 (FastAPI 一体化)
│   ├── app/
│   │   ├── api/           # API路由（含业务管理+传感器+AI视觉）
│   │   ├── models/        # SQLAlchemy 数据模型
│   │   ├── schemas/       # Pydantic 请求/响应模型
│   │   ├── sensors/       # 传感器读取模块
│   │   ├── services/      # 业务服务
│   │   └── core/          # 核心模块（配置/数据库/安全）
│   ├── vb05_python_sdk/   # 振动传感器SDK
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml     # Docker 编排配置
└── README.md              # 本文件
```

## 架构说明

Java 后端（`dam-system`）已移除，所有业务逻辑和 API 统一由 Python FastAPI 服务提供。
Python 后端同时负责：

| 模块           | 前缀               | 说明                    |
| -------------- | ------------------ | ----------------------- |
| 认证与用户管理 | `/api/auth`      | JWT 登录、用户 CRUD     |
| 设备管理       | `/api/device`    | 设备增删改查、状态查询  |
| 告警管理       | `/api/alarm`     | 告警列表、处理、统计    |
| 规则管理       | `/api/rule`      | 触发规则 CRUD           |
| 分析报告       | `/api/analysis`  | AI 分析报告 CRUD        |
| 传感器数据     | `/api/v1/sensor` | 实时/历史数据、SSE 推送 |
| 视觉分析       | `/api/v1/vision` | Qwen3-VL-8B 图像分析    |
| 健康检查       | `/api/v1/health` | 服务健康状态            |

## 快速开始

### 1. 启动基础服务

```bash
# 确保 MySQL、Redis、IoTDB 已启动
cd /home/jetson/iotdb && docker compose -f docker-compose-standalone.yml up -d
cd /home/jetson/mysql && docker compose up -d
cd /home/jetson/redis && docker compose up -d
```

### 2. 启动 AI 模型服务

```bash
# 启动 Qwen3-VL-8B
sudo docker run -d \
  --runtime=nvidia --gpus all \
  --network host \
  --ipc=host \
  --shm-size=16g \
  -v /home/jetson/.cache/modelscope/hub/models/Qwen/Qwen3-VL-8B-Instruct:/models \
  -v /home/jetson/vllm_cache:/root/.cache/vllm \
  --name vllm-qwen \
  -e TZ=Asia/Shanghai \
  -e PYTHONWARNINGS="ignore::UserWarning" \
  ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin \
  python3 -m vllm.entrypoints.openai.api_server \
  --model /models \
  --served-model-name "qwen" \
  --gpu-memory-utilization 0.5 \
  --max-model-len 8192 \
  --max-num-seqs 3 \
  --max-num-batched-tokens 8192 \
  --trust-remote-code \
  --kv-cache-dtype auto \
  --enable-prefix-caching \
  --generation-config vllm \
  --tensor-parallel-size 1
```

### 3. 启动应用服务

```bash
cd /home/jetson/box_system
docker compose up -d
```

### 4. 访问系统

- 前端页面: http://localhost:9457
- Python 后端: http://localhost:8090
- API 文档: http://localhost:8090/docs

## 技术栈

| 组件   | 技术                   | 版本   |
| ------ | ---------------------- | ------ |
| 前端   | Vue3 + Element Plus    | 3.4+   |
| 后端   | FastAPI (Python 3.10)  | 0.110+ |
| 数据库 | MySQL (SQLAlchemy ORM) | 8.0    |
| 时序库 | IoTDB                  | 2.0.8  |
| 缓存   | Redis                  | 7.x    |
| 大模型 | Qwen3-VL-8B (vLLM)     | -      |

## 端口说明

| 服务        | 端口 | 说明                       |
| ----------- | ---- | -------------------------- |
| 前端        | 9457 | Web 界面 (Nginx)           |
| Python 后端 | 8090 | 一体化业务 + AI + 数据采集 |
| OnlyOffice  | 80   | 在线文档编辑服务（host 网络） |
| MySQL       | 3306 | 关系数据库                 |
| Redis       | 6379 | 缓存                       |
| IoTDB       | 6667 | 时序数据库                 |
| Qwen3-VL-8B | 8003 | 视觉模型                   |
| WebRTC 网关 | 8002 | 仅回环监听的 RTSP 信令代理 |

## 无人机巡航动作 API

无人机巡航已从测试页面动作中抽成可供 ECA/工作流调用的业务 API。两条固定动作均会产生四张取证图：去程两张、回程两张；照片归档到 MinIO 的
`drone-cruises/{route_key}/{run_id}/` 目录，并在接口完成后返回四个 `minio_url`。

```text
GET  /api/v1/drone/routes
POST /api/v1/drone/cruises/fishing   # 禁渔航线
POST /api/v1/drone/cruises/wading    # 禁涉水航线
```

请求需要登录凭证：`Authorization: Bearer <JWT>`。默认模拟模式不要求请求体，传空 JSON 即可；也可以用 `duration_seconds`（1~900）调整模拟时长：

```json
{}
```

真实航线模式需要提供或在环境变量中配置以下四项：`workspace_id`（工作空间）、`dock_sn`（机场 SN）、`file_id`（对应航线 KMZ 文件 ID）、`payload_index`（相机负载索引，例如 `88-0-0`）。还可以传 `rth_altitude`（返航高度，默认 50 米）和 `min_battery_capacity`（最低电量阈值，默认 50%）：

```json
{
  "workspace_id": "工作空间 ID",
  "dock_sn": "机场 SN",
  "file_id": "当前航线文件 ID",
  "payload_index": "88-0-0",
  "rth_altitude": 50,
  "min_battery_capacity": 50
}
```

`fishing` 和 `wading` 会分别读取对应的航线文件配置。接口是同步调用，完成巡航和四张照片的 MinIO 归档后返回 `photos` 和 `image_urls`；默认 `DRONE_CRUISE_EXECUTOR=simulation` 用于当前演示联调，切换为 `real` 后才下发 DJI 航线和拍照指令。

## 安全注意事项

- **生产环境必须**将 `JWT_SECRET` 环境变量设置为强随机字符串
- **生产环境必须**更改默认管理员密码 `DEFAULT_ADMIN_PASSWORD`
- MySQL 密码通过 `MYSQL_PASSWORD` 环境变量传入，不要在配置文件中硬编码
- 所有 API（除登录和健康检查外）需要 JWT 认证

<!-- dai -->
## 摄像头实时检测与分类配置

`/monitor/camera` 顶部可以选择“目标检测”或“图片分类”。两类模型通过独立适配器
注册，实时摄像头、截图、图片上传和视频上传共用同一任务选择；所有 Jetson 推理请求
使用一条串行执行通道，避免多个模型同时争抢 GPU。

当前 Compose 默认模型为：

```dotenv
YOLO_DETECT_MODEL_PATH=/models/runs/yolo26x_continue/weights/best.pt
YOLO_CLASSIFY_MODEL_PATH=/models/disaster-classifier/best.engine
YOLO_CLASSIFY_FALLBACK_PATH=/models/disaster-classifier/best.pt
```

灾害分类模型输出 `earthquake / flood / landslide / mudslide`，分类模式只返回整图类别
与置信度，页面不会绘制检测框。当前默认挂载
`/home/jetson/sep/disaster_idf/yolo26x/models`，其中 `best.engine` 是面向当前
Jetson/TensorRT/CUDA 环境导出的 TensorRT FP16 engine；如果部署到不同 Jetson 或不同
TensorRT 版本机器，需要在目标机器上重新导出 engine；系统会用 `best.pt` 作为兜底分类
权重，避免 engine 不兼容时分类功能直接不可用。

摄像头统一在“实时监控 / 设备管理”中录入。连接测试成功后，设备保存到
`camera_device`，视频监控页按数据库主键加载已启用的视频源，不再读取环境变量中的
临时视频源配置。

海康 `101` 通常为主码流，`102` 通常为子码流。实时检测优先使用子码流以降低端到端延迟。
检测默认关闭，只有在页面点击“开启检测”后才会启动该摄像头的共享推理线程。

Compose 会运行 ARM64 `webrtc-streamer`，通过 `127.0.0.1:8002` 接收后端代理的
WebRTC 信令，媒体 UDP 端口范围为 `50000-50100`。HTTP 信令不直接暴露到局域网，
RTSP 用户名和密码也不会返回浏览器。海康码流请设置为 H.264；当前容器启用 H.264
压缩帧透传以降低 Jetson CPU 占用和播放延迟。如果跨路由器或公网观看，还需要部署
TURN 并开放对应 UDP 端口，当前默认配置面向 Jetson 同一局域网访问。

实时链路是两条并行支路：`webrtc-streamer` 直接将 RTSP 转成浏览器 WebRTC；Python
后端另行通过 OpenCV 拉取同一 RTSP，按 `CAMERA_DETECTION_FPS` 抽帧交给 YOLO。
检测结果以 SSE 元数据发送到前端，并用 SVG 叠加框，不会把标注后画面重新编码推流。
WebRTC 不可用时，页面会自动回退到原有的鉴权 MJPEG 兼容流。

图片与视频上传分析均位于 `/monitor/camera`。视频采用临时任务处理：浏览器播放本地
视频，后端按时间抽帧并返回分析时间轴；检测模式同步显示检测框，分类模式显示对应
采样位置的整图类别和置信度。原视频和结果不会写入
历史或触发告警，任务结果默认 30 分钟后清理。默认限制为 200MB、10 分钟，可通过
`MAX_VIDEO_SIZE_MB`、`MAX_VIDEO_DURATION_SECONDS` 和 `VIDEO_DETECTION_FPS` 调整。
