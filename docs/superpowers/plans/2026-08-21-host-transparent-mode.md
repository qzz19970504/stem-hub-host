# Host Exclusive Transparent Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the PySide6 host from framed UART tunnel commands to the firmware's exclusive raw transparent mode at 9600 8N1.

**Architecture:** Keep the current UI and reverse UART event framing while making `SerialWorker` own an explicit AT/entering/transparent/exiting session state. `Controller` serializes target changes and polling around worker transitions, and `FakeFirmware` mirrors the new wire contract for deterministic end-to-end tests.

**Tech Stack:** Python 3.11, PySide6, QtSerialPort, pytest, PyInstaller, STM32 UART hardware.

---

### Task 1: Lock the new protocol and worker API with tests

**Files:**
- Modify: `tests/test_at_protocol.py`
- Modify: `tests/test_serial_worker.py`

- [ ] Add failing tests for the three `AT+TRANS` mappings and invalid modes.
- [ ] Add failing worker tests for entry state, exact raw writes, reserved escape rejection, guarded exit, timeout disconnect, and close/reset behavior.
- [ ] Run the targeted tests and confirm failures are caused by missing APIs.
- [ ] Implement the minimal protocol builders and worker session state.
- [ ] Run the targeted tests until green and commit.

### Task 2: Migrate controller and fake firmware behavior

**Files:**
- Modify: `stem_hub_host/controller.py`
- Modify: `stem_hub_host/fake_firmware.py`
- Modify: `tests/test_behavior_regressions.py`

- [ ] Replace legacy bridge and hexadecimal tunnel expectations with failing exclusive-session tests.
- [ ] Verify the tests fail against the old controller and fake firmware.
- [ ] Serialize entry, exit, target switching, direct binary sends, polling, and failure recovery.
- [ ] Implement fake-firmware raw forwarding, reverse events, and guarded escape.
- [ ] Replace fixed sleeps with condition-based waits and run behavior tests until green.
- [ ] Commit the controller and fake-firmware migration.

### Task 3: Align tools and current documentation

**Files:**
- Modify: `README.md`
- Modify: `tools/real_serial_smoke.py`
- Create: `docs/transparent-mode-at-contract.md`
- Create: `docs/transparent-mode-hardware-test-2026-08-21.md`

- [ ] Set every operational default to 9600 and remove test-branch wording.
- [ ] Document the exact entry, raw transfer, reverse event, guarded exit, and failure contracts.
- [ ] Extend the real serial smoke path to exercise UART3 without changing firmware.
- [ ] Run documentation searches and targeted tool tests, then commit.

### Task 4: Verify, package, test hardware, and integrate

- [ ] Run the full pytest suite, Python compilation, and visual regression.
- [ ] Build the PyInstaller executable and launch it in fake mode for smoke testing.
- [ ] Discover the current UART1/downstream ports and complete UART3 bidirectional hardware verification at 9600 8N1.
- [ ] Record exact hardware evidence and leave the device out of transparent mode.
- [ ] Review the diff, commit the hardware record, and require a clean feature branch.
- [ ] Merge with `--no-ff` into local `master` only after every gate passes.
- [ ] Re-run the full tests and key connected checks on merged `master`.
