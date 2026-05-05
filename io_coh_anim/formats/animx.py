"""
ANIMX text format reader and writer.

ANIMX is the text-based animation export format from 3DS Max.
Each bone has per-frame axis-angle transforms in world space (3DS Max coordinates).

File syntax:
    Version 200
    SourceName MyFile.max
    TotalFrames 30
    FirstFrame 0

    Bone "HIPS"
    {
        # frames: 30
        Transform
        {
            Axis 0 0 1
            Angle 0
            Translation 0 0 42.5
            Scale 1 1 1
        }
        ...
    }

Reference: utilities/3dsmax/coh_anim_exp/animexp.cpp
           utilities/3dsmax/coh_anim_imp/import_animx.c
"""

import re
from dataclasses import dataclass, field


@dataclass
class AnimXTransform:
    """A single frame's transform for a bone."""
    axis: tuple = (0.0, 0.0, 1.0)
    angle: float = 0.0
    translation: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)


@dataclass
class AnimXBone:
    """Animation data for a single bone."""
    name: str = ""
    transforms: list = field(default_factory=list)  # List of AnimXTransform


@dataclass
class AnimXData:
    """Complete ANIMX file data."""
    version: int = 200
    source_name: str = ""
    total_frames: int = 0
    first_frame: int = 0
    bones: list = field(default_factory=list)  # List of AnimXBone


# ─── Reader ─────────────────────────────────────────────────────────────────

def read_animx(filepath):
    """Parse an ANIMX text file.

    Args:
        filepath: Path to the .animx file

    Returns:
        AnimXData with parsed bone transforms
    """
    with open(filepath, 'r') as f:
        text = f.read()

    return _parse_animx(text)


def _parse_animx(text):
    """Parse ANIMX text content into AnimXData."""
    data = AnimXData()
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue

        if line.startswith('Version'):
            data.version = int(line.split()[1])
        elif line.startswith('SourceName'):
            data.source_name = line.split(None, 1)[1] if len(line.split()) > 1 else ""
        elif line.startswith('TotalFrames'):
            data.total_frames = int(line.split()[1])
        elif line.startswith('FirstFrame'):
            data.first_frame = int(line.split()[1])
        elif line.startswith('Bone'):
            bone, i = _parse_bone(lines, i, line)
            data.bones.append(bone)

    return data


def _parse_bone(lines, i, bone_line):
    """Parse a Bone block starting from the line after 'Bone "NAME"'.

    Returns:
        (AnimXBone, next_line_index)
    """
    # Extract bone name from: Bone "NAME"
    match = re.search(r'"([^"]+)"', bone_line)
    bone = AnimXBone(name=match.group(1) if match else "")

    # Expect opening brace
    depth = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith('#'):
            continue

        if line == '{':
            depth += 1
            continue
        elif line == '}':
            depth -= 1
            if depth <= 0:
                break
            continue

        if line.startswith('Transform'):
            transform, i = _parse_transform(lines, i)
            bone.transforms.append(transform)

    return bone, i


def _parse_transform(lines, i):
    """Parse a Transform block.

    Returns:
        (AnimXTransform, next_line_index)
    """
    transform = AnimXTransform()

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith('#'):
            continue

        if line == '{':
            continue
        elif line == '}':
            break

        parts = line.split()
        keyword = parts[0]

        if keyword == 'Axis' and len(parts) >= 4:
            transform.axis = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif keyword == 'Angle' and len(parts) >= 2:
            transform.angle = float(parts[1])
        elif keyword == 'Translation' and len(parts) >= 4:
            transform.translation = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif keyword == 'Scale' and len(parts) >= 4:
            transform.scale = (float(parts[1]), float(parts[2]), float(parts[3]))

    return transform, i


# ─── Writer ─────────────────────────────────────────────────────────────────

def write_animx(filepath, data):
    """Write AnimXData to an ANIMX text file.

    Args:
        filepath: Output file path
        data: AnimXData to write
    """
    with open(filepath, 'w') as f:
        _write_animx(f, data)


def _write_animx(f, data):
    """Write ANIMX format to a file handle."""
    # Header comments
    version_major = data.version // 100
    version_minor = data.version % 100
    f.write("# NCsoft CoH Animation Export\n")
    f.write("# Generated from Blender using:\n")
    f.write(f"#\t\tPlugin: 'io_coh_anim', Version {version_major}, Revision {version_minor}\n")
    if data.source_name:
        f.write(f"#\t\tSource File: {data.source_name}\n")
    f.write("\n")

    # Header fields
    f.write(f"Version {data.version}\n")
    f.write(f"SourceName {data.source_name}\n")
    f.write(f"TotalFrames {data.total_frames}\n")
    f.write(f"FirstFrame {data.first_frame}\n\n")

    # Bone data
    for bone in data.bones:
        _write_bone(f, bone)


def _write_bone(f, bone):
    """Write a single bone's animation data."""
    f.write(f'Bone "{bone.name}"\n')
    f.write('{\n')
    f.write(f'\t# frames: {len(bone.transforms)}\n\n')

    for transform in bone.transforms:
        f.write('\tTransform\n')
        f.write('\t{\n')
        f.write(f'\t\tAxis {transform.axis[0]:.7g} {transform.axis[1]:.7g} {transform.axis[2]:.7g} \n')
        f.write(f'\t\tAngle {transform.angle:.7g}\n')
        f.write(f'\t\tTranslation {transform.translation[0]:.7g} {transform.translation[1]:.7g} {transform.translation[2]:.7g} \n')
        f.write(f'\t\tScale {transform.scale[0]:.7g} {transform.scale[1]:.7g} {transform.scale[2]:.7g} \n')
        f.write('\t}\n\n')

    f.write('}\n\n')
