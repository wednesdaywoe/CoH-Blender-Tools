import math
import struct

MAX_5_BYTE_QUATERNION = 1 / (2 ** 0.5)
SCALE_8_BYTE_QUATERNION_COMPRESS = 10000
SCALE_8_BYTE_QUATERNION_DECOMPRESS = 1.0 / SCALE_8_BYTE_QUATERNION_COMPRESS
SCALE_6_BYTE_VECTOR3_COMPRESS = 32000
SCALE_6_BYTE_VECTOR3_DECOMPRESS = 1.0 / SCALE_6_BYTE_VECTOR3_COMPRESS

def findBiggest(quat):
    biggest_i = -1
    biggest_v = 0
    for i, v in enumerate(quat):
        if abs(v) > biggest_v:
            biggest_v = abs(v)
            biggest_i = i
    if quat[biggest_i] < 0:
        return (biggest_i, (-quat[0], -quat[1], -quat[2], -quat[3]))
    else:
        return (biggest_i, ( quat[0],  quat[1],  quat[2],  quat[3]))

def compressQuaternion_5Byte(quat):
    #Find biggset value and negate the quaternion to make it positive.
    missing, q = findBiggest(quat)
    d = []
    for i in range(4):
        if i == missing:
            continue
        v = int(math.floor(0.5 + q[i] / MAX_5_BYTE_QUATERNION * 2048))
        if v < -2048:
            v = -2048
        elif v > 2047:
            v = 2047
        d.append(v + 2048)
    v = (
        (missing << 36) |
        (d[0] << 24) |
        (d[1] << 12) |
        d[2]
        )
    s = struct.pack("<Q", v)
    #Return with the top most byte first, but remaining bytes in little endian order.
    return s[4:5] + s[0:4]

def decompressQuaternion_5Byte(data):
    #Source data has the top most byte first, but remaining bytes are little endian.
    #print("decompressQuaternion_5Byte(data): %s" % ([data],))
    #Rearrange byte data into a little endian uint64.
    s = data[1:5] + data[0:1] + b"\x00\x00\x00"
    (v, ) = struct.unpack("<Q", s)

    #Parse out the data.
    missing = (v >> 36) & 0x3
    d = [
        (v >> 24) & 0xfff,
        (v >> 12) & 0xfff,
        v & 0xfff,
        ]

    #Rescale values and summing the squares into x.
    x = 0
    #print("%s" % (d, ))
    for i in range(3):
        d[i] = (d[i] - 2048) * MAX_5_BYTE_QUATERNION / 2048.0
        x += d[i] ** 2.0
    #print("%s -> %s" % (d, x))
    #Use pythagoras to compute the missing field into x.
    x = (1 - x) ** 0.5
    #Rebuild the quaternion.
    d_i = 0;
    q = []
    for i in range(4):
        if i == missing:
            q.append(x)
        else:
            q.append(d[d_i])
            d_i += 1
    return q

def compressQuaternion_8Byte(quat):
    return struct.pack("<hhhh",
                       int(math.floor(0.5 + quat[0] * SCALE_8_BYTE_QUATERNION_COMPRESS)),
                       int(math.floor(0.5 + quat[1] * SCALE_8_BYTE_QUATERNION_COMPRESS)),
                       int(math.floor(0.5 + quat[2] * SCALE_8_BYTE_QUATERNION_COMPRESS)),
                       int(math.floor(0.5 + quat[3] * SCALE_8_BYTE_QUATERNION_COMPRESS))
    )

def decompressQuaternion_8Byte(data):
    d = struct.unpack("<hhhh", data[0:8])
    return [
        d[0] * SCALE_8_BYTE_QUATERNION_DECOMPRESS,
        d[1] * SCALE_8_BYTE_QUATERNION_DECOMPRESS,
        d[2] * SCALE_8_BYTE_QUATERNION_DECOMPRESS,
        d[3] * SCALE_8_BYTE_QUATERNION_DECOMPRESS
    ]


def compressVector3_6Byte(vec):
    return struct.pack("<hhh",
                       int(math.floor(0.5 + vec[0] * SCALE_6_BYTE_VECTOR3_COMPRESS)),
                       int(math.floor(0.5 + vec[1] * SCALE_6_BYTE_VECTOR3_COMPRESS)),
                       int(math.floor(0.5 + vec[2] * SCALE_6_BYTE_VECTOR3_COMPRESS))
    )

def decompressVector3_6Byte(data):
    d = struct.unpack("<hhh", data[0:6])
    return [(x * SCALE_6_BYTE_VECTOR3_DECOMPRESS) for x in d]
