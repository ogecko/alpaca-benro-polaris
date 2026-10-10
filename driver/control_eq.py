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


# ---------------------------------------------------------------------------------------
# Keeping the rig above the Polaris
# ---------------------------------------------------------------------------------------
# Camera-up (camera +x) is the M3 axis: M3 pans the camera about it and never rolls it over. On a level base M2 keeps
# it within THETA2_MAX of the zenith, so the rig is always above the Polaris, even pointing below the horizon. On a
# wedge that limit is about the M1 axis (the pole) instead, and camera-up can tilt to 90 - |lat| + THETA2_MAX
# (~137 deg) from the zenith: the rig hanging under the Polaris by the tripod. limit_rig_tilt() keeps it within a
# limit, at little cost in sky (98.4% reachable at 100 deg vs 98.9%): what it costs is part of the PA range near the
# polar caps.

EQ_MIN_TRACK_ROOM_DEG = 120.0                       # M1 travel a goto leaves for tracking before its limit (8 h)


def rig_tilt_deg(cameraQ_C2T: Quaternion) -> float:
    """Tilt (deg) of camera-up (the M3 axis) from the zenith."""
    return math.degrees(math.acos(np.clip(cameraQ_C2T.rotate([1.0, 0.0, 0.0])[2], -1.0, 1.0)))


def _arc(u, w, c, m):
    """Angles phi where (u cos phi + w sin phi) . c >= m, as (centre, half width) on the circle, half width None if
    none, pi if all."""
    a, b = float(np.dot(u, c)), float(np.dot(w, c))
    r = math.hypot(a, b)
    if r < 1e-12:
        return 0.0, (math.pi if m <= 0 else None)
    x = m / r
    if x > 1.0 + 1e-12:
        return 0.0, None
    return math.atan2(b, a), (math.pi if x < -1.0 else math.acos(min(1.0, x)))


def _nearest_allowed_pa_turn(q, m1_axis, cos_tilt):
    """Smallest turn phi (rad) of camera-up about the boresight that keeps it within THETA2_MAX of the M1 axis (the
    motors' reach) and within the tilt limit of the zenith, or None if no PA allows both."""
    bore, up = np.array(q.rotate([0.0, 0.0, -1.0])), np.array(q.rotate([1.0, 0.0, 0.0]))
    w = np.cross(bore, up)                          # up turned +90 deg about the boresight
    arcs = [_arc(up, w, m1_axis, math.cos(math.radians(THETA2_MAX)) - 1e-12),
            _arc(up, w, np.array([0.0, 0.0, 1.0]), cos_tilt)]
    if any(half is None for _, half in arcs):
        return None

    def inside(phi):
        return all(half >= math.pi or abs(math.remainder(phi - c, 2 * math.pi)) <= half + 1e-12 for c, half in arcs)

    candidates = [0.0] + [math.remainder(c + s * half, 2 * math.pi) for c, half in arcs if half < math.pi for s in (-1, 1)]
    allowed = [phi for phi in candidates if inside(phi)]
    return min(allowed, key=abs) if allowed else None


def limit_rig_tilt(cameraQ_C2T: Quaternion, alignQ_B2T: Quaternion, tilt_limit_deg: float) -> Quaternion:
    """The pose nearest cameraQ_C2T that keeps camera-up within tilt_limit_deg of the zenith (and within the motors'
    reach): the same pointing with the nearest allowed PA, or where no PA is allowed (rings by the polar caps) the
    pointing moved the least distance away from the nearer pole, as the cap itself clamps it."""
    if rig_tilt_deg(cameraQ_C2T) <= tilt_limit_deg:
        return cameraQ_C2T
    m1_axis = np.array(alignQ_B2T.rotate([0.0, 0.0, 1.0]))
    cos_tilt = math.cos(math.radians(tilt_limit_deg))

    def turned(q):
        phi = _nearest_allowed_pa_turn(q, m1_axis, cos_tilt)
        return None if phi is None else Quaternion(axis=q.rotate([0.0, 0.0, -1.0]), radians=phi) * q

    result = turned(cameraQ_C2T)
    if result is not None:
        return result
    bore = np.array(cameraQ_C2T.rotate([0.0, 0.0, -1.0]))
    k = np.cross(m1_axis, bore)
    if np.linalg.norm(k) < 1e-12:
        return cameraQ_C2T
    away = 1.0 if np.dot(bore, m1_axis) >= 0 else -1.0  # turning about m1 x bore moves the pointing off the M1 axis

    def moved(deg):
        return Quaternion(axis=k, degrees=away * deg) * cameraQ_C2T

    lo, hi = 0.0, None
    for deg in np.arange(1.0, 91.0, 1.0):
        if turned(moved(deg)) is not None:
            hi = deg
            break
        lo = deg
    if hi is None:
        return cameraQ_C2T
    for _ in range(30):                             # bisect: continuous, so tracking along the edge is smooth
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if turned(moved(mid)) is not None else (mid, hi)
    return turned(moved(hi))


def eq_theta1_with_room(theta1_goal: float, theta1_now: float, lo: float, hi: float, direction: float,
                        min_room: float = EQ_MIN_TRACK_ROOM_DEG) -> float:
    """theta1_goal + k*360 within [lo, hi] for a goto: the nearest to theta1_now that leaves min_room of M1 travel in
    the tracking direction (-1 theta1 falls, +1 rises), else the one with the most room."""
    candidates = [theta1_goal + 360.0 * k for k in range(-3, 4) if lo <= theta1_goal + 360.0 * k <= hi]
    if not candidates:
        return theta1_goal

    def room(t):
        return t - lo if direction < 0 else hi - t

    roomy = [t for t in candidates if room(t) >= min_room]
    if roomy:
        return min(roomy, key=lambda t: abs(t - theta1_now))
    return max(candidates, key=room)
