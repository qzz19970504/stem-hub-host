from __future__ import annotations

import pytest

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow


class FailingOpenTransport(FakeSerialTransport):
    def open(self, port_name: str, baudrate: int) -> bool:
        return False

    def error_string(self) -> str:
        return "access denied"


def _short_controller() -> tuple[
    FakeSerialTransport,
    SerialWorker,
    Controller,
]:
    get_app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(
        worker,
        handshake_deadline_ms=120,
        handshake_retry_ms=20,
        handshake_attempt_timeout_ms=15,
        handshake_initial_delay_ms=0,
    )
    return transport, worker, controller


def test_handshake_deadline_closes_before_reporting_failure() -> None:
    _, worker, controller = _short_controller()
    events: list[str] = []
    failures: list[str] = []
    worker.disconnected.connect(lambda: events.append("disconnected"))

    def record_failure(reason: str) -> None:
        events.append("failed")
        failures.append(reason)

    controller.handshake_failed.connect(record_failure)

    assert worker.open("FAKE0", 115200)
    QTest.qWait(70)
    assert worker.is_open()
    assert failures == []

    QTest.qWait(100)

    assert not worker.is_open()
    assert events == ["disconnected", "failed"]
    assert len(failures) == 1
    assert not controller._handshake_delay_timer.isActive()
    assert not controller._handshake_retry_timer.isActive()
    assert not controller._handshake_deadline_timer.isActive()


def test_success_cancels_deadline_and_starts_polling() -> None:
    transport, worker, controller = _short_controller()
    failures: list[str] = []
    controller.handshake_failed.connect(failures.append)

    assert worker.open("FAKE0", 115200)
    QTimer.singleShot(
        5,
        lambda: transport.feed(b"+VERSION:release-v3.3\r\nOK\r\n"),
    )
    QTest.qWait(60)

    assert controller.is_handshake_ok
    assert worker.is_open()
    assert controller._sense_timer.isActive()
    assert failures == []
    assert not controller._handshake_retry_timer.isActive()
    assert not controller._handshake_deadline_timer.isActive()
    worker.close()


@pytest.mark.parametrize(
    "version",
    ["release-v3.1", "release-v3.0", "release-v2.2"],
)
def test_older_firmware_does_not_pass_v3_2_power_protocol_gate(version: str) -> None:
    transport, worker, controller = _short_controller()
    failures: list[str] = []
    controller.handshake_failed.connect(failures.append)

    assert worker.open("FAKE0", 115200)
    QTimer.singleShot(
        5,
        lambda: transport.feed(f"+VERSION:{version}\r\nOK\r\n".encode()),
    )
    QTest.qWait(60)

    assert not controller.is_handshake_ok
    assert not worker.is_open()
    assert failures
    assert "INCOMPATIBLE_VERSION" in failures[-1]


def test_v2_response_cannot_reenable_main_window_gate(monkeypatch) -> None:
    app = get_app()
    transport, worker, controller = _short_controller()
    window = MainWindow(controller)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: QMessageBox.StandardButton.Ok,
    )

    assert worker.open("FAKE0", 115200)
    QTimer.singleShot(
        5,
        lambda: transport.feed(b"+VERSION:release-v2.2\r\nOK\r\n"),
    )
    QTest.qWait(60)

    assert not controller.is_handshake_ok
    assert not worker.is_open()
    assert window.console_tab.serial_bar.status_badge.text() == "OFFLINE"
    assert window.console_tab.serial_bar.connect_btn.text() == "CONNECT"
    assert not window.console_tab.charge_card.all_off_button.isEnabled()

    window.close()
    app.processEvents()


def test_user_close_during_connecting_does_not_report_failure() -> None:
    _, worker, controller = _short_controller()
    failures: list[str] = []
    controller.handshake_failed.connect(failures.append)

    assert worker.open("FAKE0", 115200)
    QTest.qWait(10)
    controller.close()
    QTest.qWait(150)

    assert not worker.is_open()
    assert failures == []
    assert not controller._handshake_retry_timer.isActive()
    assert not controller._handshake_deadline_timer.isActive()


def test_fast_reconnect_ignores_old_connection_timers() -> None:
    transport, worker, controller = _short_controller()
    failures: list[str] = []
    controller.handshake_failed.connect(failures.append)

    assert worker.open("FAKE0", 115200)
    controller.close()
    assert worker.open("FAKE1", 115200)
    QTimer.singleShot(
        5,
        lambda: transport.feed(b"+VERSION:release-v3.3\r\nOK\r\n"),
    )
    QTest.qWait(160)

    assert worker.is_open()
    assert controller.is_handshake_ok
    assert failures == []
    worker.close()


def test_handshake_failure_is_offline_before_single_dialog(
    monkeypatch,
) -> None:
    app = get_app()
    _, worker, controller = _short_controller()
    window = MainWindow(controller)
    warnings: list[tuple[str, str]] = []

    def record_warning(parent, title: str, text: str):
        assert window.console_tab.serial_bar.status_badge.text() == "OFFLINE"
        assert window.console_tab.serial_bar.connect_btn.text() == "CONNECT"
        assert window.console_tab.serial_bar.port_combo.isEnabled()
        warnings.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", record_warning)

    assert worker.open("FAKE0", 115200)
    QTest.qWait(280)

    assert len(warnings) == 1
    assert warnings[0][0] == "Connection Failed"
    assert "5 seconds" in warnings[0][1]
    assert not worker.is_open()
    window.close()
    app.processEvents()


def test_direct_open_failure_restores_offline_and_warns_once(
    monkeypatch,
) -> None:
    app = get_app()
    worker = SerialWorker(FailingOpenTransport())
    controller = Controller(worker)
    window = MainWindow(controller)
    warnings: list[tuple[str, str]] = []

    def record_warning(parent, title: str, text: str):
        warnings.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", record_warning)

    window._on_open_serial("COM_BAD", 115200)
    app.processEvents()

    bar = window.console_tab.serial_bar
    assert bar.status_badge.text() == "OFFLINE"
    assert bar.connect_btn.text() == "CONNECT"
    assert bar.port_combo.isEnabled()
    assert warnings == [
        (
            "Connection Failed",
            "Unable to open serial port COM_BAD.\n\n"
            "Check that the port is not in use and try again.",
        )
    ]
    window.close()
