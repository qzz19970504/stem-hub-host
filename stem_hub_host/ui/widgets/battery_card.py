"""Animated battery voltage card."""
from __future__ import annotations

import math
import re
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    Property,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme


# ---- 数据解析辅助 ----
def parse_celsius(s: str) -> Optional[float]:
    s = s.strip()
    if not s or s == "ERR":
        return None
    m = re.match(r"^(-?\d+(?:\.\d+)?)C$", s)
    return float(m.group(1)) if m else None


def parse_volts(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)V$", s)
    return float(m.group(1)) if m else None


def parse_amps(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)A$", s)
    return float(m.group(1)) if m else None


# ---- 颜色映射 ----
def _battery_color(volts: float | None) -> str:
    if volts is None:
        return theme.FG_TERTIARY
    if volts < theme.BATTERY_DANGER_V:
        return theme.STATUS_ERROR
    if volts < theme.BATTERY_WARN_V:
        return theme.STATUS_WARN
    return theme.ACCENT


# ---- 横向电池图标 (匹配设计图: 圆角矩形 + 右侧凸头 + 内部"能量格"横线) ----
def _paint_battery_icon_h(
    p: QPainter,
    cx: float,
    cy: float,
    w: float,
    h: float,
    color: str,
    ratio: float,
) -> None:
    """Draw a clean outline battery with a ratio-driven energy fill."""
    p.save()
    body_w = w * 0.84
    body_h = h * 0.76
    tip_w = w * 0.07
    tip_h = body_h * 0.42
    x = cx - (body_w + tip_w) / 2
    y = cy - body_h / 2

    pen_w = max(1.4, w * 0.042)
    p.setPen(QPen(QColor(color), pen_w, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    body_rect = QRectF(x, y, body_w, body_h)
    radius = body_h * 0.24
    p.drawRoundedRect(body_rect, radius, radius)

    tip_x = x + body_w
    tip_y = cy - tip_h / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(
        QRectF(tip_x + pen_w * 0.35, tip_y, tip_w, tip_h),
        tip_h * 0.25,
        tip_h * 0.25,
    )

    inner = body_rect.adjusted(
        pen_w * 1.65,
        pen_w * 1.65,
        -pen_w * 1.65,
        -pen_w * 1.65,
    )
    fill_width = inner.width() * max(0.0, min(1.0, ratio))
    if fill_width > 0:
        fill_rect = QRectF(inner.x(), inner.y(), fill_width, inner.height())
        gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
        start = QColor(color)
        start.setAlpha(145)
        end = QColor(color)
        end.setAlpha(235)
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)
        p.setBrush(gradient)
        p.drawRoundedRect(
            fill_rect,
            inner.height() * 0.23,
            inner.height() * 0.23,
        )
    p.restore()


class BatteryRing(QWidget):
    BATTERY_ICON_X_RATIO = 0.0
    BATTERY_ICON_Y_RATIO = -0.29

    """Battery voltage ring with state-driven progress and glow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value: Optional[float] = None
        self._ratio = 0.0
        self._target_ratio = 0.0
        self._glow_phase = 0.0

        self._ratio_anim = QPropertyAnimation(self, b"ratio", self)
        self._ratio_anim.setDuration(theme.ANIMATION_BATTERY_MS)
        self._ratio_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._ratio_anim.setStartValue(0.0)
        self._ratio_anim.setEndValue(0.0)

        self._glow_anim = QPropertyAnimation(self, b"glow_phase", self)
        self._glow_anim.setDuration(theme.BATTERY_GLOW_PULSE_MS)
        self._glow_anim.setStartValue(0.0)
        self._glow_anim.setKeyValueAt(0.5, 1.0)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_anim.setLoopCount(-1)

        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ---- Qt 属性 ----
    def _get_ratio(self) -> float:
        return self._ratio

    def _set_ratio(self, v: float) -> None:
        self._ratio = v
        self.update()

    ratio = Property(float, _get_ratio, _set_ratio)

    def _get_glow_phase(self) -> float:
        return self._glow_phase

    def _set_glow_phase(self, value: float) -> None:
        self._glow_phase = value
        self.update()

    glow_phase = Property(float, _get_glow_phase, _set_glow_phase)

    @property
    def value(self) -> Optional[float]:
        """Return the latest parsed battery voltage."""

        return self._value

    def set_value(self, volts: Optional[float], *, animate: bool = True) -> None:
        """Update voltage without restarting an identical in-flight animation."""

        target_ratio = theme.battery_ratio(volts)
        is_unchanged = volts == self._value and target_ratio == self._target_ratio
        self._value = volts
        if is_unchanged and animate:
            return

        self._target_ratio = target_ratio
        self._ratio_anim.stop()

        if volts is None or not animate:
            self._set_ratio(target_ratio)
        else:
            self._ratio_anim.setStartValue(self._ratio)
            self._ratio_anim.setEndValue(target_ratio)
            self._ratio_anim.start()

        if volts is None:
            self._glow_anim.stop()
            self._set_glow_phase(0.0)
        elif self._glow_anim.state() != QPropertyAnimation.State.Running:
            self._glow_anim.start()
        self.update()

    # ---- 绘制 ----
    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        pad = 26
        side = min(w, h) - pad * 2
        cx, cy = w / 2, h / 2
        rect = QRectF(cx - side / 2, cy - side / 2, side, side)

        thickness = max(10, int(side * 0.07))
        color = _battery_color(self._value)

        # ---- 1. 背景环 (深灰蓝) ----
        p.setPen(QPen(QColor(theme.BORDER), thickness,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # ---- 2. Progress glow ----
        if self._value is not None and self._ratio > 0:
            color_obj = QColor(color)
            pulse_alpha = int(8 * self._glow_phase)
            for offset, alpha in ((7, 26), (14, 16), (22, 8)):
                glow_color = QColor(color_obj)
                glow_color.setAlpha(alpha + pulse_alpha)
                p.setPen(QPen(glow_color, thickness + offset,
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(
                    rect,
                    90 * 16,
                    int(-theme.BATTERY_ARC_DEGREES * 16 * self._ratio),
                )

        # ---- 3. 进度弧 (主色实心) ----
        if self._ratio > 0:
            pen = QPen(QColor(color), thickness,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(
                rect,
                90 * 16,
                int(-theme.BATTERY_ARC_DEGREES * 16 * self._ratio),
            )

        # ---- 4. Progress endpoint glow ----
        if self._value is not None and self._ratio > 0:
            endpoint_angle = math.radians(
                90.0 - theme.BATTERY_ARC_DEGREES * self._ratio
            )
            radius = side / 2
            endpoint = QPointF(
                cx + math.cos(endpoint_angle) * radius,
                cy - math.sin(endpoint_angle) * radius,
            )
            endpoint_color = QColor(color)
            endpoint_color.setAlpha(80 + int(70 * self._glow_phase))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(endpoint_color)
            endpoint_radius = thickness * (0.55 + self._glow_phase * 0.12)
            p.drawEllipse(endpoint, endpoint_radius, endpoint_radius)

        # ---- 5. 电池图标 (中心偏上) ----
        icon_w = side * 0.20
        icon_h = side * 0.10
        icon_cx = cx + side * self.BATTERY_ICON_X_RATIO
        icon_cy = cy + side * self.BATTERY_ICON_Y_RATIO
        _paint_battery_icon_h(
            p,
            icon_cx,
            icon_cy,
            icon_w,
            icon_h,
            color,
            self._ratio,
        )

        # ---- 6. 电压大字 (居中略下) ----
        if self._value is None:
            text = "--.-"
            t_color = theme.FG_TERTIARY
        else:
            text = f"{self._value:.1f}"
            t_color = theme.FG_PRIMARY

        f = QFont(theme.FONT_MONO)
        f.setPointSize(int(side * 0.22))
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        text_y = cy + side * 0.10
        # 居中绘制 (水平 + 垂直)
        # ---- 7. "V" 单位 (与数字作为一个整体居中) ----
        unit = "V"
        f_unit = QFont(theme.FONT_MONO)
        f_unit.setPointSize(int(side * 0.10))
        f_unit.setBold(True)
        fm_unit = QFontMetrics(f_unit)
        text_w = fm.horizontalAdvance(text)
        unit_w = fm_unit.horizontalAdvance(unit)
        gap = max(4, int(side * 0.018))
        group_x = (w - text_w - gap - unit_w) / 2

        text_rect = QRectF(group_x, text_y - fm.ascent(), text_w, fm.height() + 4)
        p.setFont(f)
        p.setPen(QColor(t_color))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

        p.setFont(f_unit)
        unit_y = text_y + side * 0.045
        unit_rect = QRectF(group_x + text_w + gap, unit_y - fm_unit.height(),
                           unit_w, fm_unit.height())
        p.setPen(QColor(t_color))
        p.drawText(unit_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, unit)


class BatteryCard(QFrame):
    """Card that renders the latest battery voltage as an animated ring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(0)
        self.ring = BatteryRing()
        outer.addWidget(self.ring, 1)

    def update_from_sense(self, sense) -> None:
        if sense is None:
            self.ring.set_value(None)
            return
        self.ring.set_value(parse_volts(sense.batt_v))
