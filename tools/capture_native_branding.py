"""Capture the real Windows frame in both application color schemes."""
from __future__ import annotations

from pathlib import Path
import sys
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow


def _grab_complete_window(window: MainWindow):
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(
        wintypes.HWND(int(window.winId())),
        ctypes.byref(rect),
    ):
        raise OSError("GetWindowRect failed")

    # Windows returns physical coordinates for Qt's DPI-aware HWND, while
    # QScreen takes device-independent coordinates and returns a DPR pixmap.
    dpr = window.devicePixelRatioF()
    x = round(rect.left / dpr)
    y = round(rect.top / dpr)
    width = round((rect.right - rect.left) / dpr)
    height = round((rect.bottom - rect.top) / dpr)
    return window.screen().grabWindow(0, x, y, width, height)


def main() -> int:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    app = get_app()
    app.setStyle("Fusion")
    worker = SerialWorker(FakeSerialTransport())
    window = MainWindow(Controller(worker))
    window.set_color_scheme("dark", persist=False)
    window.show()

    def capture(scheme: str) -> None:
        window.set_color_scheme(scheme, persist=False)
        QApplication.processEvents()
        pixmap = _grab_complete_window(window)
        path = output_dir / f"iteration_native_titlebar_{scheme}.png"
        if not pixmap.save(str(path)):
            raise OSError(f"Unable to save {path}")
        print(f"saved -> {path} ({pixmap.width()}x{pixmap.height()})")

    def finish() -> None:
        capture("light")
        window.close()
        worker.close()
        app.quit()

    QTimer.singleShot(500, lambda: capture("dark"))
    QTimer.singleShot(900, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
