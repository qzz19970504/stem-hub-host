from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.fonts import load_application_fonts
from stem_hub_host.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return get_app()


@pytest.fixture
def main_window(qapp: QApplication) -> MainWindow:
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    settings_key = "appearance/colorScheme"
    had_saved_scheme = window._appearance_settings.contains(settings_key)
    saved_scheme = window._appearance_settings.value(settings_key)
    window.show()
    qapp.processEvents()
    yield window
    window.set_color_scheme("dark", persist=False)
    if had_saved_scheme:
        window._appearance_settings.setValue(settings_key, saved_scheme)
    else:
        window._appearance_settings.remove(settings_key)
    window._appearance_settings.sync()
    window.close()
    worker.close()
    worker.deleteLater()
    qapp.processEvents()


def test_default_client_size_is_resizable(main_window: MainWindow) -> None:
    assert main_window.minimumSize() == QSize(1280, 720)
    assert main_window.maximumWidth() > 1600
    assert main_window.maximumHeight() > 900
    assert main_window.size() == QSize(1600, 900)


def test_f11_enters_fullscreen_and_escape_restores_normal_size(
    main_window: MainWindow,
    qapp: QApplication,
) -> None:
    main_window.resize(1420, 800)
    qapp.processEvents()
    normal_size = main_window.size()

    QTest.keyClick(main_window, Qt.Key.Key_F11)
    qapp.processEvents()

    assert main_window.isFullScreen()

    QTest.keyClick(main_window, Qt.Key.Key_Escape)
    qapp.processEvents()

    assert not main_window.isFullScreen()
    assert main_window.size() == normal_size
    assert main_window.maximumWidth() > normal_size.width()


def test_main_window_keeps_bundled_fonts_registered(main_window: MainWindow) -> None:
    families = load_application_fonts()

    assert families.display in QFontDatabase.families()
    assert families.mono in QFontDatabase.families()
    assert families.cjk in QFontDatabase.families()


def test_root_surface_fills_the_window_client_area(
    main_window: MainWindow,
    qapp: QApplication,
) -> None:
    main_window.resize(1420, 800)
    qapp.processEvents()

    assert main_window.centralWidget() is main_window.root
    assert main_window.root.rect().size() == main_window.centralWidget().size()
    assert main_window.root.layout().contentsMargins().left() == 0
    assert main_window.root.layout().contentsMargins().top() == 0


def test_theme_toggle_switches_complete_window_palette(
    main_window: MainWindow,
    qapp: QApplication,
) -> None:
    main_window.set_color_scheme("dark", persist=False)
    dark_card = main_window.console_tab.battery_card.grab().toImage().pixelColor(
        12, 12
    )

    main_window.theme_toggle.click()
    qapp.processEvents()
    light_card = main_window.console_tab.battery_card.grab().toImage().pixelColor(
        12, 12
    )

    assert main_window.color_scheme == "light"
    assert main_window.theme_toggle.color_scheme == "light"
    assert light_card.lightness() > dark_card.lightness() + 80
    main_window.set_color_scheme("dark", persist=False)


def test_theme_toggle_stays_inside_visible_tab_header(
    main_window: MainWindow,
    qapp: QApplication,
) -> None:
    qapp.processEvents()
    toggle_rect = main_window.theme_toggle.geometry()

    assert main_window.theme_toggle.isVisible()
    assert toggle_rect.right() <= main_window.tabs.width()
    assert toggle_rect.top() >= 0
    assert toggle_rect.bottom() < main_window.tabs.tabBar().height() + 8
