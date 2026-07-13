import math
import sys
import types
import unittest


class FakeLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=FakeLogger()))

from app.services.history_aggregation import aggregate_bucket_values, circular_mean_degrees
from app.services.history_config import build_history_window, get_range_config


class HistoryAggregationTest(unittest.TestCase):
    def test_six_month_range_uses_one_day_rollup(self):
        config = get_range_config("6mo")
        self.assertEqual(config.rollup_level, "1d")
        self.assertEqual(config.bucket_ms, 24 * 60 * 60 * 1000)
        self.assertEqual(config.max_point_count, 180)

    def test_build_history_window_aligns_six_month_to_day_boundary(self):
        now_ms = 1782957050000
        window = build_history_window("6mo", now_ms)
        self.assertEqual(window["sample_ms"], 24 * 60 * 60 * 1000)
        self.assertEqual(window["rollup_level"], "1d")
        utc_8_offset_ms = 8 * 60 * 60 * 1000
        self.assertEqual(
            ((window["end_ms"] + utc_8_offset_ms) % (24 * 60 * 60 * 1000)),
            0,
        )

    def test_circular_mean_wraps_across_zero_degrees(self):
        self.assertAlmostEqual(circular_mean_degrees([350, 10]), 0.0, places=6)

    def test_wind_direction_uses_circular_mean_and_canonical_direction(self):
        result = aggregate_bucket_values(
            "wind",
            {
                "wind_speed_ms": [2, 4],
                "wind_speed_kmh": [7.2, 14.4],
                "wind_level": [2, 4],
                "wind_angle": [350, 10],
            },
        )
        self.assertEqual(result["wind_speed_ms"], 3.0)
        self.assertEqual(result["wind_speed_kmh"], 10.8)
        self.assertEqual(result["wind_level"], 3.0)
        self.assertAlmostEqual(result["wind_angle"], 0.0, places=6)
        self.assertEqual(result["wind_dir_code"], 0)
        self.assertEqual(result["wind_direction"], "北")

    def test_temperature_humidity_use_average(self):
        result = aggregate_bucket_values(
            "temp_humidity",
            {"temperature": [20, 22, 24], "humidity": [50, 55, 60]},
        )
        self.assertEqual(result, {"temperature": 22.0, "humidity": 55.0})

    def test_rain_uses_average_for_selected_bucket(self):
        result = aggregate_bucket_values(
            "rain",
            {"instant_rain": [0.2, 0.4], "hour_rain": [1.0, 2.0], "today_rain": [8.0, 10.0]},
        )
        self.assertEqual(result["instant_rain"], 0.3)
        self.assertEqual(result["hour_rain"], 1.5)
        self.assertEqual(result["today_rain"], 9.0)

    def test_vibration_uses_average_for_current_template(self):
        result = aggregate_bucket_values("vibration", {"加速度X": [0.1, 0.3], "频率X": [40, 44]})
        self.assertEqual(result["加速度X"], 0.2)
        self.assertEqual(result["频率X"], 42.0)


if __name__ == "__main__":
    unittest.main()
