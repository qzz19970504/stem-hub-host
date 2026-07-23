"""Try loading Qt6Core via NativeLibrary (CLR) and via WinDLL with diagnostic."""
import os
import ctypes
from pathlib import Path
import subprocess

LIB_BIN = Path(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")

# Run powershell to inspect DLL dependencies
ps_script = f"""
$dll = '{LIB_BIN}\\Qt6Core.dll'
# Use the P/Invoke LoadLibraryEx with proper flags
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Loader {{
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr LoadLibraryEx(string lpFileName, IntPtr hReservedNull, uint dwFlags);
    [DllImport("kernel32")]
    public static extern int GetLastError();
}}
"@
$h = [Loader]::LoadLibraryEx($dll, [IntPtr]::Zero, 0x1000)  # LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
Write-Output ("Handle: " + $h)
Write-Output ("Last error: " + [Loader]::GetLastError())
"""

# Try simpler: see if there's a "dependency" tool available, or just use a C tool
# Actually use Python's ctypes.GetLastError
print("Trying ctypes.WinDLL with full path...")
qtcore = LIB_BIN / "Qt6Core.dll"
try:
    h = ctypes.windll.kernel32.LoadLibraryExW(str(qtcore), None, 0x00000010)  # LOAD_WITH_ALTERED_SEARCH_PATH
    print(f"  LoadLibraryEx handle: {h}")
    if not h:
        err = ctypes.GetLastError()
        print(f"  GetLastError: {err}")
except Exception as e:
    print(f"  Exception: {e}")
