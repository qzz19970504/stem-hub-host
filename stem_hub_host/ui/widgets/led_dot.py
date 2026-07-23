"""LED 状态点 — 实心圆 + 颜色对应 OK/WARN/ERROR/OFF."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QWidget

from .. import theme


class LedDot(QWidget):
    """简单 LED 圆点 — 实心."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = theme.STATUS_OFF
        self.setFixedSize(QSize(12, 12))

    def set_state(self, state: str) -> None:
        m = {
            "ok": theme.STATUS_OK,
            "warn": theme.STATUS_WARN,
            "error": theme.STATUS_ERROR,
            "off": theme.STATUS_OFF,
        }
        self._color = m.get(state, theme.STATUS_OFF)
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 实心圆
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self._color)))
        p.drawEllipse(2, 2, self.width() - 4, self.height() - 4)