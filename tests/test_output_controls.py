from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.models import FaultState, MotorState, OutputState, SenseData
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.main_window import MainWindow
from stem_hub_host.ui.widgets.charge_mode_card import ChargeModeCard
from stem_hub_host.ui.widgets.motor_card import MotorCard


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
        "CHARGE_BYPASS",
        "DRIVE",
        "NMOS1",
        "NMOS2",
        "LIGHTS",
    }
    assert "BALANCING" not in output_card.control_names
    assert output_card.all_off_button.text() == "ALL OFF"


def test_charge_bypass_is_vertically_aligned_with_lights(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(520, 430)
    output_card.show()
    qapp.processEvents()

    bypass_x = output_card._cells["CHARGE_BYPASS"].toggle.mapTo(
        output_card,
        output_card._cells["CHARGE_BYPASS"].toggle.rect().center(),
    ).x()
    lights_x = output_card._cells["LIGHTS"].toggle.mapTo(
        output_card,
        output_card._cells["LIGHTS"].toggle.rect().center(),
    ).x()

    assert abs(bypass_x - lights_x) <= 2
    assert output_card.drive_hierarchy.objectName() == "driveHierarchy"


def test_output_controls_follow_approved_hierarchy(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(367, 312)
    output_card.show()
    qapp.processEvents()

    centers = {
        name: cell.toggle.mapTo(output_card, cell.toggle.rect().center())
        for name, cell in output_card._cells.items()
    }

    assert abs(centers["CHARGE"].y() - centers["CHARGE_BYPASS"].y()) <= 2
    assert centers["CHARGE"].y() < centers["DRIVE"].y()
    assert centers["DRIVE"].y() < centers["NMOS1"].y()
    assert abs(centers["NMOS1"].y() - centers["NMOS2"].y()) <= 2
    assert abs(centers["NMOS2"].y() - centers["LIGHTS"].y()) <= 2
    assert abs(centers["DRIVE"].x() - centers["NMOS2"].x()) <= 2
    assert output_card._cells["CHARGE_BYPASS"].label.text() == "CHARGE BYPASS"
    assert (
        output_card._cells["CHARGE_BYPASS"].label.font().pointSize()
        == output_card._cells["CHARGE"].label.font().pointSize()
    )


def test_output_upper_region_gives_drive_twice_the_charge_height(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(710, 511)
    output_card.show()
    qapp.processEvents()

    assert hasattr(output_card, "charge_region")
    assert hasattr(output_card, "drive_region")
    ratio = output_card.drive_region.height() / output_card.charge_region.height()
    assert 1.95 <= ratio <= 2.05


def test_output_switches_and_labels_are_fully_contained(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(367, 312)
    output_card.show()
    qapp.processEvents()

    for cell in output_card._cells.values():
        for widget in (cell.toggle, cell.label):
            top_left = widget.mapTo(output_card, widget.rect().topLeft())
            bottom_right = widget.mapTo(output_card, widget.rect().bottomRight())
            assert top_left.x() >= 0
            assert top_left.y() >= 0
            assert bottom_right.x() < output_card.width()
            assert bottom_right.y() < output_card.divider.y()
            assert widget.sizeHint().width() <= widget.width()


def test_motor_status_bands_use_equal_vertical_spacing(
    qapp: QApplication,
) -> None:
    card = MotorCard()
    card.setFixedSize(710, 511)
    card.show()
    qapp.processEvents()

    mode_bottom = card.mode_badge.mapTo(card, card.mode_badge.rect().bottomLeft()).y()
    current_top = card.current_badge.mapTo(card, card.current_badge.rect().topLeft()).y()
    current_bottom = card.current_badge.mapTo(
        card, card.current_badge.rect().bottomLeft()
    ).y()
    divider_top = card.divider.mapTo(card, card.divider.rect().topLeft()).y()

    mode_to_status = current_top - mode_bottom
    status_to_divider = divider_top - current_bottom
    assert abs(mode_to_status - status_to_divider) <= 2
    assert 14 <= mode_to_status <= 16

    card.close()
    card.deleteLater()


def test_output_parent_child_gates_are_independent(
    output_card: ChargeModeCard,
) -> None:
    output_card.set_enabled(True)
    output_card.set_control_enabled("CHARGE_BYPASS", False)
    for name in ("NMOS1", "NMOS2", "LIGHTS"):
        output_card.set_control_enabled(name, False)

    assert output_card._cells["CHARGE"].toggle.isEnabled()
    assert output_card._cells["DRIVE"].toggle.isEnabled()
    assert not output_card._cells["CHARGE_BYPASS"].toggle.isEnabled()
    assert all(
        not output_card._cells[name].toggle.isEnabled()
        for name in ("NMOS1", "NMOS2", "LIGHTS")
    )


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


def test_fault_rows_use_the_lower_card_area_without_dead_space(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(520, 430)
    output_card.show()
    qapp.processEvents()

    fault_bottom = max(
        fault.mapTo(output_card, fault.rect().bottomLeft()).y()
        for fault in (
            output_card.fault_overtemp,
            output_card.fault_overcurrent,
            output_card.fault_undervoltage,
            output_card.fault_drv,
            output_card.fault_aux,
        )
    )

    assert output_card.height() - fault_bottom <= 55


def test_fault_rows_have_three_equal_vertical_gaps(
    output_card: ChargeModeCard,
    qapp: QApplication,
) -> None:
    output_card.setFixedSize(710, 511)
    output_card.show()
    qapp.processEvents()

    first_row = (
        output_card.fault_overtemp,
        output_card.fault_overcurrent,
        output_card.fault_undervoltage,
    )
    second_row = (output_card.fault_drv, output_card.fault_aux)
    first_top = min(widget.geometry().top() for widget in first_row)
    first_bottom = max(widget.geometry().bottom() for widget in first_row)
    second_top = min(widget.geometry().top() for widget in second_row)
    second_bottom = max(widget.geometry().bottom() for widget in second_row)
    gaps = (
        first_top,
        second_top - first_bottom - 1,
        output_card.fault_region.height() - second_bottom - 1,
    )

    assert max(gaps) - min(gaps) <= 2


def test_charge_and_drive_are_mutually_exclusive(
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
    assert not window.console_tab.charge_card.is_on("DRIVE")

    window.console_tab.charge_card.set_toggle("CHARGE", True)
    window._on_toggle_changed("DRIVE", True)

    assert requested_modes == ["charge", "drive"]
    assert not window.console_tab.charge_card.is_on("CHARGE")


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


def test_power_off_failure_restores_confirmed_drive_without_key_error(
    window: MainWindow,
) -> None:
    card = window.console_tab.charge_card
    window._controller._latest_output = OutputState(
        "DRIVE", "IDLE", False, False, False, False, False
    )
    card.clear_controls()

    window._on_output_command_failed("POWER", False, "OUTPUT_QUEUE")

    assert not card.is_on("CHARGE")
    assert card.is_on("DRIVE")


def test_sensor_and_fault_data_drive_honest_indicators(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The semantic tile layout is migrated in Task 4; isolate this fault test.
    monkeypatch.setattr(
        window.console_tab.temp_grid,
        "update_from_sense",
        lambda _: None,
    )
    window._controller._latest_sense = SenseData(
        batt_ntc="82.0C",
        batt_v="29.0V",
        mcu_c="30.0C",
        lm51770_c="31.0C",
        mp4317_c="32.0C",
        drv8874_c="33.0C",
        charge_mos_c="34.0C",
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
    assert card.fault_aux.state == "off"


def test_confirmed_output_state_drives_switches_and_child_gates(
    window: MainWindow,
) -> None:
    window._handshake_connected = True
    window._controller._latest_motor = MotorState("FWD", 500, 0, 0)
    window._controller._latest_output = OutputState(
        "DRIVE", "IDLE", True, False, True, True, False
    )

    window._refresh_ui_from_state()

    output_card = window.console_tab.charge_card
    motor_card = window.console_tab.motor_card
    assert output_card.is_on("DRIVE")
    assert not output_card.is_on("CHARGE")
    assert output_card.is_on("NMOS1")
    assert output_card.is_on("LIGHTS")
    assert not output_card.is_on("CHARGE_BYPASS")
    assert output_card._cells["NMOS1"].toggle.isEnabled()
    assert not output_card._cells["CHARGE_BYPASS"].toggle.isEnabled()
    assert motor_card.bypass_toggle.is_on()
    assert motor_card.bypass_toggle.isEnabled()


def test_motor_bypass_is_disabled_outside_confirmed_motion(
    window: MainWindow,
) -> None:
    window._handshake_connected = True
    window._controller._latest_motor = MotorState("STOP", 0, 0, 0)
    window._controller._latest_output = OutputState(
        "OFF", "IDLE", False, False, False, False, False
    )

    window._refresh_ui_from_state()

    assert not window.console_tab.motor_card.bypass_toggle.isEnabled()
