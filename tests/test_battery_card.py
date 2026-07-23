from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from stem_hub_host.ui.widgets.battery_card import BatteryRing


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def battery_ring(qapp: QApplication) -> BatteryRing:
    ring = BatteryRing()
    yield ring
    ring.deleteLater()
    qapp.processEvents()


def test_set_value_animates_from_previous_ratio(battery_ring: BatteryRing) -> None:
    battery_ring.set_value(28.0, animate=False)
    battery_ring.set_value(37.0)

    assert battery_ring.ratio == 0.0
    assert battery_ring._ratio_anim.startValue() == 0.0
    assert battery_ring._ratio_anim.endValue() == 1.0
    assert battery_ring._ratio_anim.state() == QAbstractAnimation.State.Running


def test_repeated_value_does_not_restart_animation(battery_ring: BatteryRing) -> None:
    battery_ring.set_value(28.0, animate=False)
    battery_ring.set_value(37.0)
    QTest.qWait(50)
    elapsed_before_repeat = battery_ring._ratio_anim.currentTime()

    battery_ring.set_value(37.0)

    assert battery_ring._ratio_anim.currentTime() >= elapsed_before_repeat


def test_missing_value_clears_ratio_without_animation(battery_ring: BatteryRing) -> None:
    battery_ring.set_value(37.0, animate=False)

    battery_ring.set_value(None)

    assert battery_ring.value is None
    assert battery_ring.ratio == 0.0
    assert battery_ring._ratio_anim.state() == QAbstractAnimation.State.Stopped


def test_non_animated_update_snaps_an_identical_in_flight_target(
    battery_ring: BatteryRing,
) -> None:
    battery_ring.set_value(37.0)
    battery_ring.set_value(37.0, animate=False)

    assert battery_ring.ratio == 1.0
    assert battery_ring._ratio_anim.state() == QAbstractAnimation.State.Stopped


def test_battery_glyph_is_centered_in_the_space_above_voltage() -> None:
    assert BatteryRing.BATTERY_ICON_X_RATIO == 0.0
    assert BatteryRing.BATTERY_ICON_Y_RATIO <= -0.23
