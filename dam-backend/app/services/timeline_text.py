"""记录流日志文案的公共中文标签与截断工具。

安全事件「记录流」（safety_event_timeline_log）各写入点在拼接 message 时，
统一从这里取中文标签，避免同一套映射散落在多个服务文件里口径不一致。
本模块为纯函数工具，不依赖数据库或其它服务。
"""

from __future__ import annotations

import datetime as dt
from typing import Optional


def risk_label(level) -> str:
    """风险等级 -> 中文标签（兼容英文枚举与数字）。"""
    return {
        "LOW": "低风险",
        "MEDIUM": "中风险",
        "HIGH": "高风险",
        1: "低风险",
        2: "中风险",
        3: "高风险",
        "1": "低风险",
        "2": "中风险",
        "3": "高风险",
    }.get(str(level).upper() if isinstance(level, str) else level, str(level or "未确认"))


def status_label(status) -> str:
    """事件/步骤状态 -> 中文标签。"""
    return {
        "PENDING": "待处理",
        "PROCESSING": "处理中",
        "COMPLETED": "已完成",
        "SUCCESS": "成功",
        "FAILED": "失败",
        "FAIL": "失败",
        "ERROR": "失败",
        "FALSE_ALARM": "误报",
        "RESOLVED": "已闭环",
        "NOT_SUBMITTED": "未提交",
    }.get(str(status or "").upper(), str(status or "未知"))


def trigger_label(trigger_type) -> str:
    """触发方式 -> 中文标签。"""
    return {"AUTO": "自动", "MANUAL": "人工"}.get(str(trigger_type or "").upper(), str(trigger_type or "系统"))


def source_type_label(source_type) -> str:
    """来源类型 -> 中文标签。"""
    return {"camera": "摄像头", "sensor": "传感器"}.get(str(source_type or "").lower(), str(source_type or "系统"))


def category_label(category) -> str:
    """事件分类 -> 中文标签。"""
    return {
        "PERSON_SAFETY": "人员安全",
        "ILLEGAL_FISHING": "非法捕鱼",
        "CAMERA": "摄像头",
        "SENSOR": "传感器",
        "environment": "环境事件",
        "structure": "结构事件",
        "equipment": "设备事件",
    }.get(str(category or ""), str(category or "未分类"))


def action_label(action_type) -> str:
    """动作类型 -> 中文动作名（兼容 ECA 步骤与 SQL 状态机两种命名）。"""
    return {
        # ECA 步骤 / 动作配置
        "alert": "告警通知",
        "http": "HTTP 调用",
        "script": "脚本执行",
        "llm": "大模型分析",
        "broadcast": "自动广播",
        "drone_dispatch": "无人机派飞取证驱离",
        "machine_dog_dispatch": "机器狗巡检",
        "staff_task": "生成人工处置任务",
        "camera_snapshot": "摄像头抓拍",
        # 广播服务
        "AUTO_BROADCAST": "系统自动广播",
        "MANUAL_BROADCAST": "人工广播",
        "MANUAL_ONE_TOUCH_BROADCAST": "一键喊话",
        "broadcast_requested": "请求广播驱离",
        # SQL 状态机
        "DRONE_DISPATCH": "系统自动派出无人机",
        "drone_dispatch_requested": "请求无人机派飞",
        "STAFF_DISPATCH": "创建人工处置任务",
        "staff_task_requested": "请求工作人员现场处置",
        "push_requested": "请求消息推送",
    }.get(str(action_type or ""), str(action_type or "联动动作"))


def truncate(text, limit: int = 180) -> str:
    """截断文案，避免超过记录流 message 的 500 字符上限。"""
    if text is None:
        return ""
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def format_duration(seconds: Optional[float]) -> str:
    """把秒数格式化为「X分Y秒」/「X小时Y分」。"""
    if seconds is None:
        return ""
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分"
    if minutes:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def iso_or_na(value) -> str:
    """时间字段兜底显示。"""
    if value in (None, ""):
        return "未知"
    return str(value)


def duration_between(start: dt.datetime, end: dt.datetime) -> str:
    """计算两个时间点之间的历时文案（用于闭环类日志）。"""
    if not start or not end:
        return ""
    try:
        return format_duration((end - start).total_seconds())
    except Exception:
        return ""
