"""SerialWorker + FakeFirmware 集成测试 (不需要硬件).

需要 QApplication 跑事件循环, 所以用 pytest-qt 的 qtbot.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    pytest.skip("PySide6 not installed", allow_module_level=True)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def fake_pair(qapp):
    """提供一个 (worker, fake_firmware) 对, 用 FakeSerialTransport 联通."""
    from stem_hub_host.fake_firmware import FakeFirmware
    from stem_hub_host.serial_worker import SerialWorker
    from stem_hub_host.transport import FakeSerialTransport

    # 关键: worker 和 firmware 必须**共享同一个** transport
    transport = FakeSerialTransport()
    worker = SerialWorker(transport=transport)
    fw = FakeFirmware(worker)
    assert worker.open("FAKE0", 115200)
    yield worker, fw
    worker.close()
    fw.deleteLater()
    worker.deleteLater()


def test_handshake(fake_pair):
    from stem_hub_host.at_protocol import cmd_handshake

    worker, fw = fake_pair
    resp = worker.send_and_wait(cmd_handshake(), timeout_ms=500)
    assert resp.ok
    assert fw.VERSION == "release-v3.2"
    assert resp.version.version == "release-v3.2"
    # 之前 at_data_received 触发过, 但我们直接看 response


def test_query_sense(fake_pair, qapp):
    from stem_hub_host.at_protocol import cmd_query_sense

    worker, fw = fake_pair
    resp = worker.send_and_wait(cmd_query_sense(), timeout_ms=500)
    assert resp.ok
    # data 行不直接进 resp, 但 at_data_received 触发过, 我们重新查 firmware state
    assert fw._sense_count >= 1


def test_set_motor(fake_pair):
    from stem_hub_host.at_protocol import cmd_set_motor
    from stem_hub_host.at_protocol import cmd_query_motor

    worker, fw = fake_pair
    resp = worker.send_and_wait(cmd_set_motor("FWD"), timeout_ms=500)
    assert resp.ok
    assert fw._motor_mode == "FWD"

    resp2 = worker.send_and_wait(cmd_query_motor(), timeout_ms=500)
    assert resp2.motor.mode == "FWD"


def test_power_modes_are_mutually_exclusive_in_fake_firmware(fake_pair):
    from stem_hub_host.at_protocol import (
        cmd_power_off,
        cmd_set_charge,
        cmd_set_drive,
    )

    worker, firmware = fake_pair

    assert worker.send_and_wait(cmd_set_charge(True), timeout_ms=500).ok
    assert firmware._lm51770 is True
    assert firmware._mp4317 is False

    assert worker.send_and_wait(cmd_set_drive(True), timeout_ms=500).ok
    assert firmware._lm51770 is False
    assert firmware._mp4317 is True

    assert worker.send_and_wait(cmd_power_off(), timeout_ms=500).ok
    assert firmware._lm51770 is False
    assert firmware._mp4317 is False

    old_command = worker.send_and_wait("AT+LM51770=ON\r\n", timeout_ms=500)
    assert not old_command.ok
    assert old_command.error is not None
    assert old_command.error.code == "PARSE"


def test_error_response(fake_pair):
    """错误的命令 → ERROR:PARSE."""
    worker, fw = fake_pair
    resp = worker.send_and_wait("AT+NONSENSE\r\n", timeout_ms=500)
    assert not resp.ok
    assert resp.error is not None
    assert resp.error.code == "PARSE"


def test_timeout(fake_pair):
    """对方不回包时, send_and_wait 抛 SerialTimeout."""
    from stem_hub_host.serial_worker import SerialTimeout

    worker, fw = fake_pair
    # 直接构造一个不响应的命令
    fw._handle_cmd = lambda cmd: None  # noqa: E731 — 让 firmware 不响应
    with pytest.raises(SerialTimeout):
        worker.send_and_wait("AT+VERSION?\r\n", timeout_ms=100)


def test_invalid_utf8_is_reported_as_hex_not_passthrough(qapp):
    from PySide6.QtTest import QSignalSpy

    from stem_hub_host.serial_worker import SerialWorker
    from stem_hub_host.transport import FakeSerialTransport

    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    passthrough = QSignalSpy(worker.passthrough_received)
    errors = QSignalSpy(worker.error_occurred)

    transport.feed(b"\xff\xfe\r\n")

    assert passthrough.count() == 0
    assert errors.count() == 1
    assert "FF FE" in errors.at(0)[0]


def test_commands_are_written_one_at_a_time(qapp):
    from PySide6.QtTest import QSignalSpy

    from stem_hub_host.serial_worker import SerialWorker
    from stem_hub_host.transport import FakeSerialTransport

    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    responses = QSignalSpy(worker.response_received)

    worker.send_command("AT+SENSE?\r\n")
    worker.send_command("AT+FAULT?\r\n")

    assert transport.get_written() == b"AT+SENSE?\r\n"

    transport.feed(b"+SENSE:BATT_NTC=20.0C\r\n")
    assert transport.get_written() == b"AT+SENSE?\r\n"

    transport.feed(b"OK\r\n")
    assert responses.at(0)[0] == "AT+SENSE?\r\n"
    assert transport.get_written() == b"AT+SENSE?\r\nAT+FAULT?\r\n"


def test_sync_timeout_starts_when_queued_command_is_written(qapp):
    from PySide6.QtCore import QTimer

    from stem_hub_host.serial_worker import SerialWorker
    from stem_hub_host.transport import FakeSerialTransport

    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)

    worker.send_command("AT+LED=ON\r\n", timeout_ms=500)
    QTimer.singleShot(80, lambda: transport.feed(b"OK\r\n"))
    QTimer.singleShot(100, lambda: transport.feed(b"OK\r\n"))

    response = worker.send_and_wait("AT+LED=OFF\r\n", timeout_ms=50)

    assert response.ok
    assert transport.get_written() == b"AT+LED=ON\r\nAT+LED=OFF\r\n"


def test_sync_waiter_uses_pending_identity_for_identical_commands(qapp):
    from PySide6.QtCore import QTimer

    from stem_hub_host.serial_worker import SerialWorker
    from stem_hub_host.transport import FakeSerialTransport

    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    command = "AT+VERSION?\r\n"

    worker.send_command(command, timeout_ms=500)
    QTimer.singleShot(
        20,
        lambda: transport.feed(b"+VERSION:first\r\nOK\r\n"),
    )
    QTimer.singleShot(
        40,
        lambda: transport.feed(b"+VERSION:second\r\nOK\r\n"),
    )

    response = worker.send_and_wait(command, timeout_ms=200)

    assert response.version is not None
    assert response.version.version == "second"
    assert transport.get_written() == command.encode() * 2
