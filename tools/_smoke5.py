"""Find which DLL is missing when loading QtCore."""
import os, sys
from pathlib import Path

CONDA_ENV = Path(r"C:\Users\44575\.conda\envs\stem-hub-host")
conda_bin = CONDA_ENV / "Library" / "bin"
print("Adding DLL dir:", conda_bin)
os.add_dll_directory(str(conda_bin))

# Now, list of known Qt DLLs and verify each is reachable
import ctypes
for name in ["Qt6Core", "Qt6Gui", "Qt6Widgets", "shiboken6"]:
    try:
        h = ctypes.WinDLL(name + ".dll")
        print(f"  {name}.dll  OK  ->", ctypes.util.find_library(name))
        del h
    except OSError as e:
        print(f"  {name}.dll  FAIL: {e}")

print()
print("Now try importing shiboken6.Shiboken...")
import shiboken6
print("ok:", shiboken6.__file__)

print("Now try import PySide6...")
import PySide6
print("ok:", PySide6.__file__)

print("Now try PySide6.QtCore...")
try:
    from PySide6 import QtCore
    print("ok:", QtCore.__version__)
except Exception as e:
    print("FAIL:", type(e).__name__, e)
    import traceback
    traceback.print_exc()
