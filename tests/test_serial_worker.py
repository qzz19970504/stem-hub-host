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
