"""Hardware output controls and derived fault indicators."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from .fault_indicator import FaultIndicator
from .toggle_switch import ToggleSwitch


class _ToggleCell(QWidget):
    """单个 toggle + 标签 (竖向, 居中)."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 6, 0, 6)
        col.setSpacing(6)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.toggle = ToggleSwitch(self)
        col.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignHCenter)

        self.label = QLabel(name)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        f = QFont(theme.FONT_MONO.split(",")[0].strip())
        f.setPointSize(9 if len(name) > 10 else 11)
        f.setBold(True)
        self.label.setFont(f)
        self.label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; letter-spacing: 1.5px;"
        )
        col.addWidget(self.label)


def _make_divider() -> QFrame:
    f = QFrame()
    f.setObjectName("divider")
    f.setFixedHeight(theme.DIVIDER_HEIGHT)
    return f


class ChargeModeCard(QFrame):
    """Control the five real outputs and expose honest fault states."""

    toggle_changed = Signal(str, bool)
    all_off_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
            theme.LAYOUT_MARGIN_CARD,
            theme.LAYOUT_MARGIN_CARD_Y,
        )
        outer.setSpacing(theme.LAYOUT_GAP_CONTROL)

        self.upper_region = QWidget(self)
        self.upper_region.setStyleSheet(
            f"background-color: {theme.BG_CARD};"
        )
        self.upper_region.setFixedHeight(theme.CARD_UPPER_REGION_HEIGHT)
        upper_layout = QVBoxLayout(self.upper_region)
        upper_layout.setContentsMargins(
            0,
            theme.CARD_UPPER_MIN_GAP,
            0,
            theme.CARD_UPPER_MIN_GAP,
        )
        upper_layout.setSpacing(0)
        upper_layout.addStretch(1)

        self.upper_content = QWidget(self.upper_region)
        self.upper_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        content_layout = QVBoxLayout(self.upper_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(theme.LAYOUT_GAP_CONTROL)

        self._cells: dict[str, _ToggleCell] = {}
        top_row = QHBoxLayout()
        top_row.setSpacing(theme.LAYOUT_GAP_CONTROL)
        top_row.addWidget(self._make_toggle_cell("CHARGE"), 1)
        top_row.addWidget(QWidget(self), 1)
        top_row.addWidget(QWidget(self), 1)
        top_row.addWidget(self._make_toggle_cell("CHARGE_BYPASS"), 1)
        content_layout.addLayout(top_row)

        self.drive_hierarchy = QFrame(self)
        self.drive_hierarchy.setObjectName("driveHierarchy")
        self.drive_hierarchy.setStyleSheet(
            f"QFrame#driveHierarchy {{ border-top: 1px solid {theme.BORDER}; }}"
        )
        drive_row = QHBoxLayout(self.drive_hierarchy)
        drive_row.setContentsMargins(0, 5, 0, 0)
        drive_row.setSpacing(theme.LAYOUT_GAP_CONTROL)
        for name in ("DRIVE", "NMOS1", "NMOS2", "LIGHTS"):
            drive_row.addWidget(self._make_toggle_cell(name), 1)
        content_layout.addWidget(self.drive_hierarchy)

        self.all_off_row = QFrame(self)
        self.all_off_row.setObjectName("allOffRow")
        all_off_layout = QHBoxLayout(self.all_off_row)
        all_off_layout.setContentsMargins(0, 0, 0, 0)
        all_off_layout.addStretch(1)
        self.all_off_button = QPushButton("ALL OFF")
        self.all_off_button.setObjectName("allOffButton")
        self.all_off_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_off_button.setFixedSize(112, theme.CONTROL_HEIGHT_SM)
        all_off_font = QFont(theme.FONT_DISPLAY)
        all_off_font.setPointSize(11)
        all_off_font.setBold(True)
        self.all_off_button.setFont(all_off_font)
        self.all_off_button.clicked.connect(self.all_off_clicked)
        all_off_layout.addWidget(self.all_off_button)
        all_off_layout.addStretch(1)
        content_layout.addWidget(self.all_off_row)

        upper_layout.addWidget(self.upper_content)
        upper_layout.addStretch(1)
        outer.addWidget(self.upper_region)

        # 下划线 (分隔 toggle 区与故障区)
        self.divider = _make_divider()
        outer.addWidget(self.divider)

        fault_grid = QGridLayout()
        fault_grid.setHorizontalSpacing(8)
        fault_grid.setVerticalSpacing(8)
        self.fault_overtemp = FaultIndicator("OVERTEMP")
        self.fault_overcurrent = FaultIndicator("OVERCURRENT")
        self.fault_undervoltage = FaultIndicator("UNDERVOLTAGE")
        self.fault_drv = FaultIndicator("DRV FAULT")
        self.fault_aux = FaultIndicator("AUX FAULT")

        fault_grid.addWidget(self.fault_overtemp, 0, 0)
        fault_grid.addWidget(self.fault_overcurrent, 0, 1)
        fault_grid.addWidget(self.fault_undervoltage, 0, 2)
        fault_grid.addWidget(self.fault_drv, 1, 0)
        fault_grid.addWidget(self.fault_aux, 1, 1)
        fault_grid.setRowStretch(0, 1)
        fault_grid.setRowStretch(1, 1)

        outer.addLayout(fault_grid, 1)

    def _make_toggle_cell(self, name: str) -> _ToggleCell:
        cell = _ToggleCell(name, self)
        cell.toggle.toggled.connect(
            lambda on, n=name: self.toggle_changed.emit(n, on)
        )
        self._cells[name] = cell
        return cell

    def is_on(self, name: str) -> bool:
        return self._cells[name].toggle.is_on()

    @property
    def control_names(self) -> tuple[str, ...]:
        """Return stable hardware control identifiers in display order."""

        return tuple(self._cells)

    def set_toggle(self, name: str, on: bool, *, animate: bool = True) -> None:
        self._cells[name].toggle.set_on(on, animate=animate)

    def set_enabled(self, enabled: bool) -> None:
        for name in self._cells:
            self.set_control_enabled(name, enabled)
        self.all_off_button.setEnabled(enabled)

    def set_control_enabled(self, name: str, enabled: bool) -> None:
        cell = self._cells[name]
        cell.toggle.setEnabled(enabled)
        color = theme.FG_PRIMARY if enabled else theme.FG_DISABLED
        cell.label.setStyleSheet(
            f"color: {color}; background: transparent; letter-spacing: 1.5px;"
        )

    def update_fault(
        self,
        drv: int | None = None,
        aux: int | None = None,
        *,
        overtemp: bool | None = None,
        overcurrent: bool | None = None,
        undervoltage: bool | None = None,
    ) -> None:
        if drv is not None:
            state = "error" if drv else "ok"
            self.fault_drv.set_state(state)
        if aux is not None:
            state = "error" if aux else "ok"
            self.fault_aux.set_state(state)
        if overtemp is not None:
            self.fault_overtemp.set_state("error" if overtemp else "ok")
        if overcurrent is not None:
            self.fault_overcurrent.set_state("error" if overcurrent else "ok")
        if undervoltage is not None:
            self.fault_undervoltage.set_state("error" if undervoltage else "ok")

    def clear_all(self) -> None:
        self.clear_controls()
        for fault in (
            self.fault_overtemp,
            self.fault_overcurrent,
            self.fault_undervoltage,
            self.fault_drv,
            self.fault_aux,
        ):
            fault.set_state("off")

    def clear_controls(self) -> None:
        """Reset local output switches without emitting hardware commands."""

        for cell in self._cells.values():
            cell.toggle.set_on(False, animate=False)

    def refresh_theme(self) -> None:
        self.upper_region.setStyleSheet(
            f"background-color: {theme.BG_CARD};"
        )
        self.set_enabled(self.all_off_button.isEnabled())
        self.drive_hierarchy.setStyleSheet(
            f"QFrame#driveHierarchy {{ border-top: 1px solid {theme.BORDER}; }}"
        )
        for cell in self._cells.values():
            cell.toggle.update()
