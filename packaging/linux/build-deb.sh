#!/usr/bin/env bash
# 把 PyInstaller 的 dist/seekie-image 打成 .deb。
#
# 用法（先在仓库根目录跑 PyInstaller）：
#   bash packaging/linux/build-deb.sh
#
# 产出：dist/seekie-image_<version>_<arch>.deb
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

src="$root/dist/seekie-image"
[ -x "$src/seekie-image" ] || {
    echo "找不到 $src/seekie-image，请先运行 pyinstaller" >&2
    exit 1
}
command -v dpkg-deb >/dev/null || {
    echo "需要 dpkg-deb" >&2
    exit 1
}

bash "$root/packaging/linux/trim-bundle.sh" "$src"

version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' seekie_image/__init__.py)"
[ -n "$version" ] || {
    echo "读不到版本号" >&2
    exit 1
}
arch="$(dpkg --print-architecture)"
maintainer="Shellexy <299902+shellexy@users.noreply.github.com>"
out="$root/dist/seekie-image_${version}_${arch}.deb"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
pkg="$stage/seekie-image"
mkdir -p \
    "$pkg/DEBIAN" \
    "$pkg/opt/seekie-image" \
    "$pkg/usr/bin" \
    "$pkg/usr/share/applications" \
    "$pkg/usr/share/doc/seekie-image"

cp -a "$src/." "$pkg/opt/seekie-image/"

cat > "$pkg/usr/bin/seekie-image" <<'EOF'
#!/bin/sh
exec /opt/seekie-image/seekie-image "$@"
EOF
chmod 755 "$pkg/usr/bin/seekie-image"

# 启动器与图标和 pip 安装时用的是同一份资源
cp "$root/seekie_image/assets/seekie-image.desktop" "$pkg/usr/share/applications/"
for icon in "$root"/seekie_image/assets/hicolor/*/apps/seekie-image.png; do
    size="$(basename "$(dirname "$(dirname "$icon")")")"
    mkdir -p "$pkg/usr/share/icons/hicolor/$size/apps"
    cp "$icon" "$pkg/usr/share/icons/hicolor/$size/apps/"
done

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
Architecture: $arch
Maintainer: $maintainer
Installed-Size: $installed_size
Depends: python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
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

rm -f "$out"
dpkg-deb --build --root-owner-group "$pkg" "$out" >/dev/null
echo "已生成 $out"
