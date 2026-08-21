"""Automatic staff-task creation for HIGH safety events."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from loguru import logger

from app.core.database import SessionLocal
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import SafetyEventInstance
from app.services.safety_event_runtime_service import safety_event_runtime_service


STAFF_EVENT_TYPE_LABELS = {
    "PERSON_WADING": "人员涉水事件",
    "NIGHT_FISHING": "夜间捕鱼事件",
    "NATURAL_DISASTER_EVENT": "自然灾害事件",
    "EXTREME_WEATHER_EVENT": "极端天气事件",
}

STAFF_EVENT_TYPE_ALIASES = {
    "PERSON_WADING": "PERSON_WADING",
    "PERSON_HIGH": "PERSON_WADING",
    "人员涉水": "PERSON_WADING",
    "人员涉水事件": "PERSON_WADING",
    "人员亲水": "PERSON_WADING",
    "人员闯入": "PERSON_WADING",
    "NIGHT_FISHING": "NIGHT_FISHING",
    "BOAT_ILLEGAL_FISHING": "NIGHT_FISHING",
    "FISHING": "NIGHT_FISHING",
    "夜间捕鱼": "NIGHT_FISHING",
    "夜间捕鱼事件": "NIGHT_FISHING",
    "非法捕鱼": "NIGHT_FISHING",
    "禁渔事件": "NIGHT_FISHING",
    # 历史“洪水事件”统一归入自然灾害，不再作为配置侧独立事件类型展示。
    "NATURAL_DISASTER_EVENT": "NATURAL_DISASTER_EVENT",
    "NATURAL_DISASTER": "NATURAL_DISASTER_EVENT",
    "FLOOD_EVENT": "NATURAL_DISASTER_EVENT",
    "FLOOD": "NATURAL_DISASTER_EVENT",
    "FLOOD_WARNING": "NATURAL_DISASTER_EVENT",
    "FLOOD_HIGH": "NATURAL_DISASTER_EVENT",
    "洪水": "NATURAL_DISASTER_EVENT",
    "洪水事件": "NATURAL_DISASTER_EVENT",
    "洪涝": "NATURAL_DISASTER_EVENT",
    "洪涝事件": "NATURAL_DISASTER_EVENT",
    "自然灾害": "NATURAL_DISASTER_EVENT",
    "自然灾害事件": "NATURAL_DISASTER_EVENT",
    "EXTREME_WEATHER_EVENT": "EXTREME_WEATHER_EVENT",
    "EXTREME_WEATHER": "EXTREME_WEATHER_EVENT",
    "极端天气": "EXTREME_WEATHER_EVENT",
    "极端天气事件": "EXTREME_WEATHER_EVENT",
    "暴雨": "EXTREME_WEATHER_EVENT",
    "台风": "EXTREME_WEATHER_EVENT",
}


def normalize_staff_event_type(value: str) -> str:
    """把前端/小程序可能传入的事件类型统一成稳定的业务枚举。"""
    text = str(value or "").strip()
    canonical = STAFF_EVENT_TYPE_ALIASES.get(text.upper(), STAFF_EVENT_TYPE_ALIASES.get(text))
    if not canonical:
        raise ValueError("人工处置事件类型仅支持 PERSON_WADING、NIGHT_FISHING、NATURAL_DISASTER_EVENT 或 EXTREME_WEATHER_EVENT")
    return canonical


class StaffTaskService:
    def start_manual_task(
        self,
        db,
        event: SafetyEventInstance,
        *,
        operator: str,
        event_type: str,
    ) -> dict[str, Any]:
        """把待处理任务切换为处理中，并记录接单日志。"""
        canonical_type = normalize_staff_event_type(event_type)
        task = safety_event_runtime_service.latest_task(db, event.id)
        if not task or task.task_status not in {"WAITING_ACCEPT", "DISPATCHED"}:
            raise ValueError("当前人工处置任务不能开始处理")
        now = dt.datetime.now()
        task.assignee = task.assignee or operator
        task.task_status = "PROCESSING"
        task.accepted_at = now
        event.status = "PROCESSING"
        event.version = (event.version or 0) + 1
        log = safety_event_runtime_service.append_timeline(
            db,
            event,
            action_key=safety_event_runtime_service.new_action_key("staff-accept"),
            log_type="MANUAL",
            trigger_type="MANUAL",
            status="SUCCESS",
            title="人工处置开始",
            message=f"{operator} 已开始处理{STAFF_EVENT_TYPE_LABELS[canonical_type]}",
            operator=operator,
            payload={
                "instance_no": event.instance_no,
                "canonical_action_type": "STAFF_ACCEPTED",
                "event_type": canonical_type,
                "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
                "task_id": task.id,
            },
            create_time=now,
        )
        db.flush()
        return {"task": task, "timeline": log, "event_type": canonical_type}

    def complete_demo_task(
        self,
        db,
        event: SafetyEventInstance,
        *,
        operator: str,
        event_type: str,
        photo_urls: list[str],
    ) -> dict[str, Any]:
        """用固定照片和固定文本完成演示任务。"""
        canonical_type = normalize_staff_event_type(event_type)
        remarks = {
            "PERSON_WADING": "已完成现场核查，人员已成功驱离，并已上传驱离前后照片。",
            "NIGHT_FISHING": "已完成现场核查，夜间捕鱼行为已成功制止并驱离，并已上传驱离前后照片。",
            "NATURAL_DISASTER_EVENT": "已完成自然灾害现场核查和应急处置，并已上传处置前后照片。",
            "EXTREME_WEATHER_EVENT": "已完成极端天气现场核查和应急处置，并已上传处置前后照片。",
        }
        return self.complete_manual_task(
            db,
            event,
            operator=operator,
            event_type=canonical_type,
            result="DRIVEN_AWAY",
            result_label="已完成驱离",
            remark=remarks[canonical_type],
            photo_urls=photo_urls,
        )
    def dispatch_manual_task(
        self,
        db,
        event: SafetyEventInstance,
        *,
        operator: str,
        event_type: str,
        assignee: Optional[str] = None,
        group_name: Optional[str] = None,
        note: str = "",
    ) -> dict[str, Any]:
        """通过统一事件表模拟下发现场人工任务。"""
        if event.state == "RESOLVED" or event.status in {"COMPLETED", "FALSE_ALARM"}:
            raise ValueError("事件已结束，不能重复下发人工处置任务")

        canonical_type = normalize_staff_event_type(event_type)
        task = safety_event_runtime_service.latest_task(db, event.id)
        if task and task.task_status == "COMPLETED":
            raise ValueError("人工处置任务已完成，不能重复下发")
        if task and task.task_status in {"ACCEPTED", "PROCESSING"}:
            raise ValueError("人工处置任务正在处理中")

        now = dt.datetime.now()
        if task is None:
            task = SafetyEventTask(event_instance_id=event.id)
            db.add(task)
        task.assignee = assignee or task.assignee
        if group_name:
            task.assigned_group_id = group_name
            task.assigned_group_name = group_name
        task.dispatch_operator = operator
        task.task_status = "WAITING_ACCEPT"
        task.task_note = note or f"{STAFF_EVENT_TYPE_LABELS[canonical_type]}现场处置"
        task.dispatched_at = now
        event.state = "ACTIVE"
        # 任务下发后尚未有人接单，事件应留在小程序“待处理”页；
        # 接单接口再把它切换为 PROCESSING。
        event.status = "PENDING"
        event.version = (event.version or 0) + 1
        db.flush()
        task_id = task.id
        log = safety_event_runtime_service.append_timeline(
            db,
            event,
            action_key=safety_event_runtime_service.new_action_key("staff-dispatch"),
            log_type="MANUAL",
            trigger_type="MANUAL",
            status="SUCCESS",
            title="人工处置任务下发",
            message=f"{operator} 已下发{STAFF_EVENT_TYPE_LABELS[canonical_type]}人工处置任务",
            operator=operator,
            payload={
                "instance_no": event.instance_no,
                "canonical_action_type": "STAFF_DISPATCH",
                "event_type": canonical_type,
                "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
                "assignee": task.assignee,
                "task_id": task_id,
                "note": note,
            },
            create_time=now,
        )
        return {
            "task": task,
            "timeline": log,
            "event_type": canonical_type,
            "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
            "group_name": task.assigned_group_name,
        }

    def complete_manual_task(
        self,
        db,
        event: SafetyEventInstance,
        *,
        operator: str,
        event_type: str,
        result: str,
        result_label: str,
        remark: str = "",
        photo_urls: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """完成人工任务并把现场照片登记为任务证据。"""
        if event.state == "RESOLVED" or event.status in {"COMPLETED", "FALSE_ALARM"}:
            raise ValueError("事件已结束，不能重复提交")
        canonical_type = normalize_staff_event_type(event_type)
        task = safety_event_runtime_service.latest_task(db, event.id)
        if not task or task.task_status not in {"ACCEPTED", "PROCESSING"}:
            raise ValueError("事件尚未进入人工处理")

        now = dt.datetime.now()
        photo_urls = [str(url) for url in (photo_urls or []) if str(url).strip()]
        task.task_status = "COMPLETED"
        task.completed_at = now
        task.result_type = result
        task.result_remark = remark
        event.status = "COMPLETED"
        event.state = "RESOLVED"
        event.resolved_at = now
        event.resolve_reason = "staff_completed"
        event.version = (event.version or 0) + 1
        log = safety_event_runtime_service.append_timeline(
            db,
            event,
            action_key=safety_event_runtime_service.new_action_key("staff-result"),
            log_type="RESOLVE",
            trigger_type="MANUAL",
            status="SUCCESS",
            title="人工处置完成",
            message=f"{operator} 提交{STAFF_EVENT_TYPE_LABELS[canonical_type]}现场处置结果：{result_label}",
            operator=operator,
            payload={
                "instance_no": event.instance_no,
                "canonical_action_type": "STAFF_COMPLETED",
                "from_status": "PROCESSING",
                "to_status": "COMPLETED",
                "event_type": canonical_type,
                "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
                "result": result,
                "result_label": result_label,
                "remark": remark,
                "task_id": task.id,
                "photo_urls": photo_urls,
            },
            create_time=now,
        )
        for index, photo_url in enumerate(photo_urls, 1):
            safety_event_runtime_service.add_evidence(
                db,
                event,
                timeline_log_id=log.id,
                task_id=task.id,
                evidence_type="IMAGE",
                source_type="STAFF",
                source_id=operator,
                file_url=photo_url,
                description=f"人工现场处置照片（{'驱离前' if index == 1 else '驱离后'}）",
                metadata={
                    "event_type": canonical_type,
                    "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
                    "photo_index": index,
                    "phase": "before" if index == 1 else "after",
                },
                captured_at=now,
            )
        db.flush()
        return {
            "task": task,
            "timeline": log,
            "photo_urls": photo_urls,
            "event_type": canonical_type,
            "event_type_label": STAFF_EVENT_TYPE_LABELS[canonical_type],
        }

    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") != "STAFF_DISPATCH":
            return
        event_id = action.get("event_id")
        camera_id = action.get("camera_id")
        risk_level = action.get("risk_level")
        if not event_id:
            return
        now = dt.datetime.now()
        db = SessionLocal()
        try:
            unified_event = (
                db.query(SafetyEventInstance)
                .filter(SafetyEventInstance.instance_no == str(event_id))
                .with_for_update()
                .first()
            )
            if not unified_event:
                logger.warning(f"Staff task skipped because unified event is missing: event={event_id}")
                return
            unified_event.status = "PENDING"

            task = (
                db.query(SafetyEventTask)
                .filter(SafetyEventTask.event_instance_id == unified_event.id)
                .order_by(SafetyEventTask.id.desc())
                .first()
            )
            if task is None:
                task = SafetyEventTask(
                    event_instance_id=unified_event.id,
                    dispatch_operator="SYSTEM",
                    task_status="WAITING_ACCEPT",
                    task_note="高风险事件自动创建人工处置任务",
                    dispatched_at=now,
                )
                db.add(task)
                db.flush()
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "success",
                "人工处置任务已创建",
                {"task_id": task.id, "task_status": task.task_status},
            )
            db.commit()

            try:
                from app.services.safety_event_ws import safety_event_ws_manager

                safety_event_ws_manager.publish({
                    "type": "HIGH_RISK_ALERT",
                    "priority": "HIGH",
                    "data": {
                        "event_id": event_id,
                        "camera_id": camera_id,
                        "risk_level": risk_level,
                        "handling_mode": "MANUAL",
                        "disposal_status": "WAITING_MANUAL",
                    },
                })
            except Exception:
                pass
        except Exception as exc:
            db.rollback()
            logger.warning(f"Staff task creation failed: event={event_id}, error={exc}")
            self._mark_safety_action(db, action.get("action_id"), "failed", str(exc))
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _mark_safety_action(
        db,
        action_id: Optional[str],
        status: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not action_id:
            return
        safety_event_runtime_service.finish_engine_action(
            db,
            action_id,
            status=status,
            message=message,
            payload=payload,
        )


staff_task_service = StaffTaskService()
