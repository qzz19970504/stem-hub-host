"""串口工作线程.

设计:
- 持有一个 Transport (RealSerialTransport 或 FakeSerialTransport)
- 用 LineSplitter 切出完整行
- 每行 parse 成 ParsedResponse
- 按发送顺序 FIFO 处理响应: +XXX:... → data 行; OK / ERROR → 完成 future
- 透传行 → 发 passthrough_received signal, 不进 future 队列

高层 API:
- open(port_name, baudrate=115200) -> bool
- close()
- send_and_wait(cmd: str, timeout_ms: int) -> ParsedResponse  (throws on error / timeout)
- send_only(cmd: str)  (不等回包, 用在状态广播类场景)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal

from .at_protocol import LineSplitter, ParsedResponse
from .transport import RealSerialTransport, Transport


class SerialError(Exception):
    """串口/协议层错误."""


class SerialTimeout(SerialError):
    """等待响应超时."""


@dataclass
class _Pending:
    command: str
    on_data: Optional[ParsedResponse] = None
    finished: bool = False
    timeout_timer: Optional[QTimer] = None


class SerialWorker(QObject):
    """串口 worker, 必须在 QApplication 主事件循环里使用."""

    connected = Signal(str, int)  # (port_name, baudrate)
    disconnected = Signal()
    error_occurred = Signal(str)

    response_received = Signal(str, ParsedResponse)  # (command, response)
    passthrough_received = Signal(bytes)
    uart_rx_received = Signal(int, bytes)
    at_data_received = Signal(str, ParsedResponse)  # (command, data response)

    def __init__(
        self,
        transport: Transport | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._transport: Transport = transport or RealSerialTransport(self)
        self._splitter = LineSplitter()
        self._pending: Deque[_Pending] = deque()
        self._is_open = False
        self._port_name = ""
        self._baudrate = 0
        self._passthrough_raw = False

        # 连接信号
        self._transport.ready_read.connect(self._on_ready_read)
        self._transport.error_occurred.connect(self._on_port_error)

    # ---- 公开 API ----
    @staticmethod
    def list_ports():
        from .transport import list_serial_ports
        return list_serial_ports()

    def is_open(self) -> bool:
        return self._is_open

    def open(self, port_name: str, baudrate: int = 115200) -> bool:
        if self._is_open:
            self.close()
        if not self._transport.open(port_name, baudrate):
            self.error_occurred.emit(
                f"打开串口失败: {self._transport.error_string()}"
            )
            return False
        self._is_open = True
        self._port_name = port_name
        self._baudrate = baudrate
        self._splitter.reset()
        self._pending.clear()
        self.connected.emit(port_name, baudrate)
        return True

    def close(self) -> None:
        if self._is_open:
            for pending in self._pending:
                self._dispose_timeout_timer(pending)
            self._transport.close()
            self._is_open = False
            self._pending.clear()
            self.disconnected.emit()

    def send_only(self, cmd: str) -> None:
        self.send_bytes(cmd.encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        """Write an exact byte sequence without text transcoding."""
        if not self._is_open:
            raise SerialError("串口未打开")
        n = self._transport.write(data)
        if n != len(data):
            raise SerialError(f"串口写入不完整: 写了 {n}/{len(data)}")

    def send_command(self, cmd: str, timeout_ms: int = 1000) -> None:
        """Queue an AT command so its eventual OK/ERROR keeps attribution."""
        pending = _Pending(command=cmd)
        self._pending.append(pending)
        try:
            self.send_only(cmd)
        except SerialError:
            self._pending.remove(pending)
            raise
        if timeout_ms > 0:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._on_async_timeout(pending))
            pending.timeout_timer = timer
            timer.start(timeout_ms)

    def set_passthrough_raw(self, enabled: bool) -> None:
        """Compatibility shim; the framed tunnel always keeps line parsing active."""
        self._passthrough_raw = False

    def _on_async_timeout(self, pending: _Pending) -> None:
        if pending.finished or pending not in self._pending:
            return
        self.error_occurred.emit(
            f"命令响应超时，串口已断开以重新同步: {pending.command!r}"
        )
        self.close()

    @staticmethod
    def _dispose_timeout_timer(pending: _Pending) -> None:
        timer = pending.timeout_timer
        if timer is None:
            return
        pending.timeout_timer = None
        timer.stop()
        timer.timeout.disconnect()
        timer.setParent(None)
        timer.deleteLater()

    def send_and_wait(self, cmd: str, timeout_ms: int = 1000) -> ParsedResponse:
        """发命令并等待回包.

        返回的 ParsedResponse 优先包含 data 行 (+XXX:...) 的字段;
        如果只有 OK 行, 则只设 ok=True. 如果是 ERROR, error 不为 None.
        """
        if not self._is_open:
            raise SerialError("串口未打开")

        pending = _Pending(command=cmd)
        self._pending.append(pending)
        try:
            self.send_only(cmd)
        except SerialError:
            self._pending.remove(pending)
            raise

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        captured: dict[str, ParsedResponse] = {}

        def _on_data(command: str, response: ParsedResponse) -> None:
            # data 行先到: 暂存到 pending.on_data (handler 已经做了),
            # 但要捕获以便 response_received 时合并
            if command == cmd:
                captured["data"] = response

        def _on_response(command: str, response: ParsedResponse) -> None:
            if command == cmd and "resp" not in captured:
                # 把 data 行的字段 merge 到 response 上
                if "data" in captured and response.ok:
                    d = captured["data"]
                    response.sense = d.sense or response.sense
                    response.fault = d.fault or response.fault
                    response.motor = d.motor or response.motor
                    response.version = d.version or response.version
                    response.diag = d.diag or response.diag
                captured["resp"] = response
                loop.quit()

        def _on_timeout() -> None:
            loop.quit()

        self.at_data_received.connect(_on_data)
        self.response_received.connect(_on_response)
        timer.timeout.connect(_on_timeout)
        if timeout_ms > 0:
            timer.start(timeout_ms)
        try:
            loop.exec()
        finally:
            self.at_data_received.disconnect(_on_data)
            self.response_received.disconnect(_on_response)
            timer.stop()
            try:
                self._pending.remove(pending)
            except ValueError:
                pass

        if "resp" in captured:
            return captured["resp"]
        raise SerialTimeout(f"等待响应超时 ({timeout_ms}ms): {cmd!r}")

    # ---- 内部 ----
    def _on_ready_read(self) -> None:
        data = self._transport.read_all()
        if not data:
            return
        for raw_line in self._splitter.feed_raw(data):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                line = raw_line.decode("latin-1")
            self._handle_line(line, raw_line)

    def _on_port_error(self) -> None:
        # transport 端已经过滤 NoError, 这里只管发错误消息
        self.error_occurred.emit(f"串口错误: {self._transport.error_string()}")

    def _handle_line(self, line: str, raw_line: bytes | None = None) -> None:
        resp = ParsedResponse.parse(line)

        if resp.uart_rx is not None:
            self.uart_rx_received.emit(
                resp.uart_rx.uart_index,
                resp.uart_rx.payload,
            )
            return

        if resp.is_passthrough:
            self.passthrough_received.emit(
                raw_line if raw_line is not None else line.encode("utf-8")
            )
            return

        cur = None
        for p in self._pending:
            if not p.finished:
                cur = p
                break
        if cur is None:
            self.at_data_received.emit("", resp)
            return

        if resp.ok or resp.error is not None:
            self._dispose_timeout_timer(cur)
            if cur.on_data is not None and resp.ok:
                data = cur.on_data
                resp.sense = data.sense or resp.sense
                resp.fault = data.fault or resp.fault
                resp.motor = data.motor or resp.motor
                resp.version = data.version or resp.version
                resp.diag = data.diag or resp.diag
            cur.finished = True
            self.response_received.emit(cur.command, resp)
        elif resp.sense or resp.fault or resp.motor or resp.version or resp.diag:
            cur.on_data = resp
            self.at_data_received.emit(cur.command, resp)

        while self._pending and self._pending[0].finished:
            self._pending.popleft()
