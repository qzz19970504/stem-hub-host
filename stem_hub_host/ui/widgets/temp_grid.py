"""TempGridCard — 第四轮: 改进图标 + 完美对齐."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from .battery_card import parse_celsius


class ThermometerIcon(QWidget):
    """Clean circular sensor glyph with a minimal thermometer silhouette."""

    RENDER_SCALE = 3

    def __init__(self, size: int = 46, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = theme.ACCENT

    def set_color(self, c: str) -> None:
        self._color = c
        self.update()

    def paintEvent(self, _ev) -> None:
        scale = self.RENDER_SCALE
        image = QImage(
            self.width() * scale,
            self.height() * scale,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(scale, scale)
        s = min(self.width(), self.height())
        color = QColor(self._color)
        center = QPointF(s / 2, s / 2)
        halo = QColor(color)
        halo.setAlpha(28)
        outline = QColor(color)
        outline.setAlpha(105)
        p.setPen(QPen(outline, 1))
        p.setBrush(halo)
        p.drawEllipse(center, s * 0.44, s * 0.44)

        pen_w = max(1.6, s * 0.055)
        cx = s * 0.43
        bulb_cy = s * 0.68
        bulb_r = s * 0.105
        stem = QRectF(
            cx - s * 0.075,
            s * 0.24,
            s * 0.15,
            s * 0.39,
        )
        p.setPen(QPen(
            color,
            pen_w,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        ))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(stem, stem.width() / 2, stem.width() / 2)
        p.drawEllipse(QPointF(cx, bulb_cy), bulb_r, bulb_r)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        column_w = s * 0.045
        p.drawRoundedRect(
            QRectF(
                cx - column_w / 2,
                s * 0.42,
                column_w,
                bulb_cy - s * 0.42,
            ),
            column_w / 2,
            column_w / 2,
        )
        p.drawEllipse(QPointF(cx, bulb_cy), bulb_r * 0.62, bulb_r * 0.62)

        p.setPen(QPen(color, max(1.2, pen_w * 0.7), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        for y, length in ((0.32, 0.10), (0.43, 0.07), (0.54, 0.10)):
            p.drawLine(
                QPointF(s * 0.62, s * y),
                QPointF(s * (0.62 + length), s * y),
            )
        p.end()

        target = QPainter(self)
        target.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target.drawImage(self.rect(), image)


class TempTile(QFrame):
    """温度小卡 — 严格水平对齐."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._celsius: Optional[float] = None
        self.setObjectName("tempTile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 严格布局: 左 44px 图标 + 右 弹性文字栏
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)

        # 图标 (固定大小, 垂直居中)
        self.icon = ThermometerIcon(size=42)
        self.icon.setMinimumWidth(42)
        self.icon.setMaximumWidth(42)
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        # 文字栏 (弹性宽度, 垂直居中)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(text_col)

        # 大温度数值
        self.value_label = QLabel("--")
        f_val = QFont(theme.FONT_MONO)
        f_val.setPointSize(20)
        f_val.setBold(True)
        self.value_label.setFont(f_val)
        self.value_label.setStyleSheet(
            f"color: {theme.FG_PRIMARY}; background: transparent;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setMinimumWidth(112)
        text_col.addWidget(self.value_label)

        # 标签
        self.title_label = QLabel(title)
        f_lbl = QFont(theme.FONT_DISPLAY)
        f_lbl.setPointSize(11)
        f_lbl.setBold(True)
        self.title_label.setFont(f_lbl)
        self.title_label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; "
            f"border: none; letter-spacing: 1.8px;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_col.addWidget(self.title_label)
        lay.addStretch(1)

        self.set_value(None)

    def set_value(self, celsius: Optional[float]) -> None:
        self._celsius = celsius
        if celsius is None:
            self.value_label.setText("--")
            self.value_label.setStyleSheet(
                f"color: {theme.FG_TERTIARY}; background: transparent;"
            )
            self.icon.set_color(theme.FG_TERTIARY)
        else:
            self.value_label.setText(f"{celsius:.1f}°C")
            color = theme.temp_color(celsius)
            self.value_label.setStyleSheet(
                f"color: {theme.FG_PRIMARY}; background: transparent;"
            )
            self.icon.set_color(color)

    def refresh_theme(self) -> None:
        self.title_label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; background: transparent; "
            f"border: none; letter-spacing: 1.8px;"
        )
        self.set_value(self._celsius)


class TempGridCard(QFrame):
    """2x2 温度卡 — 外框 + 内嵌 4 个小卡."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tempGrid")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            "QFrame#tempGrid { background: transparent; border: none; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        grid = QGridLayout()
        grid.setSpacing(theme.GRID_GAP)
        outer.addLayout(grid, 1)

        self.tile_batt = TempTile("BATTERY")
        self.tile_ntc1 = TempTile("NTC1")
        self.tile_ntc2 = TempTile("NTC2")
        self.tile_ntc3 = TempTile("NTC3")

        grid.addWidget(self.tile_batt, 0, 0)
        grid.addWidget(self.tile_ntc1, 0, 1)
        grid.addWidget(self.tile_ntc2, 1, 0)
        grid.addWidget(self.tile_ntc3, 1, 1)

    def update_from_sense(self, sense) -> None:
        if sense is None:
            for t in (
                self.tile_batt,
                self.tile_ntc1,
                self.tile_ntc2,
                self.tile_ntc3,
            ):
                t.set_value(None)
            return
        self.tile_batt.set_value(parse_celsius(sense.batt_ntc))
        self.tile_ntc1.set_value(parse_celsius(sense.ntc1_c))
        self.tile_ntc2.set_value(parse_celsius(sense.ntc2_c))
        self.tile_ntc3.set_value(parse_celsius(sense.ntc3_c))

    def refresh_theme(self) -> None:
        for tile in (
            self.tile_batt,
            self.tile_ntc1,
            self.tile_ntc2,
            self.tile_ntc3,
        ):
            tile.refresh_theme()
