# Rate-Limited Sampling and Connection Timeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit telemetry polling to five 0.2–1.0 Hz rates, keep the chart on a real 300-second timebase, and replace infinite serial handshake retries with a five-second connection attempt that resets cleanly on failure.

**Architecture:** `Controller` remains the owner of polling and handshake timing. It normalizes sample rates, owns a single connection deadline plus single-shot retry timer, and emits one final failure only after the worker is closed. `MainWindow` owns the modal user notification, while `PlotTab` reflects normalized rates and `PlotWidget` owns the visible time range.

**Tech Stack:** Python 3.11, PySide6 (`QTimer`, `QDoubleSpinBox`, `QMessageBox`), pyqtgraph, pytest/QtTest, PyInstaller.

---

### Task 1: Sample-rate contract and timer intervals

**Files:**
- Modify: `stem_hub_host/controller.py`
- Modify: `stem_hub_host/ui/tab2_plot.py`
- Modify: `stem_hub_host/ui/main_window.py`
- Test: `tests/test_sampling_rate.py`

- [ ] **Step 1: Write failing tests for the five rates and UI contract**

Create `tests/test_sampling_rate.py` with:

```python
import pytest
from PySide6.QtWidgets import QDoubleSpinBox

from stem_hub_host.app import get_app
from stem_hub_host.controller import Controller
from stem_hub_host.serial_worker import SerialWorker
from stem_hub_host.transport import FakeSerialTransport
from stem_hub_host.ui.tab2_plot import PlotTab
from stem_hub_host.ui.widgets.plot_widget import PlotWidget
from stem_hub_host.data_buffer import DataBuffer


def test_sample_rate_control_exposes_only_slow_range():
    get_app()
    tab = PlotTab(DataBuffer())
    assert isinstance(tab.hz_spin, QDoubleSpinBox)
    assert tab.hz_spin.minimum() == 0.2
    assert tab.hz_spin.maximum() == 1.0
    assert tab.hz_spin.singleStep() == 0.2
    assert tab.hz_spin.decimals() == 1
    assert tab.hz_spin.value() == 1.0


def test_controller_maps_supported_rates_to_intervals():
    get_app()
    controller = Controller(SerialWorker(FakeSerialTransport()))
    expected = {0.2: 5000, 0.4: 2500, 0.6: 1667, 0.8: 1250, 1.0: 1000}
    for hz, interval in expected.items():
        controller.set_sense_hz(hz)
        assert controller.sense_hz == hz
        assert controller._sense_timer.interval() == interval


def test_non_step_rate_snaps_up_at_midpoint():
    get_app()
    controller = Controller(SerialWorker(FakeSerialTransport()))
    changed = []
    controller.sense_request_hz_changed.connect(changed.append)
    controller.set_sense_hz(0.3)
    assert controller.sense_hz == 0.4
    assert changed[-1] == 0.4
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py -q
```

Expected: failures showing the current `0.1–20.0`, `0.5` step, `2.0` default, and unrestricted Controller behavior.

- [ ] **Step 3: Add the rate constants and normalization**

In `stem_hub_host/controller.py`, add:

```python
SENSE_HZ_OPTIONS = (0.2, 0.4, 0.6, 0.8, 1.0)
DEFAULT_SENSE_HZ = 1.0


def normalize_sense_hz(hz: float) -> float:
    value = float(hz)
    return min(
        SENSE_HZ_OPTIONS,
        key=lambda option: (abs(option - value), -option),
    )
```

Initialize `_sense_hz` from `DEFAULT_SENSE_HZ`. In `set_sense_hz`, normalize,
update the timer, and always emit the normalized value so typed non-step values
are reflected back to the UI:

```python
def set_sense_hz(self, hz: float) -> None:
    normalized = normalize_sense_hz(hz)
    self._sense_hz = normalized
    self._apply_sense_interval()
    self.sense_request_hz_changed.emit(normalized)
```

Calculate the interval with:

```python
self._sense_timer.setInterval(round(1000 / self._sense_hz))
```

- [ ] **Step 4: Restrict and synchronize the spin box**

In `stem_hub_host/ui/tab2_plot.py`, configure:

```python
self.hz_spin.setDecimals(1)
self.hz_spin.setRange(0.2, 1.0)
self.hz_spin.setSingleStep(0.2)
self.hz_spin.setValue(1.0)
```

Add a signal-safe setter:

```python
def set_sample_rate(self, hz: float) -> None:
    self.hz_spin.blockSignals(True)
    self.hz_spin.setValue(hz)
    self.hz_spin.blockSignals(False)
```

In `MainWindow.__init__`, connect:

```python
self._controller.sense_request_hz_changed.connect(
    self.plot_tab.set_sample_rate
)
```

- [ ] **Step 5: Verify GREEN and commit**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py -q
```

Expected: all tests pass.

Commit:

```powershell
git add stem_hub_host/controller.py stem_hub_host/ui/tab2_plot.py stem_hub_host/ui/main_window.py tests/test_sampling_rate.py
git commit -m "feat: limit telemetry sampling to one hertz"
```

### Task 2: Real 300-second chart timebase

**Files:**
- Modify: `stem_hub_host/ui/widgets/plot_widget.py`
- Test: `tests/test_sampling_rate.py`

- [ ] **Step 1: Write failing timebase tests**

Add tests that seed non-uniform timestamps and inspect both plotted x values and
the visible range:

```python
def test_plot_uses_real_elapsed_seconds_and_fixed_window():
    get_app()
    buffer = DataBuffer()
    buffer.series["batt_v"].times.extend((10.0, 12.5, 17.0))
    buffer.series["batt_v"].values.extend((36.0, 36.5, 37.0))
    plot = PlotWidget(buffer)
    plot.set_channels(("batt_v",))
    plot.update_from_buffer()

    x, _ = plot._curves["batt_v"].getData()
    assert tuple(x) == (-7.0, -4.5, 0.0)
    x_range = plot._plot.viewRange()[0]
    assert x_range[0] == pytest.approx(-300.0)
    assert x_range[1] == pytest.approx(0.0)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py::test_plot_uses_real_elapsed_seconds_and_fixed_window -q
```

Expected: real timestamp assertion passes, but visible x range is not
`[-300, 0]`.

- [ ] **Step 3: Apply the explicit time window**

In `PlotWidget.__init__`, disable automatic x-range and set the contract:

```python
self._plot.disableAutoRange(axis="x")
self._plot.setXRange(-DataBuffer.WINDOW_SECONDS, 0.0, padding=0)
```

After each redraw, reapply the same x range so new data and theme refreshes
cannot silently change the audit timebase.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_sampling_rate.py -q
```

Commit:

```powershell
git add stem_hub_host/ui/widgets/plot_widget.py tests/test_sampling_rate.py
git commit -m "fix: anchor charts to real five-minute timebase"
```

### Task 3: Bounded handshake state machine

**Files:**
- Modify: `stem_hub_host/controller.py`
- Create: `tests/test_connection_flow.py`
- Modify: `tests/test_behavior_regressions.py`

- [ ] **Step 1: Write failing finite-connection tests**

Create `tests/test_connection_flow.py`. Build controllers with short injected
test timings:

```python
controller = Controller(
    worker,
    handshake_deadline_ms=120,
    handshake_retry_ms=20,
    handshake_attempt_timeout_ms=15,
    handshake_initial_delay_ms=0,
)
```

Cover:

```python
def test_handshake_deadline_closes_before_reporting_failure(qapp):
    # Open a FakeSerialTransport without FakeFirmware, wait past the deadline.
    # Record worker.disconnected and controller.handshake_failed ordering.
    # Assert one failure, worker closed, and no retry/deadline timer active.


def test_success_cancels_deadline_and_starts_polling(qapp):
    # Feed +VERSION:test and OK during the first attempt.
    # Assert handshake true, deadline/retry timers stopped, polling active.


def test_user_close_during_connecting_does_not_report_failure(qapp):
    # Open, close before deadline, wait past deadline.
    # Assert no handshake_failed signal.


def test_fast_reconnect_ignores_old_connection_timers(qapp):
    # Open FAKE0, close, open FAKE1, complete FAKE1 handshake.
    # Assert one live successful connection and no late failure.
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py -q
```

Expected: constructor keyword errors and/or evidence that retries remain active
indefinitely.

- [ ] **Step 3: Add configurable production-default timing**

Extend `Controller.__init__`:

```python
def __init__(
    self,
    worker: SerialWorker,
    parent: QObject | None = None,
    *,
    handshake_deadline_ms: int = 5000,
    handshake_retry_ms: int = 1000,
    handshake_attempt_timeout_ms: int = 500,
    handshake_initial_delay_ms: int = 200,
) -> None:
```

Store the four timings, add a single-shot `_handshake_deadline_timer`, and make
the existing retry timer single-shot.

- [ ] **Step 4: Implement one connection attempt lifecycle**

On `worker.connected`:

```python
self._connection_attempt_active = True
self._last_handshake_error = "TIMEOUT"
self._handshake_deadline_timer.start(self._handshake_deadline_ms)
self._handshake_delay_timer.start(self._handshake_initial_delay_ms)
```

On a failed handshake attempt, save the reason and start only the single-shot
retry timer. Do not emit final failure yet and do not place the UI in persistent
`ERROR`.

On success, use one idempotent `_complete_handshake()` method that:

```python
self._connection_attempt_active = False
self._handshake_ok = True
self._cancel_handshake_timers()
self._start_polling()
```

On deadline, use `_fail_connection_attempt()`:

```python
reason = self._last_handshake_error
self._connection_attempt_active = False
self._cancel_handshake_timers()
self._worker.close()
self.handshake_failed.emit(reason)
```

Guard `_do_handshake` and every exception branch with
`_connection_attempt_active` so a deadline firing inside its nested event loop
cannot produce a second failure.

On user `close()` and worker disconnection, stop delay, retry, and deadline
timers without emitting failure.

- [ ] **Step 5: Update the old infinite-retry regression**

Replace `test_rejected_handshake_enters_error_state_and_retries` with a bounded
test asserting the temporary connection stays open before the deadline and
returns offline after it. Keep the rapid reconnect regression and adapt it to
the injected short timing API.

- [ ] **Step 6: Verify GREEN and commit**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py tests\test_behavior_regressions.py -q
```

Commit:

```powershell
git add stem_hub_host/controller.py tests/test_connection_flow.py tests/test_behavior_regressions.py
git commit -m "fix: bound serial handshake attempts"
```

### Task 4: Offline reset and one failure dialog

**Files:**
- Modify: `stem_hub_host/ui/main_window.py`
- Modify: `stem_hub_host/ui/widgets/serial_bar.py`
- Test: `tests/test_connection_flow.py`
- Test: `tests/test_serial_bar.py`

- [ ] **Step 1: Write failing UI-state tests**

Add tests:

```python
def test_opening_state_reads_connecting(serial_bar):
    serial_bar.set_connected("COM3", 115200)
    assert serial_bar.status_badge.text() == "CONNECTING"


def test_handshake_failure_is_offline_before_single_dialog(qapp, monkeypatch):
    # Patch QMessageBox.warning to record calls without blocking.
    # Run a short no-response connection attempt through MainWindow.
    # In the patched warning callback, assert status is OFFLINE,
    # connect button is CONNECT, and port combo is enabled.
    # Assert exactly one warning call after waiting beyond two deadlines.


def test_direct_open_failure_restores_offline_and_warns_once(qapp, monkeypatch):
    # Use a transport whose open returns False.
    # Call MainWindow._on_open_serial and assert OFFLINE + one warning.
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py tests\test_serial_bar.py -q
```

Expected: `OPENING` label and no failure dialog/offline reset.

- [ ] **Step 3: Implement final UI notification**

Change `SerialBar.set_connected()` to display `CONNECTING`.

In `MainWindow`, replace the persistent-error handler with:

```python
def _on_handshake_failed(self, reason: str) -> None:
    self._apply_handshake_gate(connected=False)
    self.console_tab.at_console.append_error(
        f"连接失败: {reason}"
    )
    QMessageBox.warning(
        self,
        "连接失败",
        "串口已打开，但未能在 5 秒内完成设备握手。\n"
        f"原因：{reason}\n\n请检查端口、波特率和下位机状态后重试。",
    )
```

Because Controller closes the worker before emitting this signal, the existing
`_on_worker_disconnected()` has already restored `OFFLINE`.

For direct `Controller.open()` failure, explicitly call
`serial_bar.set_disconnected()` and the same one-shot warning helper. Do not
start any retry.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py tests\test_serial_bar.py -q
```

Commit:

```powershell
git add stem_hub_host/ui/main_window.py stem_hub_host/ui/widgets/serial_bar.py tests/test_connection_flow.py tests/test_serial_bar.py
git commit -m "fix: restore offline UI after connection failure"
```

### Task 5: No-hardware workflow documentation and fake verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_connection_flow.py`

- [ ] **Step 1: Add an end-to-end fake handshake test**

Use the real `FakeFirmware`, `FakeSerialTransport`, `SerialWorker`, Controller,
and MainWindow. Open `FAKE0`, wait for handshake, and assert:

```python
assert controller.is_handshake_ok
assert window.console_tab.serial_bar.status_badge.text() == "CONNECTED"
assert window.console_tab.motor_card.isEnabled()
assert window.console_tab.charge_card.isEnabled()
```

- [ ] **Step 2: Run the test and verify it passes through production flow**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py::test_fake_firmware_completes_real_connection_flow -q
```

Expected: PASS. This is a characterization/integration test for the already
existing fake transport, so it need not be RED.

- [ ] **Step 3: Document the correct no-hardware entry points**

Add a `无硬件联调` section to `README.md`:

```powershell
# 可操作的完整 fake 界面
& 'env\release\Scripts\python.exe' -m stem_hub_host.main --fake

# 只验证连接状态机
& 'env\release\Scripts\python.exe' -m pytest tests\test_connection_flow.py -q

# 打包后验证
& 'dist\stem-hub-host.exe' --fake
```

Explain that pytest closes its windows automatically and is not the interactive
preview.

- [ ] **Step 4: Commit**

```powershell
git add README.md tests/test_connection_flow.py
git commit -m "docs: add no-hardware test workflow"
```

### Task 6: Visual baseline, full verification, and release

**Files:**
- Modify: `tests/golden/visual/dark/fixed-charts-connected.png`
- Modify: `tests/golden/visual/dark/fullscreen-charts-connected.png`
- Modify: `tests/golden/visual/light/fixed-charts-connected.png`
- Modify: `tests/golden/visual/light/fullscreen-charts-connected.png`
- Modify: `tests/golden/visual/manifest.json`
- Create: `docs/superpowers/reports/2026-07-23-sampling-connection-implementation.md`
- Build: `dist/stem-hub-host.exe`

- [ ] **Step 1: Run the complete automated suite**

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests -q
& 'env\release\Scripts\python.exe' -m compileall -q stem_hub_host tools
```

Expected: every test passes and compileall exits zero.

- [ ] **Step 2: Explicitly update and review visual baselines**

```powershell
& 'env\release\Scripts\python.exe' tools\update_visual_baselines.py
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
```

Expected: 16/16 captures pass. Visually inspect at least Dark/Light fixed Charts
and Dark fixed Console to confirm `1.0 Hz`, chart scale, fonts, and connection
layout.

- [ ] **Step 3: Verify source fake startup**

Start:

```powershell
& 'env\release\Scripts\python.exe' -m stem_hub_host.main --fake
```

Confirm the process remains alive for at least 5 seconds and reaches
`CONNECTED`, then stop only this test process.

- [ ] **Step 4: Write the implementation report**

Record the final frequency options and intervals, connection state sequence,
test count, visual result, EXE size/hash, and fake startup evidence in
`docs/superpowers/reports/2026-07-23-sampling-connection-implementation.md`.

- [ ] **Step 5: Commit source and approved visual changes**

```powershell
git add tests/golden/visual docs/superpowers/reports/2026-07-23-sampling-connection-implementation.md
git commit -m "test: refresh sampling and connection visual baselines"
```

- [ ] **Step 6: Rebuild with the retained release environment**

```powershell
& 'env\release\Scripts\python.exe' -m PyInstaller --clean --noconfirm stem-hub-host.spec
```

Do not delete, recreate, or upgrade `env/release`.

- [ ] **Step 7: Verify the packaged application**

Run `dist/stem-hub-host.exe --fake` for at least 5 seconds. Confirm it remains
alive, then stop only processes whose executable path is exactly the new
`dist/stem-hub-host.exe`. Record size and SHA-256 and confirm the PyInstaller
analysis includes four bundled fonts plus `style.qss`, with no MKL/TBB.

- [ ] **Step 8: Run final post-build gates**

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests -q
& 'env\release\Scripts\python.exe' tools\check_visual_regression.py
git status --short
```

Preserve the user's pre-existing modification to
`docs/superpowers/plans/2026-07-23-visual-elevation-roadmap.md`.
