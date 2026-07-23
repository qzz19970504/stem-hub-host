"""Walk Qt6Core's imports using PE parsing, or use a simpler check.

Try loading each potential dependency of Qt6Core and see which fails.
Qt6Core.dll typical deps:
- KERNEL32.dll, USER32.dll, GDI32.dll
- msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll, concrt140.dll
- api-ms-win-*.dll (UCRT)
- IPHLPAPI.DLL, WS2_32.DLL, DNSAPI.DLL (networking)
- d3d11.dll, dxgi.dll, etc. (graphics)
- libcrypto-3-x64.dll, libssl-3-x64.dll (for QtNetwork)
- msvcp140_1.dll, msvcp140_2.dll
- double-conversion.dll

Let's try a few critical ones.
"""
import os
import ctypes
from pathlib import Path

LIB_BIN = Path(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")

# Walk env bin and try loading every DLL
print("Scanning all DLLs in env for loadability...")
ok, fail = [], []
for dll in sorted(LIB_BIN.glob("*.dll")):
    try:
        h = ctypes.windll.kernel32.LoadLibraryExW(str(dll), None, 0x00000008)  # LOAD_LIBRARY_AS_DATAFILE
        # Actually use real load
        h = ctypes.windll.kernel32.LoadLibraryExW(str(dll), None, 0x00000010)  # LOAD_WITH_ALTERED_SEARCH_PATH
        if h:
            ok.append(dll.name)
            ctypes.windll.kernel32.FreeLibrary(h)
        else:
            err = ctypes.GetLastError()
            fail.append((dll.name, err))
    except Exception as e:
        fail.append((dll.name, str(e)))

print(f"OK: {len(ok)}, FAIL: {len(fail)}")
print("Failed DLLs (first 30):")
for name, err in fail[:30]:
    print(f"  {name}: error {err}")
