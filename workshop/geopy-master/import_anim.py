import bpy.path
import bpy
from mathutils import Vector, Quaternion
try:
    from .anim import *
    from .bones import *
except:
    from anim import *
    from bones import *

def import_fix_coord(v):
    return Vector((-v[0],  -v[2], v[1]))
def import_fix_normal(v):
    return Vector(( v[0], v[2],  -v[1]))
def import_fix_quaternion(quat):
    return Quaternion((quat[3], -quat[0],  -quat[2], quat[1]))


def getBoneLength(arm_data, bone_name):
    bl = arm_data.bones[bone_name]
    if bl.parent is None:
        return bl.head

def getBoneRotation(bone, bone_trk_lookup, trk_rot_list, index):
    if bone is None:
        #rot_p = Quaternion()
        return Quaternion()
    else:
        rot_p = getBoneRotation(bone.parent, bone_trk_lookup, trk_rot_list, index)
    if bone.name in bone_trk_lookup:
        trk_index = bone_trk_lookup[bone.name]
        rot_list = trk_rot_list[trk_index]
        if index >= len(rot_list):
            rot_s = rot_list[-1].copy()
        else:
            rot_s = rot_list[index].copy()
    else:
        rot_s = Quaternion()
    rot_p.rotate(rot_s)
    return rot_p
    #rot_s.rotate(rot_p)
    #return rot_s
def convertAnimation(context, arm_obj, arm_data, anim, rescale = True):
    full_name = anim.header_name.decode("utf-8")
    anim_name = full_name.split("/")[1]#.lstrip("skel_")
    #get all bones used in animation, and maximum fram count
    max_frames = 0
    bone_ids = []
    bone_names = []
    bone_trk_lengths = []
    bone_arm_lengths = []
    bone_scales = []
    bone_trk_lookup = {}
    for i, bt in enumerate(anim.bone_tracks):
        #get maximum frame count
        max_frames = max(max_frames, len(bt.positions), len(bt.rotations))
        #get IDs and names
        bone_id = bt.bone_id
        bone_name = BONES_LIST[bone_id]
        bone_trk_lookup[bone_name] = i
        bone_ids.append(bone_id)
        bone_names.append(bone_name)
        #get animation's T-pose length
        bone_trk_len = Vector(bt.positions[0]).length
        bone_trk_lengths.append(bone_trk_len)
        #get armature's T-pose length
        bone_arm_len = getBoneLength(arm_data, bone_name)
        bone_arm_lengths.append(bone_arm_len)
        #determine scale
        bone_scale = rescale and (bone_arm_len / bone_trk_len) or (1.0)
        bone_scales.append(bone_scale)

    #create animation
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    if anim_name in arm_obj.animation_data.nla_tracks:
        #todo: properly handle cases where the name already exists
        nla_track = arm_obj.animation_data.nla_tracks[anim_name]
        pass
    else:
        nla_track = arm_obj.animation_data.nla_tracks.new()
        nla_track.name = anim_name
    action = bpy.data.actions.new(anim_name)
    action.use_fake_user = True
    nla_strip = nla_track.strips.new(anim_name, 0, action)
    nla_strip.action_frame_start = 0
    nla_strip.action_frame_end = max_frames

    #Extract all position and rotation track data in blender coordinates.
    trk_pos_list = []
    trk_rot_list = []
    for i, bt in enumerate(anim.bone_tracks):
        #pos_start = (len(bt.positions) > 1) and 1 or 0
        pos_start = 0
        pos_stop = len(bt.positions)
        #rot_start = (len(bt.rotations) > 1) and 1 or 0
        rot_start = 0
        rot_stop = len(bt.rotations)
        pos_list = []
        rot_list = []
        for j in range(pos_start, pos_stop):
            v = import_fix_coord(bt.positions[j])
            pos_list.append(v)
            pass
        for j in range(rot_start, rot_stop):
            v = import_fix_quaternion(bt.rotations[j])
            rot_list.append(v)
            pass
        trk_pos_list.append(pos_list)
        trk_rot_list.append(rot_list)


    #Iterate over bone tracks and generate FCurves for each of them.
    for i, bt in enumerate(anim.bone_tracks):
        bone_name = bone_names[i]
        bone = arm_data.bones[bone_name]
        pose_bone = arm_obj.pose.bones[bone_name]
        #pos_start = (len(bt.positions) > 1) and 1 or 0
        pos_start = 0
        pos_stop = len(bt.positions)
        #rot_start = (len(bt.rotations) > 1) and 1 or 0
        rot_start = 0
        rot_stop = len(bt.rotations)
        pos_list = trk_pos_list[i]
        rot_list = trk_rot_list[i]
        props = [(pose_bone.path_from_id("location"), 3, bone_name), #"Location"),
                 (pose_bone.path_from_id("rotation_quaternion"), 4, bone_name), #"Quaternion Rotation"),
                 #(pose_bone.path_from_id("rotation_axis_angle"), 4, "Axis Angle Rotation"),
                 #(pose_bone,path_from_id("rotatin_euler"), 3, "Euler Rotation"),
                 #(pose_bone.path_from_id("scale"), 3, "Scale"),
                 ]
        curves = [action.fcurves.new(prop, index = cidx, action_group = agrp)
                  for prop, channel_count, agrp in props
                  for cidx in range(channel_count)]
        pos_curves = curves[0:3]
        rot_curves = curves[3:7]
        for j, pos in enumerate(pos_list):
            #Remove the bone component from the position.
            if bone.parent is None:
                #Only compute it for root bones.
                rot = getBoneRotation(bone.parent, bone_trk_lookup, trk_rot_list, j)
                #rot.invert()
                pos0 = pos_list[0].copy()
                pos0.rotate(rot)
                l = (pos - pos0).length
                if l >= 0.001:# and (bone.name in ["Hips", "Waist","Chest"]):
                    print("%s, %s: %s: pos: %s : %s ::: %s : %s" % (bone.name, j, l, pos, pos0, pos_list[0], rot))
                pos = pos - pos0
                if l < 0.001:
                    #Distance is close to zero, force position adjustment to zero.
                    pos = Vector()
            else:
                #assume 0,0,0 correction in other nodes.
                pos = Vector()
            for k, crv in enumerate(pos_curves):
                crv.keyframe_points.insert(j, pos[k], options={'NEEDED', 'FAST'}).interpolation = 'LINEAR'
        for j, rot in enumerate(rot_list):
            for k, crv in enumerate(rot_curves):
                crv.keyframe_points.insert(j, rot[k], options={'NEEDED', 'FAST'}).interpolation = 'LINEAR'
        for crv in curves:
            crv.update()


    #todo: delete mid points for simple motions?
    pass

def load(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True, ignore_lod = True):
    #Load .anim file
    fh_in = open(filepath, "rb")
    anim = Anim()
    anim.loadFromFile(fh_in)
    fh_in.close()

    #todo: prefer armature name that matches import?
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
    convertAnimation(context, armature_obj, armature, anim, False)

    return {'FINISHED'}
