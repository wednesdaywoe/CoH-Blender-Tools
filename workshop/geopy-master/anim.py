#! /usr/bin/python3
import sys

try:
    from .bones import *
    from .util import *
    from .geomesh import GeoMesh, GeoFace, GeoVertex
    from .compression_anim import *
except:
    from bones import *
    from util import *
    from geomesh import GeoMesh, GeoFace, GeoVertex
    from compression_anim import *


#.anim header
#Offset	Size	Description
#0	4	(int32) headerSize Size of this header plus BoneAnimTrack data and skeleton hierarchy data.
#4	256	(asciiz) name
#260	256	(asciiz) baseAnimName
#516	4	(float32) max_hip_displacement
#520	4	(float32) length
#524	4	(ptr u32) bone_tracks Offset to array of BoneAnimTrack structures.
#528	4	(int32) bone_track_count
#532	4	(int32) rotation_compression_type ??
#536	4	(int32) position_compression_type ??
#540	4	(ptr u32) skeletonHeirarchy ?? SkeletonHeirarchy
#Below are reserved for use by the game.
#544	4	(ptr u32) backupAnimTrack *SkeletonAnimTrack
#548	4	(int32) loadstate
#552	4	(float32) lasttimeused
#556	4	(int32) fileAge
#560	4*9	(int32[9]) spare_room
#596	-

#BoneAnimTrack
#0	4	(ptr u32) rot_idx ?? Offset to the rotation data. Format depends on compression method.
#4	4	(ptr u32) pos_idx ?? Offset to the position data. Format depends on compression method.
#8	2	(u16) rot_fullkeycount ??
#10	2	(u16) pos_fullkeycount ??
#12	2	(u16) rot_count ??
#14	2	(u16) pos_count ??
#16	1	(char) id Bone ID.
#17	1	(char) flags ??
#18	2	(u16) pack_pad  Padding to push the structure to 4 byte alignment.
#20	-

#SkeletonHeirarchy
#0	4	(int) heirarchy_root ?? First bone in the hierarchy.
#4	12*100	(BoneLink[BONES_ON_DISK])
#1204	-
#BONES_ON_DISK = 100

#BoneLink
#0	4	(int) child  ?? First child bone?
#4	4	(int) next ?? The next sibling bone?
#8	4	(int/BoneId) id The ID of this bone.
#12	-

ROTATION_UNCOMPRESSED = 1 << 0
ROTATION_COMPRESSED_TO_5_BYTES = 1 << 1
ROTATION_COMPRESSED_TO_8_BYTES = 1 << 2
POSITION_UNCOMPRESS = 1 << 3
POSITION_COMPRESSED_TO_6_BYTES = 1 << 4
ROTATION_DELTACODED = 1 << 5
POSITION_DELTACODED = 1 << 6
ROTATION_COMPRESSED_NONLINEAR = 1 << 7

ROTATION_MASK = ROTATION_UNCOMPRESSED | ROTATION_COMPRESSED_TO_5_BYTES | ROTATION_COMPRESSED_TO_8_BYTES | ROTATION_DELTACODED | ROTATION_COMPRESSED_NONLINEAR
POSITION_MASK = POSITION_UNCOMPRESS | POSITION_COMPRESSED_TO_6_BYTES | POSITION_DELTACODED


class BoneLink:
    def __init__(self, data_or_child = None, next = None, boneid = None):
        self.child = -1
        self.next = -1
        self.boneid = -1
        if data_or_child is None:
            return
        if next is None:
            (self.child, self.next, self.boneid) = data_or_child.decode("<iii")
            if self.child == 0 and self.next == 0 and self.boneid == 0:
                #All zero indicates an unused bone when written to disk.
                #Change it to all -1 make it clear it's unused.
                (self.child, self.next, self.boneid) = (-1, -1, -1)
        else:
            self.child = data_or_child
            self.next = next
            self.boneid = boneid
    def encode(self):
        if self.boneid == -1:
            return struct.pack("<iii", 0, 0, 0)
        return struct.pack("<iii", self.child, self.next, self.boneid)
    def dump(self):
        print("bone: %s (%s)" % (self.boneid, BONES_LIST[self.boneid]))
        print("  child: %s (%s)" % (self.child, BONES_LIST[self.child]))
        print("   next: %s (%s)" % (self.next, BONES_LIST[self.next]))

class SkeletonHierarchy:
    def __init__(self):
        self.root = -1
        self.bones = []
    def clear(self):
        self.root = -1
        self.bones = []
    def parseData(self, data, size = None):
        self.root = data.decode("<i")[0]
        self.bones = []
        if size is None:
            size = len(data)
        count = int(math.floor((size - 4) / 12.0))
        for i in range(count): #BONES_ON_DISK):
            self.bones.append(BoneLink(data))
    def encode(self):
        bone_max = len(self.bones)
        data = struct.pack("<i", self.root)
        blank_bone = BoneLink().encode()
        for bl in self.bones:
            if bl is None:
                data += blank_bone
            else:
                data += bl.encode()
        for i in range(bone_max, BONES_ON_DISK):
            data += blank_bone
        return data
    def initBones(self, bone_id):
        if bone_id == -1 or bone_id is None:
            return
        #Ensure the array is sized up to bone_id, and it's non-None.
        if len(self.bones) <= bone_id:
            #print("initBones(%s): %s: %s" % (bone_id, len(self.bones), self.bones,))
            self.bones += [None] * (bone_id - len(self.bones) + 1)
            #print("initBones(%s): %s: %s" % (bone_id, len(self.bones), self.bones,))
        if self.bones[bone_id] is None or self.bones[bone_id].boneid == -1:
            self.bones[bone_id] = BoneLink(-1, -1, bone_id)

    def addBone(self, parent_id, bone_id):
        self.initBones(bone_id)
        self.initBones(parent_id)
        if parent_id == -1 or parent_id is None:
            #New bone is a root bone.
            if self.root == -1:
                #It's the first root bone.
                self.root = bone_id
            else:
                #Find the last root bone, and add it to the end of the next chain.
                last_root_id = self.root
                while self.bones[last_root_id].next != -1:
                    last_root_id = self.bones[last_root_id].next
                self.bones[last_root_id].next = bone_id
        else:
            #New bone has a parent.
            if self.bones[parent_id].child != -1:
                #Parent already has children, add it to the end of the next chain.
                last_sibling_id = self.bones[parent_id].child
                while self.bones[last_sibling_id].next != -1:
                    last_sibling_id = self.bones[last_sibling_id].next
                self.bones[last_sibling_id].next = bone_id
            else:
                #It's the first child bone.
                self.bones[parent_id].child = bone_id
    def dump(self):
        print("SkeletonHierarchy: root: %s (%s) bones: %s" % (self.root, BONES_LIST[self.root], len(self.bones)))
        for i, b in enumerate(self.bones):
            if b is None:
                print("No bone: %s (%s)" % (i, BONES_LIST[i]))
            else:
                b.dump()

class BoneAnimTrack:
    def __init__(self, data = b"", srcdata = None):
        self.rawdata = data
        self.srcdata = srcdata
        self.rotations_data_offset = 0
        self.positions_data_offset = 0
        self.rotations = []
        self.positions = []
        self.rot_fullkeycount = 0
        self.pos_fullkeycount = 0
        self.rot_count = 0
        self.pos_count = 0
        self.bone_id = 0
        self.flags = 0
        self.padding = b""
        if len(data):
            self.parseData()
    def parseData(self):
        self.data = Data(self.rawdata)
        self.rotations_data_offset = self.data.decode("I")[0]
        self.positions_data_offset = self.data.decode("I")[0]
        self.rot_fullkeycount = self.data.decode("H")[0]
        self.pos_fullkeycount = self.data.decode("H")[0]
        self.rot_count = self.data.decode("H")[0]
        self.pos_count = self.data.decode("H")[0]
        self.bone_id = self.data.decode("B")[0]
        self.flags = self.data.decode("B")[0]
        self.padding = self.data.read(2)
        self.parseRotations()
        self.parsePositions()
    def parseRotations(self):
        self.rotations = []
        offset = self.srcdata.offset
        self.srcdata.seek(self.rotations_data_offset)
        method = self.flags & ROTATION_MASK
        if method == ROTATION_UNCOMPRESSED:
            for i in range(self.rot_count):
                self.rotations.append(self.srcdata.decode("<ffff"))
            pass
        elif method == ROTATION_COMPRESSED_TO_5_BYTES:
            for i in range(self.rot_count):
                self.rotations.append(decompressQuaternion_5Byte(self.srcdata.read(5)))
            pass
        elif method == ROTATION_COMPRESSED_TO_8_BYTES:
            for i in range(self.rot_count):
                self.rotations.append(decompressQuaternion_8Byte(self.srcdata.read(8)))
            pass
        elif method == ROTATION_DELTACODED:
            raise
            pass
        elif method == ROTATION_COMPRESSED_NONLINEAR:
            raise Exception("Unsupported rotation compression: ROTATION_COMPRESSED_NONLINEAR")
            pass
        else:
            #raise Exception("bone track rotation type 0x%2.2x unknown" % (self.flags, ))
            pass
        self.srcdata.seek(offset)
    def parsePositions(self):
        self.positions = []
        offset = self.srcdata.offset
        self.srcdata.seek(self.positions_data_offset)
        method = self.flags & POSITION_MASK
        if method == POSITION_UNCOMPRESS:
            for i in range(self.pos_count):
                self.positions.append(self.srcdata.decode("<fff"))
            pass
        elif method == POSITION_COMPRESSED_TO_6_BYTES:
            for i in range(self.pos_count):
                self.positions.append(decompressVector3_6Byte(self.srcdata.read(6)))
            pass
        elif method == POSITION_DELTACODED:
            raise
            pass
        else:
            #raise Exception("bone track position type 0x%2.2x unknown" % (self.flags, ))
            pass
        self.srcdata.seek(offset)
    def encode(self, out_offset, out_data):
        self.encodePositions()
        self.encodeRotations()
        self.data = Data()

        self.rotations_data_offset = len(out_data) + out_offset
        out_data.write(self.rotation_data)
        self.positions_data_offset = len(out_data) + out_offset
        out_data.write(self.position_data)

        self.rot_count = self.rot_fullkeycount = len(self.rotations)
        self.pos_count = self.pos_fullkeycount = len(self.positions)

        self.data.encode("<I", self.rotations_data_offset)
        self.data.encode("<I", self.positions_data_offset)
        self.data.encode("<H", self.rot_fullkeycount)
        self.data.encode("<H", self.pos_fullkeycount)
        self.data.encode("<H", self.rot_count)
        self.data.encode("<H", self.pos_count)
        self.data.encode("<BBBB", self.bone_id, self.flags, 0, 0)
        self.rawdata = self.data.data
        return self.rawdata

    def encodePositions(self):
        #Choose encoding.
        require_full = False
        for pos in self.positions:
            for v in pos:
                if abs(v) > 1.0:
                    require_full = True
        self.flags = self.flags & ~POSITION_MASK
        #Set flags and endode data
        self.position_data = b""
        if require_full:
            self.flags = self.flags | POSITION_UNCOMPRESS
            for pos in self.positions:
                self.position_data += struct.pack("<fff", pos[0], pos[1], pos[2])
        else:
            self.flags = self.flags | POSITION_COMPRESSED_TO_6_BYTES
            for pos in self.positions:
                self.position_data += compressVector3_6Byte(pos)
        pass

    def encodeRotations(self):
        #Choose encoding.
        require_full = False
        #for pos in self.positions:
        #    for v in pos:
        #        if abs(v) > 1.0:
        #            require_full = True
        self.flags = self.flags & ~ROTATION_MASK
        #Set flags and endode data
        self.rotation_data = b""
        if require_full:
            self.flags = self.flags | ROTATION_UNCOMPRESS
            for rot in self.rotattions:
                self.rotation_data += struct.pack("<ffff", rot[0], rot[1], rot[2], rot[3])
        else:
            self.flags = self.flags | ROTATION_COMPRESSED_TO_5_BYTES
            for rot in self.rotations:
                self.rotation_data += compressQuaternion_5Byte(rot)
        pass

    def dump(self):
        print("rotations_data_offset: %s" % (self.rotations_data_offset, ))
        print("positions_data_offset: %s" % (self.positions_data_offset, ))
        print("rot_fullkeycount: %s" % (self.rot_fullkeycount, ))
        print("pos_fullkeycount: %s" % (self.pos_fullkeycount, ))
        print("rot_count: %s" % (self.rot_count, ))
        print("pos_count: %s" % (self.pos_count, ))
        if self.bone_id > len(BONES_LIST):
            print("bone_id: %s (?)" % (self.bone_id, ))
        else:
            print("bone_id: %s %s" % (self.bone_id, BONES_LIST[self.bone_id]))
        print("flags: 0x%2.2x" % (self.flags, ))
        print("padding: %s" % (self.padding, ))
        print("rotations: %s" % (self.rotations, ))
        print("positions: %s" % (self.positions, ))


class Anim:
    def __init__(self):
        self.data = b""
        self.offset = 0
        self.version = -1

        self.header_size = -1
        self.header_name = ""
        self.header_base_anim_name = ""
        self.header_max_hip_displacement = 0
        self.header_length = 0
        self.header_bone_tracks_offset = 0
        self.header_bone_track_count = 0
        self.header_rotation_compression_type = 0
        self.header_position_compression_type = 0
        self.header_skeleton_hierarchy_offset = 0
        self.header_backup_anim_track = 0
        self.header_load_state = 0
        self.header_last_time_used = 0
        self.header_file_age = 0
        self.header_spare_room = b""

        self.bone_tracks = []
        self.skeleton_hierarchy = None

        pass
    def loadFromData(self, data):
        self.data = Data(data)
        self.offset = 0
        self.parseData()
        pass
    def loadFromFile(self, filein):
        self.data = Data(filein.read())
        self.offset = 0
        self.parseData()
        pass
    def saveToData(self):
        self.encode()
        return self.data.data
    def saveToFile(self, fileout):
        self.encode()
        fileout.write(self.data.data)
    def parseData(self):
        self.data.seek(0)
        self.header_size = self.data.decode("i")[0]
        self.header_name = extractString(self.data.read(256))
        self.header_base_anim_name = extractString(self.data.read(256))
        self.header_max_hip_displacement = self.data.decode("f")[0]
        self.header_length = self.data.decode("f")[0]
        self.header_bone_tracks_offset = self.data.decode("I")[0]
        self.header_bone_track_count = self.data.decode("i")[0]
        self.header_rotation_compression_type = self.data.decode("i")[0]
        self.header_position_compression_type = self.data.decode("i")[0]
        self.header_skeleton_hierarchy_offset = self.data.decode("I")[0]
        self.header_backup_anim_track = self.data.decode("I")[0]
        self.header_load_state = self.data.decode("i")[0]
        self.header_last_time_used = self.data.decode("f")[0]
        self.header_file_age = self.data.decode("f")[0]
        self.header_spare_room = self.data.read(4 * 9)

        self.bone_tracks = []
        if self.header_bone_tracks_offset > 0:
            self.data.seek(self.header_bone_tracks_offset)
            for i in range(self.header_bone_track_count):
                self.bone_tracks.append(BoneAnimTrack(self.data.read(20), self.data))
        self.skeleton_hierarchy = None
        if self.header_skeleton_hierarchy_offset > 0:
            self.data.seek(self.header_skeleton_hierarchy_offset)
            self.skeleton_hierarchy = SkeletonHierarchy()
            if self.header_skeleton_hierarchy_offset > self.header_bone_tracks_offset:
                skel_size = self.header_size - self.header_skeleton_hierarchy_offset
            else:
                skel_size = self.header_bone_tracks_offset - self.header_skeleton_hierarchy_offset
            self.skeleton_hierarchy.parseData(self.data, skel_size)
        pass
    def encode(self):
        if isinstance(self.header_name, str):
            self.header_name = bytes(self.header_name, "utf-8")
        if isinstance(self.header_base_anim_name, str):
            self.header_base_anim_name = bytes(self.header_base_anim_name, "utf-8")
        header_base_size = 596
        header_bone_tracks_size = 20 * len(self.bone_tracks)
        if self.skeleton_hierarchy is None:
            skel_data = b""
            header_skeleton_hierarhy_size = 0
        else:
            skel_data = self.skeleton_hierarchy.encode()
            header_skeleton_hierarhy_size = len(skel_data)
            #todo: verify all defined bones are present in the track data
        header_total_size = header_base_size + header_bone_tracks_size + header_skeleton_hierarhy_size
        header_bone_track_data = b""
        bone_track_data = Data()
        for bt in self.bone_tracks:
            header_bone_track_data += bt.encode(header_total_size, bone_track_data)
        if len(header_bone_track_data) != header_bone_tracks_size:
            #Verify the header is the right length.
            raise Exception("Internal error: Header bone tracks size mismatch! Got: %s  Expected: %s" % (len(header_bone_tracks), header_bone_tracks_size))

        self.header_size = header_total_size
        #self.header_max_hip_displacement = 0
        self.header_length = 0
        for bt in self.bone_tracks:
            self.header_length = max(self.header_length, len(bt.positions), len(bt.rotations))
        self.header_length = max(0, self.header_length - 1)
        self.header_bone_tracks_offset = header_base_size + header_skeleton_hierarhy_size
        self.header_bone_track_count = len(self.bone_tracks)
        self.header_rotation_compression_type = 0
        self.header_position_compression_type = 0
        if self.skeleton_hierarchy is None:
            self.header_skeleton_hierarchy_offset = 0
        else:
            self.header_skeleton_hierarchy_offset = header_base_size
        self
        header_data = (
            struct.pack("<i256s256sff",
                        header_total_size,
                        storeString(self.header_name, 256),
                        storeString(self.header_base_anim_name, 256),
                        self.header_max_hip_displacement,
                        self.header_length) +
            struct.pack("<IiiiI",
                        self.header_bone_tracks_offset,
                        self.header_bone_track_count,
                        self.header_rotation_compression_type,
                        self.header_position_compression_type,
                        self.header_skeleton_hierarchy_offset) +
            ZERO_BYTE * (4 * 13))
        #Verify header lengths
        if len(header_data) != header_base_size:
            raise Exception("Internal error: Header base size mismatch! Got: %s  Expected: %s" % (len(header_data), header_base_size))
        #todo: total header length

        rawdata = header_data + skel_data + header_bone_track_data + bone_track_data.data
        self.data = Data(rawdata)
        return rawdata


    def dump(self):
        print("header_size: %s" % (self.header_size, ))
        print("header_name: %s" % (self.header_name, ))
        print("header_base_anim_name: %s" % (self.header_base_anim_name, ))
        print("header_max_hip_displacement: %s" % (self.header_max_hip_displacement, ))
        print("header_length: %s" % (self.header_length, ))
        print("header_bone_tracks_offset: %s" % (self.header_bone_tracks_offset, ))
        print("header_bone_track_count: %s" % (self.header_bone_track_count, ))
        print("header_rotation_compression_type: %s" % (self.header_rotation_compression_type, ))
        print("header_position_compression_type: %s" % (self.header_position_compression_type, ))
        print("header_skeleton_hierarchy_offset: %s" % (self.header_skeleton_hierarchy_offset, ))
        print("header_backup_anim_track: %s" % (self.header_backup_anim_track, ))
        print("header_load_state: %s" % (self.header_load_state, ))
        print("header_last_time_used: %s" % (self.header_last_time_used, ))
        print("header_file_age: %s" % (self.header_file_age, ))
        print("header_spare_room: %s" % (self.header_spare_room, ))

        print("Bone Tracks:")
        for bt in self.bone_tracks:
            bt.dump()
        if self.skeleton_hierarchy is not None:
            self.skeleton_hierarchy.dump()
        pass

    def checkSkeletonHierarchy(self):
        if self.skeleton_hierarchy is None:
            return False
        return True
    def checkSkeletonBones(self):
        if self.skeleton_hierarchy is None:
            return False
        seen = []
        if self.checkSkeletonBonesBody(self.skeleton_hierarchy.root, seen):
            return True
        return False
    def checkSkeletonBonesBody(self, bone_id, seen):
        if bone_id == -1:
            return True
        if bone_id < -1:
            return False
        if bone_id in seen:
            return False
        seen.append(bone_id)
        bones = self.skeleton_hierarchy.bones
        if bone_id >= len(bones):
            return False
        if bones[bone_id].boneid != bone_id:
            return False
        if not self.checkSkeletonBonesBody(bones[bone_id].next, seen):
            return False
        if not self.checkSkeletonBonesBody(bones[bone_id].child, seen):
            return False
        return True
if __name__ == "__main__":
    if len(sys.argv) <= 1 or len(sys.argv) > 3:
        print("Usage:")
        print("   %s <file_in> [<file_out>]" % (sys.argv[0], ))
        print("Test loads a .anim file, dumps its content, and optionally writes its content out.")
        exit(0)
    fh = open(sys.argv[1], "rb")
    anim = Anim()
    anim.loadFromFile(fh)
    fh.close()
    #print(sys.argv)
    if len(sys.argv) <= 2:
        fho = None
    else:
        fho = open(sys.argv[2], "wb")
    if fho is not None:
        data = anim.saveToData()
        #anim.dump()
        fho.write(data)
    else:
        anim.dump()
    #print("%s" % [anim.header_data])

