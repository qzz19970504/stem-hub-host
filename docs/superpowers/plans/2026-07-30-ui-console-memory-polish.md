# UI Console Memory Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the motor/output-card dividers, vertically center their upper control groups, add a log-only “清除全部” context action, and bound received-data memory to three minutes.

**Architecture:** Keep the existing card classes and public signals intact. Introduce shared layout tokens for the upper card region, add bounded timestamped entries inside `AtConsole`, and shorten `DataBuffer`'s rolling window; tests verify geometry, action isolation, time eviction, and hard limits.

**Tech Stack:** Python 3.11, PySide6/Qt Widgets, NumPy, pytest, pytest-qt, PyInstaller.

---

### Task 1: Bound telemetry history to 180 seconds

**Files:**
- Modify: `stem_hub_host/data_buffer.py`
- Modify: `tests/test_sampling_rate.py`

- [ ] **Step 1: Write the failing rolling-window test**

Add a clock injection seam and test deterministic expiry:

```python
def test_data_buffer_keeps_only_latest_three_minutes(monkeypatch) -> None:
    now = 1000.0
    monkeypatch.setattr("stem_hub_host.data_buffer.time.monotonic", lambda: now)
    buffer = DataBuffer()
    buffer.series["batt_v"].append(0.0, 36.0)
    buffer.series["batt_v"].append(179.0, 36.5)
    buffer.series["batt_v"].append(181.0, 37.0)

    buffer.trim_to(181.0)

    assert buffer.WINDOW_SECONDS == 180.0
    assert list(buffer.series["batt_v"].times) == [179.0, 181.0]
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py::test_data_buffer_keeps_only_latest_three_minutes -q
```

Expected: failure because `WINDOW_SECONDS` is still `300.0` and `trim_to` does not exist.

- [ ] **Step 3: Implement the three-minute policy**

In `DataBuffer`, change the constant and centralize trimming:

```python
WINDOW_SECONDS = 180.0
MAX_SAMPLES_PER_CHANNEL = 2000

def trim_to(self, elapsed_seconds: float) -> None:
    cutoff = elapsed_seconds - self.WINDOW_SECONDS
    for series in self.series.values():
        series.trim(cutoff)
```

Construct both channel deques with `maxlen=self.MAX_SAMPLES_PER_CHANNEL` and replace the inline `feed_sense` trim loop with `self.trim_to(t)`.

- [ ] **Step 4: Run focused and related tests**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py tests\test_behavior_regressions.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add stem_hub_host/data_buffer.py tests/test_sampling_rate.py
git commit -m "fix: bound telemetry history to three minutes"
```

### Task 2: Add bounded AT log storage

**Files:**
- Modify: `stem_hub_host/ui/widgets/at_console.py`
- Modify: `tests/test_console_layout.py`

- [ ] **Step 1: Write failing retention and hard-limit tests**

Use a fake monotonic clock and public append calls:

```python
def test_at_console_evicts_entries_older_than_three_minutes(
    qapp: QApplication, monkeypatch
) -> None:
    now = 1000.0
    monkeypatch.setattr("stem_hub_host.ui.widgets.at_console.time.monotonic", lambda: now)
    console = AtConsole()
    console.append_log("RX", "old")
    now += 181.0
    console.append_log("RX", "new")

    assert "old" not in console.log_view.toPlainText()
    assert "new" in console.log_view.toPlainText()
    assert len(console._entries) == 1


def test_at_console_caps_entries_and_qt_document_blocks(qapp: QApplication) -> None:
    console = AtConsole()
    for index in range(console.MAX_LOG_ENTRIES + 20):
        console.append_log("RX", f"line-{index}")

    assert len(console._entries) == console.MAX_LOG_ENTRIES
    assert console.log_view.document().maximumBlockCount() == console.MAX_DOCUMENT_BLOCKS
    assert console.log_view.document().blockCount() <= console.MAX_DOCUMENT_BLOCKS
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py -q
```

Expected: failure because entries lack timestamps and no log/document limits exist.

- [ ] **Step 3: Implement timestamped bounded entries**

In `AtConsole`:

```python
LOG_RETENTION_SECONDS = 180.0
MAX_LOG_ENTRIES = 2000
MAX_DOCUMENT_BLOCKS = 2200
```

Store entries as `(timestamp, direction, text)` in a `deque`, configure:

```python
self.log_view.document().setMaximumBlockCount(self.MAX_DOCUMENT_BLOCKS)
```

Before rendering a newly appended entry:

```python
now = time.monotonic()
self._entries.append((now, direction, text))
cutoff = now - self.LOG_RETENTION_SECONDS
trimmed_count = 0
while self._entries and self._entries[0][0] < cutoff:
    self._entries.popleft()
    trimmed_count += 1
while len(self._entries) > self.MAX_LOG_ENTRIES:
    self._entries.popleft()
    trimmed_count += 1
self._remove_leading_rendered_entries(trimmed_count)
self._append_rendered_entry(direction, text)
```

Implement `_remove_leading_rendered_entries` with `QTextCursor` so each
expired entry removes one leading document block without rebuilding the
complete log. Update theme refresh and clear paths to unpack timestamped
entries.

- [ ] **Step 4: Run console tests**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py tests\test_widget_states.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add stem_hub_host/ui/widgets/at_console.py tests/test_console_layout.py
git commit -m "fix: bound AT console history"
```

### Task 3: Add “清除全部” to the AT log context menu

**Files:**
- Modify: `stem_hub_host/ui/widgets/at_console.py`
- Modify: `tests/test_console_layout.py`

- [ ] **Step 1: Write failing context-menu isolation tests**

Expose the menu construction as a small testable method:

```python
def test_at_console_context_menu_offers_clear_all(qapp: QApplication) -> None:
    console = AtConsole()
    labels = [action.text() for action in console._create_log_context_menu().actions()]
    assert "清除全部" in labels


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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py -q
```

Expected: failure because `_create_log_context_menu` and `clear_log` do not exist.

- [ ] **Step 3: Implement the custom context menu**

Configure the log view:

```python
self.log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self.log_view.customContextMenuRequested.connect(self._show_log_context_menu)
```

Add:

```python
def _create_log_context_menu(self) -> QMenu:
    menu = self.log_view.createStandardContextMenu()
    menu.addSeparator()
    clear_action = menu.addAction("清除全部")
    clear_action.triggered.connect(self.clear_log)
    return menu

def _show_log_context_menu(self, position: QPoint) -> None:
    menu = self._create_log_context_menu()
    menu.exec(self.log_view.viewport().mapToGlobal(position))
    menu.deleteLater()

def clear_log(self) -> None:
    self._entries.clear()
    self.log_view.clear()
```

- [ ] **Step 4: Run console tests**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py -q
```

Expected: all console tests pass.

- [ ] **Step 5: Commit**

```powershell
git add stem_hub_host/ui/widgets/at_console.py tests/test_console_layout.py
git commit -m "feat: clear AT log from context menu"
```

### Task 4: Align dividers and vertically center upper controls

**Files:**
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`
- Modify: `tests/test_console_layout.py`

- [ ] **Step 1: Write failing geometry tests**

Name the relevant widgets and compare global geometry:

```python
def test_motor_and_output_dividers_share_vertical_position(qapp: QApplication) -> None:
    host = QWidget()
    layout = QHBoxLayout(host)
    motor = MotorCard()
    output = ChargeModeCard()
    layout.addWidget(motor)
    layout.addWidget(output)
    host.resize(1300, 500)
    host.show()
    qapp.processEvents()

    motor_y = motor.divider.mapTo(host, QPoint(0, 0)).y()
    output_y = output.divider.mapTo(host, QPoint(0, 0)).y()
    assert abs(motor_y - output_y) <= 1


@pytest.mark.parametrize("card_type", [MotorCard, ChargeModeCard])
def test_card_upper_content_is_vertically_centered(qapp: QApplication, card_type) -> None:
    card = card_type()
    card.resize(650, 500)
    card.show()
    qapp.processEvents()
    region = card.upper_region.geometry()
    content = card.upper_content.geometry()
    assert abs(content.center().y() - region.rect().center().y()) <= 2
    assert content.top() - region.top() >= theme.CARD_UPPER_MIN_GAP
    assert region.bottom() - content.bottom() >= theme.CARD_UPPER_MIN_GAP
```

- [ ] **Step 2: Run geometry tests and verify RED**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py -q
```

Expected: failure because shared region widgets and divider attributes do not exist.

- [ ] **Step 3: Add shared geometry tokens**

In `theme.py`:

```python
CARD_UPPER_REGION_HEIGHT = 246
CARD_UPPER_MIN_GAP = 12
```

- [ ] **Step 4: Refactor each card’s upper section**

For each card:

- create `self.upper_region = QWidget(self)` with fixed height `CARD_UPPER_REGION_HEIGHT`;
- create a zero-margin `QVBoxLayout` on it;
- add stretch, then `self.upper_content`, then stretch;
- put the existing MODE/CURRENT group or switch/ALL OFF group inside `upper_content`;
- assign the separator to `self.divider`;
- leave lower controls and signal wiring unchanged.

- [ ] **Step 5: Run layout and visual tests**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests\test_console_layout.py tests\test_output_controls.py tests\test_widget_states.py -q
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: geometry tests pass. Visual regression is expected to report intentional golden-image differences, which must be inspected before baselines are updated.

- [ ] **Step 6: Capture and inspect updated UI**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' tools\snap_tab1.py
```

Inspect the generated dark/light fixed and fullscreen console images. Confirm divider alignment, centered upper groups, and balanced top/bottom gaps before updating baselines with:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' tools\update_visual_baselines.py
```

- [ ] **Step 7: Commit**

```powershell
git add stem_hub_host/ui/theme.py stem_hub_host/ui/widgets/motor_card.py stem_hub_host/ui/widgets/charge_mode_card.py tests/test_console_layout.py tests/golden/visual
git commit -m "fix: align console control cards"
```

### Task 5: Full verification, real hardware smoke test, and release build

**Files:**
- Modify if needed: `tools/real_serial_smoke.py`
- Verify: `stem-hub-host.spec`

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run visual regression**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: all visual variants pass against reviewed baselines.

- [ ] **Step 3: Run COM12 read-only hardware smoke test**

Inspect `tools/real_serial_smoke.py` before execution and ensure the command set is limited to:

```text
AT+VERSION?
AT+SENSE?
AT+FAULT?
AT+MOTOR?
```

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' tools\real_serial_smoke.py --port COM12 --duration 190
```

Expected: connection/handshake succeeds, sensor responses continue for at least 190 seconds, retained telemetry/log history remains bounded, and no control or firmware-write command is issued.

- [ ] **Step 4: Build the release executable**

Run:

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m PyInstaller --clean --noconfirm stem-hub-host.spec
```

Expected: exit code 0 and `dist/stem-hub-host.exe` exists.

- [ ] **Step 5: Smoke-launch packaged fake mode**

Start `dist/stem-hub-host.exe --fake`, wait until its main window appears, verify it remains responsive, and close it without modifying hardware.

- [ ] **Step 6: Review diff and commit any verification-only changes**

```powershell
git diff --check
git status --short
```

If verification required tracked script corrections, commit only those intentional changes:

```powershell
git add tools/real_serial_smoke.py
git commit -m "test: strengthen serial retention smoke test"
```

### Task 6: Merge into master and re-verify

**Files:**
- No new source files expected.

- [ ] **Step 1: Confirm feature branch is clean**

```powershell
git status --short
git log --oneline master..HEAD
```

Expected: no working-tree changes and the design plus feature commits are listed.

- [ ] **Step 2: Merge from the main checkout**

```powershell
git -C D:\Codes\STM32\stem-hub-host checkout master
git -C D:\Codes\STM32\stem-hub-host merge --no-ff codex/ui-console-memory-polish
```

Expected: merge succeeds without conflicts.

- [ ] **Step 3: Re-run complete tests on merged master**

```powershell
& 'D:\Codes\STM32\stem-hub-host\env\release\Scripts\python.exe' -m pytest D:\Codes\STM32\stem-hub-host\tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 4: Remove the merged worktree and branch**

From the main checkout:

```powershell
git worktree remove D:\Codes\STM32\stem-hub-host\.worktrees\ui-console-memory-polish
git worktree prune
git branch -d codex/ui-console-memory-polish
```

Expected: the feature branch is deleted only after the merge and merged-result test succeed.
