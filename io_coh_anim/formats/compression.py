"""
CoH animation compression/decompression for binary .anim files.

Two compression methods are used:
1. 5-byte quaternion: Drop the largest component, quantize remaining 3 into 40 bits
2. 6-byte position: Multiply each component by 32000, store as 3 signed 16-bit shorts

Reference: GetAnimation2/src/process_animx.c (compressQuatToFiveBytes)
           Common/seq/animtrack.h (constants and structures)
"""

import math
import struct

# Compression flags (from animtrack.h)
ROTATION_UNCOMPRESSED = 1 << 0            # 16 bytes per key (4 floats)
ROTATION_COMPRESSED_TO_5_BYTES = 1 << 1   # 5 bytes per key
ROTATION_COMPRESSED_TO_8_BYTES = 1 << 2   # 8 bytes per key (4 shorts)
POSITION_UNCOMPRESSED = 1 << 3            # 12 bytes per key (3 floats)
POSITION_COMPRESSED_TO_6_BYTES = 1 << 4   # 6 bytes per key (3 shorts)
ROTATION_DELTACODED = 1 << 5
POSITION_DELTACODED = 1 << 6
ROTATION_COMPRESSED_NONLINEAR = 1 << 7

# Key sizes in bytes
SIZE_ROTKEY_UNCOMPRESSED = 16
SIZE_ROTKEY_5BYTE = 5
SIZE_ROTKEY_8BYTE = 8
SIZE_POSKEY_UNCOMPRESSED = 12
SIZE_POSKEY_6BYTE = 6

# Compression factors
CFACTOR_6BYTE_POS = 32000
EFACTOR_6BYTE_POS = 1.0 / 32000.0
CFACTOR_8BYTE_QUAT = 10000
EFACTOR_8BYTE_QUAT = 0.0001


# ─── 5-Byte Quaternion Compression ──────────────────────────────────────────
#
# The 5-byte format stores a unit quaternion in 40 bits:
#   - 4 bits: index of the dropped (largest) component
#   - 3 × 12 bits: the three remaining components as lookup table indices
#
# The dropped component is reconstructed as sqrt(1 - a² - b² - c²).
# Before compression, the quaternion is adjusted so the dropped component
# is positive (negate all if needed).
#
# Byte layout (little-endian, from CoH's unPack5ByteQuat):
#   Byte 0: [missing:4 high][qidxs[0] bits 11-8: 4 low]
#   Bytes 1-4 as little-endian U32:
#     bits 31-24 = qidxs[0] bits 7-0
#     bits 23-12 = qidxs[1] (12 bits)
#     bits 11-0  = qidxs[2] (12 bits)
#
# Lookup table: table[i] = 2.0 * max_value * (i / 4096.0) - max_value
# where max_value = 1/sqrt(2). Maps 12-bit indices [0, 4095] to
# [-1/sqrt(2), +1/sqrt(2)].
#
# Reference: Common/seq/animtrackanimate.c
#            (initLookUpTable, compressQuatToFiveBytes, unPack5ByteQuat)


# Lookup table for 5-byte quat decompression
_5BYTE_MAX_VALUE = 1.0 / math.sqrt(2.0)
_5BYTE_TABLE_SIZE = 4096
_5BYTE_TABLE = [
    2.0 * _5BYTE_MAX_VALUE * (i / _5BYTE_TABLE_SIZE) - _5BYTE_MAX_VALUE
    for i in range(_5BYTE_TABLE_SIZE)
]


def compress_quat_5byte(quat):
    """Compress a unit quaternion to 5 bytes.

    Uses the exact same algorithm as CoH's compressQuatToFiveBytes:
    find the largest component, drop it, quantize the remaining 3 as
    12-bit lookup table indices, and pack using CoH's LE bit layout.

    Args:
        quat: (w, x, y, z) unit quaternion

    Returns:
        bytes object of length 5
    """
    w, x, y, z = quat

    # Normalize
    length = math.sqrt(w * w + x * x + y * y + z * z)
    if length < 1e-10:
        w, x, y, z = 1.0, 0.0, 0.0, 0.0
    else:
        inv = 1.0 / length
        w, x, y, z = w * inv, x * inv, y * inv, z * inv

    # Find largest component (to drop)
    components = [w, x, y, z]
    abs_components = [abs(c) for c in components]
    missing = abs_components.index(max(abs_components))

    # Ensure the dropped component is positive
    if components[missing] < 0:
        w, x, y, z = -w, -x, -y, -z
        components = [w, x, y, z]

    # Get the 3 remaining components (in order, skipping 'missing')
    remaining = []
    for i in range(4):
        if i != missing:
            remaining.append(components[i])

    # Quantize each to 12-bit index.
    # The table is linear: table[i] = 2*max*(i/4096) - max
    # So inverse is: i = (val + max) / (2*max) * 4096
    indices = []
    for val in remaining:
        val = max(-_5BYTE_MAX_VALUE, min(_5BYTE_MAX_VALUE, val))
        idx = int(round((val + _5BYTE_MAX_VALUE) / (2.0 * _5BYTE_MAX_VALUE) * _5BYTE_TABLE_SIZE))
        idx = max(0, min(_5BYTE_TABLE_SIZE - 1, idx))
        indices.append(idx)

    # Pack using CoH's little-endian bit layout:
    #   Byte 0: [missing:4 high][qidxs[0] bits 11-8: 4 low]
    #   Bytes 1-4 as LE U32:
    #     bits 31-24 = qidxs[0] bits 7-0
    #     bits 23-12 = qidxs[1]
    #     bits 11-0  = qidxs[2]
    byte0 = ((missing & 0xF) << 4) | ((indices[0] >> 8) & 0x0F)
    dword = ((indices[0] & 0xFF) << 24) | ((indices[1] & 0xFFF) << 12) | (indices[2] & 0xFFF)

    result = bytes([byte0]) + struct.pack('<I', dword)
    return result


def decompress_quat_5byte(data):
    """Decompress a 5-byte quaternion.

    Uses the exact same algorithm as CoH's unPack5ByteQuat /
    animExpand5ByteQuat: unpack 3 × 12-bit indices from the LE bit
    layout, look up values in the table, reconstruct the missing
    component.

    Args:
        data: bytes or bytearray of length 5

    Returns:
        (w, x, y, z) unit quaternion
    """
    # Unpack using CoH's little-endian bit layout
    byte0 = data[0]
    dword = struct.unpack_from('<I', data, 1)[0]

    missing = (byte0 >> 4) & 0xF
    qidx0 = ((byte0 & 0x0F) << 8) | ((dword >> 24) & 0xFF)
    qidx1 = (dword >> 12) & 0xFFF
    qidx2 = dword & 0xFFF

    # Look up values from table
    vals = [
        _5BYTE_TABLE[min(qidx0, _5BYTE_TABLE_SIZE - 1)],
        _5BYTE_TABLE[min(qidx1, _5BYTE_TABLE_SIZE - 1)],
        _5BYTE_TABLE[min(qidx2, _5BYTE_TABLE_SIZE - 1)],
    ]

    # Reconstruct the missing component
    sum_sq = vals[0] ** 2 + vals[1] ** 2 + vals[2] ** 2
    missing_val = math.sqrt(max(0.0, 1.0 - sum_sq))

    # Rebuild quaternion [w, x, y, z]
    components = [0.0, 0.0, 0.0, 0.0]
    j = 0
    for i in range(4):
        if i == missing:
            components[i] = missing_val
        else:
            components[i] = vals[j]
            j += 1

    return tuple(components)


# ─── 8-Byte Quaternion Compression ──────────────────────────────────────────

def compress_quat_8byte(quat):
    """Compress a quaternion to 8 bytes (4 signed shorts × factor 10000).

    Args:
        quat: (w, x, y, z)

    Returns:
        bytes object of length 8
    """
    values = []
    for c in quat:
        val = int(round(c * CFACTOR_8BYTE_QUAT))
        val = max(-32768, min(32767, val))
        values.append(val)
    return struct.pack('<4h', *values)


def decompress_quat_8byte(data):
    """Decompress an 8-byte quaternion (4 signed shorts).

    Args:
        data: bytes of length 8

    Returns:
        (w, x, y, z) quaternion
    """
    shorts = struct.unpack('<4h', data[:8])
    return tuple(s * EFACTOR_8BYTE_QUAT for s in shorts)


# ─── Uncompressed Quaternion ────────────────────────────────────────────────

def decompress_quat_uncompressed(data):
    """Read an uncompressed quaternion (4 floats, 16 bytes).

    Returns:
        (w, x, y, z) quaternion
    """
    return struct.unpack('<4f', data[:16])


def compress_quat_uncompressed(quat):
    """Write an uncompressed quaternion (4 floats, 16 bytes)."""
    return struct.pack('<4f', *quat)


# ─── 6-Byte Position Compression ───────────────────────────────────────────

def compress_pos_6byte(vec):
    """Compress a position vector to 6 bytes (3 signed shorts × 32000).

    Only valid when all components have absolute value < 1.0.

    Args:
        vec: (x, y, z) position

    Returns:
        bytes object of length 6
    """
    values = []
    for c in vec:
        val = int(round(c * CFACTOR_6BYTE_POS))
        val = max(-32768, min(32767, val))
        values.append(val)
    return struct.pack('<3h', *values)


def decompress_pos_6byte(data):
    """Decompress a 6-byte position (3 signed shorts).

    Args:
        data: bytes of length 6

    Returns:
        (x, y, z) position
    """
    shorts = struct.unpack('<3h', data[:6])
    return tuple(s * EFACTOR_6BYTE_POS for s in shorts)


# ─── Uncompressed Position ─────────────────────────────────────────────────

def decompress_pos_uncompressed(data):
    """Read an uncompressed position (3 floats, 12 bytes).

    Returns:
        (x, y, z) position
    """
    return struct.unpack('<3f', data[:12])


def compress_pos_uncompressed(vec):
    """Write an uncompressed position (3 floats, 12 bytes)."""
    return struct.pack('<3f', *vec)


# ─── Utility ───────────────────────────────────────────────────────────────

def can_compress_pos_6byte(positions):
    """Check if all positions can be compressed to 6 bytes.

    Returns True if all components of all positions have absolute value < 1.0.
    """
    for pos in positions:
        for c in pos:
            if abs(c) >= 1.0:
                return False
    return True


def rot_key_size(flags):
    """Return the size of one rotation key based on compression flags."""
    if flags & ROTATION_COMPRESSED_TO_5_BYTES:
        return SIZE_ROTKEY_5BYTE
    elif flags & ROTATION_COMPRESSED_TO_8_BYTES:
        return SIZE_ROTKEY_8BYTE
    elif flags & ROTATION_UNCOMPRESSED:
        return SIZE_ROTKEY_UNCOMPRESSED
    # Default to 5-byte (most common)
    return SIZE_ROTKEY_5BYTE


def pos_key_size(flags):
    """Return the size of one position key based on compression flags."""
    if flags & POSITION_COMPRESSED_TO_6_BYTES:
        return SIZE_POSKEY_6BYTE
    elif flags & POSITION_UNCOMPRESSED:
        return SIZE_POSKEY_UNCOMPRESSED
    # Default to 6-byte
    return SIZE_POSKEY_6BYTE


def decompress_rotation(data, flags):
    """Decompress a single rotation key based on flags.

    Returns:
        (w, x, y, z) quaternion
    """
    if flags & ROTATION_COMPRESSED_TO_5_BYTES:
        return decompress_quat_5byte(data)
    elif flags & ROTATION_COMPRESSED_TO_8_BYTES:
        return decompress_quat_8byte(data)
    elif flags & ROTATION_UNCOMPRESSED:
        return decompress_quat_uncompressed(data)
    # Default to 5-byte
    return decompress_quat_5byte(data)


def decompress_position(data, flags):
    """Decompress a single position key based on flags.

    Returns:
        (x, y, z) position
    """
    if flags & POSITION_COMPRESSED_TO_6_BYTES:
        return decompress_pos_6byte(data)
    elif flags & POSITION_UNCOMPRESSED:
        return decompress_pos_uncompressed(data)
    # Default to 6-byte
    return decompress_pos_6byte(data)
