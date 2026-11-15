"""PyInstaller 运行时钩子：让冻结后的 Windows 版能找到 pythonnet 和 WebView2。

pywebview 的 EdgeChromium 后端在 import 时就会 `import clr`；如果没有告诉
pythonnet 去哪找 Python.Runtime.dll、python3xx.dll 和 WebView2 的 DLL，进程会在
CLR 里直接崩掉（退出码 0xE0434352），窗口根本不出现。

这个钩子在 main.py 之前执行，把这个几路径补进 PYTHONNET_PYDLL、PATH 和
os.add_dll_directory。
"""

import os
import sys

if sys.platform == "win32":
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    exe_dir = os.path.dirname(sys.executable)
    dll_name = f"python{sys.version_info.major}{sys.version_info.minor}.dll"

    def find_file(name: str, *hints: str) -> str | None:
        for hint in hints:
            candidate = os.path.join(base, hint, name)
            if os.path.isfile(candidate):
                return candidate
        for root, _dirs, files in os.walk(base):
            if name in files:
                return os.path.join(root, name)
        return None

    pydll = find_file(dll_name)
    runtime_dll = find_file("Python.Runtime.dll", os.path.join("pythonnet", "runtime"))

    os.environ["PYTHONNET_RUNTIME"] = "netfx"
    if pydll:
        os.environ["PYTHONNET_PYDLL"] = pydll

    search_dirs = []
    for path in (
        base,
        exe_dir,
        os.path.join(base, "pythonnet", "runtime"),
        os.path.dirname(runtime_dll) if runtime_dll else None,
        os.path.dirname(pydll) if pydll else None,
        os.path.join(base, "webview", "lib"),
        os.path.join(base, "webview", "lib", "runtimes", "win-x64", "native"),
        os.path.join(base, "webview", "lib", "runtimes", "win-x86", "native"),
        os.path.join(base, "webview", "lib", "runtimes", "win-arm64", "native"),
    ):
        if path and os.path.isdir(path) and path not in search_dirs:
            search_dirs.append(path)

    os.environ["PATH"] = os.pathsep.join(
        search_dirs + [p for p in os.environ.get("PATH", "").split(os.pathsep) if p and p not in search_dirs]
    )
    if hasattr(os, "add_dll_directory"):
        # 句柄必须留着，回收了目录就会从 DLL 搜索路径消失
        _dll_dir_handles = []
        for path in search_dirs:
            try:
                _dll_dir_handles.append(os.add_dll_directory(path))
            except OSError:
                pass
