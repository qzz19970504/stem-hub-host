"""FaultIndicator — 第四轮: LED 圆点 + 文字 (改进样式)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import theme


class _LEDDot(QWidget):
    """LED 圆点 — 实心 + 外圈描边."""

    def __init__(self, color: str = theme.STATUS_OFF, size: int = 12, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(QSize(size, size))

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height())
        cx = s / 2
        cy = s / 2
        # 外圈 (实心)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(int(cx - s / 2 + 1), int(cy - s / 2 + 1),
                      int(s - 2), int(s - 2))


class FaultIndicator(QWidget):
    """小圆点 + 文字."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = "off"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.dot = _LEDDot()
        lay.addWidget(self.dot)

        self.label = QLabel(label)
        label_font = QFont(theme.FONT_DISPLAY)
        label_font.setPointSize(11)
        label_font.setBold(True)
        self.label.setFont(label_font)
        self.label.setStyleSheet(
            f"color: {theme.FG_SECONDARY}; letter-spacing: 1.2px;"
        )
        lay.addWidget(self.label)
        lay.addStretch(0)
        self.set_state("off")

    def set_state(self, state: str) -> None:
        self._state = state
        self.dot.set_color(_state_to_color(state))
        text_color = _state_to_text_color(state)
        self.label.setStyleSheet(
            f"color: {text_color}; letter-spacing: 1.2px; font-weight: 700;"
        )

    @property
    def state(self) -> str:
        """Return the semantic state currently represented by the indicator."""

        return self._state

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def refresh_theme(self) -> None:
        self.set_state(self._state)


def _state_to_color(state: str) -> str:
    return {
        "ok": theme.STATUS_OK,
        "warn": theme.STATUS_WARN,
        "error": theme.STATUS_ERROR,
        "off": theme.STATUS_OFF,
    }.get(state, theme.STATUS_OFF)


def _state_to_text_color(state: str) -> str:
    return {
        "ok": theme.STATUS_OK,
        "warn": theme.STATUS_WARN,
        "error": theme.STATUS_ERROR,
        "off": theme.FG_SECONDARY,
    }.get(state, theme.FG_SECONDARY)
