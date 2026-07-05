"""
Canonical CoH bind-pose skeletons for the standard humanoid body types.

City of Heroes does not ship a stand-alone skeleton/bind-pose asset in the
piggs — a character's rest skeleton is assembled at runtime from the base
animation ("male/skel_ready2" and friends). Every full-body animation, though,
carries each bone's constant local offset from its parent as the first key of
that bone's position track. Those offsets are identical across animations of a
given body type, so accumulating them down the standard hierarchy reproduces
the rest (T-pose) skeleton exactly.

The tables below were derived once from the game's own base animations
(mode of the frame-0 position key across ~25 full-body anims per body type,
restricted to the deform hierarchy in ``core.bones.STANDARD_HIERARCHY``). They
let the addon build an anatomically correct bind-pose armature for skinned
``.geo`` import without needing the piggs at import time.

Values are LOCAL offsets from the parent bone, in CoH game space
(left-handed, Y-up). Convert to Blender space with ``core.coords.game_to_blender``.
HIPS is anchored at the origin; character meshes are authored hip-centred, so an
origin-anchored HIPS overlays the mesh (see the validation notes in the repo
history — joints land on the mesh limbs to within a few cm).
"""

from .bones import STANDARD_HIERARCHY, BONE_PARENT


BODY_TYPES = ("male", "fem", "huge")
DEFAULT_BODY_TYPE = "male"


# Per-body-type local bone offsets from parent, in game space.
# Derived from player_library/animations/<body>/*.anim frame-0 position keys.
BIND_POSE_LOCAL = {
    "male": {
        "HIPS": (0.0, 0.0, 0.0),
        "WAIST": (0.0, 0.4228, 0.0498),
        "CHEST": (0.0, 0.4094, -0.1458),
        "NECK": (0.0, 0.7577, -0.0974),
        "HEAD": (0.0, 0.24, 0.0485),
        "COL_R": (0.26, 0.3941, -0.0522),
        "COL_L": (-0.26, 0.3941, -0.0522),
        "UARMR": (0.3518, 0.085, -0.0442),
        "UARML": (-0.3518, 0.085, -0.0442),
        "LARMR": (0.9142, -0.0019, 0.0346),
        "LARML": (-0.9142, -0.0019, 0.0346),
        "HANDR": (0.8177, 0.0006, -0.0185),
        "HANDL": (-0.8177, 0.0006, -0.0185),
        "F1_R": (0.0935, -0.0073, 0.0),
        "F1_L": (-0.0935, -0.0073, 0.0),
        "F2_R": (0.1452, -0.0165, 0.0),
        "F2_L": (-0.1452, -0.0165, 0.0),
        "T1_R": (0.0294, -0.0012, 0.1068),
        "T1_L": (-0.0294, -0.0012, 0.1068),
        "T2_R": (0.0231, -0.0074, 0.0999),
        "T2_L": (-0.0231, -0.0074, 0.0999),
        "T3_R": (0.0353, -0.0445, 0.0864),
        "T3_L": (-0.0353, -0.0445, 0.0864),
        "ULEGR": (0.2735, -0.2854, 0.0562),
        "ULEGL": (-0.273, -0.2854, 0.0566),
        "LLEGR": (0.0845, -1.4883, 0.1638),
        "LLEGL": (-0.1115, -1.4883, 0.1634),
        "FOOTR": (0.0006, -1.5112, -0.3794),
        "FOOTL": (-0.0006, -1.5112, -0.3794),
        "TOER": (0.0, -0.317, 0.3491),
        "TOEL": (0.0, -0.317, 0.3491),
        "BROW": (-0.0019, 0.121, 0.2949),
        "CHEEKS": (-0.002, 0.1707, 0.2898),
        "CHIN": (-0.002, -0.036, 0.2754),
        "CRANIUM": (0.0014, 0.1578, 0.1017),
        "JAW": (-0.002, 0.0712, 0.1444),
        "NOSE": (-0.002, 0.1482, 0.3746),
    },
    "fem": {
        "HIPS": (0.0, 0.0, 0.0),
        "WAIST": (0.0, 0.369, 0.0411),
        "CHEST": (0.0, 0.2879, -0.0692),
        "NECK": (0.0, 0.6039, -0.104),
        "HEAD": (0.0, 0.2087, 0.0143),
        "COL_R": (0.1702, 0.4135, -0.0536),
        "COL_L": (-0.1702, 0.4135, -0.0536),
        "UARMR": (0.2448, 0.0463, -0.0527),
        "UARML": (-0.2448, 0.0463, -0.0527),
        "LARMR": (0.7771, 0.0216, -0.0459),
        "LARML": (-0.7771, 0.0216, -0.0459),
        "HANDR": (0.7592, 0.0096, 0.0491),
        "HANDL": (-0.7592, 0.0096, 0.0491),
        "F1_R": (0.0612, -0.0116, 0.0),
        "F1_L": (-0.0612, -0.0116, 0.0),
        "F2_R": (0.0943, -0.0299, 0.0),
        "F2_L": (-0.0943, -0.0299, 0.0),
        "T1_R": (0.002, -0.0006, 0.1055),
        "T1_L": (-0.002, -0.0006, 0.1055),
        "T2_R": (0.0208, -0.0041, 0.0698),
        "T2_L": (-0.0208, -0.0041, 0.0698),
        "T3_R": (0.0194, -0.0463, 0.0476),
        "T3_L": (-0.0194, -0.0463, 0.0476),
        "ULEGR": (0.2381, -0.2301, 0.0201),
        "ULEGL": (-0.2381, -0.2301, 0.0201),
        "LLEGR": (0.0134, -1.3667, 0.133),
        "LLEGL": (-0.0134, -1.3667, 0.133),
        "FOOTR": (0.0538, -1.505, -0.3032),
        "FOOTL": (-0.0538, -1.505, -0.3032),
        "TOER": (0.0, -0.2543, 0.2607),
        "TOEL": (0.0, -0.2543, 0.2607),
        "BROW": (-0.0019, 0.121, 0.2949),
        "CHEEKS": (-0.002, 0.1707, 0.2898),
        "CHIN": (-0.002, -0.036, 0.2754),
        "CRANIUM": (0.0014, 0.1578, 0.1017),
        "JAW": (-0.002, 0.0712, 0.1444),
        "NOSE": (-0.002, 0.1482, 0.3746),
    },
    "huge": {
        "HIPS": (0.0, 0.0, 0.0),
        "WAIST": (0.0, 0.4228, 0.0498),
        "CHEST": (0.0, 0.4094, -0.1458),
        "NECK": (0.0, 0.9121, -0.0358),
        "HEAD": (0.0, 0.159, -0.0026),
        "COL_R": (0.452, 0.3941, -0.0522),
        "COL_L": (-0.452, 0.3941, -0.0522),
        "UARMR": (0.5048, 0.085, -0.2061),
        "UARML": (-0.505, 0.085, -0.2061),
        "LARMR": (0.9142, -0.0019, 0.0346),
        "LARML": (-0.9142, -0.0019, 0.0346),
        "HANDR": (0.8972, 0.0006, 0.0198),
        "HANDL": (-0.8967, 0.0006, 0.0203),
        "F1_R": (0.1237, -0.0073, 0.0),
        "F1_L": (-0.1237, -0.0073, 0.0),
        "F2_R": (0.1452, -0.0165, 0.0),
        "F2_L": (-0.1452, -0.0165, 0.0),
        "T1_R": (0.0294, -0.0012, 0.1068),
        "T1_L": (-0.0294, -0.0012, 0.099),
        "T2_R": (0.0045, -0.0074, 0.1322),
        "T2_L": (-0.005, -0.0074, 0.14),
        "T3_R": (0.1438, -0.0445, 0.192),
        "T3_L": (-0.1439, -0.0445, 0.192),
        "ULEGR": (0.3323, -0.4453, 0.0231),
        "ULEGL": (-0.332, -0.4453, 0.0235),
        "LLEGR": (0.0256, -1.4082, 0.1638),
        "LLEGL": (-0.026, -1.4082, 0.1634),
        "FOOTR": (0.0006, -1.3271, -0.5013),
        "FOOTL": (-0.0006, -1.3271, -0.5013),
        "TOER": (0.0, -0.408, 0.3491),
        "TOEL": (0.0, -0.408, 0.3491),
        "BROW": (-0.0019, 0.121, 0.2949),
        "CHEEKS": (-0.002, 0.1707, 0.2898),
        "CHIN": (-0.002, -0.036, 0.2754),
        "CRANIUM": (0.0014, 0.1578, 0.1017),
        "JAW": (-0.002, 0.0712, 0.1444),
        "NOSE": (-0.002, 0.1482, 0.3746),
    },
}


def resolve_body_type(body_type):
    """Normalise a body-type string to one of BODY_TYPES.

    Accepts common aliases ('female' -> 'fem'). Unknown values fall back to
    the default (male).
    """
    if not body_type:
        return DEFAULT_BODY_TYPE
    bt = body_type.strip().lower()
    if bt in BIND_POSE_LOCAL:
        return bt
    if bt in ("female", "woman", "f"):
        return "fem"
    if bt in ("male", "m", "man"):
        return "male"
    if bt in ("monster", "big", "large"):
        return "huge"
    return DEFAULT_BODY_TYPE


def guess_body_type(*hints):
    """Guess the CoH body type from filename/model-name hints.

    Returns one of BODY_TYPES, defaulting to 'male' when nothing matches.
    Checked in specificity order so 'female' beats the 'male' substring.
    """
    text = " ".join(h for h in hints if h).lower()
    if "female" in text or "_fem" in text or "/fem" in text or "_f_" in text or text.startswith("fem"):
        return "fem"
    if "huge" in text or "monster" in text or "_huge" in text:
        return "huge"
    return "male"


def bind_pose_world(body_type=DEFAULT_BODY_TYPE):
    """Compute world-space bind-pose bone positions for a body type.

    Accumulates each bone's local offset down ``STANDARD_HIERARCHY`` from HIPS
    (anchored at the origin). Bones without a tabulated offset sit on their
    parent (zero local offset), which keeps the parent chain intact for bones
    like FACE/EYES that aren't used for body-part skinning.

    Args:
        body_type: 'male', 'fem', or 'huge' (aliases accepted).

    Returns:
        dict {bone_name: (x, y, z)} in CoH game space, covering every bone in
        the standard deform hierarchy.
    """
    bt = resolve_body_type(body_type)
    local = BIND_POSE_LOCAL[bt]

    # Every bone in the standard deform hierarchy: parents (dict keys) and
    # their children.
    bones = set(STANDARD_HIERARCHY)
    for children in STANDARD_HIERARCHY.values():
        bones.update(children)

    world = {}

    def resolve(name):
        if name in world:
            return world[name]
        off = local.get(name, (0.0, 0.0, 0.0))
        parent = BONE_PARENT.get(name)
        if parent is None:
            pos = off
        else:
            pw = resolve(parent)
            pos = (pw[0] + off[0], pw[1] + off[1], pw[2] + off[2])
        world[name] = pos
        return pos

    for bone in bones:
        resolve(bone)

    return world
