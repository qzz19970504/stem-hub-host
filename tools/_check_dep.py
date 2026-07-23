"""Test: does shiboken6 find Qt6Core if Library/bin is added?"""
import os
from pathlib import Path

# 1. Add conda Library/bin (where Qt6Core.dll lives) and shiboken6/
os.add_dll_directory(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")
os.add_dll_directory(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin\shiboken6")

# 2. Try importing in the same order PySide6/__init__.py does
print("Loading shiboken6...")
import shiboken6
print("shiboken6 ok, version:", getattr(shiboken6, "__version__", "?"))

print("Loading PySide6.QtCore...")
from PySide6 import QtCore
print("QtCore ok, version:", QtCore.__version__)
