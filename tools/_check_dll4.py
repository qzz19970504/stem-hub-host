import os
p = os.path.dirname(os.__file__) if False else None
import PySide6
init_py = PySide6.__file__
print("PySide6 __init__.py:", init_py)
print()
print("=== first 50 lines ===")
with open(init_py, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if i > 60: break
        print(f"{i:3}: {line.rstrip()}")
