# Safe Release Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the one-file Windows release size without changing application behavior or UI rendering.

**Architecture:** Keep application and UI sources unchanged, but build them in an isolated Python 3.11 virtual environment using pinned PyPI wheels so Conda's full MKL/TBB runtime is not collected. Accept the release only after tests, archive inspection, executable startup, and deterministic visual captures pass.

**Tech Stack:** Python 3.11, PySide6 6.11.1, pyqtgraph 0.14.0, NumPy 2.4.6, PyInstaller 6.21.0, pytest

---

### Task 1: Pin the release toolchain

**Files:**
- Create: `requirements-release.txt`
- Modify: `README.md`

- [ ] **Step 1: Record the current dependency versions**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -c "import numpy, PySide6, pyqtgraph, PyInstaller; print(numpy.__version__, PySide6.__version__, pyqtgraph.__version__, PyInstaller.__version__)"
```

Expected: `2.4.6 6.11.1 0.14.0 6.21.0`.

- [ ] **Step 2: Add exact release requirements**

Create `requirements-release.txt` containing:

```text
PySide6==6.11.1
PySide6-Addons==6.11.1
pyqtgraph==0.14.0
numpy==2.4.6
PyInstaller==6.21.0
pytest==9.1.1
```

- [ ] **Step 3: Document the isolated build command**

Add a release-build section to `README.md` that creates `env\release`, installs
`requirements-release.txt`, runs tests, and invokes the existing spec.

- [ ] **Step 4: Inspect the diff**

Run:

```powershell
git diff -- requirements-release.txt README.md
```

Expected: only release dependency and build documentation changes.

### Task 2: Create the isolated release environment

**Files:**
- Create locally, ignored by Git: `env/release/`

- [ ] **Step 1: Create a clean virtual environment**

Run:

```powershell
& 'C:\Users\44575\.conda\envs\stem-hub-host\python.exe' -m venv 'env\release'
```

Expected: `env\release\Scripts\python.exe` exists.

- [ ] **Step 2: Install pinned release dependencies**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pip install --upgrade pip
& 'env\release\Scripts\python.exe' -m pip install -r requirements-release.txt
```

Expected: all pinned packages install without dependency conflicts.

- [ ] **Step 3: Verify numerical backend**

Run:

```powershell
& 'env\release\Scripts\python.exe' -c "import numpy; numpy.show_config()"
```

Expected: the configuration does not reference Intel MKL.

### Task 3: Establish behavior parity

**Files:**
- Test: `tests/`

- [ ] **Step 1: Run all tests in the release environment**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests -q
```

Expected: all 122 tests pass.

- [ ] **Step 2: Stop on any failure**

If a test fails, compare package versions and runtime output with the baseline.
Do not modify UI or control behavior to make the release environment pass.

### Task 4: Build and inspect the optimized executable

**Files:**
- Modify: `stem-hub-host.spec`
- Generate, ignored by Git: `build/`, `dist/stem-hub-host.exe`

- [ ] **Step 1: Preserve the old release size**

Run:

```powershell
Get-Item 'dist\stem-hub-host.exe' | Select-Object Length
```

Expected baseline: `252837203` bytes.

- [ ] **Step 2: Build from clean analysis state**

Before `Analysis`, prepend the base Python 3.11 interpreter's `Library/bin`
directory to `PATH` so PyInstaller cannot resolve `pyexpat.pyd` against a DLL
from another Conda installation:

```python
PYTHON_BASE_LIBRARY_BIN = Path(sys.base_prefix) / "Library" / "bin"
if PYTHON_BASE_LIBRARY_BIN.is_dir():
    os.environ["PATH"] = (
        f"{PYTHON_BASE_LIBRARY_BIN}{os.pathsep}{os.environ.get('PATH', '')}"
    )
```

Run:

```powershell
& 'env\release\Scripts\python.exe' -m PyInstaller --clean --noconfirm stem-hub-host.spec
```

Expected: PyInstaller exits with code 0.

- [ ] **Step 3: Inspect bundled files**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m PyInstaller.utils.cliutils.archive_viewer -l 'dist\stem-hub-host.exe'
```

Expected: `style.qss`, Rajdhani, JetBrains Mono, and Noto Sans SC are present;
Intel MKL/TBB entries are absent.

- [ ] **Step 4: Record final size**

Run:

```powershell
Get-Item 'dist\stem-hub-host.exe' | Select-Object Length
```

Expected: materially smaller than `252837203` bytes.

### Task 5: Verify executable and visual parity

**Files:**
- Use: `dist/stem-hub-host.exe`
- Generate, ignored or temporary: visual audit captures

- [ ] **Step 1: Run the packaged fake-firmware application**

Launch `dist\stem-hub-host.exe --fake`, wait at least five seconds, and verify
that it remains running. Close it cleanly after the check.

- [ ] **Step 2: Generate deterministic visual captures**

Run:

```powershell
& 'env\release\Scripts\python.exe' tools\snap_visual_audit.py docs\release_audit dark
```

Expected: normal and fullscreen captures for the console, charts, and
passthrough pages are written.

- [ ] **Step 3: Compare captures**

Compare the release-environment captures with the current `docs/visual_v4/night`
captures. Font rendering, card geometry, colors, controls, and chart layout must
remain visually equivalent. Investigate any material pixel difference.

- [ ] **Step 4: Run the complete test suite again**

Run:

```powershell
& 'env\release\Scripts\python.exe' -m pytest tests -q
```

Expected: all 122 tests pass.

### Task 6: Archive the optimized release configuration

**Files:**
- Commit: `requirements-release.txt`
- Commit: `README.md`
- Commit: this design and plan

- [ ] **Step 1: Review tracked changes**

Run:

```powershell
git status --short
git diff --check
git diff
```

Expected: no generated executable, virtual environment, cache, or temporary
capture is staged.

- [ ] **Step 2: Commit the verified build configuration**

Run:

```powershell
git add requirements-release.txt README.md docs/superpowers/specs/2026-07-23-safe-release-compression-design.md docs/superpowers/plans/2026-07-23-safe-release-compression.md
git commit -m "build: shrink release without changing runtime behavior"
```

- [ ] **Step 3: Verify final repository state**

Run:

```powershell
git status --short --branch
git log -2 --oneline
```

Expected: clean worktree with the optimized build commit above baseline commit
`74e4101`.
