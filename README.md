# CoH Blender Tools

Import City of Heroes geometry (`.geo`) and animations (`.anim`) directly into Blender, with material/texture wiring.

The goal of this project is to replace the legacy 3DS Max 2011 + GetVrml + GetAnimation2 + GetTex workflow. So far it's been tested against Ouroboros v2i210 piggs and Blender 5.0 (4.0+ should work).

---

## What's in the box

```
CoH Blender Tools/
├── io_coh_anim/                    Blender addon (drag-and-drop install)
├── io_coh_anim.zip                 Same addon, zipped for Blender's installer
├── coh_workshop.bat                Browser-UI launcher (recommended entry point)
├── workshop/                       Workshop server (runs on Blender's bundled Python)
├── extract_geo_with_textures.py    CLI alternative: pull a .geo + textures
├── extract_from_pigg.py            CLI alternative: pull any single file
└── lib/pigg_wrangler/              Vendored: stdlib-only pigg reader
```

---

## Requirements

- **Blender 4.0+** (5.0 recommended). Used for both the addon and as the runtime for the Workshop launcher's bundled Python.
- **A working CoH install** with a `Client/piggs/` directory containing the game's `.pigg` archives. Ouroboros, Homecoming, etc. all work — the tool doesn't care about the distribution.
- **`bindump.exe`** (only needed to resolve `X_*` trick texture names; ships with Ouroboros at the install root). Direct texture refs work without it.
- No `pip install`, no system Python required if you use the Workshop launcher. The CLI scripts need Python 3.10+ on `PATH` (or use the `py` launcher on Windows).

---

## Install the Blender addon (do this first either way)

Two equivalent options:

- **From the zip**: in Blender, Edit → Preferences → Add-ons → Install, pick `io_coh_anim.zip`, then enable it (search "City of Heroes").
- **From the folder**: copy `io_coh_anim/` into `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`, then enable it the same way.

Once enabled you'll find the importers under **File → Import → CoH ...**.

---

## Option A — Workshop launcher (recommended)

Double-click **`coh_workshop.bat`**. It locates Blender, runs the Workshop server using Blender's bundled Python, and opens a browser tab against `http://localhost:8765`.

The first run asks for your CoH install path and remembers it in `workshop/config.json`. From the UI you can:

- Search the pigg archives for any file by name.
- Extract a `.geo` (with its textures resolved) into the workshop's `work/` folder.
- Round-trip a `.geo` through Blender (background mode) and stage the result as a workshop-tagged patch pigg in your patch dir.
- See and remove patch piggs the workshop has placed.

Workshop only manages patch piggs with the `coh_workshop_` filename prefix. Anything you placed manually shows up in the listing but won't be touched.

Closing the launcher console window shuts the server down.

**Scope of v1**: static unskinned `.geo` round-trip and patch-pigg staging. Animations and skinned meshes work in the addon but the Workshop's round-trip flow doesn't yet handle them — use the addon directly via Blender for those, or the CLI scripts below.

---

## Option B — CLI scripts (for scripting / automation)

Useful if you want to extract assets in bulk or wire the extraction into a pipeline. Skip these if the Workshop is enough.

### Configure

Open `extract_geo_with_textures.py` and `extract_from_pigg.py`, edit the `OUROBOROS_DIR` constant near the top to your install path. Default is `G:\Ouroboros-v2i210`. Pigg dir and `bindump.exe` location are derived from this.

### Extract a textured `.geo`

```
py -3 extract_geo_with_textures.py AP_plaza_pedestal.geo out/pedestal
```

This:
1. Finds and extracts `AP_plaza_pedestal.geo` from the piggs.
2. Reads its texture references.
3. Resolves each name — direct lookup first, then through `bin/tricks.bin` (the texture-modifier table) for `X_*` names that account for ~80% of environment-asset materials.
4. Dumps every resolved `.texture` file to `out/pedestal/textures/` under the original tex_name.

The first run shells out to `bindump.exe` to convert the 13 MB `bin/tricks.bin` into a 1.7 MB JSON cache (~30 seconds). Subsequent runs reuse it instantly. Cache lives at `tricks_cache.json` next to the script — delete it after a game update to force a rebuild.

Then in Blender: **File → Import → CoH Geometry (.geo)**, pick the extracted file, leave **Import Textures** checked, and switch the viewport to **Material Preview** (`Z` → Material Preview, or the third sphere icon top-right).

### Extract a single file

```
py -3 extract_from_pigg.py <pigg-path-or-basename> <output-file>
```

Prints the source pigg and internal path so you can compute override locations under `Client/data/`.

---

## What works

| Feature | Status |
|---|---|
| `.geo` v1 / v2 / v3-8 import | Working, round-trip bit-exact on positions and winding |
| `.geo` export | Working; metadata fields (`lod_distances`, `bone_id`) need to be preserved or re-supplied for in-game use |
| Skinned mesh import (vertex weights) | Working — per-vertex bone weights become vertex groups named by CoH bone in the game's canonical casing (`Hips`, `UarmR`, …), so they bind to real CoH skeletons / Geopy rigs by name |
| Skinned mesh armature bind | Working — with a CoH armature active on import, skinned meshes are parented + get an Armature modifier so they deform |
| Auto bind-pose skeleton on import | Working — a skinned `.geo` with no armature present builds a rest-pose armature at the correct joint positions (male/fem/huge, auto-detected) and binds to it, so the mesh deforms around real joints with no manual skeleton step. Bone positions are validated bit-exact against the leaked dev skeletons |
| Skinned mesh export | Working — vertex groups named after CoH bones are written back as GEO skinning (top 2 influences per vertex, ≤15 bones per mesh) |
| Direct `.texture` references | Working — DXT1/DXT5 decoded in pure Python, wired into Principled BSDF base color |
| `X_*` trick references via `bin/tricks.bin` | Working — `Base1` diffuse is resolved |
| `.anim` / `.animx` / `.skelx` import + export | Working |
| In-game override pipeline | Working — patch piggs land in your patch dir (`Client/ouro/` on Ouroboros) |

## Known limits

- **Multi-pass trick layers**: only the trick's `Base1` (diffuse) is wired. `BumpMap1`, `Multiply1`, `DualColor1`, `Mask`, etc. are not connected. Most environment assets read correctly with just the diffuse.
- **Collision PolyGrid and LOD reductions**: written as zeros on export. The engine tolerates this for some static props but it's not a substitute for what `getvrml` produces. Anything where collision matters or aggressive LOD is needed should still go through the legacy tools.
- **Skinned deformation uses a canonical bind-pose skeleton**: importing a skinned `.geo` with no armature present auto-builds a rest skeleton at the correct joint positions (reconstructed from the game's own base animations, for male/fem/huge — pick the body type in the import options or let it auto-detect from the filename). The joint positions are validated bit-exact (to 1e-4) against the leaked dev skeletons, so the mesh poses and animates around real joints out of the box. Bones use the game's canonical names (`Hips`, `UarmR`, …), so imported meshes also bind by name directly to a real CoH skeleton if you bring your own. Bone tails default to pointing at their child joint (easier to hand-pose); switch **Bone Tails → +Y Nub** in the import options to match Geopy/the dev rigs exactly for 1:1 game `.anim` playback. Remaining caveat: it's the *standard* humanoid rig, so unusually-proportioned custom bodies won't match exactly. `Create CoH Armature` still exists but stacks every bone at the origin — prefer the auto bind-pose (or import a real `.skelx`/`.anim`) for anything you intend to pose.
- **Reflection quads**: slot preserved on export, not generated.
- **DXT decode is pure Python**: a 512×512 image takes ~1s, a 2048×2048 ~15s. Large meshes with many textures can be slow to import. Untick "Import Textures" if you only need geometry.

---

## Troubleshooting

**"Pigg directory not found"** — Edit `OUROBOROS_DIR` at the top of the extractor scripts. The Workshop launcher asks for the path on first run instead.

**"bindump.exe not found"** — Ouroboros ships it at the install root. Without it, extraction still works for direct texture refs, but `X_*` trick names will fall through as missing.

**Material previews are blank / object looks white** — Three things to check, in order:
1. Viewport shading is **Material Preview** (or Rendered), not Solid. Top-right sphere icons.
2. You're inspecting the right object — click the imported mesh in the outliner first, then look at the Material Properties tab.
3. The mesh actually has resolvable textures. Some assets reference textures we can't resolve yet (multi-pass tricks, missing files); those slots stay default-white. Open the extractor's terminal output to see which textures resolved vs. missed.

**Re-imported but materials still empty** — Blender reuses materials by name across imports. Delete the previous imported objects *and* their orphaned materials (File → Clean Up → Purge Unused Data) before re-importing. Also re-enable the addon to flush Python module cache if you've upgraded the bundle.

**Workshop launcher: "Could not locate blender.exe"** — Set the `BLENDER` environment variable to the full path of `blender.exe`, or install Blender to the default `C:\Program Files\Blender Foundation\Blender <version>\` location.

**Workshop launcher: port 8765 in use** — Another instance is already running, or another tool grabbed the port. Close the other instance, or edit `PORT` near the top of `workshop/server.py`.
