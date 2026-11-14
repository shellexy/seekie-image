#!/usr/bin/env bash
# 把源码打成纯 Python 的 .deb。
#
# 打出来的包不冻结 Python、也不带 GTK/WebKit：Python 模块装进
# /usr/lib/python3/dist-packages/seekie_image，启动器直接跑系统 python3，
# 界面依赖交给 python3-webview 和系统的 gir1.2-webkit2-4.1。
#
# 用法：
#   bash packaging/linux/build-deb.sh
#
# 产出：dist/seekie-image_<version>_all.deb
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

command -v dpkg-deb >/dev/null || {
    echo "需要 dpkg-deb" >&2
    exit 1
}

version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' seekie_image/__init__.py)"
[ -n "$version" ] || {
    echo "读不到版本号" >&2
    exit 1
}
maintainer="Shellexy <299902+shellexy@users.noreply.github.com>"
out="$root/dist/seekie-image_${version}_all.deb"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
pkg="$stage/seekie-image"
pydir="$pkg/usr/lib/python3/dist-packages"
mkdir -p \
    "$pkg/DEBIAN" \
    "$pydir" \
    "$pkg/usr/bin" \
    "$pkg/usr/share/applications" \
    "$pkg/usr/share/doc/seekie-image"

# Python 包本体（web/ 和 assets/ 都在里面），不带 __pycache__
cp -a "$root/seekie_image" "$pydir/"
find "$pydir/seekie_image" \
    \( -type d -name __pycache__ \
       -o -type f -name '*.pyc' -o -type f -name '*.pyo' \
       -o -type f -name '*.swp' -o -type f -name '*.swo' \
       -o -type f -name '.DS_Store' \) \
    -exec rm -rf {} +

cat > "$pkg/usr/bin/seekie-image" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 -m seekie_image "$@"
EOF
chmod 755 "$pkg/usr/bin/seekie-image"

# 启动器与图标和 pip 安装时用的是同一份资源
cp "$root/seekie_image/assets/seekie-image.desktop" "$pkg/usr/share/applications/"
for icon in "$root"/seekie_image/assets/hicolor/*/apps/seekie-image.png; do
    size="$(basename "$(dirname "$(dirname "$icon")")")"
    mkdir -p "$pkg/usr/share/icons/hicolor/$size/apps"
    cp "$icon" "$pkg/usr/share/icons/hicolor/$size/apps/"
done

cp "$root/README.md" "$pkg/usr/share/doc/seekie-image/"

# Debian 的 copyright：头部 + 完整的 MIT 正文（每行前加空格，空行写成 .）
{
    echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
    echo "Upstream-Name: seekie-image"
    echo "Source: https://github.com/shellexy/seekie-image"
    echo
    echo "Files: *"
    echo "Copyright: 2026 Shellexy"
    echo "License: MIT"
    sed -e 's/^$/./' -e 's/^/ /' "$root/LICENSE"
} > "$pkg/usr/share/doc/seekie-image/copyright"

for script in postinst postrm; do
    cat > "$pkg/DEBIAN/$script" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
    chmod 755 "$pkg/DEBIAN/$script"
done

installed_size="$(du -sk "$pkg" | cut -f1)"
cat > "$pkg/DEBIAN/control" <<EOF
Package: seekie-image
Version: $version
Architecture: all
Maintainer: $maintainer
Installed-Size: $installed_size
Depends: python3 (>= 3.10), python3-webview (>= 5.0), python3-httpx (>= 0.26), python3-pil (>= 10.0), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: fonts-noto-cjk
Section: graphics
Priority: optional
Homepage: https://github.com/shellexy/seekie-image
Description: Desktop image generator for OpenAI-compatible APIs
 Seekie Image is a small desktop client for OpenAI-compatible image
 generation APIs (official, new-api / one-api and similar gateways).
 It supports reference images, streaming previews, multiple images per
 request and keeps a local history.
EOF

mkdir -p "$root/dist"
rm -f "$out"
dpkg-deb --build --root-owner-group "$pkg" "$out" >/dev/null
echo "已生成 $out"
