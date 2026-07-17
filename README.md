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
| MySQL       | 3306 | 关系数据库                 |
| Redis       | 6379 | 缓存                       |
| IoTDB       | 6667 | 时序数据库                 |
| Qwen3-VL-8B | 8000 | 视觉模型                   |
| WebRTC 网关 | 8002 | 仅回环监听的 RTSP 信令代理 |

## 安全注意事项

- **生产环境必须**将 `JWT_SECRET` 环境变量设置为强随机字符串
- **生产环境必须**更改默认管理员密码 `DEFAULT_ADMIN_PASSWORD`
- MySQL 密码通过 `MYSQL_PASSWORD` 环境变量传入，不要在配置文件中硬编码
- 所有 API（除登录和健康检查外）需要 JWT 认证

<!-- dai -->
## 摄像头实时检测配置

未接入摄像头时 `CAMERA_RTSP_URL` 保持为空，系统会正常启动，`/monitor/camera`
页面显示待配置状态。接入单路海康摄像头时，在项目 `.env` 中配置：

```dotenv
CAMERA_RTSP_URL=rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/102
CAMERA_ID=camera_001
CAMERA_NAME=主摄像头
CAMERA_AUTO_START=true
CAMERA_DETECTION_FPS=5
CAMERA_JPEG_QUALITY=80
```

如果需要展示并切换多路摄像头，使用 JSON 数组替代单路地址：

```dotenv
CAMERA_CONFIGS_JSON=[{"camera_id":"camera_east","name":"东侧摄像头","rtsp_url":"rtsp://用户:密码@192.0.2.10:554/Streaming/Channels/102","auto_start":true},{"camera_id":"camera_west","name":"西侧摄像头","rtsp_url":"rtsp://用户:密码@192.0.2.11:554/Streaming/Channels/102","auto_start":true}]
```

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

<!-- dai -->
海康网络摄像头即使网线连接在 Jetson 上，仍使用 RTSP 地址接入，不需要映射
`/dev/video0`。USB/UVC 摄像头才使用本地设备方式：

```dotenv
CAMERA_SOURCE=/dev/video0
CAMERA_DEVICE=/dev/video0
```

多路 JSON 的每一项也可以使用 `source`，例如
`{"camera_id":"usb","source":"/dev/video0"}`。页面中的“接入视频源”支持
RTSP 和 USB 两种类型；页面临时添加的配置在后端重启后不会
保留，正式部署请写入 `.env` 或 `CAMERA_CONFIGS_JSON`。

图片与视频上传检测均位于 `/monitor/camera`。视频采用临时任务处理：浏览器播放本地
视频，后端按时间抽帧并返回检测时间轴，播放时同步显示检测框。原视频和结果不会写入
历史或触发告警，任务结果默认 30 分钟后清理。默认限制为 200MB、10 分钟，可通过
`MAX_VIDEO_SIZE_MB`、`MAX_VIDEO_DURATION_SECONDS` 和 `VIDEO_DETECTION_FPS` 调整。
