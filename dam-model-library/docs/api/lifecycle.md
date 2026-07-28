# 容器生命周期接口

## 接口说明

管理模型容器的启动、停止、重启、重建等生命周期操作。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/model-registry/{model_id}/start` | 启动模型 |
| POST | `/api/model-registry/{model_id}/stop` | 停止模型 |
| POST | `/api/model-registry/{model_id}/restart` | 重启模型 |
| POST | `/api/model-registry/{model_id}/rebuild` | 重建容器 |
| GET | `/api/model-registry/{model_id}/status` | 查询实时状态 |

---

## 1. 启动模型

### 接口说明

启动模型容器。根据绑定类型执行不同操作：
- `container` / `both`: 直接启动已有容器
- `image`: 自动创建并启动新容器

启动后如有健康检查地址，会自动轮询等待服务就绪（超时 120 秒）。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/start`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/start
```

#### Python
```python
import requests

response = requests.post("http://localhost:5001/api/model-registry/1/start")
print(response.json())
```

### 响应示例

#### 成功
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "running",
    "message": "模型启动成功"
  }
}
```

#### 启动失败
```json
{
  "code": 500,
  "message": "启动失败: 容器创建失败 - 镜像不存在",
  "data": null
}
```

#### 无绑定信息
```json
{
  "code": 400,
  "message": "模型未绑定容器或镜像",
  "data": null
}
```

---

## 2. 停止模型

### 接口说明

停止运行中的模型容器（不删除容器）。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/stop`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| timeout | int | 否 | 30 | 停止超时时间（秒） |

### 调用示例

#### curl
```bash
# 默认超时
curl -X POST http://localhost:5001/api/model-registry/1/stop

# 自定义超时
curl -X POST "http://localhost:5001/api/model-registry/1/stop?timeout=60"
```

#### Python
```python
import requests

# 默认超时
response = requests.post("http://localhost:5001/api/model-registry/1/stop")

# 自定义超时
response = requests.post(
    "http://localhost:5001/api/model-registry/1/stop",
    params={"timeout": 60}
)
print(response.json())
```

### 响应示例

#### 成功
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "stopped",
    "message": "模型停止成功"
  }
}
```

#### 未运行
```json
{
  "code": 400,
  "message": "模型未在运行中",
  "data": null
}
```

---

## 3. 重启模型

### 接口说明

重启模型容器（先停止再启动）。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/restart`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/restart
```

#### Python
```python
import requests

response = requests.post("http://localhost:5001/api/model-registry/1/restart")
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "running",
    "message": "模型重启成功"
  }
}
```

---

## 4. 重建容器

### 接口说明

删除旧容器并重新创建。需要模型已绑定镜像（bind_type 为 `image` 或 `both`）。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/rebuild`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/rebuild
```

#### Python
```python
import requests

response = requests.post("http://localhost:5001/api/model-registry/1/rebuild")
print(response.json())
```

### 响应示例

#### 成功
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "running",
    "message": "容器重建成功"
  }
}
```

#### 无镜像绑定
```json
{
  "code": 400,
  "message": "模型未绑定镜像，无法重建容器",
  "data": null
}
```

---

## 5. 查询实时状态

### 接口说明

查询模型的实时运行状态和资源使用情况。

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/model-registry/{model_id}/status`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl http://localhost:5001/api/model-registry/1/status
```

#### Python
```python
import requests

response = requests.get("http://localhost:5001/api/model-registry/1/status")
print(response.json())
```

### 响应示例

#### 运行中
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "running",
    "container_status": "running",
    "resources": {
      "cpu_percent": 12.5,
      "memory_usage_bytes": 1073741824,
      "memory_limit_bytes": 8589934592,
      "memory_percent": 12.5
    },
    "inference_url": "http://127.0.0.1:8000/v1/chat/completions"
  }
}
```

#### 已停止
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "stopped",
    "container_status": "exited",
    "resources": null,
    "inference_url": null
  }
}
```

#### 无绑定
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "model_id": 1,
    "runtime_status": "stopped",
    "container_status": null,
    "resources": null,
    "inference_url": null
  }
}
```
