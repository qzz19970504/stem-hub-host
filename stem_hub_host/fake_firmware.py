"""假固件 — 模拟 stem-hub 固件行为, 用于无硬件联调.

用 FakeSerialTransport + SerialWorker 跑:
1. SerialWorker 用 FakeSerialTransport
2. 假固件监听 worker 写出的字节
3. 看到 AT 命令 → 模拟响应, 通过 transport.feed() 喂回 worker

启动:
    from stem_hub_host.fake_firmware import FakeFirmware
    fw = FakeFirmware(worker)
    worker.open("FAKE0", 115200)  # 任何名字都行
    # 之后可以 send_and_wait
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from .at_protocol import (
    CRLF,
    LineSplitter,
)
from .serial_worker import SerialWorker
from .transport import FakeSerialTransport


class FakeFirmware(QObject):
    """模拟固件行为."""

    VERSION = "release-v3.0-fake"

    def __init__(self, worker: SerialWorker, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._splitter = LineSplitter()

        # 固件状态
        self._motor_mode = "SLEEP"
        self._motor_current_ma = 0
        self._overcurrent = 0
        self._drv_fault = 0
        self._aux_fault = 0
        self._led_on = True
        self._nmos1 = False
        self._nmos2 = False
        self._mp4317 = False
        self._lm51770 = False
        self._uart2 = False
        self._uart3 = False
        self._sense_count = 0
        self._tick_start = time.monotonic()

        # 监听 worker 写出的字节
        self._worker.send_only_signal = self._worker.send_only  # type: ignore  # not used
        # 直接 hook transport 写入: 用 timer poll 太低效, 改用 monkey-patch
        # 实际上更简单: 暴露一个 _on_user_send(cmd) 方法, 由调用方在 send_and_wait 后通知我们
        # 但更优雅: 重写 send_only 来通知. 但这违反封装.
        #
        # 最干净做法: 给 FakeFirmware 自己的 splitter, 让它跟 worker 共享 transport
        # 但 transport.feed() 不算 readAll...
        #
        # 折中: 监控 worker 的 transport._written —— 依赖私有属性, 但 fake 场景 OK
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(5)  # 5 ms 一次

    def _set_power_mode(self, mode: str) -> None:
        self._lm51770 = False
        self._mp4317 = False
        if mode == "charge":
            self._lm51770 = True
        elif mode == "drive":
            self._mp4317 = True

    def _poll(self) -> None:
        """定时检查 worker transport 写出的字节."""
        transport = self._worker._transport  # type: ignore[attr-defined]
        if not isinstance(transport, FakeSerialTransport):
            return
        written = transport.get_written()
        if not written:
            return
        # 取出并清空
        transport._written = bytearray()
        for line in self._splitter.feed(written):
            self._handle_cmd(line)

    def _handle_cmd(self, cmd: str) -> None:
        cmd = cmd.strip()
        transport = self._worker._transport  # type: ignore[attr-defined]
        if not isinstance(transport, FakeSerialTransport):
            return

        if cmd == "AT+VERSION?":
            transport.feed(f"+VERSION:{self.VERSION}{CRLF}OK{CRLF}".encode())
        elif cmd == "AT+SENSE?":
            self._sense_count += 1
            tick = int((time.monotonic() - self._tick_start) * 1000) & 0xFFFFFFFF
            t = time.monotonic()
            batt_v = 36.5 + 0.5 * math.sin(t / 3.0)
            batt_ntc = 25.0 + 0.3 * math.sin(t / 5.0)
            ntc1 = 24.5 + 0.4 * math.sin(t / 4.0)
            ntc2 = -2.0 + 0.2 * math.sin(t / 6.0)
            ntc3 = 26.0 + 0.5 * math.sin(t / 7.0)
            motor_i = 1.5 if self._motor_mode in ("FWD", "REV") else 0.0
            sense = (
                f"+SENSE:BATT_NTC={batt_ntc:.1f}C,BATT_V={batt_v:.1f}V,"
                f"NTC1_C={ntc1:.1f}C,NTC2_C={ntc2:.1f}C,NTC3_C={ntc3:.1f}C,"
                f"MOTOR_I={motor_i:.1f}A,TICK={tick},COUNT={self._sense_count},"
                f"STK_AT=200,STK_SENSOR=180,STK_MOTOR=160,TX_SP=0,TX_LS=0"
            )
            transport.feed(f"{sense}{CRLF}OK{CRLF}".encode())
        elif cmd == "AT+FAULT?":
            transport.feed(f"+FAULT:DRV={self._drv_fault},AUX={self._aux_fault}{CRLF}OK{CRLF}".encode())
        elif cmd == "AT+MOTOR?":
            transport.feed(
                f"+MOTOR:MODE={self._motor_mode},CURRENT_MA={self._motor_current_ma},"
                f"OVERCURRENT={self._overcurrent},FAULT={self._drv_fault}{CRLF}OK{CRLF}".encode()
            )
        elif cmd == "AT+DIAG?":
            payload = (
                "+DIAG:RX_ISR=1,RX_BYTE=2,RX_OVERFLOW=0,RX_ERR=0,ORE=0,NE=0,FE=0,PE=0,"
                "LINE_TOO_LONG=0,AT_LOOP=10,TX_CALL=5,TX_OK=5,TX_TIMEOUT=0,TX_ERR=0,"
                "TX_BUSY=0,TX_STATE_PRE=0,TX_STATE_POST=0,TX_ERR_PRE=0,TX_ERR_POST=0,"
                "TX_LAST_STATUS=0,SENSOR_LOOP=10,SENSOR_PUBLISH=10,"
                "SENSOR_LAST_PUBLISH_TICK=1000,SENSOR_ADC1_READ_FAIL=0,"
                "SENSOR_ADC2_READ_FAIL=0,UART2_RX_BYTE=0,UART2_RX_OVERFLOW=0,"
                "UART3_RX_BYTE=0,UART3_RX_OVERFLOW=0"
                + CRLF + "OK" + CRLF
            )
            transport.feed(payload.encode())
        elif cmd.startswith("AT+MOTOR="):
            mode = cmd[len("AT+MOTOR="):]
            if mode in ("SLEEP", "WAKE", "FWD", "REV", "BRAKE", "STOP"):
                self._motor_mode = mode
                if mode in ("FWD", "REV"):
                    self._motor_current_ma = 1500
                else:
                    self._motor_current_ma = 0
                transport.feed(b"OK" + CRLF.encode())
            else:
                transport.feed(b"ERROR:PARSE" + CRLF.encode())
        elif cmd == "AT+LED=ON":
            self._led_on = True
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+LED=OFF":
            self._led_on = False
            transport.feed(b"OK" + CRLF.encode())
        elif cmd.startswith("AT+NMOS"):
            try:
                if cmd == "AT+NMOS1=ON":
                    self._nmos1 = True
                elif cmd == "AT+NMOS1=OFF":
                    self._nmos1 = False
                elif cmd == "AT+NMOS2=ON":
                    self._nmos2 = True
                elif cmd == "AT+NMOS2=OFF":
                    self._nmos2 = False
                else:
                    transport.feed(b"ERROR:PARSE" + CRLF.encode())
                    return
                transport.feed(b"OK" + CRLF.encode())
            except Exception:
                transport.feed(b"ERROR" + CRLF.encode())
        elif cmd == "AT+CHARGE=ON":
            self._set_power_mode("charge")
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+CHARGE=OFF":
            self._set_power_mode("off")
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+DRIVE=ON":
            self._set_power_mode("drive")
            transport.feed(b"OK" + CRLF.encode())
        elif cmd in ("AT+DRIVE=OFF", "AT+POWER=OFF"):
            self._set_power_mode("off")
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+UART2=ON":
            self._uart2 = True
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+UART2=OFF":
            self._uart2 = False
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+UART3=ON":
            self._uart3 = True
            transport.feed(b"OK" + CRLF.encode())
        elif cmd == "AT+UART3=OFF":
            self._uart3 = False
            transport.feed(b"OK" + CRLF.encode())
        elif cmd in ("AT+UART2&3=ON", "AT+UART23=ON"):
            self._uart2 = True
            self._uart3 = True
            transport.feed(b"OK" + CRLF.encode())
        elif cmd in ("AT+UART2&3=OFF", "AT+UART23=OFF"):
            self._uart2 = False
            self._uart3 = False
            transport.feed(b"OK" + CRLF.encode())
        elif cmd.startswith("AT+UARTTX="):
            value = cmd[len("AT+UARTTX="):]
            if (
                not value
                or len(value) % 2
                or len(value) > 64
                or any(char not in "0123456789ABCDEF" for char in value)
            ):
                transport.feed(b"ERROR:HEX" + CRLF.encode())
            elif not self._uart2 and not self._uart3:
                transport.feed(b"ERROR:UART_DISABLED" + CRLF.encode())
            else:
                if self._uart2:
                    transport.feed(f"+UART2RX:{value}{CRLF}".encode())
                if self._uart3:
                    transport.feed(f"+UART3RX:{value}{CRLF}".encode())
                transport.feed(b"OK" + CRLF.encode())
        else:
            transport.feed(b"ERROR:PARSE" + CRLF.encode())
