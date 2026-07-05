import bpy.path
import bpy

try:
    from .export_anim import *
except:
    from export_anim import *



def save_skel(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True):
    return save(operator, context, scale = scale, filepath = filepath, global_matrix = global_matrix, use_mesh_modifiers = use_mesh_modifiers, save_skeleton = True)
