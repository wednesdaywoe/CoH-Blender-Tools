"""
CoH `bin/tricks.bin` resolver.

`tricks.bin` registers ~14k named texture-modifier definitions ("tricks").
A trick named e.g. `X_AP_CityHall_Concrete_01` references one or more base
textures via fields like `Base1`, `Base`, `BumpMap1`, etc. The runtime
resolves a `.geo`'s `X_*` tex_name through this table to find the actual
`.texture` files to render.

Reverse-engineering the binary format directly is involved (auto-generated
ParseAuto layout). Instead, this module shells out to the official
`bindump.exe` to convert tricks.bin → text, then parses the text into a
JSON cache: `{trick_name_lower: {base1, base, bumpmap1, bumpmap, ...}}`.

Cache is written once per game install, reused thereafter.
"""

import json
import os
import re
import subprocess
from pathlib import Path


# Fields we care about for resolving the diffuse / normal / etc. texture.
# Order in DIFFUSE_FIELDS = priority order: first non-empty wins.
DIFFUSE_FIELDS = ('Base1', 'Base', 'Base2')
NORMAL_FIELDS = ('BumpMap1', 'BumpMap')
ALL_FIELDS = (
    'Base', 'Base1', 'Base2', 'BumpMap', 'BumpMap1',
    'Multiply1', 'Multiply2', 'DualColor1', 'DualColor2',
    'AddGlow1', 'AddGlow2', 'Mask',
)

_NAME_RE = re.compile(r'^\s+Name\s*=\s*(.+?)\s*$')
_FIELD_RE = re.compile(r'^\s+(\w+)\s*=\s*(.*?)\s*$')
_RECORD_BREAK = re.compile(r'^\s+-+\s*Texture\s+\d+\s*-+')


def _is_real_value(val):
    """Trick fields use empty string or literal 'none' to mean "no texture"."""
    if not val:
        return False
    v = val.strip().lower()
    if v in ('', 'none'):
        return False
    return True


def parse_tricks_dump(dump_path):
    """Parse a `bindump.exe` text dump of tricks.bin into a name->fields dict.

    Args:
        dump_path: Path to a text file produced by `bindump.exe tricks.bin`.

    Returns:
        Dict: `{trick_name_lower: {field_name: value, ...}}` for each entry,
        keeping only the fields in ALL_FIELDS that have real (non-empty,
        non-'none') values.
    """
    tricks = {}
    current_name = None
    current_fields = {}

    def flush():
        nonlocal current_name, current_fields
        if current_name and current_fields:
            tricks[current_name.lower()] = current_fields
        current_name = None
        current_fields = {}

    with open(dump_path, 'r', encoding='ascii', errors='replace') as f:
        for line in f:
            if _RECORD_BREAK.match(line):
                flush()
                continue
            m = _NAME_RE.match(line)
            if m and current_name is None:
                current_name = m.group(1)
                continue
            m = _FIELD_RE.match(line)
            if m:
                key, val = m.group(1), m.group(2)
                if key in ALL_FIELDS and _is_real_value(val):
                    current_fields[key] = val
        flush()

    return tricks


def build_trick_cache(bindump_exe, ouroboros_dir, cache_json):
    """Run bindump.exe on tricks.bin and produce a JSON cache.

    Args:
        bindump_exe: Path to `bindump.exe` (ships with Ouroboros).
        ouroboros_dir: Path to the Ouroboros install root (CWD for bindump,
            since bindump expects relative paths into Client/piggs).
        cache_json: Output JSON path.

    Returns:
        The parsed dict (also written to disk).
    """
    bindump_exe = str(bindump_exe)
    ouroboros_dir = str(ouroboros_dir)
    cache_json = Path(cache_json)
    cache_json.parent.mkdir(parents=True, exist_ok=True)

    dump_txt = cache_json.with_suffix('.txt')
    print(f"  running bindump.exe -> {dump_txt}  (~60 MB, ~30s)...")
    with open(dump_txt, 'wb') as out:
        subprocess.check_call(
            [bindump_exe, 'Client/piggs/bin.pigg:bin/tricks.bin'],
            cwd=ouroboros_dir,
            stdout=out,
        )

    print(f"  parsing dump...")
    tricks = parse_tricks_dump(dump_txt)
    print(f"  parsed {len(tricks)} trick entries")

    with open(cache_json, 'w', encoding='utf-8') as f:
        json.dump(tricks, f, separators=(',', ':'), sort_keys=True)
    print(f"  wrote {cache_json}  ({cache_json.stat().st_size:,} bytes)")

    # Keep the .txt around — it's useful to inspect specific tricks.
    return tricks


def load_trick_cache(cache_json):
    """Load a JSON cache. Returns dict (lowercased keys) or None if missing."""
    cache_json = Path(cache_json)
    if not cache_json.is_file():
        return None
    with open(cache_json, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_diffuse(trick_map, name):
    """Look up a trick by name (case-insensitive) and return the first
    non-empty diffuse-priority field value, or None."""
    if not trick_map:
        return None
    entry = trick_map.get(name.lower())
    if not entry:
        return None
    for field in DIFFUSE_FIELDS:
        v = entry.get(field)
        if _is_real_value(v):
            return v
    return None


def resolve(trick_map, name):
    """Look up a trick. Returns {field: value} dict or None."""
    if not trick_map:
        return None
    return trick_map.get(name.lower())
