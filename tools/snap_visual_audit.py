"""Capture deterministic screenshots for secondary tabs and fullscreen layout."""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.models import FaultState, MotorState, SenseData
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow


def _seed_plot(window: MainWindow) -> None:
    buffer = window._data_buffer
    for index in range(180):
        seconds = index * 0.5
        values = {
            "batt_v": 36.4 + math.sin(index / 17) * 0.45,
            "batt_ntc": 41.0 + math.sin(index / 23) * 1.8,
            "ntc1_c": 38.0 + math.cos(index / 21) * 1.4,
            "ntc2_c": 50.0 + math.sin(index / 14) * 2.3,
            "ntc3_c": 45.0 + math.cos(index / 18) * 1.9,
            "motor_i": 12.0 + math.sin(index / 8) * 2.0,
        }
        for name, value in values.items():
            buffer.series[name].append(seconds, value)
    window.plot_tab.plot_widget.set_channels(("batt_v", "motor_i"))
    window.plot_tab.plot_widget.update_from_buffer()


def _seed_console(window: MainWindow) -> None:
    controller = window._controller
    controller._latest_sense = SenseData(
        batt_ntc="42.5C",
        batt_v="37.0V",
        ntc1_c="38.1C",
        ntc2_c="51.2C",
        ntc3_c="45.8C",
        motor_i="14.2A",
        tick=12345,
        count=6789,
        stk_at=10,
        stk_sensor=20,
        stk_motor=30,
        tx_sp=40,
        tx_ls=50,
    )
    controller._latest_motor = MotorState(
        mode="FWD",
        current_ma=14200,
        overcurrent=0,
        fault=0,
    )
    controller._latest_fault = FaultState(drv=0, aux=0)
    window._refresh_ui_from_state()
    window.console_tab.battery_card.ring.set_value(37.0, animate=False)
    window.console_tab.charge_card.set_toggle("DRIVE", True, animate=False)
    window.console_tab.charge_card.set_toggle("LIGHTS", True, animate=False)

    console = window.console_tab.at_console
    console.append_log("TX", "AT+MOTOR=FWD")
    console.append_log("RX", "OK")
    console.append_log("TX", "AT+GET=VOLTAGE")
    console.append_log("RX", "37.0V")
    console.append_info("handshake ok: firmware release-v3.0")


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs")
    color_scheme = sys.argv[2] if len(sys.argv) > 2 else "dark"
    output_dir.mkdir(parents=True, exist_ok=True)

    app = get_app()
    app.setStyle("Fusion")
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    window.set_color_scheme(color_scheme, persist=False)
    _seed_plot(window)
    _seed_console(window)
    window.passthrough_tab.panel.feed_rx(
        b"UART bridge ready\r\nRX 54 45 53 54\r\ntelemetry packet: ok\r\n"
    )
    window.show()
    window.console_tab.serial_bar.set_handshake_ok("release-v3.0")
    window._apply_handshake_gate(connected=True)

    captures = [
        (1, output_dir / "iteration_charts.png"),
        (2, output_dir / "iteration_passthrough.png"),
    ]

    def capture_next(index: int = 0) -> None:
        if index < len(captures):
            tab_index, path = captures[index]
            if tab_index == 2:
                window._on_passthrough_mode_changed("uart2")
            window.tabs.setCurrentIndex(tab_index)
            QApplication.processEvents()
            window.grab().save(str(path))
            print(f"saved -> {path}")
            QTimer.singleShot(120, lambda: capture_next(index + 1))
            return

        window.tabs.setCurrentIndex(0)
        window._on_passthrough_mode_changed("off")
        window.toggle_fullscreen()
        QTimer.singleShot(200, capture_fullscreen)

    fullscreen_captures = [
        (0, "off", output_dir / "iteration_console_fullscreen.png"),
        (1, "off", output_dir / "iteration_charts_fullscreen.png"),
        (2, "uart2", output_dir / "iteration_passthrough_fullscreen.png"),
    ]

    def capture_fullscreen(index: int = 0) -> None:
        tab_index, mode, path = fullscreen_captures[index]
        window._on_passthrough_mode_changed(mode)
        window.tabs.setCurrentIndex(tab_index)
        QApplication.processEvents()
        window.grab().save(str(path))
        print(f"saved -> {path}")
        if index + 1 < len(fullscreen_captures):
            QTimer.singleShot(120, lambda: capture_fullscreen(index + 1))
            return
        window.close()
        worker.close()
        app.quit()

    QTimer.singleShot(200, capture_next)
    app.exec()


if __name__ == "__main__":
    main()
