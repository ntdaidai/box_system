"""Generate event handling reports from DAM workflow LLM results."""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse, urlunparse
from zoneinfo import ZoneInfo

from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from loguru import logger
from sqlalchemy.orm import Session, load_only

from app.core.config import BASE_DIR, settings
from app.models.analysis_report import AnalysisReport
from app.models.camera import Camera
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
)
from app.services.minio_service import minio_service
from app.services.patrol_report_service import store_generated_document
from app.services.safety_event_runtime_service import safety_event_runtime_service


TEMPLATE_PATH = Path(BASE_DIR) / "app" / "templates" / "dam_event_handling_report_template.docx"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
TEMPLATE_FIELDS = {
    "event_name",
    "instance_no",
    "risk_label",
    "result_label",
    "occur_time",
    "completed_at",
    "source_label",
    "location",
    "evidence_count",
    "summary",
    "key_observation",
    "source_summary",
    "handling_source",
    "timeline_count",
    "handling_summary",
    "timeline_summary",
    "evidence_summary",
    "frame_evidence_summary",
    "linkage_evidence_summary",
    "evidence_caption",
    "conclusion",
    "report_time",
    "instance_no_prefix",
    "instance_no_suffix",
    "occur_time_display",
    "event_duration",
    "emergency_level",
    "confidence_label",
    "trigger_summary",
    "screening_summary",
    "model_route_summary",
    "workflow_nodes_summary",
    "specialized_summary",
    "local_analysis_summary",
    "cloud_analysis_summary",
    "scene_detail",
    "risk_assessment_detail",
    "impact_assessment",
    "response_plan",
    "monitoring_suggestions",
    "recommendations_text",
    "evidence_inventory",
    "analysis_limitations",
    "follow_up_actions",
}
RISK_NAMES = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}
STATUS_NAMES = {
    "PENDING": "待处理",
    "PROCESSING": "处理中",
    "COMPLETED": "已完成",
    "FALSE_ALARM": "误报",
}
SYSTEM_FACT_FIELDS = {
    "report_date",
    "report_time",
    "event_name",
    "instance_no",
    "instance_no_prefix",
    "instance_no_suffix",
    "risk_label",
    "result_label",
    "occur_time",
    "occur_time_display",
    "completed_at",
    "event_duration",
    "source_label",
    "location",
    "evidence_count",
    "timeline_count",
    "timeline_summary",
    "evidence_caption",
    "evidence_image",
    "handling_summary",
    "conclusion",
    "summary",
    "key_observation",
    "source_summary",
    "screening_summary",
    "model_route_summary",
    "frame_evidence_summary",
    "evidence_summary",
}


class DamEventReportService:
    """Render and archive event reports using cloud LLM results with local fallback."""

    def generate_from_workflow(
        self,
        db: Session,
        *,
        instance: SafetyEventInstance,
        event: EventLibrary,
        workflow_payload: dict[str, Any],
    ) -> Optional[AnalysisReport]:
        selected = self.select_llm_report(workflow_payload)
        if not selected:
            logger.info("DAM事件报告跳过：未找到可用的大模型分析结果 instance={}", instance.instance_no)
            return None

        context = self.build_context(db, instance, event, workflow_payload, selected)
        docx_bytes = self.render_docx(context)
        # 报告文件名：以 ECA 触发的事件名命名，如「洪水灾害告警处置报告」
        event_name = getattr(event, "event_name", None) or instance.summary or "安全事件"
        filename = f"{self.safe_filename_part(event_name)}处置报告_{instance.instance_no}.docx"
        document_id = f"dam_event_report_{instance.instance_no}"
        document = store_generated_document(
            user_id=settings.PATROL_REPORT_USER_ID,
            user_name=settings.PATROL_REPORT_USER_NAME,
            document_id=document_id,
            filename=filename,
            content=docx_bytes,
            report_date=context["report_date"],
        )

        report = self.upsert_analysis_report(
            db,
            instance=instance,
            event=event,
            file_url=document["url"],
            report_date=context["report_date"],
        )
        safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"dam-event-report:{instance.instance_no}",
            log_type="REPORT",
            trigger_type="AUTO",
            status="SUCCESS",
            message=f"{event_name}处置报告已生成：{selected['source_label']}",
            payload={
                "instance_no": instance.instance_no,
                "analysis_report_id": report.id,
                "report_url": document["url"],
                "document_id": document["document_id"],
                "llm_source": selected["source"],
                "llm_source_label": selected["source_label"],
                "cloud_error": selected.get("cloud_error"),
            },
        )
        return report

    def select_llm_report(self, workflow_payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        execution = workflow_payload.get("execution_result")
        if not isinstance(execution, dict):
            return None
        node_results = execution.get("node_results") or []
        if not isinstance(node_results, list):
            return None

        cloud_error = self.find_cloud_error(node_results) or workflow_payload.get("execution_error")
        cloud_report = self.find_node_report(node_results, preferred_ids={"action_report"})
        if cloud_report:
            cloud_report["cloud_error"] = cloud_error
            return cloud_report

        local_report = self.find_node_report(node_results, preferred_ids={"action_reasoning"})
        if local_report:
            local_report["source"] = "qwen4b"
            local_report["source_label"] = "Qwen3-VL-4B 本地场景理解"
            if cloud_error:
                local_report["source_label"] += "（云端增强不可用，已降级采用本地结果）"
            local_report["cloud_error"] = cloud_error
            return local_report
        return None

    def find_node_report(
        self,
        node_results: list[Any],
        *,
        preferred_ids: set[str],
    ) -> Optional[dict[str, Any]]:
        for row in node_results:
            if not isinstance(row, dict):
                continue
            node_id = str(row.get("node_id") or row.get("id") or "")
            if node_id not in preferred_ids:
                continue
            if str(row.get("status") or "").lower() != "success":
                continue
            output = row.get("output")
            text = self.extract_text(output) or self.summarize_structured_output(output)
            if not text:
                continue
            if node_id == "action_report":
                return {
                    "source": "qwen35b",
                    "source_label": "Qwen3.6-35B-A3B 云端增强分析",
                    "text": text,
                    "raw_output": output,
                    "node_id": node_id,
                }
            return {
                "source": "qwen4b",
                "source_label": "Qwen3-VL-4B 本地场景理解",
                "text": text,
                "raw_output": output,
                "node_id": node_id,
            }
        return None

    def find_cloud_error(self, node_results: list[Any]) -> Optional[str]:
        for row in node_results:
            if not isinstance(row, dict):
                continue
            if str(row.get("node_id") or "") != "action_report":
                continue
            status = str(row.get("status") or "").lower()
            if status == "success":
                return None
            error = row.get("error") or row.get("message")
            if error:
                return str(error)
            output = row.get("output")
            if isinstance(output, dict) and output.get("error"):
                return str(output.get("error"))
        return None

    def extract_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("response", "report", "analysis", "summary", "content", "text", "final_report"):
                text = self.extract_text(value.get(key))
                if text:
                    return text
            inference = value.get("inference_result")
            text = self.extract_text(inference)
            if text:
                return text
            choices = value.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    text = self.extract_text(choice)
                    if text:
                        return text
            message = value.get("message")
            text = self.extract_text(message)
            if text:
                return text
        if isinstance(value, list):
            for item in value:
                text = self.extract_text(item)
                if text:
                    return text
        return ""

    def summarize_structured_output(self, value: Any) -> str:
        fields = self.extract_template_overrides(value)
        if fields.get("handling_summary"):
            return str(fields["handling_summary"]).strip()
        if fields.get("summary"):
            return str(fields["summary"]).strip()
        if fields.get("conclusion"):
            return str(fields["conclusion"]).strip()
        if not isinstance(value, dict):
            return ""
        parts = []
        for key in (
            "scene_description",
            "suspected_event",
            "risk_level",
            "confidence",
            "evidence",
            "uncertainties",
            "recommendations",
            "risk_assessment",
            "emergency_suggestion",
        ):
            current = value.get(key)
            if current in (None, "", []):
                continue
            label = {
                "scene_description": "现场描述",
                "suspected_event": "疑似事件",
                "risk_level": "风险等级",
                "confidence": "置信度",
                "evidence": "证据",
                "uncertainties": "不确定因素",
                "recommendations": "处置建议",
                "risk_assessment": "风险研判",
                "emergency_suggestion": "应急建议",
            }.get(key, key)
            if isinstance(current, list):
                current = "；".join(str(item) for item in current if item)
            parts.append(f"{label}：{current}")
        return "\n".join(parts)

    def extract_template_overrides(self, value: Any) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        self.collect_template_dicts(value, candidates)
        overrides: dict[str, Any] = {}
        for candidate in candidates:
            detailed = self.detailed_fields_summary(candidate)
            if detailed:
                overrides["handling_summary"] = detailed
            for field in TEMPLATE_FIELDS:
                current = candidate.get(field)
                if current in (None, "", []):
                    continue
                if field == "handling_summary" and overrides.get("handling_summary"):
                    continue
                if isinstance(current, (dict, list)):
                    current = self.format_structured_value(current)
                overrides[field] = current
            if not overrides.get("key_observation"):
                risk_reasoning = candidate.get("risk_reasoning")
                if isinstance(risk_reasoning, str) and risk_reasoning.strip():
                    overrides["key_observation"] = self.compact(risk_reasoning, 260)
            if not overrides.get("conclusion"):
                conclusion = candidate.get("impact_assessment") or candidate.get("monitoring_suggestions")
                if isinstance(conclusion, str) and conclusion.strip():
                    overrides["conclusion"] = self.compact(conclusion, 320)
        return overrides

    def detailed_fields_summary(self, value: dict[str, Any]) -> str:
        fields = [
            ("一、现场场景", value.get("detailed_scene_analysis")),
            ("二、风险研判", value.get("risk_reasoning")),
            ("三、影响评估", value.get("impact_assessment")),
            ("四、处置建议", value.get("response_plan")),
            ("五、持续监测", value.get("monitoring_suggestions")),
        ]
        lines = [f"{label}：{text}" for label, text in fields if isinstance(text, str) and text.strip()]
        return "\n".join(lines)

    def collect_template_dicts(self, value: Any, candidates: list[dict[str, Any]]) -> None:
        if isinstance(value, dict):
            if any(key in value for key in TEMPLATE_FIELDS):
                candidates.append(value)
            for key in ("template_fields", "template_data", "docx_context", "final_report", "inference_result"):
                current = value.get(key)
                if isinstance(current, dict):
                    self.collect_template_dicts(current, candidates)
            choices = value.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    self.collect_template_dicts(choice, candidates)
        elif isinstance(value, list):
            for item in value:
                self.collect_template_dicts(item, candidates)

    def format_structured_value(self, value: Any) -> str:
        if isinstance(value, list):
            return "；".join(str(item) for item in value if item)
        if isinstance(value, dict):
            return "；".join(f"{key}：{val}" for key, val in value.items() if val not in (None, "", []))
        return str(value)

    def build_context(
        self,
        db: Session,
        instance: SafetyEventInstance,
        event: EventLibrary,
        workflow_payload: dict[str, Any],
        selected: dict[str, Any],
    ) -> dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc)
        report_date = self.to_local_datetime(instance.started_at or now).date()
        source = db.query(DataSource).filter(DataSource.id == instance.data_source_id).first()
        camera = self.find_camera(db, instance)
        timeline = (
            db.query(SafetyEventTimelineLog)
            .options(
                load_only(
                    SafetyEventTimelineLog.id,
                    SafetyEventTimelineLog.event_instance_id,
                    SafetyEventTimelineLog.log_type,
                    SafetyEventTimelineLog.status,
                    SafetyEventTimelineLog.message,
                    SafetyEventTimelineLog.create_time,
                )
            )
            .filter(SafetyEventTimelineLog.event_instance_id == instance.id)
            .order_by(SafetyEventTimelineLog.id.asc())
            .all()
        )
        evidence = (
            db.query(SafetyEventEvidence)
            .filter(SafetyEventEvidence.event_instance_id == instance.id)
            .order_by(SafetyEventEvidence.captured_at.asc(), SafetyEventEvidence.id.asc())
            .all()
        )
        visual = self.visual_snapshot(instance)
        image_items = self.collect_image_items(workflow_payload, visual, evidence)
        video_items = self.collect_video_items(workflow_payload, visual, evidence)
        selected_text = self.clean_report_text(selected["text"])
        workflow_insight = self.workflow_insight(workflow_payload, visual, selected_text)
        if not image_items and video_items:
            image_items = self.extract_frame_items_from_videos(
                video_items,
                event_name=getattr(event, "event_name", None) or instance.summary or "安全事件",
                analysis_text=selected_text,
                workflow_insight=workflow_insight,
            )
        timeline_summary = self.timeline_summary(timeline)
        evidence_image_path = self.download_first_image(image_items)

        source_label = self.source_label(instance, source, selected)
        cloud_note = ""
        if selected.get("source") == "qwen4b" and selected.get("cloud_error"):
            cloud_note = f"云端增强分析返回异常：{selected['cloud_error']}；本报告已采用本地 4B 分析结果生成。"

        context = {
            "report_date": report_date,
            "report_time": self.format_datetime(dt.datetime.now(LOCAL_TIMEZONE)),
            "event_name": getattr(event, "event_name", None) or instance.summary or "安全事件",
            "instance_no": instance.instance_no,
            "instance_no_prefix": self.instance_no_parts(instance.instance_no)[0],
            "instance_no_suffix": self.instance_no_parts(instance.instance_no)[1],
            "risk_label": RISK_NAMES.get(str(instance.max_risk_level or instance.risk_level or "").upper(), "低风险"),
            "result_label": self.result_label(instance),
            "occur_time": self.format_datetime(instance.started_at),
            "occur_time_display": self.format_datetime(instance.started_at).replace(" ", "\n"),
            "completed_at": self.completed_at(instance, timeline),
            "event_duration": self.event_duration(instance, timeline),
            "emergency_level": self.emergency_level(instance),
            "confidence_label": self.confidence_label(selected),
            "source_label": source_label,
            "location": self.location(source, camera, visual),
            "evidence_count": len(image_items),
            "summary": self.event_summary(instance, event, source, visual, workflow_insight),
            "key_observation": self.key_observation(workflow_payload, visual, selected_text, workflow_insight),
            "source_summary": self.source_summary(image_items, video_items, selected),
            "handling_source": selected["source_label"],
            "timeline_count": len(timeline),
            "trigger_summary": self.trigger_summary(instance, event, visual, workflow_insight),
            "screening_summary": self.screening_summary(visual),
            "model_route_summary": self.model_route_summary(workflow_payload, selected),
            "workflow_nodes_summary": self.workflow_nodes_summary(workflow_payload),
            "specialized_summary": self.specialized_summary(workflow_insight),
            "local_analysis_summary": self.node_analysis_summary(workflow_payload, "action_reasoning"),
            "cloud_analysis_summary": self.node_analysis_summary(workflow_payload, "action_report"),
            "scene_detail": self.final_report_field(selected, "detailed_scene_analysis", selected_text),
            "risk_assessment_detail": self.final_report_field(selected, "risk_reasoning", workflow_insight.get("raw_excerpt")),
            "impact_assessment": self.final_report_field(selected, "impact_assessment", "需结合现场巡查、水位雨量和坝体状态持续确认影响范围。"),
            "response_plan": self.final_report_field(selected, "response_plan", "维持事件取证和现场复核，按风险等级启动相应联动处置。"),
            "monitoring_suggestions": self.final_report_field(selected, "monitoring_suggestions", "持续跟踪摄像头画面、水位、雨量、风速和坝体安全监测数据。"),
            "recommendations_text": self.recommendations_text(selected),
            "evidence_inventory": self.evidence_inventory(image_items, video_items),
            "frame_evidence_summary": self.frame_evidence_summary(image_items, video_items),
            "linkage_evidence_summary": self.linkage_evidence_summary(evidence),
            "analysis_limitations": self.analysis_limitations(selected, workflow_insight, image_items, video_items),
            "follow_up_actions": self.follow_up_actions(instance, selected),
            "handling_summary": self.handling_summary(
                instance=instance,
                event=event,
                visual=visual,
                selected=selected,
                selected_text=selected_text,
                workflow_insight=workflow_insight,
                image_items=image_items,
                video_items=video_items,
            ),
            "timeline_summary": timeline_summary,
            "evidence_summary": self.evidence_summary(image_items, video_items),
            "evidence_caption": self.evidence_caption(image_items, video_items),
            "evidence_image": evidence_image_path,
            "conclusion": self.build_conclusion(selected, workflow_insight, cloud_note),
        }
        overrides = self.extract_template_overrides(selected.get("raw_output"))
        context.update({
            key: value
            for key, value in overrides.items()
            if key not in SYSTEM_FACT_FIELDS
        })
        context["report_date"] = report_date
        context["report_time"] = self.format_datetime(dt.datetime.now(LOCAL_TIMEZONE))
        context["event_name"] = getattr(event, "event_name", None) or instance.summary or "安全事件"
        context["instance_no"] = instance.instance_no
        context["instance_no_prefix"], context["instance_no_suffix"] = self.instance_no_parts(instance.instance_no)
        context["risk_label"] = RISK_NAMES.get(str(instance.max_risk_level or instance.risk_level or "").upper(), "低风险")
        context["result_label"] = self.result_label(instance)
        context["occur_time"] = self.format_datetime(instance.started_at)
        context["occur_time_display"] = self.format_datetime(instance.started_at).replace(" ", "\n")
        context["completed_at"] = self.completed_at(instance, timeline)
        context["event_duration"] = self.event_duration(instance, timeline)
        context["evidence_count"] = len(image_items)
        context["timeline_count"] = len(timeline)
        context["timeline_summary"] = timeline_summary
        context["evidence_caption"] = self.evidence_caption(image_items, video_items)
        context["evidence_image"] = evidence_image_path
        if selected.get("source") == "qwen4b":
            if not context.get("handling_summary"):
                context["handling_summary"] = self.handling_summary(
                    instance=instance,
                    event=event,
                    visual=visual,
                    selected=selected,
                    selected_text=selected_text,
                    workflow_insight=workflow_insight,
                    image_items=image_items,
                    video_items=video_items,
                )
            context["conclusion"] = self.build_conclusion(selected, workflow_insight, cloud_note)
        else:
            context["conclusion"] = self.build_conclusion(selected, workflow_insight, cloud_note)
        return context

    def render_docx(self, context: dict[str, Any]) -> bytes:
        template = DocxTemplate(str(TEMPLATE_PATH))
        image_path = context.pop("evidence_image", None)
        render_context = dict(context)
        if image_path:
            render_context["evidence_image"] = InlineImage(template, str(image_path), width=Mm(130))
        else:
            render_context["evidence_image"] = "未获取到可嵌入图像"
        template.render(render_context)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            template.save(str(temp_path))
            return temp_path.read_bytes()
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if image_path:
                try:
                    Path(image_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def upsert_analysis_report(
        self,
        db: Session,
        *,
        instance: SafetyEventInstance,
        event: EventLibrary,
        file_url: str,
        report_date: dt.date,
    ) -> AnalysisReport:
        report = None
        if instance.analysis_report_id:
            report = db.query(AnalysisReport).filter(AnalysisReport.id == instance.analysis_report_id).first()
        if not report:
            report_no = f"EVR_{instance.instance_no}"
            report = db.query(AnalysisReport).filter(AnalysisReport.report_no == report_no).first()
        if not report:
            report = AnalysisReport(
                report_no=f"EVR_{instance.instance_no}",
                report_title=f"{getattr(event, 'event_name', None) or '安全事件'}处置报告",
                report_type="event",
                report_date=report_date,
                file_url=file_url,
            )
            db.add(report)
            db.flush()
        else:
            report.report_title = f"{getattr(event, 'event_name', None) or '安全事件'}处置报告"
            report.report_type = "event"
            report.report_date = report_date
            report.file_url = file_url
        instance.analysis_report_id = report.id
        db.flush()
        return report

    def find_camera(self, db: Session, instance: SafetyEventInstance) -> Optional[Camera]:
        visual = self.visual_snapshot(instance)
        camera_id = visual.get("camera_id") or instance.source_id
        if camera_id and str(camera_id).isdigit():
            return db.query(Camera).filter(Camera.id == int(camera_id)).first()
        return None

    def visual_snapshot(self, instance: SafetyEventInstance) -> dict[str, Any]:
        observation = dict(instance.latest_observation or {})
        visual = observation.get("visual")
        return dict(visual) if isinstance(visual, dict) else {}

    def collect_image_items(
        self,
        workflow_payload: dict[str, Any],
        visual: dict[str, Any],
        evidence: list[SafetyEventEvidence],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        self.extend_media_items(items, visual.get("qwen_image_urls"))
        self.extend_media_items(items, visual.get("images"))
        self.extend_media_items(items, screening.get("qwen_image_urls"))
        self.extend_media_items(items, screening.get("image_urls"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "representative_frame"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "representative_frames"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "key_frames"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "images"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "image_urls"))
        for row in evidence:
            if str(row.evidence_type or "").upper() in {"IMAGE", "CAMERA_SNAPSHOT", "DRONE_IMAGE", "STAFF_IMAGE"}:
                items.append({"url": row.file_url, "caption": row.description or "事件图像"})
        return self.unique_media_items(items)[:8]

    def collect_video_items(
        self,
        workflow_payload: dict[str, Any],
        visual: dict[str, Any],
        evidence: list[SafetyEventEvidence],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        self.extend_media_items(items, visual.get("video_urls"))
        self.extend_media_items(items, visual.get("videos"))
        self.extend_media_items(items, screening.get("video_urls"))
        self.extend_media_items(items, screening.get("videos"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "videos"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "video_urls"))
        for row in evidence:
            if str(row.evidence_type or "").upper() == "VIDEO":
                items.append({"url": row.file_url, "caption": row.description or "事件证据视频"})
        return self.unique_media_items(items)

    def extend_media_items(self, items: list[dict[str, Any]], value: Any) -> None:
        if not value:
            return
        if isinstance(value, str):
            if "{{" in value or "}}" in value:
                return
            items.append({"url": value, "caption": ""})
            return
        if isinstance(value, dict):
            url = (
                value.get("url")
                or value.get("file_url")
                or value.get("image_url")
                or value.get("video_url")
                or value.get("object_url")
            )
            object_name = value.get("object_name") or value.get("object_key")
            if not url and value.get("bucket") and object_name:
                url = f"{value.get('bucket')}/{object_name}"
            if url:
                if "{{" in str(url) or "}}" in str(url):
                    return
                items.append({"url": str(url), "caption": str(value.get("caption") or value.get("description") or "")})
            return
        if isinstance(value, list):
            for item in value:
                self.extend_media_items(items, item)

    def unique_media_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result = []
        for item in items:
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            bucket, object_name = self.parse_minio_reference(url)
            dedupe_key = f"{bucket}/{object_name}" if bucket and object_name else url
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            result.append(item)
        return result

    def find_nested_values(self, value: Any, key: str) -> list[Any]:
        values: list[Any] = []
        if isinstance(value, dict):
            for current_key, current_value in value.items():
                if current_key == key:
                    values.append(current_value)
                values.extend(self.find_nested_values(current_value, key))
        elif isinstance(value, list):
            for item in value:
                values.extend(self.find_nested_values(item, key))
        return values

    def download_first_image(self, items: list[dict[str, Any]]) -> Optional[Path]:
        for item in items:
            content = self.read_minio_or_http_bytes(str(item.get("url") or ""))
            if not content:
                continue
            suffix = ".jpg"
            parsed_suffix = Path(urlparse(str(item.get("url") or "")).path).suffix.lower()
            if parsed_suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                suffix = parsed_suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                return Path(tmp.name)
        return None

    def extract_frame_items_from_videos(
        self,
        video_items: list[dict[str, Any]],
        *,
        event_name: str,
        analysis_text: str,
        workflow_insight: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Legacy fallback for reports generated before the workflow returned representative frames."""
        items: list[dict[str, Any]] = []
        for index, item in enumerate(video_items[:2], 1):
            frame_path = self.extract_video_frame(str(item.get("url") or ""))
            if frame_path:
                items.append({
                    "url": str(frame_path),
                    "caption": item.get("caption") or f"事件证据视频兜底抽帧{index}",
                    "source": "legacy_video_frame_fallback",
                })
        return items

    def extract_video_frame(self, value: str) -> Optional[Path]:
        candidates = self.extract_video_candidate_frames(value)
        if not candidates:
            return None
        middle = candidates[len(candidates) // 2]
        selected_path = Path(str(middle["path"]))
        for candidate in candidates:
            path = Path(str(candidate.get("path") or ""))
            if path != selected_path:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        return selected_path if selected_path.exists() else None

    def extract_video_candidate_frames(self, value: str, count: int = 4) -> list[dict[str, Any]]:
        video_bytes = self.read_minio_or_http_bytes(
            value,
            allowed_suffixes={".mp4", ".mov", ".m4v", ".webm"},
            allowed_content_prefixes={"video/"},
        )
        if not video_bytes:
            return []
        ffmpeg = shutil.which(settings.FFMPEG_BIN) or shutil.which("ffmpeg")
        if not ffmpeg:
            logger.warning("未找到 FFmpeg，无法从事件视频抽帧")
            return []
        input_path: Optional[Path] = None
        output_paths: list[Path] = []
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_tmp:
                video_tmp.write(video_bytes)
                input_path = Path(video_tmp.name)
            duration = self.probe_video_duration(input_path)
            timestamps = self.candidate_frame_timestamps(duration, count=count)
            candidates: list[dict[str, Any]] = []
            for frame_index, timestamp in enumerate(timestamps, 1):
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as frame_tmp:
                    output_path = Path(frame_tmp.name)
                output_paths.append(output_path)
                command = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(input_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale='if(gte(iw,ih),min(iw,1280),-2)':'if(gte(iw,ih),-2,min(ih,720))'",
                    "-q:v",
                    "4",
                    "-y",
                    str(output_path),
                ]
                result = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=12,
                    check=False,
                )
                if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                    candidates.append({
                        "index": frame_index,
                        "timestamp": round(timestamp, 3),
                        "path": output_path,
                    })
                else:
                    message = result.stderr.decode("utf-8", errors="replace").strip()
                    logger.debug("候选代表帧抽取失败 {} @{}s: {}", value, timestamp, message[:200])
            return candidates
        except Exception as exc:
            logger.warning("事件视频抽帧异常 {}: {}", value, exc)
        finally:
            if input_path:
                try:
                    input_path.unlink(missing_ok=True)
                except OSError:
                    pass
        for output_path in output_paths:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
        return []

    @staticmethod
    def probe_video_duration(input_path: Path) -> float:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0.0
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(input_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False,
            )
            return max(0.0, float((result.stdout or b"").decode().strip() or 0.0))
        except Exception:
            return 0.0

    @staticmethod
    def candidate_frame_timestamps(duration: float, count: int = 4) -> list[float]:
        count = max(1, min(int(count or 4), 6))
        if duration > 1.2:
            start = min(0.6, duration * 0.12)
            end = max(start, duration - min(0.4, duration * 0.08))
            if count == 1:
                return [duration / 2]
            return [
                start + (end - start) * index / (count - 1)
                for index in range(count)
            ]
        return [0.2 + index * 0.8 for index in range(count)]

    def read_minio_or_http_bytes(
        self,
        value: str,
        *,
        allowed_suffixes: Optional[set[str]] = None,
        allowed_content_prefixes: Optional[set[str]] = None,
    ) -> Optional[bytes]:
        allowed_suffixes = allowed_suffixes or {".jpg", ".jpeg", ".png", ".webp"}
        allowed_content_prefixes = allowed_content_prefixes or {"image/"}
        local_path = Path(str(value or ""))
        if local_path.is_absolute() and local_path.exists():
            suffix = local_path.suffix.lower()
            if suffix in allowed_suffixes:
                try:
                    return local_path.read_bytes()
                except OSError as exc:
                    logger.debug("读取本地图像失败 {}: {}", value, exc)
        bucket, object_name = self.parse_minio_reference(value)
        if bucket and object_name and not minio_service.client:
            try:
                minio_service.connect()
            except Exception as exc:
                logger.debug("MinIO 懒连接失败: {}", exc)
        if bucket and object_name and minio_service.client:
            try:
                response = minio_service.client.get_object(bucket, object_name)
                try:
                    return response.read()
                finally:
                    response.close()
                    response.release_conn()
            except Exception as exc:
                logger.debug("读取 MinIO 图像失败 {}: {}", value, exc)
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            urls = [value]
            if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 9000:
                endpoint = getattr(settings, "QWEN_CAMERA_SCREENING_MINIO_ENDPOINT", "") or "172.17.0.1:9000"
                urls.append(urlunparse(parsed._replace(netloc=endpoint)))
            for url in urls:
                try:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        content_type = response.headers.get("Content-Type") or ""
                        data = response.read()
                    if data and (
                        any(content_type.startswith(prefix) for prefix in allowed_content_prefixes)
                        or Path(parsed.path).suffix.lower() in allowed_suffixes
                    ):
                        return data
                except Exception as exc:
                    logger.debug("HTTP读取图像失败 {}: {}", url, exc)
        return None

    def parse_minio_reference(self, value: str) -> tuple[Optional[str], Optional[str]]:
        text = str(value or "").strip()
        if not text:
            return None, None
        parsed = urlparse(text)
        if parsed.scheme in {"http", "https"}:
            parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
            if len(parts) >= 2:
                return parts[0], "/".join(parts[1:])
            return None, None
        if "/" in text and not text.startswith("/"):
            bucket, object_name = text.split("/", 1)
            if bucket and object_name:
                return bucket, object_name
        return None, None

    def source_label(self, instance: SafetyEventInstance, source: Optional[DataSource], selected: dict[str, Any]) -> str:
        source_type = str(instance.source_type or getattr(source, "source_type", "") or "").lower()
        base = {"camera": "摄像头触发", "sensor": "传感器触发"}.get(source_type, source_type or "事件触发")
        return f"{base} · {selected['source_label']}"

    def location(self, source: Optional[DataSource], camera: Optional[Camera], visual: dict[str, Any]) -> str:
        values = [
            visual.get("camera_name"),
            getattr(camera, "install_address", None),
            visual.get("zone_name"),
            getattr(source, "source_name", None),
        ]
        return " · ".join(str(value) for value in values if value) or "—"

    def result_label(self, instance: SafetyEventInstance) -> str:
        if instance.state == "RESOLVED":
            if instance.status == "FALSE_ALARM":
                return "误报关闭"
            return "已闭环"
        return STATUS_NAMES.get(str(instance.status or "").upper(), "处理中")

    def completed_at(
        self,
        instance: SafetyEventInstance,
        timeline: Optional[list[SafetyEventTimelineLog]] = None,
    ) -> str:
        end = self.completion_time(instance, timeline)
        return self.format_datetime(end) if end else "—"

    def event_duration(
        self,
        instance: SafetyEventInstance,
        timeline: Optional[list[SafetyEventTimelineLog]] = None,
    ) -> str:
        start = instance.started_at
        end = self.completion_time(instance, timeline) or instance.last_observed_at or dt.datetime.now()
        if not start or not end:
            return "—"
        seconds = max(0, int((end - start).total_seconds()))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}小时{minutes}分钟{sec}秒"
        if minutes:
            return f"{minutes}分钟{sec}秒"
        return f"{sec}秒"

    @staticmethod
    def completion_time(
        instance: SafetyEventInstance,
        timeline: Optional[list[SafetyEventTimelineLog]] = None,
    ) -> Optional[dt.datetime]:
        if timeline:
            candidates = [
                row.create_time
                for row in timeline
                if row.create_time
                and str(row.log_type or "").upper() in {"ACTION", "REPORT", "DAM_WORKFLOW"}
            ]
            if candidates:
                return max(candidates)
        return instance.resolved_at

    def instance_no_parts(self, instance_no: str) -> tuple[str, str]:
        text = str(instance_no or "").strip()
        if "_" not in text:
            return text, ""
        parts = text.split("_")
        if len(parts) >= 3:
            return "_".join(parts[:2]), "_".join(parts[2:])
        return text, ""

    def emergency_level(self, instance: SafetyEventInstance) -> str:
        risk = str(instance.max_risk_level or instance.risk_level or "").upper()
        return {"HIGH": "I级关注", "MEDIUM": "II级关注", "LOW": "III级关注"}.get(risk, "待确认")

    def confidence_label(self, selected: dict[str, Any]) -> str:
        confidence = self.numeric_value(self.find_in_selected(selected, "confidence"))
        if confidence is None:
            return "—"
        return f"{confidence * 100:.1f}%"

    def event_summary(
        self,
        instance: SafetyEventInstance,
        event: EventLibrary,
        source: Optional[DataSource],
        visual: dict[str, Any],
        insight: dict[str, Any],
    ) -> str:
        camera_name = visual.get("camera_name") or getattr(source, "source_name", None) or "现场摄像头"
        event_name = getattr(event, "event_name", None) or instance.summary or "安全事件"
        qwen_summary = insight.get("qwen_summary")
        if self.looks_like_model_thinking(str(qwen_summary or "")):
            qwen_summary = ""
        qwen4b_summary = self.compact(str(insight.get("qwen4b_conclusion") or ""), 120)
        if qwen4b_summary and qwen4b_summary != "—":
            return self.compact(f"{camera_name}触发{event_name}，智能分析结论：{qwen4b_summary}", 170)
        if qwen_summary:
            return self.compact(f"{camera_name}触发{event_name}，初筛摘要：{qwen_summary}。", 180)
        detected = insight.get("specialized_class_label")
        if detected:
            return f"{camera_name}触发{event_name}，专有模型复核结果为{detected}。"
        return self.compact(instance.summary or event_name, 220)

    def key_observation(
        self,
        workflow_payload: dict[str, Any],
        visual: dict[str, Any],
        selected_text: str,
        insight: Optional[dict[str, Any]] = None,
    ) -> str:
        insight = insight or {}
        parts = []
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        if screening.get("summary") and not self.looks_like_model_thinking(str(screening.get("summary"))):
            parts.append(str(screening.get("summary")))
        if not parts and insight.get("qwen4b_risk_reasoning"):
            parts.append(self.compact(str(insight.get("qwen4b_risk_reasoning")), 220))
        main_class = insight.get("specialized_class")
        confidence = insight.get("specialized_confidence")
        if main_class:
            parts.append(f"专有模型复核：{insight.get('specialized_class_label') or main_class}")
        if confidence is not None:
            try:
                parts.append(f"置信度：{float(confidence) * 100:.1f}%")
            except (TypeError, ValueError):
                parts.append(f"置信度：{confidence}")
        if parts:
            return "；".join(parts[:3])
        return self.compact(selected_text, 180)

    def first_nested_value(self, value: Any, key: str) -> Any:
        values = self.find_nested_values(value, key)
        for item in values:
            if item in (None, "", []):
                continue
            if isinstance(item, dict):
                continue
            if isinstance(item, list):
                continue
            else:
                return item
        return None

    def source_summary(self, image_items: list[dict[str, Any]], video_items: list[dict[str, Any]], selected: dict[str, Any]) -> str:
        pieces = [f"采用{selected['source_label']}生成分析结论"]
        if video_items:
            pieces.append(f"关联事件证据视频 {len(video_items)} 段")
        if image_items:
            pieces.append(f"关联抽帧图像 {len(image_items)} 张")
        return "；".join(pieces) + "。"

    def evidence_summary(self, image_items: list[dict[str, Any]], video_items: list[dict[str, Any]]) -> str:
        if not image_items and not video_items:
            return "本次事件未记录可用图像或视频证据。"
        pieces = []
        if video_items:
            pieces.append(f"已归档 {len(video_items)} 段事件证据视频")
        if image_items:
            pieces.append(f"已归档 {len(image_items)} 张关键帧/检测图像")
        return "；".join(pieces) + "，用于支撑本次事件研判。"

    def evidence_caption(self, image_items: list[dict[str, Any]], video_items: list[dict[str, Any]]) -> str:
        return ""

    def trigger_summary(
        self,
        instance: SafetyEventInstance,
        event: EventLibrary,
        visual: dict[str, Any],
        insight: dict[str, Any],
    ) -> str:
        event_name = getattr(event, "event_name", None) or instance.summary or "安全事件"
        camera_name = visual.get("camera_name") or "现场摄像头"
        summary = insight.get("qwen_summary") or "触发时未记录初筛摘要"
        return f"{camera_name}在{self.format_datetime(instance.started_at)}触发{event_name}，初筛摘要为：{summary}。"

    def screening_summary(self, visual: dict[str, Any]) -> str:
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        if not screening:
            return "未获取到摄像头初筛结构化结果。"
        labels = [
            ("洪水", "flood_detected", "flood_confidence"),
            ("泥石流", "mudslide_detected", "mudslide_confidence"),
            ("滑坡", "landslide_detected", "landslide_confidence"),
            ("地震", "earthquake_detected", "earthquake_confidence"),
            ("人员", "person_present", "person_confidence"),
            ("船只/捕鱼", "boat_present", "boat_confidence"),
        ]
        hits = []
        negatives = []
        for label, flag_key, confidence_key in labels:
            flag = screening.get(flag_key)
            confidence = self.numeric_value(screening.get(confidence_key))
            text = f"{label}({confidence * 100:.1f}%)" if confidence is not None else label
            if str(flag) in {"1", "True", "true"} or flag == 1 or flag is True:
                hits.append(text)
            else:
                negatives.append(label)
        hit_text = "、".join(hits) if hits else "未命中明确场景"
        negative_text = "、".join(negatives[:6]) if negatives else "无"
        return f"初筛命中：{hit_text}；未命中/排除：{negative_text}；风险等级：{screening.get('qwen_risk_level') or '—'}。"

    def model_route_summary(self, workflow_payload: dict[str, Any], selected: dict[str, Any]) -> str:
        execution = workflow_payload.get("execution_result") if isinstance(workflow_payload, dict) else {}
        nodes = (execution or {}).get("node_results") or []
        success_nodes = {
            str(row.get("node_id") or "")
            for row in nodes
            if isinstance(row, dict) and str(row.get("status") or "").lower() == "success"
        }
        route_parts = []
        if "action_classify" in success_nodes:
            route_parts.append("专有模型完成灾害类别复核")
        if "action_reasoning" in success_nodes:
            route_parts.append("4B本地模型完成现场语义理解")
        if "action_report" in success_nodes:
            route_parts.append("35B云端模型完成增强研判与报告校核")
        route_text = "，".join(route_parts) if route_parts else "模型节点已完成可用结果回传"
        source_label = selected.get("source_label", "智能分析模型")
        return f"ECA触发后，智能路由进入自然灾害分析链路，{route_text}；本报告以{source_label}结果作为最终分析依据。"

    def workflow_nodes_summary(self, workflow_payload: dict[str, Any]) -> str:
        execution = workflow_payload.get("execution_result") if isinstance(workflow_payload, dict) else {}
        rows = []
        label_map = {
            "start_0": "事件触发",
            "action_classify": "专有模型复核",
            "action_reasoning": "4B 场景理解",
            "action_report": "35B 增强分析",
            "end_0": "流程结束",
        }
        for row in (execution or {}).get("node_results") or []:
            if not isinstance(row, dict):
                continue
            node_id = str(row.get("node_id") or "")
            status = str(row.get("status") or "unknown")
            model_id = row.get("model_id")
            meta = row.get("request_meta") if isinstance(row.get("request_meta"), dict) else {}
            media = []
            if meta.get("video_count"):
                media.append(f"视频{meta.get('video_count')}段")
            if meta.get("image_count"):
                media.append(f"图片{meta.get('image_count')}张")
            media_text = f"，输入{'、'.join(media)}" if media else ""
            model_text = f"，模型ID {model_id}" if model_id else ""
            rows.append(f"{label_map.get(node_id, node_id)}：{status}{model_text}{media_text}")
        return "\n".join(rows) or "未记录模型节点执行明细。"

    def specialized_summary(self, insight: dict[str, Any]) -> str:
        label = insight.get("specialized_class_label") or "未获得专有模型类别"
        confidence = insight.get("specialized_confidence")
        confidence_text = f"{confidence * 100:.1f}%" if confidence is not None else "—"
        sampled = insight.get("sampled_frames") or "—"
        report = insight.get("classification_report")
        suffix = f"；模型说明：{self.compact(str(report), 220)}" if report else ""
        return f"复核类别：{label}；置信度：{confidence_text}；采样帧数：{sampled}{suffix}。"

    def node_analysis_summary(self, workflow_payload: dict[str, Any], node_id: str) -> str:
        inference = self.find_node_inference(workflow_payload, node_id)
        if not inference:
            return "该节点未返回可用分析。"
        source = inference.get("system_prompt_source") or inference.get("actor_name") or node_id
        risk = inference.get("risk_level") or self.find_in_value(inference, "risk_level") or "—"
        confidence = self.numeric_value(inference.get("confidence") or self.find_in_value(inference, "confidence"))
        confidence_text = f"{confidence * 100:.1f}%" if confidence is not None else "—"
        report = (
            inference.get("report")
            or self.find_in_value(inference, "scene_analysis")
            or self.find_in_value(inference, "detailed_scene_analysis")
            or "未生成文字摘要"
        )
        return f"来源：{source}；风险：{risk}；置信度：{confidence_text}；摘要：{self.compact(str(report), 420)}"

    def evidence_inventory(self, image_items: list[dict[str, Any]], video_items: list[dict[str, Any]]) -> str:
        rows = []
        for index, item in enumerate(video_items[:5], 1):
            rows.append(f"视频{index}：{item.get('caption') or '事件证据视频'}，位置：{item.get('url')}")
        for index, item in enumerate(image_items[:8], 1):
            rows.append(f"图像{index}：{item.get('caption') or '关键帧/截图'}，位置：{item.get('url')}")
        return "\n".join(rows) if rows else "未归档媒体证据。"

    def frame_evidence_summary(self, image_items: list[dict[str, Any]], video_items: list[dict[str, Any]]) -> str:
        qwen_frames = 0
        review_frames = 0
        for item in image_items:
            url = str(item.get("url") or "")
            if "/evidence/" in url or "yolo_frames" in url or "key_frame" in url:
                review_frames += 1
            else:
                qwen_frames += 1
        parts = []
        if video_items:
            parts.append(f"事件证据视频{len(video_items)}段")
        if qwen_frames:
            parts.append(f"摄像头初筛关键帧{qwen_frames}张")
        if review_frames:
            parts.append(f"模型复核抽帧{review_frames}张")
        if not parts:
            return "未记录可用于报告展示的抽帧图片。"
        return "已归档" + "、".join(parts) + "；报告正文嵌入代表性画面，其余图片随事件证据一并留存。"

    def linkage_evidence_summary(self, evidence: list[SafetyEventEvidence]) -> str:
        labels = {
            "DRONE": "无人机",
            "UAV": "无人机",
            "DRONE_IMAGE": "无人机",
            "DRONE_VIDEO": "无人机",
            "ROBOT_DOG": "机器狗",
            "ROBOT": "机器狗",
            "ROBOT_IMAGE": "机器狗",
            "ROBOT_VIDEO": "机器狗",
        }
        counts: dict[str, int] = {}
        for row in evidence:
            source_type = str(row.source_type or "").upper()
            evidence_type = str(row.evidence_type or "").upper()
            label = labels.get(source_type) or labels.get(evidence_type)
            if not label:
                continue
            counts[label] = counts.get(label, 0) + 1
        if counts:
            return "；".join(f"{label}联动取证{count}条" for label, count in counts.items()) + "，作为现场补充证据。"
        return "本次事件暂未记录机器狗或无人机联动取证；如后续联动设备上传图片/视频，将作为补充证据归档。"

    def analysis_limitations(
        self,
        selected: dict[str, Any],
        insight: dict[str, Any],
        image_items: list[dict[str, Any]],
        video_items: list[dict[str, Any]],
    ) -> str:
        limitations = self.find_in_selected(selected, "uncertainties")
        if isinstance(limitations, list) and limitations:
            return "；".join(str(item) for item in limitations if item)
        if isinstance(limitations, str) and limitations.strip():
            return limitations.strip()
        parts = []
        if not video_items:
            parts.append("缺少可回放事件视频")
        if not image_items:
            parts.append("报告未嵌入可用关键帧")
        if not insight.get("specialized_confidence"):
            parts.append("专有模型置信度未记录")
        return "；".join(parts) if parts else "未发现明显数据缺口，仍建议结合现场人工复核。"

    def follow_up_actions(self, instance: SafetyEventInstance, selected: dict[str, Any]) -> str:
        risk = str(instance.max_risk_level or instance.risk_level or "").upper()
        base = [
            "保留本次事件视频、关键帧、模型结果和人工处置记录，形成可追溯证据链。",
            "将事件结论同步至值班台账，复盘智能路由节点耗时和模型输出质量。",
        ]
        if risk == "HIGH":
            base.insert(0, "按高风险事件进行持续跟踪，闭环后仍需安排现场或远程复核。")
        if selected.get("cloud_error"):
            base.append("云端模型异常期间应复核本地 4B 结果，待云端恢复后可重新生成增强报告。")
        return "\n".join(f"{idx}. {text}" for idx, text in enumerate(base, 1))

    def recommendations_text(self, selected: dict[str, Any]) -> str:
        value = self.find_in_selected(selected, "recommendations")
        if isinstance(value, list) and value:
            return "\n".join(f"{idx}. {item}" for idx, item in enumerate(value, 1) if item)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "1. 继续监测事件区域。\n2. 结合现场条件执行人工复核。\n3. 视风险变化升级联动处置。"

    def final_report_field(self, selected: dict[str, Any], key: str, fallback: Any = "") -> str:
        value = self.find_in_selected(selected, key)
        if isinstance(value, list):
            return "；".join(str(item) for item in value if item)
        if isinstance(value, dict):
            return self.format_structured_value(value)
        text = str(value or fallback or "").strip()
        return text or "—"

    def find_in_selected(self, selected: dict[str, Any], key: str) -> Any:
        return self.find_in_value(selected.get("raw_output"), key)

    def find_in_value(self, value: Any, key: str) -> Any:
        if isinstance(value, dict):
            if key in value and value.get(key) not in (None, "", []):
                return value.get(key)
            for child_key in ("inference_result", "final_report", "scene_analysis", "template_data", "docx_context", "output"):
                found = self.find_in_value(value.get(child_key), key)
                if found not in (None, "", []):
                    return found
            for child in value.values():
                found = self.find_in_value(child, key)
                if found not in (None, "", []):
                    return found
        elif isinstance(value, list):
            for item in value:
                found = self.find_in_value(item, key)
                if found not in (None, "", []):
                    return found
        return None

    def timeline_summary(self, timeline: list[SafetyEventTimelineLog]) -> str:
        if not timeline:
            return "暂无处置时间线记录。"
        rows = []
        for row in timeline[-8:]:
            time_text = self.to_local_datetime(row.create_time).strftime("%H:%M:%S") if row.create_time else "--:--:--"
            rows.append(f"{time_text} {row.log_type}/{row.status}：{row.message}")
        return "\n".join(rows)

    def build_conclusion(
        self,
        selected: dict[str, Any],
        workflow_insight: dict[str, Any],
        cloud_note: str,
    ) -> str:
        conclusion = self.final_report_field(selected, "conclusion", "")
        if self.looks_like_model_thinking(conclusion):
            conclusion = "—"
        if conclusion == "—":
            impact = self.final_report_field(selected, "impact_assessment", "")
            monitoring = self.final_report_field(selected, "monitoring_suggestions", "")
            if self.looks_like_model_thinking(impact):
                impact = str(workflow_insight.get("qwen4b_impact_assessment") or "").strip() or "—"
            if self.looks_like_model_thinking(monitoring):
                monitoring = str(workflow_insight.get("qwen4b_monitoring_suggestions") or "").strip() or "—"
            if impact != "—" and monitoring != "—":
                conclusion = f"{impact} 后续应{monitoring.lstrip('建议')}"
            elif impact != "—":
                conclusion = impact
            else:
                event_text = (
                    workflow_insight.get("qwen4b_conclusion")
                    or workflow_insight.get("qwen_summary")
                    or ""
                )
                conclusion = (
                    f"本次事件已完成智能路由分析和证据归档。{self.compact(str(event_text or ''), 180)}"
                    "建议结合现场巡查与连续监测结果确认最终处置等级。"
                )
        if cloud_note:
            return f"{cloud_note}\n{conclusion}"
        return conclusion

    def clean_report_text(self, text: str) -> str:
        text = str(text or "").strip()
        text = text.replace("✅", "")
        text = text.replace("▶", "")
        text = text.replace("—\n", "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text or "未生成详细分析内容。"

    def compact(self, value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text or "—"
        return text[: max(0, limit - 1)].rstrip() + "…"

    @staticmethod
    def safe_filename_part(value: str, limit: int = 50) -> str:
        """清洗事件名，用作报告文件名前缀（去除文件系统非法字符）。"""
        text = re.sub(r'[\\/:*?"<>|\s]+', "_", str(value or "").strip())
        text = text.strip("_. ")
        return text[:limit] or "事件"

    def format_datetime(self, value: Optional[dt.datetime]) -> str:
        if not value:
            return "—"
        return self.to_local_datetime(value).strftime("%Y-%m-%d %H:%M:%S")

    def to_local_datetime(self, value: dt.datetime) -> dt.datetime:
        """Convert DB/application timestamps to local display time.

        The backend container currently runs in UTC, so naïve application
        datetimes in event tables are UTC values. Reports are user-facing and
        should display Beijing time.
        """
        if value.tzinfo is None:
            current_utc_naive = dt.datetime.utcnow()
            if value <= current_utc_naive + dt.timedelta(hours=1):
                value = value.replace(tzinfo=dt.timezone.utc)
            else:
                value = value.replace(tzinfo=LOCAL_TIMEZONE)
        return value.astimezone(LOCAL_TIMEZONE)

    def workflow_insight(
        self,
        workflow_payload: dict[str, Any],
        visual: dict[str, Any],
        selected_text: str,
    ) -> dict[str, Any]:
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
        result = {
            "qwen_summary": screening.get("qwen_summary") or screening.get("summary"),
            "qwen_risk_level": screening.get("qwen_risk_level"),
            "flood_detected": screening.get("flood_detected"),
            "person_present": screening.get("person_present"),
            "boat_present": screening.get("boat_present"),
            "raw_excerpt": self.extract_useful_excerpt(selected_text),
        }
        classify = self.find_node_inference(workflow_payload, "action_classify")
        main_class = classify.get("main_class")
        confidence = self.numeric_value(classify.get("confidence"))
        if confidence is None:
            confidence = self.best_key_frame_confidence(classify.get("key_frames"))
        result.update({
            "specialized_class": main_class,
            "specialized_class_label": self.class_label(main_class),
            "specialized_confidence": confidence,
            "sampled_frames": classify.get("sampled_frames"),
            "classification_report": classify.get("report"),
        })
        reasoning = self.find_node_inference(workflow_payload, "action_reasoning")
        knowledge_sources = self.find_in_value(reasoning, "knowledge_sources")
        result.update({
            "qwen4b_detailed_scene_analysis": self.find_in_value(reasoning, "detailed_scene_analysis"),
            "qwen4b_risk_reasoning": self.find_in_value(reasoning, "risk_reasoning"),
            "qwen4b_impact_assessment": self.find_in_value(reasoning, "impact_assessment"),
            "qwen4b_response_plan": self.find_in_value(reasoning, "response_plan"),
            "qwen4b_monitoring_suggestions": self.find_in_value(reasoning, "monitoring_suggestions"),
            "knowledge_sources": knowledge_sources if isinstance(knowledge_sources, list) else [],
            "knowledge_sources_summary": self.format_knowledge_sources(knowledge_sources),
            "qwen4b_conclusion": (
                self.find_in_value(reasoning, "impact_assessment")
                or self.find_in_value(reasoning, "monitoring_suggestions")
            ),
        })
        return result

    @staticmethod
    def format_knowledge_sources(sources: Any) -> str:
        if not isinstance(sources, list):
            return ""
        lines = []
        seen = set()
        for item in sources:
            if not isinstance(item, dict):
                continue
            title = item.get("document_title") or item.get("filename")
            chunk_id = item.get("chunk_id")
            if not title:
                continue
            key = (title, chunk_id)
            if key in seen:
                continue
            seen.add(key)
            suffix = f"（{chunk_id}）" if chunk_id else ""
            lines.append(f"{len(lines) + 1}. {title}{suffix}")
            if len(lines) >= 5:
                break
        return "\n".join(lines)

    def find_node_inference(self, workflow_payload: dict[str, Any], node_id: str) -> dict[str, Any]:
        execution = workflow_payload.get("execution_result") if isinstance(workflow_payload, dict) else {}
        for row in (execution or {}).get("node_results") or []:
            if not isinstance(row, dict) or row.get("node_id") != node_id:
                continue
            output = row.get("output") if isinstance(row.get("output"), dict) else {}
            inference = output.get("inference_result")
            return inference if isinstance(inference, dict) else output
        return {}

    def numeric_value(self, value: Any) -> Optional[float]:
        try:
            if value in (None, "") or isinstance(value, (dict, list)):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def best_key_frame_confidence(self, key_frames: Any) -> Optional[float]:
        values = []
        if isinstance(key_frames, list):
            for frame in key_frames:
                if isinstance(frame, dict):
                    current = self.numeric_value(frame.get("confidence"))
                    if current is not None:
                        values.append(current)
        return max(values) if values else None

    def class_label(self, value: Any) -> str:
        labels = {
            "flood": "洪水",
            "landslide": "滑坡",
            "mudslide": "泥石流",
            "earthquake": "地震",
            "person": "人员",
            "boat": "船只",
        }
        text = str(value or "").strip()
        return labels.get(text.lower(), text)

    def extract_useful_excerpt(self, text: str) -> str:
        cleaned = self.clean_report_text(text)
        if "三、分析流程规划" in cleaned and not cleaned.rstrip().endswith("。"):
            cleaned = cleaned.split("三、分析流程规划", 1)[0].strip()
        cleaned = re.sub(r"【[^】]+】", "", cleaned).strip()
        return self.compact(cleaned, 520)

    def handling_summary(
        self,
        *,
        instance: SafetyEventInstance,
        event: EventLibrary,
        visual: dict[str, Any],
        selected: dict[str, Any],
        selected_text: str,
        workflow_insight: dict[str, Any],
        image_items: list[dict[str, Any]],
        video_items: list[dict[str, Any]],
    ) -> str:
        detailed = self.selected_detailed_summary(selected)
        if detailed:
            return detailed
        detailed = self.workflow_detailed_summary(workflow_insight)
        if detailed:
            return detailed

        event_name = getattr(event, "event_name", None) or instance.summary or "安全事件"
        qwen_summary = workflow_insight.get("qwen_summary") or "初筛未提供明确文字摘要"
        class_label = workflow_insight.get("specialized_class_label") or "未获得专有模型类别"
        confidence = workflow_insight.get("specialized_confidence")
        confidence_text = f"{confidence * 100:.1f}%" if confidence is not None else "—"
        sampled_frames = workflow_insight.get("sampled_frames") or len(image_items) or "—"
        cloud_text = ""
        if selected.get("cloud_error"):
            cloud_text = f"云端增强节点返回异常（{selected.get('cloud_error')}），本报告采用本地 4B 场景理解与专有模型结果整理生成。"
        else:
            cloud_text = f"报告来源为{selected.get('source_label', '智能分析模型')}。"

        risk_text = RISK_NAMES.get(str(instance.max_risk_level or instance.risk_level or "").upper(), "待确认")
        lines = [
            f"一、事件复核：系统触发{event_name}，当前风险等级为{risk_text}。{cloud_text}",
            f"二、现场证据：摄像头初筛摘要为“{qwen_summary}”。本次关联事件证据视频{len(video_items)}段、关键帧/检测图像{len(image_items)}张。",
            f"三、模型研判：专有模型复核类别为{class_label}，置信度{confidence_text}，采样帧数{sampled_frames}。边缘侧4B和云端增强节点已结合视频证据、事件类型和上下文完成复核。",
            "四、处置建议：保持摄像头连续取证，联动相关传感器和现场巡查记录；如风险指标持续升高或现场出现人员、设施受威胁情况，应升级告警并启动现场处置。",
        ]
        return "\n".join(lines)

    def selected_detailed_summary(self, selected: dict[str, Any]) -> str:
        fields = [
            ("一、现场场景", self.final_report_field(selected, "detailed_scene_analysis", "")),
            ("二、风险研判", self.final_report_field(selected, "risk_reasoning", "")),
            ("三、影响评估", self.final_report_field(selected, "impact_assessment", "")),
            ("四、处置建议", self.final_report_field(selected, "response_plan", "")),
            ("五、持续监测", self.final_report_field(selected, "monitoring_suggestions", "")),
        ]
        lines = [
            f"{label}：{text}"
            for label, text in fields
            if text and text != "—" and not self.looks_like_model_thinking(text)
        ]
        return "\n".join(lines) if len(lines) >= 2 else ""

    @staticmethod
    def workflow_detailed_summary(workflow_insight: dict[str, Any]) -> str:
        fields = [
            ("一、现场场景", workflow_insight.get("qwen4b_detailed_scene_analysis")),
            ("二、风险研判", workflow_insight.get("qwen4b_risk_reasoning")),
            ("三、影响评估", workflow_insight.get("qwen4b_impact_assessment")),
            ("四、处置建议", workflow_insight.get("qwen4b_response_plan")),
            ("五、持续监测", workflow_insight.get("qwen4b_monitoring_suggestions")),
            ("六、知识依据", workflow_insight.get("knowledge_sources_summary")),
        ]
        lines = [f"{label}：{str(text).strip()}" for label, text in fields if str(text or "").strip()]
        return "\n".join(lines) if len(lines) >= 2 else ""

    @staticmethod
    def looks_like_model_thinking(text: str) -> bool:
        value = str(text or "").strip()
        return (
            value.startswith(("好的，我现在", "首先，我", "<think>"))
            or "</think>" in value
            or "需要处理用户" in value[:120]
            or "生成一个关于" in value[:160]
        )

    def looks_truncated(self, text: str) -> bool:
        stripped = str(text or "").strip()
        if not stripped:
            return True
        if stripped.endswith(("专", "“", "：", ":", "，", "、", "-", "—")):
            return True
        return len(stripped) > 80 and not re.search(r"[。！？.!?]$", stripped)


dam_event_report_service = DamEventReportService()
