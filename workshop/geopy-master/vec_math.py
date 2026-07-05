import math


class Vector3:
    def __init__(self, *args):
        if len(args) == 0:
            self.data = [0, 0, 0]
            return
        if len(args) == 1:
            if type(args[0]) in (tuple , list):
                self.data = list(args[0])
            if isinstance(args[0], Vector3):
                self.data = list(args[0].data)
                return
        if len(args) == 3:
            self.data = list(args)
            return
        #todo: raise error
        pass
    def __getitem__(self, index):
        return self.data[index]
    def __setitem__(self, index, value):
        self.data[index] = value
    def __len__(self):
        return len(self.data)
    def __str__(self):
        return str(self.data)
    def __repr__(self):
        return "Vector3(%f, %f, %f)" % tuple(self.data)
    def __add__(self, other):
        return  Vector3(self[0] + other[0], self[1] + other[1], self[2] + other[2])
    def __sub__(self, other):
        return  Vector3(self[0] - other[0], self[1] - other[1], self[2] - other[2])
    def __mul__(self, other):
        return Vector3(self[0] * other, self[1] * other, self[2] * other)
    def __div__(self, other):
        return Vector3(self[0] / other, self[1] / other, self[2] / other)
    def __iadd__(self, other):
        self[0] += other[0]
        self[1] += other[1]
        self[2] += other[2]
        return self
    def __isub__(self, other):
        self[0] -= other[0]
        self[1] -= other[1]
        self[2] -= other[2]
        return self
    def __imul__(self, other):
        other = float(other)
        self[0] *= other
        self[1] *= other
        self[2] *= other
        return self
    def __idiv__(self, other):
        other = float(other)
        self[0] /= other
        self[1] /= other
        self[2] /= other
        return self
    def __neg__(self):
        return Vector3(-self[0], -self[1], -self[2])
    def __eq__(self, other):
        return self[0] == other[0] and self[1] == other[1] and self[2] == other[2]
    def __ne__(self, other):
        return self[0] != other[0] or self[1] != other[1] or self[2] != other[2]
    def mag(self):
        return (self.data[0] ** 2 + self.data[1] ** 2 + self.data[2] ** 2) ** 0.5
    def mag2(self):
        return (self.data[0] ** 2 + self.data[1] ** 2 + self.data[2] ** 2)
    def normalize(self):
        m = self.mag()
        if m == 0:
            return
        for i in range(3):
            self.data[i] /= m
    def dot(self, other):
        return self[0] * other[0] + self[1] * other[1] + self[2] * other[2]
    def cross(self, other):
        return Vector3(self[1] * other[2] - self[2] * other[1],
                       self[2] * other[0] - self[0] * other[2],
                       self[0] * other[1] - self[1] * other[0])

class Quaternion:
    #u, x, y, z
    def __init__(self, *args):
        if len(args) == 0:
            self.data = [1, 0, 0, 0]
        elif len(args) == 3:
            (roll, pitch, yaw) = tuple(args)
            sroll  = math.sin(roll)
            spitch = math.sin(pitch)
            syaw   = math.sin(yaw)
            croll  = math.cos(roll)
            cpitch = math.cos(pitch)
            cyaw   = math.cos(yaw)
            m = ( #create rotational Matrix
                (cyaw * cpitch, cyaw * spitch * sroll - syaw * croll, cyaw * spitch * croll + syaw * sroll),
                (syaw * cpitch, syaw * spitch * sroll + cyaw * croll, syaw * spitch * croll - cyaw * sroll),
                (      -spitch,                       cpitch * sroll,                       cpitch * croll)
            )
            _u = (sqrt(max(0.0, 1 + m[0][0] + m[1][1] + m[2][2])) / 2.0)
            _x = (sqrt(max(0.0, 1 + m[0][0] - m[1][1] - m[2][2])) / 2.0)
            _y = (sqrt(max(0.0, 1 - m[0][0] + m[1][1] - m[2][2])) / 2.0)
            _z = (sqrt(max(0.0, 1 - m[0][0] - m[1][1] + m[2][2])) / 2.0)
            self.data = (_u,
                         (m[2][1] - m[1][2]) >= 0 and abs(_x) or -abs(_x),
                         (m[0][2] - m[2][0]) >= 0 and abs(_y) or -abs(_y),
                         (m[1][0] - m[0][1]) >= 0 and abs(_z) or -abs(_z))
        elif len(args) == 4:
            self.data = list(args)
        else:
            #todo: raise error
            pass
    def __getitem__(self, index):
        return args[index]
    def __setitem__(self, index, value):
        self.data[index] = value
    def __len__(self):
        return len(self.data)
    def __str__(self):
        return str(self.data)
    def __repr__(self):
        return "Quaternion(%f, %f, %f, %f)" % tuple(self.data)
    def __mul__(self, other):
        if len(other) == 3:
            o = [0, other[0], other[1], other[2]]
        else:
            o = other
        return Quaternion(self[0] * o[0] - self[1]*o[1] - self[2]*o[2] - self[3]*o[3],
		          self[2] * o[3] - o[2]*self[3] + self[0]*o[1] + o[0]*self[1],
		          self[3] * o[1] - o[3]*self[1] + self[0]*o[2] + o[0]*self[2],
		          self[1] * o[2] - o[1]*self[2] + self[0]*o[3] + o[0]*self[3]);

    def rotate(self, vec):
        return self * vec * self.inv()
    def inv(self):
        return Quaternion(self[0], -self[1], -self[2], -self[3])
    def mag(self):
        return (self.data[0] ** 2 + self.data[1] ** 2 + self.data[2] ** 2 + self.data[3] ** 2) ** 0.5
    def mag2(self):
        return (self.data[0] ** 2 + self.data[1] ** 2 + self.data[2] ** 2 + self.data[3] ** 2)
    def normalize(self):
        m = self.mag()
        if m == 0:
            return
        for i in range(4):
            self.data[i] /= m


class Aabb:
    def __init__(self, mn = None, mx = None):
        if mn is None:
            self.min = Vector3(float('inf'), float('inf'), float('inf'))
            self.max = Vector3(-float('inf'), -float('inf'), -float('inf'))
        else:
            self.min = mn
            self.max = mx
    def __str__(self):
        return "%s" % str((self.min, self.max))
    def __repr__(self):
        return "Aabb(min: %s, max: %s)" % (repr(self.min), repr(self.max))
    def isEmpty(self):
        for i in range(3):
            if self.min[i] > self.max[i]:
                return True
        return False
    def expand(self, *args):
        for a in args:
            if type(a) is Aabb:
                self.expand(a.min)
                self.expand(a.max)
            else:
                for i in range(3):
                    if a[i] < self.min[i]:
                        self.min[i] = a[i]
                    if a[i] > self.max[i]:
                        self.max[i] = a[i]
    def clear(self):
        self.min = Vector3(float('inf'), float('inf'), float('inf'))
        self.max = Vector3(-float('inf'), -float('inf'), -float('inf'))
    def center(self):
        if self.isEmpty():
            return Vector3(0, 0, 0)
        return (self.min + self.max) * 0.5
    def size(self):
        if self.isEmpty():
            return Vector3(0, 0, 0)
        return (self.max - self.min)
    def test(self, other):
        if self.isEmpty():
            #Empty AABBs can't overlap anything.
            return False
        if isinstance(other, Aabb):
            if other.isEmpty():
                #Empty AABBs can't overlap anything.
                return False
            for i in range(3):
                if self.min[i] > other.max[i]:
                    return False
                if other.min[i] > self.max[i]:
                    return False
            return True
        else:
            for i in range(3):
                if other[i] < self.min[i] or other[i] > self.max[i]:
                    return False
            return True


class Triangle:
    def __init__(self, *args):
        if len(args) == 0:
            self.vertex = [Vector3(), Vector3(), Vector3()]
            #print(":::a:::%s" % (repr(self), ))
            return
        if len(args) == 1:
            if isinstance(args[0], Triangle):
                v = args[0].vertex
                self.vertex = [Vector3(v[0]), Vector3(v[1]), Vector3(v[2])]
                #print(":::b:::%s" % (repr(self), ))
                return
        if len(args) != 3:
            #todo: raise error
            pass
        self.vertex = list(args)
        #print(":::c:::%s" % (repr(self), ))
    def __str__(self):
        return str(self.vertex)
    def __repr__(self):
        return "Triangle(%s)" % repr(self.vertex)
    def translate(self, vec):
        for i in range(3):
            #print("%s: %s += %s" % (i, repr(self.vertex[i]), repr(vec)))
            self.vertex[i] += vec
    def rotate(self, quat):
        for i in range(3):
            self.vertex[i] = quat.rotate(self.vertex[i])
    def scale(self, *args):
        #print("Triangel.scale: self: %s  other: %s" % (repr(self), repr(args)))
        if len(args) == 1:
            if isinstance(args[0], Vector3):
                for i in range(3):
                    for j in range(3):
                        self.vertex[i][j] *= args[0][j]
            else:
                for i in range(3):
                    self.vertex[i] *= args[0]
        elif len(args) == 3:
            for i in range(3):
                for j in range(3):
                    self.vertex[i][j] *= args[j]
        else:
            #todo: raise error
            pass
    def testAabb(self, aabb):
        #Empty AABBs can't collide
        if aabb.isEmpty():
            return False
        #Easy test: Test if AABBs overlap, return false if they don't.
        for i in range(3):
            if self.vertex[0][i] < aabb.min[i] and self.vertex[1][i] < aabb.min[i] and self.vertex[2][i] < aabb.min[i]:
                return False
            if self.vertex[0][i] > aabb.max[i] and self.vertex[1][i] > aabb.max[i] and self.vertex[2][i] > aabb.min[i]:
                return False
        #Easy test: Test if points are inside the AABB, return true if they do.
        for i in range(3):
            if aabb.test(self.vertex[i]):
                return True
        #Copy triangle, to allow manipulation.
        t = Triangle(self)
        t.translate(-aabb.center())
        s = aabb.size()
        for i in range(3):
            s[i] = 1.0 / s[i]
        t.scale(s)
        return t.testCubeBody(0.5)
    def testCubeBody(self, halfwidth):
        def testPlaneInCube():
            vmin = Vector3()
            vmax = Vector3()
            for i in range(3):
                if normal[i] > 0:
                    vmin[i] = -halfwidth
                    vmax[i] = halfwidth
                else:
                    vmin[i] = halfwidth
                    vmax[i] = -halfwidth
            #print("vmin: %s, %s" % (repr(vmin), normal.dot(vmin)))
            #print("vmax: %s, %s" % (repr(vmax), normal.dot(vmax)))
            if dist < normal.dot(vmin):
                return False
            if dist <= normal.dot(vmax):
                return True
            return False
        def testAxis(vr, vs, ia, ib, a, b):
            fa = abs(a)
            fb = abs(b)
            pr = a * vr[ia] + b * vr[ib]
            ps = a * vs[ia] + b * vs[ib]
            if pr < ps:
                mn = pr
                mx = ps
            else:
                mn = ps
                mx = pr
            rad = (fa + fb) * halfwidth
            #print("fa: %s  fb: %s  pr: %s  ps: %s  mn: %s  mx: %s  rad: %s" % (fa, fb, pr, ps, mn, mx, rad))
            if mn > rad or mx < -rad:
                return False
            return True

        edge = [None, None, None]
        for i in range(3):
            edge[i] = self.vertex[(i + 1) % 3] - self.vertex[i]
        #print("edge: %s" % repr(edge))
        normal = edge[0].cross(edge[1])
        #print("normal (raw): %s" % repr(normal))
        normal.normalize()
        dist = normal.dot(self.vertex[0])
        #print("normal: %s  distance: %s" % (repr(normal), dist))
        #print("halfwidth: %s" % (halfwidth, ))
        #Test if the triangles plane intersects the cube.
        if not testPlaneInCube():
            return False
        v = self.vertex
        #print("vertex: %s" % (repr(v)))
        if not testAxis(v[0], v[2], 1, 2,  edge[0][2], -edge[0][1]): return False
        if not testAxis(v[0], v[2], 0, 2, -edge[0][2],  edge[0][0]): return False
        if not testAxis(v[1], v[2], 0, 1,  edge[0][1], -edge[0][0]): return False

        if not testAxis(v[0], v[2], 1, 2,  edge[1][2], -edge[1][1]): return False
        if not testAxis(v[0], v[2], 0, 2, -edge[1][2],  edge[1][0]): return False
        if not testAxis(v[0], v[1], 0, 1,  edge[1][1], -edge[1][0]): return False

        if not testAxis(v[0], v[1], 1, 2,  edge[2][2], -edge[2][1]): return False
        if not testAxis(v[0], v[1], 0, 2, -edge[2][2],  edge[2][0]): return False
        if not testAxis(v[1], v[2], 0, 1,  edge[2][1], -edge[2][0]): return False
        return True

if __name__ == "__main__":
    #todo: make these unit tests better
    #Unit test Vector3
    assert(Vector3() == [0, 0, 0])
    assert(Vector3(0, 0, 0) == Vector3())
    assert(Vector3(1, 1, 1) + Vector3(-1, -1, -1) == Vector3())
    assert(Vector3(1, 1, 1) - Vector3(1, 1, 1) == Vector3())
    assert(Vector3(2, 2, 2) * 0.5 == Vector3(1, 1, 1))
    assert(Vector3(2, 2, 2) / 2 == Vector3(1, 1, 1))
    assert(-Vector3(1, 1, 1) == Vector3(-1, -1, -1))
    assert(len(Vector3()) == 3)
    assert(Vector3(1, 1, 1).mag() == (3 ** 0.5))
    assert(Vector3(1, 1, 1).mag2() == 3)
    v = Vector3(0, 0, 10)
    v.normalize()
    assert(v == Vector3(0, 0, 1))
    assert(Vector3(1, 2, 3).dot(Vector3(3, 2, 1)) == 10)
    assert(Vector3(1, 0, 0).cross(Vector3(0, 1, 0)) == Vector3(0, 0, 1))
    assert(Vector3(0, 1, 0).cross(Vector3(0, 0, 1)) == Vector3(1, 0, 0))
    assert(Vector3(0, 1, 0).cross(Vector3(1, 0, 0)) == Vector3(0, 0, -1))
    #todo: unit test Quaternion

    #unit test Aabb
    assert(Aabb().isEmpty())
    assert(Aabb().min == Vector3(float("inf"), float("inf"), float("inf")))
    assert(Aabb().max == Vector3(-float("inf"), -float("inf"), -float("inf")))
    box = Aabb(Vector3(-1, -1, -1), Vector3(1, 1, 1))
    assert(box.min == Vector3(-1, -1, -1))
    assert(box.max == Vector3(1, 1, 1))
    box = Aabb()
    box.expand(Vector3(1, 0, -1), Vector3(-1, 1, 0), Vector3(0, -1, 1))
    assert(box.min == Vector3(-1, -1, -1))
    assert(box.max == Vector3(1, 1, 1))
    assert(box.size() == Vector3(2, 2, 2))
    assert(box.center() == Vector3())

    #unit test Triangle
    box = Aabb(Vector3(-2, -2, -2), Vector3(2, 2, 2))
    tri = Triangle(Vector3(3, 0, 0), Vector3(0, 3, 0), Vector3(0, 0, 3))
    assert(tri.testAabb(box))
    box = Aabb(Vector3(-1, -1, -1), Vector3(1, 1, 1))
    tri = Triangle(Vector3(4, 0, 0), Vector3(0, 4, 0), Vector3(0, 0, 4))
    assert(not tri.testAabb(box))

    pass
