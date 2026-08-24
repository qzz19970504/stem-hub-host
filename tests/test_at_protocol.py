"""AT 协议解析单元测试.

不需要任何硬件, 不需要 QApplication. 用 `python -m pytest tests/` 跑.
"""
from __future__ import annotations

import pytest

from stem_hub_host.at_protocol import (
    CRLF,
    LineSplitter,
    ParsedResponse,
    cmd_handshake,
    cmd_query_diag,
    cmd_query_fault,
    cmd_query_motor,
    cmd_query_output,
    cmd_query_sense,
    cmd_raw,
    iter_uart_tx_commands,
    cmd_power_off,
    cmd_set_charge,
    cmd_set_drive,
    cmd_set_led,
    cmd_set_motor,
    cmd_set_motor_bypass,
    cmd_set_nmos,
    cmd_set_charge_bypass,
    cmd_set_uart2,
    cmd_set_uart23,
    cmd_set_uart3,
)
from stem_hub_host.models import (
    AtError,
    DiagInfo,
    FaultState,
    MotorState,
    OutputState,
    SenseData,
    VersionInfo,
    UartRxFrame,
)


SEMANTIC_SENSE_FIELDS = (
    ("BATT_NTC", "25.1C"),
    ("BATT_V", "37.0V"),
    ("MCU_C", "24.9C"),
    ("LM51770_C", "35.2C"),
    ("MP4317_C", "36.3C"),
    ("DRV8874_C", "37.4C"),
    ("CHARGE_MOS_C", "38.5C"),
    ("MOTOR_I", "1.2A"),
    ("TICK", "12345"),
    ("COUNT", "42"),
    ("STK_AT", "200"),
    ("STK_SENSOR", "180"),
    ("STK_MOTOR", "160"),
    ("TX_SP", "3"),
    ("TX_LS", "4"),
)
SEMANTIC_SENSE_LINE = "+SENSE:" + ",".join(
    f"{key}={value}" for key, value in SEMANTIC_SENSE_FIELDS
)


# ---- 命令构造 ----
class TestCommandBuilders:
    def test_handshake(self):
        assert cmd_handshake() == "AT+VERSION?\r\n"

    def test_query_sense(self):
        assert cmd_query_sense() == "AT+SENSE?\r\n"

    def test_query_fault(self):
        assert cmd_query_fault() == "AT+FAULT?\r\n"

    def test_query_motor(self):
        assert cmd_query_motor() == "AT+MOTOR?\r\n"

    def test_query_output(self):
        assert cmd_query_output() == "AT+OUTPUT?\r\n"

    def test_query_diag(self):
        assert cmd_query_diag() == "AT+DIAG?\r\n"

    @pytest.mark.parametrize("mode", ["SLEEP", "WAKE", "FWD", "REV", "BRAKE", "STOP"])
    def test_set_motor_all_modes(self, mode):
        assert cmd_set_motor(mode) == f"AT+MOTOR={mode}\r\n"

    def test_set_bypasses(self):
        assert cmd_set_motor_bypass(True) == "AT+MOTOR_BYPASS=ON\r\n"
        assert cmd_set_motor_bypass(False) == "AT+MOTOR_BYPASS=OFF\r\n"
        assert cmd_set_charge_bypass(True) == "AT+CHARGE_BYPASS=ON\r\n"
        assert cmd_set_charge_bypass(False) == "AT+CHARGE_BYPASS=OFF\r\n"

    def test_set_led(self):
        assert cmd_set_led(True) == "AT+LED=ON\r\n"
        assert cmd_set_led(False) == "AT+LED=OFF\r\n"

    def test_set_nmos_validates(self):
        with pytest.raises(ValueError):
            cmd_set_nmos(3, True)
        with pytest.raises(ValueError):
            cmd_set_nmos(0, True)
        assert cmd_set_nmos(1, True) == "AT+NMOS1=ON\r\n"
        assert cmd_set_nmos(2, False) == "AT+NMOS2=OFF\r\n"

    def test_set_power_modes(self):
        assert cmd_set_charge(True) == "AT+CHARGE=ON\r\n"
        assert cmd_set_charge(False) == "AT+CHARGE=OFF\r\n"
        assert cmd_set_drive(True) == "AT+DRIVE=ON\r\n"
        assert cmd_set_drive(False) == "AT+DRIVE=OFF\r\n"
        assert cmd_power_off() == "AT+POWER=OFF\r\n"

    def test_set_uart(self):
        assert cmd_set_uart2(True) == "AT+UART2=ON\r\n"
        assert cmd_set_uart3(False) == "AT+UART3=OFF\r\n"
        assert cmd_set_uart23(True) == "AT+UART2&3=ON\r\n"

    def test_cmd_raw_no_crlf(self):
        assert cmd_raw("AT+FOO=BAR") == "AT+FOO=BAR\r\n"

    def test_cmd_raw_with_crlf(self):
        assert cmd_raw("AT+FOO=BAR\r\n") == "AT+FOO=BAR\r\n"

    def test_cmd_raw_preserves_intermediate(self):
        # 解析器不允许中间空格, 但 raw 不强制改, 留给固件报错
        assert cmd_raw("AT + FOO = BAR") == "AT + FOO = BAR\r\n"

    def test_uart_tx_chunks_are_binary_exact(self):
        payload = bytes(range(32)) + b"\x00\xff\r\n"
        assert list(iter_uart_tx_commands(payload)) == [
            f"AT+UARTTX={bytes(range(32)).hex().upper()}\r\n",
            "AT+UARTTX=00FF0D0A\r\n",
        ]

    def test_uart_tx_rejects_empty_payload(self):
        with pytest.raises(ValueError):
            list(iter_uart_tx_commands(b""))


# ---- 响应解析 ----
class TestParsedResponse:
    def test_ok(self):
        r = ParsedResponse.parse("OK")
        assert r.ok
        assert r.error is None
        assert r.raw_line == "OK"

    def test_error_bare(self):
        r = ParsedResponse.parse("ERROR")
        assert r.error == AtError(code="")
        assert not r.ok

    def test_error_with_code(self):
        r = ParsedResponse.parse("ERROR:PARSE")
        assert r.error == AtError(code="PARSE")
        assert not r.ok

    @pytest.mark.parametrize(
        "code",
        ["PARSE", "SENSE_NOT_READY", "LINE_TOO_LONG", "STATE_BUSY", "LED_QUEUE",
         "MOTOR_QUEUE", "OUTPUT_QUEUE", "UNSUPPORTED"],
    )
    def test_error_all_codes(self, code):
        r = ParsedResponse.parse(f"ERROR:{code}")
        assert r.error.code == code

    def test_sense(self):
        r = ParsedResponse.parse(SEMANTIC_SENSE_LINE)
        assert r.sense is not None
        d = r.sense
        assert d.batt_ntc == "25.1C"
        assert d.batt_v == "37.0V"
        assert d.mcu_c == "24.9C"
        assert d.lm51770_c == "35.2C"
        assert d.mp4317_c == "36.3C"
        assert d.drv8874_c == "37.4C"
        assert d.charge_mos_c == "38.5C"
        assert d.motor_i == "1.2A"
        assert d.tick == 12345
        assert d.count == 42
        assert d.stk_at == 200
        assert d.stk_sensor == 180
        assert d.stk_motor == 160
        assert d.tx_sp == 3
        assert d.tx_ls == 4

    def test_legacy_numbered_sense_line_is_rejected(self):
        line = (
            "+SENSE:BATT_NTC=25.1C,BATT_V=37.0V,NTC1_C=24.9C,NTC2_C=35.2C,"
            "NTC3_C=36.3C,MOTOR_I=1.2A,TICK=12345,COUNT=42,"
            "STK_AT=200,STK_SENSOR=180,STK_MOTOR=160,TX_SP=3,TX_LS=4"
        )
        assert ParsedResponse.parse(line).sense is None

    @pytest.mark.parametrize(
        "missing_key",
        [key for key, _ in SEMANTIC_SENSE_FIELDS],
    )
    def test_missing_required_semantic_sense_field_is_rejected(self, missing_key):
        line = "+SENSE:" + ",".join(
            f"{key}={value}"
            for key, value in SEMANTIC_SENSE_FIELDS
            if key != missing_key
        )
        assert ParsedResponse.parse(line).sense is None

    @pytest.mark.parametrize(
        "extra_field",
        [
            "NTC1_C=24.9C",
            "NTC2_C=35.2C",
            "NTC3_C=36.3C",
            "MCU_C=99.9C",
        ],
    )
    def test_unexpected_or_duplicate_sense_field_is_rejected(self, extra_field):
        assert ParsedResponse.parse(
            f"{SEMANTIC_SENSE_LINE},{extra_field}"
        ).sense is None

    @pytest.mark.parametrize(
        "numeric_key",
        ["TICK", "COUNT", "STK_AT", "STK_SENSOR", "STK_MOTOR", "TX_SP", "TX_LS"],
    )
    def test_malformed_numeric_sense_diagnostic_is_rejected(self, numeric_key):
        line = "+SENSE:" + ",".join(
            f"{key}={'bad' if key == numeric_key else value}"
            for key, value in SEMANTIC_SENSE_FIELDS
        )
        assert ParsedResponse.parse(line).sense is None

    def test_fault(self):
        r = ParsedResponse.parse("+FAULT:DRV=0,AUX=1")
        assert r.fault == FaultState(drv=0, aux=1)

    def test_motor(self):
        r = ParsedResponse.parse("+MOTOR:MODE=FWD,CURRENT_MA=1234,OVERCURRENT=0,FAULT=0")
        assert r.motor == MotorState(mode="FWD", current_ma=1234, overcurrent=0, fault=0)

    def test_output(self):
        r = ParsedResponse.parse(
            "+OUTPUT:POWER=CHARGE,CHARGE_PHASE=OFF,NMOS1=0,NMOS2=1,"
            "LIGHTS=0,MOTOR_BYPASS=1,CHARGE_BYPASS=1"
        )
        assert r.output == OutputState(
            power="CHARGE",
            charge_phase="OFF",
            nmos1=False,
            nmos2=True,
            lights=False,
            motor_bypass=True,
            charge_bypass=True,
        )

    @pytest.mark.parametrize(
        "line",
        [
            "+OUTPUT:POWER=CHARGE,CHARGE_PHASE=OFF,NMOS1=0,NMOS2=1,"
            "LIGHTS=0,MOTOR_BYPASS=1",
            "+OUTPUT:POWER=CHARGE,CHARGE_PHASE=OFF,NMOS1=0,NMOS2=1,"
            "LIGHTS=0,MOTOR_BYPASS=1,CHARGE_BYPASS=1,EXTRA=0",
            "+OUTPUT:POWER=INVALID,CHARGE_PHASE=OFF,NMOS1=0,NMOS2=1,"
            "LIGHTS=0,MOTOR_BYPASS=1,CHARGE_BYPASS=1",
            "+OUTPUT:POWER=CHARGE,CHARGE_PHASE=OFF,NMOS1=2,NMOS2=1,"
            "LIGHTS=0,MOTOR_BYPASS=1,CHARGE_BYPASS=1",
            "+OUTPUT:POWER=CHARGE,POWER=DRIVE,CHARGE_PHASE=OFF,NMOS1=0,"
            "NMOS2=1,LIGHTS=0,MOTOR_BYPASS=1,CHARGE_BYPASS=1",
        ],
    )
    def test_malformed_output_is_rejected(self, line):
        parsed = ParsedResponse.parse(line)
        assert parsed.output is None

    def test_version(self):
        r = ParsedResponse.parse("+VERSION:release-v2.1")
        assert r.version == VersionInfo(version="release-v2.1")

    def test_diag(self):
        line = (
            "+DIAG:RX_ISR=1,RX_BYTE=2,RX_OVERFLOW=0,RX_ERR=0,ORE=0,NE=0,FE=0,PE=0,"
            "LINE_TOO_LONG=0,AT_LOOP=10,TX_CALL=5,TX_OK=5,TX_TIMEOUT=0,TX_ERR=0,"
            "TX_BUSY=1,TX_STATE_PRE=2,TX_STATE_POST=3,TX_ERR_PRE=4,TX_ERR_POST=5,"
            "TX_LAST_STATUS=6,SENSOR_LOOP=7,SENSOR_PUBLISH=8,SENSOR_LAST_PUBLISH_TICK=9,"
            "SENSOR_ADC1_READ_FAIL=10,SENSOR_ADC2_READ_FAIL=11,UART2_RX_BYTE=12,"
            "UART2_RX_OVERFLOW=13,UART3_RX_BYTE=14,UART3_RX_OVERFLOW=15"
        )
        r = ParsedResponse.parse(line)
        assert r.diag is not None
        assert r.diag.rx_isr == 1
        assert r.diag.at_loop == 10
        assert r.diag.uart2_rx_byte == 12
        assert r.diag.uart3_rx_overflow == 15

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("+UART2RX:000D0AFF", UartRxFrame(2, b"\x00\r\n\xff")),
            ("+UART3RX:414243", UartRxFrame(3, b"ABC")),
        ],
    )
    def test_uart_rx_event(self, line, expected):
        r = ParsedResponse.parse(line)
        assert r.uart_rx == expected
        assert not r.is_passthrough

    @pytest.mark.parametrize(
        "line",
        ["+UART2RX:", "+UART2RX:0", "+UART2RX:00ff", "+UART3RX:GG"],
    )
    def test_malformed_uart_rx_event_is_not_accepted(self, line):
        assert ParsedResponse.parse(line).uart_rx is None

    def test_passthrough(self):
        r = ParsedResponse.parse("HELLO")
        assert r.is_passthrough
        assert r.raw_line == "HELLO"
        assert not r.ok and r.error is None

    def test_passthrough_binary_as_latin1(self):
        r = ParsedResponse.parse("0xFF 0xAB")  # 实际上 raw line 是解码后字符串
        assert r.is_passthrough


# ---- 行切分 ----
class TestLineSplitter:
    def test_no_data(self):
        s = LineSplitter()
        assert s.feed(b"") == []

    def test_single_line(self):
        s = LineSplitter()
        assert s.feed(b"OK\r\n") == ["OK"]

    def test_multiple_lines_in_one_chunk(self):
        s = LineSplitter()
        data = b"+SENSE:...\r\nOK\r\n"
        assert s.feed(data) == ["+SENSE:...", "OK"]

    def test_split_across_chunks(self):
        s = LineSplitter()
        assert s.feed(b"+SE") == []
        assert s.feed(b"NSE:...") == []
        assert s.feed(b"\r\nOK\r\n") == ["+SENSE:...", "OK"]

    def test_partial_line_at_end_kept(self):
        s = LineSplitter()
        # 第一段: 完整一行 + 一行半
        assert s.feed(b"AT line 1\r\nAT line 2 partia") == ["AT line 1"]
        # 第二段: 续上前面那行
        assert s.feed(b"l\r\n") == ["AT line 2 partial"]

    def test_reset(self):
        s = LineSplitter()
        s.feed(b"partial line")
        s.reset()
        assert s.feed(b"new line\r\n") == ["new line"]

    def test_utf8(self):
        s = LineSplitter()
        assert s.feed("中文\r\n".encode("utf-8")) == ["中文"]

    def test_invalid_utf8_falls_back(self):
        s = LineSplitter()
        # 0xff 0xfe 不是合法 utf-8, 我们的策略: utf-8 失败则用 latin-1 兜底
        # latin-1 把每个 byte 直接当 codepoint, 所以 0xff -> ÿ, 0xfe -> þ
        assert s.feed(b"\xff\xfe\r\n") == ["\xff\xfe"]
