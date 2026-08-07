# box_system 数据库融合最终设计

更新时间：2026-08-06

本文是当前业务数据库融合的最终口径。早期草案中提到的 `alarm`、`camera_broadcast_device`、`camera_zone_condition`、`action_flow`、`action_step`、旧动作执行 `event_action`、`event_action_step_config` 已不再作为目标结构使用；实际状态以本文、ORM 和已执行迁移为准。

## 1. 总体链路

```text
data_source
  -> condition_library
  -> event_condition -> event_library
  -> event_action
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

模板只保存播报文本和场景信息；具体哪个事件使用哪个模板，由 `event_action.template_id` 决定。

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

条件库。视觉业务将 `time_window` 和 `duration` 都解释为秒。

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

### 2.9 `event_action`

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
- `zone_id`
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
- `zone_id` 可选关联 `camera_detection_zone.id`，用于当前区域查询；历史展示名称仍以快照为准。
- 摄像头名称可通过 `data_source_id -> data_source -> camera_device` 获取。
- 区域名称、对象类型、置信度、bbox 等视觉展示快照保存在 `latest_observation.visual`。

### 2.11 `safety_event_timeline_log`

统一事件时间线。

核心字段：

- `id`
- `event_instance_id`
- `event_id`
- `condition_id`
- `event_action_id`
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

### 2.12 `safety_event_evidence`

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

### 2.13 `safety_event_task`

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

### 2.14 `analysis_report`

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

## 3. 已删除结构

已删除或不再使用：

- `alarm`
- `camera_broadcast_device`
- `camera_zone_condition`
- 旧版 `event_action`
- `action_flow`
- `action_step`
- `event_action_step_config`
- `event_action_config`
- `visual_event_detail`
- `schema_migration`
- 旧 `safety_event`
- 旧 `safety_event_log`
- 旧 `event_log`
- `sys_device`
- `sys_trigger_rule`
- 区域 rect、旧绘制 ID、区域表触发时间、重复风险字段

对应迁移脚本：

- `dam-backend/scripts/migrate_20260806_event_action_config_consolidation.py`
- `dam-backend/scripts/migrate_20260806_event_runtime_simplification.py`
- `dam-backend/scripts/migrate_20260806_phase3_cleanup.py`
- `dam-backend/scripts/drop_schema_migration.py`
- `dam-backend/scripts/migrate_20260807_timeline_event_action_id_seconds.py`

迁移脚本执行前必须只读审计，执行时必须备份被删除表和关键数据。

## 4. 旧接口处理状态

### 4.1 已替代

- 旧动作配置接口已切到 `event_action`。
- 摄像头广播绑定接口已删除，广播设备由事件动作配置选择。
- 区域保存接口不再保存逐区域触发时间。
- 旧 `/api/alarm/*` 后端兼容路由已删除；Dashboard 和告警入口直接读取统一安全事件接口。

## 5. 视觉业务口径

当前业务不对具体某个人或某条船做精细停留统计，而是按区域聚合：

- 人员事件：区域内持续出现人员达到条件时触发。
- 船只事件：捕鱼区内持续出现船只达到条件时触发或升级。
- 人和船必须区分，区分依据优先为事件码和事件分类。
- `condition_library` 不增加 `zone_id/object_type`，避免变成“每个摄像头每个区域一套条件”。
- 触发时长按区域类型背后的事件码配置，例如人员闯入区对应 `PERSON_INTRUSION.duration`。
- 同一类型区域共用触发时长；如果 1 号摄像头和 2 号摄像头都画了“人员闯入区”，默认使用同一条条件时长。
- `zone_id` 只进入 `safety_event_instance`，用于事件追溯、筛选和详情展示。

区域删除策略：

- 测试期允许物理删除区域。
- 历史事件展示不能依赖区域表一定存在；关键展示快照应保存在 `latest_observation.visual` 或时间线 `payload`。

## 6. 第三阶段执行结果

第三阶段已完成以下收口：

1. `event_action_config` 已重命名为 `event_action`，时间线 `event_action_id` 外键指向 `event_action.id`。
2. `safety_event_instance` 增加 `zone_id` 外键，视觉详情快照统一放入 `latest_observation.visual`。
3. `visual_event_detail` 已备份并删除，运行时详情、巡查报告、人工升级判断和列表筛选不再读取该表。
4. 旧 `/api/alarm/*`、前端 `src/api/alarm.js`、旧告警列表/报告页面已删除；`/alarm/list` 路由重定向到 `/alarm/safety-events`。
5. 摄像头广播绑定接口已删除；设备管理和小程序只展示全局可用广播设备。

已执行迁移：

- `dam-backend/scripts/migrate_20260806_phase3_cleanup.py --apply`
- `dam-backend/scripts/drop_schema_migration.py --apply`
- `dam-backend/scripts/migrate_20260807_timeline_event_action_id_seconds.py --apply`
- 备份文件：
  - `backups/phase3_cleanup_20260806_132743.json`
  - `backups/schema_migration_drop_20260806_134220.json`
  - `backups/timeline_event_action_id_seconds_20260807_113034.json`

历史迁移脚本仍保留用于审计已发生的结构变化，不作为新库初始化目标。

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
