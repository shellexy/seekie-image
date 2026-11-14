"""PyInstaller 运行时钩子：把系统的 PyGObject / WebKit typelib 找回来。

PyInstaller 里的 Python 是独立的一份，默认不会去读发行版的 dist-packages；
而 GTK、WebKit2 的 typelib 属于发行版，不适合整包复制。这里把常见路径补进
sys.path，让 gi 能从系统加载。找不到也不会报错，PyInstaller 已经带上的那份
gi 会先被导入。
"""

import os
import sys

for _path in (
    "/usr/lib/python3/dist-packages",
    f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages",
    "/usr/lib64/python3/dist-packages",
    "/usr/local/lib/python3/dist-packages",
):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.append(_path)
