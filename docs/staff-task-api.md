# 现场人员人工处置 API（算法联调交接）

本文档用于算法侧调用现场人员人工处置任务接口。算法只需要调用“下发任务”接口；任务下发后，工作人员可以在 Web 端或小程序端接单、上传现场结果并完成闭环。

## 0. 接入约定

- 以下接口路径已经包含 `/api` 前缀，完整地址为：`http(s)://<服务地址>/<接口路径>`。
- `/api/v1/integration/...` 为 Web/算法集成接口，需要携带 Web 用户令牌：

  ```http
  Authorization: Bearer <web-token>
  ```

- `instance_id` 是安全事件实例在数据库中的数字 `id`，不是事件编号 `instance_no`。
- 算法建议使用本文档中的大写标准枚举值，不要依赖中文别名。
- 所有时间由服务端写入，返回 ISO 8601 时间字符串；算法不需要自行生成处置时间。

## 1. 业务流程

### 1.1 正常模式

```text
算法下发任务
  -> WAITING_ACCEPT（事件 PENDING）
  -> Web/小程序接单
  -> PROCESSING（事件 PROCESSING）
  -> 提交驱离前、驱离后两张图片及文本结果
  -> COMPLETED（事件 RESOLVED）
```

正常模式调用下发接口时，`demo` 传 `false` 或不传。系统不会自动完成任务，等待工作人员操作。

### 1.2 演示模式

```text
算法下发 demo=true
  -> 系统自动写入下发、接单、完成三条操作记录
  -> 从固定演示目录读取两张图片并上传 MinIO
  -> 自动完成任务，状态直接为 COMPLETED
```

演示模式不需要工作人员点击接单，也不需要算法上传图片。两类演示图片会在后端启动初始化阶段预置到 MinIO；后续每次演示调用只引用已经存在的 MinIO 地址，不会再次读取本地图片或重复上传。系统会返回固定的“驱离前”和“驱离后”图片地址以及固定处置文本。

## 2. 事件类型

算法传入的 `event_type` 必须表示本次人工处置对应的业务类型：

| 标准值 | 中文名称 | 首次预置来源目录（后续调用不读取） |
| --- | --- | --- |
| `PERSON_WADING` | 人员涉水事件 | `data/worker_pictures/nowater` |
| `NIGHT_FISHING` | 夜间捕鱼事件 | `data/worker_pictures/nofishing` |

当前也兼容以下历史别名，但算法侧不要使用别名：

- 人员类：`PERSON_HIGH`、`人员涉水`、`人员涉水事件`、`人员亲水`、`人员闯入`
- 捕鱼类：`BOAT_ILLEGAL_FISHING`、`FISHING`、`夜间捕鱼`、`夜间捕鱼事件`、`非法捕鱼`、`禁渔事件`

## 3. 算法下发人工处置任务

### 3.1 接口

```http
POST /api/v1/integration/safety-events/{instance_id}/staff-task/dispatch
Authorization: Bearer <web-token>
Content-Type: application/json
```

### 3.2 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `event_type` | string | 是 | `PERSON_WADING` 或 `NIGHT_FISHING` |
| `assignee` | string | 否 | 指定处理人名称，最长 128 个字符；不指定时由工作人员接单 |
| `group_name` | string | 否 | 接收任务的处置组名称，最长 128 个字符 |
| `note` | string | 否 | 给工作人员的任务说明，最长 500 个字符；不传时服务端自动生成 |
| `demo` | boolean | 否 | 是否启用演示自动闭环，默认 `false` |

### 3.3 正常模式请求示例

```bash
curl -X POST \
  "http://<服务地址>/api/v1/integration/safety-events/123/staff-task/dispatch" \
  -H "Authorization: Bearer <web-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "PERSON_WADING",
    "group_name": "现场处置一组",
    "note": "请到 9 号监测点核查并完成驱离",
    "demo": false
  }'
```

正常模式返回后，算法重点关注：

```json
{
  "code": 200,
  "message": "人工处置任务已下发",
  "data": {
    "event_type": "PERSON_WADING",
    "event_type_label": "人员涉水事件",
    "demo": false,
    "task": {
      "id": 456,
      "assigned_group_name": "现场处置一组",
      "status": "WAITING_ACCEPT",
      "event_type": "PERSON_WADING",
      "event_type_label": "人员涉水事件",
      "dispatched_at": "2026-08-21T16:00:00"
    },
    "photo_urls": [],
    "demo_pictures": []
  }
}
```

### 3.4 演示模式请求示例

```bash
curl -X POST \
  "http://<服务地址>/api/v1/integration/safety-events/123/staff-task/dispatch" \
  -H "Authorization: Bearer <web-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "NIGHT_FISHING",
    "group_name": "现场处置一组",
    "note": "演示夜间捕鱼现场处置",
    "demo": true
  }'
```

演示模式返回的关键字段如下：

```json
{
  "code": 200,
  "message": "演示人工处置任务已自动完成",
  "data": {
    "event_type": "NIGHT_FISHING",
    "event_type_label": "夜间捕鱼事件",
    "demo": true,
    "task": {
      "id": 456,
      "status": "COMPLETED",
      "result_type": "DRIVEN_AWAY",
      "result_remark": "已完成现场核查，夜间捕鱼行为已成功制止并驱离，并已上传驱离前后照片。",
      "event_type": "NIGHT_FISHING",
      "event_type_label": "夜间捕鱼事件",
      "dispatched_at": "2026-08-21T16:00:00",
      "accepted_at": "2026-08-21T16:00:01",
      "completed_at": "2026-08-21T16:00:02"
    },
    "photo_urls": [
      "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/before-<uuid>.png",
      "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/after-<uuid>.png"
    ],
    "demo_pictures": [
      {
        "phase": "before",
        "object_name": "safety-events/field-images/2026-08-21/EVT-001/before-<uuid>.png",
        "minio_url": "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/before-<uuid>.png",
        "source_file_name": "工作人员捕鱼图1.png"
      },
      {
        "phase": "after",
        "object_name": "safety-events/field-images/2026-08-21/EVT-001/after-<uuid>.png",
        "minio_url": "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/after-<uuid>.png",
        "source_file_name": "工作人员捕鱼图2.png"
      }
    ],
    "result_remark": "已完成现场核查，夜间捕鱼行为已成功制止并驱离，并已上传驱离前后照片。"
  }
}
```

说明：上例中的地址、事件编号、任务编号和 UUID 仅为格式示例，实际值以接口响应为准。`photo_urls[0]` 永远是驱离前照片，`photo_urls[1]` 永远是驱离后照片。

演示模式固定处置文本：

- `PERSON_WADING`：`已完成现场核查，人员已成功驱离，并已上传驱离前后照片。`
- `NIGHT_FISHING`：`已完成现场核查，夜间捕鱼行为已成功制止并驱离，并已上传驱离前后照片。`

## 4. Web 端提交人工处置结果

正常模式下由 Web 端工作人员接单并提交。算法一般不需要调用此接口；如果算法联调需要模拟工作人员提交结果，可以使用此接口。

### 4.1 接口

```http
POST /api/v1/integration/safety-events/{instance_id}/staff-task/result
Authorization: Bearer <web-token>
Content-Type: multipart/form-data
```

### 4.2 表单参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `event_type` | string | 是 | `PERSON_WADING` 或 `NIGHT_FISHING` |
| `result` | string | 是 | `DRIVEN_AWAY`、`LEFT_BY_SELF` 或 `OTHER` |
| `remark` | string | 否 | 现场处置文本，最长 500 个字符 |
| `photos` | file | 是 | 必须重复提交两次，第一张为驱离前，第二张为驱离后；支持 JPG、PNG、WEBP，单张不超过 10MB |

### 4.3 请求示例

```bash
curl -X POST \
  "http://<服务地址>/api/v1/integration/safety-events/123/staff-task/result" \
  -H "Authorization: Bearer <web-token>" \
  -F "event_type=PERSON_WADING" \
  -F "result=DRIVEN_AWAY" \
  -F "remark=已完成现场核查，人员已成功驱离" \
  -F "photos=@/tmp/before.jpg" \
  -F "photos=@/tmp/after.jpg"
```

提交成功后，任务状态为 `COMPLETED`，事件状态为已闭环，并返回：

```json
{
  "code": 200,
  "message": "处理结果已提交，事件已闭环",
  "data": {
    "event_type": "PERSON_WADING",
    "event_type_label": "人员涉水事件",
    "photo_urls": [
      "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/before-<uuid>.jpg",
      "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/after-<uuid>.jpg"
    ],
    "remark": "已完成现场核查，人员已成功驱离"
  }
}
```

## 5. 小程序端接口参考

Web 和小程序使用同一套任务状态和 MinIO 图片路径。算法只负责下发任务时，不需要直接调用下面接口；下面内容用于算法联调和端到端验证。

### 5.1 小程序接单

```http
POST /api/miniprogram/v1/events/{event_id}/accept
Content-Type: application/json
```

请求示例：

```json
{
  "staff_id": 12,
  "openid": "工作人员 openid",
  "remark": "已接单"
}
```

`event_id` 支持事件实例数字 ID 或事件编号。接单后任务进入 `ACCEPTED`，事件进入处理中。

### 5.2 分别上传驱离前、驱离后照片

```http
POST /api/miniprogram/v1/events/{event_id}/field-photo
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `phase` | string | 第一次传 `before`，第二次传 `after` |
| `event_type` | string | `PERSON_WADING` 或 `NIGHT_FISHING` |
| `operator` | string | 可选，处理人名称 |
| `photo` | file | 当前阶段的一张现场图片 |

接口返回 `photo_url`。两次返回的地址按 `before`、`after` 顺序保存。

### 5.3 确认提交文本结果

```http
POST /api/miniprogram/v1/events/{event_id}/field-result/confirm
Content-Type: application/json
```

请求示例：

```json
{
  "result": "DRIVEN_AWAY",
  "remark": "已完成现场核查，人员已成功驱离",
  "operator": "张三",
  "event_type": "PERSON_WADING",
  "photo_urls": [
    "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/before-<uuid>.jpg",
    "<minio-url>/safety-events/field-images/2026-08-21/EVT-001/after-<uuid>.jpg"
  ]
}
```

`photo_urls` 必须正好两条，且必须是人工处置现场图片路径。确认后任务进入 `COMPLETED`，同时写入事件证据。

如果客户端希望一次提交两张图片，也可以使用：

```http
POST /api/miniprogram/v1/events/{event_id}/field-result
Content-Type: multipart/form-data
```

表单中传入 `event_type`、`result`、`remark`、`operator`，并重复传两次 `photos`；顺序同样是驱离前、驱离后。

## 6. 图片存储规则

无论是演示图片、Web 上传还是小程序上传，统一写入 MinIO，对象路径格式为：

```text
safety-events/field-images/{YYYY-MM-DD}/{instance_no}/before-{uuid}.jpg
safety-events/field-images/{YYYY-MM-DD}/{instance_no}/after-{uuid}.jpg
```

- 第一张图片使用 `before-` 前缀，表示驱离前。
- 第二张图片使用 `after-` 前缀，表示驱离后。
- 图片不会保存为服务端本地临时结果；MinIO 上传失败时接口直接返回错误，不会返回不可用的本地路径。
- 事件详情接口中的 `tasks[].photo_urls` 和接口响应中的 `data.photo_urls` 是同一组可展示地址。

演示图片首次预置的本地根目录由配置项 `STAFF_TASK_DEMO_PICTURE_ROOT` 控制，默认容器路径为：

```text
/app/data/worker_pictures
├── nowater/
└── nofishing/
```

每个事件类型目录至少需要两张 JPG、PNG 或 WEBP 图片，后端启动初始化时按文件名排序取前两张，分别作为驱离前、驱离后图片，并上传为稳定的 MinIO 对象：

```text
safety-events/demo-field-images/person-wading/before.png
safety-events/demo-field-images/person-wading/after.png
safety-events/demo-field-images/night-fishing/before.png
safety-events/demo-field-images/night-fishing/after.png
```

对象前缀可通过 `STAFF_TASK_DEMO_OBJECT_PREFIX` 配置。初始化时如果对象已经存在，系统只登记已有地址，不会重复上传；算法调用演示接口时只会读取这组已登记的 MinIO 地址。算法不需要传本地文件路径。

## 7. 状态和返回字段

### 7.1 任务状态

| 状态 | 含义 |
| --- | --- |
| `WAITING_ACCEPT` | 已下发，等待工作人员接单 |
| `ACCEPTED` | 工作人员已接单 |
| `PROCESSING` | 正在现场处理 |
| `COMPLETED` | 已提交结果并完成闭环 |

### 7.2 任务对象常用字段

| 字段 | 说明 |
| --- | --- |
| `id` | 任务 ID |
| `assignee` | 处理人名称 |
| `dispatch_operator` | 下发任务的操作人；演示自动闭环的接单和完成操作人为 `SYSTEM` |
| `assigned_group_id` / `assigned_group_name` | 接收任务的处置组 |
| `status` | 任务状态 |
| `note` | 任务说明 |
| `event_type` / `event_type_label` | 人工处置事件类型及中文名称 |
| `result_type` | `DRIVEN_AWAY`、`LEFT_BY_SELF` 或 `OTHER` |
| `result_remark` | 现场处理文本 |
| `dispatched_at` / `accepted_at` / `completed_at` | 各阶段服务端时间 |

图片地址不放在集成接口返回的 `data.task` 内：演示下发或提交结果时使用顶层 `data.photo_urls`；查询事件详情时使用 `tasks[].photo_urls`。两者顺序均为驱离前、驱离后。

## 8. 错误处理和重试约定

常见 HTTP 状态码：

| 状态码 | 说明 |
| --- | --- |
| `200` | 调用成功 |
| `400` | 参数或图片不合法、演示图片不足、MinIO 上传失败 |
| `401` | Web Token 缺失或无效 |
| `404` | 安全事件不存在 |
| `409` | 事件已结束、任务已完成或任务正在被处理，不能重复操作 |
| `422` | 请求体或表单字段未通过接口校验 |

重试建议：

- 网络超时可以重试，但应先查询事件详情确认任务状态，避免重复下发。
- `WAITING_ACCEPT` 时重复下发不会创建另一条并行任务，服务端会更新当前任务；算法仍建议保存第一次成功响应中的任务 ID。
- `ACCEPTED`、`PROCESSING` 或 `COMPLETED` 时再次下发会返回 `409`，不要循环重试。
- `demo=true` 是一次性演示闭环；如果该事件已经完成，再次调用会返回 `409`。
- 演示接口成功返回 `200` 且 `data.task.status=COMPLETED` 后，算法可以直接把 `data.photo_urls` 和 `data.result_remark` 作为本次人工处置结果使用。
