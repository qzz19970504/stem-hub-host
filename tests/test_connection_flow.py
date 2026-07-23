from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport


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
        lambda: transport.feed(b"+VERSION:test\r\nOK\r\n"),
    )
    QTest.qWait(60)

    assert controller.is_handshake_ok
    assert worker.is_open()
    assert controller._sense_timer.isActive()
    assert failures == []
    assert not controller._handshake_retry_timer.isActive()
    assert not controller._handshake_deadline_timer.isActive()
    worker.close()


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
        lambda: transport.feed(b"+VERSION:test\r\nOK\r\n"),
    )
    QTest.qWait(160)

    assert worker.is_open()
    assert controller.is_handshake_ok
    assert failures == []
    worker.close()
