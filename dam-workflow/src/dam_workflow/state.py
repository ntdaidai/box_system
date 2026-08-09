# -*- coding: utf-8 -*-
"""DAM 工作流状态定义"""
from typing import List, Dict, Optional, TypedDict, Any


class DamInput(TypedDict):
    """DAM 系统标准输入"""
    event_type: str                # 已确定的事件类型（如 "洪水"、"人员入侵"、"暴雨"）
    event_group: str               # 工作流族（natural_disaster/person_behavior/extreme_weather）
    images: List[str]              # 现场图片路径列表
    videos: List[str]              # 现场视频路径列表
    media_objects: List[Dict[str, Any]]  # 现场媒体对象引用
    sensor_data: Optional[dict]    # 传感器信息、设备信息等辅助数据（可选，内容由用户自行填写）
    actor_name: Optional[str]      # 指定角色名（可选，未指定时按事件推断）
    user_prompt: str               # 完整的系统 prompt（包含事件描述和任务要求）


class ErrorSignal(TypedDict):
    """错误信号"""
    has_error: bool
    error_type: str  # "dag_generation" / "model_selection" / "io_config" / "execution"
    error_message: str
    retryable: bool


class DamState(TypedDict, total=False):
    """DAM 轻量工作流状态"""
    # --- 输入 ---
    event_type: str                        # 已确定的事件类型
    event_group: str                       # 工作流族
    images: List[str]                      # 现场图片路径列表
    videos: List[str]                      # 现场视频路径列表
    media_objects: List[Dict[str, Any]]    # 媒体对象引用
    sensor_data: Optional[dict]            # 传感器信息、设备信息（可选，内容由用户自行填写）
    actor_name: Optional[str]              # 指定角色名
    user_prompt: str                       # 完整系统 prompt

    # --- 中间产物（内部使用，不对外暴露） ---
    draft_dag: Optional[Dict]              # dag_generator 输出
    populated_dag: Optional[Dict]          # model_selector 输出
    final_dag: Optional[Dict]              # io_configurator 输出

    # --- 输出 ---
    result_dag: Optional[List[Dict]]       # 最终可执行 DAG（内部使用）
    analysis_report: Optional[str]         # 最终事件分析报告（对外输出）

    # --- 错误 ---
    error_signal: Optional[ErrorSignal]    # 错误信号
    retry_count: int                       # 重试计数
