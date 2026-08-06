# Box System 业务与事件闭环交接说明

> 更新时间：2026-08-06
> 用途：新 Agent 接手前先阅读本文。本文描述当前最终方案和实际代码边界，不是早期讨论草案。
> 更完整的表结构背景见 `docs/database-integration-final-design.md`，实际字段以 `dam-backend/app/models` 和 `mysql/init/init.sql` 为准。

## 1. 项目目标

系统包含两个监测模块，但共用一套安全事件闭环：

1. **大坝传感器监测**：温湿度、风速风向、雨量、振动等数据进入 ECA。
2. **视频巡查安全**：摄像头模型检测人员或船只，结合检测区域和持续时间触发 ECA 事件。

两条业务线最终统一为：

```text
数据源 -> 条件定义 -> 事件定义 -> 处置流程 -> 安全事件实例
       -> 时间线 -> 证据 -> 无人机/广播/人工任务 -> 自动或人工闭环
```

统一的是事件定义、实例、时间线、证据和处置结果；传感器采集与视觉跟踪仍使用各自适合的检测入口。

## 2. 明确边界

- 暂不修改：用户表、模型库、工作流模块。
- 模型库与本业务只保留 `event_action_config.model_id` 这一可选耦合点。
- 原 `alarm` 表已删除；旧 `/api/alarm/*` 路径保留为兼容层，内部读取 `safety_event_instance`。
- `analysis_report` 保留为报告归档表，只保存报告编号、标题、类型、日期和 MinIO 地址。
- 巡查报告入口保留；日报、月报和事件分析报告都应归档到 `analysis_report`。
- 无人机可在监控总览和实时数据中静态展示，但它不是 `data_source`。
- 广播设备也不是 `data_source`，它是动作执行目标。
- 所有枚举值数据库存英文，页面显示中文。

## 3. 核心数据关系

```text
data_source
  -> condition_library
  -> event_condition -> event_library
  -> event_action_config

camera_device -> camera_detection_zone
event_action_config -> broadcast_device / broadcast_template / drone / route

event_library -> safety_event_instance
                  -> visual_event_detail（仅视觉事件）
                  -> safety_event_timeline_log
                  -> safety_event_evidence
                  -> safety_event_task（需要人工处置时）
                  -> analysis_report（可选，仅事件分析报告）
```

### 3.1 ECA 定义层


| 表                         | 作用           | 关键字段                                                                         |
| ---------------------------- | ---------------- | ---------------------------------------------------------------------------------- |
| `data_source`              | ECA 数据入口   | `source_type`、`device_id`、`data_path`、`is_activate`                           |
| `condition_library`        | 条件库         | `source_id`、`expression`、`time_window`、`duration`、`is_activate`              |
| `event_library`            | 事件库         | `event_code`、`event_category`、`risk_level`、`recovery_duration`、`route_role_id`、`is_activate` |
| `event_condition`          | 事件与条件关系 | `event_id`、`condition_id`、`logic_type`、`group_id`、`sort_order`               |
| `event_action_config`      | 事件动作配置   | `event_id`、`step_order`、`action_type`、设备/模板/无人机/航线、重复策略、启用状态 |

注意：

- 视觉条件表达式保持简单，例如 `person_present == 1`、`boat_present == 1`。
- 摄像头、区域、目标轨迹不写进表达式，由视觉运行上下文提供。
- 视觉业务将 `condition_library.duration` 解释为触发持续秒数；不要因旧字段注释而改成分钟。
- 传感器已有 ECA 数据不能覆盖或删除，视觉事件只做增量补充。

### 3.2 设备与区域层

**`camera_device`**

- 数字主键 `id` 是唯一摄像头标识。
- 不再存在 `dahua_001`、`camera_001` 一类业务 ID。
- `camera_id` 出现在接口或运行时上下文中时，均指 `camera_device.id`。
- 用户基础配置：名称、IP、账号、密码、描述。
- 高级配置：安装地址、经纬度、RTSP 端口、Web 端口。
- 名称唯一；保存前必须测试连接；品牌由后端自动探测大华/海康。

**`camera_detection_zone`**

- 关键字段：`camera_device_id`、`zone_name`、`zone_type`、`polygon_points`、`enabled`。
- 多边形只能有 3 至 15 个点，坐标为 0 至 1 的归一化值。
- 不保存矩形、前端绘制 ID、风险等级或触发秒数。
- 数据库区域主键就是运行时 `zone_id`，不得增加兼容 ID。
- 区域类型只有：
  - `PERSON_LOW`：人员低风险区
  - `PERSON_MEDIUM`：人员中风险区
  - `PERSON_HIGH`：人员高风险区
  - `FISHING`：捕鱼监测区

区域不再通过 `camera_zone_condition` 关联条件；该表已删除。

触发持续时间只按区域类型/事件类型统一配置：

- `PERSON_LOW` 使用 `PERSON_INTRUSION` 对应条件的 `duration`。
- `PERSON_MEDIUM` 使用 `PERSON_WATERFRONT` 对应条件的 `duration`。
- `PERSON_HIGH` 使用 `PERSON_WADING` 对应条件的 `duration`。
- `FISHING` 使用 `BOAT_INTRUSION`、`BOAT_STAY`、`BOAT_ILLEGAL_FISHING` 三个条件的 `duration`。

区域页面只配置区域名称、类型、多边形和启停；触发时间在信息配置页的触发条件中修改，全局生效。

**广播相关**

- `broadcast_device`：广播设备台账；演示设备正式名称为“一号点广播”。
- `broadcast_template`：自动广播文案模板。
- 不再维护摄像头和广播设备绑定表；一号摄像头触发事件后按事件动作配置播放广播。
- 自动广播必须同时选定广播设备和模板，并由 `event_action_config` 保存。
- 一键喊话是用户实时录音，不使用模板、不记录说话文本，只记录用户、设备、执行结果和时间线。

**`data_source.device_id`**

- 它是按 `source_type` 解释的多态设备标识，而不是跨设备共用外键。
- `source_type=camera` 时关联 `camera_device.id`。
- `source_type=sensor` 时保存当前传感器逻辑设备 ID；目前没有独立传感器设备表。
- 查询必须同时使用 `source_type + device_id`。

## 4. 视觉事件定义

### 4.1 人员安全


| 事件编码            | 中文事件 | 区域            | 风险   | 默认持续时间     |
| --------------------- | ---------- | ----------------- | -------- | ------------------ |
| `PERSON_INTRUSION`  | 人员闯入 | `PERSON_LOW`    | LOW    | 5 秒             |
| `PERSON_WATERFRONT` | 人员亲水 | `PERSON_MEDIUM` | MEDIUM | 3 秒             |
| `PERSON_WADING`     | 人员涉水 | `PERSON_HIGH`   | HIGH   | 0 秒，进入即触发 |

事件分类为 `PERSON_SAFETY`。默认值只用于初始化或兜底，用户可在区域配置/信息配置中修改，数据库条件值是持久化来源。

### 4.2 非法捕鱼


| 事件编码               | 中文事件 | 区域      | 风险   | 默认持续时间 |
| ------------------------ | ---------- | ----------- | -------- | -------------- |
| `BOAT_INTRUSION`       | 船只闯入 | `FISHING` | LOW    | 0 秒         |
| `BOAT_STAY`            | 船只停留 | `FISHING` | MEDIUM | 30 秒        |
| `BOAT_ILLEGAL_FISHING` | 船只偷捕 | `FISHING` | HIGH   | 120 秒       |

事件分类为 `ILLEGAL_FISHING`。当前业务不再精细跟踪“区域内具体某条船”的停留，而是按捕鱼区内是否持续出现船只统计，达到 0/30/120 秒触发或升级。

## 5. 视觉事件状态线

### 5.1 区域连续性

- 当前业务按“摄像头 + 区域 + 对象类型”聚合，不再按具体某个人或某条船定义进入区域时间。
- 人和船仍要区分：人员事件使用 `PERSON_*` 事件码，船只事件使用 `BOAT_*` 事件码。
- `condition_library` 不保存 `zone_id` 和 `object_type`；触发时间按事件码全局配置。
- 运行时可继续利用模型 `track_id` 做短期去抖和画面连续性，但事件触发语义以区域内是否持续出现人员/船只为准。
- 风险升级时更新同一个 `safety_event_instance` 的 `current_event_id`、`risk_level` 和 `max_risk_level`，历史阶段写入时间线。
- 不得因同一区域风险升级创建多个并行实例。

当前默认去抖参数：丢失宽限 3 秒、离场确认 10 秒、轨迹记忆 20 秒、IoU 阈值 0.2。这些参数服务于检测稳定性，不改变按区域聚合的业务语义。

### 5.2 触发、升级与闭环

```text
目标进入区域
  -> 持续达到条件 duration
  -> 创建统一事件实例
  -> 写 TRIGGER 时间线和首次抓拍证据
  -> 执行当前风险流程
  -> 同一区域达到更高风险条件时更新同一实例
  -> 写 RISK_CHANGE、升级抓拍和新风险动作
  -> 目标离开当前风险区域并持续超过确认时间
  -> 再次抓拍
  -> 写 RESOLVE 时间线并自动闭环
```

业务简化规则：

- 低风险人员未离开时事件保持活动，广播按配置限频重复，不因逗留时间自动升级风险。
- 中风险人员离开中风险区即可开始闭环；即使随后回到低风险区，也不继续维持原中风险阶段。
- 同一区域直接达到高风险条件时，原实例升级为高风险。
- 船只在同一捕鱼区按 0/30/120 秒升级，始终保持一个实例。
- 自动闭环必须保存离场抓拍，不能只有触发截图。
- 用户可人工确认、升级风险、派单、接单、完成任务、标记误报或人工关闭。

## 6. 传感器事件状态线

```text
传感器数据进入 ECA
  -> 条件为真
  -> 按“事件定义 + 数据源”查询活动实例
  -> 无实例则创建 safety_event_instance 和 TRIGGER 时间线
  -> 已有实例则只更新 last_observed_at/latest_observation
  -> 条件首次恢复时记录 recovery_started_at
  -> 持续正常达到 event_library.recovery_duration
  -> 状态改为 RESOLVED/COMPLETED
  -> 写 RESOLVE 时间线，原因 condition_recovered
```

例如高温报警不能因为一次正常读数立刻完成，必须持续正常达到恢复时间。传感器与视觉共用实例、时间线、证据和人工操作表。

当前实现边界：传感器已经统一实例和闭环日志，传感器和视觉动作配置统一读取 `event_action_config`。以后若要求传感器事件也自动广播、派无人机或生成人工任务，应继续复用统一动作配置和执行器，不能恢复旧 `safety_event/event_action` 执行日志方案，也不能再建一套传感器闭环表。

## 7. 标准处置流程


| 事件     | 步骤                                         |
| ---------- | ---------------------------------------------- |
| 人员闯入 | 摄像头抓拍 -> 自动广播                       |
| 人员亲水 | 摄像头抓拍 -> 自动广播 -> 无人机派飞取证驱离 |
| 人员涉水 | 摄像头抓拍 -> 自动广播 -> 生成人工处置任务   |
| 船只闯入 | 摄像头抓拍 -> 自动广播                       |
| 船只停留 | 摄像头抓拍 -> 自动广播 -> 无人机派飞取证驱离 |
| 船只偷捕 | 摄像头抓拍 -> 自动广播 -> 生成人工处置任务   |

动作类型至少包括：`camera_snapshot`、`broadcast`、`drone_dispatch`、`staff_task`。

- `event_action_config` 一行描述某个事件的一个动作步骤，按 `step_order` 顺序执行。
- 广播设备、模板、无人机、航线、超时、失败策略、重试次数和广播重复策略均直接保存在 `event_action_config`。
- 当前广播默认重复策略为间隔 60 秒、最多 3 次，可在具体动作配置中修改。
- 缺少广播设备/模板或无人机/航线时，应明确报配置错误，不能偷偷回退到旧数据。
- 流程步骤完成表示动作已成功下发/接受，不要求等待无人机返航或工作人员最终处置完成。

## 8. 统一运行表

### `safety_event_instance`

唯一的安全事件事实主表。关键字段：

- `instance_no`：业务唯一编号，例如 `EVT_20260804_xxx`。
- `current_event_id`：当前阶段对应的事件库记录，可随风险升级改变。
- `analysis_report_id`：可选，关联事件闭环分析报告；日报和月报不一定关联事件实例。
- `event_category`、`source_type`、`source_id`、`data_source_id`：事件分类和来源。
- `risk_level`、`max_risk_level`：当前和历史最高风险。
- `state`：`ACTIVE/RESOLVED`。
- `status`：`PENDING/PROCESSING/COMPLETED/FALSE_ALARM`。
- `started_at`、`last_observed_at`、`resolved_at`、`resolve_reason`。
- `summary`、`latest_observation`、`version`。

### `visual_event_detail`

视觉事件一对一补充：摄像头、目标类型、`target_id`、区域、置信度和少量 `extra`。传感器事件没有此行。

### `safety_event_timeline_log`

事件所有变化的审计时间线：

- 类型：`TRIGGER/RISK_CHANGE/ACTION/MANUAL/RESOLVE/SYSTEM`。
- 关联当时的事件、条件、流程和步骤。
- 当前动作配置关联使用 `action_config_id`；旧 `flow_id/step_id` 已从 ORM 中移除。
- 固定阶段字段 `stage` 用于前端进度条，当前约定为 `TRIGGER/DISPATCH/PROCESSING/REPORT/CLOSE`。
- `action_key` 用于动作幂等，防止重复执行。
- `payload` 保存当时配置快照、触发数据、动作参数、执行结果和错误详情。
- 历史阶段名称、模板、设备等易变信息应保存在 `payload`，不能只依赖当前配置回查。

### `safety_event_evidence`

统一保存摄像头截图/视频、无人机图片和工作人员现场图片。证据可关联时间线和人工任务，页面在对应时间线节点提供查看入口。

### `safety_event_task`

仅管理人工处置分支：派单人、接单人、任务状态、备注、派单/接单/完成时间、处置结果。任务状态与事件实例状态是两个概念。

### `analysis_report`

报告归档表，只保存检索与下载所需的基础信息：

- `report_no`：报告编号，唯一。
- `report_title`：报告标题。
- `report_type`：报告类型，当前约定为 `event/daily/monthly`。
- `report_date`：报告日期。
- `file_url`：MinIO 文件地址。

不要再把长正文、AI 模型名、风险等级等分析内容塞入该表；报告正文以文件形式保存在 MinIO。

## 9. 页面与用户入口

- 实时监控 `/monitor`：传感器页、视频监控、设备管理、区域配置、信息配置、无人机监测。
- 设备管理 `/monitor/camera/devices`：摄像头管理、广播设备和广播模板；不再配置摄像头广播绑定。
- 区域配置入口会打开视频监控区域抽屉；支持 3 至 15 点多边形、区域类型和启用状态，不配置触发时间。
- 信息配置 `/monitor/config`：可配置视觉条件持续时间、事件参数、智能路由角色逻辑 ID，以及每个事件的动作步骤和具体动作目标。
- 告警管理 `/alarm/safety-events`：统一安全事件列表和详情；旧 `/alarm/list` 页面通过实例表兼容展示，不再依赖 `alarm` 表。
- 详情页重点展示：当前状态、风险、来源、视觉详情、完整时间线、证据和人工任务。
- 视频监控的检测事件展示也读取统一事件实例，不使用旧安全闭环表。
- 小程序保留四项核心能力：事件列表、实时监控、一键喊话、人工处置。
- 监控总览和实时数据保留无人机静态卡片；无人机不进入数据源统计。
- 巡查报告入口保留，接口当前返回 `TEMPLATE_PENDING`。

## 10. 主要接口

- 摄像头：`/api/v1/camera/devices`、`/devices/test-connection`、`/{camera_id}/zones`、视频流和检测接口。
- 广播：`/api/broadcast/devices`、`/templates`、`/camera/{camera_id}/devices`、`/audio/play`。
- 融合配置：`/api/v1/integration/config` 及 conditions/events/flows/actions 更新接口。
- 统一事件：`/api/v1/integration/safety-events`、详情、`operation`、WebSocket。
- ECA 定义读取与调度：`/api/v1/eca/...`。
- 小程序：`/api/miniprogram/v1/cameras`、`/events`、录音广播、人工处置接口。

人工事件操作包括：`ACKNOWLEDGE`、`DISPATCH_TASK`、`ACCEPT_TASK`、`COMPLETE_TASK`、`RESOLVE`、`FALSE_ALARM`、`UPGRADE`。

## 11. 禁止重新引入的旧耦合

- 不得恢复字符串摄像头业务 ID，所有摄像头关联使用 `camera_device.id`。
- 不得恢复矩形检测区域、绘制 ID、区域表触发时间或读取 rect 的 fallback。
- 不得让视觉检测再次调用旧通用 ECA 回调并重复创建事件。
- 不得恢复旧 `event_action/action_flow/action_step/event_action_step_config` 拆表结构；事件动作统一使用 `event_action_config`。
- 不得恢复 `camera_zone_condition` 或区域级触发时间；触发持续时间只在 `condition_library` 按事件码配置。
- 不得恢复旧 `alarm` 表；旧告警接口只能作为 `safety_event_instance` 的兼容层。
- 不得恢复旧 `safety_event`、旧安全事件日志或旧视觉闭环接口。
- 不得让广播/无人机从旧测试 `event_action` 数据推断具体配置。
- 不得恢复旧 `/api/device`、`/api/rule`、`/api/v1/camera/add|list|safety` 或 `/api/v1/eca/logs` 接口。
- 不得为了兼容测试数据保留旧字段；测试事件、旧区域和旧动作数据可以清理。
- 清理数据库前必须先全局检索代码引用并完成新链路替代，不能先删表再补代码。

## 12. 当前实现与接手检查

截至本文生成时：

- ORM 已切换到 `event_action_config`；旧 `event_action/action_flow/action_step/event_action_step_config` 和 `camera_broadcast_device` 由迁移脚本 `dam-backend/scripts/migrate_20260806_event_action_config_consolidation.py` 备份并删除。
- 第二阶段迁移脚本 `dam-backend/scripts/migrate_20260806_event_runtime_simplification.py` 已执行并记录到 `schema_migration`：删除 `alarm`、`camera_zone_condition`，清理旧 `[ZONE_ECA:*]` 和旧 PRESENT 视觉条件，保留 6 条业务视觉条件，调整 `analysis_report` 并为 `safety_event_instance` 增加 `analysis_report_id`。
- 旧 `/api/alarm/*` 路径仍存在，但只作为兼容层读取和更新 `safety_event_instance`；不得再新增 `Alarm` ORM 或 `alarm` 表。
- `visual_event_detail` 当前仍保守保留，因为运行时事件详情、巡查报告和人工升级判断仍有直接读取。下一阶段若继续减表，应先把区域、对象类型、置信度和展示详情收敛到 `safety_event_instance.latest_observation` 或少量实例字段，再删除该表。
- 信息配置页已改为事件策略和动作流程配置，不再依赖旧流程三表。
- 区域配置页不再保存逐区域触发时间；触发时间统一在信息配置页的触发条件中配置。
- 后端针对性测试最近结果：广播服务 11 通过、无人机派飞 2 通过、传感器统一实例 1 通过、旧告警兼容映射 3 通过。
- 前端生产构建通过。
- `schema_migration` 仍作为手写迁移脚本的幂等记录表保留；本轮迁移稳定后再评估是否删除。
- 当前工作区有用户及前一轮清理留下的未提交修改，接手 Agent 必须先执行 `git status`，不得回滚不属于自己的更改。

仍需持续验证的实现细节：目标明确从区域离开时已有离场帧可生成抓拍；目标直接从检测结果中消失时，当前 missing 分支可能没有把最新画面传给 `_resolve`。后续改动必须补测“完全消失后自动闭环也有离场证据”，但不要因此改变本文定义的闭环规则。

新 Agent 开始修改前按以下顺序核对：

1. 先读本文、`docs/database-integration-final-design.md` 和当前 ORM。
2. 执行 `git status`，识别并保留现有改动。
3. 搜索旧表名、旧接口、字符串摄像头 ID 和 rect fallback，确认没有重新出现。
4. 修改事件逻辑时同时覆盖：同轨迹升级、重复动作幂等、离场抓拍、自动恢复、人工关闭。
5. 数据库变更采用可重复执行的迁移/初始化脚本；不得覆盖已有传感器 ECA 数据。
6. 至少测试一条人员低到高升级、一条船只 0/30/120 秒升级、一条视觉离场闭环、一条传感器条件恢复闭环，以及广播/无人机/人工任务各一条动作链。
