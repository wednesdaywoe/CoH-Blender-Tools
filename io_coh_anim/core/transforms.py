"""
Quaternion, axis-angle, and transform math for CoH animation data.

Provides pure-Python math that works outside Blender (for testing).
When running inside Blender, mathutils types are compatible with these functions.

Key CoH conventions:
- Axis-angle to quaternion conversion NEGATES the angle (from process_animx.c)
- World-to-local: qLocal = inverse(qParent) * qChild
- Position local: pLocal = rotate(inverse(qParent), pChild - pParent)
"""

import math


def normalize_quat(q):
    """Normalize a quaternion (w, x, y, z) to unit length."""
    w, x, y, z = q
    length = math.sqrt(w * w + x * x + y * y + z * z)
    if length < 1e-10:
        return (1.0, 0.0, 0.0, 0.0)
    inv = 1.0 / length
    return (w * inv, x * inv, y * inv, z * inv)


def axis_angle_to_quat(axis, angle):
    """Convert axis-angle to quaternion (w, x, y, z).

    Applies the CoH convention of NEGATING the angle, matching:
        axisAngleToQuat(axis, -angle, quat)
    from process_animx.c.

    Args:
        axis: (x, y, z) rotation axis (will be normalized)
        angle: rotation angle in radians

    Returns:
        (w, x, y, z) quaternion
    """
    # CoH negates the angle during conversion
    angle = -angle

    ax, ay, az = axis
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length < 1e-10:
        return (1.0, 0.0, 0.0, 0.0)

    inv = 1.0 / length
    ax *= inv
    ay *= inv
    az *= inv

    half = angle * 0.5
    s = math.sin(half)
    w = math.cos(half)
    return (w, ax * s, ay * s, az * s)


def quat_to_axis_angle(q):
    """Convert quaternion (w, x, y, z) to axis-angle.

    Applies the inverse of the CoH angle negation convention.

    Returns:
        (axis, angle) where axis is (x, y, z) and angle is in radians
    """
    w, x, y, z = normalize_quat(q)

    # Clamp w to avoid NaN from acos
    w = max(-1.0, min(1.0, w))
    half_angle = math.acos(abs(w))
    angle = 2.0 * half_angle

    s = math.sin(half_angle)
    if s < 1e-10:
        # Near-zero rotation, axis is arbitrary
        return ((0.0, 0.0, 1.0), 0.0)

    inv_s = 1.0 / s
    if w < 0:
        inv_s = -inv_s

    axis = (x * inv_s, y * inv_s, z * inv_s)

    # Negate angle back (inverse of the CoH convention)
    angle = -angle

    return (axis, angle)


def quat_multiply(a, b):
    """Multiply two quaternions: result = a * b. Hamilton product.

    Args:
        a, b: (w, x, y, z) quaternions

    Returns:
        (w, x, y, z) quaternion
    """
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quat_inverse(q):
    """Inverse of a unit quaternion (conjugate)."""
    w, x, y, z = q
    return (w, -x, -y, -z)


def quat_rotate_vec(q, v):
    """Rotate a vector by a quaternion.

    Args:
        q: (w, x, y, z) unit quaternion
        v: (x, y, z) vector

    Returns:
        (x, y, z) rotated vector
    """
    # q * v_quat * q_inv, where v_quat = (0, vx, vy, vz)
    vq = (0.0, v[0], v[1], v[2])
    result = quat_multiply(quat_multiply(q, vq), quat_inverse(q))
    return (result[1], result[2], result[3])


def world_to_local(parent_quat, parent_pos, child_quat, child_pos):
    """Convert child world-space transform to parent-local space.

    This matches the GetAnimation2 animxTransformJointKeysRelative() logic:
        qLocal = inverse(qParent) * qChild
        pLocal = rotate(inverse(qParent), pChild - pParent)

    Args:
        parent_quat: (w, x, y, z) parent world rotation
        parent_pos: (x, y, z) parent world position
        child_quat: (w, x, y, z) child world rotation
        child_pos: (x, y, z) child world position

    Returns:
        (local_quat, local_pos) in parent-local space
    """
    parent_inv = quat_inverse(parent_quat)

    # Local rotation = inverse(parent) * child
    local_quat = quat_multiply(parent_inv, child_quat)

    # Local position = rotate(inverse(parent), child_pos - parent_pos)
    diff = (
        child_pos[0] - parent_pos[0],
        child_pos[1] - parent_pos[1],
        child_pos[2] - parent_pos[2],
    )
    local_pos = quat_rotate_vec(parent_inv, diff)

    return (local_quat, local_pos)


def local_to_world(parent_quat, parent_pos, local_quat, local_pos):
    """Convert parent-local transform to world space. Inverse of world_to_local.

    Args:
        parent_quat: (w, x, y, z) parent world rotation
        parent_pos: (x, y, z) parent world position
        local_quat: (w, x, y, z) local rotation relative to parent
        local_pos: (x, y, z) local position relative to parent

    Returns:
        (world_quat, world_pos) in world space
    """
    # World rotation = parent * local
    world_quat = quat_multiply(parent_quat, local_quat)

    # World position = parent_pos + rotate(parent, local_pos)
    rotated = quat_rotate_vec(parent_quat, local_pos)
    world_pos = (
        parent_pos[0] + rotated[0],
        parent_pos[1] + rotated[1],
        parent_pos[2] + rotated[2],
    )

    return (world_quat, world_pos)


def make_biggest_positive(q):
    """Ensure the largest-magnitude component of a quaternion is positive.

    This is required before 5-byte compression to ensure consistent encoding.
    """
    w, x, y, z = q
    # Find the component with the largest absolute value
    abs_vals = [abs(w), abs(x), abs(y), abs(z)]
    max_idx = abs_vals.index(max(abs_vals))

    components = [w, x, y, z]
    if components[max_idx] < 0:
        return (-w, -x, -y, -z)
    return q
