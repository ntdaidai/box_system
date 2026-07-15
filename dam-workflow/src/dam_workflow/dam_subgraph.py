# -*- coding: utf-8 -*-
"""DAM 子图组装"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from src.dam_workflow.state import DamState
from src.dam_workflow.input_parser import parse_dam_input
from src.dam_workflow.dag_generator import generate_dag
from src.dam_workflow.model_selector import populate_models
from src.dam_workflow.io_configurator import configure_io

logger = logging.getLogger(__name__)


def run_dam_workflow(
    user_prompt: str,
    images: list,
    sensor_data: dict = None,
    db: Session = None,
) -> Dict[str, Any]:
    """运行 DAM 工作流生成

    Args:
        user_prompt: 用户输入的完整 prompt
        images: 现场图片路径列表
        sensor_data: 传感器数据（可选）
        db: SQLAlchemy Session（可选）

    Returns:
        {
            "success": bool,
            "final_dag": Dict,  # 最终可执行 DAG
            "event_type": str,  # 事件类型
            "visual_tasks": List[str],  # 视觉任务列表
            "error": str,  # 错误信息（如有）
        }
    """
    try:
        # 阶段 0：输入解析
        dam_input = parse_dam_input(user_prompt, images, sensor_data)

        # 构建初始状态
        state: DamState = {
            "event_type": dam_input["event_type"],
            "images": dam_input["images"],
            "sensor_data": dam_input.get("sensor_data"),
            "user_prompt": dam_input["user_prompt"],
            "retry_count": 0,
        }

        # 阶段 1：DAG 生成
        draft_dag = generate_dag(state, db)
        state["draft_dag"] = draft_dag

        # 阶段 2：模型挂载
        populated_dag = populate_models(state, db)
        state["populated_dag"] = populated_dag

        # 阶段 3：IO 配对
        final_dag = configure_io(state, db)
        state["final_dag"] = final_dag

        return {
            "success": True,
            "final_dag": final_dag,
            "event_type": dam_input["event_type"],
            "visual_tasks": draft_dag.get("visual_tasks", []),
        }

    except Exception as e:
        logger.exception("DAM 工作流生成失败: %s", e)
        return {
            "success": False,
            "error": str(e),
        }
