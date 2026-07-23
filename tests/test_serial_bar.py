from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.ui.widgets.serial_bar import SerialBar


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def serial_bar(qapp: QApplication) -> SerialBar:
    bar = SerialBar()
    yield bar
    bar.deleteLater()
    qapp.processEvents()


def test_disconnected_action_is_green_connect_state(serial_bar: SerialBar) -> None:
    serial_bar.set_disconnected()

    assert serial_bar.connect_btn.text() == "CONNECT"
    assert serial_bar.connect_btn.property("connectionState") == "offline"
    assert serial_bar.status_badge.text() == "OFFLINE"


def test_open_port_action_is_red_disconnect_state(serial_bar: SerialBar) -> None:
    serial_bar.set_connected("COM3", 115200)

    assert serial_bar.connect_btn.text() == "DISCONNECT"
    assert serial_bar.connect_btn.property("connectionState") == "opening"
    assert serial_bar.status_badge.text() == "OPENING"


def test_handshake_action_stays_red_and_reports_connected(serial_bar: SerialBar) -> None:
    serial_bar.set_handshake_ok("release-v2.1")

    assert serial_bar.connect_btn.text() == "DISCONNECT"
    assert serial_bar.connect_btn.property("connectionState") == "connected"
    assert serial_bar.status_badge.text() == "CONNECTED"


def test_serial_status_and_action_controls_expose_semantic_dots(
    serial_bar: SerialBar,
) -> None:
    serial_bar.set_handshake_ok("release-v2.1")

    assert serial_bar.status_badge.dot_color == "connected"
    assert serial_bar.connect_btn.dot_color == "connected"

    serial_bar.set_disconnected()
    assert serial_bar.status_badge.dot_color == "offline"
    assert serial_bar.connect_btn.dot_color == "offline"


def test_disconnect_action_has_room_for_dot_and_complete_label(
    serial_bar: SerialBar,
) -> None:
    assert serial_bar.connect_btn.width() >= 146
