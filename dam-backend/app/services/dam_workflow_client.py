"""Client for the DAM intelligent workflow routing service."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventInstance


IMAGE_KEYS = (
    "images",
    "image_paths",
    "image_urls",
    "qwen_image_urls",
    "minio_urls",
    "minio_paths",
    "object_names",
    "object_keys",
    "image",
    "image_path",
    "image_url",
    "minio_url",
    "minio_path",
    "object_name",
    "object_key",
    "bucket_object",
    "snapshot_path",
    "snapshot_url",
    "file_url",
)

VIDEO_KEYS = (
    "videos",
    "video_paths",
    "video_urls",
    "video",
    "video_path",
    "video_url",
    "source_video_url",
    "minio_video_url",
)

MEDIA_KEYS = (
    "media",
    "media_objects",
    "evidence",
    "evidence_files",
)

DEFAULT_ACTOR_NAME = "自然灾害分析专家"
ACTOR_RULES = (
    ("自然灾害分析专家", ("自然灾害", "泥石流", "滑坡", "洪水", "地震", "landslide", "debris", "flood", "earthquake", "natural_disaster")),
    ("人员行为分析专家", ("人员", "入侵", "滩涂", "游玩", "电鱼", "捕鱼", "船只", "行为", "intrusion", "person", "people", "fishing", "behavior")),
    ("极端天气分析专家", ("极端天气", "台风", "暴雨", "高温", "低温", "风速", "雨量", "气象", "typhoon", "rainstorm", "weather", "temperature")),
)


class DamWorkflowClient:
    """Thin HTTP wrapper around dam-workflow's `/api/dam/analyze` endpoint."""

    def __init__(
        self,
        base_url: str = settings.DAM_WORKFLOW_BASE_URL,
        timeout: float = settings.DAM_WORKFLOW_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def analyze_event(
        self,
        *,
        event: EventLibrary,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = self.build_payload(
            event=event,
            instance=instance,
            sensor_data=sensor_data,
        )
        url = f"{self.base_url}/api/dam/analyze"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
        if not result.get("success"):
            raise RuntimeError(str(result.get("error") or "DAM 工作流生成失败"))
        return result

    def build_payload(
        self,
        *,
        event: EventLibrary,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        images = self._extract_images(sensor_data)
        videos = self._extract_values(sensor_data, VIDEO_KEYS)
        media_objects = self._extract_media_objects(sensor_data, prefer_videos=bool(videos))
        actor_name = self._resolve_actor_name(event, instance, sensor_data)
        if videos:
            images = []
        elif not images:
            images = [settings.DAM_WORKFLOW_PLACEHOLDER_IMAGE]
        return {
            "prompt": self._build_prompt(event, instance, sensor_data),
            "images": images,
            "videos": videos,
            "media_objects": media_objects,
            "actor_name": actor_name,
            "sensor_data": {
                **dict(sensor_data or {}),
                "videos": videos,
                "media_objects": media_objects,
                "actor_name": actor_name,
                "event_instance_no": instance.instance_no,
                "event_id": event.id,
                "event_name": event.event_name,
                "event_code": getattr(event, "event_code", None),
                "event_category": event.event_category,
                "risk_level": event.risk_level,
            },
        }

    @staticmethod
    def _build_prompt(
        event: EventLibrary,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> str:
        sensor_json = json.dumps(
            DamWorkflowClient._compact_sensor_data(sensor_data or {}),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        media_hint = "现场证据以事件视频为主；初筛图片仅作为触发证据。" if (
            sensor_data or {}
        ).get("source_video_url") else "现场证据以图片/视频引用为准。"
        return (
            "你是一名库坝应急巡查智能感知系统中的工作流规划智能体。\n"
            f"当前触发事件：{event.event_name}。\n"
            f"事件编码：{getattr(event, 'event_code', None) or '未配置'}。\n"
            f"事件分类：{event.event_category or '未配置'}。\n"
            f"风险等级：{event.risk_level or '未配置'}。\n"
            f"统一事件实例：{instance.instance_no}。\n"
            f"{media_hint}\n"
            "事件类型已经由系统确定，请规划最合理的视觉分析流程。\n"
            "原则：专有模型优先，小模型优先，大模型负责理解与推理，避免重复分析。\n"
            f"当前传感器数据：\n{sensor_json}"
        )

    @staticmethod
    def _resolve_actor_name(
        event: EventLibrary,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> str:
        data = dict(sensor_data or {})
        for key in ("actor_name", "actor", "actor_role", "role_prompt_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        text = " ".join(
            str(value or "")
            for value in (
                event.event_name,
                event.event_category,
                getattr(event, "event_code", None),
                instance.event_category,
                instance.summary,
                data.get("event_type"),
                data.get("event_name"),
                data.get("summary"),
                data.get("description"),
            )
        )
        for actor_name, keywords in ACTOR_RULES:
            if any(keyword in text for keyword in keywords):
                return actor_name
        return DEFAULT_ACTOR_NAME

    @staticmethod
    def _extract_images(sensor_data: Dict[str, Any]) -> List[str]:
        return DamWorkflowClient._extract_values(sensor_data, IMAGE_KEYS)

    @staticmethod
    def _extract_values(sensor_data: Dict[str, Any], keys: tuple[str, ...]) -> List[str]:
        values: List[str] = []
        data = dict(sensor_data or {})
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value:
                values.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item:
                        values.append(item)
                    elif isinstance(item, dict):
                        ref = DamWorkflowClient._media_ref(item)
                        if ref:
                            values.append(ref)
            elif isinstance(value, dict):
                ref = DamWorkflowClient._media_ref(value)
                if ref:
                    values.append(ref)
        return list(dict.fromkeys(values))

    @staticmethod
    def _extract_media_objects(
        sensor_data: Dict[str, Any],
        *,
        prefer_videos: bool = False,
    ) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        data = dict(sensor_data or {})
        for key in MEDIA_KEYS:
            value = data.get(key)
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, dict):
                    objects.append(dict(item))
                elif isinstance(item, str) and item:
                    objects.append({"path": item})
        for video in DamWorkflowClient._extract_values(sensor_data, VIDEO_KEYS):
            objects.append({"type": "video", "path": video})
        if prefer_videos:
            return DamWorkflowClient._dedupe_media_objects(
                [item for item in objects if str(item.get("type") or "").lower() == "video"]
            )
        for image in DamWorkflowClient._extract_values(sensor_data, IMAGE_KEYS):
            if image != settings.DAM_WORKFLOW_PLACEHOLDER_IMAGE:
                objects.append({"type": "image", "path": image})
        return DamWorkflowClient._dedupe_media_objects(objects)

    @staticmethod
    def _dedupe_media_objects(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in objects:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    @staticmethod
    def _compact_sensor_data(sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        keep_keys = {
            "event_code",
            "event_name",
            "event_category",
            "risk_level",
            "event_instance_no",
            "qwen_summary",
            "qwen_risk_level",
            "flood_detected",
            "flood_confidence",
            "mudslide_detected",
            "mudslide_confidence",
            "landslide_detected",
            "landslide_confidence",
            "earthquake_detected",
            "earthquake_confidence",
            "person_present",
            "person_confidence",
            "boat_present",
            "boat_confidence",
        }
        compact = {key: value for key, value in sensor_data.items() if key in keep_keys}
        video_values = DamWorkflowClient._extract_values(sensor_data, VIDEO_KEYS)
        if video_values:
            compact["video_evidence_count"] = len(video_values)
            compact["video_evidence"] = "事件证据视频已入库"
        image_urls = sensor_data.get("qwen_image_urls")
        if isinstance(image_urls, list) and image_urls:
            compact["qwen_image_count"] = len(image_urls)
            compact["qwen_image_ref"] = "关键帧已入库，工作流以事件视频为主"
        media_objects = sensor_data.get("media_objects")
        if isinstance(media_objects, list) and media_objects:
            compact["video_media_object_count"] = sum(
                1 for item in media_objects
                if isinstance(item, dict) and str(item.get("type") or "").lower() == "video"
            )
        return compact

    @staticmethod
    def _media_ref(value: Dict[str, Any]) -> Optional[str]:
        bucket = value.get("bucket")
        object_name = value.get("object_name") or value.get("object_key")
        if bucket and object_name:
            return f"{bucket}/{object_name}"
        for key in ("path", "url", "minio_url", "file_url", "object_name", "object_key"):
            if value.get(key):
                return str(value[key])
        return None


dam_workflow_client = DamWorkflowClient()
