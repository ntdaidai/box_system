# 机器狗路线测试 API

机器狗当前只有一条固定的全路线。接口调用后执行该路线，读取
`dam-backend/data/frone_pictures/dogtake/` 下的四张测试照片，上传到 MinIO，
完成后返回四张照片地址。

## 接口列表

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/machine-dog/routes` | 查询唯一机器狗路线 |
| `POST` | `/api/v1/machine-dog/cruises/all` | 执行全路线并返回四张照片 |

接口需要登录认证：

```http
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

## 调用示例

```bash
curl -X POST "<BASE_URL>/api/v1/machine-dog/cruises/all" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

请求体为空即可，不需要传路线参数。接口内部固定执行 `all` 路线。

## 成功响应

```json
{
  "code": 200,
  "message": "机器狗全路线完成，已归档 4 张照片",
  "data": {
    "run_id": "all_3e1b2c...",
    "route_key": "all",
    "route_name": "机器狗全路线",
    "executor": "simulation",
    "photo_count": 4,
    "photos": [
      {
        "index": 1,
        "point": "巡检点 1",
        "object_name": "machine-dog-cruises/all/all_3e1b2c.../point-1.png",
        "minio_url": "http://minio.example.com/dam/machine-dog-cruises/all/.../point-1.png",
        "source_file_name": "dog-1.png"
      },
      {
        "index": 2,
        "point": "巡检点 2",
        "object_name": "machine-dog-cruises/all/all_3e1b2c.../point-2.png",
        "minio_url": "http://minio.example.com/dam/machine-dog-cruises/all/.../point-2.png",
        "source_file_name": "dog-2.png"
      },
      {
        "index": 3,
        "point": "巡检点 3",
        "object_name": "machine-dog-cruises/all/all_3e1b2c.../point-3.png",
        "minio_url": "http://minio.example.com/dam/machine-dog-cruises/all/.../point-3.png",
        "source_file_name": "dog-3.png"
      },
      {
        "index": 4,
        "point": "巡检点 4",
        "object_name": "machine-dog-cruises/all/all_3e1b2c.../point-4.png",
        "minio_url": "http://minio.example.com/dam/machine-dog-cruises/all/.../point-4.png",
        "source_file_name": "dog-4.png"
      }
    ],
    "image_urls": [
      "http://minio.example.com/dam/machine-dog-cruises/all/.../point-1.png",
      "http://minio.example.com/dam/machine-dog-cruises/all/.../point-2.png",
      "http://minio.example.com/dam/machine-dog-cruises/all/.../point-3.png",
      "http://minio.example.com/dam/machine-dog-cruises/all/.../point-4.png"
    ]
  }
}
```

## 照片目录

默认目录为：

```text
dam-backend/data/frone_pictures/dogtake/
```

接口按文件名排序读取前 4 张 `.jpg`、`.jpeg`、`.png` 或 `.webp` 图片，分别作为
巡检点 1、巡检点 2、巡检点 3、巡检点 4 的结果。目录不足 4 张图片时返回 `502`。

可以通过环境变量调整本地目录和 MinIO 前缀：

```dotenv
MACHINE_DOG_CRUISE_PICTURE_ROOT=/path/to/frone_pictures
MACHINE_DOG_CRUISE_OBJECT_PREFIX=machine-dog-cruises
```

## 常见错误

| HTTP 状态码 | 说明 |
| --- | --- |
| `401` | 未登录或 JWT 已失效 |
| `502` | 照片目录不存在、照片不足或 MinIO 上传失败 |
