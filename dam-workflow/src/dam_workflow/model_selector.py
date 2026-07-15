# -*- coding: utf-8 -*-
"""模型选择器（阶段 2）"""
import logging
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

from src.dam_workflow.state import DamState
from src.core.config import settings
from src.core.models import (
    ModelEventMapping, ModelRegistry, ModelDeployBinding, ModelIOSchema,
    ModelEvaluationTemplate,
)

logger = logging.getLogger(__name__)


def query_event_model_mapping(db: Session, event_type: str, task_type: str, model_category: str) -> List[Dict]:
    """从事件→模型映射表查询候选模型

    Args:
        db: SQLAlchemy Session
        event_type: 事件类型
        task_type: 任务类型
        model_category: 模型类别 (specialized/llm)

    Returns:
        候选模型列表
    """
    rows = (
        db.query(ModelEventMapping)
        .filter(
            ModelEventMapping.event_type == event_type,
            ModelEventMapping.task_type == task_type,
            ModelEventMapping.model_category == model_category,
        )
        .order_by(ModelEventMapping.priority.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "task_type": r.task_type,
            "model_category": r.model_category,
            "model_id": r.model_id,
            "priority": r.priority,
        }
        for r in rows
    ]


def get_model_with_inference_url(model_id: int, db: Session) -> Optional[Dict]:
    """获取模型信息（含推理地址）

    Args:
        model_id: 模型 ID
        db: SQLAlchemy Session

    Returns:
        模型信息字典
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        return None

    binding = (
        db.query(ModelDeployBinding)
        .filter(
            ModelDeployBinding.model_id == model_id,
            ModelDeployBinding.deploy_status == "running",
        )
        .first()
    )
    schema = (
        db.query(ModelIOSchema)
        .filter(ModelIOSchema.model_id == model_id)
        .first()
    )

    inference_url = None
    if binding and binding.host_ip and binding.host_port and binding.inference_path:
        inference_url = f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path}"

    io_schema = None
    if schema:
        io_schema = {
            "inputs": schema.inputs,
            "outputs": schema.outputs,
        }

    return {
        "model_id": model.id,
        "model_name": model.name,
        "model_type": model.model_type,
        "framework": model.framework,
        "inference_url": inference_url,
        "io_schema": io_schema,
    }


def fuzzy_match_model(node_type: str, model_category: str, db: Session) -> Optional[Dict]:
    """从 model_registry 按类型模糊匹配模型

    Args:
        node_type: 节点类型描述（如 "滑坡区域检测"）
        model_category: 模型类别
        db: SQLAlchemy Session

    Returns:
        模型信息字典，未找到返回 None
    """
    # 提取关键词
    keywords = []
    for kw in ["检测", "分割", "变化", "推理", "识别", "测量", "分析", "评估"]:
        if kw in node_type:
            keywords.append(kw)

    # 无关键词时不进行模糊匹配，避免返回任意模型
    if not keywords:
        logger.warning("fuzzy_match_model: node_type='%s' 未提取到关键词，跳过模糊匹配", node_type)
        return None

    query = db.query(ModelRegistry).filter(ModelRegistry.runtime_status == "running")

    if model_category == "specialized":
        query = query.filter(ModelRegistry.model_type.isnot(None))
    elif model_category == "llm":
        query = query.filter(
            ModelRegistry.model_type.ilike("%llm%") | ModelRegistry.model_type.ilike("%language%")
        )

    for kw in keywords:
        query = query.filter(
            ModelRegistry.name.ilike(f"%{kw}%") | ModelRegistry.description.ilike(f"%{kw}%")
        )

    model = query.first()
    if not model:
        return None

    return get_model_with_inference_url(model.id, db)


def fetch_evaluation_template(db: Session, event_type: str = None) -> Optional[Dict]:
    """从数据库读取评价 prompt 模板

    Args:
        db: SQLAlchemy Session
        event_type: 事件类型（None 表示通用模板）

    Returns:
        模板字典，未找到返回 None
    """
    query = db.query(ModelEvaluationTemplate).filter(ModelEvaluationTemplate.is_active == 1)

    if event_type:
        template = query.filter(ModelEvaluationTemplate.event_type == event_type).first()
        if template:
            return {
                "id": template.id,
                "template_name": template.template_name,
                "event_type": template.event_type,
                "prompt_template": template.prompt_template,
                "input_schema": template.input_schema,
                "output_schema": template.output_schema,
            }

    template = query.filter(ModelEvaluationTemplate.event_type.is_(None)).first()
    if template:
        return {
            "id": template.id,
            "template_name": template.template_name,
            "event_type": template.event_type,
            "prompt_template": template.prompt_template,
            "input_schema": template.input_schema,
            "output_schema": template.output_schema,
        }

    return None


def select_model_for_action(node: Dict, event_type: str, db: Session = None) -> Optional[Dict]:
    """为 ACTION 节点选择模型

    Args:
        node: 节点信息
        event_type: 事件类型
        db: SQLAlchemy Session

    Returns:
        模型信息字典，包含 model_id, model_name, inference_url 等
    """
    node_type = node.get("node_type", "")
    model_category = node.get("model_category", "specialized")

    if db:
        # 1. 从映射表查询候选模型
        candidates = query_event_model_mapping(db, event_type, node_type, model_category)

        if candidates:
            # 2. 按优先级选择
            best = max(candidates, key=lambda x: x.get("priority", 0))
            if best.get("model_id"):
                # 3. 从 model_registry + model_deploy_binding 获取完整信息
                model_info = get_model_with_inference_url(best["model_id"], db)
                if model_info:
                    return model_info

        # 4. 映射表无命中，模糊匹配
        model_info = fuzzy_match_model(node_type, model_category, db)
        if model_info:
            return model_info

    # 5. 无数据库连接或未找到，返回占位信息
    return {
        "model_id": None,
        "model_name": f"{node_type}模型（待配置）",
        "model_type": node_type,
        "framework": None,
        "inference_url": None,
        "io_schema": None,
    }


def configure_evaluation_node(node: Dict, event_type: str, user_prompt: str, db: Session = None) -> Dict:
    """为 EVALUATION 节点注入固定配置

    Args:
        node: 节点信息
        event_type: 事件类型
        user_prompt: 用户 prompt
        db: SQLAlchemy Session

    Returns:
        配置后的节点
    """
    # 1. 从数据库读取 prompt 模板
    template = None
    if db:
        template = fetch_evaluation_template(db, event_type=event_type)

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

    # 3. 注入 prompt 模板
    if template:
        node["evaluation_template"] = template.get("prompt_template")
    else:
        node["evaluation_template"] = (
            "你是库坝应急巡查专家。请根据以下事件的检测结果和分析数据，生成专业的应急巡查分析报告。\n\n"
            "【事件信息】\n事件类型: {{event_type}}\n{{user_prompt}}\n\n"
            "【上游检测结果】\n{{detection_results}}\n\n"
            "【传感器数据】\n{{sensor_data}}\n\n"
            "【报告要求】\n"
            "1. 事件概述：简述事件的基本情况\n"
            "2. 检测结果分析：基于上游专有模型的检测结果进行分析\n"
            "3. 风险评估：评估当前风险等级和发展趋势\n"
            "4. 应急处置建议：提出具体的处置措施和监测方案\n"
            "5. 结论与建议\n\n"
            "【重要约束】\n"
            "- 直接利用上游检测结果，不要重复识别目标\n"
            "- 仅输出分析报告，不要输出模型调用过程、模型名称或工作流步骤\n"
            "- 报告应专业、完整、可直接用于决策\n\n"
            "输出格式：\n"
            "- evaluation_report: 详细分析报告（自然语言）\n"
            "- risk_level: 风险等级（低/中/高/极高）\n"
            "- compliance_status: 安全状态（安全/警告/危险）\n"
            "- recommendations: 处置建议列表"
        )

    # 4. 标记使用模型库推理接口
    if not settings.llm_0_8b_model_id:
        logger.warning("llm_0_8b_model_id 未配置，EVALUATION 节点将无法调用大模型生成报告")

    node["implementation"] = {"type": "MODEL_API", "model_id": settings.llm_0_8b_model_id}
    node["model_name"] = "大模型（通过模型库推理接口）"
    node["inference_method"] = "model_registry_api"

    return node


def populate_models(dam_state: DamState, db: Session = None) -> Dict:
    """阶段 2：为 DAG 中的节点挂载模型

    Args:
        dam_state: DAM 状态
        db: SQLAlchemy Session

    Returns:
        PopulatedDAG 字典
    """
    draft_dag = dam_state.get("draft_dag")
    event_type = dam_state.get("event_type")
    user_prompt = dam_state.get("user_prompt", "")

    if not draft_dag:
        raise ValueError("draft_dag 为空，无法进行模型挂载")

    nodes = draft_dag.get("nodes", [])

    for node in nodes:
        node_class = node.get("node_class")

        if node_class == "ACTION":
            model_info = select_model_for_action(node, event_type, db)
            if model_info:
                node["model_id"] = model_info.get("model_id")
                node["model_name"] = model_info.get("model_name")
                node["inference_url"] = model_info.get("inference_url")
                node["io_schema"] = model_info.get("io_schema")

        elif node_class == "EVALUATION":
            configure_evaluation_node(node, event_type, user_prompt, db)

    return draft_dag
