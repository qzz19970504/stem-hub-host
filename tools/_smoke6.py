"""Verify ctypes can find DLLs in Library/bin."""
import os
from pathlib import Path
import ctypes

LIB_BIN = Path(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")

# Test 1: load with just file name (should fail)
print("Test 1: WinDLL by name only")
for name in ["shiboken6", "Qt6Core", "Qt6Gui"]:
    try:
        ctypes.WinDLL(name + ".dll")
        print(f"  {name}.dll  OK (somehow)")
    except OSError as e:
        print(f"  {name}.dll  FAIL: {e}")

# Test 2: add Library/bin via add_dll_directory
print()
print("Test 2: add_dll_directory then WinDLL by name")
os.add_dll_directory(str(LIB_BIN))
for name in ["shiboken6", "Qt6Core", "Qt6Gui"]:
    try:
        ctypes.WinDLL(name + ".dll")
        print(f"  {name}.dll  OK")
    except OSError as e:
        print(f"  {name}.dll  FAIL: {e}")

# Test 3: add via os.environ PATH
print()
print("Test 3: PATH env then WinDLL by name")
os.environ["PATH"] = str(LIB_BIN) + os.pathsep + os.environ.get("PATH", "")
for name in ["shiboken6", "Qt6Core", "Qt6Gui"]:
    try:
        ctypes.WinDLL(name + ".dll")
        print(f"  {name}.dll  OK")
    except OSError as e:
        print(f"  {name}.dll  FAIL: {e}")

# Test 4: load with full path
print()
print("Test 4: WinDLL with full path")
for name in ["shiboken6", "Qt6Core", "Qt6Gui"]:
    p = LIB_BIN / (name + ".dll")
    try:
        ctypes.WinDLL(str(p))
        print(f"  {name}.dll  OK ({p})")
    except OSError as e:
        print(f"  {name}.dll  FAIL: {e}")
