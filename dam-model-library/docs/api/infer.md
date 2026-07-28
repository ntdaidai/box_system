# 模型推理接口

## 接口说明

模型推理接口，支持直接推理和一次性运行两种模式。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/model-registry/{model_id}/infer` | 直接推理 |
| POST | `/api/model-registry/{model_id}/run` | 一次性运行 |

---

## 1. 直接推理

### 接口说明

直接向运行中的模型发送推理请求。模型必须处于 `running` 状态。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/infer`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| validate | bool | 否 | false | 是否基于 IO Schema 校验输入 |
| filter_output | bool | 否 | false | 是否基于 IO Schema 过滤输出 |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| request_data | object | 是 | 推理请求数据，结构取决于模型类型 |

### request_data 示例

#### Chat 模型（如 vLLM）
```json
{
  "model": "Qwen/Qwen2-7B",
  "messages": [
    {"role": "user", "content": "你好，请介绍一下自己"}
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

#### 视觉模型
```json
{
  "model": "Qwen/Qwen2-VL-7B",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "data:image;base64,..."}},
        {"type": "text", "text": "描述这张图片"}
      ]
    }
  ]
}
```

#### 自定义模型
```json
{
  "image": "base64编码的图片",
  "confidence": 0.5
}
```

### 调用示例

#### curl
```bash
# Chat 模型推理
curl -X POST http://localhost:5001/api/model-registry/1/infer \
  -H "Content-Type: application/json" \
  -d '{
    "request_data": {
      "model": "Qwen/Qwen2-7B",
      "messages": [
        {"role": "user", "content": "你好，请介绍一下自己"}
      ],
      "temperature": 0.7,
      "max_tokens": 1024
    }
  }'

# 带 Schema 校验
curl -X POST "http://localhost:5001/api/model-registry/1/infer?validate=true&filter_output=true" \
  -H "Content-Type: application/json" \
  -d '{
    "request_data": {
      "image": "base64编码的图片",
      "confidence": 0.5
    }
  }'
```

#### Python
```python
import requests

data = {
    "request_data": {
        "model": "Qwen/Qwen2-7B",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下自己"}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/infer",
    json=data
)
print(response.json())
```

### 响应示例

#### Chat 模型响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1720857600,
    "model": "Qwen/Qwen2-7B",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "你好！我是Qwen2-7B，一个由阿里云开发的大语言模型..."
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 50,
      "total_tokens": 60
    }
  }
}
```

#### 自定义模型响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "detections": [
      {"class": "cat", "confidence": 0.95, "bbox": [100, 200, 300, 400]},
      {"class": "dog", "confidence": 0.87, "bbox": [400, 200, 600, 400]}
    ]
  }
}
```

#### 模型未运行
```json
{
  "code": 400,
  "message": "模型未在运行中，当前状态: stopped",
  "data": null
}
```

#### Schema 校验失败
```json
{
  "code": 400,
  "message": "输入校验失败: 缺少必填字段 'image'",
  "data": null
}
```

---

## 2. 一次性运行

### 接口说明

一次性运行模型：自动启动 → 等待就绪 → 推理 → 自动停止。适合低频调用场景。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/run`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| wait_timeout | int | 否 | 600 | 等待服务就绪的超时时间（秒） |
| validate | bool | 否 | false | 是否基于 IO Schema 校验输入 |
| filter_output | bool | 否 | false | 是否基于 IO Schema 过滤输出 |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| request_data | object | 是 | 推理请求数据 |

### 调用示例

#### curl
```bash
# 基本调用
curl -X POST http://localhost:5001/api/model-registry/1/run \
  -H "Content-Type: application/json" \
  -d '{
    "request_data": {
      "model": "Qwen/Qwen2-7B",
      "messages": [
        {"role": "user", "content": "你好"}
      ]
    }
  }'

# 自定义超时
curl -X POST "http://localhost:5001/api/model-registry/1/run?wait_timeout=1200" \
  -H "Content-Type: application/json" \
  -d '{
    "request_data": {
      "model": "Qwen/Qwen2-7B",
      "messages": [
        {"role": "user", "content": "你好"}
      ]
    }
  }'
```

#### Python
```python
import requests

data = {
    "request_data": {
        "model": "Qwen/Qwen2-7B",
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/run",
    json=data,
    params={"wait_timeout": 1200}
)
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "inference_result": {
      "id": "chatcmpl-abc123",
      "object": "chat.completion",
      "created": 1720857600,
      "model": "Qwen/Qwen2-7B",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "你好！我是Qwen2-7B，一个由阿里云开发的大语言模型..."
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 50,
        "total_tokens": 60
      }
    },
    "runtime_info": {
      "auto_started": true,
      "start_time": "2026-07-13T10:00:00",
      "stop_time": "2026-07-13T10:00:05",
      "duration_ms": 5000
    }
  }
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| inference_result | 推理结果，结构取决于模型类型 |
| runtime_info.auto_started | 是否自动启动了容器 |
| runtime_info.start_time | 容器启动时间 |
| runtime_info.stop_time | 容器停止时间 |
| runtime_info.duration_ms | 容器运行时长（毫秒） |

### 错误响应

#### 超时
```json
{
  "code": 500,
  "message": "等待服务就绪超时",
  "data": null
}
```

#### 无绑定
```json
{
  "code": 400,
  "message": "模型未绑定容器或镜像",
  "data": null
}
```
