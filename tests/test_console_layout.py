from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QSizePolicy

from stem_hub_host.data_buffer import DataBuffer
from stem_hub_host.ui.tab1_console import ConsoleTab
from stem_hub_host.ui.widgets.at_console import AtConsole


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
