from tools import real_serial_smoke


def test_real_serial_smoke_defaults_to_firmware_baud() -> None:
    assert real_serial_smoke.DEFAULT_BAUD == 9600


def test_real_serial_smoke_exposes_binary_probe_payloads() -> None:
    assert real_serial_smoke.TRANSPARENT_FORWARD_PROBE == (
        b"HOST-TRANS\x00\xffabc+++def"
    )
    assert real_serial_smoke.TRANSPARENT_REVERSE_PROBE == b"MCU-TRANS\x00\xff"


def test_real_serial_smoke_maps_explicit_transparent_targets() -> None:
    assert real_serial_smoke.TRANSPARENT_TARGET_UART_INDEX == {
        "uart2": 2,
        "uart3": 3,
    }
