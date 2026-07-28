# Docker 测试接口

## 接口说明

Docker 容器查询测试接口，用于调试和监控。这些接口直接查询 Docker daemon，不依赖模型注册数据。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/docker/containers` | 列出容器 |
| GET | `/api/docker/containers/{container_id}` | 查询容器详情 |
| GET | `/api/docker/containers/{container_id}/logs` | 获取容器日志 |
| GET | `/api/docker/containers/{container_id}/stats` | 获取容器资源使用 |

---

## 1. 列出容器

### 接口说明

列出 Docker 容器。

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/docker/containers`
- **认证要求**: 无

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| all | bool | 否 | false | 是否包含已停止的容器 |

### 调用示例

#### curl
```bash
# 仅运行中的容器
curl http://localhost:5001/api/docker/containers

# 所有容器
curl "http://localhost:5001/api/docker/containers?all=true"
```

#### Python
```python
import requests

# 仅运行中的容器
response = requests.get("http://localhost:5001/api/docker/containers")
print(response.json())

# 所有容器
response = requests.get("http://localhost:5001/api/docker/containers", params={"all": True})
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "abc123def456",
      "name": "dam-qwen2-7b-1",
      "status": "running",
      "image": "vllm/vllm-openai:latest",
      "created": "2026-07-13T10:00:00"
    },
    {
      "id": "def789ghi012",
      "name": "dam-llama3-8b-2",
      "status": "exited",
      "image": "vllm/vllm-openai:latest",
      "created": "2026-07-13T09:00:00"
    }
  ]
}
```

---

## 2. 查询容器详情

### 接口说明

查询指定容器的详细信息。

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/docker/containers/{container_id}`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id | string | 是 | 容器 ID 或名称 |

### 调用示例

#### curl
```bash
# 使用容器 ID
curl http://localhost:5001/api/docker/containers/abc123def456

# 使用容器名称
curl http://localhost:5001/api/docker/containers/dam-qwen2-7b-1
```

#### Python
```python
import requests

response = requests.get("http://localhost:5001/api/docker/containers/dam-qwen2-7b-1")
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "abc123def456789...",
    "name": "dam-qwen2-7b-1",
    "status": "running",
    "image": "vllm/vllm-openai:latest",
    "started_at": "2026-07-13T10:00:05",
    "created_at": "2026-07-13T10:00:00"
  }
}
```

### 错误响应

```json
{
  "code": 404,
  "message": "容器不存在",
  "data": null
}
```

---

## 3. 获取容器日志

### 接口说明

获取指定容器的日志。

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/docker/containers/{container_id}/logs`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id | string | 是 | 容器 ID 或名称 |

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| tail | int | 否 | 100 | 返回的日志行数 |

### 调用示例

#### curl
```bash
# 获取最近 100 行
curl http://localhost:5001/api/docker/containers/dam-qwen2-7b-1/logs

# 获取最近 50 行
curl "http://localhost:5001/api/docker/containers/dam-qwen2-7b-1/logs?tail=50"
```

#### Python
```python
import requests

response = requests.get(
    "http://localhost:5001/api/docker/containers/dam-qwen2-7b-1/logs",
    params={"tail": 50}
)
print(response.json()["data"]["logs"])
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "logs": "INFO:     Started server process [1]\nINFO:     Waiting for application startup.\nINFO:     Application startup complete.\nINFO:     Uvicorn running on http://0.0.0.0:8000"
  }
}
```

---

## 4. 获取容器资源使用

### 接口说明

获取指定容器的实时资源使用情况。

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/docker/containers/{container_id}/stats`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| container_id | string | 是 | 容器 ID 或名称 |

### 调用示例

#### curl
```bash
curl http://localhost:5001/api/docker/containers/dam-qwen2-7b-1/stats
```

#### Python
```python
import requests

response = requests.get("http://localhost:5001/api/docker/containers/dam-qwen2-7b-1/stats")
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "cpu_percent": 12.5,
    "memory_usage_bytes": 1073741824,
    "memory_limit_bytes": 8589934592,
    "memory_percent": 12.5
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| cpu_percent | float | CPU 使用率（%） |
| memory_usage_bytes | int | 内存使用量（字节） |
| memory_limit_bytes | int | 内存限制（字节） |
| memory_percent | float | 内存使用率（%） |

### 内存单位换算

| 单位 | 换算 |
|------|------|
| 1 GB | 1073741824 字节 (1024^3) |
| 1 MB | 1048576 字节 (1024^2) |
| 1 KB | 1024 字节 |

### 错误响应

```json
{
  "code": 404,
  "message": "容器不存在",
  "data": null
}
```
