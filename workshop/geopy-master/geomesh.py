import functools

def weight_cmp(a, b):
    return a[1] < b[1] or (a[1] == b[1] and a[0] < b[0])

def tuple_weights(weights):
    return tuple((tuple(w) for w in weights))

class GeoVertex:
    def __init__(self, coord, normal, uv, weights):
        self.coord = coord
        self.normal = normal
        self.uv = uv
        self.weights = tuple(weights)
    def __eq__(self, other):
        return self.coord == other.coord and self.normal == other.normal and self.uv == other.uv and self.weights == other.weights
    def __hash__(self):
        #print("__hash__: %s" % ((tuple(self.coord), tuple(self.normal), tuple(self.uv), tuple(self.weights)), ))
        #self.dump()
        return hash((tuple(self.coord), tuple(self.normal), tuple(self.uv), tuple_weights(self.weights)))
    def selectWeights(self, count = None):
        """Returns the list of weights attached to this vertex. List is sorted by weight, with the strongest first. If 'count' is given, only 'count' strongest are return. The final list is normalized so the sum is 1."""
        if len(self.weights) <= 0:
            return []
        weights = list(self.weights)
        #sort by weight
        weights.sort(key = functools.cmp_to_key(weight_cmp), reverse = True)
        if count is not None and len(weights) > count:
            weights = weights[0:count]
        nw = 0.0
        for w in weights:
            nw += w[1]
        if nw <= 0:
            for w in weights:
                w[1] = 0
            weights[0][1] = 1
        else:
            for w in weights:
                w[1] /= nw
        return weights
    def dump(self):
        print("        GeoVertex: coord: %s  normal: %s  uv: %s  weights: %s" % (self.coord, self.normal, self.uv, self.weights))
class GeoFace:
    def __init__(self, vert_indexes, texture_index):
        self.vert_indexes = vert_indexes
        self.texture_index = texture_index
    def __eq__(self, other):
        return self.vert_indexes == other.vert_indexes and self.texture_index == other.texture_index
    def dump(self):
        print("       GeoFace:  vertex indexes: %s  texture index: %s" % (self.vert_indexes, self.texture_index))
class GeoMesh:
    def __init__(self):
        self.geovertex = []
        self.geovertex_map = {}
        self.textures = []
        self.textures_map = {}
        self.weights = []
        self.weights_map = {}
        self.face = []
        self.have_weights = False
        self.have_uvs = True
    def getGeoVertexIndexNew(self, gv):
        index = self.geovertex_map.get(gv, len(self.geovertex))
        if index == len(self.geovertex):
            self.geovertex_map[gv] = index
        index = len(self.geovertex)
        self.geovertex.append(gv)
        return index
    def getGeoVertexIndex(self, gv):
        index = self.geovertex_map.get(gv, len(self.geovertex))
        if index == len(self.geovertex):
            self.geovertex_map[gv] = index
            self.geovertex.append(gv)
        return index
    def getTextureIndex(self, name):
        if isinstance(name, int):
            #Convenience, assume ints are from a previous look up.
            return name
        index = self.textures_map.get(name, len(self.textures))
        #print("GeoMesh.getTextureIndex(%s): %s" % (name, index))
        if index == len(self.textures):
            self.textures_map[name] = index
            self.textures.append(name)
        return index
    def getWeightIndex(self, name):
        index = self.weights_map.get(name, len(self.weights))
        if index == len(self.weights):
            self.weights_map[name] = index
            self.weights.append(name)
        return index
    def rebuildWeightsList(self):
        self.weights_map = {}
        self.weights = []
        for v in self.geovertex:
            for w in v.weights:
                if w[0] in self.weights_map:
                    continue
                self.weights_map[w[0]] = len(self.weights)
                self.weights.append(w[0])

    def addFace(self, geovertices, texture_name):
        l = len(geovertices)
        if l > 3:
            #Do a naive conversion to a triangle fan, add each of those triangles as a face. Will give bad results in shape is not convex.
            #Choose the start point as the one closest to the origin. Ties are resolved by lexical comparison of the coordinates.
            start = 0
            start_dist = geovertices[0].coord.magnitude
            for i in range(1, len(geovertices)):
                dist = geovertices[i].coord.magnitude
                if dist < start_dist:
                    start = i
                    start_dist = dist
                elif dist == start_dist:
                    for j in range(3):
                        if geovertices[i].coord[j] < geovertices[start].coord[j]:
                            start = i
                            start_dist = dist
                            break
            for i in range(2, len(geovertices)):
                i1 = (start + i - 1) % l
                i2 = (start + i) % l
                self.addFace([geovertices[start], geovertices[i1], geovertices[i2]], texture_name)
            return
        elif l < 3:
            return
        for i in range(3):
            for w in geovertices[i].weights:
            #    w_index = self.getWeightIndex(w[0])
                self.have_weights = True
        geovertices_index = [self.getGeoVertexIndex(geovertices[0]),
                             self.getGeoVertexIndex(geovertices[1]),
                             self.getGeoVertexIndex(geovertices[2])]
        self.face.append(GeoFace(geovertices_index, self.getTextureIndex(texture_name)))
        pass
    def sortFaces(self):
        #Sort faces so they're grouped by texture index.
        #todo:
        pass

    def dump(self):
        print("GeoMesh:")
        print("    Textures: %s" % (self.textures, ))
        print("    Weights: %s" % (self.weights, ))
        print("    Vertices:")
        for i, v in enumerate(self.geovertex):
            v.dump()
        print("    Faces:")
        for i, f in enumerate(self.face):
            f.dump()
