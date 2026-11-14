# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

Linux 用 GTK/WebKit，Windows 用 WebView2，macOS 用 Cocoa；只带上当前平台的后端，
免得把其它平台的界面库也打进去。
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent.parent  # packaging/pyinstaller -> 仓库根目录

datas = [
    (str(ROOT / "seekie_image" / "web"), "seekie_image/web"),
    (str(ROOT / "seekie_image" / "assets"), "seekie_image/assets"),
]
# pywebview 自己的 JS / WebView2 运行库
datas += collect_data_files("webview")

hiddenimports = ["seekie_image"]
runtime_hooks = []
# PyQt / PySide 不参与打包：Linux 包固定走 GTK，把 Qt 打进来只会白白变大
excludes = [
    "tkinter", "qtpy", "PyQt5", "PyQt6", "PySide2", "PySide6", "shiboken2", "shiboken6",
    # 这些是构建机上装着的开发/分析工具，程序本身不用；不排除的话
    # Ubuntu 的 sitecustomize/apport 会顺着 import 链把 IPython、matplotlib、
    # pylint 的依赖一起拖进来，包会从几十 MB 涨到几百 MB。
    "IPython", "jedi", "parso", "astroid", "pylint",
    "matplotlib", "matplotlib_inline", "numpy", "dateutil", "cycler",
    "kiwisolver", "pyparsing", "fontTools", "contourpy",
    "apport", "apport_python_hook", "problem_report", "sitecustomize",
    "cryptography", "OpenSSL", "bcrypt",
    "traitlets", "psutil", "setproctitle", "rich", "pygments",
    "markdown_it", "mdurl", "yaml", "zstandard", "h2", "hpack", "hyperframe",
]

if sys.platform.startswith("linux"):
    hiddenimports += [
        "webview.platforms.gtk",
        "gi",
        "gi.repository.GLib",
        "gi.repository.Gdk",
        "gi.repository.Gtk",
        "gi.repository.WebKit2",
    ]
    runtime_hooks.append(str(ROOT / "packaging" / "pyinstaller" / "gi_path.py"))
elif sys.platform == "win32":
    hiddenimports += ["webview.platforms.winforms", "webview.platforms.edgechromium"]
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="seekie-image",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "seekie_image" / "assets" / "seekie-image.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="seekie-image",
)
