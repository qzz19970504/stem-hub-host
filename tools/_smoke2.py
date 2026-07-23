"""Pre-import hook to add conda Library/bin to DLL search path."""
import os, sys
from pathlib import Path

# This file lives at D:/Codes/STM32/stem-hub-host/tools/_smoke2.py
# The conda env path is hard-coded for the smoke test only.
conda_bin = Path(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")
conda_shiboken6 = conda_bin / "shiboken6"

if conda_bin.exists():
    os.add_dll_directory(str(conda_bin))
if conda_shiboken6.exists():
    os.add_dll_directory(str(conda_shiboken6))

# Now do the real import
from PySide6 import QtCore, QtSerialPort, QtWidgets
import pyqtgraph
import numpy as np
print('PySide6', QtCore.__version__)
print('pyqtgraph', pyqtgraph.__version__)
print('numpy', np.__version__)
print('QtSerialPort ok:', hasattr(QtSerialPort, 'QSerialPort'))
