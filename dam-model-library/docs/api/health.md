# 健康检查接口

## 接口说明

检查服务、MySQL 数据库、Docker 服务的连通性。

## 接口信息

- **请求方法**: `GET`
- **请求路径**: `/api/health`
- **认证要求**: 无

## 请求参数

无

## 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| code | int | 状态码 |
| message | string | 状态信息 |
| data | object | 健康状态对象 |
| data.service | string | 服务状态: "ok" |
| data.mysql | string | MySQL 状态: "ok" 或错误信息 |
| data.docker | string | Docker 状态: "ok" 或错误信息 |

## 调用示例

### curl
```bash
curl http://localhost:5001/api/health
```

### Python (requests)
```python
import requests

response = requests.get("http://localhost:5001/api/health")
print(response.json())
```

### JavaScript (fetch)
```javascript
fetch("http://localhost:5001/api/health")
  .then(res => res.json())
  .then(data => console.log(data));
```

## 响应示例

### 成功
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service": "ok",
    "mysql": "ok",
    "docker": "ok"
  }
}
```

### Docker 连接失败
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service": "ok",
    "mysql": "ok",
    "docker": "Error while fetching server API version"
  }
}
```
