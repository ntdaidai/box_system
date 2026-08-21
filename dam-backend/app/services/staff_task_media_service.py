"""现场人工处置照片的统一 MinIO 存储入口。"""

from __future__ import annotations

import datetime as dt
import asyncio
import mimetypes
import random
import uuid
from pathlib import Path
from typing import Any

from app.services.minio_service import minio_service


class StaffTaskMediaService:
    """把工作人员上传的现场照片保存到 MinIO。"""

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/octet-stream",
    }
    _prepared_demo_pictures: dict[str, list[dict[str, str]]] = {}

    @staticmethod
    def _extension(filename: str | None, content_type: str | None) -> str:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = {
                "image/png": ".png",
                "image/webp": ".webp",
            }.get(content_type, ".jpg")
        return suffix

    @classmethod
    async def save_upload(
        cls,
        event_id: str,
        upload: Any,
        *,
        folder: str = "field-images",
        phase: str | None = None,
    ) -> str:
        content_type = getattr(upload, "content_type", None)
        if content_type not in cls.allowed_types:
            raise ValueError("现场照片仅支持 JPG、PNG、WEBP")

        content = await upload.read()
        if not content:
            raise ValueError("现场照片不能为空")
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("现场照片不能超过 10MB")

        suffix = cls._extension(getattr(upload, "filename", None), content_type)
        normalized_phase = str(phase or "").strip().lower()
        if normalized_phase not in {"before", "after"}:
            normalized_phase = ""
        filename = f"{normalized_phase + '-' if normalized_phase else ''}{uuid.uuid4().hex}{suffix}"
        captured_day = dt.datetime.now().strftime("%Y-%m-%d")
        object_name = f"safety-events/{folder.strip('/')}/{captured_day}/{event_id}/{filename}"
        normalized_type = content_type if content_type in {"image/jpeg", "image/png", "image/webp"} else {
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")
        url = minio_service.upload_bytes(
            content,
            object_name=object_name,
            content_type=normalized_type,
        )
        if url:
            return url
        raise ValueError("现场照片上传 MinIO 失败，请检查 MinIO 服务")

    async def prepare_demo_pictures(
        self,
        *,
        source_root: str | Path | None = None,
    ) -> dict[str, list[dict[str, str]]]:
        """预置演示图片到 MinIO；已存在的稳定对象不会重复上传。"""
        from app.core.config import settings

        if not minio_service.client:
            raise ValueError("MinIO 未连接，无法预置人工处置演示图片")

        root = Path(source_root or settings.STAFF_TASK_DEMO_PICTURE_ROOT)
        event_sources = {
            "PERSON_WADING": "nowater",
            "NIGHT_FISHING": "nofishing",
            # 现有洪水现场图作为自然灾害/极端天气处置的演示素材；真实任务
            # 仍由工作人员回传现场照片。
            "NATURAL_DISASTER_EVENT": "flood",
            "EXTREME_WEATHER_EVENT": "flood",
        }
        prepared: dict[str, list[dict[str, str]]] = {}
        for event_type, folder_name in event_sources.items():
            picture_dir = root / folder_name
            pictures = sorted(
                path
                for path in picture_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ) if picture_dir.is_dir() else []
            required_count = 4 if event_type in {"NATURAL_DISASTER_EVENT", "EXTREME_WEATHER_EVENT"} else 2
            if len(pictures) < required_count:
                raise ValueError(f"人工处置演示图片不足，需要 {required_count} 张：{picture_dir}")

            event_slug = event_type.lower().replace("_", "-")
            result: list[dict[str, str]] = []
            for index, picture_path in enumerate(pictures[:required_count], 1):
                suffix = picture_path.suffix.lower() or ".jpg"
                # 洪水演示要预置四张候选图，每次任务再从中抽取两张；其余
                # 事件仍保留稳定的 before/after 对象名以兼容已有数据。
                phase = ("before", "after")[index - 1] if required_count == 2 else f"picture-{index}"
                object_name = (
                    f"{settings.STAFF_TASK_DEMO_OBJECT_PREFIX}/"
                    f"{event_slug}/{phase}{suffix}"
                )
                if not minio_service.object_exists(object_name):
                    image = await asyncio.to_thread(picture_path.read_bytes)
                    content_type = mimetypes.guess_type(picture_path.name)[0] or "image/jpeg"
                    url = await asyncio.to_thread(
                        minio_service.upload_bytes,
                        image,
                        object_name=object_name,
                        content_type=content_type,
                    )
                    if not url:
                        raise ValueError(f"人工处置演示图片预置到 MinIO 失败：{picture_path.name}")
                else:
                    url = minio_service.object_url(object_name)
                result.append({
                    "phase": phase,
                    "object_name": object_name,
                    "minio_url": url,
                    "source_file_name": picture_path.name,
                })
            prepared[event_type] = result

        self._prepared_demo_pictures = prepared
        return prepared

    def get_prepared_demo_pictures(self, event_type: str) -> list[dict[str, str]]:
        """只读取已预置的 MinIO 地址，不读取本地文件，也不执行上传。"""
        canonical_type = str(event_type or "").strip().upper()
        pictures = self._prepared_demo_pictures.get(canonical_type)
        if not pictures or len(pictures) < 2:
            raise ValueError("人工处置演示图片尚未预置到 MinIO，请先执行演示图片初始化")
        selected = random.sample(pictures, 2) if canonical_type in {
            "NATURAL_DISASTER_EVENT", "EXTREME_WEATHER_EVENT",
        } else pictures[:2]
        return [
            {**item, "phase": phase}
            for phase, item in zip(("before", "after"), selected)
        ]


staff_task_media_service = StaffTaskMediaService()
