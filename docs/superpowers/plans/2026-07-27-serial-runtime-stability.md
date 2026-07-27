# Serial and MCU Runtime Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the MCU and host connected and readable through recoverable UART
errors, malformed frames, and individual command timeouts.

**Architecture:** Preserve the existing framed AT protocol. Recovery is local to
the MCU HAL callback and host `SerialWorker`; UI receives only validated tunnel
frames and safe diagnostic text.

**Tech Stack:** STM32F103, STM32 HAL, FreeRTOS/CMSIS-RTOS2, Python 3.11, PySide6,
pytest, pyserial, STM32Cube command-line tools.

---

### Task 1: Record host regressions

**Files:**
- Modify: `tests/test_behavior_regressions.py`
- Modify: `tests/test_serial_worker.py`

- [ ] Add a test that feeds `b"\xff\xfe\r\n"` and asserts
  `passthrough_received` remains empty while `error_occurred` contains
  `"FF FE"`.
- [ ] Replace the disconnect-on-timeout test with a test that asserts the
  transport remains open, late `OK` is discarded, and a command succeeds after
  the 200 ms resynchronization interval.
- [ ] Add a UI test that calls `_on_uart_rx` while tunnel mode is off and asserts
  the pass-through RX count remains zero.
- [ ] Run the focused tests and confirm they fail against the baseline:
  `.\\env\\release\\Scripts\\python.exe -m pytest -q
  tests\\test_serial_worker.py tests\\test_behavior_regressions.py`.

### Task 2: Implement host framing and timeout recovery

**Files:**
- Modify: `stem_hub_host/serial_worker.py`
- Modify: `stem_hub_host/controller.py`
- Modify: `stem_hub_host/ui/main_window.py`

- [ ] Add a 200 ms resynchronization timer and reject commands while it is
  active.
- [ ] Make the worker FIFO single-flight: only write its head, start timeout
  accounting when it is written, and advance after terminal `OK` or `ERROR`.
- [ ] On timeout, dispose every pending timer, clear the FIFO, emit
  `ParsedResponse(error=AtError("TIMEOUT"))` for abandoned commands, reset the
  splitter, drain RX, and start the quiet timer without closing the transport.
- [ ] During resynchronization, discard input and restart the quiet timer.
- [ ] Strictly decode protocol lines as UTF-8. Emit a hexadecimal protocol
  diagnostic for invalid or unrecognized lines; do not emit
  `passthrough_received`.
- [ ] Expose the confirmed controller tunnel mode and gate `_on_uart_rx` when it
  is `"off"`.
- [ ] Format binary UART events as hexadecimal in the AT console.
- [ ] Run focused tests, then all host tests.

### Task 3: Record and fix MCU UART recovery

**Files:**
- Modify: `App/Src/app_runtime.c`
- Create: `tools/uart_fault_repro.py`

- [ ] Add a hardware reproduction script that queries VERSION, injects
  wrong-baud traffic, returns to 115200 baud, and verifies VERSION/DIAG remain
  responsive.
- [ ] Run it against the baseline firmware and retain the failing result.
- [ ] Change `HAL_UART_ErrorCallback` so UART1 only rearms when `RxState` is
  READY; BUSY_RX means the receive-complete callback already rearmed it.
- [ ] Preserve the original HAL error bits long enough to update every
  diagnostic counter.
- [ ] Build Debug with the bundled CMake executable.

### Task 4: Flash and stress-test both sides

**Files:**
- Modify only if a test exposes another root cause.

- [ ] Flash `build/Debug/stem-hub.elf` through ST-Link and reset the target.
- [ ] Run the UART fault reproduction script.
- [ ] Run a mixed VERSION/SENSE/FAULT/MOTOR/DIAG stress loop for at least five
  minutes.
- [ ] Run the host application or its real-transport harness long enough to
  cross multiple polling cycles and verify it stays connected.
- [ ] Capture diagnostic counters, failure frames, and task stack high-water
  marks.

### Task 5: Commit, merge, and verify

**Files:**
- All files changed by Tasks 1-4.

- [ ] Review both diffs and confirm the pre-existing MCU `.settings` changes are
  excluded.
- [ ] Commit host and MCU fixes on their `codex/` branches.
- [ ] Re-run complete host tests, MCU build, real-device smoke test, and Git
  status checks.
- [ ] Merge each fix branch into its original branch without including unrelated
  working-tree changes.
- [ ] Verify the merged tips and final repository statuses.
