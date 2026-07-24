from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui import native_chrome, theme
from stem_hub_host.ui.main_window import MainWindow


def test_caption_palette_matches_adjacent_surface_in_both_themes() -> None:
    dark = native_chrome.caption_palette("dark")
    light = native_chrome.caption_palette("light")

    assert dark.background == theme._DARK_PALETTE["BG_BASE"]
    assert dark.foreground == theme._DARK_PALETTE["FG_PRIMARY"]
    assert dark.use_dark_mode is True
    assert light.background == theme._LIGHT_PALETTE["BG_BASE"]
    assert light.foreground == theme._LIGHT_PALETTE["FG_PRIMARY"]
    assert light.use_dark_mode is False


def test_windows_colorref_uses_bgr_byte_order() -> None:
    assert native_chrome.hex_to_colorref("#123456") == 0x563412


def test_main_window_uses_exact_branding_and_bundled_icon() -> None:
    app = get_app()
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    try:
        assert QApplication.applicationName() == "stem hub host"
        assert window.windowTitle() == "stem hub host"
        assert not app.windowIcon().isNull()
        assert not window.windowIcon().isNull()
    finally:
        window.close()
        worker.close()


def test_theme_change_reapplies_native_title_bar(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        native_chrome,
        "apply_windows_title_bar",
        lambda _window, scheme: calls.append(scheme) or True,
    )
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    try:
        calls.clear()
        window.set_color_scheme("light", persist=False)
        window.set_color_scheme("dark", persist=False)
        assert calls == ["light", "dark"]
    finally:
        window.close()
        worker.close()
