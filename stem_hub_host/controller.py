"""Controller — UI <-> SerialWorker 联动.

- 持有 SerialWorker 实例
- 监听 UI 信号 → 翻译成 AT 命令下发
- 监听 SerialWorker 响应 → 推送到 UI 更新
- 周期拉取 SENSE/FAULT/MOTOR
- 握手: 打开串口后 200ms 发起 AT+VERSION?, 500ms 内回 OK + 有效版本即成功
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from decimal import Decimal

from PySide6.QtCore import QObject, QTimer, Signal

from .at_protocol import (
    cmd_handshake,
    cmd_query_fault,
    cmd_query_motor,
    cmd_query_sense,
    iter_uart_tx_commands,
    cmd_set_lm51770,
    cmd_set_led,
    cmd_set_motor,
    cmd_set_mp4317,
    cmd_set_nmos,
    cmd_set_uart2,
    cmd_set_uart23,
    cmd_set_uart3,
)
from .data_buffer import DataBuffer
from .serial_worker import SerialError, SerialTimeout, SerialWorker


SENSE_HZ_OPTIONS = (0.2, 0.4, 0.6, 0.8, 1.0)
DEFAULT_SENSE_HZ = 1.0


def normalize_sense_hz(hz: float) -> float:
    """Return the nearest supported rate, preferring the higher midpoint."""

    value = Decimal(str(hz))
    decimal_options = tuple(Decimal(str(option)) for option in SENSE_HZ_OPTIONS)
    normalized = min(
        decimal_options,
        key=lambda option: (abs(option - value), -option),
    )
    return float(normalized)


class Controller(QObject):
    """UI 与串口之间的胶水."""

    # ---- 状态 ----
    sense_request_hz_changed = Signal(float)
    error_occurred = Signal(str)
    handshake_failed = Signal(str)
    output_command_failed = Signal(str, bool, str)
    motor_command_failed = Signal(str, str, str)
    charge_transition_changed = Signal(bool)
    passthrough_mode_changed = Signal(str)
    passthrough_transition_changed = Signal(bool)
    passthrough_tx_confirmed = Signal(int)

    def __init__(
        self,
        worker: SerialWorker,
        parent: QObject | None = None,
        *,
        handshake_deadline_ms: int = 5000,
        handshake_retry_ms: int = 1000,
        handshake_attempt_timeout_ms: int = 500,
        handshake_initial_delay_ms: int = 200,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._data_buffer = DataBuffer()
        self._handshake_deadline_ms = handshake_deadline_ms
        self._handshake_retry_ms = handshake_retry_ms
        self._handshake_attempt_timeout_ms = handshake_attempt_timeout_ms
        self._handshake_initial_delay_ms = handshake_initial_delay_ms

        # 状态缓存
        self._is_open = False
        self._handshake_ok = False
        self._connection_attempt_active = False
        self._last_handshake_error = "TIMEOUT"
        self._sense_hz = DEFAULT_SENSE_HZ
        self._latest_sense = None
        self._latest_motor = None
        self._confirmed_motor_mode: str | None = None
        self._latest_fault = None
        self._pending_outputs: dict[
            str,
            deque[
                tuple[
                    str,
                    bool,
                    Callable[[], None] | None,
                    Callable[[str], None] | None,
                ]
            ],
        ] = defaultdict(deque)
        self._pending_bridges: dict[
            str,
            deque[
                tuple[Callable[[], None], Callable[[str], None]]
            ],
        ] = defaultdict(deque)
        self._passthrough_mode = "off"
        self._charge_transition_active = False
        self._queued_charge_mode: str | None = None
        self._all_outputs_off_queued = False
        self._passthrough_transition_active = False
        self._queued_passthrough_mode: str | None = None
        self._passthrough_tx_queue: deque[tuple[str, int]] = deque()
        self._passthrough_tx_active: tuple[str, int] | None = None

        # 周期拉取定时器
        self._sense_timer = QTimer(self)
        self._sense_timer.timeout.connect(self._poll_once)
        self._apply_sense_interval()

        # 握手专用
        self._handshake_delay_timer = QTimer(self)
        self._handshake_delay_timer.setSingleShot(True)
        self._handshake_delay_timer.timeout.connect(self._do_handshake)
        self._handshake_retry_timer = QTimer(self)
        self._handshake_retry_timer.setSingleShot(True)
        self._handshake_retry_timer.timeout.connect(self._do_handshake)
        self._handshake_deadline_timer = QTimer(self)
        self._handshake_deadline_timer.setSingleShot(True)
        self._handshake_deadline_timer.timeout.connect(
            self._fail_connection_attempt
        )

        # 连 worker 信号
        worker.connected.connect(self._on_worker_connected)
        worker.disconnected.connect(self._on_worker_disconnected)
        worker.error_occurred.connect(self._on_worker_error)
        worker.at_data_received.connect(self._on_at_data)
        worker.response_received.connect(self._on_response)
        worker.passthrough_received.connect(self._on_passthrough)

    # ---- 公开 API ----
    @property
    def worker(self) -> SerialWorker:
        return self._worker

    @property
    def is_connected(self) -> bool:
        return self._is_open

    @property
    def is_handshake_ok(self) -> bool:
        return self._handshake_ok

    @property
    def sense_hz(self) -> float:
        return self._sense_hz

    def set_sense_hz(self, hz: float) -> None:
        self._sense_hz = normalize_sense_hz(hz)
        self._apply_sense_interval()
        self.sense_request_hz_changed.emit(self._sense_hz)

    def open(self, port: str, baud: int = 115200) -> bool:
        ok = self._worker.open(port, baud)
        return ok

    def close(self) -> None:
        self._connection_attempt_active = False
        self._cancel_handshake_timers()
        self._stop_polling()
        self._worker.close()

    # ---- 周期拉取 ----
    def _apply_sense_interval(self) -> None:
        ms = round(1000 / self._sense_hz)
        self._sense_timer.setInterval(ms)

    def _start_polling(self) -> None:
        self._sense_timer.start()

    def _stop_polling(self) -> None:
        self._sense_timer.stop()

    def _poll_once(self) -> None:
        """发 SENSE / FAULT / MOTOR 查询, 不阻塞 (用 send_only 让响应自然回来)."""
        if (
            not self._is_open
            or not self._handshake_ok
            or self._passthrough_mode != "off"
            or self._passthrough_transition_active
        ):
            return
        self._worker.send_command(cmd_query_sense())
        self._worker.send_command(cmd_query_fault())
        self._worker.send_command(cmd_query_motor())

    # ---- 用户操作: 命令下发 ----
    def set_motor(self, mode: str) -> None:
        if not self._standard_commands_available():
            return
        try:
            self._worker.send_command(cmd_set_motor(mode))
        except SerialError as e:
            self._on_worker_error(f"电机命令失败: {e}")

    def set_nmos(self, idx: int, on: bool) -> None:
        self._send_output(cmd_set_nmos(idx, on), f"NMOS{idx}", on)

    def set_mp4317(self, on: bool) -> None:
        self._send_output(cmd_set_mp4317(on), "DISCHARGE", on)

    def set_lm51770(self, on: bool) -> None:
        self._send_output(cmd_set_lm51770(on), "CHARGE", on)

    def set_charge_mode(self, mode: str) -> None:
        """Serialize mutually exclusive charge-path changes."""
        if mode not in {"charge", "discharge", "off"}:
            return
        if self._charge_transition_active:
            self._queued_charge_mode = mode
            return
        if not self._standard_commands_available():
            return

        self._charge_transition_active = True
        self.charge_transition_changed.emit(True)
        self._run_charge_transition(mode)

    def _run_charge_transition(self, mode: str) -> None:
        if mode == "charge":
            self._run_charge_steps(
                (
                    (cmd_set_mp4317(False), "DISCHARGE", False),
                    (cmd_set_lm51770(False), "CHARGE", False),
                    (cmd_set_lm51770(True), "CHARGE", True),
                ),
                target="CHARGE",
            )
        elif mode == "discharge":
            self._run_charge_steps(
                (
                    (cmd_set_lm51770(False), "CHARGE", False),
                    (cmd_set_mp4317(False), "DISCHARGE", False),
                    (cmd_set_mp4317(True), "DISCHARGE", True),
                ),
                target="DISCHARGE",
            )
        else:
            def send_mp_off() -> None:
                self._send_output(
                    cmd_set_mp4317(False),
                    "DISCHARGE",
                    False,
                    on_success=self._finish_charge_transition,
                    on_failure=lambda _reason: self._finish_charge_transition(),
                    allow_charge_transition=True,
                )

            self._send_output(
                cmd_set_lm51770(False),
                "CHARGE",
                False,
                on_success=send_mp_off,
                on_failure=lambda _reason: send_mp_off(),
                allow_charge_transition=True,
            )

    def _run_charge_steps(
        self,
        steps: Sequence[tuple[str, str, bool]],
        *,
        target: str,
    ) -> None:
        """Run one mutually exclusive power-path sequence, one ACK at a time."""

        def run_step(index: int) -> None:
            if index >= len(steps):
                self._finish_charge_transition()
                return

            command, control, on = steps[index]

            def fail(reason: str) -> None:
                if on:
                    self._finish_charge_transition()
                else:
                    self._abort_charge_transition(target, reason)

            self._send_output(
                command,
                control,
                on,
                on_success=lambda: run_step(index + 1),
                on_failure=fail,
                allow_charge_transition=True,
            )

        run_step(0)

    def _abort_charge_transition(self, target: str, reason: str) -> None:
        self.output_command_failed.emit(target, True, f"aborted: {reason}")
        self._finish_charge_transition()

    def set_all_outputs_off(self) -> None:
        """Turn every output off sequentially in the documented safe order."""
        if self._charge_transition_active:
            self._queued_charge_mode = None
            self._all_outputs_off_queued = True
            return
        if not self._standard_commands_available():
            return

        self._charge_transition_active = True
        self.charge_transition_changed.emit(True)
        self._run_all_outputs_off()

    def _run_all_outputs_off(self) -> None:
        steps = (
            (cmd_set_lm51770(False), "CHARGE"),
            (cmd_set_mp4317(False), "DISCHARGE"),
            (cmd_set_nmos(1, False), "NMOS1"),
            (cmd_set_nmos(2, False), "NMOS2"),
            (cmd_set_led(False), "LIGHTS"),
        )

        def run_step(index: int) -> None:
            if index >= len(steps):
                self._finish_charge_transition()
                return
            command, control = steps[index]
            advance = lambda _reason=None: run_step(index + 1)
            self._send_output(
                command,
                control,
                False,
                on_success=lambda: advance(),
                on_failure=advance,
                allow_charge_transition=True,
            )

        run_step(0)

    def _finish_charge_transition(self) -> None:
        if self._all_outputs_off_queued and self._is_open:
            self._all_outputs_off_queued = False
            self._run_all_outputs_off()
            return
        next_mode = self._queued_charge_mode
        self._queued_charge_mode = None
        if next_mode is not None and self._is_open:
            self._run_charge_transition(next_mode)
            return

        self._charge_transition_active = False
        self.charge_transition_changed.emit(False)
        next_passthrough = self._queued_passthrough_mode
        self._queued_passthrough_mode = None
        if next_passthrough is not None:
            self.set_passthrough(next_passthrough)

    def set_led(self, on: bool) -> None:
        self._send_output(cmd_set_led(on), "LIGHTS", on)

    def _send_output(
        self,
        cmd: str,
        control: str,
        on: bool,
        *,
        on_success: Callable[[], None] | None = None,
        on_failure: Callable[[str], None] | None = None,
        allow_charge_transition: bool = False,
    ) -> None:
        if not self._standard_commands_available():
            return
        if (
            self._charge_transition_active
            and control in {"CHARGE", "DISCHARGE"}
            and not allow_charge_transition
        ):
            return
        self._pending_outputs[cmd].append(
            (control, on, on_success, on_failure)
        )
        try:
            self._worker.send_command(cmd)
        except SerialError as e:
            self._pending_outputs[cmd].pop()
            self.output_command_failed.emit(control, on, str(e))
            if on_failure is not None:
                on_failure(str(e))
            self._on_worker_error(f"{control} 命令失败: {e}")

    def set_passthrough(self, mode: str) -> None:
        """mode: 'uart2' / 'uart3' / 'both' / 'off'."""
        if mode not in {"uart2", "uart3", "both", "off"}:
            return
        if not self._is_open:
            return
        if self._charge_transition_active:
            self._queued_passthrough_mode = mode
            return
        if self._passthrough_transition_active:
            self._queued_passthrough_mode = mode
            return

        self._passthrough_transition_active = True
        self.passthrough_transition_changed.emit(True)
        self._run_passthrough_transition(mode)

    def _run_passthrough_transition(self, mode: str) -> None:
        previous = self._passthrough_mode
        self._worker.set_passthrough_raw(False)
        self._stop_polling()

        def revert(reason: str) -> None:
            self._apply_passthrough_mode(previous)
            self._on_worker_error(f"透传命令失败: {reason}")
            self._finish_passthrough_transition()

        def confirm() -> None:
            self._apply_passthrough_mode(mode)
            self._finish_passthrough_transition()

        def enable_failed(reason: str) -> None:
            self._apply_passthrough_mode("off")
            self._on_worker_error(f"透传命令失败: {reason}")
            self._finish_passthrough_transition()

        if mode == "uart2":
            after_off = confirm if previous == "both" else lambda: self._send_bridge(
                cmd_set_uart2(True), confirm, enable_failed
            )
            self._send_bridge(cmd_set_uart3(False), after_off, revert)
        elif mode == "uart3":
            after_off = confirm if previous == "both" else lambda: self._send_bridge(
                cmd_set_uart3(True), confirm, enable_failed
            )
            self._send_bridge(cmd_set_uart2(False), after_off, revert)
        elif mode == "both":
            self._send_bridge(cmd_set_uart23(True), confirm, revert)
        elif mode == "off":
            self._send_bridge(cmd_set_uart23(False), confirm, revert)

    def _finish_passthrough_transition(self) -> None:
        next_mode = self._queued_passthrough_mode
        self._queued_passthrough_mode = None
        if next_mode is not None and next_mode != self._passthrough_mode and self._is_open:
            self._run_passthrough_transition(next_mode)
            return

        self._passthrough_transition_active = False
        self.passthrough_transition_changed.emit(False)
        if self._passthrough_mode == "off" and self._is_open and self._handshake_ok:
            self._start_polling()

    def _send_bridge(
        self,
        cmd: str,
        on_success: Callable[[], None],
        on_failure: Callable[[str], None],
    ) -> None:
        self._pending_bridges[cmd].append((on_success, on_failure))
        try:
            self._worker.send_command(cmd)
        except SerialError as error:
            self._pending_bridges[cmd].pop()
            on_failure(str(error))

    def _apply_passthrough_mode(self, mode: str) -> None:
        self._passthrough_mode = mode
        self._worker.set_passthrough_raw(False)
        if (
            mode == "off"
            and not self._passthrough_transition_active
            and self._is_open
            and self._handshake_ok
        ):
            self._start_polling()
        self.passthrough_mode_changed.emit(mode)

    def send_passthrough_bytes(self, data: bytes) -> bool:
        """Queue exact bytes as acknowledged, binary-safe AT tunnel frames."""
        if (
            not self._is_open
            or not self._handshake_ok
            or self._passthrough_mode == "off"
            or self._passthrough_transition_active
            or not data
        ):
            return False

        offset = 0
        for command in iter_uart_tx_commands(data):
            chunk_length = min(32, len(data) - offset)
            self._passthrough_tx_queue.append((command, chunk_length))
            offset += chunk_length
        self._send_next_passthrough_chunk()
        return True

    def _send_next_passthrough_chunk(self) -> None:
        if self._passthrough_tx_active is not None or not self._passthrough_tx_queue:
            return
        item = self._passthrough_tx_queue.popleft()
        self._passthrough_tx_active = item
        try:
            self._worker.send_command(item[0])
        except SerialError as error:
            self._passthrough_tx_active = None
            self._passthrough_tx_queue.clear()
            self._on_worker_error(f"透传发送失败: {error}")

    def send_raw(self, cmd: str) -> None:
        """AT 输入框直接发, 不等回包."""
        if not self._standard_commands_available():
            return
        try:
            self._worker.send_command(cmd)
        except SerialError as e:
            self._on_worker_error(f"AT 发送失败: {e}")

    def _standard_commands_available(self) -> bool:
        return (
            self._is_open
            and self._passthrough_mode == "off"
            and not self._passthrough_transition_active
        )

    # ---- Worker 信号处理 ----
    def _on_worker_connected(self, port: str, baud: int) -> None:
        self._is_open = True
        self._handshake_ok = False
        self._connection_attempt_active = True
        self._last_handshake_error = "TIMEOUT"
        self._cancel_handshake_timers()
        self._handshake_deadline_timer.start(self._handshake_deadline_ms)
        self._start_handshake()

    def _on_worker_disconnected(self) -> None:
        self._is_open = False
        self._handshake_ok = False
        self._connection_attempt_active = False
        self._stop_polling()
        self._cancel_handshake_timers()
        self._latest_sense = None
        self._latest_motor = None
        self._confirmed_motor_mode = None
        self._latest_fault = None
        self._pending_outputs.clear()
        self._pending_bridges.clear()
        charge_was_active = self._charge_transition_active
        bridge_was_active = self._passthrough_transition_active
        self._charge_transition_active = False
        self._queued_charge_mode = None
        self._all_outputs_off_queued = False
        self._passthrough_transition_active = False
        self._queued_passthrough_mode = None
        self._passthrough_mode = "off"
        self._passthrough_tx_queue.clear()
        self._passthrough_tx_active = None
        self._worker.set_passthrough_raw(False)
        if charge_was_active:
            self.charge_transition_changed.emit(False)
        if bridge_was_active:
            self.passthrough_transition_changed.emit(False)
        self.passthrough_mode_changed.emit("off")

    def _on_worker_error(self, msg: str) -> None:
        self.error_occurred.emit(msg)

    def _on_passthrough(self, line: str) -> None:
        # 透传面板在第 ⑥ 步接管
        pass

    def _on_response(self, cmd: str, resp) -> None:
        if (
            self._passthrough_tx_active is not None
            and cmd == self._passthrough_tx_active[0]
        ):
            _, byte_count = self._passthrough_tx_active
            self._passthrough_tx_active = None
            if resp.error is not None:
                self._passthrough_tx_queue.clear()
                self._on_worker_error(f"透传发送失败: {resp.error.code}")
            else:
                self.passthrough_tx_confirmed.emit(byte_count)
                self._send_next_passthrough_chunk()
            return

        pending = self._pending_outputs.get(cmd)
        if pending:
            control, requested_state, on_success, on_failure = pending.popleft()
            if not pending:
                self._pending_outputs.pop(cmd, None)
            if resp.error is not None:
                reason = resp.error.code
                self.output_command_failed.emit(
                    control,
                    requested_state,
                    reason,
                )
                if on_failure is not None:
                    on_failure(reason)
            elif on_success is not None:
                on_success()

        bridge_pending = self._pending_bridges.get(cmd)
        if bridge_pending:
            on_success, on_failure = bridge_pending.popleft()
            if not bridge_pending:
                self._pending_bridges.pop(cmd, None)
            if resp.error is not None:
                on_failure(resp.error.code)
            else:
                on_success()
        # 握手响应特殊处理
        stripped_cmd = cmd.strip()
        if stripped_cmd.startswith("AT+MOTOR="):
            requested_mode = stripped_cmd.partition("=")[2]
            if resp.error is not None:
                self.motor_command_failed.emit(
                    requested_mode,
                    self._confirmed_motor_mode or "",
                    resp.error.code,
                )
            else:
                self._confirmed_motor_mode = requested_mode

        if stripped_cmd.startswith("AT+VERSION?") and resp.version is not None:
            self._complete_handshake()
            return

    def _on_at_data(self, cmd: str, resp) -> None:
        if resp.sense is not None:
            self._latest_sense = resp.sense
            self._data_buffer.feed_sense(resp.sense)
        if resp.motor is not None:
            self._latest_motor = resp.motor
            self._confirmed_motor_mode = resp.motor.mode
        if resp.fault is not None:
            self._latest_fault = resp.fault

    # ---- 握手 ----
    def _start_handshake(self) -> None:
        # Restarting this timer cancels a stale handshake from a prior port.
        self._handshake_delay_timer.start(self._handshake_initial_delay_ms)

    def _do_handshake(self) -> None:
        if not self._is_open or not self._connection_attempt_active:
            return
        try:
            resp = self._worker.send_and_wait(
                cmd_handshake(),
                timeout_ms=self._handshake_attempt_timeout_ms,
            )
            if not self._connection_attempt_active:
                return
            if resp.version is not None:
                self._complete_handshake()
            else:
                reason = (
                    resp.error.code
                    if resp.error is not None
                    else "INVALID_VERSION"
                )
                self._schedule_handshake_retry(reason)
        except SerialTimeout:
            if self._connection_attempt_active:
                self._schedule_handshake_retry("TIMEOUT")
        except SerialError as e:
            if self._connection_attempt_active and self._is_open:
                self._schedule_handshake_retry(str(e))

    def _schedule_handshake_retry(self, reason: str) -> None:
        if not self._connection_attempt_active or not self._is_open:
            return
        self._last_handshake_error = reason
        self._handshake_retry_timer.start(self._handshake_retry_ms)

    def _complete_handshake(self) -> None:
        if self._handshake_ok:
            return
        self._connection_attempt_active = False
        self._handshake_ok = True
        self._cancel_handshake_timers()
        self._start_polling()

    def _fail_connection_attempt(self) -> None:
        if not self._connection_attempt_active:
            return
        reason = self._last_handshake_error
        self._connection_attempt_active = False
        self._cancel_handshake_timers()
        if self._worker.is_open():
            self._worker.close()
        self.handshake_failed.emit(reason)

    def _cancel_handshake_timers(self) -> None:
        self._handshake_delay_timer.stop()
        self._handshake_retry_timer.stop()
        self._handshake_deadline_timer.stop()

    # ---- UI 拉取最新状态 ----
    def get_latest(self):
        return {
            "sense": self._latest_sense,
            "motor": self._latest_motor,
            "fault": self._latest_fault,
        }

    def get_data_buffer(self) -> DataBuffer:
        return self._data_buffer
