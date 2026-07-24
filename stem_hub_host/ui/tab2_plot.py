"""Tab 2: 实时图表 (全屏版)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..data_buffer import DataBuffer
from . import theme
from .widgets.plot_widget import PlotWidget


class PlotTab(QWidget):
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
        outer.setSpacing(theme.GRID_GAP)

        # 顶部工具条
        self.toolbar_panel = QFrame(self)
        self.toolbar_panel.setObjectName("toolbarPanel")
        toolbar = QHBoxLayout(self.toolbar_panel)
        toolbar.setContentsMargins(14, 10, 14, 10)
        toolbar.setSpacing(10)
        outer.addWidget(self.toolbar_panel)

        title = QLabel("SENSE STREAM")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)
        toolbar.addSpacing(10)
        self.sample_rate_label = QLabel("SAMPLE RATE")
        self.sample_rate_label.setObjectName("toolbarLabel")
        label_font = QFont(theme.FONT_DISPLAY)
        label_font.setPointSize(13)
        label_font.setBold(True)
        self.sample_rate_label.setFont(label_font)
        toolbar.addWidget(
            self.sample_rate_label,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.hz_spin = QDoubleSpinBox()
        self.hz_spin.setObjectName("sampleRateControl")
        self.hz_spin.setFixedWidth(140)
        self.hz_spin.setFixedHeight(theme.TOOLBAR_CONTROL_HEIGHT)
        spin_font = QFont(theme.FONT_MONO)
        spin_font.setPointSize(12)
        self.hz_spin.setFont(spin_font)
        self.hz_spin.setDecimals(1)
        self.hz_spin.setRange(0.2, 1.0)
        self.hz_spin.setSingleStep(0.2)
        self.hz_spin.setValue(1.0)
        self.hz_spin.setSuffix(" Hz")
        toolbar.addWidget(
            self.hz_spin,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.clear_btn = QPushButton("CLEAR DATA")
        self.clear_btn.setObjectName("secondaryAction")
        self.clear_btn.setFixedSize(
            theme.TOOLBAR_ACTION_WIDTH,
            theme.TOOLBAR_CONTROL_HEIGHT,
        )
        action_font = QFont(theme.FONT_DISPLAY)
        action_font.setPointSize(13)
        action_font.setBold(True)
        self.clear_btn.setFont(action_font)
        toolbar.addWidget(
            self.clear_btn,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        toolbar.addStretch(1)

        # 绘图
        self.plot_widget = PlotWidget(data_buffer, compact=False)
        outer.addWidget(self.plot_widget, 1)

        # 信号
        self.clear_btn.clicked.connect(self.plot_widget.reset)

    def set_sample_rate(self, hz: float) -> None:
        """Reflect the Controller-normalized sampling rate without recursion."""

        self.hz_spin.blockSignals(True)
        self.hz_spin.setValue(hz)
        self.hz_spin.blockSignals(False)
