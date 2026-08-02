# box_system 数据库整合设计稿 V1

更新时间：2026-08-01

本文只记录第一阶段已经讨论的设备、摄像头、广播、检测区域和数据源设计。ECA、安全事件、动作流程、任务和佐证将在后续讨论中继续补充。本阶段不修改数据库和业务代码。

## 1. 设计边界

- 暂不调整 `sys_user`、模型库、工作流和 `analysis_report`。
- 模型库与工作流由其他小组维护，后续只预留执行器或引用接口，不在本阶段建立强耦合。
- 当前重点是打通“用户配置摄像头 -> 绘制风险区域 -> 视频检测 -> ECA 判断 -> 事件 -> 广播/无人机/人工处置 -> 统一告警展示”。
- 最终实施时，SQLAlchemy 模型、版本化迁移脚本和实际 MySQL 结构必须一致。

## 2. `sys_device` 现状与决定

当前摄像头业务没有使用 `sys_device`：摄像头管理接口、服务启动加载、视频流管理和检测区域均直接使用 `camera_device`。`sys_device` 目前是一个带串口、Modbus 地址的传感器设备模型，并不是摄像头父表；实际运行库中也没有这张表。

第一阶段决定：

- 不让 `camera_device` 再继承或重复写入 `sys_device`。
- 当前设计不引入通用设备主表。
- `sys_device` 暂定为待废弃模型；传感器设备如何建表，在传感器与 ECA 设计阶段单独确定。
- 删除前需检查 `/api/device` 是否还有前端页面或外部调用，避免直接移除造成兼容问题。

## 3. `camera_device` 目标设计

用途：摄像头设备台账，是设备管理、视频监控下拉列表、视频流连接和检测区域的唯一摄像头来源。

| 字段 | 建议类型 | 约束/默认值 | 说明 |
| --- | --- | --- | --- |
| id | bigint | PK，自增 | 摄像头唯一标识；不再保留 `dahua_001` 一类业务 ID |
| name | varchar(128) | NOT NULL，UNIQUE | 摄像头名称，页面展示名称 |
| ip_address | varchar(128) | NOT NULL | 摄像头 IP 地址 |
| username | varchar(128) | NOT NULL | 登录账号 |
| password | varchar(256) | NOT NULL | 登录密码；实现时应加密保存，接口不回传明文 |
| description | varchar(1000) | NULL | 描述 |
| install_address | varchar(255) | NULL | 安装地址 |
| longitude | decimal(10,7) | NULL | 经度 |
| latitude | decimal(9,7) | NULL | 纬度 |
| enabled | boolean | NOT NULL，默认 true | 是否启用 |
| last_error | text | NULL | 最近一次连接或运行错误 |
| rtsp_port | int | NOT NULL，默认 554 | RTSP 端口 |
| web_port | int | NOT NULL，默认 80 | 摄像头控制台端口 |
| web_proxy_port | int | NULL，UNIQUE | 后端代理监听端口，由系统分配或维护 |
| rtsp_path | varchar(256) | NOT NULL | 测试连接成功后保存的实际 RTSP 通道路径 |
| last_online_at | datetime | NULL | 最近在线时间 |
| create_time | datetime | NOT NULL | 创建时间 |
| update_time | datetime | NOT NULL | 更新时间 |

明确删除：

- `camera_id` 业务 ID。
- 要求用户选择的 `brand` 字段。后端测试连接时依次尝试大华、海康通道路径，保存成功的 `rtsp_path`。

所有关联表和 API 最终改用 `camera_device.id`。前端 URL、组件内部变量仍可叫 `cameraId`，但值改为数据库数字主键；页面只展示 `name`。

### 3.1 摄像头新增流程

基础设置（用户填写）：

- 名称
- IP 地址
- 登录账号
- 登录密码
- 描述

高级设置（展开后选填）：

- 安装地址
- 经度、纬度
- RTSP 端口，默认 554
- 控制台端口，默认 80

保存流程：

1. 前端提交测试连接请求，不先写数据库。
2. 后端按候选 RTSP 路径测试大华和海康视频流。
3. 返回连接结果和识别出的可用 `rtsp_path`。
4. 连接成功后才允许写入 `camera_device`。
5. 创建成功后，视频监控的视频源下拉列表自动出现该摄像头。

### 3.2 前端入口调整

- 删除视频监控页面的“接入 Jetson 视频源”入口和弹窗。
- 摄像头只能从设备管理页面新增、编辑、测试连接和删除。
- 视频监控页面继续保留现有摄像头展示样式及视频源下拉框。
- 下拉框使用摄像头主键作为值，显示摄像头名称。
- 不再要求用户填写摄像头业务 ID、品牌或完整 RTSP URL。

## 4. `broadcast_device` 目标设计

用途：保存摄像头对应的广播设备。广播属于动作执行设备，不属于 `data_source`。

| 字段 | 建议类型 | 约束/默认值 | 说明 |
| --- | --- | --- | --- |
| id | bigint | PK，自增 | 广播设备主键 |
| camera_id | bigint | NOT NULL，FK -> camera_device.id | 所属摄像头 |
| name | varchar(128) | NOT NULL，UNIQUE | 广播设备名称，不允许重复 |
| description | varchar(1000) | NULL | 描述 |
| enabled | boolean | NOT NULL，默认 true | 是否启用 |
| create_time | datetime | NOT NULL | 创建时间 |
| update_time | datetime | NOT NULL | 更新时间 |

关系约定：

- 广播设备必须属于一个摄像头。
- 默认按“一台摄像头可以有多个广播设备”设计，即 `camera_device 1:N broadcast_device`。
- 如果后续确认严格一对一，可给 `broadcast_device.camera_id` 增加 UNIQUE 约束。
- 原 `camera_broadcast_device` 中间表在数据迁移完成后删除。

待确认：上述字段没有广播协议、地址或设备参数。若实际广播完全由 Jetson 本机固定音频输出，连接参数可以由环境配置维护；如果需要接入不同厂商或网络广播，后续必须补充执行器类型和连接配置。

## 5. `broadcast_template` 目标设计

| 字段 | 建议类型 | 约束/默认值 | 说明 |
| --- | --- | --- | --- |
| id | bigint | PK，自增 | 模板主键；替代目前字符串业务 ID 的方向待最终确认 |
| name | varchar(128) | NOT NULL | 模板名称 |
| scene_type | varchar(64) | NOT NULL | 场景类型，例如人员涉水、人员闯入 |
| risk_level | varchar(16) | NOT NULL | LOW/MEDIUM/HIGH |
| content | text | NOT NULL | 播报文本 |
| enabled | boolean | NOT NULL，默认 true | 是否启用 |
| create_time | datetime | NOT NULL | 创建时间 |
| update_time | datetime | NOT NULL | 更新时间 |

广播设备和广播模板的管理功能放到“视频监控”下新增的管理栏目中，允许用户查看、新增、编辑和启停。

## 6. `camera_detection_zone` 目标设计

用途：保存用户在某个摄像头画面上绘制的多边形风险区域。区域只表达空间边界和风险级别，不保存触发时长。

| 字段 | 建议类型 | 约束/默认值 | 说明 |
| --- | --- | --- | --- |
| id | bigint | PK，自增 | 检测区域主键 |
| camera_id | bigint | NOT NULL，FK -> camera_device.id | 所属摄像头 |
| name | varchar(80) | NOT NULL | 区域名称；建议同一摄像头下不可重名 |
| zone_type | varchar(16) | NOT NULL | LOW/MEDIUM/HIGH，对应低/中/高风险区域 |
| polygon_points | json | NOT NULL | 归一化多边形点位 |
| create_time | datetime | NOT NULL | 创建时间 |
| update_time | datetime | NOT NULL | 更新时间 |

多边形规则：

- 只支持多边形，不再支持矩形结构。
- `polygon_points` 必须包含 3 至 15 个点。
- 每个点格式为 `{ "x": number, "y": number }`，坐标归一化到 0 至 1。
- 后端必须验证点数量、字段类型、坐标范围和多边形有效性。
- 删除 `rect_x`、`rect_y`、`rect_width`、`rect_height`。
- 删除由 rect 还原多边形的前后端 fallback。
- 删除 `trigger_seconds`，触发时长进入 ECA 条件配置。
- 不再使用“警戒区、亲水区、涉水区”等写死类型。

关于“前端绘制区域 ID”：建议不落库。前端绘制未保存图形时可以使用临时 ID，保存成功后统一使用数据库 `id`。这样与摄像头取消业务 ID 的原则一致。如果后续存在离线编辑或批量同步需求，再增加明确命名的 `client_key`。

待确认：是否保留 `enabled`。保留它可以临时停用区域而不删除；若业务不需要停用能力则不加入目标表。

## 7. 区域停留时长进入 ECA

将低风险区停留 20 秒、中风险区停留 10 秒、进入高风险区立即触发等规则放进 ECA 的 C 是正确方向，区域表只保存“哪里”和“风险级别”。

视频检测层需要持续向 ECA 提供标准观测变量：

- `camera_id`
- `target_type`
- `track_id`
- `zone_id`
- `zone_level`
- `dwell_seconds`
- `confidence`
- `bbox`
- `observed_at`

条件示例：

- `target_type = person AND zone_level = LOW AND dwell_seconds >= 20`
- `target_type = person AND zone_level = MEDIUM AND dwell_seconds >= 10`
- `target_type = person AND zone_level = HIGH`

这样调整时长只改 ECA 配置，不改检测区域和代码。具体条件表字段、表达式结构和事件定义将在 ECA 阶段确定。

## 8. 同一目标跨风险区域的事件连续性

同一摄像头内，同一个人从低风险区域进入高风险区域，应维护为同一个安全事件：

1. 使用 `(camera_id, target_type, track_id)` 查找当前未关闭事件。
2. 低风险条件满足后创建事件并执行低风险流程。
3. 同一 `track_id` 进入高风险区域时，更新原事件的当前风险和最高风险。
4. 写入风险变化日志 `LOW -> HIGH`，随后执行高风险流程。
5. 中间未经过 MEDIUM 时，默认不执行中风险流程；是否补执行被跳过级别的动作，留到 ECA 动作策略阶段决定。

当前引擎已经支持模型提供的 `track_id`；模型未提供时，会按同摄像头、同目标类型、时间窗口和检测框 IoU 尝试关联。因此同一画面正常连续移动时可以保持为一个目标，但遮挡、长时间丢失或模型重新编号仍可能造成换 ID。重构时需要保留：

- 跟踪 ID 优先关联。
- 短时间丢失宽限期。
- IoU/位置/时间二次关联。
- 事件关闭前的重复事件抑制。

当前阶段只保证同一摄像头内的连续跟踪；跨摄像头识别同一个人需要 ReID 能力，不纳入本阶段。

## 9. `data_source` 决定与待处理问题

`data_source` 第一阶段保持现有字段：

- `id`
- `source_name`
- `source_type`
- `device_id`
- `data_path`
- `description`
- `is_activate`
- `create_time`
- `update_time`

约定：

- 摄像头可以作为数据源。
- 当 `source_type = camera` 时，`device_id` 保存 `camera_device.id`。
- 广播是动作执行端，不进入 `data_source`。

结构风险：如果传感器的 `device_id` 没有统一设备表，而摄像头的 `device_id` 指向 `camera_device.id`，这个字段只能做逻辑关联，MySQL 无法让同一列按 `source_type` 外键到不同表。这个问题先记录，在 ECA 与传感器表设计阶段决定使用以下哪一种方案：

- 为摄像头增加独立的 `camera_id` 外键字段。
- 为不同来源建立独立绑定表。
- 等传感器设备表确定后，再建立统一来源引用方案。

在该问题确定前，不给 `data_source.device_id` 添加错误的物理外键。

## 10. 后续 ECA 与事件设计预留

已确认的需求：

- 同一种事件可按 LOW/MEDIUM/HIGH 关联不同 `action_flow`。
- 例如人员涉水：低风险自动广播；中风险无人机调度和自动广播；高风险创建人工派出任务。
- 无人机返回图片后，作为事件佐证展示给用户。
- 用户可以标记误报。
- 用户可以手动升级风险；风险修改必须记录操作人、修改前后级别、时间和原因。
- 事件需保存完整的风险变化、动作执行、任务和佐证时间线。

后续重点设计：

- 事件定义与风险级别如何关联动作流程。
- ECA 条件如何引用摄像头目标观测变量。
- 安全事件主表的保留/删除字段。
- 动作执行日志、人工派单和佐证表。
- `alarm` 如何迁入统一安全事件并保持原告警列表 API 兼容。

## 11. 最终实施原则

整体数据库框架确认前不修改生产表。实施时按以下原则执行：

1. 以实际 MySQL 结构建立迁移基线。
2. 使用版本化迁移管理所有建表、改列、数据回填和外键。
3. SQLAlchemy 模型与迁移后的实际表逐字段核对。
4. 生产启动流程不再用零散的 `create_all + ALTER TABLE` 代替正式迁移。
5. 先迁移数据和兼容 API，再切换前端，最后删除旧字段和旧表。
