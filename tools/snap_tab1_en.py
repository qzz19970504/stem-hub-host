"""截图脚本: 启动 --fake 模式, 截 Tab1 截图 (英文版避免 CJK 字体问题)."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stem_hub_host.controller import Controller
from stem_hub_host.app import get_app
from stem_hub_host.fake_firmware import FakeFirmware
from stem_hub_host.models import FaultState, MotorState, SenseData
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow
from stem_hub_host.ui import theme


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Codes\STM32\stem-hub-host\docs\dark_v3.png"

    app = get_app()
    app.setStyle("Fusion")

    # Worker + fake
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    fake = FakeFirmware(worker)
    worker.open("FAKE0", 115200)
    loop = QEventLoop()
    worker.connected.connect(loop.quit)
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    controller = Controller(worker)
    win = MainWindow(controller)
    win.show()

    def take_screenshot():
        controller._latest_sense = SenseData(
            batt_ntc="42.5C", batt_v="37.0V",
            mcu_c="38.1C", lm51770_c="51.2C", mp4317_c="45.8C",
            drv8874_c="47.3C", charge_mos_c="49.4C",
            motor_i="14.2A", tick=12345, count=6789,
            stk_at=10, stk_sensor=20, stk_motor=30, tx_sp=40, tx_ls=50,
        )
        controller._latest_motor = MotorState(mode="FWD", current_ma=14200, overcurrent=0, fault=0)
        controller._latest_fault = FaultState(drv=0, aux=0)
        win._refresh_ui_from_state()
        win.console_tab.serial_bar.set_handshake_ok("release-v3.2")
        win._apply_handshake_gate(connected=True)
        win.console_tab.charge_card.set_toggle("DRIVE", True)
        win.console_tab.charge_card.set_toggle("LIGHTS", True)
        win.console_tab.battery_card.ring.set_value(37.0, animate=False)

        at = win.console_tab.at_console
        at.append_log("TX", "AT+MOTOR=FWD")
        at.append_log("RX", "OK")
        at.append_log("TX", "AT+GET=VOLTAGE")
        at.append_log("RX", "37.0V")
        at.append_log("TX", "AT+GET=CURRENT")
        at.append_log("RX", "14.2A")
        at.append_log("TX", "AT+GET=TEMP_BAT")
        at.append_log("RX", "42.5C")
        at.append_info("handshake ok: firmware release-v3.2")

        QApplication.processEvents()
        # 等待事件循环跑几帧确保 paint 完成
        for _ in range(5):
            QApplication.processEvents()
        pixmap = win.grab()
        pixmap.save(out_path)
        print(f"saved -> {out_path}")
        app.quit()

    QTimer.singleShot(500, take_screenshot)
    app.exec()


if __name__ == "__main__":
    main()
