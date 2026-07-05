import struct
import sys

ZERO_BYTE = struct.pack("B", 0)

if sys.version_info[0] < 3:
    byte = chr
    unbyte = ord
else:
    def byte(v):
        #return struct.pack("B", v)
        return bytes((v,))
    def unbyte(v):
        return v


class Data:
    def __init__(self, rawdata = b"", off = 0):
        self.data = rawdata
        self.offset = off
    def setData(self, rawdata, off = 0):
        self.data = rawdata
        self.offset = off
    def seek(self, off):
        self.offset = off
    def seekEnd(self, off = 0):
        self.offset = len(self.data) + off
    def seekRel(self, off = 0):
        self.offset += off
    def tell(self):
        return self.offset
    def decode(self, fmt):
        size = struct.calcsize(fmt)
        val = struct.unpack(fmt, self.data[self.offset : self.offset + size])
        self.offset += size
        return val
    def encode(self, fmt, *args):
        data = struct.pack(fmt, *args)
        self.write(data)
    def read(self, length):
        val = self.data[self.offset : self.offset + length]
        self.offset += length
        return val
    def write(self, data):
        #todo: handle
        if self.offset == len(self.data):
            self.data += data
            self.offset = len(self.data)
        elif self.offset > len(self.data):
            self.data += ZERO_BYTE * (self.offset - len(self.data))
            self.data += data
            self.offset = len(self.data)
        elif self.offset + len(data) >= len(self.data):
            self.data = self.data[0 : self.offset] + data
        else:
            self.data = self.data[0 : self.offset] + data + self.data [self.offset + len(data) : ]
    def truncate(self, offset = None):
        if offset is None:
            offset = self.offset
        self.data[0 : offset]
    def __len__(self):
        return len(self.data)
    def __str__(self):
        return str(self.data)
    def __repr__(self):
        return repr(self.data)

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
