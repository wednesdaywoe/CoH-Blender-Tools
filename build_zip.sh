#!/usr/bin/env bash
#
# Rebuild the distributable Blender addon zip (io_coh_anim.zip) from source.
#
# io_coh_anim.zip is what users install via Blender's "Install from Disk". It
# must always match the io_coh_anim/ source tree. Run this after changing
# anything under io_coh_anim/ — or let the pre-commit hook do it automatically
# (see "Rebuilding the addon zip" in README.md).
#
# Usage: ./build_zip.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

ADDON=io_coh_anim
ZIP=io_coh_anim.zip

if [[ ! -f "$ADDON/__init__.py" ]]; then
    echo "error: $ADDON/__init__.py not found — run from the repo root" >&2
    exit 1
fi
if ! command -v zip >/dev/null 2>&1; then
    echo "error: 'zip' not installed" >&2
    exit 1
fi

# Never ship compiled caches.
find "$ADDON" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

rm -f "$ZIP"
# -r recurse, -X drop extra file attributes; exclude caches/compiled files.
zip -r -X "$ZIP" "$ADDON" -x '*/__pycache__/*' '*.pyc' >/dev/null

# Fail loudly if a core module didn't make it in (the exact bug this guards).
missing=0
for f in __init__.py operators.py armature.py mesh.py \
         core/bindpose.py core/bones.py core/coords.py \
         formats/geo.py formats/anim_binary.py; do
    if ! unzip -l "$ZIP" | grep -q " $ADDON/$f\$"; then
        echo "error: $ADDON/$f missing from $ZIP" >&2
        missing=1
    fi
done
[[ $missing -eq 0 ]] || exit 1

version="$(grep -oE '"version": \([0-9, ]+\)' "$ADDON/__init__.py" || echo '"version": (?)')"
count="$(unzip -l "$ZIP" | grep -cE '\.py$')"
echo "Built $ZIP — $count .py files, bl_info ${version#*: }"
