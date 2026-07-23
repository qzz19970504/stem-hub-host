"""Smoke test for PySide6 with hardlinked conda env.
Adds Library/bin to DLL search path BEFORE importing shiboken6 / PySide6.
"""
import os
from pathlib import Path

# conda 25 uses hardlinks for python.exe, so the env wrapper that would
# normally prepend Library/bin to PATH is missing. Fix it manually.
CONDA_ENV = Path(os.environ.get("CONDA_PREFIX", r"C:\Users\44575\.conda\envs\stem-hub-host"))
conda_bin = CONDA_ENV / "Library" / "bin"
if conda_bin.exists():
    os.add_dll_directory(str(conda_bin))

# Now do the real imports
from PySide6 import QtCore, QtSerialPort, QtWidgets
import pyqtgraph
import numpy as np

print("PySide6", QtCore.__version__)
print("pyqtgraph", pyqtgraph.__version__)
print("numpy", np.__version__)
print("QtSerialPort ok:", hasattr(QtSerialPort, "QSerialPort"))
print("QtWidgets ok:", hasattr(QtWidgets, "QApplication"))
