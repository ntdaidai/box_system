"""OpenCV pre-processing for low-light camera frames before vision inference."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import cv2
import numpy as np


def _get_bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float_env(key: str, default: float, lower: float, upper: float) -> float:
    try:
        value = float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, min(value, upper))


def _get_int_env(key: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lower, min(value, upper))


@dataclass(frozen=True)
class LowLightEnhancementConfig:
    enabled: bool = _get_bool_env("VISION_LOW_LIGHT_ENHANCE", True)
    mode: str = os.getenv("VISION_LOW_LIGHT_MODE", "auto").strip().lower()
    mean_threshold: float = _get_float_env(
        "VISION_LOW_LIGHT_MEAN_THRESHOLD", 72.0, 1.0, 255.0
    )
    p10_threshold: float = _get_float_env(
        "VISION_LOW_LIGHT_P10_THRESHOLD", 45.0, 1.0, 255.0
    )
    clahe_clip_limit: float = _get_float_env(
        "VISION_LOW_LIGHT_CLAHE_CLIP", 2.2, 0.5, 8.0
    )
    clahe_tile_size: int = _get_int_env("VISION_LOW_LIGHT_CLAHE_TILE", 8, 2, 32)
    gamma: float = _get_float_env("VISION_LOW_LIGHT_GAMMA", 0.72, 0.2, 2.0)
    sharpen_amount: float = _get_float_env(
        "VISION_LOW_LIGHT_SHARPEN", 0.18, 0.0, 1.0
    )


def _frame_luma_stats(image: np.ndarray) -> Tuple[float, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()), float(np.percentile(gray, 10))


def _should_enhance(
    image: np.ndarray,
    config: LowLightEnhancementConfig,
) -> Tuple[bool, Dict[str, Any]]:
    luma_mean, luma_p10 = _frame_luma_stats(image)
    metadata: Dict[str, Any] = {
        "enabled": config.enabled,
        "mode": config.mode,
        "applied": False,
        "luma_mean": round(luma_mean, 2),
        "luma_p10": round(luma_p10, 2),
    }

    if not config.enabled or config.mode == "off":
        metadata["reason"] = "disabled"
        return False, metadata
    if config.mode == "always":
        metadata["reason"] = "forced"
        return True, metadata

    low_light = luma_mean < config.mean_threshold or (
        luma_p10 < config.p10_threshold and luma_mean < 96.0
    )
    metadata["reason"] = "low_light" if low_light else "normal_light"
    return low_light, metadata


def _apply_low_light_enhancement(
    image: np.ndarray,
    config: LowLightEnhancementConfig,
) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(
        clipLimit=config.clahe_clip_limit,
        tileGridSize=(config.clahe_tile_size, config.clahe_tile_size),
    )
    enhanced_l = clahe.apply(l_channel)
    enhanced = cv2.cvtColor(
        cv2.merge((enhanced_l, a_channel, b_channel)),
        cv2.COLOR_LAB2BGR,
    )

    if config.gamma != 1.0:
        table = np.array(
            [((value / 255.0) ** config.gamma) * 255 for value in range(256)],
            dtype=np.uint8,
        )
        enhanced = cv2.LUT(enhanced, table)

    if config.sharpen_amount > 0:
        blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.0)
        enhanced = cv2.addWeighted(
            enhanced,
            1.0 + config.sharpen_amount,
            blurred,
            -config.sharpen_amount,
            0,
        )

    return enhanced


def enhance_low_light_if_needed(
    image: np.ndarray,
    config: LowLightEnhancementConfig | None = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Return an inference-ready frame plus metadata about any enhancement."""
    config = config or LowLightEnhancementConfig()
    should_enhance, metadata = _should_enhance(image, config)
    if not should_enhance:
        return image, metadata

    enhanced = _apply_low_light_enhancement(image, config)
    metadata["applied"] = True
    enhanced_mean, enhanced_p10 = _frame_luma_stats(enhanced)
    metadata["enhanced_luma_mean"] = round(enhanced_mean, 2)
    metadata["enhanced_luma_p10"] = round(enhanced_p10, 2)
    return enhanced, metadata
