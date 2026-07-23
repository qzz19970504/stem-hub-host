# Dark Console Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the PySide6 host UI around the `docs/design_dark.png` visual reference at a fixed 1600x900 baseline while preserving every existing serial, motor, plotting, passthrough, and AT-console behavior.

**Architecture:** Keep the existing Controller/SerialWorker/UI signal boundaries. Centralize design constants and font loading, then refit the existing independent widgets into a 1:1.26:1 fixed-height console grid. Use normal Qt controls for input and QPainter only for presentation-heavy controls.

**Tech Stack:** Python 3.11, PySide6 6.8+, QtSerialPort, pyqtgraph, pytest, PyInstaller

**Repository note:** `D:\Codes\STM32\stem-hub-host` has no `.git` directory. Commit steps are intentionally replaced by verification checkpoints.

---

### Task 1: Design Tokens, Battery Policy, and Bundled Fonts

**Files:**
- Create: `stem_hub_host/ui/fonts.py`
- Create: `stem_hub_host/resources/fonts/README.md`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/app.py`
- Modify: `stem-hub-host.spec`
- Test: `tests/test_ui_theme.py`

- [ ] **Step 1: Write failing tests for battery policy and font registration**

```python
from stem_hub_host.ui import theme
from stem_hub_host.ui.fonts import load_application_fonts


def test_battery_ratio_clamps():
    assert theme.battery_ratio(27.0) == 0.0
    assert theme.battery_ratio(28.0) == 0.0
    assert theme.battery_ratio(32.5) == 0.5
    assert theme.battery_ratio(37.0) == 1.0
    assert theme.battery_ratio(40.0) == 1.0


def test_font_loader_returns_named_families(qapp):
    families = load_application_fonts()
    assert families.display
    assert families.mono
    assert families.cjk
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_ui_theme.py -q`

Expected: collection fails because `fonts.py` and `theme.battery_ratio` do not exist.

- [ ] **Step 3: Define tokens and a pure battery mapping**

Add `BATTERY_EMPTY_V = 28.0`, `BATTERY_FULL_V = 37.0`, `BATTERY_WARN_V = 30.0`, `TEMP_WARN_C = 65.0`, `TEMP_DANGER_C = 80.0`, layout sizes, and animation durations to `theme.py`. Implement:

```python
def battery_ratio(volts: float | None) -> float:
    if volts is None:
        return 0.0
    span = BATTERY_FULL_V - BATTERY_EMPTY_V
    return max(0.0, min(1.0, (volts - BATTERY_EMPTY_V) / span))
```

- [ ] **Step 4: Add deterministic font loading**

`fonts.py` must resolve resources through `Path(__file__).resolve().parent.parent / "resources" / "fonts"`, register every `.ttf`/`.otf` with `QFontDatabase.addApplicationFont`, choose bundled families when available, and return fallbacks otherwise:

```python
@dataclass(frozen=True)
class FontFamilies:
    display: str
    mono: str
    cjk: str


def load_application_fonts() -> FontFamilies:
    fonts_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
    for path in sorted(fonts_dir.glob("*")):
        if path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        QFontDatabase.addApplicationFont(str(path))
    available = set(QFontDatabase.families())
    return FontFamilies(
        display="Rajdhani" if "Rajdhani" in available else "Segoe UI",
        mono="JetBrains Mono" if "JetBrains Mono" in available else "Consolas",
        cjk="Noto Sans SC" if "Noto Sans SC" in available else "Microsoft YaHei UI",
    )
```

Call it in `get_app()` immediately after creating QApplication. Include `stem_hub_host/resources/fonts` in the PyInstaller `datas` list.

- [ ] **Step 5: Add open-source font assets**

Bundle `Rajdhani-SemiBold.ttf`, `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Bold.ttf`, and `NotoSansSC-Regular.ttf` with license/source notes in `resources/fonts/README.md`. Verify each file returns a non-negative font ID.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_ui_theme.py -q`

Expected: all tests pass and no missing-family warning is printed.

### Task 2: Fixed Design Canvas and Fullscreen State

**Files:**
- Modify: `stem_hub_host/ui/main_window.py`
- Modify: `stem_hub_host/ui/style.qss`
- Test: `tests/test_main_window.py`

- [ ] **Step 1: Write failing tests for window constraints and fullscreen shortcuts**

```python
def test_default_client_size_is_fixed(main_window):
    assert main_window.minimumSize() == QSize(1600, 900)
    assert main_window.maximumSize() == QSize(1600, 900)


def test_f11_toggles_fullscreen(main_window, qtbot):
    qtbot.keyClick(main_window, Qt.Key_F11)
    assert main_window.isFullScreen()
    qtbot.keyClick(main_window, Qt.Key_Escape)
    assert not main_window.isFullScreen()
    assert main_window.size() == QSize(1600, 900)
```

- [ ] **Step 2: Verify failures**

Run: `python -m pytest tests/test_main_window.py -q`

Expected: size remains 1320x820 and F11 has no effect.

- [ ] **Step 3: Implement the window state transition**

Set `WINDOW_W = 1600`, `WINDOW_H = 900`; implement `toggle_fullscreen()`, `keyPressEvent()`, and a top-bar double-click event filter. Before `showFullScreen()`, relax the maximum size to `QWIDGETSIZE_MAX`; when leaving, call `showNormal()`, restore min/max 1600x900, and resize.

- [ ] **Step 4: Add the outer panel frame**

Give `rootContainer` an inset margin, one-pixel teal border, dark outer background, and a controlled glow without changing the content dimensions.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_main_window.py -q`

Expected: all size and fullscreen tests pass.

### Task 3: Console Grid and Serial Connection Bar

**Files:**
- Modify: `stem_hub_host/ui/tab1_console.py`
- Modify: `stem_hub_host/ui/widgets/serial_bar.py`
- Modify: `stem_hub_host/ui/main_window.py`
- Test: `tests/test_console_layout.py`
- Test: `tests/test_serial_bar.py`

- [ ] **Step 1: Write failing layout and state tests**

```python
def test_console_column_ratios(console_tab):
    assert console_tab.grid.columnStretch(0) == 100
    assert console_tab.grid.columnStretch(1) == 126
    assert console_tab.grid.columnStretch(2) == 100


def test_connection_action_colors(serial_bar):
    serial_bar.set_disconnected()
    assert serial_bar.connect_btn.property("connectionState") == "offline"
    serial_bar.set_handshake_ok("release-v2.1")
    assert serial_bar.connect_btn.property("connectionState") == "connected"
```

- [ ] **Step 2: Verify failures**

Run: `python -m pytest tests/test_console_layout.py tests/test_serial_bar.py -q`

Expected: the grid is equal-width and the connection state property is absent.

- [ ] **Step 3: Refit the 2x3 grid**

Expose `self.grid`, set stretches `100/126/100`, use fixed top/bottom design heights, and retain the existing placements: Battery, Motor, Outputs on row 0; Temp on row 1 column 0; AT console spans columns 1-2.

- [ ] **Step 4: Rebuild SerialBar state semantics**

Replace the visible Refresh text button with automatic refresh in `_ChevronCombo.showPopup()`. Add a status pill. Set dynamic properties instead of testing button text:

```python
def _set_connection_state(self, state: str, label: str) -> None:
    self.connect_btn.setProperty("connectionState", state)
    self.status_badge.setProperty("connectionState", state)
    self.status_badge.setText(label)
    self.style().unpolish(self.connect_btn)
    self.style().polish(self.connect_btn)
```

QSS must make offline `CONNECT` green and connected/opening `DISCONNECT` red.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_console_layout.py tests/test_serial_bar.py -q`

Expected: all tests pass.

### Task 4: Animated Battery Ring

**Files:**
- Modify: `stem_hub_host/ui/widgets/battery_card.py`
- Test: `tests/test_battery_card.py`

- [ ] **Step 1: Write failing animation-state tests**

```python
def test_set_value_animates_from_previous_ratio(qtbot, battery_ring):
    battery_ring.set_value(28.0, animate=False)
    battery_ring.set_value(37.0)
    assert battery_ring.ratio == 0.0
    assert battery_ring._ratio_anim.endValue() == 1.0


def test_missing_value_stops_emphasis(battery_ring):
    battery_ring.set_value(None)
    assert battery_ring.value is None
    assert battery_ring.ratio == 0.0
```

- [ ] **Step 2: Verify the existing interpolation bug**

Run: `python -m pytest tests/test_battery_card.py -q`

Expected: the first test fails because current code assigns the target before setting the animation start value.

- [ ] **Step 3: Implement state-driven animation**

Use `theme.battery_ratio`; capture `start = self._ratio` before changing the target; use `QEasingCurve.OutCubic`; remove the perpetual rotating scan; animate only the ratio and a subtle opacity pulse while data is valid.

- [ ] **Step 4: Refine painting against the target**

Keep the horizontal battery glyph, thicken the background rail, draw multi-pass progress glow inside the card bounds, center voltage and unit as one measured composition, and make color thresholds use theme constants.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_battery_card.py -q`

Expected: all tests pass.

### Task 5: Real Output Controls and Derived Faults

**Files:**
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`
- Modify: `stem_hub_host/ui/main_window.py`
- Modify: `stem_hub_host/ui/widgets/fault_indicator.py`
- Test: `tests/test_output_controls.py`

- [ ] **Step 1: Write failing mapping and safety tests**

```python
def test_charge_and_discharge_are_mutually_exclusive(window, mocker):
    set_lm = mocker.patch.object(window._controller, "set_lm51770")
    set_mp = mocker.patch.object(window._controller, "set_mp4317")
    window._on_toggle_changed("CHARGE", True)
    assert set_mp.call_args_list[-1].args == (False,)
    assert set_lm.call_args_list[-1].args == (True,)


def test_all_off_closes_every_output(window, mocker):
    calls = []
    mocker.patch.object(window._controller, "set_lm51770", side_effect=lambda on: calls.append(("lm", on)))
    mocker.patch.object(window._controller, "set_mp4317", side_effect=lambda on: calls.append(("mp", on)))
    mocker.patch.object(window._controller, "set_nmos", side_effect=lambda idx, on: calls.append((f"n{idx}", on)))
    mocker.patch.object(window._controller, "set_led", side_effect=lambda on: calls.append(("led", on)))
    window._on_all_outputs_off()
    assert calls == [("lm", False), ("mp", False), ("n1", False), ("n2", False), ("led", False)]
```

- [ ] **Step 2: Verify failures**

Run: `python -m pytest tests/test_output_controls.py -q`

Expected: `ALL OFF` does not exist and the old card still exposes BALANCING.

- [ ] **Step 3: Replace the six cells**

Expose five ToggleSwitch cells named CHARGE, DISCHARGE, NMOS1, NMOS2, LIGHTS plus an `all_off_clicked` action button. Remove BALANCING and duplicate fault widget insertion.

- [ ] **Step 4: Map actions to real commands**

Make CHARGE and DISCHARGE mutually exclusive and map them directly to LM51770 and MP4317. Add `_on_all_outputs_off()` with deterministic safe-off ordering and clear UI toggles without emitting new signals.

- [ ] **Step 5: Derive honest fault states**

During `_refresh_ui_from_state`, derive overtemperature from parsed valid temperatures, undervoltage from `theme.BATTERY_WARN_V`, and overcurrent from MotorState. Keep DRV/AUX from FaultState. Display only these five indicators.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_output_controls.py -q`

Expected: all tests pass.

### Task 6: Motor, Temperature, Terminal, and Shared QSS Polish

**Files:**
- Modify: `stem_hub_host/ui/widgets/motor_card.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`
- Modify: `stem_hub_host/ui/widgets/at_console.py`
- Modify: `stem_hub_host/ui/widgets/toggle_switch.py`
- Modify: `stem_hub_host/ui/style.qss`
- Test: `tests/test_widget_states.py`

- [ ] **Step 1: Write failing state tests**

```python
def test_motor_buttons_follow_confirmed_mode(motor_card):
    motor_card.update_state("REV", 1200, 0, 0)
    assert motor_card.buttons["REV"].isChecked()
    assert sum(button.isChecked() for button in motor_card.buttons.values()) == 1


def test_terminal_log_uses_no_timestamp(at_console):
    at_console.append_log("RX", "OK")
    assert "OK" in at_console.log_view.toPlainText()
    assert not re.search(r"\d{2}:\d{2}:\d{2}", at_console.log_view.toPlainText())
```

- [ ] **Step 2: Verify current differences**

Run: `python -m pytest tests/test_widget_states.py -q`

Expected: terminal timestamp assertion fails; public button mapping may be absent.

- [ ] **Step 3: Simplify and align widgets**

Expose a stable motor button mapping, remove the non-functional current diamond, tune icon geometry, make temperature tiles share baselines, and remove AT log timestamps while retaining TX/RX/INFO/ERR semantics.

- [ ] **Step 4: Consolidate component states in QSS**

Implement default, hover, pressed, focus, checked, and disabled states through object names and dynamic properties. Ensure no control changes size between states.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_widget_states.py -q`

Expected: all tests pass.

### Task 7: Visual Harness and Screenshot Iteration

**Files:**
- Modify: `tools/snap_tab1.py`
- Modify: `tools/snap_tab1_disconnected.py`
- Create: `tools/compare_design.py`
- Output: `docs/iteration_connected.png`
- Output: `docs/iteration_disconnected.png`

- [ ] **Step 1: Make screenshot state deterministic**

Set a fixed Fusion style, fixed 1600x900 client size, known fake firmware values, known control states, and wait for font loading and animation settlement before `grab()`.

- [ ] **Step 2: Capture connected and disconnected states**

Run:

```powershell
python tools/snap_tab1.py docs/iteration_connected.png
python tools/snap_tab1_disconnected.py docs/iteration_disconnected.png
```

Expected: both PNG files are 1600x900 and contain nonblank UI pixels.

- [ ] **Step 3: Add a reproducible comparison image**

`compare_design.py` must resize `docs/design_dark.png` to 1600x900, place it beside the generated screenshot, and write an optional 50% alpha overlay using Pillow when installed. It must print image dimensions and mean absolute RGB difference.

- [ ] **Step 4: Inspect and iterate**

Check the connected screenshot for the 1:1.26:1 grid, target card heights, font rendering, voltage composition, toggle alignment, motor button spacing, and terminal baseline. Adjust tokens rather than one-off local values.

- [ ] **Step 5: Capture all tabs and fullscreen**

Use the existing tab screenshot utilities to capture Charts and Passthrough at 1600x900, then exercise F11 and capture a fullscreen frame. Confirm no clipping, overlap, or blank canvas.

### Task 8: Regression, Packaging, and Completion Audit

**Files:**
- Modify: only the exact source or test file named by a failing assertion from Tasks 1-7
- Verify: `stem-hub-host.spec`

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest tests -q`

Expected: all protocol, serial worker, UI policy, mapping, and state tests pass.

- [ ] **Step 2: Run fake-firmware smoke test**

Run: `python -m stem_hub_host.main --fake`

Expected: app opens, handshake enables controls, switching tabs remains responsive, and closing exits without worker errors.

- [ ] **Step 3: Build the executable**

Run: `pyinstaller --noconfirm stem-hub-host.spec`

Expected: `dist/stem-hub-host.exe` builds with QSS and bundled fonts included.

- [ ] **Step 4: Validate packaged font rendering**

Launch the executable in fake mode or with the screenshot harness. Confirm English labels, numeric values, and a Chinese error string render as glyphs rather than boxes.

- [ ] **Step 5: Audit every design requirement**

Verify fixed/default and fullscreen behavior, 2x3 proportions, button positions, five real toggles plus ALL OFF, derived faults, animated battery state, connection action colors, all three functional tabs, and screenshot fidelity against `docs/design_dark.png`.
