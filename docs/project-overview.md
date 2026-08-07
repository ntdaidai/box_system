# Box System 项目总览

> 更新时间：2026-08-07
> 目标：让接手者快速看懂系统做什么、页面怎么分、数据怎么流、核心表怎么配合。
> 更细的数据库最终口径见 [database-integration-final-design.md](./database-integration-final-design.md)。

## 1. 一句话说明

Box System 是一套“传感器 + 视频巡查 + 统一安全事件闭环”的边缘侧业务系统。

它做三件事：

1. 接入传感器和摄像头数据。
2. 按条件触发统一安全事件实例。
3. 把事件走完广播、无人机、人工任务、报告归档等闭环。

## 2. 系统分层

### 2.1 前端

- 技术栈：Vue 3 + Element Plus
- 入口：`dam-frontend`
- 负责：监控展示、设备管理、区域配置、信息配置、告警管理、报告和文档入口

### 2.2 后端

- 技术栈：FastAPI + SQLAlchemy
- 入口：`dam-backend`
- 负责：规则计算、事件实例、时间线、证据、人工任务、广播、无人机、巡查报告、视觉检测、传感器采集联动

### 2.3 基础服务

- MySQL：业务数据库
- Redis：缓存和状态
- IoTDB：传感器时序数据
- MinIO：图片、报告文件、证据文件
- Qwen / vLLM：摄像头初筛和视觉分析
- OnlyOffice：在线文档
- WebRTC / MediaMTX：摄像头实时流

## 3. 核心业务

### 3.1 传感器链路

传感器数据进入 ECA 引擎后，根据 `condition_library -> event_condition -> event_library` 计算是否触发事件。

典型场景：

- 风速超阈值
- 雨量超阈值
- 振动异常
- 温湿度异常

### 3.2 视频巡查链路

摄像头画面进入视觉检测后，按区域类型和持续时间触发安全事件。

当前口径：

- 不做“对某一个人/某一条船”的精细跟踪闭环
- 只统计“某个区域里人或船持续出现了多少秒”
- 人和船仍然区分，但触发逻辑按区域聚合
- 事件时长统一在条件表里配置，区域表不再单独存触发时间

### 3.3 闭环链路

```text
数据源
  -> 条件库
  -> 事件库
  -> 事件动作
  -> 安全事件实例
  -> 时间线
  -> 证据
  -> 广播 / 无人机 / 人工任务
  -> 报告归档
```

## 4. 页面功能地图

### 4.1 综合态势

- `/dashboard`
- 作用：看全局运行态势、设备在线情况、最近事件、风险统计、告警概览

### 4.2 感知监测

- `/monitor/overview`：监控总览
- `/monitor/system`：系统监测
- `/monitor/sensors`：综合传感器
- `/monitor/temp`：温湿度
- `/monitor/wind`：风速风向
- `/monitor/rain`：雨量计
- `/monitor/vibration`：振动传感器
- `/monitor/camera`：视频监控
- `/monitor/camera/devices`：摄像头与数据源管理
- `/monitor/config`：信息配置
- `/monitor/device`：设备状态
- `/monitor/drone`：无人机监测

### 4.3 告警管理

- `/alarm/safety-events`
- 作用：统一安全事件列表、详情、时间线、证据、人工处置入口
- 旧告警列表已统一到安全事件实例，不再走旧 `alarm` 表

### 4.4 系统管理

- `/system/devices`
- `/system/linkage`
- `/system/models`
- 作用：设备、联动、模型相关配置入口

### 4.5 数据与文档

- `/document/hub`
- `/document/knowledge`
- `/document/editor/:documentId`
- 作用：文档管理、知识库和在线编辑

## 5. 关键业务表

### 5.1 定义层

- `data_source`：统一数据入口，摄像头和传感器都从这里进入
- `condition_library`：条件库
- `event_library`：事件库
- `event_condition`：事件和条件的关系
- `event_action`：事件动作配置

### 5.2 运行层

- `safety_event_instance`：统一事件事实表，也是告警列表的事实来源
- `safety_event_timeline_log`：事件时间线
- `safety_event_evidence`：证据
- `safety_event_task`：人工处置任务
- `analysis_report`：报告归档

### 5.3 设备层

- `camera_device`：摄像头设备台账
- `camera_detection_zone`：摄像头区域
- `broadcast_device`：广播设备
- `broadcast_template`：广播模板

## 6. 事件闭环规则

### 6.1 传感器事件

- 条件满足就触发实例
- 条件恢复后按恢复时间自动闭环
- 事件实例会保留过程时间线和证据

### 6.2 视频事件

- 以区域内人员或船只持续出现为触发依据
- 人员事件和船只事件分开配置
- 区域类型负责展示语义，条件库负责持续时间
- 当前不建议把触发逻辑做成“每个摄像头每个区域一套独立条件”

### 6.3 动作执行

- 一行 `event_action` 对应一个动作步骤
- 当前动作包括广播、无人机、人工任务、抓拍等
- 前端按 `event_id + step_order` 展示流程

## 7. 当前运行习惯

- 摄像头、传感器都通过 `data_source` 统一接入
- `source_type` 需要保留，便于按来源分流
- `event_action_id` 是时间线上的动作外键名
- 秒级字段不强改名，字段名保留，注释写清单位
- `config_json` 只放扩展项，核心配置尽量用普通字段
- 摄像头初筛默认在 `docker-compose.yml` 中开启；测试环境如需停掉，可显式把 `QWEN_CAMERA_SCREENING_ENABLED=false`

## 8. 你接手时最该先看什么

1. [agent-handoff-business-logic.md](./agent-handoff-business-logic.md)
2. [database-integration-final-design.md](./database-integration-final-design.md)
3. `dam-backend/app/models`
4. `dam-backend/app/services/eca_engine.py`
5. `dam-backend/app/services/safety_event_runtime_service.py`
6. `dam-frontend/src/router/index.js`

## 9. 一句话提醒

当前系统不是“单独的告警列表系统”，而是“统一安全事件闭环系统”。

页面上的“告警”，本质上都是 `safety_event_instance` 的不同视图。
