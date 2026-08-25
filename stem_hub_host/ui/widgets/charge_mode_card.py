"""Hardware output controls and derived fault indicators."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
        self.setMinimumWidth(theme.OUTPUT_CELL_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.toggle = ToggleSwitch(self)
        col.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignHCenter)

        self.label = QLabel(name)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        f = QFont(theme.FONT_MONO.split(",")[0].strip())
        self.letter_spacing = 0.0 if len(name) > 10 else 1.5
        f.setPointSize(
            theme.OUTPUT_LONG_LABEL_FONT_SIZE if len(name) > 10 else 10
        )
        f.setBold(True)
        self.label.setFont(f)
        self.label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; "
            f"letter-spacing: {self.letter_spacing}px;"
        )
        col.addWidget(self.label)


class _OutputHierarchy(QWidget):
    """Paint dependency connectors behind the native output controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cells: dict[str, _ToggleCell] = {}
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        required = {"CHARGE", "CHARGE_BYPASS", "DRIVE", "NMOS1", "NMOS2", "LIGHTS"}
        if not required.issubset(self.cells):
            return

        def center(name: str) -> QPointF:
            toggle = self.cells[name].toggle
            point = toggle.mapTo(self, toggle.rect().center())
            return QPointF(point)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(theme.BORDER_LIGHT), 1.2))

        charge = center("CHARGE")
        charge_bypass = center("CHARGE_BYPASS")
        track_half = theme.SWITCH_WIDTH / 2
        painter.drawLine(
            QPointF(charge.x() + track_half + theme.SP_XS, charge.y()),
            QPointF(charge_bypass.x() - track_half - theme.SP_XS, charge_bypass.y()),
        )

        drive = center("DRIVE")
        children = [center(name) for name in ("NMOS1", "NMOS2", "LIGHTS")]
        branch_y = (drive.y() + children[0].y()) / 2
        painter.drawLine(
            QPointF(drive.x(), drive.y() + theme.SWITCH_HEIGHT / 2 + 2),
            QPointF(drive.x(), branch_y),
        )
        painter.drawLine(
            QPointF(children[0].x(), branch_y),
            QPointF(children[-1].x(), branch_y),
        )
        for child in children:
            painter.drawLine(
                QPointF(child.x(), branch_y),
                QPointF(child.x(), child.y() - theme.SWITCH_HEIGHT / 2 - 2),
            )
        painter.end()


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
        outer.setSpacing(0)

        self.upper_region = QWidget(self)
        self.upper_region.setStyleSheet(
            f"background-color: {theme.BG_CARD};"
        )
        self.upper_region.setMinimumHeight(theme.CARD_UPPER_REGION_MIN_HEIGHT)
        self.upper_region.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        upper_layout = QVBoxLayout(self.upper_region)
        upper_layout.setContentsMargins(
            0,
            theme.CARD_UPPER_MIN_GAP,
            0,
            theme.CARD_UPPER_MIN_GAP,
        )
        upper_layout.setSpacing(0)
        self.upper_content = QWidget(self.upper_region)
        self.upper_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content_layout = QVBoxLayout(self.upper_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._cells: dict[str, _ToggleCell] = {}
        self.output_hierarchy = _OutputHierarchy(self.upper_content)
        self.output_hierarchy.setObjectName("driveHierarchy")
        self.drive_hierarchy = self.output_hierarchy
        hierarchy_grid = QGridLayout(self.output_hierarchy)
        hierarchy_grid.setContentsMargins(0, 0, 0, 0)
        hierarchy_grid.setHorizontalSpacing(0)
        hierarchy_grid.setVerticalSpacing(theme.OUTPUT_HIERARCHY_GAP)
        for column in range(5):
            hierarchy_grid.setColumnStretch(column, 1)

        charge = self._make_toggle_cell("CHARGE")
        charge_bypass = self._make_toggle_cell("CHARGE_BYPASS", "CHARGE BYPASS")
        drive = self._make_toggle_cell("DRIVE")
        nmos1 = self._make_toggle_cell("NMOS1")
        nmos2 = self._make_toggle_cell("NMOS2")
        lights = self._make_toggle_cell("LIGHTS")
        hierarchy_grid.addWidget(charge, 0, 0)
        hierarchy_grid.addWidget(charge_bypass, 0, 4)
        hierarchy_grid.addWidget(drive, 1, 2)
        hierarchy_grid.addWidget(nmos1, 2, 0)
        hierarchy_grid.addWidget(nmos2, 2, 2)
        hierarchy_grid.addWidget(lights, 2, 4)
        self.output_hierarchy.cells = self._cells

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
        hierarchy_grid.addWidget(self.all_off_row, 3, 1, 1, 3)
        content_layout.addWidget(self.output_hierarchy)

        upper_layout.addWidget(self.upper_content)
        outer.addWidget(self.upper_region, theme.CARD_UPPER_REGION_STRETCH)

        # 下划线 (分隔 toggle 区与故障区)
        self.divider = _make_divider()
        outer.addWidget(self.divider)

        self.fault_region = QWidget(self)
        self.fault_region.setObjectName("faultRegion")
        self.fault_region.setStyleSheet(
            "QWidget#faultRegion { background: transparent; }"
        )
        self.fault_region.setMinimumHeight(theme.CARD_LOWER_REGION_MIN_HEIGHT)
        self.fault_region.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        fault_grid = QGridLayout(self.fault_region)
        fault_grid.setContentsMargins(0, 0, 0, 0)
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

        outer.addWidget(self.fault_region, theme.CARD_LOWER_REGION_STRETCH)

    def _make_toggle_cell(self, name: str, label: str | None = None) -> _ToggleCell:
        cell = _ToggleCell(label or name, self)
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
            f"color: {color}; background: transparent; "
            f"letter-spacing: {cell.letter_spacing}px;"
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
        self.output_hierarchy.update()
        for cell in self._cells.values():
            cell.toggle.update()
