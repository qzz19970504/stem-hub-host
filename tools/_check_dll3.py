import os, glob
root = r"C:\Users\44575\.conda\envs\stem-hub-host"
print("Searching for DLLs under env root...")
dlls = glob.glob(os.path.join(root, "**", "*.dll"), recursive=True)
print(f"Found {len(dlls)} DLLs")
for f in sorted(dlls)[:60]:
    rel = os.path.relpath(f, root).replace("\\", "/")
    sz = os.path.getsize(f)
    print(f"  {rel}  ({sz//1024} KB)")
