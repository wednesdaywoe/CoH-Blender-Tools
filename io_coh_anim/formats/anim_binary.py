"""
Binary .anim file reader and writer for City of Heroes.

File format (32-bit layout, little-endian):
    [SkeletonAnimTrack header - 596 bytes]
    [SkeletonHeirarchy - 1204 bytes, if present]
    [BoneAnimTrack array - bone_track_count × 20 bytes]
    [Animation key data - variable size]

All pointer fields are stored as byte offsets from file start.
On load, the game adds the base allocation address to convert to pointers.

Reference: Common/seq/animtrack.h, GetAnimation2/src/outputanim.c
"""

import struct
from dataclasses import dataclass, field

from ..core.bones import bone_name_from_id, bone_id_from_name, BONES_ON_DISK
from .compression import (
    ROTATION_UNCOMPRESSED,
    ROTATION_COMPRESSED_TO_5_BYTES,
    ROTATION_COMPRESSED_TO_8_BYTES,
    POSITION_UNCOMPRESSED,
    POSITION_COMPRESSED_TO_6_BYTES,
    rot_key_size,
    pos_key_size,
    decompress_rotation,
    decompress_position,
    compress_quat_5byte,
    compress_pos_6byte,
    compress_pos_uncompressed,
    can_compress_pos_6byte,
)

# Struct sizes (32-bit layout)
SIZEOF_SKELETON_ANIM_TRACK = 596
SIZEOF_BONE_ANIM_TRACK = 20
SIZEOF_BONE_LINK = 12
SIZEOF_SKELETON_HEIRARCHY = 4 + BONES_ON_DISK * SIZEOF_BONE_LINK  # 1204

MAX_ANIM_FILE_NAME_LEN = 256


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class BoneLink:
    """A node in the skeleton hierarchy tree."""
    child: int = -1    # First child bone ID (-1 = none)
    next: int = -1     # Next sibling bone ID (-1 = none)
    id: int = 0        # Bone ID (redundant)


@dataclass
class SkeletonHierarchy:
    """Skeleton bone hierarchy, only present in skel_*.anim files."""
    root: int = 0
    bones: list = field(default_factory=lambda: [BoneLink() for _ in range(BONES_ON_DISK)])


@dataclass
class BoneTrackData:
    """Decompressed animation data for a single bone."""
    bone_id: int
    bone_name: str
    rotations: list  # List of (w, x, y, z) quaternions per frame
    positions: list  # List of (x, y, z) vectors per frame
    flags: int = 0


@dataclass
class AnimData:
    """Complete animation data from a binary .anim file."""
    name: str = ""
    base_anim_name: str = ""
    max_hip_displacement: float = 0.0
    length: float = 0.0
    bone_tracks: list = field(default_factory=list)  # List of BoneTrackData
    hierarchy: SkeletonHierarchy | None = None
    # Raw header fields preserved for round-tripping
    rotation_compression_type: int = 0
    position_compression_type: int = 0


# ─── Binary Reader ──────────────────────────────────────────────────────────

def read_anim(filepath):
    """Read a binary .anim file and return decompressed AnimData.

    Args:
        filepath: Path to the .anim file

    Returns:
        AnimData with decompressed bone tracks
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    return _parse_anim(data)


def _parse_anim(data):
    """Parse binary animation data from a byte buffer."""
    buf = memoryview(data)

    # ── Parse SkeletonAnimTrack header ──
    header_size = struct.unpack_from('<i', buf, 0)[0]
    name = _read_string(buf, 4, MAX_ANIM_FILE_NAME_LEN)
    base_anim_name = _read_string(buf, 4 + MAX_ANIM_FILE_NAME_LEN, MAX_ANIM_FILE_NAME_LEN)

    offset = 4 + 2 * MAX_ANIM_FILE_NAME_LEN  # 516

    max_hip_displacement, length = struct.unpack_from('<ff', buf, offset)
    offset += 8  # 524

    bone_tracks_offset = struct.unpack_from('<I', buf, offset)[0]
    offset += 4  # 528

    bone_track_count = struct.unpack_from('<i', buf, offset)[0]
    offset += 4  # 532

    rotation_compression_type, position_compression_type = struct.unpack_from('<ii', buf, offset)
    offset += 8  # 540

    hierarchy_offset = struct.unpack_from('<I', buf, offset)[0]
    offset += 4  # 544

    # ── Parse SkeletonHierarchy (if present) ──
    hierarchy = None
    if hierarchy_offset != 0:
        hierarchy = _parse_hierarchy(buf, hierarchy_offset)

    # ── Parse BoneAnimTrack array ──
    bone_tracks = []
    for i in range(bone_track_count):
        bt_offset = bone_tracks_offset + i * SIZEOF_BONE_ANIM_TRACK
        bt = _parse_bone_track(buf, bt_offset, header_size)
        bone_tracks.append(bt)

    return AnimData(
        name=name,
        base_anim_name=base_anim_name,
        max_hip_displacement=max_hip_displacement,
        length=length,
        bone_tracks=bone_tracks,
        hierarchy=hierarchy,
        rotation_compression_type=rotation_compression_type,
        position_compression_type=position_compression_type,
    )


def _read_string(buf, offset, max_len):
    """Read a null-terminated string from a fixed-size field."""
    raw = bytes(buf[offset:offset + max_len])
    null_pos = raw.find(b'\x00')
    if null_pos >= 0:
        raw = raw[:null_pos]
    return raw.decode('ascii', errors='replace')


def _parse_hierarchy(buf, offset):
    """Parse SkeletonHierarchy at the given offset."""
    hierarchy = SkeletonHierarchy()
    hierarchy.root = struct.unpack_from('<i', buf, offset)[0]

    for i in range(BONES_ON_DISK):
        bl_offset = offset + 4 + i * SIZEOF_BONE_LINK
        child, next_id, bone_id = struct.unpack_from('<iii', buf, bl_offset)
        hierarchy.bones[i] = BoneLink(child=child, next=next_id, id=bone_id)

    return hierarchy


def _parse_bone_track(buf, offset, header_size):
    """Parse a BoneAnimTrack and decompress its key data."""
    # Unpack the BoneAnimTrack struct (20 bytes)
    (rot_idx_offset, pos_idx_offset,
     rot_fullkeycount, pos_fullkeycount,
     rot_count, pos_count,
     bone_id_byte, flags_byte,
     pack_pad) = struct.unpack_from('<II HH HH bb H', buf, offset)

    bone_id = bone_id_byte
    flags = flags_byte & 0xFF
    bone_name = bone_name_from_id(bone_id) or f"UNKNOWN_{bone_id}"

    # Decompress rotation keys
    rotations = []
    rk_size = rot_key_size(flags)
    for i in range(rot_fullkeycount):
        key_offset = rot_idx_offset + i * rk_size
        key_data = bytes(buf[key_offset:key_offset + rk_size])
        rotations.append(decompress_rotation(key_data, flags))

    # Decompress position keys
    positions = []
    pk_size = pos_key_size(flags)
    for i in range(pos_fullkeycount):
        key_offset = pos_idx_offset + i * pk_size
        key_data = bytes(buf[key_offset:key_offset + pk_size])
        positions.append(decompress_position(key_data, flags))

    return BoneTrackData(
        bone_id=bone_id,
        bone_name=bone_name,
        rotations=rotations,
        positions=positions,
        flags=flags,
    )


# ─── Binary Writer ──────────────────────────────────────────────────────────

def write_anim(filepath, anim_data):
    """Write an AnimData object to a binary .anim file.

    Args:
        filepath: Output file path
        anim_data: AnimData with bone tracks to write
    """
    binary = _build_anim(anim_data)
    with open(filepath, 'wb') as f:
        f.write(binary)


def _build_anim(anim_data):
    """Build the complete binary representation of an animation."""
    # ── Determine compression and build key data ──
    bone_key_data = []  # List of (rot_bytes, pos_bytes, flags) per bone
    for bt in anim_data.bone_tracks:
        rot_bytes, pos_bytes, flags = _compress_bone_track(bt)
        bone_key_data.append((rot_bytes, pos_bytes, flags))

    # ── Calculate sizes and offsets ──
    has_hierarchy = anim_data.hierarchy is not None
    hierarchy_size = SIZEOF_SKELETON_HEIRARCHY if has_hierarchy else 0
    bone_tracks_array_size = len(anim_data.bone_tracks) * SIZEOF_BONE_ANIM_TRACK

    header_size = SIZEOF_SKELETON_ANIM_TRACK + hierarchy_size + bone_tracks_array_size

    # Calculate key data offsets
    key_data_offset = header_size
    bone_track_entries = []

    current_offset = key_data_offset
    for i, (rot_bytes, pos_bytes, flags) in enumerate(bone_key_data):
        bt = anim_data.bone_tracks[i]
        rot_idx = current_offset
        current_offset += len(rot_bytes)
        pos_idx = current_offset
        current_offset += len(pos_bytes)

        bone_track_entries.append({
            'rot_idx': rot_idx,
            'pos_idx': pos_idx,
            'rot_fullkeycount': len(bt.rotations),
            'pos_fullkeycount': len(bt.positions),
            'rot_count': len(bt.rotations),
            'pos_count': len(bt.positions),
            'bone_id': bt.bone_id,
            'flags': flags,
        })

    total_size = current_offset

    # ── Build the binary buffer ──
    output = bytearray(total_size)

    # Write SkeletonAnimTrack header
    struct.pack_into('<i', output, 0, header_size)
    _write_string(output, 4, anim_data.name, MAX_ANIM_FILE_NAME_LEN)
    _write_string(output, 4 + MAX_ANIM_FILE_NAME_LEN, anim_data.base_anim_name, MAX_ANIM_FILE_NAME_LEN)

    offset = 4 + 2 * MAX_ANIM_FILE_NAME_LEN  # 516
    struct.pack_into('<ff', output, offset, anim_data.max_hip_displacement, anim_data.length)
    offset += 8

    bone_tracks_offset = SIZEOF_SKELETON_ANIM_TRACK + hierarchy_size
    struct.pack_into('<I', output, offset, bone_tracks_offset)
    offset += 4

    struct.pack_into('<i', output, offset, len(anim_data.bone_tracks))
    offset += 4

    struct.pack_into('<ii', output, offset,
                     anim_data.rotation_compression_type,
                     anim_data.position_compression_type)
    offset += 8

    hierarchy_offset_value = SIZEOF_SKELETON_ANIM_TRACK if has_hierarchy else 0
    struct.pack_into('<I', output, offset, hierarchy_offset_value)
    offset += 4

    # backupAnimTrack, loadstate, lasttimeused, fileAge = 0 (runtime only)
    # spare_room[9] = preserved from input if available
    # (already zeroed from bytearray)

    # Write SkeletonHierarchy (if present)
    if has_hierarchy:
        _write_hierarchy(output, SIZEOF_SKELETON_ANIM_TRACK, anim_data.hierarchy)

    # Write BoneAnimTrack array
    for i, entry in enumerate(bone_track_entries):
        bt_offset = bone_tracks_offset + i * SIZEOF_BONE_ANIM_TRACK
        struct.pack_into('<II HH HH bb H', output, bt_offset,
                         entry['rot_idx'], entry['pos_idx'],
                         entry['rot_fullkeycount'], entry['pos_fullkeycount'],
                         entry['rot_count'], entry['pos_count'],
                         entry['bone_id'] & 0xFF, entry['flags'] & 0xFF,
                         0)  # pack_pad

    # Write key data
    for i, (rot_bytes, pos_bytes, _flags) in enumerate(bone_key_data):
        entry = bone_track_entries[i]
        output[entry['rot_idx']:entry['rot_idx'] + len(rot_bytes)] = rot_bytes
        output[entry['pos_idx']:entry['pos_idx'] + len(pos_bytes)] = pos_bytes

    return bytes(output)


def _compress_bone_track(bt):
    """Compress a bone track's rotation and position data.

    Returns:
        (rot_bytes, pos_bytes, flags)
    """
    flags = 0

    # Compress rotations (always use 5-byte)
    rot_bytes = bytearray()
    flags |= ROTATION_COMPRESSED_TO_5_BYTES
    for quat in bt.rotations:
        rot_bytes.extend(compress_quat_5byte(quat))

    # Compress positions (6-byte if possible, else uncompressed)
    pos_bytes = bytearray()
    if can_compress_pos_6byte(bt.positions):
        flags |= POSITION_COMPRESSED_TO_6_BYTES
        for pos in bt.positions:
            pos_bytes.extend(compress_pos_6byte(pos))
    else:
        flags |= POSITION_UNCOMPRESSED
        for pos in bt.positions:
            pos_bytes.extend(compress_pos_uncompressed(pos))

    return bytes(rot_bytes), bytes(pos_bytes), flags


def _write_string(buf, offset, text, max_len):
    """Write a null-terminated ASCII string into a fixed-size field."""
    encoded = text.encode('ascii', errors='replace')[:max_len - 1]
    buf[offset:offset + len(encoded)] = encoded
    # Rest is already zeroed from bytearray initialization


def _write_hierarchy(buf, offset, hierarchy):
    """Write SkeletonHierarchy at the given offset."""
    struct.pack_into('<i', buf, offset, hierarchy.root)
    for i in range(BONES_ON_DISK):
        bl = hierarchy.bones[i]
        bl_offset = offset + 4 + i * SIZEOF_BONE_LINK
        struct.pack_into('<iii', buf, bl_offset, bl.child, bl.next, bl.id)
