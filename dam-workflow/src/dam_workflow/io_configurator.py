# -*- coding: utf-8 -*-
"""IO 配对器（阶段 3）"""
import copy
import json
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from src.dam_workflow.state import DamState
from src.dam_workflow.tools.rule_io_matcher import (
    rule_based_io_match,
    START_OUTPUTS,
    LLM_ACTION_IO,
    build_end_data_flow,
)
from src.core.models import ModelIOTemplate
from src.dam_workflow.model_registry_client import model_registry_client
from src.core.config import settings


def query_io_template(db: Session, event_type: str, source_category: str, target_category: str) -> Optional[Dict]:
    """从 IO 模板表查询匹配的模板

    Args:
        db: SQLAlchemy Session
        event_type: 事件类型
        source_category: 上游模型类别
        target_category: 下游模型类别

    Returns:
        模板字典，未找到返回 None
    """
    # 优先精确匹配事件类型
    template = (
        db.query(ModelIOTemplate)
        .filter(
            ModelIOTemplate.event_type == event_type,
            ModelIOTemplate.source_model_category == source_category,
            ModelIOTemplate.target_model_category == target_category,
        )
        .first()
    )

    if not template:
        # 匹配通用模板
        template = (
            db.query(ModelIOTemplate)
            .filter(
                ModelIOTemplate.event_type.is_(None),
                ModelIOTemplate.source_model_category == source_category,
                ModelIOTemplate.target_model_category == target_category,
            )
            .first()
        )

    if template:
        return {
            "id": template.id,
            "template_name": template.template_name,
            "event_type": template.event_type,
            "field_mapping": template.field_mapping,
        }

    return None


def llm_io_match(source_io: Dict, target_io: Dict, context: str = "") -> Dict:
    """LLM 兜底 IO 匹配（通过模型库推理接口调用）

    Args:
        source_io: 上游节点的 IO schema
        target_io: 下游节点的 IO schema
        context: 上下文信息

    Returns:
        data_flow 字典
    """
    if not settings.llm_fallback_model_id:
        # 无可用 LLM，返回空映射
        return {"inputs": {}, "outputs": {}}

    prompt = (
        "为以下两个节点配对数据流。\n\n"
        f"【上游输出】\n{json.dumps(source_io.get('outputs', {}), ensure_ascii=False, indent=2)}\n\n"
        f"【下游输入】\n{json.dumps(target_io.get('inputs', {}), ensure_ascii=False, indent=2)}\n\n"
    )
    if context:
        prompt += f"【上下文】\n{context}\n\n"

    prompt += (
        '输出格式：{"inputs": {"field_name": "{{source_node.field}}"}, "outputs": {"field_name": "target_node.field"}}\n'
        "仅输出 JSON，不要输出其他内容。"
    )

    try:
        result = model_registry_client.infer(
            model_id=settings.llm_fallback_model_id,
            request_data={"prompt": prompt},
        )
    except Exception as e:
        logger.warning("LLM IO 匹配推理调用失败: %s", e)
        return {"inputs": {}, "outputs": {}}

    # 解析 vLLM 返回格式：{"data": {"choices": [{"message": {"content": "..."}}]}}
    try:
        choices = result.get("data", {}).get("choices", [])
        if not choices:
            logger.warning("LLM IO 匹配返回的 choices 为空")
            return {"inputs": {}, "outputs": {}}
        content = choices[0].get("message", {}).get("content", "")
    except (KeyError, IndexError) as e:
        logger.warning("LLM IO 匹配返回格式解析失败: %s", e)
        return {"inputs": {}, "outputs": {}}

    if not isinstance(content, str) or not content.strip():
        logger.warning("LLM IO 匹配返回内容为空")
        return {"inputs": {}, "outputs": {}}

    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]

    try:
        mapping = json.loads(content)
        if isinstance(mapping, dict) and "inputs" in mapping:
            return mapping
        logger.warning("LLM IO 匹配返回的 JSON 缺少 inputs 字段: %s", content[:200])
    except json.JSONDecodeError as e:
        logger.warning("LLM IO 匹配返回的 JSON 解析失败: %s", e)

    return {"inputs": {}, "outputs": {}}


def match_io_for_edge(source_node: Dict, target_node: Dict, event_type: str, db: Session = None) -> Dict:
    """为一条边匹配 IO

    Args:
        source_node: 上游节点
        target_node: 下游节点
        event_type: 事件类型
        db: SQLAlchemy Session

    Returns:
        data_flow 字典
    """
    source_class = source_node.get("node_class")
    target_class = target_node.get("node_class")
    source_category = source_node.get("model_category", "start" if source_class == "START" else "unknown")
    target_category = target_node.get("model_category", "unknown")
    source_id = source_node.get("node_id", "source_node")

    # Workflow-specific fixed mappings keep media and reports from being matched by
    # loose type compatibility rules such as boxes -> images.
    if source_class == "START" and target_category == "specialized":
        return {
            "inputs": {
                "images": f"{{{{{source_id}.images}}}}",
                "videos": f"{{{{{source_id}.videos}}}}",
                "media_objects": f"{{{{{source_id}.media_objects}}}}",
                "sensor_data": f"{{{{{source_id}.sensor_data}}}}",
                "event_type": f"{{{{{source_id}.event_type}}}}",
                "task_type": target_node.get("model_task") or target_node.get("node_type"),
            },
            "outputs": {},
        }

    if source_category == "specialized" and target_category == "local_llm":
        return {
            "inputs": {
                "detection_results": f"{{{{{source_id}.detection_results}}}}",
                "media_objects": f"{{{{{source_id}.media_objects}}}}",
            },
            "outputs": {},
        }

    if source_class == "START" and target_category == "local_llm":
        return {
            "inputs": {
                "images": f"{{{{{source_id}.images}}}}",
                "videos": f"{{{{{source_id}.videos}}}}",
                "media_objects": f"{{{{{source_id}.media_objects}}}}",
                "sensor_data": f"{{{{{source_id}.sensor_data}}}}",
                "event_type": f"{{{{{source_id}.event_type}}}}",
                "user_prompt": f"{{{{{source_id}.user_prompt}}}}",
            },
            "outputs": {},
        }

    if source_category == "local_llm" and target_category == "cloud_llm":
        return {
            "inputs": {
                "preliminary_report": f"{{{{{source_id}.report}}}}",
                "edge_analysis": f"{{{{{source_id}.final_report}}}}",
                "media_objects": f"{{{{{source_id}.media_objects}}}}",
                "cloud_media_objects": f"{{{{{source_id}.cloud_media_objects}}}}",
            },
            "outputs": {},
        }

    # Layer 1: 模板匹配
    if db:
        template = query_io_template(db, event_type, source_category, target_category)
        if template and template.get("field_mapping"):
            return template["field_mapping"]

    # Layer 2: 规则匹配
    source_io = {}
    target_io = {}

    # 构建 source_io
    if source_class == "START":
        source_io = {"outputs": START_OUTPUTS}
    elif source_node.get("physical_io_schema"):
        source_io = source_node["physical_io_schema"]
    elif source_node.get("io_schema"):
        source_io = source_node["io_schema"]

    # 构建 target_io
    if target_node.get("physical_io_schema"):
        target_io = target_node["physical_io_schema"]
    elif target_node.get("io_schema"):
        target_io = target_node["io_schema"]
    elif target_category in ["local_llm", "cloud_llm"]:
        target_io = LLM_ACTION_IO

    if source_io and target_io:
        mapping = rule_based_io_match(source_io, target_io)
        if mapping.get("inputs"):
            return mapping

    # Layer 3: LLM 兜底
    context = f"事件类型: {event_type}, 上游: {source_node.get('node_type', '')}, 下游: {target_node.get('node_type', '')}"
    return llm_io_match(source_io, target_io, context)


def bind_source_node_id(data_flow: Dict, source_id: str) -> Dict:
    """将规则模板中的 source_node 占位符替换为真实上游节点 ID。"""
    if not isinstance(data_flow, dict):
        return data_flow
    bound = copy.deepcopy(data_flow)
    for section in ("inputs", "outputs"):
        values = bound.get(section)
        if not isinstance(values, dict):
            continue
        for key, value in list(values.items()):
            if isinstance(value, str):
                values[key] = value.replace("{{source_node.", "{{" + source_id + ".")
    return bound


def configure_io(dam_state: DamState, db: Session = None) -> Dict:
    """阶段 3：IO 配对

    Args:
        dam_state: DAM 状态
        db: SQLAlchemy Session

    Returns:
        FinalDAG 字典
    """
    populated_dag = dam_state.get("populated_dag")
    event_type = dam_state.get("event_type")

    if not populated_dag:
        raise ValueError("populated_dag 为空，无法进行 IO 配对")

    # 深拷贝，避免 final_dag 和 populated_dag 指向同一对象
    dag = copy.deepcopy(populated_dag)
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])

    # 构建 node_id -> node 映射
    node_map = {n["node_id"]: n for n in nodes}

    # 为每条边匹配 IO
    for edge in edges:
        source_id = edge["source"]
        target_id = edge["target"]
        source_node = node_map.get(source_id, {})
        target_node = node_map.get(target_id, {})

        data_flow = match_io_for_edge(source_node, target_node, event_type, db)
        data_flow = bind_source_node_id(data_flow, source_id)
        edge["data_flow"] = data_flow

    # 为 END 节点构建 data_flow
    end_node = next((n for n in nodes if n.get("node_class") == "END"), None)
    if end_node:
        predecessors = [e["source"] for e in edges if e["target"] == end_node["node_id"]]
        physical_io = {}
        for n in nodes:
            if n.get("physical_io_schema"):
                physical_io[n["node_id"]] = n["physical_io_schema"]
        end_node["data_flow"] = build_end_data_flow(predecessors, physical_io)

    return dag
