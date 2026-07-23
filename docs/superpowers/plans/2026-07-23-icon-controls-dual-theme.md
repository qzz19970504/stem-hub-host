# Icon, Controls, and Dual Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Refine annotated controls and add a complete persistent day/night
appearance switch.

**Architecture:** `theme.py` owns both palettes and switches the active token
set. Application QSS is regenerated after a switch; widgets with inline or
custom painting expose `refresh_theme()`. A custom tab-corner switch invokes
the transition through `MainWindow`.

**Tech Stack:** Python 3.11, PySide6, QPainter, QSettings, pytest.

---

### Task 1: Lock required visual behavior

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `tests/test_output_controls.py`
- Modify: `tests/test_main_window.py`
- Modify: `tests/test_serial_bar.py`

- [ ] Add failing tests for dual palette switching and the tab-corner switch.
- [ ] Add failing tests for supersampled toggles and ALL OFF footer geometry.
- [ ] Add failing tests for serial status/action dot widgets.
- [ ] Add failing tests for MODE glow and translucent MOTOR fills.
- [ ] Run focused tests and confirm failures match missing behavior.

### Task 2: Implement palette switching

**Files:**
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/stylesheet.py`
- Create: `stem_hub_host/ui/widgets/theme_toggle.py`
- Modify: `stem_hub_host/ui/main_window.py`

- [ ] Define complete dark and light palettes.
- [ ] Add cache invalidation and regenerate QSS from the active palette.
- [ ] Add the custom day/night switch to the tab corner.
- [ ] Persist scheme choice with `QSettings`.

### Task 3: Make existing widgets theme-aware

**Files:**
- Modify: `stem_hub_host/ui/widgets/at_console.py`
- Modify: `stem_hub_host/ui/widgets/serial_bar.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`
- Modify: `stem_hub_host/ui/widgets/fault_indicator.py`
- Modify: `stem_hub_host/ui/widgets/plot_widget.py`

- [ ] Add focused `refresh_theme()` hooks.
- [ ] Re-render terminal entries from semantic log records.
- [ ] Refresh plots, labels, dividers, custom painters, and inline styles.
- [ ] Verify switching preserves telemetry and interaction state.

### Task 4: Refine annotated components

**Files:**
- Modify: `stem_hub_host/ui/widgets/battery_card.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`
- Modify: `stem_hub_host/ui/widgets/toggle_switch.py`
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`
- Modify: `stem_hub_host/ui/widgets/serial_bar.py`

- [ ] Redraw battery and thermometer glyphs as clean vector symbols.
- [ ] Add translucent MOTOR fills and MODE glow.
- [ ] Supersample toggle rendering.
- [ ] Move ALL OFF to its own centered footer.
- [ ] Paint serial status and action dots.

### Task 5: Visual and release verification

**Files:**
- Modify: `tools/snap_visual_audit.py`
- Output: `docs/visual_v3/*`

- [ ] Capture night and day screenshots for all pages.
- [ ] Inspect annotated regions at original resolution.
- [ ] Run the full test suite.
- [ ] Rebuild the EXE and perform a fake-mode smoke test.

