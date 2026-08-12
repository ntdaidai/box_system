# 0.8B 摄像头初筛"人员/船只疑似档位"改造说明

- **文档日期**：2026-08-11
- **涉及组件**：dam-backend（FastAPI）、dam-model-library
- **改造范围**：Qwen 0.8B 端侧摄像头初筛 → ECA 事件触发 → 4B/35B 复核 整条链路
- **目标版本**：camera_screening 提示词 v1 → v2

---

## 1. 概述

针对**库坝/河道摄像头远距离、画质差、夜间红外**的实际场景，为**人员**与**船只**两类目标新增"**疑似档位**"：

- 0.8B 端侧初筛在**画质差、距离远、夜间红外、目标很小或目标被遮挡**导致无法确认时，不再直接判"无"并丢弃，而是输出低置信度（0.3 ~ 0.6）；
- 后端据此派生 `possible_person` / `possible_boat` **疑似位**，保留疑似证据；
- ECA 触发条件由"仅确认命中"升级为"**确认命中 OR 疑似命中**"，让疑似事件**进入 4B/35B 复核**；
- 疑似事件**风险降级为 LOW、不自动广播**，避免打扰，等待云端复核确认。

自然灾害（泥石流/滑坡/洪水/地震）四类**维持原判定**，不做疑似处理。

---

## 2. 背景与问题

### 2.1 现状链路

```
摄像头关键帧 → Qwen 0.8B 初筛 JSON → 后端解析(置信度归一+归零) → ECA 条件判断 → 事件实例 + 时间线 → 4B 边缘分析 / 35B 云端复核 → 报告
```

### 2.2 痛点

| 问题 | 具体表现 | 后果 |
|---|---|---|
| **宁缺毋滥** | 0.8B 对人员/船只的 `confidence < 0.65` 时，`person_present`/`boat_present` 被强制归零 | 远处船只、模糊人影直接判"无"，疑似证据被丢弃 |
| **复核不唤起** | ECA 触发条件只认确认位（`person_present == 1`） | 疑似场景不建事件，下游 4B/35B 不复核，漏报 |
| **用户诉求** | 人员/船只目标距离远、画质差，端侧**能给出疑似结果即可** | 期望"宁滥勿缺"式疑似 → 交云端确认，而非直接丢弃 |

### 2.3 关键设计决策（用户已确认）

1. **场景范围**：仅人员、船只两类加疑似档位；自然灾害维持"证据不足输出 0"。
2. **疑似档位**：`confidence ≥ 0.65` → 确认；`0.3 ≤ confidence < 0.65` → 疑似；`< 0.3` → 无。
3. **疑似处理**：降级触发 · 不打扰 —— 建事件进复核，但风险压 LOW、不广播、标记"疑似待确认"。

---

## 3. 分级判定规则

仅人员/船只生效（后端派生，模型无需输出 `possible_*`）：

| confidence 区间 | person/boat 确认位 | possible_* 疑似位 | 下游行为 |
|---|---|---|---|
| `≥ 0.65`（清晰可见） | `person_present`/`boat_present = 1` | 0 | 按 event_library 配置的正常风险触发，可广播 |
| `0.30 ~ 0.65`（画质差/距离远/夜间红外/目标很小/遮挡） | 0 | `possible_person`/`possible_boat = 1` | 触发进入复核，风险压 **LOW**，不自动广播 |
| `< 0.30` | 0 | 0 | 不触发 |

- 边界说明：`0.30` 含（疑似下界 inclusive）；`0.65` 不含（疑似），`0.65` 起为确认。
- 阈值可配置：环境变量 `QWEN_CAMERA_SCREENING_MIN_CONFIDENCE`（默认 `0.65`）、`QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE`（默认 `0.30`）。

---

## 4. 端到端数据流

```
Qwen 0.8B 初筛 JSON
  { scene: {person_present: 0, ...}, confidence: {person_confidence: 0.5, ...}, ... }
        │
        ▼
qwen_camera_screening._parse_result        ← ① 疑似派生（739-750 行）
  低置信确认位归零后：person_present=0, possible_person=1
        │
        ▼
vision_detector.update_qwen_screening_result  ← ② 变量注入（mapping 含 possible_*）
        │
        ▼
vision_detector.get_detection_snapshot     ← ③ 扁平化 ECA 变量
  { person_present:0, possible_person:1, person_confidence:0.5, ... }
        │
        ▼
eca_engine.trigger_camera_event            ← ④ 疑似检测 + 降级（1791-1802 行）
  suspected=True, risk="LOW", observation 打标
        │
        ▼
ECA 条件表达式（OR 形式）→ 触发事件实例
  person_present == 1 OR possible_person == 1   ← 疑似也触发
        │
        ├──► plan_dam_workflow：4B 边缘分析 / 35B 云端复核（不阻断）
        └──► broadcast_service：疑似事件被守卫拦截，不自动广播
```

---

## 5. 详细改动清单

### 5.1 配置阈值 —— dam-backend/app/core/config.py

| 位置 | 内容 |
|---|---|
| [config.py:66-71](../dam-backend/app/core/config.py#L66-L71) | 在 `QWEN_CAMERA_SCREENING_MIN_CONFIDENCE`（0.65）旁新增 `QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE = 0.30`，即疑似档下界；低于该值视为无 |

```python
# 人员/船只疑似档下界：低于该值视为无；介于 [下界, MIN_CONFIDENCE) 视为疑似(possible_*)
QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE: float = float(
    _get_env("QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE", "0.30")
)
```

### 5.2 初筛产出侧 —— dam-backend/app/services/qwen_camera_screening.py

**a) SYSTEM_PROMPT 措辞（[30-72 行](../dam-backend/app/services/qwen_camera_screening.py#L30-L72)）**

新增人员/船只疑似规则（[66-69 行](../dam-backend/app/services/qwen_camera_screening.py#L66-L69)）：

```
- 人员/船只规则：画面清晰、明确看到人员或船只时，detected 输出 1，confidence 给 0.65 以上。
  如果画质差、距离远、夜间红外、目标很小或目标被遮挡，只能确认存在疑似迹象而无法确认时，
  detected 输出 0，但请给出 0.3 ~ 0.6 的 confidence（不要直接给 0），并把不确定因素写入 uncertainties。
  系统会根据该置信度自动标记 possible_person/possible_boat 疑似位，你无需输出这两个字段。
- 夜间电鱼/偷捕弱特征：小船或漂浮目标在水面移动、船后尾迹/扰动水纹、靠近水面的异常强光/探照灯、
  凌晨或夜间河面活动，即使目标小或模糊，也应作为船只/捕鱼疑似线索处理：
  boat_present 输出 0，boat_confidence 给 0.35 ~ 0.60，并在 evidence 中说明。
- 特别注意夜间河面小目标：如果连续帧中出现水面移动暗斑、细长漂浮目标、尾迹/扰动水纹，
  或靠近水面的异常强光，即使看不清船体，也不允许把 boat_confidence 写成 0；
  应按“疑似船只/疑似捕鱼”输出 boat_present=0、boat_confidence=0.35~0.60，并在 uncertainties 中说明待复核确认。
```

自然灾害规则明确**保持不变**（证据不足仍输出 0，不低置信硬凑）。

**b) `_parse_result` 疑似派生块（[739-750 行](../dam-backend/app/services/qwen_camera_screening.py#L739-L750)）**

解析时兼容模型偶发字段漂移：若 `confidence` 中误写为 `person_present` / `boat_present`，会自动归一到 `person_confidence` / `boat_confidence`，避免疑似信号被丢弃。

放在归零循环（726-736 行）与 `_enforce_single_scene`（737 行）**之后**、risk 抬升（751-759 行）**之前**：

```python
# 疑似档派生：人员/船只低置信(0.3~0.65)不归零，另置 possible_* 位。
# 注意 possible_* 不进 scene_keys，避免下方 risk 抬升把纯疑似误判为 MEDIUM。
suspect_min = max(0.0, min(settings.QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE, 1.0))
for confirmed_key, possible_key, conf_key in (
    ("person_present", "possible_person", "person_confidence"),
    ("boat_present", "possible_boat", "boat_confidence"),
):
    score = float(confidence.get(conf_key, 0.0) or 0.0)
    if int(scene.get(confirmed_key, 0) or 0) == 0 and suspect_min <= score < min_confidence:
        scene[possible_key] = 1
    else:
        scene[possible_key] = 0
```

**关键约束**：`possible_*` **绝不加入 `scene_keys`**，否则归零循环会误处理、且 754-759 行的 `scene_keys[4:]` 会把纯疑似误抬为 MEDIUM。`_enforce_single_scene` 只清 6 对确认 key，天然不碰 possible，因此"人员确认 + 船只疑似"可以共存。

### 5.3 变量注入 —— dam-backend/app/services/vision_detector.py

| 位置 | 内容 |
|---|---|
| [detection_types 55-76 行](../dam-backend/app/services/vision_detector.py#L55-L76) | 新增 `possible_person`、`possible_boat` 检测类型，`variable` 分别为 `possible_person`/`possible_boat`（驱动 `get_detection_snapshot` 扁平化输出 ECA 变量） |
| [mapping 189-198 行](../dam-backend/app/services/vision_detector.py#L189-L198) | `update_qwen_screening_result` 的映射新增 `"possible_person": ("possible_person", "person_confidence")`、`"possible_boat": ("possible_boat", "boat_confidence")`，置信度复用 person/boat 值 |
| [219 行](../dam-backend/app/services/vision_detector.py#L219) | 修复默认值陷阱：`default_score = 1.0 if (detected and not detection_type.startswith("possible_")) else 0.0` —— possible 条目缺失 confidence 时强制默认 0，避免回落到 1.0 |

> 注意：`get_detection_snapshot` 会额外输出 `possible_person_confidence` 等镜像键（[318 行](../dam-backend/app/services/vision_detector.py#L318)）。经确认**无任何表达式引用这些镜像键**，属无害噪声，本期保留。

### 5.4 ECA 触发条件（双事实来源同步）—— OR 表达式

触发条件有两个事实来源，需同步改：

**a) 运行时定义** —— [camera_zone_store.py:102-111](../dam-backend/app/services/camera_zone_store.py#L102-L111)

```python
"PERSON_LOW":   (("PERSON_INTRUSION", "person_present == 1 OR possible_person == 1", "人员闯入", 5),),
"PERSON_MEDIUM": (("PERSON_WATERFRONT", "person_present == 1 OR possible_person == 1", "人员亲水", 3),),
"PERSON_HIGH":  (("PERSON_WADING", "person_present == 1 OR possible_person == 1", "人员涉水", 0),),
# BOAT_* 同理：boat_present == 1 OR possible_boat == 1
```

`ensure_visual_event_conditions` 保存区域时会用该定义覆盖 DB，无需额外处理。

**b) 历史迁移脚本** —— [migrate_20260806_event_runtime_simplification.py:30-37](../dam-backend/scripts/migrate_20260806_event_runtime_simplification.py#L30-L37)

`VISUAL_EVENTS` 中 6 类事件表达式同步改为 OR 形式（仅一致性；线上库由新迁移脚本 UPDATE，见第 6 节）。

> 表达式语法要求：ECA 手写解析器 `_evaluate_expression` 原生支持 `OR`；`_evaluate_comparison` 右侧必须为数值字面量（`== 1`），OR 两侧保留空格。

### 5.5 疑似降级核心 —— dam-backend/app/services/eca_engine.py

**a) 告警类型** —— [`_determine_alarm_type` 1599-1605 行](../dam-backend/app/services/eca_engine.py#L1599-L1605)

`vision_variables` 集合新增 `possible_person`/`possible_boat`，使纯疑似命中归为 `"ai"` 告警类型（AI 检测类告警）。

**b) 疑似检测与降级** —— [`trigger_camera_event` 1768-1875 行](../dam-backend/app/services/eca_engine.py#L1768-L1875)

- 疑似判定（[1791-1797 行](../dam-backend/app/services/eca_engine.py#L1791-L1797)）：

```python
# 疑似命中检测：人员/船只低置信（possible_*==1 且对应确认位!=1）→ 降级 LOW 并标记待复核
suspected = (
    int(observation.get("possible_person") or 0) == 1
    and int(observation.get("person_present") or 0) != 1
) or (
    int(observation.get("possible_boat") or 0) == 1
    and int(observation.get("boat_present") or 0) != 1
)
```

- 疑似时（[1798-1802 行](../dam-backend/app/services/eca_engine.py#L1798-L1802)）：
  - `risk = "LOW"`（覆盖 event_library 配置的正常风险）；
  - `observation["suspected"] = True`、`suspected_label = "疑似人员/船只待复核"`、`screening_note = "0.8B 初筛低置信命中，已进入 4B/35B 复核，风险等级按 LOW 降级处理"`。
- 新建事件分支（[1824-1862 行](../dam-backend/app/services/eca_engine.py#L1824-L1862)）：timeline 消息追加"**（疑似命中，待4B/35B复核确认）**"（[1852-1853 行](../dam-backend/app/services/eca_engine.py#L1852-L1853)），payload 加 `"suspected": suspected`（[1858 行](../dam-backend/app/services/eca_engine.py#L1858)）。
- 复用分支（[1814-1822 行](../dam-backend/app/services/eca_engine.py#L1814-L1822)）：`risk_level` 同样被压 LOW，`max_risk_level` 保留历史最高；该分支只更新实例、**不新建 timeline**（既有行为）。
- **不阻断复核**：`plan_dam_workflow`（[889 行](../dam-backend/app/services/eca_engine.py#L889)）在动作执行阶段无条件调度，疑似事件照常走 4B/35B。

### 5.6 广播兜底 —— dam-backend/app/services/broadcast_service.py

[`handle_safety_event_action` 432-453 行](../dam-backend/app/services/broadcast_service.py#L432-L453) 在 `_allow_auto` 前新增疑似守卫：

```python
# 疑似事件（latest_observation.suspected）不自动广播；不影响 4B/35B 复核链路
try:
    from app.models.safety_integration import SafetyEventInstance
    inst = db.query(SafetyEventInstance).filter(
        SafetyEventInstance.instance_no == str(event_id)
    ).first()
    if inst and bool((inst.latest_observation or {}).get("suspected")):
        return
except Exception:
    pass  # 查询失败不阻断既有广播逻辑
```

> 说明：Qwen 初筛路径本身不发布 AUTO_BROADCAST（自动广播唯一入口是 main.py 的 bus 订阅，由 YOLO track 链路发布），该守卫仅作为**兜底**，防止未来广播路径对疑似事件误发。已通过单测覆盖（确认事件仍广播、疑似事件不广播）。

### 5.7 下游白名单透传

疑似字段必须在各层白名单中透传，否则进入工作流前被裁剪：

| 文件 | 位置 | 改动 |
|---|---|---|
| dam-backend/app/services/dam_workflow_client.py | [`_compact_sensor_data` keep_keys 284-285 行](../dam-backend/app/services/dam_workflow_client.py#L284-L285) | 新增 `possible_person`/`possible_boat` |
| dam-model-library/app/services/workflow_executor_service.py | [`_slim_sensor_data` keep 490-491 行](../dam-model-library/app/services/workflow_executor_service.py#L490-L491) | 新增 `possible_person`/`possible_boat` |

### 5.8 报告展示 —— dam-backend/app/services/dam_event_report_service.py

| 位置 | 改动 |
|---|---|
| [`screening_summary` 1155-1161 行](../dam-backend/app/services/dam_event_report_service.py#L1155-L1161) | 新增"疑似待复核：疑似人员/疑似船只"，输出格式：`初筛命中：{命中}；疑似待复核：{疑似}；未命中/排除：{排除}；风险等级：{风险}。` |
| [`workflow_insight` 1520-1534 行](../dam-backend/app/services/dam_event_report_service.py#L1520-L1534) | result 新增 `possible_person`/`possible_boat`/`suspected`（`suspected` 由任一 possible 位派生） |

---

## 6. 数据库迁移

### 6.1 迁移内容

| 目标 | 变更 |
|---|---|
| `actor_prompt_stage`（camera_screening / qwen0_8b / 活跃记录） | `system_prompt` 更新为含疑似规则的 v2 文案，`version` v1 → v2 |
| `actor_prompt_stage` 推理参数 | `temperature=0.0`、`max_tokens=512`，降低 0.8B 初筛随机漂移并避免 2048 上下文溢出 |
| `condition_library`（`[VISUAL_ECA:*]` marker，6 类事件） | `expression` 升级为 OR 形式 |

涉及脚本：

1. **`scripts/migrate_20260811_camera_screening_suspect.py`**（新建，主力）——遵循既有惯例（`--apply` + 只读 audit + JSON 备份 + `schema_migration` 表幂等防重跑）：
   - `MIGRATION_ID = "20260811_camera_screening_suspect_v1"`
   - 更新 `actor_prompt_stage` 的 camera_screening 记录（完整 prompt 文本 + version=v2）
   - 按 `[VISUAL_ECA:{event_code}]%` marker UPDATE `condition_library.expression` 为 OR 形式
   - 写 JSON 备份到 `backups/` 后记录 `schema_migration`，已应用时直接抛错拒绝重跑
2. **`scripts/migrate_actor_prompt_stage.sql`**（同步更新）——camera_screening 插入/更新文案改为 v2（`ON DUPLICATE KEY UPDATE` 幂等；`_get_camera_screening_prompt` 按 update_time/id 排序、不依赖 version，安全）。

### 6.2 执行方式

```bash
cd /home/jetson/box_system/dam-backend

# 只读审计（不落库）
MYSQL_URL="mysql+pymysql://root:root@<目标库IP>:3306/dam_system" \
  python scripts/migrate_20260811_camera_screening_suspect.py

# 落库
MYSQL_URL="mysql+pymysql://root:root@<目标库IP>:3306/dam_system" \
  python scripts/migrate_20260811_camera_screening_suspect.py --apply
```

> ⚠️ **默认连接 `192.168.31.52:3306` 生产库**，执行前必须用 `MYSQL_URL` 显式指定目标库，防止误连生产。

### 6.3 当前执行状态（2026-08-11）

- ✅ **当前运行库已 `--apply`**，抽查确认：
  - `actor_prompt_stage` camera_screening：`version=v2`、`is_active=1`、含 `possible_person` 规则；
  - `condition_library`：PERSON_*/BOAT_* 6 类事件各 3 条，共 18 条表达式全部升级为 OR；
  - `schema_migration` 已记录 `20260811_camera_screening_suspect_v1`，防重跑。
- ⏳ 如需迁移到其他环境，按 6.2 节显式指定 `MYSQL_URL` 后先审计、再 `--apply`。

---

## 7. 测试与验证

### 7.1 新增/修改单测（全部通过）

| 测试文件 | 数量 | 覆盖点 |
|---|---|---|
| dam-backend/tests/test_qwen_camera_screening_parse.py（新增） | 9 | 三级判定（确认/疑似/无）、边界值（0.30 含、0.65 不含）、确认+疑似共存、自然灾害不产生 possible、ECA OR 表达式求值 |
| dam-backend/tests/test_broadcast_service.py（+2） | 13 | 疑似事件跳过自动广播、确认事件仍广播 |
| dam-model-library/tests/test_workflow_executor_service.py（+1） | 6 | `_slim_sensor_data` 保留疑似字段 |

### 7.2 端到端集成验证（连本地已迁移库，真实链路，12/12 通过）

> 脚本：`/tmp/camera_suspect_e2e.py`（初筛解析 → 变量注入 → ECA 触发，验证后自动清理写入数据）

| 场景 | 输入 | 结果 |
|---|---|---|
| 模糊人影（远处/画质差） | `person_confidence=0.5` | `possible_person=1`、risk 降 **LOW**、`suspected=true`、timeline 含"疑似命中"、payload.suspected=true |
| 清晰人员（近距清晰） | `person_confidence=0.8` | `person_present=1`、`possible_person=0`、risk 保持 **HIGH**（PERSON_WADING=3）、无 suspected、timeline 无"疑似命中" |

### 7.3 回归测试（相关既有测试全部通过）

| 测试 | 结果 |
|---|---|
| test_safety_event_engine | 11 通过 |
| test_eca_runtime_boundary | 3 通过 |
| test_camera_api_contract | 4 通过 |
| test_camera_config_and_ticket | 2 通过 |
| dam-model-library 全量 | 6 通过 |

### 7.4 既有失败（与本次改动无关，git 确认未改动相关文件）

| 测试 | 失败原因 |
|---|---|
| test_eca_wind | 硬编码查询 `ConditionLibrary.id == 5`，本地库无此记录（id 从 8 开始），系针对生产库数据的既有测试假设 |
| test_camera_http_flow | 测试文件自身缺 `from unittest.mock import patch` 导入，`NameError`，为既有缺陷 |

---

## 8. 部署与上线

1. **代码**：dam-backend、dam-model-library 改动随正常发布流程部署。
2. **迁移**：目标库执行 6.2 节命令（确认 `MYSQL_URL` 指向正确环境）。
3. **重启后端**：DB 侧 `actor_prompt_stage` 提示词有 **60s 缓存**，改后需等缓存过期或重启 dam-backend 才能生效；内置 `SYSTEM_PROMPT`（代码常量）与 DB 记录双源须一致。
4. **可选**：前端 `EventConfig` 暂不识 `possible_*` 变量，本期不改也能工作（运行时以 condition_library 为准），如需展示标签可后续补充。

---

## 9. 回滚方案

| 层 | 回滚动作 |
|---|---|
| 表达式 | 将 `condition_library` 中 `[VISUAL_ECA:*]` 6 类事件的 `expression` 恢复为 `person_present == 1` / `boat_present == 1`（迁移前 JSON 备份在 `dam-backend/backups/camera_screening_suspect_*.json`） |
| 提示词 | 将 `actor_prompt_stage` camera_screening 记录回退为 v1 文案（备份同上），或重新执行旧版 `migrate_actor_prompt_stage.sql` |
| 代码 | git 回退相关文件：`config.py`、`qwen_camera_screening.py`、`vision_detector.py`、`camera_zone_store.py`、`eca_engine.py`、`broadcast_service.py`、`dam_workflow_client.py`、`dam_event_report_service.py`、`workflow_executor_service.py` |
| 已迁移标记 | 如需重跑迁移，删除 `schema_migration` 中 `20260811_camera_screening_suspect_v1` 记录后重新执行（迁移内含幂等保护，正常不可重跑） |

---

## 10. 风险与注意事项

- **`possible_*` 不进 `scene_keys`**：这是最关键的约束，否则归零循环与 risk 抬升（`scene_keys[4:]`）会破坏疑似逻辑。
- **表达式语法**：`== 1` 数值字面量（ECA 手写解析器要求），OR 两侧留空格。
- **prompt 双源**：DB 记录 + 内置 `SYSTEM_PROMPT` 必须同步修改，避免行为漂移。
- **镜像键噪声**：`get_detection_snapshot` 会输出 `possible_person_confidence` 等键，已确认无表达式引用，属无害噪声。
- **复用分支**：疑似事件若复用了历史 ACTIVE 实例，复用分支只更新实例、不新增"疑似命中" timeline（既有行为），risk 与 `suspected` 标记仍正确更新。
- **广播守卫是兜底**：Qwen 初筛链路本身不广播，守卫仅防未来广播路径误发疑似事件。

---

## 11. 相关文件索引

| 组件 | 文件 |
|---|---|
| 阈值配置 | dam-backend/app/core/config.py |
| 初筛解析与提示词 | dam-backend/app/services/qwen_camera_screening.py |
| ECA 变量注入 | dam-backend/app/services/vision_detector.py |
| 触发条件（运行时） | dam-backend/app/services/camera_zone_store.py |
| 触发条件（历史迁移） | dam-backend/scripts/migrate_20260806_event_runtime_simplification.py |
| 疑似降级触发 | dam-backend/app/services/eca_engine.py |
| 广播守卫 | dam-backend/app/services/broadcast_service.py |
| 工作流透传（后端） | dam-backend/app/services/dam_workflow_client.py |
| 工作流透传（模型库） | dam-model-library/app/services/workflow_executor_service.py |
| 报告展示 | dam-backend/app/services/dam_event_report_service.py |
| 迁移脚本（新建） | dam-backend/scripts/migrate_20260811_camera_screening_suspect.py |
| 提示词迁移 SQL | dam-backend/scripts/migrate_actor_prompt_stage.sql |
| 解析/表达式单测（新增） | dam-backend/tests/test_qwen_camera_screening_parse.py |
