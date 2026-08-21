"""机器狗路线测试服务。

机器狗当前只有一条固定路线。第一版使用本地 dogtake 图片模拟路线完成后的
四张拍摄结果，并沿用无人机动作的 MinIO 归档方式。
"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.minio_service import minio_service


MACHINE_DOG_ROUTE = {
    "route_key": "all",
    "name": "9号检测区域巡检路线",
    "photo_plan": ["巡检点 1", "巡检点 2", "巡检点 3", "巡检点 4"],
}
MACHINE_DOG_DEVICE_ID = "dog-01"
MACHINE_DOG_ROUTE_ALIASES = {
    "all": MACHINE_DOG_ROUTE["route_key"],
    "机器狗全路线": MACHINE_DOG_ROUTE["route_key"],
    "9号检测区域巡检路线": MACHINE_DOG_ROUTE["route_key"],
    "巡检路线": MACHINE_DOG_ROUTE["route_key"],
    # 流程编辑器早期曾展示两条逻辑路线；保留兼容，但统一执行唯一的 all 路线。
    "route-a": MACHINE_DOG_ROUTE["route_key"],
    "route-b": MACHINE_DOG_ROUTE["route_key"],
    "岸线由西向东巡检": MACHINE_DOG_ROUTE["route_key"],
    "岸线由东向西巡检": MACHINE_DOG_ROUTE["route_key"],
}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class MachineDogCruiseError(RuntimeError):
    """机器狗路线测试失败。"""


def normalize_machine_dog_route(route_id: str | None) -> str:
    """将历史配置统一为当前唯一可执行的机器狗路线。"""
    value = str(route_id or "").strip().lower()
    route_key = MACHINE_DOG_ROUTE_ALIASES.get(value)
    if not route_key:
        raise MachineDogCruiseError("机器狗巡检 route_id 仅支持 all（9号检测区域巡检路线）")
    return route_key


class MachineDogCruiseService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def route_catalog(self) -> list[dict[str, Any]]:
        return [{
            "route_key": MACHINE_DOG_ROUTE["route_key"],
            "name": MACHINE_DOG_ROUTE["name"],
            "photo_count": len(MACHINE_DOG_ROUTE["photo_plan"]),
            "photo_plan": MACHINE_DOG_ROUTE["photo_plan"],
            "executor": "simulation",
        }]

    async def cruise(self) -> dict[str, Any]:
        """执行 9 号检测区域固定巡检路线并返回四张归档照片。"""
        async with self._lock:
            run_id = f"all_{uuid.uuid4().hex}"
            pictures = self._select_pictures()
            photos = await self._upload_pictures(run_id, pictures)
            return {
                "run_id": run_id,
                "route_key": MACHINE_DOG_ROUTE["route_key"],
                "route_name": MACHINE_DOG_ROUTE["name"],
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
    async def _upload_pictures(run_id: str, pictures: list[Path]) -> list[dict[str, Any]]:
        photos: list[dict[str, Any]] = []
        for index, picture_path in enumerate(pictures, 1):
            image = await asyncio.to_thread(picture_path.read_bytes)
            suffix = picture_path.suffix.lower() or ".png"
            content_type = mimetypes.guess_type(picture_path.name)[0] or "image/png"
            object_name = (
                f"{settings.MACHINE_DOG_CRUISE_OBJECT_PREFIX}/all/{run_id}/"
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
                "point": MACHINE_DOG_ROUTE["photo_plan"][index - 1],
                "object_name": object_name,
                "minio_url": minio_url,
                "source_file_name": picture_path.name,
            })
        return photos


machine_dog_cruise_service = MachineDogCruiseService()
