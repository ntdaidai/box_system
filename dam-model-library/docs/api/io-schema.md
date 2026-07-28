# IO Schema 接口

## 接口说明

管理模型的输入输出 Schema 定义，用于推理时的参数校验和输出过滤。

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/model-registry/{model_id}/io-schema` | 获取 IO Schema |
| POST | `/api/model-registry/{model_id}/io-schema` | 设置 IO Schema |
| PUT | `/api/model-registry/{model_id}/io-schema` | 更新 IO Schema |
| DELETE | `/api/model-registry/{model_id}/io-schema` | 删除 IO Schema |

---

## Schema 字段结构

每个输入/输出字段的结构如下：

```json
{
  "field": "字段名",
  "type": "字段类型",
  "label": "显示标签",
  "targetFormat": "目标格式",
  "defaultValue": "默认值",
  "required": true
}
```

### 支持的字段类型

| 类型 | 说明 |
|------|------|
| text | 文本 |
| integer | 整数 |
| float | 浮点数 |
| json | JSON 对象 |
| image | 图片 |
| audio | 音频 |
| video | 视频 |
| file | 文件 |

---

## 1. 获取 IO Schema

### 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/model-registry/{model_id}/io-schema`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl http://localhost:5001/api/model-registry/1/io-schema
```

#### Python
```python
import requests

response = requests.get("http://localhost:5001/api/model-registry/1/io-schema")
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
    "inputs": [
      {
        "field": "image",
        "type": "image",
        "label": "输入图片",
        "targetFormat": "base64",
        "defaultValue": null,
        "required": true
      },
      {
        "field": "confidence",
        "type": "float",
        "label": "置信度阈值",
        "targetFormat": null,
        "defaultValue": 0.5,
        "required": false
      }
    ],
    "outputs": [
      {
        "field": "detections",
        "type": "json",
        "label": "检测结果",
        "targetFormat": null,
        "defaultValue": null,
        "required": true
      }
    ],
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

#### 无 Schema
```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

## 2. 设置 IO Schema

### 接口说明

为模型设置输入输出 Schema。

### 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/model-registry/{model_id}/io-schema`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| inputs | array | 否 | 输入字段 Schema 列表 |
| outputs | array | 否 | 输出字段 Schema 列表 |

### 调用示例

#### curl
```bash
curl -X POST http://localhost:5001/api/model-registry/1/io-schema \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "field": "image",
        "type": "image",
        "label": "输入图片",
        "targetFormat": "base64",
        "required": true
      },
      {
        "field": "prompt",
        "type": "text",
        "label": "提示词",
        "required": true
      },
      {
        "field": "temperature",
        "type": "float",
        "label": "温度",
        "defaultValue": 0.7,
        "required": false
      }
    ],
    "outputs": [
      {
        "field": "result",
        "type": "text",
        "label": "生成结果",
        "required": true
      }
    ]
  }'
```

#### Python
```python
import requests

data = {
    "inputs": [
        {
            "field": "image",
            "type": "image",
            "label": "输入图片",
            "targetFormat": "base64",
            "required": True
        },
        {
            "field": "prompt",
            "type": "text",
            "label": "提示词",
            "required": True
        },
        {
            "field": "temperature",
            "type": "float",
            "label": "温度",
            "defaultValue": 0.7,
            "required": False
        }
    ],
    "outputs": [
        {
            "field": "result",
            "type": "text",
            "label": "生成结果",
            "required": True
        }
    ]
}

response = requests.post(
    "http://localhost:5001/api/model-registry/1/io-schema",
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
    "inputs": [
      {
        "field": "image",
        "type": "image",
        "label": "输入图片",
        "targetFormat": "base64",
        "defaultValue": null,
        "required": true
      },
      {
        "field": "prompt",
        "type": "text",
        "label": "提示词",
        "targetFormat": null,
        "defaultValue": null,
        "required": true
      },
      {
        "field": "temperature",
        "type": "float",
        "label": "温度",
        "targetFormat": null,
        "defaultValue": 0.7,
        "required": false
      }
    ],
    "outputs": [
      {
        "field": "result",
        "type": "text",
        "label": "生成结果",
        "targetFormat": null,
        "defaultValue": null,
        "required": true
      }
    ],
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:00:00"
  }
}
```

---

## 3. 更新 IO Schema

### 接口说明

更新模型的 IO Schema，所有字段可选。

### 接口信息

- **请求方法**: `PUT`
- **请求路径**: `/api/model-registry/{model_id}/io-schema`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 请求参数 (Body)

| 参数 | 类型 | 说明 |
|------|------|------|
| inputs | array | 输入字段 Schema 列表 |
| outputs | array | 输出字段 Schema 列表 |

### 调用示例

#### curl
```bash
curl -X PUT http://localhost:5001/api/model-registry/1/io-schema \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [
      {
        "field": "image",
        "type": "image",
        "label": "输入图片",
        "targetFormat": "base64",
        "required": true
      },
      {
        "field": "prompt",
        "type": "text",
        "label": "提示词",
        "required": true
      },
      {
        "field": "temperature",
        "type": "float",
        "label": "温度",
        "defaultValue": 0.7,
        "required": false
      },
      {
        "field": "max_tokens",
        "type": "integer",
        "label": "最大Token数",
        "defaultValue": 1024,
        "required": false
      }
    ]
  }'
```

#### Python
```python
import requests

data = {
    "inputs": [
        {
            "field": "image",
            "type": "image",
            "label": "输入图片",
            "targetFormat": "base64",
            "required": True
        },
        {
            "field": "prompt",
            "type": "text",
            "label": "提示词",
            "required": True
        },
        {
            "field": "temperature",
            "type": "float",
            "label": "温度",
            "defaultValue": 0.7,
            "required": False
        },
        {
            "field": "max_tokens",
            "type": "integer",
            "label": "最大Token数",
            "defaultValue": 1024,
            "required": False
        }
    ]
}

response = requests.put(
    "http://localhost:5001/api/model-registry/1/io-schema",
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
    "inputs": [
      {
        "field": "image",
        "type": "image",
        "label": "输入图片",
        "targetFormat": "base64",
        "defaultValue": null,
        "required": true
      },
      {
        "field": "prompt",
        "type": "text",
        "label": "提示词",
        "targetFormat": null,
        "defaultValue": null,
        "required": true
      },
      {
        "field": "temperature",
        "type": "float",
        "label": "温度",
        "targetFormat": null,
        "defaultValue": 0.7,
        "required": false
      },
      {
        "field": "max_tokens",
        "type": "integer",
        "label": "最大Token数",
        "targetFormat": null,
        "defaultValue": 1024,
        "required": false
      }
    ],
    "outputs": [
      {
        "field": "result",
        "type": "text",
        "label": "生成结果",
        "targetFormat": null,
        "defaultValue": null,
        "required": true
      }
    ],
    "create_time": "2026-07-13T10:00:00",
    "update_time": "2026-07-13T10:05:00"
  }
}
```

---

## 4. 删除 IO Schema

### 接口说明

删除模型的 IO Schema。

### 接口信息

- **请求方法**: `DELETE`
- **请求路径**: `/api/model-registry/{model_id}/io-schema`
- **认证要求**: 无

### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

### 调用示例

#### curl
```bash
curl -X DELETE http://localhost:5001/api/model-registry/1/io-schema
```

#### Python
```python
import requests

response = requests.delete("http://localhost:5001/api/model-registry/1/io-schema")
print(response.json())
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```
