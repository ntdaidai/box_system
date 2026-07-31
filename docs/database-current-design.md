# box_system 前后端数据库现状

本文基于当前运行中的 MySQL `dam_system`、`dam-backend/app/models` 和前端 API 使用关系整理。前端不直接访问数据库，所有业务数据经由 `dam-backend/app/api/*` 访问。

## 1. 存储边界

当前系统不是单一 MySQL：

- MySQL `dam_system`：业务配置、告警、摄像头、安全事件、ECA、模型库/工作流元数据。
- IoTDB：传感器时序数据，路径形如 `root.dam.sensor.{device_id}`，以及历史聚合 rollup 路径。
- MinIO：文档、图片、告警快照、视频证据等对象文件。
- Redis：缓存、限流、运行态辅助数据。
- SQLite：后端本地 `sensor_pending.sqlite3`，用于 IoTDB 写入失败时的待补偿队列。

## 2. 核心业务表

### sys_user 用户表

用途：系统用户、默认管理员、旧登录接口兼容。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 用户 ID |
| username | varchar(50) unique | 用户名 |
| password | varchar(255) | bcrypt 哈希密码 |
| real_name | varchar(50) | 真实姓名 |
| phone | varchar(20) | 手机号 |
| email | varchar(100) | 邮箱 |
| role | varchar(20) | 角色，`admin/user` |
| status | int | 状态，1 启用，0 禁用 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |

关系：目前没有外键引用它，很多操作人字段用字符串保存用户名。

### alarm 告警表

用途：告警中心展示、处理状态、统计；ECA 和视频安全事件都会同步到这里。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 告警 ID |
| alarm_code | varchar(64) | 告警编码；视频安全事件里通常等于 `safety_event.event_id` |
| device_id | int | 关联设备 ID，当前无外键 |
| alarm_type | varchar(32) | `threshold/manual/ai` |
| alarm_level | int | 1 低，2 中，3 高 |
| alarm_content | text | 告警内容 |
| alarm_time | datetime | 告警触发时间 |
| handle_status | int | 0 未处理，1 已处理 |
| handle_user | varchar(50) | 处理人 |
| handle_time | datetime | 处理时间 |
| handle_remark | varchar(500) | 处理备注 |
| create_time | datetime | 创建时间 |

关系：`alarm.alarm_code` 与 `safety_event.event_id` 是业务约定关系，不是外键。

### analysis_report 分析报告表

用途：AI 分析报告、日报、人工报告。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 报告 ID |
| report_title | varchar(200) | 标题 |
| report_type | varchar(32) | `vision/manual/daily` |
| risk_level | varchar(16) | `low/medium/high/critical` |
| content | text | Markdown 内容 |
| ai_model | varchar(64) | 使用的模型 |
| create_time | datetime | 创建时间 |

关系：独立记录表，目前没有强外键。

### actor_library 角色库

用途：灾害分析、安全专家、水文专家等 Prompt 角色配置。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 主键 |
| actor_name | varchar(128) unique | 角色名称 |
| description | varchar(512) | 描述 |
| local_system_prompt | text | 边缘模型系统提示词 |
| cloud_system_prompt | text | 云端模型系统提示词 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |

关系：当前更像配置库，尚未和模型执行链建立强外键。

## 3. 设备与摄像头

### camera_device 摄像头台账

用途：摄像头设备管理、RTSP/Web 控制台代理、监测页面摄像头列表。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 主键 |
| camera_id | varchar(64) unique | 摄像头业务 ID |
| camera_name | varchar(128) | 摄像头名称 |
| brand | varchar(32) | `dahua/hikvision` |
| ip_address | varchar(128) | IP 地址 |
| rtsp_port | int | RTSP 端口 |
| web_port | int | Web 控制台端口 |
| web_proxy_port | int unique | 后端代理监听端口 |
| username | varchar(128) | 登录账号 |
| password | varchar(256) | 登录密码 |
| rtsp_path | varchar(256) | RTSP 通道路径 |
| description | text | 描述 |
| enabled | tinyint | 是否启用 |
| last_online_at | datetime | 最近在线时间 |
| last_error | text | 最近错误 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |

关系：`camera_id` 被 `camera_detection_zone`、`safety_event`、`camera_broadcast_device`、`event_action` 以字符串引用，但多数没有外键。

注意：代码模型里还有 `install_address/latitude/longitude`，实际库当前没有这些列。

### camera_detection_zone 摄像头检测区域

用途：每个摄像头的视频画面上配置警戒区/亲水区/涉水区。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 区域 ID |
| camera_id | varchar(64) | 摄像头 ID |
| zone_name | varchar(80) | 区域名称 |
| zone_type | varchar(32) | `warning_zone/waterside_zone/wading_zone` |
| rect_x | decimal(8,6) | 矩形左上角 X，归一化 |
| rect_y | decimal(8,6) | 矩形左上角 Y，归一化 |
| rect_width | decimal(8,6) | 宽度，归一化 |
| rect_height | decimal(8,6) | 高度，归一化 |
| enabled | tinyint | 是否启用 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| zone_id | varchar(64) | 前端绘制区域 ID |
| polygon_points | json | 多边形点位 |
| risk_level | varchar(16) | `LOW/MEDIUM/HIGH` |
| trigger_seconds | decimal(8,3) | 持续触发秒数 |

关系：归属 `camera_device.camera_id`，但当前无外键。

### broadcast_device 广播设备

用途：本地音频/USB 广播设备台账。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 主键 |
| name | varchar(128) | 名称 |
| vendor_type | varchar(64) | 供应商/设备类型 |
| device_code | varchar(128) unique | 设备编码 |
| ip | varchar(64) | IP |
| port | int | 端口 |
| username | varchar(128) | 账号 |
| password | varchar(256) | 密码 |
| status | varchar(32) | 状态 |
| location | varchar(255) | 位置 |
| enabled | tinyint | 是否启用 |
| config_json | json | 扩展配置 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |

### camera_broadcast_device 摄像头-广播设备绑定

用途：指定摄像头触发风险时使用哪些广播设备。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 主键 |
| camera_id | varchar(64) | 摄像头 ID |
| broadcast_device_id | bigint | 广播设备 ID |
| create_time | datetime | 创建时间 |

关系：应连接 `camera_device.camera_id` 和 `broadcast_device.id`，当前无外键。

### broadcast_template 广播模板

用途：不同风险等级/场景的语音播报内容。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(64) PK | 模板 ID |
| name | varchar(128) | 模板名称 |
| risk_level | varchar(32) | 风险等级 |
| scene_type | varchar(64) | 场景类型 |
| content | text | 播报文本 |
| enabled | tinyint | 是否启用 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |

## 4. 视频安全事件闭环

业务链路：

`camera_device` → 视频检测 → `safety_event` → `safety_event_log` / `safety_event_task` / `event_action` → 同步 `alarm` → 前端安全闭环、告警中心、小程序。

### safety_event 安全事件主表

用途：一次人员/船只等目标进入危险区域后的完整事件生命周期。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 主键 |
| event_id | varchar(64) unique | 事件唯一编号 |
| camera_id | varchar(64) | 摄像头 ID |
| entity_type | varchar(32) | `person/boat` |
| track_id | varchar(128) | 跟踪 ID |
| state | varchar(32) | 引擎状态 |
| risk_level | varchar(16) | 当前风险等级 |
| started_at | datetime | 事件开始 |
| first_seen_at | datetime | 首次发现 |
| danger_started_at | datetime | 进入危险区域时间 |
| last_seen_at | datetime | 最近看到目标 |
| low_entered_at | datetime | 进入低风险时间 |
| missing_since | datetime | 丢失开始时间 |
| clear_since | datetime | 离开危险区开始时间 |
| resolved_at | datetime | 关闭时间 |
| resolve_reason | varchar(64) | 关闭原因 |
| snapshot_url | varchar(512) | 快照地址 |
| zone_type | varchar(32) | 触发区域类型 |
| zone_name | varchar(80) | 触发区域名称 |
| zone_ids | json | 触发区域 ID 列表 |
| latest_bbox | json | 最近目标框 |
| latest_observation | json | 最近观测 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| status | varchar(32) | 闭环状态 |
| event_type | varchar(64) | 事件类型 |
| camera_name | varchar(128) | 摄像头名称快照 |
| video_url | varchar(512) | 留证视频地址 |
| duration_seconds | int | 持续秒数 |
| ack_operator | varchar(128) | 确认人 |
| ack_at | datetime | 确认时间 |
| resolved_operator | varchar(128) | 解除人 |
| false_alarm_operator | varchar(128) | 误报确认人 |
| false_alarm_reason | varchar(500) | 误报原因 |
| version | int | 乐观锁版本 |
| max_risk_level | varchar(16) | 最高风险等级 |
| handling_mode | varchar(32) | `AUTO/AUTO_DEVICE/MANUAL` |
| disposal_status | varchar(32) | 处置状态 |
| target_status | varchar(32) | 目标状态 |
| medium_entered_at | datetime | 进入中风险时间 |
| video_status | varchar(32) | 视频证据状态 |
| video_error | varchar(500) | 视频失败原因 |
| video_created_at | datetime | 视频生成时间 |
| video_expires_at | datetime | 视频过期时间 |

### safety_event_log 安全事件动作日志

用途：记录确认、广播、派单、解除、误报等动作。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 日志 ID |
| action_id | varchar(64) unique | 动作唯一编号 |
| event_id | varchar(64) | 安全事件 ID |
| action_type | varchar(64) | 动作类型 |
| risk_level | varchar(16) | 风险等级 |
| status | varchar(16) | 执行状态 |
| message | varchar(255) | 动作说明/失败原因 |
| payload | json | 动作上下文 |
| create_time | datetime | 创建时间 |
| update_time | datetime | 更新时间 |
| from_status | varchar(32) | 操作前状态 |
| to_status | varchar(32) | 操作后状态 |
| operator | varchar(128) | 操作人 |
| operator_role | varchar(64) | 操作人角色 |

### safety_event_task 派单任务

用途：现场处置任务。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | bigint PK | 任务 ID |
| event_id | varchar(64) | 安全事件 ID |
| assignee | varchar(128) | 现场处置人员 |
| assignee_phone | varchar(64) | 电话 |
| dispatch_operator | varchar(128) | 派单人 |
| task_status | varchar(32) | 任务状态 |
| task_note | varchar(500) | 说明 |
| dispatched_at | datetime | 派单时间 |
| completed_at | datetime | 完成时间 |
| accepted_at | datetime | 接单时间 |

## 5. ECA 规则体系

业务链路：

`data_source` 定义数据来源 → `condition_library` 定义判断条件 → `event_library` 定义业务事件 → `event_condition` 组合事件条件 → `action_flow` 定义处置流程 → `action_step` 定义步骤 → `event_action` 把事件绑定到流程 → `event_log` 记录触发历史。

### data_source 数据源

字段：`id`、`source_name`、`source_type`、`device_id`、`data_path`、`description`、`is_activate`、`create_time`、`update_time`。

### condition_library 条件库

字段：`id`、`condition_name`、`source_id`、`expression`、`time_window`、`duration`、`description`、`is_activate`、`create_time`、`update_time`。

关系：`condition_library.source_id -> data_source.id`。

### event_library 事件库

字段：`id`、`event_name`、`event_code`、`event_category`、`risk_level`、`trigger_mode`、`description`、`is_activate`、`create_time`、`update_time`。

### event_condition 事件-条件关系

字段：`id`、`event_id`、`condition_id`、`logic_type`、`group_id`、`sort_order`、`create_time`。

关系：`event_id -> event_library.id`，`condition_id -> condition_library.id`。

### action_flow 行为流程

字段：`id`、`flow_name`、`flow_code`、`timeout_seconds`、`failure_strategy`、`description`、`is_activate`、`create_time`、`update_time`。

### action_step 行为步骤

字段：`id`、`flow_id`、`step_order`、`step_name`、`action_type`、`model_id`、`parameter`、`retry_count`、`description`、`create_time`、`update_time`。

关系：`flow_id -> action_flow.id`，`model_id -> model_library.id`。

### event_action 事件-行为/动作审计混合表

字段：`id`、`event_id`、`flow_id`、`priority`、`is_activate`、`create_time`、`action_type`、`broadcast_event_id`、`camera_id`、`device_id`、`template_id`、`trigger_type`、`content`、`start_time`、`end_time`、`result`、`error_message`、`operator`、`risk_level`、`drone_id`、`strategy_id`、`dispatch_time`。

关系：

- 旧 ECA 用法：`event_id -> event_library.id`，`flow_id -> action_flow.id`。
- 新闭环用法：作为广播/无人机/人工处置动作记录，使用 `broadcast_event_id` 指向 `safety_event.event_id`。

注意：这是当前最混乱的表之一，一个表同时承担“配置关系”和“动作流水”。

### event_log 事件触发记录

字段：`id`、`event_id`、`trigger_time`、`trigger_data`、`conditions_met`、`status`、`result`、`create_time`。

关系：`event_id -> event_library.id`。

## 6. 模型库与工作流表

### model_library 老模型表

用途：ECA `action_step.model_id` 当前引用它。

字段：`id`、`model_name`、`model_type`、`api_url`、`description`、`is_activate`、`create_time`、`update_time`。

### model_registry 新模型注册表

用途：模型库服务的主表。

字段：`id`、`name`、`description`、`tags`、`framework`、`architecture`、`model_type`、`model_size`、`runtime_status`、`owner_id`、`create_time`、`update_time`。

### model_deploy_binding 模型部署绑定

字段：`id`、`model_id`、`bind_type`、`container_id`、`container_name`、`image_name`、`host_ip`、`host_port`、`container_port`、`inference_path`、`health_check_url`、`gpu_device`、`extra_mounts`、`extra_env`、`container_config`、`remark`、`create_time`、`update_time`。

关系：`model_id -> model_registry.id`。

### model_io_schema 模型输入输出 Schema

字段：`id`、`model_id`、`inputs`、`outputs`、`create_time`、`update_time`。

关系：`model_id -> model_registry.id`。

### model_operation_log 模型操作日志

字段：`id`、`model_id`、`operator_id`、`operation`、`detail`、`result`、`error_msg`、`create_time`。

关系：`model_id -> model_registry.id`。

### model_event_mapping 工作流事件-模型映射

字段：`id`、`event_type`、`task_type`、`model_category`、`model_id`、`priority`、`remark`、`create_time`、`update_time`。

注意：实际库 `model_category` 是 `specialized/llm`，工作流脚本/代码倾向 `specialized/local_llm/cloud_llm`，需要统一。

### model_evaluation_template 评价 Prompt 模板

字段：`id`、`template_name`、`event_type`、`prompt_template`、`input_schema`、`output_schema`、`is_active`、`create_time`、`update_time`。

### model_io_template IO 配对模板

字段：`id`、`template_name`、`event_type`、`source_model_category`、`target_model_category`、`source_task_type`、`target_task_type`、`field_mapping`、`create_time`、`update_time`。

## 7. 当前最混乱的点

1. `event_action` 同时是 ECA 配置表和安全事件动作流水表，建议拆成 `event_flow_binding` 和 `event_action_log`。
2. `alarm` 与 `safety_event` 都表达风险事件，一个偏告警列表，一个偏闭环生命周期，建议统一主事件模型，告警做视图或轻量派生表。
3. `model_library` 与 `model_registry` 是两套模型台账，建议保留 `model_registry`，迁移 ECA 的 `action_step.model_id` 指向它。
4. 摄像头、传感器、广播设备分散，`camera_device`、`broadcast_device`、后端代码里的 `sys_device` 没统一设备主数据。
5. 多数业务关系靠字符串约定，没有外键，例如 `camera_id`、`event_id`、`operator`。
6. 启动时 `create_all + ALTER TABLE` 和 SQL 脚本并存，缺少正式迁移链，导致代码定义、脚本定义、实际库结构不一致。

## 8. 建议的新设计方向

建议先定 5 个主域：

1. 设备域：统一设备主表 `device`，摄像头/广播/传感器做扩展表。
2. 事件域：统一事件实例 `incident`，把 `alarm` 和 `safety_event` 融进去。
3. 处置域：统一动作日志 `incident_action_log`、任务表 `incident_task`、广播记录表。
4. 规则域：保留 ECA 配置，但把配置关系和执行日志拆开。
5. 模型域：统一到 `model_registry`，废弃或兼容迁移 `model_library`。

