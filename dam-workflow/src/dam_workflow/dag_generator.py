# -*- coding: utf-8 -*-
"""DAG 生成器（阶段 1）"""
from typing import Dict, Optional
from collections import deque
import json

from src.dam_workflow.state import DamState
from src.dam_workflow.tools.event_templates import get_template, get_supported_event_types
from src.dam_workflow.model_registry_client import model_registry_client
from src.core.config import settings


def ensure_evaluation_node(dag: Dict) -> Dict:
    """确保 DAG 中存在 EVALUATION 节点，位于 END 之前

    Args:
        dag: 包含 nodes 和 edges 的 DAG 字典

    Returns:
        处理后的 DAG
    """
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
    edges.append({"source": "evaluation_0", "target": end_id})

    # 插入 EVALUATION 节点（在 END 之前）
    end_idx = nodes.index(end_node)
    nodes.insert(end_idx, eval_node)

    return {"nodes": nodes, "edges": edges}


def validate_dag(dag: Dict) -> tuple[bool, str]:
    """轻量校验 DAG

    Args:
        dag: 包含 nodes 和 edges 的 DAG 字典

    Returns:
        (is_valid, error_message)
    """
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    # 1. START/END 存在性
    start_nodes = [n for n in nodes if n.get("node_class") == "START"]
    end_nodes = [n for n in nodes if n.get("node_class") == "END"]

    if len(start_nodes) != 1:
        return False, f"必须有且仅有一个 START 节点，当前有 {len(start_nodes)} 个"
    if len(end_nodes) != 1:
        return False, f"必须有且仅有一个 END 节点，当前有 {len(end_nodes)} 个"

    # 2. EVALUATION 约束
    eval_nodes = [n for n in nodes if n.get("node_class") == "EVALUATION"]
    if len(eval_nodes) != 1:
        return False, f"必须有且仅有一个 EVALUATION 节点，当前有 {len(eval_nodes)} 个"

    # 3. 连通性检查（从 START BFS）
    adj = {}
    for node in nodes:
        adj[node["node_id"]] = []
    for edge in edges:
        adj[edge["source"]].append(edge["target"])

    start_id = start_nodes[0]["node_id"]
    visited = set()
    queue = deque([start_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for neighbor in adj.get(current, []):
            queue.append(neighbor)

    node_ids = {n["node_id"] for n in nodes}
    if visited != node_ids:
        unreachable = node_ids - visited
        return False, f"存在不可达节点: {unreachable}"

    return True, ""


def generate_dag_via_llm(event_type: str, user_prompt: str) -> Dict:
    """使用 8B 模型通过 LLM 生成 DAG（兜底路径）

    Args:
        event_type: 事件类型
        user_prompt: 用户 prompt

    Returns:
        DraftDAG 字典

    Raises:
        RuntimeError: LLM 调用失败
    """
    if not settings.llm_8b_model_id:
        raise RuntimeError(
            f"事件类型 '{event_type}' 未找到预定义模板，且未配置 8B LLM 模型 ID（llm_8b_model_id）。"
            f"支持的事件类型: {get_supported_event_types()}"
        )

    prompt = (
        "你是库坝应急巡查工作流规划专家。请根据以下事件类型，规划视觉分析工作流。\n\n"
        f"【事件类型】\n{event_type}\n\n"
        f"【用户需求】\n{user_prompt}\n\n"
        "【设计原则】\n"
        "1. 专有模型优先：优先调用专有微调模型完成视觉识别\n"
        "2. 小模型优先：轻量模型能完成的任务不调用大模型\n"
        "3. 大模型负责理解与推理：仅在需要综合分析时调用大模型\n"
        "4. 避免重复分析：大模型不得重复执行专有模型已完成的识别任务\n"
        "5. 工作流简洁高效：仅调用必需的模型\n\n"
        "【节点类型】\n"
        "- START: 入口节点（有且仅一个）\n"
        "- ACTION: 执行节点（挂载专有模型或大模型）\n"
        "- EVALUATION: 评价节点（有且仅一个，位于 END 之前）\n"
        "- END: 出口节点（有且仅一个）\n\n"
        "【拓扑约束】\n"
        "- 线性流程：START → 专业识别节点 → 智能推理节点 → EVALUATION → END\n"
        "- 专业识别在前，智能推理在后\n"
        "- 无 CONDITION 节点\n\n"
        "【输出格式】\n"
        "请输出 JSON，格式如下：\n"
        '{\n'
        '  "workflow_complexity": "COMPLEX",\n'
        '  "visual_tasks": ["任务1", "任务2", ...],\n'
        '  "nodes": [\n'
        '    {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},\n'
        '    {"node_id": "action_xxx", "node_class": "ACTION", "node_type": "XXX检测", '
        '"expected_implementation_type": "MODEL", "model_category": "specialized"},\n'
        '    {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "XXX推理", '
        '"expected_implementation_type": "MODEL", "model_category": "llm"},\n'
        '    {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告", '
        '"expected_implementation_type": "MODEL"},\n'
        '    {"node_id": "end_0", "node_class": "END", "node_type": "输出"}\n'
        '  ],\n'
        '  "edges": [\n'
        '    {"source": "start_0", "target": "action_xxx"},\n'
        '    ...\n'
        '  ]\n'
        '}\n\n'
        "仅输出 JSON，不要输出其他内容。"
    )

    try:
        result = model_registry_client.infer(
            model_id=settings.llm_8b_model_id,
            request_data={"prompt": prompt},
        )
    except Exception as e:
        raise RuntimeError(f"LLM 推理接口调用失败: {e}") from e

    content = result.get("data", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM 返回内容为空")

    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]

    try:
        dag = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM 返回的 JSON 解析失败: {e}") from e

    if not isinstance(dag, dict) or "nodes" not in dag or "edges" not in dag:
        raise RuntimeError(f"LLM 返回的 JSON 缺少 nodes/edges 字段: {list(dag.keys()) if isinstance(dag, dict) else type(dag).__name__}")

    dag.setdefault("workflow_complexity", "COMPLEX")
    dag.setdefault("visual_tasks", [])
    return dag


def generate_dag(state: DamState, db=None) -> Dict:
    """阶段 1：生成 DAG

    Args:
        state: DAM 状态
        db: 未使用，保留接口兼容性

    Returns:
        DraftDAG 字典
    """
    event_type = state.get("event_type")
    user_prompt = state.get("user_prompt", "")

    # 1. 尝试从模板获取
    template = get_template(event_type)
    if template:
        dag = {
            "workflow_complexity": "COMPLEX" if len(template["nodes"]) > 4 else "TRIVIAL",
            "visual_tasks": template["visual_tasks"],
            "nodes": template["nodes"],
            "edges": template["edges"],
        }
    else:
        # 2. 模板未命中，使用 8B LLM 生成
        dag = generate_dag_via_llm(event_type, user_prompt)

    # 3. 确保 EVALUATION 节点存在
    dag = ensure_evaluation_node(dag)

    # 4. 轻量校验
    is_valid, error_msg = validate_dag(dag)
    if not is_valid:
        raise ValueError(f"DAG 校验失败: {error_msg}")

    return dag
