import bpy.path
import bpy
from mathutils import Vector, Quaternion
try:
    from .anim import *
    from .bones import *
    from .import_anim import convertAnimation
except:
    from anim import *
    from bones import *
    from import_anim import convertAnimation

def import_fix_coord(v):
    return Vector((-v[0],  -v[2], v[1]))
def import_fix_normal(v):
    return Vector(( v[0], v[2],  -v[1]))
def import_fix_quaternion(quat):
    return Quaternion((quat[3], -quat[0],  -quat[2], quat[1]))

TAIL_LENGTH = 0.05 #0.204377
TAIL_VECTOR = Vector((0, 1, 0))

def getTposeOffset(anim, bone_id):
    offset = Vector((0, 0, 0))
    for bt in anim.bone_tracks:
        if bt.bone_id == bone_id:
            return import_fix_coord(bt.positions[0])
    return offset

def convertBone(anim, arm_obj, arm_data, bone_id, parent, parent_position, tail_nub):
    bone_link = anim.skeleton_hierarchy.bones[bone_id]
    #if bone_link.boneid != bone_id:
    #    raise Exception("")
    bone_name = BONES_LIST[bone_id]

    # Create the (edit)bone.
    new_bone = arm_data.edit_bones.new(name=bone_name)
    new_bone.select = True
    new_bone.name = bone_name

    bone_offset = getTposeOffset(anim, bone_id)
    bone_position = parent_position + bone_offset
    if parent is None:
        if tail_nub:
            #new_bone.head = bone_offset + TAIL_VECTOR * TAIL_LENGTH
            #new_bone.tail = bone_offset
            new_bone.head = bone_position
            new_bone.tail = bone_position + TAIL_VECTOR * TAIL_LENGTH
        else:
            raise
        pass
    else:
        new_bone.parent = parent
        if tail_nub:
            #new_bone.head = bone_offset - TAIL_VECTOR * TAIL_LENGTH
            #new_bone.tail = bone_offset
            new_bone.head = bone_position
            new_bone.tail = bone_position + TAIL_VECTOR * TAIL_LENGTH
        else:
            raise

    #visit children
    if bone_link.next != -1:
        convertBone(anim, arm_obj, arm_data, bone_link.next, parent, parent_position, tail_nub)
    if bone_link.child != -1:
        convertBone(anim, arm_obj, arm_data, bone_link.child, new_bone, bone_position, tail_nub)


def convertSkeleton(context, anim):
    full_name = anim.header_name.decode("utf-8")
    skeleton_name = full_name.split("/")[0]

    #create armature
    arm_data = bpy.data.armatures.new(name=skeleton_name)
    arm_obj = bpy.data.objects.new(name=skeleton_name, object_data=arm_data)

    # instance in scene
    context.view_layer.active_layer_collection.collection.objects.link(arm_obj)
    arm_obj.select_set(True)

    # Switch to Edit mode.
    context.view_layer.objects.active = arm_obj
    is_hidden = arm_obj.hide_viewport
    arm_obj.hide_viewport = False  # Can't switch to Edit mode hidden objects...
    bpy.ops.object.mode_set(mode='EDIT')

    #Traverse tree, creating bones, and position heads and tails.
    convertBone(anim, arm_obj, arm_data, anim.skeleton_hierarchy.root, None, Vector(), True)

    #Switch to Object mode.
    bpy.ops.object.mode_set(mode='OBJECT')
    arm_obj.hide_viewport = is_hidden

    convertAnimation(context, arm_obj, arm_data, anim, rescale = False)

def load(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True, ignore_lod = True):
    #Load .anim file
    fh_in = open(filepath, "rb")
    anim = Anim()
    anim.loadFromFile(fh_in)
    fh_in.close()


    #Check for a skeleton hierarchy
    if not anim.checkSkeletonHierarchy():
        raise Exception("Animation does not have a skeleton. (Or it has errors.)")
    #todo: check for a T-pose
    convertSkeleton(context, anim)

    return {'FINISHED'}
