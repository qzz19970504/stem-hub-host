"""电机驱动卡片 — 第四轮 (方形按钮 + MODE 联动配色 + 半透明 + MODE/CURRENT 加大)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from .toggle_switch import ToggleSwitch


# ---- 按钮配色 ----
BTN_CFG = {
    "SLEEP": {"color": theme.STATUS_OFF, "fill": theme.BG_INPUT,
              "icon_off": theme.FG_SECONDARY, "icon_on": "#0A1119"},
    "WAKE":  {"color": theme.STATUS_WARN, "fill": theme.BG_INPUT,
              "icon_off": theme.STATUS_WARN, "icon_on": "#0A1119"},
    "FWD":   {"color": theme.ACCENT, "fill": theme.BG_INPUT,
              "icon_off": theme.FG_PRIMARY, "icon_on": "#0A1119"},
    "REV":   {"color": theme.ACCENT, "fill": theme.BG_INPUT,
              "icon_off": theme.FG_PRIMARY, "icon_on": "#0A1119"},
    "BRAKE": {"color": theme.STATUS_ERROR, "fill": theme.BG_INPUT,
              "icon_off": theme.STATUS_ERROR, "icon_on": "#FFFFFF"},
    "STOP":  {"color": theme.STATUS_ERROR, "fill": theme.BG_INPUT,
              "icon_off": theme.STATUS_ERROR, "icon_on": "#FFFFFF"},
}


def _button_config(key: str) -> dict[str, str]:
    return {
        "SLEEP": {"color": theme.FG_TERTIARY, "fill": theme.BG_INPUT,
                  "icon_off": theme.FG_SECONDARY, "icon_on": theme.BG_BASE},
        "WAKE":  {"color": theme.STATUS_WARN, "fill": theme.BG_INPUT,
                  "icon_off": theme.STATUS_WARN, "icon_on": theme.BG_BASE},
        "FWD":   {"color": theme.ACCENT, "fill": theme.BG_INPUT,
                  "icon_off": theme.FG_PRIMARY, "icon_on": theme.BG_BASE},
        "REV":   {"color": theme.ACCENT, "fill": theme.BG_INPUT,
                  "icon_off": theme.FG_PRIMARY, "icon_on": theme.BG_BASE},
        "BRAKE": {"color": theme.STATUS_ERROR, "fill": theme.BG_INPUT,
                  "icon_off": theme.STATUS_ERROR, "icon_on": "#FFFFFF"},
        "STOP":  {"color": theme.STATUS_ERROR, "fill": theme.BG_INPUT,
                  "icon_off": theme.STATUS_ERROR, "icon_on": "#FFFFFF"},
    }[key]


# ---- 自绘图标 ----

def _draw_power_standby(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    pen = QPen(QColor(color), max(2, r * 0.18), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(cx - r, cy - r * 0.72, r * 2, r * 2), 35 * 16, 290 * 16)
    p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r * 0.05))
    p.restore()


def _draw_power_active(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    pen = QPen(QColor(color), max(2, r * 0.16), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(cx - r * 0.66, cy - r * 0.48, r * 1.32, r * 1.32),
              35 * 16, 290 * 16)
    p.drawLine(QPointF(cx, cy - r * 0.72), QPointF(cx, cy + r * 0.02))
    for i in range(6):
        ang = math.pi + i * math.pi / 5
        x1 = cx + math.cos(ang) * r * 0.88
        y1 = cy + math.sin(ang) * r * 0.88
        x2 = cx + math.cos(ang) * r * 1.08
        y2 = cy + math.sin(ang) * r * 1.08
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.restore()


def _draw_arrow_up(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    pen = QPen(QColor(color), max(2, r * 0.16), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    top_y = cy - r * 0.7
    bot_y = cy + r * 0.3
    p.drawLine(QPointF(cx, top_y), QPointF(cx, bot_y))
    head_len = r * 0.45
    p.drawLine(QPointF(cx, top_y), QPointF(cx - head_len, top_y + head_len))
    p.drawLine(QPointF(cx, top_y), QPointF(cx + head_len, top_y + head_len))
    # 横线 (下方)
    line_y = cy + r * 0.55
    p.drawLine(QPointF(cx - r * 0.55, line_y), QPointF(cx + r * 0.55, line_y))
    p.restore()


def _draw_arrow_down(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    pen = QPen(QColor(color), max(2, r * 0.16), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    top_y = cy - r * 0.3
    bot_y = cy + r * 0.7
    p.drawLine(QPointF(cx, top_y), QPointF(cx, bot_y))
    head_len = r * 0.45
    p.drawLine(QPointF(cx, bot_y), QPointF(cx - head_len, bot_y - head_len))
    p.drawLine(QPointF(cx, bot_y), QPointF(cx + head_len, bot_y - head_len))
    # 横线 (上方)
    line_y = cy - r * 0.55
    p.drawLine(QPointF(cx - r * 0.55, line_y), QPointF(cx + r * 0.55, line_y))
    p.restore()


def _draw_brake_disc(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    pen = QPen(QColor(color), max(2, r * 0.15), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx - r * 0.12, cy), r * 0.68, r * 0.68)
    p.drawEllipse(QPointF(cx - r * 0.12, cy), r * 0.13, r * 0.13)
    p.drawArc(QRectF(cx + r * 0.15, cy - r * 0.82, r * 0.78, r * 1.64),
              75 * 16, -150 * 16)
    p.restore()


def _draw_stop_square(p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
    p.save()
    s = r * 1.25
    p.setPen(QPen(QColor(color), max(2, r * 0.16), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(cx - s / 2, cy - s / 2, s, s), r * 0.14, r * 0.14)
    p.restore()


# ---- MODE 标题框 (颜色跟随激活按钮) ----
class _ModeBadge(QFrame):
    """MODE: FWD 框 — 描边 + 大字, 背景/边框跟随当前 mode 颜色."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mode: str | None = None
        self.setMinimumHeight(130)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._apply_surface(theme.BORDER, active=False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 8, 28, 8)
        lay.setSpacing(24)
        lay.addStretch(1)

        self._label = QLabel("MODE:")
        f_lbl = QFont(theme.FONT_DISPLAY)
        f_lbl.setPointSize(40)
        f_lbl.setBold(True)
        self._label.setFont(f_lbl)
        self._label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; border: none;"
        )
        lay.addWidget(self._label)

        self._value = QLabel("----")
        f_val = QFont(theme.FONT_DISPLAY)
        f_val.setPointSize(48)
        f_val.setBold(True)
        self._value.setFont(f_val)
        self._value.setStyleSheet(
            f"color: {theme.FG_TERTIARY}; background: transparent; border: none; letter-spacing: 2px;"
        )
        self.value_glow = QGraphicsDropShadowEffect(self._value)
        self.value_glow.setBlurRadius(18)
        self.value_glow.setOffset(0, 0)
        self.value_glow.setColor(QColor(theme.ACCENT))
        self.value_glow.setEnabled(False)
        self._value.setGraphicsEffect(self.value_glow)
        lay.addWidget(self._value)
        lay.addStretch(1)

    def _apply_surface(self, border: str, *, active: bool) -> None:
        if active:
            start, end = theme.mode_surface(border)
        else:
            start, end = theme.BG_ELEVATED, theme.BG_CARD
        self.setStyleSheet(
            "QFrame {"
            "  background: qlineargradient("
            "    x1: 0, y1: 0, x2: 1, y2: 1,"
            f"    stop: 0 {start}, stop: 1 {end}"
            "  );"
            f"  border: 1.5px solid {border};"
            "  border-radius: 14px;"
            "}"
        )

    def set_value(self, mode: str | None) -> None:
        self._mode = mode
        color_map = {
            "FWD": theme.ACCENT,
            "REV": theme.ACCENT,
            "BRAKE": theme.STATUS_ERROR,
            "STOP": theme.STATUS_ERROR,
            "SLEEP": theme.STATUS_OFF,
            "WAKE": theme.STATUS_WARN,
        }
        if mode is None or not mode:
            self._value.setText("----")
            self._value.setStyleSheet(
                f"color: {theme.FG_TERTIARY}; background: transparent; border: none; letter-spacing: 2px;"
            )
            self._apply_surface(theme.BORDER, active=False)
            self.value_glow.setEnabled(False)
            return
        self._value.setText(mode)
        color = color_map.get(mode, theme.FG_PRIMARY)
        self._value.setStyleSheet(
            f"color: {color}; background: transparent; border: none; letter-spacing: 2px;"
        )
        self.value_glow.setColor(QColor(color))
        self.value_glow.setEnabled(True)
        # 边框跟随激活按钮颜色, 半透明背景
        self._apply_surface(color, active=True)

    def refresh_theme(self) -> None:
        self._label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; border: none;"
        )
        self.set_value(self._mode)


class _CurrentBadge(QFrame):
    """Rounded current and motor-bypass status surface."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ma: int | None = None
        self.setMinimumHeight(72)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._apply_surface()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(0)

        self.current_region = QWidget(self)
        self.current_region.setObjectName("currentReadoutRegion")
        self.current_region.setStyleSheet(
            "QWidget#currentReadoutRegion { background: transparent; border: none; }"
        )
        current_row = QHBoxLayout(self.current_region)
        current_row.setContentsMargins(24, 0, 10, 0)
        current_row.setSpacing(10)

        self._label = QLabel("CURRENT:")
        f_lbl = QFont(theme.FONT_DISPLAY)
        f_lbl.setPointSize(20)
        f_lbl.setBold(True)
        self._label.setFont(f_lbl)
        self._label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent;"
        )
        current_row.addWidget(self._label)

        self._value = QLabel("--.- A")
        f_val = QFont(theme.FONT_MONO)
        f_val.setPointSize(26)
        f_val.setBold(True)
        self._value.setFont(f_val)
        self._value.setStyleSheet(
            f"color: {theme.FG_PRIMARY}; background: transparent;"
        )
        current_row.addWidget(self._value)

        current_row.addStretch(1)

        lay.addWidget(self.current_region, 2)

        self.bypass_region = QWidget(self)
        self.bypass_region.setObjectName("motorBypassRegion")
        self.bypass_region.setStyleSheet(
            "QWidget#motorBypassRegion { background: transparent; border: none; }"
        )

        bypass_column = QVBoxLayout(self.bypass_region)
        bypass_column.setContentsMargins(0, 0, 0, 0)
        bypass_column.setSpacing(2)
        self.bypass_toggle = ToggleSwitch(self)
        bypass_column.addWidget(
            self.bypass_toggle, 0, Qt.AlignmentFlag.AlignHCenter
        )
        self.bypass_label = QLabel("MOTOR BYPASS")
        bypass_font = QFont(theme.FONT_MONO)
        bypass_font.setPointSize(9)
        bypass_font.setBold(True)
        self.bypass_label.setFont(bypass_font)
        self.bypass_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bypass_column.addWidget(self.bypass_label)
        lay.addWidget(self.bypass_region, 1)

    def _apply_surface(self) -> None:
        self.setStyleSheet(
            "QFrame {"
            f" background: {theme.BG_ELEVATED};"
            f" border: 1.5px solid {theme.BORDER};"
            " border-radius: 14px;"
            "}"
            "QLabel { background: transparent; border: none; }"
        )

    def set_current_ma(self, ma: int | None) -> None:
        self._ma = ma
        if ma is None:
            self._value.setText("--.- A")
            self._value.setStyleSheet(
                f"color: {theme.FG_TERTIARY}; background: transparent;"
            )
            return
        a = ma / 1000.0
        self._value.setText(f"{a:.1f} A")
        color = theme.STATUS_ERROR if a > 15.0 else theme.FG_PRIMARY
        self._value.setStyleSheet(
            f"color: {color}; background: transparent;"
        )

    def refresh_theme(self) -> None:
        self._apply_surface()
        self._label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent;"
        )
        color = theme.FG_PRIMARY if self.bypass_toggle.isEnabled() else theme.FG_DISABLED
        self.bypass_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.set_current_ma(self._ma)


class _ModeButton(QPushButton):
    """方形模式按钮 — 自绘图标 + 半透明未激活 / 高亮激活."""

    RENDER_SCALE = 3
    inactive_surface_alpha = theme.MOTOR_INACTIVE_SURFACE_ALPHA
    active_surface_alpha = theme.MOTOR_ACTIVE_SURFACE_ALPHA

    def __init__(self, key: str, surface_group: str, parent=None) -> None:
        super().__init__(parent)
        self._key = key
        self.surface_group = surface_group
        cfg = _button_config(key)
        self._color = cfg["color"]
        self._fill = cfg["fill"]
        self._icon_off = cfg["icon_off"]
        self._icon_on = cfg["icon_on"]
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        # 正方形 — 强制等宽高
        self.setMinimumSize(QSize(64, 64))
        self.setMaximumSize(QSize(180, 180))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 选中态发光
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(22)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(self._color))
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)

    def refresh_theme(self) -> None:
        cfg = _button_config(self._key)
        self._color = cfg["color"]
        self._fill = cfg["fill"]
        self._icon_off = cfg["icon_off"]
        self._icon_on = cfg["icon_on"]
        self._glow.setColor(QColor(self._color))
        self.update()

    def setChecked(self, checked: bool) -> None:  # type: ignore[override]
        super().setChecked(checked)
        self._glow.setEnabled(checked)
        self.update()

    def setEnabled(self, enabled: bool) -> None:  # type: ignore[override]
        super().setEnabled(enabled)
        if not enabled:
            self._glow.setEnabled(False)
        self.update()

    def _draw_icon(self, p: QPainter, cx: float, cy: float, r: float, color: str) -> None:
        if self._key == "SLEEP":
            _draw_power_standby(p, cx, cy, r, color)
        elif self._key == "WAKE":
            _draw_power_active(p, cx, cy, r, color)
        elif self._key == "FWD":
            _draw_arrow_up(p, cx, cy, r, color)
        elif self._key == "REV":
            _draw_arrow_down(p, cx, cy, r, color)
        elif self._key == "BRAKE":
            _draw_brake_disc(p, cx, cy, r, color)
        elif self._key == "STOP":
            _draw_stop_square(p, cx, cy, r, color)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _ev) -> None:  # type: ignore[override]
        scale = self.RENDER_SCALE
        image = QImage(
            self.width() * scale,
            self.height() * scale,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.scale(scale, scale)
        # 方形内边距
        pad = 4
        rect = self.rect().adjusted(pad, pad, -pad, -pad)
        # 强制正方形
        side = min(rect.width(), rect.height())
        sq = QRectF(
            rect.x() + (rect.width() - side) / 2,
            rect.y() + (rect.height() - side) / 2,
            side,
            side,
        )
        path = QPainterPath()
        radius = 10
        path.addRoundedRect(sq, radius, radius)

        # 颜色: 未激活 = 半透明, 激活 = 实心
        if self.isChecked():
            bg_top = QColor(self._color).lighter(110)
            bg_bottom = QColor(self._color).darker(108)
            bg_top.setAlpha(self.active_surface_alpha)
            bg_bottom.setAlpha(self.active_surface_alpha)
            text_color = QColor(self._icon_on)
            border_color = QColor(self._color)
        else:
            group_color = {
                "idle": theme.FG_TERTIARY,
                "motion": theme.ACCENT,
                "safety": theme.STATUS_ERROR,
            }[self.surface_group]
            bg_top = QColor(group_color)
            bg_bottom = QColor(group_color)
            bg_top.setAlpha(self.inactive_surface_alpha)
            bg_bottom.setAlpha(max(28, self.inactive_surface_alpha - 30))
            text_color = QColor(self._icon_off)
            border_color = QColor(group_color)
            border_color.setAlpha(theme.EFFECT_BORDER_ALPHA)

        if not self.isEnabled():
            bg_top = QColor(theme.BG_INPUT)
            bg_bottom = QColor(theme.BG_BASE)
            border_color = QColor(theme.BORDER)
            text_color = QColor(theme.FG_DISABLED)
        elif self.isDown():
            # 按下: 表面明显压暗产生下陷感, 边框用按钮自身语义色 (不再统一青)
            bg_top = bg_top.darker(145)
            bg_bottom = bg_bottom.darker(160)
            border_color = QColor(self._color)
        elif self.underMouse():
            if self.isChecked():
                border_color = QColor(self._color).lighter(125)
            else:
                # 悬浮: 边框用所属分组的语义色提亮, 与按钮含义一致 (不再统一青)
                bg_top = QColor(theme.BG_CARD_HOVER).lighter(112)
                bg_bottom = QColor(theme.BG_CARD_HOVER)
                border_color = QColor(group_color).lighter(130)

        background = QLinearGradient(0, sq.top(), 0, sq.bottom())
        background.setColorAt(0.0, bg_top)
        background.setColorAt(1.0, bg_bottom)

        # 填充
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(background))
        p.drawPath(path)

        # 边框
        pen = QPen(border_color, 1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # 图标 (居中)
        icon_cx = sq.x() + sq.width() / 2
        icon_cy = sq.y() + sq.height() * 0.45
        icon_r = sq.width() * 0.26
        self._draw_icon(p, icon_cx, icon_cy, icon_r, text_color.name())

        # 标签 (下方)
        label_rect = QRectF(
            sq.x(),
            sq.y() + sq.height() * 0.72,
            sq.width(),
            sq.height() * 0.24,
        )
        f_lbl = QFont(theme.FONT_DISPLAY)
        lbl_pt = max(10, int(sq.width() / 6.5))
        f_lbl.setPointSize(lbl_pt)
        f_lbl.setBold(True)
        p.setFont(f_lbl)
        p.setPen(QColor(text_color))
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._key)

        if self.hasFocus():
            focus_path = QPainterPath()
            focus_path.addRoundedRect(sq.adjusted(2, 2, -2, -2), radius - 2, radius - 2)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(theme.FG_PRIMARY), 2))
            p.drawPath(focus_path)
        p.end()

        target = QPainter(self)
        target.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target.drawImage(self.rect(), image)


class MotorCard(QFrame):
    """电机驱动卡片 — 方形按钮 + MODE 联动配色."""

    sleep_clicked = Signal()
    wake_clicked = Signal()
    fwd_clicked = Signal()
    rev_clicked = Signal()
    brake_clicked = Signal()
    stop_clicked = Signal()
    bypass_changed = Signal(bool)
    button_pairs = (
        ("SLEEP", "WAKE"),
        ("FWD", "REV"),
        ("BRAKE", "STOP"),
    )
    button_order = ("SLEEP", "WAKE", "FWD", "REV", "BRAKE", "STOP")

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
            theme.MOTOR_STATUS_GAP,
            0,
            theme.MOTOR_STATUS_GAP,
        )
        upper_layout.setSpacing(0)

        self.upper_content = QWidget(self.upper_region)
        self.upper_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content_layout = QVBoxLayout(self.upper_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(theme.MOTOR_STATUS_GAP)

        self.mode_badge = _ModeBadge(self)
        content_layout.addWidget(self.mode_badge, 2)

        self.current_badge = _CurrentBadge(self)
        self.bypass_toggle = self.current_badge.bypass_toggle
        self.bypass_toggle.toggled.connect(self.bypass_changed)
        content_layout.addWidget(self.current_badge, 1)

        upper_layout.addWidget(self.upper_content)
        outer.addWidget(self.upper_region, theme.CARD_UPPER_REGION_STRETCH)

        self.divider = QFrame(self)
        self.divider.setObjectName("divider")
        self.divider.setFixedHeight(theme.DIVIDER_HEIGHT)
        outer.addWidget(self.divider)
        self.button_region = QWidget(self)
        self.button_region.setObjectName("motorButtonRegion")
        self.button_region.setStyleSheet(
            "QWidget#motorButtonRegion { background: transparent; }"
        )
        self.button_region.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.button_region.setMinimumHeight(theme.CARD_LOWER_REGION_MIN_HEIGHT)
        row = QHBoxLayout(self.button_region)
        row.setSpacing(theme.LAYOUT_GAP_CONTROL)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.button_region, theme.CARD_LOWER_REGION_STRETCH)

        self._btns: dict[str, _ModeButton] = {}
        surface_groups = {
            "SLEEP": "idle",
            "WAKE": "idle",
            "FWD": "motion",
            "REV": "motion",
            "BRAKE": "safety",
            "STOP": "safety",
        }
        for key in self.button_order:
            button = _ModeButton(key, surface_groups[key], self)
            row.addWidget(button, 1)
            self._btns[key] = button

        self._btns["SLEEP"].clicked.connect(self._on_sleep)
        self._btns["WAKE"].clicked.connect(self._on_wake)
        self._btns["FWD"].clicked.connect(self._on_fwd)
        self._btns["REV"].clicked.connect(self._on_rev)
        self._btns["BRAKE"].clicked.connect(self._on_brake)
        self._btns["STOP"].clicked.connect(self._on_stop)

        self.set_enabled(False)

    @property
    def buttons(self) -> dict[str, _ModeButton]:
        """Return motor buttons keyed by firmware mode name."""

        return self._btns

    def _mutex(self, clicked_key: str) -> None:
        for k, b in self._btns.items():
            blocked = b.signalsBlocked()
            b.blockSignals(True)
            b.setChecked(k == clicked_key)
            b.blockSignals(blocked)
            b.update()

    def _on_sleep(self) -> None:
        self._mutex("SLEEP")
        self.sleep_clicked.emit()

    def _on_wake(self) -> None:
        self._mutex("WAKE")
        self.wake_clicked.emit()

    def _on_fwd(self) -> None:
        self._mutex("FWD")
        self.fwd_clicked.emit()

    def _on_rev(self) -> None:
        self._mutex("REV")
        self.rev_clicked.emit()

    def _on_brake(self) -> None:
        self._mutex("BRAKE")
        self.brake_clicked.emit()

    def _on_stop(self) -> None:
        self._mutex("STOP")
        self.stop_clicked.emit()

    def set_enabled(self, enabled: bool) -> None:
        for b in self._btns.values():
            b.setEnabled(enabled)
        if not enabled:
            self.set_bypass_enabled(False)

    def set_bypass_enabled(self, enabled: bool) -> None:
        self.bypass_toggle.setEnabled(enabled)
        color = theme.FG_PRIMARY if enabled else theme.FG_DISABLED
        self.current_badge.bypass_label.setStyleSheet(
            f"color: {color}; background: transparent;"
        )

    def set_bypass_state(self, on: bool) -> None:
        self.bypass_toggle.set_on(on, animate=False)

    def update_state(
        self, mode: str | None, current_ma: int | None,
        overcurrent: int = 0, fault: int = 0,
    ) -> None:
        self.mode_badge.set_value(mode)
        self.current_badge.set_current_ma(current_ma)
        for k, b in self._btns.items():
            blocked = b.signalsBlocked()
            b.blockSignals(True)
            b.setChecked(k == mode)
            b.blockSignals(blocked)
            b.update()

    def refresh_theme(self) -> None:
        self.upper_region.setStyleSheet(
            f"background-color: {theme.BG_CARD};"
        )
        self.mode_badge.refresh_theme()
        self.current_badge.refresh_theme()
        for button in self._btns.values():
            button.refresh_theme()
