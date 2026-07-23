from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QImage

from stem_hub_host.visual_regression import compare_images


def _image(width: int, height: int, color: QColor) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(color)
    return image


def test_compare_images_reports_exact_rgb_metrics() -> None:
    expected = _image(2, 1, QColor(0, 0, 0, 255))
    actual = expected.copy()
    actual.setPixelColor(0, 0, QColor(3, 6, 9, 255))

    metrics = compare_images(
        expected,
        actual,
        channel_threshold=2,
    )

    assert metrics.dimensions_match
    assert metrics.mean_rgb_abs_diff == pytest.approx(3.0)
    assert metrics.changed_pixel_ratio == pytest.approx(0.5)
    assert metrics.max_channel_diff == 9
    assert not metrics.passes(
        mean_limit=2.9,
        changed_ratio_limit=0.49,
    )


def test_compare_images_rejects_dimension_mismatch() -> None:
    expected = _image(2, 1, QColor("black"))
    actual = _image(3, 1, QColor("black"))

    metrics = compare_images(expected, actual)

    assert not metrics.dimensions_match
    assert not metrics.passes()


def test_compare_images_accepts_identical_images() -> None:
    expected = _image(2, 2, QColor("#5EEAD4"))

    metrics = compare_images(expected, expected.copy())

    assert metrics.dimensions_match
    assert metrics.mean_rgb_abs_diff == 0.0
    assert metrics.changed_pixel_ratio == 0.0
    assert metrics.max_channel_diff == 0
    assert metrics.passes()
