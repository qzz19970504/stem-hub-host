from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.ui import theme
from stem_hub_host.ui import stylesheet
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


def test_source_qss_contains_no_hex_color_literals() -> None:
    source = stylesheet.load_qss_source()

    assert not re.search(r"#[0-9A-Fa-f]{6}\b", source)


def test_source_qss_tokens_are_declared() -> None:
    source = stylesheet.load_qss_source()
    source_tokens = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", source))

    assert source_tokens
    assert source_tokens <= set(stylesheet.qss_tokens())


def test_all_qss_tokens_resolve() -> None:
    rendered = stylesheet.get_qss()

    assert not re.search(r"\{\{[A-Z0-9_]+\}\}", rendered)

