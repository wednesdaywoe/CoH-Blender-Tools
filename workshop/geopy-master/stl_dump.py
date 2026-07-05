#! /usr/bin/python3

import struct
import geo
import sys
import os
import os.path

if len(sys.argv) < 2:
    print("Usage:")
    print("    %s <file.geo>")
    print("Dumps all the meshes contained in <file.geo> to <geo_name>/<model_name.stl>.")
    print("<geo_name> and <model_name> are read from the .geo.")

fh = open(sys.argv[1], "rb")
g = geo.Geo()
g.loadFromFile(fh)

geo_name = g.header_modelheader_name.decode("utf-8")
if not os.path.exists(geo_name):
    os.mkdir(geo_name)

for i in range(len(g.models)):
    model = g.models[i]
    model_name = model.name.decode("utf-8")
    filename = geo_name + "/" + model_name + ".stl"
    print(filename)
    ofh = open(filename, "wb")
    ofh.write(b"\x00" * 80)
    ofh.write(struct.pack("<i", model.tri_count))
    for i in range(model.tri_count):
        tri_index = model.tris[i]
        tri_verts = (model.verts[tri_index[0]],
             model.verts[tri_index[1]],
             model.verts[tri_index[2]])
        t = b""
        #print "%5d: %s" % (i, tri_verts)
        t += struct.pack("<fff", 0, 0, 0)
        for v in tri_verts:
            t += struct.pack("<fff", v[0], v[1], v[2])
        t += b"\x00\x00"
        ofh.write(t)
    ofh.close()

