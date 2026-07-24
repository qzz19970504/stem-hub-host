from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSizePolicy

from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.ui.tab1_console import ConsoleTab


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def console_tab(qapp: QApplication) -> ConsoleTab:
    tab = ConsoleTab(DataBuffer())
    yield tab
    tab.deleteLater()
    qapp.processEvents()


def test_console_grid_uses_target_column_ratio(console_tab: ConsoleTab) -> None:
    assert console_tab.grid.columnStretch(0) == 100
    assert console_tab.grid.columnStretch(1) == 126
    assert console_tab.grid.columnStretch(2) == 100


def test_console_grid_keeps_two_row_composition(console_tab: ConsoleTab) -> None:
    assert console_tab.grid.rowStretch(0) == 565
    assert console_tab.grid.rowStretch(1) == 435
    assert console_tab.grid.indexOf(console_tab.at_console) >= 0


def test_console_page_contains_only_the_two_by_three_grid(
    console_tab: ConsoleTab,
) -> None:
    assert console_tab.layout().count() == 1
    assert console_tab.layout().itemAt(0).layout() is console_tab.grid


def test_console_cards_do_not_bias_target_column_ratio(
    console_tab: ConsoleTab,
) -> None:
    cards = (
        console_tab.battery_card,
        console_tab.motor_card,
        console_tab.charge_card,
        console_tab.temp_grid,
        console_tab.at_console,
    )

    assert all(
        card.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        for card in cards
    )
