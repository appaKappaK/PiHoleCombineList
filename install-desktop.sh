#!/usr/bin/env bash
# install-desktop.sh — install the Pi-hole Combine List desktop entry and icon
# v1.1.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"

# ── preflight ────────────────────────────────────────────────────────────────
if ! command -v pihole-gui &>/dev/null; then
    echo "Error: pihole-gui not found in PATH."
    echo "Install the package first:  pip install -e ."
    exit 1
fi

# ── install ───────────────────────────────────────────────────────────────────
mkdir -p "$ICON_DIR" "$APPS_DIR"

cp "$SCRIPT_DIR/assets/piholecombinelist.svg" "$ICON_DIR/piholecombinelist.svg"
echo "  icon  → $ICON_DIR/piholecombinelist.svg"

cp "$SCRIPT_DIR/assets/piholecombinelist.desktop" "$APPS_DIR/piholecombinelist.desktop"
echo "  entry → $APPS_DIR/piholecombinelist.desktop"

# ── update caches (best-effort) ───────────────────────────────────────────────
command -v update-desktop-database &>/dev/null \
    && update-desktop-database "$APPS_DIR" 2>/dev/null || true

command -v gtk-update-icon-cache &>/dev/null \
    && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "Done. Pi-hole Combine List should now appear in your app launcher."
