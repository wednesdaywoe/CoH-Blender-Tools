"""
CoH .texture format reader and writer.

A .texture file wraps a DDS file with a CoH-specific header containing
metadata like dimensions, flags, and the texture name. This replaces
the GetTex utility for converting TGA/PNG images to game-ready textures.

File layout:
    TextureFileHeader (32 bytes)
    Texture name string (null-terminated, variable length)
    [Optional: TextureFileMipHeader (16 bytes) for v2 format]
    DDS file data ("DDS " magic + header + pixel data)

Reference: Game/src/render/tex.h (TextureFileHeader)
           Utilities/GetTex/src/gettex.c (writeMipMapHeader)
"""

import struct
import os
from dataclasses import dataclass, field

from .dds import (
    read_dds, write_dds, dds_mip_size,
    DDS_MAGIC, DDS_HEADER_SIZE,
    FOURCC_DXT1, FOURCC_DXT5,
)


# TextureFileHeader size
TEXTURE_HEADER_SIZE = 32

# OpenGL format codes used in TextureFileMipHeader
GL_COMPRESSED_DXT1 = 0x83F1
GL_COMPRESSED_DXT5 = 0x83F3


@dataclass
class TextureData:
    """Parsed .texture file data."""
    name: str = ""
    width: int = 0
    height: int = 0
    flags: int = 0
    alpha: bool = False
    fade: tuple = (0.0, 0.0)
    dds_data: bytes = b''


# ─── Reader ──────────────────────────────────────────────────────────────


def read_texture(filepath):
    """Read a CoH .texture file.

    Args:
        filepath: Path to the .texture file

    Returns:
        TextureData with parsed header and DDS data
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()

    return _parse_texture(file_data)


def _parse_texture(file_data):
    """Parse .texture file data."""
    if len(file_data) < TEXTURE_HEADER_SIZE:
        raise ValueError("File too small for .texture header")

    # TextureFileHeader (32 bytes)
    header_size = struct.unpack_from('<i', file_data, 0)[0]
    file_size = struct.unpack_from('<i', file_data, 4)[0]
    width = struct.unpack_from('<i', file_data, 8)[0]
    height = struct.unpack_from('<i', file_data, 12)[0]
    flags = struct.unpack_from('<I', file_data, 16)[0]
    fade_min = struct.unpack_from('<f', file_data, 20)[0]
    fade_max = struct.unpack_from('<f', file_data, 24)[0]
    alpha = file_data[28]
    pad = file_data[29:32]

    # Read texture name (null-terminated string after header)
    name_start = TEXTURE_HEADER_SIZE
    name_end = file_data.index(b'\x00', name_start)
    name = file_data[name_start:name_end].decode('ascii', errors='replace')

    # Check for v2 format (pad == b'TX2')
    is_v2 = (pad == b'TX2')

    # DDS data starts at header_size offset
    dds_data = file_data[header_size:]

    return TextureData(
        name=name,
        width=width,
        height=height,
        flags=flags,
        alpha=bool(alpha),
        fade=(fade_min, fade_max),
        dds_data=dds_data,
    )


# ─── Writer ──────────────────────────────────────────────────────────────


def write_texture(filepath, dds_data, name="", width=0, height=0,
                  flags=0, alpha=False, fade=(0.0, 0.0)):
    """Write a CoH .texture file.

    Args:
        filepath: Output file path
        dds_data: Complete DDS file data (with "DDS " magic)
        name: Texture name string
        width: Texture width (auto-detected from DDS if 0)
        height: Texture height (auto-detected from DDS if 0)
        flags: TexOptFlags
        alpha: Whether texture has alpha channel
        fade: (fade_min, fade_max) tuple
    """
    # Auto-detect dimensions from DDS header if not provided
    if (width == 0 or height == 0) and len(dds_data) >= 128:
        dds_info = read_dds(dds_data)
        width = dds_info['width']
        height = dds_info['height']
        if dds_info['fourcc'] == FOURCC_DXT5:
            alpha = True

    # Build the file
    name_bytes = name.encode('ascii') + b'\x00'
    header_size = TEXTURE_HEADER_SIZE + len(name_bytes)

    # Align header_size to 4 bytes
    while header_size % 4 != 0:
        name_bytes += b'\x00'
        header_size = TEXTURE_HEADER_SIZE + len(name_bytes)

    file_size = len(dds_data)

    # TextureFileHeader
    header = struct.pack('<i', header_size)
    header += struct.pack('<i', file_size)
    header += struct.pack('<i', width)
    header += struct.pack('<i', height)
    header += struct.pack('<I', flags)
    header += struct.pack('<f', fade[0])
    header += struct.pack('<f', fade[1])
    header += struct.pack('<B', 1 if alpha else 0)
    header += b'TX2'  # v2 format marker

    assert len(header) == TEXTURE_HEADER_SIZE

    with open(filepath, 'wb') as f:
        f.write(header)
        f.write(name_bytes)
        f.write(dds_data)


# ─── High-level Conversion ──────────────────────────────────────────────


def image_to_texture(image_path, output_path, name=None, fmt='DXT5'):
    """Convert an image file (TGA/PNG/BMP) to CoH .texture format.

    Requires Pillow (PIL) for image loading. Falls back to raw TGA
    loading if Pillow is not available.

    Args:
        image_path: Path to source image
        output_path: Path for output .texture file
        name: Texture name (defaults to filename without extension)
        fmt: DXT format ('DXT1' for no alpha, 'DXT5' for alpha)
    """
    if name is None:
        name = os.path.splitext(os.path.basename(image_path))[0]

    # Load image pixels
    pixels, width, height, has_alpha = _load_image(image_path)

    # Auto-select format based on alpha
    if has_alpha and fmt == 'DXT1':
        fmt = 'DXT5'

    # Create DDS data
    dds_data = write_dds(pixels, width, height, fmt=fmt, mipmaps=True)

    # Write .texture file
    write_texture(
        output_path, dds_data,
        name=name,
        width=width,
        height=height,
        alpha=has_alpha,
    )


def _load_image(filepath):
    """Load an image file and return RGBA pixel data.

    Returns:
        (pixels, width, height, has_alpha)
        pixels: list of (R, G, B, A) tuples
    """
    try:
        from PIL import Image
        img = Image.open(filepath).convert('RGBA')
        width, height = img.size
        raw = img.tobytes()
        pixels = []
        for i in range(0, len(raw), 4):
            pixels.append((raw[i], raw[i+1], raw[i+2], raw[i+3]))

        # Check if image has meaningful alpha
        has_alpha = any(a < 255 for _, _, _, a in pixels)
        return pixels, width, height, has_alpha

    except ImportError:
        # Fallback: basic TGA loader for uncompressed 24/32-bit TGA
        return _load_tga(filepath)


def _load_tga(filepath):
    """Basic TGA loader for uncompressed 24/32-bit images."""
    with open(filepath, 'rb') as f:
        data = f.read()

    id_length = data[0]
    color_map_type = data[1]
    image_type = data[2]
    width = struct.unpack_from('<H', data, 12)[0]
    height = struct.unpack_from('<H', data, 14)[0]
    bpp = data[16]
    descriptor = data[17]

    if image_type != 2:
        raise ValueError(f"Unsupported TGA type: {image_type} (only uncompressed RGB supported)")

    pixel_start = 18 + id_length
    if color_map_type:
        cm_length = struct.unpack_from('<H', data, 5)[0]
        cm_entry_size = data[7]
        pixel_start += cm_length * ((cm_entry_size + 7) // 8)

    has_alpha = bpp == 32
    bytes_per_pixel = bpp // 8
    # TGA stores pixels bottom-to-top by default
    top_origin = (descriptor >> 5) & 1

    pixels = []
    for y in range(height):
        row = (height - 1 - y) if not top_origin else y
        for x in range(width):
            offset = pixel_start + (row * width + x) * bytes_per_pixel
            b = data[offset]
            g = data[offset + 1]
            r = data[offset + 2]
            a = data[offset + 3] if has_alpha else 255
            pixels.append((r, g, b, a))

    return pixels, width, height, has_alpha
