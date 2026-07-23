"""Reusable image metrics for deterministic UI visual regression."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtGui import QImage


@dataclass(frozen=True)
class VisualDiffMetrics:
    """Summary of one expected/actual screenshot comparison."""

    dimensions_match: bool
    mean_rgb_abs_diff: float
    changed_pixel_ratio: float
    max_channel_diff: int

    def passes(
        self,
        *,
        mean_limit: float = 3.0,
        changed_ratio_limit: float = 0.01,
    ) -> bool:
        return (
            self.dimensions_match
            and self.mean_rgb_abs_diff <= mean_limit
            and self.changed_pixel_ratio <= changed_ratio_limit
        )


def _rgb_array(image: QImage) -> np.ndarray:
    normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
    height = normalized.height()
    width = normalized.width()
    raw = np.frombuffer(normalized.constBits(), dtype=np.uint8)
    rows = raw.reshape(height, normalized.bytesPerLine())
    rgba = rows[:, : width * 4].reshape(height, width, 4)
    return rgba[:, :, :3].copy()


def compare_images(
    expected: QImage,
    actual: QImage,
    *,
    channel_threshold: int = 12,
) -> VisualDiffMetrics:
    """Compare two images with RGB metrics that are stable and inspectable."""

    dimensions_match = expected.size() == actual.size()
    if not dimensions_match:
        return VisualDiffMetrics(
            dimensions_match=False,
            mean_rgb_abs_diff=float("inf"),
            changed_pixel_ratio=1.0,
            max_channel_diff=255,
        )

    expected_rgb = _rgb_array(expected).astype(np.int16)
    actual_rgb = _rgb_array(actual).astype(np.int16)
    difference = np.abs(expected_rgb - actual_rgb)
    changed_pixels = np.any(difference > channel_threshold, axis=2)

    return VisualDiffMetrics(
        dimensions_match=True,
        mean_rgb_abs_diff=float(difference.mean()),
        changed_pixel_ratio=float(changed_pixels.mean()),
        max_channel_diff=int(difference.max()),
    )
