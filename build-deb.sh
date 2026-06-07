#!/bin/bash
set -euo pipefail

VERSION=$(cat VERSION | tr -d '[:space:]')
ARCH=$(dpkg --print-architecture)
PKG_NAME="ddev-menubar"
STAGING="build/deb-staging"
OUTPUT_DIR="build"

echo "Building ${PKG_NAME}_${VERSION}_${ARCH}.deb …"

rm -rf "$STAGING"
mkdir -p \
    "$STAGING/DEBIAN" \
    "$STAGING/usr/bin" \
    "$STAGING/usr/lib/ddev-menubar" \
    "$STAGING/usr/share/applications" \
    "$STAGING/usr/share/icons/hicolor/scalable/apps" \
    "$STAGING/usr/share/ddev-menubar/assets" \
    "$STAGING/etc/xdg/autostart" \
    "$OUTPUT_DIR"

# Python source (exclude __pycache__)
cp -r src/ddev_menubar "$STAGING/usr/lib/ddev-menubar/"
find "$STAGING/usr/lib/ddev-menubar" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Assets
cp assets/ddev-menubar.svg "$STAGING/usr/share/ddev-menubar/assets/"
cp assets/ddev-menubar.svg "$STAGING/usr/share/icons/hicolor/scalable/apps/ddev-menubar.svg"

# Launcher script
cat > "$STAGING/usr/bin/ddev-menubar" << 'SCRIPT'
#!/bin/bash
exec python3 -m ddev_menubar "$@"
SCRIPT
chmod +x "$STAGING/usr/bin/ddev-menubar"

# Add the lib path to PYTHONPATH in the launcher
cat > "$STAGING/usr/bin/ddev-menubar" << 'SCRIPT'
#!/bin/bash
export PYTHONPATH="/usr/lib/ddev-menubar:${PYTHONPATH:-}"
exec python3 -m ddev_menubar "$@"
SCRIPT
chmod +x "$STAGING/usr/bin/ddev-menubar"

# Desktop entry for applications menu
cp ddev-menubar.desktop "$STAGING/usr/share/applications/"

# Autostart entry
cp ddev-menubar.desktop "$STAGING/etc/xdg/autostart/"

# DEBIAN/control
cat > "$STAGING/DEBIAN/control" << EOF
Package: $PKG_NAME
Version: $VERSION
Section: devel
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, gir1.2-notify-0.7
Maintainer: Alan <alan@purple.ai>
Description: DDEV project manager for Ubuntu
 A system tray application for managing DDEV projects on Ubuntu.
 Provides a convenient interface to start, stop, and restart
 DDEV projects, view logs, toggle Xdebug, SSH into projects,
 and manage project groups.
EOF

# DEBIAN/postinst - update icon cache
cat > "$STAGING/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
POSTINST
chmod 755 "$STAGING/DEBIAN/postinst"

# DEBIAN/md5sums
(cd "$STAGING" && find usr etc -type f | sort | xargs md5sum > DEBIAN/md5sums)

DEB_FILE="${OUTPUT_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGING" "$DEB_FILE"

echo ""
echo "Built: $DEB_FILE"
echo ""
echo "Install with:"
echo "  sudo apt install ./$DEB_FILE"
echo ""
echo "Or:"
echo "  sudo dpkg -i $DEB_FILE && sudo apt-get install -f"
