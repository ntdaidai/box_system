# 容器日志接口

## 接口说明

获取模型容器的运行日志，支持一次性返回和流式推送。

## 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/model-registry/{model_id}/logs`
- **认证要求**: 无

## 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_id | int | 是 | 模型 ID |

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| tail | int | 否 | 100 | 返回的日志行数 |
| follow | bool | 否 | false | 是否流式推送 |

## 响应格式

### 一次性返回 (follow=false)

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "logs": "2026-07-13 10:00:00 INFO  Starting vLLM server...\n2026-07-13 10:00:01 INFO  Loading model..."
  }
}
```

### 流式推送 (follow=true)

返回 SSE (Server-Sent Events) 流，每个事件格式：

```
data: {"log": "2026-07-13 10:00:02 INFO  Model loaded successfully"}

data: {"log": "2026-07-13 10:00:03 INFO  Server started on port 8000"}
```

## 调用示例

### curl

```bash
# 获取最近 50 行日志
curl "http://localhost:5001/api/model-registry/1/logs?tail=50"

# 流式跟踪日志
curl -N "http://localhost:5001/api/model-registry/1/logs?follow=true"

# 流式跟踪最近 20 行
curl -N "http://localhost:5001/api/model-registry/1/logs?tail=20&follow=true"
```

### Python (requests)

```python
import requests

# 获取最近 50 行日志
response = requests.get(
    "http://localhost:5001/api/model-registry/1/logs",
    params={"tail": 50}
)
print(response.json()["data"]["logs"])
```

### Python (流式)

```python
import requests
import json

# 流式跟踪日志
with requests.get(
    "http://localhost:5001/api/model-registry/1/logs",
    params={"follow": True},
    stream=True
) as response:
    for line in response.iter_lines():
        if line:
            # 解析 SSE 数据
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                print(data["log"])
```

### JavaScript (fetch)

```javascript
// 流式跟踪日志
const eventSource = new EventSource(
  "http://localhost:5001/api/model-registry/1/logs?follow=true"
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.log);
};

eventSource.onerror = (error) => {
  console.error("日志流错误:", error);
  eventSource.close();
};
```

### JavaScript (fetch with abort)

```javascript
// 可取消的流式日志
const controller = new AbortController();

fetch(
  "http://localhost:5001/api/model-registry/1/logs?follow=true",
  { signal: controller.signal }
)
  .then(response => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) return;
        const text = decoder.decode(value);
        console.log(text);
        read();
      });
    }
    read();
  });

// 10 秒后停止
setTimeout(() => controller.abort(), 10000);
```

## 响应示例

### 一次性返回

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "logs": "INFO:     Started server process [1]\nINFO:     Waiting for application startup.\nINFO:     Application startup complete.\nINFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)\nINFO:     172.17.0.1:54321 - \"GET /health HTTP/1.1\" 200 OK"
  }
}
```

### 流式推送

```
data: {"log": "INFO:     Started server process [1]"}

data: {"log": "INFO:     Waiting for application startup."}

data: {"log": "INFO:     Application startup complete."}

data: {"log": "INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)"}

data: {"log": "INFO:     172.17.0.1:54321 - \"GET /health HTTP/1.1\" 200 OK"}
```

## 错误响应

### 模型未绑定容器

```json
{
  "code": 400,
  "message": "模型未绑定容器",
  "data": null
}
```

### 容器不存在

```json
{
  "code": 404,
  "message": "容器不存在",
  "data": null
}
```
