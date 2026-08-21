"""Supplemental operational context for safety-event risk escalation."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.models.analysis_report import AnalysisReportKnowledgeCitation
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.services.knowledge_service import knowledge_service
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.timeline_text import risk_label, truncate


PERSON_EVENT_CODES = {"PERSON_INTRUSION", "PERSON_WATERFRONT", "PERSON_WADING"}
RISK_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


class SupplementalContextService:
    """Apply operator-provided context and knowledge-backed risk escalation."""

    def apply(
        self,
        db: Session,
        instance: SafetyEventInstance,
        *,
        context: dict[str, Any],
        operator: str = "SYSTEM",
        defer_risk_decision_to_model: bool = False,
    ) -> dict[str, Any]:
        event = db.query(EventLibrary).filter(EventLibrary.id == instance.current_event_id).first()
        before = str(instance.max_risk_level or instance.risk_level or "LOW").upper()
        normalized = self._normalize_context(context, operator)
        observation = dict(instance.latest_observation or {})
        observation["supplemental_context"] = normalized
        instance.latest_observation = observation

        context_active = bool(normalized.get("active", True))
        safety_event_runtime_service.append_timeline(
            db,
            instance,
            log_type="SUPPLEMENTAL_CONTEXT",
            status="SUCCESS",
            title="补充运行状态",
            message=(
                f"工作人员补充运行状态：{normalized.get('label') or normalized.get('context_type')}"
                f"（类型 {normalized.get('context_type')}，影响区域 {truncate(normalized.get('affected_area') or '未知')}，"
                f"严重程度 {risk_label(normalized.get('severity_hint'))}，状态 {'持续中' if context_active else '已结束'}）"
            ),
            operator=operator,
            payload={"supplemental_context": normalized},
        )

        knowledge_result = self._search_knowledge(db, instance, event, observation, normalized)
        hits = knowledge_result.get("results") or []
        person_related = self._has_person_signal(event, observation)
        discharge_active = normalized.get("context_type") == "DAM_DISCHARGE" and bool(normalized.get("active", True))
        high_hit = self._first_high_risk_hit(hits)
        escalated = False
        after = before
        reason = ""

        if discharge_active and person_related and high_hit and defer_risk_decision_to_model:
            # 视频/传感器入口提交的特殊工况仅向 DAM 模型提供知识库依据，
            # 不能由规则直接把风险写成高风险；最终级别由模型工作流输出确认。
            reason = self._escalation_reason(normalized, high_hit)
            observation["risk_escalation"] = {
                "escalated": False,
                "pending_model_review": True,
                "from": before,
                "to": before,
                "reason": reason,
                "knowledge_hits": self._knowledge_hit_summary(hits),
                "escalation_source": "knowledge_base_pending_model",
            }
            instance.latest_observation = observation
            flag_modified(instance, "latest_observation")
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                log_type="RISK_REVIEW",
                status="SUCCESS",
                title="知识库风险依据待模型确认",
                message=(
                    f"已将补充信息「{normalized.get('label') or normalized.get('context_type')}」及知识库高风险依据"
                    "提交 DAM 模型复核，当前风险暂不变更"
                    + (f"（依据：{truncate(reason)}）" if reason else "")
                ),
                operator="SYSTEM",
                payload={
                    "risk_before": before,
                    "risk_after": before,
                    "pending_model_review": True,
                    "reason": reason,
                    "knowledge_hits": self._knowledge_hit_summary(hits),
                },
            )
        elif discharge_active and person_related and high_hit:
            after = "HIGH"
            reason = self._escalation_reason(normalized, high_hit)
            self._upgrade_instance(instance, observation, before, after, reason, hits)
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                log_type="RISK_CHANGE",
                status="SUCCESS",
                title="知识库风险升级",
                message=(
                    f"结合补充信息「{normalized.get('label') or normalized.get('context_type')}」与知识库依据，"
                    f"系统将风险由{risk_label(before)}升级为{risk_label(after)}"
                    + (f"（原因：{truncate(reason)}）" if reason else "")
                ),
                operator="SYSTEM",
                risk_level="HIGH",
                payload={
                    "risk_before": before,
                    "risk_after": after,
                    "reason": reason,
                    "knowledge_hits": self._knowledge_hit_summary(hits),
                    "escalation_source": "knowledge_base",
                },
            )
            self._store_existing_report_citations(db, instance, hits, reason)
            escalated = True
        else:
            reason = self._no_escalation_reason(discharge_active, person_related, bool(high_hit))
            observation["risk_escalation"] = {
                "escalated": False,
                "reason": reason,
                "knowledge_hits": self._knowledge_hit_summary(hits),
            }
            instance.latest_observation = observation
            flag_modified(instance, "latest_observation")
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                log_type="RISK_REVIEW",
                status="SUCCESS",
                title="知识库风险复核",
                message=f"知识库复核完成：{truncate(reason)}；当前风险维持{risk_label(after)}",
                operator="SYSTEM",
                payload={
                    "risk_before": before,
                    "risk_after": after,
                    "knowledge_hits": self._knowledge_hit_summary(hits),
                    "knowledge_hit_count": len(hits),
                },
            )

        db.commit()
        # The caller forwards this return value to the workflow payload.  Keep
        # the pending-review flag and provenance from the persisted object;
        # otherwise the model nodes receive only a flattened LOW result and
        # cannot distinguish a special-condition review from a normal event.
        workflow_escalation = observation.get("risk_escalation") if isinstance(observation.get("risk_escalation"), dict) else {}
        return {
            "event_instance_id": instance.id,
            "instance_no": instance.instance_no,
            "risk_before": before,
            "risk_after": after,
            "escalated": escalated,
            "reason": reason,
            "knowledge_hits": self._knowledge_hit_summary(hits),
            "pending_model_review": bool(workflow_escalation.get("pending_model_review")),
            "from": workflow_escalation.get("from", before),
            "to": workflow_escalation.get("to", after),
            "escalation_source": workflow_escalation.get("escalation_source"),
        }

    @staticmethod
    def _normalize_context(context: dict[str, Any], operator: str) -> dict[str, Any]:
        now = dt.datetime.now().isoformat()
        context_type = str(context.get("context_type") or "DAM_DISCHARGE").strip() or "DAM_DISCHARGE"
        label = str(context.get("label") or "").strip()
        if not label and context_type == "DAM_DISCHARGE":
            label = "库坝正在泄洪"
        return {
            "context_type": context_type,
            "active": bool(context.get("active", True)),
            "label": label or context_type,
            "severity_hint": str(context.get("severity_hint") or "HIGH").upper(),
            "occurred_at": context.get("occurred_at") or now,
            "affected_area": str(context.get("affected_area") or "滩涂、消落带、下游河道、近水岸线").strip(),
            "note": str(context.get("note") or "").strip(),
            "source": str(context.get("source") or "OPERATOR").upper(),
            "submitted_by": operator,
            "submitted_at": now,
        }

    def _search_knowledge(
        self,
        db: Session,
        instance: SafetyEventInstance,
        event: Optional[EventLibrary],
        observation: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        visual = observation.get("visual") if isinstance(observation.get("visual"), dict) else {}
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        terms = [
            context.get("label"),
            context.get("affected_area"),
            context.get("note"),
            getattr(event, "event_name", None),
            getattr(event, "event_code", None),
            observation.get("qwen_summary"),
            screening.get("qwen_summary"),
            "库坝 泄洪 开闸放水 滩涂 人员 亲水 涉水 消落带 下游河道 禁止进入 高风险 处置规范 风险升级",
        ]
        query = " ".join(str(item) for item in terms if item)
        return knowledge_service.search(
            db,
            query=query,
            category="risk_escalation",
            event_type="person_wading",
            risk_level="high",
            top_k=5,
        )

    @staticmethod
    def _has_person_signal(event: Optional[EventLibrary], observation: dict[str, Any]) -> bool:
        event_code = str(getattr(event, "event_code", "") or "").upper()
        if event_code in PERSON_EVENT_CODES:
            return True
        text = " ".join(
            str(value or "")
            for value in (
                getattr(event, "event_name", None),
                getattr(event, "event_category", None),
                observation.get("qwen_summary"),
                observation.get("summary"),
            )
        )
        visual = observation.get("visual") if isinstance(observation.get("visual"), dict) else {}
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        if int(observation.get("person_present") or screening.get("person_present") or 0) == 1:
            return True
        if int(observation.get("possible_person") or screening.get("possible_person") or 0) == 1:
            return True
        return any(keyword in text for keyword in ("人员", "滩涂", "亲水", "涉水", "消落带"))

    @staticmethod
    def _first_high_risk_hit(hits: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        for hit in hits:
            content = str(hit.get("content") or "")
            metadata = hit.get("metadata") or {}
            risk_levels = [str(item).lower() for item in metadata.get("risk_levels") or []]
            if "high" in risk_levels or "风险等级：高风险" in content or "风险等级: 高风险" in content:
                return hit
        return None

    @staticmethod
    def _upgrade_instance(
        instance: SafetyEventInstance,
        observation: dict[str, Any],
        before: str,
        after: str,
        reason: str,
        hits: list[dict[str, Any]],
    ) -> None:
        instance.risk_level = after
        if RISK_RANK.get(after, 0) > RISK_RANK.get(str(instance.max_risk_level or "").upper(), 0):
            instance.max_risk_level = after
        observation["risk_escalation"] = {
            "escalated": True,
            "from": before,
            "to": after,
            "reason": reason,
            "knowledge_hits": SupplementalContextService._knowledge_hit_summary(hits),
        }
        instance.latest_observation = observation
        flag_modified(instance, "latest_observation")
        instance.status = "PROCESSING" if instance.status not in {"FAILED", "FALSE_ALARM"} else instance.status

    @staticmethod
    def _knowledge_hit_summary(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for hit in hits[:5]:
            source = hit.get("source") or {}
            metadata = hit.get("metadata") or {}
            content = str(hit.get("content") or "")
            clause_id = source.get("clause_id") or metadata.get("clause_id") or SupplementalContextService._extract_clause_id(content)
            rows.append({
                "evidence_id": hit.get("evidence_id"),
                "chunk_id": hit.get("chunk_id"),
                "document_id": hit.get("document_id"),
                "document_title": source.get("document_title"),
                "clause_id": clause_id,
                "score": hit.get("score"),
                "excerpt": content[:240],
            })
        return rows

    @staticmethod
    def _extract_clause_id(content: str) -> str:
        match = re.search(r"条款编号[:：]\s*([A-Z0-9_-]+)", content or "")
        return match.group(1) if match else ""

    @staticmethod
    def _escalation_reason(context: dict[str, Any], hit: dict[str, Any]) -> str:
        source = hit.get("source") or {}
        clause_id = source.get("clause_id") or SupplementalContextService._extract_clause_id(str(hit.get("content") or ""))
        return (
            f"补充信息显示{context.get('label') or '库坝正在泄洪'}，"
            f"事件存在人员/滩涂活动线索，命中知识库条款{clause_id or '泄洪期人员禁入规则'}，"
            "泄洪期间滩涂及近水区域人员进入存在被困、冲刷和溺水风险。"
        )

    @staticmethod
    def _no_escalation_reason(discharge_active: bool, person_related: bool, high_hit: bool) -> str:
        if not discharge_active:
            return "补充信息未标记为正在泄洪，风险维持原等级"
        if not person_related:
            return "已记录泄洪状态，但当前事件未发现人员相关线索，风险维持原等级"
        if not high_hit:
            return "已记录泄洪状态和人员线索，但知识库未命中高风险禁入条款，风险维持原等级"
        return "风险维持原等级"

    def _store_existing_report_citations(
        self,
        db: Session,
        instance: SafetyEventInstance,
        hits: list[dict[str, Any]],
        reason: str,
    ) -> None:
        if not instance.analysis_report_id:
            return
        existing = db.query(AnalysisReportKnowledgeCitation.id).filter(
            AnalysisReportKnowledgeCitation.report_id == instance.analysis_report_id,
            AnalysisReportKnowledgeCitation.instance_no == instance.instance_no,
            AnalysisReportKnowledgeCitation.field_name == "risk_escalation",
        ).first()
        if existing:
            return
        for hit in hits[:3]:
            source = hit.get("source") or {}
            metadata = hit.get("metadata") or {}
            db.add(AnalysisReportKnowledgeCitation(
                report_id=instance.analysis_report_id,
                instance_no=instance.instance_no,
                field_name="risk_escalation",
                sentence=reason,
                evidence_id=str(hit.get("evidence_id") or ""),
                chunk_id=hit.get("chunk_id"),
                document_id=hit.get("document_id"),
                document_title=source.get("document_title") or "",
                section_path=source.get("section_path") or "",
                clause_id=source.get("clause_id") or metadata.get("clause_id") or self._extract_clause_id(str(hit.get("content") or "")),
                support_type="direct",
                confidence=str(hit.get("score") or ""),
            ))


supplemental_context_service = SupplementalContextService()
