#!/usr/bin/env bash
set -e

APP_NAME="ManazerBOZP"
OUTPUT_NAME="ManagerBOZP.AppImage"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$PROJECT_DIR"

echo "== Manažer BOZP release build =="

APP_DISPLAY_NAME="$(python3 -c "from core.version import app_display_name; print(app_display_name())")"

if [ ! -d ".venv" ]; then
  echo "Chybí .venv"
  exit 1
fi

source .venv/bin/activate

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "Chybí PyInstaller. Instaluj: pip install pyinstaller"
  exit 1
fi

LINUXDEPLOY_APPIMAGE="$PROJECT_DIR/linuxdeploy-x86_64.AppImage"
if [ ! -f "$LINUXDEPLOY_APPIMAGE" ]; then
  echo "Chybí linuxdeploy-x86_64.AppImage"
  exit 1
fi

LINUXDEPLOY_WORKDIR="$(mktemp -d)"
cleanup_linuxdeploy_workdir() {
  rm -rf "$LINUXDEPLOY_WORKDIR"
}
trap cleanup_linuxdeploy_workdir EXIT

(
  cd "$LINUXDEPLOY_WORKDIR"
  "$LINUXDEPLOY_APPIMAGE" --appimage-extract >/dev/null
)

if [ ! -x "$LINUXDEPLOY_WORKDIR/squashfs-root/AppRun" ]; then
  echo "linuxdeploy se nepodařilo rozbalit."
  exit 1
fi

echo "== Čištění =="
rm -rf build dist AppDir squashfs-root
rm -f "$OUTPUT_NAME" Mana_er_BOZP*.AppImage ManazerBOZP*.AppImage Manažer_BOZP*.AppImage

echo "== PyInstaller =="
pyinstaller --onedir --windowed \
  --name "$APP_NAME" \
  --add-data "moduly:moduly" \
  --add-data "core:core" \
  --add-data "ciselniky:ciselniky" \
  --add-data "zdroje:zdroje" \
  main.py

echo "== AppDir =="
mkdir -p AppDir/usr/bin
cp -r "dist/$APP_NAME/"* AppDir/usr/bin/

cat > AppDir/ManazerBOZP.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=${APP_DISPLAY_NAME}
Exec=$APP_NAME
Icon=manazer-bozp
Categories=Office;
Terminal=false
DESKTOP

mkdir -p AppDir/usr/share/applications
cp AppDir/ManazerBOZP.desktop AppDir/usr/share/applications/

mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
cat > AppDir/usr/share/icons/hicolor/scalable/apps/manazer-bozp.svg <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="32" fill="#2e7d32"/>
  <rect x="30" y="30" width="196" height="196" rx="18" fill="none" stroke="#ffffff" stroke-width="10"/>
  <text x="128" y="145" font-size="54" font-family="Arial, sans-serif" font-weight="bold" text-anchor="middle" fill="#ffffff">BOZP</text>
</svg>
SVG

echo "== AppImage =="
"$LINUXDEPLOY_WORKDIR/squashfs-root/AppRun" \
  --appdir AppDir \
  --desktop-file AppDir/usr/share/applications/ManazerBOZP.desktop \
  --icon-file AppDir/usr/share/icons/hicolor/scalable/apps/manazer-bozp.svg \
  --icon-filename manazer-bozp \
  --output appimage

FOUND_APPIMAGE="$(ls -t *.AppImage | grep -v '^linuxdeploy-x86_64.AppImage$' | head -n 1)"

if [ -z "$FOUND_APPIMAGE" ]; then
  echo "AppImage nebyl vytvořen."
  exit 1
fi

mv "$FOUND_APPIMAGE" "$OUTPUT_NAME"
chmod +x "$OUTPUT_NAME"

echo
echo "HOTOVO:"
ls -lh "$OUTPUT_NAME"
