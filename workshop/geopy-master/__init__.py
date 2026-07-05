
bl_info = {
    "name": "City of Heroes (.geo)",
    "author": "TigerKat",
    "version": (0, 2, 9),
    "blender": (2, 80, 0),
    "location": "File > Import/Export,",
    "description": "City of Heroes (.geo)",
    "tracker_url": "https://git.ourodev.com/tigerkat/geopy/issues",
    "warning": "",
    "category": "Import-Export"}

def check_reload():
    if "bpy" in locals():
        import importlib
        if "import_geo" in locals():
            importlib.reload(import_geo)
        if "import_skel" in locals():
            importlib.reload(import_skel)
        if "import_anim" in locals():
            importlib.reload(import_anim)
        if "export_geo" in locals():
            importlib.reload(export_geo)
        if "export_skel" in locals():
            importlib.reload(export_skel)
        if "export_anim" in locals():
            importlib.reload(export_anim)
        if "geo" in locals():
            importlib.reload(geo)
        if "geomesh" in locals():
            importlib.reload(geomesh)
        if "vec_math" in locals():
            importlib.reload(vec_math)
check_reload()

## Python doesn't reload package sub-modules at the same time as __init__.py!
#import os.path
#import imp, sys
#for filename in [ f for f in os.listdir(os.path.dirname(os.path.realpath(__file__))) if f.endswith(".py") ]:
#    if filename == os.path.basename(__file__): continue
#    mod = sys.modules.get("{}.{}".format(__name__,filename[:-3]))
#    if mod: imp.reload(mod)

import mathutils
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    StringProperty,
)

from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper,
)

##############################################################################

class ImportGeo(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.geo"
    bl_label = "Import GEO"

    filename_ext = ".geo"
    filter_glob = StringProperty(default="*.geo", options={'HIDDEN'})
    def execute(self, context):
        from . import import_geo
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_geo.load(self, context, 1.0, **keywords)

class ImportGeoMetric(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene_metric.geo"
    bl_label = "Import GEO (Metric)"

    filename_ext = ".geo"
    filter_glob = StringProperty(default="*.geo", options={'HIDDEN'})
    def execute(self, context):
        from . import import_geo
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_geo.load(self, context, 0.30480000376701355, **keywords)

class ImportSkel(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.geo_skel"
    bl_label = "Import GEO Skeleton"

    filename_ext = ".anim"
    filter_glob = StringProperty(default="skel_*.anim", options={'HIDDEN'})
    def execute(self, context):
        from . import import_skel
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_skel.load(self, context, 1.0, **keywords)

class ImportAnim(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.geo_anim"
    bl_label = "Import GEO Animation"

    filename_ext = ".anim"
    filter_glob = StringProperty(default="*.anim", options={'HIDDEN'})
    def execute(self, context):
        from . import import_anim
        keywords = self.as_keywords(ignore=("filter_glob",))
        return import_anim.load(self, context, 1.0, **keywords)

class ExportGeo(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.geo"
    bl_label = "Export GEO"

    filename_ext = ".geo"
    filter_glob = StringProperty(default="*.geo", options={'HIDDEN'})
    def execute(self, context):
        from . import export_geo
        keywords = self.as_keywords(ignore=("filter_glob",
                                            "check_existing",
        ))
        return export_geo.save(self, context, 1.0, **keywords)

class ExportGeoMetric(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene_metric.geo"
    bl_label = "Export GEO (Metric)"

    filename_ext = ".geo"
    filter_glob = StringProperty(default="*.geo", options={'HIDDEN'})
    def execute(self, context):
        from . import export_geo
        keywords = self.as_keywords(ignore=("filter_glob",
                                            "check_existing",
        ))
        return export_geo.save(self, context, 1.0 / 0.30480000376701355, **keywords)

class ExportSkel(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.geo_skel"
    bl_label = "Export GEO Skeleton"

    filename_ext = ".anim"
    filter_glob = StringProperty(default="skel_*.anim", options={'HIDDEN'})
    def execute(self, context):
        from . import export_skel
        keywords = self.as_keywords(ignore=("filter_glob",
                                            "check_existing",
        ))
        return export_skel.save_skel(self, context, 1.0, **keywords)

class ExportAnim(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.geo_anim"
    bl_label = "Export GEO Animation"

    filename_ext = ".anim"
    filter_glob = StringProperty(default="*.anim", options={'HIDDEN'})
    def execute(self, context):
        from . import export_anim
        keywords = self.as_keywords(ignore=("filter_glob",
                                            "check_existing",
        ))
        return export_anim.save(self, context, 1.0, **keywords)

def menu_func_import(self, context):
    self.layout.operator(ImportGeo.bl_idname,
                         text="City of Heroes (Feet) (.geo)")
    self.layout.operator(ImportGeoMetric.bl_idname,
                         text="City of Heroes (Meters) (.geo)")
    self.layout.operator(ImportSkel.bl_idname,
                         text="City of Heroes Skeleton (skel_*.anim)")
    self.layout.operator(ImportAnim.bl_idname,
                         text="City of Heroes Animation (.anim)")

def menu_func_export(self, context):
    self.layout.operator(ExportGeo.bl_idname,
                         text="City of Heroes (Feet) (.geo)")
    self.layout.operator(ExportGeoMetric.bl_idname,
                         text="City of Heroes (Meters) (.geo)")
    self.layout.operator(ExportSkel.bl_idname,
                         text="City of Heroes Skeleton (skel_*.anim)")
    self.layout.operator(ExportAnim.bl_idname,
                         text="City of Heroes Animation (.anim)")

def make_annotations(cls):
    """Converts class fields to annotations if running with Blender 2.8"""
    if bpy.app.version < (2, 80):
        return cls
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls
classes = (
    ImportGeo,
    ImportGeoMetric,
    ImportSkel,
    ImportAnim,
    ExportGeo,
    ExportGeoMetric,
    ExportSkel,
    ExportAnim,
    )
def register():
    #bpy.utils.register_module(__name__)
    for cls in classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    #bpy.utils.unregister_module(__name__)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
