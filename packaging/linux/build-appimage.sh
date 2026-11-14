#!/usr/bin/env bash
# 把 PyInstaller 的 dist/seekie-image 打成 AppImage。
#
# 用法（先在仓库根目录跑 PyInstaller）：
#   bash packaging/linux/build-appimage.sh
#
# 产出：dist/Seekie-Image-<version>-x86_64.AppImage
#
# AppImage 里带的是程序自己的 Python 和依赖；GTK / WebKitGTK 仍用系统的，
# 和 .deb 一样需要 gir1.2-gtk-3.0、gir1.2-webkit2-4.1。
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

src="$root/dist/seekie-image"
[ -x "$src/seekie-image" ] || {
    echo "找不到 $src/seekie-image，请先运行 pyinstaller" >&2
    exit 1
}

bash "$root/packaging/linux/trim-bundle.sh" "$src"

version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' seekie_image/__init__.py)"
[ -n "$version" ] || {
    echo "读不到版本号" >&2
    exit 1
}
out="$root/dist/Seekie-Image-${version}-x86_64.AppImage"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
appdir="$stage/AppDir"
mkdir -p "$appdir/usr/lib/seekie-image" "$appdir/usr/bin"

cp -a "$src/." "$appdir/usr/lib/seekie-image/"
ln -s ../lib/seekie-image/seekie-image "$appdir/usr/bin/seekie-image"

cat > "$appdir/AppRun" <<'EOF'
#!/bin/sh
set -e
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/lib/seekie-image/seekie-image" "$@"
EOF
chmod 755 "$appdir/AppRun"

cp "$root/seekie_image/assets/seekie-image.desktop" "$appdir/seekie-image.desktop"
cp "$root/seekie_image/assets/hicolor/256x256/apps/seekie-image.png" "$appdir/seekie-image.png"

tool="${APPIMAGETOOL:-$stage/appimagetool}"
if [ ! -x "$tool" ]; then
    echo "下载 appimagetool…"
    curl -fL --retry 3 --retry-delay 2 \
        -o "$tool" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod 755 "$tool"
fi

export ARCH=x86_64
export VERSION="$version"
# runner 上通常没有 FUSE，让 appimagetool 自己解包再运行
export APPIMAGE_EXTRACT_AND_RUN=1
rm -f "$out"
"$tool" --no-appstream "$appdir" "$out"
chmod 755 "$out"
echo "已生成 $out"
