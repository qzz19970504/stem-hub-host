"""AT 命令协议 — 构造命令 + 解析响应.

包模型:
- 控制命令 (e.g. AT+LED=ON): 响应 = 'OK' 或 'ERROR[:code]'
- 查询命令 (e.g. AT+SENSE?): 响应 = '+KEY:val,val,val\\r\\n' + 'OK' (两行)
  - 解析: 收到数据行 → 调对应 parser.parse(line) → 收到 OK → 触发 future
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Union

from .models import (
    AtError,
    DiagInfo,
    FaultState,
    MotorState,
    SenseData,
    UartRxFrame,
    VersionInfo,
)


# AT 命令结尾必须 CRLF
CRLF = "\r\n"


# ---- 命令构造 ----
def cmd_handshake() -> str:
    return f"AT+VERSION?{CRLF}"


def cmd_query_sense() -> str:
    return f"AT+SENSE?{CRLF}"


def cmd_query_fault() -> str:
    return f"AT+FAULT?{CRLF}"


def cmd_query_motor() -> str:
    return f"AT+MOTOR?{CRLF}"


def cmd_query_diag() -> str:
    return f"AT+DIAG?{CRLF}"


def cmd_set_motor(mode: str) -> str:
    """mode: SLEEP / WAKE / FWD / REV / BRAKE / STOP."""
    return f"AT+MOTOR={mode}{CRLF}"


def cmd_set_led(on: bool) -> str:
    return f"AT+LED={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_nmos(idx: int, on: bool) -> str:
    """idx: 1 or 2."""
    if idx not in (1, 2):
        raise ValueError(f"nmos idx must be 1 or 2, got {idx}")
    return f"AT+NMOS{idx}={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_charge(on: bool) -> str:
    return f"AT+CHARGE={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_drive(on: bool) -> str:
    return f"AT+DRIVE={'ON' if on else 'OFF'}{CRLF}"


def cmd_power_off() -> str:
    return f"AT+POWER=OFF{CRLF}"


def cmd_set_uart2(on: bool) -> str:
    return f"AT+UART2={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_uart3(on: bool) -> str:
    return f"AT+UART3={'ON' if on else 'OFF'}{CRLF}"


def cmd_set_uart23(on: bool) -> str:
    """同时开关 UART2 & 3."""
    return f"AT+UART2&3={'ON' if on else 'OFF'}{CRLF}"

def iter_uart_tx_commands(payload: bytes, chunk_size: int = 32):
    """Yield acknowledged, binary-safe UART tunnel commands."""
    if not payload:
        raise ValueError("UART tunnel payload must not be empty")
    if chunk_size < 1 or chunk_size > 32:
        raise ValueError("UART tunnel chunk size must be between 1 and 32")
    for offset in range(0, len(payload), chunk_size):
        yield f"AT+UARTTX={payload[offset:offset + chunk_size].hex().upper()}{CRLF}"


def cmd_raw(text: str) -> str:
    """用户从 AT 输入框发送的任意命令, 自动补 CRLF 结尾.

    不会 trim 内部空格, 因为固件 AT 解析器不允许中间空格, 留原样让用户/固件自己报错.
    """
    if CRLF in text:
        # 用户可能没注意, 帮助补上结尾
        return text if text.endswith(CRLF) else text + CRLF
    return text + CRLF


# ---- 响应解析 ----
@dataclass
class ParsedResponse:
    """单条响应. 可能是 OK / ERROR / 数据行 / 透传行."""

    raw_line: str  # 去掉 CRLF 之后的原文

    # 下面四个里最多一个有值
    ok: bool = False
    error: Optional[AtError] = None
    sense: Optional[SenseData] = None
    fault: Optional[FaultState] = None
    motor: Optional[MotorState] = None
    version: Optional[VersionInfo] = None
    diag: Optional[DiagInfo] = None
    uart_rx: Optional[UartRxFrame] = None
    is_passthrough: bool = False  # 透传行 (非 AT 数据)

    @classmethod
    def parse(cls, line: str) -> "ParsedResponse":
        """从一行响应 (无 CRLF) 构造."""
        s = line.strip()
        if s == "OK":
            return cls(raw_line=line, ok=True)
        err = AtError.parse(s)
        if err is not None:
            return cls(raw_line=line, error=err)
        if s.startswith("+SENSE:"):
            d = SenseData.parse(s)
            if d is not None:
                return cls(raw_line=line, sense=d)
        if s.startswith("+FAULT:"):
            d = FaultState.parse(s)
            if d is not None:
                return cls(raw_line=line, fault=d)
        if s.startswith("+MOTOR:"):
            d = MotorState.parse(s)
            if d is not None:
                return cls(raw_line=line, motor=d)
        if s.startswith("+VERSION:"):
            d = VersionInfo.parse(s)
            if d is not None:
                return cls(raw_line=line, version=d)
        if s.startswith("+DIAG:"):
            d = DiagInfo.parse(s)
            if d is not None:
                return cls(raw_line=line, diag=d)
        if s.startswith(("+UART2RX:", "+UART3RX:")):
            frame = UartRxFrame.parse(s)
            if frame is not None:
                return cls(raw_line=line, uart_rx=frame)
        # 既不是 OK / ERROR 也不是 +XXX:  → 透传数据
        return cls(raw_line=line, is_passthrough=True)


# ---- 行切分器 ----
class LineSplitter:
    """从字节流中切出完整行 (以 CRLF 结尾).

    透传数据可能不带 CRLF, 这里只按 CRLF 切.
    透传面板会直接消费 raw bytes, 这里只负责 AT 行切分.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[str]:
        """把新数据塞进来, 返回所有切出的完整行 (不包含 CRLF)."""
        lines: list[str] = []
        for line_bytes in self.feed_raw(data):
            try:
                line = line_bytes.decode("utf-8")
            except UnicodeDecodeError:
                line = line_bytes.decode("latin-1")
            lines.append(line)
        return lines

    def feed_raw(self, data: bytes) -> list[bytes]:
        """Return complete CRLF-delimited lines without decoding their bytes."""
        if not data:
            return []
        self._buf.extend(data)
        lines: list[bytes] = []
        while True:
            i = self._buf.find(b"\r\n")
            if i < 0:
                break
            line_bytes = bytes(self._buf[:i])
            del self._buf[: i + 2]
            lines.append(line_bytes)
        return lines

    def reset(self) -> None:
        self._buf.clear()
