"""Generate event handling reports from DAM workflow LLM results."""

from __future__ import annotations

import datetime as dt
import re
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse
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
    "evidence_caption",
    "conclusion",
}
RISK_NAMES = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}
STATUS_NAMES = {
    "PENDING": "待处理",
    "PROCESSING": "处理中",
    "COMPLETED": "已完成",
    "FALSE_ALARM": "误报",
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
        filename = f"事件处置报告_{instance.instance_no}.docx"
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
            message=f"事件处置报告已生成：{selected['source_label']}",
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
            for field in TEMPLATE_FIELDS:
                current = candidate.get(field)
                if current in (None, "", []):
                    continue
                if isinstance(current, (dict, list)):
                    current = self.format_structured_value(current)
                overrides[field] = current
        return overrides

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
        timeline_summary = self.timeline_summary(timeline)
        evidence_image_path = self.download_first_image(image_items)

        source_label = self.source_label(instance, source, selected)
        cloud_note = ""
        if selected.get("source") == "qwen4b" and selected.get("cloud_error"):
            cloud_note = f"云端增强分析返回异常：{selected['cloud_error']}；本报告已采用本地 4B 分析结果生成。"

        context = {
            "report_date": report_date,
            "event_name": getattr(event, "event_name", None) or instance.summary or "安全事件",
            "instance_no": instance.instance_no,
            "risk_label": RISK_NAMES.get(str(instance.max_risk_level or instance.risk_level or "").upper(), "低风险"),
            "result_label": self.result_label(instance),
            "occur_time": self.format_datetime(instance.started_at),
            "completed_at": self.format_datetime(instance.resolved_at) if instance.resolved_at else "—",
            "source_label": source_label,
            "location": self.location(source, camera, visual),
            "evidence_count": len(image_items),
            "summary": self.event_summary(instance, event, source, visual, workflow_insight),
            "key_observation": self.key_observation(workflow_payload, visual, selected_text, workflow_insight),
            "source_summary": self.source_summary(image_items, video_items, selected),
            "handling_source": selected["source_label"],
            "timeline_count": len(timeline),
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
            "conclusion": self.build_conclusion(workflow_insight, cloud_note),
        }
        context.update(self.extract_template_overrides(selected.get("raw_output")))
        context["report_date"] = report_date
        context["evidence_image"] = evidence_image_path
        if selected.get("source") == "qwen4b":
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
            context["conclusion"] = self.build_conclusion(workflow_insight, cloud_note)
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
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "key_frames"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "images"))
        self.extend_media_items(items, self.find_nested_values(workflow_payload, "image_urls"))
        for row in evidence:
            if str(row.evidence_type or "").upper() in {"IMAGE", "CAMERA_SNAPSHOT", "DRONE_IMAGE", "STAFF_IMAGE"}:
                items.append({"url": row.file_url, "caption": row.description or "事件图像"})
        return self.unique_media_items(items)

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

    def read_minio_or_http_bytes(self, value: str) -> Optional[bytes]:
        bucket, object_name = self.parse_minio_reference(value)
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
        if qwen_summary:
            return f"{camera_name}触发{event_name}，初筛摘要：{qwen_summary}。"
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
        if screening.get("summary"):
            parts.append(str(screening.get("summary")))
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
        if image_items:
            caption = image_items[0].get("caption") or "事件关键帧"
            return str(caption)
        if video_items:
            return "事件证据视频已归档，报告中未嵌入视频内容。"
        return "暂无图像证据"

    def timeline_summary(self, timeline: list[SafetyEventTimelineLog]) -> str:
        if not timeline:
            return "暂无处置时间线记录。"
        rows = []
        for row in timeline[-8:]:
            time_text = self.to_local_datetime(row.create_time).strftime("%H:%M:%S") if row.create_time else "--:--:--"
            rows.append(f"{time_text} {row.log_type}/{row.status}：{row.message}")
        return "\n".join(rows)

    def build_conclusion(self, selected_text: str, cloud_note: str) -> str:
        if isinstance(selected_text, dict):
            insight = selected_text
            conclusion = insight.get("conclusion") or "当前事件已完成智能分析，建议结合现场水位、降雨和坝体状态持续跟踪。"
        else:
            sentences = re.split(r"(?<=[。！？])\s*", str(selected_text or "").strip())
            useful = [sentence.strip() for sentence in sentences if sentence.strip() and not sentence.strip().endswith("专")]
            conclusion = useful[-1] if useful else "当前事件已完成智能分析，建议结合现场水位、降雨和坝体状态持续跟踪。"
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
        return result

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
        if selected.get("source") == "qwen35b" and not self.looks_truncated(selected_text):
            return self.clean_report_text(selected_text)

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
            f"三、模型研判：专有分类模型复核类别为{class_label}，置信度{confidence_text}，采样帧数{sampled_frames}。边缘侧4B分析认为现场水流状态异常，需按洪水风险持续跟踪。",
            "四、处置建议：保持摄像头连续取证，联动水位、雨量和坝体安全监测数据；对现场临水区域进行人工复核；如水位继续上涨或出现人员靠近，应升级告警并启动现场处置。",
        ]
        return "\n".join(lines)

    def looks_truncated(self, text: str) -> bool:
        stripped = str(text or "").strip()
        if not stripped:
            return True
        if stripped.endswith(("专", "“", "：", ":", "，", "、", "-", "—")):
            return True
        return len(stripped) > 80 and not re.search(r"[。！？.!?]$", stripped)


dam_event_report_service = DamEventReportService()
