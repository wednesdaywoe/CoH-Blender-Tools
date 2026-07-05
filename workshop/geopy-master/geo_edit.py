#! /usr/bin/python3

import sys
import re
from geo import Geo
try:
    from .bones import *
except:
    from bones import *




if len(sys.argv) < 4:
    print("Usage:")
    print("    %s <infile.geo> <outfile.geo> <operation> [<operation options> ...]" % (sys.argv[0], ))
    print("Operations:")
    print("    del_model <reg_ex_filter>    Delete models with the name matching regular expression.")
    print("    geo_name <geo_name>          Rename the name of the .geo .")
    print("    swap_left_right <reg_ex>     Swap left and right bones for all models matching the regular expression.")
    print("    rename_model <old> <new>     Rename model <old> to <new>.")
    print("    rename_texture <old> <new>   Rename texture <old> to <new>.")
    print("    rescale_all <scale>          Rescale all models by the given amount.")
    print("    set_model_scale <model> <x> <y> <z> Set scale property of <model> to <x> <y> <z>.")
    exit()

fn_in = sys.argv[1]
fn_out = sys.argv[2]
#if fn_in == fn_out:
#    print("Input and output filenames are identical. Refusing to run, to avoid accidental lose.")
#    exit()

print("Reading '%s'..." % (fn_in, ))
fh_in = open(fn_in, "rb")
geo = Geo()
geo.loadFromFile(fh_in)
fh_in.close()
print("Done.")
print()

arg_i = 3
while arg_i < len(sys.argv):
    operation = sys.argv[arg_i]
    arg_i += 1
    if operation == "del_model":
        reg_exp_str = sys.argv[arg_i]
        arg_i += 1
        reg_exp = re.compile(reg_exp_str)
        for i in range(len(geo.models) - 1, -1, -1):
            name = geo.models[i].name.decode("utf-8")
            if reg_exp.search(name) is not None:
                print("Remove: %s" % (name, ))
                del geo.models[i]
            else:
                print("Keep  : %s" % (name, ))
    elif operation == "geo_name":
        name = sys.argv[arg_i]
        arg_i += 1
        print("Rename GEO from '%s' to '%s'" % (geo.header_modelheader_name.decode("utf-8"), name))
        geo.header_modelheader_name = bytes(name, "utf-8")
    elif operation == "rename_model":
        nameold = bytes(sys.argv[arg_i], "utf-8")
        namenew = bytes(sys.argv[arg_i+1], "utf-8")
        arg_i += 2
        renamed = 0
        for m in geo.models:
            if m.name == nameold:
                m.name = namenew
                print("Renamed model '%s' to '%s'" % (nameold.decode("utf-8"), namenew.decode("utf-8")))
                renamed +=1
                break
        if renamed <= 0:
            print("   **Warning!*** Rename failed, no model name matched '%s'." % (nameold.decode("utf-8"), ))
    elif operation == "rename_texture":
        nameold = bytes(sys.argv[arg_i], "utf-8")
        namenew = bytes(sys.argv[arg_i+1], "utf-8")
        arg_i += 2
        renamed = 0
        for i, t in enumerate(geo.header_texnames):
            if t == nameold:
                geo.header_texnames[i] = namenew
                print("Renamed texture '%s' to '%s'" % (nameold.decode("utf-8"), namenew.decode("utf-8")))
                renamed += 1
                break
        if renamed <= 0:
            print("   **Warning!*** Rename failed, no texture name matched '%s'." % (nameold.decode("utf-8"), ))
    elif operation == "rescale_all":
        scale = float(sys.argv[arg_i])
        arg_i += 1
        for m in geo.models:
            for i in range(len(m.verts)):
                for j in range(3):
                    m.verts[i][j] *= scale
    elif operation == "set_model_scale":
        name = bytes(sys.argv[arg_i], "utf-8")
        scale = sys.argv[arg_i + 1 : arg_i + 4]
        for i in range(3):
            scale[i] = float(scale[i])
        arg_i += 4
        found = 0
        for m in geo.models:
            if m.name == name:
                found += 1
                print("Changed scale of '%s' from %s to %s" % (name.decode("utf-8"), m.scale, scale))
                m.scale = scale
                break
        if found <= 0:
            print("   **Warning!*** Set model scale failed, no model named '%s'." % (nameold.decode("utf-8"), ))
    elif operation == "swap_left_right":
        reg_exp_str = sys.argv[arg_i]
        arg_i += 1
        reg_exp = re.compile(reg_exp_str)
        for i in range(len(geo.models) - 1, -1, -1):
            name = geo.models[i].name.decode("utf-8")
            if reg_exp.search(name) is not None:
                print("Swapping left and right in: %s" % (name, ))
                model = geo.models[i]
                for j in range(len(model.weight_bones)):
                    for k in range(len(model.weight_bones[j])):
                        model.weight_bones[j][k] = BONES_SWAP[model.weight_bones[j][k]]
    else:
        print("Unknown operation: '%s'" % (operation, ))
        exit()

print()
print("Writing '%s'..." % (fn_out, ))
data = geo.saveToData()
fh_out = open(fn_out, "wb")
fh_out.write(data)
fh_out.close()
print("Done.")
