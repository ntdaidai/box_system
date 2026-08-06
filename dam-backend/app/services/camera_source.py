"""Helpers for building camera source URLs from device rows."""

from __future__ import annotations

from urllib.parse import quote

from app.models.camera import Camera


def camera_rtsp_path(brand: str) -> str:
    if brand == "hikvision":
        return "Streaming/Channels/101"
    return "cam/realmonitor?channel=1&subtype=0"


def camera_source_from_row(row: Camera) -> str:
    path = row.rtsp_path or camera_rtsp_path(row.brand)
    auth = ""
    if row.username:
        auth = quote(row.username, safe="")
        if row.password:
            auth = f"{auth}:{quote(row.password, safe='')}"
        auth = f"{auth}@"
    return f"rtsp://{auth}{row.ip_address}:{row.rtsp_port}/{path}"
