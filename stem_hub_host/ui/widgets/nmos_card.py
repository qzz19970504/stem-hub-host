"""NMOS & 电源芯片卡片.

包含:
- NMOS1 / NMOS2 独立开关
- MP4317 / LM51770 独立开关
- nFAULT / nFLT 状态点
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from .. import theme
from .led_dot import LedDot


class NmosCard(QFrame):
    """NMOS & 电源芯片卡片."""

    nmos1_toggled = Signal(bool)
    nmos2_toggled = Signal(bool)
    mp4317_toggled = Signal(bool)
    lm51770_toggled = Signal(bool)
    led_toggled = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        title = QLabel("NMOS / 电源芯片 / 故障")
        title.setObjectName("label-small")
        outer.addWidget(title)

        # NMOS 行
        nmos_row = QHBoxLayout()
        nmos_row.setSpacing(16)
        outer.addLayout(nmos_row)

        nmos_row.addWidget(QLabel("NMOS"))
        self.nmos1 = QCheckBox("NMOS1")
        self.nmos1.toggled.connect(self.nmos1_toggled)
        nmos_row.addWidget(self.nmos1)
        self.nmos2 = QCheckBox("NMOS2")
        self.nmos2.toggled.connect(self.nmos2_toggled)
        nmos_row.addWidget(self.nmos2)
        nmos_row.addSpacing(20)

        nmos_row.addWidget(QLabel("电源"))
        self.mp4317 = QCheckBox("MP4317")
        self.mp4317.toggled.connect(self.mp4317_toggled)
        nmos_row.addWidget(self.mp4317)
        self.lm51770 = QCheckBox("LM51770")
        self.lm51770.toggled.connect(self.lm51770_toggled)
        nmos_row.addWidget(self.lm51770)
        nmos_row.addSpacing(20)

        self.led_cb = QCheckBox("LED 联动")
        self.led_cb.toggled.connect(self.led_toggled)
        nmos_row.addWidget(self.led_cb)
        nmos_row.addStretch(1)

        # 故障行
        fault_row = QHBoxLayout()
        fault_row.setSpacing(24)
        outer.addLayout(fault_row)

        self.drv_dot = LedDot()
        self.drv_label = QLabel("DRV8874 nFAULT: --")
        self.drv_label.setObjectName("secondary")
        fault_row.addWidget(self.drv_dot)
        fault_row.addWidget(self.drv_label)
        fault_row.addSpacing(20)

        self.aux_dot = LedDot()
        self.aux_label = QLabel("AUX nFLT: --")
        self.aux_label.setObjectName("secondary")
        fault_row.addWidget(self.aux_dot)
        fault_row.addWidget(self.aux_label)
        fault_row.addStretch(1)

    def update_fault(self, drv: int | None, aux: int | None) -> None:
        """drv/aux: None = 未连接, 0/1 = 实际状态."""
        if drv is None:
            self.drv_dot.set_state("off")
            self.drv_label.setText("DRV8874 nFAULT: --")
        else:
            self.drv_dot.set_state("error" if drv else "ok")
            self.drv_label.setText(f"DRV8874 nFAULT: {'故障' if drv else '正常'}")
        if aux is None:
            self.aux_dot.set_state("off")
            self.aux_label.setText("AUX nFLT: --")
        else:
            self.aux_dot.set_state("error" if aux else "ok")
            self.aux_label.setText(f"AUX nFLT: {'故障' if aux else '正常'}")

    def set_switches(self, *, nmos1=None, nmos2=None, mp4317=None, lm51770=None, led=None) -> None:
        """回写 UI 状态 (避免信号循环)."""
        if nmos1 is not None:
            self.nmos1.blockSignals(True)
            self.nmos1.setChecked(nmos1)
            self.nmos1.blockSignals(False)
        if nmos2 is not None:
            self.nmos2.blockSignals(True)
            self.nmos2.setChecked(nmos2)
            self.nmos2.blockSignals(False)
        if mp4317 is not None:
            self.mp4317.blockSignals(True)
            self.mp4317.setChecked(mp4317)
            self.mp4317.blockSignals(False)
        if lm51770 is not None:
            self.lm51770.blockSignals(True)
            self.lm51770.setChecked(lm51770)
            self.lm51770.blockSignals(False)
        if led is not None:
            self.led_cb.blockSignals(True)
            self.led_cb.setChecked(led)
            self.led_cb.blockSignals(False)
