# -*- coding: utf-8 -*-
#
# align_model.py - the alignment model fitted with QUEST's rotation
#
# Each sync point's raw motor angles are corrected before the forward kinematics:
#     theta' = theta + (0, d2 + s2 * (theta2 - 45), d3)
#   d2, d3   M2/M3 zero offsets, fitted per alignment (they change with the setup: how the camera and lens sit on
#            the head -- a constant sideways pull on the lens is indistinguishable from d3)
#   s2       M2 scale, a mount constant (+1-2% on every Polaris in the logs; config align_m2_scale)
# docs/study_alignment_mac_v2.md: on 1,300 archived sync points these take residuals from 36-95' to 2-8'.
#
# The fit is numpy only and vectorised over the points, with analytic derivatives: it runs at each alignment sync,
# and must stay fast on a Raspberry Pi Zero 2 W (target under ~20 ms for 10 points).

from dataclasses import dataclass, field
import numpy as np
from quaternion import Q as Quaternion

M2_SCALE_REF_DEG = 45.0     # the M2 scale acts about this angle, mid-range, so s2 and d2 stay separable
MIN_POINTS_OFFSETS = 3      # fewer points: rotation only, the offsets held
MIN_SV_RATIO = 0.02         # the offsets are fitted only when the points separate them from the rotation: the
                            # smallest singular value of the column-normalised Jacobian over the largest
MAX_ITER = 10
_D2R = np.pi / 180.0


def corrected_theta(theta, d2=0.0, d3=0.0, s2=0.0):
    """Motor angles (deg, (..., 3)) with the model applied: M2 offset and scale, M3 offset."""
    th = np.array(theta, float, copy=True)
    th[..., 1] += d2 + s2 * (th[..., 1] - M2_SCALE_REF_DEG)
    th[..., 2] += d3
    return th


def _fk(theta):
    """Boresights (N, 3) of motor angles (deg) and their derivatives with respect to theta2 and theta3 (per deg).
    The driver's theta_to_q: C = Rz(-theta1 + 90) . Ry(-theta2 - 90) . Rx(-theta3), boresight C . (0, 0, -1)."""
    th = np.atleast_2d(np.asarray(theta, float))
    a1 = (-th[:, 0] + 90.0) * _D2R
    a2 = (-th[:, 1] - 90.0) * _D2R
    a3 = -th[:, 2] * _D2R
    c1, s1, c2, s2, c3, s3 = np.cos(a1), np.sin(a1), np.cos(a2), np.sin(a2), np.cos(a3), np.sin(a3)
    # v = Ry(a2) . Rx(a3) . (0, 0, -1) and its derivatives with respect to a2 and a3
    v = np.column_stack([-s2 * c3, s3, -c2 * c3])
    dv_a2 = np.column_stack([-c2 * c3, np.zeros_like(c3), s2 * c3])
    dv_a3 = np.column_stack([s2 * s3, c3, c2 * s3])

    def rz(u):
        return np.column_stack([c1 * u[:, 0] - s1 * u[:, 1], s1 * u[:, 0] + c1 * u[:, 1], u[:, 2]])
    # d(a)/d(theta) = -1 (deg -> rad)
    return rz(v), -_D2R * rz(dv_a2), -_D2R * rz(dv_a3)


def boresights(theta):
    """Boresight unit vectors (N, 3) in the base frame for motor angles (deg, (N, 3))."""
    return _fk(theta)[0]


def _kabsch(p, o):
    """Rotation matrix R minimising sum |o - R p|^2 (unweighted QUEST)."""
    u, _, vt = np.linalg.svd(p.T @ o)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return vt.T @ np.diag([1.0, 1.0, d]) @ u.T


def _exp(w):
    """Rotation matrix of the rotation vector w (rad)."""
    a = np.linalg.norm(w)
    if a < 1e-15:
        return np.eye(3)
    k = w / a
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * (K @ K)


def _skew_rows(p):
    """Stacked (3N, 3) of -[p_i]x: d(R p_i)/d(w) for a left perturbation exp(w) R."""
    n = len(p)
    m = np.zeros((n, 3, 3))
    m[:, 0, 1], m[:, 0, 2] = p[:, 2], -p[:, 1]
    m[:, 1, 0], m[:, 1, 2] = -p[:, 2], p[:, 0]
    m[:, 2, 0], m[:, 2, 1] = p[:, 1], -p[:, 0]
    return m.reshape(3 * n, 3)


@dataclass
class AlignFit:
    q: Quaternion                    # base -> topocentric rotation (alignQ_B2T)
    d2: float = 0.0                  # deg
    d3: float = 0.0                  # deg
    s2: float = 0.0                  # fraction
    offsets_fitted: bool = False     # False: d2, d3 held at d_init (too few points, or not separable)
    s2_fitted: bool = False
    rms_arcmin: float = 0.0
    residuals_arcmin: np.ndarray = field(default_factory=lambda: np.zeros(0))
    iterations: int = 0


def _jacobian(R, theta, d2, d3, s2, n_free):
    tc = corrected_theta(theta, d2, d3, s2)
    b, db2, db3 = _fk(tc)
    p = b @ R.T
    cols = [_skew_rows(p)]
    if n_free >= 2:
        cols += [(db2 @ R.T).reshape(-1, 1), (db3 @ R.T).reshape(-1, 1)]
    if n_free == 3:
        cols.append(((db2 * (theta[:, 1:2] - M2_SCALE_REF_DEG)) @ R.T).reshape(-1, 1))
    return p, np.hstack(cols)


def _separable(R, theta, d2, d3, s2, n_free):
    """Whether the points determine the free model terms as well as the rotation (column-normalised Jacobian)."""
    if len(theta) < MIN_POINTS_OFFSETS:
        return False
    _, J = _jacobian(R, theta, d2, d3, s2, n_free)
    J = J / np.maximum(np.linalg.norm(J, axis=0), 1e-15)
    sv = np.linalg.svd(J, compute_uv=False)
    return sv[-1] / sv[0] >= MIN_SV_RATIO


def fit_alignment(theta, obs, s2=0.0, d_init=(0.0, 0.0), fit_offsets=True, fit_s2=False, max_iter=MAX_ITER):
    """
    Least-squares alignment of raw motor angles theta (deg, (N, 3)) to observed directions obs (unit, (N, 3)):
    the rotation (QUEST's, as the starting point), and d2, d3 (and s2 with fit_s2) when the points determine them;
    otherwise they are held at d_init / s2. Unweighted. Returns an AlignFit.
    """
    theta = np.atleast_2d(np.asarray(theta, float))
    obs = np.atleast_2d(np.asarray(obs, float))
    d2, d3 = float(d_init[0]), float(d_init[1])
    R = _kabsch(boresights(corrected_theta(theta, d2, d3, s2)), obs)
    n_free = (3 if fit_s2 else 2) if fit_offsets else 0
    if n_free and not _separable(R, theta, d2, d3, s2, n_free):
        n_free = 0
    it = 0
    if n_free:
        for it in range(1, max_iter + 1):
            p, J = _jacobian(R, theta, d2, d3, s2, n_free)
            r = (obs - p).reshape(-1)
            step = np.linalg.lstsq(J, r, rcond=None)[0]
            R = _exp(step[:3]) @ R
            d2 += step[3]
            d3 += step[4]
            if n_free == 3:
                s2 += step[5]
            if np.max(np.abs(step)) < 1e-12:
                break
    p = boresights(corrected_theta(theta, d2, d3, s2)) @ R.T
    res = np.degrees(np.arctan2(np.linalg.norm(np.cross(p, obs), axis=1), np.sum(p * obs, axis=1))) * 60
    return AlignFit(q=Quaternion(matrix=R).normalised, d2=d2, d3=d3, s2=s2, offsets_fitted=n_free >= 2,
                    s2_fitted=n_free == 3, rms_arcmin=float(np.sqrt(np.mean(res ** 2))) if len(res) else 0.0,
                    residuals_arcmin=res, iterations=it)
