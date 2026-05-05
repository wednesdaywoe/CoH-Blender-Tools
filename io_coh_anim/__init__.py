"""
City of Heroes Animation & Geometry Tools - Blender Addon

Import/export City of Heroes data in all supported formats:
- Binary .anim (direct game animation format)
- ANIMX text (3DS Max animation export format)
- SKELX text (3DS Max skeleton export format)
- GEO geometry (game 3D model format)
- .texture conversion (TGA/PNG to game texture format)

Replaces the legacy 3DS Max 2011 + GetAnimation2 + GetVrml + GetTex
workflow with a free, modern Blender-based pipeline.
"""

bl_info = {
    "name": "City of Heroes Animation & Geometry Tools",
    "author": "CoH Community",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Import/Export, 3D View > Sidebar > CoH",
    "description": "Import/export City of Heroes animations and geometry (ANIM, ANIMX, SKELX, GEO, TEXTURE)",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

# Guard all Blender-dependent code so the package can be imported
# outside Blender for testing the format parsers and core math.
try:
    import bpy
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False

if _HAS_BPY:
    from .operators import CLASSES as OPERATOR_CLASSES

    def menu_func_import(self, context):
        self.layout.operator("import_anim.coh_anim", text="CoH Animation (.anim)")
        self.layout.operator("import_anim.coh_animx", text="CoH Animation Text (.animx)")
        self.layout.operator("import_anim.coh_skelx", text="CoH Skeleton (.skelx)")
        self.layout.operator("import_mesh.coh_geo", text="CoH Geometry (.geo)")

    def menu_func_export(self, context):
        self.layout.operator("export_anim.coh_anim", text="CoH Animation (.anim)")
        self.layout.operator("export_anim.coh_animx", text="CoH Animation Text (.animx)")
        self.layout.operator("export_anim.coh_skelx", text="CoH Skeleton (.skelx)")
        self.layout.operator("export_mesh.coh_geo", text="CoH Geometry (.geo)")

    class COH_PT_sidebar(bpy.types.Panel):
        """CoH Tools sidebar panel."""
        bl_label = "CoH Tools"
        bl_idname = "COH_PT_sidebar"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'CoH'

        def draw(self, context):
            layout = self.layout

            layout.label(text="Armature:")
            layout.operator("object.coh_create_armature", text="Create CoH Armature")

            layout.separator()
            layout.label(text="Animation:")
            row = layout.row(align=True)
            row.operator("import_anim.coh_anim", text="Import .anim")
            row.operator("export_anim.coh_anim", text="Export .anim")
            row = layout.row(align=True)
            row.operator("import_anim.coh_animx", text="Import .animx")
            row.operator("export_anim.coh_animx", text="Export .animx")
            layout.operator("import_anim.coh_skelx", text="Import .skelx")

            layout.separator()
            layout.label(text="Geometry:")
            row = layout.row(align=True)
            row.operator("import_mesh.coh_geo", text="Import .geo")
            row.operator("export_mesh.coh_geo", text="Export .geo")

            layout.separator()
            layout.label(text="Textures:")
            layout.operator("coh.convert_texture", text="Convert to .texture")

            obj = context.active_object
            if obj:
                layout.separator()
                layout.label(text=f"Active: {obj.name}")
                if obj.type == 'ARMATURE':
                    layout.label(text=f"Bones: {len(obj.data.bones)}")
                    if obj.animation_data and obj.animation_data.action:
                        layout.label(text=f"Action: {obj.animation_data.action.name}")
                elif obj.type == 'MESH':
                    mesh = obj.data
                    layout.label(text=f"Verts: {len(mesh.vertices)}")
                    layout.label(text=f"Tris: {len(mesh.polygons)}")

    ALL_CLASSES = OPERATOR_CLASSES + [COH_PT_sidebar]

    def register():
        for cls in ALL_CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    def unregister():
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        for cls in reversed(ALL_CLASSES):
            bpy.utils.unregister_class(cls)

    if __name__ == "__main__":
        register()
