"""Tab 1: 控制台 — 第三轮 (顶 60% / 底 40% 高度)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..data_buffer import DataBuffer
from .widgets.at_console import AtConsole
from .widgets.battery_card import BatteryCard
from .widgets.charge_mode_card import ChargeModeCard
from .widgets.motor_card import MotorCard
from .widgets.serial_bar import SerialBar
from .widgets.temp_grid import TempGridCard
from . import theme


class ConsoleTab(QWidget):
    """Tab 1 — 控制台."""

    open_serial = Signal(str, int)
    close_serial = Signal()
    refresh_serial = Signal()
    motor_cmd = Signal(str)
    toggle_changed = Signal(str, bool)
    at_send = Signal(str)

    def __init__(
        self,
        data_buffer: DataBuffer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
            theme.PAGE_MARGIN_X,
            theme.PAGE_MARGIN_Y,
        )
        outer.setSpacing(theme.SERIAL_GRID_GAP)

        # 顶部 SerialBar
        self.serial_bar = SerialBar()
        self.serial_bar.open_requested.connect(self.open_serial)
        self.serial_bar.close_requested.connect(self.close_serial)
        self.serial_bar.refresh_requested.connect(self.refresh_serial)
        outer.addWidget(self.serial_bar)

        # 主区: 2x3 网格, 上下行比例 60:40
        self.grid = QGridLayout()
        self.grid.setSpacing(theme.GRID_GAP)
        outer.addLayout(self.grid, 1)

        self.battery_card = BatteryCard()
        self.motor_card = MotorCard()
        self.charge_card = ChargeModeCard()
        self.temp_grid = TempGridCard()
        self.at_console = AtConsole()

        # QGridLayout includes each widget's sizeHint before applying stretch.
        # Ignore horizontal hints so the reference 1:1.26:1 geometry remains exact.
        for c in (self.battery_card, self.motor_card, self.charge_card,
                  self.temp_grid, self.at_console):
            c.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        # 第一行 3 卡
        self.grid.addWidget(self.battery_card, 0, 0)
        self.grid.addWidget(self.motor_card,    0, 1)
        self.grid.addWidget(self.charge_card,   0, 2)
        # 第二行: 温度 + AT 终端
        self.grid.addWidget(self.temp_grid,     1, 0)
        self.grid.addWidget(self.at_console,    1, 1, 1, 2)

        self.grid.setColumnStretch(0, theme.COLUMN_STRETCH_LEFT)
        self.grid.setColumnStretch(1, theme.COLUMN_STRETCH_CENTER)
        self.grid.setColumnStretch(2, theme.COLUMN_STRETCH_RIGHT)
        self.grid.setRowStretch(0, theme.TOP_ROW_STRETCH)
        self.grid.setRowStretch(1, theme.BOTTOM_ROW_STRETCH)

        # 信号
        self.motor_card.sleep_clicked.connect(lambda: self.motor_cmd.emit("SLEEP"))
        self.motor_card.wake_clicked.connect(lambda: self.motor_cmd.emit("WAKE"))
        self.motor_card.fwd_clicked.connect(lambda: self.motor_cmd.emit("FWD"))
        self.motor_card.rev_clicked.connect(lambda: self.motor_cmd.emit("REV"))
        self.motor_card.brake_clicked.connect(lambda: self.motor_cmd.emit("BRAKE"))
        self.motor_card.stop_clicked.connect(lambda: self.motor_cmd.emit("STOP"))

        self.charge_card.toggle_changed.connect(self.toggle_changed)
        self.at_console.send_requested.connect(self.at_send)
