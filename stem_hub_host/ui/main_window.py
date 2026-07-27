"""Main window and controller-to-UI state binding."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..at_protocol import cmd_query_diag, cmd_query_sense
from ..branding import APP_DISPLAY_NAME, load_app_icon
from ..controller import Controller
from . import native_chrome
from .stylesheet import apply_to
from .tab1_console import ConsoleTab
from .tab2_plot import PlotTab
from .tab3_passthrough import PassthroughTab
from . import theme
from .widgets.battery_card import parse_celsius, parse_volts
from .widgets.serial_bar import SerialBar
from .widgets.theme_toggle import ThemeToggleButton


CHARGE_TOGGLE_MAP = {
    "CHARGE":    "charge",
    "DISCHARGE": "discharge",
}
AUX_TOGGLE_MAP = {
    "NMOS1": "nmos1",
    "NMOS2": "nmos2",
    "LIGHTS": "light",
}


WINDOW_W = theme.WINDOW_WIDTH
WINDOW_H = theme.WINDOW_HEIGHT
QT_WIDGET_SIZE_LIMIT = (1 << 24) - 1


class MainWindow(QMainWindow):
    """上位机主窗口."""

    def __init__(self, controller: Controller) -> None:
        super().__init__()
        self._controller = controller
        self._data_buffer = controller.get_data_buffer()
        self._handshake_connected = False
        self._charge_transition_active = False
        self._passthrough_transition_active = False
        self._passthrough_mode = "off"
        self._appearance_settings = QSettings()
        saved_scheme = str(
            self._appearance_settings.value("appearance/colorScheme", "dark")
        )
        if saved_scheme not in {"dark", "light"}:
            saved_scheme = "dark"
        theme.set_color_scheme(saved_scheme)
        self.color_scheme = saved_scheme
        self._normal_geometry = None
        self._was_maximized_before_fullscreen = False

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(load_app_icon())

        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.setMaximumSize(QT_WIDGET_SIZE_LIMIT, QT_WIDGET_SIZE_LIMIT)
        self.resize(WINDOW_W, WINDOW_H)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)

        # 状态栏 (隐藏 — 设计稿没有)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setFixedHeight(0)
        self.statusBar().setVisible(False)

        self.root = QFrame(self)
        self.root.setObjectName("rootContainer")
        self.setCentralWidget(self.root)
        self.design_canvas = self.root

        root_lay = QVBoxLayout(self.root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 顶部: Tab (无全屏按钮)
        self.tabs = QTabWidget(self.root)
        self.console_tab = ConsoleTab(data_buffer=self._data_buffer)
        self.plot_tab = PlotTab(data_buffer=self._data_buffer)
        self.passthrough_tab = PassthroughTab()
        self.tabs.addTab(self.console_tab, "CONSOLE")
        self.tabs.addTab(self.plot_tab, "CHARTS")
        self.tabs.addTab(self.passthrough_tab, "PASSTHROUGH")
        self.serial_bar = SerialBar(self.tabs)
        self.console_tab.serial_bar = self.serial_bar
        self.theme_toggle = ThemeToggleButton(self.color_scheme, self.tabs)
        self.theme_toggle.scheme_changed.connect(self.set_color_scheme)
        root_lay.addWidget(self.tabs)
        self.tabs.installEventFilter(self)
        self.tabs.tabBar().installEventFilter(self)
        QTimer.singleShot(0, self._position_theme_toggle)

        # ---- UI signal -> Controller ----
        self.serial_bar.open_requested.connect(self._on_open_serial)
        self.serial_bar.close_requested.connect(self._on_close_serial)
        self.serial_bar.refresh_requested.connect(self.serial_bar.refresh_ports)
        self.console_tab.motor_cmd.connect(self._controller.set_motor)
        self.console_tab.toggle_changed.connect(self._on_toggle_changed)
        self.console_tab.charge_card.all_off_clicked.connect(
            self._on_all_outputs_off
        )
        self.console_tab.at_send.connect(self._on_at_send)

        # ---- Controller -> UI ----
        self._controller.worker.connected.connect(self._on_worker_connected)
        self._controller.worker.disconnected.connect(self._on_worker_disconnected)
        self._controller.error_occurred.connect(self._on_worker_error)
        self._controller.handshake_failed.connect(self._on_handshake_failed)
        self._controller.worker.response_received.connect(self._on_response)
        self._controller.worker.passthrough_received.connect(self._on_passthrough)
        self._controller.worker.uart_rx_received.connect(self._on_uart_rx)
        self._controller.worker.at_data_received.connect(self._on_at_data)
        self._controller.passthrough_tx_confirmed.connect(
            self.passthrough_tab.panel.confirm_tx_sent
        )
        self._controller.output_command_failed.connect(
            self._on_output_command_failed
        )
        self._controller.motor_command_failed.connect(
            self._on_motor_command_failed
        )
        self._controller.charge_transition_changed.connect(
            self._on_charge_transition_changed
        )
        self._controller.passthrough_mode_changed.connect(
            self._on_passthrough_mode_changed
        )
        self._controller.passthrough_transition_changed.connect(
            self._on_passthrough_transition_changed
        )

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui_from_state)
        self._ui_timer.start(100)

        self.plot_tab.hz_spin.valueChanged.connect(self._controller.set_sense_hz)
        self._controller.sense_request_hz_changed.connect(
            self.plot_tab.set_sample_rate
        )
        self.passthrough_tab.panel.bridge_changed.connect(self._controller.set_passthrough)
        self.passthrough_tab.panel.tx_requested.connect(self._on_passthrough_tx)

        from ..app import get_app
        apply_to(get_app())
        QTimer.singleShot(0, self._apply_native_title_bar)

        # 初始: 未连接 → 所有交互禁用
        self._apply_handshake_gate(connected=False)

    def set_color_scheme(self, scheme: str, *, persist: bool = True) -> None:
        """Switch the complete application palette without losing UI state."""

        if scheme not in {"dark", "light"}:
            return
        theme.set_color_scheme(scheme)
        self.color_scheme = scheme
        self.theme_toggle.set_color_scheme(scheme)
        from ..app import get_app
        apply_to(get_app())
        native_chrome.apply_windows_title_bar(self, scheme)

        for widget in self.findChildren(QWidget):
            refresh = getattr(widget, "refresh_theme", None)
            if callable(refresh):
                refresh()
            widget.update()
        self._refresh_ui_from_state()
        if persist:
            self._appearance_settings.setValue("appearance/colorScheme", scheme)

    def _apply_native_title_bar(self) -> None:
        """Synchronize the Windows caption after its native handle exists."""

        native_chrome.apply_windows_title_bar(self, self.color_scheme)

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen while restoring the previous normal window state."""

        if self.isFullScreen():
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()
                if self._normal_geometry is not None:
                    self.setGeometry(self._normal_geometry)
            return

        self._was_maximized_before_fullscreen = self.isMaximized()
        if not self._was_maximized_before_fullscreen:
            self._normal_geometry = self.geometry()
        self.showFullScreen()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if (
            watched in (self.tabs, self.tabs.tabBar())
            and event.type() == QEvent.Type.Resize
        ):
            self._position_theme_toggle()
            return super().eventFilter(watched, event)

        if event.type() != QEvent.Type.MouseButtonDblClick:
            return super().eventFilter(watched, event)

        tab_bar = self.tabs.tabBar()
        if watched is tab_bar and tab_bar.tabAt(event.position().toPoint()) >= 0:
            return super().eventFilter(watched, event)
        if watched is self.tabs or watched is tab_bar:
            self.toggle_fullscreen()
            return True
        return super().eventFilter(watched, event)

    def _position_theme_toggle(self) -> None:
        """Place persistent serial and theme controls in the tab header."""

        if not hasattr(self, "theme_toggle") or not hasattr(self, "serial_bar"):
            return
        tab_bar = self.tabs.tabBar()
        toggle_x = max(
            0,
            self.tabs.width() - self.theme_toggle.width() - theme.PAGE_MARGIN_X,
        )
        serial_x = (
            toggle_x
            - theme.SERIAL_HEADER_GAP
            - self.serial_bar.width()
        )
        header_height = max(tab_bar.height(), theme.SERIAL_HEADER_HEIGHT)
        serial_y = max(
            0,
            (header_height - self.serial_bar.height()) // 2,
        )
        toggle_y = max(
            0,
            (header_height - self.theme_toggle.height()) // 2,
        )
        self.serial_bar.move(serial_x, serial_y)
        self.theme_toggle.move(toggle_x, toggle_y)
        self.serial_bar.show()
        self.serial_bar.raise_()
        self.theme_toggle.raise_()

    # ---- 握手门禁 ----
    def _apply_handshake_gate(self, connected: bool) -> None:
        """握手成功后才启用设备控制。"""
        self._handshake_connected = connected
        self._refresh_control_gates()

    def _on_charge_transition_changed(self, active: bool) -> None:
        self._charge_transition_active = active
        self._refresh_control_gates()

    def _on_passthrough_transition_changed(self, active: bool) -> None:
        self._passthrough_transition_active = active
        self._refresh_control_gates()

    def _on_passthrough_mode_changed(self, mode: str) -> None:
        self._passthrough_mode = mode
        self.passthrough_tab.panel.set_bridge_mode(mode)
        self._refresh_control_gates()

    def _refresh_control_gates(self) -> None:
        standard_enabled = (
            self._handshake_connected
            and self._passthrough_mode == "off"
            and not self._passthrough_transition_active
        )
        self.console_tab.motor_card.set_enabled(standard_enabled)
        self.console_tab.charge_card.set_enabled(
            standard_enabled and not self._charge_transition_active
        )
        self.console_tab.at_console.input_edit.setEnabled(standard_enabled)
        self.console_tab.at_console.send_btn.setEnabled(standard_enabled)

        bridge_enabled = (
            self._handshake_connected
            and not self._charge_transition_active
            and not self._passthrough_transition_active
        )
        tx_enabled = (
            self._handshake_connected
            and self._passthrough_mode != "off"
            and not self._passthrough_transition_active
        )
        panel = self.passthrough_tab.panel
        panel.set_bridge_controls_enabled(bridge_enabled)
        panel.set_tx_controls_enabled(tx_enabled)

    # ---- 串口 ----
    def _on_open_serial(self, port: str, baud: int) -> None:
        if not self._controller.open(port, baud):
            self.serial_bar.set_disconnected()
            self.console_tab.at_console.append_error(f"Open failed: {port}")
            QMessageBox.warning(
                self,
                "连接失败",
                f"无法打开串口 {port}。\n\n请检查端口是否被占用后重试。",
            )

    def _on_close_serial(self) -> None:
        self._controller.close()

    def _on_at_send(self, cmd: str) -> None:
        self._controller.send_raw(cmd)

    def _on_passthrough_tx(self, data: bytes) -> None:
        if not self._controller.send_passthrough_bytes(data):
            self._on_worker_error("Pass-through send failed: not connected")

    def _on_output_command_failed(
        self,
        control: str,
        requested_state: bool,
        reason: str,
    ) -> None:
        self.console_tab.charge_card.set_toggle(
            control,
            not requested_state,
            animate=False,
        )

    def _on_motor_command_failed(
        self,
        requested_mode: str,
        confirmed_mode: str,
        reason: str,
    ) -> None:
        motor = self._controller.get_latest()["motor"]
        self.console_tab.motor_card.update_state(
            confirmed_mode or None,
            motor.current_ma if motor is not None else None,
            motor.overcurrent if motor is not None else 0,
            motor.fault if motor is not None else 0,
        )

    def _on_handshake_failed(self, reason: str) -> None:
        self._apply_handshake_gate(connected=False)
        self.console_tab.at_console.append_error(f"连接失败: {reason}")
        QMessageBox.warning(
            self,
            "连接失败",
            "串口已打开，但未能在 5 秒内完成设备握手。\n"
            f"原因：{reason}\n\n"
            "请检查端口、波特率和下位机状态后重试。",
        )

    def _on_toggle_changed(self, name: str, on: bool) -> None:
        c = self.console_tab.charge_card
        if name in CHARGE_TOGGLE_MAP:
            mode = CHARGE_TOGGLE_MAP[name]
            if on:
                for other in CHARGE_TOGGLE_MAP:
                    if other != name and c.is_on(other):
                        c.set_toggle(other, False)
                self._controller.set_charge_mode(mode)
            else:
                self._controller.set_charge_mode("off")
        elif name in AUX_TOGGLE_MAP:
            tag = AUX_TOGGLE_MAP[name]
            if tag == "nmos1":
                self._controller.set_nmos(1, on)
            elif tag == "nmos2":
                self._controller.set_nmos(2, on)
            elif tag == "light":
                self._controller.set_led(on)
        else:
            self._on_worker_error(f"Unknown toggle: {name}")

    def _on_all_outputs_off(self) -> None:
        """Close every controllable power output in deterministic safe order."""

        self._controller.set_all_outputs_off()
        self.console_tab.charge_card.clear_controls()

    def _on_worker_connected(self, port: str, baud: int) -> None:
        self.serial_bar.set_connected(port, baud)
        self.console_tab.at_console.append_info(f"Opened: {port} @ {baud}")

    def _on_worker_disconnected(self) -> None:
        self.serial_bar.set_disconnected()
        self.console_tab.at_console.append_info("Disconnected")
        self.console_tab.battery_card.update_from_sense(None)
        self.console_tab.temp_grid.update_from_sense(None)
        self.console_tab.motor_card.update_state(None, None, 0, 0)
        self.console_tab.charge_card.clear_all()
        self._apply_handshake_gate(connected=False)

    def _on_worker_error(self, msg: str) -> None:
        self.console_tab.at_console.append_error(msg)

    def _on_response(self, cmd: str, resp) -> None:
        if cmd.strip().startswith("AT+VERSION?") and resp.version is not None:
            self.serial_bar.set_handshake_ok(resp.version.version)
            self.console_tab.at_console.append_info(f"Handshake OK: fw {resp.version.version}")
            self._apply_handshake_gate(connected=True)
            return
        if resp.ok:
            self.console_tab.at_console.append_log("RX", "OK")
        elif resp.error is not None:
            self.console_tab.at_console.append_error(f"{cmd.strip()} → {resp.error}")

    def _on_at_data(self, cmd: str, resp) -> None:
        self.console_tab.at_console.append_log("RX", resp.raw_line)
        if resp.fault is not None:
            self.console_tab.charge_card.update_fault(drv=resp.fault.drv, aux=resp.fault.aux)

    def _on_passthrough(self, data: bytes) -> None:
        if self._controller.passthrough_mode == "off":
            return
        self.passthrough_tab.panel.feed_rx(data)
        display = self._format_serial_payload(data)
        self.console_tab.at_console.append_log("RX", f"[pass] {display}")

    def _on_uart_rx(self, uart_index: int, data: bytes) -> None:
        if self._controller.passthrough_mode == "off":
            return
        self.passthrough_tab.panel.feed_rx(data)
        display = self._format_serial_payload(data)
        self.console_tab.at_console.append_log("RX", f"[UART{uart_index}] {display}")

    @staticmethod
    def _format_serial_payload(data: bytes) -> str:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return data.hex(" ").upper()
        if all(character.isprintable() or character in "\r\n\t" for character in text):
            return text
        return data.hex(" ").upper()

    def _refresh_ui_from_state(self) -> None:
        latest = self._controller.get_latest()
        if latest["sense"] is not None:
            self.console_tab.battery_card.update_from_sense(latest["sense"])
            self.console_tab.temp_grid.update_from_sense(latest["sense"])
        if latest["motor"] is not None:
            m = latest["motor"]
            self.console_tab.motor_card.update_state(
                m.mode, m.current_ma, m.overcurrent, m.fault
            )
        if latest["fault"] is not None:
            self.console_tab.charge_card.update_fault(
                drv=latest["fault"].drv, aux=latest["fault"].aux
            )
        self._refresh_derived_faults(latest["sense"], latest["motor"])
        self.plot_tab.plot_widget.update_from_buffer()

    def _refresh_derived_faults(self, sense, motor) -> None:
        fault_updates: dict[str, bool] = {}
        if sense is not None:
            temperatures = (
                parse_celsius(sense.batt_ntc),
                parse_celsius(sense.ntc1_c),
                parse_celsius(sense.ntc2_c),
                parse_celsius(sense.ntc3_c),
            )
            valid_temperatures = [
                temperature
                for temperature in temperatures
                if temperature is not None
            ]
            fault_updates["overtemp"] = any(
                temperature >= theme.TEMP_DANGER_C
                for temperature in valid_temperatures
            )
            battery_voltage = parse_volts(sense.batt_v)
            if battery_voltage is not None:
                fault_updates["undervoltage"] = (
                    battery_voltage < theme.BATTERY_WARN_V
                )
        if motor is not None:
            fault_updates["overcurrent"] = bool(motor.overcurrent)
        if fault_updates:
            self.console_tab.charge_card.update_fault(**fault_updates)
