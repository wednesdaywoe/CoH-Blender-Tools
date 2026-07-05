
import math
import struct
try:
    from .vec_math import Vector3, Quaternion, Aabb, Triangle
    from .util import Data
except:
    from vec_math import Vector3, Quaternion, Aabb, Triangle
    from util import Data

#PolyGrid is an octree where the leaf nodes contain a list of all triangles that intersect that leaf node.
#Each node on a PolyGrid is a PolyCell.


#POLYGRID_EPSILON exapnds the cube of a PolyCell for purposes of finding a triangle collision.
POLYGRID_EPSILON_MAX = 0.1 #Amount to expand the max corner of the AABB.
POLYGRID_EPSILON_MIN = 0.0 #Amount to expand the min corner of the AABB.
POLYGRID_MINIMUM_SIZE = 1


class PolyCell:
    def __init__(self):
        self.children = None
        self.tri_idxs = []
        self.tri_count = 0
        self.position = [0, 0, 0]
        self.width = 0
    def decode(self, data, offset):
        (children_offset, tri_idxs_offset, self.tri_count) = struct.unpack("<iii", data[offset : offset + 12])
        if children_offset == 0:
            self.children = None
        else:
            self.children = [None] * 8
            children_offsets = struct.unpack("<iiiiiiii", data[children_offset : children_offset + 4 * 8])
            for i in range(8):
                if children_offsets[i] == 0:
                    continue
                self.children[i] = PolyCell()
                self.children[i].decode(data, children_offsets[i])
        if tri_idxs_offset == 0:
            self.tri_idxs = []
        else:
            self.tri_idxs = struct.unpack("<" + "H" * self.tri_count, data[tri_idxs_offset : tri_idxs_offset + self.tri_count * 2])

    def rebuild(self, min_width, triangles, pos, width):
        #triangles is a list of tuples (index, Triangle)
        self.width = width
        self.position = pos
        halfwidth = width * 0.5
        self.tri_idxs = []
        self.tri_count = 0
        #Create AABB for this cell, including epsilon margin.
        aabb = Aabb(pos, Vector3(width, width, width) + pos)
        aabb.min -= Vector3(POLYGRID_EPSILON_MIN, POLYGRID_EPSILON_MIN, POLYGRID_EPSILON_MIN)
        aabb.max += Vector3(POLYGRID_EPSILON_MAX, POLYGRID_EPSILON_MAX, POLYGRID_EPSILON_MAX)
        #Filter triangles to only those matching
        tris = []
        for t in triangles:
            if t[1].testAabb(aabb):
                tris.append(t)
        #Return false if this node is empty.
        if len(tris) == 0:
            return False
        #
        if (width <= min_width and len(tris) < 9) or width <= 4:
            #This cell is a leaf node. Populate triangle index list and return True.
            for t in tris:
                self.tri_idxs.append(t[0])
            self.tri_count = len(self.tri_idxs)
            return True
        self.children = [None] * 8
        #Populate branches
        for i in range(8):
            x = (0, halfwidth)[i & 0x1]
            y = (0, halfwidth)[(i >> 1) & 0x1]
            z = (0, halfwidth)[(i >> 2) & 0x1]
            p = pos + Vector3(x, y, z)
            cell = PolyCell()
            if cell.rebuild(min_width, tris, p, halfwidth):
                #Child cell has triangles store in its branch, store it.
                self.children[i] = cell
        return True
    def encode(self, data):
        data.seekEnd()
        offset = data.tell()
        o = offset + 12
        if len(self.tri_idxs) > 0:
            to = o
            o += len(self.tri_idxs) * struct.calcsize("<H")
        else:
            to = 0
        if self.children is not None:
            co = o
            cosz = struct.calcsize("<iiiiiiii")
            o += cosz
        else:
            co = 0
        data.encode("<iii", co, to, len(self.tri_idxs))
        if len(self.tri_idxs) > 0:
            data.encode("<" + "H" * len(self.tri_idxs), *self.tri_idxs)
        if self.children is not None:
            data.encode("<iiiiiiii", 0, 0, 0, 0, 0, 0, 0, 0)
            child_offsets = [0] * 8
            for i in range(8):
                if self.children[i] is not None:
                    child_offsets[i] = self.children[i].encode(data)
            data.seek(co)
            data.write(struct.pack("<iiiiiiii", *child_offsets))
        return offset
    def clear(self):
        if self.children is not None:
            for c in self.children:
                if c is not None:
                    c.clear()
            self.children = None
        self.tri_idxs = []
        self.tri_count = 0
    def collectTris(self, used_tris):
        if self.children is not None:
            for c in self.children:
                if c is not None:
                    c.collectTris(used_tris)
        for idx in self.tri_idxs:
            used_tris[idx] += 1
    def countCells(self):
        pass
    def dump(self, indent):
        print(indent + "position: %s  width: %s" % (repr(self.position), self.width))
        print(indent + "tri_idxs: %s" % ([self.tri_idxs], ))
        print(indent + "children? %s" % (self.children is not None, ))
        if self.children is not None:
            for c in self.children:
                if c is not None:
                    c.dump(indent + "    ")
                else:
                    print(indent + "    " + "-")


class PolyGrid:
    def __init__(self, model):
        self.model = model
        self.cell = None
        self.position = [0, 0, 0]
        self.width = 1.0
        self.bits = 0
        self.aabb = Aabb()
        self.radius = 0
        pass
    def parsePolyGridData(self, data, grid_header):
        self.cell = PolyCell()
        self.cell.decode(data, 0)
        self.grid_header = grid_header
        self.position = grid_header[1:4]
        self.width = grid_header[4]
        self.bits = grid_header[7]
        pass
    def clearTree(self):
        self.cell.clear()
        self.cell = None
    def rebuild(self):
        #Extract vertices and bounding box of the Model.
        aabb = Aabb()
        verts = []
        for v in self.model.verts:
            verts.append(Vector3(*v))
            aabb.expand(verts[-1])
        tris = []
        #Extract triangles from the Model.
        for i in range(len(self.model.tris)):
            t = self.model.tris[i]
            tri = Triangle(verts[t[0]], verts[t[1]], verts[t[2]])
            tris.append((i, tri))
        #Compute the position and width of this bounding box.
        self.position = aabb.min
        sz = aabb.size()
        radius = sz.mag() * 0.5
        self.aabb = aabb
        self.radius = radius
        if radius > 2000:
            min_width = 1024
        elif radius > 1000:
            min_width = 256
        elif radius > 500:
            min_width = 128
        else:
            min_width = 64
        self.width = max(sz[0], sz[1], sz[2])
        self.width = 2.0 ** math.ceil(math.log(self.width, 2.0))
        self.width = max(1.0, self.width)
        self.bits = int(math.floor(math.log(self.width, 2) + 0.5))

        self.cell = PolyCell()
        self.cell.rebuild(min_width, tris, self.position, self.width)

        if not self.check():
            print(self.model.name)
            print(repr(tris))
            self.dump()
    def encode(self):
        #Reconstruct the cell tree.
        self.rebuild()
        assert(self.check())
        #Encode data
        self.data = Data()
        o = self.cell.encode(self.data)
        self.grid_header = (0, self.position[0], self.position[1], self.position[2], self.width, 1.0 / self.width, 0, self.bits)
        return self.data.data
    def check(self):
        """Checks that all triangles in the model are in at least of the nodes of the tree."""
        used_tris = [0] * len(self.model.tris)
        self.cell.collectTris(used_tris)
        for v in used_tris:
            if v <= 0:
                print(repr(used_tris))
                return False
        return True
    def dump(self, indent = "    "):
        print(indent + "position: %s   width: %s" % (self.position, self.width))
        if self.cell is not None:
            self.cell.dump(indent + "    ")
