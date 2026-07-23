import os, glob
import PySide6
p = os.path.dirname(PySide6.__file__)
print("PySide6 path:", p)
for f in sorted(glob.glob(os.path.join(p, "*.dll"))):
    print("  ", os.path.basename(f))
