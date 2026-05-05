"""Extract a .geo from the CoH piggs along with all its textures.

Loads the .geo, reads the texture names it references, then for each name:
  - Tries a direct lookup in the piggs (<name>.texture).
  - If not found, looks the name up in bin/tricks.bin (the texture-modifier
    table) and resolves to the trick's Base1 / Base diffuse texture.

All resolved textures are dumped to <out-dir>/textures/ under their
ORIGINAL tex_name, so the Blender importer's name-based material wiring
works without any extra mapping step.

The first run shells out to Ouroboros's bindump.exe to convert tricks.bin
to text and parses ~10k trick entries into a JSON cache. Subsequent runs
reuse the cache (~30s build, instant load).

Usage:
    python extract_geo_with_textures.py <geo-name-or-path> <out-dir>

Examples:
    python extract_geo_with_textures.py AP_plaza_pedestal.geo out/pedestal
    python extract_geo_with_textures.py object_library/.../foo.geo out/foo
"""

import sys
from pathlib import Path

# ─── USER CONFIG ─────────────────────────────────────────────────────────
# Edit this if your Ouroboros install is somewhere other than the default.
# Everything else is derived from this single path.
OUROBOROS_DIR = Path(r"G:\Ouroboros-v2i210")
# ─────────────────────────────────────────────────────────────────────────


PIGGS_DIR = OUROBOROS_DIR / "Client" / "piggs"
BINDUMP_EXE = OUROBOROS_DIR / "bindump.exe"

_HERE = Path(__file__).resolve().parent
TRICKS_CACHE = _HERE / "tricks_cache.json"

sys.path.insert(0, str(_HERE / "lib"))
sys.path.insert(0, str(_HERE))

from pigg_wrangler.pigg import PiggCollection
from io_coh_anim.formats.geo import read_geo
from io_coh_anim.formats import tricks as tricks_mod


def _find_in_collection(coll, basename):
    """Search every archive for a file with the given basename (case-insensitive)."""
    target_lower = basename.lower()
    for archive in coll.readers:
        for entry in archive.entries:
            if entry.filename.lower() == target_lower:
                return archive, entry
    return None


def _stem(name):
    s = name
    if "." in s.rsplit("/", 1)[-1]:
        s = s.rsplit(".", 1)[0]
    return s


def _resolve_texture(coll, tex_name, trick_map, depth=0):
    """Resolve a tex_name to (archive, entry, source_label) or None.

    1. Direct: try `<name>.texture` and `<stem>.texture` in any pigg.
    2. Trick: if registered in tricks.bin, recurse on Base1/Base/Base2.
    """
    if depth > 3:
        return None

    stem = _stem(tex_name)
    for cand in (f"{tex_name}.texture", f"{stem}.texture"):
        hit = _find_in_collection(coll, cand)
        if hit is not None:
            return (*hit, "direct" if depth == 0 else f"trick-{depth}")

    diffuse = tricks_mod.resolve_diffuse(trick_map, tex_name)
    if diffuse:
        return _resolve_texture(coll, diffuse, trick_map, depth=depth + 1)

    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)

    target = sys.argv[1]
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    if not PIGGS_DIR.is_dir():
        print(f"Pigg directory not found: {PIGGS_DIR}")
        print(f"Edit OUROBOROS_DIR at the top of {__file__}.")
        sys.exit(1)

    coll = PiggCollection(PIGGS_DIR)
    if not coll.readers:
        print(f"No .pigg files found at {PIGGS_DIR}")
        sys.exit(1)

    # ── Trick cache (built once, reused after) ────────────────────────────
    trick_map = tricks_mod.load_trick_cache(TRICKS_CACHE)
    if trick_map is None:
        if not BINDUMP_EXE.is_file():
            print(f"bindump.exe not found at {BINDUMP_EXE} — can't build trick cache.")
            print("X_* texture names won't resolve. Continuing with direct lookup only.")
            trick_map = {}
        else:
            print("Building trick cache (one-time, ~30s)...")
            trick_map = tricks_mod.build_trick_cache(BINDUMP_EXE, OUROBOROS_DIR, TRICKS_CACHE)
    print(f"Trick cache: {len(trick_map)} entries.\n")

    # ── 1. Find and extract the .geo ──────────────────────────────────────
    geo_basename = target.rsplit("/", 1)[-1]
    if not geo_basename.lower().endswith(".geo"):
        geo_basename += ".geo"

    hit = None
    for archive in coll.readers:
        entry = archive.get(target) or archive.get(geo_basename)
        if entry is not None:
            hit = (archive, entry)
            break

    if hit is None:
        print(f"'{target}' not found in any pigg.")
        sys.exit(1)

    archive, entry = hit
    geo_bytes = archive.extract(entry)
    geo_out = out_dir / geo_basename
    geo_out.write_bytes(geo_bytes)
    print(f"Extracted GEO: {Path(archive.pigg_path).name} :: {entry.path}")
    print(f"  -> {geo_out}  ({len(geo_bytes)} bytes)")

    # ── 2. Parse to get referenced texture names ──────────────────────────
    geo_file = read_geo(str(geo_out))
    tex_names = list(geo_file.tex_names)
    if not tex_names:
        print("\nGEO references no textures — done.")
        return

    print(f"\nGEO references {len(tex_names)} texture(s).")

    # ── 3. Resolve and extract each (direct first, then via tricks) ───────
    tex_dir = out_dir / "textures"
    tex_dir.mkdir(exist_ok=True)

    found, missing = [], []
    for tex_name in tex_names:
        result = _resolve_texture(coll, tex_name, trick_map)
        if result is None:
            missing.append(tex_name)
            continue

        tex_archive, tex_entry, source_label = result
        tex_bytes = tex_archive.extract(tex_entry)
        tex_out = tex_dir / f"{tex_name}.texture"
        tex_out.write_bytes(tex_bytes)
        found.append((tex_name, Path(tex_archive.pigg_path).name, tex_entry.path, source_label))

    print(f"\nExtracted {len(found)}/{len(tex_names)} textures -> {tex_dir}")
    for name, pigg, path, source in found:
        print(f"  [{source:<8}] {name:<40} <- {pigg} :: {path}")
    if missing:
        print(f"\nMissing ({len(missing)}):")
        for name in missing:
            print(f"  {name}")

    print(f"\nDone. Open {geo_out} in Blender (with 'Import textures' enabled).")


if __name__ == "__main__":
    main()
