# -*- coding: utf-8 -*-
"""模型选择器（阶段 2）

支持三种模型类别：
- specialized：专用小模型（分类、检测等，可选）
- local_llm：本地大模型（qwen4B，场景推理，一定存在）
- cloud_llm：云端大模型（qwen35B，最终报告，一定存在）
"""
import logging
from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session

from src.dam_workflow.state import DamState
from src.core.config import settings
from src.core.models import (
    ModelEventMapping, ModelRegistry, ModelDeployBinding, ModelIOSchema,
    ModelEvaluationTemplate, ActorLibrary,
)

logger = logging.getLogger(__name__)


DEFAULT_ACTOR_NAME = "自然灾害分析专家"
ACTOR_RULES = (
    ("自然灾害分析专家", ("自然灾害", "泥石流", "滑坡", "洪水", "地震", "landslide", "debris", "flood", "earthquake", "natural_disaster")),
    ("人员行为分析专家", ("人员", "入侵", "滩涂", "游玩", "电鱼", "捕鱼", "船只", "行为", "intrusion", "person", "people", "fishing", "behavior")),
    ("极端天气分析专家", ("极端天气", "台风", "暴雨", "高温", "低温", "风速", "雨量", "气象", "typhoon", "rainstorm", "weather", "temperature")),
)


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def infer_actor_name(
    event_type: str,
    sensor_data: Optional[Dict[str, Any]] = None,
    explicit_actor_name: Optional[str] = None,
) -> str:
    """根据显式配置或事件上下文推断角色名。"""
    sensor_data = sensor_data or {}
    explicit = _first_text(
        explicit_actor_name,
        sensor_data.get("actor_name"),
        sensor_data.get("actor"),
        sensor_data.get("actor_role"),
        sensor_data.get("role_prompt_name"),
    )
    if explicit:
        return explicit

    text = " ".join(
        str(value or "")
        for value in (
            event_type,
            sensor_data.get("event_type"),
            sensor_data.get("event_name"),
            sensor_data.get("event_category"),
            sensor_data.get("summary"),
            sensor_data.get("description"),
        )
    )
    for actor_name, keywords in ACTOR_RULES:
        if any(keyword in text for keyword in keywords):
            return actor_name
    return DEFAULT_ACTOR_NAME


def fetch_actor_prompt(
    db: Session,
    actor_name: str,
    model_category: str,
) -> Optional[Dict[str, str]]:
    """从 actor_library 读取本地或云端模型 system prompt。"""
    if not db:
        return None

    actor = db.query(ActorLibrary).filter(ActorLibrary.actor_name == actor_name).first()
    if not actor and actor_name != DEFAULT_ACTOR_NAME:
        actor = db.query(ActorLibrary).filter(ActorLibrary.actor_name == DEFAULT_ACTOR_NAME).first()
    if not actor:
        return None

    if model_category == "local_llm":
        prompt = actor.local_system_prompt
        source = "actor_library.local_system_prompt"
    elif model_category == "cloud_llm":
        prompt = actor.cloud_system_prompt
        source = "actor_library.cloud_system_prompt"
    else:
        return None

    if not prompt:
        return None
    return {
        "actor_name": actor.actor_name,
        "system_prompt": prompt,
        "system_prompt_source": source,
    }


def query_event_model_mapping(db: Session, event_type: str, task_type: str, model_category: str) -> List[Dict]:
    """从事件→模型映射表查询候选模型

    Args:
        db: SQLAlchemy Session
        event_type: 事件类型
        task_type: 任务类型
        model_category: 模型类别 (specialized/local_llm/cloud_llm)

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
        .filter(ModelDeployBinding.model_id == model_id)
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
    for kw in ["检测", "分割", "变化", "推理", "识别", "测量", "分析", "评估", "报告"]:
        if kw in node_type:
            keywords.append(kw)

    # 无关键词时不进行模糊匹配，避免返回任意模型
    if not keywords:
        logger.warning("fuzzy_match_model: node_type='%s' 未提取到关键词，跳过模糊匹配", node_type)
        return None

    query = db.query(ModelRegistry).filter(ModelRegistry.runtime_status == "running")

    if model_category == "specialized":
        # 专用模型：非 LLM 类型
        query = query.filter(ModelRegistry.model_type.isnot(None))
    elif model_category == "local_llm":
        # 本地大模型：LLM 类型
        query = query.filter(
            ModelRegistry.model_type.ilike("%llm%") | ModelRegistry.model_type.ilike("%language%")
        )
    elif model_category == "cloud_llm":
        # 云端大模型：LLM 类型（后续可通过标签区分）
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


def fetch_evaluation_template(db: Session, event_type: str = None, template_type: str = None) -> Optional[Dict]:
    """从数据库读取 prompt 模板

    Args:
        db: SQLAlchemy Session
        event_type: 事件类型（None 表示通用模板）
        template_type: 模板类型（reasoning/report，可选）

    Returns:
        模板字典，未找到返回 None
    """
    query = db.query(ModelEvaluationTemplate).filter(ModelEvaluationTemplate.is_active == 1)

    if template_type:
        query = query.filter(ModelEvaluationTemplate.template_type == template_type)

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


def get_model_id_by_category(model_category: str) -> Optional[int]:
    """根据模型类别获取默认模型 ID

    Args:
        model_category: 模型类别 (specialized/local_llm/cloud_llm)

    Returns:
        模型 ID，未配置返回 None
    """
    if model_category == "local_llm":
        return settings.llm_local_model_id
    elif model_category == "cloud_llm":
        return settings.llm_cloud_model_id
    elif model_category == "specialized":
        return None  # 专用模型需要从映射表查询
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

    # 对于 local_llm 和 cloud_llm，优先使用配置的默认模型 ID
    default_model_id = get_model_id_by_category(model_category)
    if default_model_id and db:
        model_info = get_model_with_inference_url(default_model_id, db)
        if model_info:
            return model_info

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


def configure_action_node(
    node: Dict,
    event_type: str,
    user_prompt: str,
    db: Session = None,
    sensor_data: Optional[Dict[str, Any]] = None,
    actor_name: Optional[str] = None,
) -> Dict:
    """为 ACTION 节点注入配置

    Args:
        node: 节点信息
        event_type: 事件类型
        user_prompt: 用户 prompt
        db: SQLAlchemy Session
        sensor_data: 事件上下文
        actor_name: 指定角色名

    Returns:
        配置后的节点
    """
    model_category = node.get("model_category", "specialized")

    # 为 local_llm 和 cloud_llm 节点注入 prompt 模板
    if model_category in ["local_llm", "cloud_llm"]:
        inferred_actor_name = infer_actor_name(event_type, sensor_data, actor_name)
        actor_prompt = fetch_actor_prompt(db, inferred_actor_name, model_category) if db else None
        if actor_prompt:
            node["actor_name"] = actor_prompt["actor_name"]
            node["system_prompt"] = actor_prompt["system_prompt"]
            node["system_prompt_source"] = actor_prompt["system_prompt_source"]
        else:
            node["actor_name"] = inferred_actor_name
            node["system_prompt_source"] = "default_model_service_prompt"

        template = None
        if db:
            template = fetch_evaluation_template(db, event_type=event_type)

        if template:
            node["prompt_template"] = template.get("prompt_template")
        else:
            # 默认提示词
            if model_category == "local_llm":
                node["prompt_template"] = (
                    "你是库坝应急巡查专家。请根据以下信息进行场景分析，生成初步分析报告。\n\n"
                    "【事件信息】\n事件类型: {{event_type}}\n{{user_prompt}}\n\n"
                    "【检测结果】\n{{detection_results}}\n\n"
                    "【传感器数据】\n{{sensor_data}}\n\n"
                    "请分析当前情况并生成初步报告。"
                )
            else:  # cloud_llm
                node["prompt_template"] = (
                    "你是库坝应急巡查高级分析专家。请根据以下信息进行综合分析，生成最终报告。\n\n"
                    "【事件信息】\n事件类型: {{event_type}}\n{{user_prompt}}\n\n"
                    "【初步分析报告】\n{{preliminary_report}}\n\n"
                    "【传感器数据】\n{{sensor_data}}\n\n"
                    "请生成最终的综合分析报告，包含风险评估和处置建议。"
                )

        # 注入 IO schema
        node["physical_io_schema"] = {
            "inputs": {
                "detection_results": {"type": "object", "required": False, "description": "检测结果"},
                "sensor_data": {"type": "object", "required": False, "description": "传感器数据"},
                "user_prompt": {"type": "string", "required": True, "description": "用户原始需求"},
                "event_type": {"type": "string", "required": True, "description": "事件类型"},
                "images": {"type": "array", "required": False, "description": "图片路径列表"},
                "videos": {"type": "array", "required": False, "description": "视频路径列表"},
                "media_objects": {"type": "array", "required": False, "description": "媒体对象引用"},
                "system_prompt": {"type": "string", "required": False, "description": "角色 system prompt"},
            },
            "outputs": {
                "report": {"type": "string", "description": "分析报告"},
                "preliminary_report": {"type": "string", "description": "初步分析报告"},
                "final_report": {"type": "object", "description": "结构化分析报告"},
                "risk_level": {"type": "string", "description": "风险等级"},
                "template_id": {"type": "string", "description": "OnlyOffice 模板 ID"},
                "template_data": {"type": "object", "description": "OnlyOffice/docxtpl 模板上下文"},
                "template_fields": {"type": "object", "description": "扁平模板字段"},
                "template_tables": {"type": "object", "description": "模板表格数据"},
                "docx_context": {"type": "object", "description": "DOCX 渲染上下文"},
                "media_objects": {"type": "array", "description": "传递给下游模型的媒体对象引用"},
                "cloud_media_objects": {"type": "array", "description": "已上传到云端 MinIO 的媒体对象引用"},
            },
        }

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
    sensor_data = dam_state.get("sensor_data") or {}
    actor_name = dam_state.get("actor_name")

    if not draft_dag:
        raise ValueError("draft_dag 为空，无法进行模型挂载")

    nodes = draft_dag.get("nodes", [])

    for node in nodes:
        node_class = node.get("node_class")

        if node_class == "ACTION":
            # 先注入配置
            configure_action_node(
                node,
                event_type,
                user_prompt,
                db,
                sensor_data=sensor_data,
                actor_name=actor_name,
            )

            # 再选择模型
            model_info = select_model_for_action(node, event_type, db)
            if model_info:
                node["model_id"] = model_info.get("model_id")
                node["model_name"] = model_info.get("model_name")
                node["inference_url"] = model_info.get("inference_url")
                node["io_schema"] = model_info.get("io_schema")

    return draft_dag
