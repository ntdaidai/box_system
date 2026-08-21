# 无人机巡航动作 API

这两个接口把无人机巡航封装成可被其他任务、ECA 或工作流调用的动作。真实模式会执行对应 DJI 航线并将 4 张真实取证照片归档到 MinIO；演示模式会从启动时已经预置到 MinIO 的固定图片中返回 4 张地址，不会在每次接口调用时重复读取本地目录或上传图片。

## 接口列表

| 方法 | 路径 | 航线 |
| --- | --- | --- |
| `POST` | `/api/v1/drone/cruises/fishing` | 禁渔航线 |
| `POST` | `/api/v1/drone/cruises/wading` | 禁涉水航线 |

接口需要登录认证：

```http
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

下面的 `<BASE_URL>` 替换为后端地址，例如 `http://127.0.0.1:8090`。

## 最简单的调用方式

默认执行模式为 `simulation`，请求体可以传空对象。模拟模式不会调用 DJI，也不会读取视频；后端启动时会把两条航线各自的 6 张固定图片预置到 MinIO，接口调用时从对应的 6 个 MinIO 对象中随机选择 4 张返回。

### 禁渔航线

```bash
curl -X POST "<BASE_URL>/api/v1/drone/cruises/fishing" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 禁涉水航线

```bash
curl -X POST "<BASE_URL>/api/v1/drone/cruises/wading" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 请求参数

请求体为 JSON，所有字段均为可选。未传时优先读取后端环境变量配置。

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `workspace_id` | string | 环境变量 | DJI 工作空间 ID，真实模式可覆盖配置 |
| `dock_sn` | string | 环境变量 | 执行任务的机场 SN，真实模式可覆盖配置 |
| `file_id` | string | 对应航线环境变量 | DJI 航线 KMZ 文件 ID；禁渔和禁涉水分别配置 |
| `payload_index` | string | `88-0-0` | 相机负载索引，真实拍照时使用 |
| `rth_altitude` | integer | `50` | 返航高度，单位米，范围 `20~500` |
| `min_battery_capacity` | integer | `50` | 最低电量阈值，范围 `0~100` |

真实 DJI 航线调用示例：

```json
{
  "workspace_id": "workspace-001",
  "dock_sn": "机场设备 SN",
  "file_id": "禁渔航线 KMZ 文件 ID",
  "payload_index": "88-0-0",
  "rth_altitude": 50,
  "min_battery_capacity": 50
}
```

## 成功响应

两个接口统一返回以下结构。`data.image_urls` 是最方便给其他任务继续使用的 4 个 MinIO 地址。

```json
{
  "code": 200,
  "message": "无人机巡航完成，已归档 4 张照片",
  "data": {
    "run_id": "fishing_3e1b2c...",
    "route_key": "fishing",
    "route_name": "禁渔航线",
    "executor": "simulation",
    "photo_count": 4,
    "photos": [
      {
        "index": 1,
        "phase": "outbound",
        "phase_index": 1,
        "object_name": "drone-cruises/demo/fishing/2.png",
        "minio_url": "http://minio.example.com/drone-cruises/demo/fishing/2.png",
        "source_file_name": "无人机禁渔图片2.png"
      },
      {
        "index": 2,
        "phase": "outbound",
        "phase_index": 2,
        "object_name": "drone-cruises/demo/fishing/5.png",
        "minio_url": "http://minio.example.com/drone-cruises/demo/fishing/5.png",
        "source_file_name": "无人机禁渔图片5.png"
      },
      {
        "index": 3,
        "phase": "return",
        "phase_index": 1,
        "object_name": "drone-cruises/demo/fishing/1.png",
        "minio_url": "http://minio.example.com/drone-cruises/demo/fishing/1.png",
        "source_file_name": "无人机禁渔图片1.png"
      },
      {
        "index": 4,
        "phase": "return",
        "phase_index": 2,
        "object_name": "drone-cruises/demo/fishing/6.png",
        "minio_url": "http://minio.example.com/drone-cruises/demo/fishing/6.png",
        "source_file_name": "无人机禁渔图片6.png"
      }
    ],
    "image_urls": [
      "http://minio.example.com/drone-cruises/demo/fishing/2.png",
      "http://minio.example.com/drone-cruises/demo/fishing/5.png",
      "http://minio.example.com/drone-cruises/demo/fishing/1.png",
      "http://minio.example.com/drone-cruises/demo/fishing/6.png"
    ]
  }
}
```

`phase` 的取值说明：

- `outbound`：去程
- `return`：回程

模拟模式的照片对象会包含来源文件名 `source_file_name`；真实模式的照片对象会包含 DJI 原始照片的 `source_file_id`。

## MinIO 目录

真实模式每次调用都会生成独立的 `run_id`，真实照片目录格式为：

```text
drone-cruises/{route_key}/{run_id}/
```

例如禁渔航线：

```text
drone-cruises/fishing/{run_id}/outbound-1.png
drone-cruises/fishing/{run_id}/outbound-2.png
drone-cruises/fishing/{run_id}/return-1.png
drone-cruises/fishing/{run_id}/return-2.png
```

模拟模式使用固定对象，不按每次调用生成新目录：

```text
drone-cruises/demo/fishing/1.png
drone-cruises/demo/fishing/2.png
drone-cruises/demo/fishing/3.png
drone-cruises/demo/fishing/4.png
drone-cruises/demo/fishing/5.png
drone-cruises/demo/fishing/6.png
drone-cruises/demo/wading/1.png
drone-cruises/demo/wading/2.png
drone-cruises/demo/wading/3.png
drone-cruises/demo/wading/4.png
drone-cruises/demo/wading/5.png
drone-cruises/demo/wading/6.png
```

## 模拟模式与真实模式

默认配置：

```dotenv
DRONE_CRUISE_EXECUTOR=simulation
```

模拟模式首次预置时从以下目录读取图片，每条航线各有 6 张，按文件名排序后上传为上面的固定 MinIO 对象。后端启动时如果对象已经存在，只登记地址，不会重复上传。之后每次接口调用从已登记的 6 个 MinIO 地址中随机抽取 4 个，其中前 2 张标记为去程、后 2 张标记为回程：

```text
dam-backend/data/drone_pictures/nofishing/  # 禁渔航线
dam-backend/data/drone_pictures/nowater/    # 禁涉水航线
```

预置对象前缀可通过 `DRONE_CRUISE_DEMO_OBJECT_PREFIX` 配置，默认值为 `drone-cruises/demo`。如果启动初始化失败，模拟接口不会自行回退到逐次上传，而是返回错误，需先恢复 MinIO 或图片初始化配置。

因此模拟阶段调用接口不需要传任何航线、机场或 DJI 参数。

真实执行需要改为：

```dotenv
DRONE_CRUISE_EXECUTOR=real
DRONE_CRUISE_WORKSPACE_ID=<DJI 工作空间 ID>
DRONE_CRUISE_DOCK_SN=<机场 SN>
DRONE_CRUISE_FISHING_FILE_ID=<禁渔航线 KMZ 文件 ID>
DRONE_CRUISE_WADING_FILE_ID=<禁涉水航线 KMZ 文件 ID>
DRONE_CRUISE_PAYLOAD_INDEX=88-0-0
```

真实模式会下发 DJI 航线任务，在去程和回程进度点发送拍照指令，等待 4 张照片上传后再复制到 MinIO 并返回地址。

## 常见错误

| HTTP 状态码 | 说明 |
| --- | --- |
| `401` | 未登录或 JWT 已失效 |
| `422` | 请求参数校验失败 |
| `502` | DJI 航线、拍照或照片归档失败 |
| `503` | 后端无人机 HTTP 客户端尚未就绪 |
