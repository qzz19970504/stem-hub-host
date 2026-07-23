"""截图脚本: 未连接状态 (绿色按钮)."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stem_hub_host.controller import Controller
from stem_hub_host.app import get_app
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Codes\STM32\stem-hub-host\docs\dark_disconnected.png"
    color_scheme = sys.argv[2] if len(sys.argv) > 2 else "dark"

    app = get_app()
    app.setStyle("Fusion")

    # 不调用 worker.open → 保持未连接
    transport = FakeSerialTransport()
    worker = SerialWorker(transport)
    # 注意: 这里不创建 fake, 不打开 port, 保持 disconnected 状态

    controller = Controller(worker)
    win = MainWindow(controller)
    win.set_color_scheme(color_scheme, persist=False)
    win.show()

    def take_screenshot():
        # 不调 set_handshake_ok, 保持未连接
        # 显示一些 AT log 历史
        at = win.console_tab.at_console
        at.append_info("Awaiting serial connection…")
        for _ in range(5):
            QApplication.processEvents()
        pixmap = win.grab()
        pixmap.save(out_path)
        print(f"saved → {out_path}")
        app.quit()

    QTimer.singleShot(800, take_screenshot)
    app.exec()


if __name__ == "__main__":
    main()
