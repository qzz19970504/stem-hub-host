from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.models import FaultState, MotorState, SenseData
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow
from stem_hub_host.ui.widgets.charge_mode_card import ChargeModeCard


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return get_app()


@pytest.fixture
def output_card(qapp: QApplication) -> ChargeModeCard:
    card = ChargeModeCard()
    yield card
    card.deleteLater()
    qapp.processEvents()


@pytest.fixture
def window(qapp: QApplication) -> MainWindow:
    worker = SerialWorker(FakeSerialTransport())
    host_controller = Controller(worker)
    main_window = MainWindow(host_controller)
    yield main_window
    main_window.close()
    worker.close()
    worker.deleteLater()
    qapp.processEvents()


def test_output_card_exposes_only_real_toggle_controls(
    output_card: ChargeModeCard,
) -> None:
    assert set(output_card.control_names) == {
        "CHARGE",
        "DISCHARGE",
        "NMOS1",
        "NMOS2",
        "LIGHTS",
    }
    assert "BALANCING" not in output_card.control_names
    assert output_card.all_off_button.text() == "ALL OFF"


def test_all_off_is_centered_below_the_five_output_switches(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(520, 430)
    output_card.show()
    qapp.processEvents()

    lowest_toggle_y = max(
        cell.toggle.mapTo(output_card, cell.toggle.rect().center()).y()
        for cell in output_card._cells.values()
    )
    all_off_center = output_card.all_off_button.mapTo(
        output_card,
        output_card.all_off_button.rect().center(),
    )

    assert output_card.all_off_row.objectName() == "allOffRow"
    assert all_off_center.y() > lowest_toggle_y
    assert abs(all_off_center.x() - output_card.width() / 2) < 8


def test_charge_closes_discharge_path_before_enabling_charge(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_modes: list[str] = []
    monkeypatch.setattr(
        window._controller,
        "set_charge_mode",
        requested_modes.append,
    )

    window._on_toggle_changed("CHARGE", True)

    assert requested_modes == ["charge"]
    assert not window.console_tab.charge_card.is_on("DISCHARGE")


def test_all_off_closes_every_output_in_safe_order(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        window._controller,
        "set_all_outputs_off",
        lambda: calls.append(("all_outputs", False)),
    )

    window._on_all_outputs_off()

    assert calls == [("all_outputs", False)]


def test_sensor_and_fault_data_drive_honest_indicators(window: MainWindow) -> None:
    window._controller._latest_sense = SenseData(
        batt_ntc="82.0C",
        batt_v="29.0V",
        ntc1_c="30.0C",
        ntc2_c="31.0C",
        ntc3_c="32.0C",
        motor_i="2.9A",
        tick=1,
        count=1,
        stk_at=0,
        stk_sensor=0,
        stk_motor=0,
        tx_sp=0,
        tx_ls=0,
    )
    window._controller._latest_motor = MotorState(
        mode="FWD",
        current_ma=2900,
        overcurrent=1,
        fault=1,
    )
    window._controller._latest_fault = FaultState(drv=1, aux=0)

    window._refresh_ui_from_state()

    card = window.console_tab.charge_card
    assert card.fault_overtemp.state == "error"
    assert card.fault_overcurrent.state == "error"
    assert card.fault_undervoltage.state == "error"
    assert card.fault_drv.state == "error"
    assert card.fault_aux.state == "ok"
