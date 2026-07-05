from .geo import Geo
from .geomesh import *
from .bones import *
import bpy.path
import bpy
import mathutils

from bpy_extras.io_utils import axis_conversion

def convert_mesh(geo_model, mesh, obj):
    if bpy.app.version < (2, 80):
        # Be sure tessface & co are available!
        if not mesh.tessfaces and mesh.polygons:
            mesh.calc_tessface()
    else:
        # Be sure tessellated loop trianlges are available!
        if not mesh.loop_triangles and mesh.polygons:
            mesh.calc_loop_triangles()

    mesh_verts = mesh.vertices  # save a lookup

    if bpy.app.version < (2, 80):
        has_uv = bool(mesh.tessface_uv_textures)
        if has_uv:
            active_uv_layer = mesh.tessface_uv_textures.active
            if not active_uv_layer:
                has_uv = False
            else:
                active_uv_layer = active_uv_layer.data
    else:
        has_uv = bool(mesh.uv_layers)
        if has_uv:
            active_uv_layer = mesh.uv_layers.active
            if not active_uv_layer:
                has_uv = False
            else:
                active_uv_layer = active_uv_layer.data

    geomesh = GeoMesh()

    texture_name = "white.tga"
    if bpy.app.version < (2, 80):
        faces = mesh.tessfaces
        print("len(mesh.tessfaces): %s" % len(faces))
        print("mesh.tessfaces: %s" % repr(faces))
    else:
        faces = mesh.loop_triangles
    for i, f in enumerate(faces):
        if has_uv:
            uv = active_uv_layer[i]
            if bpy.app.version < (2, 80):
                texture_image = uv.image
                if texture_image is None:
                    texture_name = "white.tga"
                else:
                    texture_name = texture_image.name
                    if texture_name == "":
                        texture_name = bpy.path.display_name_from_filepath(texture_image.filepath)
                    if texture_name == "":
                        texture_name = "white.tga"
            else:
                mat = mesh.materials[f.material_index]
                if len(mat.texture_paint_images) <= 0:
                    texture_name = mat.name
                else:
                    texture_image = mat.texture_paint_images[0]
                    texture_name = texture_image.name
                    if texture_name == "":
                        texture_name = bpy.path.display_name_from_filepath(texture_image.filepath)
                    if texture_name == "":
                        texture_name = "white.tga"
            if bpy.app.version < (2, 80):
                uv = [uv.uv1, uv.uv2, uv.uv3, uv.uv4]
            else:
                print("uv.uv: %s" % uv.uv)
                uv = [active_uv_layer[l].uv[:] for l in f.loops]
        else:
            uv = [(0, 0)] * 4
            texture_name = "white.tga"
        f_verts = f.vertices
        verts = []
        norms = []
        groups = []
        geoverts = []
        for i, v_index in enumerate(f_verts):
            v = mesh_verts[v_index]
            verts.append(v.co)
            norms.append(v.normal)
            weights = []
            for weight in v.groups:
                group = obj.vertex_groups[weight.group]
                w = [group.name, weight.weight]
                weights.append(w)
            print("i: %s   f_verts: %s   uv: %s" % (i, repr(f_verts), repr(uv)))
            gv = GeoVertex(v.co, -v.normal, uv[i], weights)
            geoverts.append(gv)
        geoverts.reverse()
        geomesh.addFace(geoverts, texture_name)

        print("face: vertices: %s  uvs: %s norms: %s groups: %s" % (verts, uv, norms, weights))
    #todo: optimize face order for bone association
    geomesh.dump()
    geo_model.loadFromGeoMesh(geomesh)
    pass

def save(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True):
    print("export_geo.save(): %s" % (filepath, ))

    geo = Geo()
    geo.getTextureIndex("white.tga")
    #geo.getTextureIndex("white")

    body_name = bpy.path.display_name_from_filepath(filepath)
    geo.setName(body_name)

    #print("AXIS_ROTATION")
    #axis_rotation = axis_conversion('-Y', 'Z', 'Z', 'Y')
    #print("%s" % (axis_rotation, ))
    #print("AXIS_ROTATION")
    #axis_rotation = axis_conversion('Y', 'Z', '-Z', 'Y')
    #print("%s" % (axis_rotation, ))
    #print("AXIS_ROTATION")
    axis_rotation = mathutils.Matrix([
        [-1, 0, 0],
        [0, 0, 1],
        [0, -1, 0],
    ])
    #print("%s" % (axis_rotation, ))
    #print("AXIS_ROTATION")
    axis_rotation.resize_4x4()

    print("scale: %s" % (scale, ))
    for ob in context.selected_objects:
        print("Object: %s (%s)" % (ob.name, ob.type))
        if ob.type != "MESH":
            continue
        ob.update_from_editmode()

        if global_matrix is None:
            from mathutils import Matrix
            global_matrix = Matrix()

        # get the modifiers
        if bpy.app.version < (2, 80):
            mesh = ob.to_mesh(bpy.context.scene, use_mesh_modifiers, "PREVIEW")
        else:
            mesh = ob.to_mesh(preserve_all_data_layers = True)

        #translate_matrix = Matrix.Translation(-ob.location)
        translate_matrix = Matrix()
        #scale_matrix = Matrix.Scale(1 / 0.30480000376701355, 4)
        obj_matrix = ob.matrix_world
        print(obj_matrix)
        obj_scale = obj_matrix.to_scale()[0] #assume scaling is uniform on all axis
        print("obj_scale: %s   final_scale: %s" % (obj_scale, obj_scale * scale))
        print(obj_scale * scale)
        scale_matrix = Matrix.Scale(obj_scale * scale, 4)
        if bpy.app.version < (2, 80):
            mesh.transform(global_matrix * scale_matrix * translate_matrix * axis_rotation)
        else:
            mesh.transform(global_matrix @ scale_matrix @ translate_matrix @ axis_rotation)

        mesh.calc_normals()

        geo_model = geo.addModel(ob.name)

        convert_mesh(geo_model, mesh, ob)

    if False: #flip bones
        for i in range(len(geo.models) - 1, -1, -1):
            name = geo.models[i].name.decode("utf-8")
            #if reg_exp.search(name) is not None:
            if True:
                print("Swapping left and right in: %s" % (name, ))
                model = geo.models[i]
                for j in range(len(model.weight_bones)):
                    for k in range(len(model.weight_bones[j])):
                        model.weight_bones[j][k] = BONES_SWAP[model.weight_bones[j][k]]

    data = geo.saveToData()
    fh = open(filepath, "wb")
    fh.write(data)
    fh.close()

    return {'FINISHED'}
