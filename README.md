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

## 安全注意事项

- **生产环境必须**将 `JWT_SECRET` 环境变量设置为强随机字符串
- **生产环境必须**更改默认管理员密码 `DEFAULT_ADMIN_PASSWORD`
- MySQL 密码通过 `MYSQL_PASSWORD` 环境变量传入，不要在配置文件中硬编码
- 所有 API（除登录和健康检查外）需要 JWT 认证

