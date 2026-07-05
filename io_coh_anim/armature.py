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
from .core.bindpose import bind_pose_world, resolve_body_type
from .core.coords import game_to_blender, blender_to_game
from .core.transforms import axis_angle_to_quat, quat_to_axis_angle


# Default bone length in Blender units (cosmetic only, affects display)
DEFAULT_BONE_LENGTH = 0.1

# Geopy / cohbodies.blend build every bone as a short +Y nub of this length
# with zero roll. Matching it keeps the local bone axes identical to those
# tools, which is what game / Geopy-authored .anim rotations are keyed against.
NUB_TAIL_LENGTH = 0.05
NUB_TAIL_VECTOR = (0.0, 1.0, 0.0)


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
        _build_hierarchy(armature, "Hips", None)
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


def create_bind_pose_armature(context, body_type="male", name=None,
                              tail_mode="chain", ground_anchored=False):
    """Create a CoH armature posed at the canonical rest (bind) pose.

    Unlike ``create_coh_armature`` (which stacks every bone at the origin),
    this places each bone at its real joint position for the given body type,
    reconstructed from the game's base animations (see ``core.bindpose``). The
    result overlays a skinned character mesh and poses/animates around the
    correct joints, so an imported skinned ``.geo`` deforms sensibly.

    Args:
        context: Blender context
        body_type: 'male', 'fem', or 'huge' (aliases accepted)
        name: Object name (defaults to ``CoH_<body_type>_bindpose``)
        tail_mode: How to orient bone tails. ``'chain'`` points each tail at
            its child joint — nicer to select and hand-pose. ``'nub'`` gives
            every bone a short +Y stub with zero roll, exactly like Geopy and
            cohbodies.blend, so game/Geopy-authored ``.anim`` rotations map 1:1.
            Bone *head* (the deform pivot) is identical either way.
        ground_anchored: If False (default), HIPS sits at the origin so the rig
            overlays a hip-centred imported ``.geo``. If True, the rig is placed
            feet-on-ground to match a cohbodies/Geopy skeleton.

    Returns:
        The created armature object.
    """
    body_type = resolve_body_type(body_type)
    if name is None:
        name = f"CoH_{body_type}_bindpose"

    # World-space joint positions in Blender coordinates.
    world = {b: game_to_blender(p)
             for b, p in bind_pose_world(body_type, ground_anchored).items()}

    armature = bpy.data.armatures.new(f"{name}_Data")
    obj = bpy.data.objects.new(name, armature)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    try:
        _build_bind_pose(armature, world, "Hips", None, tail_mode,
                         STANDARD_HIERARCHY)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    for bone in armature.bones:
        bid = bone_id_from_name(bone.name)
        if bid >= 0:
            bone["coh_bone_id"] = bid

    return obj


def _bind_pose_tail(head, bone_name, parent_name, world, tail_mode, children_map):
    """Compute a bone's tail for a positioned rest armature.

    ``children_map`` is {bone_name: [child names]} for the skeleton being built
    (the standard hierarchy, or one read from a skel file).
    """
    if tail_mode == "nub":
        # Geopy / cohbodies convention: short +Y stub, zero roll.
        return head + mathutils.Vector(NUB_TAIL_VECTOR) * NUB_TAIL_LENGTH

    # 'chain': point at the first child joint that isn't coincident with head.
    for child_name in children_map.get(bone_name, []):
        if child_name in world:
            cvec = mathutils.Vector(world[child_name])
            if (cvec - head).length > 1e-5:
                return cvec

    # Leaf (or degenerate) bone: continue the direction from the parent,
    # falling back to a short vertical stub.
    direction = None
    if parent_name and parent_name in world:
        direction = head - mathutils.Vector(world[parent_name])
    if direction is None or direction.length < 1e-5:
        direction = mathutils.Vector((0.0, 0.0, DEFAULT_BONE_LENGTH))
    return head + direction.normalized() * DEFAULT_BONE_LENGTH


def _build_bind_pose(armature, world, bone_name, parent_name, tail_mode,
                     children_map):
    """Recursively create a bone at its bind-pose joint."""
    head = mathutils.Vector(world.get(bone_name, (0.0, 0.0, 0.0)))
    tail = _bind_pose_tail(head, bone_name, parent_name, world, tail_mode,
                           children_map)

    edit_bone = armature.edit_bones.new(bone_name)
    edit_bone.head = head
    edit_bone.tail = tail

    if parent_name:
        parent_bone = armature.edit_bones.get(parent_name)
        if parent_bone:
            edit_bone.parent = parent_bone

    for child_name in children_map.get(bone_name, []):
        _build_bind_pose(armature, world, child_name, bone_name, tail_mode,
                         children_map)


def _skeleton_world_from_anim(anim_data, anchor="file"):
    """Reconstruct rest-pose joint positions from a ``.anim`` file.

    Every full-body ``.anim`` carries, for each bone, its constant local offset
    from its parent as the first key of the bone's position track. Accumulating
    those offsets down the skeleton tree reproduces the rest skeleton — the same
    reconstruction Geopy's import_skel and the game's runtime perform.

    Two sources for the tree, in priority order:

    1. An embedded hierarchy (``child``/``next`` links). Only prop skeletons
       (``skel_ready.anim``) and dev-exported files carry one; the game ships no
       humanoid skeleton file with an embedded hierarchy.
    2. Otherwise the standard humanoid hierarchy (``core.bones``), which every
       full-body character animation implicitly targets — this is the common
       case for the shipped ``fem/`` / ``male/`` / ``huge/`` animations.

    Args:
        anim_data: AnimData from ``read_anim``.
        anchor: ``'file'`` keeps HIPS at its own frame-0 position (feet on the
            ground, as the file stores it); ``'hip'`` drops HIPS to the origin
            so the rig overlays a hip-centred imported mesh.

    Returns:
        (world_game, children_map, root_name):
            world_game   {bone_name: (x, y, z)} in game space
            children_map {bone_name: [child bone names]}
            root_name    name of the root bone (or None)
    """
    offsets = {bt.bone_id: bt.positions[0]
               for bt in anim_data.bone_tracks if bt.positions}

    if anim_data.hierarchy:
        return _skeleton_world_from_hierarchy(anim_data.hierarchy, offsets, anchor)
    return _skeleton_world_from_standard(offsets, anchor)


def _skeleton_world_from_hierarchy(h, offsets, anchor):
    """Reconstruct joints by walking an embedded ``child``/``next`` tree."""
    world = {}
    children = {}
    root_name = bone_name_from_id(h.root)

    def visit(bone_id, parent_pos, parent_name, is_root):
        if bone_id < 0 or bone_id >= len(h.bones):
            return
        name = bone_name_from_id(bone_id)
        off = offsets.get(bone_id, (0.0, 0.0, 0.0))
        if is_root and anchor == "hip":
            off = (0.0, 0.0, 0.0)
        pos = (parent_pos[0] + off[0],
               parent_pos[1] + off[1],
               parent_pos[2] + off[2])

        if name:
            world[name] = pos
            children.setdefault(name, [])
            if parent_name:
                children.setdefault(parent_name, []).append(name)

        link = h.bones[bone_id]
        # First child accumulates from this bone; siblings share our parent.
        if link.child != -1:
            visit(link.child, pos, name or parent_name, False)
        if link.next != -1:
            visit(link.next, parent_pos, parent_name, is_root)

    visit(h.root, (0.0, 0.0, 0.0), None, True)
    return world, children, root_name


def _skeleton_world_from_standard(offsets, anchor):
    """Reconstruct joints down the standard humanoid hierarchy from HIPS."""
    name_off = {}
    for bid, off in offsets.items():
        n = bone_name_from_id(bid)
        if n:
            name_off[n] = off

    root_off = name_off.get("Hips", (0.0, 0.0, 0.0)) if anchor == "file" \
        else (0.0, 0.0, 0.0)

    world = {}

    def resolve(name):
        if name in world:
            return world[name]
        parent = BONE_PARENT.get(name)
        if parent is None:
            pos = root_off
        else:
            pw = resolve(parent)
            off = name_off.get(name, (0.0, 0.0, 0.0))
            pos = (pw[0] + off[0], pw[1] + off[1], pw[2] + off[2])
        world[name] = pos
        return pos

    bones = set(STANDARD_HIERARCHY)
    for kids in STANDARD_HIERARCHY.values():
        bones.update(kids)
    for b in bones:
        resolve(b)

    return world, STANDARD_HIERARCHY, "Hips"


def armature_from_skeleton_anim(context, anim_data, name="CoH_Skeleton",
                                tail_mode="nub", anchor="file"):
    """Build a correctly-positioned rest armature from a ``.anim`` file.

    Each bone is placed at its real joint position — reconstructed from the
    frame-0 position keys down the skeleton tree (an embedded hierarchy if the
    file has one, else the standard humanoid hierarchy). This matches Geopy's
    import_skel and the game's runtime rest assembly. No animation is applied;
    the result is the rest skeleton, ready to bind a skinned mesh or receive a
    separate ``.anim``.

    Args:
        context: Blender context
        anim_data: AnimData from ``read_anim``
        name: Object name
        tail_mode: ``'nub'`` (+Y stub, zero roll — matches Geopy/game anims,
            default) or ``'chain'`` (tails point at child joints, easier to pose)
        anchor: ``'file'`` (keep the file's feet-on-ground HIPS position) or
            ``'hip'`` (recentre HIPS to the origin for a hip-centred mesh)

    Returns:
        The created armature object.

    Raises:
        ValueError: if no recognisable root bone could be reconstructed.
    """
    world_game, children_map, root_name = _skeleton_world_from_anim(
        anim_data, anchor=anchor)
    if not root_name or root_name not in world_game:
        raise ValueError("Could not reconstruct a skeleton from this .anim "
                         "(no recognised CoH bones).")

    world = {b: game_to_blender(p) for b, p in world_game.items()}

    armature = bpy.data.armatures.new(f"{name}_Data")
    obj = bpy.data.objects.new(name, armature)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    try:
        _build_bind_pose(armature, world, root_name, None, tail_mode,
                         children_map)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

    for bone in armature.bones:
        bid = bone_id_from_name(bone.name)
        if bid >= 0:
            bone["coh_bone_id"] = bid

    return obj


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
