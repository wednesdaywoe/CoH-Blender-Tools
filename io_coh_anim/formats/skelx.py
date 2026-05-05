"""
SKELX text format reader and writer.

SKELX defines the skeleton hierarchy with bind pose transforms.
Bones are nested within their parents using braces.

File syntax:
    Version 200
    SourceName SM_Master.max

    Bone "HIPS"
    {
        Axis 0 0 1
        Angle 0
        Translation 0 0 42.5
        Scale 1 1 1
        Row0 1 0 0
        Row1 0 1 0
        Row2 0 0 1
        Row3 0 0 42.5
        Children 1
        Bone "WAIST"
        {
            ...
        }
    }

Reference: utilities/3dsmax/coh_anim_exp/skelexp.cpp
           utilities/GetAnimation2/src/process_skelx.c
"""

import re
from dataclasses import dataclass, field


@dataclass
class SkelXBone:
    """A bone in the skeleton hierarchy."""
    name: str = ""
    axis: tuple = (0.0, 0.0, 1.0)
    angle: float = 0.0
    translation: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)
    matrix_rows: list = field(default_factory=lambda: [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 0.0),
    ])
    children: list = field(default_factory=list)  # List of SkelXBone


@dataclass
class SkelXData:
    """Complete SKELX file data."""
    version: int = 200
    source_name: str = ""
    bones: list = field(default_factory=list)  # Root-level SkelXBone list


# ─── Reader ─────────────────────────────────────────────────────────────────

def read_skelx(filepath):
    """Parse a SKELX text file.

    Args:
        filepath: Path to the .skelx file

    Returns:
        SkelXData with parsed bone hierarchy
    """
    with open(filepath, 'r') as f:
        text = f.read()

    return _parse_skelx(text)


def _parse_skelx(text):
    """Parse SKELX text content into SkelXData."""
    data = SkelXData()
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith('#'):
            continue

        if line.startswith('Version'):
            data.version = int(line.split()[1])
        elif line.startswith('SourceName'):
            parts = line.split(None, 1)
            data.source_name = parts[1] if len(parts) > 1 else ""
        elif line.startswith('Bone'):
            bone, i = _parse_skel_bone(lines, i, line)
            data.bones.append(bone)

    return data


def _parse_skel_bone(lines, i, bone_line):
    """Parse a Bone block with nested children.

    Returns:
        (SkelXBone, next_line_index)
    """
    match = re.search(r'"([^"]+)"', bone_line)
    bone = SkelXBone(name=match.group(1) if match else "")

    # Find and consume opening brace
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if line == '{':
            break

    # Parse bone contents until closing brace
    depth = 1
    while i < len(lines) and depth > 0:
        line = lines[i].strip()
        i += 1

        if not line or line.startswith('#'):
            continue

        if line == '}':
            depth -= 1
            if depth <= 0:
                break
            continue

        parts = line.split()
        keyword = parts[0]

        if keyword == 'Axis' and len(parts) >= 4:
            bone.axis = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif keyword == 'Angle' and len(parts) >= 2:
            bone.angle = float(parts[1])
        elif keyword == 'Translation' and len(parts) >= 4:
            bone.translation = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif keyword == 'Scale' and len(parts) >= 4:
            bone.scale = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif keyword.startswith('Row') and len(parts) >= 4:
            row_idx = int(keyword[3])
            row = (float(parts[1]), float(parts[2]), float(parts[3]))
            if 0 <= row_idx <= 3:
                bone.matrix_rows[row_idx] = row
        elif keyword == 'Children':
            # Just informational, children are parsed by encountering nested Bone blocks
            pass
        elif keyword == 'Bone':
            child, i = _parse_skel_bone(lines, i, line)
            bone.children.append(child)

    return bone, i


# ─── Writer ─────────────────────────────────────────────────────────────────

def write_skelx(filepath, data):
    """Write SkelXData to a SKELX text file.

    Args:
        filepath: Output file path
        data: SkelXData to write
    """
    with open(filepath, 'w') as f:
        _write_skelx(f, data)


def _write_skelx(f, data):
    """Write SKELX format to a file handle."""
    version_major = data.version // 100
    version_minor = data.version % 100

    f.write("# NCsoft CoH Skeleton Export\n")
    f.write("# Generated from Blender using:\n")
    f.write(f"#\t\tPlugin: 'io_coh_anim', Version {version_major}, Revision {version_minor}\n")
    if data.source_name:
        f.write(f"#\t\tSource File: {data.source_name}\n")
    f.write("\n")

    f.write(f"Version {data.version}\n")
    f.write(f"SourceName {data.source_name}\n")

    # Write hierarchy comment tree
    f.write("\n# NODE HIERARCHY\n")
    for bone in data.bones:
        _write_hierarchy_comment(f, bone, [], False)
    f.write("\n")

    # Write bone definitions
    for bone in data.bones:
        _write_skel_bone(f, bone, 0)


def _write_hierarchy_comment(f, bone, deco_stack, has_sibling):
    """Write the visual hierarchy tree as comments."""
    f.write("#\t")
    for d in deco_stack:
        f.write("| " if d else "  ")
    f.write(f"|_ {bone.name}\n")

    for idx, child in enumerate(bone.children):
        child_has_sibling = idx < len(bone.children) - 1
        _write_hierarchy_comment(f, child, deco_stack + [has_sibling], child_has_sibling)


def _write_skel_bone(f, bone, depth):
    """Write a bone definition with proper indentation."""
    indent = "    " * depth

    f.write(f'{indent}Bone "{bone.name}"\n')
    f.write(f'{indent}{{\n')

    inner = "    " * (depth + 1)
    f.write(f'{inner}Axis {bone.axis[0]:.7g} {bone.axis[1]:.7g} {bone.axis[2]:.7g} \n')
    f.write(f'{inner}Angle {bone.angle:.7g}\n')
    f.write(f'{inner}Translation {bone.translation[0]:.7g} {bone.translation[1]:.7g} {bone.translation[2]:.7g} \n')
    f.write(f'{inner}Scale {bone.scale[0]:.7g} {bone.scale[1]:.7g} {bone.scale[2]:.7g} \n')
    f.write(f'{inner}\n')

    for row_idx, row in enumerate(bone.matrix_rows):
        f.write(f'{inner}Row{row_idx} {row[0]:.7g} {row[1]:.7g} {row[2]:.7g} \n')

    if bone.children:
        f.write(f'{inner}\n')
        f.write(f'{inner}Children {len(bone.children)}\n\n')

        for child in bone.children:
            _write_skel_bone(f, child, depth + 1)

    f.write(f'{indent}}}\n\n')
