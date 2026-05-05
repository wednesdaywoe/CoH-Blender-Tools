"""Create a single-file PIGG archive that the CoH client will load.

Real pigg format (reverse-engineered from piggtools-master/Pigg Interface):

    Header (16 bytes):
        U32 marker       = 0x00000123
        U32 unknown[0]   = 0x00020002  (fixed)
        U32 unknown[1]   = 0x00300010  (fixed)
        U32 entry_count

    Directory entry (48 bytes, repeated entry_count times):
        U32 marker            = 0x00003456
        U32 string_index
        U32 uncompressed_size
        U32 timestamp_epoch    (seconds since 1970)
        U64 offset             (file position of payload)
        U32 secondary_index    (-1 for non-image)
        U8[16] md5             (MD5 of payload)
        U32 compressed_size    (0 = stored uncompressed; >0 = zlib data starting with 2-byte zlib header)

    String table:
        U32 marker = 0x00006789
        U32 count
        U32 size               (bytes of per-string data after this header)
        Per string: U32 length (includes trailing NUL), bytes (length-1), U8 0x00

    Secondary table (always present, even if no images):
        U32 marker = 0x00009ABC
        U32 entry_count
        U32 entry_size

    File payloads, at offsets recorded in directory entries.

The pigg_wrangler reader in CoH-Planner has bugs (4-byte offset instead
of 8-byte, doesn't validate per-entry marker, doesn't know about the
secondary table) — those bugs cancel for read-only inspection of valid
piggs but a writer must match the real format or the engine rejects it
with "Couldn't read all of the required data from a Pig file".

Usage:
    py make_patch_pigg.py <input-file> <internal-path> <output.pigg>
"""

import hashlib
import struct
import sys
import time
import zlib
from pathlib import Path

PIGG_MARKER = 0x00000123
HEADER_UNK0 = 0x00020002
HEADER_UNK1 = 0x00300010
DIR_ENTRY_MARKER = 0x00003456
STRING_TABLE_MARKER = 0x00006789
SECONDARY_TABLE_MARKER = 0x00009ABC

HEADER_SIZE = 16
DIR_ENTRY_SIZE = 48
STRING_TABLE_HEADER_SIZE = 12
SECONDARY_TABLE_HEADER_SIZE = 12


def build_pigg(files: list[tuple[str, bytes]]) -> bytes:
    """Build a PIGG archive from (internal_path, payload_bytes) tuples.

    Files are stored uncompressed (compressed_size = 0).
    """
    n = len(files)
    timestamp = int(time.time())

    # Build string table body (per-string entries) so we know its size
    string_body = bytearray()
    for path, _ in files:
        # length is total bytes of the string entry, INCLUDING trailing NUL
        encoded = path.encode("ascii") + b"\x00"
        string_body += struct.pack("<I", len(encoded))
        string_body += encoded
    string_table_data_size = len(string_body)

    # Layout sizes
    string_table_total = STRING_TABLE_HEADER_SIZE + string_table_data_size
    secondary_table_total = SECONDARY_TABLE_HEADER_SIZE  # no entries
    payload_start = (
        HEADER_SIZE
        + n * DIR_ENTRY_SIZE
        + string_table_total
        + secondary_table_total
    )

    # Build directory entries; concatenate payloads
    dir_entries = bytearray()
    payload_block = bytearray()
    cursor = payload_start
    for idx, (path, data) in enumerate(files):
        size = len(data)
        md5 = hashlib.md5(data).digest()  # 16 bytes
        entry = bytearray(DIR_ENTRY_SIZE)
        struct.pack_into("<I", entry, 0, DIR_ENTRY_MARKER)
        struct.pack_into("<I", entry, 4, idx)             # string_index
        struct.pack_into("<I", entry, 8, size)            # uncompressed_size
        struct.pack_into("<I", entry, 12, timestamp)      # timestamp
        struct.pack_into("<Q", entry, 16, cursor)         # offset (8 bytes)
        struct.pack_into("<i", entry, 24, -1)             # secondary_index = -1
        entry[28:44] = md5                                # md5
        struct.pack_into("<I", entry, 44, 0)              # compressed_size = 0
        dir_entries += entry
        payload_block += data
        cursor += size

    # Header
    header = bytearray()
    header += struct.pack("<I", PIGG_MARKER)
    header += struct.pack("<I", HEADER_UNK0)
    header += struct.pack("<I", HEADER_UNK1)
    header += struct.pack("<I", n)

    # String table header
    string_header = bytearray()
    string_header += struct.pack("<I", STRING_TABLE_MARKER)
    string_header += struct.pack("<I", n)                            # count
    string_header += struct.pack("<I", string_table_data_size)       # size

    # Secondary table header (no entries — non-image pigg)
    secondary_header = bytearray()
    secondary_header += struct.pack("<I", SECONDARY_TABLE_MARKER)
    secondary_header += struct.pack("<I", 0)   # entry count
    secondary_header += struct.pack("<I", 0)   # entry size

    return bytes(
        header
        + dir_entries
        + string_header
        + string_body
        + secondary_header
        + payload_block
    )


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    input_path = Path(sys.argv[1])
    internal_path = sys.argv[2]
    output_pigg = Path(sys.argv[3])

    data = input_path.read_bytes()
    pigg = build_pigg([(internal_path, data)])

    output_pigg.parent.mkdir(parents=True, exist_ok=True)
    output_pigg.write_bytes(pigg)

    print(f"Wrote {output_pigg}")
    print(f"  size:           {len(pigg)} bytes")
    print(f"  contains:       {internal_path}")
    print(f"  payload size:   {len(data)} bytes (uncompressed)")
    print(f"  payload md5:    {hashlib.md5(data).hexdigest()}")


if __name__ == "__main__":
    main()
