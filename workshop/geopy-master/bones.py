

#List of bone ids. Should be kept strictly ordered.
BONES_LIST = [
    "Hips",
    "Waist",
    "Chest",
    "Neck",
    "Head",
    "Col_R",
    "Col_L",
    "UarmR",
    "UarmL",
    "LarmR",
    "LarmL",
    "HandR",
    "HandL",
    "F1_R",
    "F1_L",
    "F2_R",
    "F2_L",
    "T1_R",
    "T1_L",
    "T2_R",
    "T2_L",
    "T3_R",
    "T3_L",
    "UlegR",
    "UlegL",
    "LlegR",
    "LlegL",
    "FootR",
    "FootL",
    "ToeR",
    "ToeL",

    "Face",
    "Dummy",
    "Breast",
    "Belt",
    "GloveL",
    "GloveR",
    "BootL",
    "BootR",
    "RingL",
    "RingR",
    "WepL",
    "WepR",
    "Hair",
    "Eyes",
    "Emblem",
    "SpadL",
    "SpadR",
    "Back",
    "Neckline",
    "ClawL",
    "ClawR",
    "Gun",

    "RWing1",
    "RWing2",
    "RWing3",
    "RWing4",

    "LWing1",
    "LWing2",
    "LWing3",
    "LWing4",

    "Mystic",

    "SleeveL",
    "SleeveR",
    "Robe",
    "BendMystic",

    "Collar",
    "Broach",

    "BosomR",
    "BosomL",

    "Top",
    "Skirt",
    "Sleeves",

    "Brow",
    "Cheeks",
    "Chin",
    "Cranium",
    "Jaw",
    "Nose",

    "Hind_UlegL",
    "Hind_LlegL",
    "Hind_FootL",
    "Hind_ToeL",
    "Hind_UlegR",
    "Hind_LlegR",
    "Hind_FootR",
    "Hind_ToeR",
    "Fore_UlegL",
    "Fore_LlegL",
    "Fore_FootL",
    "Fore_ToeL",
    "Fore_UlegR",
    "Fore_LlegR",
    "Fore_FootR",
    "Fore_ToeR",

    "Leg_L_Jet1",
    "Leg_L_Jet2",
    "Leg_R_Jet1",
    "Leg_R_Jet2",
]

BONES_ON_DISK = 100

BONES_LEFT = []
BONES_RIGHT = []
BONES_SWAP = []

BONES_LOOKUP = {}

for i in range(len(BONES_LIST)):
    BONES_LOOKUP[BONES_LIST[i]] = i
    BONES_LOOKUP[BONES_LIST[i].upper()] = i
    BONES_LOOKUP[BONES_LIST[i].lower()] = i
    if BONES_LIST[i][-1] == "L" or BONES_LIST[i].startswith("LWing"):
        BONES_LEFT.append(BONES_LIST[i])
    if BONES_LIST[i][-1] == "R" or BONES_LIST[i].startswith("RWing"):
        BONES_RIGHT.append(BONES_LIST[i])
for i in range(len(BONES_LIST)):
    j = i
    n = BONES_LIST[i]
    if n in BONES_LEFT:
        n = BONES_RIGHT[BONES_LEFT.index(n)]
        j = BONES_LOOKUP[n]
    elif n in BONES_RIGHT:
        n = BONES_LEFT[BONES_RIGHT.index(n)]
        j = BONES_LOOKUP[n]
    BONES_SWAP.append(j)
