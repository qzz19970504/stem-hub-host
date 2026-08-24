# Bypass Layout Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the motor/output card layouts so the shipped PySide UI matches the approved hierarchy rendering without changing control behavior.

**Architecture:** Keep the existing card public APIs and controller wiring. Replace only internal layout composition: deterministic vertical spacing for `MotorCard`, and a grid-backed hierarchy canvas for `ChargeModeCard` whose connector painter derives endpoints from child geometry.

**Tech Stack:** Python 3.11, PySide6, pytest/pytest-qt, native QPainter rendering, PyInstaller.

---

### Task 1: Lock motor spacing with a failing geometry test

**Files:**
- Modify: `tests/test_output_controls.py`
- Modify: `stem_hub_host/ui/widgets/motor_card.py`

- [ ] Add a test that shows `MotorCard` at its production card size, maps MODE bottom, current surface top/bottom, and divider top into card coordinates, and asserts both gaps differ by at most two pixels.
- [ ] Run the focused test and confirm it fails because the current-to-divider gap is larger.
- [ ] Remove vertical stretch-based centering from the motor upper region, use explicit tokenized top/between/bottom spacing, and preserve the card/button API.
- [ ] Re-run the focused test and existing motor widget tests.

### Task 2: Lock the approved output hierarchy with failing tests

**Files:**
- Modify: `tests/test_output_controls.py`
- Modify: `stem_hub_host/ui/widgets/charge_mode_card.py`
- Modify: `stem_hub_host/ui/theme.py`

- [ ] Add tests asserting CHARGE and CHARGE BYPASS share a row, DRIVE is centered below them, NMOS1/NMOS2/LIGHTS form the next row, DRIVE is centered over NMOS2, and CHARGE BYPASS aligns with LIGHTS.
- [ ] Add containment assertions proving every toggle and label stays inside the card at the supported fixed-card width.
- [ ] Run the focused tests and confirm failure against the current two-row spacer layout.
- [ ] Implement a hierarchy canvas with a five-column grid, stable toggle-cell minimum sizes, human-readable labels, and QPainter connector lines behind the controls.
- [ ] Re-run output-control and controller/state tests.

### Task 3: Visual verification and release rebuild

**Files:**
- Modify: `tests/golden/visual/dark/*.png`
- Modify: `tests/golden/visual/light/*.png`
- Modify: `tests/golden/visual/manifest.json`

- [ ] Render dark/light fixed and fullscreen console states and inspect them against the approved reference for spacing, clipping, hierarchy, and alignment.
- [ ] Accept only the intended console baseline changes, then run all visual regression cases.
- [ ] Run `env/release/Scripts/python.exe -m pytest tests -q` and require zero failures.
- [ ] Run a clean PyInstaller build, verify resources and absence of MKL/TBB, and launch `dist/stem-hub-host.exe --fake` for an eight-second smoke test.
- [ ] Commit the implementation, merge the feature branch to `master` with a merge commit, and repeat the focused tests and clean-worktree check.

