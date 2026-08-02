"""Mirror sensor ECA state into the unified safety-event lifecycle."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.action_flow import ActionFlow
from app.models.data_source import DataSource
from app.models.event_action import EventAction
from app.models.event_condition import EventCondition
from app.models.event_library import EventLibrary
from app.models.event_log import EventLog
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog


RISK_NAMES = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}


class UnifiedSensorEventService:
    """Maintain one active unified instance for each sensor ECA event."""

    def observe(
        self,
        db: Session,
        event: EventLibrary,
        sensor_data: Dict[str, Any],
        conditions_met: bool,
        event_log: Optional[EventLog] = None,
        source_id: Optional[int] = None,
    ) -> None:
        source = self._source(db, event.id, source_id)
        if not source or str(source.source_type).lower() != "sensor":
            return

        instance = (
            db.query(SafetyEventInstance)
            .filter(
                SafetyEventInstance.current_event_id == event.id,
                SafetyEventInstance.data_source_id == source.id,
                SafetyEventInstance.source_type == "sensor",
                SafetyEventInstance.state == "ACTIVE",
            )
            .order_by(SafetyEventInstance.id.desc())
            .first()
        )
        now = dt.datetime.now()
        observation = dict(sensor_data or {})

        if conditions_met:
            if instance is None:
                if event_log is None:
                    return
                risk = RISK_NAMES.get(int(event.risk_level or 1), "LOW")
                instance = SafetyEventInstance(
                    instance_no=f"EVT_{now:%Y%m%d}_{uuid.uuid4().hex[:12]}",
                    current_event_id=event.id,
                    event_category=event.event_category or "SENSOR",
                    data_source_id=source.id,
                    source_type="sensor",
                    source_id=source.device_id or source.id,
                    risk_level=risk,
                    max_risk_level=risk,
                    state="ACTIVE",
                    status="PROCESSING",
                    started_at=event_log.trigger_time or now,
                    last_observed_at=now,
                    summary=f"{source.source_name} - {event.event_name}",
                    latest_observation=observation,
                )
                db.add(instance)
                db.flush()
                flow_id = self._flow_id(db, event.id)
                db.add(SafetyEventTimelineLog(
                    event_instance_id=instance.id,
                    event_id=event.id,
                    flow_id=flow_id,
                    action_key=f"sensor-trigger:{event_log.id}",
                    log_type="TRIGGER",
                    trigger_type="AUTO",
                    risk_level=risk,
                    status="SUCCESS",
                    message=f"{event.event_name}已触发",
                    operator="SYSTEM",
                    payload={"event_log_id": event_log.id, "observation": observation},
                    create_time=event_log.trigger_time or now,
                ))
            else:
                instance.last_observed_at = now
                instance.latest_observation = observation
            db.commit()
            return

        if instance is None:
            return
        latest = dict(instance.latest_observation or {})
        recovery_started_at = latest.get("recovery_started_at")
        if not recovery_started_at:
            latest["recovery_started_at"] = now.isoformat()
            latest["recovery_observation"] = observation
            instance.latest_observation = latest
            db.commit()
            return

        try:
            recovery_started = dt.datetime.fromisoformat(str(recovery_started_at))
        except ValueError:
            recovery_started = now
        if (now - recovery_started).total_seconds() < max(int(event.recovery_duration or 0), 0):
            return

        instance.state = "RESOLVED"
        instance.status = "COMPLETED"
        instance.resolved_at = now
        instance.resolve_reason = "condition_recovered"
        instance.latest_observation = {"recovery_observation": observation}
        db.add(SafetyEventTimelineLog(
            event_instance_id=instance.id,
            event_id=event.id,
            flow_id=self._flow_id(db, event.id),
            action_key=f"sensor-resolve:{instance.instance_no}",
            log_type="RESOLVE",
            trigger_type="AUTO",
            risk_level=instance.risk_level,
            status="SUCCESS",
            message=f"{event.event_name}条件已恢复，事件自动闭环",
            operator="SYSTEM",
            payload={"reason": "condition_recovered", "observation": observation},
            create_time=now,
        ))
        db.commit()

    @staticmethod
    def _source(db: Session, event_id: int, source_id: Optional[int]) -> Optional[DataSource]:
        if source_id is not None:
            return db.query(DataSource).filter(DataSource.id == source_id).first()
        relation = (
            db.query(EventCondition)
            .filter(EventCondition.event_id == event_id)
            .order_by(EventCondition.sort_order.asc(), EventCondition.id.asc())
            .first()
        )
        return relation.condition.source if relation and relation.condition else None

    @staticmethod
    def _flow_id(db: Session, event_id: int) -> Optional[int]:
        relation = db.query(EventAction).filter(
            EventAction.event_id == event_id,
            EventAction.is_activate.is_(True),
        ).order_by(EventAction.priority.asc(), EventAction.id.asc()).first()
        if not relation:
            return None
        return db.query(ActionFlow.id).filter(ActionFlow.id == relation.flow_id).scalar()


unified_sensor_event_service = UnifiedSensorEventService()
