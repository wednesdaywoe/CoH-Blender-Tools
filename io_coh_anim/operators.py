"""
Blender operators for CoH animation and geometry import/export.

Provides file browser operators for all supported formats:
- Binary .anim (import/export)
- ANIMX text (import/export)
- SKELX text (import/export)
- GEO geometry (import/export)
- Texture conversion (TGA/PNG → .texture)
- Create CoH armature (utility)
"""

import os
import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper


# ─── Import Operators ───────────────────────────────────────────────────────

class COH_OT_import_anim(bpy.types.Operator, ImportHelper):
    """Import a City of Heroes binary animation (.anim)"""
    bl_idname = "import_anim.coh_anim"
    bl_label = "Import CoH Animation (.anim)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".anim"
    filter_glob: StringProperty(default="*.anim", options={'HIDDEN'})

    def execute(self, context):
        from .formats.anim_binary import read_anim
        from .armature import armature_from_anim, apply_animation

        anim_data = read_anim(self.filepath)

        # Check if active object is a CoH armature
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            # Apply animation to existing armature
            apply_animation(context, obj, anim_data)
            self.report({'INFO'}, f"Applied animation '{anim_data.name}' ({len(anim_data.bone_tracks)} bones)")
        else:
            # Create new armature
            anim_name = os.path.splitext(os.path.basename(self.filepath))[0]
            obj = armature_from_anim(context, anim_data, name=anim_name)

            if anim_data.bone_tracks:
                apply_animation(context, obj, anim_data)

            self.report({'INFO'}, f"Imported '{anim_data.name}' ({len(anim_data.bone_tracks)} bones)")

        return {'FINISHED'}


class COH_OT_import_animx(bpy.types.Operator, ImportHelper):
    """Import a City of Heroes text animation (.animx)"""
    bl_idname = "import_anim.coh_animx"
    bl_label = "Import CoH Animation Text (.animx)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".animx"
    filter_glob: StringProperty(default="*.animx;*.ANIMX", options={'HIDDEN'})

    def execute(self, context):
        from .formats.animx import read_animx

        animx_data = read_animx(self.filepath)

        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select a CoH armature first, then import ANIMX")
            return {'CANCELLED'}

        # Apply ANIMX transforms as keyframes
        _apply_animx_to_armature(context, obj, animx_data)

        self.report({'INFO'},
                    f"Applied ANIMX animation ({animx_data.total_frames} frames, {len(animx_data.bones)} bones)")
        return {'FINISHED'}


class COH_OT_import_skelx(bpy.types.Operator, ImportHelper):
    """Import a City of Heroes skeleton (.skelx)"""
    bl_idname = "import_anim.coh_skelx"
    bl_label = "Import CoH Skeleton (.skelx)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".skelx"
    filter_glob: StringProperty(default="*.skelx;*.SKELX", options={'HIDDEN'})

    def execute(self, context):
        from .formats.skelx import read_skelx
        from .armature import armature_from_skelx

        skelx_data = read_skelx(self.filepath)
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        obj = armature_from_skelx(context, skelx_data, name=name)

        self.report({'INFO'}, f"Created armature '{name}' from SKELX")
        return {'FINISHED'}


# ─── Export Operators ───────────────────────────────────────────────────────

class COH_OT_export_anim(bpy.types.Operator, ExportHelper):
    """Export a City of Heroes binary animation (.anim)"""
    bl_idname = "export_anim.coh_anim"
    bl_label = "Export CoH Animation (.anim)"
    bl_options = {'REGISTER'}

    filename_ext = ".anim"
    filter_glob: StringProperty(default="*.anim", options={'HIDDEN'})

    anim_name: StringProperty(
        name="Animation Name",
        description="Internal animation path (e.g., 'male/my_animation')",
        default="male/custom_anim",
    )

    base_anim_name: StringProperty(
        name="Base Skeleton",
        description="Reference skeleton path (e.g., 'male/skel_ready2')",
        default="male/skel_ready2",
    )

    body_type: EnumProperty(
        name="Body Type",
        items=[
            ('male', "Male", "Standard male body type"),
            ('fem', "Female", "Female body type"),
            ('huge', "Huge", "Large body type"),
        ],
        default='male',
    )

    def execute(self, context):
        from .formats.anim_binary import AnimData, write_anim
        from .armature import extract_animation

        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select a CoH armature to export")
            return {'CANCELLED'}

        frame_start = context.scene.frame_start
        frame_end = context.scene.frame_end

        bone_tracks = extract_animation(context, obj, frame_start, frame_end)
        if not bone_tracks:
            self.report({'ERROR'}, "No CoH bones found in armature")
            return {'CANCELLED'}

        anim_data = AnimData(
            name=self.anim_name,
            base_anim_name=self.base_anim_name,
            length=float(frame_end - frame_start),
            bone_tracks=bone_tracks,
        )

        write_anim(self.filepath, anim_data)
        self.report({'INFO'}, f"Exported '{self.anim_name}' ({len(bone_tracks)} bones, {frame_end - frame_start + 1} frames)")
        return {'FINISHED'}


class COH_OT_export_animx(bpy.types.Operator, ExportHelper):
    """Export a City of Heroes text animation (.animx)"""
    bl_idname = "export_anim.coh_animx"
    bl_label = "Export CoH Animation Text (.animx)"
    bl_options = {'REGISTER'}

    filename_ext = ".animx"
    filter_glob: StringProperty(default="*.animx", options={'HIDDEN'})

    def execute(self, context):
        from .formats.animx import AnimXData, AnimXBone, AnimXTransform, write_animx
        from .core.bones import bone_id_from_name
        from .core.coords import blender_to_game
        from .core.transforms import quat_to_axis_angle

        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select a CoH armature to export")
            return {'CANCELLED'}

        frame_start = context.scene.frame_start
        frame_end = context.scene.frame_end
        total_frames = frame_end - frame_start + 1

        animx = AnimXData(
            version=200,
            source_name=os.path.basename(bpy.data.filepath) or "Blender",
            total_frames=total_frames,
            first_frame=frame_start,
        )

        bpy.ops.object.mode_set(mode='POSE')

        try:
            for pose_bone in obj.pose.bones:
                if bone_id_from_name(pose_bone.name) < 0:
                    continue

                bone_data = AnimXBone(name=pose_bone.name)

                for frame in range(frame_start, frame_end + 1):
                    context.scene.frame_set(frame)

                    rot = pose_bone.rotation_quaternion
                    loc = pose_bone.location

                    # Convert rotation to axis-angle in 3DS Max coords
                    # Note: blender_to_game is same as blender_to_max for axis conversion
                    axis, angle = quat_to_axis_angle((rot[0], rot[1], rot[2], rot[3]))

                    # Convert position to 3DS Max coords (same as game for position)
                    # Actually ANIMX is in 3DS Max space, not game space
                    # blender_to_max is identity, so export Blender coords directly
                    # (GA2 will do the coord conversion)
                    pos = (loc[0], loc[1], loc[2])

                    bone_data.transforms.append(AnimXTransform(
                        axis=axis,
                        angle=angle,
                        translation=pos,
                        scale=(1.0, 1.0, 1.0),
                    ))

                animx.bones.append(bone_data)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

        write_animx(self.filepath, animx)
        self.report({'INFO'}, f"Exported ANIMX ({total_frames} frames, {len(animx.bones)} bones)")
        return {'FINISHED'}


class COH_OT_export_skelx(bpy.types.Operator, ExportHelper):
    """Export a City of Heroes skeleton (.skelx)"""
    bl_idname = "export_anim.coh_skelx"
    bl_label = "Export CoH Skeleton (.skelx)"
    bl_options = {'REGISTER'}

    filename_ext = ".skelx"
    filter_glob: StringProperty(default="*.skelx", options={'HIDDEN'})

    def execute(self, context):
        from .formats.skelx import SkelXData, SkelXBone, write_skelx
        from .core.bones import bone_id_from_name

        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select a CoH armature to export")
            return {'CANCELLED'}

        armature = obj.data
        skelx = SkelXData(
            version=200,
            source_name=os.path.basename(bpy.data.filepath) or "Blender",
        )

        # Build hierarchy from Blender bone parents
        root_bones = [b for b in armature.bones if b.parent is None and bone_id_from_name(b.name) >= 0]
        for bone in root_bones:
            skel_bone = _bone_to_skelx(bone)
            if skel_bone:
                skelx.bones.append(skel_bone)

        write_skelx(self.filepath, skelx)
        self.report({'INFO'}, f"Exported SKELX skeleton")
        return {'FINISHED'}


# ─── Utility Operators ──────────────────────────────────────────────────────

class COH_OT_create_armature(bpy.types.Operator):
    """Create a City of Heroes armature with standard bone hierarchy"""
    bl_idname = "object.coh_create_armature"
    bl_label = "Create CoH Armature"
    bl_options = {'REGISTER', 'UNDO'}

    body_type: EnumProperty(
        name="Body Type",
        items=[
            ('male', "Male", "Standard male body type"),
            ('fem', "Female", "Female body type"),
            ('huge', "Huge", "Large body type"),
        ],
        default='male',
    )

    def execute(self, context):
        from .armature import create_coh_armature

        obj = create_coh_armature(context, name=f"CoH_{self.body_type}")
        self.report({'INFO'}, f"Created CoH {self.body_type} armature")
        return {'FINISHED'}


# ─── GEO Operators ─────────────────────────────────────────────────────────

class COH_OT_import_geo(bpy.types.Operator, ImportHelper):
    """Import City of Heroes geometry (.geo)"""
    bl_idname = "import_mesh.coh_geo"
    bl_label = "Import CoH Geometry (.geo)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".geo"
    filter_glob: StringProperty(default="*.geo", options={'HIDDEN'})

    import_textures: BoolProperty(
        name="Import Textures",
        description="Look for .texture/.dds files matching each material name "
                    "in the .geo's folder (or a sibling 'textures/' folder) "
                    "and wire them into the material's Principled BSDF",
        default=True,
    )

    bind_to_armature: BoolProperty(
        name="Bind to Armature",
        description="If a CoH armature is active (or the scene has exactly one), "
                    "parent skinned meshes to it and add an Armature modifier so "
                    "they deform. Vertex groups are imported either way",
        default=True,
    )

    auto_create_armature: BoolProperty(
        name="Auto-create Bind-pose Armature",
        description="When a mesh is skinned but no CoH armature exists to bind "
                    "to, build one automatically at the canonical rest (bind) "
                    "pose so the mesh deforms around the correct joints",
        default=True,
    )

    body_type: EnumProperty(
        name="Body Type",
        description="Skeleton proportions for an auto-created bind-pose armature",
        items=[
            ('auto', "Auto", "Guess from the file/mesh name (defaults to Male)"),
            ('male', "Male", "Standard male body type"),
            ('fem', "Female", "Female body type"),
            ('huge', "Huge", "Large body type"),
        ],
        default='auto',
    )

    bone_tail_mode: EnumProperty(
        name="Bone Tails",
        description="How to orient bones in an auto-created bind-pose armature. "
                    "The deform pivot is identical either way",
        items=[
            ('chain', "Toward Child",
             "Point each bone at its child joint — easier to select and "
             "hand-pose"),
            ('nub', "+Y Nub (Geopy-compatible)",
             "Short +Y stubs with zero roll, matching Geopy and cohbodies.blend "
             "so game/Geopy-authored .anim rotations map 1:1"),
        ],
        default='chain',
    )

    def execute(self, context):
        from .formats.geo import read_geo
        from .mesh import mesh_from_geo
        from .armature import create_bind_pose_armature
        from .core.bindpose import guess_body_type

        geo_file = read_geo(self.filepath)
        texture_dir = os.path.dirname(self.filepath) if self.import_textures else None

        # Pick a target armature: the active object if it's an armature,
        # otherwise the scene's sole armature (if unambiguous).
        armature_obj = None
        if self.bind_to_armature:
            act = context.active_object
            if act and act.type == 'ARMATURE':
                armature_obj = act
            else:
                arms = [o for o in context.scene.objects if o.type == 'ARMATURE']
                if len(arms) == 1:
                    armature_obj = arms[0]

        # No suitable armature but the geo is skinned: build a bind-pose
        # armature so the mesh actually deforms around its joints.
        geo_is_skinned = any(
            m.bone_info and m.bone_info.weights for m in geo_file.models
        )
        created_armature = False
        if (self.bind_to_armature and self.auto_create_armature
                and armature_obj is None and geo_is_skinned):
            model_names = " ".join(m.name for m in geo_file.models)
            bt = (guess_body_type(os.path.basename(self.filepath), model_names)
                  if self.body_type == 'auto' else self.body_type)
            armature_obj = create_bind_pose_armature(context, body_type=bt,
                                                     tail_mode=self.bone_tail_mode)
            created_armature = True

        objects = mesh_from_geo(context, geo_file, texture_dir=texture_dir,
                                armature_obj=armature_obj)

        total_verts = sum(m.vert_count for m in geo_file.models)
        skinned = sum(1 for o in objects if o.type == 'MESH' and o.vertex_groups)
        msg = f"Imported {len(objects)} mesh(es), {total_verts} vertices"
        if skinned:
            if created_armature:
                msg += f"; built bind-pose armature '{armature_obj.name}' and " \
                       f"bound {skinned} skinned mesh(es)"
            elif armature_obj is not None:
                msg += f"; bound {skinned} skinned mesh(es) to '{armature_obj.name}'"
            else:
                msg += f"; {skinned} skinned mesh(es) have vertex groups " \
                       "(no armature to bind — import a CoH skeleton first)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class COH_OT_export_geo(bpy.types.Operator, ExportHelper):
    """Export City of Heroes geometry (.geo)"""
    bl_idname = "export_mesh.coh_geo"
    bl_label = "Export CoH Geometry (.geo)"
    bl_options = {'REGISTER'}

    filename_ext = ".geo"
    filter_glob: StringProperty(default="*.geo", options={'HIDDEN'})

    geo_name: StringProperty(
        name="GEO Name",
        description="Internal name for the geometry file",
        default="custom",
    )

    def execute(self, context):
        from .formats.geo import write_geo
        from .mesh import geo_from_mesh

        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "Select at least one mesh object to export")
            return {'CANCELLED'}

        geo_file = geo_from_mesh(context, selected, geo_name=self.geo_name)
        write_geo(self.filepath, geo_file)

        total_verts = sum(m.vert_count for m in geo_file.models)
        self.report({'INFO'},
                    f"Exported {len(geo_file.models)} mesh(es), {total_verts} vertices")
        return {'FINISHED'}


# ─── Texture Operators ─────────────────────────────────────────────────────

class COH_OT_convert_texture(bpy.types.Operator, ImportHelper):
    """Convert an image to CoH .texture format"""
    bl_idname = "coh.convert_texture"
    bl_label = "Convert Image to CoH Texture"
    bl_options = {'REGISTER'}

    filename_ext = ".tga"
    filter_glob: StringProperty(
        default="*.tga;*.png;*.bmp;*.jpg;*.jpeg",
        options={'HIDDEN'},
    )

    output_dir: StringProperty(
        name="Output Directory",
        description="Directory for the output .texture file",
        subtype='DIR_PATH',
        default="",
    )

    dxt_format: EnumProperty(
        name="DXT Format",
        items=[
            ('DXT5', "DXT5 (Alpha)", "DXT5 compression with alpha channel"),
            ('DXT1', "DXT1 (No Alpha)", "DXT1 compression, no alpha"),
        ],
        default='DXT5',
    )

    def execute(self, context):
        from .formats.texture import image_to_texture

        basename = os.path.splitext(os.path.basename(self.filepath))[0]
        out_dir = self.output_dir or os.path.dirname(self.filepath)
        output_path = os.path.join(out_dir, basename + ".texture")

        try:
            image_to_texture(self.filepath, output_path, fmt=self.dxt_format)
            self.report({'INFO'}, f"Created {output_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Conversion failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


# ─── Helper Functions ───────────────────────────────────────────────────────

def _apply_animx_to_armature(context, obj, animx_data):
    """Apply ANIMX animation data to an existing armature."""
    from .core.transforms import axis_angle_to_quat
    from .core.coords import game_to_blender

    action_name = animx_data.source_name or "ANIMX_Animation"
    action = bpy.data.actions.new(name=action_name)
    if not obj.animation_data:
        obj.animation_data_create()
    obj.animation_data.action = action

    bpy.ops.object.mode_set(mode='POSE')

    try:
        for anim_bone in animx_data.bones:
            pose_bone = obj.pose.bones.get(anim_bone.name)
            if not pose_bone:
                continue

            for frame_idx, transform in enumerate(anim_bone.transforms):
                frame = frame_idx + 1

                # Convert axis-angle to quaternion (with CoH angle negation)
                w, x, y, z = axis_angle_to_quat(transform.axis, transform.angle)
                pose_bone.rotation_quaternion = (w, x, y, z)
                pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

                # Position (ANIMX is in 3DS Max world space)
                pose_bone.location = transform.translation
                pose_bone.keyframe_insert(data_path="location", frame=frame)

        context.scene.frame_start = 1
        context.scene.frame_end = animx_data.total_frames
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')


def _bone_to_skelx(blender_bone):
    """Convert a Blender bone to SkelXBone recursively."""
    from .formats.skelx import SkelXBone
    from .core.bones import bone_id_from_name

    if bone_id_from_name(blender_bone.name) < 0:
        return None

    skel_bone = SkelXBone(
        name=blender_bone.name,
        translation=(blender_bone.head_local[0], blender_bone.head_local[1], blender_bone.head_local[2]),
    )

    for child in blender_bone.children:
        child_skel = _bone_to_skelx(child)
        if child_skel:
            skel_bone.children.append(child_skel)

    return skel_bone


# ─── Registration ───────────────────────────────────────────────────────────

CLASSES = [
    COH_OT_import_anim,
    COH_OT_import_animx,
    COH_OT_import_skelx,
    COH_OT_import_geo,
    COH_OT_export_anim,
    COH_OT_export_animx,
    COH_OT_export_skelx,
    COH_OT_export_geo,
    COH_OT_convert_texture,
    COH_OT_create_armature,
]
