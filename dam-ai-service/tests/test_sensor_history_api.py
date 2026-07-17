import asyncio
import concurrent.futures
import os
import sys
import types
import unittest


os.environ.setdefault("JWT_SECRET", "unit-test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "unit-test-admin-password")


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))


class FakeAPIRouter:
    def get(self, *_args, **_kwargs):
        return lambda func: func


class FakeBaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FakeCollector:
    def get_latest_data(self, *_args, **_kwargs):
        return {}

    def get_history_data(self, *_args, **_kwargs):
        return []

    def get_all_devices_status(self):
        return {}

    def get_history_queue_status(self):
        return {"pending_count": 0}


sys.modules.setdefault(
    "fastapi",
    types.SimpleNamespace(
        APIRouter=lambda *args, **kwargs: FakeAPIRouter(),
        HTTPException=FakeHTTPException,
        Depends=lambda *args, **kwargs: None,
        Query=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault("fastapi.responses", types.SimpleNamespace(StreamingResponse=object))
sys.modules.setdefault("pydantic", types.SimpleNamespace(BaseModel=FakeBaseModel))
sys.modules.setdefault("app.core.cache", types.SimpleNamespace(cached=lambda *args, **kwargs: (lambda func: func)))
sys.modules.setdefault("app.core.security", types.SimpleNamespace(require_auth=None, get_current_user=None, decode_token=None))
sys.modules.setdefault("app.models.user", types.SimpleNamespace(User=object))
sys.modules.setdefault("app.core.database", types.SimpleNamespace(get_db=lambda: None))
sys.modules.setdefault("app.services.sensor_collector", types.SimpleNamespace(sensor_collector=FakeCollector()))

from app.api import sensor as sensor_api


class FakeHistoryService:
    def query_temp_humidity_trends(self, view, year, month):
        return {
            "device_name": "temp_humidity",
            "view": view,
            "year": year,
            "month": month,
            "aggregation": "daily_extrema" if view == "calendar" else "30m_average",
            "history": [],
            "point_count": 0,
        }

    def query_rain_calendar(self, year, month):
        return {
            "device_name": "rain",
            "view": "calendar",
            "year": year,
            "month": month,
            "aggregation": "daily_rainfall",
            "history": [],
            "point_count": 0,
        }

    def query_history(self, device_name, range_key):
        if device_name == "vibration":
            return {
                "device_name": device_name,
                "source": "rollup",
                "rollup_level": "30m",
                "window": {"start": 1.0, "end": 2.0},
                "sample_interval": 1800,
                "max_point_count": 48,
                "history": [{
                    "timestamp": 2.0,
                    "data": {
                        "加速度幅值X": 3,
                        "加速度幅值Y": 4,
                        "频率X": 2,
                        "频率Y": 4,
                        "温度": 26.5,
                    },
                }],
                "point_count": 1,
            }
        return {
            "device_name": device_name,
            "source": "rollup",
            "rollup_level": "1d",
            "window": {"start": 1.0, "end": 2.0},
            "sample_interval": 86400,
            "max_point_count": 180,
            "history": [{
                "timestamp": 2.0,
                "data": {
                    "temperature": 21.0,
                    "加速度幅值X": 0.03,
                    "加速度幅值Y": 0.04,
                    "频率X": 3.0,
                    "频率Y": 5.0,
                    "温度": 27.0,
                },
            }],
            "point_count": 1,
        }


class BrokenHistoryService:
    def query_history(self, *_args, **_kwargs):
        from app.services.iotdb_service import IoTDBUnavailableError
        raise IoTDBUnavailableError("transport unavailable")


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


class SensorHistoryApiTest(unittest.TestCase):
    def setUp(self):
        self.original_executor = sensor_api._io_executor
        sensor_api._io_executor = InlineExecutor()

    def tearDown(self):
        sensor_api._io_executor = self.original_executor

    def test_history_route_returns_service_payload(self):
        original = sensor_api.get_sensor_history_service
        sensor_api.get_sensor_history_service = lambda: FakeHistoryService()
        try:
            response = asyncio.run(sensor_api.get_sensor_history("temp_humidity", range="6mo"))
        finally:
            sensor_api.get_sensor_history_service = original

        self.assertEqual(response.code, 200)
        self.assertEqual(response.data["source"], "rollup")
        self.assertEqual(response.data["rollup_level"], "1d")
        self.assertEqual(response.data["sample_interval"], 86400)

    def test_temp_humidity_trends_route_supports_calendar_selection(self):
        original = sensor_api.get_sensor_history_service
        sensor_api.get_sensor_history_service = lambda: FakeHistoryService()
        try:
            response = asyncio.run(
                sensor_api.get_temp_humidity_trends(view="calendar", year=2026, month=7)
            )
        finally:
            sensor_api.get_sensor_history_service = original

        self.assertEqual(response.code, 200)
        self.assertEqual(response.data["view"], "calendar")
        self.assertEqual(response.data["year"], 2026)
        self.assertEqual(response.data["month"], 7)
        self.assertEqual(response.data["aggregation"], "daily_extrema")

    def test_rain_trends_route_supports_calendar_selection(self):
        original = sensor_api.get_sensor_history_service
        sensor_api.get_sensor_history_service = lambda: FakeHistoryService()
        try:
            response = asyncio.run(sensor_api.get_rain_trends(year=2026, month=7))
        finally:
            sensor_api.get_sensor_history_service = original

        self.assertEqual(response.code, 200)
        self.assertEqual(response.data["device_name"], "rain")
        self.assertEqual(response.data["view"], "calendar")
        self.assertEqual(response.data["year"], 2026)
        self.assertEqual(response.data["month"], 7)
        self.assertEqual(response.data["aggregation"], "daily_rainfall")

    def test_history_route_returns_503_when_iotdb_is_unavailable(self):
        original = sensor_api.get_sensor_history_service
        sensor_api.get_sensor_history_service = lambda: BrokenHistoryService()
        try:
            # dai: Full-suite discovery may import the real FastAPI module in an
            # earlier test; assert the exception class actually bound by sensor.py.
            with self.assertRaises(sensor_api.HTTPException) as raised:
                asyncio.run(sensor_api.get_sensor_history("temp_humidity", range="1h"))
        finally:
            sensor_api.get_sensor_history_service = original

        self.assertEqual(raised.exception.status_code, 503)

    def test_vibration_trends_delegates_to_unified_history_service(self):
        original = sensor_api.get_sensor_history_service
        sensor_api.get_sensor_history_service = lambda: FakeHistoryService()
        try:
            response = asyncio.run(sensor_api.get_vibration_trends(range="24h"))
        finally:
            sensor_api.get_sensor_history_service = original

        self.assertEqual(response.code, 200)
        self.assertEqual(response.data["range"], "1d")
        self.assertEqual(response.data["source"], "rollup")
        self.assertEqual(response.data["rollup_level"], "30m")
        self.assertEqual(response.data["point_count"], 1)
        self.assertEqual(response.data["max_point_count"], 48)
        self.assertEqual(response.data["coverage_ratio"], 0.0208)
        self.assertEqual(response.data["window"], {"start": 1.0, "end": 2.0})
        self.assertEqual(response.data["history"][0]["rms"], 5.0)
        self.assertEqual(response.data["history"][0]["freq"], 3.0)
        self.assertEqual(response.data["history"][0]["temperature"], 26.5)

    def test_vibration_history_prefers_persisted_rms(self):
        point = sensor_api._vibration_history_point({
            "timestamp": 10.0,
            "data": {
                "total_rms": 0.1234,
                "加速度幅值X": 3,
                "加速度幅值Y": 4,
            },
        })

        self.assertEqual(point["rms"], 0.1234)

if __name__ == "__main__":
    unittest.main()
