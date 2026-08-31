"""Hardware output controls and derived fault indicators."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
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

        # 方向二: 布局由 ChargeModeCard 组装 (双主开关列 + 页脚),
        # 本控件只保留透明画布与连线绘制.
        self.regions_layout = QVBoxLayout(self)
        self.regions_layout.setContentsMargins(0, 0, 0, 0)
        self.regions_layout.setSpacing(theme.SP_XS)

        self.charge_region = QWidget(self)
        self.charge_region.setObjectName("chargeRegion")
        self.charge_region.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.drive_region = QWidget(self)
        self.drive_region.setObjectName("driveRegion")
        self.drive_region.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

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

        # CHARGE → CHARGE BYPASS: 同列纵向父子连线
        charge = center("CHARGE")
        charge_bypass = center("CHARGE_BYPASS")
        painter.drawLine(
            QPointF(charge.x(), charge.y() + theme.SWITCH_HEIGHT / 2 + 2),
            QPointF(charge_bypass.x(), charge_bypass.y() - theme.SWITCH_HEIGHT / 2 - 2),
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
        self.charge_region = self.output_hierarchy.charge_region
        self.drive_region = self.output_hierarchy.drive_region

        # ---- 方向二: 双主开关列 (子开关归入父列, 消除横向真空) ----
        column_style = (
            "background: {bg}; border: 1px solid {border}; border-radius: 12px;"
        ).format(bg=theme.BG_SUB_CARD, border=theme.BORDER)

        self.charge_column = self.charge_region
        self.charge_column.setObjectName("chargeColumn")
        self.charge_column.setStyleSheet(
            f"QWidget#chargeColumn {{ {column_style} }}"
        )
        charge_col_layout = QVBoxLayout(self.charge_column)
        charge_col_layout.setContentsMargins(
            theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM
        )
        charge_col_layout.setSpacing(theme.SP_XS)

        self.drive_column = self.drive_region
        self.drive_column.setObjectName("driveColumn")
        self.drive_column.setStyleSheet(
            f"QWidget#driveColumn {{ {column_style} }}"
        )
        drive_col_layout = QVBoxLayout(self.drive_column)
        drive_col_layout.setContentsMargins(
            theme.SP_SM, theme.SP_SM, theme.SP_SM, theme.SP_SM
        )
        drive_col_layout.setSpacing(theme.SP_XS)

        charge = self._make_toggle_cell("CHARGE")
        charge_bypass = self._make_toggle_cell("CHARGE_BYPASS", "CHARGE BYPASS")
        drive = self._make_toggle_cell("DRIVE")
        nmos1 = self._make_toggle_cell("NMOS1")
        nmos2 = self._make_toggle_cell("NMOS2")
        lights = self._make_toggle_cell("LIGHTS")
        # 子开关列宽收窄, 让三枚能并排进入 DRIVE 列
        for child in (nmos1, nmos2, lights):
            child.setMinimumWidth(theme.SWITCH_WIDTH + 8)

        charge_col_layout.addWidget(charge, 1, Qt.AlignmentFlag.AlignHCenter)
        charge_col_layout.addWidget(charge_bypass, 1, Qt.AlignmentFlag.AlignHCenter)

        drive_col_layout.addWidget(drive, 1, Qt.AlignmentFlag.AlignHCenter)
        drive_children_row = QHBoxLayout()
        drive_children_row.setSpacing(theme.SP_XS)
        for child in (nmos1, nmos2, lights):
            drive_children_row.addWidget(child, 1, Qt.AlignmentFlag.AlignHCenter)
        drive_col_layout.addLayout(drive_children_row, 1)

        self.output_hierarchy.cells = self._cells
        columns_row = QHBoxLayout()
        columns_row.setSpacing(theme.SP_SM)
        # DRIVE 列需要容纳三枚子开关, 取更宽的 stretch
        columns_row.addWidget(self.charge_column, 2)
        columns_row.addWidget(self.drive_column, 3)

        # ---- ALL OFF 页脚: 整行落地, 不再悬在层级中间 ----
        self.all_off_row = QFrame(self.output_hierarchy)
        self.all_off_row.setObjectName("allOffRow")
        all_off_layout = QHBoxLayout(self.all_off_row)
        all_off_layout.setContentsMargins(0, 0, 0, 0)
        self.all_off_button = QPushButton("ALL OFF")
        self.all_off_button.setObjectName("allOffButton")
        self.all_off_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_off_button.setMinimumHeight(theme.CONTROL_HEIGHT_SM)
        self.all_off_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        all_off_font = QFont(theme.FONT_DISPLAY)
        all_off_font.setPointSize(11)
        all_off_font.setBold(True)
        self.all_off_button.setFont(all_off_font)
        self.all_off_button.clicked.connect(self.all_off_clicked)
        all_off_layout.addWidget(self.all_off_button)

        self.output_hierarchy.regions_layout.addLayout(columns_row, 1)
        self.output_hierarchy.regions_layout.addWidget(self.all_off_row)
        content_layout.addWidget(self.output_hierarchy)

        upper_layout.addWidget(self.upper_content)
        outer.addWidget(self.upper_region, theme.CARD_UPPER_REGION_STRETCH)

        # 下划线 (分隔控制区与故障区)
        self.divider = _make_divider()
        outer.addWidget(self.divider)

        # ---- 故障灯: 紧凑 3+2 两行块, 垂直居中 (无拉伸空行), 与左卡下区同节奏 ----
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
        fault_outer = QVBoxLayout(self.fault_region)
        fault_outer.setContentsMargins(0, 0, 0, 0)
        fault_outer.setSpacing(theme.SP_XS)
        self.fault_overtemp = FaultIndicator("OVERTEMP")
        self.fault_overcurrent = FaultIndicator("OVERCURRENT")
        self.fault_undervoltage = FaultIndicator("UNDERVOLTAGE")
        self.fault_drv = FaultIndicator("DRV FAULT")
        self.fault_aux = FaultIndicator("AUX FAULT")
        fault_outer.addStretch(1)
        first_row = QHBoxLayout()
        first_row.setSpacing(theme.SP_XS)
        for fault in (
            self.fault_overtemp,
            self.fault_overcurrent,
            self.fault_undervoltage,
        ):
            first_row.addWidget(fault, 1, Qt.AlignmentFlag.AlignVCenter)
        fault_outer.addLayout(first_row)
        second_row = QHBoxLayout()
        second_row.setSpacing(theme.SP_XS)
        second_row.addWidget(self.fault_drv, 1, Qt.AlignmentFlag.AlignVCenter)
        second_row.addWidget(self.fault_aux, 1, Qt.AlignmentFlag.AlignVCenter)
        second_row.addStretch(1)
        fault_outer.addLayout(second_row)
        fault_outer.addStretch(1)

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
            state = "error" if drv else "off"
            self.fault_drv.set_state(state)
        if aux is not None:
            state = "error" if aux else "off"
            self.fault_aux.set_state(state)
        if overtemp is not None:
            self.fault_overtemp.set_state("error" if overtemp else "off")
        if overcurrent is not None:
            self.fault_overcurrent.set_state("error" if overcurrent else "off")
        if undervoltage is not None:
            self.fault_undervoltage.set_state("error" if undervoltage else "off")

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
