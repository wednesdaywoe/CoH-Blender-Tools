"""
CoH GEO binary format reader and writer.

GEO files store 3D geometry (vertices, normals, UVs, triangles) with
optional bone skinning information. They use delta compression for
vertex data and zlib compression for the header block.

File structure (version 8):
    [File Header: 16 bytes]
    [Zlib-compressed header block]
    [Packed data block (geometry)]
    [Struct data block (BoneInfo, etc.)]

Reference: Utilities/GetVrml/src/output.c (outputData, outputPackAllNodes)
           Common/seq/anim.c (geoLoadStubs, readModel, uncompressDeltas)
           Common/seq/anim.h (struct definitions)
"""

import struct
import zlib
from dataclasses import dataclass, field

from .geo_compression import (
    decompress_deltas, compress_deltas,
    decompress_tri_indices, compress_tri_indices,
    decompress_vertices, compress_vertices,
    decompress_normals, compress_normals,
    decompress_uvs, compress_uvs,
    zip_block, unzip_block,
    PACK_F32, PACK_U32,
    SCALE_VERTICES, SCALE_NORMALS, SCALE_UV1, SCALE_UV2,
)

# Current GEO version
GEO_VERSION = 8

# Maximum bones per geometry object
MAX_OBJBONES = 15


# ─── Data Classes ─────────────────────────────────────────────────────────


@dataclass
class TexID:
    """Texture assignment for a run of consecutive triangles."""
    id: int = 0       # Index into texture name table
    count: int = 0    # Number of consecutive triangles with this texture


@dataclass
class BoneInfo:
    """Skinning data for a geometry object."""
    numbones: int = 0
    bone_ids: list = field(default_factory=list)  # Up to MAX_OBJBONES ints
    weights: list = field(default_factory=list)    # Per-vertex: float (primary weight)
    matidxs: list = field(default_factory=list)    # Per-vertex: (idx0, idx1)


@dataclass
class GeoModel:
    """A single mesh within a GEO file."""
    name: str = ""
    radius: float = 0.0
    min: tuple = (0.0, 0.0, 0.0)
    max: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)
    vert_count: int = 0
    tri_count: int = 0
    vertices: list = field(default_factory=list)    # [(x, y, z), ...]
    normals: list = field(default_factory=list)      # [(nx, ny, nz), ...]
    uvs: list = field(default_factory=list)          # [(u, v), ...]
    uvs2: list = field(default_factory=list)         # [(u, v), ...] secondary
    triangles: list = field(default_factory=list)    # [(v0, v1, v2), ...]
    tex_ids: list = field(default_factory=list)      # [TexID, ...]
    bone_info: object = None                         # BoneInfo or None
    lod_distances: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    bone_id: int = -2  # -2 = GEO node


@dataclass
class GeoHeader:
    """Header for a group of models from one source file."""
    name: str = ""
    model_count: int = 0
    length: float = 0.0


@dataclass
class GeoFile:
    """Complete GEO file data."""
    version: int = GEO_VERSION
    headers: list = field(default_factory=list)   # [GeoHeader, ...]
    models: list = field(default_factory=list)     # [GeoModel, ...]
    tex_names: list = field(default_factory=list)  # Global texture name table
    obj_names: list = field(default_factory=list)  # Global object name table


# ─── Name Table Parsing ──────────────────────────────────────────────────


def _parse_name_table(data, offset, block_size):
    """Parse a packed name table from the header block.

    Format: U32 count, then count U32 offsets, then null-terminated strings.
    Offsets are relative to after the offsets array.

    Returns:
        (list of name strings, bytes consumed)
    """
    if block_size == 0:
        return [], 0

    pos = offset
    count = struct.unpack_from('<I', data, pos)[0]
    pos += 4

    offsets = []
    for i in range(count):
        off = struct.unpack_from('<I', data, pos)[0]
        offsets.append(off)
        pos += 4

    strings_base = pos
    names = []
    for off in offsets:
        str_pos = strings_base + off
        end = data.index(b'\x00', str_pos)
        names.append(data[str_pos:end].decode('ascii', errors='replace'))

    return names, block_size


def _parse_string_pool(data, offset, block_size):
    """Parse a raw string pool (used for object names).

    The block is a concatenation of null-terminated strings.
    Returns a list of strings and a dict mapping byte offsets to strings.
    """
    if block_size == 0:
        return [], {}

    pool = data[offset:offset + block_size]
    strings = []
    offset_map = {}
    pos = 0
    while pos < len(pool):
        end = pool.find(b'\x00', pos)
        if end < 0:
            break
        s = pool[pos:end].decode('ascii', errors='replace')
        if s:  # skip empty strings
            strings.append(s)
            offset_map[pos] = s
        pos = end + 1

    return strings, offset_map


def _build_name_table(names):
    """Build a packed name table binary block.

    Returns bytes with format: U32 count, U32 offsets[], null-terminated strings.
    Used for texture names.
    """
    if not names:
        return b''

    count = len(names)
    # Calculate string offsets
    offsets = []
    str_offset = 0
    encoded_strings = []
    for name in names:
        offsets.append(str_offset)
        encoded = name.encode('ascii') + b'\x00'
        encoded_strings.append(encoded)
        str_offset += len(encoded)

    # Build the block
    result = struct.pack('<I', count)
    for off in offsets:
        result += struct.pack('<I', off)
    for enc in encoded_strings:
        result += enc

    return result


def _build_string_pool(names):
    """Build a raw string pool (concatenated null-terminated strings).

    Returns (pool_bytes, offset_map) where offset_map maps name → byte offset.
    Used for object names.
    """
    if not names:
        return b'', {}

    pool = bytearray()
    offset_map = {}
    for name in names:
        offset_map[name] = len(pool)
        pool.extend(name.encode('ascii') + b'\x00')

    return bytes(pool), offset_map


# ─── PolyGrid struct (32 bytes on disk) ──────────────────────────────────

POLYGRID_SIZE = 32


def _read_polygrid(data, offset):
    """Read a PolyGrid struct (32 bytes). Returns dict with fields."""
    cell, px, py, pz, size, inv_size, tag, num_bits = struct.unpack_from(
        '<I3f2fII', data, offset
    )
    return {
        'cell': cell,
        'pos': (px, py, pz),
        'size': size,
        'inv_size': inv_size,
        'tag': tag,
        'num_bits': num_bits,
    }


def _write_polygrid(grid=None):
    """Write a PolyGrid struct (32 bytes). Writes zeros if no grid."""
    if grid is None:
        return b'\x00' * POLYGRID_SIZE
    return struct.pack(
        '<I3f2fII',
        grid.get('cell', 0),
        *grid.get('pos', (0.0, 0.0, 0.0)),
        grid.get('size', 0.0),
        grid.get('inv_size', 0.0),
        grid.get('tag', 0),
        grid.get('num_bits', 0),
    )


# ─── PackData struct (12 bytes) ──────────────────────────────────────────

PACKDATA_SIZE = 12


def _read_packdata(data, offset):
    """Read a PackData struct: packsize(4) + unpacksize(4) + data_offset(4)."""
    packsize, unpacksize, data_offset = struct.unpack_from('<III', data, offset)
    # Sign-extend data_offset in case it represents an offset
    return packsize, unpacksize, data_offset


# ─── ModelHeader (136 bytes on disk) ─────────────────────────────────────
# name[124] + *model_data(4) + length(4) + **models(4) + model_count(4) = 140
# But the source shows sizeof is used, and name is 124 chars.
# From reading the code: name is a char[124] field, then padding/pointers.

MODELHEADER_SIZE = 140  # 124 + 4 + 4 + 4 + 4


def _read_model_header(data, offset):
    """Read a ModelHeader struct."""
    name_bytes = data[offset:offset + 124]
    name_end = name_bytes.find(b'\x00')
    name = name_bytes[:name_end].decode('ascii', errors='replace') if name_end >= 0 else name_bytes.decode('ascii', errors='replace')

    # Skip model_data pointer (4 bytes, unused)
    length = struct.unpack_from('<f', data, offset + 128)[0]
    # Skip models pointer (4 bytes, unused)
    model_count = struct.unpack_from('<I', data, offset + 136)[0]

    return GeoHeader(name=name, model_count=model_count, length=length)


# ─── Reader ──────────────────────────────────────────────────────────────


def read_geo(filepath):
    """Read a GEO binary file.

    Args:
        filepath: Path to the .geo file

    Returns:
        GeoFile with parsed geometry data
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()

    return _parse_geo(file_data)


def _parse_geo(file_data):
    """Parse GEO binary data."""
    if len(file_data) < 8:
        raise ValueError("File too small to be a GEO file")

    # Read first two U32s to detect format version
    ziplen, second = struct.unpack_from('<II', file_data, 0)

    if second == 0:
        # New format (v2+): 16-byte file header
        if len(file_data) < 16:
            raise ValueError("File too small for v2+ GEO header")
        version = struct.unpack_from('<I', file_data, 8)[0]
        header_len = struct.unpack_from('<I', file_data, 12)[0]

        if version > 8 or version == 6:
            raise ValueError(f"Unsupported GEO version: {version}")

        # ziplen includes 12-byte bias (for pig system caching)
        compressed_header_size = ziplen - 12
        data_start = 16
    else:
        # Old format (v1): 8-byte file header
        # second field IS the header_len (non-zero)
        version = 1
        header_len = second
        # In v1, ziplen counts bytes after the first U32 (includes headersize field)
        # Actual compressed data is ziplen-4 bytes starting at offset 8
        compressed_header_size = ziplen - 4
        data_start = 8

    compressed_header = file_data[data_start:data_start + compressed_header_size]
    header_data = zlib.decompress(compressed_header)

    if len(header_data) != header_len:
        raise ValueError(
            f"Header decompressed size mismatch: expected {header_len}, got {len(header_data)}"
        )

    # Packed data starts after the compressed header
    if version == 1:
        # v1: packed data at offset 8 + ziplen (old bug: +4 padding after compressed data)
        packed_data_offset = 8 + ziplen
    else:
        # v2+: packed data immediately after compressed header
        packed_data_offset = data_start + compressed_header_size

    # Parse header contents
    pos = 0

    # Data size (total packed + struct data)
    datasize = struct.unpack_from('<I', header_data, pos)[0]
    pos += 4

    # Block sizes
    texname_blocksize = struct.unpack_from('<I', header_data, pos)[0]
    pos += 4
    objname_blocksize = struct.unpack_from('<I', header_data, pos)[0]
    pos += 4
    texidx_blocksize = struct.unpack_from('<I', header_data, pos)[0]
    pos += 4

    # v2-v6 have an additional LOD info block size
    lodinfo_blocksize = 0
    if 2 <= version <= 6:
        lodinfo_blocksize = struct.unpack_from('<I', header_data, pos)[0]
        pos += 4

    # Texture name table (packed format: count + offsets + strings)
    tex_names, consumed = _parse_name_table(header_data, pos, texname_blocksize)
    pos += texname_blocksize

    # Object name table (raw string pool — models reference by byte offset)
    obj_names_list, obj_name_offsets = _parse_string_pool(
        header_data, pos, objname_blocksize
    )
    pos += objname_blocksize

    # Texture index block (raw TexID data, parsed per-model later)
    texidx_data = header_data[pos:pos + texidx_blocksize]
    pos += texidx_blocksize

    # v2-v6: skip LOD info data block
    if 2 <= version <= 6:
        pos += lodinfo_blocksize

    # Exactly ONE ModelHeader (140 bytes)
    hdr = _read_model_header(header_data, pos)
    headers = [hdr]
    total_models = hdr.model_count
    pos += MODELHEADER_SIZE

    # Read packed data and struct data from the file
    packed_and_struct = file_data[packed_data_offset:packed_data_offset + datasize]

    # Read model structs (they follow the ModelHeader in the decompressed header)
    models = []
    for model_idx in range(total_models):
        if version < 3:
            model, consumed = _read_model_v2(
                header_data, pos, packed_and_struct, texidx_data,
                tex_names, obj_name_offsets,
            )
            pos += consumed
        else:
            model = _read_model_v3plus(
                header_data, pos, packed_and_struct, texidx_data,
                tex_names, obj_name_offsets, version
            )
            # v3+ structs start with struct_size
            struct_size = struct.unpack_from('<I', header_data, pos)[0]
            pos += struct_size
        models.append(model)

    return GeoFile(
        version=version,
        headers=headers,
        models=models,
        tex_names=tex_names,
        obj_names=obj_names_list,
    )


def _read_model_v2(header_data, pos, packed_data, texidx_data,
                    tex_names, obj_name_offsets):
    """Read a ModelFormatOnDisk_v2 struct (fixed layout, used by v1 and v2 files).

    The v2 struct uses a fixed binary layout with pointer fields stored as
    offsets. Fields differ from v3+ (no sts3, no struct_size prefix).

    Returns:
        (GeoModel, bytes_consumed)
    """
    model = GeoModel()
    offset = pos

    # flags (U32)
    flags = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # radius (F32)
    model.radius = struct.unpack_from('<f', header_data, offset)[0]
    offset += 4

    # vbo pointer (U32, skip)
    offset += 4

    # tex_count (I32)
    tex_count = struct.unpack_from('<i', header_data, offset)[0]
    offset += 4

    # id (S16)
    model.bone_id = struct.unpack_from('<h', header_data, offset)[0]
    offset += 2

    # blend_mode (U8)
    offset += 1

    # loadstate (U8)
    offset += 1

    # boneinfo pointer (U32, stored as offset)
    boneinfo_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # trick pointer (U32, skip)
    offset += 4

    # vert_count (I32)
    model.vert_count = struct.unpack_from('<i', header_data, offset)[0]
    offset += 4

    # tri_count (I32)
    model.tri_count = struct.unpack_from('<i', header_data, offset)[0]
    offset += 4

    # tex_idx pointer (U32, stored as byte offset into texidx_data)
    texidx_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # PolyGrid (32 bytes)
    grid = _read_polygrid(header_data, offset)
    offset += POLYGRID_SIZE

    # ctris pointer (U32, skip)
    offset += 4

    # tags pointer (U32, skip)
    offset += 4

    # name pointer (U32, stored as byte offset into objname pool)
    name_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # api pointer (U32)
    api_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # extra pointer (U32, skip)
    offset += 4

    # scale (Vec3)
    sx, sy, sz = struct.unpack_from('<3f', header_data, offset)
    model.scale = (sx, sy, sz)
    offset += 12

    # min (Vec3)
    mnx, mny, mnz = struct.unpack_from('<3f', header_data, offset)
    model.min = (mnx, mny, mnz)
    offset += 12

    # max (Vec3)
    mxx, mxy, mxz = struct.unpack_from('<3f', header_data, offset)
    model.max = (mxx, mxy, mxz)
    offset += 12

    # gld pointer (U32, skip)
    offset += 4

    # PackBlockOnDisk: 7 PackData structs (no sts3 in v2)
    pack_fields_v2 = ['tris', 'verts', 'norms', 'sts',
                      'weights', 'matidxs', 'grid']
    pack_data = {}
    for field_name in pack_fields_v2:
        ps, us, do = _read_packdata(header_data, offset)
        pack_data[field_name] = (ps, us, do)
        offset += PACKDATA_SIZE

    # v2 has no sts3, reductions, or reflection_quads
    pack_data['st3s'] = (0, 0, 0)
    pack_data['reductions'] = (0, 0, 0)
    pack_data['reflection_quads'] = (0, 0, 0)

    model.lod_distances = [-1.0, -1.0, -1.0]

    # Resolve model name
    if name_offset in obj_name_offsets:
        model.name = obj_name_offsets[name_offset]
    else:
        model.name = f"model_{name_offset}"

    # Resolve texture IDs
    if tex_count > 0 and texidx_data:
        tid_pos = texidx_offset
        for t in range(tex_count):
            if tid_pos + 4 <= len(texidx_data):
                tid, tcount = struct.unpack_from('<HH', texidx_data, tid_pos)
                model.tex_ids.append(TexID(id=tid, count=tcount))
                tid_pos += 4

    # Decompress geometry
    _decompress_model_geometry(model, pack_data, packed_data, boneinfo_offset)

    consumed = offset - pos
    return model, consumed


def _read_model_v3plus(header_data, pos, packed_data, texidx_data,
                       tex_names, obj_name_offsets, version):
    """Read a single model struct (v3-v8 variable-length format).

    Args:
        obj_name_offsets: dict mapping byte offset → name string
    """
    model = GeoModel()

    # Read struct fields
    struct_size = struct.unpack_from('<I', header_data, pos)[0]
    offset = pos + 4

    model.radius = struct.unpack_from('<f', header_data, offset)[0]
    offset += 4

    tex_count = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    boneinfo_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    model.vert_count = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    model.tri_count = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    reflection_quad_count = 0
    if version >= 8:
        reflection_quad_count = struct.unpack_from('<I', header_data, offset)[0]
        offset += 4

    texidx_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # PolyGrid (32 bytes)
    grid = _read_polygrid(header_data, offset)
    offset += POLYGRID_SIZE

    # Name offset (byte offset into objname string pool)
    name_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # AltPivotInfo offset
    api_offset = struct.unpack_from('<I', header_data, offset)[0]
    offset += 4

    # Scale (Vec3)
    sx, sy, sz = struct.unpack_from('<3f', header_data, offset)
    model.scale = (sx, sy, sz)
    offset += 12

    # Min (Vec3)
    mnx, mny, mnz = struct.unpack_from('<3f', header_data, offset)
    model.min = (mnx, mny, mnz)
    offset += 12

    # Max (Vec3)
    mxx, mxy, mxz = struct.unpack_from('<3f', header_data, offset)
    model.max = (mxx, mxy, mxz)
    offset += 12

    # PackData structs (12 bytes each)
    # Order: tris, verts, norms, sts, st3s, weights, matidxs, grid
    pack_fields = ['tris', 'verts', 'norms', 'sts', 'st3s',
                   'weights', 'matidxs', 'grid']

    pack_data = {}
    for field_name in pack_fields:
        ps, us, do = _read_packdata(header_data, offset)
        pack_data[field_name] = (ps, us, do)
        offset += PACKDATA_SIZE

    # v4 has two extra lightmap PackData structs (skip them)
    if version == 4:
        offset += PACKDATA_SIZE * 2  # lmap_utransforms + lmap_vtransforms

    # v7+ adds reductions pack
    if version >= 7:
        ps, us, do = _read_packdata(header_data, offset)
        pack_data['reductions'] = (ps, us, do)
        offset += PACKDATA_SIZE
    else:
        pack_data['reductions'] = (0, 0, 0)

    # v8+ adds reflection_quads pack
    if version >= 8:
        ps, us, do = _read_packdata(header_data, offset)
        pack_data['reflection_quads'] = (ps, us, do)
        offset += PACKDATA_SIZE
    else:
        pack_data['reflection_quads'] = (0, 0, 0)

    # v7+ has LOD distances (3 floats)
    if version >= 7:
        lod0, lod1, lod2 = struct.unpack_from('<3f', header_data, offset)
        model.lod_distances = [lod0, lod1, lod2]
        offset += 12
    else:
        model.lod_distances = [-1.0, -1.0, -1.0]

    # Bone ID (S16)
    model.bone_id = struct.unpack_from('<h', header_data, offset)[0]
    offset += 2

    # Resolve model name from object name string pool (by byte offset)
    if name_offset in obj_name_offsets:
        model.name = obj_name_offsets[name_offset]
    else:
        model.name = f"model_{name_offset}"

    # Resolve texture IDs
    if tex_count > 0 and texidx_data:
        tid_pos = texidx_offset
        for t in range(tex_count):
            if tid_pos + 4 <= len(texidx_data):
                tid, tcount = struct.unpack_from('<HH', texidx_data, tid_pos)
                model.tex_ids.append(TexID(id=tid, count=tcount))
                tid_pos += 4

    # Decompress geometry from packed data
    _decompress_model_geometry(model, pack_data, packed_data, boneinfo_offset)

    return model


def _extract_pack_block(pack_info, packed_data):
    """Extract and decompress a pack data block.

    Args:
        pack_info: (packsize, unpacksize, data_offset) tuple
        packed_data: The full packed data block

    Returns:
        Decompressed bytes, or empty bytes if no data
    """
    packsize, unpacksize, data_offset = pack_info

    if unpacksize == 0:
        return b''

    raw = packed_data[data_offset:data_offset + (packsize if packsize > 0 else unpacksize)]
    return unzip_block(raw, packsize, unpacksize)


def _decompress_model_geometry(model, pack_data, packed_data, boneinfo_offset):
    """Decompress all geometry data for a model."""
    # Triangles
    if model.tri_count > 0 and pack_data['tris'][1] > 0:
        tri_data = _extract_pack_block(pack_data['tris'], packed_data)
        if tri_data:
            model.triangles = decompress_tri_indices(tri_data, model.tri_count)

    # Vertices
    if model.vert_count > 0 and pack_data['verts'][1] > 0:
        vert_data = _extract_pack_block(pack_data['verts'], packed_data)
        if vert_data:
            model.vertices = decompress_vertices(vert_data, model.vert_count)

    # Normals
    if model.vert_count > 0 and pack_data['norms'][1] > 0:
        norm_data = _extract_pack_block(pack_data['norms'], packed_data)
        if norm_data:
            model.normals = decompress_normals(norm_data, model.vert_count)

    # UV coordinates (set 1)
    if model.vert_count > 0 and pack_data['sts'][1] > 0:
        uv_data = _extract_pack_block(pack_data['sts'], packed_data)
        if uv_data:
            model.uvs = decompress_uvs(uv_data, model.vert_count)

    # UV coordinates (set 2)
    if model.vert_count > 0 and pack_data['st3s'][1] > 0:
        uv2_data = _extract_pack_block(pack_data['st3s'], packed_data)
        if uv2_data:
            model.uvs2 = decompress_uvs(uv2_data, model.vert_count)

    # Bone weights and matrix indices
    if boneinfo_offset > 0 and model.vert_count > 0:
        # Weights are U8 per vertex (scaled by 255)
        if pack_data['weights'][1] > 0:
            weight_data = _extract_pack_block(pack_data['weights'], packed_data)
            if weight_data:
                model.bone_info = model.bone_info or BoneInfo()
                model.bone_info.weights = [b / 255.0 for b in weight_data]

        # Matrix indices are U8 pairs per vertex
        if pack_data['matidxs'][1] > 0:
            matidx_data = _extract_pack_block(pack_data['matidxs'], packed_data)
            if matidx_data:
                model.bone_info = model.bone_info or BoneInfo()
                model.bone_info.matidxs = [
                    (matidx_data[i * 2], matidx_data[i * 2 + 1])
                    for i in range(model.vert_count)
                ]


# ─── Writer ──────────────────────────────────────────────────────────────


def write_geo(filepath, geo_file):
    """Write a GeoFile to a binary GEO file.

    Args:
        filepath: Output file path
        geo_file: GeoFile to write
    """
    with open(filepath, 'wb') as f:
        _write_geo(f, geo_file)


def _write_geo(f, geo_file):
    """Write GEO format to a file handle."""
    version = geo_file.version

    # Build name tables
    texname_block = _build_name_table(geo_file.tex_names)
    objname_block, objname_offset_map = _build_string_pool(geo_file.obj_names)

    # Align object name block to 4 bytes
    while len(objname_block) % 4 != 0:
        objname_block += b'\x00'

    # Build texture index block
    texidx_block = b''
    for model in geo_file.models:
        for tid in model.tex_ids:
            texidx_block += struct.pack('<HH', tid.id, tid.count)

    # Build packed data and struct data
    packed_data = bytearray()
    struct_data = bytearray()

    # Compress and pack geometry for each model
    model_pack_infos = []
    for model in geo_file.models:
        pack_info = _compress_model_geometry(model, packed_data, struct_data)
        model_pack_infos.append(pack_info)

    # Align packed data to 4 bytes
    while len(packed_data) % 4 != 0:
        packed_data += b'\x00'

    # Build model header structs
    model_headers_bin = b''
    for hdr in geo_file.headers:
        name_bytes = hdr.name.encode('ascii')[:123]
        name_bytes = name_bytes + b'\x00' * (124 - len(name_bytes))
        model_headers_bin += name_bytes
        model_headers_bin += struct.pack('<I', 0)   # model_data pointer (unused)
        model_headers_bin += struct.pack('<f', hdr.length)
        model_headers_bin += struct.pack('<I', 0)   # models pointer (unused)
        model_headers_bin += struct.pack('<I', hdr.model_count)

    # Build model struct data
    model_structs_bin = b''
    texidx_pos = 0
    for idx, model in enumerate(geo_file.models):
        pack_info = model_pack_infos[idx]

        # Find name byte offset in obj_names pool
        name_byte_offset = objname_offset_map.get(model.name, 0)

        model_struct = _build_model_struct_v8(
            model, pack_info, name_byte_offset, texidx_pos, version
        )
        model_structs_bin += model_struct

        # Advance texidx position
        texidx_pos += len(model.tex_ids) * 4

    # Assemble header block
    datasize = len(packed_data) + len(struct_data)

    header_block = struct.pack('<I', datasize)
    header_block += struct.pack('<I', len(texname_block))
    header_block += struct.pack('<I', len(objname_block))
    header_block += struct.pack('<I', len(texidx_block))
    header_block += texname_block
    header_block += objname_block
    header_block += texidx_block
    header_block += model_headers_bin
    header_block += model_structs_bin

    header_len = len(header_block)

    # Compress header
    compressed_header = zlib.compress(header_block)

    # Write file
    ziplen = len(compressed_header) + 12  # 12-byte bias for pig system
    f.write(struct.pack('<I', ziplen))
    f.write(struct.pack('<I', 0))         # zero marker
    f.write(struct.pack('<I', version))
    f.write(struct.pack('<I', header_len))
    f.write(compressed_header)
    f.write(bytes(packed_data))
    f.write(bytes(struct_data))


def _compress_model_geometry(model, packed_data, struct_data):
    """Compress all geometry for a model, appending to packed_data.

    Returns dict of pack_info tuples: {field: (packsize, unpacksize, offset)}
    """
    pack_info = {}

    def _add_pack(field_name, raw_data):
        if not raw_data:
            pack_info[field_name] = (0, 0, 0)
            return
        compressed, packsize, unpacksize = zip_block(raw_data)
        offset = len(packed_data)
        packed_data.extend(compressed)
        pack_info[field_name] = (packsize, unpacksize, offset)

    # Triangles
    if model.triangles:
        tri_raw = compress_tri_indices(model.triangles, model.tri_count)
        _add_pack('tris', tri_raw)
    else:
        _add_pack('tris', None)

    # Vertices
    if model.vertices:
        vert_raw = compress_vertices(model.vertices, model.vert_count)
        _add_pack('verts', vert_raw)
    else:
        _add_pack('verts', None)

    # Normals
    if model.normals:
        norm_raw = compress_normals(model.normals, model.vert_count)
        _add_pack('norms', norm_raw)
    else:
        _add_pack('norms', None)

    # UVs
    if model.uvs:
        uv_raw = compress_uvs(model.uvs, model.vert_count)
        _add_pack('sts', uv_raw)
    else:
        _add_pack('sts', None)

    # UVs (set 2)
    if model.uvs2:
        uv2_raw = compress_uvs(model.uvs2, model.vert_count, secondary=True)
        _add_pack('st3s', uv2_raw)
    else:
        _add_pack('st3s', None)

    # Bone weights
    if model.bone_info and model.bone_info.weights:
        weight_bytes = bytes(
            min(255, max(0, int(w * 255)))
            for w in model.bone_info.weights
        )
        _add_pack('weights', weight_bytes)
    else:
        _add_pack('weights', None)

    # Bone matrix indices
    if model.bone_info and model.bone_info.matidxs:
        matidx_bytes = bytearray()
        for idx0, idx1 in model.bone_info.matidxs:
            matidx_bytes.append(idx0 & 0xFF)
            matidx_bytes.append(idx1 & 0xFF)
        _add_pack('matidxs', bytes(matidx_bytes))
    else:
        _add_pack('matidxs', None)

    # Grid, reductions, reflection_quads (write empty for now)
    _add_pack('grid', None)
    _add_pack('reductions', None)
    _add_pack('reflection_quads', None)

    # BoneInfo struct data
    if model.bone_info and model.bone_info.numbones > 0:
        bi_offset = len(struct_data)
        # BoneInfo: numbones(4) + bone_ID[15](60) + weights_ptr(4) + matidxs_ptr(4) = 72
        bi_data = struct.pack('<I', model.bone_info.numbones)
        for i in range(MAX_OBJBONES):
            if i < len(model.bone_info.bone_ids):
                bi_data += struct.pack('<I', model.bone_info.bone_ids[i])
            else:
                bi_data += struct.pack('<I', 0)
        bi_data += struct.pack('<I', 0)  # weights pointer (resolved at load)
        bi_data += struct.pack('<I', 0)  # matidxs pointer (resolved at load)
        struct_data.extend(bi_data)
        pack_info['boneinfo_offset'] = bi_offset
    else:
        pack_info['boneinfo_offset'] = 0

    return pack_info


def _build_model_struct_v8(model, pack_info, name_idx, texidx_offset, version):
    """Build a ModelFormatOnDisk_v8 binary struct."""
    parts = bytearray()

    # struct_size placeholder (filled at end)
    parts += struct.pack('<I', 0)

    # radius
    parts += struct.pack('<f', model.radius)

    # tex_count
    parts += struct.pack('<I', len(model.tex_ids))

    # boneinfo offset
    parts += struct.pack('<I', pack_info.get('boneinfo_offset', 0))

    # vert_count
    parts += struct.pack('<I', model.vert_count)

    # tri_count
    parts += struct.pack('<I', model.tri_count)

    # reflection_quad_count (v8)
    if version >= 8:
        parts += struct.pack('<I', 0)

    # tex_idx offset
    parts += struct.pack('<I', texidx_offset)

    # PolyGrid (32 bytes, zeros)
    parts += _write_polygrid()

    # name offset (index into obj_names)
    parts += struct.pack('<I', name_idx)

    # api offset
    parts += struct.pack('<I', 0)

    # scale
    parts += struct.pack('<3f', *model.scale)

    # min
    parts += struct.pack('<3f', *model.min)

    # max
    parts += struct.pack('<3f', *model.max)

    # PackData structs (10 for v8)
    pack_fields = [
        'tris', 'verts', 'norms', 'sts', 'st3s',
        'weights', 'matidxs', 'grid', 'reductions',
    ]
    if version >= 8:
        pack_fields.append('reflection_quads')

    for field_name in pack_fields:
        ps, us, do = pack_info.get(field_name, (0, 0, 0))
        parts += struct.pack('<III', ps, us, do)

    # LOD distances
    parts += struct.pack('<3f', *model.lod_distances)

    # Bone ID (S16) + 2 bytes padding
    parts += struct.pack('<h', model.bone_id)
    parts += b'\x00\x00'

    # Fix struct_size
    struct.pack_into('<I', parts, 0, len(parts))

    return bytes(parts)
