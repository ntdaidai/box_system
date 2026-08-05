# 部署绑定接口

## 接口说明

管理模型与 Docker 容器/镜像的绑定关系。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/model-registry/{model_id}/bind-container` | 绑定已有容器 |
| POST | `/api/model-registry/{model_id}/bind-image` | 绑定镜像 |
| POST | `/api/model-registry/{model_id}/bind-both` | 同时绑定容器和镜像 |
| PUT | `/api/model-registry/{model_id}/binding` | 更新绑定配置 |
| DELETE | `/api/model-registry/{model_id}/binding` | 解绑 |

---

## 1. 绑定已有容器

### 接口说明

将一个已存在的 Docker 容器绑定到模型。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/bind-container`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id | string | 是 | 容器 ID 或名称 |
| container_port | int | 否 | 容器内部端口，默认 8000 |
| host_port | int | 否 | 宿主机端口，默认自动分配 |
| inference_path | string | 否 | 推理路径，默认 `/infer` |
| health_check_url | string | 否 | 健康检查路径，默认 `/health` |
| container_config | object | 否 | Docker 容器运行时配置 |
| remark | string | 否 | 备注 |

### container_config 结构

```json
{
  "runtime": "nvidia",
  "gpus": "all",
  "ipc_mode": "host",
  "shm_size": "16g",
  "network_mode": "host",
  "cap_add": ["SYS_PTRACE"],
  "devices": ["/dev/fuse"],
  "privileged": false,
  "ulimits": [{"name": "nofile", "soft": 65536, "hard": 65536}],
  "labels": {"app": "model"},
  "restart_policy": {"Name": "unless-stopped"}
}
```

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/bind-container \
  -H "Content-Type: application/json" \
  -d '{
    "container_id": "my-vllm-container",
    "container_port": 8000,
    "host_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "remark": "绑定已有 vLLM 容器"
  }'
```

#### Python
```python
import requests

data = {
    "container_id": "my-vllm-container",
    "container_port": 8000,
    "host_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "remark": "绑定已有 vLLM 容器"
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/bind-container",
    json=data
)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "model_id": 1,
    "bind_type": "container",
    "container_id": "abc123def456",
    "container_name": "my-vllm-container",
    "image_name": null,
    "host_ip": "127.0.0.1",
    "host_port": 8000,
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "remark": "绑定已有 vLLM 容器",
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

---

## 2. 绑定镜像

### 接口说明

绑定一个 Docker 镜像到模型（不创建容器，启动时自动创建）。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/bind-image`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image_name | string | 是 | 镜像全名（如 `vllm/vllm-openai:latest`） |
| container_port | int | 否 | 容器内部端口，默认 8000 |
| host_port | int | 否 | 宿主机端口，默认自动分配 |
| inference_path | string | 否 | 推理路径，默认 `/infer` |
| health_check_url | string | 否 | 健康检查路径，默认 `/health` |
| extra_mounts | array | 否 | 挂载卷列表 |
| extra_env | object | 否 | 环境变量 |
| container_config | object | 否 | Docker 容器运行时配置 |
| remark | string | 否 | 备注 |

### extra_mounts 结构

```json
[
  {"host": "/data/models", "container": "/models"},
  {"host": "/data/cache", "container": "/root/.cache"}
]
```

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/bind-image \
  -H "Content-Type: application/json" \
  -d '{
    "image_name": "vllm/vllm-openai:latest",
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "extra_mounts": [
      {"host": "/data/models", "container": "/models"}
    ],
    "extra_env": {
      "MODEL_NAME": "Qwen/Qwen2-7B",
      "GPU_MEMORY_UTILIZATION": "0.9"
    },
    "container_config": {
      "runtime": "nvidia",
      "gpus": "all",
      "shm_size": "16g"
    },
    "remark": "vLLM 推理镜像"
  }'
```

#### Python
```python
import requests

data = {
    "image_name": "vllm/vllm-openai:latest",
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "extra_mounts": [
        {"host": "/data/models", "container": "/models"}
    ],
    "extra_env": {
        "MODEL_NAME": "Qwen/Qwen2-7B",
        "GPU_MEMORY_UTILIZATION": "0.9"
    },
    "container_config": {
        "runtime": "nvidia",
        "gpus": "all",
        "shm_size": "16g"
    },
    "remark": "vLLM 推理镜像"
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/bind-image",
    json=data
)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "model_id": 1,
    "bind_type": "image",
    "container_id": null,
    "container_name": null,
    "image_name": "vllm/vllm-openai:latest",
    "host_ip": "127.0.0.1",
    "host_port": null,
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "extra_mounts": [{"host": "/data/models", "container": "/models"}],
    "extra_env": {"MODEL_NAME": "Qwen/Qwen2-7B"},
    "remark": "vLLM 推理镜像",
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

---

## 3. 同时绑定容器和镜像

### 接口说明

同时绑定一个容器和镜像到模型，用于记录容器来源镜像。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/bind-both`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id | string | 是 | 容器 ID 或名称 |
| image_name | string | 是 | 镜像全名 |
| container_port | int | 否 | 容器内部端口，默认 8000 |
| host_port | int | 否 | 宿主机端口，默认自动分配 |
| inference_path | string | 否 | 推理路径 |
| health_check_url | string | 否 | 健康检查路径 |
| container_config | object | 否 | Docker 容器运行时配置 |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/bind-both \
  -H "Content-Type: application/json" \
  -d '{
    "container_id": "my-vllm-container",
    "image_name": "vllm/vllm-openai:latest",
    "container_port": 8000,
    "host_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health"
  }'
```

#### Python
```python
import requests

data = {
    "container_id": "my-vllm-container",
    "image_name": "vllm/vllm-openai:latest",
    "container_port": 8000,
    "host_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health"
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/bind-both",
    json=data
)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "model_id": 1,
    "bind_type": "both",
    "container_id": "abc123def456",
    "container_name": "my-vllm-container",
    "image_name": "vllm/vllm-openai:latest",
    "host_ip": "127.0.0.1",
    "host_port": 8000,
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

---

## 4. 更新绑定配置

### 接口说明

更新已有的绑定配置，所有字段可选。

### 接口信息

- **请求方法**: `PUT`
- **请求路径**: `/api/model-registry/{model_id}/binding`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

所有字段可选。

| 参数 | 类型 | 说明 |
|------|------|------|
| container_port | int | 容器内部端口 |
| host_port | int | 宿主机端口 |
| inference_path | string | 推理路径 |
| health_check_url | string | 健康检查路径 |
| extra_mounts | array | 挂载卷列表 |
| extra_env | object | 环境变量 |
| container_config | object | Docker 容器运行时配置 |
| remark | string | 备注 |

### 调用示例

#### curl
```bash
curl -X PUT http://localhost:5001/api/model-registry/1/binding \
  -H "Content-Type: application/json" \
  -d '{
    "host_port": 8001,
    "remark": "更新端口"
  }'
```

#### Python
```python
import requests

data = {
    "host_port": 8001,
    "remark": "更新端口"
}

response = requests.put(
    "http://localhost:5001/api/model-registry/1/binding",
    json=data
)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "model_id": 1,
    "bind_type": "both",
    "container_id": "abc123def456",
    "container_name": "my-vllm-container",
    "image_name": "vllm/vllm-openai:latest",
    "host_ip": "127.0.0.1",
    "host_port": 8001,
    "container_port": 8000,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "remark": "更新端口",
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:05:00"
  }
}
```

---

## 5. 解绑

### 接口说明

解除模型与容器/镜像的绑定关系。

### 接口信息

- **请求方法**: `DELETE`
- **请求路径**: `/api/model-registry/{model_id}/binding`
- **认证要求**: 无
- **限制**: 运行中（running）的模型禁止解绑

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X DELETE http://localhost:5001/api/model-registry/1/binding
```

#### Python
```python
import requests

response = requests.delete("http://localhost:5001/api/model-registry/1/binding")
print(response.json())
```

### 响应示例

#### 成功
```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

#### 运行中禁止解绑
```json
{
  "code": 409,
  "message": "运行中的模型禁止解绑，请先停止模型",
  "data": null
}
```
