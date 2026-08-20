import asyncio
import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services.drone_cruise_service import DroneCruiseService
from app.services.minio_service import minio_service


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        return self._body


class FakeHttpClient:
    async def post(self, url, **kwargs):
        if url.endswith("/login"):
            return FakeResponse({"code": 0, "data": {"access_token": "test-token"}})
        if url.endswith("/simulation/start"):
            return FakeResponse({"code": 0, "data": {"job_id": "sim-test"}})
        raise AssertionError(f"unexpected POST {url}")

    async def get(self, url, **kwargs):
        if "/simulation/status/" in url:
            return FakeResponse({"code": 0, "data": {"status": "completed"}})
        raise AssertionError(f"unexpected GET {url}")


class DroneCruiseServiceTests(unittest.TestCase):
    def test_catalog_contains_two_routes_and_four_photo_plan(self):
        catalog = DroneCruiseService().route_catalog()
        self.assertEqual([item["route_key"] for item in catalog], ["fishing", "wading"])
        self.assertTrue(all(item["photo_count"] == 4 for item in catalog))

    def test_simulation_returns_two_outbound_and_two_return_minio_urls(self):
        service = DroneCruiseService()
        uploaded = []

        def upload(data, *, object_name, content_type):
            uploaded.append((data, object_name, content_type))
            return f"http://minio.test/dam/{object_name}"

        with patch.object(settings, "DRONE_CRUISE_EXECUTOR", "simulation"), \
             patch.object(settings, "DRONE_CRUISE_SIMULATION_DURATION_SECONDS", 1.0), \
             patch.object(settings, "DRONE_CRUISE_TIMEOUT_SECONDS", 10.0), \
             patch.object(settings, "DRONE_CRUISE_POLL_SECONDS", 0.01), \
             patch.object(settings, "DRONE_CRUISE_FISHING_VIDEO", "/tmp/demo-fishing.mp4"), \
             patch.object(service, "_read_video_frame", return_value=b"jpeg"), \
             patch.object(minio_service, "upload_bytes", side_effect=upload):
            result = asyncio.run(service.cruise("fishing", {}, FakeHttpClient()))

        self.assertEqual(result["photo_count"], 4)
        self.assertEqual([item["phase"] for item in result["photos"]], [
            "outbound", "outbound", "return", "return"
        ])
        self.assertEqual(result["image_urls"], [item["minio_url"] for item in result["photos"]])
        self.assertEqual(len(uploaded), 4)
        self.assertTrue(all(name.startswith("drone-cruises/fishing/") for _, name, _ in uploaded))


if __name__ == "__main__":
    unittest.main()
