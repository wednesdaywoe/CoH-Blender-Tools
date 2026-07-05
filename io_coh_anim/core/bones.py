"""
City of Heroes bone ID definitions and skeleton hierarchy.

Bone names and IDs match the game engine's BoneId enum (Common/seq/bones.h).
The AUTO_ENUM macro strips the 'BONEID_' prefix to create runtime name strings.
"""

# Maximum bones stored in binary .anim files
BONES_ON_DISK = 100

# Bone names in enum order (index = bone ID)
BONE_NAMES = [
    "Hips",          # 0  - Root/pelvis
    "Waist",         # 1  - Lower torso
    "Chest",         # 2  - Upper torso
    "Neck",          # 3
    "Head",          # 4
    "Col_R",         # 5  - Right clavicle
    "Col_L",         # 6  - Left clavicle
    "UarmR",         # 7  - Right upper arm
    "UarmL",         # 8  - Left upper arm
    "LarmR",         # 9  - Right forearm
    "LarmL",         # 10 - Left forearm
    "HandR",         # 11 - Right hand
    "HandL",         # 12 - Left hand
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
    "UlegR",         # 23 - Right upper leg
    "UlegL",         # 24 - Left upper leg
    "LlegR",         # 25 - Right lower leg
    "LlegL",         # 26 - Left lower leg
    "FootR",         # 27 - Right foot
    "FootL",         # 28 - Left foot
    "ToeR",          # 29 - Right toe
    "ToeL",          # 30 - Left toe
    "Face",          # 31
    "Dummy",         # 32
    "Breast",        # 33
    "Belt",          # 34
    "GloveL",        # 35 - Left glove
    "GloveR",        # 36 - Right glove
    "BootL",         # 37 - Left boot
    "BootR",         # 38 - Right boot
    "RingL",         # 39 - Left ring
    "RingR",         # 40 - Right ring
    "WepL",          # 41 - Left weapon
    "WepR",          # 42 - Right weapon
    "Hair",          # 43
    "Eyes",          # 44
    "Emblem",        # 45
    "SpadL",         # 46 - Left shoulder pad
    "SpadR",         # 47 - Right shoulder pad
    "Back",          # 48
    "Neckline",      # 49
    "ClawL",         # 50 - Left claw
    "ClawR",         # 51 - Right claw
    "Gun",           # 52
    "RWing1",        # 53
    "RWing2",        # 54
    "RWing3",        # 55
    "RWing4",        # 56
    "LWing1",        # 57
    "LWing2",        # 58
    "LWing3",        # 59
    "LWing4",        # 60
    "Mystic",        # 61
    "SleeveL",       # 62 - Left sleeve
    "SleeveR",       # 63 - Right sleeve
    "Robe",          # 64
    "BendMystic",    # 65
    "Collar",        # 66
    "Broach",        # 67
    "BosomR",        # 68 - Right bosom
    "BosomL",        # 69 - Left bosom
    "Top",           # 70 - Shirt/top
    "Skirt",         # 71
    "Sleeves",       # 72
    "Brow",          # 73
    "Cheeks",        # 74
    "Chin",          # 75
    "Cranium",       # 76
    "Jaw",           # 77
    "Nose",          # 78
    "Hind_UlegL",    # 79 - Quadruped hind left upper leg
    "Hind_LlegL",    # 80
    "Hind_FootL",    # 81
    "Hind_ToeL",     # 82
    "Hind_UlegR",    # 83 - Quadruped hind right upper leg
    "Hind_LlegR",    # 84
    "Hind_FootR",    # 85
    "Hind_ToeR",     # 86
    "Fore_UlegL",    # 87 - Quadruped fore left upper leg
    "Fore_LlegL",    # 88
    "Fore_FootL",    # 89
    "Fore_ToeL",     # 90
    "Fore_UlegR",    # 91 - Quadruped fore right upper leg
    "Fore_LlegR",    # 92
    "Fore_FootR",    # 93
    "Fore_ToeR",     # 94
    "Leg_L_Jet1",    # 95
    "Leg_L_Jet2",    # 96
    "Leg_R_Jet1",    # 97
    "Leg_R_Jet2",    # 98
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
    "Hips": ["Waist", "UlegR", "UlegL"],
    "Waist": ["Chest"],
    "Chest": ["Neck", "Col_R", "Col_L"],
    "Neck": ["Head"],
    "Head": ["Face"],
    "Face": ["Brow", "Cheeks", "Chin", "Cranium", "Jaw", "Nose", "Eyes"],
    "Col_R": ["UarmR"],
    "Col_L": ["UarmL"],
    "UarmR": ["LarmR"],
    "UarmL": ["LarmL"],
    "LarmR": ["HandR"],
    "LarmL": ["HandL"],
    "HandR": ["F1_R", "F2_R", "T1_R"],
    "HandL": ["F1_L", "F2_L", "T1_L"],
    "T1_R": ["T2_R"],
    "T1_L": ["T2_L"],
    "T2_R": ["T3_R"],
    "T2_L": ["T3_L"],
    "UlegR": ["LlegR"],
    "UlegL": ["LlegL"],
    "LlegR": ["FootR"],
    "LlegL": ["FootL"],
    "FootR": ["ToeR"],
    "FootL": ["ToeL"],
}

# Reverse lookup: child → parent
BONE_PARENT = {}
for parent, children in STANDARD_HIERARCHY.items():
    for child in children:
        BONE_PARENT[child] = parent
