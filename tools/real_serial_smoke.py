"""Run the real PySide6 host stack against a connected STEM Hub."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtSerialPort import QSerialPort
from PySide6.QtWidgets import QApplication

from stem_hub_host.at_protocol import cmd_query_sense
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialSessionState, SerialWorker
from stem_hub_host.ui.main_window import MainWindow


DEFAULT_BAUD = 9600
DEFAULT_DURATION_SECONDS = 90.0
TRANSPARENT_FORWARD_PROBE = b"HOST-TRANS\x00\xffabc+++def"
TRANSPARENT_REVERSE_PROBE = b"MCU-TRANS\x00\xff"
TRANSPARENT_TARGET_UART_INDEX = {
    "uart2": 2,
    "uart3": 3,
}
HARDWARE_STEP_TIMEOUT_SECONDS = 3.0


def _wait_until(app: QApplication, predicate, description: str) -> None:
    deadline = time.monotonic() + HARDWARE_STEP_TIMEOUT_SECONDS
    while not predicate():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"timed out waiting for {description}")
        app.processEvents()
        time.sleep(0.005)


def _open_downstream_port(port_name: str) -> QSerialPort:
    port = QSerialPort()
    port.setPortName(port_name)
    port.setBaudRate(DEFAULT_BAUD)
    port.setDataBits(QSerialPort.DataBits.Data8)
    port.setParity(QSerialPort.Parity.NoParity)
    port.setStopBits(QSerialPort.StopBits.OneStop)
    port.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
    if not port.open(QSerialPort.OpenModeFlag.ReadWrite):
        raise RuntimeError(
            f"failed to open downstream {port_name}: {port.errorString()}"
        )
    return port


def _verify_transparent_passthrough(
    app: QApplication,
    worker: SerialWorker,
    controller: Controller,
    downstream_port_name: str,
    target: str,
) -> dict[str, object]:
    downstream = _open_downstream_port(downstream_port_name)
    forward_received = bytearray()
    reverse_received = bytearray()

    downstream.readyRead.connect(
        lambda: forward_received.extend(bytes(downstream.readAll()))
    )

    target_uart_index = TRANSPARENT_TARGET_UART_INDEX[target]

    def collect_reverse(uart_index: int, payload: bytes) -> None:
        if uart_index == target_uart_index:
            reverse_received.extend(payload)

    worker.uart_rx_received.connect(collect_reverse)
    try:
        downstream.clear()
        controller.set_passthrough(target)
        _wait_until(
            app,
            lambda: controller.passthrough_mode == target,
            f"{target.upper()} transparent entry",
        )

        if not controller.send_passthrough_bytes(TRANSPARENT_FORWARD_PROBE):
            raise RuntimeError(f"host rejected {target.upper()} forward probe")
        _wait_until(
            app,
            lambda: len(forward_received) >= len(TRANSPARENT_FORWARD_PROBE),
            f"{target.upper()} forward bytes",
        )
        if bytes(forward_received) != TRANSPARENT_FORWARD_PROBE:
            raise RuntimeError(
                f"{target.upper()} forward mismatch: "
                f"{bytes(forward_received).hex(' ').upper()}"
            )

        if downstream.write(TRANSPARENT_REVERSE_PROBE) != len(
            TRANSPARENT_REVERSE_PROBE
        ):
            raise RuntimeError(
                f"downstream {target.upper()} write was incomplete"
            )
        if not downstream.waitForBytesWritten(1000):
            raise RuntimeError(
                f"downstream {target.upper()} write failed: "
                f"{downstream.errorString()}"
            )
        _wait_until(
            app,
            lambda: len(reverse_received) >= len(TRANSPARENT_REVERSE_PROBE),
            f"{target.upper()} reverse event",
        )
        if bytes(reverse_received) != TRANSPARENT_REVERSE_PROBE:
            raise RuntimeError(
                f"{target.upper()} reverse mismatch: "
                f"{bytes(reverse_received).hex(' ').upper()}"
            )

        controller.set_passthrough("off")
        _wait_until(
            app,
            lambda: (
                controller.passthrough_mode == "off"
                and worker.session_state is SerialSessionState.AT
            ),
            "guarded transparent exit",
        )
        sense = worker.send_and_wait(cmd_query_sense(), timeout_ms=1500)
        if sense.sense is None:
            raise RuntimeError("AT+SENSE? did not recover after transparent exit")
        return {
            f"{target}_forward": bytes(forward_received).hex().upper(),
            f"{target}_reverse": bytes(reverse_received).hex().upper(),
            "guarded_exit": True,
            "sense_after_exit": True,
        }
    finally:
        if controller.passthrough_mode != "off" and worker.is_open():
            controller.set_passthrough("off")
            try:
                _wait_until(
                    app,
                    lambda: controller.passthrough_mode == "off",
                    "cleanup transparent exit",
                )
            except RuntimeError:
                worker.close()
        downstream.close()


def run(
    port_name: str,
    duration_seconds: float,
    downstream_port_name: str | None = None,
    target: str = "uart3",
) -> None:
    """Exercise handshake, polling, parser, controller, and UI bindings."""
    app = QApplication.instance() or QApplication([])
    worker = SerialWorker()
    controller = Controller(worker)
    window = MainWindow(controller)
    errors: list[str] = []
    unexpected_disconnects: list[bool] = []
    handshake_failures: list[str] = []

    worker.error_occurred.connect(errors.append)
    worker.disconnected.connect(lambda: unexpected_disconnects.append(True))
    controller.handshake_failed.connect(handshake_failures.append)

    if not worker.open(port_name, DEFAULT_BAUD):
        raise RuntimeError(f"failed to open {port_name}")

    QTimer.singleShot(round(duration_seconds * 1000), app.quit)
    app.exec()

    uart3_result: dict[str, object] = {}
    if controller.is_handshake_ok and downstream_port_name is not None:
        uart3_result = _verify_transparent_passthrough(
            app,
            worker,
            controller,
            downstream_port_name,
            target,
        )

    latest = controller.get_latest()
    console_text = window.console_tab.at_console.log_view.toPlainText()
    result = {
        "port_open": worker.is_open(),
        "handshake_ok": controller.is_handshake_ok,
        "unexpected_disconnects": len(unexpected_disconnects),
        "handshake_failures": handshake_failures,
        "errors": errors,
        "passthrough_rx_bytes": window.passthrough_tab.panel._rx_bytes,
        "has_replacement_character": "\ufffd" in console_text,
        "has_sense": latest["sense"] is not None,
        "has_fault": latest["fault"] is not None,
        "has_motor": latest["motor"] is not None,
        **uart3_result,
    }
    print(result)

    worker.close()
    window.close()
    app.processEvents()

    failed_checks = [
        key for key, value in result.items()
        if key in {"port_open", "handshake_ok", "has_sense", "has_fault", "has_motor"}
        and not value
    ]
    if result["unexpected_disconnects"]:
        failed_checks.append("unexpected_disconnects")
    if result["handshake_failures"]:
        failed_checks.append("handshake_failures")
    expected_passthrough_rx = (
        len(TRANSPARENT_REVERSE_PROBE)
        if downstream_port_name is not None
        else 0
    )
    if result["passthrough_rx_bytes"] != expected_passthrough_rx:
        failed_checks.append("passthrough_rx_bytes")
    if result["has_replacement_character"]:
        failed_checks.append("has_replacement_character")
    if errors:
        failed_checks.append("errors")
    if failed_checks:
        raise RuntimeError(f"real serial smoke failed: {failed_checks}")


def parse_args() -> argparse.Namespace:
    """Parse connected test parameters."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM12")
    parser.add_argument(
        "--downstream-port",
        help="optional downstream adapter for bidirectional transparent smoke",
    )
    parser.add_argument(
        "--target",
        choices=tuple(TRANSPARENT_TARGET_UART_INDEX),
        default="uart3",
        help="transparent target wired to --downstream-port",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=DEFAULT_DURATION_SECONDS,
    )
    return parser.parse_args()


def main() -> int:
    """Run the connected smoke test with a process-compatible result."""
    options = parse_args()
    try:
        run(
            options.port,
            options.duration_seconds,
            options.downstream_port,
            options.target,
        )
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: real host serial smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
