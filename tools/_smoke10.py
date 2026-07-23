"""Parse PE imports of Qt6Core.dll to see what DLLs it needs."""
import struct, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

LIB_BIN = Path(r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin")
qtcore = LIB_BIN / "Qt6Core.dll"
data = qtcore.read_bytes()

# DOS header
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
# PE header signature + COFF header
sig = data[e_lfanew:e_lfanew+4]
assert sig == b"PE\0\0", f"Not a PE file: {sig!r}"
coff = e_lfanew + 4
machine, num_sections, _, _, _, opt_hdr_size, characteristics = struct.unpack_from("<HHIIIHH", data, coff)
print(f"Machine: 0x{machine:X}, Sections: {num_sections}, OptHdrSize: {opt_hdr_size}")
# Optional header
opt = coff + 20
magic = struct.unpack_from("<H", data, opt)[0]
print(f"Optional header magic: 0x{magic:X} ({'PE32+' if magic==0x20b else 'PE32'})")
# Data directory starts at opt + 96 for PE32+ / opt + 92 for PE32
dd_offset = opt + (112 if magic == 0x20b else 96)
imports_rva, imports_size = struct.unpack_from("<II", data, dd_offset + 8)[0:2]  # index 1 = import table
print(f"Import table RVA: 0x{imports_rva:X}, size: {imports_size}")

# Need section table to convert RVA to file offset
sec_table = opt + opt_hdr_size
sections = []
for i in range(num_sections):
    base = sec_table + 40 * i
    name = data[base:base+8].rstrip(b"\0").decode("ascii", errors="replace")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, base + 8)
    sections.append((name, vaddr, vsize, raddr, rsize))

def rva_to_offset(rva):
    for name, vaddr, vsize, raddr, rsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None

# Walk import descriptors
print()
print("Imports of Qt6Core.dll:")
i = 0
seen = set()
off = rva_to_offset(imports_rva)
while off is not None:
    ilt_rva, _, _, _, _, name_rva, ifa_rva = struct.unpack_from("<IIIII II", data, off)[:7]
    if ilt_rva == 0 and name_rva == 0:
        break
    name_off = rva_to_offset(name_rva)
    if name_off is None:
        break
    name = b""
    j = name_off
    while data[j] != 0:
        name += bytes([data[j]])
        j += 1
    name = name.decode("ascii", errors="replace")
    print(f"  {name}")
    seen.add(name.lower())
    off += 20

# Also look at delay-load imports (data dir index 13)
print()
print("Also check delay-load imports and bound imports...")
# Check what api-ms-win-*.dll look like (typical UCRT) and confirm system32 has them
import os
test_dlls = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "ucrtbase.dll"]
print("System32 check:")
for d in test_dlls:
    p = Path("C:/Windows/System32") / d
    print(f"  {d}: exists={p.exists()}, size={p.stat().st_size if p.exists() else 0}")

# Check api-ms-win-core-* presence
print()
print("api-ms-win-core in System32 sample:")
for d in os.listdir("C:/Windows/System32"):
    if d.startswith("api-ms-win-core-"):
        print(f"  {d}")
        break
