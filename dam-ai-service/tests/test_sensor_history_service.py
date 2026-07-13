import csv
import sys
import tempfile
import types
import unittest
from pathlib import Path


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.services.sensor_history_service import SensorHistoryService


class FakeIoTDB:
    def __init__(self):
        self.rollup_points = []
        self.raw_points = []
        self.inserted = []
        self.deleted = []

    def query_points(self, path, start_ms, end_ms):
        if path.startswith("root.dam.rollup_"):
            if self.inserted:
                return [
                    {"timestamp": item["timestamp_ms"] / 1000.0, "data": item["data"]}
                    for item in self.inserted
                ]
            return list(self.rollup_points)
        return list(self.raw_points)

    def insert_record_at_path(self, path, timestamp_ms, data):
        self.inserted.append({"path": path, "timestamp_ms": timestamp_ms, "data": data})
        return True

    def delete_points_older_than(self, path, cutoff_ms):
        self.deleted.append({"path": path, "cutoff_ms": cutoff_ms})
        return True


class SensorHistoryServiceTest(unittest.TestCase):
    def test_query_history_reads_rollup_first(self):
        fake = FakeIoTDB()
        fake.rollup_points = [
            {"timestamp": 1782952860.0 + index * 60, "data": {"temperature": 21.5}}
            for index in range(60)
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "1h", now_ms=1782956911000)

        self.assertEqual(payload["source"], "rollup")
        self.assertEqual(payload["rollup_level"], "1m")
        self.assertEqual(payload["sample_interval"], 60)
        self.assertEqual(payload["history"], fake.rollup_points)

    def test_query_history_rebuilds_rollup_from_raw_when_rollup_empty(self):
        fake = FakeIoTDB()
        fake.raw_points = [
            {"timestamp": 1782952810.0, "data": {"temperature": 20, "humidity": 50}},
            {"timestamp": 1782952830.0, "data": {"temperature": 22, "humidity": 54}},
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "1h", now_ms=1782956911000)

        self.assertEqual(payload["source"], "rollup_rebuilt")
        self.assertEqual(payload["history"][0]["data"]["temperature"], 21.0)
        self.assertEqual(payload["history"][0]["data"]["humidity"], 52.0)

    def test_query_history_rebuilds_incomplete_rollup_window(self):
        fake = FakeIoTDB()
        fake.rollup_points = [
            {"timestamp": 1782952860.0, "data": {"temperature": 99}},
        ]
        fake.raw_points = [
            {"timestamp": 1782952810.0, "data": {"temperature": 20}},
            {"timestamp": 1782952830.0, "data": {"temperature": 22}},
            {"timestamp": 1782952870.0, "data": {"temperature": 24}},
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "1h", now_ms=1782956911000)

        self.assertEqual(payload["source"], "rollup_rebuilt")
        self.assertEqual(len(fake.inserted), 2)
        self.assertEqual(payload["history"][0]["data"]["temperature"], 21.0)
        self.assertEqual(payload["history"][1]["data"]["temperature"], 24.0)

    def test_build_and_write_rollup_reads_raw_and_writes_rollup_path(self):
        fake = FakeIoTDB()
        fake.raw_points = [
            {"timestamp": 1782952810.0, "data": {"wind_angle": 350, "wind_speed_ms": 2}},
            {"timestamp": 1782952830.0, "data": {"wind_angle": 10, "wind_speed_ms": 4}},
        ]
        service = SensorHistoryService(iotdb=fake)
        window = {"start_ms": 1782952800000, "end_ms": 1782952860000, "sample_ms": 60000, "rollup_level": "1m"}

        written = service.build_and_write_rollup("wind", "1m", window)

        self.assertEqual(written, 1)
        self.assertEqual(fake.inserted[0]["path"], "root.dam.rollup_1m.wind_001")
        self.assertEqual(fake.inserted[0]["timestamp_ms"], 1782952860000)
        self.assertAlmostEqual(fake.inserted[0]["data"]["wind_angle"], 0.0, places=6)
        self.assertEqual(fake.inserted[0]["data"]["wind_direction"], "北")

    def test_export_raw_archive_writes_daily_csv(self):
        fake = FakeIoTDB()
        fake.raw_points = [
            {"timestamp": 1782952810.0, "data": {"temperature": 20, "humidity": 50}},
            {"timestamp": 1782952830.0, "data": {"humidity": 54}},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SensorHistoryService(iotdb=fake, archive_base_dir=tmpdir)
            output = service.export_raw_archive("temp_humidity", "2026-07-02", 1782952800000, 1782956400000)

            self.assertEqual(output, str(Path(tmpdir) / "2026-07-02" / "temp_001.csv"))
            with open(output, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["timestamp"], "1782952810.0")
            self.assertEqual(rows[0]["temperature"], "20")
            self.assertEqual(rows[1]["humidity"], "54")

    def test_enforce_retention_cleans_raw_and_rollup_paths(self):
        fake = FakeIoTDB()
        service = SensorHistoryService(iotdb=fake)

        result = service.enforce_retention(now_ms=1782956911000)

        self.assertEqual(result["raw"], 4)
        self.assertEqual(result["rollup"], {"1m": 4, "10m": 4, "30m": 4, "1h": 4, "1d": 4})
        self.assertIn(
            {"path": "root.dam.sensor.temp_001", "cutoff_ms": 1781747311000},
            fake.deleted,
        )
        self.assertIn(
            {"path": "root.dam.rollup_30m.rain_001", "cutoff_ms": 1775180911000},
            fake.deleted,
        )


if __name__ == "__main__":
    unittest.main()
