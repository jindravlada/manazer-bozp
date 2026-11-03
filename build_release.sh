#!/usr/bin/env bash
set -e

APP_NAME="ManazerBOZP"
OUTPUT_NAME="ManagerBOZP.AppImage"

# Snímek AppImage v aktuálním adresáři: inode, velikost, čas a cesta.
snapshot_appimages() {
  local dest="$1"
  (
    shopt -s nullglob
    local path
    for path in ./*.AppImage; do
      stat --printf '%i\t%s\t%Y\t%n\n' "$path"
    done | LC_ALL=C sort
  ) > "$dest"
}

# Výsledkem smí být jen AppImage vytvořený nebo přepsaný právě tímto během.
publish_built_appimage() {
  local before="$1"
  local after="$2"
  local -a candidates=()
  local line path base

  while IFS= read -r line; do
    [ -z "$line" ] && continue
    path="${line##*$'\t'}"
    base="$(basename "$path")"
    if [ "$base" = "linuxdeploy-x86_64.AppImage" ]; then
      continue
    fi
    candidates+=("$path")
  done < <(comm -13 "$before" "$after")

  if [ "${#candidates[@]}" -eq 0 ]; then
    echo "AppImage nebyl vytvořen. Starší balíčky v pracovním adresáři zůstaly nedotčené."
    exit 1
  fi
  if [ "${#candidates[@]}" -gt 1 ]; then
    echo "Sestavení změnilo více AppImage souborů a výsledek nelze určit:"
    printf ' - %s\n' "${candidates[@]}"
    exit 1
  fi

  if [ "$(basename "${candidates[0]}")" != "$OUTPUT_NAME" ]; then
    mv -- "${candidates[0]}" "$OUTPUT_NAME"
  fi
  chmod +x "$OUTPUT_NAME"
}

run_appimage_packaging() {
  local before after status
  before="$(mktemp)"
  after="$(mktemp)"
  set +e
  (
    set -e
    snapshot_appimages "$before"
    if [ "$#" -gt 0 ]; then
      "$@"
    else
      "$LINUXDEPLOY_WORKDIR/squashfs-root/AppRun" \
        --appdir AppDir \
        --desktop-file AppDir/usr/share/applications/ManazerBOZP.desktop \
        --icon-file AppDir/usr/share/icons/hicolor/scalable/apps/manazer-bozp.svg \
        --icon-filename manazer-bozp \
        --output appimage
    fi
    snapshot_appimages "$after"
    publish_built_appimage "$before" "$after"
  )
  status=$?
  set -e
  rm -f "$before" "$after"
  return "$status"
}

main() {
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
  echo "Chybí PyInstaller. Instaluj: pip install -r requirements-build.txt"
  exit 1
fi

LINUXDEPLOY_APPIMAGE="$PROJECT_DIR/linuxdeploy-x86_64.AppImage"
python3 "$PROJECT_DIR/packaging/verify_linuxdeploy.py" --ensure "$LINUXDEPLOY_APPIMAGE"

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

echo "== PyInstaller =="
if [ ! -f "$PROJECT_DIR/zdroje/preklady/qtbase_cs.qm" ]; then
  echo "Chybí zdroje/preklady/qtbase_cs.qm (český Qt překlad)."
  exit 1
fi
mapfile -t QT_THEME_BINARIES < <(python3 -c 'from core.packaging.qt_platform_plugins import pyinstaller_binary_specs; print("\n".join(pyinstaller_binary_specs()))')
ADD_THEME_BINARIES=()
for spec in "${QT_THEME_BINARIES[@]}"; do
  ADD_THEME_BINARIES+=(--add-binary "$spec")
done
pyinstaller --onedir --windowed \
  --name "$APP_NAME" \
  --add-data "moduly:moduly" \
  --add-data "core:core" \
  --add-data "ciselniky:ciselniky" \
  --add-data "zdroje:zdroje" \
  "${ADD_THEME_BINARIES[@]}" \
  main.py

PORTAL_PLUGIN="dist/$APP_NAME/_internal/PySide6/Qt/plugins/platformthemes/libqxdgdesktopportal.so"
if [ ! -f "$PORTAL_PLUGIN" ]; then
  echo "Chybí Qt platform-theme plugin xdgdesktopportal ($PORTAL_PLUGIN)."
  exit 1
fi

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
run_appimage_packaging

echo
echo "HOTOVO:"
ls -lh "$OUTPUT_NAME"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
