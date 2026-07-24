"""UART 透传面板.

功能:
- 桥接开关: 仅 UART2 / 仅 UART3 / UART2&3 / 全部关闭 (4 态互斥)
- 发送框: 多行输入 + hex/文本切换
- 接收区: 滚动显示, hex + 文本双视图
- 计数: TX / RX 字节
- 清空 / 自动滚动
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .. import theme


_HEX_CHARS = "0123456789ABCDEF"


def text_to_bytes(s: str) -> bytes:
    """'AA BB CC' -> b'\\xaa\\xbb\\xcc' (允许空格 / '-' 分隔, 大小写无关)."""
    cleaned = s.replace(",", " ").replace("-", " ")
    cleaned = "".join(c for c in cleaned if c in _HEX_CHARS or c.isspace())
    parts = cleaned.split()
    try:
        return bytes(int(p, 16) for p in parts if p)
    except ValueError:
        return b""


def bytes_to_hex(b: bytes) -> str:
    """b'\\xaa\\xbb' -> 'AA BB'."""
    return " ".join(f"{x:02X}" for x in b)


def bytes_to_text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1", errors="replace")


class PassthroughPanel(QFrame):
    """UART 透传面板."""

    # mode: 'uart2' / 'uart3' / 'both' / 'off'
    bridge_changed = Signal(str)
    # 发送 (bytes)
    tx_requested = Signal(bytes)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("passthroughLayout")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._tx_buffer = bytearray()
        self._rx_buffer = bytearray()
        self._auto_scroll = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(theme.GRID_GAP)

        # 桥接模式 — 与全局按钮语言一致的 segmented chips。
        self.bridge_panel = QFrame(self)
        self.bridge_panel.setObjectName("card")
        bridge_row = QHBoxLayout(self.bridge_panel)
        bridge_row.setContentsMargins(14, 10, 14, 10)
        bridge_row.setSpacing(8)
        outer.addWidget(self.bridge_panel)

        bridge_title = QLabel("UART BRIDGE")
        bridge_title.setObjectName("sectionTitle")
        bridge_row.addWidget(bridge_title)
        bridge_row.addSpacing(8)
        self.btn_uart2 = QRadioButton("UART2")
        self.btn_uart3 = QRadioButton("UART3")
        self.btn_both = QRadioButton("UART2 + UART3")
        self.btn_off = QRadioButton("BRIDGE OFF")
        self.btn_off.setChecked(True)
        for control in (
            self.btn_uart2,
            self.btn_uart3,
            self.btn_both,
            self.btn_off,
        ):
            control.setObjectName("modeChip")
            control.setCursor(Qt.CursorShape.PointingHandCursor)
            bridge_row.addWidget(control)
        bridge_row.addStretch(1)

        self._bridge_group = QButtonGroup(self)
        self._bridge_group.setExclusive(True)
        for b in (self.btn_uart2, self.btn_uart3, self.btn_both, self.btn_off):
            self._bridge_group.addButton(b)
        self._bridge_group.buttonClicked.connect(self._on_bridge_changed)

        # 主区域: 左发送 / 右接收
        body = QHBoxLayout()
        body.setSpacing(theme.GRID_GAP)
        outer.addLayout(body, 1)

        # 发送
        self.tx_panel = QFrame(self)
        self.tx_panel.setObjectName("card")
        tx_col = QVBoxLayout(self.tx_panel)
        tx_col.setContentsMargins(14, 14, 14, 14)
        tx_col.setSpacing(10)
        body.addWidget(self.tx_panel, 1)

        tx_header = QHBoxLayout()
        tx_col.addLayout(tx_header)
        tx_title = QLabel("TRANSMIT")
        tx_title.setObjectName("sectionTitle")
        tx_header.addWidget(tx_title)
        self.hex_mode_cb = QCheckBox("HEX MODE")
        self.hex_mode_cb.toggled.connect(self._on_hex_mode_toggled)
        tx_header.addWidget(self.hex_mode_cb)
        tx_header.addStretch(1)

        self.tx_edit = QPlainTextEdit()
        self.tx_edit.setPlaceholderText(
            "文本模式: 直接输入文本, 自动补 CRLF\n"
            "Hex 模式: 输入 AA BB CC DD ..."
        )
        self.tx_edit.setMinimumHeight(240)
        tx_col.addWidget(self.tx_edit)

        tx_btn_row = QHBoxLayout()
        tx_col.addLayout(tx_btn_row)
        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("primary")
        self.send_btn.clicked.connect(self._on_send)
        tx_btn_row.addWidget(self.send_btn)
        self.clear_tx_btn = QPushButton("CLEAR TX")
        self.clear_tx_btn.setObjectName("secondaryAction")
        self.clear_tx_btn.clicked.connect(lambda: self.tx_edit.clear())
        tx_btn_row.addWidget(self.clear_tx_btn)
        tx_btn_row.addStretch(1)

        self.tx_count_label = QLabel("TX: 0 字节")
        self.tx_count_label.setObjectName("secondary")
        tx_btn_row.addSpacing(12)
        tx_btn_row.addWidget(self.tx_count_label)

        # 接收
        self.rx_panel = QFrame(self)
        self.rx_panel.setObjectName("card")
        rx_col = QVBoxLayout(self.rx_panel)
        rx_col.setContentsMargins(14, 14, 14, 14)
        rx_col.setSpacing(10)
        body.addWidget(self.rx_panel, 1)

        rx_header = QHBoxLayout()
        rx_col.addLayout(rx_header)
        rx_title = QLabel("RECEIVE")
        rx_title.setObjectName("sectionTitle")
        rx_header.addWidget(rx_title)
        self.show_hex_cb = QCheckBox("HEX VIEW")
        self.show_hex_cb.setChecked(False)
        self.show_hex_cb.toggled.connect(self._refresh_rx_view)
        rx_header.addWidget(self.show_hex_cb)
        self.auto_scroll_cb = QCheckBox("AUTO SCROLL")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(
            lambda c: setattr(self, "_auto_scroll", c)
        )
        rx_header.addWidget(self.auto_scroll_cb)
        rx_header.addStretch(1)

        self.rx_view = QPlainTextEdit()
        self.rx_view.setReadOnly(True)
        self.rx_view.setMaximumBlockCount(2000)
        self.rx_view.setFont(QFont(theme.FONT_MONO, 11))
        rx_col.addWidget(self.rx_view, 1)

        # RX panel footer
        bottom = QHBoxLayout()
        rx_col.addLayout(bottom)
        self.rx_count_label = QLabel("RX: 0 字节")
        self.rx_count_label.setObjectName("secondary")
        bottom.addWidget(self.rx_count_label)
        bottom.addStretch(1)
        self.clear_rx_btn = QPushButton("CLEAR RX")
        self.clear_rx_btn.setObjectName("secondaryAction")
        self.clear_rx_btn.clicked.connect(self._clear_rx)
        bottom.addWidget(self.clear_rx_btn)

    # ---- API ----
    def feed_rx(self, data: bytes) -> None:
        """从 SerialWorker 收到透传数据时调."""
        self._rx_buffer.extend(data)
        self._rx_bytes += len(data)
        self._refresh_rx_view()
        self.rx_count_label.setText(f"RX: {self._rx_bytes} 字节")

    def reset(self) -> None:
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._tx_buffer.clear()
        self._rx_buffer.clear()
        self._refresh_rx_view()
        self._refresh_count()

    # ---- 内部 ----
    def _on_bridge_changed(self, btn: QRadioButton) -> None:
        if btn is self.btn_uart2:
            mode = "uart2"
        elif btn is self.btn_uart3:
            mode = "uart3"
        elif btn is self.btn_both:
            mode = "both"
        else:
            mode = "off"
        self.bridge_changed.emit(mode)

    def _on_hex_mode_toggled(self, hex_mode: bool) -> None:
        if hex_mode:
            self.tx_edit.setPlaceholderText("Hex 模式: AA BB CC DD ...（自动补 CRLF）")
        else:
            self.tx_edit.setPlaceholderText("文本模式: 直接输入文本")

    def _on_send(self) -> None:
        text = self.tx_edit.toPlainText()
        if not text:
            return
        is_hex = self.hex_mode_cb.isChecked()
        if is_hex:
            data = text_to_bytes(text)
        else:
            data = text.encode("utf-8")
        if not data:
            return
        if not data.endswith(b"\r\n"):
            data += b"\r\n"
        self.tx_requested.emit(data)

    def confirm_tx_sent(self, byte_count: int) -> None:
        """Commit UI state only after the transport accepted the bytes."""
        self._tx_bytes += byte_count
        self._refresh_count()
        self.tx_edit.clear()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.set_bridge_controls_enabled(enabled)
        self.set_tx_controls_enabled(enabled)

    def set_bridge_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.btn_uart2,
            self.btn_uart3,
            self.btn_both,
            self.btn_off,
        ):
            control.setEnabled(enabled)

    def set_tx_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.hex_mode_cb,
            self.tx_edit,
            self.send_btn,
            self.clear_tx_btn,
        ):
            control.setEnabled(enabled)

    def set_bridge_mode(self, mode: str) -> None:
        target = {
            "uart2": self.btn_uart2,
            "uart3": self.btn_uart3,
            "both": self.btn_both,
            "off": self.btn_off,
        }.get(mode, self.btn_off)
        blocked = self._bridge_group.signalsBlocked()
        self._bridge_group.blockSignals(True)
        target.setChecked(True)
        self._bridge_group.blockSignals(blocked)

    def _refresh_rx_view(self) -> None:
        if self.show_hex_cb.isChecked():
            display = bytes_to_hex(self._rx_buffer)
        else:
            display = bytes_to_text(bytes(self._rx_buffer))
        self.rx_view.setPlainText(display)
        if self._auto_scroll:
            sb = self.rx_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _clear_rx(self) -> None:
        self._rx_buffer.clear()
        self._refresh_rx_view()

    def _refresh_count(self) -> None:
        self.tx_count_label.setText(f"TX: {self._tx_bytes} 字节")
        self.rx_count_label.setText(f"RX: {self._rx_bytes} 字节")
