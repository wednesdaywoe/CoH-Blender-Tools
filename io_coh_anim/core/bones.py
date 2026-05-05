"""
City of Heroes bone ID definitions and skeleton hierarchy.

Bone names and IDs match the game engine's BoneId enum (Common/seq/bones.h).
The AUTO_ENUM macro strips the 'BONEID_' prefix to create runtime name strings.
"""

# Maximum bones stored in binary .anim files
BONES_ON_DISK = 100

# Bone names in enum order (index = bone ID)
BONE_NAMES = [
    "HIPS",          # 0  - Root/pelvis
    "WAIST",         # 1  - Lower torso
    "CHEST",         # 2  - Upper torso
    "NECK",          # 3
    "HEAD",          # 4
    "COL_R",         # 5  - Right clavicle
    "COL_L",         # 6  - Left clavicle
    "UARMR",         # 7  - Right upper arm
    "UARML",         # 8  - Left upper arm
    "LARMR",         # 9  - Right forearm
    "LARML",         # 10 - Left forearm
    "HANDR",         # 11 - Right hand
    "HANDL",         # 12 - Left hand
    "F1_R",          # 13 - Right index finger
    "F1_L",          # 14 - Left index finger
    "F2_R",          # 15 - Right middle finger
    "F2_L",          # 16 - Left middle finger
    "T1_R",          # 17 - Right ring finger
    "T1_L",          # 18 - Left ring finger
    "T2_R",          # 19 - Right pinky
    "T2_L",          # 20 - Left pinky
    "T3_R",          # 21 - Right thumb
    "T3_L",          # 22 - Left thumb
    "ULEGR",         # 23 - Right upper leg
    "ULEGL",         # 24 - Left upper leg
    "LLEGR",         # 25 - Right lower leg
    "LLEGL",         # 26 - Left lower leg
    "FOOTR",         # 27 - Right foot
    "FOOTL",         # 28 - Left foot
    "TOER",          # 29 - Right toe
    "TOEL",          # 30 - Left toe
    "FACE",          # 31
    "DUMMY",         # 32
    "BREAST",        # 33
    "BELT",          # 34
    "GLOVEL",        # 35 - Left glove
    "GLOVER",        # 36 - Right glove
    "BOOTL",         # 37 - Left boot
    "BOOTR",         # 38 - Right boot
    "RINGL",         # 39 - Left ring
    "RINGR",         # 40 - Right ring
    "WEPL",          # 41 - Left weapon
    "WEPR",          # 42 - Right weapon
    "HAIR",          # 43
    "EYES",          # 44
    "EMBLEM",        # 45
    "SPADL",         # 46 - Left shoulder pad
    "SPADR",         # 47 - Right shoulder pad
    "BACK",          # 48
    "NECKLINE",      # 49
    "CLAWL",         # 50 - Left claw
    "CLAWR",         # 51 - Right claw
    "GUN",           # 52
    "RWING1",        # 53
    "RWING2",        # 54
    "RWING3",        # 55
    "RWING4",        # 56
    "LWING1",        # 57
    "LWING2",        # 58
    "LWING3",        # 59
    "LWING4",        # 60
    "MYSTIC",        # 61
    "SLEEVEL",       # 62 - Left sleeve
    "SLEEVER",       # 63 - Right sleeve
    "ROBE",          # 64
    "BENDMYSTIC",    # 65
    "COLLAR",        # 66
    "BROACH",        # 67
    "BOSOMR",        # 68 - Right bosom
    "BOSOML",        # 69 - Left bosom
    "TOP",           # 70 - Shirt/top
    "SKIRT",         # 71
    "SLEEVES",       # 72
    "BROW",          # 73
    "CHEEKS",        # 74
    "CHIN",          # 75
    "CRANIUM",       # 76
    "JAW",           # 77
    "NOSE",          # 78
    "HIND_ULEGL",    # 79 - Quadruped hind left upper leg
    "HIND_LLEGL",    # 80
    "HIND_FOOTL",    # 81
    "HIND_TOEL",     # 82
    "HIND_ULEGR",    # 83 - Quadruped hind right upper leg
    "HIND_LLEGR",    # 84
    "HIND_FOOTR",    # 85
    "HIND_TOER",     # 86
    "FORE_ULEGL",    # 87 - Quadruped fore left upper leg
    "FORE_LLEGL",    # 88
    "FORE_FOOTL",    # 89
    "FORE_TOEL",     # 90
    "FORE_ULEGR",    # 91 - Quadruped fore right upper leg
    "FORE_LLEGR",    # 92
    "FORE_FOOTR",    # 93
    "FORE_TOER",     # 94
    "LEG_L_JET1",    # 95
    "LEG_L_JET2",    # 96
    "LEG_R_JET1",    # 97
    "LEG_R_JET2",    # 98
]

BONEID_COUNT = len(BONE_NAMES)  # 99 (0-98), game has 119 but we match what's in bones.h enum

# Name → ID lookup (case-insensitive)
BONE_ID = {name.upper(): i for i, name in enumerate(BONE_NAMES)}

# ID → Name lookup
BONE_NAME = {i: name for i, name in enumerate(BONE_NAMES)}


def bone_id_from_name(name: str) -> int:
    """Get bone ID from name. Returns -1 if not found. Case-insensitive."""
    return BONE_ID.get(name.upper(), -1)


def bone_name_from_id(bone_id: int) -> str | None:
    """Get bone name from ID. Returns None if invalid."""
    return BONE_NAME.get(bone_id)


def bone_id_is_valid(bone_id: int) -> bool:
    """Check if a bone ID is valid."""
    return 0 <= bone_id < BONEID_COUNT


# Standard male humanoid hierarchy: parent → [children]
# Derived from the CoH skeleton structure (SM_Master.max rig)
STANDARD_HIERARCHY = {
    "HIPS": ["WAIST", "ULEGR", "ULEGL"],
    "WAIST": ["CHEST"],
    "CHEST": ["NECK", "COL_R", "COL_L"],
    "NECK": ["HEAD"],
    "HEAD": ["FACE"],
    "FACE": ["BROW", "CHEEKS", "CHIN", "CRANIUM", "JAW", "NOSE", "EYES"],
    "COL_R": ["UARMR"],
    "COL_L": ["UARML"],
    "UARMR": ["LARMR"],
    "UARML": ["LARML"],
    "LARMR": ["HANDR"],
    "LARML": ["HANDL"],
    "HANDR": ["F1_R", "F2_R", "T1_R"],
    "HANDL": ["F1_L", "F2_L", "T1_L"],
    "T1_R": ["T2_R"],
    "T1_L": ["T2_L"],
    "T2_R": ["T3_R"],
    "T2_L": ["T3_L"],
    "ULEGR": ["LLEGR"],
    "ULEGL": ["LLEGL"],
    "LLEGR": ["FOOTR"],
    "LLEGL": ["FOOTL"],
    "FOOTR": ["TOER"],
    "FOOTL": ["TOEL"],
}

# Reverse lookup: child → parent
BONE_PARENT = {}
for parent, children in STANDARD_HIERARCHY.items():
    for child in children:
        BONE_PARENT[child] = parent
