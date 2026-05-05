"""
Coordinate system conversions between Blender/3DS Max and the CoH game engine.

Blender & 3DS Max: Right-handed, Z-up  (X=right, Y=forward, Z=up)
CoH Game Engine:   Left-handed, Y-up   (X=left,  Y=up,      Z=forward)

Conversion (from processanim.c ConvertCoordsFrom3DSMAX):
  game.x = -source.x
  game.y =  source.z
  game.z = -source.y

Note: Blender and 3DS Max share the same handedness and up-axis,
so the same conversion applies for both.
"""


def blender_to_game(vec):
    """Convert a position/axis vector from Blender space to CoH game space.

    Args:
        vec: (x, y, z) in Blender coordinates

    Returns:
        (x, y, z) in game coordinates
    """
    return (-vec[0], vec[2], -vec[1])


def game_to_blender(vec):
    """Convert a position/axis vector from CoH game space to Blender space.

    Args:
        vec: (x, y, z) in game coordinates

    Returns:
        (x, y, z) in Blender coordinates
    """
    return (-vec[0], -vec[2], vec[1])


# Aliases - 3DS Max uses the same coordinate system as Blender
max_to_game = blender_to_game
game_to_max = game_to_blender


def blender_to_max(vec):
    """Blender and 3DS Max share the same coordinate convention.

    Both are right-handed Z-up, so this is identity.
    """
    return (vec[0], vec[1], vec[2])


def max_to_blender(vec):
    """3DS Max and Blender share the same coordinate convention.

    Both are right-handed Z-up, so this is identity.
    """
    return (vec[0], vec[1], vec[2])
