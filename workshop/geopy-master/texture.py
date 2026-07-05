import sys
import struct
import math
#from PIL import Image
from wand.image import Image
import io

#TextureFileHeader
#offset	size	description
#0	4	i32: header_size
#4	4	i32: file_size
#8	4	i32: width
#12	4	i32: height
#16	4	u32(TexOptFlags): flags
#20	4	f32[2]: fade
#28	1	u8: alpha
#29	3	u8[3]: version "TEX" or "TX2"
#32	variable	char[] (ASCIIZ): file path of origianl texture
#?	16	TextureFileMipHeader: mipmap_header  (TX2 only) (optional, assumed present if header_size is larger than previous data.)
#?	?	MipMapData: All mipmap data that's 8x8 or smaller. (TX2 only) (present if mipmap_header is present)

#TextureFileMipHeader
#offset	size	description
#0	4	i32: structsize
#4	4	i32: width
#8	4	i32: height
#12	4	i32: format
#16

#MipMapData
#This contains a copy of the mipmap of size mipmap_header.width by mipmap_header.height and all thos smaller than it. The format should match that of the main texture.

#TexReadInfo
#0	4	ptr: data?
#4	4	i32: mip_count
#8	4	i32: format
#12	4	i32: mip_count
#16	4	i32: width
#20	4	i32: height
#24	4	i32: size
#28

#TexReadInfo

GL_FORMATS = {
    "GL_COMPRESSED_RGB_S3TC_DXT1_EXT": 0x83F0,
    "GL_COMPRESSED_RGBA_S3TC_DXT1_EXT":  0x83F1,
    "GL_COMPRESSED_RGBA_S3TC_DXT3_EXT":  0x83F2,
    "GL_COMPRESSED_RGBA_S3TC_DXT5_EXT":  0x83F3,
}
GL_FORMATS_LOOKUP = {}
for k, v in GL_FORMATS.items():
    GL_FORMATS_LOOKUP[v] = k

TEX_OPT_FLAGS = [
    "TEX_ALPHA", # bit 0
    "TEX_RGB8",  # bit 1
    "TEX_COMP4", # bit 2
    "TEX_COMP8", # bit 3
    "TEX_UNKNOWN_BIT_4", # bit 4
    "TEX_TGA",   # bit 5
    "TEX_DDS",   # bit 6
    "TEX_UNKNOWN_BIT_7", # bit 7
    "TEX_UNKNOWN_BIT_8", # bit 8
    "TEX_CUBEMAPFACE",   # bit 9
    "TEX_REPLACEABLE",   # bit 10
    "TEX_BUMPMAP",   # bit 11
    "TEX_UNKNOWN_BIT_12", # bit 12
    "TEX_JPEG",  # bit 13
]

while len(TEX_OPT_FLAGS) < 32:
    TEX_OPT_FLAGS.append("TEX_UNKNOWN_BIT_%d" % len(TEX_OPT_FLAGS))

TEX_OPT_FLAGS_LOOKUP = {}
for i in range(32):
    s = TEX_OPT_FLAGS[i]
    TEX_OPT_FLAGS_LOOKUP[s] = i
    TEX_OPT_FLAGS_LOOKUP[s.lower()] = i
    if s.startswith("TEX_"):
        TEX_OPT_FLAGS_LOOKUP[s[4:]] = i
        TEX_OPT_FLAGS_LOOKUP[s[4:].lower()] = i

def decodeTexOptFlags(bits):
    v = []
    for i in range(32):
        if bits & (1 << i):
            v.append(TEX_OPT_FLAGS[i])
    return v
def encodeTexOptFlags(flags):
    v = 0
    for f in flags:
        v = v | (1 << TEX_OPT_FLAGS_LOOKUP[f.upper()])
    return v

class Texture:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.tex_opt_flags = []
        self.tex_opt_flags_data = 0
        self.fade = [0, 0]
        self.alpha = None
        self.version = 2
        self.version_string = b"TX2"
        self.image_data = None
        self.filename = None
        self.mip_present = False
        self.mip_struct_size = 0
        self.mip_width = 0
        self.mip_height = 0
        self.mip_format = 0
        self.mip_data = None
        #self.header_size = 0
        #self.file_size = 0

        self.image = None

    def extractRawMipMapData(self, cell_w, cell_h, cell_bytes):
        #Computes the number of cells of data
        cell_count = 0
        w = self.width
        h = self.height
        #Halve width and height until both are 8 pixels or less.
        while w > 8 or h > 8:
            w = int(math.ceil(w / 2.0))
            h = int(math.ceil(h / 2.0))
        self.mip_width = w
        self.mip_height = h
        #Determine the number of cells used by this cell and all those smaller than it.
        while True:
            #What is the width and height of this mip map, in cells?
            #Number has to be rounded up.
            cw = int(math.ceil(w / float(cell_w)))
            ch = int(math.ceil(h / float(cell_h)))
            #Accumulate cells.
            cell_count += cw * ch
            #Stop if this was 1 by 1 pixel.
            if w <= 1 and h <= 1:
                break
            #Halve width and height for next smaller mip map.
            w = int(math.ceil(w / 2.0))
            h = int(math.ceil(h / 2.0))
        #Return the data for the last cell_count cells in the source file.
        return self.image_data[-(cell_count * cell_bytes) : ]
    def extractMipMapData(self):
        #cell_w, cell_h = 1, 1
        #if self.image.alpha_channel:
        #    cell_bytes = 4
        #else:
        #    cell_bytes = 3
        if self.image.format == 'DDS':
            #todo: a real lazy kludge to find the format of the image.
            img_header = self.image_data[0:512]
            if b"DXT1" in img_header:
                if self.alpha:
                    self.mip_format = GL_FORMATS["GL_COMPRESSED_RGBA_S3TC_DXT1_EXT"]
                else:
                    self.mip_format = GL_FORMATS["GL_COMPRESSED_RGB_S3TC_DXT1_EXT"]
                cell_bytes = 8
            elif b"DXT3" in img_header:
                self.mip_format = GL_FORMATS["GL_COMPRESSED_RGBA_S3TC_DXT3_EXT"]
                cell_bytes = 16
            elif b"DXT5" in img_header:
                self.mip_format = GL_FORMATS["GL_COMPRESSED_RGBA_S3TC_DXT5_EXT"]
                cell_bytes = 16
            else:
                self.mip_present = False
                return
            cell_w, cell_h = 4, 4
        else:
            self.mip_present = False
            return
        self.mip_present = True
        self.mip_data = self.extractRawMipMapData(cell_w, cell_h, cell_bytes)
        
    def extractImageInfo(self):
        self.width = self.image.width
        self.height = self.image.height

    def setImageData(self, image_data):
        self.image_data = image_data
        self.image = Image(file = io.BytesIO(self.image_data))
        self.width = self.image.width
        self.height = self.image.height
        if self.image.alpha_channel:
            image_raw = self.image.make_blob(format = "RGBA")
            alpha_raw = image_raw[3::4]
            count = 0
            #todo: there's probably a better way than this
            for i in range(247, 256):
                b = bytes((i, ))
                count += alpha_raw.count(b)
            self.alpha = count < len(alpha_raw)
        else:
            self.alpha = False
        
    def loadFromFile(self, fh):
        self.loadFromData(fh.read())
    def loadFromData(self, data):
        main_header_size = struct.calcsize("<iiiiIffB3s")
        offset = 0
        (
            self.header_size,
            self.file_size,
            self.width,
            self.height,
            self.tex_opt_flags_data,
            self.fade[0],
            self.fade[1],
            self.alpha,
            self.version_string,
        ) = struct.unpack("<iiiiIffB3s", data[offset : offset + main_header_size])
        if self.version_string == b"TEX":
            self.version = 1
        elif self.version_string == b"TX2":
            self.version = 2
        else:
            self.version = 0
            #todo: raise errror
        offset += main_header_size
        filename_end = data.find(b"\x00", offset)
        if filename_end < 0:
            filename_end = len(data)
        self.filename = data[offset : filename_end]
        offset = filename_end + 1
        self.mip_struct_size = 0
        self.mip_width = 0
        self.mip_height = 0
        self.mip_format = 0
        self.tex_opt_flags = decodeTexOptFlags(self.tex_opt_flags_data)
        if self.version == 2:
            if self.header_size > offset:
                self.mip_present = True
                texture_file_mip_header_size = struct.calcsize("<iiii")
                (
                    self.mip_struct_size,
                    self.mip_width,
                    self.mip_height,
                    self.mip_format,
                ) = struct.unpack("<iiii", data[offset : offset + texture_file_mip_header_size])
                offset += self.mip_struct_size #texture_file_mip_header_size
                self.mip_data = data[offset : self.header_size]
                #mip_size = struct.calcsize("<iiii")
                #while offset < len(header_size):
                #    offset += mip_size
            else:
                self.mip_present = False
        else:
            self.mip_data = b""
        
        self.image_data = data[self.header_size:]
        #print("%s" % (repr(self.image_data[0:16]), ))
        self.image = Image(file = io.BytesIO(self.image_data))
        self.extractImageInfo()

    def saveToFile(self, fh):
        fh.write(self.saveToData)
    def saveToData(self):
        data = b""
        #Set version and version string.
        self.version = 2
        if self.version == 1:
            self.version_string = b"TEX"
        elif self.version == 2:
            self.version_string = b"TX2"
        else:
            self.version_string = b"TX2"
            #todo: raise error
        #extract mipmap data
        self.extractMipMapData()
        #encode mipmap data and header
        if self.version >= 2:
            if self.mip_present:
                self.mip_struct_size = struct.calcsize("<iiii")
                mipmap_data = struct.pack("<iiii",
                                          self.mip_struct_size,
                                          self.mip_width,
                                          self.mip_height,
                                          self.mip_format) + self.mip_data
            else:
                mipmap_data = b""
        #encode filename
        filename_data = self.filename + b"\x00"
        #compute sizes
        main_header_size = struct.calcsize("<iiiiIffB3s")
        self.header_size = main_header_size + len(filename_data) + len(mipmap_data)
        self.file_size = len(self.image_data)
        #encode flags
        self.tex_opt_flags_data = encodeTexOptFlags(self.tex_opt_flags)
        #encode header
        header_data = struct.pack("<iiiiIffB3s",
                                  self.header_size,
                                  self.file_size,
                                  self.width,
                                  self.height,
                                  self.tex_opt_flags_data,
                                  self.fade[0],
                                  self.fade[1],
                                  self.alpha,
                                  self.version_string)
        #assemble data
        data = header_data + filename_data + mipmap_data + self.image_data
        return data
    def dump(self):
        print("header_size: %d" % (self.header_size, ))
        print("image_file_size: %d" % (self.file_size, ))
        print("width x height: %d x %d" % (self.width, self.height))
        print("tex_opt_flags_data: 0x%8.8x" % (self.tex_opt_flags_data, ))
        print("tex_opt_flags: %s" % (self.tex_opt_flags, ))
        print("fade: %s" % (self.fade, ))
        print("alpha: %s" % (self.alpha, ))
        print("version: %s (%s)" % (self.version, self.version_string))
        print("filename: %s" % (self.filename, ))
        print("mip_struct_size: %d" % (self.mip_struct_size, ))
        print("mip_width: %d" % (self.mip_width, ))
        print("mip_height: %d" % (self.mip_height, ))
        print("mip_format: 0x%8.8x (%s)" % (self.mip_format, GL_FORMATS_LOOKUP[self.mip_format]))
        print("mip_data: len: %d" % (self.mip_data and len(self.mip_data) or 0, ))
        print("mip_data: %s" % (repr(self.mip_data), ))
        print("image_data: len: %d" % (self.image_data and len(self.image_data) or 0, ))
        print("image_data: %s" % (repr(self.image_data[0:512]), ))
        print("image.format: %s" % (self.image.format, ))
        #print("image.compression: %s" % (self.image.compression, ))
        image_raw = self.image.make_blob(format = "RGBA")
        alpha_raw = image_raw[3::4]
        #print("image.blob: %s" % (image_raw, ))
        #print("image.blob.alpha: %s" % (alpha_raw, ))
        #print("image.channels: %s" % (self.image.channels, ))

if __name__ == "__main__":
    if len(sys.argv) <= 1 or len(sys.argv) > 3:
        print("Usage:")
        print("   %s <file_in> [<file_out>]" % (sys.argv[0], ))
        print("Test loads a .texture file, dumps its content, and optionally writes its content out.")
        exit(0)
    fh = open(sys.argv[1], "rb")
    texture = Texture()
    texture.loadFromFile(fh)
    fh.close()
    #print(sys.argv)
    if len(sys.argv) <= 2:
        fho = None
    else:
        fho = open(sys.argv[2], "wb")
    if fho is not None:
        data = texture.saveToData()
        #texture.dump()
        fho.write(data)
    else:
        texture.dump()
    #print("%s" % [texture.header_data])

