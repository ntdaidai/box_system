"""机器狗路线测试服务。

提供同一岸线的东西双向巡检。首版仍使用本地 dogtake 图片模拟取证，
并沿用无人机动作的 MinIO 归档方式。
"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.minio_service import minio_service


MACHINE_DOG_ROUTES = {
    "route-a": {
        "route_key": "route-a",
        "name": "岸线由西向东巡检",
        "photo_plan": ["巡检点 1", "巡检点 2", "巡检点 3", "巡检点 4"],
    },
    "route-b": {
        "route_key": "route-b",
        "name": "岸线由东向西巡检",
        "photo_plan": ["巡检点 4", "巡检点 3", "巡检点 2", "巡检点 1"],
    },
}
MACHINE_DOG_DEVICE_ID = "dog-01"
MACHINE_DOG_ROUTE_ALIASES = {
    "all": "route-a",
    "机器狗全路线": "route-a",
    "9号检测区域巡检路线": "route-a",
    "巡检路线": "route-a",
    "route-a": "route-a",
    "route-b": "route-b",
    "岸线由西向东巡检": "route-a",
    "岸线由东向西巡检": "route-b",
}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class MachineDogCruiseError(RuntimeError):
    """机器狗路线测试失败。"""


def normalize_machine_dog_route(route_id: str | None) -> str:
    """将历史配置和展示名称规范为可执行的双向路线标识。"""
    value = str(route_id or "").strip().lower()
    route_key = MACHINE_DOG_ROUTE_ALIASES.get(value)
    if not route_key:
        raise MachineDogCruiseError("机器狗巡检路线仅支持岸线由西向东或由东向西巡检")
    return route_key


class MachineDogCruiseService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def route_catalog(self) -> list[dict[str, Any]]:
        return [{
            "route_key": route["route_key"],
            "name": route["name"],
            "photo_count": len(route["photo_plan"]),
            "photo_plan": route["photo_plan"],
            "executor": "simulation",
        } for route in MACHINE_DOG_ROUTES.values()]

    async def cruise(self, route_id: str | None = None) -> dict[str, Any]:
        """执行指定方向的岸线巡检并返回四张归档照片。"""
        route_key = normalize_machine_dog_route(route_id)
        route = MACHINE_DOG_ROUTES[route_key]
        async with self._lock:
            run_id = f"{route_key}_{uuid.uuid4().hex}"
            pictures = self._select_pictures()
            photos = await self._upload_pictures(route, run_id, pictures)
            return {
                "run_id": run_id,
                "route_key": route["route_key"],
                "route_name": route["name"],
                "executor": "simulation",
                "photo_count": len(photos),
                "photos": photos,
                "image_urls": [item["minio_url"] for item in photos],
            }

    @staticmethod
    def _select_pictures() -> list[Path]:
        picture_dir = Path(settings.MACHINE_DOG_CRUISE_PICTURE_ROOT) / "dogtake"
        if not picture_dir.is_dir():
            raise MachineDogCruiseError(f"机器狗照片目录不存在: {picture_dir}")

        pictures = sorted(
            path for path in picture_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
        if len(pictures) < 4:
            raise MachineDogCruiseError(f"机器狗照片不足，需要至少 4 张: {picture_dir}")
        return pictures[:4]

    @staticmethod
    async def _upload_pictures(route: dict[str, Any], run_id: str, pictures: list[Path]) -> list[dict[str, Any]]:
        photos: list[dict[str, Any]] = []
        for index, picture_path in enumerate(pictures, 1):
            image = await asyncio.to_thread(picture_path.read_bytes)
            suffix = picture_path.suffix.lower() or ".png"
            content_type = mimetypes.guess_type(picture_path.name)[0] or "image/png"
            object_name = (
                f"{settings.MACHINE_DOG_CRUISE_OBJECT_PREFIX}/{route['route_key']}/{run_id}/"
                f"point-{index}{suffix}"
            )
            minio_url = await asyncio.to_thread(
                minio_service.upload_bytes,
                image,
                object_name=object_name,
                content_type=content_type,
            )
            if not minio_url:
                raise MachineDogCruiseError(f"第 {index} 张机器狗照片上传 MinIO 失败")
            photos.append({
                "index": index,
                "point": route["photo_plan"][index - 1],
                "object_name": object_name,
                "minio_url": minio_url,
                "source_file_name": picture_path.name,
            })
        return photos


machine_dog_cruise_service = MachineDogCruiseService()
