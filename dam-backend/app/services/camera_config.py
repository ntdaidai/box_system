# dai
"""Parse one-or-many camera environment settings into validated entries."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.parse import urlparse


CAMERA_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
LOCAL_VIDEO_PATTERN = re.compile(r"^/dev/video\d+$")


def normalize_camera_source(value: Any) -> str:
    """Allow a Hikvision RTSP URL or an explicitly scoped Jetson camera device."""
    source = str(value or "").strip()
    parsed = urlparse(source)
    if parsed.scheme in {"rtsp", "rtsps"} and parsed.hostname:
        return source
    if LOCAL_VIDEO_PATTERN.fullmatch(source):
        return source
    raise ValueError("视频源必须是 RTSP/RTSPS 或 /dev/videoN")


def camera_source_type(source: str) -> str:
    if LOCAL_VIDEO_PATTERN.fullmatch(source):
        return "usb"
    return "rtsp"


def _validated_entry(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    camera_id = str(raw.get("camera_id", "")).strip()
    source = raw.get("source") or raw.get("rtsp_url")
    name = str(raw.get("name") or camera_id).strip()
    auto_start = raw.get("auto_start", True)

    if not CAMERA_ID_PATTERN.fullmatch(camera_id):
        raise ValueError(f"第 {index + 1} 个摄像头 camera_id 格式无效")
    try:
        source = normalize_camera_source(source)
    except ValueError as exc:
        raise ValueError(f"摄像头 {camera_id} 的视频源无效: {exc}") from exc
    if not isinstance(auto_start, bool):
        raise ValueError(f"摄像头 {camera_id} 的 auto_start 必须为布尔值")
    return {
        "camera_id": camera_id,
        "source": source,
        "name": name[:100],
        "auto_start": auto_start,
    }


def load_camera_configs(settings: Any) -> List[Dict[str, Any]]:
    """Prefer CAMERA_CONFIGS_JSON; fall back to the legacy single URL."""
    raw_json = str(getattr(settings, "CAMERA_CONFIGS_JSON", "") or "").strip()
    if raw_json:
        try:
            decoded = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"CAMERA_CONFIGS_JSON 不是合法 JSON: {exc.msg}") from exc
        if not isinstance(decoded, list):
            raise ValueError("CAMERA_CONFIGS_JSON 必须是摄像头对象数组")
        configs = [_validated_entry(item, index) for index, item in enumerate(decoded) if isinstance(item, dict)]
        if len(configs) != len(decoded):
            raise ValueError("CAMERA_CONFIGS_JSON 的每一项都必须是对象")
    else:
        source = str(getattr(settings, "CAMERA_SOURCE", "") or "").strip()
        source = source or str(getattr(settings, "CAMERA_RTSP_URL", "") or "").strip()
        if not source:
            return []
        configs = [
            _validated_entry(
                {
                    "camera_id": getattr(settings, "CAMERA_ID", "camera_001"),
                    "source": source,
                    "name": getattr(settings, "CAMERA_NAME", "主摄像头"),
                    "auto_start": getattr(settings, "CAMERA_AUTO_START", True),
                },
                0,
            )
        ]

    camera_ids = [config["camera_id"] for config in configs]
    if len(camera_ids) != len(set(camera_ids)):
        raise ValueError("CAMERA_CONFIGS_JSON 中存在重复的 camera_id")
    return configs
