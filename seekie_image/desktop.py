"""把启动器和图标装进当前用户的 XDG 目录（Linux）。

`pip install` 时 setup.py 里的 data_files 是相对安装前缀放的：`pip install --user` 会落在
~/.local/share，桌面环境能看到；但装在虚拟环境或 pipx 里时，文件在环境自己的 share/ 下，
应用菜单里不会出现。这个模块把同一份 .desktop 和图标复制到用户目录，并把 Exec 写成
当前这份安装的绝对路径，所以哪种装法都能用：

    seekie-image --install-desktop
    seekie-image --uninstall-desktop
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

APP_ID = "seekie-image"
ASSETS = Path(__file__).parent / "assets"
ICON = ASSETS / "icon.png"
_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _targets() -> tuple[Path, list[tuple[Path, Path]]]:
    """(.desktop 的目标路径, [(图标源文件, 目标路径), ...])"""
    home = _data_home()
    icons = [
        (source, home / "icons" / source.relative_to(ASSETS))
        for source in sorted((ASSETS / "hicolor").glob(f"*/apps/{APP_ID}.png"))
    ]
    return home / "applications" / f"{APP_ID}.desktop", icons


def launch_command() -> list[str]:
    """启动当前这份安装的命令行。"""
    candidates = [Path(sys.executable).parent / APP_ID]
    try:
        candidates.append(Path(sysconfig.get_path("scripts", f"{os.name}_user")) / APP_ID)
    except KeyError:
        pass
    for script in candidates:
        if script.is_file() and os.access(script, os.X_OK):
            return [str(script)]
    main_py = Path(__file__).resolve().parent.parent / "main.py"  # 没安装、直接在源码目录里跑
    if main_py.is_file():
        return [sys.executable, str(main_py)]
    return [sys.executable, "-m", "seekie_image"]


def _quote(arg: str) -> str:
    """按 Desktop Entry 规范给 Exec 里的参数加引号。"""
    arg = arg.replace("%", "%%")
    if not any(ch in _RESERVED for ch in arg):
        return arg
    for ch in '\\"`$':
        arg = arg.replace(ch, "\\" + ch)
    return f'"{arg}"'


def _refresh_caches() -> None:
    home = _data_home()
    for command in (
        ["update-desktop-database", str(home / "applications")],
        ["gtk-update-icon-cache", "-q", "-t", "-f", str(home / "icons" / "hicolor")],
    ):
        if shutil.which(command[0]):
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def install() -> int:
    if not sys.platform.startswith("linux"):
        print("--install-desktop 只用于 Linux。")
        return 1
    desktop, icons = _targets()
    command = launch_command()
    lines = []
    for line in (ASSETS / f"{APP_ID}.desktop").read_text("utf-8").splitlines():
        if line.startswith("Exec="):
            # TryExec：这份安装被删掉以后，启动器会自动从菜单里消失
            lines.append(f"TryExec={command[0]}")
            line = "Exec=" + " ".join(_quote(part) for part in command)
        lines.append(line)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text("\n".join(lines) + "\n", "utf-8")
    for source, target in icons:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    _refresh_caches()
    print(f"已安装启动器：{desktop}")
    print(f"已安装图标：{_data_home() / 'icons' / 'hicolor'}（{len(icons)} 个尺寸）")
    print(f"启动命令：{' '.join(command)}")
    return 0


def uninstall() -> int:
    desktop, icons = _targets()
    removed = 0
    for path in [desktop, *(target for _, target in icons)]:
        if path.exists():
            path.unlink()
            removed += 1
    _refresh_caches()
    print(f"已移除 {removed} 个文件。" if removed else "没有找到已安装的启动器。")
    return 0
