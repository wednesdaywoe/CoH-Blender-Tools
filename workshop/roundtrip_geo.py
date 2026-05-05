"""Round-trip a .geo through Blender and write the result to disk.

Used by the workshop server to produce file-override candidates for
live-game testing. The output file is the result of:
    read_geo -> mesh_from_geo -> geo_from_mesh -> write_geo
If the addon's GEO pipeline is correct, dropping the output as an override
should render identically to the original.

Usage:
    blender --background --python roundtrip_geo.py -- <input.geo> <output.geo>
"""

import sys
from pathlib import Path


_THIS_DIR = Path(__file__).resolve().parent
_BUNDLE_DIR = _THIS_DIR.parent              # CoH Blender Tools/
sys.path.insert(0, str(_BUNDLE_DIR))

# Blender pre-imports installed addons; force project source to win.
for _name in [k for k in list(sys.modules) if k == "io_coh_anim" or k.startswith("io_coh_anim.")]:
    del sys.modules[_name]

import bpy  # noqa: E402

from io_coh_anim.formats.geo import read_geo, write_geo  # noqa: E402
from io_coh_anim.mesh import mesh_from_geo, geo_from_mesh  # noqa: E402


def main():
    argv = sys.argv
    if "--" not in argv:
        print("Usage: blender --background --python roundtrip_geo.py -- <input.geo> <output.geo>")
        sys.exit(2)
    args = argv[argv.index("--") + 1:]
    if len(args) != 2:
        print("Usage: blender --background --python roundtrip_geo.py -- <input.geo> <output.geo>")
        sys.exit(2)

    inp = Path(args[0])
    out = Path(args[1])

    if not inp.exists():
        print(f"Input not found: {inp}")
        sys.exit(1)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    print(f"Reading  {inp}")
    geo = read_geo(str(inp))
    print(f"  models={len(geo.models)}  tex_names={len(geo.tex_names)}")

    print("Importing into Blender...")
    objs = mesh_from_geo(bpy.context, geo, name=inp.stem)
    print(f"  imported {len(objs)} object(s)")

    print("Exporting back to GeoFile...")
    out_geo = geo_from_mesh(bpy.context, objs, geo_name=inp.stem)
    print(f"  models={len(out_geo.models)}  tex_names={len(out_geo.tex_names)}")

    # Preserve metadata fields the Blender mesh doesn't carry through.
    for src, dst in zip(geo.models, out_geo.models):
        dst.lod_distances = list(src.lod_distances)
        dst.bone_id = src.bone_id

    out.parent.mkdir(parents=True, exist_ok=True)
    write_geo(str(out), out_geo)
    print(f"Wrote   {out}")
    print(f"        size={out.stat().st_size} bytes (orig {inp.stat().st_size})")


if __name__ == "__main__":
    main()
