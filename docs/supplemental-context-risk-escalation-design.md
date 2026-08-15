# 补充信息驱动的知识库风险升级方案

## 1. 目标

在视频初筛只给出低风险或疑似事件时，允许值班人员在页面补充现场运行状态，例如“库坝正在泄洪”。系统将补充信息与视频事件、知识库条款共同交给大模型研判；如果知识库命中“泄洪期间滩涂/消落带/岸边禁止人员进入”等条款，则自动把事件风险升级为高风险，并让事件列表、事件详情、联动流程和事件处置报告都按高风险口径展示。

典型场景：

```text
视频初筛：疑似人员在滩涂边活动，风险 LOW
人工补充：当前库坝正在泄洪
知识库命中：泄洪期间禁止人员进入滩涂、消落带、下游河道及近水区域
系统结论：风险升级 HIGH，报告引用知识库条款说明升级依据
```

## 2. 总体链路

```text
视频测试页
  1. 上传视频并触发事件
  2. 点击“补充运行状态”
  3. 选择/填写：正在泄洪、泄洪流量、闸门开度、下游禁入范围、备注
        │
        ▼
后端补充信息接口
  1. 写入 safety_event_instance.latest_observation.context
  2. 追加 timeline：SUPPLEMENTAL_CONTEXT
  3. 构造知识库检索 query
        │
        ▼
知识库检索 + 大模型风险复核
  1. 检索“泄洪 + 滩涂人员 + 禁止进入 + 风险等级”
  2. 将命中条款、初筛结果、补充信息交给 4B/35B
  3. 输出 risk_level_override、reason、knowledge_sources
        │
        ▼
事件运行时
  1. 若 risk_level_override=HIGH 且依据充分，更新 risk_level/max_risk_level
  2. 追加 RISK_CHANGE 时间线
  3. 重新/继续执行高风险动作和报告生成
        │
        ▼
报告
  1. 风险等级使用 instance.max_risk_level/risk_level
  2. “风险研判依据”写入补充信息与知识库条款
  3. “知识库依据”列出条款编号、标题、引用片段
```

## 3. 前端设计

### 3.1 页面位置

页面：`/system/video-detection`

在“事件处理中”区域增加按钮：

```text
补充运行状态
```

按钮启用条件：

- 已经有 `result.event_instance_id`；
- 当前事件还未生成最终报告，或允许“补充后重新研判”；
- 当前视频检测结果包含人员/滩涂/亲水/涉水相关线索时优先显示，也可常驻。

### 3.2 弹窗字段

建议第一期做成结构化表单，减少自由文本误差：

```json
{
  "context_type": "DAM_DISCHARGE",
  "label": "库坝正在泄洪",
  "active": true,
  "severity_hint": "HIGH",
  "started_at": "2026-08-15 14:20:00",
  "discharge_flow_m3s": null,
  "gate_opening": "",
  "affected_area": "滩涂、消落带、下游河道、近水岸线",
  "note": "泄洪期间禁止人员进入滩涂边活动"
}
```

按钮交互建议：

- 主按钮：`补充运行状态`
- 快捷选项：
  - `正在泄洪`
  - `强降雨/水位上涨`
  - `闸门开启`
  - `下游禁入`
- 提交后页面流程增加节点状态：`补充信息已提交，正在结合知识库复核风险`

## 4. 后端接口设计

### 4.1 新增接口

建议放在融合事件接口下：

```http
POST /api/v1/integration/safety-events/{event_id}/supplemental-context
```

请求：

```json
{
  "context_type": "DAM_DISCHARGE",
  "active": true,
  "label": "库坝正在泄洪",
  "severity_hint": "HIGH",
  "occurred_at": "2026-08-15T14:20:00+08:00",
  "affected_area": "滩涂、消落带、下游河道、近水岸线",
  "note": "泄洪期间禁止人员进入滩涂边活动",
  "source": "OPERATOR"
}
```

响应：

```json
{
  "event_instance_id": 267,
  "risk_before": "LOW",
  "risk_after": "HIGH",
  "escalated": true,
  "knowledge_hits": [
    {
      "clause_id": "DISCHARGE-PERSON-001",
      "title": "泄洪期间滩涂及近水区域人员禁入规则",
      "risk_level": "HIGH"
    }
  ],
  "message": "已结合补充信息和知识库完成风险复核"
}
```

### 4.2 入库字段

写入 `safety_event_instance.latest_observation`：

```json
{
  "supplemental_context": {
    "context_type": "DAM_DISCHARGE",
    "active": true,
    "label": "库坝正在泄洪",
    "affected_area": "滩涂、消落带、下游河道、近水岸线",
    "note": "泄洪期间禁止人员进入滩涂边活动",
    "submitted_by": "SYSTEM/USER",
    "submitted_at": "2026-08-15T14:20:00+08:00"
  },
  "risk_escalation": {
    "from": "LOW",
    "to": "HIGH",
    "reason": "泄洪期间人员出现在滩涂/近水区域，命中知识库禁入条款",
    "knowledge_clause_ids": ["DISCHARGE-PERSON-001", "DISCHARGE-PERSON-002"]
  }
}
```

追加两条时间线：

```text
SUPPLEMENTAL_CONTEXT：值班人员补充“库坝正在泄洪”
RISK_CHANGE：结合知识库依据，风险由 LOW 升级为 HIGH
```

## 5. 风险升级规则

### 5.1 第一阶段规则

满足以下条件即可升级 HIGH：

1. 补充信息 `context_type=DAM_DISCHARGE` 且 `active=true`；
2. 事件包含人员相关线索：
   - `event_code` 为 `PERSON_INTRUSION`、`PERSON_WATERFRONT`、`PERSON_WADING`；
   - 或 `latest_observation` 中 `person_present=1` / `possible_person=1`；
   - 或 summary/evidence 中包含“人员、滩涂、亲水、涉水、消落带、岸边活动”；
3. 知识库命中至少一条 `risk_level=HIGH` 且 `applicable_event_types` 包含人员/泄洪/滩涂禁入的条款。

### 5.2 大模型输出约束

大模型风险复核必须输出 JSON：

```json
{
  "risk_level_override": "HIGH",
  "confidence": 0.86,
  "reason": "库坝泄洪期间，人员出现在滩涂或近水区域，存在水位快速上涨、冲刷、被困及溺水风险。",
  "matched_clauses": ["DISCHARGE-PERSON-001"],
  "recommended_actions": [
    "立即广播劝离",
    "通知现场巡查人员核查",
    "必要时联动无人机复核滩涂人员位置"
  ]
}
```

如果知识库未命中，不允许仅凭补充信息升级为 HIGH；应输出 `risk_level_override=null`，并把“未命中条款”写入时间线。

## 6. 知识库检索 Query

构造 query 时不要只用事件名，要拼接补充信息和初筛结果：

```text
库坝正在泄洪 滩涂 人员 亲水 涉水 消落带 禁止进入 下游河道 安全管控 风险等级 高风险 处置规范
```

同时传入过滤 hint：

```json
{
  "category": "risk_escalation",
  "event_type": "PERSON_INTRUSION",
  "risk_level": "HIGH",
  "source_type": "regulation"
}
```

## 7. 报告要求

报告中必须新增或填充以下内容：

- 风险等级：高风险；
- 风险升级依据：说明“视频初筛为疑似/低风险，但补充信息表明库坝正在泄洪”；
- 知识库依据：引用命中的条款编号和条款标题；
- 处置建议：
  - 立即广播劝离；
  - 通知现场人员核查；
  - 必要时联动无人机或云台复核；
  - 持续关注泄洪流量、水位和滩涂人员移动情况。

## 8. 实施步骤

1. 前端 `VideoDetection.vue` 增加“补充运行状态”按钮和弹窗。
2. 后端 `integration.py` 增加 supplemental-context 接口。
3. 新增风险复核服务：
   - 写入补充信息；
   - 调 knowledge search；
   - 调大模型输出风险复核 JSON；
   - 更新事件风险和时间线。
4. `dam_workflow_client.build_payload()` 把 `supplemental_context` 和 `risk_escalation` 带入 `sensor_data` 和 prompt。
5. 报告服务读取 `latest_observation.risk_escalation`，写入风险依据和知识库引用。
6. 知识库新增“泄洪期间人员禁入与风险升级规范”文档并完成索引。

## 9. 验收用例

### 用例 1：低风险人员疑似 + 正在泄洪

- 输入视频：滩涂远处疑似人员活动；
- 初筛：`possible_person=1`，风险 LOW；
- 补充：`DAM_DISCHARGE active=true`；
- 知识库：命中 `DISCHARGE-PERSON-001`；
- 结果：事件 `risk_level=HIGH`，报告为高风险并引用知识库。

### 用例 2：低风险人员疑似 + 无补充信息

- 初筛：`possible_person=1`；
- 补充：无；
- 结果：维持 LOW，进入复核但不自动广播。

### 用例 3：正在泄洪 + 无人员线索

- 初筛：无人员/船只；
- 补充：正在泄洪；
- 结果：不创建人员风险升级事件，可记录运行状态但不抬风险。

