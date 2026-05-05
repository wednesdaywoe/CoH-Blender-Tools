"""
Blender armature creation and management for CoH skeletons.

Creates Blender armatures matching the CoH bone hierarchy, handles
coordinate conversion, and manages bind poses.
"""

import bpy
import mathutils

from .core.bones import (
    BONE_NAMES, BONE_ID, BONE_PARENT, STANDARD_HIERARCHY,
    bone_id_from_name, bone_name_from_id,
)
from .core.coords import game_to_blender, blender_to_game
from .core.transforms import axis_angle_to_quat, quat_to_axis_angle


# Default bone length in Blender units (cosmetic only, affects display)
DEFAULT_BONE_LENGTH = 0.1


def create_coh_armature(context, name="CoH_Armature"):
    """Create a fresh CoH armature with the standard humanoid hierarchy.

    The armature is created at the origin with bones in default positions.
    Use apply_bind_pose() to set actual bone positions from a skeleton file.

    Args:
        context: Blender context
        name: Name for the armature object

    Returns:
        The created armature object
    """
    armature = bpy.data.armatures.new(f"{name}_Data")
    obj = bpy.data.objects.new(name, armature)

    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    # Must be in edit mode to add bones
    bpy.ops.object.mode_set(mode='EDIT')

    try:
        _build_hierarchy(armature, "HIPS", None)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    # Store CoH bone IDs as custom properties
    for bone in armature.bones:
        bid = bone_id_from_name(bone.name)
        if bid >= 0:
            bone["coh_bone_id"] = bid

    return obj


def _build_hierarchy(armature, bone_name, parent_name):
    """Recursively create bones following the standard hierarchy."""
    edit_bone = armature.edit_bones.new(bone_name)
    edit_bone.head = (0, 0, 0)
    edit_bone.tail = (0, DEFAULT_BONE_LENGTH, 0)

    if parent_name:
        parent_bone = armature.edit_bones.get(parent_name)
        if parent_bone:
            edit_bone.parent = parent_bone

    # Recurse into children
    children = STANDARD_HIERARCHY.get(bone_name, [])
    for child_name in children:
        _build_hierarchy(armature, child_name, bone_name)


def armature_from_anim(context, anim_data, name="CoH_Armature"):
    """Create an armature from binary ANIM data.

    If the ANIM has a skeleton hierarchy (skel_* file), uses it.
    Otherwise creates bones for each bone track present.

    Args:
        context: Blender context
        anim_data: AnimData from anim_binary.read_anim()
        name: Name for the armature object

    Returns:
        The created armature object
    """
    armature = bpy.data.armatures.new(f"{name}_Data")
    obj = bpy.data.objects.new(name, armature)

    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')

    try:
        if anim_data.hierarchy:
            _build_from_hierarchy(armature, anim_data.hierarchy)
        else:
            # No hierarchy - create flat bone list from tracks
            for bt in anim_data.bone_tracks:
                edit_bone = armature.edit_bones.new(bt.bone_name)
                edit_bone.head = (0, 0, 0)
                edit_bone.tail = (0, DEFAULT_BONE_LENGTH, 0)

                # Try to parent based on standard hierarchy
                parent_name = BONE_PARENT.get(bt.bone_name)
                if parent_name:
                    parent_bone = armature.edit_bones.get(parent_name)
                    if parent_bone:
                        edit_bone.parent = parent_bone
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    # Store bone IDs
    for bone in armature.bones:
        bid = bone_id_from_name(bone.name)
        if bid >= 0:
            bone["coh_bone_id"] = bid

    return obj


def _build_from_hierarchy(armature, hierarchy):
    """Build bones from a SkeletonHierarchy."""
    # First create all bones
    for i in range(len(hierarchy.bones)):
        bl = hierarchy.bones[i]
        if bl.child == 0 and bl.next == 0 and bl.id == 0 and i != hierarchy.root:
            continue  # Skip empty entries

        bname = bone_name_from_id(i)
        if bname and not armature.edit_bones.get(bname):
            edit_bone = armature.edit_bones.new(bname)
            edit_bone.head = (0, 0, 0)
            edit_bone.tail = (0, DEFAULT_BONE_LENGTH, 0)

    # Then set up parenting by walking the hierarchy
    _parent_from_hierarchy_recurse(armature, hierarchy, hierarchy.root, None)


def _parent_from_hierarchy_recurse(armature, hierarchy, bone_idx, parent_name):
    """Recursively set bone parents from hierarchy data."""
    if bone_idx < 0 or bone_idx >= len(hierarchy.bones):
        return

    bname = bone_name_from_id(bone_idx)
    if not bname:
        return

    edit_bone = armature.edit_bones.get(bname)
    if not edit_bone:
        return

    if parent_name:
        parent_bone = armature.edit_bones.get(parent_name)
        if parent_bone:
            edit_bone.parent = parent_bone

    # Process children
    bl = hierarchy.bones[bone_idx]
    if bl.child >= 0:
        _parent_from_hierarchy_recurse(armature, hierarchy, bl.child, bname)

    # Process siblings
    if bl.next >= 0:
        _parent_from_hierarchy_recurse(armature, hierarchy, bl.next, parent_name)


def armature_from_skelx(context, skelx_data, name="CoH_Armature"):
    """Create an armature from SKELX data with bind pose positions.

    Args:
        context: Blender context
        skelx_data: SkelXData from skelx.read_skelx()
        name: Name for the armature object

    Returns:
        The created armature object
    """
    armature = bpy.data.armatures.new(f"{name}_Data")
    obj = bpy.data.objects.new(name, armature)

    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')

    try:
        for bone in skelx_data.bones:
            _create_skelx_bone(armature, bone, None)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    # Store bone IDs
    for bone in armature.bones:
        bid = bone_id_from_name(bone.name)
        if bid >= 0:
            bone["coh_bone_id"] = bid

    return obj


def _create_skelx_bone(armature, skel_bone, parent_name):
    """Create a bone from SKELX data and recurse into children."""
    edit_bone = armature.edit_bones.new(skel_bone.name)

    # Convert bind pose position from 3DS Max space to Blender space
    pos = game_to_blender(skel_bone.translation)
    edit_bone.head = pos
    edit_bone.tail = (pos[0], pos[1] + DEFAULT_BONE_LENGTH, pos[2])

    if parent_name:
        parent_bone = armature.edit_bones.get(parent_name)
        if parent_bone:
            edit_bone.parent = parent_bone

    for child in skel_bone.children:
        _create_skelx_bone(armature, child, skel_bone.name)


def apply_animation(context, obj, anim_data, action_name=None):
    """Apply animation data to an armature as keyframes.

    Args:
        context: Blender context
        obj: Armature object
        anim_data: AnimData with bone tracks
        action_name: Name for the action (defaults to anim_data.name)
    """
    if not obj or obj.type != 'ARMATURE':
        return

    if action_name is None:
        action_name = anim_data.name or "CoH_Animation"

    # Create or get action
    action = bpy.data.actions.new(name=action_name)
    if not obj.animation_data:
        obj.animation_data_create()
    obj.animation_data.action = action

    bpy.ops.object.mode_set(mode='POSE')

    try:
        for bt in anim_data.bone_tracks:
            pose_bone = obj.pose.bones.get(bt.bone_name)
            if not pose_bone:
                continue

            # Apply rotation keyframes
            num_frames = max(len(bt.rotations), len(bt.positions))
            for frame_idx in range(num_frames):
                context.scene.frame_set(frame_idx + 1)

                if frame_idx < len(bt.rotations):
                    w, x, y, z = bt.rotations[frame_idx]
                    # Convert from game quaternion to Blender
                    # Game is (w,x,y,z) in game coords → convert axis to Blender
                    bx, by, bz = game_to_blender((x, y, z))
                    pose_bone.rotation_quaternion = (w, bx, by, bz)
                    pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame_idx + 1)

                if frame_idx < len(bt.positions):
                    pos = game_to_blender(bt.positions[frame_idx])
                    pose_bone.location = pos
                    pose_bone.keyframe_insert(data_path="location", frame=frame_idx + 1)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    # Set frame range
    context.scene.frame_start = 1
    context.scene.frame_end = int(anim_data.length) if anim_data.length > 0 else num_frames


def extract_animation(context, obj, frame_start, frame_end):
    """Extract animation data from a Blender armature for export.

    Args:
        context: Blender context
        obj: Armature object with animation
        frame_start: First frame to export
        frame_end: Last frame to export

    Returns:
        List of BoneTrackData for each CoH bone found in the armature
    """
    from .formats.anim_binary import BoneTrackData

    if not obj or obj.type != 'ARMATURE':
        return []

    bone_tracks = []

    bpy.ops.object.mode_set(mode='POSE')

    try:
        for pose_bone in obj.pose.bones:
            bid = bone_id_from_name(pose_bone.name)
            if bid < 0:
                continue

            rotations = []
            positions = []

            for frame in range(frame_start, frame_end + 1):
                context.scene.frame_set(frame)

                # Get rotation as quaternion and convert to game space
                rot = pose_bone.rotation_quaternion
                gx, gy, gz = blender_to_game((rot[1], rot[2], rot[3]))
                rotations.append((rot[0], gx, gy, gz))

                # Get position and convert to game space
                loc = pose_bone.location
                positions.append(blender_to_game((loc[0], loc[1], loc[2])))

            bone_tracks.append(BoneTrackData(
                bone_id=bid,
                bone_name=pose_bone.name,
                rotations=rotations,
                positions=positions,
            ))
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    return bone_tracks
