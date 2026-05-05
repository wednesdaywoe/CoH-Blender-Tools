"""
Delta compression for CoH GEO binary files.

The GEO format uses a custom delta compression scheme for vertex positions,
normals, UV coordinates, and triangle indices. Each value is stored as a
delta from the previous value, with a 2-bit code indicating the byte width
of each delta.

Compressed block layout:
    [bit codes: 2 bits per component, packed little-endian into U32s]
    [1 byte: log2(float_scale)]
    [data bytes: variable length per code]

Per-component codes:
    0 → delta is 0, no data bytes
    1 → delta in 1 byte (signed via bias: value - 0x7F)
    2 → delta in 2 bytes LE (signed via bias: value - 0x7FFF)
    3 → delta in 4 bytes LE (raw int32 for floats, raw delta for ints)

Reference: Utilities/GetVrml/src/output.c (compressDeltas, zipDeltas)
           Common/seq/anim.c (uncompressDeltas)
"""

import math
import struct
import zlib


# Pack types matching the C enum
PACK_F32 = 0
PACK_U32 = 1
PACK_U16 = 2

# Scale factors used by the GEO format
SCALE_VERTICES = 32768.0
SCALE_NORMALS = 256.0
SCALE_UV1 = 4096.0
SCALE_UV2 = 32768.0


def _log2_int(val):
    """Integer log2, matching C's log2() for powers of 2."""
    if val <= 0:
        return 0
    return int(math.log2(val))


def _quant_f32(val, float_scale, inv_float_scale):
    """Quantize a float value matching CoH's quantF32().

    Multiplies by scale, truncates to int, clears LSB, divides back.
    """
    ival = int(val * float_scale)
    ival &= ~1  # Clear LSB
    return ival * inv_float_scale


# ─── Decompression ────────────────────────────────────────────────────────


def decompress_deltas(data, stride, count, pack_type):
    """Decompress delta-encoded data.

    Matches CoH's uncompressDeltas() exactly.

    Args:
        data: Raw compressed bytes
        stride: Components per element (3 for Vec3, 2 for Vec2)
        count: Number of elements
        pack_type: PACK_F32, PACK_U32, or PACK_U16

    Returns:
        Flat list of decoded values (floats for PACK_F32, ints for PACK_U32/U16)
    """
    if not count or not data:
        return []

    src = bytes(data)  # ensure we have bytes
    total_components = count * stride

    # Bit codes are at the start: 2 bits per component, packed into U32s LE
    bit_bytes = (2 * total_components + 7) // 8

    # Data bytes start after the bit codes
    data_offset = bit_bytes

    # First data byte is log2(float_scale)
    float_scale_log2 = src[data_offset]
    float_scale = 1 << float_scale_log2 if float_scale_log2 > 0 else 0
    inv_float_scale = 1.0 / float_scale if float_scale else 1.0
    byte_pos = data_offset + 1

    # State tracking for delta decoding
    f_last = [0.0] * stride
    i_last = [0] * stride

    result = []
    bit_pos = 0

    for i in range(count):
        for j in range(stride):
            # Read 2-bit code from the bit array (LE U32 packing)
            word_idx = bit_pos >> 5
            bit_idx = bit_pos & 31
            # Read U32 little-endian from the bit array
            word_offset = word_idx * 4
            if word_offset + 4 <= bit_bytes:
                word = struct.unpack_from('<I', src, word_offset)[0]
            else:
                # Handle partial last word
                remaining = src[word_offset:word_offset + 4]
                remaining = remaining + b'\x00' * (4 - len(remaining))
                word = struct.unpack('<I', remaining)[0]
            code = (word >> bit_idx) & 3
            bit_pos += 2

            # Read delta based on code
            if code == 0:
                i_delta = 0
            elif code == 1:
                i_delta = src[byte_pos] - 0x7F
                byte_pos += 1
            elif code == 2:
                i_delta = (src[byte_pos] | (src[byte_pos + 1] << 8)) - 0x7FFF
                byte_pos += 2
            else:  # code == 3
                # Read as signed 32-bit (matching C's int behavior)
                i_delta = struct.unpack_from('<i', src, byte_pos)[0]
                byte_pos += 4

            if pack_type == PACK_F32:
                if code != 3:
                    f_delta = i_delta * inv_float_scale
                else:
                    # Code 3 stores raw float bits — reinterpret as float
                    f_delta = struct.unpack('<f', struct.pack('<i', i_delta))[0]
                f_last[j] = f_last[j] + f_delta
                result.append(f_last[j])
            elif pack_type == PACK_U32:
                i_last[j] = i_last[j] + i_delta + 1
                result.append(i_last[j])
            elif pack_type == PACK_U16:
                i_last[j] = i_last[j] + i_delta + 1
                result.append(i_last[j])

    return result


# ─── Compression ──────────────────────────────────────────────────────────


def compress_deltas(values, stride, count, pack_type, float_scale=0.0):
    """Compress data using delta encoding.

    Matches CoH's compressDeltas() exactly.

    Args:
        values: Flat list/array of values to compress
        stride: Components per element (3 for Vec3, 2 for Vec2)
        count: Number of elements
        pack_type: PACK_F32, PACK_U32, or PACK_U16
        float_scale: Scale factor for float quantization (e.g. 32768.0)

    Returns:
        Compressed bytes
    """
    if not values or not count:
        return b''

    total_components = count * stride
    inv_float_scale = 1.0 / float_scale if float_scale else 1.0

    # Allocate bit array and byte buffer
    bit_word_count = (2 * total_components + 31) // 32
    bits = [0] * bit_word_count
    byte_data = bytearray()

    # First byte of data section is log2(float_scale)
    byte_data.append(_log2_int(int(float_scale)) if float_scale > 0 else 0)

    f_last = [0.0] * stride
    i_last = [0] * stride
    bit_pos = 0
    val_idx = 0

    for i in range(count):
        for j in range(stride):
            val = values[val_idx]
            val_idx += 1

            if pack_type == PACK_F32:
                f_delta = _quant_f32(val, float_scale, inv_float_scale) - f_last[j]
                val8 = int(f_delta * float_scale + 0x7F)
                val16 = int(f_delta * float_scale + 0x7FFF)
                val32 = struct.unpack('<i', struct.pack('<f', f_delta))[0]
            else:
                t = int(val)
                i_delta = t - i_last[j] - 1
                i_last[j] = t
                val8 = i_delta + 0x7F
                val16 = i_delta + 0x7FFF
                val32 = i_delta

            if val8 == 0x7F:
                code = 0
            elif (val8 & ~0xFF) == 0:
                code = 1
                out_val = val8
                if pack_type == PACK_F32:
                    f_last[j] = (val8 - 0x7F) * inv_float_scale + f_last[j]
            elif (val16 & ~0xFFFF) == 0:
                code = 2
                out_val = val16
                if pack_type == PACK_F32:
                    f_last[j] = (val16 - 0x7FFF) * inv_float_scale + f_last[j]
            else:
                code = 3
                out_val = val32
                if pack_type == PACK_F32:
                    f_last[j] = f_delta + f_last[j]

            # Store 2-bit code in bit array
            word_idx = bit_pos >> 5
            bit_idx = bit_pos & 31
            bits[word_idx] |= (code << bit_idx)
            bit_pos += 2

            # Store data bytes (little-endian)
            byte_count = [0, 1, 2, 4][code]
            if code != 0:
                for k in range(byte_count):
                    byte_data.append((out_val >> (k * 8)) & 0xFF)

    # Assemble: bit array first, then byte data
    bit_bytes = (bit_pos + 7) // 8
    packed = bytearray()
    for w in bits:
        packed.extend(struct.pack('<I', w & 0xFFFFFFFF))
    # Trim bit array to exact byte count
    packed = packed[:bit_bytes]
    packed.extend(byte_data)

    return bytes(packed)


# ─── High-level helpers ───────────────────────────────────────────────────


def zip_block(data):
    """Optionally zlib-compress a data block.

    Returns (compressed_data, packsize, unpacksize) where packsize=0
    means data was not compressed (compression didn't save enough).
    """
    if not data:
        return b'', 0, 0

    unpacksize = len(data)
    compressed = zlib.compress(data)

    if len(compressed) < unpacksize * 0.8:
        return compressed, len(compressed), unpacksize
    else:
        return data, 0, unpacksize


def unzip_block(data, packsize, unpacksize):
    """Decompress a zlib-compressed block.

    If packsize == 0, data is not compressed.
    """
    if not data:
        return b''

    if packsize > 0:
        return zlib.decompress(data, bufsize=unpacksize)
    else:
        return data[:unpacksize]


def compress_vertices(positions, count):
    """Compress vertex positions (Vec3, scale=32768)."""
    flat = []
    for pos in positions:
        flat.extend(pos)
    return compress_deltas(flat, 3, count, PACK_F32, SCALE_VERTICES)


def decompress_vertices(data, count):
    """Decompress vertex positions to list of (x, y, z) tuples."""
    flat = decompress_deltas(data, 3, count, PACK_F32)
    return [tuple(flat[i * 3:(i + 1) * 3]) for i in range(count)]


def compress_normals(normals, count):
    """Compress normals (Vec3, scale=256)."""
    flat = []
    for n in normals:
        flat.extend(n)
    return compress_deltas(flat, 3, count, PACK_F32, SCALE_NORMALS)


def decompress_normals(data, count):
    """Decompress normals to list of (nx, ny, nz) tuples."""
    flat = decompress_deltas(data, 3, count, PACK_F32)
    return [tuple(flat[i * 3:(i + 1) * 3]) for i in range(count)]


def compress_uvs(uvs, count, secondary=False):
    """Compress UV coordinates (Vec2, scale=4096 or 32768 for secondary)."""
    flat = []
    for uv in uvs:
        flat.extend(uv)
    scale = SCALE_UV2 if secondary else SCALE_UV1
    return compress_deltas(flat, 2, count, PACK_F32, scale)


def decompress_uvs(data, count):
    """Decompress UV coordinates to list of (u, v) tuples."""
    flat = decompress_deltas(data, 2, count, PACK_F32)
    return [tuple(flat[i * 2:(i + 1) * 2]) for i in range(count)]


def compress_tri_indices(triangles, tri_count):
    """Compress triangle indices (3 ints per tri, PACK_U32)."""
    flat = []
    for tri in triangles:
        flat.extend(tri)
    return compress_deltas(flat, 3, tri_count, PACK_U32, 0)


def decompress_tri_indices(data, tri_count):
    """Decompress triangle indices to list of (v0, v1, v2) tuples."""
    flat = decompress_deltas(data, 3, tri_count, PACK_U32)
    return [tuple(flat[i * 3:(i + 1) * 3]) for i in range(tri_count)]
