from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.ui import theme
from stem_hub_host.ui.fonts import load_application_fonts


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    application = QApplication.instance() or QApplication([])
    return application


@pytest.mark.parametrize(
    ("volts", "expected"),
    [
        (None, 0.0),
        (27.0, 0.0),
        (28.0, 0.0),
        (32.5, 0.5),
        (37.0, 1.0),
        (40.0, 1.0),
    ],
)
def test_battery_ratio_clamps(volts: float | None, expected: float) -> None:
    assert theme.battery_ratio(volts) == expected


def test_font_loader_returns_named_families(qapp: QApplication) -> None:
    families = load_application_fonts()

    assert families.display
    assert families.mono
    assert families.cjk

