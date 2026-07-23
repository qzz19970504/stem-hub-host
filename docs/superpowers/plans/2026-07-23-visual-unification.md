# Visual Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Unify the console, charts, and passthrough visuals around the supplied
dark-console render without changing device behavior.

**Architecture:** Theme tokens remain the visual source of truth. QSS handles
standard Qt controls and object-name roles; custom-painted MOTOR controls use
the same tokens directly. Existing controller signals and public widget APIs
remain unchanged.

**Tech Stack:** Python 3.11, PySide6, Qt Style Sheets, pyqtgraph, pytest.

---

### Task 1: Lock the intended component structure

**Files:**
- Modify: `tests/test_widget_states.py`
- Modify: `tests/test_passthrough_panel.py`
- Modify: `tests/test_plot_widget.py`

- [x] Add tests asserting that the terminal exposes an outer card and one
  named command bar while its log viewport is visually transparent.
- [x] Add tests asserting that passthrough bridge controls use the shared
  `modeChip` role and TX/RX actions use primary/secondary roles.
- [x] Add tests asserting that chart channel controls use the shared
  `channelChip` role and the toolbar has a named surface.
- [x] Run the focused tests and confirm they fail because the roles and
  structure are absent.

### Task 2: Lift and consolidate the palette

**Files:**
- Modify: `stem_hub_host/ui/theme.py`
- Modify: `stem_hub_host/ui/style.qss`

- [x] Add tokens for elevated panels, controls, plots, soft accent surfaces,
  and semantic button tints.
- [x] Update global QSS so default, hover, pressed, focus, checked, and disabled
  states share one material language.
- [x] Run focused rendering tests and confirm the new palette does not remove
  disabled/focus distinction.

### Task 3: Refine MOTOR and terminal surfaces

**Files:**
- Modify: `stem_hub_host/ui/widgets/motor_card.py`
- Modify: `stem_hub_host/ui/widgets/at_console.py`

- [x] Replace the plain mode badge fill with a subtle tokenized gradient.
- [x] Make inactive mode buttons uniform slate controls and keep semantic color
  in their icons/borders only.
- [x] Name the command bar and blend the log viewport into the terminal card so
  only two boundaries remain visible.
- [x] Run widget tests and capture the console screenshot.

### Task 4: Unify charts and passthrough

**Files:**
- Modify: `stem_hub_host/ui/tab2_plot.py`
- Modify: `stem_hub_host/ui/widgets/plot_widget.py`
- Modify: `stem_hub_host/ui/widgets/passthrough_panel.py`

- [x] Wrap chart controls in `toolbarPanel`, assign the clear action a
  secondary role, and render channels as `channelChip` toggles.
- [x] Apply plot-specific background/grid tokens.
- [x] Render bridge radios as `modeChip` segments and place TX/RX content in
  matching named sub-panels.
- [x] Assign all passthrough actions primary or secondary roles.
- [x] Run focused tests and capture both secondary-page screenshots.

### Task 5: Visual and release verification

**Files:**
- Modify: `tools/snap_visual_audit.py` only if deterministic fixtures require it
- Output: `docs/iteration_*_v2.png`

- [x] Generate connected, disconnected, charts, passthrough, and fullscreen
  screenshots.
- [x] Inspect every screenshot for clipping, missing fonts, inconsistent
  states, and unintended black insets.
- [x] Run `tools/compare_design.py` and require no RGB-difference regression.
- [x] Run `python -m pytest tests -q` and require zero failures.
- [x] Rebuild with `python -m PyInstaller --noconfirm stem-hub-host.spec`.
- [x] Launch the packaged EXE with `--fake` and confirm it remains alive for
  three seconds.
