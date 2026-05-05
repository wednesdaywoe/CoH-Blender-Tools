"""
DDS (DirectDraw Surface) file format reader and writer.

Handles DXT1 (no alpha) and DXT5 (with alpha) compressed textures
as used by City of Heroes .texture files.

DDS file layout:
    "DDS " magic (4 bytes)
    DDSURFACEDESC2 (124 bytes)
    Pixel data (compressed blocks or raw pixels)

DXT1: 8 bytes per 4x4 block (RGB, optional 1-bit alpha)
DXT5: 16 bytes per 4x4 block (RGBA, interpolated 8-bit alpha)

Reference: Game/src/render/dd.h, Utilities/GetTex/src/gettex.c
"""

import struct
import math

# DDS magic number
DDS_MAGIC = b'DDS '

# DDSD flags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000

# DDPF flags
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_ALPHAPIXELS = 0x1

# DDSCAPS flags
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000
DDSCAPS_COMPLEX = 0x8

# FourCC codes
FOURCC_DXT1 = 0x31545844  # 'DXT1'
FOURCC_DXT3 = 0x33545844  # 'DXT3'
FOURCC_DXT5 = 0x35545844  # 'DXT5'

# DDS header size (DDSURFACEDESC2)
DDS_HEADER_SIZE = 124
DDS_PIXELFORMAT_SIZE = 32


def _fourcc_bytes(code):
    """Convert FourCC int to bytes."""
    return struct.pack('<I', code)


def _fourcc_int(b):
    """Convert FourCC bytes to int."""
    return struct.unpack('<I', b)[0]


# ─── DDS Reading ─────────────────────────────────────────────────────────


def read_dds(data):
    """Parse DDS file data.

    Args:
        data: Raw bytes of a DDS file

    Returns:
        dict with keys: width, height, format, mipmap_count, fourcc, pixel_data
    """
    if len(data) < 128:
        raise ValueError("Data too small for DDS file")

    magic = data[:4]
    if magic != DDS_MAGIC:
        raise ValueError(f"Invalid DDS magic: {magic}")

    # Parse DDSURFACEDESC2 (124 bytes starting at offset 4)
    hdr_offset = 4
    dwSize = struct.unpack_from('<I', data, hdr_offset)[0]
    dwFlags = struct.unpack_from('<I', data, hdr_offset + 4)[0]
    dwHeight = struct.unpack_from('<I', data, hdr_offset + 8)[0]
    dwWidth = struct.unpack_from('<I', data, hdr_offset + 12)[0]
    dwLinearSize = struct.unpack_from('<I', data, hdr_offset + 16)[0]
    dwMipMapCount = struct.unpack_from('<I', data, hdr_offset + 24)[0]

    # Parse pixel format (at offset 72 within header = hdr_offset + 72)
    pf_offset = hdr_offset + 72
    pf_dwFlags = struct.unpack_from('<I', data, pf_offset + 4)[0]
    pf_dwFourCC = struct.unpack_from('<I', data, pf_offset + 8)[0]
    pf_dwRGBBitCount = struct.unpack_from('<I', data, pf_offset + 12)[0]

    # Determine format
    if pf_dwFlags & DDPF_FOURCC:
        fourcc = pf_dwFourCC
        if fourcc == FOURCC_DXT1:
            fmt = 'DXT1'
        elif fourcc == FOURCC_DXT3:
            fmt = 'DXT3'
        elif fourcc == FOURCC_DXT5:
            fmt = 'DXT5'
        else:
            fmt = f'FOURCC_0x{fourcc:08X}'
    else:
        fourcc = 0
        fmt = f'RGB{pf_dwRGBBitCount}'

    if dwMipMapCount == 0:
        dwMipMapCount = 1

    # Pixel data starts after magic + header
    pixel_data = data[4 + DDS_HEADER_SIZE:]

    return {
        'width': dwWidth,
        'height': dwHeight,
        'format': fmt,
        'fourcc': fourcc,
        'mipmap_count': dwMipMapCount,
        'linear_size': dwLinearSize,
        'pixel_data': pixel_data,
    }


def dds_mip_size(width, height, fmt):
    """Calculate the byte size of one mipmap level."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    if fmt in ('DXT1',):
        return bw * bh * 8
    elif fmt in ('DXT3', 'DXT5'):
        return bw * bh * 16
    else:
        return width * height * 4  # RGBA8888 fallback


# ─── DXT Block Compression ──────────────────────────────────────────────


def _color_to_565(r, g, b):
    """Convert 8-bit RGB to RGB565."""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _color_from_565(c):
    """Convert RGB565 to 8-bit (R, G, B)."""
    r = ((c >> 11) & 0x1F) << 3
    g = ((c >> 5) & 0x3F) << 2
    b = (c & 0x1F) << 3
    # Fill lower bits for better accuracy
    r |= r >> 5
    g |= g >> 6
    b |= b >> 5
    return r, g, b


def _compress_dxt1_block(pixels):
    """Compress a 4x4 block of RGBA pixels to DXT1 (8 bytes).

    Args:
        pixels: list of 16 (R, G, B, A) tuples (row-major, 0-255)

    Returns:
        8 bytes of DXT1 compressed data
    """
    # Find min/max colors (simple bounding box approach)
    min_r = min_g = min_b = 255
    max_r = max_g = max_b = 0
    for r, g, b, a in pixels:
        min_r = min(min_r, r)
        min_g = min(min_g, g)
        min_b = min(min_b, b)
        max_r = max(max_r, r)
        max_g = max(max_g, g)
        max_b = max(max_b, b)

    c0 = _color_to_565(max_r, max_g, max_b)
    c1 = _color_to_565(min_r, min_g, min_b)

    # Ensure c0 > c1 for 4-color mode (no alpha)
    if c0 < c1:
        c0, c1 = c1, c0
    elif c0 == c1:
        # All same color — indices all 0
        return struct.pack('<HH', c0, c1) + b'\x00\x00\x00\x00'

    # Generate palette
    r0, g0, b0 = _color_from_565(c0)
    r1, g1, b1 = _color_from_565(c1)
    palette = [
        (r0, g0, b0),
        (r1, g1, b1),
        ((2 * r0 + r1 + 1) // 3, (2 * g0 + g1 + 1) // 3, (2 * b0 + b1 + 1) // 3),
        ((r0 + 2 * r1 + 1) // 3, (g0 + 2 * g1 + 1) // 3, (b0 + 2 * b1 + 1) // 3),
    ]

    # Find best index for each pixel
    indices = 0
    for i, (r, g, b, a) in enumerate(pixels):
        best_idx = 0
        best_dist = float('inf')
        for j, (pr, pg, pb) in enumerate(palette):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_dist:
                best_dist = d
                best_idx = j
        indices |= (best_idx << (i * 2))

    return struct.pack('<HHI', c0, c1, indices)


def _compress_dxt5_block(pixels):
    """Compress a 4x4 block of RGBA pixels to DXT5 (16 bytes).

    Args:
        pixels: list of 16 (R, G, B, A) tuples (row-major, 0-255)

    Returns:
        16 bytes of DXT5 compressed data
    """
    # Alpha block (8 bytes)
    alphas = [a for _, _, _, a in pixels]
    a0 = max(alphas)
    a1 = min(alphas)

    if a0 == a1:
        # All same alpha
        alpha_block = struct.pack('<BB', a0, a1) + b'\x00\x00\x00\x00\x00\x00'
    else:
        # Ensure a0 > a1 for 8-value interpolation mode
        if a0 <= a1:
            a0, a1 = max(a0, a1 + 1), min(a0, a1)

        # Generate alpha palette (8 values)
        a_palette = [a0, a1]
        for i in range(1, 7):
            a_palette.append(((7 - i) * a0 + i * a1 + 3) // 7)

        # Find best alpha index for each pixel
        a_indices = 0
        for i, a in enumerate(alphas):
            best_idx = 0
            best_dist = abs(a - a_palette[0])
            for j in range(1, 8):
                d = abs(a - a_palette[j])
                if d < best_dist:
                    best_dist = d
                    best_idx = j
            a_indices |= (best_idx << (i * 3))

        alpha_block = struct.pack('<BB', a0, a1)
        # Pack 48 bits (6 bytes) of alpha indices
        for byte_idx in range(6):
            alpha_block += struct.pack('<B', (a_indices >> (byte_idx * 8)) & 0xFF)

    # Color block (8 bytes) — same as DXT1
    color_block = _compress_dxt1_block(pixels)

    return alpha_block + color_block


def _decompress_dxt1_block(block_data):
    """Decompress a DXT1 block (8 bytes) to 16 RGBA pixels."""
    c0, c1, indices = struct.unpack_from('<HHI', block_data, 0)
    r0, g0, b0 = _color_from_565(c0)
    r1, g1, b1 = _color_from_565(c1)

    if c0 > c1:
        palette = [
            (r0, g0, b0, 255),
            (r1, g1, b1, 255),
            ((2*r0+r1+1)//3, (2*g0+g1+1)//3, (2*b0+b1+1)//3, 255),
            ((r0+2*r1+1)//3, (g0+2*g1+1)//3, (b0+2*b1+1)//3, 255),
        ]
    else:
        palette = [
            (r0, g0, b0, 255),
            (r1, g1, b1, 255),
            ((r0+r1+1)//2, (g0+g1+1)//2, (b0+b1+1)//2, 255),
            (0, 0, 0, 0),  # Transparent
        ]

    pixels = []
    for i in range(16):
        idx = (indices >> (i * 2)) & 3
        pixels.append(palette[idx])
    return pixels


def _decompress_dxt5_block(block_data):
    """Decompress a DXT5 block (16 bytes) to 16 RGBA pixels."""
    # Alpha block (first 8 bytes)
    a0 = block_data[0]
    a1 = block_data[1]

    # Extract 48 bits of alpha indices
    a_bits = 0
    for i in range(6):
        a_bits |= block_data[2 + i] << (i * 8)

    if a0 > a1:
        a_palette = [a0, a1]
        for i in range(1, 7):
            a_palette.append(((7 - i) * a0 + i * a1 + 3) // 7)
    else:
        a_palette = [a0, a1]
        for i in range(1, 5):
            a_palette.append(((5 - i) * a0 + i * a1 + 2) // 5)
        a_palette.extend([0, 255])

    alphas = []
    for i in range(16):
        idx = (a_bits >> (i * 3)) & 7
        alphas.append(a_palette[idx])

    # Color block (last 8 bytes)
    color_pixels = _decompress_dxt1_block(block_data[8:16])

    # Combine alpha with colors
    pixels = []
    for i in range(16):
        r, g, b, _ = color_pixels[i]
        pixels.append((r, g, b, alphas[i]))
    return pixels


# ─── Image Compression/Decompression ────────────────────────────────────


def compress_image(pixels, width, height, fmt='DXT5'):
    """Compress RGBA pixel data to DXT format.

    Args:
        pixels: bytes or list of RGBA values (width * height * 4 bytes)
        width: Image width
        height: Image height
        fmt: 'DXT1' or 'DXT5'

    Returns:
        Compressed block data as bytes
    """
    if isinstance(pixels, (bytes, bytearray)):
        # Convert flat bytes to list of (R, G, B, A) tuples
        pixel_list = []
        for i in range(0, len(pixels), 4):
            pixel_list.append((pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]))
        pixels = pixel_list

    compress_fn = _compress_dxt5_block if fmt == 'DXT5' else _compress_dxt1_block
    result = bytearray()

    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = []
            for py in range(4):
                for px in range(4):
                    x = min(bx + px, width - 1)
                    y = min(by + py, height - 1)
                    block.append(pixels[y * width + x])
            result.extend(compress_fn(block))

    return bytes(result)


def decompress_image(data, width, height, fmt='DXT5'):
    """Decompress DXT block data to RGBA pixels.

    Args:
        data: Compressed block data
        width: Image width
        height: Image height
        fmt: 'DXT1' or 'DXT5'

    Returns:
        List of (R, G, B, A) tuples, row-major
    """
    decompress_fn = _decompress_dxt5_block if fmt == 'DXT5' else _decompress_dxt1_block
    block_size = 16 if fmt == 'DXT5' else 8

    pixels = [(0, 0, 0, 255)] * (width * height)
    block_offset = 0

    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            if block_offset + block_size > len(data):
                break
            block_pixels = decompress_fn(data[block_offset:block_offset + block_size])
            block_offset += block_size

            for py in range(4):
                for px in range(4):
                    x = bx + px
                    y = by + py
                    if x < width and y < height:
                        pixels[y * width + x] = block_pixels[py * 4 + px]

    return pixels


# ─── Mipmap Generation ──────────────────────────────────────────────────


def generate_mipmaps(pixels, width, height):
    """Generate mipmap chain using box filter.

    Args:
        pixels: list of (R, G, B, A) tuples for the base level

    Yields:
        (width, height, pixels) for each mip level (including base)
    """
    yield (width, height, pixels)

    while width > 1 or height > 1:
        new_w = max(1, width // 2)
        new_h = max(1, height // 2)
        new_pixels = []

        for y in range(new_h):
            for x in range(new_w):
                # Average 2x2 block
                x0, y0 = x * 2, y * 2
                x1 = min(x0 + 1, width - 1)
                y1 = min(y0 + 1, height - 1)

                p00 = pixels[y0 * width + x0]
                p10 = pixels[y0 * width + x1]
                p01 = pixels[y1 * width + x0]
                p11 = pixels[y1 * width + x1]

                r = (p00[0] + p10[0] + p01[0] + p11[0] + 2) // 4
                g = (p00[1] + p10[1] + p01[1] + p11[1] + 2) // 4
                b = (p00[2] + p10[2] + p01[2] + p11[2] + 2) // 4
                a = (p00[3] + p10[3] + p01[3] + p11[3] + 2) // 4
                new_pixels.append((r, g, b, a))

        width, height = new_w, new_h
        pixels = new_pixels
        yield (width, height, pixels)


# ─── DDS File Writing ────────────────────────────────────────────────────


def write_dds(pixels, width, height, fmt='DXT5', mipmaps=True):
    """Create a DDS file from RGBA pixels.

    Args:
        pixels: list of (R, G, B, A) tuples or flat RGBA bytes
        width: Image width
        height: Image height
        fmt: 'DXT1' or 'DXT5'
        mipmaps: Whether to generate mipmaps

    Returns:
        Complete DDS file as bytes
    """
    if isinstance(pixels, (bytes, bytearray)):
        pixel_list = []
        for i in range(0, len(pixels), 4):
            pixel_list.append((pixels[i], pixels[i+1], pixels[i+2], pixels[i+3]))
        pixels = pixel_list

    # Generate mip chain
    mip_levels = list(generate_mipmaps(pixels, width, height)) if mipmaps else [(width, height, pixels)]
    mip_count = len(mip_levels)

    # Compress all mip levels
    compressed_data = bytearray()
    for mw, mh, mpixels in mip_levels:
        compressed_data.extend(compress_image(mpixels, mw, mh, fmt))

    # Calculate linear size of base level
    linear_size = dds_mip_size(width, height, fmt)

    # Build DDS header
    fourcc = FOURCC_DXT1 if fmt == 'DXT1' else FOURCC_DXT5

    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT

    caps = DDSCAPS_TEXTURE
    if mip_count > 1:
        caps |= DDSCAPS_MIPMAP | DDSCAPS_COMPLEX

    # DDSURFACEDESC2 (124 bytes)
    header = struct.pack('<I', DDS_HEADER_SIZE)  # dwSize
    header += struct.pack('<I', flags)            # dwFlags
    header += struct.pack('<I', height)           # dwHeight
    header += struct.pack('<I', width)            # dwWidth
    header += struct.pack('<I', linear_size)      # dwLinearSize
    header += struct.pack('<I', 0)                # dwDepth
    header += struct.pack('<I', mip_count)        # dwMipMapCount
    header += b'\x00' * 44                        # dwReserved[11]

    # DDPIXELFORMAT (32 bytes)
    header += struct.pack('<I', DDS_PIXELFORMAT_SIZE)  # dwSize
    header += struct.pack('<I', DDPF_FOURCC)           # dwFlags
    header += struct.pack('<I', fourcc)                 # dwFourCC
    header += struct.pack('<I', 0)                      # dwRGBBitCount
    header += struct.pack('<I', 0)                      # dwRBitMask
    header += struct.pack('<I', 0)                      # dwGBitMask
    header += struct.pack('<I', 0)                      # dwBBitMask
    header += struct.pack('<I', 0)                      # dwRGBAlphaBitMask

    # DDSCAPS2 (16 bytes)
    header += struct.pack('<I', caps)             # dwCaps
    header += struct.pack('<I', 0)                # dwCaps2
    header += struct.pack('<I', 0)                # dwCaps3
    header += struct.pack('<I', 0)                # dwCaps4

    header += struct.pack('<I', 0)                # dwTextureStage

    assert len(header) == DDS_HEADER_SIZE

    # Assemble file
    result = bytearray()
    result.extend(DDS_MAGIC)
    result.extend(header)
    result.extend(compressed_data)

    return bytes(result)
