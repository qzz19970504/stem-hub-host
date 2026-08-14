"""数据模型 — 解析后的固件响应.

每个 dataclass 对应一个 AT 查询响应. 字段名贴近固件文档.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---- 错误响应 ----
@dataclass(frozen=True)
class AtError:
    """AT 命令错误响应, 例如 'ERROR:PARSE' 或 'ERROR:SENSE_NOT_READY'."""

    code: str  # 去掉 'ERROR:' 前缀, 例 'PARSE', 'SENSE_NOT_READY', 'STATE_BUSY'

    @classmethod
    def parse(cls, line: str) -> "AtError | None":
        """从 'ERROR[:xxx]' 一行构造, 不匹配返回 None."""
        line = line.strip()
        if not line.startswith("ERROR"):
            return None
        # 'ERROR' 或 'ERROR:PARSE'
        if line == "ERROR":
            return cls(code="")
        if line.startswith("ERROR:"):
            return cls(code=line[len("ERROR:") :])
        return None

    def __str__(self) -> str:
        return f"ERROR:{self.code}" if self.code else "ERROR"


# ---- 握手 ----
@dataclass(frozen=True)
class VersionInfo:
    """`+VERSION:release-v3.0` 响应."""

    version: str

    @classmethod
    def parse(cls, line: str) -> "VersionInfo | None":
        line = line.strip()
        prefix = "+VERSION:"
        if not line.startswith(prefix):
            return None
        return cls(version=line[len(prefix) :].strip())


# ---- 传感 ----
@dataclass(frozen=True)
class SenseData:
    """`+SENSE:...` 响应, 15 个字段.

    BATT_NTC / *_C 是 'XX.XC' 或 'ERR' 字符串 — 这里先存 raw 字符串, UI 层负责格式化.
    BATT_V 是 'XX.XV' 字符串, 同样 raw.
    MOTOR_I 是 'X.XA' 字符串.
    """

    batt_ntc: str  # 电池 NTC
    batt_v: str  # 电池电压
    mcu_c: str
    lm51770_c: str
    mp4317_c: str
    drv8874_c: str
    charge_mos_c: str
    motor_i: str  # 电机电流
    tick: int
    count: int
    stk_at: int
    stk_sensor: int
    stk_motor: int
    tx_sp: int
    tx_ls: int

    @classmethod
    def parse(cls, line: str) -> "SenseData | None":
        """从 '+SENSE:BATT_NTC=...,BATT_V=...V,...' 解析."""
        line = line.strip()
        prefix = "+SENSE:"
        if not line.startswith(prefix):
            return None
        body = line[len(prefix) :]
        required_keys = {
            "BATT_NTC", "BATT_V", "MCU_C", "LM51770_C", "MP4317_C",
            "DRV8874_C", "CHARGE_MOS_C", "MOTOR_I", "TICK", "COUNT",
            "STK_AT", "STK_SENSOR", "STK_MOTOR", "TX_SP", "TX_LS",
        }
        fields: dict[str, str] = {}
        for kv in body.split(","):
            if "=" not in kv:
                return None
            k, v = kv.split("=", 1)
            key = k.strip()
            if key in fields:
                return None
            fields[key] = v.strip()
        if fields.keys() != required_keys:
            return None
        try:
            return cls(
                batt_ntc=fields["BATT_NTC"],
                batt_v=fields["BATT_V"],
                mcu_c=fields["MCU_C"],
                lm51770_c=fields["LM51770_C"],
                mp4317_c=fields["MP4317_C"],
                drv8874_c=fields["DRV8874_C"],
                charge_mos_c=fields["CHARGE_MOS_C"],
                motor_i=fields["MOTOR_I"],
                tick=int(fields["TICK"]),
                count=int(fields["COUNT"]),
                stk_at=int(fields["STK_AT"]),
                stk_sensor=int(fields["STK_SENSOR"]),
                stk_motor=int(fields["STK_MOTOR"]),
                tx_sp=int(fields["TX_SP"]),
                tx_ls=int(fields["TX_LS"]),
            )
        except (KeyError, ValueError):
            return None


# ---- 故障 ----
@dataclass(frozen=True)
class FaultState:
    """`+FAULT:DRV=0,AUX=1` 响应.

    字段值: 0=无故障, 1=有故障 (低电平有效).
    """

    drv: int  # DRV8874 nFAULT
    aux: int  # 另一路 nFLT

    @classmethod
    def parse(cls, line: str) -> "FaultState | None":
        line = line.strip()
        prefix = "+FAULT:"
        if not line.startswith(prefix):
            return None
        body = line[len(prefix) :]
        fields: dict[str, str] = {}
        for kv in body.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            fields[k.strip()] = v.strip()
        try:
            return cls(
                drv=int(fields.get("DRV", "0")),
                aux=int(fields.get("AUX", "0")),
            )
        except (KeyError, ValueError):
            return None


# ---- 电机 ----
@dataclass(frozen=True)
class MotorState:
    """`+MOTOR:MODE=FWD,CURRENT_MA=1234,OVERCURRENT=0,FAULT=0` 响应."""

    mode: str  # SLEEP / WAKE / FWD / REV / BRAKE / STOP
    current_ma: int
    overcurrent: int  # 0/1
    fault: int  # 0/1

    @classmethod
    def parse(cls, line: str) -> "MotorState | None":
        line = line.strip()
        prefix = "+MOTOR:"
        if not line.startswith(prefix):
            return None
        body = line[len(prefix) :]
        fields: dict[str, str] = {}
        for kv in body.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            fields[k.strip()] = v.strip()
        try:
            return cls(
                mode=fields.get("MODE", ""),
                current_ma=int(fields.get("CURRENT_MA", "0")),
                overcurrent=int(fields.get("OVERCURRENT", "0")),
                fault=int(fields.get("FAULT", "0")),
            )
        except (KeyError, ValueError):
            return None


# ---- 诊断 ----
@dataclass(frozen=True)
class UartRxFrame:
    """Binary bytes received by a bridged firmware UART."""

    uart_index: int
    payload: bytes

    @classmethod
    def parse(cls, line: str) -> "UartRxFrame | None":
        line = line.strip()
        for uart_index in (2, 3):
            prefix = f"+UART{uart_index}RX:"
            if not line.startswith(prefix):
                continue
            value = line[len(prefix):]
            if (
                not value
                or len(value) % 2
                or len(value) > 64
                or any(char not in "0123456789ABCDEF" for char in value)
            ):
                return None
            return cls(uart_index=uart_index, payload=bytes.fromhex(value))
        return None


@dataclass(frozen=True)
class DiagInfo:
    """`+DIAG:RX_ISR=...` 响应 (12 个计数器)."""

    rx_isr: int
    rx_byte: int
    rx_overflow: int
    rx_err: int
    ore: int
    ne: int
    fe: int
    pe: int
    line_too_long: int
    at_loop: int
    tx_call: int
    tx_ok: int
    tx_timeout: int
    tx_err: int
    tx_busy: int = 0
    tx_state_pre: int = 0
    tx_state_post: int = 0
    tx_err_pre: int = 0
    tx_err_post: int = 0
    tx_last_status: int = 0
    sensor_loop: int = 0
    sensor_publish: int = 0
    sensor_last_publish_tick: int = 0
    sensor_adc1_read_fail: int = 0
    sensor_adc2_read_fail: int = 0
    uart2_rx_byte: int = 0
    uart2_rx_overflow: int = 0
    uart3_rx_byte: int = 0
    uart3_rx_overflow: int = 0
    uart_wdg: int = 0

    @classmethod
    def parse(cls, line: str) -> "DiagInfo | None":
        line = line.strip()
        prefix = "+DIAG:"
        if not line.startswith(prefix):
            return None
        body = line[len(prefix) :]
        fields: dict[str, str] = {}
        for kv in body.split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            fields[k.strip()] = v.strip()
        try:
            return cls(
                rx_isr=int(fields.get("RX_ISR", "0")),
                rx_byte=int(fields.get("RX_BYTE", "0")),
                rx_overflow=int(fields.get("RX_OVERFLOW", "0")),
                rx_err=int(fields.get("RX_ERR", "0")),
                ore=int(fields.get("ORE", "0")),
                ne=int(fields.get("NE", "0")),
                fe=int(fields.get("FE", "0")),
                pe=int(fields.get("PE", "0")),
                line_too_long=int(fields.get("LINE_TOO_LONG", "0")),
                at_loop=int(fields.get("AT_LOOP", "0")),
                tx_call=int(fields.get("TX_CALL", "0")),
                tx_ok=int(fields.get("TX_OK", "0")),
                tx_timeout=int(fields.get("TX_TIMEOUT", "0")),
                tx_err=int(fields.get("TX_ERR", "0")),
                tx_busy=int(fields.get("TX_BUSY", "0")),
                tx_state_pre=int(fields.get("TX_STATE_PRE", "0")),
                tx_state_post=int(fields.get("TX_STATE_POST", "0")),
                tx_err_pre=int(fields.get("TX_ERR_PRE", "0")),
                tx_err_post=int(fields.get("TX_ERR_POST", "0")),
                tx_last_status=int(fields.get("TX_LAST_STATUS", "0")),
                sensor_loop=int(fields.get("SENSOR_LOOP", "0")),
                sensor_publish=int(fields.get("SENSOR_PUBLISH", "0")),
                sensor_last_publish_tick=int(
                    fields.get("SENSOR_LAST_PUBLISH_TICK", "0")
                ),
                sensor_adc1_read_fail=int(fields.get("SENSOR_ADC1_READ_FAIL", "0")),
                sensor_adc2_read_fail=int(fields.get("SENSOR_ADC2_READ_FAIL", "0")),
                uart2_rx_byte=int(fields.get("UART2_RX_BYTE", "0")),
                uart2_rx_overflow=int(fields.get("UART2_RX_OVERFLOW", "0")),
                uart3_rx_byte=int(fields.get("UART3_RX_BYTE", "0")),
                uart3_rx_overflow=int(fields.get("UART3_RX_OVERFLOW", "0")),
                uart_wdg=int(fields.get("UART_WDG", "0")),
            )
        except (KeyError, ValueError):
            return None
