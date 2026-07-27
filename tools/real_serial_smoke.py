"""Run the real PySide6 host stack against a connected STEM Hub."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.ui.main_window import MainWindow


DEFAULT_BAUD = 115200
DEFAULT_DURATION_SECONDS = 90.0


def run(port_name: str, duration_seconds: float) -> None:
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
    if result["passthrough_rx_bytes"]:
        failed_checks.append("passthrough_rx_bytes")
    if result["has_replacement_character"]:
        failed_checks.append("has_replacement_character")
    if any("命令响应超时" in error for error in errors):
        failed_checks.append("command_timeout")
    if failed_checks:
        raise RuntimeError(f"real serial smoke failed: {failed_checks}")


def parse_args() -> argparse.Namespace:
    """Parse connected test parameters."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM12")
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
        run(options.port, options.duration_seconds)
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: real host serial smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
