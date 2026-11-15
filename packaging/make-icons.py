#!/usr/bin/env python3
"""从 seekie_image/assets/icon.png 生成各处要用的图标。

icon.png 是母版（正方形、带透明通道）。改完它以后在仓库根目录执行：

    python packaging/make-icons.py

会重写：

* seekie_image/assets/hicolor/<尺寸>/apps/seekie-image.png（Linux 桌面图标）
* seekie_image/assets/seekie-image.ico（Windows 程序 / 安装包 / 快捷方式图标）

Linux 桌面窗口本身用的是 icon.png，不需要另外生成；网页里的 web/logo.png 是
单独的一张插图，不会被这个脚本改动。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "seekie_image" / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    source = ASSETS / "icon.png"
    if not source.is_file():
        print(f"找不到母版：{source}", file=sys.stderr)
        return 1

    image = Image.open(source).convert("RGBA")
    if image.width != image.height:
        print(f"母版需要是正方形，现在是 {image.width}x{image.height}", file=sys.stderr)
        return 1

    for size in SIZES:
        target = ASSETS / "hicolor" / f"{size}x{size}" / "apps" / "seekie-image.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        image.resize((size, size), Image.Resampling.LANCZOS).save(target, "PNG", optimize=True)
        print(f"已生成 {target.relative_to(ROOT)}")

    ico = ASSETS / "seekie-image.ico"
    image.save(ico, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"已生成 {ico.relative_to(ROOT)}（{', '.join(f'{s}x{s}' for s in SIZES)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
