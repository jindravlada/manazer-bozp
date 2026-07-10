#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="manager-bozp-oldlinux-build"
CONTAINER_NAME="manager-bozp-oldlinux-builder"

echo "== Manažer BOZP – build AppImage pro starší Linux =="
echo "Projekt: $PROJECT_DIR"

cat > "$PROJECT_DIR/Dockerfile.oldlinux" <<'EOF'
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip \
    build-essential \
    libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-xinerama0 libxcb-xinput0 libxcb-randr0 libxcb-shape0 \
    libxcb-sync1 libxcb-xfixes0 libxcb1 libx11-xcb1 \
    wget curl file desktop-file-utils patchelf fuse \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
EOF

echo "== Stavím Docker image =="
docker build -t "$IMAGE_NAME" -f "$PROJECT_DIR/Dockerfile.oldlinux" "$PROJECT_DIR"

echo "== Spouštím build uvnitř Ubuntu 22.04 =="
docker run --rm \
  --name "$CONTAINER_NAME" \
  -v "$PROJECT_DIR:/src" \
  -w /src \
  "$IMAGE_NAME" \
  bash -lc '
    set -euo pipefail

    echo "== Čistím starší build artefakty =="
    rm -rf build dist AppDir squashfs-root .venv-oldlinux
    rm -f ManagerBOZP-oldlinux.AppImage

    echo "== Vytvářím venv =="
    python3 -m venv .venv-oldlinux
    source .venv-oldlinux/bin/activate

    echo "== Aktualizuji pip =="
    pip install --upgrade pip wheel setuptools

    echo "== Instaluji závislosti =="
    if [ -f requirements.txt ]; then
      pip install -r requirements.txt
    else
      echo "CHYBA: requirements.txt nenalezen."
      exit 1
    fi

    echo "== PyInstaller build =="
    pip install pyinstaller

    pyinstaller \
      --onedir \
      --windowed \
      --name ManazerBOZP \
      --add-data "moduly:moduly" \
      --add-data "core:core" \
      main.py

    echo "== Připravuji AppDir =="
    APP_DISPLAY_NAME="$(python3 -c "from core.version import app_display_name; print(app_display_name())")"
    mkdir -p AppDir/usr/bin
    cp -r dist/ManazerBOZP/* AppDir/usr/bin/

    cat > AppDir/ManazerBOZP.desktop <<EOF
[Desktop Entry]
Type=Application
Name=${APP_DISPLAY_NAME}
Exec=ManazerBOZP
Icon=manazer-bozp
Categories=Office;
Terminal=false
EOF

    mkdir -p AppDir/usr/share/applications
    cp AppDir/ManazerBOZP.desktop AppDir/usr/share/applications/

    mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

    if [ -f ikona.png ]; then
      cp ikona.png AppDir/usr/share/icons/hicolor/256x256/apps/manazer-bozp.png
    elif [ -f icon.png ]; then
      cp icon.png AppDir/usr/share/icons/hicolor/256x256/apps/manazer-bozp.png
    else
      echo "UPOZORNĚNÍ: ikona.png/icon.png nenalezena, vytvářím jednoduchou ikonu."
      python3 - <<PY
try:
    from PIL import Image
    img = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    img.save("AppDir/usr/share/icons/hicolor/256x256/apps/manazer-bozp.png")
except Exception:
    import struct, zlib
    width = height = 256
    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t+d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    open("AppDir/usr/share/icons/hicolor/256x256/apps/manazer-bozp.png", "wb").write(png)
PY
    fi

    cat > AppDir/AppRun <<EOF
#!/usr/bin/env bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\${HERE}/usr/bin/ManazerBOZP" "\$@"
EOF
    chmod +x AppDir/AppRun

    echo "== Stahuji linuxdeploy =="
    wget -q -O linuxdeploy-x86_64.AppImage \
      https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
    chmod +x linuxdeploy-x86_64.AppImage

    echo "== Rozbaluji linuxdeploy bez FUSE =="
    rm -rf squashfs-root
    ./linuxdeploy-x86_64.AppImage --appimage-extract >/dev/null
    LINUXDEPLOY="./squashfs-root/AppRun"

    echo "== Tvořím AppImage =="
    "$LINUXDEPLOY" \
      --appdir AppDir \
      --output appimage

    echo "== Hledám nově vytvořenou AppImage =="
    OUTPUT_APPIMAGE=$(find . -maxdepth 1 \
      -name "*.AppImage" \
      ! -name "linuxdeploy-x86_64.AppImage" \
      ! -name "ManagerBOZP.AppImage" \
      ! -name "ManagerBOZP-oldlinux.AppImage" \
      | head -n 1)

    if [ -z "$OUTPUT_APPIMAGE" ]; then
      echo "CHYBA: Výstupní AppImage nebyla nalezena."
      ls -lh *.AppImage || true
      exit 1
    fi

    echo "== Přejmenovávám: $OUTPUT_APPIMAGE -> ManagerBOZP-oldlinux.AppImage =="
    mv "$OUTPUT_APPIMAGE" ManagerBOZP-oldlinux.AppImage
    chmod +x ManagerBOZP-oldlinux.AppImage

    echo "== HOTOVO =="
    ls -lh ManagerBOZP-oldlinux.AppImage
  '

echo
echo "Hotovo:"
echo "$PROJECT_DIR/ManagerBOZP-oldlinux.AppImage"
