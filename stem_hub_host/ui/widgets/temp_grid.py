"""Animated 2×2 temperature sensor card."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
)
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


class ThermalGauge(QWidget):
    """Compact vertical gauge whose fill follows the sensor value."""

    RENDER_SCALE = 3
    MIN_CELSIUS = 0.0
    MAX_CELSIUS = 100.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(
            theme.TEMP_GAUGE_WIDTH,
            theme.TEMP_GAUGE_HEIGHT,
        )
        self._celsius: Optional[float] = None
        self._level = 0.0
        self._color = theme.FG_TERTIARY
        self._animation: QPropertyAnimation | None = None

    @property
    def celsius(self) -> Optional[float]:
        return self._celsius

    def _get_level(self) -> float:
        return self._level

    def _set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level)))
        self.update()

    level = Property(float, _get_level, _set_level)

    def set_value(
        self,
        celsius: Optional[float],
        *,
        animate: bool = True,
    ) -> None:
        self._celsius = celsius
        self._color = (
            theme.temp_color(celsius)
            if celsius is not None
            else theme.FG_TERTIARY
        )
        target = 0.0
        if celsius is not None:
            target = (
                float(celsius) - self.MIN_CELSIUS
            ) / (self.MAX_CELSIUS - self.MIN_CELSIUS)
            target = max(0.0, min(1.0, target))

        if self._animation is not None:
            self._animation.stop()
        if not animate:
            self._set_level(target)
            return

        animation = QPropertyAnimation(self, b"level", self)
        animation.setDuration(theme.ANIMATION_NORMAL_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(self._level)
        animation.setEndValue(target)
        animation.start()
        self._animation = animation

    def refresh_theme(self) -> None:
        self._color = (
            theme.temp_color(self._celsius)
            if self._celsius is not None
            else theme.FG_TERTIARY
        )
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        scale = self.RENDER_SCALE
        image = QImage(
            self.width() * scale,
            self.height() * scale,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)

        track = QRectF(8, 4, 18, self.height() - 8)
        radius = track.width() / 2
        painter.setPen(QPen(QColor(theme.BORDER_LIGHT), 1.0))
        painter.setBrush(QColor(theme.BG_INPUT))
        painter.drawRoundedRect(track, radius, radius)

        inner = track.adjusted(3, 3, -3, -3)
        fill_height = inner.height() * self._level
        if fill_height > 0.2:
            fill_rect = QRectF(
                inner.left(),
                inner.bottom() - fill_height,
                inner.width(),
                fill_height,
            )
            active_spectrum = QLinearGradient(
                fill_rect.left(),
                fill_rect.bottom(),
                fill_rect.left(),
                fill_rect.top(),
            )
            color = QColor(self._color)
            active_spectrum.setColorAt(0.0, color.darker(116))
            active_spectrum.setColorAt(1.0, color.lighter(106))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(active_spectrum)
            painter.drawRoundedRect(
                fill_rect,
                inner.width() / 2,
                inner.width() / 2,
            )

        painter.setPen(QPen(
            QColor(theme.FG_TERTIARY),
            1.0,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        ))
        for ratio, length in ((0.25, 6), (0.5, 9), (0.75, 6)):
            y = inner.bottom() - inner.height() * ratio
            painter.drawLine(
                QPointF(track.right() + 4, y),
                QPointF(track.right() + 4 + length, y),
            )
        painter.end()

        target = QPainter(self)
        target.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target.drawImage(self.rect(), image)


class TempTile(QFrame):
    """One animated temperature reading."""

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._celsius: Optional[float] = None
        self.setObjectName("tempTile")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.LAYOUT_MARGIN_CARD,
            theme.SP_SM,
            theme.LAYOUT_MARGIN_CARD_Y,
            theme.SP_SM,
        )
        layout.setSpacing(theme.SP_SM)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        self.gauge = ThermalGauge()
        layout.addWidget(
            self.gauge,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_column)

        self.value_label = QLabel("--")
        value_font = QFont(theme.FONT_MONO)
        value_font.setPointSize(20)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.value_label.setMinimumWidth(112)
        text_column.addWidget(self.value_label)

        self.title_label = QLabel(title)
        title_font = QFont(theme.FONT_DISPLAY)
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        text_column.addWidget(self.title_label)
        layout.addStretch(1)

        self.set_value(None, animate=False)

    def set_value(
        self,
        celsius: Optional[float],
        *,
        animate: bool = True,
    ) -> None:
        self._celsius = celsius
        if celsius is None:
            self.value_label.setText("--")
            self.value_label.setStyleSheet(
                f"color: {theme.FG_TERTIARY};"
                " background: transparent;"
            )
        else:
            self.value_label.setText(f"{celsius:.1f}°C")
            self.value_label.setStyleSheet(
                f"color: {theme.temp_color(celsius)};"
                " background: transparent;"
            )
        self.gauge.set_value(celsius, animate=animate)

    def refresh_theme(self) -> None:
        self.title_label.setStyleSheet(
            f"color: {theme.FG_SECONDARY};"
            " background: transparent;"
            " border: none;"
            " letter-spacing: 1.8px;"
        )
        self.gauge.refresh_theme()
        self.set_value(self._celsius, animate=False)


class TempGridCard(QFrame):
    """Responsive 2×2 grid of temperature sensors."""

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
            for tile in self._tiles():
                tile.set_value(None, animate=False)
            return
        self.tile_batt.set_value(parse_celsius(sense.batt_ntc))
        self.tile_ntc1.set_value(parse_celsius(sense.ntc1_c))
        self.tile_ntc2.set_value(parse_celsius(sense.ntc2_c))
        self.tile_ntc3.set_value(parse_celsius(sense.ntc3_c))

    def refresh_theme(self) -> None:
        for tile in self._tiles():
            tile.refresh_theme()

    def _tiles(self) -> tuple[TempTile, TempTile, TempTile, TempTile]:
        return (
            self.tile_batt,
            self.tile_ntc1,
            self.tile_ntc2,
            self.tile_ntc3,
        )
