"""手工构造 PE32+ forwarder DLL。

把 RoGetActivationFactory 和 RoOriginateLanguageException 转发到 combase.dll。
这些 API 缺失是 Win10 早期补丁未打导致, 但 combase.dll 里实际有实现。

构造策略: 最小 PE32+ 文件
- DOS stub + PE header
- 1 个 .edata section, 装 export directory + 字符串 + forwarder string
- 2 个导出符号都 forward 到 combase.RoXxx

参考 PE/COFF 规范 (Microsoft) 第 8 章节 "The .edata Section"
"""
import os
import struct
import time

OUTPUT_DIR = r"C:\Users\44575\.conda\envs\stem-hub-host\Library\bin"

# ---- 通用常量 ----
DOS_HEADER_SIZE = 64
PE_SIG_SIZE = 4
FILE_HEADER_SIZE = 20
OPTIONAL_HEADER64_SIZE = 240  # PE32+
SECTION_HEADER_SIZE = 40
FILE_ALIGNMENT = 0x200
SECTION_ALIGNMENT = 0x1000
IMAGE_SIZEOF_HEADER_ALIGN = 0x400  # PE header 总大小对齐到 0x400


def align_up(x, align):
    return (x + align - 1) & ~(align - 1)


def build_forwarder_dll(dll_filename, exports):
    """Build a minimal PE32+ forwarder DLL.

    exports: list of (symbol_name, target_dll, target_symbol)
             例: [("RoGetActivationFactory", "combase.dll", "RoGetActivationFactory")]
    """
    # ---- 准备字符串数据 ----
    # .edata 段布局:
    #   [0..N)                 : export directory (40 bytes)
    #   [N..)                  : DLL name (forwarder DLL 名字)
    #   [..]                   : function name pointers (RVA array, 4 bytes each)
    #   [..]                   : name ordinals (2 bytes each)
    #   [..]                   : function address table (4 bytes each, 这里填 forwarder string RVA)
    #   [..]                   : function name strings (null-terminated)
    #   [..]                   : forwarder strings ("combase.RoXxx", null-terminated)

    num_exports = len(exports)

    # 偏移计算
    exp_dir_offset = 0
    exp_dir_size = 40
    dll_name_offset = exp_dir_offset + exp_dir_size  # forwarder DLL 名字字符串位置

    # 先把 dll filename 编码
    dll_name_bytes = dll_filename.encode("ascii") + b"\x00"

    function_names_offset = dll_name_offset + len(dll_name_bytes)
    # function name RVA table (num_exports entries, 4 bytes each)
    function_names_rva_table_offset = function_names_offset
    function_names_rva_table_size = num_exports * 4

    # name ordinals table
    name_ordinals_offset = function_names_rva_table_offset + function_names_rva_table_size
    name_ordinals_size = num_exports * 2

    # function address table (这里每个 entry 是个 RVA 指向 forwarder string)
    func_addr_table_offset = name_ordinals_offset + name_ordinals_size
    func_addr_table_size = num_exports * 4

    # function name strings (null-terminated)
    func_name_strs_offset = func_addr_table_offset + func_addr_table_size
    func_name_strs_data = b""
    name_offsets = []  # 每个 name string 在 section 里的 offset
    for sym_name, _, _ in exports:
        name_offsets.append(func_name_strs_offset + len(func_name_strs_data))
        func_name_strs_data += sym_name.encode("ascii") + b"\x00"

    # forwarder strings
    forwarder_strs_offset = func_name_strs_offset + len(func_name_strs_data)
    forwarder_strs_data = b""
    forwarder_str_offsets = []
    for _, target_dll, target_sym in exports:
        # PE forwarder 字符串格式: "ModuleName.SymbolName"
        # 注意 ModuleName **不带** .dll 后缀! 例如 "ucrtbase._Exit", "combase.RoGetActivationFactory"
        fwd_str = f"{target_dll}.{target_sym}"
        forwarder_str_offsets.append(forwarder_strs_offset + len(forwarder_strs_data))
        forwarder_strs_data += fwd_str.encode("ascii") + b"\x00"

    # section data 总大小
    section_data_size = forwarder_strs_offset + len(forwarder_strs_data)
    # 对齐
    section_data_size_aligned = align_up(section_data_size, FILE_ALIGNMENT)
    padding = section_data_size_aligned - section_data_size

    # ---- 构造 .edata section 原始数据 ----
    edata_raw = bytearray(section_data_size_aligned)

    # Export Directory
    edata = bytearray(40)
    struct.pack_into("<I", edata, 0, 0)  # Characteristics
    struct.pack_into("<I", edata, 4, int(time.time()) & 0xFFFFFFFF)  # TimeDateStamp
    struct.pack_into("<H", edata, 8, 0)  # MajorVersion
    struct.pack_into("<H", edata, 10, 0)  # MinorVersion
    struct.pack_into(
        "<I", edata, 12, 0x1000 + dll_name_offset
    )  # Name RVA (相对 image base; 段 RVA 0x1000)
    struct.pack_into("<I", edata, 16, 1)  # OrdinalBase
    struct.pack_into("<I", edata, 20, num_exports)  # NumberOfFunctions
    struct.pack_into("<I", edata, 24, num_exports)  # NumberOfNames
    struct.pack_into(
        "<I", edata, 28, 0x1000 + func_addr_table_offset
    )  # AddressOfFunctions RVA -> function address table
    struct.pack_into(
        "<I", edata, 32, 0x1000 + function_names_rva_table_offset
    )  # AddressOfNames RVA -> name RVA array (each entry points to a name string)
    struct.pack_into(
        "<I", edata, 36, 0x1000 + name_ordinals_offset
    )  # AddressOfNameOrdinals RVA
    edata_raw[exp_dir_offset : exp_dir_offset + 40] = edata

    # DLL name
    edata_raw[dll_name_offset : dll_name_offset + len(dll_name_bytes)] = dll_name_bytes

    # function names RVA table (RVA relative to image base; 段在 0x1000)
    for i, name_off in enumerate(name_offsets):
        rva = 0x1000 + name_off
        struct.pack_into("<I", edata_raw, function_names_rva_table_offset + i * 4, rva)

    # name ordinals (每个 export i 对应 ordinal i, 因为 OrdinalBase=1)
    for i in range(num_exports):
        struct.pack_into("<H", edata_raw, name_ordinals_offset + i * 2, i)

    # function address table (指向 forwarder string)
    for i, fwd_off in enumerate(forwarder_str_offsets):
        rva = 0x1000 + fwd_off
        struct.pack_into("<I", edata_raw, func_addr_table_offset + i * 4, rva)

    # function name strings
    edata_raw[
        func_name_strs_offset : func_name_strs_offset + len(func_name_strs_data)
    ] = func_name_strs_data

    # forwarder strings
    edata_raw[
        forwarder_strs_offset : forwarder_strs_offset + len(forwarder_strs_data)
    ] = forwarder_strs_data

    # ---- DOS Header ----
    dos_header = bytearray(DOS_HEADER_SIZE)
    dos_header[0:2] = b"MZ"
    # e_lfanew 指向 PE signature (在 file 0x80 位置以避免 stub)
    pe_offset = 0x80
    struct.pack_into("<I", dos_header, 0x3C, pe_offset)

    # ---- PE Signature ----
    pe_sig = b"PE\0\0"

    # ---- File Header ----
    file_header = bytearray(FILE_HEADER_SIZE)
    struct.pack_into("<H", file_header, 0, 0x8664)  # Machine = AMD64
    struct.pack_into("<H", file_header, 2, num_exports)  # NumberOfSections
    struct.pack_into("<I", file_header, 4, int(time.time()) & 0xFFFFFFFF)  # TimeDateStamp
    struct.pack_into(
        "<I", file_header, 8, 0
    )  # PointerToSymbolTable (deprecated, 0 for image)
    struct.pack_into("<I", file_header, 12, 0)  # NumberOfSymbols
    struct.pack_into(
        "<H", file_header, 16, OPTIONAL_HEADER64_SIZE
    )  # SizeOfOptionalHeader
    struct.pack_into("<H", file_header, 18, 0x2022)  # Characteristics: EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE | DLL

    # ---- Optional Header (PE32+) ----
    opt_header = bytearray(OPTIONAL_HEADER64_SIZE)
    struct.pack_into("<H", opt_header, 0, 0x020B)  # Magic: PE32+
    opt_header[2] = 14  # MajorLinkerVersion
    opt_header[3] = 0  # MinorLinkerVersion
    struct.pack_into(
        "<I", opt_header, 4, 0
    )  # SizeOfCode (unfilled; this is not COFF obj)
    struct.pack_into("<I", opt_header, 8, section_data_size_aligned)  # SizeOfInitializedData
    struct.pack_into("<I", opt_header, 12, 0)  # SizeOfUninitializedData
    # AddressOfEntryPoint = 0 (forwarder DLL no entry, 必须为 0!)
    struct.pack_into("<I", opt_header, 16, 0)  # AddressOfEntryPoint
    struct.pack_into("<I", opt_header, 20, 0x1000)  # BaseOfCode
    # ImageBase: 64-bit DLL default 0x180000000
    struct.pack_into("<Q", opt_header, 24, 0x180000000)  # ImageBase
    struct.pack_into("<I", opt_header, 32, SECTION_ALIGNMENT)  # SectionAlignment
    struct.pack_into("<I", opt_header, 36, FILE_ALIGNMENT)  # FileAlignment
    struct.pack_into("<H", opt_header, 40, 6)  # MajorOperatingSystemVersion
    struct.pack_into("<H", opt_header, 42, 0)  # MinorOperatingSystemVersion
    struct.pack_into("<H", opt_header, 44, 0)  # MajorImageVersion
    struct.pack_into("<H", opt_header, 46, 0)  # MinorImageVersion
    struct.pack_into("<H", opt_header, 48, 6)  # MajorSubsystemVersion
    struct.pack_into("<H", opt_header, 50, 0)  # MinorSubsystemVersion
    struct.pack_into("<I", opt_header, 52, 0)  # Win32VersionValue (reserved)
    # SizeOfImage: 一个 .edata 段,虚拟对齐后
    size_of_image = 0x1000 + align_up(section_data_size, SECTION_ALIGNMENT)
    struct.pack_into("<I", opt_header, 56, size_of_image)
    size_of_headers = align_up(
        pe_offset + PE_SIG_SIZE + FILE_HEADER_SIZE + OPTIONAL_HEADER64_SIZE + SECTION_HEADER_SIZE,
        FILE_ALIGNMENT,
    )
    struct.pack_into("<I", opt_header, 60, size_of_headers)  # SizeOfHeaders
    struct.pack_into("<I", opt_header, 64, 0)  # CheckSum (can be 0 for DLL)
    struct.pack_into("<H", opt_header, 68, 3)  # Subsystem = Windows CUI (3) or GUI (2); use CUI
    struct.pack_into("<H", opt_header, 70, 0x4160)  # DllCharacteristics: DYNAMIC_BASE | NX_COMPAT | HIGH_ENTROPY_VA | GUARD_CF
    # SizeOfStackReserve, SizeOfStackCommit, SizeOfHeapReserve, SizeOfHeapCommit
    struct.pack_into("<Q", opt_header, 72, 0x100000)  # SizeOfStackReserve
    struct.pack_into("<Q", opt_header, 80, 0x1000)  # SizeOfStackCommit
    struct.pack_into("<Q", opt_header, 88, 0x100000)  # SizeOfHeapReserve
    struct.pack_into("<Q", opt_header, 96, 0x1000)  # SizeOfHeapCommit
    struct.pack_into("<I", opt_header, 104, 0)  # LoaderFlags
    struct.pack_into("<I", opt_header, 108, 16)  # NumberOfRvaAndSizes
    # Data Directories (16 entries, 8 bytes each = 128 bytes, start at offset 112)
    # 我们只有 Export Directory (index 0).
    # 注意: EAT entry 在 ExportDir VA..VA+Size 范围内时才被认作 forwarder string。
    # 所以 Size 必须覆盖整个 .edata 段, 否则 loader 不会把 EAT entry 当 forwarder。
    struct.pack_into("<I", opt_header, 112, 0x1000)  # Export Directory VA
    struct.pack_into("<I", opt_header, 116, section_data_size)  # Export Directory Size (整个 .edata 段)

    # ---- Section Header (.edata) ----
    section_header = bytearray(SECTION_HEADER_SIZE)
    section_header[0:6] = b".edata"
    # VirtualSize / VirtualAddress
    struct.pack_into("<I", section_header, 8, section_data_size)  # VirtualSize
    struct.pack_into("<I", section_header, 12, 0x1000)  # VirtualAddress
    struct.pack_into("<I", section_header, 16, section_data_size_aligned)  # SizeOfRawData
    struct.pack_into("<I", section_header, 20, size_of_headers)  # PointerToRawData
    struct.pack_into(
        "<I", section_header, 24, 0
    )  # PointerToRelocations
    struct.pack_into("<I", section_header, 28, 0)  # PointerToLineNumbers
    struct.pack_into("<H", section_header, 32, 0)  # NumberOfRelocations
    struct.pack_into("<H", section_header, 34, 0)  # NumberOfLineNumbers
    struct.pack_into(
        "<I", section_header, 36, 0x40000040
    )  # Characteristics: INITIALIZED_DATA | READ

    # ---- 拼装文件 ----
    # headers: DOS + padding to pe_offset + PE sig + FileHeader + OptionalHeader + SectionHeader
    # 总 header 大小 = size_of_headers, headers 区域要 0-padding 到 size_of_headers
    headers = bytearray(size_of_headers)
    headers[0:DOS_HEADER_SIZE] = dos_header
    headers[pe_offset : pe_offset + PE_SIG_SIZE] = pe_sig
    file_header_offset = pe_offset + PE_SIG_SIZE
    headers[
        file_header_offset : file_header_offset + FILE_HEADER_SIZE
    ] = file_header
    opt_offset = file_header_offset + FILE_HEADER_SIZE
    headers[opt_offset : opt_offset + OPTIONAL_HEADER64_SIZE] = opt_header
    sec_offset = opt_offset + OPTIONAL_HEADER64_SIZE
    headers[sec_offset : sec_offset + SECTION_HEADER_SIZE] = section_header

    # 文件内容: headers (size_of_headers bytes) + edata raw (section_data_size_aligned bytes)
    out_path = os.path.join(OUTPUT_DIR, dll_filename)
    with open(out_path, "wb") as f:
        f.write(headers)
        f.write(edata_raw)

    print(f"Wrote {out_path} ({os.path.getsize(out_path)} bytes)")
    return out_path


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # api-ms-win-core-winrt-l1-1-0.dll: RoGetActivationFactory
    # 注意: PE forwarder 字符串里 module name **不带** .dll 后缀
    build_forwarder_dll(
        "api-ms-win-core-winrt-l1-1-0.dll",
        [
            ("RoGetActivationFactory", "combase", "RoGetActivationFactory"),
        ],
    )

    # api-ms-win-core-winrt-error-l1-1-1.dll: RoOriginateLanguageException
    build_forwarder_dll(
        "api-ms-win-core-winrt-error-l1-1-1.dll",
        [
            ("RoOriginateLanguageException", "combase", "RoOriginateLanguageException"),
        ],
    )

    print("Done.")
