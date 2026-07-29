from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from stem_hub_host.controller import Controller
from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.fake_firmware import FakeFirmware
from stem_hub_host.models import FaultState, MotorState, SenseData
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow
from stem_hub_host.ui.widgets.passthrough_panel import PassthroughPanel
from stem_hub_host.ui.widgets.plot_widget import PlotWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_disconnect_clears_controller_telemetry_cache() -> None:
    controller = Controller(SerialWorker(FakeSerialTransport()))
    controller._latest_sense = SenseData(
        "42.0C", "37.0V", "38.0C", "39.0C", "40.0C", "1.0A",
        1, 1, 0, 0, 0, 0, 0,
    )
    controller._latest_motor = MotorState("FWD", 1000, 0, 0)
    controller._latest_fault = FaultState(0, 0)

    controller._on_worker_disconnected()

    assert controller.get_latest() == {
        "sense": None,
        "motor": None,
        "fault": None,
    }


def test_uart_single_bridge_closes_other_channel_first() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_passthrough("uart2")

    assert transport.get_written() == b"AT+UART3=OFF\r\n"
    transport.feed(b"OK\r\n")
    assert transport.get_written() == b"AT+UART3=OFF\r\nAT+UART2=ON\r\n"


def test_uart_bridge_aborts_enable_when_disable_is_rejected() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)
    confirmed = QSignalSpy(controller.passthrough_mode_changed)

    controller.set_passthrough("uart2")
    transport.feed(b"ERROR:OUTPUT_QUEUE\r\n")

    assert transport.get_written() == b"AT+UART3=OFF\r\n"
    assert confirmed.at(0)[0] == "off"


def test_worker_raw_write_preserves_binary_bytes() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)

    worker.send_bytes(b"\xff\x00\r\n")

    assert transport.get_written() == b"\xff\x00\r\n"


def test_worker_uart_event_preserves_binary_payload() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    received = QSignalSpy(worker.uart_rx_received)

    transport.feed(b"+UART2RX:FF00\r\n")

    assert received.at(0)[0] == 2
    assert bytes(received.at(0)[1]) == b"\xff\x00"


def test_uart_event_does_not_consume_pending_command() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    responses = QSignalSpy(worker.response_received)
    received = QSignalSpy(worker.uart_rx_received)

    worker.send_command("AT+LED=ON\r\n")
    transport.feed(b"+UART3RX:00FF\r\n")
    assert responses.count() == 0
    assert bytes(received.at(0)[1]) == b"\x00\xff"

    transport.feed(b"OK\r\n")
    assert responses.at(0)[0] == "AT+LED=ON\r\n"


def test_passthrough_text_adds_crlf_and_counts_only_after_confirmation() -> None:
    _app()
    panel = PassthroughPanel()
    sent = QSignalSpy(panel.tx_requested)
    panel.tx_edit.setPlainText("hello")

    panel._on_send()

    assert bytes(sent.at(0)[0]) == b"hello\r\n"
    assert panel.tx_count_label.text() == "TX: 0 字节"
    assert panel.tx_edit.toPlainText() == "hello"

    panel.confirm_tx_sent(len(b"hello\r\n"))
    assert panel.tx_count_label.text() == "TX: 7 字节"
    assert panel.tx_edit.toPlainText() == ""


def test_passthrough_hex_mode_sends_exact_bytes_and_accepts_lowercase() -> None:
    _app()
    panel = PassthroughPanel()
    panel.hex_mode_cb.setChecked(True)
    panel.tx_edit.setPlainText("ff 00")
    sent = QSignalSpy(panel.tx_requested)

    panel._on_send()

    assert bytes(sent.at(0)[0]) == b"\xff\x00"


def test_passthrough_chunks_wait_for_each_ack() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)
    controller._handshake_ok = True
    controller._apply_passthrough_mode("uart2")
    confirmed = QSignalSpy(controller.passthrough_tx_confirmed)
    payload = bytes(range(32)) + b"\xff"

    assert controller.send_passthrough_bytes(payload)
    first = f"AT+UARTTX={bytes(range(32)).hex().upper()}\r\n".encode()
    assert transport.get_written() == first

    transport.feed(b"+UART2RX:00\r\nOK\r\n")
    assert transport.get_written() == first + b"AT+UARTTX=FF\r\n"
    assert confirmed.at(0)[0] == 32

    transport.feed(b"OK\r\n")
    assert confirmed.at(1)[0] == 1


def test_fake_firmware_bidirectional_tunnel_end_to_end() -> None:
    _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    firmware = FakeFirmware(worker)
    assert worker.open("FAKE0", 115200)
    controller._handshake_ok = True
    received = QSignalSpy(worker.uart_rx_received)
    confirmed = QSignalSpy(controller.passthrough_tx_confirmed)

    controller.set_passthrough("uart2")
    QTest.qWait(40)
    assert controller._passthrough_mode == "uart2"

    assert controller.send_passthrough_bytes(b"\x00\xff")
    QTest.qWait(30)

    assert received.at(0)[0] == 2
    assert bytes(received.at(0)[1]) == b"\x00\xff"
    assert confirmed.at(0)[0] == 2
    firmware.deleteLater()


def test_plot_reset_removes_existing_curve_data() -> None:
    _app()
    buffer = DataBuffer()
    buffer.series["batt_v"].append(0.0, 37.0)
    plot = PlotWidget(buffer)
    plot.update_from_buffer()
    assert len(plot._curves["batt_v"].xData) == 1

    plot.reset()

    assert plot._curves["batt_v"].xData is None


def test_passthrough_controls_follow_handshake_gate() -> None:
    app = _app()
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))

    window._apply_handshake_gate(False)
    assert not window.passthrough_tab.panel.send_btn.isEnabled()
    assert not window.passthrough_tab.panel.btn_uart2.isEnabled()

    window._apply_handshake_gate(True)
    assert not window.passthrough_tab.panel.send_btn.isEnabled()
    assert window.passthrough_tab.panel.btn_uart2.isEnabled()

    window._on_passthrough_mode_changed("uart2")
    assert window.passthrough_tab.panel.btn_uart2.isEnabled()
    assert window.passthrough_tab.panel.send_btn.isEnabled()
    window.close()
    app.processEvents()


def test_async_output_error_is_attributed_and_rolls_back_ui() -> None:
    app = _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    window = MainWindow(controller)
    assert worker.open("FAKE0", 115200)
    failures = QSignalSpy(controller.output_command_failed)

    window.console_tab.charge_card.set_toggle("LIGHTS", True, animate=False)
    controller.set_led(True)
    transport.feed(b"ERROR:OUTPUT_QUEUE\r\n")
    QCoreApplication.processEvents()

    assert failures.count() == 1
    assert failures.at(0)[0:2] == ["LIGHTS", True]
    assert not window.console_tab.charge_card.is_on("LIGHTS")
    assert (
        window.console_tab.at_console.log_view.toPlainText().count(
            "ERROR:OUTPUT_QUEUE"
        )
        == 1
    )
    window.close()
    app.processEvents()


def test_charge_mode_reports_atomic_command_failure() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)
    failures = QSignalSpy(controller.output_command_failed)

    controller.set_charge_mode("charge")
    assert transport.get_written() == b"AT+CHARGE=ON\r\n"

    transport.feed(b"ERROR:OUTPUT_QUEUE\r\n")

    assert [failures.at(i)[0:2] for i in range(failures.count())] == [
        ["CHARGE", True],
    ]
    assert not controller._charge_transition_active


def test_charge_mode_uses_one_atomic_command() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_charge_mode("charge")
    assert transport.get_written() == b"AT+CHARGE=ON\r\n"

    transport.feed(b"OK\r\n")
    assert not controller._charge_transition_active


def test_charge_off_uses_one_atomic_command() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_charge_mode("off")
    assert transport.get_written() == b"AT+POWER=OFF\r\n"

    transport.feed(b"OK\r\n")
    assert not controller._charge_transition_active


def test_drive_mode_uses_one_atomic_command() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_charge_mode("drive")
    assert transport.get_written() == b"AT+DRIVE=ON\r\n"

    transport.feed(b"OK\r\n")
    assert not controller._charge_transition_active


def test_rapid_charge_mode_requests_are_serialized() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_charge_mode("charge")
    controller.set_charge_mode("drive")
    assert transport.get_written() == b"AT+CHARGE=ON\r\n"

    transport.feed(b"OK\r\n")
    assert transport.get_written().endswith(b"AT+DRIVE=ON\r\n")
    transport.feed(b"OK\r\n")

    assert transport.get_written() == (
        b"AT+CHARGE=ON\r\n"
        b"AT+DRIVE=ON\r\n"
    )


def test_all_outputs_off_waits_for_each_ack_in_safe_order() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_all_outputs_off()
    expected_commands = (
        b"AT+POWER=OFF\r\n",
        b"AT+NMOS1=OFF\r\n",
        b"AT+NMOS2=OFF\r\n",
        b"AT+LED=OFF\r\n",
    )
    written = b""
    for command in expected_commands:
        written += command
        assert transport.get_written() == written
        transport.feed(b"OK\r\n")

    assert not controller._charge_transition_active


def test_rapid_uart_mode_requests_are_serialized() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    assert worker.open("FAKE0", 115200)

    controller.set_passthrough("uart2")
    controller.set_passthrough("uart3")
    assert transport.get_written() == b"AT+UART3=OFF\r\n"

    for expected_tail in (
        b"AT+UART2=ON\r\n",
        b"AT+UART2=OFF\r\n",
        b"AT+UART3=ON\r\n",
    ):
        transport.feed(b"OK\r\n")
        assert transport.get_written().endswith(expected_tail)
    transport.feed(b"OK\r\n")

    assert transport.get_written() == (
        b"AT+UART3=OFF\r\n"
        b"AT+UART2=ON\r\n"
        b"AT+UART2=OFF\r\n"
        b"AT+UART3=ON\r\n"
    )
    assert not worker._passthrough_raw


def test_raw_passthrough_blocks_at_commands_and_gates_main_controls() -> None:
    app = _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    window = MainWindow(controller)
    assert worker.open("FAKE0", 115200)
    window._apply_handshake_gate(True)

    controller._apply_passthrough_mode("uart2")
    before = transport.get_written()
    controller.set_led(True)
    controller.set_motor("FWD")
    controller.send_raw("AT+DIAG?\r\n")

    assert transport.get_written() == before
    assert not window.console_tab.motor_card.buttons["FWD"].isEnabled()
    assert not window.console_tab.charge_card._cells["LIGHTS"].toggle.isEnabled()
    assert not window.console_tab.at_console.send_btn.isEnabled()
    assert window.passthrough_tab.panel.btn_off.isEnabled()
    assert window.passthrough_tab.panel.send_btn.isEnabled()
    window.close()
    app.processEvents()


def test_completed_async_commands_release_timeout_timers() -> None:
    _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)

    for _ in range(20):
        worker.send_command("AT+LED=OFF\r\n")
        transport.feed(b"OK\r\n")
    assert [
        timer.objectName()
        for timer in worker.findChildren(QTimer)
    ] == ["serialResynchronizationTimer"]


def test_controller_level_errors_reach_terminal_once() -> None:
    app = _app()
    worker = SerialWorker(FakeSerialTransport())
    controller = Controller(worker)
    window = MainWindow(controller)

    controller._on_worker_error("bridge transition failed")
    worker.error_occurred.emit("serial framing failed")
    QCoreApplication.processEvents()
    log = window.console_tab.at_console.log_view.toPlainText()

    assert log.count("bridge transition failed") == 1
    assert log.count("serial framing failed") == 1
    window.close()
    app.processEvents()


def test_async_command_timeout_resynchronizes_without_disconnecting() -> None:
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    assert worker.open("FAKE0", 115200)
    responses = QSignalSpy(worker.response_received)

    worker.send_command("AT+NO-REPLY\r\n", timeout_ms=40)
    QTest.qWait(80)

    assert worker.is_open()
    assert responses.count() == 1
    assert responses.at(0)[0] == "AT+NO-REPLY\r\n"
    assert responses.at(0)[1].error.code == "TIMEOUT"

    transport.feed(b"OK\r\n")
    QTest.qWait(240)
    assert responses.count() == 1

    worker.send_command("AT+LED=OFF\r\n")
    transport.feed(b"OK\r\n")
    assert responses.count() == 2
    assert responses.at(1)[0] == "AT+LED=OFF\r\n"


def test_uart_event_does_not_pollute_passthrough_page_while_disabled() -> None:
    app = _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    window = MainWindow(controller)

    window._on_uart_rx(2, b"\xff\x00")

    assert window.passthrough_tab.panel._rx_bytes == 0

    controller._apply_passthrough_mode("uart2")
    window._on_uart_rx(2, b"\xff\x00")

    assert window.passthrough_tab.panel._rx_bytes == 2
    assert "FF 00" in window.console_tab.at_console.log_view.toPlainText()
    window.close()
    app.processEvents()


def test_fast_reconnect_cancels_stale_delayed_handshake() -> None:
    _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)

    assert worker.open("FAKE0", 115200)
    worker.close()
    assert worker.open("FAKE1", 115200)
    QTimer.singleShot(240, lambda: transport.feed(b"+VERSION:test\r\nOK\r\n"))
    QTest.qWait(320)

    assert transport.get_written().count(b"AT+VERSION?\r\n") == 1
    assert controller.is_handshake_ok


def test_rejected_handshake_stops_at_connection_deadline() -> None:
    _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(
        worker,
        handshake_deadline_ms=120,
        handshake_retry_ms=20,
        handshake_attempt_timeout_ms=15,
        handshake_initial_delay_ms=0,
    )
    failures: list[str] = []
    controller.handshake_failed.connect(failures.append)

    assert worker.open("FAKE0", 115200)
    QTimer.singleShot(5, lambda: transport.feed(b"ERROR:PARSE\r\n"))
    QTest.qWait(60)

    assert not controller.is_handshake_ok
    assert worker.is_open()
    assert failures == []

    QTest.qWait(100)

    assert not worker.is_open()
    assert failures == ["TIMEOUT"]
    assert not controller._handshake_retry_timer.isActive()


def test_rejected_motor_command_restores_last_confirmed_mode() -> None:
    app = _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    controller = Controller(worker)
    window = MainWindow(controller)
    assert worker.open("FAKE0", 115200)
    controller._handshake_ok = True
    window._apply_handshake_gate(True)
    controller._on_at_data(
        "AT+MOTOR?\r\n",
        type("Response", (), {"sense": None, "motor": MotorState("FWD", 900, 0, 0), "fault": None})(),
    )
    window.console_tab.motor_card.update_state("FWD", 900, 0, 0)

    window.console_tab.motor_card._on_rev()
    transport.feed(b"ERROR:OUTPUT_QUEUE\r\n")
    QCoreApplication.processEvents()

    assert window.console_tab.motor_card.buttons["FWD"].isChecked()
    assert not window.console_tab.motor_card.buttons["REV"].isChecked()
    window.close()
    worker.close()
    app.processEvents()


def test_completed_handshake_enables_every_gated_surface() -> None:
    app = _app()
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    firmware = FakeFirmware(worker)
    controller = Controller(worker)
    window = MainWindow(controller)
    window.show()

    assert worker.open("FAKE0", 115200)
    QTest.qWait(800)

    assert controller.is_handshake_ok
    assert window.console_tab.serial_bar.status_badge.text() == "CONNECTED"
    assert window.console_tab.charge_card._cells["LIGHTS"].toggle.isEnabled()
    assert window.passthrough_tab.panel.btn_uart2.isEnabled()
    assert not window.passthrough_tab.panel.send_btn.isEnabled()
    window.close()
    worker.close()
    firmware.deleteLater()
    app.processEvents()
