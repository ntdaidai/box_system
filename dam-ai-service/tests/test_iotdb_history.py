import unittest
import os
import sys
import types

os.environ.setdefault("JWT_SECRET", "unit-test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "unit-test-admin-password")


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.services.iotdb_service import (
    IoTDBService,
    _field_to_value,
    aggregate_history_points,
    build_history_window,
)


class FakeField:
    def __init__(self, double=None, string=None, int_value=None, null=False):
        self.double = double
        self.string = string
        self.int_value = int_value
        self.null = null

    def is_null(self):
        return self.null

    def get_double_value(self):
        return self.double

    def get_string_value(self):
        return self.string

    def get_int_value(self):
        return self.int_value


class FakeSession:
    def __init__(self):
        self.sql = []

    def execute_non_query_statement(self, sql):
        self.sql.append(sql)


class IoTDBHistoryTest(unittest.TestCase):
    def test_field_to_value_preserves_zero_float(self):
        self.assertEqual(_field_to_value(FakeField(double=0.0, string="0.0")), 0.0)

    def test_field_to_value_converts_numeric_string(self):
        self.assertEqual(_field_to_value(FakeField(double=None, string="12.5")), 12.5)

    def test_field_to_value_reads_integer_fields(self):
        self.assertEqual(_field_to_value(FakeField(double=None, int_value=3)), 3.0)

    def test_build_history_window_aligns_one_hour_to_ten_minutes(self):
        now_ms = 1782956911000  # 2026-07-02 09:48:31 +08:00
        window = build_history_window("1h", now_ms)
        self.assertEqual(window["end_ms"], 1782956400000)  # 09:40:00
        self.assertEqual(window["start_ms"], 1782952800000)  # 08:40:00
        self.assertEqual(window["sample_ms"], 60 * 1000)

    def test_build_history_window_aligns_six_hours_to_half_hour(self):
        now_ms = 1782957050000  # 2026-07-02 09:50:50 +08:00
        window = build_history_window("6h", now_ms)
        self.assertEqual(window["end_ms"], 1782955800000)  # 09:30:00
        self.assertEqual(window["start_ms"], 1782934200000)  # 03:30:00
        self.assertEqual(window["sample_ms"], 10 * 60 * 1000)

    def test_build_history_window_aligns_day_to_hour(self):
        now_ms = 1782957050000  # 2026-07-02 09:50:50 +08:00
        window = build_history_window("1d", now_ms)
        self.assertEqual(window["end_ms"], 1782954000000)  # 09:00:00
        self.assertEqual(window["start_ms"], 1782867600000)  # previous day 09:00:00
        self.assertEqual(window["sample_ms"], 30 * 60 * 1000)

    def test_build_history_window_aligns_seven_days_to_hour(self):
        now_ms = 1782957050000  # 2026-07-02 09:50:50 +08:00
        window = build_history_window("7d", now_ms)
        self.assertEqual(window["end_ms"], 1782954000000)  # 09:00:00
        self.assertEqual(window["start_ms"], 1782349200000)  # seven days earlier 09:00:00
        self.assertEqual(window["sample_ms"], 60 * 60 * 1000)
        self.assertEqual(window["max_point_count"], 168)

    def test_aggregate_history_points_averages_numeric_fields(self):
        window = {
            "start_ms": 1782952800000,
            "end_ms": 1782952920000,
            "sample_ms": 60 * 1000,
        }
        raw = [
            {"timestamp": 1782952810.0, "data": {"temperature": 20, "humidity": 50}},
            {"timestamp": 1782952830.0, "data": {"temperature": 22, "humidity": 54}},
            {"timestamp": 1782952870.0, "data": {"temperature": 24, "humidity": 58}},
        ]
        result = aggregate_history_points(raw, "temp_humidity", window)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["timestamp"], 1782952860.0)
        self.assertEqual(result[0]["data"]["temperature"], 21.0)
        self.assertEqual(result[0]["data"]["humidity"], 52.0)
        self.assertEqual(result[1]["timestamp"], 1782952920.0)
        self.assertEqual(result[1]["data"]["temperature"], 24.0)

    def test_delete_points_older_than_deletes_all_measurements_under_path(self):
        service = IoTDBService()
        service.session = FakeSession()

        ok = service.delete_points_older_than("root.dam.rollup_30m.rain_001", 1775180911000)

        self.assertTrue(ok)
        self.assertEqual(
            service.session.sql[0],
            "DELETE FROM root.dam.rollup_30m.rain_001.* WHERE time < 1775180911000",
        )


if __name__ == "__main__":
    unittest.main()
