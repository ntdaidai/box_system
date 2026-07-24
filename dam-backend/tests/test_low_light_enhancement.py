"""Tests for low-light frame pre-processing used before model inference."""

import unittest

import numpy as np

from app.services.low_light_enhancement import (
    LowLightEnhancementConfig,
    enhance_low_light_if_needed,
)


class LowLightEnhancementTests(unittest.TestCase):
    def test_dark_frame_is_enhanced_without_changing_shape(self):
        image = np.full((48, 80, 3), 24, dtype=np.uint8)
        image[18:24, 20:34] = 58

        enhanced, metadata = enhance_low_light_if_needed(
            image,
            LowLightEnhancementConfig(enabled=True, mode="auto"),
        )

        self.assertTrue(metadata["applied"])
        self.assertEqual(enhanced.shape, image.shape)
        self.assertGreater(metadata["enhanced_luma_mean"], metadata["luma_mean"])

    def test_normal_brightness_frame_is_left_unchanged(self):
        image = np.full((48, 80, 3), 160, dtype=np.uint8)

        enhanced, metadata = enhance_low_light_if_needed(
            image,
            LowLightEnhancementConfig(enabled=True, mode="auto"),
        )

        self.assertFalse(metadata["applied"])
        self.assertIs(enhanced, image)
        self.assertEqual(metadata["reason"], "normal_light")

    def test_disabled_config_skips_enhancement(self):
        image = np.full((48, 80, 3), 20, dtype=np.uint8)

        enhanced, metadata = enhance_low_light_if_needed(
            image,
            LowLightEnhancementConfig(enabled=False, mode="auto"),
        )

        self.assertFalse(metadata["applied"])
        self.assertIs(enhanced, image)
        self.assertEqual(metadata["reason"], "disabled")


if __name__ == "__main__":
    unittest.main()
