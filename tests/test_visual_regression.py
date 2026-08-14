from __future__ import annotations

import ast
import inspect
import textwrap

import pytest
from PySide6.QtGui import QColor, QImage

from stem_hub_host import visual_audit
from stem_hub_host.ui import theme
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


def test_visual_audit_console_seed_spans_temperature_bands() -> None:
    values = getattr(visual_audit, "CONSOLE_TEMPERATURES", ())

    assert values == (12.0, 36.0, 58.0, 84.0, 47.0, 49.0)
    assert len({
        theme.temp_color(value)
        for value in values
    }) == 4


def test_visual_audit_console_seed_preserves_settled_temperature_subset() -> None:
    settled_values = getattr(visual_audit, "SETTLED_CONSOLE_TEMPERATURES", ())

    assert settled_values == visual_audit.CONSOLE_TEMPERATURES[:4]


def test_visual_audit_console_seed_uses_semantic_temperature_names() -> None:
    source = inspect.getsource(visual_audit._seed_connected)
    function_tree = ast.parse(textwrap.dedent(source))
    sense_call = next(
        node
        for node in ast.walk(function_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SenseData"
    )
    expected_temperature_variables = {
        "batt_ntc": "battery_temperature",
        "mcu_c": "mcu_temperature",
        "lm51770_c": "lm51770_temperature",
        "mp4317_c": "mp4317_temperature",
        "drv8874_c": "drv8874_temperature",
        "charge_mos_c": "charge_mos_temperature",
    }
    temperature_variables = {
        keyword.arg: [
            node.id
            for node in ast.walk(keyword.value)
            if isinstance(node, ast.Name)
        ]
        for keyword in sense_call.keywords
        if keyword.arg in expected_temperature_variables
    }

    assert temperature_variables == {
        field: [variable]
        for field, variable in expected_temperature_variables.items()
    }
    assert "ntc1_temp" not in source
    assert "ntc2_temp" not in source
    assert "ntc3_temp" not in source
