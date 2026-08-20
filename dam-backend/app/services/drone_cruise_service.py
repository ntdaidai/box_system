"""Reusable drone cruise actions.

The page-level demo used to own the idea of a drone task.  This service makes
the two patrol routes callable by ECA/workflow jobs instead.  A cruise always
has four evidence photos: two outbound and two return photos, stored below a
run-specific MinIO prefix.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.services.minio_service import minio_service


ROUTES: Dict[str, Dict[str, Any]] = {
    "fishing": {
        "name": "禁渔航线",
        "file_id_setting": "DRONE_CRUISE_FISHING_FILE_ID",
        "video_setting": "DRONE_CRUISE_FISHING_VIDEO",
        "waypoints": [
            {"x": 94.9, "y": 24.9, "label": "机场"},
            {"x": 47.4, "y": 58.1, "label": "禁渔点"},
            {"x": 94.9, "y": 24.9, "label": "机场"},
        ],
    },
    "wading": {
        "name": "禁涉水航线",
        "file_id_setting": "DRONE_CRUISE_WADING_FILE_ID",
        "video_setting": "DRONE_CRUISE_WADING_VIDEO",
        "waypoints": [
            {"x": 94.9, "y": 24.9, "label": "机场"},
            {"x": 96.3, "y": 54.3, "label": "禁涉水点"},
            {"x": 94.9, "y": 24.9, "label": "机场"},
        ],
    },
}

PHOTO_MARKS = (
    ("outbound", 1),
    ("outbound", 2),
    ("return", 1),
    ("return", 2),
)
PHOTO_PROGRESS = (0.20, 0.35, 0.65, 0.80)


class DroneCruiseError(RuntimeError):
    """A cruise could not be started or did not produce four photos."""


class DroneCruiseService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def route_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "route_key": key,
                "name": route["name"],
                "photo_count": 4,
                "photo_plan": ["去程第1张", "去程第2张", "回程第1张", "回程第2张"],
                "executor": settings.DRONE_CRUISE_EXECUTOR,
            }
            for key, route in ROUTES.items()
        ]

    async def cruise(
        self,
        route_key: str,
        payload: Dict[str, Any],
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        route = ROUTES.get(route_key)
        if route is None:
            raise DroneCruiseError(f"不支持的无人机航线: {route_key}")

        # A dock cannot safely execute two route actions at the same time.
        async with self._lock:
            run_id = f"{route_key}_{uuid.uuid4().hex}"
            if settings.DRONE_CRUISE_EXECUTOR == "real":
                return await self._cruise_real(run_id, route_key, route, payload, http_client)
            return await self._cruise_simulation(run_id, route_key, route, payload, http_client)

    async def _cruise_simulation(
        self,
        run_id: str,
        route_key: str,
        route: dict[str, Any],
        payload: dict[str, Any],
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        """Run the existing DJI simulation and capture four demo frames."""
        headers = await self._dji_login(http_client)
        duration = float(payload.get("duration_seconds") or settings.DRONE_CRUISE_SIMULATION_DURATION_SECONDS)
        duration = max(1.0, min(duration, settings.DRONE_CRUISE_TIMEOUT_SECONDS))
        response = await http_client.post(
            f"{settings.DJI_CLOUD_API_BASE_URL}/manage/api/v1/simulation/start",
            headers=headers,
            json={
                "job_id": run_id,
                "route_name": route["name"],
                "waypoints": route["waypoints"],
                "duration": int(duration * 1000),
            },
        )
        data = self._dji_data(response, "启动无人机巡航模拟失败")
        simulation_job_id = str(data.get("job_id") or run_id)

        capture_task = asyncio.create_task(
            self._capture_simulation_photos(
                route_key=route_key,
                route=route,
                run_id=run_id,
                video_path=Path(getattr(settings, route["video_setting"])),
                duration=duration,
            )
        )
        try:
            await self._wait_simulation(http_client, headers, simulation_job_id, duration)
            photos = await capture_task
        except Exception:
            capture_task.cancel()
            try:
                await capture_task
            except asyncio.CancelledError:
                pass
            raise

        return {
            "run_id": run_id,
            "route_key": route_key,
            "route_name": route["name"],
            "executor": "simulation",
            "simulation_job_id": simulation_job_id,
            "photo_count": len(photos),
            "photos": photos,
            "image_urls": [item["minio_url"] for item in photos],
        }

    async def _capture_simulation_photos(
        self,
        *,
        route_key: str,
        route: dict[str, Any],
        run_id: str,
        video_path: Path,
        duration: float,
    ) -> list[dict[str, Any]]:
        started = time.monotonic()
        photos: list[dict[str, Any]] = []
        for index, ((phase, phase_index), mark) in enumerate(zip(PHOTO_MARKS, PHOTO_PROGRESS), 1):
            await asyncio.sleep(max(0.0, started + duration * mark - time.monotonic()))
            image = await asyncio.to_thread(self._read_video_frame, video_path, mark)
            object_name = (
                f"{settings.DRONE_CRUISE_OBJECT_PREFIX}/{route_key}/{run_id}/"
                f"{phase}-{phase_index}.jpg"
            )
            minio_url = await asyncio.to_thread(
                minio_service.upload_bytes,
                image,
                object_name=object_name,
                content_type="image/jpeg",
            )
            if not minio_url:
                raise DroneCruiseError(f"第 {index} 张无人机照片上传 MinIO 失败")
            photos.append(
                {
                    "index": index,
                    "phase": phase,
                    "phase_index": phase_index,
                    "object_name": object_name,
                    "minio_url": minio_url,
                }
            )
        return photos

    @staticmethod
    def _read_video_frame(video_path: Path, position: float) -> bytes:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise DroneCruiseError("当前环境未安装 OpenCV，无法生成无人机照片") from exc

        if not video_path.is_file():
            raise DroneCruiseError(f"无人机巡航演示视频不存在: {video_path}")
        capture = cv2.VideoCapture(str(video_path))
        try:
            if not capture.isOpened():
                raise DroneCruiseError(f"无法打开无人机巡航演示视频: {video_path}")
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            target = max(0, min(frame_count - 1, int(frame_count * position)))
            capture.set(cv2.CAP_PROP_POS_FRAMES, target)
            ok, frame = capture.read()
            if not ok:
                raise DroneCruiseError(f"无法从巡航演示视频读取第 {position:.0%} 位置画面")
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            if not ok:
                raise DroneCruiseError("无人机巡航画面 JPEG 编码失败")
            return encoded.tobytes()
        finally:
            capture.release()

    async def _wait_simulation(
        self,
        http_client: httpx.AsyncClient,
        headers: dict[str, str],
        job_id: str,
        duration: float,
    ) -> None:
        started = time.monotonic()
        deadline = started + max(duration + 10, settings.DRONE_CRUISE_TIMEOUT_SECONDS)
        while time.monotonic() < deadline:
            response = await http_client.get(
                f"{settings.DJI_CLOUD_API_BASE_URL}/manage/api/v1/simulation/status/{job_id}",
                headers=headers,
            )
            try:
                data = self._dji_data(response, "查询无人机巡航模拟状态失败")
            except DroneCruiseError as exc:
                # 模拟控制器在完成时会移除内存任务，已观察到运行状态后可视为完成。
                if "任务不存在" in str(exc) and time.monotonic() - started >= duration:
                    return
                raise
            if data.get("status") == "completed":
                return
            await asyncio.sleep(max(0.1, settings.DRONE_CRUISE_POLL_SECONDS))
        raise DroneCruiseError("无人机巡航超时")

    async def _cruise_real(
        self,
        run_id: str,
        route_key: str,
        route: dict[str, Any],
        payload: dict[str, Any],
        http_client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        """Execute a DJI wayline and copy its four uploaded photos to MinIO.

        The configured KMZ must contain the same route as the named action. The
        four payload commands below are also sent at outbound/return progress
        marks, so the action remains reusable even when the KMZ has no photo
        actions of its own.
        """
        headers = await self._dji_login(http_client)
        workspace_id = str(payload.get("workspace_id") or settings.DRONE_CRUISE_WORKSPACE_ID)
        dock_sn = str(payload.get("dock_sn") or settings.DRONE_CRUISE_DOCK_SN)
        file_id = str(payload.get("file_id") or getattr(settings, route["file_id_setting"]))
        payload_index = str(payload.get("payload_index") or settings.DRONE_CRUISE_PAYLOAD_INDEX)
        if not workspace_id or not dock_sn or not file_id:
            raise DroneCruiseError(
                f"{route['name']} 未配置 workspace_id、dock_sn 或 file_id，无法执行真实航线"
            )
        if not payload_index:
            raise DroneCruiseError("未配置无人机相机 payload_index，无法保证拍照")

        response = await http_client.post(
            f"{settings.DJI_CLOUD_API_BASE_URL}/wayline/api/v1/workspaces/{workspace_id}/flight-tasks",
            headers=headers,
            json={
                "name": f"{route['name']}-{run_id}",
                "fileId": file_id,
                "dockSn": dock_sn,
                "waylineType": 0,
                "taskType": 0,
                "rthAltitude": int(payload.get("rth_altitude") or 50),
                "outOfControlAction": 0,
                "minBatteryCapacity": int(payload.get("min_battery_capacity") or 50),
            },
        )
        data = self._dji_data(response, "下发无人机真实航线失败")
        job_id = str(data.get("job_id") or "")
        if not job_id:
            raise DroneCruiseError("DJI 未返回航线任务 ID")

        photo_errors: list[str] = []
        next_photo = 0
        deadline = time.monotonic() + settings.DRONE_CRUISE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            job = await self._get_job(http_client, headers, workspace_id, job_id)
            progress = float(job.get("progress") or 0) / 100
            while next_photo < len(PHOTO_PROGRESS) and progress >= PHOTO_PROGRESS[next_photo]:
                try:
                    await self._take_photo(http_client, headers, dock_sn, payload_index)
                except Exception as exc:  # keep polling so a route can still finish safely
                    photo_errors.append(str(exc))
                next_photo += 1
            status = int(job.get("status") or -1)
            if status in (3, 4, 5):
                if status != 3:
                    raise DroneCruiseError(f"无人机航线执行失败，状态码: {status}")
                break
            await asyncio.sleep(max(0.2, settings.DRONE_CRUISE_POLL_SECONDS))
        else:
            raise DroneCruiseError("无人机真实航线执行超时")

        # If progress notifications were sparse, send any remaining captures
        # before reading the media list. This still yields exactly four files.
        while next_photo < len(PHOTO_PROGRESS):
            try:
                await self._take_photo(http_client, headers, dock_sn, payload_index)
            except Exception as exc:
                photo_errors.append(str(exc))
            next_photo += 1
        if photo_errors:
            logger.warning("无人机拍照指令存在失败: {}", photo_errors)

        media = await self._wait_for_media(http_client, headers, workspace_id, job_id)
        if len(media) < 4:
            raise DroneCruiseError(f"无人机航线只上传了 {len(media)} 张照片，要求 4 张")
        photos = []
        for index, ((phase, phase_index), item) in enumerate(zip(PHOTO_MARKS, media[:4]), 1):
            object_name = (
                f"{settings.DRONE_CRUISE_OBJECT_PREFIX}/{route_key}/{run_id}/"
                f"{phase}-{phase_index}.jpg"
            )
            content = await self._download_media(http_client, headers, workspace_id, item)
            minio_url = await asyncio.to_thread(
                minio_service.upload_bytes,
                content,
                object_name=object_name,
                content_type="image/jpeg",
            )
            if not minio_url:
                raise DroneCruiseError(f"第 {index} 张无人机照片归档 MinIO 失败")
            photos.append({
                "index": index,
                "phase": phase,
                "phase_index": phase_index,
                "object_name": object_name,
                "minio_url": minio_url,
                "source_file_id": item.get("fileId"),
            })
        return {
            "run_id": run_id,
            "route_key": route_key,
            "route_name": route["name"],
            "executor": "real",
            "job_id": job_id,
            "photo_count": len(photos),
            "photos": photos,
            "image_urls": [item["minio_url"] for item in photos],
        }

    async def _take_photo(
        self,
        http_client: httpx.AsyncClient,
        headers: dict[str, str],
        dock_sn: str,
        payload_index: str,
    ) -> None:
        response = await http_client.post(
            f"{settings.DJI_CLOUD_API_BASE_URL}/control/api/v1/devices/{dock_sn}/payload/commands",
            headers=headers,
            json={"cmd": "camera_photo_take", "data": {"payload_index": payload_index}},
        )
        self._dji_data(response, "无人机拍照指令失败")

    async def _get_job(
        self,
        http_client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        response = await http_client.get(
            f"{settings.DJI_CLOUD_API_BASE_URL}/wayline/api/v1/workspaces/{workspace_id}/jobs",
            headers=headers,
            params={"page": 1, "page_size": 100},
        )
        data = self._dji_data(response, "查询无人机航线状态失败")
        records = data.get("records") or data.get("list") or []
        for item in records:
            if str(item.get("jobId") or item.get("job_id")) == job_id:
                return item
        raise DroneCruiseError(f"未找到无人机航线任务: {job_id}")

    async def _wait_for_media(
        self,
        http_client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: str,
        job_id: str,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + settings.DRONE_CRUISE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = await http_client.get(
                f"{settings.DJI_CLOUD_API_BASE_URL}/media/api/v1/files/{workspace_id}/files",
                headers=headers,
                params={"page": 1, "page_size": 100},
            )
            data = self._dji_data(response, "查询无人机照片失败")
            records = data.get("records") or data.get("list") or []
            matched = [
                item for item in records
                if str(item.get("jobId") or item.get("job_id")) == job_id
            ]
            if len(matched) >= 4:
                return matched
            await asyncio.sleep(max(0.2, settings.DRONE_CRUISE_POLL_SECONDS))
        raise DroneCruiseError("等待无人机四张照片上传超时")

    async def _download_media(
        self,
        http_client: httpx.AsyncClient,
        headers: dict[str, str],
        workspace_id: str,
        item: dict[str, Any],
    ) -> bytes:
        file_id = item.get("fileId") or item.get("file_id")
        if not file_id:
            raise DroneCruiseError("无人机照片记录缺少 file_id")
        response = await http_client.get(
            f"{settings.DJI_CLOUD_API_BASE_URL}/media/api/v1/files/{workspace_id}/file/{file_id}/url",
            headers=headers,
            follow_redirects=True,
        )
        if response.status_code >= 400 or not response.content:
            raise DroneCruiseError(f"下载无人机照片失败: {file_id}")
        return response.content

    async def _dji_login(self, http_client: httpx.AsyncClient) -> dict[str, str]:
        response = await http_client.post(
            f"{settings.DJI_CLOUD_API_BASE_URL}/manage/api/v1/login",
            json={
                "username": settings.DJI_CLOUD_API_USERNAME,
                "password": settings.DJI_CLOUD_API_PASSWORD,
                "flag": 1,
            },
        )
        data = self._dji_data(response, "无人机服务认证失败")
        token = data.get("access_token") or data.get("token")
        if not token:
            raise DroneCruiseError("无人机服务未返回认证 token")
        return {"x-auth-token": str(token)}

    @staticmethod
    def _dji_data(response: httpx.Response, message: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise DroneCruiseError(f"{message}: HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise DroneCruiseError(f"{message}: 响应不是 JSON") from exc
        code = body.get("code")
        if code not in (None, 0, 200):
            raise DroneCruiseError(str(body.get("message") or message))
        data = body.get("data")
        if isinstance(data, dict):
            return data
        if data is None:
            return {}
        return {"value": data}


drone_cruise_service = DroneCruiseService()
