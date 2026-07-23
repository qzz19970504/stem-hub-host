# Window and controls fourth-pass implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard fill a normally resizable window and refine the battery, temperature, motor, and output-control visuals from the user's three annotated references.

**Architecture:** Keep the existing PySide6 widget boundaries and controller signals. Change only window/layout policy and custom widget painting, with theme tokens remaining the source of colors. Lock exact semantics and geometry with focused Qt tests before each production edit.

**Tech Stack:** Python 3.11, PySide6, Qt custom painting, pytest, PyInstaller

---

### Task 1: Resizable edge-to-edge window

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `stem_hub_host/ui/main_window.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/style.qss`

- [ ] **Step 1: Write failing window-policy tests**

```python
def test_window_is_resizable_and_root_fills_client_area(main_window, qapp):
    assert main_window.minimumWidth() == 1280
    assert main_window.maximumWidth() > 1600
    assert main_window.centralWidget() is main_window.root
    assert main_window.root.geometry() == main_window.centralWidget().rect()

def test_fullscreen_restore_returns_to_previous_normal_geometry(main_window, qapp):
    main_window.resize(1420, 800)
    before = main_window.size()
    main_window.toggle_fullscreen()
    main_window.toggle_fullscreen()
    assert main_window.size() == before
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the window is fixed and the root is inset**

Run:

```powershell
python -m pytest tests/test_main_window.py -q
```

Expected: the new policy assertions fail.

- [ ] **Step 3: Replace the aspect-fit surface with an edge-to-edge root**

Use `QFrame` directly as `MainWindow`'s central widget, expose it as
`self.root`, call `resize(1600, 900)`, set a 1280×720 minimum, and remove the
fixed maximum. Save normal geometry before entering fullscreen and restore it
when leaving.

- [ ] **Step 4: Remove the root border and outer-margin tokens**

Set `QFrame#rootContainer` to an unbordered, square-cornered surface and remove
the obsolete outer gutter constants from the active layout path.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_main_window.py -q
```

Expected: all main-window tests pass.

### Task 2: Exact NTC labels and temperature composition

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`

- [ ] **Step 1: Write failing semantic tests**

```python
def test_temperature_tiles_use_hardware_channel_names(qapp):
    grid = TempGridCard()
    assert grid.tile_batt.title_label.text() == "BATTERY"
    assert [grid.tile_ntc1.title_label.text(),
            grid.tile_ntc2.title_label.text(),
            grid.tile_ntc3.title_label.text()] == ["NTC1", "NTC2", "NTC3"]
```

Add a sense update assertion proving `ntc1_c`, `ntc2_c`, and `ntc3_c` populate
the matching tiles.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
python -m pytest tests/test_widget_states.py -k temperature -q
```

Expected: failure because the current labels are ESC, MOTOR 1, and MOTOR 2.

- [ ] **Step 3: Rename the three tiles and refine layout**

Create `tile_ntc1`, `tile_ntc2`, and `tile_ntc3`. Reduce excess left padding,
center the icon more precisely, use a consistent 4px text-column gap, and keep
the value/title left edges aligned.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2 and expect all selected tests to pass.

### Task 3: Battery glyph placement

**Files:**
- Modify: `tests/test_battery_card.py`
- Modify: `stem_hub_host/ui/widgets/battery_card.py`

- [ ] **Step 1: Write a failing placement contract**

Expose normalized glyph placement constants and assert:

```python
assert BatteryRing.BATTERY_ICON_Y_RATIO <= -0.23
assert BatteryRing.BATTERY_ICON_X_RATIO == 0.0
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
python -m pytest tests/test_battery_card.py -q
```

Expected: failure because the placement constants do not yet exist.

- [ ] **Step 3: Use the constants in the painter**

Keep the icon horizontally centered and move its center from `-0.18 × side` to
`-0.24 × side`, placing it in the center of the empty area above the voltage.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2 and expect all battery tests to pass.

### Task 4: Three paired motor-control groups

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`

- [ ] **Step 1: Write failing group and rendering tests**

```python
def test_motor_buttons_are_arranged_as_three_semantic_pairs(qapp):
    card = MotorCard()
    assert card.button_pairs == (
        ("SLEEP", "WAKE"),
        ("FWD", "REV"),
        ("BRAKE", "STOP"),
    )
    assert card.buttons["SLEEP"].surface_group == "idle"
    assert card.buttons["FWD"].surface_group == "motion"
    assert card.buttons["BRAKE"].surface_group == "safety"
```

Also assert `_ModeButton.RENDER_SCALE >= 3` and that inactive alpha is nonzero.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
python -m pytest tests/test_widget_states.py -k motor -q
```

Expected: failure because pair metadata and supersampling are absent.

- [ ] **Step 3: Build pair layouts and tinted inactive surfaces**

Use three nested horizontal pair layouts with 5px internal spacing and 14px
between pairs. Pass a semantic group to each button and derive its inactive
fill/border from slate, cyan, or warm safety tokens. Render buttons at 3× and
smooth-downsample, retaining checked glow and all existing click signals.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2 and expect all selected tests to pass.

### Task 5: Softer output switches

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/toggle_switch.py`
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`

- [ ] **Step 1: Write failing render-contract tests**

```python
def test_output_toggle_uses_inset_four_x_rendering():
    assert ToggleSwitch.RENDER_SCALE >= 4
    assert ToggleSwitch.TRACK_INSET >= 2
    assert ToggleSwitch.KNOB_SIZE < ToggleSwitch.TRACK_HEIGHT
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
python -m pytest tests/test_widget_states.py -k toggle -q
```

Expected: failure on scale, inset, or track constants.

- [ ] **Step 3: Redraw the switch**

Use a 74×36 widget, a 70×32 inset track, translucent gradient fill, outer halo,
inner highlight stroke, and a 28px knob with border and top highlight. Update
the target-position calculation to use the inset geometry.

- [ ] **Step 4: Rebalance toggle-cell spacing**

Reduce label spacing and vertical padding so both switch rows align cleanly
without changing output names or state behavior.

- [ ] **Step 5: Run focused tests**

Run the command from Step 2 and expect all selected tests to pass.

### Task 6: Visual and packaged verification

**Files:**
- Modify: `docs/visual_v4/*.png`
- Rebuild: `dist/stem-hub-host.exe`

- [ ] **Step 1: Run the full suite**

```powershell
python -m pytest tests -q
```

Expected: zero failures.

- [ ] **Step 2: Generate dark and light screenshots**

Create connected and disconnected console screenshots plus charts,
passthrough, and fullscreen audits under `docs/visual_v4`.

- [ ] **Step 3: Inspect every annotated region**

Verify edge-to-edge client fill, native resize policy, centered battery glyph,
NTC1/2/3 labels, three motor pairs, and smooth output switches.

- [ ] **Step 4: Build**

```powershell
python -m PyInstaller --noconfirm --clean stem-hub-host.spec
```

Expected: build exits 0 and produces `dist/stem-hub-host.exe`.

- [ ] **Step 5: Smoke-launch**

Launch `dist/stem-hub-host.exe --fake`, wait three seconds, verify it is still
running, and then stop the test process.
