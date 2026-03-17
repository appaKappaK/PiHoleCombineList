#!/usr/bin/env bash
# install-desktop.sh — install the Pi-hole Combine List desktop entry and icon
# v1.1.1
set -euo pipefail

if command -v phlist-desktop &>/dev/null; then
    exec phlist-desktop
elif command -v python3 &>/dev/null; then
    exec python3 -m phlist._install_desktop
else
    echo "Error: package not installed. Run 'pip install -e .' first."
    exit 1
fi
