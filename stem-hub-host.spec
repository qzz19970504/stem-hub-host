# PyInstaller spec for stem-hub-host
# Build:  pyinstaller --noconfirm stem-hub-host.spec
# Output: dist/stem-hub-host.exe

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve()

block_cipher = None

# A venv created from Conda keeps its matching native runtime under the base
# interpreter's Library/bin. Put it ahead of unrelated Conda installations so
# dependency analysis cannot pair Python 3.11 extensions with Python 3.13 DLLs.
PYTHON_BASE_LIBRARY_BIN = Path(sys.base_prefix) / "Library" / "bin"
if PYTHON_BASE_LIBRARY_BIN.is_dir():
    os.environ["PATH"] = (
        f"{PYTHON_BASE_LIBRARY_BIN}{os.pathsep}{os.environ.get('PATH', '')}"
    )

# 数据文件 (style.qss)
datas = [
    (str(PROJECT_ROOT / "stem_hub_host" / "ui" / "style.qss"), "stem_hub_host/ui"),
    (
        str(PROJECT_ROOT / "stem_hub_host" / "resources" / "fonts"),
        "stem_hub_host/resources/fonts",
    ),
    (
        str(PROJECT_ROOT / "stem_hub_host" / "resources" / "icons"),
        "stem_hub_host/resources/icons",
    ),
]

# 隐式 import (确保所有 widget 模块都被收集)
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSerialPort",
    "PySide6.QtNetwork",
    "stem_hub_host.app",
    "stem_hub_host.branding",
    "stem_hub_host.at_protocol",
    "stem_hub_host.controller",
    "stem_hub_host.data_buffer",
    "stem_hub_host.fake_firmware",
    "stem_hub_host.main",
    "stem_hub_host.models",
    "stem_hub_host.serial_worker",
    "stem_hub_host.transport",
    "stem_hub_host.ui.main_window",
    "stem_hub_host.ui.native_chrome",
    "stem_hub_host.ui.fonts",
    "stem_hub_host.ui.stylesheet",
    "stem_hub_host.ui.tab1_console",
    "stem_hub_host.ui.tab2_plot",
    "stem_hub_host.ui.tab3_passthrough",
    "stem_hub_host.ui.theme",
    "stem_hub_host.ui.widgets.at_console",
    "stem_hub_host.ui.widgets.battery_card",
    "stem_hub_host.ui.widgets.charge_mode_card",
    "stem_hub_host.ui.widgets.fault_indicator",
    "stem_hub_host.ui.widgets.led_dot",
    "stem_hub_host.ui.widgets.motor_card",
    "stem_hub_host.ui.widgets.passthrough_panel",
    "stem_hub_host.ui.widgets.plot_widget",
    "stem_hub_host.ui.widgets.serial_bar",
    "stem_hub_host.ui.widgets.temp_grid",
    "stem_hub_host.ui.widgets.toggle_switch",
    "shiboken6",
]

a = Analysis(
    [str(PROJECT_ROOT / "stem_hub_host" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除没用的大库, 让 .exe 小一点.
        # 警告: pyqtgraph 内部 import xml.etree / pydoc 等 stdlib, 别排这些.
        # stdlib 本身不大, 别手贱.
        "tkinter",
        "unittest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="stem-hub-host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # GUI 程序, 不弹 console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(
        PROJECT_ROOT
        / "stem_hub_host"
        / "resources"
        / "icons"
        / "app_icon.ico"
    ),
)
