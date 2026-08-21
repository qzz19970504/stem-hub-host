from tools import real_serial_smoke


def test_real_serial_smoke_defaults_to_firmware_baud() -> None:
    assert real_serial_smoke.DEFAULT_BAUD == 9600


def test_real_serial_smoke_exposes_uart3_probe_payloads() -> None:
    assert real_serial_smoke.UART3_FORWARD_PROBE == (
        b"HOST-UART3\x00\xffabc+++def"
    )
    assert real_serial_smoke.UART3_REVERSE_PROBE == b"MCU-UART3\x00\xff"
