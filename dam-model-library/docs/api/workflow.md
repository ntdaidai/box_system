# 工作流执行接口

## 接口说明

执行 `dam-workflow` 生成的 DAG。执行器按照 DAG 边关系做拓扑排序，依次执行 `ACTION` / `EVALUATION` 节点，并复用模型库现有推理能力：

- `mode=infer`：调用 `/infer` 语义，要求模型已经是 `running`
- `mode=run`：调用 `/run` 语义，必要时自动启动模型，推理后停止
- `videos` 是视频路径、MinIO object path 或 URL 字符串，当前现场证据优先使用视频
- `images` 是可选抓拍图路径；没有抓拍图时可为空
- `media_objects` 可传带 `type/bucket/object_name/path/url` 的媒体对象，执行器会透传给模型节点
- 未配置 `model_id` 的节点会标记为 `skipped`，不会中断整个 DAG

## 接口信息

- **请求方法**: `POST`
- **请求路径**: `/api/workflow/execute`
- **认证要求**: 无

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| dag | object | 是 | - | `dam-workflow` 返回的 `final_dag` |
| prompt | string | 否 | `""` | 事件 prompt |
| images | array | 否 | `[]` | 图片路径/MinIO 路径/URL 字符串 |
| videos | array | 否 | `[]` | 视频路径/MinIO 路径/URL 字符串 |
| media_objects | array | 否 | `[]` | 媒体对象列表 |
| sensor_data | object | 否 | `{}` | 传感器与事件上下文 |
| event_type | string | 否 | `null` | 已识别事件类型 |
| mode | string | 否 | `infer` | `infer` 或 `run` |
| validate | bool | 否 | `false` | 是否按 IO Schema 校验输入 |
| filter_output | bool | 否 | `false` | 是否按 IO Schema 过滤输出 |
| wait_timeout | int | 否 | `600` | `run` 模式等待模型就绪超时秒数 |

## 调用示例

```bash
curl -X POST http://localhost:5001/api/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "dag": {
      "nodes": [
        {"node_id": "start_0", "node_class": "START"},
        {"node_id": "action_0", "node_class": "ACTION", "node_type": "滑坡区域检测", "model_id": 10},
        {"node_id": "end_0", "node_class": "END"}
      ],
      "edges": [
        {"source": "start_0", "target": "action_0"},
        {"source": "action_0", "target": "end_0"}
      ]
    },
    "prompt": "发生了滑坡事件，请分析",
    "images": [],
    "videos": ["safety-events/videos/20260804/a.mp4"],
    "media_objects": [{"type": "video", "path": "safety-events/videos/20260804/a.mp4"}],
    "sensor_data": {"位移量": 15.2},
    "event_type": "滑坡",
    "mode": "infer"
  }'
```

## 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "success",
    "order": ["start_0", "action_0", "end_0"],
    "node_results": [
      {
        "node_id": "action_0",
        "node_class": "ACTION",
        "node_type": "滑坡区域检测",
        "model_id": 10,
        "model_name": "滑坡区域检测模型",
        "status": "success",
        "output": {}
      }
    ],
    "final_output": {}
  }
}
```

## 执行状态

| 状态 | 说明 |
|------|------|
| success | 所有可执行节点执行成功 |
| partial | 存在未配置 `model_id` 的跳过节点 |
| failed | 至少一个节点执行失败 |
