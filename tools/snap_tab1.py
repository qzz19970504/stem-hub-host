"""截图脚本: 启动 --fake 模式, 截 Tab1 截图."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stem_hub_host.controller import Controller
from stem_hub_host.app import get_app
from stem_hub_host.fake_firmware import FakeFirmware
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Codes\STM32\stem-hub-host\docs\dark_v5.png"
    color_scheme = sys.argv[2] if len(sys.argv) > 2 else "dark"

    app = get_app()
    app.setStyle("Fusion")

    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    fake = FakeFirmware(worker)
    worker.open("FAKE0", 115200)

    from PySide6.QtCore import QEventLoop
    loop = QEventLoop()
    worker.connected.connect(loop.quit)
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    controller = Controller(worker)
    win = MainWindow(controller)
    win.set_color_scheme(color_scheme, persist=False)
    win.show()

    def take_screenshot():
        from stem_hub_host.models import FaultState, MotorState, SenseData
        controller._latest_sense = SenseData(
            batt_ntc="42.5C", batt_v="37.0V",
            ntc1_c="38.1C", ntc2_c="51.2C", ntc3_c="45.8C",
            motor_i="14.2A", tick=12345, count=6789,
            stk_at=10, stk_sensor=20, stk_motor=30, tx_sp=40, tx_ls=50,
        )
        controller._latest_motor = MotorState(mode="FWD", current_ma=14200, overcurrent=0, fault=0)
        controller._latest_fault = FaultState(drv=0, aux=0)
        win._refresh_ui_from_state()
        win.console_tab.serial_bar.set_handshake_ok("release-v3.0")
        # 模拟握手门禁开启
        win._apply_handshake_gate(connected=True)
        # 模拟 toggle
        win.console_tab.charge_card.set_toggle("DRIVE", True)
        win.console_tab.charge_card.set_toggle("LIGHTS", True)
        # 故障灯
        c = win.console_tab.charge_card
        c.fault_overtemp.set_state("error")
        c.fault_overcurrent.set_state("warn")
        c.fault_undervoltage.set_state("ok")
        c.fault_drv.set_state("error")
        c.fault_aux.set_state("ok")
        at = win.console_tab.at_console
        at.append_log("TX", "AT+MODE=FWD")
        at.append_log("RX", "OK")
        at.append_log("TX", "AT+SPEED=1500")
        at.append_log("RX", "OK")
        at.append_log("TX", "AT+GET=VOLTAGE")
        at.append_log("RX", "37.0V")
        at.append_log("TX", "AT+GET=CURRENT")
        at.append_log("RX", "14.2A")
        at.append_log("TX", "AT+GET=TEMP_BAT")
        at.append_log("RX", "42.5C")
        at.append_info("Handshake OK: fw release-v3.0")
        # 多次 processEvents 让动画跑到目标值
        for _ in range(12):
            QApplication.processEvents()
            time.sleep(0.05)
        QApplication.processEvents()
        pixmap = win.grab()
        pixmap.save(out_path)
        print(f"saved → {out_path}")
        app.quit()

    QTimer.singleShot(800, take_screenshot)
    app.exec()


if __name__ == "__main__":
    main()
