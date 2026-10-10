"""
Equatorial (wedge) mode -- proof of concept, kinematics only.

On a wedge that tilts the Polaris base so the M1 axis points at the visible celestial pole, M1 becomes an RA axis.
M1 is the first joint, so turning it rotates M2, M3 and the camera rigidly about the pole, which is exactly the
sky's motion: any pointing tracks with M1 alone at the sidereal rate, and field rotation is matched for free.
M2 and M3 then only set Dec and framing:

    sin(dec_p) = cos(theta3) * sin(theta2)          dec_p = Dec measured toward the visible pole (-Dec in the south)

With theta2 limited to [THETA2_MIN, THETA2_MAX] = [-8, 81.5]:
  - dec_p in [-8, 81.5] is reachable with theta3 = 0 (theta2 = dec_p), leaving M3 free for framing.
  - dec_p in [-81.5, -8) (the far side of the equator) needs |theta3| > 90: the camera swung round past the M2 arm.
  - |dec_p| > 81.5 (the cap around either pole) is unreachable.
  - theta2 ~ 0 puts the M3 axis on the M1 axis (gimbal lock): dec_p ~ 0 at theta3 = 0.

The driver already splits the camera pose into motor kinematics (camera->base: theta_to_q / q_to_theta) and a
base->topocentric rotation (alignQ_B2T, normally QUEST's small levelling/azimuth correction). A wedge is just a large
base->topocentric rotation, so wedge_alignQ_B2T() is all the kinematics needs; the rest is unchanged.
"""
import math

import numpy as np

from quaternion import Q as Quaternion
from kinematics import THETA2_MAX

THETA2_MIN = -8.0
SIDEREAL_RATE_ARCSEC_S = 360 * 3600 / 86164.0905     # ~15.041"/s


def celestial_pole_topo(lat_deg: float) -> np.ndarray:
    """Unit vector (East, North, Up) of the visible celestial pole: the NCP north of the equator, the SCP south."""
    lat = math.radians(lat_deg)
    sign = 1.0 if lat_deg >= 0 else -1.0
    return sign * np.array([0.0, math.cos(lat), math.sin(lat)])


def wedge_alignQ_B2T(lat_deg: float) -> Quaternion:
    """Base->topocentric rotation of an ideal wedge: tilts the M1 axis (base +Z) by 90 - |lat| about the East-West
    axis, toward the pole, so it points at the visible celestial pole. Used in place of (or as the starting point
    for) QUEST's alignQ_B2T."""
    pole = celestial_pole_topo(lat_deg)
    axis = np.cross([0.0, 0.0, 1.0], pole)
    if np.linalg.norm(axis) < 1e-12:                 # at a geographic pole the level mount is already equatorial
        return Quaternion(1, 0, 0, 0)
    return Quaternion(axis=axis, radians=math.acos(np.clip(pole[2], -1.0, 1.0)))


def theta_to_pole_dec(theta2: float, theta3: float) -> float:
    """Dec toward the visible pole (degrees) of the boresight at theta2/theta3, on an ideal wedge."""
    return math.degrees(math.asin(math.cos(math.radians(theta3)) * math.sin(math.radians(theta2))))


def min_abs_theta3_for_dec(dec_deg: float, lat_deg: float):
    """Smallest |theta3| (degrees) that reaches Dec dec_deg on an ideal wedge at latitude lat_deg, or None if out
    of reach. 0 means M2 alone sets the Dec; above 90 the camera must swing round past the M2 arm."""
    return _min_abs_theta3(dec_deg if lat_deg >= 0 else -dec_deg)


def _min_abs_theta3(dec_p: float):
    """Smallest |theta3| that reaches dec_p (the boresight's angle above the base plane, toward the M1 axis)."""
    if abs(dec_p) > THETA2_MAX:
        return None
    if dec_p >= THETA2_MIN:
        return 0.0
    # far side: cos(theta3) = sin(dec_p) / sin(theta2) is negative; |theta3| is smallest at theta2 = THETA2_MAX
    return math.degrees(math.acos(math.sin(math.radians(dec_p)) / math.sin(math.radians(THETA2_MAX))))
