#!/usr/bin/env bash
#
# One-step macOS build for Spellbook.
#
# Produces:  dist/Spellbook.app
#      and:  dist/Spellbook-macos-<arch>.zip   (ready to attach to a GitHub release)
#
# Usage:
#   ./build_mac.sh              # normal build
#   ./build_mac.sh --clean      # wipe caches / build/ first
#   ./build_mac.sh --run        # open the .app when the build succeeds
#
# Requirements: macOS, Python 3.10+ with tkinter, and PyInstaller
#   python3 -m pip install -r requirements.txt pyinstaller
#
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
fi

CLEAN=0
RUN=0
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=1 ;;
        --run)   RUN=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

echo "Interpreter: $PYTHON"
"$PYTHON" --version

if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "ERROR: PyInstaller is not installed for $PYTHON" >&2
    echo "  $PYTHON -m pip install -r requirements.txt pyinstaller" >&2
    exit 1
fi
if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
    echo "ERROR: this Python has no tkinter. Install a Tk-enabled Python" >&2
    echo "  (python.org installer, or 'brew install python-tk')." >&2
    exit 1
fi

# --- 1. Generate Spellbook.icns from the PNG (best effort; needs macOS tools) ---
if command -v sips >/dev/null && command -v iconutil >/dev/null; then
    echo "Generating Spellbook.icns ..."
    ICONSET="$(mktemp -d)/Spellbook.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z "$size" "$size"     "Spellbook Icon.png" --out "$ICONSET/icon_${size}x${size}.png"     >/dev/null
        sips -z $((size*2)) $((size*2)) "Spellbook Icon.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "Spellbook.icns"
    rm -rf "$(dirname "$ICONSET")"
else
    echo "sips/iconutil not found - PyInstaller will convert the PNG itself."
fi

# --- 2. Clean previous output ---
rm -rf "dist/Spellbook.app" dist/Spellbook-macos-*.zip
if [ "$CLEAN" = "1" ]; then
    echo "Removing build/ ..."
    rm -rf build
fi

# --- 3. Build ---
CMD=("$PYTHON" -m PyInstaller Spellbook-mac.spec --noconfirm)
[ "$CLEAN" = "1" ] && CMD+=(--clean)
echo "+ ${CMD[*]}"
"${CMD[@]}"

if [ ! -d "dist/Spellbook.app" ]; then
    echo "BUILD REPORTED SUCCESS but dist/Spellbook.app is missing." >&2
    exit 1
fi

# --- 4. Ad-hoc codesign so Gatekeeper on Apple Silicon will run it at all ---
# (This is free and requires no Apple account. It is NOT notarization - users
#  still do the right-click -> Open dance once. See README.)
echo "Ad-hoc signing the bundle ..."
codesign --force --deep --sign - "dist/Spellbook.app" || \
    echo "WARNING: ad-hoc codesign failed; the app may still run after right-click -> Open."

# --- 5. Zip it for release upload (ditto preserves the bundle + signature) ---
ARCH="$(uname -m)"
ZIP="dist/Spellbook-macos-${ARCH}.zip"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "dist/Spellbook.app" "$ZIP"

echo
echo "===================================================="
echo "BUILD OK"
echo "  dist/Spellbook.app"
echo "  $ZIP  ($(du -h "$ZIP" | cut -f1))"
echo "===================================================="

if [ "$RUN" = "1" ]; then
    open "dist/Spellbook.app"
fi
