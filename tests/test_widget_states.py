from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPropertyAnimation, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.models import SenseData
from stem_hub_host.ui import theme
from stem_hub_host.ui.stylesheet import get_qss, invalidate_cache
from stem_hub_host.ui.tab2_plot import PlotTab
from stem_hub_host.ui.widgets.at_console import AtConsole
from stem_hub_host.ui.widgets.charge_mode_card import ChargeModeCard
from stem_hub_host.ui.widgets.motor_card import MotorCard
from stem_hub_host.ui.widgets.passthrough_panel import PassthroughPanel
from stem_hub_host.ui.widgets.temp_grid import TempGridCard, ThermalGauge
from stem_hub_host.ui.widgets.toggle_switch import ToggleSwitch


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    theme.set_color_scheme("dark")
    invalidate_cache()
    app.setStyleSheet(get_qss())
    return app


@pytest.fixture
def semantic_sense() -> SenseData:
    return SenseData(
        batt_ntc="40.0C",
        batt_v="28.0V",
        mcu_c="41.0C",
        lm51770_c="42.0C",
        mp4317_c="43.0C",
        drv8874_c="44.0C",
        charge_mos_c="45.0C",
        motor_i="1.0A",
        tick=1,
        count=2,
        stk_at=3,
        stk_sensor=4,
        stk_motor=5,
        tx_sp=6,
        tx_ls=7,
    )


def test_motor_buttons_follow_confirmed_mode(qapp: QApplication) -> None:
    card = MotorCard()
    assert card.mode_badge.height() == 130
    card.update_state("REV", 1200, 0, 0)

    assert card.buttons["REV"].isChecked()
    assert sum(button.isChecked() for button in card.buttons.values()) == 1

    card.deleteLater()
    qapp.processEvents()


def test_thermal_gauge_reuses_one_animation_for_repeated_updates(
    qapp: QApplication,
) -> None:
    gauge = ThermalGauge()
    gauge.set_value(25.0)
    animation = gauge._animation

    for _ in range(100):
        gauge.set_value(25.0)

    assert gauge._animation is animation
    assert len(gauge.findChildren(QPropertyAnimation)) == 1
    gauge.deleteLater()
    qapp.processEvents()


def test_terminal_log_uses_direction_without_timestamp(qapp: QApplication) -> None:
    console = AtConsole()
    console.append_log("RX", "OK")
    plain_text = console.log_view.toPlainText()

    assert "<< OK" in plain_text
    assert not re.search(r"\d{2}:\d{2}:\d{2}", plain_text)

    console.deleteLater()
    qapp.processEvents()


def test_toggle_switch_supports_keyboard_activation(qapp: QApplication) -> None:
    toggle = ToggleSwitch()
    emitted_states: list[bool] = []
    toggle.toggled.connect(emitted_states.append)
    toggle.show()
    toggle.setFocus()

    QTest.keyClick(toggle, Qt.Key.Key_Space)
    qapp.processEvents()

    assert toggle.is_on()
    assert emitted_states == [True]
    assert toggle.focusPolicy() == Qt.FocusPolicy.StrongFocus

    toggle.deleteLater()
    qapp.processEvents()


def test_toggle_switch_activates_on_release_and_has_disabled_visual(
    qapp: QApplication,
) -> None:
    toggle = ToggleSwitch()
    toggle.show()
    qapp.processEvents()

    QTest.mousePress(toggle, Qt.MouseButton.LeftButton)
    assert not toggle.is_on()
    QTest.mouseRelease(toggle, Qt.MouseButton.LeftButton)
    assert toggle.is_on()

    enabled_color = toggle.grab().toImage().pixelColor(4, 20)
    toggle.setEnabled(False)
    qapp.processEvents()
    disabled_color = toggle.grab().toImage().pixelColor(4, 20)
    assert disabled_color.lightness() < enabled_color.lightness()
    assert toggle.testAttribute(Qt.WidgetAttribute.WA_Hover)
    toggle.deleteLater()
    qapp.processEvents()


def test_motor_buttons_opt_into_hover_rendering(qapp: QApplication) -> None:
    card = MotorCard()

    assert all(
        button.testAttribute(Qt.WidgetAttribute.WA_Hover)
        for button in card.buttons.values()
    )
    card.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("object_name", ["primary", "allOffButton"])
def test_named_action_buttons_render_visibly_dim_when_disabled(
    qapp: QApplication,
    object_name: str,
) -> None:
    qapp.setStyleSheet(get_qss())
    button = QPushButton("ACTION")
    button.setObjectName(object_name)
    button.setFixedSize(120, 40)
    button.show()
    qapp.processEvents()
    enabled_color = button.grab().toImage().pixelColor(12, 20)

    button.setEnabled(False)
    qapp.processEvents()
    disabled_color = button.grab().toImage().pixelColor(12, 20)

    assert disabled_color.lightness() < enabled_color.lightness() - 10
    button.deleteLater()
    qapp.processEvents()


def test_at_console_send_button_uses_shared_disabled_state(
    qapp: QApplication,
) -> None:
    qapp.setStyleSheet(get_qss())
    console = AtConsole()
    console.show()
    qapp.processEvents()
    console.send_btn.setEnabled(True)
    qapp.processEvents()
    enabled_color = console.send_btn.grab().toImage().pixelColor(12, 18)

    console.send_btn.setEnabled(False)
    qapp.processEvents()
    disabled_color = console.send_btn.grab().toImage().pixelColor(12, 18)

    assert console.send_btn.objectName() == "primary"
    assert disabled_color.lightness() < enabled_color.lightness() - 10
    console.deleteLater()
    qapp.processEvents()


def test_terminal_has_only_outer_card_and_named_command_bar(
    qapp: QApplication,
) -> None:
    console = AtConsole()

    assert console.command_bar.objectName() == "commandBar"
    assert "background: transparent" in console.log_view.styleSheet()
    console.deleteLater()
    qapp.processEvents()


def test_temperature_tiles_use_semantic_hardware_names_in_order(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()

    assert tuple(tile.title_label.text() for tile in grid._tiles()) == (
        "BATTERY",
        "MCU",
        "LM51770",
        "MP4317",
        "DRV8874",
        "CHG MOS",
    )
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_tiles_follow_the_matching_semantic_fields(
    qapp: QApplication,
    semantic_sense: SenseData,
) -> None:
    grid = TempGridCard()
    grid.update_from_sense(semantic_sense)

    assert tuple(tile.value_label.text() for tile in grid._tiles()) == (
        "40.0°C",
        "41.0°C",
        "42.0°C",
        "43.0°C",
        "44.0°C",
        "45.0°C",
    )
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_tiles_reset_all_semantic_channels_without_data(
    qapp: QApplication,
    semantic_sense: SenseData,
) -> None:
    grid = TempGridCard()
    grid.update_from_sense(semantic_sense)

    grid.update_from_sense(None)

    assert all(tile.value_label.text() == "--" for tile in grid._tiles())
    assert all(tile.gauge.celsius is None for tile in grid._tiles())
    assert all(tile.gauge.level == 0.0 for tile in grid._tiles())
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_tiles_use_exact_three_by_two_positions(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()

    assert grid.grid.itemAtPosition(0, 0).widget() is grid.tile_battery
    assert grid.grid.itemAtPosition(0, 1).widget() is grid.tile_mcu
    assert grid.grid.itemAtPosition(1, 0).widget() is grid.tile_lm51770
    assert grid.grid.itemAtPosition(1, 1).widget() is grid.tile_mp4317
    assert grid.grid.itemAtPosition(2, 0).widget() is grid.tile_drv8874
    assert grid.grid.itemAtPosition(2, 1).widget() is grid.tile_charge_mos
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_tiles_use_animated_thermal_gauges(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()

    assert all(
        hasattr(tile, "gauge")
        for tile in grid._tiles()
    )

    for value, expected in (
        (-2.0, 0.0),
        (0.0, 0.0),
        (40.0, 0.4),
        (100.0, 1.0),
        (125.0, 1.0),
    ):
        for tile in grid._tiles():
            tile.set_value(value, animate=False)
            assert tile.gauge.celsius == value
            assert tile.gauge.level == pytest.approx(expected)

    for tile in grid._tiles():
        tile.set_value(None, animate=False)
        assert tile.gauge.level == 0.0
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_theme_refresh_updates_all_semantic_tiles(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grid = TempGridCard()
    refreshed_tiles = []
    for tile in grid._tiles():
        monkeypatch.setattr(
            tile,
            "refresh_theme",
            lambda current_tile=tile: refreshed_tiles.append(current_tile),
        )

    grid.refresh_theme()

    assert refreshed_tiles == list(grid._tiles())
    grid.deleteLater()
    qapp.processEvents()


def test_temperature_palette_has_five_theme_aware_bands() -> None:
    try:
        theme.set_color_scheme("dark")
        dark = [
            QColor(theme.temp_color(value))
            for value in (10.0, 35.0, 57.0, 72.0, 90.0)
        ]
        assert len({color.name() for color in dark}) == 5
        assert theme.temp_color(None) == theme.FG_TERTIARY

        theme.set_color_scheme("light")
        light = [
            QColor(theme.temp_color(value))
            for value in (10.0, 35.0, 57.0, 72.0, 90.0)
        ]
        assert [color.name() for color in light] != [
            color.name() for color in dark
        ]
    finally:
        theme.set_color_scheme("dark")


def test_temperature_value_text_follows_current_band(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()
    tile = grid.tile_battery
    tile.set_value(72.0, animate=False)

    expected = QColor(theme.temp_color(72.0)).name()
    assert expected in tile.value_label.styleSheet().lower()

    grid.deleteLater()
    qapp.processEvents()


def test_temperature_gauge_is_neutral_without_sensor_data(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()
    grid.tile_battery.set_value(None, animate=False)
    image = grid.tile_battery.gauge.grab().toImage()
    neutral = image.pixelColor(17, 20)

    assert neutral.name() == QColor(theme.BG_INPUT).name()

    grid.deleteLater()
    qapp.processEvents()


def test_temperature_column_uses_current_band_color_at_exact_level(
    qapp: QApplication,
) -> None:
    grid = TempGridCard()
    gauge = grid.tile_battery.gauge
    samples = {}

    for value in (25.0, 72.0):
        grid.tile_battery.set_value(value, animate=False)
        assert gauge.level == pytest.approx(value / 100.0)
        image = gauge.grab().toImage()
        samples[value] = image.pixelColor(17, 66)

    assert samples[25.0].hue() != samples[72.0].hue()
    assert samples[25.0].green() > samples[25.0].red()
    assert samples[72.0].red() > samples[72.0].blue()

    grid.deleteLater()
    qapp.processEvents()


def test_motor_buttons_are_evenly_distributed(
    qapp: QApplication,
) -> None:
    qapp.setStyleSheet(get_qss())
    card = MotorCard()
    card.set_enabled(True)
    card.setFixedSize(650, 410)
    card.show()
    qapp.processEvents()

    ordered = [
        card.buttons[key]
        for key in ("SLEEP", "WAKE", "FWD", "REV", "BRAKE", "STOP")
    ]
    centers = [button.geometry().center().x() for button in ordered]
    gaps = [
        right_center - left_center
        for left_center, right_center in zip(centers, centers[1:])
    ]
    widths = [button.width() for button in ordered]

    assert max(gaps) - min(gaps) <= 2
    assert max(widths) - min(widths) <= 1
    card.deleteLater()
    qapp.processEvents()


def test_brake_and_stop_use_red_safety_surfaces(
    qapp: QApplication,
) -> None:
    qapp.setStyleSheet(get_qss())
    card = MotorCard()
    card.set_enabled(True)
    card.setFixedSize(650, 410)
    card.show()
    qapp.processEvents()

    for key in ("BRAKE", "STOP"):
        button = card.buttons[key]
        image = button.grab().toImage()
        side = min(button.width(), button.height()) - 8
        left = (button.width() - side) // 2
        top = (button.height() - side) // 2
        surface = image.pixelColor(left + 12, top + 12)
        assert surface.red() >= surface.green() + 10
        assert surface.red() >= surface.blue() + 8

    card.deleteLater()
    qapp.processEvents()


def test_inactive_motor_button_has_subtle_vertical_material_gradient(
    qapp: QApplication,
) -> None:
    qapp.setStyleSheet(get_qss())
    card = MotorCard()
    card.set_enabled(True)
    card.setFixedSize(650, 410)
    card.show()
    qapp.processEvents()
    button = card.buttons["REV"]
    image = button.grab().toImage()
    side = min(button.width(), button.height()) - 8
    left = (button.width() - side) // 2
    top = (button.height() - side) // 2
    upper = image.pixelColor(left + 12, top + 12)
    lower = image.pixelColor(left + 12, top + side - 12)

    assert abs(upper.lightness() - lower.lightness()) >= 3
    card.deleteLater()
    qapp.processEvents()


def test_secondary_pages_use_shared_control_roles(
    qapp: QApplication,
) -> None:
    passthrough = PassthroughPanel()
    plot_tab = PlotTab(DataBuffer())

    assert {
        control.objectName()
        for control in (
            passthrough.btn_uart2,
            passthrough.btn_uart3,
            passthrough.btn_both,
            passthrough.btn_off,
        )
    } == {"modeChip"}
    assert passthrough.send_btn.objectName() == "primary"
    assert passthrough.clear_tx_btn.objectName() == "secondaryAction"
    assert passthrough.clear_rx_btn.objectName() == "secondaryAction"
    assert plot_tab.toolbar_panel.objectName() == "toolbarPanel"
    assert plot_tab.clear_btn.objectName() == "secondaryAction"
    assert {
        control.objectName()
        for control in plot_tab.plot_widget._channel_checks.values()
    } == {"channelChip"}

    passthrough.deleteLater()
    plot_tab.deleteLater()
    qapp.processEvents()


def test_passthrough_uses_three_standalone_cards(
    qapp: QApplication,
) -> None:
    panel = PassthroughPanel()

    assert panel.objectName() == "passthroughLayout"
    assert panel.bridge_panel.objectName() == "card"
    assert panel.tx_panel.objectName() == "card"
    assert panel.rx_panel.objectName() == "card"
    assert panel.layout().contentsMargins().left() == 0

    panel.deleteLater()
    qapp.processEvents()


def test_elevated_card_palette_is_not_near_black() -> None:
    assert QColor(theme.BG_CARD).value() >= 48


def test_theme_palette_switches_between_dark_and_light() -> None:
    try:
        theme.set_color_scheme("dark")
        dark_card = QColor(theme.BG_CARD)
        dark_text = QColor(theme.FG_PRIMARY)

        theme.set_color_scheme("light")
        light_card = QColor(theme.BG_CARD)
        light_text = QColor(theme.FG_PRIMARY)

        assert theme.color_scheme() == "light"
        assert light_card.lightness() > dark_card.lightness() + 100
        assert light_text.lightness() < dark_text.lightness() - 100
    finally:
        theme.set_color_scheme("dark")


def test_motor_mode_has_glow_and_buttons_use_translucent_surfaces(
    qapp: QApplication,
) -> None:
    card = MotorCard()
    card.update_state("FWD", 1200, 0, 0)
    effect = card.mode_badge.value_glow

    assert effect.isEnabled()
    assert effect.blurRadius() >= 10
    assert card.buttons["REV"].inactive_surface_alpha < 255
    assert card.buttons["FWD"].active_surface_alpha < 255
    card.deleteLater()
    qapp.processEvents()


def test_motor_mode_badge_fill_follows_active_mode(
    qapp: QApplication,
) -> None:
    card = MotorCard()
    card.setFixedSize(650, 410)
    card.show()
    qapp.processEvents()
    samples = {}
    for mode in ("FWD", "WAKE", "BRAKE"):
        card.update_state(mode, 0, 0, 0)
        qapp.processEvents()
        image = card.mode_badge.grab().toImage()
        samples[mode] = image.pixelColor(18, 18)

    assert samples["FWD"].green() > samples["FWD"].red()
    assert samples["WAKE"].red() > samples["WAKE"].blue()
    assert samples["BRAKE"].red() > samples["BRAKE"].green()
    assert len({color.name() for color in samples.values()}) == 3


def test_motor_and_charge_upper_regions_use_card_background(
    qapp: QApplication,
) -> None:
    motor = MotorCard()
    charge = ChargeModeCard()
    motor.show()
    charge.show()
    qapp.processEvents()

    expected = QColor(theme.BG_CARD)
    assert motor.upper_region.grab().toImage().pixelColor(4, 4).name() == expected.name()
    assert charge.upper_region.grab().toImage().pixelColor(4, 4).name() == expected.name()

    motor.deleteLater()
    charge.deleteLater()
    qapp.processEvents()


def test_card_upper_regions_follow_light_theme_background(
    qapp: QApplication,
) -> None:
    motor = MotorCard()
    charge = ChargeModeCard()
    motor.show()
    charge.show()
    theme.set_color_scheme("light")
    motor.refresh_theme()
    charge.refresh_theme()
    qapp.processEvents()

    expected = QColor(theme.BG_CARD)
    assert motor.upper_region.grab().toImage().pixelColor(4, 4).name() == expected.name()
    assert charge.upper_region.grab().toImage().pixelColor(4, 4).name() == expected.name()

    theme.set_color_scheme("dark")
    motor.deleteLater()
    charge.deleteLater()
    qapp.processEvents()


def test_motor_buttons_keep_stable_firmware_order(
    qapp: QApplication,
) -> None:
    card = MotorCard()

    assert card.button_order == (
        "SLEEP",
        "WAKE",
        "FWD",
        "REV",
        "BRAKE",
        "STOP",
    )
    assert card.buttons["SLEEP"].surface_group == "idle"
    assert card.buttons["FWD"].surface_group == "motion"
    assert card.buttons["BRAKE"].surface_group == "safety"
    assert type(card.buttons["SLEEP"]).RENDER_SCALE >= 3
    card.deleteLater()
    qapp.processEvents()


def test_toggle_switch_uses_supersampled_vector_rendering() -> None:
    assert ToggleSwitch.RENDER_SCALE >= 4
    assert ToggleSwitch.KNOB_SIZE < ToggleSwitch.TRACK_HEIGHT


def test_toggle_switch_uses_balanced_dashboard_geometry() -> None:
    toggle = ToggleSwitch()

    assert toggle.size() == QSize(60, 36)
    assert toggle.TRACK_WIDTH == 60
    assert toggle.TRACK_HEIGHT == 36
    assert toggle.KNOB_SIZE == 28
    assert toggle.KNOB_GAP == 4
    assert toggle.TRACK_WIDTH / toggle.TRACK_HEIGHT == pytest.approx(
        1.667,
        abs=0.001,
    )


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("on", [False, True])
def test_toggle_switch_knob_is_opaque_white(
    qapp: QApplication,
    scheme: str,
    on: bool,
) -> None:
    try:
        theme.set_color_scheme(scheme)
        toggle = ToggleSwitch(initial=on)
        toggle.show()
        qapp.processEvents()

        knob_center_x = round(toggle._knob_x + toggle.KNOB_SIZE / 2)
        knob_center_y = toggle.height() // 2
        pixel = toggle.grab().toImage().pixelColor(
            knob_center_x,
            knob_center_y,
        )

        assert pixel.alpha() == 255
        assert pixel.red() >= 245
        assert pixel.green() >= 245
        assert pixel.blue() >= 245
        toggle.deleteLater()
        qapp.processEvents()
    finally:
        theme.set_color_scheme("dark")


def test_toggle_switch_uses_a_flat_theme_track(qapp: QApplication) -> None:
    toggle = ToggleSwitch()
    toggle.set_on(True, animate=False)
    toggle.show()
    qapp.processEvents()

    image = toggle.grab().toImage()
    sample_x = toggle.KNOB_GAP + toggle.KNOB_SIZE // 2
    track_top = (toggle.height() - toggle.TRACK_HEIGHT) // 2
    upper = image.pixelColor(sample_x, track_top + 9)
    lower = image.pixelColor(
        sample_x,
        track_top + toggle.TRACK_HEIGHT - 10,
    )

    assert abs(upper.red() - lower.red()) <= 2
    assert abs(upper.green() - lower.green()) <= 2
    assert abs(upper.blue() - lower.blue()) <= 2
    assert QColor(theme.ACCENT).hue() == upper.hue()
    toggle.deleteLater()
    qapp.processEvents()
