"""实时折线图 widget (pyqtgraph).

可配置:
- visible_channels: 显示哪些通道
- compact: True = 紧凑 (Tab1 底部), False = 全屏 (Tab2)

用法:
    plot = PlotWidget(compact=True)
    plot.set_channels(['batt_v', 'ntc1_c'])
    plot.update_from_buffer(buffer)  # 每次新数据来时调
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ...data_buffer import DataBuffer


# pyqtgraph 全局: 深色背景
pg.setConfigOption("background", theme.BG_CARD)
pg.setConfigOption("foreground", theme.FG_SECONDARY)
pg.setConfigOptions(antialias=True)


class PlotWidget(QFrame):
    """实时折线图."""

    def __init__(
        self,
        buffer: DataBuffer,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._buffer = buffer
        self._compact = compact
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._visible: set[str] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8 if compact else 14, 6 if compact else 12, 8 if compact else 14, 8 if compact else 12)
        outer.setSpacing(4 if compact else 8)

        # 顶部: 标题 + 通道复选 (非 compact 才显示)
        if not compact:
            title = QLabel("TELEMETRY CHANNELS")
            title.setObjectName("sectionTitle")
            outer.addWidget(title)

        # 通道选择行
        ch_row = QHBoxLayout()
        ch_row.setSpacing(10)
        outer.addLayout(ch_row)

        self._channel_checks: dict[str, QCheckBox] = {}
        for name, (color, unit) in DataBuffer.CHANNELS.items():
            cb = QCheckBox(f"{name.replace('_', ' ').upper()}")
            cb.setObjectName("channelChip")
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setChecked(name == "batt_v")  # 默认只显示电压
            cb.toggled.connect(self._on_channel_toggled)
            self._channel_checks[name] = cb
            ch_row.addWidget(cb)
        ch_row.addStretch(1)

        # pyqtgraph plot widget
        self._plot = pg.PlotWidget()
        self._plot.setBackground(theme.BG_PLOT)
        self._plot.setMouseEnabled(x=True, y=False)  # 横向缩放, 纵向固定
        self._plot.showGrid(x=True, y=True, alpha=0.16)
        self._plot.setLabel("left", "VALUE")
        self._plot.setLabel("bottom", "TIME", units="s")
        self._plot.disableAutoRange(axis="x")
        self._apply_time_range()
        for axis_name in ("bottom", "left"):
            axis = self._plot.getAxis(axis_name)
            axis.setPen(pg.mkPen(theme.BORDER_LIGHT))
            axis.setTextPen(pg.mkPen(theme.FG_SECONDARY))
            axis.setStyle(tickFont=QFont(theme.FONT_MONO, 9))
        if compact:
            self._plot.setMinimumHeight(140)
        else:
            self._plot.setMinimumHeight(360)
        outer.addWidget(self._plot, 1)

        # 初始化可见
        for name, cb in self._channel_checks.items():
            if cb.isChecked():
                self._show_channel(name)

    def set_channels(self, names: Iterable[str]) -> None:
        """以编程方式设置可见通道."""
        for name, cb in self._channel_checks.items():
            cb.blockSignals(True)
            cb.setChecked(name in set(names))
            cb.blockSignals(False)
        self._rebuild_curves()

    def _on_channel_toggled(self, checked: bool) -> None:
        sender = self.sender()
        if not isinstance(sender, QCheckBox):
            return
        # 找 name
        for name, cb in self._channel_checks.items():
            if cb is sender:
                if checked:
                    self._show_channel(name)
                else:
                    self._hide_channel(name)
                break

    def _show_channel(self, name: str) -> None:
        if name in self._visible:
            return
        color, _ = DataBuffer.CHANNELS[name]
        pen = pg.mkPen(color=color, width=2)
        curve = self._plot.plot([], [], pen=pen, name=name)
        self._curves[name] = curve
        self._visible.add(name)
        self._redraw_channel(name)

    def _hide_channel(self, name: str) -> None:
        if name not in self._curves:
            return
        self._plot.removeItem(self._curves[name])
        del self._curves[name]
        self._visible.discard(name)

    def _rebuild_curves(self) -> None:
        for name in list(self._curves.keys()):
            self._hide_channel(name)
        for name, cb in self._channel_checks.items():
            if cb.isChecked():
                self._show_channel(name)

    def update_from_buffer(self) -> None:
        """重画所有可见曲线 (从 buffer 读)."""
        for name in list(self._visible):
            self._redraw_channel(name)

    def _redraw_channel(self, name: str) -> None:
        if name not in self._curves:
            return
        s = self._buffer.series[name]
        if not s.times:
            self._curves[name].setData([], [])
            return
        t, v = s.as_arrays()
        # 时间归一化: 最新时间为 0, 之前的为负
        t_rel = t - t[-1]
        self._curves[name].setData(t_rel, v)
        self._apply_time_range()

    def _apply_time_range(self) -> None:
        """Keep every sampling rate on the same real five-minute timebase."""

        self._plot.setXRange(
            -DataBuffer.WINDOW_SECONDS,
            0.0,
            padding=0,
        )

    def reset(self) -> None:
        """清空数据 + 重画."""
        self._buffer.reset()
        self.update_from_buffer()

    def refresh_theme(self) -> None:
        self._plot.setBackground(theme.BG_PLOT)
        for axis_name in ("bottom", "left"):
            axis = self._plot.getAxis(axis_name)
            axis.setPen(pg.mkPen(theme.BORDER_LIGHT))
            axis.setTextPen(pg.mkPen(theme.FG_SECONDARY))
        self._plot.update()
