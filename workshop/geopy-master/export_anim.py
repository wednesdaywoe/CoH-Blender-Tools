import bpy.path
import bpy
import math
from mathutils import Vector, Quaternion
try:
    from .anim import *
    from .bones import *
except:
    from anim import *
    from bones import *

def export_fix_coord(v):
    return Vector((-v[0],  v[2], -v[1]))
def export_fix_normal(v):
    return Vector(( v[0], -v[2],  v[1]))
def export_fix_quaternion(quat):
    return Quaternion((-quat[1],  quat[3], -quat[2], quat[0]))


def getBoneRotation(bone, bone_tracks, index):
    if bone is None:
        #rot_p = Quaternion()
        return Quaternion()
    else:
        rot_p = getBoneRotation(bone.parent, bone_tracks, index)
    if bone.name in bone_tracks:
        trk = bone_tracks[bone.name]
        chn = trk["rotation_quaternion"]
        if index >= len(chn):
            rot_s = chn[-1].copy()
        else:
            rot_s = chn[index].copy()
    else:
        rot_s = Quaternion()
    rot_p.rotate(rot_s)
    return rot_p
    #rot_s.rotate(rot_p)
    #return rot_s


def convert_animation(context, arm_obj, arm_data, nla_track, anim, save_skel):
    bone_tracks = {}
    for nla_strip in nla_track.strips:
        #todo: what's the proper way to handle multiple strips?
        #Presently later strips will overwrite earlier strips.
        #>>> [x.data_path for x in bpy.data.objects['fem'].animation_data.nla_tracks['run'].strips[0].action.fcurves]
        #>>> [x.array_index for x in bpy.data.objects['fem'].animation_data.nla_tracks['run'].strips[0].action.fcurves]
        for crv in nla_strip.action.fcurves:
            #>>> [y.co for x in bpy.data.objects['fem'].animation_data.nla_tracks['run'].strips[0].action.fcurves for y in x.sampled_points]
            dp = crv.data_path
            idx = crv.array_index
            print("crv: %s : %s" % (dp, idx))
            #Naively convert data_path into bone, and transform type
            parts_a = dp.split('["')
            parts_b = parts_a[1].split('"].')
            bone_name = parts_b[0]
            transform = parts_b[1]
            if bone_name not in bone_tracks:
                bone_tracks[bone_name] = {}
            bone_track = bone_tracks[bone_name]
            if transform == "location":
                data_type = Vector
            elif transform == "rotation_quaternion":
                data_type = Quaternion
            else:
                #todo:
                raise
                data_type = None
            if transform not in bone_track:
                bone_track[transform] = []
            bone_track_channel = bone_track[transform]
            for pnt in crv.sampled_points:
                k = int(math.floor(pnt.co[0] + 0.5))
                if k < 0:
                    #ignore samples before 0
                    continue
                while len(bone_track_channel) <= k:
                    bone_track_channel.append(data_type())
                bone_track_channel[k][idx] = pnt.co[1]
    #print("bone_tracks: %s" % bone_tracks)
    print("bone_tracks['Head']: %s" % bone_tracks.get("Head", None))
    #todo: convert FCurve data to track positions and rotations

    #todo: Get bones required for export.
    if save_skel:
        #If we need to save the skeleton, ensure we have values for the T-pose loaded into bones that haven't been referenced yet.
        for bn in arm_data.bones.keys():
            if bn not in bone_tracks:
                bone_tracks[bn] = {
                    "location": [Vector()],
                    "rotation_quaternion": [Quaternion()],
                }

    #todo: trim back tracks that have duplicates on their tail.
    for bn, bt in bone_tracks.items():
        #ensure missing channels have a T-pose value.
        if "location" not in bt:
            bt["location"] = [Vector()]
        if "rotation_quaternion" not in bt:
            bt["rotation_quaternion"] = [Quaternion()]
        #Trim back duplicates at the end of a track.
        for cn in ("location", "rotation_quaternion"):
            chn = bt[cn]
            while len(chn) >= 2:
                if chn[-1] == chn[-2]:
                    chn.pop()
                else:
                    break

    #Convert track positions and rotations into a more convenient form.
    for bn, bt in bone_tracks.items():
        bone = arm_data.bones[bn]
        #Get position of bone, relative to parent (or armature origin for root bones).
        if bone.parent is None:
            bone_position = bone.head
        else:
            bone_position = bone.head + (bone.parent.tail - bone.parent.head)
            #print("parent[%s]: %s %s" % (bone.parent.name, bone.parent.head, bone.parent.tail))
        print("bone_position[%s(%s)]: %s" % (bn, bone.name, bone_position))
        bt["net_location"] = [bone_position]
        bt["net_rotation_quaternion"] = []
        rot_chn = bt["rotation_quaternion"]
        for i in range(len(rot_chn)):
            bt["net_rotation_quaternion"].append(getBoneRotation(bone, bone_tracks, i))
        for i in range(1, len(bt["location"])):
            if i >= len(bt["net_rotation_quaternion"]):
                rot = bt["net_rotation_quaternion"][-1]
            else:
                rot = bt["net_rotation_quaternion"][i]
            pos = bone_position + bt["location"][i]
            print("   pos[%s]: %s" % (i, pos))
            pos.rotate(rot)
            bt["net_location"].append(pos)

    #print("bone_tracks: %s" % bone_tracks)

    #Store bone track information in the Anim
    for bn, bt in bone_tracks.items():
        bat = BoneAnimTrack()
        bat.bone_id = BONES_LOOKUP[bn]
        bat.rotations = [export_fix_quaternion(x) for x in bt["rotation_quaternion"]]
        bat.positions = [export_fix_coord(x) for x in bt["net_location"]]
        anim.bone_tracks.append(bat)

    #Save the skeleton (if flagged).
    if save_skel:
        anim.skeleton_hierarchy = SkeletonHierarchy()
        for bn in BONES_LIST:
            if bn in arm_data.bones:
                bone = arm_data.bones[bn]
                if bone.parent is None:
                    parent_id = None
                else:
                    parent_id = BONES_LOOKUP[bone.parent.name]
                bone_id = BONES_LOOKUP[bn]
                anim.skeleton_hierarchy.addBone(parent_id, bone_id)

    anim.dump()
    pass

def save(operator, context, scale = 1.0, filepath = "", global_matrix = None, use_mesh_modifiers = True, save_skeleton = False):
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
    #todo:
    track = None
    skel_track = None
    #todo: error/warning if multiple tracks are selected.
    #todo: error/warning if multiple skel_ tracks are found
    #todo: error if no skel_tracks are found
    for t in armature_obj.animation_data.nla_tracks:
        if t.select:
            track = t
        if t.name.lower().startswith("skel_"):
            skel_track = t
    if save_skeleton:
        skel_track = track
    arm_name = armature_obj.name
    track_name = bpy.path.display_name_from_filepath(filepath)
    skel_track_name = skel_track.name

    #Get name and base name
    anim_name = "%s/%s" % (arm_name, track_name)
    anim_base_name = "%s/%s" % (arm_name, skel_track_name)
    #todo: warning if anim_name doesn't match file path

    anim = Anim()
    anim.header_name = anim_name
    anim.header_base_anim_name = anim_base_name

    save_skel = save_skeleton or anim_name == anim_base_name
    convert_animation(context, armature_obj, armature, track, anim, save_skel)

    data = anim.saveToData()
    fh = open(filepath, "wb")
    fh.write(data)
    fh.close()

    return {'FINISHED'}
