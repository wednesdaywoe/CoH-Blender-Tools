#! /usr/bin/python3

import struct
import zlib
import sys
import traceback
import math
try:
    from .bones import *
    from .polygrid import PolyCell, PolyGrid
    from .util import Data
    from .geomesh import GeoMesh, GeoFace, GeoVertex
except:
    from bones import *
    from polygrid import PolyCell, PolyGrid
    from util import Data
    from geomesh import GeoMesh, GeoFace, GeoVertex

#Ver 0 .geo pre-header:
#Offset	Size	Description
#0	4	'ziplen' ? Compressed header data size + 4
#4	4	Header size (Must be non-zero for old formats.)
#8	variable	zlib Compressed header data
#variable	4	Dummy data?

#Version 2+ .geo pre-header:
#Offset	Size	Description
#0	4	'ziplen' ? Compressed header data size + 12
#4	4	Legacy header size (Must be 0 for new file formats.)
#8	4	Version number 2 to 5, and 7 to 8
#12	4	Header size
#16	variable	zlib Compressed header data



#.geo header
#Offset	Size	Description
#0	4	i32: gld->datasize
#4	4	i32: texname_blocksize
#8	4	i32: objname_blocksize
#12	4	i32: texidx_blocksize
#16	4	i32: lodinfo_blocksize (only present in version 2 to 6)
#?	texname_blocksize	PackNames block of texture names
#?	objname_blocksize	objnames
#?	texidx_blocksize	TexID[]: texidx_block,
#?	lodinfo_blocksize	lodinfo (only present in version 2 to 6)
#?	ModelHeader	???


#PackNames block:
#Size	Description
#4	name_count
#4*name_count	offset of the name, relative to the start of name_block
#variable	name_block (ASCIIZ?)

#ModelHeader:
#Size	Description
#124	ASCIIZ name.
#4	Model pointer (0 in file?)
#4	Float track length (technically a fallback if not specified elsewhere?)
#4	Pointer to an array of Model pointers (-1 in file?)
#*note: pointers aren't really needed.

#Model:
#version 0 to 2: (struct ModelFormatOnDisk_v2: "Common/seq/anim.c" )
#Offset	Size	Description
#0	4	u32: Flags
#4	4	f32: radius
#8	4	ptr: VBO?
#12	4	i32: tex_count
#16	2	i16: id  ("I am this bone" ?)
#18	1	u8: blend_mode
#19	1	u8: loadstate
#20	4	ptr(BoneInfo)
#24	4	ptr(TrickNode)
#28	4	i32: vert_count
#32	4	i32: tri_count
#36	4	ptr: TexID
#40	32	PolyGrid: polygrid
#72	4	ptr(CTri): ctris ?
#76	4	ptr(i32): tags
#80	4	ptr(char): name
#84	4	ptr(AltPivotInfo): api
#88	4	ptr(ModelExtra): extra
#92	12	Vec3: scale
#104	12	Vec3: min
#116	12	Vec3: max
#120	4	ptr(GeoLoadData): gld
#124	84	PackBlockOnDisk
#208

#version 3+: "Common/seq/anim.c"
#	Offset	Size	Description
#	0	4	i32: size
#	4	4	f32: radius
#	8	4	i32: tex_count, The number of TexID entries in the texidx_block.
#	12	4	ptr(BoneInfo): boneinfo ?
#	16	4	i32: vert_count
#	20	4	i32: tri_count
#ver 8+	24	4	i32: reflection_quad_count
#	+4	4	ptr(TexID): tex_idx, Byte offset in the texidx_block to the first TexID for this model.
#	+4	32	PolyGrid: grid
#	+32	4	ptr(char): name
#	+4	4	ptr(AltPivotInfo):
#	+4	12	Vec3: scale
#	+12	12	Vec3: min
#	+12	12	Vec3: max
#	+12	12	PackData: pack.tris
#	+12	12	PackData: pack.verts
#	+12	12	PackData: pack.norms
#	+12	12	PackData: pack.sts
#	+12	12	PackData: pack.sts3
#	+12	12	PackData: pack.weights
#	+12	12	PackData: pack.matidxs
#	+12	12	PackData: pack.grid
#Ver 4	+12	12	PackData: pack.lmap_utransforms
#Ver 4	+12	12	PackData: pack.lmap_vtransforms
#Ver 7+	+12	12	PackData: pack.reductions
#Ver 8+	+12	12	PackData: pack.reflection_quads
#Ver 7+	+12	12	f32[3]: autolod_dists
#	+12	2	i16: id

#PackBlockOnDisk: "Common/seq/anim.c"
#Offset	Size	Description
#0	12	PackData: tris
#12	12	PackData: verts
#24	12	PackData: norms
#36	12	PackData: sts
#48	12	PackData: weights
#60	12	PackData: matidxs
#72	12	PackData: grid
#84

#PackData:
#Offset	Size	Description
#0	4	i32: packsize, The compressed size of this data block. 0 if this is uncompressed.
#4	4	u32: unpacksize, The size of this data block when uncompressed.
#8	4	ptr(u8): data, The offset of this block of data inside the .geo's main data block. 
#12

#TexID:
#Offset	Size	Description
#0	2	u16: id, Index to the texture name in the texture name list.
#2	2	u16: count, Number of tris using this texture.

#struct PolyGrid: "libs/UtilitiesLib/components/gridpoly.h"
#Offset	Size	Description
#0	4	ptr(PolyCell): cell
#4	12	Vec3: pos
#16	4	f32: size
#20	4	f32: inv_size
#24	4	i32: tag
#28	4	i32: num_bits
#32


#PolyCell:
#Offset	Size	Description
#0	4	ptr(ptr(PolyCell)): children
#4	4	ptr(u16): tri_idxs, Triangle indexes.
#8	4	i32: tri_count

#BoneInfo
#Offset Size	Description
#0	4	i32: numbones
#4	4*15	i32[15]: bone_ID, Bones used by this geometry.
#64

#Reductions
#Size	Description
#4	int: num_reductions
#num_reductions*4	int[]:num_tris_left
#num_reductions*4	int[]:error_values
#num_reductions*4	int[]:remap_counts
#num_reductions*4	int[]:changes_counts
#4	int: total_remaps
#total_remaps*4 	int[]:remaps
#4	int: total_remap_tris
#total_remap_tris*4	int[]:remap_tris
#4	int: total_changes
#total_changes*4	int[]:changes
#4	int: positions_delta_length
#positions_delta_length	byte[]: compressDelta(positions, 3, total_changes, "f", 0x8000)
#4	int: total_changes_delta_length
#total_changes_delta_length	byte[]: compressDelta(changes, 2, total_changes, "f", 0x1000)

ZERO_BYTE = struct.pack("B", 0)
#def unbyte(v):
#    return struct.unpack("B", v)[0]
if sys.version_info[0] < 3:
    byte = chr
    unbyte = ord
else:
    def byte(v):
        #return struct.pack("B", v)
        return bytes((v,))
    def unbyte(v):
        return v

def unpackNames(data):
    """Extract strings from data, as layed out as a PackNames structure."""
    (length, ) = struct.unpack("<i", data[0:4])
    strings = []
    data_strings = data[length * 4 + 4:]
    for i in range(length):
        #todo: scan string for zero
        (offset, ) = struct.unpack("<i", data[i * 4 + 4: i * 4 + 4 + 4])
        for j in range(offset, len(data_strings)):
            if unbyte(data_strings[j]) == 0:
                strings.append(data_strings[offset:j])
                break
            pass
        pass
    return strings
def packNames(strings):
    """Convert a sequence of strings into a PackNames structure."""
    data_strings = b""
    data = struct.pack("<i", len(strings))
    for s in strings:
        data += struct.pack("<i", len(data_strings))
        data_strings += s + ZERO_BYTE
    return data + data_strings

def unpackStrings(data):
    """Convert a block of ASCIIZ strings into list of strings."""
    strings = []
    start = 0
    for i in range(len(data)):
        if unbyte(data[i]) == 0:
            strings.append(data[start:i])
            start = i + 1
            pass
        pass
    return strings
def packStrings(strings):
    """Convert a list of strings into a block of ASCIIZ strings"""
    data = b""
    for s in strings:
        data += s + ZERO_BYTE
    return data

def extractString(data, offset = 0):
    """Extract an ASCIIZ string from a fixed length buffer."""
    for i in range(offset, len(data)):
        if unbyte(data[i]) == 0:
            return data[offset : i]
        pass
    return data
def storeString(string, length):
    """Store an ASCIIZ string into a fixed length buffer. If the string is longer than the buffer the output will be truncated, with \\x00 character guarenteed at the end."""
    if len(string) >= length:
        return string[0 : length - 1] + ZERO_BYTE
    else:
        return string + ZERO_BYTE * (length - len(string))

def uncompressDeltas(src, stride, count, pack_type):
    """Expand a list a delta compressed with deltas

src: Source data containg 3 parts:
  - delta codes: Contain 'count' * 'stride' 2 bit size code fields. The end of the block is padded to the byte boundary.
  - float scale: A byte with the exponent for scaling floating point deltas. This part is present with integer types, but unused.
  - byte data: This is read and processed according to the codes specified in the delta codes block.
stride: the number of channels in the data (1 to 3)
count: the number off elements in the data
pack_type: Is a character indicating the type of packing. Valid values are "f" (float32), "H" (unsigned16), "I" (unsigned32) (these match the struct modules types).
The returned data is an array of arrays, with the inner most arrays being 'stride' long, and the outer array being 'count' in length.
"""
    if len(src) <= 0:
        return None
    #Compute offset to the byte data after all the bit fields.
    byte_offset = int((2 * count * stride + 7) / 8)
    #print("stride: %d  count: %d  pack_type: %s" % (stride, count, pack_type))
    #print("src:%s" % ([src],))
    float_scale = float(1 << unbyte(src[byte_offset]))
    float_scale_inv = 1.0 / float_scale
    byte_offset += 1
    current_bit = 0
    if pack_type in "f":
        fLast = [0.0] * stride
    else:
        iLast = [0] * stride
    out_data = []
    for i in range(count):
        row_data = []
        for j in range(stride):
            code = (unbyte(src[current_bit >> 3]) >> (current_bit & 0x7)) & 0x3
            current_bit += 2
            if code == 0:
                iDelta = 0
            elif code == 1:
                iDelta = unbyte(src[byte_offset]) - 0x7f
                byte_offset += 1
            elif code == 2:
                iDelta = (
                    unbyte(src[byte_offset]) |
                    (unbyte(src[byte_offset + 1]) << 8)
                ) - 0x7fff
                byte_offset += 2
            elif code == 3:
                (iDelta, ) = struct.unpack("<i", src[byte_offset : byte_offset + 4])
                byte_offset += 4
            if pack_type == "f":
                if code == 3:
                    (fDelta, ) = struct.unpack("<f", src[byte_offset - 4 : byte_offset])
                else:
                    fDelta = iDelta * float_scale_inv
                fLast[j] += fDelta
                row_data.append(fLast[j])
            elif pack_type == "I":
                iLast[j] += iDelta + 1
                iLast[j] &= 0xffffffff
                row_data.append(iLast[j])
            elif pack_type == "H":
                iLast[j] += iDelta + 1
                iLast[j] &= 0xffff
                row_data.append(iLast[j])
        out_data.append(row_data)
    return out_data

def quantF32(v, float_scale, float_scale_inv):
    i = int(v * float_scale)
    i &= ~1
    return i * float_scale_inv
def compressDeltas(src, stride, count, pack_type, float_scale):
    if float_scale != 0:
        float_scale_inv = 1.0 / float_scale
    else:
        float_scale_inv = 1.0
    codes = [0] * (stride * count + 3) #over fill it by 3 for easier conversion into byte data
    float_scale_byte = byte(int(math.log(float_scale, 2)))
    bytes_data = b""
    if pack_type in "f":
        fLast = [0.0] * stride
    else:
        iLast = [0] * stride
        if pack_type == "I":
            iMask = 0xffffffff
        else:
            iMask = 0xffff

    k = 0
    for i in range(count):
        for j in range(stride):
            if pack_type == "f":
                fDelta = quantF32(src[i][j], float_scale, float_scale_inv) - fLast[j]
                val8 = int(fDelta * float_scale + 0x7f)
                val16 = int(fDelta * float_scale + 0x7fff)
            else:
                t = src[i][j]
                iDelta = t - iLast[j] - 1
                iLast[j] = t
                val8 = iDelta + 0x7f
                val16 = iDelta + 0x7fff
                val32 = iDelta;
            if val8 == 0x7f:
                codes[k] = 0
            elif val8 & ~0xff == 0:
                codes[k] = 1
                bytes_data += byte(val8)
                if pack_type == "f":
                    fLast[j] = (val8 - 0x7f) * float_scale_inv + fLast[j];
            elif pack_type == "H" or val16 & ~0xffff == 0:
                codes[k] = 2
                bytes_data += struct.pack("<H", val16)
                if pack_type == "f":
                    fLast[j] = (val16 - 0x7fff) * float_scale_inv + fLast[j];
            elif pack_type == "I":
                codes[k] = 3
                bytes_data += struct.pack("<I", val32 & iMask)
            else:
                codes[k] = 3
                bytes_data += struct.pack("<f", fDelta)
                fLast[j] = fDelta + fLast[j]
            k += 1
                
        
    code_data = b""
    for i in range(0, stride * count, 4):
        v = ((codes[i + 0] << 0) |
             (codes[i + 1] << 2) |
             (codes[i + 2] << 4) |
             (codes[i + 3] << 6))
        code_data += byte(v)
    return code_data + float_scale_byte + bytes_data

def inferSizes(size, pack_list, other_list):
    """Infer the size of the blocks in 'other_list' as infered by the total size and items in 'pack_list'."""
    starts = []
    for p in pack_list:
        s = p[2]
        if s in starts:
            continue
        starts.append(s)
    for o in other_list:
        if o in starts:
            continue
        starts.append(o)
    starts.sort()
    output = []
    for o in other_list:
        if o == 0:
            output.append( (0, 0, 0) )
            continue
        i = starts.index(o) + 1
        if i < 0 or i >= len(starts):
            output.append( (0, 0, o) )
            continue
        output.append( (0, starts[i] - o, o) )
        
    return tuple(output)


class Reductions:
    def __init__(self, model):
        self.model = model
    def decode(self, data):
        (self.num_reductions, ) = data.decode("<i")
        self.num_tris_left = data.decode("<" + "i" * self.num_reductions)
        self.error_values = data.decode("<" + "f" * self.num_reductions)
        self.remap_counts = data.decode("<" + "i" * self.num_reductions)
        self.changes_counts = data.decode("<" + "i" * self.num_reductions)
        (self.total_remaps, ) = data.decode("<i")
        self.remaps = data.decode("<" + "i" * (self.total_remaps * 3))
        (self.total_remap_tris, ) = data.decode("<i")
        self.remap_tris = data.decode("<" + "i" * self.total_remap_tris)
        (self.total_changes, ) = data.decode("<i")
        self.changes = data.decode("<" + "i" * self.total_changes)
        (positions_delta_length, ) = data.decode("<i")
        #print("positions_delta_length: %s" % (positions_delta_length, ))
        #print("data remaining: %s" %([data.data[data.offset : ]], ))
        #self.dump()
        self.positions = uncompressDeltas(data.read(positions_delta_length), 3, self.total_changes, "f")
        (tex1s_delta_length, ) = data.decode("<i")
        self.tex1s = uncompressDeltas(data.read(tex1s_delta_length), 2, self.total_changes, "f")
        #print("data remaining: %s" %([data.data[data.offset : ]], ))
    def encode(self):
        data = b""
        data += struct.pack("<i", self.num_reductions)
        data += struct.pack("<" + "i" * self.num_reductions, *self.num_tris_left)
        data += struct.pack("<" + "f" * self.num_reductions, *self.error_values)
        data += struct.pack("<" + "i" * self.num_reductions, *self.remap_counts)
        data += struct.pack("<" + "i" * self.num_reductions, *self.changes_counts)
        data += struct.pack("<i", self.total_remaps)
        data += struct.pack("<" + "i" * (self.total_remaps * 3), *self.remaps)
        data += struct.pack("<i", self.total_remap_tris)
        data += struct.pack("<" + "i" * self.total_remap_tris, *self.remap_tris)
        data += struct.pack("<i", self.total_changes)
        data += struct.pack("<" + "i" * self.total_changes, *self.changes)
        d = compressDeltas(self.positions, 3, self.total_changes, "f", 0x8000)
        data += struct.pack("<i", len(d))
        data += d
        d = compressDeltas(self.tex1s, 2, self.total_changes, "f", 0x1000)
        data += struct.pack("<i", len(d))
        data += d
        return data
    def dump(self):
        print("    reductions:")
        print("        num_reductions: %s" % (self.num_reductions, ))
        print("        num_tris_left: %s" % (self.num_tris_left, ))
        print("        error_values: %s" % (self.error_values, ))
        print("        remap_counts: %s" % (self.remap_counts, ))
        print("        changes_counts: %s" % (self.changes_counts, ))
        print("        total_remaps: %s" % (self.total_remaps, ))
        print("        remaps: %s" % (self.remaps, ))
        print("        total_remap_tris: %s" % (self.total_remap_tris, ))
        print("        remap_tris: %s" % (self.remap_tris, ))
        print("        total_changes: %s" % (self.total_changes, ))
        print("        changes: %s" % (self.changes, ))
        print("        positions: %s" % (self.positions, ))
        print("        tex1s: %s" % (self.tex1s, ))

class Model:
    def __init__(self, geo):
        self.geo = geo
        self.radius = None
        self.tex_count = None
        self.vert_count = None
        self.tri_count = None
        self.reflection_quad_count = None
        self.tex_idx = None
        self.name = b""
        self.textures = []
        pass
    def parseHeaderDataV2(self):
        (self.flags, ) = self.geo.getHeaderElement("<I")
        (self.radius, ) = self.geo.getHeaderElement("<f")
        self.geo.header_offset += 4 #ptr(VBO)
        #print("VBO: %s" % (self.geo.getHeaderElement("<i"), ))
        (self.tex_count, ) = self.geo.getHeaderElement("<i")
        (self.id, blend_mode, loadstate) = self.geo.getHeaderElement("<hBB")
        #print("blend_mode, loadstate: %d, %d" % (blend_mode, loadstate))
        (self.boneinfo_ptr, ) = self.geo.getHeaderElement("<i")
        self.geo.header_offset += 4 #ptr(TrickNode)
        #print("TrickNode: %s" % (self.geo.getHeaderElement("<i"), ))
        (self.vert_count, self.tri_count) = self.geo.getHeaderElement("<ii")
        (self.tex_idx_ptr, ) = self.geo.getHeaderElement("<i")
        self.grid_header = self.geo.getHeaderElement("<ifffffii")
        self.geo.header_offset += 4 #ptr(CTri)
        self.geo.header_offset += 4 #ptr(tags)
        #print("CTri: %s" % (self.geo.getHeaderElement("<i"), ))
        #print("Tags: %s" % (self.geo.getHeaderElement("<i"), ))
        (self.name_ptr, self.api_ptr) = self.geo.getHeaderElement("<ii")
        #print("???: %s" % (self.geo.getHeaderElement("<f"), ))
        self.geo.header_offset += 4 #ptr(ModelExtra)
        self.scale = list(self.geo.getHeaderElement("<fff"))
        self.min = list(self.geo.getHeaderElement("<fff"))
        self.max = list(self.geo.getHeaderElement("<fff"))
        self.geo.header_offset += 4 #ptr(GeoLoadData)
        #print("GeoLoadData: %s" % (self.geo.getHeaderElement("<i"), ))
        self.pack_tris = self.geo.getHeaderElement("<iii")
        self.pack_verts = self.geo.getHeaderElement("<iii")
        self.pack_norms = self.geo.getHeaderElement("<iii")
        self.pack_sts = self.geo.getHeaderElement("<iii")
        self.pack_sts3 = (0, 0, 0)
        self.pack_weights = self.geo.getHeaderElement("<iii")
        self.pack_matidxs = self.geo.getHeaderElement("<iii")
        self.pack_grid = self.geo.getHeaderElement("<iii")
        self.pack_reductions = (0, 0, 0)
        self.pack_reflection_quads = (0, 0, 0)

        self.name = extractString(self.geo.header_objname_data, self.name_ptr)
        self.autolod_dists = [-1, -1, -1]
        self.skipped_data = None
        #self.dump()
    def parseHeaderData(self):
        if self.geo.version <= 2:
            self.parseHeaderDataV2()
            return
        (size, ) = struct.unpack("<i", self.geo.header_data[self.geo.header_offset: self.geo.header_offset + 4])
        final_offset = self.geo.header_offset + size
        self.geo.header_offset += 4
        (self.radius, ) = self.geo.getHeaderElement("<f")
        (self.tex_count, self.boneinfo_ptr) = self.geo.getHeaderElement("<ii")
        (self.vert_count, self.tri_count) = self.geo.getHeaderElement("<ii")
        if self.geo.version >= 8:
            (self.reflection_quad_count, ) = self.geo.getHeaderElement("<i")
        (self.tex_idx_ptr, ) = self.geo.getHeaderElement("<i")
        self.grid_header = self.geo.getHeaderElement("<ifffffii")
        (self.name_ptr, self.api_ptr) = self.geo.getHeaderElement("<ii")
        self.scale = list(self.geo.getHeaderElement("<fff"))
        self.min = list(self.geo.getHeaderElement("<fff"))
        self.max = list(self.geo.getHeaderElement("<fff"))
        self.pack_tris = self.geo.getHeaderElement("<iii")
        self.pack_verts = self.geo.getHeaderElement("<iii")
        self.pack_norms = self.geo.getHeaderElement("<iii")
        self.pack_sts = self.geo.getHeaderElement("<iii")
        self.pack_sts3 = self.geo.getHeaderElement("<iii")
        self.pack_weights = self.geo.getHeaderElement("<iii")
        self.pack_matidxs = self.geo.getHeaderElement("<iii")
        self.pack_grid = self.geo.getHeaderElement("<iii")
        if self.geo.version == 4:
            #pack.lmap_utransforms, pack.lmap_vtransforms
            self.geo.header_offset += 12 * 2
        if self.geo.version >= 7:
            self.pack_reductions = self.geo.getHeaderElement("<iii")
        else:
            self.pack_reductions = (0, 0, 0)
        if self.geo.version >= 8:
            self.pack_reflection_quads = self.geo.getHeaderElement("<iii")
        else:
            self.pack_reflection_quads = (0, 0, 0)
        #pack_list = [
        #    self.pack_tris,
        #    self.pack_verts,
        #    self.pack_norms,
        #    self.pack_sts,
        #    self.pack_sts3,
        #    self.pack_weights,
        #    self.pack_matidxs,
        #    self.pack_grid,
        #    #pack.lmap_utransforms, pack.lmap_vtransforms
        #    self.pack_reductions,
        #    self.pack_reflection_quads,
        #]
        #other_list = [
        #    self.boneinfo_ptr,
        #    self.name_ptr,
        #    self.api_ptr,
        #]
        #(self.pack_boneinfo, self.pack_name, self.pack_api) = inferSizes(self.geo.main_data_size, pack_list, other_list)
        self.name = extractString(self.geo.header_objname_data, self.name_ptr)

        #self.geo.header_offset = final_offset - 12 - 2
        if self.geo.version <= 7:
            #lightmap_size
            self.geo.header_offset += 4
        if self.geo.version >= 7:
            self.autolod_dists = list(self.geo.getHeaderElement("<fff"))
        else:
            self.autolod_dists = [-1, -1, -1]
        #(self.mystery, ) = self.geo.getHeaderElement("<f")
        (self.id, ) = self.geo.getHeaderElement("<h")
        #self.mystery = self.geo.getHeaderElement("<fh")
        #print("automatic offset: %d  final offset: %d" % (self.geo.header_offset, final_offset))
        self.skipped_data = self.geo.header_data[self.geo.header_offset : final_offset]
        self.geo.header_offset = final_offset

    def parseData(self):
        self.tex_idx = []
        texidx_data = self.geo.header_texidx_data
        texidx_data.seek(self.tex_idx_ptr)
        c = 0
        for i in range(self.tex_count):
            self.tex_idx.append(texidx_data.decode("<HH"))
            c += self.tex_idx[-1][1]
        #todo: assert(c == self.tri_count)

        self.altpivotinfo = []
        if self.api_ptr != 0:
            self.geo.seekMainData(self.api_ptr)
            (self.altpivotinfo_count, ) = self.geo.getMainElement("<i")
            for i in range(self.altpivotinfo_count):
                self.altpivotinfo.append([])
                for j in range(4):
                    self.altpivotinfo[i].append(list(self.geo.getMainElement("<fff")))
        self.altpivotinfo_count = len(self.altpivotinfo)

        self.tris_data = self.geo.getDataBlock(self.pack_tris)
        self.verts_data = self.geo.getDataBlock(self.pack_verts)
        self.norms_data = self.geo.getDataBlock(self.pack_norms)
        self.sts_data = self.geo.getDataBlock(self.pack_sts)
        self.sts3_data = self.geo.getDataBlock(self.pack_sts3)
        self.weights_data = self.geo.getDataBlock(self.pack_weights)
        self.matidxs_data = self.geo.getDataBlock(self.pack_matidxs)
        self.grid_data = self.geo.getDataBlock(self.pack_grid)
        self.reductions_data = self.geo.getDataBlock(self.pack_reductions)
        self.reflection_quads_data = self.geo.getDataBlock(self.pack_reflection_quads)

        self.tris = uncompressDeltas(self.tris_data, 3, self.tri_count, "I")
        self.verts = uncompressDeltas(self.verts_data, 3, self.vert_count, "f")
        self.norms = uncompressDeltas(self.norms_data, 3, self.vert_count, "f")
        self.sts = uncompressDeltas(self.sts_data, 2, self.vert_count, "f")
        self.sts3 = uncompressDeltas(self.sts3_data, 2, self.vert_count, "f")

        if self.boneinfo_ptr != 0:
            self.geo.seekMainData(self.boneinfo_ptr)
            (self.bone_count, ) = self.geo.getMainElement("<i")
            self.bone_ids = self.geo.getMainElement("<" + ("i" * 15))
        else:
            self.bone_count = 0
            self.bone_ids = [0] * 15
        if len(self.weights_data) == 0:
            self.weights = None
            self.weight_bones = None
        else:
            self.weights = []
            self.weight_bones = []
            for i in range(self.vert_count):
                w = unbyte(self.weights_data[i]) / 255.0
                b = self.matidxs_data[i * 2 : i * 2 + 2]
                b1 = self.bone_ids[unbyte(b[0]) // 3]
                b2 = self.bone_ids[unbyte(b[1]) // 3]
                self.weights.append([w, 1 - w])
                self.weight_bones.append([b1, b2])

        if len(self.grid_data) == 0:
            self.polygrid = None
        else:
            self.polygrid = PolyGrid(self)
            self.polygrid.parsePolyGridData(self.grid_data, self.grid_header)

        if len(self.reductions_data) == 0:
            self.reductions = None
        else:
            #self.reductions = None
            #self.dump()
            self.reductions = Reductions(self)
            self.reductions.decode(Data(self.reductions_data))
        if len(self.reflection_quads_data) == 0:
            self.reflection_quads = None
        else:
            #todo:
            self.reflection_quads = None
        #if self.geo.version <= 2:
        #    self.dump()

    def packDeltas(self, data, stride, count, pack_type):
        deltas = compressDeltas(data, stride, count, pack_type)
        pack = self.geo.encodeMainDataPacked(deltas)
    def rebuildWeightsAndBones(self):
        self.weights_data = b""
        self.matidxs_data = b""
        if self.weights is None or len(self.weights) == 0:
            self.bone_count = 0
            self.bone_ids = [0] * 15
            return
        self.bone_ids = []
        bone_lookup = {}
        for wb in self.weight_bones:
            for wbx in wb:
                if wbx not in bone_lookup:
                    bone_lookup[wbx] = len(self.bone_ids)
                    self.bone_ids.append(wbx)
        #print(self.weights)
        for i in range(len(self.weights)):
            #Copy values to avoid corruption.
            w = self.weights[i][:]
            wb = self.weight_bones[i][:]
            if len(w) > 2:
                #.geos only support 2 weights per vertex.
                #todo: get only largest weights?
                w = w[0 : 2]
                wb = wb[0 : 2]
            if len(w) == 1 or wb[0] == wb[1]:
                self.weights_data += byte(255)
                self.matidxs_data += byte(bone_lookup[wb[0]] * 3) + ZERO_BYTE
                continue
            if w[0] + w[1] == 0:
                w[0] = 0.5
                w[1] = 0.5
            w[0] = w[0] / float(w[0] + w[1])
            if w[0] < 0:
                w[0] = 0.0
            elif w[0] > 1:
                w[0] = 1.0
            #print("weights: %s -> %s" % (self.weights[i], w))
            self.weights_data += byte(int(math.floor(255 * w[0] + 0.5)))
            self.matidxs_data += byte(bone_lookup[wb[0]] * 3) +byte(bone_lookup[wb[1]] * 3)
        self.bone_count = len(self.bone_ids)
        self.bone_ids += [0] * (15 - self.bone_count)
    def encode(self):
        #Regenerate dynamic data
        if self.verts is not None and len(self.verts) > 0:
            self.polygrid = PolyGrid(self)
            self.grid_data = self.polygrid.encode()
            self.grid_header = self.polygrid.grid_header
            self.radius = self.polygrid.radius
            self.min = self.polygrid.aabb.min.data
            self.max = self.polygrid.aabb.max.data
        else:
            self.polygrid = None
            self.grid_data = b""
            self.grid_header = (0, 0.0, 0.0, 0.0, 1.0, 1.0, 0, 0)
            self.radius = 0
            self.min = [0, 0, 0]
            self.max = [0, 0, 0]
        if self.geo.version >= 7:
            #todo: build reductions
            if self.reductions is not None:
                self.reductions_data = self.reductions.encode()
            else:
                self.reductions_data = b""
            pass
        self.rebuildWeightsAndBones()

        #Encode data into the main block.
        #note: PackData should go first, otherwise other ptr types might point to the start of the data block, which would result in a 0 point, which is treated as not present.
        self.pack_tris = self.geo.encodeMainDataPackedDeltas(self.tris, 3, self.tris and len(self.tris), "I", 1)
        self.pack_verts = self.geo.encodeMainDataPackedDeltas(self.verts, 3, self.verts and len(self.verts), "f", 0x8000)
        self.pack_norms = self.geo.encodeMainDataPackedDeltas(self.norms, 3, self.norms and len(self.norms), "f", 0x100)
        self.pack_sts = self.geo.encodeMainDataPackedDeltas(self.sts, 2, self.sts and len(self.sts), "f", 0x1000)
        self.pack_sts3 = self.geo.encodeMainDataPackedDeltas(self.sts3, 2, self.sts3 and len(self.sts3), "f", 0x8000)
        self.pack_weights = self.geo.encodeMainDataPacked(self.weights_data)
        self.pack_matidxs = self.geo.encodeMainDataPacked(self.matidxs_data)
        self.pack_grid = self.geo.encodeMainDataPacked(self.grid_data)
        self.pack_reductions = self.geo.encodeMainDataPacked(self.reductions_data)
        self.pack_reflection_quads = self.geo.encodeMainDataPacked(self.reflection_quads_data)
        if self.bone_count > 0:
            bone_data = struct.pack("<" + "i" * (1 + 15), self.bone_count, *self.bone_ids)
            bone_data += struct.pack("<ii", 0, 0) #weights_ptr and matidx_ptr place holders, needed by the game
            self.boneinfo_ptr = self.geo.encodeMainData(bone_data)
        else:
            self.boneinfo_ptr

        api_data = b""
        if len(self.altpivotinfo) > 0:
            api_data = struct.pack("<i", len(self.altpivotinfo))
            for i in range(len(self.altpivotinfo)):
                for j in range(len(self.altpivotinfo[i])):
                    api_data += struct.pack("<fff", *self.altpivotinfo[i][j])
            for i in range(15 - len(self.altpivotinfo)):
                api_data += struct.pack("<fff", 0, 0, 0) * 4
        if len(api_data) > 0:
            self.api_ptr = self.geo.encodeMainData(api_data)
        else:
            self.api_ptr = 0

        #Encode shared header data
        self.texidx_ptr = len(self.geo.header_texidx_data)
        texidx_data = self.geo.header_texidx_data
        texidx_data.seekEnd()
        for t in self.tex_idx:
            texidx_data.encode("<HH", *t)
        self.tex_count = len(self.tex_idx)
        self.vert_count = self.verts and len(self.verts) or 0
        self.tri_count = self.tris and len(self.tris) or 0
        self.name_ptr = len(self.geo.header_objname_data)
        self.geo.header_objname_data += self.name + ZERO_BYTE
        self.geo.header_objnames.append(self.name)
        
        #Encode the header
        self.header_data = b""
        self.header_data += struct.pack("<f", self.radius)
        self.header_data += struct.pack("<i", self.tex_count)
        self.header_data += struct.pack("<i", self.boneinfo_ptr)
        self.header_data += struct.pack("<i", self.vert_count)
        self.header_data += struct.pack("<i", self.tri_count)
        if self.geo.version >= 8:
            if self.reflection_quads is None or len(self.reflection_quads):
                self.reflection_quads_count = 0
            else:
                self.reflection_quads_count = len(self.reflection_quads)
            self.header_data += struct.pack("<i", self.reflection_quads_count)
            pass
        self.header_data += struct.pack("<i", self.texidx_ptr)
        self.header_data += struct.pack("<ifffffii", *self.grid_header)
        self.header_data += struct.pack("<i", self.name_ptr)
        self.header_data += struct.pack("<i", self.api_ptr)
        self.header_data += struct.pack("<fff", *self.scale)
        self.header_data += struct.pack("<fff", *self.min)
        self.header_data += struct.pack("<fff", *self.max)
        self.header_data += struct.pack("<iii", *self.pack_tris)
        self.header_data += struct.pack("<iii", *self.pack_verts)
        self.header_data += struct.pack("<iii", *self.pack_norms)
        self.header_data += struct.pack("<iii", *self.pack_sts)
        self.header_data += struct.pack("<iii", *self.pack_sts3)
        self.header_data += struct.pack("<iii", *self.pack_weights)
        self.header_data += struct.pack("<iii", *self.pack_matidxs)
        self.header_data += struct.pack("<iii", *self.pack_grid)
        if self.geo.version == 4:
            #pack.lmap_utransforms, pack.lmap_vtransforms
            self.header_data += struct.pack("<iiiiii", 0, 0, 0, 0, 0, 0)
        if self.geo.version >= 7:
            self.header_data += struct.pack("<iii", *self.pack_reductions)
            pass
        if self.geo.version >= 8:
            self.header_data += struct.pack("<iii", *self.pack_reflection_quads)
            pass
        self.header_data += struct.pack("<fff", *self.autolod_dists)
        self.header_data += struct.pack("<h", self.id)

        if self.geo.version >= 8:
            #Pad to match the alignment of "ModelFormatOnDisk_v8" produced by "GetVrml/output.c"
            self.header_data += struct.pack("<h", 0)

        self.header_data = struct.pack("<i", len(self.header_data) + 4) + self.header_data
        pass
    def encodeHeader(self):
        self.geo.header_data += self.header_data

    def getBoneRoot(self):
        if self.bone_count <= 0:
            return None
        #todo: find the root properly. For now it just grabs the lowest bone id and hopes it's right.
        #print("getBoneRoot():")
        bid = self.bone_ids[0]
        for i in range(self.bone_count):
            b = self.bone_ids[i]
            #print("   %s : %s" % (bid, b))
            if b < bid:
                bid = b
        return BONES_LIST[bid]
    def dump(self):
        print("    radius: %s" % self.radius)
        print("    tex_count: %s" % self.tex_count)
        print("    boneinfo_ptr: %s" % self.boneinfo_ptr)
        print("    vert_count: %s" % self.vert_count)
        print("    tri_count: %s" % self.tri_count)
        print("    name_ptr: %s" % self.name_ptr)
        print("    api_ptr: %s" % self.api_ptr)
        print("    grid: %s" % (self.grid_header, ))
        print("    scale: %s" % self.scale)
        print("    min: %s" % self.min)
        print("    max: %s" % self.max)
        print("    pack_tris: %s" % (self.pack_tris, ))
        print("    pack_verts: %s" % (self.pack_verts, ))
        print("    pack_norms: %s" % (self.pack_norms, ))
        print("    pack_sts: %s" % (self.pack_sts, ))
        print("    pack_sts3: %s" % (self.pack_sts3, ))
        print("    pack_weights: %s" % (self.pack_weights, ))
        print("    pack_matidxs: %s" % (self.pack_matidxs, ))
        print("    pack_grid: %s" % (self.pack_grid, ))
        #print("    pack_boneinfo: %s" % (self.pack_boneinfo, ))
        #print("    pack_name: %s" % (self.pack_name, ))
        #print("    pack_api: %s" % (self.pack_api, ))
        print("    autolod_dists: %s" % (self.autolod_dists, ))
        print("    id: %s" % (self.id, ))
        #print("    mystery: %s" % (self.mystery, ))
        print("    skipped_data: %s" % ([self.skipped_data], ))

        print("    name: %s" % self.name)
        #print("    tris_data: %s" % ([self.tris_data], ))
        #print("    verts_data: %s" % ([self.verts_data], ))
        #print("    sts_data: %s" % ([self.sts_data], ))
        #print("    sts3_data: %s" % ([self.sts3_data], ))
        #print("    weights_data: %s" % ([self.weights_data], ))
        #print("    matidxs_data: %s" % ([self.matidxs_data], ))
        #print("    grid_data: %s" % ([self.grid_data], ))
        #print("    reductions_data: %s" % ([self.reductions_data], ))
        print("    reflection_quads_data: %s" % ([self.reflection_quads_data], ))

        print("    tex_idx: %s" % ([self.tex_idx]))
        print("    tris: %s" % ([self.tris], ))
        print("    verts: %s" % ([self.verts], ))
        print("    norms: %s" % ([self.norms], ))
        print("    weights: %s" % ([self.weights], ))
        print("    weight_bones (matidxs): %s" % ([self.weight_bones], ))
        if self.polygrid == None:
            print("    grid: None")
        else:
            print("    grid:")
            self.polygrid.dump()
        if self.reductions == None:
            print("    reductions: None")
        else:
            self.reductions.dump()
            
        print("    sts: %s" % ([self.sts], ))
        print("    sts3: %s" % ([self.sts3], ))

        print("    bone_count: %d" % self.bone_count)
        print("    bone_ids: %s" % (self.bone_ids, ))

        print("    altpivotinfo: %s" % (self.altpivotinfo, ))
        for i in range(self.bone_count):
            print("        : %s" % (BONES_LIST[self.bone_ids[i]], ))

    def saveToGeoMesh(self):
        geomesh = GeoMesh()
        geomesh.have_uvs = self.sts is not None
        geomesh.have_weights = self.weights is not None
        for i in range(len(self.verts)):
            coord = self.verts[i]
            normal = self.norms[i]
            if geomesh.have_uvs:
                uv = self.sts[i]
            else:
                uv = (0, 0)
            if geomesh.have_weights:
                weights = []
                #print("verts #: %s  weights #: %s  weight bones #: %s" % (len(self.verts), len(self.weights), len(self.weight_bones)))
                #for k, w in enumerate(self.weights):
                w = self.weights[i]
                w_bones = self.weight_bones[i]
                for j, b in enumerate(w_bones):
                    if w[j] == 0:
                        continue
                    #print("vertex_idx: %s weight_bones: %s" % (i, b, ))
                    #print("  bone_id: %s" % (self.bone_ids[b], ))
                    w_name = BONES_LIST[b]
                    #weights.append((geomesh.getWeightIndex(w_name), w[j]))
                    geomesh.getWeightIndex(w_name)
                    weights.append([w_name, w[j]])
            else:
                weights = []
            #print("   weights: %s" % (weights, ))
            v = GeoVertex(coord, normal, uv, weights)
            geomesh.getGeoVertexIndexNew(v)
        texture_indexes = []
        #print("Geo.tex_idx: %s Geo.geo.header_texnames: %s" % (self.tex_idx, self.geo.header_texnames))
        for t in self.tex_idx:
            texture_indexes += [geomesh.getTextureIndex(self.geo.header_texnames[t[0]])] * t[1]
        #print("len(self.verts): %s" % (len(self.verts), ))
        #print("len(geomesh.geovertex): %s" % (len(geomesh.geovertex), ))
        #print("%s" % (self.tex_idx, ))
        #print("%s" % (texture_indexes, ))
        for i, t in enumerate(self.tris):
            #print("  - %s: %s" % (i, t))
            geomesh.addFace([geomesh.geovertex[t[0]], geomesh.geovertex[t[1]], geomesh.geovertex[t[2]]], texture_indexes[i])
        return geomesh
    def loadFromGeoMesh(self, geomesh):
        self.tris = [] #uncompressDeltas(self.tris_data, 3, self.tri_count, "I")
        self.verts = [] #uncompressDeltas(self.verts_data, 3, self.vert_count, "f")
        self.norms = [] #uncompressDeltas(self.norms_data, 3, self.vert_count, "f")
        self.sts = [] #uncompressDeltas(self.sts_data, 2, self.vert_count, "f")
        self.sts3 = None #uncompressDeltas(self.sts3_data, 2, self.vert_count, "f")
        self.tex_idx = []
        self.reductions = None
        self.reflection_quads_data = None
        self.reflection_quads = None
        self.altpivotinfo = []
        self.scale = [1.0, 1.0, 1.0]
        self.autolod_dists = [-1, -1, -1]
        self.id = -2

        if geomesh.have_weights:
            self.weights = []
            self.weight_bones = []
        else:
            self.weights = None
            self.weight_bones = None
        geomesh.sortFaces()
        #Determine the remap for converting geomesh textures indexes to geo texture indexes.
        texture_remap = []
        for i in range(len(geomesh.textures)):
            texture_remap.append(self.geo.getTextureIndex(geomesh.textures[i]))
        #Determine the remap for converting geomesh weight/bones indexes to geo weight/bone indexes.
        geomesh.rebuildWeightsList()
        weight_remap = {}
        for i in range(len(geomesh.weights)):
            #weight_remap.append(BONES_LOOKUP.get(geomesh.weights[i], 0))
            weight_remap[geomesh.weights[i]] = BONES_LOOKUP.get(geomesh.weights[i], 0)
            #print("   '%s' -> %s" % (geomesh.weights[i], weight_remap[geomesh.weights[i]]))
        #if len(weight_remap) <= 0:
        #    weight_remap.append(0)
        #Convert vetices to: positions, normals, uvs, weights
        for i, v in enumerate(geomesh.geovertex):
            self.verts.append(v.coord)
            self.norms.append(v.normal)
            self.sts.append(v.uv)
            if geomesh.have_weights:
                weights = v.selectWeights(2)
                #print(weights)
                if len(weights) == 0:
                    self.weights.append([1, 0])
                    self.weight_bones.append([weight_remap[0], weight_remap[0]])
                elif len(weights) == 1:
                    self.weights.append([weights[0][1], 0])
                    self.weight_bones.append([weight_remap[weights[0][0]], weight_remap[weights[0][0]]])
                else:
                    self.weights.append([weights[0][1], weights[1][1]])
                    self.weight_bones.append([weight_remap[weights[0][0]], weight_remap[weights[1][0]]])
        #Convert faces
        texture_index = None
        texture_count = 0
        for i, t in enumerate(geomesh.face):
            self.tris.append(t.vert_indexes)
            if texture_index != t.texture_index:
                if texture_index is not None:
                    self.tex_idx.append((texture_remap[texture_index], texture_count))
                texture_count = 0
                texture_index = t.texture_index
            texture_count += 1
        if texture_count != 0:
            self.tex_idx.append((texture_remap[texture_index], texture_count))
        print("self.tex_idx: %s" % (self.tex_idx, ))


class Geo:
    def __init__(self):
        self.data = b""
        self.offset = 0
        self.version = -1
        self.models = []
        self.header_texnames = []
        self.header_modelheader_tracklength = 0
        pass
    def loadFromData(self, data):
        self.data = data
        self.offset = 0
        self.parseData()
        pass
    def loadFromFile(self, filein):
        self.data = filein.read()
        self.offset = 0
        self.parseData()
        pass
    def saveToData(self):
        self.encode()
        return self.data
    def saveToFile(self, fileout):
        self.encode()
        fileout.write(self.data)
    def parseData(self):
        (ziplen, self.header_size) = struct.unpack("<ii", self.data[self.offset : self.offset + 8])
        if self.header_size != 0:
            self.version = 0
            self.offset += 8
            ziplen -= 4
        else:
            (self.version,
             self.header_size) = struct.unpack("<ii", self.data[self.offset + 8: self.offset + 8 + 8])
            ziplen -= 12
            self.offset += 16
        #print("%s" % [self.data[self.offset : self.offset + ziplen]])
        self.header_data = zlib.decompress(self.data[self.offset : self.offset + ziplen])#, bufsize = self.header_size)
        self.offset += ziplen
        if self.version == 0:
            self.offset += 4

        self.header_offset = 0
        (self.main_data_size,
         self.texname_blocksize,
         self.objname_blocksize,
         self.texidx_blocksize) = struct.unpack("<iiii", self.header_data[self.header_offset : self.header_offset + 16])
        self.header_offset += 16
        if self.version >= 2 and self.version <= 6:
            (self.lodinfo_blocksize, ) = struct.unpack("<i", self.header_data[self.header_offset : self.header_offset + 4])
            self.header_offset += 4
        else:
            self.lodinfo_blocksize = 0
        self.header_texname_data = self.header_data[self.header_offset : self.header_offset + self.texname_blocksize]
        self.header_offset += self.texname_blocksize
        self.header_objname_data = self.header_data[self.header_offset : self.header_offset + self.objname_blocksize]
        self.header_offset += self.objname_blocksize
        self.header_texidx_data = Data(self.header_data[self.header_offset : self.header_offset + self.texidx_blocksize])
        self.header_offset += self.texidx_blocksize
        self.header_lodinfo_data = self.header_data[self.header_offset : self.header_offset + self.lodinfo_blocksize]
        self.header_offset += self.lodinfo_blocksize

        self.header_modelheader_data = self.header_data[self.header_offset : self.header_offset + 124 + 4 + 4 + 4 + 4]
        self.header_offset += 124 + 4 + 4 + 4 + 4

        self.header_texnames = unpackNames(self.header_texname_data)
        self.header_objnames = unpackStrings(self.header_objname_data)
        self.header_modelheader_name = extractString(self.header_modelheader_data[0:124])
        (self.header_modelheader_tracklength, ) = struct.unpack("<f", self.header_modelheader_data[124 + 4: 124 + 4 + 4])
        (self.header_modelheader_modelcount, ) = struct.unpack("<i", self.header_modelheader_data[124 + 4 + 4 + 4: 124 + 4 + 4 + 4 + 4])
        #print("main offset: %d 0x%x" % (self.offset, self.offset))
        self.main_data = self.data[self.offset : self.offset + self.main_data_size]
        #print(" %s" % [self.main_data])
        self.models = []
        #self.dump()
        for i in range(self.header_modelheader_modelcount):
            self.models.append(Model(self))
            self.models[-1].parseHeaderData()
            self.models[-1].parseData()
            #if i < len(self.header_objnames):
            #    self.models[-1].name = self.header_objnames[i]

    def getHeaderElement(self, fmt):
        size = struct.calcsize(fmt)
        data = struct.unpack(fmt, self.header_data[self.header_offset : self.header_offset + size])
        self.header_offset += size
        return data
    def getDataBlock(self, tup):
        #print("%s" % (tup, ))
        (packsize, unpacksize, offset) = tup
        if packsize == 0:
            return self.main_data[offset : offset + unpacksize]
        rawdata = self.main_data[offset : offset + packsize]
        #print("%s" % [rawdata])
        try:
            data = zlib.decompress(rawdata)
        except Exception as e:
            print("%s" % (tup, ))
            print("%s" % [rawdata])
            traceback.print_exc()
            #data = rawdata
            raise e
        #todo: sanity check size?
        return data

    def getTextureIndex(self, texture_name):
        if isinstance(texture_name, str):
            texture_name = bytes(texture_name, "utf-8")
        for i in range(len(self.header_texnames)):
            if texture_name == self.header_texnames[i]:
                return i
        i = len(self.header_texnames)
        self.header_texnames.append(texture_name)
        return i

    def encode(self):
        self.data = None
        self.version = 8
        self.main_data = b""
        self.header_data = b""
        self.header_objnames = []
        self.header_objname_data = b""
        self.lodinfo_data = b""
        self.header_texidx_data = Data()
        #Encode models into main data
        for m in self.models:
            m.encode()
        #Convert remaining data
        self.header_texname_data = packNames(self.header_texnames)
        #Encode information into header data.
        self.header_data += struct.pack("<iiii", len(self.main_data), len(self.header_texname_data), len(self.header_objname_data), len(self.header_texidx_data))
        if self.version >= 2 and self.version <= 6:
            self.header_data += struct.pack("<i", len(self.lodinfo_data))
        self.header_data += self.header_texname_data + self.header_objname_data + self.header_texidx_data.data
        if self.version >= 2 and self.version <= 6:
            self.header_data += self.lodinfo_data
        #Encode the main model header.
        self.header_data += storeString(self.header_modelheader_name, 124)
        self.header_data += struct.pack("<ifii", 0, self.header_modelheader_tracklength, -1, len(self.models))
        #Encode model headers into header data.
        for m in self.models:
            m.encodeHeader()
        zheader_data = zlib.compress(self.header_data)
        if self.version == 0:
            preheader = struct.pack("<ii", len(zheader_data) + 4, len(self.header_data))
        else:
            preheader = struct.pack("<iiii", len(zheader_data) + 12, 0, self.version, len(self.header_data))
        if self.version == 0:
            zheader += struct.pack("<i", 0)
        self.data = preheader + zheader_data + self.main_data
    def encodeObjName(self, name):
        o = len(self.header_objname_data)
        self.header_objname_data += name + ZERO_BYTE
        self.header_objnames.append(name)
        return o
    def encodeMainData(self, data):
        o = len(self.main_data)
        self.main_data += data
        return o
    def encodeMainDataPacked(self, data):
        o = len(self.main_data)
        if data is None or len(data) <= 0:
            return (0, 0, o)
        #todo: minimum compression?
        d = zlib.compress(data)
        if len(d) >= len(data):
            self.main_data += data
            return (0, len(data), o)
        else:
            self.main_data += d
            return (len(d), len(data), o)
    def encodeMainDataPackedDeltas(self, data, stride, count, pack_type, float_scale):
        if data is None:
            return (0, 0, 0)
        deltas = compressDeltas(data, stride, count, pack_type, float_scale)
        pack = self.encodeMainDataPacked(deltas)
        return pack

    def dump(self):
        print("version: %d" % self.version)
        print("header_size: expected: %d  actual: %d" % (self.header_size, len(self.header_data)))
        #print("header_data: %s" % [self.header_data])
        print("main_data_size: %d" % self.main_data_size)
        print("header_data sizes: texname: %d  objname: %d  texidx: %d  lodinfo: %d" % (self.texname_blocksize, self.objname_blocksize, self.texidx_blocksize, self.lodinfo_blocksize))
        print("header_texname_data: %s" % [self.header_texname_data])
        print("header_texnames: %s" % [self.header_texnames])
        print("header_objname_data: %s" % [self.header_objname_data])
        print("header_objnames: %s" % [self.header_objnames])
        print("header_texidx_data: %s" % [self.header_texidx_data])
        print("header_lodinfo_data: %s" % [self.header_lodinfo_data])
        print("header_modelheader_name: %s" % [self.header_modelheader_name])
        print("header_modelheader_tracklength: %s" % self.header_modelheader_tracklength)
        print("header_modelheader_modelcount: %s" % self.header_modelheader_modelcount)
        print("header_modelheader_data: %s" % [self.header_modelheader_data[124:]])
        print("header remaining: %d" % ((len(self.header_data) - self.header_offset), ))
        print("header remaining: %s" %  ([self.header_data[self.header_offset:]], ))

        #%d  objname: %d  texidx: %d  lodinfo: %d" % (self.texname_blocksize, self.objname_blocksize, self.texidx_blocksize, self.lodinfo_blocksize)
        for i in range(len(self.models)):
            print("Model %d:" % (i, ))
            self.models[i].dump()

    def seekMainData(self, offset):
        self.main_data_offset = offset
    def skipMainData(self, skip):
        if type(skip) is int:
            self.main_data_offset += skip
        else:
            self.main_data_offset += struct.calcsize(skip)
    def getMainElement(self, fmt):
        size = struct.calcsize(fmt)
        data = struct.unpack(fmt, self.main_data[self.main_data_offset : self.main_data_offset + size])
        self.main_data_offset += size
        return data
    def getElement(self, offset, fmt):
        size = struct.calcsize(fmt)
        data = struct.unpack(fmt, self.main_data[offset : offset + size])
        return data

    def setName(self, name):
        if isinstance(name, str):
            name = bytes(name, "utf-8")
        self.header_modelheader_name = name
    def addModel(self, name):
        if isinstance(name, str):
            name = bytes(name, "utf-8")
        self.models.append(Model(self))
        self.models[-1].name = name
        return self.models[-1]

if __name__ == "__main__":
    if len(sys.argv) <= 1 or len(sys.argv) > 3:
        print("Usage:")
        print("   %s <file_in> [<file_out>]" % (sys.argv[0], ))
        print("Test loads a .geo file, dumps its content, and optionally writes its content out.")
        exit(0)
    fh = open(sys.argv[1], "rb")
    geo = Geo()
    geo.loadFromFile(fh)
    fh.close()
    #print(sys.argv)
    if len(sys.argv) <= 2:
        fho = None
    else:
        fho = open(sys.argv[2], "wb")
    if fho is not None:
        data = geo.saveToData()
        #geo.dump()
        fho.write(data)
    else:
        geo.dump()
    #print("%s" % [geo.header_data])
