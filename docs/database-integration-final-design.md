# box_system 数据库融合最终设计

更新时间：2026-08-06

本文是当前业务数据库融合的最终口径。早期草案中提到的 `alarm`、`camera_broadcast_device`、`camera_zone_condition`、`action_flow`、`action_step`、`event_action`、`event_action_step_config` 已不再作为目标结构使用；实际状态以本文、ORM 和已执行迁移为准。

## 1. 总体链路

```text
data_source
  -> condition_library
  -> event_condition -> event_library
  -> event_action_config
  -> safety_event_instance
       -> safety_event_timeline_log
       -> safety_event_evidence
       -> safety_event_task
       -> analysis_report（可选，仅事件报告）
```

业务原则：

- 数据源是感知入口；摄像头、传感器通过 `data_source.source_type + device_id` 定位。
- 广播、无人机、人工任务是动作执行目标，不进入 `data_source`。
- 摄像头和广播不再绑定；摄像头触发事件后，按事件动作配置选择广播设备和模板。
- 事件、条件、动作配置按事件类型统一管理，尽量不按具体设备/区域拆过细配置。
- 运行事件统一进入 `safety_event_instance`，页面告警列表和安全事件列表都应从该表展示。

## 2. 当前保留表

### 2.1 `camera_device`

摄像头设备台账。`id` 是唯一摄像头标识，前后端所有摄像头路径参数均指该主键。

核心字段：

- `id`
- `camera_name`
- `brand`
- `ip_address`
- `rtsp_port`
- `web_port`
- `username`
- `password`
- `install_address`
- `longitude`
- `latitude`
- `description`
- `enabled`
- `last_error`
- `rtsp_path`
- `last_online_at`
- `create_time`
- `update_time`

旧字符串业务 ID 不再保留。

### 2.2 `broadcast_device`

广播设备台账。当前不保存摄像头绑定关系。

核心字段：

- `id`
- `name`
- `description`
- `enabled`
- `create_time`
- `update_time`

### 2.3 `broadcast_template`

广播模板库。

核心字段：

- `id`
- `name`
- `scene_type`
- `risk_level`
- `content`
- `enabled`
- `create_time`
- `update_time`

模板只保存播报文本和场景信息；具体哪个事件使用哪个模板，由 `event_action_config.template_id` 决定。

### 2.4 `camera_detection_zone`

摄像头检测区域表，只保存区域几何和启停，不保存触发时间。

核心字段：

- `id`
- `camera_device_id`
- `zone_name`
- `zone_type`
- `polygon_points`
- `enabled`
- `create_time`
- `update_time`

区域类型固定为：

- `PERSON_LOW`：页面展示“人员闯入区”
- `PERSON_MEDIUM`：页面展示“人员亲水区”
- `PERSON_HIGH`：页面展示“人员涉水区”
- `FISHING`：页面展示“捕鱼监测区”

触发时间统一在 `condition_library.duration` 中按事件码配置，不按具体 `zone_id` 配置。

### 2.5 `data_source`

统一感知入口。

核心字段：

- `id`
- `source_name`
- `source_type`
- `device_id`
- `data_path`
- `description`
- `is_activate`
- `create_time`
- `update_time`

解释规则：

- `source_type=camera` 时，`device_id` 指向 `camera_device.id`。
- `source_type=sensor` 时，`device_id` 保存当前传感器逻辑设备 ID。
- 查询和唯一性判断必须同时使用 `source_type + device_id`。
- MySQL 不给 `device_id` 建多态物理外键，合法性由后端保证。

### 2.6 `condition_library`

条件库。视觉业务将 `duration` 解释为“持续秒数”。

核心字段：

- `id`
- `condition_name`
- `source_id`
- `expression`
- `time_window`
- `duration`
- `description`
- `is_activate`
- `create_time`
- `update_time`

视觉条件当前保留 6 条业务条件：

| 事件码 | 表达式 | 默认持续时间 |
| --- | --- | ---: |
| `PERSON_INTRUSION` | `person_present == 1` | 5 秒 |
| `PERSON_WATERFRONT` | `person_present == 1` | 3 秒 |
| `PERSON_WADING` | `person_present == 1` | 0 秒 |
| `BOAT_INTRUSION` | `boat_present == 1` | 0 秒 |
| `BOAT_STAY` | `boat_present == 1` | 30 秒 |
| `BOAT_ILLEGAL_FISHING` | `boat_present == 1` | 120 秒 |

条件说明使用 `[VISUAL_ECA:{event_code}]` 标记。旧 `[ZONE_ECA:*]` 和旧 `*_PRESENT` 条件已清理。

### 2.7 `event_library`

事件库。

核心字段：

- `id`
- `event_name`
- `event_code`
- `event_category`
- `risk_level`
- `trigger_mode`
- `description`
- `route_role_id`
- `is_activate`
- `create_time`
- `update_time`

`route_role_id` 是逻辑外键，用于对接智能路由角色库，不建立物理外键。

事件库只新增必要配置：角色逻辑 ID 和启停。是否在某时期启用某个事件类型，用 `is_activate` 控制；如果后续需要按时间段启用策略，再单独设计策略版本表，不提前塞进事件库。

### 2.8 `event_condition`

事件与条件关系。

核心字段：

- `id`
- `event_id`
- `condition_id`
- `logic_type`
- `group_id`
- `sort_order`
- `create_time`

### 2.9 `event_action_config`

事件动作配置表，替代旧 `event_action/action_flow/action_step/event_action_step_config` 四表。

核心字段：

- `id`
- `event_id`
- `step_order`
- `action_type`
- `action_name`
- `model_id`
- `parameter`
- `retry_count`
- `timeout_seconds`
- `failure_strategy`
- `broadcast_device_id`
- `template_id`
- `drone_id`
- `route_id`
- `repeat_interval_seconds`
- `max_executions`
- `config_json`
- `is_activate`
- `create_time`
- `update_time`

解释：

- 一行表示某个事件的一个动作步骤。
- 前端按 `event_id + step_order` 展示流程。
- 广播设备、模板、无人机、航线、重复策略等直接放在本表。
- 少量不稳定配置放 `config_json`。
- 不再拆抽象流程表和步骤表。

### 2.10 `safety_event_instance`

统一安全事件实例表，也是告警列表的数据事实表。

核心字段：

- `id`
- `instance_no`
- `current_event_id`
- `analysis_report_id`
- `event_category`
- `data_source_id`
- `source_type`
- `source_id`
- `risk_level`
- `max_risk_level`
- `state`
- `status`
- `started_at`
- `last_observed_at`
- `resolved_at`
- `resolve_reason`
- `summary`
- `latest_observation`
- `version`
- `create_time`
- `update_time`

说明：

- `state` 表示生命周期：`ACTIVE/RESOLVED`。
- `status` 表示处置进度：`PENDING/PROCESSING/COMPLETED/FALSE_ALARM`。
- `analysis_report_id` 可选关联事件闭环分析报告；日报/月报不一定关联事件实例。
- 摄像头名称可通过 `data_source_id -> data_source -> camera_device` 获取。
- 区域、对象类型、置信度等视觉运行信息当前仍在 `visual_event_detail` 和 `latest_observation` 中并存，第三阶段准备收敛。

### 2.11 `visual_event_detail`（第三阶段待清理）

当前仍保留，因为运行时详情、巡查报告和人工升级判断还直接读取它。

核心字段：

- `id`
- `event_instance_id`
- `camera_id`
- `camera_name`
- `target_type`
- `target_id`
- `zone_id`
- `zone_name`
- `zone_type`
- `confidence`
- `extra`
- `create_time`
- `update_time`

第三阶段目标不是简单删表，而是先替代调用方：

- `camera_id/camera_name` 改由 `data_source_id/source_id` 推导。
- `target_type` 尽量由 `event_category/event_code` 推导；必要快照放入 `latest_observation.visual.target_type`。
- `zone_id` 如需查询可提升到 `safety_event_instance.zone_id`，历史展示快照放 `latest_observation.visual.zone_name/zone_type`。
- `confidence/bbox/model/frame_time` 放入 `latest_observation.visual`。

完成替代和迁移后再备份并删除本表。

### 2.12 `safety_event_timeline_log`

统一事件时间线。

核心字段：

- `id`
- `event_instance_id`
- `event_id`
- `condition_id`
- `action_config_id`
- `action_key`
- `stage`
- `log_type`
- `trigger_type`
- `risk_level`
- `status`
- `title`
- `message`
- `operator`
- `payload`
- `create_time`
- `update_time`

固定阶段用于前端进度条：

- `TRIGGER`
- `DISPATCH`
- `PROCESSING`
- `REPORT`
- `CLOSE`

`payload` 保存当时动作参数、配置快照、设备名、模板名、错误信息等历史信息，避免配置改名影响历史展示。

### 2.13 `safety_event_evidence`

统一证据表。

核心字段：

- `id`
- `event_instance_id`
- `timeline_log_id`
- `task_id`
- `evidence_type`
- `source_type`
- `source_id`
- `file_url`
- `description`
- `metadata`
- `captured_at`
- `create_time`

摄像头截图、视频、无人机图片、人工现场图片都进入该表。

### 2.14 `safety_event_task`

人工处置任务表。

核心字段：

- `id`
- `event_instance_id`
- `dispatch_operator`
- `assignee`
- `task_status`
- `task_note`
- `dispatched_at`
- `accepted_at`
- `completed_at`
- `result_type`
- `result_remark`
- `create_time`
- `update_time`

### 2.15 `analysis_report`

报告归档表，只保存检索和下载需要的信息。

核心字段：

- `id`
- `report_no`
- `report_title`
- `report_type`
- `report_date`
- `file_url`
- `create_time`

`report_type` 当前约定：

- `event`：事件闭环分析报告
- `daily`：日报
- `monthly`：月报

报告正文、图片、排版文件保存在 MinIO，不写入数据库长文本。

### 2.16 `schema_migration`

手写迁移脚本的幂等记录表。

当前保留。原因是第二阶段仍在连续迁移，直接删除会降低迁移脚本的可重复执行能力。等表结构稳定后，再评估是否把它从业务库中移走或废弃。

## 3. 已删除结构

已删除或不再使用：

- `alarm`
- `camera_broadcast_device`
- `camera_zone_condition`
- `event_action`
- `action_flow`
- `action_step`
- `event_action_step_config`
- 旧 `safety_event`
- 旧 `safety_event_log`
- 旧 `event_log`
- `sys_device`
- `sys_trigger_rule`
- 区域 rect、旧绘制 ID、区域表触发时间、重复风险字段

对应迁移脚本：

- `dam-backend/scripts/migrate_20260806_event_action_config_consolidation.py`
- `dam-backend/scripts/migrate_20260806_event_runtime_simplification.py`

迁移脚本执行前必须只读审计，执行时必须备份被删除表和关键数据。

## 4. 旧接口处理状态

### 4.1 已替代

- 旧动作配置接口已切到 `event_action_config`。
- 摄像头广播绑定接口不再作为业务配置入口。
- 区域保存接口不再保存逐区域触发时间。

### 4.2 暂时兼容

`/api/alarm/*` 仍存在，但只是兼容层：

- `/api/alarm/list` 从 `safety_event_instance` 映射旧告警字段。
- `/api/alarm/statistics` 从 `safety_event_instance` 统计。
- `/api/alarm/{id}/handle` 更新统一事件实例并写时间线。

第三阶段后半段应把前端 Dashboard、`AlarmList.vue`、`AlarmReport.vue` 和 `src/api/alarm.js` 改为直接使用统一安全事件接口，然后删除该兼容层。

## 5. 视觉业务口径

当前业务不对具体某个人或某条船做精细停留统计，而是按区域聚合：

- 人员事件：区域内持续出现人员达到条件时触发。
- 船只事件：捕鱼区内持续出现船只达到条件时触发或升级。
- 人和船必须区分，区分依据优先为事件码和事件分类。
- `condition_library` 不增加 `zone_id/object_type`。
- 触发时长由信息配置页修改对应事件条件的 `duration`，全局生效。

区域删除策略：

- 测试期允许物理删除区域。
- 历史事件展示不能依赖区域表一定存在；关键展示快照应保存在 `latest_observation.visual` 或时间线 `payload`。

## 6. 第三阶段计划

第三阶段目标是清理旧残余，同时保证系统完整运行。

### 6.1 第一小阶段：收敛 `visual_event_detail`

执行顺序：

1. 全局审计 `VisualEventDetail/visual_event_detail` 调用方。
2. 给 `safety_event_instance` 增加必要的少量字段，优先只考虑 `zone_id`；对象类型尽量通过事件码推导，快照放 `latest_observation.visual`。
3. 修改运行时写入逻辑：新事件不再创建 `visual_event_detail`，改为写实例字段和 `latest_observation.visual`。
4. 修改详情接口、巡查报告、人工升级判断、事件列表筛选，全部不再读取 `visual_event_detail`。
5. 写迁移脚本，将旧 `visual_event_detail` 备份并回填到实例快照。
6. 只读审计确认无代码引用后，再删除表和 ORM。
7. 跑后端编译、事件接口导入、相关单测和前端构建。

不建议一次性把大量视觉字段都加到实例表。实例表只放查询和关联必要字段；展示快照放 JSON。

### 6.2 第二小阶段：删除旧告警兼容入口

执行顺序：

1. Dashboard 最近告警和统计改用统一安全事件接口。
2. `/alarm/list` 页面改为重定向或移除，保留 `/alarm/safety-events` 作为主入口。
3. `AlarmReport.vue` 若仍需要，改为基于 `analysis_report` 或安全事件详情展示。
4. 删除 `src/api/alarm.js` 和 `/api/alarm` 后端兼容路由。
5. 清理 `alarm:*` 缓存 key 命名，统一为 `safety_event:*` 或 `integration:*`。
6. 搜索确认无 `/api/alarm` 调用后再删除后端文件和 schema。

这一步删除的是旧接口，不再涉及已删除的 `alarm` 表。

### 6.3 第三小阶段：复核迁移残余

- 审计旧迁移脚本是否仍需保留。
- 评估 `schema_migration` 是否继续保留。
- 清理只用于旧方案的文档草案或标记为历史资料。
- 保留必要备份文件，不在未确认前删除备份。

## 7. 验证要求

每次数据库结构调整必须满足：

1. 修改代码前先全局搜索旧表、旧接口、旧字段引用。
2. 删除表前必须先让应用代码不再依赖该表。
3. 迁移脚本默认只读审计，显式 `--apply` 才执行。
4. 迁移脚本必须写备份。
5. 执行后再次审计表、字段、记录数和关键条件。
6. 后端至少通过 `compileall` 和应用导入检查。
7. 前端必须通过生产构建。
8. 与改动相关的单测必须通过；如果测试工具不可用，需要说明原因并使用可行替代。

## 8. 禁止恢复

- 不得恢复旧 `alarm` 表。
- 不得恢复摄像头广播绑定表。
- 不得恢复区域条件绑定表。
- 不得恢复旧动作四表。
- 不得恢复区域表触发时间。
- 不得恢复旧安全事件双轨表。
- 不得让页面展示依赖已删除旧表。
