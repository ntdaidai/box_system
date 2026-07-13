# 轻量级模型库 — Python 实施方案

## 0. 背景与目标

### 0.1 背景

当前项目（智能模型工作台）的模型库基于 Java Spring Boot 实现，功能完整但依赖较重（K8s、Kafka、MinIO、Redis、Harbor）。新需求是为**其他系统**提供一个轻量级的模型库服务，只需要核心的模型注册和容器部署管理能力，使用 Python 实现。

### 0.2 要做的事

用 Python (FastAPI) 实现一个独立的轻量级模型库服务，具备以下能力：

1. **模型注册** — 登记模型基本信息（名称、描述、框架等）
2. **部署绑定** — 将模型绑定到已有的 Docker 容器，或绑定到镜像（启动时自动创建容器），或两者同时绑定
3. **启动模型** — 已有容器则 `docker start`，仅绑镜像则 `docker run` 创建新容器后启动
4. **停止模型** — `docker stop` 停止运行中的容器（容器保留不销毁，下次可直接 start）
5. **容器重建** — 容器损坏时用相同配置重新创建
6. **推理代理** — 提供完整的推理地址 `http://{host_ip}:{host_port}{inference_path}`，调用方无需关心容器细节
7. **健康检查** — 启动后轮询推理端点确认服务就绪；运行中定时心跳检测
8. **日志查看** — 查看容器运行日志，支持流式推送
9. **状态同步** — 定时校验容器实际状态，防止数据库与 Docker 状态不一致
10. **资源监控** — 查询运行中容器的 CPU/内存/GPU 使用率

### 0.3 不做的事

以下功能在原系统中存在，但轻量级模型库**不需要**：
- 标签体系、收藏、模型卡片展示
- MinIO 镜像上传管道
- K8s/K3s 编排（改用本地 Docker）
- Kafka 异步消息（直接同步调用）
- 外部 API 接入（OPENAI/OLLAMA 等）
- Redis 缓存
- 文档发布

### 0.4 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 异步、自动生成 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 + Alembic | 数据库操作和迁移 |
| 数据库 | MySQL | 与原系统共用或独立实例 |
| Docker 客户端 | docker-py (docker SDK) | 本地 Unix socket 直连 Docker daemon |
| 定时任务 | APScheduler | 状态同步、健康检查心跳 |
| 日志流 | SSE (sse-starlette) | 容器日志流式推送 |

### 0.5 前置条件

- Python 3.10+
- Docker daemon 已安装并运行在同一主机上
- 进程用户有权限访问 `/var/run/docker.sock`（加入 `docker` 用户组）
- MySQL 实例可用
- GPU 支持需安装 NVIDIA Container Toolkit（如需 GPU 推理）

---

## 1. 数据库设计

### 1.1 表关系

```
model_registry (模型注册表)
  │
  ├── 1:1 ── model_deploy_binding (部署绑定表)
  │
  ├── 1:1 ── model_io_schema (IO Schema，可选)
  │
  └── 1:N ── model_operation_log (操作日志)
```

### 1.2 DDL — 全部建表语句

直接执行以下 SQL 即可完成建表：

```sql
-- 模型注册表
CREATE TABLE `model_registry` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `name`            VARCHAR(128)  NOT NULL COMMENT '模型名称',
  `description`     VARCHAR(512)  DEFAULT NULL COMMENT '模型描述',
  `framework`       VARCHAR(64)   DEFAULT NULL COMMENT '框架（PyTorch/TensorFlow/ONNX等）',
  `architecture`    VARCHAR(64)   DEFAULT NULL COMMENT '架构（CNN/Transformer等）',
  `model_type`      VARCHAR(64)   DEFAULT NULL COMMENT '模型类型（目标检测/图像分类/LLM等）',
  `model_size`      VARCHAR(32)   DEFAULT NULL COMMENT '模型大小（如 7B、1.2GB）',
  `runtime_status`  VARCHAR(16)   NOT NULL DEFAULT 'stopped' COMMENT '运行状态：stopped/starting/running/stopping/error',
  `owner_id`        BIGINT        DEFAULT NULL COMMENT '所有者用户 ID',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_owner_id` (`owner_id`),
  KEY `idx_runtime_status` (`runtime_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型注册表';

-- 部署绑定表
CREATE TABLE `model_deploy_binding` (
  `id`                BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`          BIGINT        NOT NULL COMMENT '关联模型 ID（model_registry.id）',
  `bind_type`         VARCHAR(16)   NOT NULL COMMENT '绑定类型：container / image / both',
  `container_id`      VARCHAR(64)   DEFAULT NULL COMMENT 'Docker 容器 ID',
  `container_name`    VARCHAR(128)  DEFAULT NULL COMMENT 'Docker 容器名称',
  `image_name`        VARCHAR(256)  DEFAULT NULL COMMENT 'Docker 镜像全名（含 tag）',
  `host_ip`           VARCHAR(64)   NOT NULL DEFAULT '127.0.0.1' COMMENT '宿主机 IP',
  `host_port`         INT           DEFAULT NULL COMMENT '宿主机映射端口',
  `container_port`    INT           DEFAULT NULL COMMENT '容器内部端口',
  `inference_path`    VARCHAR(256)  DEFAULT NULL COMMENT '推理接口路径（如 /predict）',
  `health_check_url`  VARCHAR(512)  DEFAULT NULL COMMENT '健康检查路径（如 /health）',
  `gpu_device`        VARCHAR(64)   DEFAULT NULL COMMENT 'GPU 设备映射（如 0 或 0,1）',
  `extra_mounts`      JSON          DEFAULT NULL COMMENT '挂载卷 [{"host":"...","container":"..."}]',
  `extra_env`         JSON          DEFAULT NULL COMMENT '环境变量 {"KEY":"VALUE"}',
  `remark`            VARCHAR(256)  DEFAULT NULL COMMENT '备注',
  `create_time`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  KEY `idx_container_id` (`container_id`),
  CONSTRAINT `fk_binding_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型部署绑定表';

-- IO Schema 表
CREATE TABLE `model_io_schema` (
  `id`          BIGINT    NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`    BIGINT    NOT NULL COMMENT '关联模型 ID',
  `inputs`      JSON      DEFAULT NULL COMMENT '输入 Schema',
  `outputs`     JSON      DEFAULT NULL COMMENT '输出 Schema',
  `create_time` DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_id` (`model_id`),
  CONSTRAINT `fk_schema_model` FOREIGN KEY (`model_id`) REFERENCES `model_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型 IO Schema';

-- 操作日志表
CREATE TABLE `model_operation_log` (
  `id`           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `model_id`     BIGINT       NOT NULL COMMENT '关联模型 ID',
  `operator_id`  BIGINT       DEFAULT NULL COMMENT '操作者用户 ID',
  `operation`    VARCHAR(32)  NOT NULL COMMENT '操作类型：start/stop/restart/rebuild/bind/unbind/delete',
  `detail`       JSON         DEFAULT NULL COMMENT '操作详情',
  `result`       VARCHAR(16)  NOT NULL COMMENT '结果：success/failed',
  `error_msg`    VARCHAR(512) DEFAULT NULL COMMENT '失败原因',
  `create_time`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `idx_model_id` (`model_id`),
  KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型操作日志';
```

### 1.3 表字段详解

#### model_registry — 运行状态机

```
stopped (默认) → starting → running → stopping → stopped
                  ↘         ↘ error   ↗
```

| 状态 | 含义 | 触发条件 |
|------|------|----------|
| `stopped` | 已停止 | 初始状态 / docker stop 成功 |
| `starting` | 启动中 | docker start/run 执行开始 |
| `running` | 运行中 | 容器 Running + 健康检查通过 |
| `stopping` | 停止中 | docker stop 执行开始 |
| `error` | 异常 | 启动失败 / 健康检查超时 / 容器崩溃 |

#### model_deploy_binding — 绑定类型

| bind_type | container_id | image_name | 场景 | 首次启动行为 |
|-----------|-------------|------------|------|-------------|
| `container` | 必填 | 可选 | 已有容器，直接纳入管理 | docker start |
| `image` | 空 | 必填 | 仅有镜像，启动时创建容器 | docker run → 自动填入 container_id，bind_type 改为 both |
| `both` | 必填 | 必填 | 容器已存在 + 记录镜像来源 | docker start（可 rebuild 用镜像重建） |

#### model_deploy_binding — 推理地址拼接

```
推理地址 = http://{host_ip}:{host_port}{inference_path}
```

示例：
- `http://127.0.0.1:8080/predict`
- `http://127.0.0.1:11434/v1/chat/completions`

这个地址在查询详情和列表接口中直接返回给调用方，调用方拿到即可调用推理服务。

#### model_io_schema — inputs/outputs 结构

inputs 是一个 JSON 数组，每个元素：
```json
{
  "field": "image",          // 字段 key（程序用）
  "type": "image",           // 语义类型：image / text / float / json / timeseries 等
  "label": "输入图片",        // 显示名（前端用）
  "targetFormat": "base64",  // 期望格式：base64 / url / file_path
  "defaultValue": null,      // 默认值
  "required": true           // 是否必填
}
```

outputs 同理但更简单：
```json
{
  "field": "detections",
  "type": "json",
  "label": "检测结果",
  "targetFormat": null
}
```

---

## 2. 项目结构

建议的目录结构：

```
model-registry-service/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口
│   ├── config.py                # 配置（数据库连接、Docker socket 路径等）
│   ├── database.py              # SQLAlchemy engine、session 管理
│   ├── models/                  # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── model_registry.py
│   │   ├── model_deploy_binding.py
│   │   ├── model_io_schema.py
│   │   └── model_operation_log.py
│   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── binding.py
│   │   ├── io_schema.py
│   │   └── common.py
│   ├── routers/                 # API 路由
│   │   ├── __init__.py
│   │   ├── registry.py          # /api/model-registry CRUD
│   │   ├── binding.py           # /api/model-registry/{id}/bind-*
│   │   ├── lifecycle.py         # /api/model-registry/{id}/start|stop|restart|rebuild
│   │   ├── logs.py              # /api/model-registry/{id}/logs
│   │   └── io_schema.py         # /api/model-registry/{id}/io-schema
│   ├── services/                # 业务逻辑
│   │   ├── __init__.py
│   │   ├── registry_service.py  # 模型 CRUD
│   │   ├── binding_service.py   # 绑定管理
│   │   ├── lifecycle_service.py # 容器生命周期（核心）
│   │   └── docker_service.py    # Docker SDK 封装
│   ├── tasks/                   # 后台定时任务
│   │   ├── __init__.py
│   │   └── status_sync.py       # 状态同步 + 健康检查心跳
│   └── utils/
│       ├── __init__.py
│       └── logger.py
├── alembic/                     # 数据库迁移
│   └── versions/
├── alembic.ini
├── requirements.txt
└── README.md
```

---

## 3. 实施任务清单

以下是按优先级排序的实施步骤，每一步完成后应可独立验证。

### 阶段一：基础框架搭建

#### 任务 1：初始化项目 + 依赖安装

创建 `requirements.txt`：
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pymysql>=1.1.0
alembic>=1.13.0
docker>=7.0.0
apscheduler>=3.10.0
sse-starlette>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
httpx>=0.27.0
```

创建 `app/config.py`：
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "model_registry"

    # Docker
    docker_host: str = "unix:///var/run/docker.sock"

    # 服务
    host: str = "0.0.0.0"
    port: int = 5001

    # 状态同步
    sync_interval_seconds: int = 30
    health_check_timeout_seconds: int = 120
    start_timeout_seconds: int = 60

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    class Config:
        env_file = ".env"
```

创建 `app/database.py`：
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import Settings

settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### 任务 2：创建 SQLAlchemy ORM 模型

创建 4 个 ORM 模型文件，对应 4 张表。每个模型的字段与上面 DDL 完全一致。

**关键点：**
- 使用 SQLAlchemy 2.0 的 `Mapped` 注解风格
- `model_registry` 的 `runtime_status` 用 Python Enum 约束
- `model_deploy_binding` 的 `extra_mounts` 和 `extra_env` 用 JSON 类型
- `model_deploy_binding` 的 `model_id` 设置外键 + 级联删除
- `create_time`/`update_time` 用 `server_default` 和 `onupdate`

#### 任务 3：创建 Pydantic 请求/响应模型

在 `app/schemas/` 下定义接口的输入输出模型：

**registry.py 示例：**
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RegistryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    framework: Optional[str] = None
    architecture: Optional[str] = None
    model_type: Optional[str] = None
    model_size: Optional[str] = None
    owner_id: Optional[int] = None

class RegistryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    framework: Optional[str] = None
    architecture: Optional[str] = None
    model_type: Optional[str] = None
    model_size: Optional[str] = None

class RegistryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    framework: Optional[str]
    architecture: Optional[str]
    model_type: Optional[str]
    model_size: Optional[str]
    runtime_status: str
    owner_id: Optional[int]
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True

class RegistryDetailResponse(RegistryResponse):
    binding: Optional["BindingResponse"] = None
    inference_url: Optional[str] = None
```

**binding.py 示例：**
```python
class BindContainerRequest(BaseModel):
    container_id: str = Field(..., min_length=1, max_length=64)
    host_port: int
    container_port: int
    inference_path: Optional[str] = None
    health_check_url: Optional[str] = None
    gpu_device: Optional[str] = None
    remark: Optional[str] = None

class BindImageRequest(BaseModel):
    image_name: str = Field(..., min_length=1, max_length=256)
    host_port: int
    container_port: int
    inference_path: Optional[str] = None
    health_check_url: Optional[str] = None
    gpu_device: Optional[str] = None
    extra_mounts: Optional[list[dict]] = None
    extra_env: Optional[dict] = None
    remark: Optional[str] = None

class BindBothRequest(BaseModel):
    container_id: str
    image_name: str
    host_port: int
    container_port: int
    inference_path: Optional[str] = None
    health_check_url: Optional[str] = None
    gpu_device: Optional[str] = None

class BindingUpdateRequest(BaseModel):
    host_port: Optional[int] = None
    container_port: Optional[int] = None
    inference_path: Optional[str] = None
    health_check_url: Optional[str] = None
    gpu_device: Optional[str] = None
    extra_mounts: Optional[list[dict]] = None
    extra_env: Optional[dict] = None
```

#### 任务 4：FastAPI 应用入口 + 启动脚本

`app/main.py`：
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base
from app.routers import registry, binding, lifecycle, logs, io_schema
from app.tasks.status_sync import start_sync_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：建表 + 启动定时任务
    Base.metadata.create_all(bind=engine)
    start_sync_task()
    yield
    # 关闭时：停止定时任务（如需要）

app = FastAPI(title="轻量级模型库", version="1.0.0", lifespan=lifespan)

app.include_router(registry.router, prefix="/api/model-registry", tags=["模型注册"])
app.include_router(binding.router, prefix="/api/model-registry/{model_id}", tags=["部署绑定"])
app.include_router(lifecycle.router, prefix="/api/model-registry/{model_id}", tags=["容器生命周期"])
app.include_router(logs.router, prefix="/api/model-registry/{model_id}", tags=["日志"])
app.include_router(io_schema.router, prefix="/api/model-registry/{model_id}", tags=["IO Schema"])
```

启动命令：`uvicorn app.main:app --host 0.0.0.0 --port 5001`

### 阶段二：Docker 服务封装

#### 任务 5：封装 Docker SDK 操作

创建 `app/services/docker_service.py`，这是整个系统的核心组件，封装所有 Docker 操作。

**需要实现的方法：**

```python
import docker
from docker.errors import NotFound, APIError

class DockerService:
    def __init__(self):
        # 连接本地 Docker daemon（默认 unix:///var/run/docker.sock）
        self.client = docker.from_env()

    def inspect_container(self, container_id: str) -> dict:
        """查询容器详情（状态、名称、镜像、启动时间等）"""
        container = self.client.containers.get(container_id)
        return {
            "id": container.id,
            "name": container.name,
            "status": container.status,       # running / exited / paused / ...
            "image": container.image.tags[0] if container.image.tags else str(container.image.id),
            "started_at": container.attrs["State"]["StartedAt"],
        }

    def start_container(self, container_id: str) -> None:
        """启动已有容器"""
        container = self.client.containers.get(container_id)
        container.start()

    def stop_container(self, container_id: str, timeout: int = 30) -> None:
        """停止容器（不删除）"""
        container = self.client.containers.get(container_id)
        container.stop(timeout=timeout)

    def create_and_start_container(
        self,
        image_name: str,
        container_name: str,
        host_port: int,
        container_port: int,
        gpu_device: str | None = None,
        extra_mounts: list[dict] | None = None,
        extra_env: dict | None = None,
    ) -> str:
        """创建并启动容器，返回容器 ID"""
        # 端口映射: {container_port/tcp: host_port}
        ports = {f"{container_port}/tcp": host_port}

        # 挂载卷: ["/host/path:/container/path", ...]
        volumes = {}
        if extra_mounts:
            for m in extra_mounts:
                volumes[m["host"]] = {"bind": m["container"], "mode": "rw"}

        # 环境变量
        environment = extra_env or {}

        # GPU 设备请求
        device_requests = None
        if gpu_device:
            device_requests = [
                docker.types.DeviceRequest(
                    device_ids=[gpu_device],
                    capabilities=[["gpu"]]
                )
            ]

        container = self.client.containers.run(
            image=image_name,
            name=container_name,
            detach=True,
            ports=ports,
            volumes=volumes,
            environment=environment,
            device_requests=device_requests,
        )
        return container.id

    def remove_container(self, container_id: str) -> None:
        """强制删除容器"""
        container = self.client.containers.get(container_id)
        container.remove(force=True)

    def get_container_logs(self, container_id: str, tail: int = 100, follow: bool = False, since: str | None = None):
        """获取容器日志，返回生成器（follow=True 时流式）"""
        container = self.client.containers.get(container_id)
        return container.logs(tail=tail, follow=follow, stream=follow, since=since, timestamps=True)

    def get_container_stats(self, container_id: str) -> dict:
        """获取容器资源使用快照"""
        container = self.client.containers.get(container_id)
        stats = container.stats(stream=False)

        # 解析 CPU
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        num_cpus = stats["cpu_stats"]["online_cpus"]
        cpu_percent = (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0

        # 解析内存
        mem_usage = stats["memory_stats"]["usage"]
        mem_limit = stats["memory_stats"]["limit"]
        mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage_bytes": mem_usage,
            "memory_limit_bytes": mem_limit,
            "memory_percent": round(mem_percent, 2),
        }

    def is_container_running(self, container_id: str) -> bool:
        """检查容器是否在运行"""
        try:
            info = self.inspect_container(container_id)
            return info["status"] == "running"
        except NotFound:
            return False
```

**关键注意事项：**
- `docker.from_env()` 默认连接 `unix:///var/run/docker.sock`
- `containers.run(image, detach=True)` 等价于 `docker run -d`
- `device_requests` 用于 GPU 分配，需要 NVIDIA Container Toolkit
- `container.logs(stream=True)` 返回生成器，用于 SSE 流式推送
- `container.stats(stream=False)` 获取单次快照（非持续流式）
- 所有方法需要捕获 `docker.errors.NotFound`（容器不存在）和 `docker.errors.APIError`（Docker daemon 错误）

### 阶段三：核心业务逻辑

#### 任务 6：模型注册服务

创建 `app/services/registry_service.py`：

```python
class RegistryService:
    def create_model(self, db, data: RegistryCreate) -> ModelRegistry:
        """注册模型：插入记录，runtime_status 默认 stopped"""

    def update_model(self, db, model_id: int, data: RegistryUpdate) -> ModelRegistry:
        """更新模型信息：仅更新非空字段"""

    def delete_model(self, db, model_id: int) -> None:
        """删除模型：
        1. 检查 runtime_status != running（running 禁止删除）
        2. 级联删除由外键约束自动处理
        3. 不删除 Docker 容器和镜像
        """

    def get_model(self, db, model_id: int) -> dict:
        """查询模型详情：
        1. 查 model_registry
        2. 关联查 model_deploy_binding
        3. 如果有绑定，通过 DockerService 查容器实时状态并同步 runtime_status
        4. 拼接 inference_url = http://{host_ip}:{host_port}{inference_path}
        """

    def list_models(self, db, keyword, runtime_status, framework, owner_id, page_num, page_size) -> dict:
        """分页查询：
        - keyword 模糊匹配 name / description / framework
        - 可按 runtime_status、framework、owner_id 筛选
        """
```

#### 任务 7：绑定管理服务

创建 `app/services/binding_service.py`：

```python
class BindingService:
    def bind_container(self, db, model_id: int, data: BindContainerRequest) -> ModelDeployBinding:
        """绑定已有容器：
        1. 校验模型存在
        2. 通过 DockerService.inspect_container 验证容器存在
        3. 自动填充 container_name、image_name
        4. 设置 bind_type = "container", host_ip = "127.0.0.1"
        5. 插入/更新 model_deploy_binding
        6. 同步容器实际状态到 runtime_status
        7. 记录操作日志
        """

    def bind_image(self, db, model_id: int, data: BindImageRequest) -> ModelDeployBinding:
        """绑定镜像：
        1. 设置 bind_type = "image"
        2. 不创建容器，等启动时再 docker run
        """

    def bind_both(self, db, model_id: int, data: BindBothRequest) -> ModelDeployBinding:
        """同时绑定容器和镜像"""

    def update_binding(self, db, model_id: int, data: BindingUpdateRequest) -> ModelDeployBinding:
        """更新绑定配置（部分更新）"""

    def unbind(self, db, model_id: int) -> None:
        """解绑：running 状态禁止解绑，不删除容器"""
```

#### 任务 8：容器生命周期服务（核心）

创建 `app/services/lifecycle_service.py`，这是最核心的服务：

```python
class LifecycleService:
    def __init__(self):
        self.docker = DockerService()

    def start_model(self, db, model_id: int) -> dict:
        """启动模型 — 按 bind_type 分支处理"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding:
            raise HTTPException(404, "模型未绑定部署配置")

        model = db.query(ModelRegistry).get(model_id)

        # 更新状态 → starting
        model.runtime_status = "starting"
        db.commit()

        try:
            if binding.bind_type in ("container", "both"):
                # 已有容器：docker start
                self.docker.start_container(binding.container_id)
                self._wait_container_running(binding.container_id)

            elif binding.bind_type == "image":
                # 仅有镜像：docker run 创建新容器
                container_name = f"model-{model_id}"
                container_id = self.docker.create_and_start_container(
                    image_name=binding.image_name,
                    container_name=container_name,
                    host_port=binding.host_port,
                    container_port=binding.container_port,
                    gpu_device=binding.gpu_device,
                    extra_mounts=binding.extra_mounts,
                    extra_env=binding.extra_env,
                )
                # 更新绑定记录：填入容器信息，bind_type 改为 both
                binding.container_id = container_id
                binding.container_name = container_name
                binding.bind_type = "both"
                db.commit()

            # 健康检查（如配置了 health_check_url）
            if binding.health_check_url:
                self._wait_healthy(binding)

            # 更新状态 → running
            model.runtime_status = "running"
            db.commit()
            self._log_operation(db, model_id, "start", "success")

            return {
                "modelId": model_id,
                "runtimeStatus": "running",
                "containerId": binding.container_id,
                "hostIp": binding.host_ip,
                "hostPort": binding.host_port,
                "inferenceUrl": f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path or ''}",
            }

        except Exception as e:
            model.runtime_status = "error"
            db.commit()
            self._log_operation(db, model_id, "start", "failed", str(e))
            raise HTTPException(500, f"启动失败: {e}")

    def stop_model(self, db, model_id: int, timeout: int = 30) -> dict:
        """停止模型"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        model = db.query(ModelRegistry).get(model_id)

        model.runtime_status = "stopping"
        db.commit()

        try:
            self.docker.stop_container(binding.container_id, timeout=timeout)
            model.runtime_status = "stopped"
            db.commit()
            self._log_operation(db, model_id, "stop", "success")
            return {"modelId": model_id, "runtimeStatus": "stopped"}
        except Exception as e:
            model.runtime_status = "error"
            db.commit()
            self._log_operation(db, model_id, "stop", "failed", str(e))
            raise

    def restart_model(self, db, model_id: int) -> dict:
        """重启模型"""
        self.stop_model(db, model_id)
        return self.start_model(db, model_id)

    def rebuild_container(self, db, model_id: int) -> dict:
        """重建容器"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding or binding.bind_type == "container":
            raise HTTPException(400, "需要绑定镜像才能重建")

        # 如果运行中先停止
        model = db.query(ModelRegistry).get(model_id)
        if model.runtime_status == "running":
            self.stop_model(db, model_id)

        # 删除旧容器
        if binding.container_id:
            self.docker.remove_container(binding.container_id)
            binding.container_id = None
            binding.container_name = None
            db.commit()

        # 重新启动（会创建新容器）
        return self.start_model(db, model_id)

    def _wait_container_running(self, container_id: str, timeout: int = 60):
        """轮询容器状态直到 Running"""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = self.docker.inspect_container(container_id)
            if info["status"] == "running":
                return
            time.sleep(2)
        raise TimeoutError(f"容器 {timeout}s 内未进入 Running 状态")

    def _wait_healthy(self, binding):
        """轮询健康检查端点"""
        import httpx, time
        url = f"http://{binding.host_ip}:{binding.host_port}{binding.health_check_url}"
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                resp = httpx.get(url, timeout=5)
                if resp.status_code < 400:
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError("健康检查超时")
```

#### 任务 9：日志和状态接口

创建 `app/routers/logs.py`：

```python
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

@router.get("/{model_id}/logs")
async def get_logs(model_id: int, tail: int = 100, follow: bool = False):
    """获取容器日志"""
    binding = get_binding_or_404(model_id)

    if follow:
        # SSE 流式推送
        log_generator = docker_service.get_container_logs(
            binding.container_id, tail=tail, follow=True
        )
        async def event_generator():
            for line in log_generator:
                yield {"data": line.decode("utf-8", errors="replace").strip()}
        return EventSourceResponse(event_generator())
    else:
        # 一次性返回
        logs = docker_service.get_container_logs(
            binding.container_id, tail=tail, follow=False
        )
        return {"logs": logs.decode("utf-8", errors="replace")}
```

状态查询接口在 `registry_service.get_model` 中已包含（查询详情时同步容器状态并返回资源信息）。

### 阶段四：后台任务

#### 任务 10：定时状态同步

创建 `app/tasks/status_sync.py`：

```python
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.services.docker_service import DockerService

docker_service = DockerService()
scheduler = BackgroundScheduler()

def sync_container_status():
    """每 30 秒执行一次，同步数据库状态与 Docker 实际状态"""
    db = SessionLocal()
    try:
        # 查询所有有绑定的模型
        models = db.query(ModelRegistry).join(ModelDeployBinding).all()

        for model in models:
            binding = model.binding  # 1:1 关系
            if not binding or not binding.container_id:
                continue

            try:
                info = docker_service.inspect_container(binding.container_id)
                actual_running = info["status"] == "running"
            except Exception:
                # 容器不存在
                actual_running = None

            changed = False

            if model.runtime_status == "running" and not actual_running:
                # 数据库说运行中，但容器已停/不存在
                if actual_running is None:
                    model.runtime_status = "stopped"
                    binding.container_id = None
                    binding.container_name = None
                else:
                    model.runtime_status = "error"
                changed = True

            elif model.runtime_status == "stopped" and actual_running:
                # 数据库说停止，但容器在运行（外部手动启动）
                model.runtime_status = "running"
                changed = True

            elif model.runtime_status in ("starting", "stopping"):
                # 检查是否超时（starting 超 2 分钟，stopping 超 1 分钟）
                # 需要在 model 上增加 status_changed_at 字段或用 update_time 判断
                pass

            if changed:
                db.commit()

    finally:
        db.close()

def start_sync_task():
    scheduler.add_job(sync_container_status, "interval", seconds=30, id="status_sync")
    scheduler.start()
```

### 阶段五：接口完善

#### 任务 11：实现所有路由

按照第 4 节的接口定义，实现所有路由文件。每个路由文件调用对应的 service 方法。

路由文件列表：
- `app/routers/registry.py` — 模型 CRUD + 列表查询
- `app/routers/binding.py` — bind-container / bind-image / bind-both / update / unbind
- `app/routers/lifecycle.py` — start / stop / restart / rebuild / status
- `app/routers/logs.py` — 日志查看
- `app/routers/io_schema.py` — IO Schema CRUD

#### 任务 12：操作日志记录

在 `registry_service` 和 `lifecycle_service` 的关键操作中调用：

```python
def _log_operation(db, model_id: int, operation: str, result: str, error_msg: str = None, detail: dict = None):
    log = ModelOperationLog(
        model_id=model_id,
        operation=operation,
        detail=detail,
        result=result,
        error_msg=error_msg,
    )
    db.add(log)
    db.commit()
```

需要记录的操作：start、stop、restart、rebuild、bind_container、bind_image、bind_both、unbind、delete

### 阶段六：验证与测试

#### 任务 13：启动服务并验证

```bash
# 1. 创建数据库
mysql -u root -e "CREATE DATABASE IF NOT EXISTS model_registry DEFAULT CHARSET utf8mb4;"

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 5001

# 4. 访问 API 文档
# http://localhost:5001/docs
```

**验证清单：**

| 序号 | 操作 | 预期结果 |
|------|------|----------|
| 1 | POST /api/model-registry 注册模型 | 返回模型 ID，runtime_status=stopped |
| 2 | POST /{id}/bind-container 绑定已有容器 | 自动填充 container_name/image_name |
| 3 | POST /{id}/start 启动 | runtime_status 变为 running |
| 4 | GET /{id}/status 查状态 | 返回 running + 资源信息 |
| 5 | GET /{id}/logs?tail=50 查日志 | 返回容器日志 |
| 6 | POST /{id}/stop 停止 | runtime_status 变为 stopped，容器仍在 |
| 7 | POST /{id}/start 再次启动 | 容器直接 start，无需重新创建 |
| 8 | POST /{id}/bind-image 绑定镜像 | bind_type=image |
| 9 | POST /{id}/start 启动镜像 | 自动 docker run，bind_type 变为 both |
| 10 | POST /{id}/rebuild 重建 | 删除旧容器，创建新容器 |
| 11 | DELETE /{id} 删除模型 | running 状态禁止删除 |
| 12 | 手动 docker stop 容器 | 30s 内数据库自动同步为 stopped |

---

## 4. 接口完整定义

### 4.1 模型注册 CRUD

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/model-registry` | 注册模型 | `{name, description?, framework?, architecture?, modelType?, modelSize?, ownerId?}` |
| PUT | `/api/model-registry/{id}` | 更新模型 | `{name?, description?, framework?, ...}` 部分更新 |
| DELETE | `/api/model-registry/{id}` | 删除模型 | 无（running 禁删） |
| GET | `/api/model-registry/{id}` | 查询详情 | 无（含绑定信息 + inferenceUrl） |
| GET | `/api/model-registry` | 分页列表 | Query: `pageNum, pageSize, keyword?, runtimeStatus?, framework?, ownerId?` |

### 4.2 部署绑定

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/model-registry/{id}/bind-container` | 绑定已有容器 | `{containerId, hostPort, containerPort, inferencePath?, healthCheckUrl?, gpuDevice?, remark?}` |
| POST | `/api/model-registry/{id}/bind-image` | 绑定镜像 | `{imageName, hostPort, containerPort, inferencePath?, healthCheckUrl?, gpuDevice?, extraMounts?, extraEnv?, remark?}` |
| POST | `/api/model-registry/{id}/bind-both` | 绑定容器+镜像 | `{containerId, imageName, hostPort, containerPort, inferencePath?, gpuDevice?}` |
| PUT | `/api/model-registry/{id}/binding` | 更新绑定配置 | 部分更新 |
| DELETE | `/api/model-registry/{id}/binding` | 解绑 | 无（running 禁解绑） |

### 4.3 容器生命周期

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/model-registry/{id}/start` | 启动模型 | 无 |
| POST | `/api/model-registry/{id}/stop` | 停止模型 | `{timeout?}` 默认 30s |
| POST | `/api/model-registry/{id}/restart` | 重启模型 | 无 |
| POST | `/api/model-registry/{id}/rebuild` | 重建容器 | 无（需有镜像绑定） |
| GET | `/api/model-registry/{id}/status` | 实时状态 | 无（含资源监控） |

### 4.4 日志

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/model-registry/{id}/logs` | 容器日志 | Query: `tail?` 默认 100, `follow?` 默认 false |

follow=true 时返回 SSE 流。

### 4.5 IO Schema（可选）

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/model-registry/{id}/io-schema` | 设置 | `{inputs: [...], outputs: [...]}` |
| GET | `/api/model-registry/{id}/io-schema` | 获取 | 无 |
| PUT | `/api/model-registry/{id}/io-schema` | 更新 | `{inputs?, outputs?}` |

### 4.6 批量操作

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/model-registry/batch/start` | 批量启动 | `{modelIds: [1,2,3]}` |
| POST | `/api/model-registry/batch/stop` | 批量停止 | `{modelIds: [1,2,3]}` |

### 4.7 响应格式

统一响应格式：
```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

错误响应：
```json
{
  "code": 400,
  "message": "错误描述",
  "data": null
}
```

---

## 5. 健康检查机制

### 5.1 启动后健康检查

在 `start_model` 流程中，容器进入 Running 后，如果 `health_check_url` 不为空：

```
轮询 GET http://{host_ip}:{host_port}{health_check_url}
间隔：2 秒
超时：120 秒（可通过配置调整）
成功条件：HTTP 状态码 < 400
超时处理：更新 runtime_status = error，抛出异常
```

### 5.2 运行中心跳

在定时状态同步任务中，对 `running` 状态的模型：
- 如果 `health_check_url` 不为空：HTTP GET 检查
- 如果 `health_check_url` 为空：仅检查容器状态（inspect）

心跳失败连续 3 次后更新为 `error`（需要在绑定表或新增字段记录连续失败次数）。

---

## 6. 注意事项与常见坑

### 6.1 Docker SDK 相关

- `docker.from_env()` 读取 `DOCKER_HOST` 环境变量，默认 `unix:///var/run/docker.sock`
- 如果进程没有 docker 组权限，会报 `PermissionError`，解决：`sudo usermod -aG docker $USER` 然后重新登录
- `container.stats(stream=False)` 首次调用可能返回空数据（需要容器至少运行几秒）
- `container.logs()` 返回 `bytes`，需要 `.decode("utf-8")`
- GPU 支持：`device_requests` 参数需要 Docker 19.03+ 和 NVIDIA Container Toolkit

### 6.2 数据库相关

- `runtime_status` 的状态变更需要原子操作，避免并发问题（可以用 `SELECT ... FOR UPDATE`）
- `model_deploy_binding` 的 `model_id` 是 UNIQUE 的（一个模型只能有一个绑定）
- 级联删除：删除 `model_registry` 时会自动删除关联的 binding、schema、log

### 6.3 定时任务相关

- APScheduler 默认在主线程运行，FastAPI 用 lifespan 管理启停
- 状态同步需要避免与接口操作并发冲突（比如接口正在 start，同步任务同时检查状态）
- 建议在同步任务中加锁或用乐观锁（检查 update_time 是否在最近 5 秒内变更）

### 6.4 SSE 流式日志

- `sse-starlette` 需要 `pip install sse-starlette`
- 客户端断开连接时需要正确关闭 Docker 日志流，避免资源泄漏
- 日志流中可能包含非 UTF-8 字节，需要 `errors="replace"`
