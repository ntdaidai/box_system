# dai
"""HTTP-level camera workflow tests using an in-process synthetic video source."""

import asyncio
import base64
import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "camera-tests-jwt-secret-that-is-long-enough")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "camera-tests-admin-password")

from app.api import camera as camera_api  # noqa: E402
from app.core.security import require_auth  # noqa: E402
from app.services.camera_stream import CameraManager  # noqa: E402
from app.services.stream_ticket import StreamTicketStore  # noqa: E402


def wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class SyntheticCapture:
    """Small deterministic source that exercises the same capture thread as RTSP."""

    def __init__(self, source):
        self.source = source
        self.opened = True
        self.index = 0

    def isOpened(self):
        return self.opened

    def read(self):
        if not self.opened:
            return False, None
        time.sleep(0.01)
        self.index += 1
        frame = np.full((72, 128, 3), self.index % 255, dtype=np.uint8)
        return True, frame

    def release(self):
        self.opened = False


class SyntheticCameraManager(CameraManager):
    def add_camera(self, camera_id, source, name="", **_kwargs):
        return super().add_camera(
            camera_id,
            source,
            name,
            capture_factory=SyntheticCapture,
            reconnect_interval=0.02,
        )


class SyntheticDetector:
    loaded = True
    task_type = "detect"

    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def get_status(self):
        return {
            "loaded": True,
            "model_path": "/models/test/best.pt",
            "classes": {0: {"name": "boat", "name_cn": "船只"}},
        }

    def analyze_and_render(self, image, conf=0.5, iou=0.45):
        with self.lock:
            self.calls += 1
        drawn = image.copy()
        cv2.rectangle(drawn, (10, 10), (60, 55), (0, 255, 0), 2)
        return {
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "detections": [
                {
                    "class_id": 0,
                    "class_name": "boat",
                    "class_name_cn": "船只",
                    "confidence": 0.93,
                    "bbox": {
                        "x1": 10.0,
                        "y1": 10.0,
                        "x2": 60.0,
                        "y2": 55.0,
                    },
                }
            ],
            "count": 1,
            "process_time": 0.005,
        }, drawn

    @staticmethod
    def image_to_bytes(image, quality=80):
        ok, buffer = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        )
        if not ok:
            raise RuntimeError("jpeg encode failed")
        return buffer.tobytes()


class SyntheticClassifier:
    loaded = True
    task_type = "classify"

    def get_status(self):
        return {
            "task_type": self.task_type,
            "loaded": True,
            "model_path": "/models/test/classify.engine",
            "classes": {0: {"name": "flood", "name_cn": "洪水"}},
        }

    def analyze_and_render(self, image, conf=0.5, iou=0.45):
        del conf, iou
        prediction = {
            "class_id": 0,
            "class_name": "flood",
            "class_name_cn": "洪水",
            "confidence": 0.94,
        }
        return {
            "task_type": self.task_type,
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "prediction": prediction,
            "classifications": [prediction],
            "process_time": 0.004,
        }, image


class SyntheticRegistry:
    def __init__(self, detector, classifier):
        self.models = {"detect": detector, "classify": classifier}

    def get(self, task_type):
        return self.models.get(task_type)

    def get_status(self):
        statuses = {key: model.get_status() for key, model in self.models.items()}
        return {
            "loaded": True,
            "available_tasks": list(statuses),
            "models": statuses,
        }


class ImmediateVideoService:
    def __init__(self):
        self.submitted_path = None

    def submit(self, file_path, filename, owner_id, **_kwargs):
        self.submitted_path = file_path
        self.filename = filename
        self.owner_id = owner_id
        self.payload = Path(file_path).read_bytes()
        Path(file_path).unlink(missing_ok=True)
        return {
            "job_id": "a" * 32,
            "filename": filename,
            "state": "queued",
            "progress": 0,
        }

    def get_status(self, job_id, owner_id):
        if job_id != "a" * 32 or owner_id != self.owner_id:
            return None
        return {
            "job_id": job_id,
            "filename": self.filename,
            "state": "completed",
            "progress": 100,
            "processed_samples": 1,
        }

    def get_result(self, job_id, owner_id):
        if not self.get_status(job_id, owner_id):
            return None
        return {
            "state": "completed",
            "duration_s": 1.0,
            "processed_samples": 1,
            "total_occurrences": 0,
            "class_summary": [],
            "timeline": [],
        }

    def cancel(self, job_id, owner_id):
        return bool(self.get_status(job_id, owner_id))


class ConnectedRequest:
    async def is_disconnected(self):
        return False


class FakeWebRtcResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeWebRtcClient:
    def __init__(self):
        self.requests = []

    async def request(self, method, url, params=None, json=None):
        self.requests.append(
            {"method": method, "url": url, "params": params or {}, "json": json}
        )
        if url.endswith("/api/getIceServers"):
            return FakeWebRtcResponse({"iceServers": [], "iceTransportPolicy": "all"})
        if url.endswith("/api/call"):
            return FakeWebRtcResponse(
                {"type": "answer", "sdp": "v=0\r\ns=webrtc-answer\r\n"}
            )
        if url.endswith("/api/addIceCandidate"):
            return FakeWebRtcResponse(True)
        if url.endswith("/api/getIceCandidate"):
            return FakeWebRtcResponse(
                [
                    {
                        "candidate": "candidate:1 1 UDP 1 192.0.2.10 50000 typ host",
                        "sdpMid": "0",
                        "sdpMLineIndex": 0,
                    }
                ]
            )
        if url.endswith("/api/hangup"):
            return FakeWebRtcResponse(True)
        return FakeWebRtcResponse({}, status_code=404)


class CameraHttpFlowTests(unittest.TestCase):
    def setUp(self):
        self.manager = SyntheticCameraManager()
        self.detector = SyntheticDetector()
        self.classifier = SyntheticClassifier()
        self.registry = SyntheticRegistry(self.detector, self.classifier)
        self.ticket_store = StreamTicketStore(ttl_seconds=60)
        self.video_service = ImmediateVideoService()
        app = FastAPI()
        self.webrtc_client = FakeWebRtcClient()
        app.state.http_client = self.webrtc_client
        app.include_router(camera_api.router, prefix="/api/v1/camera")
        app.dependency_overrides[require_auth] = lambda: object()
        self.client = TestClient(app)
        self.patches = [
            patch.object(camera_api, "camera_manager", self.manager),
            patch.object(camera_api, "vision_model_registry", self.registry),
            patch.object(camera_api, "stream_ticket_store", self.ticket_store),
            patch.object(camera_api, "video_detection_service", self.video_service),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        self.client.close()
        self.manager.stop_all()
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_complete_camera_and_detection_workflow(self):
        added = self.client.post(
            "/api/v1/camera/add",
            json={
                "camera_id": "camera_http",
                "name": "HTTP 测试摄像头",
                "rtsp_url": "rtsp://camera.example.test/live",
            },
        )
        self.assertEqual(added.status_code, 200)
        camera = self.manager.get_camera("camera_http")
        self.assertTrue(wait_until(lambda: camera.get_status()["connected"]))

        listed = self.client.get("/api/v1/camera/list")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"]["total"], 1)
        self.assertNotIn("rtsp_url", listed.text)

        model = self.client.get("/api/v1/camera/model/status")
        self.assertEqual(model.status_code, 200)
        self.assertTrue(model.json()["data"]["loaded"])

        enabled = self.client.post(
            "/api/v1/camera/camera_http/detection/toggle",
            json={"enabled": True, "confidence": 0.4, "target_fps": 10},
        )
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json()["data"]["detection_enabled"])
        self.assertTrue(
            wait_until(
                lambda: self.client.get(
                    "/api/v1/camera/camera_http/detections/latest"
                ).json()["data"].get("count")
                == 1
            )
        )
        latest = self.client.get(
            "/api/v1/camera/camera_http/detections/latest"
        ).json()["data"]
        self.assertEqual(latest["detections"][0]["class_name_cn"], "船只")
        self.assertLess(latest["latency_ms"], 1000)

        ticket = self.client.post(
            "/api/v1/camera/stream/camera_http/ticket",
            json={"detected": False},
        )
        self.assertEqual(ticket.status_code, 200)
        stream_data = ticket.json()["data"]
        self.assertIn("ticket=", stream_data["stream_url"])
        self.assertNotIn("camera.example.test", stream_data["stream_url"])
        invalid_stream = self.client.get(
            "/api/v1/camera/stream/camera_http", params={"ticket": "x" * 24}
        )
        self.assertEqual(invalid_stream.status_code, 401)

        fake_minio_module = types.ModuleType("app.services.minio_service")
        fake_minio_module.minio_service = types.SimpleNamespace(
            upload_image=lambda *_args, **_kwargs: "mock://snapshot.jpg"
        )
        with patch.dict(sys.modules, {"app.services.minio_service": fake_minio_module}):
            snapshot = self.client.post(
                "/api/v1/camera/camera_http/snapshot", params={"confidence": 0.4}
            )
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["data"]["count"], 1)
        self.assertTrue(snapshot.json()["data"]["image_base64"])
        self.assertEqual(snapshot.json()["data"]["minio_url"], "mock://snapshot.jpg")

        disabled = self.client.post(
            "/api/v1/camera/camera_http/detection/toggle",
            json={"enabled": False},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["data"]["detection_enabled"])

        removed = self.client.delete("/api/v1/camera/camera_http")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(
            self.client.get("/api/v1/camera/list").json()["data"]["total"], 0
        )

    def test_uploaded_image_detection_and_input_validation(self):
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        payload = base64.b64encode(encoded.tobytes()).decode("ascii")
        fake_minio_module = types.ModuleType("app.services.minio_service")
        fake_minio_module.minio_service = types.SimpleNamespace(
            upload_image=lambda *_args, **_kwargs: "mock://result.jpg"
        )
        with patch.dict(sys.modules, {"app.services.minio_service": fake_minio_module}):
            detected = self.client.post(
                "/api/v1/camera/detect/image",
                json={"image": payload, "confidence": 0.5},
            )
        self.assertEqual(detected.status_code, 200)
        body = detected.json()["data"]
        self.assertEqual(body["count"], 1)
        self.assertTrue(body["result_image_base64"])
        self.assertEqual(body["minio_url"], "mock://result.jpg")

        with patch.dict(sys.modules, {"app.services.minio_service": fake_minio_module}):
            classified = self.client.post(
                "/api/v1/camera/detect/image",
                json={
                    "image": payload,
                    "confidence": 0.5,
                    "task_type": "classify",
                },
            )
        self.assertEqual(classified.status_code, 200)
        classification = classified.json()["data"]
        self.assertEqual(classification["task_type"], "classify")
        self.assertEqual(classification["prediction"]["class_name_cn"], "洪水")
        self.assertNotIn("bbox", classification["prediction"])
        self.assertTrue(classification["result_image_base64"])

        malformed = self.client.post(
            "/api/v1/camera/detect/image",
            json={"image": "not-base64!", "confidence": 0.5},
        )
        self.assertEqual(malformed.status_code, 400)

    def test_authenticated_webrtc_signaling_hides_rtsp_credentials(self):
        added = self.client.post(
            "/api/v1/camera/add",
            json={
                "camera_id": "camera_webrtc",
                "name": "WebRTC 测试",
                "source": "rtsp://admin:secret@camera.example.test/live",
            },
        )
        self.assertEqual(added.status_code, 200)

        ice = self.client.get("/api/v1/camera/camera_webrtc/webrtc/ice")
        self.assertEqual(ice.status_code, 200)
        self.assertEqual(ice.json()["data"]["iceServers"], [])

        peer_id = "dam-test-peer-1234"
        session = self.client.post(
            "/api/v1/camera/camera_webrtc/webrtc/session",
            json={
                "peer_id": peer_id,
                "offer": {
                    "type": "offer",
                    "sdp": "v=0\r\ns=browser-offer\r\nt=0 0\r\n",
                },
            },
        )
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.json()["data"]["answer"]["type"], "answer")
        self.assertNotIn("secret", session.text)
        call = next(
            request
            for request in self.webrtc_client.requests
            if request["url"].endswith("/api/call")
        )
        self.assertEqual(
            call["params"]["url"],
            "rtsp://admin:secret@camera.example.test/live",
        )

        candidate = self.client.post(
            f"/api/v1/camera/camera_webrtc/webrtc/session/{peer_id}/candidate",
            json={
                "candidate": "candidate:2 1 UDP 1 192.0.2.20 51000 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            },
        )
        self.assertEqual(candidate.status_code, 200)
        self.assertTrue(candidate.json()["data"]["accepted"])

        remote = self.client.get(
            f"/api/v1/camera/camera_webrtc/webrtc/session/{peer_id}/candidates"
        )
        self.assertEqual(remote.status_code, 200)
        self.assertEqual(len(remote.json()["data"]["candidates"]), 1)

        closed = self.client.delete(
            f"/api/v1/camera/camera_webrtc/webrtc/session/{peer_id}"
        )
        self.assertEqual(closed.status_code, 200)
        self.assertTrue(closed.json()["data"]["closed"])

    def test_mjpeg_generator_emits_a_decodable_frame(self):
        self.manager.add_camera(
            "camera_stream",
            "rtsp://camera.example.test/stream",
            "流测试",
        )
        camera = self.manager.get_camera("camera_stream")
        self.assertTrue(wait_until(lambda: camera.get_status()["connected"]))

        async def read_one_chunk():
            response = await camera_api._mjpeg_response(
                ConnectedRequest(), camera, detected=False
            )
            iterator = response.body_iterator
            try:
                return await asyncio.wait_for(iterator.__anext__(), timeout=1.0)
            finally:
                await iterator.aclose()

        chunk = asyncio.run(read_one_chunk())
        self.assertIn(b"Content-Type: image/jpeg", chunk)
        self.assertIn(b"\xff\xd8", chunk)
        self.assertTrue(chunk.endswith(b"\r\n"))

    def test_video_upload_job_status_result_and_cleanup_contract(self):
        created = self.client.post(
            "/api/v1/camera/detect/video",
            params={"confidence": 0.5, "sample_fps": 2},
            files={"file": ("sample.mp4", b"synthetic-video", "video/mp4")},
        )
        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()["data"]["state"], "queued")
        self.assertEqual(self.video_service.payload, b"synthetic-video")

        job_id = created.json()["data"]["job_id"]
        status = self.client.get(f"/api/v1/camera/detect/video/{job_id}/status")
        result = self.client.get(f"/api/v1/camera/detect/video/{job_id}/result")
        removed = self.client.delete(f"/api/v1/camera/detect/video/{job_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["data"]["progress"], 100)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["data"]["processed_samples"], 1)
        self.assertEqual(removed.status_code, 200)

        invalid = self.client.post(
            "/api/v1/camera/detect/video",
            files={"file": ("notes.txt", b"not-video", "text/plain")},
        )
        self.assertEqual(invalid.status_code, 400)


if __name__ == "__main__":
    unittest.main()
