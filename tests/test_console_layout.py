from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.ui import theme
from stem_hub_host.ui.tab1_console import ConsoleTab
from stem_hub_host.ui.widgets.at_console import AtConsole
from stem_hub_host.ui.widgets.charge_mode_card import ChargeModeCard
from stem_hub_host.ui.widgets.motor_card import MotorCard


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


def test_at_console_evicts_entries_older_than_three_minutes(
    qapp: QApplication,
    monkeypatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: now)
    console = AtConsole()
    console.append_log("RX", "old")
    now += 181.0
    console.append_log("RX", "new")

    assert "old" not in console.log_view.toPlainText()
    assert "new" in console.log_view.toPlainText()
    assert len(console._entries) == 1
    console.deleteLater()
    qapp.processEvents()


def test_at_console_caps_entries_and_qt_document_blocks(
    qapp: QApplication,
) -> None:
    console = AtConsole()
    for index in range(console.MAX_LOG_ENTRIES + 20):
        console.append_log("RX", f"line-{index}")

    assert len(console._entries) == console.MAX_LOG_ENTRIES
    assert console.log_view.maximumBlockCount() == console.MAX_DOCUMENT_BLOCKS
    assert (
        console.log_view.document().blockCount()
        <= console.MAX_DOCUMENT_BLOCKS
    )
    console.deleteLater()
    qapp.processEvents()


def test_at_console_context_menu_offers_clear_all(
    qapp: QApplication,
) -> None:
    console = AtConsole()
    menu = console._create_log_context_menu()

    assert "清除全部" in [action.text() for action in menu.actions()]
    menu.deleteLater()
    console.deleteLater()
    qapp.processEvents()


def test_clear_all_only_clears_log_entries(qapp: QApplication) -> None:
    console = AtConsole()
    console.input_edit.setText("AT+SENSE?")
    console.append_log("RX", "OK")
    sent = QSignalSpy(console.send_requested)

    console.clear_log()

    assert console.log_view.toPlainText() == ""
    assert len(console._entries) == 0
    assert console.input_edit.text() == "AT+SENSE?"
    assert sent.count() == 0
    console.deleteLater()
    qapp.processEvents()


def test_motor_and_output_dividers_share_vertical_position(
    qapp: QApplication,
) -> None:
    host = QWidget()
    layout = QHBoxLayout(host)
    motor = MotorCard()
    output = ChargeModeCard()
    layout.addWidget(motor)
    layout.addWidget(output)
    host.resize(1320, 500)
    host.show()
    qapp.processEvents()

    motor_y = motor.divider.mapTo(host, QPoint(0, 0)).y()
    output_y = output.divider.mapTo(host, QPoint(0, 0)).y()

    assert abs(motor_y - output_y) <= 1
    host.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("card_type", [MotorCard, ChargeModeCard])
def test_card_upper_content_is_vertically_centered(
    qapp: QApplication,
    card_type,
) -> None:
    card = card_type()
    card.resize(650, 468)
    card.show()
    qapp.processEvents()
    region_rect = card.upper_region.rect()
    content_rect = card.upper_content.geometry()

    assert abs(content_rect.center().y() - region_rect.center().y()) <= 2
    assert content_rect.top() >= theme.CARD_UPPER_MIN_GAP
    assert (
        region_rect.bottom() - content_rect.bottom()
        >= theme.CARD_UPPER_MIN_GAP
    )
    card.deleteLater()
    qapp.processEvents()
