from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDoubleSpinBox

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow
from stem_hub_host.ui.tab2_plot import PlotTab


def test_sample_rate_control_exposes_only_slow_range() -> None:
    get_app()
    tab = PlotTab(DataBuffer())

    assert isinstance(tab.hz_spin, QDoubleSpinBox)
    assert tab.hz_spin.minimum() == pytest.approx(0.2)
    assert tab.hz_spin.maximum() == pytest.approx(1.0)
    assert tab.hz_spin.singleStep() == pytest.approx(0.2)
    assert tab.hz_spin.decimals() == 1
    assert tab.hz_spin.value() == pytest.approx(1.0)


def test_controller_maps_supported_rates_to_intervals() -> None:
    get_app()
    controller = Controller(SerialWorker(FakeSerialTransport()))
    expected = {
        0.2: 5000,
        0.4: 2500,
        0.6: 1667,
        0.8: 1250,
        1.0: 1000,
    }

    for hz, interval in expected.items():
        controller.set_sense_hz(hz)
        assert controller.sense_hz == pytest.approx(hz)
        assert controller._sense_timer.interval() == interval


@pytest.mark.parametrize(
    ("requested", "normalized"),
    (
        (0.01, 0.2),
        (0.3, 0.4),
        (0.51, 0.6),
        (0.91, 1.0),
        (2.0, 1.0),
    ),
)
def test_non_step_rate_snaps_to_nearest_supported_value(
    requested: float,
    normalized: float,
) -> None:
    get_app()
    controller = Controller(SerialWorker(FakeSerialTransport()))
    changed: list[float] = []
    controller.sense_request_hz_changed.connect(changed.append)

    controller.set_sense_hz(requested)

    assert controller.sense_hz == pytest.approx(normalized)
    assert changed[-1] == pytest.approx(normalized)


def test_main_window_reflects_normalized_rate_in_spin_box() -> None:
    app = get_app()
    worker = SerialWorker(FakeSerialTransport())
    controller = Controller(worker)
    window = MainWindow(controller)

    window.plot_tab.hz_spin.setValue(0.3)
    app.processEvents()

    assert controller.sense_hz == pytest.approx(0.4)
    assert window.plot_tab.hz_spin.value() == pytest.approx(0.4)
    window.close()
    worker.close()
