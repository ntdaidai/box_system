# box_system 数据库融合设计报告

更新时间：2026-08-02

## 1. 设计范围

本次只调整设备配置、ECA 和安全事件闭环相关表。

当前实施采用分阶段迁移：新表、新字段和新接口已启用；确认无数据、无外键和无页面引用的旧结构已经清理，仍有运行调用方的结构继续兼容。实际状态见第 7 节。

不调整：用户表、模型库、工作流表、分析报告表和现有 `alarm` 告警表。`action_step.model_id` 保持可空，作为以后与模型功能结合的预留点。

统一业务链路：

```text
数据源 -> 条件库 -> 事件库 -> 事件行为 -> 行为流程/步骤
                                      ↓
                               安全事件实例
                                      ↓
                      时间线 / 视觉详情 / 证据 / 人工任务
```

## 2. 设备与区域

### 2.1 `camera_device` 摄像头表

| 字段 | 释义 |
| --- | --- |
| id | 主键，摄像头唯一标识 |
| camera_name | 摄像头名称，全局唯一，前端统一展示为名称 |
| ip_address | IP 地址 |
| username | 登录账号 |
| password | 登录凭据，接口不返回明文；数据库加密列改造列入后续安全任务 |
| description | 描述 |
| install_address | 安装地址，可空 |
| longitude / latitude | 经纬度，可空 |
| enabled | 是否启用 |
| last_error | 最近连接错误 |
| rtsp_port | RTSP 端口，默认 554 |
| web_port | 控制台端口，默认 80 |
| web_proxy_port | 代理监听端口，可空且唯一 |
| rtsp_path | 测试成功后使用的 RTSP 通道路径 |
| last_online_at | 最近在线时间 |
| create_time / update_time | 创建、更新时间 |

设备管理前端使用主键 `id`，展示 `camera_name`；后端自动测试大华、海康通道路径。视频运行态暂时仍使用 `camera_id`，区域接口同时接受主键和运行态 ID；`brand` 保存自动识别结果，二者当前不能物理删除。

### 2.2 `broadcast_device` 广播设备表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| name | 广播设备名称，全局唯一 |
| description | 描述 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

演示阶段使用 USB 扬声器，不保存厂商、IP、账号等无用字段。

### 2.3 `camera_broadcast_device` 摄像头广播绑定表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| camera_id | 外键，关联 `camera_device.id` |
| broadcast_device_id | 外键，关联 `broadcast_device.id` |
| create_time | 创建时间 |

唯一约束：`(camera_id, broadcast_device_id)`。摄像头可以绑定多个广播设备，一个 USB 广播也可以供多个摄像头使用。

### 2.4 `broadcast_template` 广播模板表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| name | 模板名称，唯一 |
| scene_type | 场景类型，如人员安全、非法捕鱼 |
| risk_level | 当前兼容库保存 1 / 2 / 3，接口同时返回中文风险标签 |
| content | 播报文本 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

### 2.5 `camera_detection_zone` 检测区域表

| 字段 | 释义 |
| --- | --- |
| id | 主键，也是保存后的绘制区域 ID |
| camera_id | 外键，关联 `camera_device.id` |
| name | 区域名称，同一摄像头内唯一 |
| zone_type | PERSON_LOW / PERSON_MEDIUM / PERSON_HIGH / FISHING |
| polygon_points | 多边形点位 JSON，3 至 15 个归一化坐标点 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

新接口不再使用矩形坐标、宽高、风险重复字段和区域表 `trigger_seconds`；触发时间统一保存到条件库。对应物理列因启动兼容逻辑仍在检查而暂未删除。

### 2.6 `camera_zone_condition` 区域条件绑定表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| zone_id | 外键，关联检测区域 |
| condition_id | 外键，关联条件库 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

唯一约束：`(zone_id, condition_id)`。人员区域通常关联一条条件；捕鱼区可关联船只闯入、停留、偷捕三条条件。

## 3. ECA 配置

### 3.1 `data_source` 数据源表

字段保持不变：

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| source_name | 数据源名称 |
| source_type | sensor / camera / api / file |
| device_id | 多态设备逻辑 ID；实际关联目标由 `source_type` 决定 |
| data_path | 数据路径或接口地址 |
| description | 描述 |
| is_activate | 是否启用 |
| create_time / update_time | 创建、更新时间 |

`device_id` 不关联统一设备主表，也不建立固定物理外键。后端根据 `source_type` 解释并校验：

- `source_type = camera` 时，`device_id` 关联 `camera_device.id`。
- `source_type = sensor` 时，`device_id` 暂时保存传感器逻辑编号；以后有传感器设备表时再关联对应表。
- 查询、唯一性判断和业务校验必须同时使用 `(source_type, device_id)`。
- 广播是动作执行设备，不属于数据源。

这种多态引用适合当前演示阶段，代价是 MySQL 不能直接给 `device_id` 建立指向不同表的外键，数据有效性由后端负责。

### 3.2 `condition_library` 条件库

字段保持不变：

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| condition_name | 条件名称 |
| source_id | 外键，关联 `data_source.id` |
| expression | 简单表达式，如 `person_present == 1` |
| time_window | 条件计算窗口，单位秒 |
| duration | 条件连续成立的触发秒数 |
| description | 条件说明 |
| is_activate | 是否启用 |
| create_time / update_time | 创建、更新时间 |

`camera_id/zone_id/track_id` 由运行上下文提供，不写进表达式。区域页面修改触发时间时，实际更新这里的 `duration`。

### 3.3 `event_library` 事件库

字段保持不变：

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_name | 事件名称 |
| event_code | 稳定事件编码，唯一 |
| event_category | 事件类型编码，如 PERSON_SAFETY、ILLEGAL_FISHING、ENVIRONMENT |
| risk_level | LOW / MEDIUM / HIGH |
| trigger_mode | single / composite |
| description | 事件说明 |
| is_activate | 是否启用 |
| create_time / update_time | 创建、更新时间 |

### 3.4 `event_condition` 事件条件表

字段保持不变：

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_id | 外键，关联事件库 |
| condition_id | 外键，关联条件库 |
| logic_type | AND / OR |
| group_id | 条件组编号 |
| sort_order | 计算顺序 |
| create_time | 创建时间 |

唯一约束建议为 `(event_id, condition_id)`。

### 3.5 `action_flow` 行为流程表

字段保持不变：`id、flow_name、flow_code、timeout_seconds、failure_strategy、description、is_activate、create_time、update_time`。

流程只等待动作是否成功受理，不等待无人机返航或人工任务最终完成。

### 3.6 `action_step` 行为步骤表

字段保持不变：

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| flow_id | 外键，关联行为流程 |
| step_order | 步骤顺序 |
| step_name | 步骤名称 |
| action_type | camera_snapshot / broadcast / drone_dispatch / staff_task |
| model_id | 可空，保留模型功能耦合点 |
| parameter | 可空，通用默认参数，本次流程不使用 |
| retry_count | 重试次数 |
| description | 描述 |
| create_time / update_time | 创建、更新时间 |

### 3.7 `event_action` 事件行为表

只负责事件与流程绑定，不再记录执行日志。

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_id | 外键，关联事件库 |
| flow_id | 外键，关联行为流程 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

唯一约束：`(event_id, flow_id)`。

### 3.8 `event_action_step_config` 事件步骤具体配置表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_action_id | 外键，关联事件行为 |
| camera_id | 可空，摄像头场景下的配置范围 |
| step_id | 外键，关联行为步骤 |
| broadcast_device_id | 可空，广播步骤选择的设备 |
| template_id | 可空，广播步骤选择的模板 |
| drone_id | 可空，无人机外部编号 |
| route_id | 可空，航线外部编号 |
| config_json | 其他少量动作配置 |
| enabled | 是否启用 |
| create_time / update_time | 创建、更新时间 |

唯一约束：`(event_action_id, camera_id, step_id)`。后端校验广播设备已绑定对应摄像头，且 `step_id` 属于事件关联的流程。

## 4. 安全事件闭环

### 4.1 `safety_event_instance` 安全事件实例表

传感器和视觉事件统一进入此表。

| 字段 | 释义 |
| --- | --- |
| id | 数据库主键，其他表使用此字段作为外键 |
| instance_no | 业务实例编号，唯一，如 `EVT_20260802_xxx` |
| current_event_id | 外键，当前对应的事件定义；风险升级时更新 |
| event_category | 事件大类编码，用于事件关联和列表筛选 |
| data_source_id | 外键，主要触发数据源 |
| risk_level | 当前风险等级 |
| max_risk_level | 历史最高风险等级 |
| state | ACTIVE / RESOLVED，事件生命周期 |
| status | PENDING / PROCESSING / COMPLETED / FALSE_ALARM，处置状态 |
| started_at | 事件开始时间 |
| last_observed_at | 最近观测时间 |
| resolved_at | 关闭时间 |
| resolve_reason | 自动解除、人工关闭、误报等原因 |
| summary | 告警列表摘要 |
| latest_observation | 最近观测 JSON |
| version | 乐观锁版本，避免自动与人工操作互相覆盖 |
| create_time / update_time | 创建、更新时间 |

同一目标升级时保持 `instance_no` 不变，只更新 `current_event_id/risk_level/max_risk_level`，变化过程写入时间线。

### 4.2 `visual_event_detail` 视觉事件详情表

仅视觉事件创建，一条事件实例最多一条详情。

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_instance_id | 外键且唯一，关联安全事件实例 |
| camera_id | 外键，关联摄像头 |
| camera_name | 触发时摄像头名称快照 |
| target_type | person / boat / vehicle 等 |
| target_id | 目标跟踪 ID，可空 |
| zone_id | 当前触发区域，可空外键 |
| zone_name | 区域名称快照 |
| zone_type | PERSON_LOW / PERSON_MEDIUM / PERSON_HIGH / FISHING |
| confidence | 最近一次触发置信度 |
| extra | bbox、模型名、帧时间等扩展 JSON |
| create_time / update_time | 创建、更新时间 |

截图和视频不放在此表，统一进入证据表。

### 4.3 `safety_event_timeline_log` 安全事件时间线表

融合原 `event_log`、`safety_event_log` 和旧 `event_action` 的执行记录。

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_instance_id | 外键，关联安全事件实例 |
| event_id | 可空外键，记录当时对应的事件定义 |
| condition_id | 可空外键，记录触发条件 |
| flow_id | 可空外键，记录执行流程 |
| step_id | 可空外键，记录执行步骤 |
| action_key | 可空且唯一，防止同一动作重复执行 |
| log_type | TRIGGER / RISK_CHANGE / ACTION / MANUAL / RESOLVE / SYSTEM |
| trigger_type | AUTO / MANUAL |
| risk_level | 发生时的风险等级 |
| status | PENDING / RUNNING / SUCCESS / FAILED |
| message | 页面时间线展示文案 |
| operator | 操作人，系统自动为 SYSTEM |
| payload | 触发数据、变更前后值、配置快照、执行结果和错误 JSON |
| create_time / update_time | 发生、更新时间 |

事件升级后新增日志，旧日志不修改。`payload` 保存当时的事件名、流程名和步骤名，避免配置以后改名影响历史展示。

### 4.4 `safety_event_evidence` 统一证据表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_instance_id | 外键，关联安全事件实例 |
| timeline_log_id | 可空外键，关联产生证据的时间线动作 |
| task_id | 可空外键，关联人工任务 |
| evidence_type | CAMERA_SNAPSHOT / CAMERA_VIDEO / DRONE_IMAGE / STAFF_IMAGE / OTHER |
| source_type | CAMERA / DRONE / STAFF / SYSTEM |
| source_id | 来源设备或人员编号，可空 |
| file_url | 文件访问地址 |
| description | 证据说明 |
| metadata | bbox、无人机位置、文件信息等 JSON |
| captured_at | 拍摄或生成时间 |
| create_time | 入库时间 |

一条事件可有多张图片和多个视频，统一供详情页和时间线展示。

### 4.5 `safety_event_task` 人工处置任务表

| 字段 | 释义 |
| --- | --- |
| id | 主键 |
| event_instance_id | 外键，关联安全事件实例 |
| dispatch_operator | 派单人 |
| assignee | 接单人 |
| task_status | WAITING / ACCEPTED / PROCESSING / COMPLETED / CANCELLED |
| task_note | 现场备注或任务说明 |
| dispatched_at | 派单时间 |
| accepted_at | 接单时间 |
| completed_at | 完成时间 |
| result_type | DRIVEN_AWAY / LEFT_VOLUNTARILY / OTHER |
| result_remark | 处置结果补充说明 |
| create_time / update_time | 创建、更新时间 |

现场照片进入统一证据表，不在任务表重复保存。

## 5. 枚举存储与展示

数据库、后端判断和接口传输统一使用稳定英文编码，前端通过统一字典显示中文，不在各页面重复写转换逻辑。例如：

| 英文编码 | 中文展示 |
| --- | --- |
| PERSON_SAFETY | 人员安全 |
| ILLEGAL_FISHING | 非法捕鱼 |
| LOW / MEDIUM / HIGH | 低风险 / 中风险 / 高风险 |
| ACTIVE / RESOLVED | 进行中 / 已解除 |
| PENDING / PROCESSING / COMPLETED / FALSE_ALARM | 待处理 / 处理中 / 已完成 / 误报 |
| AUTO / MANUAL | 自动 / 手动 |
| SUCCESS / FAILED | 成功 / 失败 |

区域类型、动作类型、日志类型、任务状态和证据类型遵循相同原则。后端集中维护枚举合法值，前端集中维护中文标签。

## 6. 初始事件和流程数据

| 事件 | 分类 | 风险 | 默认触发时间 | 流程步骤 | 流程超时 |
| --- | --- | --- | ---: | --- | ---: |
| 人员闯入 | 人员安全 | LOW | 5 秒 | 抓拍 -> 广播 | 60 秒 |
| 人员亲水 | 人员安全 | MEDIUM | 3 秒 | 抓拍 -> 广播 -> 无人机派飞 | 120 秒 |
| 人员涉水 | 人员安全 | HIGH | 0 秒 | 抓拍 -> 广播 -> 创建人工任务 | 60 秒 |
| 船只闯入 | 非法捕鱼 | LOW | 0 秒 | 抓拍 -> 广播 | 60 秒 |
| 船只停留 | 非法捕鱼 | MEDIUM | 30 秒 | 抓拍 -> 广播 -> 无人机派飞 | 120 秒 |
| 船只偷捕 | 非法捕鱼 | HIGH | 120 秒 | 抓拍 -> 广播 -> 创建人工任务 | 60 秒 |

六个流程的 `failure_strategy` 均为 `continue`。抓拍、广播或派飞失败需要写失败日志，但不阻断后续必要动作。

## 7. 清理状态

| 原表/字段 | 处理 |
| --- | --- |
| `alarm` | 本期保持不变，不迁移数据、不修改原有业务 |
| `event_log` | 仅保留 3 条既有 ECA 历史记录供查询；新触发不再写入 |
| `safety_event_log` | 已备份并删除，动作统一写入 `safety_event_timeline_log` |
| 旧 `event_action` 执行字段 | 35 条测试执行记录已清理，16 个执行字段已删除；表仅保留事件到流程关系 |
| `safety_event` | 6 条测试事件已备份并删除，检测引擎和接口均已切换到统一实例 |
| `safety_event_task` | 仅通过非空 `event_instance_id` 关联实例，旧 `event_id` 和电话字段已删除 |
| `sys_device` | 已删除；原表 0 行、无外键，旧 API/模型/Schema 同步删除 |
| `sys_trigger_rule` | 已删除；原表 0 行、无外键，统一由 ECA 条件和事件处理 |
| 区域 rect、旧绘制 ID、风险字段、`trigger_seconds` | 前端与新接口已停用旧概念；数据库列暂留兼容 |

告警管理页面新增一个独立的“安全事件”入口，用于查看 `safety_event_instance` 列表。原告警列表继续查询 `alarm`，两套数据本期不合并；是否最终融合由后续协作结果决定。

原视频安全闭环数据均为测试数据，已备份后清理，不做历史迁移。新的事件状态、风险变化、动作、任务和证据只写入统一运行表。

已删除旧安全闭环前端页面、旧安全事件模型与接口实现、旧设备/触发规则接口及其模型、Schema、未使用的前端 API、历史兼容 SQL 和 `.bak` 文件。广播测试设备已合并为唯一的“一号点广播”。巡查报告入口保留，生成调度暂停，等待新版模板后直接基于统一实例和时间线实现。

## 8. 字段复核结论

- 事件实例统一使用 `data_source_id` 指向数据源；数据源再通过 `(source_type, device_id)` 定位摄像头或传感器。
- `state` 表示事件是否结束，`status` 表示处置进度，两者含义不同，需要同时保留。
- 视觉详情不重复保存证据 URL；证据表支持摄像头、无人机和人工多份材料。
- 时间线补充 `condition_id`、`event_id` 和 `action_key`，分别解决触发追溯、事件升级历史和重复动作问题。
- 具体设备、模板、无人机和航线不塞进抽象步骤，通过 `event_action_step_config` 配置。
- 当前字段已覆盖区域配置、条件触发、事件升级、动作执行、误报、人工升级、自动广播、无人机取证、人工任务和安全事件列表展示，没有明显低价值重复字段。

## 9. 实施要求

1. 先以实际 MySQL 建立迁移基线，再执行版本化迁移。
2. SQLAlchemy 模型、迁移脚本和实际表逐字段保持一致。
3. 不再依赖生产启动时的零散 `create_all + ALTER TABLE` 修改结构。
4. 先迁移和兼容旧 API，再切换前端，最后删除确认废弃的旧表、旧字段、旧代码和旧文件。
5. 全程不修改模型库和工作流小组负责的表。
6. 删除任何旧结构前先生成明确清单并告知用户，确认影响和数据迁移完成后再执行。
