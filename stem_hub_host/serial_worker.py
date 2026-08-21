"""串口工作线程.

设计:
- 持有一个 Transport (RealSerialTransport 或 FakeSerialTransport)
- 用 LineSplitter 切出完整行
- 每行 parse 成 ParsedResponse
- 按发送顺序 FIFO 处理响应: +XXX:... → data 行; OK / ERROR → 完成 future
- 透传行 → 发 passthrough_received signal, 不进 future 队列

高层 API:
- open(port_name, baudrate=9600) -> bool
- close()
- send_and_wait(cmd: str, timeout_ms: int) -> ParsedResponse  (throws on error / timeout)
- send_only(cmd: str)  (不等回包, 用在状态广播类场景)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
from typing import Callable, Deque, Optional

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal

from .at_protocol import LineSplitter, ParsedResponse
from .models import AtError
from .transport import RealSerialTransport, Transport


RESYNCHRONIZATION_QUIET_MS = 200
TRANSPARENT_ESCAPE = b"+++"
UART_FRAME_BITS = 10


class SerialSessionState(Enum):
    """Current host-side interpretation of the UART1 communication mode."""

    AT = "at"
    ENTERING = "entering"
    TRANSPARENT = "transparent"
    EXITING = "exiting"


class SerialError(Exception):
    """串口/协议层错误."""


class SerialTimeout(SerialError):
    """等待响应超时."""


@dataclass
class _Pending:
    command: str
    timeout_ms: int = 0
    on_data: Optional[ParsedResponse] = None
    completion_callback: Optional[Callable[[ParsedResponse], None]] = None
    timeout_callback: Optional[Callable[[], None]] = None
    finished: bool = False
    has_been_sent: bool = False
    timeout_timer: Optional[QTimer] = None
    transition: Optional[str] = None


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
        self._session_state = SerialSessionState.AT
        self._is_resynchronizing = False
        self._transparent_exit_timeout_ms = 0
        self._transparent_guard_timer = QTimer(self)
        self._transparent_guard_timer.setObjectName("transparentGuardTimer")
        self._transparent_guard_timer.setSingleShot(True)
        self._transparent_guard_timer.timeout.connect(
            self._write_transparent_escape
        )
        self._resynchronization_timer = QTimer(self)
        self._resynchronization_timer.setObjectName(
            "serialResynchronizationTimer"
        )
        self._resynchronization_timer.setSingleShot(True)
        self._resynchronization_timer.timeout.connect(
            self._finish_resynchronization
        )

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

    def is_resynchronizing(self) -> bool:
        return self._is_resynchronizing

    @property
    def session_state(self) -> SerialSessionState:
        """Return the host's current UART1 session state."""
        return self._session_state

    def open(self, port_name: str, baudrate: int = 9600) -> bool:
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
        self._session_state = SerialSessionState.AT
        self._transparent_guard_timer.stop()
        self._resynchronization_timer.stop()
        self._is_resynchronizing = False
        self.connected.emit(port_name, baudrate)
        return True

    def close(self) -> None:
        if self._is_open:
            abandoned = list(self._pending)
            self._pending.clear()
            for pending in abandoned:
                self._dispose_timeout_timer(pending)
            self._transport.close()
            self._is_open = False
            self._session_state = SerialSessionState.AT
            self._transparent_guard_timer.stop()
            self._resynchronization_timer.stop()
            self._is_resynchronizing = False
            self._splitter.reset()
            for pending in abandoned:
                pending.finished = True
                if pending.timeout_callback is not None:
                    pending.timeout_callback()
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
        self._ensure_command_can_be_sent()
        pending = _Pending(command=cmd, timeout_ms=timeout_ms)
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            raise

    def enter_transparent(self, command: str, timeout_ms: int = 1000) -> None:
        """Send one AT entry command and switch state only after its response."""
        self._ensure_command_can_be_sent()
        pending = _Pending(
            command=command,
            timeout_ms=timeout_ms,
            transition="enter",
        )
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            raise

    def send_transparent(self, data: bytes) -> None:
        """Write exact payload bytes while an exclusive session is active."""
        if self._session_state is not SerialSessionState.TRANSPARENT:
            raise SerialError("transparent payload requires transparent mode")
        if not data:
            raise SerialError("transparent payload must not be empty")
        if data == TRANSPARENT_ESCAPE:
            raise SerialError("reserved escape sequence cannot be payload")
        try:
            self.send_bytes(data)
        except SerialError:
            # A partial raw write leaves the host unable to know how much the
            # downstream device received. Force a reconnect instead of
            # continuing with divergent session state.
            self.close()
            raise

    def exit_transparent(
        self,
        *,
        timeout_ms: int = 1000,
        guard_ms: int = 10,
    ) -> None:
        """Write the guarded escape and wait for the firmware's final OK."""
        if self._session_state is not SerialSessionState.TRANSPARENT:
            raise SerialError("transparent exit requires transparent mode")
        if self._pending:
            raise SerialError("transparent exit requires an idle response queue")
        if timeout_ms <= 0 or guard_ms < 1:
            raise ValueError("transparent exit timing must be positive")
        self._session_state = SerialSessionState.EXITING
        self._transparent_exit_timeout_ms = timeout_ms
        try:
            drained = self._transport.wait_for_bytes_written(timeout_ms)
        except Exception as error:
            self.error_occurred.emit(f"等待透明传输写入完成失败: {error}")
            self.close()
            return
        if not drained:
            self.error_occurred.emit("透明传输写入排空超时，串口已关闭")
            self.close()
            return
        # bytesToWrite()==0 means the final byte has reached the serial driver.
        # Allow one full 8N1 frame to leave the UART, then begin the required
        # quiet interval before transmitting the escape sequence.
        final_frame_ms = math.ceil(UART_FRAME_BITS * 1000 / self._baudrate)
        self._transparent_guard_timer.start(final_frame_ms + guard_ms)

    def _write_transparent_escape(self) -> None:
        if (
            not self._is_open
            or self._session_state is not SerialSessionState.EXITING
        ):
            return
        pending = _Pending(
            command=TRANSPARENT_ESCAPE.decode("ascii"),
            timeout_ms=self._transparent_exit_timeout_ms,
            transition="exit",
        )
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            self.error_occurred.emit("透明传输退出序列写入失败")
            self.close()

    def set_passthrough_raw(self, enabled: bool) -> None:
        """Compatibility shim; the framed tunnel always keeps line parsing active."""
        self._passthrough_raw = False

    def _on_async_timeout(self, pending: _Pending) -> None:
        if pending.finished or pending not in self._pending:
            return
        if pending.transition == "exit":
            self.error_occurred.emit("透明传输退出超时，串口已关闭")
            self.close()
            return
        if pending.transition == "enter":
            self._session_state = SerialSessionState.AT
        self._begin_resynchronization(pending.command)

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
        self._ensure_command_can_be_sent()

        loop = QEventLoop()
        captured: dict[str, ParsedResponse] = {}
        did_timeout = False

        def _on_completed(response: ParsedResponse) -> None:
            captured["response"] = response
            loop.quit()

        def _on_timeout() -> None:
            nonlocal did_timeout
            did_timeout = True
            loop.quit()

        pending = _Pending(
            command=cmd,
            timeout_ms=timeout_ms,
            completion_callback=_on_completed,
            timeout_callback=_on_timeout,
        )
        self._pending.append(pending)
        try:
            self._start_next_pending()
        except SerialError:
            self._pending.remove(pending)
            raise

        if "response" not in captured and not did_timeout:
            loop.exec()

        if "response" in captured:
            return captured["response"]
        raise SerialTimeout(f"等待响应超时 ({timeout_ms}ms): {cmd!r}")

    # ---- 内部 ----
    def _on_ready_read(self) -> None:
        data = self._transport.read_all()
        if not data:
            return
        if self._is_resynchronizing:
            self._splitter.reset()
            self._resynchronization_timer.start(
                RESYNCHRONIZATION_QUIET_MS
            )
            return
        for raw_line in self._splitter.feed_raw(data):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                self._report_protocol_warning(raw_line)
                continue
            self._handle_line(line, raw_line)

    def _on_port_error(self) -> None:
        self.error_occurred.emit(f"串口错误: {self._transport.error_string()}")
        if self._session_state is not SerialSessionState.AT:
            self.close()

    def _handle_line(self, line: str, raw_line: bytes | None = None) -> None:
        resp = ParsedResponse.parse(line)

        if resp.uart_rx is not None:
            self.uart_rx_received.emit(
                resp.uart_rx.uart_index,
                resp.uart_rx.payload,
            )
            return

        if resp.is_passthrough:
            unrecognized = (
                raw_line if raw_line is not None else line.encode("utf-8")
            )
            self._report_protocol_warning(unrecognized)
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
            if cur.transition == "enter":
                self._session_state = (
                    SerialSessionState.TRANSPARENT
                    if resp.ok
                    else SerialSessionState.AT
                )
            elif cur.transition == "exit":
                if not resp.ok:
                    self.error_occurred.emit(
                        "透明传输退出被固件拒绝，串口已关闭"
                    )
                    self.close()
                    return
                self._session_state = SerialSessionState.AT
            while self._pending and self._pending[0].finished:
                self._pending.popleft()
            if cur.completion_callback is not None:
                cur.completion_callback(resp)
            self.response_received.emit(cur.command, resp)
            try:
                self._start_next_pending()
            except SerialError as error:
                self.error_occurred.emit(f"串口发送队列失败: {error}")
                self.close()
        elif resp.sense or resp.fault or resp.motor or resp.version or resp.diag:
            cur.on_data = resp
            self.at_data_received.emit(cur.command, resp)

    def _ensure_command_can_be_sent(self) -> None:
        if not self._is_open:
            raise SerialError("串口未打开")
        if self._session_state is not SerialSessionState.AT:
            raise SerialError("AT command requires AT mode")
        if self._is_resynchronizing:
            raise SerialError("串口协议正在重新同步")

    def _start_next_pending(self) -> None:
        if not self._pending:
            return
        pending = self._pending[0]
        if pending.finished or pending.has_been_sent:
            return

        if pending.transition == "enter":
            self._session_state = SerialSessionState.ENTERING
        try:
            self.send_only(pending.command)
        except SerialError:
            if pending.transition == "enter":
                self._session_state = SerialSessionState.AT
            raise
        pending.has_been_sent = True
        if pending.timeout_ms <= 0:
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_async_timeout(pending))
        pending.timeout_timer = timer
        timer.start(pending.timeout_ms)

    def _begin_resynchronization(self, timed_out_command: str) -> None:
        if not self._is_open:
            return

        abandoned = list(self._pending)
        self._pending.clear()
        self._is_resynchronizing = True
        self._splitter.reset()
        self._transport.read_all()
        self._resynchronization_timer.start(RESYNCHRONIZATION_QUIET_MS)

        for pending in abandoned:
            self._dispose_timeout_timer(pending)
            pending.finished = True
            if pending.timeout_callback is not None:
                pending.timeout_callback()

        self.error_occurred.emit(
            "命令响应超时，串口保持连接并等待重新同步: "
            f"{timed_out_command!r}"
        )
        for pending in abandoned:
            response = ParsedResponse(
                raw_line="",
                error=AtError(code="TIMEOUT"),
            )
            self.response_received.emit(pending.command, response)

    def _finish_resynchronization(self) -> None:
        self._splitter.reset()
        self._is_resynchronizing = False

    def _report_protocol_warning(self, raw_line: bytes) -> None:
        hexadecimal = raw_line.hex(" ").upper() or "<EMPTY>"
        self.error_occurred.emit(
            f"收到无法识别的串口数据，已丢弃: {hexadecimal}"
        )
