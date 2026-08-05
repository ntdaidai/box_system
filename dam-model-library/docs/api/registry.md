# 模型注册接口

## 接口说明

模型注册的增删改查及批量操作接口。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/model-registry` | 注册模型 |
| PUT | `/api/model-registry/{model_id}` | 更新模型 |
| DELETE | `/api/model-registry/{model_id}` | 删除模型 |
| GET | `/api/model-registry/{model_id}` | 查询模型详情 |
| GET | `/api/model-registry` | 分页查询模型列表 |
| POST | `/api/model-registry/batch/start` | 批量启动模型 |
| POST | `/api/model-registry/batch/stop` | 批量停止模型 |

---

## 1. 注册模型

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry`
- **认证要求**: 无

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 模型名称，1-128 字符 |
| description | string | 否 | 模型描述，最大 512 字符 |
| framework | string | 否 | 推理框架（如 vLLM、TensorRT） |
| architecture | string | 否 | 模型架构 |
| model_type | string | 否 | 模型类型 |
| model_size | string | 否 | 模型大小 |
| owner_id | int | 否 | 归属用户 ID |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Qwen2-7B",
    "description": "通义千问2代7B模型",
    "framework": "vLLM",
    "architecture": "Qwen2",
    "model_type": "chat",
    "model_size": "7B",
    "owner_id": 1
  }'
```

#### Python
```python
import requests

data = {
    "name": "Qwen2-7B",
    "description": "通义千问2代7B模型",
    "framework": "vLLM",
    "architecture": "Qwen2",
    "model_type": "chat",
    "model_size": "7B",
    "owner_id": 1
}

response = requests.post("http://localhost:5001/api/model-registry", json=data)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Qwen2-7B",
    "description": "通义千问2代7B模型",
    "framework": "vLLM",
    "architecture": "Qwen2",
    "model_type": "chat",
    "model_size": "7B",
    "runtime_status": "stopped",
    "owner_id": 1,
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

---

## 2. 更新模型

### 接口信息

- **请求方法**: `PUT`
- **请求路径**: `/api/model-registry/{model_id}`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

所有字段可选，仅更新传入的字段。

| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 模型名称 |
| description | string | 模型描述 |
| framework | string | 推理框架 |
| architecture | string | 模型架构 |
| model_type | string | 模型类型 |
| model_size | string | 模型大小 |
| owner_id | int | 归属用户 ID |

### 调用示例

#### curl
```bash
curl -X PUT http://localhost:5001/api/model-registry/1 \
  -H "Content-Type: application/json" \
  -d '{
    "description": "更新后的描述",
    "model_size": "14B"
  }'
```

#### Python
```python
import requests

data = {
    "description": "更新后的描述",
    "model_size": "14B"
}

response = requests.put("http://localhost:5001/api/model-registry/1", json=data)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Qwen2-7B",
    "description": "更新后的描述",
    "framework": "vLLM",
    "architecture": "Qwen2",
    "model_type": "chat",
    "model_size": "14B",
    "runtime_status": "stopped",
    "owner_id": 1,
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:05:00"
  }
}
```

---

## 3. 删除模型

### 接口信息

- **请求方法**: `DELETE`
- **请求路径**: `/api/model-registry/{model_id}`
- **认证要求**: 无
- **限制**: 运行中（running）的模型禁止删除

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X DELETE http://localhost:5001/api/model-registry/1
```

#### Python
```python
import requests

response = requests.delete("http://localhost:5001/api/model-registry/1")
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

#### 运行中禁止删除
```json
{
  "code": 409,
  "message": "运行中的模型禁止删除，请先停止模型",
  "data": null
}
```

---

## 4. 查询模型详情

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/model-registry/{model_id}`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl http://localhost:5001/api/model-registry/1
```

#### Python
```python
import requests

response = requests.get("http://localhost:5001/api/model-registry/1")
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "name": "Qwen2-7B",
    "description": "通义千问2代7B模型",
    "framework": "vLLM",
    "architecture": "Qwen2",
    "model_type": "chat",
    "model_size": "7B",
    "runtime_status": "running",
    "owner_id": 1,
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:05:00",
    "binding": {
      "bind_type": "both",
      "container_id": "abc123def456",
      "container_name": "dam-qwen2-7b-1",
      "image_name": "vllm/vllm-openai:latest",
      "host_ip": "127.0.0.1",
      "host_port": 8000,
      "container_port": 8000,
      "inference_path": "/infer",
      "health_check_url": "/health"
    },
    "inference_url": "http://127.0.0.1:8000/infer"
  }
}
```

---

## 5. 分页查询模型列表

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/model-registry`
- **认证要求**: 无

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| keyword | string | 否 | 无 | 搜索关键词（模糊匹配 name/description/framework） |
| runtime_status | string | 否 | 无 | 运行状态过滤: stopped/starting/running/stopping/error |
| framework | string | 否 | 无 | 推理框架过滤 |
| owner_id | int | 否 | 无 | 归属用户 ID 过滤 |
| page_num | int | 否 | 1 | 页码 |
| page_size | int | 否 | 10 | 每页数量 |

### 调用示例

#### curl
```bash
# 查询所有模型
curl "http://localhost:5001/api/model-registry"

# 带分页和过滤
curl "http://localhost:5001/api/model-registry?page_num=1&page_size=5&framework=vLLM&runtime_status=running"

# 关键词搜索
curl "http://localhost:5001/api/model-registry?keyword=Qwen"
```

#### Python
```python
import requests

params = {
    "keyword": "Qwen",
    "framework": "vLLM",
    "page_num": 1,
    "page_size": 5
}

response = requests.get("http://localhost:5001/api/model-registry", params=params)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "Qwen2-7B",
      "description": "通义千问2代7B模型",
      "framework": "vLLM",
      "runtime_status": "running",
      "owner_id": 1,
      "create_time": "2026-07-13T10:00:00",
      "update_time": "2026-07-13T10:05:00"
    },
    {
      "id": 2,
      "name": "Qwen2-14B",
      "description": "通义千问2代14B模型",
      "framework": "vLLM",
      "runtime_status": "stopped",
      "owner_id": 1,
      "create_time": "2026-07-13T11:00:00",
      "update_time": "2026-07-13T11:00:00"
    }
  ],
  "total": 2,
  "page_num": 1,
  "page_size": 5
}
```

---

## 6. 批量启动模型

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/batch/start`
- **认证要求**: 无

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_ids | array[int] | 是 | 模型 ID 列表 |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/batch/start \
  -H "Content-Type: application/json" \
  -d '{"model_ids": [1, 2, 3]}'
```

#### Python
```python
import requests

data = {"model_ids": [1, 2, 3]}
response = requests.post("http://localhost:5001/api/model-registry/batch/start", json=data)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {"model_id": 1, "status": "success", "message": "启动成功"},
    {"model_id": 2, "status": "success", "message": "启动成功"},
    {"model_id": 3, "status": "failed", "message": "未找到部署绑定"}
  ]
}
```

---

## 7. 批量停止模型

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/batch/stop`
- **认证要求**: 无

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_ids | array[int] | 是 | 模型 ID 列表 |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/batch/stop \
  -H "Content-Type: application/json" \
  -d '{"model_ids": [1, 2, 3]}'
```

#### Python
```python
import requests

data = {"model_ids": [1, 2, 3]}
response = requests.post("http://localhost:5001/api/model-registry/batch/stop", json=data)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {"model_id": 1, "status": "success", "message": "停止成功"},
    {"model_id": 2, "status": "success", "message": "停止成功"},
    {"model_id": 3, "status": "failed", "message": "模型未运行"}
  ]
}
```
