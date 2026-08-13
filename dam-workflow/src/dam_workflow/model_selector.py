# -*- coding: utf-8 -*-
"""模型选择器（阶段 2）

支持三种模型类别：
- specialized：专用小模型（分类、检测等，可选）
- local_llm：本地大模型（qwen4B，场景推理，一定存在）
- cloud_llm：云端大模型（qwen35B，最终报告，一定存在）
"""
import logging
import json
from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session

from src.dam_workflow.state import DamState
from src.core.config import settings
from src.core.models import (
    ModelRegistry, ModelDeployBinding, ModelIOSchema,
    ModelEvaluationTemplate, ActorLibrary, ActorPromptStage,
)
from src.dam_workflow.model_registry_client import model_registry_client

logger = logging.getLogger(__name__)


DEFAULT_ACTOR_NAME = "自然灾害分析专家"
MODEL_CATEGORY_STAGE = {
    "local_llm": ("edge_analysis", "qwen4b"),
    "cloud_llm": ("cloud_review", "qwen35b"),
}
ACTOR_RULES = (
    ("自然灾害分析专家", ("自然灾害", "泥石流", "滑坡", "洪水", "地震", "landslide", "debris", "flood", "earthquake", "natural_disaster")),
    ("人员行为分析专家", ("人员", "入侵", "滩涂", "游玩", "电鱼", "捕鱼", "船只", "行为", "intrusion", "person", "people", "fishing", "behavior")),
    (
        "极端天气分析专家",
        (
            "极端天气", "台风", "飓风", "暴风", "狂风", "烈风", "大风",
            "暴雨", "高温", "低温", "极高温", "极低温", "冰冻",
            "高湿", "低湿", "风速", "风力", "雨量", "气象", "湿度",
            "typhoon", "hurricane", "gale", "rainstorm", "weather",
            "temperature", "humidity", "wind",
        ),
    ),
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
    """从 actor_prompt_stage 读取模型阶段 system prompt。"""
    if not db:
        return None

    actor = db.query(ActorLibrary).filter(ActorLibrary.actor_name == actor_name).first()
    if not actor and actor_name != DEFAULT_ACTOR_NAME:
        actor = db.query(ActorLibrary).filter(ActorLibrary.actor_name == DEFAULT_ACTOR_NAME).first()
    if not actor:
        return None

    stage_info = MODEL_CATEGORY_STAGE.get(model_category)
    if stage_info:
        stage_code, model_scope = stage_info
        return fetch_actor_stage_prompt(db, actor, stage_code, model_scope)
    return None


def fetch_actor_stage_prompt(
    db: Session,
    actor: ActorLibrary,
    stage_code: str,
    model_scope: str,
) -> Optional[Dict[str, str]]:
    """读取角色阶段 prompt，优先精确模型范围，其次 general。"""
    rows = (
        db.query(ActorPromptStage)
        .filter(
            ActorPromptStage.actor_id == actor.id,
            ActorPromptStage.stage_code == stage_code,
            ActorPromptStage.is_active == 1,
            ActorPromptStage.model_scope.in_([model_scope, "general"]),
        )
        .order_by(
            (ActorPromptStage.model_scope == model_scope).desc(),
            ActorPromptStage.update_time.desc(),
            ActorPromptStage.id.desc(),
        )
        .all()
    )
    if not rows:
        return None
    row = rows[0]
    if not row.system_prompt:
        return None
    return {
        "actor_name": actor.actor_name,
        "system_prompt": row.system_prompt,
        "system_prompt_source": f"actor_prompt_stage.{row.stage_code}.{row.model_scope}.{row.version}",
        "stage_code": row.stage_code,
        "prompt_version": row.version,
        "prompt_model_scope": row.model_scope,
    }


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


def _extract_llm_content(result: Dict[str, Any]) -> str:
    """Extract chat content from model-library/vLLM style responses."""
    if not isinstance(result, dict):
        return ""
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices and isinstance(data, dict) and isinstance(data.get("data"), dict):
        choices = data["data"].get("choices")
    if choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        return (first.get("message") or {}).get("content") or first.get("text") or ""
    content = data.get("response") if isinstance(data, dict) else ""
    return content if isinstance(content, str) else ""


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return None
    content = text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        content = content[start:end + 1]
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _model_candidate_rows(model_category: str, db: Session) -> List[Dict[str, Any]]:
    """Collect selectable model candidates, including stopped but deploy-bound models."""
    query = (
        db.query(ModelRegistry, ModelDeployBinding)
        .join(ModelDeployBinding, ModelDeployBinding.model_id == ModelRegistry.id)
    )
    if model_category == "specialized":
        query = query.filter(
            ModelRegistry.model_type.isnot(None),
            ~ModelRegistry.model_type.ilike("%llm%"),
            ~ModelRegistry.model_type.ilike("%vlm%"),
            ~ModelRegistry.model_type.ilike("%language%"),
        )
    elif model_category == "local_llm":
        query = query.filter(
            ModelRegistry.model_type.ilike("%llm%")
            | ModelRegistry.model_type.ilike("%vlm%")
            | ModelRegistry.model_type.ilike("%language%")
        )
    elif model_category == "cloud_llm":
        query = query.filter(
            ModelRegistry.model_type.ilike("%llm%")
            | ModelRegistry.model_type.ilike("%vlm%")
            | ModelRegistry.model_type.ilike("%language%")
        )

    rows: List[Dict[str, Any]] = []
    for model, binding in query.order_by(ModelRegistry.id.asc()).all():
        rows.append({
            "model_id": model.id,
            "name": model.name,
            "description": model.description,
            "tags": model.tags,
            "model_type": model.model_type,
            "framework": model.framework,
            "runtime_status": model.runtime_status,
            "bind_type": binding.bind_type,
            "inference_url": (
                f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path or ''}"
                if binding.host_ip and binding.host_port else None
            ),
        })
    return rows


def _fallback_score_candidate(candidate: Dict[str, Any], node: Dict[str, Any], event_type: str) -> int:
    tags = candidate.get("tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = [tags]
    tags_text = " ".join(str(item or "") for item in tags) if isinstance(tags, list) else ""
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("name", "description", "model_type", "framework")
    )
    text = f"{text} {tags_text}".lower()
    node_text = " ".join(str(node.get(key) or "") for key in ("node_type", "model_task", "model_family", "event_group")).lower()
    wants_classification = "classification" in node_text or "分类" in node_text
    wants_detection = "detection" in node_text or "检测" in node_text or "目标" in node_text
    wants_tracking = "tracking" in node_text or "跟踪" in node_text
    has_classification = "classification" in text or "分类" in text
    has_detection = "detection" in text or "detect" in text or "检测" in text
    has_tracking = "tracking" in text or "track" in text or "跟踪" in text
    if wants_classification and not has_classification:
        return 0
    if wants_detection and not has_detection:
        return 0
    if wants_tracking and not has_tracking:
        return 0
    score = 0
    for token in (node.get("model_task"), node.get("model_family"), node.get("event_group"), event_type):
        if token and str(token).lower() in text:
            score += 5
    event_text = str(event_type or "").lower()
    if any(token in event_text for token in ("人员", "入侵", "滩涂", "游玩", "电鱼", "捕鱼", "person", "intrusion", "fishing")):
        if "person_event" in text or "人员" in text:
            score += 10
        if "baseline" in text or "默认" in text:
            score -= 6
    if "specialized" in text or "专有" in text:
        score += 4
    if wants_classification and has_classification:
        score += 8
    if wants_detection and has_detection:
        score += 8
    if wants_tracking and has_tracking:
        score += 8
    if "yolo" in node_text and "yolo" in text:
        score += 6
    if candidate.get("runtime_status") == "running":
        score += 2
    if candidate.get("inference_url"):
        score += 1
    return score


def select_model_with_qwen_selector(node: Dict, event_type: str, model_category: str, db: Session) -> Optional[Dict]:
    """Use resident Qwen4B to select a model from model_registry candidates."""
    if not settings.llm_fallback_model_id:
        return None

    candidates = _model_candidate_rows(model_category, db)
    if not candidates:
        return None

    compact_candidates = [
        {
            "model_id": item["model_id"],
            "name": item["name"],
            "description": item["description"],
            "tags": item.get("tags"),
            "model_type": item["model_type"],
            "framework": item["framework"],
            "runtime_status": item["runtime_status"],
            "inference_url": item["inference_url"],
        }
        for item in candidates[:30]
    ]
    prompt = (
        "你是模型路由选择器。请根据工作流节点需求，从候选模型中选择最合适的一个。\n"
        "只允许选择候选列表中存在的 model_id；如果没有合适模型，返回 null。\n\n"
        "选择原则：\n"
        "1. natural_disaster + classification + yolov26 优先选择 YOLO 灾害分类模型；\n"
        "2. person_behavior + detection + yolov26 优先选择 YOLO 目标检测模型；\n"
        "3. 不要为 specialized 节点选择 LLM/VLM；\n"
        "4. stopped 但已绑定 inference_url 的模型可以选择，执行阶段可再决定是否启动；\n"
        "5. 输出必须是 JSON，不要输出额外文字。\n\n"
        f"【事件类型】{event_type}\n"
        f"【节点需求】{json.dumps({k: node.get(k) for k in ['node_id', 'node_type', 'model_category', 'model_task', 'model_family', 'event_group', 'target_event_type']}, ensure_ascii=False)}\n"
        f"【候选模型】{json.dumps(compact_candidates, ensure_ascii=False)}\n\n"
        "输出格式：{\"model_id\": 12, \"confidence\": 0.0, \"reason\": \"选择理由\"}"
    )
    try:
        result = model_registry_client.infer(
            model_id=settings.llm_fallback_model_id,
            request_data={
                "prompt": prompt,
                "max_tokens": 256,
                "temperature": 0,
            },
        )
        decision = _parse_json_object(_extract_llm_content(result)) or {}
    except Exception as exc:
        logger.warning("Qwen4B 模型选择失败，使用规则兜底: %s", exc)
        decision = {}

    candidate_ids = {item["model_id"] for item in candidates}
    selected_id = decision.get("model_id")
    try:
        selected_id = int(selected_id) if selected_id is not None else None
    except (TypeError, ValueError):
        selected_id = None

    if selected_id not in candidate_ids:
        scored = sorted(
            candidates,
            key=lambda item: _fallback_score_candidate(item, node, event_type),
            reverse=True,
        )
        if not scored or _fallback_score_candidate(scored[0], node, event_type) <= 0:
            return None
        selected_id = scored[0]["model_id"]
        decision = {
            "confidence": 0.0,
            "reason": "Qwen4B 未返回有效候选，使用规则评分兜底",
        }
    else:
        selected_candidate = next((item for item in candidates if item["model_id"] == selected_id), None)
        if not selected_candidate or _fallback_score_candidate(selected_candidate, node, event_type) <= 0:
            logger.warning(
                "Qwen4B选择的模型与任务不兼容: event=%s, node=%s, selected_id=%s",
                event_type,
                node.get("node_type"),
                selected_id,
            )
            return None

    model_info = get_model_with_inference_url(selected_id, db)
    if model_info:
        model_info["selection_source"] = "qwen4b_model_selector"
        model_info["selection_reason"] = decision.get("reason")
        model_info["selection_confidence"] = decision.get("confidence")
        logger.info(
            "Qwen4B模型选择: event=%s, node=%s, model_id=%s, reason=%s",
            event_type,
            node.get("node_type"),
            selected_id,
            decision.get("reason"),
        )
    return model_info


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
    for kw in ["检测", "分类", "目标", "跟踪", "分割", "变化", "推理", "识别", "测量", "分析", "评估", "报告"]:
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
        # specialized 节点使用常驻 Qwen4B 从模型库候选中选择
        if model_category == "specialized":
            model_info = select_model_with_qwen_selector(node, event_type, model_category, db)
            if model_info:
                return model_info

        # Qwen4B 未选出结果时，回退到运行中模型模糊匹配
        model_info = fuzzy_match_model(node_type, model_category, db)
        if model_info:
            return model_info

    # 6. 无数据库连接或未找到，返回占位信息
    placeholder_name = f"{node_type}（待配置）" if node_type.endswith("模型") else f"{node_type}模型（待配置）"
    return {
        "model_id": None,
        "model_name": placeholder_name,
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
            if actor_prompt.get("stage_code"):
                node["stage_code"] = actor_prompt["stage_code"]
            if actor_prompt.get("prompt_version"):
                node["prompt_version"] = actor_prompt["prompt_version"]
            if actor_prompt.get("prompt_model_scope"):
                node["prompt_model_scope"] = actor_prompt["prompt_model_scope"]
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
                "enable_knowledge_retrieval": {"type": "boolean", "required": False, "description": "是否启用知识库检索增强"},
                "knowledge_query": {"type": "string", "required": False, "description": "显式知识库检索问题"},
            },
            "outputs": {
                "report": {"type": "string", "description": "分析报告"},
                "preliminary_report": {"type": "string", "description": "初步分析报告"},
                "final_report": {"type": "object", "description": "结构化分析报告"},
                "risk_level": {"type": "string", "description": "风险等级"},
                "knowledge_context": {"type": "object", "description": "知识库检索上下文"},
                "knowledge_sources": {"type": "array", "description": "模型引用的知识库文档片段"},
                "template_id": {"type": "string", "description": "OnlyOffice 模板 ID"},
                "template_data": {"type": "object", "description": "OnlyOffice/docxtpl 模板上下文"},
                "template_fields": {"type": "object", "description": "扁平模板字段"},
                "template_tables": {"type": "object", "description": "模板表格数据"},
                "docx_context": {"type": "object", "description": "DOCX 渲染上下文"},
                "media_objects": {"type": "array", "description": "传递给下游模型的媒体对象引用"},
                "cloud_media_objects": {"type": "array", "description": "已上传到云端 MinIO 的媒体对象引用"},
            },
        }

    elif model_category == "specialized":
        task = node.get("model_task") or node.get("node_type")
        node["physical_io_schema"] = {
            "inputs": {
                "images": {"type": "array", "required": False, "description": "图片路径列表"},
                "videos": {"type": "array", "required": False, "description": "视频路径列表"},
                "media_objects": {"type": "array", "required": False, "description": "媒体对象引用"},
                "sensor_data": {"type": "object", "required": False, "description": "传感器数据"},
                "event_type": {"type": "string", "required": True, "description": "事件类型"},
                "task_type": {"type": "string", "required": True, "description": "专有模型任务类型"},
            },
            "outputs": {
                "detection_results": {"type": "object", "description": "专有模型检测/分类结果"},
                "confidence": {"type": "float", "description": "置信度"},
                "boxes": {"type": "array", "description": "目标框"},
                "tracks": {"type": "array", "description": "目标轨迹"},
                "media_objects": {"type": "array", "description": "媒体对象引用"},
            },
        }
        node["task_type"] = task

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
                for key in ("selection_source", "selection_reason", "selection_confidence"):
                    if key in model_info:
                        node[key] = model_info.get(key)

    return draft_dag
