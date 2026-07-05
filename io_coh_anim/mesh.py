"""
Blender mesh creation and extraction for CoH GEO files.

Converts between GEO binary format data classes and Blender mesh objects.
Handles coordinate conversion, UV mapping, material assignment, and
optional bone skinning.

Similar to armature.py but for geometry instead of animations.
"""

try:
    import bpy
    import bmesh
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False

from .formats.geo import GeoFile, GeoModel, GeoHeader, TexID, BoneInfo, MAX_OBJBONES
from .core.coords import game_to_blender, blender_to_game
import math
import os


# ─── Import: GEO → Blender ──────────────────────────────────────────────


def mesh_from_geo(context, geo_file, name="GEO_Import", texture_dir=None,
                  armature_obj=None):
    """Create Blender mesh objects from a GEO file.

    Args:
        context: Blender context
        geo_file: GeoFile data
        name: Base name for created objects
        texture_dir: Optional folder to search for `.texture`/`.dds` files
            matching each tex_name. If a match is found it's loaded as an
            image and wired into the material's Principled BSDF base color.
        armature_obj: Optional CoH armature to bind skinned meshes to. When
            given, each mesh with vertex groups is parented to it and gets an
            Armature modifier so it actually deforms.

    Returns:
        List of created Blender objects
    """
    objects = []

    tex_image_cache = {}
    for model in geo_file.models:
        obj = _create_mesh_object(
            context, model, geo_file.tex_names,
            texture_dir=texture_dir, tex_image_cache=tex_image_cache,
        )
        objects.append(obj)

    if armature_obj is not None:
        bind_meshes_to_armature(objects, armature_obj)

    return objects


def bind_meshes_to_armature(objects, armature_obj):
    """Parent skinned meshes to a CoH armature and add Armature modifiers.

    The importer already names vertex groups by CoH bone name, so binding is
    just wiring each mesh to the armature; the modifier matches groups to bones
    by name. Meshes without vertex groups are left untouched.

    Returns:
        Number of meshes bound.
    """
    if armature_obj is None or armature_obj.type != 'ARMATURE':
        return 0

    bound = 0
    for obj in objects:
        if obj.type != 'MESH' or not obj.vertex_groups:
            continue

        # Parent without moving the mesh in world space.
        obj.parent = armature_obj
        obj.matrix_parent_inverse = armature_obj.matrix_world.inverted()

        mod = next((m for m in obj.modifiers if m.type == 'ARMATURE'), None)
        if mod is None:
            mod = obj.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = armature_obj
        mod.use_vertex_groups = True
        bound += 1

    return bound


def _create_mesh_object(context, model, tex_names, texture_dir=None, tex_image_cache=None):
    """Create a single Blender mesh object from a GeoModel."""
    mesh = bpy.data.meshes.new(model.name)
    obj = bpy.data.objects.new(model.name, mesh)

    # Convert vertices from game to Blender coordinates
    verts = [game_to_blender(v) for v in model.vertices]
    # game_to_blender flips handedness (det = -1), so triangles wound CCW
    # in game space become CW in Blender. Reverse to keep them front-facing.
    faces = [(t[0], t[2], t[1]) for t in model.triangles]

    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # UV mapping
    if model.uvs:
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for poly in mesh.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                if vi < len(model.uvs):
                    u, v = model.uvs[vi]
                    # Blender UVs: flip V axis (game uses top-left origin)
                    uv_layer.data[li].uv = (u, 1.0 - v)

    # Secondary UV set
    if model.uvs2:
        uv_layer2 = mesh.uv_layers.new(name="UVMap2")
        for poly in mesh.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                if vi < len(model.uvs2):
                    u, v = model.uvs2[vi]
                    uv_layer2.data[li].uv = (u, 1.0 - v)

    # Create materials from texture names
    _assign_materials(mesh, model, tex_names, texture_dir=texture_dir, tex_image_cache=tex_image_cache)

    # Custom normals
    if model.normals:
        normals = [game_to_blender(n) for n in model.normals]
        # Set normals per-loop
        loop_normals = []
        for poly in mesh.polygons:
            for vi in poly.vertices:
                if vi < len(normals):
                    loop_normals.append(normals[vi])
                else:
                    loop_normals.append((0.0, 0.0, 1.0))
        mesh.normals_split_custom_set(loop_normals)

    # Link to scene
    context.collection.objects.link(obj)

    # Skinning (vertex groups from BoneInfo)
    if model.bone_info and model.bone_info.weights:
        _apply_skinning(obj, model)

    return obj


def _assign_materials(mesh, model, tex_names, texture_dir=None, tex_image_cache=None):
    """Assign materials based on TexID runs."""
    if not model.tex_ids:
        return

    # Create a material for each referenced texture
    mat_indices = {}
    for tex_id_entry in model.tex_ids:
        tid = tex_id_entry.id
        if tid not in mat_indices:
            tex_name = tex_names[tid] if tid < len(tex_names) else f"material_{tid}"
            mat = bpy.data.materials.get(tex_name) or bpy.data.materials.new(tex_name)
            if texture_dir:
                _wire_texture_into_material(mat, tex_name, texture_dir, tex_image_cache)
            mat_indices[tid] = len(mesh.materials)
            mesh.materials.append(mat)

    # Assign material index to each triangle based on TexID runs
    tri_idx = 0
    for tex_id_entry in model.tex_ids:
        mat_idx = mat_indices.get(tex_id_entry.id, 0)
        for _ in range(tex_id_entry.count):
            if tri_idx < len(mesh.polygons):
                mesh.polygons[tri_idx].material_index = mat_idx
            tri_idx += 1


def _resolve_texture_path(tex_name, texture_dir):
    """Find a texture file for `tex_name` under `texture_dir`. Returns path or None."""
    if not texture_dir or not os.path.isdir(texture_dir):
        return None
    candidates = [
        os.path.join(texture_dir, f"{tex_name}.texture"),
        os.path.join(texture_dir, "textures", f"{tex_name}.texture"),
        os.path.join(texture_dir, f"{tex_name}.dds"),
        os.path.join(texture_dir, "textures", f"{tex_name}.dds"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Case-insensitive fallback across the directory and a textures/ subfolder
    name_lower = tex_name.lower()
    for sub in ("", "textures"):
        scan_dir = os.path.join(texture_dir, sub) if sub else texture_dir
        if not os.path.isdir(scan_dir):
            continue
        for entry in os.listdir(scan_dir):
            stem, ext = os.path.splitext(entry)
            if ext.lower() in (".texture", ".dds") and stem.lower() == name_lower:
                return os.path.join(scan_dir, entry)
    return None


def _load_texture_image(tex_path, tex_name, tex_image_cache):
    """Load a `.texture` or `.dds` as a Blender Image and return it. Cached by name.

    Blender's built-in DDS loader is unreliable across versions, so we decode
    DXT1/DXT5 ourselves with `formats.dds.decompress_image` and feed raw
    pixels into a fresh Blender image.
    """
    if tex_image_cache is not None and tex_name in tex_image_cache:
        return tex_image_cache[tex_name]

    from .formats.dds import read_dds, decompress_image
    ext = os.path.splitext(tex_path)[1].lower()

    try:
        if ext == ".texture":
            from .formats.texture import read_texture
            tex_data = read_texture(tex_path)
            dds_bytes = tex_data.dds_data
        else:
            with open(tex_path, "rb") as f:
                dds_bytes = f.read()

        dds_info = read_dds(dds_bytes)
        width = dds_info['width']
        height = dds_info['height']
        fmt = dds_info['format']

        if fmt not in ('DXT1', 'DXT5'):
            print(f"[io_coh_anim] unsupported DDS format {fmt} for {tex_name}")
            if tex_image_cache is not None:
                tex_image_cache[tex_name] = None
            return None

        # Only base mip level needed
        from .formats.dds import dds_mip_size
        base_size = dds_mip_size(width, height, fmt)
        rgba = decompress_image(dds_info['pixel_data'][:base_size], width, height, fmt)
    except Exception as exc:
        print(f"[io_coh_anim] failed to decode texture {tex_path}: {exc}")
        if tex_image_cache is not None:
            tex_image_cache[tex_name] = None
        return None

    image_name = f"{tex_name}.dds"
    image = bpy.data.images.get(image_name)
    if image is None or image.size[0] != width or image.size[1] != height:
        image = bpy.data.images.new(image_name, width=width, height=height, alpha=(fmt == 'DXT5'))

    # Blender pixels: float 0..1, RGBA, row-major, BOTTOM-LEFT origin.
    # decompress_image returns top-left, so flip rows.
    flat = [0.0] * (width * height * 4)
    for y in range(height):
        src_y = height - 1 - y
        row_off = src_y * width
        dst_off = y * width * 4
        for x in range(width):
            r, g, b, a = rgba[row_off + x]
            flat[dst_off + x*4 + 0] = r / 255.0
            flat[dst_off + x*4 + 1] = g / 255.0
            flat[dst_off + x*4 + 2] = b / 255.0
            flat[dst_off + x*4 + 3] = a / 255.0
    image.pixels[:] = flat
    image.pack()
    image.update()

    if tex_image_cache is not None:
        tex_image_cache[tex_name] = image
    return image


def _wire_texture_into_material(mat, tex_name, texture_dir, tex_image_cache):
    """If a texture exists for `tex_name`, wire it into the material's Principled BSDF."""
    tex_path = _resolve_texture_path(tex_name, texture_dir)
    if tex_path is None:
        return

    image = _load_texture_image(tex_path, tex_name, tex_image_cache)
    if image is None:
        return

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Skip if we've already wired an image into this material
    for node in nodes:
        if node.type == 'TEX_IMAGE' and node.image == image:
            return

    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)

    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = image
    tex_node.location = (-400, 0)

    base_color_input = bsdf.inputs.get('Base Color') or bsdf.inputs.get('Color')
    if base_color_input is not None:
        links.new(tex_node.outputs['Color'], base_color_input)

    # Hook up alpha if the .texture flagged it
    tex_path_lower = tex_path.lower()
    if tex_path_lower.endswith(".texture"):
        try:
            from .formats.texture import read_texture
            if read_texture(tex_path).alpha:
                alpha_input = bsdf.inputs.get('Alpha')
                if alpha_input is not None:
                    links.new(tex_node.outputs['Alpha'], alpha_input)
                mat.blend_method = 'CLIP'
        except Exception:
            pass


def _apply_skinning(obj, model):
    """Apply bone skinning data from GeoModel.bone_info to vertex groups.

    Each vertex carries a primary/secondary matrix-palette slot (matidxs) and a
    blend weight. The slot is a *local* bone index * 3, so we divide by 3 to
    index bone_info.bone_ids, which maps to the game BoneId. Vertex groups are
    named by CoH bone name (HIPS, UARMR, ...) so they line up with an imported
    armature; unknown IDs fall back to "bone_<id>".
    """
    from .core.bones import bone_name_from_id

    bi = model.bone_info
    if not bi or not bi.matidxs or not bi.weights or not bi.bone_ids:
        return

    bone_ids = bi.bone_ids
    group_cache = {}

    def _group_for(local):
        """Vertex group for a local bone slot, created on demand."""
        if local < 0 or local >= len(bone_ids):
            return None
        if local in group_cache:
            return group_cache[local]
        bid = bone_ids[local]
        name = bone_name_from_id(bid) or f"bone_{bid}"
        vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        group_cache[local] = vg
        return vg

    n = min(model.vert_count, len(bi.matidxs), len(bi.weights))
    for vi in range(n):
        idx0, idx1 = bi.matidxs[vi]
        weight = bi.weights[vi]

        local0 = idx0 // 3
        g0 = _group_for(local0)
        if g0 is not None and weight > 0.0:
            g0.add([vi], weight, 'REPLACE')

        # Secondary influence gets the remainder, unless it's the same bone.
        local1 = idx1 // 3
        if weight < 1.0 and local1 != local0:
            g1 = _group_for(local1)
            if g1 is not None:
                g1.add([vi], 1.0 - weight, 'REPLACE')


# ─── Export: Blender → GEO ──────────────────────────────────────────────


def geo_from_mesh(context, objects, geo_name="custom"):
    """Create a GeoFile from selected Blender mesh objects.

    Args:
        context: Blender context
        objects: List of Blender mesh objects
        geo_name: Name for the GEO file header

    Returns:
        GeoFile ready for writing
    """
    all_tex_names = []
    tex_name_map = {}
    models = []

    for obj in objects:
        if obj.type != 'MESH':
            continue

        model = _extract_mesh(context, obj, all_tex_names, tex_name_map)
        models.append(model)

    obj_names = [m.name for m in models]

    return GeoFile(
        version=8,
        headers=[GeoHeader(name=f"{geo_name}.wrl", model_count=len(models))],
        models=models,
        tex_names=all_tex_names,
        obj_names=obj_names,
    )


def _get_loop_normal_func(mesh):
    """Return a function that reads the loop normal for a given loop index.

    Blender 4.1+ removed calc_normals_split() in favour of corner_normals.
    """
    if hasattr(mesh, 'corner_normals'):
        # Blender 4.1+
        cn = mesh.corner_normals
        def _get(li):
            v = cn[li].vector
            return (v[0], v[1], v[2])
        return _get
    else:
        # Blender 4.0
        mesh.calc_normals_split()
        def _get(li):
            n = mesh.loops[li].normal
            return (n[0], n[1], n[2])
        return _get


def _extract_mesh(context, obj, all_tex_names, tex_name_map):
    """Extract GeoModel data from a Blender mesh object.

    Uses vertex splitting to produce per-vertex normals and UVs compatible
    with the GEO format.  Vertices are duplicated wherever loop normals or
    UVs differ (UV seams, hard edges, etc.) — the same approach 3DS Max
    used when exporting VRML for GetVrml.
    """
    # Get evaluated mesh (apply modifiers)
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    # Triangulate
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.calc_loop_triangles()

    # Prepare loop-normal reader
    get_loop_normal = _get_loop_normal_func(mesh)

    # UV layers
    uv_layer = mesh.uv_layers[0] if len(mesh.uv_layers) > 0 else None
    uv_layer2 = mesh.uv_layers[1] if len(mesh.uv_layers) > 1 else None

    # ── Vertex splitting ─────────────────────────────────────────────
    # Build unique (position, normal, uv, uv2) vertices from loop data.
    # GEO stores one normal and one UV per vertex, so we duplicate
    # vertices wherever those attributes diverge across face-corners.

    vert_map = {}   # (blender_vi, n_key, uv_key, uv2_key) → new index
    vertices = []
    normals = []
    uvs = []
    uvs2 = []
    src_vidx = []   # source Blender vertex index per output vertex (for skinning)

    # Rounding tolerances — well below GEO quantisation precision
    # (normals: 1/256 ≈ 0.0039, UV1: 1/4096 ≈ 0.00024, UV2: 1/32768)
    def _rn(v):
        return (round(v[0], 4), round(v[1], 4), round(v[2], 4))

    def _ruv(v):
        return (round(v[0], 5), round(v[1], 5))

    def _split_vertex(vi, loop_idx):
        """Return the split-vertex index for this face-corner."""
        n = get_loop_normal(loop_idx)
        n_key = _rn(n)

        if uv_layer:
            raw = uv_layer.data[loop_idx].uv
            uv = (raw[0], 1.0 - raw[1])
            uv_key = _ruv(uv)
        else:
            uv = (0.0, 0.0)
            uv_key = uv

        if uv_layer2:
            raw2 = uv_layer2.data[loop_idx].uv
            uv2 = (raw2[0], 1.0 - raw2[1])
            uv2_key = _ruv(uv2)
        else:
            uv2 = None
            uv2_key = None

        key = (vi, n_key, uv_key, uv2_key)
        idx = vert_map.get(key)
        if idx is not None:
            return idx

        idx = len(vertices)
        vert_map[key] = idx
        src_vidx.append(vi)

        co = mesh.vertices[vi].co
        vertices.append(blender_to_game((co.x, co.y, co.z)))
        normals.append(blender_to_game(n))
        uvs.append(uv)
        if uv_layer2:
            uvs2.append(uv2)

        return idx

    # ── Build triangles with split vertices, grouped by material ─────
    mat_groups = {}
    for poly in mesh.polygons:
        mi = poly.material_index
        tri = tuple(
            _split_vertex(vi, li)
            for li, vi in zip(poly.loop_indices, poly.vertices)
        )
        # blender_to_game flips handedness, so reverse winding to keep
        # triangles front-facing in game space.
        tri = (tri[0], tri[2], tri[1])
        if mi not in mat_groups:
            mat_groups[mi] = []
        mat_groups[mi].append(tri)

    # ── Sorted triangle list and TexID runs ──────────────────────────
    triangles = []
    tex_ids = []

    for mi in sorted(mat_groups.keys()):
        tris = mat_groups[mi]

        if mi < len(mesh.materials) and mesh.materials[mi]:
            tex_name = mesh.materials[mi].name
        else:
            tex_name = "white"

        if tex_name not in tex_name_map:
            tex_name_map[tex_name] = len(all_tex_names)
            all_tex_names.append(tex_name)

        tid = tex_name_map[tex_name]
        tex_ids.append(TexID(id=tid, count=len(tris)))
        triangles.extend(tris)

    # ── Bounding box ─────────────────────────────────────────────────
    if vertices:
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        zs = [v[2] for v in vertices]
        min_bound = (min(xs), min(ys), min(zs))
        max_bound = (max(xs), max(ys), max(zs))
        radius = max(math.sqrt(x*x + y*y + z*z) for x, y, z in vertices)
    else:
        min_bound = (0.0, 0.0, 0.0)
        max_bound = (0.0, 0.0, 0.0)
        radius = 0.0

    # Skinning: read vertex-group weights back into a BoneInfo (or None).
    bone_info = _extract_skin_weights(obj, mesh, src_vidx)

    model = GeoModel(
        name=obj.name,
        radius=radius,
        min=min_bound,
        max=max_bound,
        vert_count=len(vertices),
        tri_count=len(triangles),
        vertices=vertices,
        normals=normals,
        uvs=uvs,
        uvs2=uvs2,
        triangles=triangles,
        tex_ids=tex_ids,
        bone_info=bone_info,
    )

    eval_obj.to_mesh_clear()
    return model


def _extract_skin_weights(obj, mesh, src_vidx):
    """Build a BoneInfo from Blender vertex groups for GEO export.

    Mirrors the import path: vertex groups named after CoH bones map back to
    game BoneIds. Each vertex keeps its top two influences (CoH stores a
    primary/secondary matrix slot per vertex); the blend weight is the primary
    fraction. The local bone table is capped at MAX_OBJBONES, keeping the
    most-referenced bones. Returns None if the mesh has no CoH-bone groups.
    """
    from collections import Counter
    from .core.bones import bone_id_from_name

    # Blender group index → game BoneId, for groups whose name is a CoH bone.
    grp_bone = {}
    for vg in obj.vertex_groups:
        bid = bone_id_from_name(vg.name)
        if bid >= 0:
            grp_bone[vg.index] = bid
    if not grp_bone:
        return None

    # Top-two CoH influences per output (split) vertex.
    out_infl = []
    for vi in src_vidx:
        infl = [
            (grp_bone[g.group], g.weight)
            for g in mesh.vertices[vi].groups
            if g.group in grp_bone and g.weight > 0.0
        ]
        infl.sort(key=lambda bw: -bw[1])
        out_infl.append(infl[:2])

    # Local bone table, capped at MAX_OBJBONES by reference count.
    usage = Counter(bid for infl in out_infl for bid, _ in infl)
    if not usage:
        return None
    kept_bones = [bid for bid, _ in usage.most_common(MAX_OBJBONES)]
    slot_of = {bid: i for i, bid in enumerate(kept_bones)}

    weights = []
    matidxs = []
    for infl in out_infl:
        infl = [(bid, w) for bid, w in infl if bid in slot_of]
        if not infl:
            # Unweighted after capping: pin to the first (most-used) bone.
            weights.append(1.0)
            matidxs.append((0, 0))
            continue
        b0, w0 = infl[0]
        s0 = slot_of[b0]
        if len(infl) > 1:
            b1, w1 = infl[1]
            s1 = slot_of[b1]
            total = w0 + w1
            primary = w0 / total if total > 0 else 1.0
        else:
            s1, primary = s0, 1.0
        weights.append(min(1.0, max(0.0, primary)))
        # Matrix-palette slots are the local bone index * 3 (see reader).
        matidxs.append((s0 * 3, s1 * 3))

    return BoneInfo(
        numbones=len(kept_bones),
        bone_ids=kept_bones,
        weights=weights,
        matidxs=matidxs,
    )
