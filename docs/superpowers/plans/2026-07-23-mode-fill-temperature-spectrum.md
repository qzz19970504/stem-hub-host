# Motor Mode Fill and Temperature Spectrum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the motor mode banner fill follow the selected mode and replace the temperature gauge with a theme-aware, animated 0–100°C multi-color spectrum.

**Architecture:** Keep semantic colors in `ui/theme.py`, rendering in the two existing widgets, and behavioral/image assertions in `tests/test_widget_states.py`. The motor badge receives a mode-specific pair of blended surface colors; the temperature gauge draws a faint full-range spectrum and a clipped stronger spectrum, while `TempTile` applies the current band color to the numeric label.

**Tech Stack:** Python 3.12, PySide6/Qt painting and property animation, pytest-qt, PyInstaller, deterministic screenshot regression.

---

## File map

- Modify `stem_hub_host/ui/theme.py`: define theme-switching temperature palette tokens, band stops, color interpolation helpers, and mode surface blending.
- Modify `stem_hub_host/ui/widgets/motor_card.py`: feed the selected mode color into both banner fill stops.
- Modify `stem_hub_host/ui/widgets/temp_grid.py`: set the fixed 0–100 scale, replace the bubble with a cap line, paint a multi-stop spectrum, and color the value label.
- Modify `tests/test_widget_states.py`: cover range mapping, theme-aware bands, motor surface pixels, and temperature rendering.
- Modify `stem_hub_host/visual_audit.py` if needed: seed representative temperatures across the four tiles so the screenshot matrix proves the multi-color requirement.
- Update `tests/golden/visual/**` and `tests/golden/visual/manifest.json`: accept the intentional visual change only after manual inspection.
- Create or update `docs/iteration_*.png`: retain fresh review screenshots.

### Task 1: Lock the theme color contract

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/theme.py`

- [ ] **Step 1: Write failing temperature-palette tests**

Add tests that switch themes in a `try/finally` block and assert five representative values produce distinct status colors:

```python
def test_temperature_palette_has_five_theme_aware_bands() -> None:
    try:
        theme.set_color_scheme("dark")
        dark = [
            QColor(theme.temp_color(value))
            for value in (10.0, 35.0, 57.0, 72.0, 90.0)
        ]
        assert len({color.name() for color in dark}) == 5

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
```

Also assert `None` continues to return `FG_TERTIARY`.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests/test_widget_states.py -k "temperature_palette" -q
```

Expected: failure because the old function has only four bands and static colors that do not switch with the theme.

- [ ] **Step 3: Add palette tokens and band selection**

Add `TEMP_COLD`, `TEMP_NORMAL`, `TEMP_WARM`, `TEMP_WARNING`, and `TEMP_DANGER` to both `_DARK_PALETTE` and `_LIGHT_PALETTE`. Implement `temperature_stops()` and update `temp_color()`:

```python
TEMP_COOL_C = 20.0
TEMP_NORMAL_MAX_C = 50.0
TEMP_WARN_C = 65.0
TEMP_DANGER_C = 80.0

def temperature_stops() -> tuple[tuple[float, str], ...]:
    return (
        (0.0, TEMP_COLD),
        (0.20, TEMP_COLD),
        (0.50, TEMP_NORMAL),
        (0.65, TEMP_WARM),
        (0.80, TEMP_WARNING),
        (1.0, TEMP_DANGER),
    )

def temp_color(celsius: float | None) -> str:
    if celsius is None:
        return FG_TERTIARY
    if celsius < TEMP_COOL_C:
        return TEMP_COLD
    if celsius < TEMP_NORMAL_MAX_C:
        return TEMP_NORMAL
    if celsius < TEMP_WARN_C:
        return TEMP_WARM
    if celsius < TEMP_DANGER_C:
        return TEMP_WARNING
    return TEMP_DANGER
```

Choose lower-luminance variants in the dark palette and sufficiently dark variants in the light palette. Do not leave temperature constants outside the switchable palettes.

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run the same focused command. Expected: all selected tests pass.

### Task 2: Make the mode banner fill mode-specific

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`

- [ ] **Step 1: Write a failing rendered-pixel test**

Render the same `MotorCard` successively in `FWD`, `WAKE`, and `BRAKE`. Sample an interior pixel away from labels and borders and assert its dominant color changes with mode:

```python
def test_motor_mode_badge_fill_follows_active_mode(
    qapp: QApplication,
) -> None:
    card = MotorCard()
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
```

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests/test_widget_states.py::test_motor_mode_badge_fill_follows_active_mode -q
```

Expected: failure because the old active surface always starts with `BG_ACCENT_SOFT`.

- [ ] **Step 3: Implement theme-owned blended surfaces**

Add a small theme helper that blends a semantic color into the current elevated/card background without hardcoding widget colors:

```python
def blend_hex(background: str, foreground: str, alpha: float) -> str:
    bg = QColor(background)
    fg = QColor(foreground)
    alpha = max(0.0, min(1.0, alpha))
    return QColor(
        round(bg.red() * (1 - alpha) + fg.red() * alpha),
        round(bg.green() * (1 - alpha) + fg.green() * alpha),
        round(bg.blue() * (1 - alpha) + fg.blue() * alpha),
    ).name()

def mode_surface(color: str) -> tuple[str, str]:
    strength = 0.24 if color_scheme() == "dark" else 0.14
    return (
        blend_hex(BG_ELEVATED, color, strength),
        blend_hex(BG_CARD, color, strength * 0.55),
    )
```

Change `_ModeBadge._apply_surface` to accept the semantic color and use `theme.mode_surface(border)` when active. Keep the existing neutral gradient when inactive.

- [ ] **Step 4: Run the focused mode tests and confirm GREEN**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests/test_widget_states.py -k "motor_mode or brake_and_stop" -q
```

Expected: all selected tests pass.

### Task 3: Fix the range and replace the thermometer drawing

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/widgets/temp_grid.py`

- [ ] **Step 1: Replace the old range assertion with failing boundary tests**

Change the existing gauge test so it explicitly covers the fixed scale:

```python
for value, expected in (
    (-2.0, 0.0),
    (0.0, 0.0),
    (40.0, 0.4),
    (100.0, 1.0),
    (125.0, 1.0),
):
    grid.tile_batt.set_value(value, animate=False)
    assert grid.tile_batt.gauge.level == pytest.approx(expected)
```

- [ ] **Step 2: Run the range test and confirm RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests/test_widget_states.py::test_temperature_tiles_use_animated_thermal_gauges -q
```

Expected: `40°C` is about `0.5` under the old `-20–100°C` mapping, so the test fails.

- [ ] **Step 3: Implement fixed range and spectrum painter**

Set:

```python
MIN_CELSIUS = 0.0
MAX_CELSIUS = 100.0
```

Build a vertical `QLinearGradient` from `theme.temperature_stops()`. Paint it once with low alpha across the inner track, then paint the same gradient at stronger alpha clipped to the animated fill rectangle. Remove the `drawEllipse(...)` block and replace it with a short rounded cap line:

```python
cap_pen = QPen(QColor(self._color), 1.6)
cap_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
painter.setPen(cap_pen)
painter.drawLine(
    QPointF(inner.left() + 1, fill_rect.top()),
    QPointF(inner.right() - 1, fill_rect.top()),
)
```

Use the full `inner` coordinates when constructing both gradients so colors stay tied to absolute `0–100°C`, rather than stretching the entire rainbow into every current fill height.

- [ ] **Step 4: Color the numeric value by the current band**

In `TempTile.set_value`, use `theme.temp_color(celsius)` for valid readings and retain `FG_TERTIARY` for missing readings. Keep the exact numeric text and title styling unchanged.

- [ ] **Step 5: Run widget tests and confirm GREEN**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests/test_widget_states.py -q
```

Expected: all widget tests pass.

### Task 4: Make visual fixtures exercise every temperature state

**Files:**
- Modify: `stem_hub_host/visual_audit.py`
- Test: `tests/test_widget_states.py`

- [ ] **Step 1: Inspect the existing seeded telemetry**

Confirm whether the four console tiles currently receive distinct temperatures. If not, add a test around the existing audit seed helper or the rendered matrix ensuring at least three bands are represented.

- [ ] **Step 2: Run the new fixture test and confirm RED**

Run the narrow test selected in Step 1. Expected: failure if all tiles are currently near room temperature.

- [ ] **Step 3: Seed representative values**

Use stable values such as `12.0`, `36.0`, `58.0`, and `84.0°C` only in deterministic visual-audit fixtures. Do not change fake firmware behavior or production defaults.

- [ ] **Step 4: Run the fixture test and confirm GREEN**

Re-run the narrow test. Expected: pass.

### Task 5: Verify and accept the visual change

**Files:**
- Update: `tests/golden/visual/**`
- Update: `tests/golden/visual/manifest.json`
- Create/update: `docs/iteration_*.png`

- [ ] **Step 1: Run all automated tests**

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests -q
```

Expected: zero failures.

- [ ] **Step 2: Capture the visual matrix without updating baselines**

```powershell
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: console captures fail against the old baseline because the change is intentional; unrelated pages must not show material differences.

- [ ] **Step 3: Generate and manually inspect review screenshots**

Run the established console and visual-audit capture scripts. Inspect both themes at fixed size and fullscreen, checking:

- mode fill hue matches the selected mode;
- temperature spectrum is legible but subdued in dark mode;
- no glow bubble remains;
- all four values, ticks, and labels remain aligned;
- no clipping at 0 or 100°C.

- [ ] **Step 4: Explicitly update golden images**

Only after inspection:

```powershell
& 'env\release\Scripts\python.exe' tools\update_visual_baselines.py
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: `visual regression passed: 16 capture(s)`.

- [ ] **Step 5: Run final fresh verification**

```powershell
& 'env\release\Scripts\python.exe' -m compileall -q stem_hub_host
& 'env\release\Scripts\python.exe' -m pytest tests -q
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: compilation exits 0, tests report zero failures, and all 16 captures pass.

### Task 6: Rebuild and smoke-test the retained release environment

**Files:**
- Update: `dist/stem-hub-host.exe`

- [ ] **Step 1: Build with the existing retained environment**

Use the project’s existing PyInstaller spec and `env\release`; do not delete or recreate the environment.

- [ ] **Step 2: Verify package size and launch**

Launch `dist\stem-hub-host.exe --fake`, confirm it remains running for at least five seconds, then close only that test process. Record the final byte size and startup result in a report under `docs/superpowers/reports/`.

- [ ] **Step 3: Re-run the completion checklist**

Map every requirement in `docs/superpowers/specs/2026-07-23-mode-fill-temperature-spectrum-design.md` to fresh test output, inspected screenshots, or source evidence before declaring completion.
