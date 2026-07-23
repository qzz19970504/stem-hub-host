"""AT 指令控制台 — 第四轮 (log 无边框, send 区一个框 + SEND 按钮)."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import theme


class AtConsole(QFrame):
    """AT 指令控制台 — 一整块框 + cyan 辉光.

    - log 区: 背景同卡片色, 无边框
    - 发送区: 一个圆角框 (含 > 提示符, 输入框, SEND 按钮)
    """

    send_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._entries: list[tuple[str, str]] = []
        # cyan 外发光
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(12)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(theme.ACCENT_DEEP))
        self.setGraphicsEffect(self._glow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        # log 区 — 无边框, 仅背景同卡片色
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setFrameShape(QFrame.Shape.NoFrame)
        f_log = QFont(theme.FONT_MONO)
        f_log.setPointSize(13)
        self.log_view.setFont(f_log)
        outer.addWidget(self.log_view, 1)

        # 发送区 — 一个圆角框
        self.command_bar = QFrame()
        self.command_bar.setObjectName("commandBar")
        send_row = QHBoxLayout(self.command_bar)
        send_row.setContentsMargins(14, 8, 14, 8)
        send_row.setSpacing(10)

        # > 提示符
        self.prompt = QLabel(">")
        f_p = QFont(theme.FONT_MONO)
        f_p.setPointSize(16)
        f_p.setBold(True)
        self.prompt.setFont(f_p)
        self.prompt.setFixedWidth(18)
        send_row.addWidget(self.prompt)

        # 输入框 (无边框, 透明背景融入 send_bar)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("AT+SENSE?")
        self.input_edit.returnPressed.connect(self._on_send)
        self.input_edit.setFixedHeight(36)
        f_in = QFont(theme.FONT_MONO)
        f_in.setPointSize(13)
        self.input_edit.setFont(f_in)
        send_row.addWidget(self.input_edit, 1)

        # SEND 按钮
        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("primary")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedHeight(36)
        self.send_btn.setMinimumWidth(110)
        f_btn = QFont(theme.FONT_DISPLAY)
        f_btn.setPointSize(13)
        f_btn.setBold(True)
        self.send_btn.setFont(f_btn)
        self.send_btn.clicked.connect(self._on_send)
        send_row.addWidget(self.send_btn)

        outer.addWidget(self.command_bar)
        self.refresh_theme()

    def _on_send(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.append_log("TX", text)
        cmd = text if text.endswith("\r\n") else text + "\r\n"
        self.send_requested.emit(cmd)
        self.input_edit.clear()

    def append_log(self, direction: str, text: str) -> None:
        self._entries.append((direction, text))
        if len(self._entries) > 2000:
            del self._entries[: len(self._entries) - 2000]
        self._append_rendered_entry(direction, text)

    def _append_rendered_entry(self, direction: str, text: str) -> None:
        prefix_map = {
            "TX":  (">>", theme.ACCENT),
            "RX":  ("<<", theme.STATUS_OK),
            "INFO": ("··", theme.FG_SECONDARY),
            "ERR": ("!!", theme.STATUS_ERROR),
        }
        prefix, color = prefix_map.get(direction, ("??", theme.FG_PRIMARY))
        normalized_text = text.replace("\r\n", "↵\n").replace("\r", "↵")
        escaped_text = escape(normalized_text)
        escaped_prefix = escape(prefix)
        message_color = color
        if direction == "RX" and normalized_text.strip() != "OK":
            message_color = theme.FG_PRIMARY
        self.log_view.appendHtml(
            f'<span style="color: {color}; font-weight: 700;">{escaped_prefix}</span> '
            f'<span style="color: {message_color}; font-family: \'{theme.FONT_MONO}\';">'
            f"{escaped_text}</span>"
        )
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_theme(self) -> None:
        self._glow.setColor(QColor(theme.ACCENT_DEEP))
        self.log_view.setStyleSheet(
            "QPlainTextEdit {"
            "  background: transparent;"
            f"  color: {theme.FG_PRIMARY};"
            "  border: none;"
            "  padding: 8px;"
            "}"
        )
        self.prompt.setStyleSheet(
            f"color: {theme.ACCENT}; background: transparent; border: none;"
        )
        self.input_edit.setStyleSheet(
            "QLineEdit {"
            "  background: transparent;"
            f"  color: {theme.FG_PRIMARY};"
            "  border: none;"
            "  padding: 4px 8px;"
            f"  selection-background-color: {theme.ACCENT};"
            f"  selection-color: {theme.BG_BASE};"
            "}"
        )
        if self._entries:
            entries = list(self._entries)
            self.log_view.clear()
            for direction, text in entries:
                self._append_rendered_entry(direction, text)

    def append_info(self, text: str) -> None:
        self.append_log("INFO", text)

    def append_error(self, text: str) -> None:
        self.append_log("ERR", text)
