import csv
from datetime import date, datetime
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.services.sensor_history_service import (
    SensorHistoryService,
    aggregate_points_to_window,
    merge_history_points,
)


class FakeIoTDB:
    def __init__(self):
        self.rollup_points = []
        self.raw_points = []
        self.points_by_path = {}
        self.inserted = []
        self.deleted = []

    def query_points(self, path, start_ms, end_ms):
        if path in self.points_by_path:
            return list(self.points_by_path[path])
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
    def test_merge_history_points_keeps_existing_and_overrides_same_bucket(self):
        existing = [
            {"timestamp": 100.0, "data": {"temperature": 10}},
            {"timestamp": 200.0, "data": {"temperature": 20}},
        ]
        rebuilt = [
            {"timestamp": 200.0, "data": {"temperature": 21}},
            {"timestamp": 300.0, "data": {"temperature": 30}},
        ]

        merged = merge_history_points(existing, rebuilt)

        self.assertEqual([point["timestamp"] for point in merged], [100.0, 200.0, 300.0])
        self.assertEqual(merged[1]["data"]["temperature"], 21)

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

    def test_recent_24h_excludes_inclusive_start_boundary(self):
        fake = FakeIoTDB()
        now_ms = 1782957600000
        start_seconds = (now_ms - 24 * 60 * 60 * 1000) / 1000.0
        fake.rollup_points = [
            {
                "timestamp": start_seconds + index * 30 * 60,
                "data": {"temperature": 20 + index / 10, "humidity": 50},
            }
            for index in range(49)
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_temp_humidity_trends(
            "recent24h",
            now_ms=now_ms,
        )

        self.assertEqual(payload["point_count"], 48)
        self.assertEqual(len(payload["history"]), 48)
        self.assertGreater(payload["history"][0]["timestamp"], payload["window"]["start"])
        self.assertEqual(payload["coverage_ratio"], 1.0)

    def test_wind_recent_24h_excludes_inclusive_start_boundary(self):
        fake = FakeIoTDB()
        now_ms = 1782957600000
        start_seconds = (now_ms - 24 * 60 * 60 * 1000) / 1000.0
        fake.rollup_points = [
            {
                "timestamp": start_seconds + index * 30 * 60,
                "data": {
                    "wind_speed_kmh": 8 + index / 10,
                    "wind_level": 2,
                    "wind_direction": "东",
                },
            }
            for index in range(49)
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_wind_trends("recent24h", now_ms=now_ms)

        self.assertEqual(payload["aggregation"], "30m_average")
        self.assertEqual(payload["point_count"], 48)
        self.assertEqual(len(payload["history"]), 48)
        self.assertGreater(payload["history"][0]["timestamp"], payload["window"]["start"])
        self.assertEqual(payload["coverage_ratio"], 1.0)

    def test_query_history_rebuilds_rollup_from_raw_when_rollup_empty(self):
        fake = FakeIoTDB()
        fake.raw_points = [
            {"timestamp": 1782953290.0, "data": {"temperature": 20, "humidity": 50}},
            {"timestamp": 1782953310.0, "data": {"temperature": 22, "humidity": 54}},
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "1h", now_ms=1782956911000)

        self.assertEqual(payload["source"], "rollup_rebuilt")
        self.assertEqual(payload["history"][0]["data"]["temperature"], 21.0)
        self.assertEqual(payload["history"][0]["data"]["humidity"], 52.0)

    def test_query_history_rebuilds_incomplete_rollup_window(self):
        fake = FakeIoTDB()
        fake.rollup_points = [
            {"timestamp": 1782953340.0, "data": {"temperature": 99}},
        ]
        fake.raw_points = [
            {"timestamp": 1782953290.0, "data": {"temperature": 20}},
            {"timestamp": 1782953310.0, "data": {"temperature": 22}},
            {"timestamp": 1782953350.0, "data": {"temperature": 24}},
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "1h", now_ms=1782956911000)

        self.assertEqual(payload["source"], "rollup_rebuilt")
        self.assertEqual(len(fake.inserted), 2)
        self.assertEqual(payload["history"][0]["data"]["temperature"], 21.0)
        self.assertEqual(payload["history"][1]["data"]["temperature"], 24.0)

    def test_daily_rollup_contains_true_temperature_humidity_extrema(self):
        timezone = ZoneInfo("Asia/Shanghai")
        start = datetime(2026, 7, 1, tzinfo=timezone)
        start_ms = int(start.timestamp() * 1000)
        window = {
            "start_ms": start_ms,
            "end_ms": start_ms + 24 * 60 * 60 * 1000,
            "sample_ms": 24 * 60 * 60 * 1000,
            "rollup_level": "1d",
        }
        points = [
            {"timestamp": start.timestamp() + 60, "data": {"temperature": 20, "humidity": 48}},
            {"timestamp": start.timestamp() + 120, "data": {"temperature": 27, "humidity": 66}},
        ]

        result = aggregate_points_to_window(points, "temp_humidity", window)

        self.assertEqual(result[0]["data"]["temperature"], 23.5)
        self.assertEqual(result[0]["data"]["temperature_min"], 20.0)
        self.assertEqual(result[0]["data"]["temperature_max"], 27.0)
        self.assertEqual(result[0]["data"]["humidity_min"], 48.0)
        self.assertEqual(result[0]["data"]["humidity_max"], 66.0)

    def test_daily_rollup_contains_final_daily_rainfall(self):
        timezone = ZoneInfo("Asia/Shanghai")
        start = datetime(2026, 7, 1, tzinfo=timezone)
        start_ms = int(start.timestamp() * 1000)
        window = {
            "start_ms": start_ms,
            "end_ms": start_ms + 24 * 60 * 60 * 1000,
            "sample_ms": 24 * 60 * 60 * 1000,
            "rollup_level": "1d",
        }
        points = [
            {"timestamp": start.timestamp() + 60, "data": {"today_rain": 0.0}},
            {"timestamp": start.timestamp() + 120, "data": {"today_rain": 8.4}},
            {"timestamp": start.timestamp() + 180, "data": {"today_rain": 15.2}},
        ]

        result = aggregate_points_to_window(points, "rain", window)

        self.assertEqual(result[0]["data"]["daily_rain"], 15.2)
        self.assertEqual(result[0]["data"]["daily_rain_sample_count"], 3)

    def test_calendar_query_returns_daily_extrema_with_calendar_dates(self):
        fake = FakeIoTDB()
        timezone = ZoneInfo("Asia/Shanghai")
        first_bucket_end = datetime(2026, 7, 2, tzinfo=timezone).timestamp()
        second_bucket_end = datetime(2026, 7, 3, tzinfo=timezone).timestamp()
        fake.points_by_path["root.dam.rollup_1d.temp_001"] = [
            {
                "timestamp": first_bucket_end,
                "data": {
                    "temperature_min": 20,
                    "temperature_max": 28,
                    "humidity_min": 45,
                    "humidity_max": 70,
                },
            },
            {
                "timestamp": second_bucket_end,
                "data": {
                    "temperature_min": 21,
                    "temperature_max": 29,
                    "humidity_min": 46,
                    "humidity_max": 72,
                },
            },
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_temp_humidity_calendar(2026, 7)

        self.assertEqual(payload["aggregation"], "daily_extrema")
        self.assertEqual(payload["max_point_count"], 31)
        self.assertEqual(payload["point_count"], 2)
        self.assertEqual(payload["metric_point_counts"], {"temperature": 2, "humidity": 2})
        self.assertEqual(len(payload["history"]), 31)
        self.assertEqual([item["date"] for item in payload["history"][:2]], ["2026-07-01", "2026-07-02"])
        self.assertEqual(payload["history"][1]["data"]["temperature_max"], 29)
        self.assertEqual(payload["history"][2]["data"], {})

    def test_wind_calendar_returns_daily_average_speed_level_and_direction(self):
        fake = FakeIoTDB()
        timezone = ZoneInfo("Asia/Shanghai")
        first_bucket_end = datetime(2026, 7, 2, tzinfo=timezone).timestamp()
        second_bucket_end = datetime(2026, 7, 3, tzinfo=timezone).timestamp()
        fake.points_by_path["root.dam.rollup_1d.wind_001"] = [
            {
                "timestamp": first_bucket_end,
                "data": {
                    "wind_speed_ms": 3.0,
                    "wind_speed_kmh": 10.8,
                    "wind_level": 2.6,
                    "wind_angle": 270.0,
                    "wind_dir_code": 12,
                    "wind_direction": "西",
                },
            },
            {
                "timestamp": second_bucket_end,
                "data": {
                    "wind_speed_ms": 4.0,
                    "wind_speed_kmh": 14.4,
                    "wind_level": 3.0,
                    "wind_direction": "西北",
                },
            },
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_wind_calendar(2026, 7)

        self.assertEqual(payload["aggregation"], "daily_average")
        self.assertEqual(payload["max_point_count"], 31)
        self.assertEqual(payload["point_count"], 2)
        self.assertEqual(len(payload["history"]), 31)
        self.assertEqual(payload["history"][0]["data"]["wind_speed_kmh"], 10.8)
        self.assertEqual(payload["history"][0]["data"]["wind_level"], 2.6)
        self.assertEqual(payload["history"][0]["data"]["wind_direction"], "西")
        self.assertEqual(payload["history"][1]["data"]["wind_direction"], "西北")
        self.assertEqual(payload["history"][2]["data"], {})

    def test_wind_rolling_view_covers_twelve_calendar_months(self):
        fake = FakeIoTDB()
        timezone = ZoneInfo("Asia/Shanghai")
        bucket_end = datetime(2026, 7, 2, tzinfo=timezone).timestamp()
        fake.points_by_path["root.dam.rollup_1d.wind_001"] = [{
            "timestamp": bucket_end,
            "data": {"wind_speed_kmh": 10.8, "wind_level": 3, "wind_direction": "西"},
        }]
        service = SensorHistoryService(iotdb=fake)
        now_ms = int(datetime(2026, 7, 18, 12, tzinfo=timezone).timestamp() * 1000)

        payload = service.query_wind_trends("rolling12", now_ms=now_ms)

        self.assertEqual(payload["view"], "rolling12")
        self.assertEqual(payload["history"][0]["date"], "2025-08-01")
        self.assertEqual(payload["history"][-1]["date"], "2026-07-31")
        self.assertEqual(payload["max_point_count"], 365)
        self.assertEqual(payload["point_count"], 1)
        july_first = next(row for row in payload["history"] if row["date"] == "2026-07-01")
        self.assertEqual(july_first["data"]["wind_direction"], "西")

    def test_rain_calendar_returns_only_daily_rainfall(self):
        fake = FakeIoTDB()
        timezone = ZoneInfo("Asia/Shanghai")
        first_bucket_end = datetime(2026, 7, 2, tzinfo=timezone).timestamp()
        second_bucket_end = datetime(2026, 7, 3, tzinfo=timezone).timestamp()
        fake.points_by_path["root.dam.rollup_1d.rain_001"] = [
            {
                "timestamp": first_bucket_end,
                "data": {
                    "daily_rain": 18.6,
                    "daily_rain_sample_count": 1440,
                    "total_rain": 300.0,
                    "today_rain": 9.3,
                },
            },
            {
                "timestamp": second_bucket_end,
                "data": {"daily_rain": 0.0, "daily_rain_sample_count": 1440},
            },
        ]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_rain_calendar(2026, 7)

        self.assertEqual(payload["aggregation"], "daily_rainfall")
        self.assertEqual(payload["max_point_count"], 31)
        self.assertEqual(payload["point_count"], 2)
        self.assertEqual(len(payload["history"]), 31)
        self.assertEqual(payload["history"][0]["data"]["daily_rain"], 18.6)
        self.assertEqual(payload["history"][1]["data"]["daily_rain"], 0.0)
        self.assertNotIn("total_rain", payload["history"][0]["data"])
        self.assertNotIn("today_rain", payload["history"][0]["data"])
        self.assertEqual(payload["history"][2]["data"], {})

    def test_long_range_rebuild_uses_lower_rollup_instead_of_raw(self):
        fake = FakeIoTDB()
        fake.points_by_path["root.dam.rollup_10m.temp_001"] = []
        fake.points_by_path["root.dam.rollup_1m.temp_001"] = [
            {"timestamp": 1782935410.0, "data": {"temperature": 20}},
            {"timestamp": 1782935470.0, "data": {"temperature": 22}},
        ]
        fake.raw_points = [{"timestamp": 1782935410.0, "data": {"temperature": 99}}]
        service = SensorHistoryService(iotdb=fake)

        payload = service.query_history("temp_humidity", "6h", now_ms=1782957050000)

        self.assertEqual(payload["source"], "rollup_rebuilt")
        self.assertEqual(payload["history"][0]["data"]["temperature"], 21.0)

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

    def test_archive_manifest_survives_restart_and_prevents_duplicate_export(self):
        fake = FakeIoTDB()
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SensorHistoryService(
                iotdb=fake,
                archive_base_dir=tmpdir,
                state_path=str(Path(tmpdir) / "state.json"),
            )
            first = service.archive_yesterday_once(today=date(2026, 7, 3))
            restarted = SensorHistoryService(
                iotdb=fake,
                archive_base_dir=tmpdir,
                state_path=str(Path(tmpdir) / "state.json"),
            )
            second = restarted.archive_yesterday_once(today=date(2026, 7, 3))

            self.assertEqual(len(first), 4)
            self.assertEqual(second, [])
            self.assertTrue((Path(tmpdir) / "2026-07-02" / "_SUCCESS").exists())

    def test_backfill_temp_extrema_reads_existing_archive_once(self):
        fake = FakeIoTDB()
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir) / "2026-07-02"
            archive_dir.mkdir(parents=True)
            with (archive_dir / "temp_001.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "temperature", "humidity"])
                writer.writeheader()
                writer.writerow({"timestamp": "1", "temperature": "20", "humidity": "50"})
                writer.writerow({"timestamp": "2", "temperature": "28", "humidity": "70"})
            (archive_dir / "_SUCCESS").write_text(
                json.dumps({"archive_date": "2026-07-02", "rollups_built": True}),
                encoding="utf-8",
            )
            service = SensorHistoryService(
                iotdb=fake,
                archive_base_dir=tmpdir,
                state_path=str(Path(tmpdir) / "state.json"),
            )

            first = service.backfill_temp_extrema_due_days(max_days=1)
            second = service.backfill_temp_extrema_due_days(max_days=1)

            self.assertEqual(first, ["2026-07-02"])
            self.assertEqual(second, [])
            self.assertEqual(fake.inserted[0]["path"], "root.dam.rollup_1d.temp_001")
            self.assertEqual(fake.inserted[0]["data"]["temperature_min"], 20.0)
            self.assertEqual(fake.inserted[0]["data"]["temperature_max"], 28.0)
            self.assertEqual(fake.inserted[0]["data"]["humidity_min"], 50.0)
            self.assertEqual(fake.inserted[0]["data"]["humidity_max"], 70.0)
            manifest = json.loads((archive_dir / "_SUCCESS").read_text(encoding="utf-8"))
            self.assertEqual(manifest["temp_extrema_schema"], 1)

    def test_backfill_rain_daily_reads_existing_archive_once(self):
        fake = FakeIoTDB()
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_dir = Path(tmpdir) / "2026-07-02"
            archive_dir.mkdir(parents=True)
            with (archive_dir / "rain_001.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "today_rain", "total_rain"])
                writer.writeheader()
                writer.writerow({"timestamp": "1", "today_rain": "0", "total_rain": "100"})
                writer.writerow({"timestamp": "2", "today_rain": "17.4", "total_rain": "117.4"})
                writer.writerow({"timestamp": "3", "today_rain": "16.9", "total_rain": "117.4"})
            (archive_dir / "_SUCCESS").write_text(
                json.dumps({"archive_date": "2026-07-02", "rollups_built": True}),
                encoding="utf-8",
            )
            service = SensorHistoryService(
                iotdb=fake,
                archive_base_dir=tmpdir,
                state_path=str(Path(tmpdir) / "state.json"),
            )

            first = service.backfill_rain_daily_due_days(max_days=1)
            second = service.backfill_rain_daily_due_days(max_days=1)

            self.assertEqual(first, ["2026-07-02"])
            self.assertEqual(second, [])
            self.assertEqual(fake.inserted[0]["path"], "root.dam.rollup_1d.rain_001")
            self.assertEqual(fake.inserted[0]["data"]["daily_rain"], 17.4)
            self.assertEqual(fake.inserted[0]["data"]["daily_rain_sample_count"], 3)
            self.assertNotIn("total_rain", fake.inserted[0]["data"])
            manifest = json.loads((archive_dir / "_SUCCESS").read_text(encoding="utf-8"))
            self.assertEqual(manifest["rain_daily_schema"], 1)

    def test_archive_rebuilds_all_long_range_rollup_levels_from_same_raw_scan(self):
        fake = FakeIoTDB()
        fake.raw_points = [
            {"timestamp": 1782950410.0, "data": {"temperature": 20}},
            {"timestamp": 1782950470.0, "data": {"temperature": 22}},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SensorHistoryService(
                iotdb=fake,
                archive_base_dir=tmpdir,
                state_path=str(Path(tmpdir) / "state.json"),
            )
            service.archive_yesterday_once(today=date(2026, 7, 3))
            manifest = json.loads(
                (Path(tmpdir) / "2026-07-02" / "_SUCCESS").read_text(encoding="utf-8")
            )

            self.assertTrue(manifest["rollups_built"])
            self.assertEqual(
                set(manifest["rollup_counts"]["temp_humidity"]),
                {"10m", "30m", "1h", "1d"},
            )
            inserted_paths = {item["path"] for item in fake.inserted}
            self.assertIn("root.dam.rollup_10m.temp_001", inserted_paths)
            self.assertIn("root.dam.rollup_1d.temp_001", inserted_paths)

    def test_rollup_checkpoint_catches_up_after_restart(self):
        fake = FakeIoTDB()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "history_state.json")
            first = SensorHistoryService(iotdb=fake, state_path=state_path)
            first_result = first.build_due_rollups(now_ms=1782957000000)
            restarted = SensorHistoryService(iotdb=fake, state_path=state_path)
            second_result = restarted.build_due_rollups(now_ms=1782957180000)

            self.assertEqual(first_result["1m"]["processed_buckets"], 1)
            self.assertEqual(second_result["1m"]["processed_buckets"], 3)
            self.assertTrue(Path(state_path).exists())

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
