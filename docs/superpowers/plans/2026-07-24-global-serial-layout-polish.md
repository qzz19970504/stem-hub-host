# Global Serial Header and Three-Page Layout Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the temperature gauge, promote serial connection controls to a persistent global header, expose three standalone passthrough cards, and normalize chart-toolbar typography.

**Architecture:** `MainWindow` owns the single `SerialBar` and positions it beside the theme toggle inside the tab header. Existing page widgets retain their functional APIs while layout roles are narrowed: `ConsoleTab` owns only the 2×3 console grid, and `PassthroughPanel` becomes a transparent container for three independently styled cards.

**Tech Stack:** Python 3.11, PySide6 widgets/QPainter, pytest-qt, deterministic visual regression, PyInstaller.

---

### Task 1: Temperature column rendering

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`

- [ ] Add failing rendered-color tests proving 25°C and 72°C produce different single-band columns while `level == celsius / 100`.
- [ ] Run the focused tests and confirm the old spectrum rendering fails.
- [ ] Replace the active spectrum with a two-stop gradient derived from `theme.temp_color(celsius)` and remove the cap-line drawing.
- [ ] Run the focused temperature tests and confirm they pass.

### Task 2: Persistent global serial header

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `tests/test_console_layout.py`
- Modify: `stem_hub_host/ui/main_window.py`
- Modify: `stem_hub_host/ui/tab1_console.py`
- Modify: `stem_hub_host/ui/widgets/serial_bar.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/style.qss`
- Modify: `stem_hub_host/visual_audit.py`

- [ ] Add failing tests asserting `MainWindow.serial_bar` is a visible child of the tab header, persists across all page selections, and is the same compatibility instance exposed by `console_tab.serial_bar`.
- [ ] Add failing geometry tests asserting the console grid starts at the page top and the serial badge/button share size and font.
- [ ] Run the focused tests and confirm the old page-local layout fails.
- [ ] Move `SerialBar` construction and signal wiring to `MainWindow`; remove its layout row from `ConsoleTab`.
- [ ] Add one header-positioning method that lays out the serial bar and theme toggle on resize without overlapping the tab menu.
- [ ] Normalize serial dimensions/font tokens and increase the badge text inset relative to the painted dot.
- [ ] Update visual-audit references to the canonical global bar and run focused tests.

### Task 3: Three standalone passthrough cards

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/passthrough_panel.py`
- Modify: `stem_hub_host/ui/style.qss`

- [ ] Add failing tests asserting the root panel has a transparent layout role while bridge, transmit, and receive panels each use the standalone card role.
- [ ] Run the focused test and confirm the old outer `card` role fails.
- [ ] Change only the visual object roles and root margins; retain all signal and data behavior.
- [ ] Run passthrough widget/behavior tests.

### Task 4: Chart toolbar typography and baseline

**Files:**
- Modify: `tests/test_sampling_rate.py`
- Modify: `stem_hub_host/ui/tab2_plot.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/style.qss`

- [ ] Add failing tests asserting named sample-rate label, fixed control heights, display-font label/button, and mono-font numeric control.
- [ ] Run the focused tests and confirm the unlabeled/default-font widgets fail.
- [ ] Assign explicit object names, fonts, dimensions, and vertical alignment using theme tokens.
- [ ] Re-run sampling and window tests.

### Task 5: Visual acceptance and release

**Files:**
- Update: `tests/golden/visual/**`
- Create: `docs/iteration_global_header_*.png`
- Create: `docs/superpowers/reports/2026-07-24-global-serial-layout-polish-implementation.md`
- Update: `dist/stem-hub-host.exe`

- [ ] Run full pytest and compile checks.
- [ ] Capture the old-baseline diff and verify changes are confined to intended pages/regions.
- [ ] Inspect dark/light fixed and fullscreen console, chart, and passthrough screenshots.
- [ ] Update all intentional golden images and confirm 16/16 visual regression.
- [ ] Rebuild with retained `env\release` and verify `--fake` remains running after five seconds.
- [ ] Record requirement-by-requirement evidence in the implementation report.
