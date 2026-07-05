from .geo import Geo
from .geomesh import *
from .bones import *
import bpy.path
import bpy
import mathutils

def import_scale_coord(v, scale):
    return (v[0] * scale, v[1] * scale, v[2] * scale)
if 0:
    def import_fix_coord(v):
        return (v[0], v[2], -v[1])
    def import_fix_normal(v):
        return (-v[0], -v[2], v[1])
    def import_fix_winding(l):
        l = list(l)
        l.reverse()
        return l
else:
    def import_fix_coord(v):
        return (-v[0],  -v[2], v[1])
    def import_fix_normal(v):
        return ( v[0], v[2],  -v[1])
    def import_fix_winding(l):
        l = list(l)
        l.reverse()
        return l

def extractRootBoneFromName(name):
    if name.startswith("GEO_"):
        name = name[4:]
    if name.startswith("N_"):
        name = name[2:]
    bone = name.split("_")[0]
    if bone in BONES_LOOKUP:
        return bone
    else:
        return None

def convert_model(geo_model, mesh_data, obj, scale):
    #Convert the geo_model into a GeoMesh.
    geomesh = geo_model.saveToGeoMesh()

    indices = [i for face in geomesh.face for i in import_fix_winding(face.vert_indexes)]
    texture_indices = [face.texture_index for face in geomesh.face]

    #Create materials for textures.
    mesh_data.materials.clear()
    #print("geomesh.textures: %s" % (geomesh.textures,))
    for i, tex_name in enumerate(geomesh.textures):
        #if isinstance(tex_name, int):
        #    continue
        #print("tex_name: %s" % tex_name)
        mesh_data.materials.append(bpy.data.materials.new(tex_name.decode("utf-8")))

    mesh_data.vertices.add(len(geomesh.geovertex))
    mesh_data.loops.add(len(indices))
    mesh_data.polygons.add(len(geomesh.face))

    coords = [c for v in geomesh.geovertex for c in import_scale_coord(import_fix_coord(v.coord), scale)]
    normals = [n for v in geomesh.geovertex for n in import_fix_normal(v.normal)]
    #print("normals: %s" % (normals, ))
    loop_totals = []
    loop_starts = []
    i = 0
    for f in geomesh.face:
        loop_totals.append(len(f.vert_indexes))
        loop_starts.append(i)
        i += loop_totals[-1]


    mesh_data.vertices.foreach_set("co", coords)
    mesh_data.vertices.foreach_set("normal", normals)
    mesh_data.loops.foreach_set("vertex_index", indices)
    mesh_data.polygons.foreach_set("loop_start", loop_starts)
    mesh_data.polygons.foreach_set("loop_total", loop_totals)
    mesh_data.polygons.foreach_set("material_index", texture_indices)
    #mesh_data.update()

    vgroup = {}
    for w_name in geomesh.weights:
        vgroup[w_name] = obj.vertex_groups.new(name=w_name)
    for i, v in enumerate(geomesh.geovertex):
        for w in v.weights:
            #print("vertex idx: %s  group: %s  weight: %s" % (i, w[0], w[1]))
            vgroup[w[0]].add([i], w[1], 'REPLACE')
    #for v in ob.vertices:
    #    weight_values.append( v.groups[o.vertex_groups[vg_name].index].weight )
    #???mesh_data.validate(False)

    d = mesh_data.uv_layers.new().data
    uvs = [c for f in geomesh.face for i in f.vert_indexes for c in geomesh.geovertex[i].uv]
    d.foreach_set('uv', uvs)



    mesh_data.validate()
    mesh_data.update()
    mesh_data.vertices.foreach_set("normal", normals)
    mesh_data.update()

    #todo: attempt to load textures/images

def getBonePositionBody(bone):
    #todo: fix this: Presently assumes that the head to tail will always be the same direction and length.
    if bone.parent is None:
        p = bone.head
        print("root: %s: %s (%s)" % (bone, p, bone.tail))
        return p
    else:
        p = bone.tail + getBonePositionBody(bone.parent)
        print("    : %s: %s (%s) -> %s" % (bone, bone.tail, bone.head, p))
        return p

def getBonePosition(arm, name):
    return getBonePositionBody(arm.bones[name])

def load(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True, ignore_lod = True):
    #load .geo
    fh_in = open(filepath, "rb")
    geo = Geo()
    geo.loadFromFile(fh_in)
    fh_in.close()
    #Choose the first selected armature as the armature to attach to.
    armature = None
    for ob in context.selected_objects:
        if ob.type == "ARMATURE":
            armature_obj = ob
            armature = ob.data
            break
    else:
        #If none found try again with all objects.
        for ob in bpy.data.objects:
            if ob.type == "ARMATURE":
                armature_obj = ob
                armature = ob.data
                break
    for geo_model in geo.models:
        model_name = geo_model.name.decode("utf-8")
        if ignore_lod:
            islod = False
            #todo: better LOD model detection
            for l in ["_LOD1", "_LOD2"]:
                if l in model_name:
                    islod = True
                    break
            if islod:
                continue
        #create object matching model's name (or next equivilant)
        mesh = bpy.data.meshes.new(name = model_name)
        obj = bpy.data.objects.new(model_name, mesh)
        #convert model to mesh
        convert_model(geo_model, mesh, obj, scale)
        #Create object for this mesh
        scn = bpy.context.scene

        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        #Try and attach it to the armature.
        if armature != None:
            bone_name = geo_model.getBoneRoot()
            if bone_name is None:
                #No bones, don't attach.
                pass
            else:
                preferred_bone_name = extractRootBoneFromName(model_name)
                arm_pos = armature_obj.matrix_world.translation
                if preferred_bone_name is not None:
                    bone_pos = getBonePosition(armature, preferred_bone_name)
                    obj.matrix_world = mathutils.Matrix.Translation(arm_pos + bone_pos)
                    obj.modifiers.new(name = 'Armature', type = 'ARMATURE')
                    obj.modifiers['Armature'].object = armature_obj
                elif bone_name in armature.bones:
                    bone_pos = getBonePosition(armature, bone_name)
                    obj.matrix_world = mathutils.Matrix.Translation(arm_pos + bone_pos)
                    obj.modifiers.new(name = 'Armature', type = 'ARMATURE')
                    obj.modifiers['Armature'].object = armature_obj
                else:
                    print("Bone '%s' not found in armature '%s', skipping." % (bone_name, armature))
        obj.select_set(True)
        pass
    pass
    return {'FINISHED'}
