"""Deterministic visual-audit capture support.

The audit deliberately uses fixed logical sizes and seeded UI state.  It does
not connect to hardware, write application settings, or leave animations in an
intermediate frame.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtWidgets import QApplication

from .app import get_app
from .controller import Controller
from .models import FaultState, MotorState, SenseData
from .serial_worker import SerialWorker
from .transport import FakeSerialTransport
from .ui.main_window import MainWindow


TOOL_VERSION = 1
FIXED_VIEW_SIZE = (1600, 900)
FULLSCREEN_AUDIT_SIZE = (1920, 1080)
CONSOLE_TEMPERATURES = (12.0, 36.0, 58.0, 84.0, 47.0, 49.0)
SETTLED_CONSOLE_TEMPERATURES = CONSOLE_TEMPERATURES[:4]


@dataclass(frozen=True)
class VisualCapture:
    """Manifest entry for one deterministic screenshot."""

    id: str
    file: str
    sha256: str
    width: int
    height: int
    theme: str
    page: str
    state: str
    view: str
    tool_version: int = TOOL_VERSION


def _seed_plot(window: MainWindow) -> None:
    buffer = window._data_buffer
    for index in range(180):
        seconds = index * 0.5
        values = {
            "batt_v": 36.4 + math.sin(index / 17) * 0.45,
            "batt_ntc": 41.0 + math.sin(index / 23) * 1.8,
            "mcu_c": 38.0 + math.cos(index / 21) * 1.4,
            "lm51770_c": 50.0 + math.sin(index / 14) * 2.3,
            "mp4317_c": 45.0 + math.cos(index / 18) * 1.9,
            "drv8874_c": 47.0 + math.sin(index / 16) * 1.7,
            "charge_mos_c": 49.0 + math.cos(index / 19) * 2.1,
            "motor_i": 12.0 + math.sin(index / 8) * 2.0,
        }
        for name, value in values.items():
            buffer.series[name].append(seconds, value)
    window.plot_tab.plot_widget.set_channels(("batt_v", "motor_i"))
    window.plot_tab.plot_widget.update_from_buffer()


def _clear_console(window: MainWindow) -> None:
    console = window.console_tab.at_console
    console._entries.clear()
    console.log_view.clear()


def _seed_connected(window: MainWindow) -> None:
    controller = window._controller
    (
        battery_temperature,
        mcu_temperature,
        lm51770_temperature,
        mp4317_temperature,
        drv8874_temperature,
        charge_mos_temperature,
    ) = CONSOLE_TEMPERATURES
    sense = SenseData(
        batt_ntc=f"{battery_temperature:.1f}C",
        batt_v="37.0V",
        mcu_c=f"{mcu_temperature:.1f}C",
        lm51770_c=f"{lm51770_temperature:.1f}C",
        mp4317_c=f"{mp4317_temperature:.1f}C",
        drv8874_c=f"{drv8874_temperature:.1f}C",
        charge_mos_c=f"{charge_mos_temperature:.1f}C",
        motor_i="14.2A",
        tick=12345,
        count=6789,
        stk_at=10,
        stk_sensor=20,
        stk_motor=30,
        tx_sp=40,
        tx_ls=50,
    )
    controller._latest_sense = sense
    controller._latest_motor = MotorState(
        mode="FWD",
        current_ma=14200,
        overcurrent=0,
        fault=0,
    )
    controller._latest_fault = FaultState(drv=0, aux=0)
    window._refresh_ui_from_state()

    # Force every animated widget to its deterministic terminal state.
    battery_ring = window.console_tab.battery_card.ring
    battery_ring.set_value(37.0, animate=False)
    battery_ring._glow_anim.stop()
    battery_ring._set_glow_phase(0.5)
    for tile, value in zip(
        window.console_tab.temp_grid._tiles(),
        SETTLED_CONSOLE_TEMPERATURES,
    ):
        tile.set_value(value, animate=False)

    charge_card = window.console_tab.charge_card
    charge_card.clear_controls()
    charge_card.set_toggle("DRIVE", True, animate=False)
    charge_card.set_toggle("LIGHTS", True, animate=False)

    _clear_console(window)
    console = window.console_tab.at_console
    console.append_log("TX", "AT+MOTOR=FWD")
    console.append_log("RX", "OK")
    console.append_log("TX", "AT+GET=VOLTAGE")
    console.append_log("RX", "37.0V")
    console.append_info("Handshake OK: firmware release-v3.2")

    window.console_tab.serial_bar.set_handshake_ok("release-v3.2")
    window._apply_handshake_gate(connected=True)


def _seed_disconnected(window: MainWindow) -> None:
    controller = window._controller
    controller._latest_sense = None
    controller._latest_motor = None
    controller._latest_fault = None
    window.console_tab.serial_bar.set_disconnected()
    window.console_tab.battery_card.update_from_sense(None)
    window.console_tab.temp_grid.update_from_sense(None)
    window.console_tab.motor_card.update_state(None, None, 0, 0)
    window.console_tab.charge_card.clear_all()
    window._apply_handshake_gate(connected=False)
    _clear_console(window)
    window.console_tab.at_console.append_info(
        "Select a serial port, then connect to begin."
    )


def _capture(
    window: MainWindow,
    output_dir: Path,
    *,
    theme: str,
    page: str,
    state: str,
    view: str,
) -> VisualCapture:
    page_index = {"console": 0, "charts": 1, "passthrough": 2}[page]
    bridge_mode = "uart2" if page == "passthrough" else "off"
    window._on_passthrough_mode_changed(bridge_mode)
    window.tabs.setCurrentIndex(page_index)
    QApplication.processEvents()

    relative_path = Path(theme) / f"{view}-{page}-{state}.png"
    destination = output_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    pixmap = window.grab()
    if not pixmap.save(str(destination), "PNG"):
        raise RuntimeError(f"Could not save visual audit image: {destination}")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return VisualCapture(
        id=f"{theme}:{view}:{page}:{state}",
        file=relative_path.as_posix(),
        sha256=digest,
        width=pixmap.width(),
        height=pixmap.height(),
        theme=theme,
        page=page,
        state=state,
        view=view,
    )


def capture_visual_matrix(output_dir: Path) -> list[VisualCapture]:
    """Capture the complete dark/light, page, state, and viewport matrix."""

    output_dir.mkdir(parents=True, exist_ok=True)
    app = get_app()
    app.setStyle("Fusion")
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    _seed_plot(window)
    window.passthrough_tab.panel.feed_rx(
        b"UART bridge ready\r\nRX 54 45 53 54\r\ntelemetry packet: ok\r\n"
    )
    window.show()

    captures: list[VisualCapture] = []
    try:
        for color_scheme in ("dark", "light"):
            window.set_color_scheme(color_scheme, persist=False, animate=False)
            for view, size in (
                ("fixed", FIXED_VIEW_SIZE),
                ("fullscreen", FULLSCREEN_AUDIT_SIZE),
            ):
                window.resize(*size)
                QApplication.processEvents()
                _seed_connected(window)
                for page in ("console", "charts", "passthrough"):
                    captures.append(
                        _capture(
                            window,
                            output_dir,
                            theme=color_scheme,
                            page=page,
                            state="connected",
                            view=view,
                        )
                    )
                _seed_disconnected(window)
                captures.append(
                    _capture(
                        window,
                        output_dir,
                        theme=color_scheme,
                        page="console",
                        state="disconnected",
                        view=view,
                    )
                )
    finally:
        window.close()
        worker.close()
        app.processEvents()
    return captures


def write_manifest(
    output_dir: Path,
    captures: Iterable[VisualCapture],
) -> Path:
    """Write the stable, reviewable manifest beside its images."""

    manifest_path = output_dir / "manifest.json"
    payload = {
        "tool_version": TOOL_VERSION,
        "fixed_view_size": list(FIXED_VIEW_SIZE),
        "fullscreen_audit_size": list(FULLSCREEN_AUDIT_SIZE),
        "captures": [asdict(capture) for capture in captures],
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
