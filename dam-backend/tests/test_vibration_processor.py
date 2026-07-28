import math
import unittest

from app.services.vibration_processor import FFT_POINTS, VibrationProcessor


class VibrationProcessorTests(unittest.TestCase):
    def test_register_dominant_freq_uses_primary_vibration_axis(self):
        processor = VibrationProcessor()
        freq = processor.calc_register_dominant_freq({
            "频率X": 5.0,
            "频率Y": 12.0,
            "频率Z": 18.0,
            "加速度幅值X": 0.02,
            "加速度幅值Y": 0.30,
            "加速度幅值Z": 0.04,
        })

        self.assertAlmostEqual(freq, 12.0)

    def test_register_dominant_freq_blends_same_mode_only(self):
        processor = VibrationProcessor()
        freq = processor.calc_register_dominant_freq({
            "频率X": 9.8,
            "频率Y": 10.2,
            "频率Z": 16.0,
            "加速度幅值X": 0.30,
            "加速度幅值Y": 0.20,
            "加速度幅值Z": 0.18,
        })

        self.assertAlmostEqual(freq, 9.96, places=2)

    def test_fft_dominant_freq_preserves_single_axis_sine_frequency(self):
        processor = VibrationProcessor(sample_rate=100)
        freq_hz = 8.0
        for index in range(320):
            sample = math.sin(2 * math.pi * freq_hz * index / 100)
            processor.process_raw_data({
                "加速度X": sample,
                "加速度Y": 0.0,
                "加速度Z": 0.0,
            })

        self.assertAlmostEqual(processor.calc_fft_dominant_freq(), freq_hz, delta=0.5)

    def test_buffer_keeps_enough_points_for_fft(self):
        processor = VibrationProcessor(sample_rate=100)
        for index in range(300):
            processor.process_raw_data({
                "加速度X": math.sin(2 * math.pi * 6 * index / 100),
                "加速度Y": 0.0,
                "加速度Z": 0.0,
            })

        self.assertGreaterEqual(len(processor.axis_buffers["x"]), FFT_POINTS)
        self.assertGreater(processor.calc_fft_dominant_freq(), 0)

    def test_low_frequency_motion_can_override_stale_register_frequency(self):
        processor = VibrationProcessor(sample_rate=10)
        for index in range(90):
            sample = 0.12 * math.sin(2 * math.pi * 2 * index / 10)
            result = processor.process_raw_data({
                "加速度X": sample,
                "加速度Y": 0.0,
                "加速度Z": 0.0,
                "加速度幅值X": 0.01,
                "频率X": 45.0,
            })

        self.assertAlmostEqual(result["dominant_freq"], 2.0, delta=0.25)


if __name__ == "__main__":
    unittest.main()
