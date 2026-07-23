# Switch, Power-Path Sequence, and Visual Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved 60×36 output switch, acknowledged three-command charge/discharge transitions, centralized visual tokens, deterministic golden screenshots, and a rebuilt compact executable.

**Architecture:** Keep hardware sequencing in `Controller`, visual constants in `theme.py`, and QSS rendering in `stylesheet.py`. Add deterministic capture and comparison utilities under `tools/`, with fast contract tests in pytest and opt-in full golden-image verification for release checks.

**Tech Stack:** Python 3.11, PySide6 6.11.1, NumPy 2.4.6, pytest 9.1.1, PyInstaller 6.21.0

---

### Task 1: Create an isolated implementation workspace

**Files:**
- Use: `.worktrees/visual-system-v6/`
- Test: `tests/`

- [ ] **Step 1: Verify repository and worktree state**

Run:

```powershell
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git check-ignore .worktrees
```

Expected: the main checkout is on `master`, and `.worktrees` is ignored.

- [ ] **Step 2: Create the feature worktree**

Run:

```powershell
git worktree add .worktrees\visual-system-v6 -b ui/visual-system-v6
```

Expected: a linked worktree based on the committed design and plan.

- [ ] **Step 3: Run baseline tests**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests -q
```

Expected: all existing tests pass before implementation.

### Task 2: Implement acknowledged three-command power-path transitions

**Files:**
- Modify: `tests/test_behavior_regressions.py`
- Modify: `stem_hub_host/controller.py`

- [ ] **Step 1: Add failing charge-sequence tests**

Add tests that drive real `Controller`, `SerialWorker`, and `FakeSerialTransport` instances:

```python
def test_charge_mode_resets_target_before_enabling() -> None:
    transport, controller = _open_controller()
    controller.set_charge_mode("charge")
    assert transport.get_written() == b"AT+MP4317=OFF\r\n"
    transport.feed(b"OK\r\n")
    assert transport.get_written().endswith(b"AT+LM51770=OFF\r\n")
    transport.feed(b"OK\r\n")
    assert transport.get_written().endswith(b"AT+LM51770=ON\r\n")


def test_charge_mode_does_not_enable_after_target_reset_fails() -> None:
    transport, controller = _open_controller()
    controller.set_charge_mode("charge")
    transport.feed(b"OK\r\n")
    transport.feed(b"ERROR:OUTPUT_QUEUE\r\n")
    assert b"AT+LM51770=ON\r\n" not in transport.get_written()
```

Use the existing setup style if a helper would obscure ownership or cleanup.

- [ ] **Step 2: Add failing discharge-sequence tests**

Add:

```python
def test_discharge_mode_resets_target_before_enabling() -> None:
    transport, controller = _open_controller()
    controller.set_charge_mode("discharge")
    assert transport.get_written() == b"AT+LM51770=OFF\r\n"
    transport.feed(b"OK\r\n")
    assert transport.get_written().endswith(b"AT+MP4317=OFF\r\n")
    transport.feed(b"OK\r\n")
    assert transport.get_written().endswith(b"AT+MP4317=ON\r\n")
```

Update the rapid-transition expectation to contain both complete three-command sequences.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests\test_behavior_regressions.py -q
```

Expected: failures show that target-path `OFF` commands are missing.

- [ ] **Step 4: Implement the minimal acknowledged sequence**

In `Controller._run_charge_transition`, structure each mode as nested acknowledged operations:

```python
if mode == "charge":
    self._run_output_steps(
        (
            (cmd_set_mp4317(False), "DISCHARGE", False),
            (cmd_set_lm51770(False), "CHARGE", False),
            (cmd_set_lm51770(True), "CHARGE", True),
        ),
        target="CHARGE",
    )
elif mode == "discharge":
    self._run_output_steps(
        (
            (cmd_set_lm51770(False), "CHARGE", False),
            (cmd_set_mp4317(False), "DISCHARGE", False),
            (cmd_set_mp4317(True), "DISCHARGE", True),
        ),
        target="DISCHARGE",
    )
```

The helper must send one command at a time, advance only on `OK`, abort on any failure, and call `_finish_charge_transition()` exactly once.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Task 2 focused command again.

Expected: all behavior regression tests pass.

- [ ] **Step 6: Commit the power-path change**

```powershell
git add stem_hub_host\controller.py tests\test_behavior_regressions.py
git commit -m "fix: reset power path before enabling"
```

### Task 3: Apply the approved Switch geometry and opacity

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/widgets/toggle_switch.py`

- [ ] **Step 1: Add failing Switch contract tests**

Assert:

```python
assert toggle.size() == QSize(60, 36)
assert toggle.TRACK_WIDTH == 60
assert toggle.TRACK_HEIGHT == 36
assert toggle.KNOB_SIZE == 28
assert toggle.KNOB_GAP == 4
assert toggle.TRACK_WIDTH / toggle.TRACK_HEIGHT == pytest.approx(1.667, abs=0.001)
```

Grab both states in both themes and sample the knob center:

```python
pixel = toggle.grab().toImage().pixelColor(knob_center)
assert pixel.alpha() == 255
assert pixel.red() >= 245
assert pixel.green() >= 245
assert pixel.blue() >= 245
```

- [ ] **Step 2: Run the Switch tests and verify RED**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests\test_widget_states.py -k "toggle_switch" -q
```

Expected: old 74×36 geometry and gap assertions fail.

- [ ] **Step 3: Add semantic geometry tokens**

Add to `theme.py`:

```python
SWITCH_WIDTH = 60
SWITCH_HEIGHT = 36
SWITCH_KNOB_SIZE = 28
SWITCH_KNOB_GAP = 4
SWITCH_BORDER_WIDTH = 1.0
SWITCH_FOCUS_WIDTH = 1.5
SWITCH_SHADOW_ALPHA = 52
SWITCH_SHADOW_OFFSET_Y = 1.0
```

Use existing palette tokens for colors; remove obsolete switch gradient tokens if no consumer remains.

- [ ] **Step 4: Update ToggleSwitch**

Bind class geometry to `theme.py`, use a full-size 60×36 track, use a 28 px opaque knob, and preserve mouse, keyboard, hover, focus, disabled and animation behavior.

- [ ] **Step 5: Run Switch tests and verify GREEN**

Run the Task 3 focused command again.

Expected: geometry, opacity and interaction tests pass.

- [ ] **Step 6: Commit the Switch change**

```powershell
git add stem_hub_host\ui\theme.py stem_hub_host\ui\widgets\toggle_switch.py tests\test_widget_states.py
git commit -m "style: adopt balanced output switch geometry"
```

### Task 4: Centralize design tokens and tokenize QSS

**Files:**
- Modify: `tests/test_theme_system.py`
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/style.qss`
- Modify: `stem_hub_host/ui/stylesheet.py`
- Modify: affected files under `stem_hub_host/ui/`

- [ ] **Step 1: Add failing QSS token tests**

Add tests:

```python
def test_source_qss_contains_no_hex_color_literals() -> None:
    source = stylesheet.load_qss_source()
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", source)


def test_all_qss_tokens_resolve() -> None:
    rendered = stylesheet.get_qss()
    assert not re.search(r"\{\{[A-Z0-9_]+\}\}", rendered)


def test_qss_source_tokens_are_declared() -> None:
    source_tokens = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", source))
    assert source_tokens <= set(stylesheet.qss_tokens())
```

- [ ] **Step 2: Run theme tests and verify RED**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests\test_theme_system.py -q
```

Expected: current `style.qss` hardcoded hex colors fail the contract.

- [ ] **Step 3: Define common geometry and effect tokens**

Organize `theme.py` sections for:

- control heights and border widths;
- spacing and radius scales;
- shadow/glow alpha values;
- animation durations;
- Switch geometry;
- theme palette colors.

Replace shared hardcoded control heights, common margins, animation durations, border widths and effect alpha values in touched UI files with the new tokens.

- [ ] **Step 4: Replace QSS colors with named placeholders**

Convert source values such as:

```qss
background: {{BG_CARD}};
color: {{FG_PRIMARY}};
border-color: {{BORDER}};
```

Extend `stylesheet.py` with:

```python
TOKEN_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def qss_tokens() -> dict[str, str]:
    return {
        "BG_CARD": theme.BG_CARD,
        "FG_PRIMARY": theme.FG_PRIMARY,
        # every source token
    }
```

Render with strict lookup and raise a descriptive error for an unknown token.

- [ ] **Step 5: Run theme tests and verify GREEN**

Run the Task 4 focused command.

Expected: no source hex literals, missing tokens or unresolved placeholders.

- [ ] **Step 6: Run UI-focused tests**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests\test_theme_system.py tests\test_widget_states.py tests\test_console_layout.py -q
```

Expected: all pass in dark and light theme coverage.

- [ ] **Step 7: Commit the token migration**

```powershell
git add stem_hub_host\ui tests\test_theme_system.py
git commit -m "refactor: centralize visual design tokens"
```

### Task 5: Build deterministic golden screenshot tooling

**Files:**
- Create: `stem_hub_host/visual_regression.py`
- Create: `tools/update_visual_baselines.py`
- Create: `tools/check_visual_regression.py`
- Create: `tests/test_visual_regression.py`
- Modify: `tools/snap_visual_audit.py`
- Create: `tests/golden/visual/manifest.json`
- Create: `tests/golden/visual/dark/*.png`
- Create: `tests/golden/visual/light/*.png`

- [ ] **Step 1: Add failing image-metric tests**

Create small in-memory `QImage` fixtures and test:

```python
metrics = compare_images(expected, actual, channel_threshold=12)
assert metrics.mean_rgb_abs_diff == pytest.approx(...)
assert metrics.changed_pixel_ratio == pytest.approx(...)
assert metrics.max_channel_diff == ...
```

Also test that mismatched image dimensions return a failed result.

- [ ] **Step 2: Run metric tests and verify RED**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests\test_visual_regression.py -q
```

Expected: import failure because the comparison module does not exist.

- [ ] **Step 3: Implement reusable comparison metrics**

Implement `VisualDiffMetrics` and `compare_images()` using `QImage` normalization plus NumPy arrays. The result must expose:

- `dimensions_match`
- `mean_rgb_abs_diff`
- `changed_pixel_ratio`
- `max_channel_diff`
- `passes(mean_limit=3.0, changed_ratio_limit=0.01)`

- [ ] **Step 4: Make capture inputs deterministic**

Update `snap_visual_audit.py` to:

- force animations to their end state;
- accept explicit output directory and theme;
- use explicit fixed and audit-fullscreen sizes;
- write a capture metadata JSON;
- cover Console, Charts and Passthrough in both view sizes.

Use the existing connected and disconnected console scripts or consolidate their state seeding without duplicating application behavior.

- [ ] **Step 5: Implement explicit baseline update**

`tools/update_visual_baselines.py` must generate dark and light captures into `tests/golden/visual`, calculate SHA-256 and dimensions, and write `manifest.json`. It may overwrite baselines only when the user explicitly runs this command.

- [ ] **Step 6: Implement baseline comparison**

`tools/check_visual_regression.py` must:

- generate current images into an ignored build directory;
- load the manifest;
- compare every required image;
- print one compact row per image;
- exit nonzero if a file is absent, dimensions differ, mean RGB diff exceeds 3, or changed-pixel ratio exceeds 1%.

- [ ] **Step 7: Run metric tests and verify GREEN**

Run the Task 5 focused pytest command.

Expected: all comparison metric tests pass.

- [ ] **Step 8: Generate and verify the baseline**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' tools\update_visual_baselines.py
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' tools\check_visual_regression.py
```

Expected: every required image reports PASS with zero or below-threshold difference.

- [ ] **Step 9: Commit visual regression assets**

```powershell
git add stem_hub_host\visual_regression.py tools tests\test_visual_regression.py tests\golden
git commit -m "test: add deterministic visual regression baselines"
```

### Task 6: Document operation and implementation results

**Files:**
- Modify: `README.md`
- Create: `docs/superpowers/reports/2026-07-23-switch-power-visual-implementation.md`

- [ ] **Step 1: Document developer commands**

Add README commands for:

- running normal tests;
- intentionally updating golden images;
- checking golden images;
- rebuilding with retained `env\release`;
- launching `dist\stem-hub-host.exe --fake`.

- [ ] **Step 2: Write the implementation report**

Record:

- selected Switch geometry;
- final charge/discharge command sequences;
- failure and queue behavior;
- token migration boundary;
- golden screenshot matrix and thresholds;
- final test count;
- EXE size, SHA-256 and startup result.

Do not insert unverified final values; fill them after Task 7 commands run.

### Task 7: Full verification, integration, and release

**Files:**
- Test: `tests/`
- Build: `dist/stem-hub-host.exe`

- [ ] **Step 1: Run static and behavior verification**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m compileall -q stem_hub_host tools
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m pytest tests -q
```

Expected: compile exits 0 and all tests pass.

- [ ] **Step 2: Run complete visual verification**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' tools\check_visual_regression.py
```

Expected: every golden image passes.

- [ ] **Step 3: Inspect repository state**

Run:

```powershell
git diff --check
git status --short
```

Expected: only intentional source, docs, test and golden assets remain.

- [ ] **Step 4: Commit documentation**

```powershell
git add README.md docs\superpowers\reports\2026-07-23-switch-power-visual-implementation.md
git commit -m "docs: record visual system verification workflow"
```

- [ ] **Step 5: Merge the feature branch**

Fast-forward `ui/visual-system-v6` into `master` only after the feature worktree is clean and all verification passes.

- [ ] **Step 6: Verify in the retained release environment**

Run on `master`:

```powershell
& '.\env\release\Scripts\python.exe' -m pytest tests -q
& '.\env\release\Scripts\python.exe' -m PyInstaller --clean --noconfirm stem-hub-host.spec
```

Expected: tests and build both exit 0.

- [ ] **Step 7: Verify packaged startup**

Start `dist\stem-hub-host.exe --fake`, confirm matching packaged processes remain alive for at least 5 seconds, then close only those verification processes.

- [ ] **Step 8: Record release evidence**

Update the implementation report with fresh test count, EXE byte size, MiB size, SHA-256 and startup result. Commit the evidence update.

- [ ] **Step 9: Final completion audit**

Re-read the approved design and verify every explicit requirement against source, test output, visual audit output, documentation and packaged runtime evidence before declaring completion.
