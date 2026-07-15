# DAM 库坝应急巡查工作流生成系统 — 架构设计文档

## 1. 系统概述

### 1.1 定位

**库坝应急巡查智能感知系统中的工作流规划智能体**。系统根据**已确定的事件类型**和现场图片，自动规划最合理的视觉分析流程，并生成专业的事件分析报告。

**注意**：事件类型已由系统确定（传感器、规则引擎或变化检测模块），本系统不重新判断事件是否发生，也不对事件类型进行分类。

### 1.2 核心设计原则

#### 1.2.1 任务分析原则

根据当前事件，首先分析完成本次事件分析所需要的视觉任务（如目标检测、区域分割、变化检测、裂缝识别、场景理解等），而不是重新识别事件类型。

#### 1.2.2 模型调用原则

1. **专有模型优先**：优先调用针对具体任务微调后的专有模型完成视觉识别
2. **小模型优先**：能够由轻量模型完成的任务，不调用多模态大模型
3. **大模型负责理解与推理**：仅在需要综合分析时，调用多模态大模型结合专有模型输出进行场景理解、风险推理、结果解释、影响分析及处置建议生成，而不是重复执行目标检测或目标识别
4. **避免重复分析**：已经由专有模型完成识别的目标，大模型不得再次识别，应直接利用识别结果完成高层语义分析
5. **工作流应尽量简洁高效**：仅调用完成当前事件分析所必需的模型，减少不必要的模型调用，提高边缘计算效率

#### 1.2.3 输出规范

- 内部自动完成工作流规划（DAG 生成、模型挂载、IO 配对）
- **仅输出**一份完整的事件分析报告

### 1.3 与主系统（Layer 2）的对比

| 维度 | 主系统 Layer 2 | DAM 轻量版 |
|---|---|---|
| 输入 | 自然语言意图（多轮澄清） | 结构化输入（事件类型 + 图片 + 传感器） |
| 节点类型 | START / ACTION / CONDITION / EVALUATION / END | START / ACTION / EVALUATION / END |
| DAG 生成 | 两阶段 LLM（节点规划 + 边生成） | 模板匹配 + 单阶段 LLM（8B 模型） |
| 模型挂载 | UCB-MoE 语义路由 + pgvector | 事件→模型映射表 + 规则匹配 |
| IO 配对 | LLM 生成 + 10+ 修复函数 | 固定模板优先，LLM 兜底（0.8B 模型） |
| 校验 | 拓扑校验 + data_flow 校验 + LLM 评分 | 无（省资源） |
| 输出 | 可执行 DAG + 工作流详情 | 仅事件分析报告（不暴露内部流程） |
| LLM 调用次数 | 5-8 次 | 0-2 次 |

### 1.4 LLM 模型分配策略

系统使用两个不同规模的 LLM 模型，根据任务复杂度分配：

| 模型 | 参数规模 | 使用场景 | 调用次数 |
|---|---|---|---|
| **8B 模型** | 80亿参数 | DAG 生成（工作流规划） | 0-1 次 |
| **0.8B 模型** | 8000万参数 | 智能推理、IO 兜底、评价报告生成 | 1-3 次 |

**分配原则**：
- **8B 模型**：仅用于需要复杂推理的任务规划阶段（DAG 生成），确保工作流规划质量
- **0.8B 模型**：用于执行阶段的轻量级任务（场景理解、IO匹配、报告生成），降低边缘设备资源消耗

---

## 2. 输入规范

### 2.1 结构化输入

```python
class DamInput(TypedDict):
    """DAM 系统标准输入"""
    event_type: str                # 已确定的事件类型（如 "滑坡"、"裂缝"、"渗漏"）
    images: List[str]              # 现场图片路径列表（1张或多张，必需）
    sensor_data: Optional[dict]    # 传感器信息、设备信息等辅助数据（可选，内容由用户自行填写）
    user_prompt: str               # 完整的系统 prompt（包含事件描述和任务要求）
```

### 2.2 输入示例

```
事件类型: 滑坡事件
图片: [dam_landslide_001.jpg, dam_landslide_002.jpg]
传感器数据: {
    // 字典内容由用户根据实际情况自行填写，系统不约束具体字段
    // 示例字段（仅供参考）：位移量、降雨量、水位、应力、温度等
    // 用户可自由添加任意字段，如 "设备ID": "sensor_001", "采集时间": "2024-01-01 10:00:00" 等
}
```

### 2.3 输入解析

从用户 prompt 中提取结构化信息：

```python
def parse_dam_input(user_prompt: str, images: list, sensor_data: dict = None) -> DamInput:
    """解析 DAM 输入"""
    # 事件类型提取（规则匹配，无 LLM）
    event_type = extract_event_type(user_prompt)
    # 支持的事件类型：
    # - 滑坡 (landslide)
    # - 裂缝 (crack)
    # - 渗漏 (seepage)
    # - 变形 (deformation)
    # - 沉降 (settlement)
    # - 管涌 (piping)

    return {
        "event_type": event_type,
        "images": images,
        "sensor_data": sensor_data,
        "user_prompt": user_prompt,
    }
```

---

## 3. 节点类型体系

### 3.1 四类节点

| 节点类型 | 说明 | 实现类型 | 是否必须 |
|---|---|---|---|
| `START` | 入口节点，接收结构化输入（事件类型 + 图片 + 传感器数据） | 无 | 必须，有且仅一个 |
| `ACTION` | 执行节点，挂载专有微调模型（检测/分割/变化检测）或大模型（场景理解/风险推理） | MODEL / CODE | 至少一个 |
| `EVALUATION` | 评价节点，基于专有模型结果 + 用户 prompt 生成最终事件分析报告 | MODEL（固定 LLM） | 必须，有且仅一个，位于 END 之前 |
| `END` | 出口节点，输出最终报告 | 无 | 必须，有且仅一个 |

### 3.2 ACTION 节点分类

根据"专有模型优先、小模型优先、大模型补充推理"原则，ACTION 节点分为两类：

| 类别 | 模型类型 | 职责 | 示例 |
|---|---|---|---|
| **专业识别** | 专有微调模型（小模型） | 目标检测、语义分割、变化检测、缺陷分类、裂缝识别 | YOLOv8 裂缝检测、U-Net 渗漏分割、变化检测模型 |
| **智能推理** | 0.8B 轻量大模型 | 场景理解、风险推理、异常解释、影响分析、处置建议 | 0.8B 模型进行场景分析和风险评估 |

**关键约束**：
- 智能推理节点**不得重复执行**专业识别节点已完成的任务
- 智能推理节点应**直接利用**专业识别节点的输出结果进行高层语义分析

### 3.3 拓扑约束

```
START → [专业识别_1 → 专业识别_2 → ... → 智能推理] → EVALUATION → END
```

- **无 CONDITION 节点**：应急巡查场景下工作流为线性流程
- **EVALUATION 强制存在**：系统自动在 END 前插入 EVALUATION 节点
- **EVALUATION 唯一且紧邻 END**：EVALUATION 的 `next` 必须是 END
- **专业识别在前，智能推理在后**：专有模型先完成识别，大模型基于识别结果进行推理
- **线性串联**：默认 `专业识别 → 智能推理`，除非事件类型要求并行处理多模态
- **工作流简洁高效**：仅调用完成当前事件分析所必需的模型

### 3.4 节点数据结构

```python
class DamNode(TypedDict, total=False):
    node_id: str                           # 节点 ID
    node_class: str                        # START / ACTION / EVALUATION / END
    node_type: str                         # 业务功能描述
    expected_implementation_type: str      # MODEL / CODE（仅 ACTION/EVALUATION）
    implementation: NodeImplementation     # 实现载体
    data_flow: NodeDataFlow                # 数据流定义
    topology: NodeTopology                 # 拓扑定义（仅 next，无 branches）
    model_category: str                    # "specialized"（专有模型）/ "llm"（大模型）
```

---

## 4. 流水线设计

### 4.1 三阶段流水线

```
START → dag_generator → model_selector → io_configurator → END
```

| 阶段 | 节点 | LLM 调用 | 使用模型 | 说明 |
|---|---|---|---|---|
| 1 | `dag_generator` | 0-1 次 | 8B 模型 | 基于事件类型生成 DAG 骨架（节点 + 边） |
| 2 | `model_selector` | 0 次 | - | 为 ACTION 节点挂载模型，为 EVALUATION 节点注入固定配置 |
| 3 | `io_configurator` | 0-1 次 | 0.8B 模型 | 模板匹配 IO 配对，不匹配时 LLM 兜底 |

**LLM 调用预算**：最多 2 次（dag_generator 1 次 8B + io_configurator 兜底 1 次 0.8B）

### 4.2 状态定义

```python
class DamState(TypedDict, total=False):
    """DAM 轻量工作流状态"""
    # --- 输入 ---
    event_type: str                        # 已确定的事件类型
    images: List[str]                      # 现场图片路径列表（必需）
    sensor_data: Optional[dict]            # 传感器信息、设备信息（可选，内容由用户自行填写）
    user_prompt: str                       # 完整系统 prompt

    # --- 中间产物（内部使用，不对外暴露） ---
    draft_dag: DraftDAG                    # dag_generator 输出
    populated_dag: PopulatedDAG            # model_selector 输出
    final_dag: TypedDAG                    # io_configurator 输出

    # --- 输出 ---
    result_dag: Optional[List[Dict]]       # 最终可执行 DAG（内部使用）
    analysis_report: Optional[str]         # 最终事件分析报告（对外输出）

    # --- 错误 ---
    error_signal: ErrorSignal              # 错误信号
    retry_count: int                       # 重试计数
```

---

## 5. 阶段 1：DAG 生成器（dag_generator）

### 5.1 策略选择

根据事件类型选择生成策略：

| 条件 | 策略 | LLM 调用 | 使用模型 |
|---|---|---|---|
| 事件类型命中预定义模板 | 模板实例化 | 0 次 | - |
| 事件类型未命中模板 | LLM 生成 | 1 次 | **8B 模型** |

### 5.2 事件→模板映射（零 LLM）

预定义每种事件类型的标准化工作流模板。模板设计遵循"专有模型优先、大模型补充推理"原则：

```python
EVENT_WORKFLOW_TEMPLATES = {
    "滑坡": {
        "description": "滑坡事件应急巡查工作流",
        "visual_tasks": ["滑坡区域检测", "滑坡边界分割", "风险推理与处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "滑坡区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "滑坡边界分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "风险推理与处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "裂缝": {
        "description": "裂缝事件应急巡查工作流",
        "visual_tasks": ["裂缝检测与定位", "裂缝宽度测量", "裂缝成因分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "裂缝检测与定位",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_measure", "node_class": "ACTION", "node_type": "裂缝宽度测量",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "裂缝成因分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_measure"},
            {"source": "action_measure", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "渗漏": {
        "description": "渗漏事件应急巡查工作流",
        "visual_tasks": ["渗漏区域检测", "渗漏范围分割", "渗漏成因分析与处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "渗漏区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "渗漏范围分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "渗漏成因分析与处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "变形": {
        "description": "变形事件应急巡查工作流",
        "visual_tasks": ["变形区域检测", "变化检测（对比历史图像）", "变形趋势分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "变形区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_change", "node_class": "ACTION", "node_type": "变化检测（对比历史图像）",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "变形趋势分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_change"},
            {"source": "action_change", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "沉降": {
        "description": "沉降事件应急巡查工作流",
        "visual_tasks": ["沉降区域检测", "沉降成因分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "沉降区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "沉降成因分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "管涌": {
        "description": "管涌事件应急巡查工作流",
        "visual_tasks": ["管涌口检测", "管涌范围分割", "管涌成因分析与应急处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "管涌口检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "管涌范围分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "管涌成因分析与应急处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
}
```

### 5.3 LLM 生成路径（兜底，使用 8B 模型）

当事件类型未命中预定义模板时，使用 **8B 模型**生成：

```python
class DamWorkflowPlan(BaseModel):
    """DAG 生成输出"""
    workflow_complexity: Literal["TRIVIAL", "COMPLEX"]
    visual_tasks: List[str]  # 需要完成的视觉任务列表
    nodes: List[WorkflowDAGNode]
    edges: List[WorkflowDAGEdge]
```

**Prompt 设计要点**：
- 明确告知事件类型已确定，系统任务是规划视觉分析流程
- 注入"专有模型优先、小模型优先、大模型补充推理"原则
- 注入"避免重复分析"原则：大模型不得重复执行专有模型已完成的识别任务
- 注入"工作流简洁高效"原则：仅调用必需的模型
- 明确只有 4 种节点类型（无 CONDITION）
- 强制要求 EVALUATION 节点存在且位于 END 之前
- 强制要求线性拓扑：专业识别在前，智能推理在后
- 注入用户 prompt（包含事件描述和任务要求）

**调用方式**：
```python
# 使用 8B 模型进行 DAG 生成（通过模型库推理接口）
result = call_llm_via_model_registry(model_id=8b_model_id, request_data={"prompt": prompt, "schema": DamWorkflowPlan})
```

### 5.4 EVALUATION 节点强制注入

无论哪种路径，都执行 `ensure_evaluation_node()` 检查：

```python
def ensure_evaluation_node(dag: dict) -> dict:
    """确保 DAG 中存在 EVALUATION 节点，位于 END 之前"""
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    # 检查是否已存在 EVALUATION
    eval_nodes = [n for n in nodes if n.get("node_class") == "EVALUATION"]
    if eval_nodes:
        return dag  # 已存在，不处理

    # 创建 EVALUATION 节点
    eval_node = {
        "node_id": "evaluation_0",
        "node_class": "EVALUATION",
        "node_type": "事件分析报告",
        "expected_implementation_type": "MODEL",
    }

    # 找到 END 节点和它的直接前驱
    end_node = next((n for n in nodes if n.get("node_class") == "END"), None)
    if not end_node:
        raise ValueError("DAG 中缺少 END 节点")

    end_id = end_node["node_id"]
    # 找到原来指向 END 的边
    edges_to_end = [e for e in edges if e.get("target") == end_id]

    # 重定向：原来指向 END 的边改为指向 EVALUATION
    for edge in edges_to_end:
        edge["target"] = "evaluation_0"

    # 添加 EVALUATION → END 边
    edges.append({"source": "evaluation_0", "target": end_id, "condition_branch": None})

    # 插入 EVALUATION 节点（在 END 之前）
    end_idx = nodes.index(end_node)
    nodes.insert(end_idx, eval_node)

    return {"nodes": nodes, "edges": edges}
```

### 5.5 轻量校验

仅做 3 项必要检查，不调用 LLM：

1. **START/END 存在性**：必须有且仅有一个 START 和一个 END
2. **EVALUATION 约束**：有且仅有一个 EVALUATION，其 next 必须是 END
3. **连通性**：从 START BFS 能到达所有节点

---

## 6. 阶段 2：模型选择器（model_selector）

### 6.1 设计原则

- **零 LLM 调用**：所有模型选择通过数据库查询 + 规则匹配完成
- **事件→模型映射**：每种事件类型有预定义的模型组合
- **EVALUATION 固定配置**：从数据库读取固定 prompt 模板

### 6.2 ACTION 节点模型选择

#### 6.2.1 事件→模型映射表

```sql
CREATE TABLE model_event_mapping (
    id INT PRIMARY KEY AUTO_INCREMENT,
    event_type VARCHAR(64) NOT NULL,           -- 事件类型（滑坡/裂缝/渗漏/变形/沉降/管涌）
    task_type VARCHAR(128) NOT NULL,           -- 任务类型（检测/分割/变化检测/推理）
    model_category ENUM('specialized', 'llm') NOT NULL,  -- 模型类别
    model_id INT,                              -- 模型 ID（关联 model_registry.id）
    priority INT DEFAULT 0,                    -- 优先级（数值越大越优先）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_task (event_type, task_type)
);
```

#### 6.2.2 选择流程

```python
def select_model_for_action(node: dict, event_type: str, db_conn) -> dict:
    """为 ACTION 节点选择模型"""
    node_type = node.get("node_type", "")
    model_category = node.get("model_category", "specialized")

    # 1. 从映射表查询候选模型
    candidates = query_event_model_mapping(db_conn, event_type, node_type, model_category)

    if candidates:
        # 2. 按优先级选择
        best = max(candidates, key=lambda x: x["priority"])
        # 3. 从 model_registry + model_deploy_binding 获取完整信息（含推理地址）
        model_info = get_model_with_inference_url(db_conn, best["model_id"])
        return model_info

    # 4. 映射表无命中，从 model_registry 按类型模糊匹配
    return fuzzy_match_model(node_type, model_category, db_conn)
```

#### 6.2.3 模型优先级规则

| 优先级 | 条件 | 说明 |
|---|---|---|
| 1 | 事件→模型映射表精确匹配 | 最佳匹配 |
| 2 | 任务类型 + 模型类别匹配 | 次优匹配 |
| 3 | 模型标签模糊匹配 | 兜底匹配 |

### 6.3 EVALUATION 节点配置

#### 6.3.1 固定 prompt 模板

EVALUATION 节点的 prompt 从数据库 `model_evaluation_template` 表读取：

```sql
CREATE TABLE model_evaluation_template (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(128) NOT NULL,       -- 模板名称
    event_type VARCHAR(64),                    -- 适用事件类型（NULL 表示通用）
    prompt_template TEXT NOT NULL,             -- prompt 模板（含占位符）
    input_schema JSON NOT NULL,                -- 输入 schema
    output_schema JSON NOT NULL,               -- 输出 schema
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_type (event_type)
);
```

#### 6.3.2 prompt 模板设计原则

EVALUATION 节点的 prompt 模板应遵循以下原则：
- **基于上游结果分析**：直接利用专有模型的检测结果，不重复识别
- **仅输出报告**：不输出模型调用过程、模型名称、工作流步骤或推理过程
- **专业且完整**：生成包含事件概述、检测分析、风险评估、处置建议的完整报告

#### 6.3.3 prompt 模板示例（滑坡事件专用）

```
你是库坝应急巡查专家。请根据以下滑坡事件的检测结果和分析数据，生成专业的应急巡查分析报告。

【事件信息】
事件类型: 滑坡事件
{{user_prompt}}

【上游检测结果】
{{detection_results}}

【传感器数据】
{{sensor_data}}

【报告要求】
1. 事件概述：简述滑坡事件的基本情况
2. 检测结果分析：
   - 滑坡区域位置和范围（基于上游检测结果）
   - 滑坡边界分割结果（基于上游分割结果）
   - 滑坡严重程度评估
3. 风险评估：
   - 当前风险等级（低/中/高/极高）
   - 可能的影响范围
   - 发展趋势预测
4. 应急处置建议：
   - 立即采取的措施
   - 后续监测方案
   - 人员疏散建议（如需要）
5. 结论与建议

【重要约束】
- 直接利用上游检测结果，不要重复识别目标
- 仅输出分析报告，不要输出模型调用过程、模型名称或工作流步骤
- 报告应专业、完整、可直接用于决策

输出格式：
- evaluation_report: 详细分析报告（自然语言）
- risk_level: 风险等级（低/中/高/极高）
- compliance_status: 安全状态（安全/警告/危险）
- recommendations: 处置建议列表
```

#### 6.3.4 通用 prompt 模板（事件类型未命中时使用）

```
你是库坝应急巡查专家。请根据以下事件的检测结果和分析数据，生成专业的应急巡查分析报告。

【事件信息】
事件类型: {{event_type}}
{{user_prompt}}

【上游检测结果】
{{detection_results}}

【传感器数据】
{{sensor_data}}

【报告要求】
1. 事件概述：简述事件的基本情况
2. 检测结果分析：基于上游专有模型的检测结果进行分析
3. 风险评估：评估当前风险等级和发展趋势
4. 应急处置建议：提出具体的处置措施和监测方案
5. 结论与建议

【重要约束】
- 直接利用上游检测结果，不要重复识别目标
- 仅输出分析报告，不要输出模型调用过程、模型名称或工作流步骤
- 报告应专业、完整、可直接用于决策

输出格式：
- evaluation_report: 详细分析报告（自然语言）
- risk_level: 风险等级（低/中/高/极高）
- compliance_status: 安全状态（安全/警告/危险）
- recommendations: 处置建议列表
```

#### 6.3.5 EVALUATION 节点配置注入

```python
def configure_evaluation_node(node: dict, event_type: str, user_prompt: str, db_conn) -> dict:
    """为 EVALUATION 节点注入固定配置"""
    # 1. 从数据库读取 prompt 模板（优先匹配事件类型）
    template = fetch_evaluation_template(db_conn, event_type=event_type)
    if not template:
        template = fetch_evaluation_template(db_conn, event_type=None)  # 通用模板

    # 2. 注入固定 IO schema
    node["physical_io_schema"] = {
        "inputs": {
            "detection_results": {"type": "object", "required": True, "description": "上游检测结果"},
            "sensor_data": {"type": "object", "required": False, "description": "传感器数据"},
            "user_prompt": {"type": "string", "required": True, "description": "用户原始需求"},
            "event_type": {"type": "string", "required": True, "description": "事件类型"},
        },
        "outputs": {
            "evaluation_report": {"type": "string", "description": "详细分析报告（自然语言）"},
            "risk_level": {"type": "string", "description": "风险等级（低/中/高/极高）"},
            "compliance_status": {"type": "string", "description": "安全状态（安全/警告/危险）"},
            "recommendations": {"type": "array", "description": "处置建议列表"},
        },
    }

    # 3. 注入连接配置（通过模型库推理接口调用大模型）
    node["implementation"] = {"type": "MODEL_API", "model_id": llm_model_id}
    node["model_name"] = "大模型（通过模型库推理接口）"
    node["inference_method"] = "model_registry_api"  # 标记使用模型库推理接口

    # 4. 存储 prompt 模板引用（执行时填充）
    node["evaluation_template"] = template

    return node
```

### 6.4 CODE 节点处理

与主系统一致：从脚本记忆层检索，未命中则使用预定义的代码片段（不调用 LLM 自动生成）。

---

## 7. 阶段 3：IO 配对器（io_configurator）

### 7.1 设计原则

- **模板优先**：使用预定义的 IO 配对模板，覆盖常见事件类型的工作流
- **规则匹配**：基于字段名和类型的确定性匹配
- **LLM 兜底**：仅在模板和规则都无法匹配时调用 LLM（最多 1 次）

### 7.2 三层匹配策略

```
Layer 1: 模板匹配（0 LLM）
    ↓ 未命中
Layer 2: 规则匹配（0 LLM）
    ↓ 未命中
Layer 3: LLM 兜底（1 LLM）
```

#### 7.2.1 Layer 1：模板匹配

预定义 IO 配对模板，存储在数据库 `model_io_template` 表：

```sql
CREATE TABLE model_io_template (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_name VARCHAR(128) NOT NULL,
    event_type VARCHAR(64),                  -- 适用事件类型
    source_model_category VARCHAR(64),       -- 上游模型类别
    target_model_category VARCHAR(64),       -- 下游模型类别
    field_mapping JSON NOT NULL,             -- 字段映射规则
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_source_target (event_type, source_model_category, target_model_category)
);
```

字段映射规则示例（滑坡事件：检测→分割）：

```json
{
    "event_type": "滑坡",
    "source_category": "object_detection",
    "target_category": "semantic_segmentation",
    "mapping": {
        "inputs": {
            "image": "{{start_0.images}}",
            "detections": "{{action_detect.detections}}"
        },
        "outputs": {
            "segmentation_mask": "action_segment.segmentation_mask"
        }
    }
}
```

#### 7.2.2 Layer 2：规则匹配

当模板未命中时，使用确定性规则：

```python
def rule_based_io_match(source_io: dict, target_io: dict) -> dict:
    """基于规则的 IO 匹配"""
    mapping = {"inputs": {}, "outputs": {}}

    for target_field, target_meta in target_io.get("inputs", {}).items():
        target_type = target_meta.get("type", "any")

        # 规则 1：字段名精确匹配
        if target_field in source_io.get("outputs", {}):
            mapping["inputs"][target_field] = f"{{{{source_node.{target_field}}}}}"
            continue

        # 规则 2：类型兼容匹配
        for source_field, source_meta in source_io.get("outputs", {}).items():
            source_type = source_meta.get("type", "any")
            if is_type_compatible(source_type, target_type):
                mapping["inputs"][target_field] = f"{{{{source_node.{source_field}}}}}"
                break

    return mapping
```

类型兼容矩阵：

```python
TYPE_COMPAT = {
    "image": {"image", "file", "str", "any"},
    "object": {"object", "dict", "any"},
    "array": {"array", "list", "any"},
    "string": {"string", "str", "any"},
    "float": {"float", "number", "int", "any"},
    "int": {"int", "integer", "float", "number", "any"},
}
```

#### 7.2.3 Layer 3：LLM 兜底（使用 0.8B 模型）

仅当 Layer 1 和 Layer 2 都无法完成匹配时调用：

```python
def llm_io_match(source_io: dict, target_io: dict, context: str, db_conn) -> dict:
    """LLM 兜底 IO 匹配（通过模型库推理接口调用）"""
    prompt = f"""
    为以下两个节点配对数据流。

    【上游输出】
    {json.dumps(source_io.get("outputs", {}), ensure_ascii=False)}

    【下游输入】
    {json.dumps(target_io.get("inputs", {}), ensure_ascii=False)}

    【上下文】
    {context}

    输出格式：{{"inputs": {{"field_name": "{{{{source_node.field}}}}"}}, "outputs": {{"field_name": "target_node.field"}}}}
    """
    # 通过模型库推理接口调用大模型
    return call_llm_via_model_registry(model_id=llm_model_id, request_data={"prompt": prompt})
```

### 7.3 特殊节点 IO 处理

#### 7.3.1 START 节点

固定输出，对应结构化输入：

```python
START_OUTPUTS = {
    "event_type": "str",           # 事件类型
    "images": "list",              # 现场图片路径列表
    "sensor_data": "object",       # 传感器数据（可选）
    "user_prompt": "str",          # 用户原始 prompt
}
```

#### 7.3.2 EVALUATION 节点

固定输入输出：

```python
EVALUATION_IO = {
    "inputs": {
        "detection_results": {"type": "object", "required": True, "description": "上游检测结果汇总"},
        "sensor_data": {"type": "object", "required": False, "description": "传感器数据"},
        "user_prompt": {"type": "string", "required": True, "description": "用户原始需求"},
        "event_type": {"type": "string", "required": True, "description": "事件类型"},
    },
    "outputs": {
        "evaluation_report": {"type": "string", "description": "详细分析报告（自然语言）"},
        "risk_level": {"type": "string", "description": "风险等级（低/中/高/极高）"},
        "compliance_status": {"type": "string", "description": "安全状态（安全/警告/危险）"},
        "recommendations": {"type": "array", "description": "处置建议列表"},
    },
}
```

#### 7.3.3 END 节点

固定输入，汇聚所有上游输出：

```python
def build_end_data_flow(predecessors: list, physical_io: dict) -> dict:
    """为 END 节点构建 data_flow"""
    inputs = {}
    for pred_id in predecessors:
        pred_io = physical_io.get(pred_id, {})
        for out_key in pred_io.get("outputs", {}).keys():
            inputs[f"{pred_id}_{out_key}"] = f"{{{{{pred_id}.{out_key}}}}}"
    return {"inputs": inputs, "outputs": {}}
```

---

## 8. API 接口设计

### 8.1 生成事件分析报告

```
POST /api/dam/analyze

Request:
{
    "prompt": "你是一名库坝应急巡查智能感知系统中的工作流规划智能体。\n\n你的职责是根据**已确定的事件类型**和现场图片，自动规划最合理的视觉分析流程，并生成专业的事件分析报告。\n\n注意：事件类型已经由系统确定，你不需要重新判断事件是否发生，也不要对事件类型进行分类。\n\n输入\n\n1. 当前触发事件：滑坡事件。\n2. 现场图片（1张或多张）。\n3. 传感器信息、设备信息等辅助数据（可选）\n\n工作原则\n\n根据当前事件，首先分析完成本次事件分析所需要的视觉任务，例如目标检测、区域分割、变化检测、裂缝识别、场景理解等，而不是重新识别事件类型。\n\n随后，根据视觉任务自动规划最优的模型调用流程，并遵循以下原则：\n\n1. **专有模型优先**。优先调用针对具体任务微调后的专有模型完成视觉识别。\n2. **小模型优先**。能够由轻量模型完成的任务，不调用多模态大模型。\n3. **大模型负责理解与推理**。仅在需要综合分析时，调用多模态大模型结合专有模型输出进行场景理解、风险推理、结果解释、影响分析及处置建议生成，而不是重复执行目标检测或目标识别。\n4. **避免重复分析**。已经由专有模型完成识别的目标，大模型不得再次识别，应直接利用识别结果完成高层语义分析。\n5. **工作流应尽量简洁高效**。仅调用完成当前事件分析所必需的模型，减少不必要的模型调用，提高边缘计算效率。\n\n输出要求\n\n内部需要自动完成工作流规划，但**不要输出模型调用过程、模型名称、工作流步骤或推理过程**。\n\n最终仅输出一份完整的事件分析报告。",
    "images": ["base64_encoded_image..."],
    "sensor_data": {
        "位移量": 15.2,
        "降雨量": 85.0,
        "水位": 32.5
    }
}

Response:
{
    "report": "## 滑坡事件应急巡查分析报告\n\n### 一、事件概述\n...",
    "risk_level": "高",
    "compliance_status": "危险",
    "recommendations": ["立即疏散周边人员", "设置监测点", "..."]
}
```

**注意**：响应中**不包含**工作流规划详情（DAG 结构、模型名称、调用流程等），仅输出最终分析报告。

### 8.2 换模型（内部管理接口）

```
POST /api/dam/swap_model

Request:
{
    "dag": {...},
    "node_id": "action_detect",
    "new_model_id": 123
}

Response:
{
    "dag": {...},
    "io_adapter": {...}
}
```

---

## 9. 数据库与模型库对接

DAM 系统通过**只读访问**轻量级模型库获取模型信息，不涉及容器生命周期管理。

### 9.1 DAM 专属表

| 表名 | 用途 | 关键字段 |
|---|---|---|
| `model_event_mapping` | 事件→模型映射 | event_type, task_type, model_category, model_id, priority |
| `model_evaluation_template` | 评价 prompt 模板 | event_type, prompt_template, input_schema, output_schema |
| `model_io_template` | IO 配对模板 | event_type, source_model_category, target_model_category, field_mapping |

#### 9.1.1 model_event_mapping — 事件→模型映射表

```sql
CREATE TABLE `model_event_mapping` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `event_type`      VARCHAR(64)   NOT NULL COMMENT '事件类型（滑坡/裂缝/渗漏/变形/沉降/管涌）',
  `task_type`       VARCHAR(128)  NOT NULL COMMENT '任务类型（检测/分割/变化检测/推理）',
  `model_category`  ENUM('specialized', 'llm') NOT NULL COMMENT '模型类别：specialized=专有模型，llm=大模型',
  `model_id`        BIGINT        DEFAULT NULL COMMENT '模型 ID（关联 model_registry.id）',
  `priority`        INT           NOT NULL DEFAULT 0 COMMENT '优先级（数值越大越优先）',
  `remark`          VARCHAR(256)  DEFAULT NULL COMMENT '备注说明',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_task` (`event_type`, `task_type`),
  KEY `idx_model_id` (`model_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件→模型映射表';
```

#### 9.1.2 model_evaluation_template — 评价 prompt 模板表

```sql
CREATE TABLE `model_evaluation_template` (
  `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name`   VARCHAR(128)  NOT NULL COMMENT '模板名称',
  `event_type`      VARCHAR(64)   DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用模板）',
  `prompt_template` TEXT          NOT NULL COMMENT 'prompt 模板（含占位符：{{user_prompt}}, {{detection_results}}, {{sensor_data}}）',
  `input_schema`    JSON          NOT NULL COMMENT '输入 schema 定义',
  `output_schema`   JSON          NOT NULL COMMENT '输出 schema 定义',
  `is_active`       TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否启用：0=禁用，1=启用',
  `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_type` (`event_type`),
  UNIQUE KEY `uk_template_name` (`template_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价 prompt 模板表';
```

#### 9.1.3 model_io_template — IO 配对模板表

```sql
CREATE TABLE `model_io_template` (
  `id`                    BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `template_name`         VARCHAR(128)  NOT NULL COMMENT '模板名称',
  `event_type`            VARCHAR(64)   DEFAULT NULL COMMENT '适用事件类型（NULL 表示通用）',
  `source_model_category` VARCHAR(64)   NOT NULL COMMENT '上游模型类别（specialized/llm）',
  `target_model_category` VARCHAR(64)   NOT NULL COMMENT '下游模型类别（specialized/llm）',
  `source_task_type`      VARCHAR(128)  DEFAULT NULL COMMENT '上游任务类型（可选，用于精确匹配）',
  `target_task_type`      VARCHAR(128)  DEFAULT NULL COMMENT '下游任务类型（可选，用于精确匹配）',
  `field_mapping`         JSON          NOT NULL COMMENT '字段映射规则',
  `create_time`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_event_source_target` (`event_type`, `source_model_category`, `target_model_category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IO 配对模板表';
```

### 9.2 依赖的模型库数据

| 数据 | 来源表 | DAM 中的用途 |
|---|---|---|
| 模型基本信息 | `model_registry` | 查询可用模型（按 model_type、framework 筛选） |
| 模型 IO Schema | `model_io_schema` | 获取输入输出定义，用于 IO 配对 |
| 推理地址 | `model_deploy_binding` | 拼接 `inference_url` 供执行引擎调用 |

### 9.3 推理地址拼接

模型库中每个模型的推理地址格式：

```
http://{host_ip}:{host_port}{inference_path}
```

地址从 `model_deploy_binding` 表查询获得，无需硬编码。

### 9.4 大模型调用方式

**当前状态**：AGX 上暂未部署 0.8B 大模型，大模型调用统一通过模型库的推理接口代理。

**调用方式**：通过模型库的 `/api/model-registry/{id}/infer` 接口调用大模型，DAM 系统不直接连接大模型。

```python
def call_llm_via_model_registry(model_id: int, request_data: dict) -> dict:
    """通过模型库推理接口调用大模型

    Args:
        model_id: 大模型在 model_registry 中的 ID
        request_data: 推理请求数据

    Returns:
        推理结果
    """
    import httpx

    # 调用模型库的推理代理接口
    url = f"http://192.168.31.52:5001/api/model-registry/{model_id}/infer"
    response = httpx.post(url, json={"request_data": request_data}, timeout=60)
    return response.json()
```

**使用场景**：
- DAG 生成（8B 模型兜底）：`call_llm_via_model_registry(model_id=8b_model_id, ...)`
- 评价报告生成（0.8B 模型）：`call_llm_via_model_registry(model_id=0_8b_model_id, ...)`
- IO 配对兜底（0.8B 模型）：`call_llm_via_model_registry(model_id=0_8b_model_id, ...)`

### 9.5 模型选择器查询示例

```python
def get_model_with_inference_url(model_id: int, db_conn) -> dict:
    """获取模型信息（含推理地址）"""
    model = db_conn.query(ModelRegistry).get(model_id)
    binding = db_conn.query(ModelDeployBinding).filter_by(model_id=model_id).first()
    schema = db_conn.query(ModelIOSchema).filter_by(model_id=model_id).first()

    return {
        "model_id": model.id,
        "model_name": model.name,
        "model_type": model.model_type,
        "framework": model.framework,
        "inference_url": f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path}" if binding else None,
        "io_schema": {
            "inputs": schema.inputs if schema else None,
            "outputs": schema.outputs if schema else None,
        },
    }
```

### 9.6 IO Schema 获取

```python
def get_model_io_schema(model_id: int, db_conn) -> dict:
    """从模型库获取模型的 IO Schema"""
    schema = db_conn.query(ModelIOSchema).filter_by(model_id=model_id).first()

    if schema:
        return {
            "inputs": schema.inputs,   # [{"field": "image", "type": "image", ...}]
            "outputs": schema.outputs  # [{"field": "detections", "type": "json", ...}]
        }

    return None
```

### 9.7 DAM 需要的模型库接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/model-registry` | GET | 按条件筛选模型列表 |
| `/api/model-registry/{id}` | GET | 获取模型详情 + inference_url |
| `/api/model-registry/{id}/io-schema` | GET | 获取模型 IO Schema |

### 9.8 数据库配置

DAM 系统需要连接模型库的 MySQL 实例：

```python
# config.py
MODEL_REGISTRY_DB = {
    "host": "192.168.31.52",  # 模型库数据库地址（或 127.0.0.1 本地访问）
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "dam_system"
}
```

---

## 10. 与主系统的关系

### 10.1 代码复用

| 复用内容 | 来源 | 复用方式 |
|---|---|---|
| `DAGNode` / `DraftDAG` / `PopulatedDAG` 等类型 | `layer2_workflow_generation/state.py` | 直接 import |
| `WorkflowDAGNode` / `WorkflowDAGEdge` Pydantic 模型 | `layer2_workflow_generation/dag_generator.py` | 直接 import |
| `build_topology_from_edges` 等拓扑工具 | `layer2_workflow_generation/tools/topology_utils.py` | 直接 import |
| `check_io_compatibility` IO 兼容性检查 | `layer2_workflow_generation/tools/io_compatibility.py` | 直接 import |
| `call_llm_via_model_registry` | 模型库推理接口 | HTTP 调用 |
| `call_llm_via_model_registry` LLM 调用 | 模型库推理接口 | 通过 HTTP 调用 |
| `dispatch_sse_layer_result` SSE 推送 | `tools/sse_tools.py` | 直接 import |

### 10.2 新增模块

```
src/dam_workflow/
├── __init__.py
├── state.py                  # DamState 状态定义
├── input_parser.py           # 输入解析（事件类型提取）
├── dag_generator.py          # DAG 生成器（事件模板匹配 + LLM 兜底）
├── model_selector.py         # 模型选择器（事件→模型映射，零 LLM）
├── io_configurator.py        # IO 配对器（模板 + 规则 + LLM 兜底）
├── dam_subgraph.py           # LangGraph 子图组装
├── tools/
│   ├── event_templates.py    # 事件→工作流模板映射
│   ├── keyword_extractor.py  # 关键词提取（纯规则）
│   └── rule_io_matcher.py    # 规则 IO 匹配工具
└── api/
    └── dam_api.py            # API 路由
```

### 10.3 目录结构关系

```
src/
├── new_agent_graph/          # 主系统 v2（完整版）
│   └── nodes/
│       └── layer2_workflow_generation/  # 主系统 Layer 2
├── dam_workflow/             # DAM 轻量版（新增）
│   ├── state.py
│   ├── input_parser.py
│   ├── dag_generator.py
│   ├── model_selector.py
│   ├── io_configurator.py
│   └── dam_subgraph.py
└── core/                     # 共享核心模块
    ├── config.py
    └── database.py
```

---

## 11. 完整示例：滑坡事件工作流生成

### 11.1 输入

```python
{
    "prompt": "你是一名库坝应急巡查智能感知系统中的工作流规划智能体。\n\n你的职责是根据**已确定的事件类型**和现场图片，自动规划最合理的视觉分析流程，并生成专业的事件分析报告。\n\n注意：事件类型已经由系统确定，你不需要重新判断事件是否发生，也不要对事件类型进行分类。\n\n输入\n\n1. 当前触发事件：滑坡事件。\n2. 现场图片（1张或多张）。\n3. 传感器信息、设备信息等辅助数据（可选）\n\n工作原则\n\n根据当前事件，首先分析完成本次事件分析所需要的视觉任务，例如目标检测、区域分割、变化检测、裂缝识别、场景理解等，而不是重新识别事件类型。\n\n随后，根据视觉任务自动规划最优的模型调用流程，并遵循以下原则：\n\n1. **专有模型优先**。优先调用针对具体任务微调后的专有模型完成视觉识别。\n2. **小模型优先**。能够由轻量模型完成的任务，不调用多模态大模型。\n3. **大模型负责理解与推理**。仅在需要综合分析时，调用多模态大模型结合专有模型输出进行场景理解、风险推理、结果解释、影响分析及处置建议生成，而不是重复执行目标检测或目标识别。\n4. **避免重复分析**。已经由专有模型完成识别的目标，大模型不得再次识别，应直接利用识别结果完成高层语义分析。\n5. **工作流应尽量简洁高效**。仅调用完成当前事件分析所必需的模型，减少不必要的模型调用，提高边缘计算效率。\n\n输出要求\n\n内部需要自动完成工作流规划，但**不要输出模型调用过程、模型名称、工作流步骤或推理过程**。\n\n最终仅输出一份完整的事件分析报告。",
    "images": ["landslide_001.jpg"],
    "sensor_data": {"位移量": 15.2, "降雨量": 85.0}
}
```

### 11.2 阶段 1：DAG 生成

事件类型"滑坡"命中预定义模板，直接实例化：

```python
# 输出 DraftDAG（内部使用，不对外暴露）
{
    "workflow_complexity": "COMPLEX",
    "visual_tasks": ["滑坡区域检测", "滑坡边界分割", "风险推理与处置建议"],
    "nodes": [
        {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
        {"node_id": "action_detect", "node_class": "ACTION", "node_type": "滑坡区域检测",
         "expected_implementation_type": "MODEL", "model_category": "specialized"},
        {"node_id": "action_segment", "node_class": "ACTION", "node_type": "滑坡边界分割",
         "expected_implementation_type": "MODEL", "model_category": "specialized"},
        {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "风险推理与处置建议",
         "expected_implementation_type": "MODEL", "model_category": "llm"},
        {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
         "expected_implementation_type": "MODEL"},
        {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
    ],
    "edges": [
        {"source": "start_0", "target": "action_detect"},
        {"source": "action_detect", "target": "action_segment"},
        {"source": "action_segment", "target": "action_reasoning"},
        {"source": "action_reasoning", "target": "evaluation_0"},
        {"source": "evaluation_0", "target": "end_0"},
    ],
}
```

### 11.3 阶段 2：模型挂载

```python
# action_detect: 查询 model_event_mapping，找到滑坡检测专用模型（专有微调模型）
# action_segment: 查询 model_event_mapping，找到滑坡分割专用模型（专有微调模型）
# action_reasoning: 查询 model_event_mapping，找到 0.8B 轻量大模型（智能推理）
# evaluation_0: 注入固定 prompt 模板（滑坡事件专用），使用 0.8B 轻量大模型生成报告
```

### 11.4 阶段 3：IO 配对

```python
# start_0 → action_detect: image → image（模板匹配）
# action_detect → action_segment: image + detections → image + detections（模板匹配）
# action_segment → action_reasoning: segmentation_mask + image → 推理结果（模板匹配）
# action_reasoning → evaluation_0: 推理结果 + sensor_data → 评价报告（固定 IO）
# evaluation_0 → end_0: 评价报告 → 输出（固定 IO）
```

### 11.5 最终输出（对外）

```json
{
    "report": "## 滑坡事件应急巡查分析报告\n\n### 一、事件概述\n本次滑坡事件发生于XX大坝XX位置，根据现场图片分析...\n\n### 二、检测结果分析\n1. 滑坡区域位置：...\n2. 滑坡边界：...\n3. 严重程度：...\n\n### 三、风险评估\n- 风险等级：高\n- 影响范围：...\n- 发展趋势：...\n\n### 四、应急处置建议\n1. 立即措施：...\n2. 后续监测：...\n3. 人员疏散：...\n\n### 五、结论与建议\n...",
    "risk_level": "高",
    "compliance_status": "危险",
    "recommendations": ["立即疏散周边人员", "设置位移监测点", "加强巡查频率"]
}
```

**注意**：响应中不包含工作流规划详情（DAG 结构、模型名称、调用流程等）。

### 11.6 LLM 调用汇总

| 阶段 | 调用次数 | 使用模型 | 说明 |
|---|---|---|---|
| DAG 生成 | 0 次 | - | 命中预定义模板，无需 LLM |
| 智能推理 | 1 次 | 0.8B 模型 | 风险推理与处置建议 |
| 评价报告 | 1 次 | 0.8B 模型 | 生成事件分析报告 |
| **总计** | **2 次** | | |

---

## 12. 扩展性设计

### 12.1 新事件类型扩展

1. 在 `EVENT_WORKFLOW_TEMPLATES` 中添加新事件类型的模板
2. 在 `model_event_mapping` 表中添加新事件类型的模型映射
3. 在 `model_evaluation_template` 表中添加新事件类型的 prompt 模板
4. 在 `model_io_template` 表中添加新事件类型的 IO 配对模板

### 12.2 传感器数据集成

当传感器数据可用时：
- START 节点输出 `sensor_data` 字段
- 智能推理节点（大模型）可读取传感器数据辅助风险评估
- EVALUATION 节点可将传感器数据纳入报告分析

**注意**：`sensor_data` 为自由字典结构，系统不约束具体字段。用户可根据实际传感器类型和设备信息自行定义字段名称和值，系统会将整个字典传递给下游节点使用。

### 12.3 多图输入支持

当输入包含多张图片时：
- 可为每张图片并行执行专业识别节点
- 智能推理节点汇总所有图片的检测结果
- EVALUATION 节点生成综合分析报告
