# Safe Release Compression Design

## Context

The current one-file release is 252,837,203 bytes (241.12 MiB). PyInstaller's
archive contains about 171.15 MiB of compressed Intel MKL and TBB binaries,
which entered through the Conda NumPy package. The application source, UI
styles, and control logic are not responsible for most of the size.

The pre-compression state is preserved in Git commit `74e4101`.

## Requirements

- Preserve all application behavior, serial control paths, fake-firmware mode,
  charts, passthrough, keyboard shortcuts, animations, themes, fonts, and
  fixed/fullscreen window behavior.
- Keep the existing QSS and all bundled font files unchanged.
- Produce a one-file GUI executable without a console window.
- Prefer a conservative reduction over manual DLL deletion.
- Make the release build reproducible from checked-in dependency metadata.
- Reject the optimized build if tests, startup, packaged resources, or visual
  captures regress.

## Selected Approach

Build the unchanged application from an isolated `venv` populated with pinned
PyPI wheels. The PyPI NumPy wheel uses its own compact numerical runtime instead
of collecting the Conda environment's complete MKL/TBB directory. Keep the
existing PyInstaller collection policy so that Qt plugins and resources are not
removed speculatively.

This is safer than filtering individual MKL DLLs from a Conda build because
runtime CPU dispatch can load different libraries on different machines. It is
also safer than immediately excluding optional Qt modules because pyqtgraph may
load some of them dynamically.

## Native Runtime Resolution

A virtual environment created from a Conda Python interpreter still obtains
standard-library extension DLLs from that interpreter's `Library/bin`
directory. On a machine with more than one Conda installation, PyInstaller can
otherwise find an unrelated installation first through `PATH`.

The spec therefore prepends `Path(sys.base_prefix) / "Library" / "bin"` before
dependency analysis. This keeps Python 3.11 extensions paired with the Python
3.11 native runtime. It does not add Conda NumPy or MKL because NumPy itself is
installed from the pinned PyPI wheel inside the isolated environment.

## Build Inputs

Add a release-only requirements file with exact versions matching the verified
baseline:

- Python 3.11
- PySide6 6.11.1
- PySide6-Addons 6.11.1
- pyqtgraph 0.14.0
- NumPy 2.4.6
- PyInstaller 6.21.0

The local release environment lives under the ignored `env/` directory. Build
artifacts remain ignored under `build/` and `dist/`.

## Verification Gates

1. Run the full test suite in the isolated release environment.
2. Build from a clean PyInstaller analysis directory.
3. Confirm the executable starts with `--fake` and remains alive long enough
   for the fake handshake and initial UI refresh.
4. Inspect the PyInstaller archive for the four font files and `style.qss`.
5. Confirm the optimized archive no longer contains Intel MKL/TBB binaries.
6. Generate deterministic screenshots for all three tabs and fullscreen views
   using the same isolated dependencies.
7. Compare the new captures with baseline captures and inspect any difference
   before accepting the release.
8. Record final size and archive composition.

## Rollback

The original source state is recoverable with Git commit `74e4101`. The original
241.12 MiB executable remains outside Git until the optimized build has passed
all gates. No business or UI source file is changed as part of the first
compression pass.

