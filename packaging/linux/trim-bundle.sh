#!/usr/bin/env bash
# 去掉 PyInstaller 顺带收进来的桌面图标主题。
#
# PyInstaller 的 GTK 钩子会把构建机 /usr/share/icons 下的所有主题都复制进来，
# 在 Ubuntu 上光 Breeze、Oxygen、Humanity 这些光标和图标就有 200 MB 以上。
# 程序界面是 HTML/CSS，窗口图标由程序自己设置，保留 hicolor 和 Adwaita 就够了。
#
# 用法：bash packaging/linux/trim-bundle.sh dist/seekie-image
set -euo pipefail

app="${1:?用法: trim-bundle.sh <PyInstaller 输出目录>}"
icons="$app/_internal/share/icons"
[ -d "$icons" ] || exit 0

find "$icons" -mindepth 1 -maxdepth 1 -type d \
    ! -name hicolor ! -name Adwaita -exec rm -rf {} +

echo "已精简图标主题，当前剩余：$(du -sh "$icons" | cut -f1)"
