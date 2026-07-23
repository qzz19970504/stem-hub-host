"""Check if shiboken6 itself can be imported when Library/bin is on DLL path."""
import os
from pathlib import Path

CONDA_ENV = Path(r"C:\Users\44575\.conda\envs\stem-hub-host")
conda_bin = CONDA_ENV / "Library" / "bin"
print("Adding DLL dir:", conda_bin, "exists:", conda_bin.exists())
os.add_dll_directory(str(conda_bin))

print("Importing shiboken6...")
try:
    import shiboken6
    print("shiboken6 ok, file:", shiboken6.__file__)
except Exception as e:
    print("shiboken6 FAIL:", type(e).__name__, e)
