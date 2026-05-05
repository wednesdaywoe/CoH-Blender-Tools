"""Extract a single file from the CoH pigg collection.

Searches across every .pigg in Client/piggs/ for a path or basename and
writes the bytes to disk. Useful for grabbing one .geo, .texture, or .anim
without pulling its dependencies.

If you're after a .geo and want its textures too, use
extract_geo_with_textures.py instead.

Usage:
    python extract_from_pigg.py <pigg-path-or-basename> <output-file>

Examples:
    python extract_from_pigg.py AP_plaza_pedestal.geo out/AP_plaza_pedestal.geo
    python extract_from_pigg.py object_library/.../AP_plaza_pedestal.geo out/file.geo
"""

import sys
from pathlib import Path

# ─── USER CONFIG ─────────────────────────────────────────────────────────
OUROBOROS_DIR = Path(r"G:\Ouroboros-v2i210")
# ─────────────────────────────────────────────────────────────────────────


PIGGS_DIR = OUROBOROS_DIR / "Client" / "piggs"
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "lib"))

from pigg_wrangler.pigg import PiggCollection


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)

    target = sys.argv[1]
    out_path = Path(sys.argv[2])

    if not PIGGS_DIR.is_dir():
        print(f"Pigg directory not found: {PIGGS_DIR}")
        print(f"Edit OUROBOROS_DIR at the top of {__file__}.")
        sys.exit(1)

    coll = PiggCollection(PIGGS_DIR)
    if not coll.readers:
        print(f"No .pigg files found at {PIGGS_DIR}")
        sys.exit(1)

    found = []
    for archive in coll.readers:
        entry = archive.get(target)
        if entry is not None:
            found.append((archive, entry))

    if not found:
        # Substring search to help diagnose typos
        candidates = []
        needle = target.lower().rsplit("/", 1)[-1]
        for archive in coll.readers:
            for path in archive.list_paths():
                if needle in path.lower():
                    candidates.append((archive.pigg_path, path))
                    if len(candidates) >= 10:
                        break
            if len(candidates) >= 10:
                break
        if candidates:
            print(f"'{target}' not found exactly. Closest matches:")
            for pigg, path in candidates:
                print(f"  {Path(pigg).name}: {path}")
        else:
            print(f"'{target}' not found in any pigg.")
        sys.exit(1)

    if len(found) > 1:
        print(f"Found in {len(found)} piggs (using first):")
        for archive, entry in found:
            print(f"  {Path(archive.pigg_path).name}: {entry.path}")

    archive, entry = found[0]
    data = archive.extract(entry)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    print(f"Extracted from: {Path(archive.pigg_path).name}")
    print(f"Internal path:  {entry.path}")
    print(f"Wrote:          {out_path}  ({len(data)} bytes)")


if __name__ == "__main__":
    main()
