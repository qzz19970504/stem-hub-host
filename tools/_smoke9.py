"""Diagnose what's restricted in this environment."""
import ctypes
import os
import sys
from pathlib import Path

print(f"Python: {sys.executable}")
print(f"User: {os.environ.get('USERNAME')}, Domain: {os.environ.get('USERDOMAIN')}")
print(f"Session: {os.environ.get('SESSIONNAME')}")
print()

# Try basic kernel32 calls
print("Kernel32 basic test:")
k32 = ctypes.windll.kernel32
print(f"  GetModuleHandleA('kernel32.dll'): {k32.GetModuleHandleA(b'kernel32.dll')}")

# Try a known system DLL
print()
print("Loading well-known system DLLs:")
for name in ["kernel32.dll", "user32.dll", "advapi32.dll", "gdi32.dll", "ws2_32.dll", "iphlpapi.dll"]:
    try:
        h = ctypes.WinDLL(name)
        print(f"  {name}  OK")
    except OSError as e:
        print(f"  {name}  FAIL: {e}")

# Check if this is a sandboxed process
print()
print("Process info:")
print(f"  Current dir: {os.getcwd()}")
print(f"  Temp dir exists: {os.path.exists(os.environ.get('TEMP', ''))}")
print(f"  AppData exists: {os.path.exists(os.environ.get('APPDATA', ''))}")

# Check if we can create a window (the real test)
print()
print("Can we create a hidden window?")
try:
    import ctypes.wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = user32.CreateWindowExW(0, "Static", "test", 0, 0, 0, 0, 0, None, None, None, None)
    if hwnd:
        print(f"  CreateWindowExW handle: {hwnd}")
        user32.DestroyWindow(hwnd)
    else:
        err = ctypes.get_last_error()
        print(f"  CreateWindowExW FAIL: error {err}")
except Exception as e:
    print(f"  FAIL: {e}")
