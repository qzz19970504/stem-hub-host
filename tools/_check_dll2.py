import os, glob, sysconfig
sp = sysconfig.get_paths()["purelib"]
print("site-packages:", sp)
dlls = glob.glob(os.path.join(sp, "**", "*.dll"), recursive=True)
print(f"Found {len(dlls)} DLLs under site-packages")
for f in sorted(dlls)[:40]:
    print("  ", os.path.relpath(f, sp))
