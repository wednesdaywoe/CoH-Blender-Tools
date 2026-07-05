#! /usr/bin/python3

import sys
import re
from geo import Geo

show_triangles = False
show_scales = False

def listGeo(fn, fh):
    geo = Geo()
    geo.loadFromFile(fh)
    for m in geo.models:
        s = "%s : %s" % (geo.header_modelheader_name.decode("utf-8"), m.name.decode("utf-8"))
        if show_triangles:
            s += " : %d" % (m.tris and len(m.tris) or 0, )
        if show_scales:
            s += " : %f, %f, %f" % tuple(m.scale)
        print(s)

def parseOption(opt):
    global show_triangles
    global show_scales
    for c in opt[1:]:
        if c == "t":
            show_triangles = True
        elif c == "s":
            show_scales = True


if len(sys.argv) <= 1:
    print("Usage:")
    print("    %s [<options>] <infile.geo>" % (sys.argv[0], ))
    print("Options:")
    print("    -t Display triangle count.")
    print("    -s Display model scale.")
    exit()


for i in range(1, len(sys.argv)):
    if sys.argv[i].startswith("-"):
        parseOption(sys.argv[i])
        continue
    try:
        fn = sys.argv[i]
        fh = open(fn, "rb")
    except:
        print("Couldn't open '%s'." % (sys.argv[i], ))
        continue
    listGeo(fn, fh)
