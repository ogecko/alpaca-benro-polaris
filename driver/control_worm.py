# -----------------------------------------------------------------------------
# control_worm.py - worm gear periodic error: feed-forward and calibration tests
# -----------------------------------------------------------------------------
#
# Each motor's gear train after the motor has a periodic error the MCU can't see (a 6.0 deg worm, 60 teeth:
# 960 = 16 x 60). This module holds everything about it:
#
#   WormFeedForward      the profile (per motor, per harmonic) and the base-frame correction it implies
#   zeta_raw_offset      theta_raw (518) - zeta (517): MCU motor angles from 518 angles (PECLOG, the profile)
#   WormMixin            SyncManager's worm methods: the feed-forward (WFF) in the forward kinematics, and recording
#                        plate-solve syncs during an M#-WORM-GEAR calibration test
#   WormCalibration      an M#-WORM-GEAR test's step schedule; fit_worm_calibration, store/apply/revert_calibration
#
# M#-WORM-GEAR calibration tests (Speed Calibration page)
# --------------------------------------------------
# Measures one motor's worm from plate solves, instead of learning it from guided nights (utility/learn_worm.py):
# the motor is stepped through its worm while sidereal tracking holds the sky, and each plate-solve sync is recorded
# as that motor's angle error rather than applied.
#
# Stop and go, driven by the syncs: plate solving while the motor turns would smear the stars and turn the solve's
# latency (unknown, 1-3 s jitter) into error at the motor's rate. So the motor steps step_deg, tracking holds, and the
# test steps again only after a kept sync. The first sync after a step is discarded -- its exposure may have started
# during the move or settling -- so every position costs syncs_per_step (2) solves. The positions sweep `turns` worm
# turns forward and back, centred on where the mount was pointed (0 -> +half -> -half -> 0, so the field stays within
# +/- 3 deg x turns of the chosen patch of sky): a slow drift in time (the other motors' worms as tracking turns them,
# the alignment model) separates from the worm in angle, and the two directions show the backlash.
#
# Angles are the MCU's (517 zeta: theta_raw - zeta_raw_offset), which are the same every session; M1's 518 angle
# carries each session's compass / SPA heading. A profile motor calibrated here is marked 'zeta' in the profile's
# angle_reference and the feed-forward evaluates it on MCU angles.
#
# The result (fit, checks and samples) is stored in the profile file's 'calibration' section for review; approving
# the test row applies that motor's coefficients to the profile, rejecting restores the previous ones.
# -----------------------------------------------------------------------------

import datetime
import json
import os
import time
from dataclasses import dataclass, field

import numpy as np

from config import Config, DATA_DIR
from kinematics import theta_to_q, q_to_azaltroll, azalt_to_vector
from quaternion import Q as Quaternion

WORM_PROFILE_PATH = DATA_DIR / 'worm_profile.json'   # the worm gear correction profile, written when a test is approved

# ── Worm feed-forward ─────────────────────────────────────────────────────────────────────────
# Each motor's gear train after the motor has a periodic error: the true output angle = the MCU's motor angle + e_i,
# where e_i(theta_i) = sum over harmonics h of a sin(h phi_i) + b cos(h phi_i), phi_i = 360 deg x theta_i / worm_theta.
# The MCU only measures the motor shaft, so it never sees e. With a profile measured by the M#-WORM-GEAR tests (the
# worm repeats night to night on the MCU's angles), the driver builds its present value from theta + e instead of
# theta -- the true pointing -- and the PID, alignment, guiding and PEC all work from that.

@dataclass
class WormFeedForward:
    worm_theta: float = 6.0                   # deg of motor (output) rotation per worm turn (60-tooth: 960 = 16 x 60)
    harmonics: tuple = (1, 2)
    coef: np.ndarray = None                   # (3, 2 x len(harmonics)) arcsec: per motor, per harmonic, sin then cos
    meta: dict = field(default_factory=dict)  # provenance: sessions learnt from, angle reference, date, ...
    angle_reference: dict = field(default_factory=dict)   # {'M1': 'zeta'}: that motor's coef are on MCU angles (517,
                                                          # M#-WORM-GEAR test); otherwise on theta_raw (518)

    def __post_init__(self):
        n = 2 * len(self.harmonics)
        self.coef = np.zeros((3, n)) if self.coef is None else np.asarray(self.coef, float).reshape(3, n)
        self.angle_reference = dict(self.angle_reference or {})

    def error_deg(self, theta, zeta_offset=None):
        """(3,) deg: each motor's gear error at motor angles theta (deg) -- true output angle = theta + error.
        zeta_offset: theta_raw - zeta per motor (zeta_raw_offset), for motors whose coef are on MCU angles; without
        it those motors are left out."""
        theta = np.array(theta, float)
        coef = self.coef
        zeta = [m for m in range(3) if self.angle_reference.get(f'M{m + 1}') == 'zeta']
        if zeta:
            coef = coef.copy()
            for m in zeta:
                if zeta_offset is None or zeta_offset[m] is None:
                    coef[m] = 0.0
                else:
                    theta[m] -= zeta_offset[m]
        phi = 2 * np.pi * theta / self.worm_theta
        basis = np.stack([f(h * phi) for h in self.harmonics for f in (np.sin, np.cos)], axis=-1)   # (3, n)
        return np.sum(basis * coef, axis=-1) / 3600.0

    def correction_q(self, theta, zeta_offset=None):
        """Base-frame rotation taking the pose at the measured motor angles to the true pose: q(theta + e) q(theta)^-1."""
        theta = np.asarray(theta, float)
        return (theta_to_q(*(theta + self.error_deg(theta, zeta_offset))) * theta_to_q(*theta).inverse).normalised

    def save(self, path):
        core = {'worm_theta': float(self.worm_theta), 'harmonics': [int(h) for h in self.harmonics],
                'motors': {f'M{m + 1}': [round(float(v), 4) for v in self.coef[m]] for m in range(3)},
                'units': 'arcsec of motor angle; per harmonic: sin, cos; true angle = MCU angle + error'}
        if self.angle_reference:
            core['angle_reference'] = dict(self.angle_reference)
        d = {**{k: v for k, v in self.meta.items() if k not in core}, **core}        # provenance never overrides
        with open(path, 'w') as f:
            json.dump(d, f, indent=2)

    @classmethod
    def load(cls, path):
        """The profile in `path`, or None if it is missing or malformed."""
        try:
            with open(path) as f:
                d = json.load(f)
            harmonics = tuple(int(h) for h in d['harmonics'])
            coef = np.array([d['motors'][f'M{m + 1}'] for m in range(3)], float)
            meta = {k: v for k, v in d.items() if k not in ('worm_theta', 'harmonics', 'motors', 'units', 'angle_reference')}
            return cls(worm_theta=float(d['worm_theta']), harmonics=harmonics, coef=coef, meta=meta,
                       angle_reference=d.get('angle_reference') or {})
        except (OSError, ValueError, KeyError, TypeError):
            return None


def zeta_raw_offset(theta_raw, zeta):
    """theta_raw (518: the firmware's box attitude x the MCU motor angles, so M1 carries the session's compass / SPA
    heading) minus zeta (517: the MCU's own motor angles), per motor, wrapped to [-180, 180). Cached on each 517 so
    PECLOG can carry it: theta_raw - offset gives the motor angles at the 518 rate, the same every session."""
    if theta_raw is None or zeta is None:
        return None
    return [float((t - z + 180.0) % 360.0 - 180.0) for t, z in zip(theta_raw, zeta)]


class WormMixin:
    """Worm methods of SyncManager (see control.SyncManager): the feed-forward and the M#-WORM-GEAR test's syncs."""

    def init_worm(self):
        """Create the worm state; called once from SyncManager.__init__."""
        self.corrQ_WFF = Quaternion()           # worm feed-forward: measured -> true pose, base frame (identity when off)
        self._worm_ff = None                    # WormFeedForward profile, loaded on first use
        self._worm_ff_path = None               # path it was loaded from (None: reload on next use)
        self.worm_test = None                   # WormCalibration while an M#-WORM-GEAR test runs

    # ── worm feed-forward ────────────────────────────────────────────────────────────────────
    def worm_profile_path(self):
        """The profile file: worm_profile.json in the data folder."""
        return str(WORM_PROFILE_PATH)

    def _worm_ff_profile(self):
        full = self.worm_profile_path()
        if full != self._worm_ff_path:
            self._worm_ff_path = full
            self._worm_ff = WormFeedForward.load(full)
            if self._worm_ff is None:
                self.logger.warning(f"Worm feed-forward is on but there is no valid profile at {full} -- not applied "
                                    f"(measure it with the Speed Calibration M1/M2/M3-WORM-GEAR tests and approve them)")
            else:
                self.logger.info(f"Worm feed-forward profile loaded from {full}: worm {self._worm_ff.worm_theta:g} deg, "
                                 f"harmonics {list(self._worm_ff.harmonics)}, {self._worm_ff.meta.get('learnt_from', '')}")
        return self._worm_ff

    def update_worm_ff(self, theta):
        """Refresh the worm feed-forward rotation for the current motor angles (deg); identity when off, or while a
        worm calibration test measures the uncorrected worm."""
        on = getattr(Config, 'pec_worm_ff', False) and self.worm_test is None
        prof = self._worm_ff_profile() if on else None
        offset = getattr(self.polaris, '_zeta_raw_offset', None)
        self.corrQ_WFF = prof.correction_q(theta, zeta_offset=offset) if prof is not None else Quaternion()

    def reload_worm_ff(self):
        """Read the profile file again on the next tick (after a worm calibration was approved or rejected)."""
        self._worm_ff_path = None

    def _wff_radec_arcmin(self):
        """The feed-forward rotation split along the RA and Dec axes (arcmin, the guide-correction convention)."""
        axes = getattr(self, 'equatorial_axes_B', (None, None, None))
        if any(a is None for a in axes):
            return [None, None]
        q = getattr(self, 'corrQ_WFF', Quaternion())
        if q.degrees < 1e-12:
            return [0.0, 0.0]
        c = np.linalg.solve(np.column_stack(axes), np.asarray(q.axis) * q.degrees)
        return [round(float(c[0] * 60), 5), round(float(c[1] * 60), 5)]

    # ── M#-WORM-GEAR calibration test ─────────────────────────────────────────────────────────────
    def _boresight_T(self, theta):
        az, alt, _ = q_to_azaltroll(self.pvQ_to_topoQ(theta_to_q(*theta)))
        return np.asarray(azalt_to_vector(az, alt), float)

    def motor_error_from_azalt(self, axis, theta, a_az, a_alt, eps_deg=0.01):
        """The angle error (deg) of motor `axis` that best explains a plate solve at a_az/a_alt when the driver's present
        value is the motor angles theta (theta_pv space): the solved pointing minus the present one, projected on the
        direction that motor moves the boresight. Also returns that motor's sensitivity: boresight deg per motor deg
        (near 0 = the motor barely moves the field, e.g. M3 close to the line of sight)."""
        theta = np.asarray(theta, float)
        e = np.zeros(3)
        e[axis] = eps_deg
        s = (self._boresight_T(theta + e) - self._boresight_T(theta - e)) / (2 * eps_deg)   # rad per deg
        dv = np.asarray(azalt_to_vector(a_az, a_alt), float) - self._boresight_T(theta)
        ss = float(s @ s)
        if ss < 1e-12:
            return 0.0, 0.0
        return float(s @ dv / ss), float(np.sqrt(ss) / np.radians(1.0))

    def record_worm_sync(self, a_ra, a_dec, a_az, a_alt):
        """A plate-solve sync while a worm calibration test runs: record it as the test motor's angle error (not applied
        to any model) and step the motor when the test asks for it."""
        test, p = self.worm_test, self.polaris
        pid = p._pid
        axis = test.axis
        theta_pv = np.array(pid.theta_pv, float)
        err_deg, sens = self.motor_error_from_azalt(axis, theta_pv, a_az, a_alt)
        theta_raw = np.array(p._theta_raw, float)
        offset = getattr(p, '_zeta_raw_offset', None)
        angle = float(theta_raw[axis] - offset[axis]) if offset is not None else float(theta_raw[axis])
        sample = {'t': round(time.monotonic(), 3), 'angle': round(angle, 5), 'err_arcsec': round(err_deg * 3600.0, 2),
                  'sensitivity': round(sens, 3), 'theta_raw': [round(float(x), 5) for x in theta_raw],
                  'zeta_offset': offset, 'theta_pv': [round(float(x), 5) for x in theta_pv],
                  'a_ra': a_ra, 'a_dec': a_dec, 'pv_ra': getattr(p, '_rightascension', None),
                  'pv_dec': getattr(p, '_declination', None)}
        step = test.on_sync(sample)
        if self.logger:
            kept = 'kept' if test.syncs_here == 0 else 'settling'
            self.logger.info(f"WORM TEST M{axis + 1}: sync {kept} at {angle:.3f} deg, error {err_deg * 3600:.1f}\" "
                             f"(sensitivity {sens:.2f}), position {test.index}/{len(test.positions)}")
        if step:
            pid.step_motor_target(axis, step)


# ── M#-WORM-GEAR calibration test ──────────────────────────────────────────────────────────────────
MOTORS = ('M1', 'M2', 'M3')
MIN_SAMPLES = 12              # fewer kept syncs: NO DATA
MIN_TURNS = 1.5               # worm turns covered for a fit to count
MIN_SIGNIFICANCE = 4.0        # amplitude / its standard error


class WormCalibration:
    """One M#-WORM-GEAR test: the step schedule and the syncs it keeps."""

    def __init__(self, axis, step_deg=0.5, turns=2.0, worm_theta=6.0, syncs_per_step=2, no_sync_timeout_s=120.0,
                 now=None):
        self.axis = axis
        self.no_sync_timeout_s = no_sync_timeout_s
        self.last_sync = time.monotonic() if now is None else now   # start, then the last sync (kept or settling)
        self.abort_reason = None                   # why the test was cut short (goto, jog, pulse guide, no syncs ...)
        self.step_deg = step_deg
        self.worm_theta = worm_theta
        self.syncs_per_step = syncs_per_step
        n = int(round(turns * worm_theta / 2 / step_deg))
        k = range(1, n + 1)
        # motor offsets (deg) from the start, centred on it: 0 -> +half -> -half -> 0 (turns worm turns each way)
        self.positions = ([0.0] + [i * step_deg for i in k] + [(n - i) * step_deg for i in range(1, 2 * n + 1)]
                          + [(i - n) * step_deg for i in k])
        self.index = 0                             # position the mount is at (or moving to)
        self.syncs_here = 0                        # syncs seen at this position
        self.samples = []

    @property
    def done(self):
        return self.index >= len(self.positions)

    @property
    def aborted(self):
        return self.abort_reason is not None

    def abort(self, reason):
        """End the test early (the first reason is kept): something else moved the mount, or no syncs arrive."""
        if self.abort_reason is None:
            self.abort_reason = reason

    def timed_out(self, now):
        return now - self.last_sync > self.no_sync_timeout_s

    def direction(self, i):
        return 0 if i == 0 else int(np.sign(self.positions[i] - self.positions[i - 1]))

    def on_sync(self, sample, now=None):
        """Record a sync (dict) at the current position. Returns the step (deg) to make now, or None (sync discarded
        while settling, or the test is finished or aborted)."""
        if self.done or self.aborted:
            return None
        self.last_sync = time.monotonic() if now is None else now
        self.syncs_here += 1
        if self.syncs_here < self.syncs_per_step:
            return None
        self.samples.append({**sample, 'position': self.positions[self.index], 'direction': self.direction(self.index)})
        self.index += 1
        self.syncs_here = 0
        if self.done:
            return None
        return self.positions[self.index] - self.positions[self.index - 1]


# ── calibration fit ───────────────────────────────────────────────────────────────────────────
def _design(angle, t, direction, worm_theta, harmonics=(1,)):
    phi = 2 * np.pi * angle / worm_theta
    cols = [f(h * phi) for h in harmonics for f in (np.sin, np.cos)]
    nw = len(cols)
    cols += [(direction > 0).astype(float), (direction < 0).astype(float)]       # offset per direction (backlash)
    ts = (t - t.mean()) / max(np.ptp(t), 1e-9)
    xs = (angle - angle.mean()) / max(np.ptp(angle), 1e-9)
    cols += [ts, ts ** 2, xs, xs ** 2]                                           # slow drift in time and in pointing
    return np.column_stack(cols), nw


def _lstsq(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    return beta, r, float(r @ r) / dof


def _phase(a, b):
    return float(np.degrees(np.arctan2(b, a)) % 360)


def fit_worm_calibration(angle, err, t, direction, worm_theta=6.0):
    """Fit the worm to a calibration sweep: err (arcsec, the motor's angle error) at MCU angles `angle` (deg), times t
    (s) and directions (+1/-1; 0 = before the first step, left out) -- A sin(360 angle / worm_theta + phase) next to a
    per-direction offset and a quadratic trend in time and in angle. Returns a dict: status, amplitude_arcsec,
    phase_deg, coef [a, b] (a sin + b cos, the profile's first harmonic), checks."""
    angle, err, t, direction = (np.asarray(x, float) for x in (angle, err, t, direction))
    keep = direction != 0
    angle, err, t, direction = angle[keep], err[keep], t[keep], direction[keep]
    n = len(err)
    turns = float(np.ptp(angle) / worm_theta) if n else 0.0
    out = {'status': 'NO DATA', 'amplitude_arcsec': None, 'phase_deg': None, 'coef': None,
           'checks': {'n': n, 'turns': round(turns, 2)}}
    if n < MIN_SAMPLES:
        return out

    X, nw = _design(angle, t, direction, worm_theta)
    beta, r, s2 = _lstsq(X, err)
    cov = s2 * np.linalg.pinv(X.T @ X)
    a, b = beta[:2]
    A = float(np.hypot(a, b))
    se_A = float(np.sqrt(max((a * a * cov[0, 0] + b * b * cov[1, 1] + 2 * a * b * cov[0, 1]) / max(A * A, 1e-12),
                             1e-12)))
    checks = out['checks']
    checks['rms_arcsec'] = round(float(np.sqrt(s2)), 2)
    checks['significance'] = round(A / se_A, 1)
    both = (direction > 0).any() and (direction < 0).any()
    checks['backlash_arcsec'] = round(float(beta[nw] - beta[nw + 1]), 1) if both else None

    # pure sine? the 2nd harmonic relative to the 1st
    X2, _ = _design(angle, t, direction, worm_theta, harmonics=(1, 2))
    b2, _, _ = _lstsq(X2, err)
    checks['harmonic2_ratio'] = round(float(np.hypot(*b2[2:4]) / max(np.hypot(*b2[:2]), 1e-9)), 3)

    # 6 deg? the worm period that fits best
    periods = np.arange(5.0, 7.5 + 1e-9, 0.02)
    rss = [_lstsq(_design(angle, t, direction, p)[0], err)[2] for p in periods]
    checks['best_worm_theta'] = round(float(periods[int(np.argmin(rss))]), 2)

    # the same worm both ways? phase from each direction on its own
    for name, sel in (('phase_fwd_deg', direction > 0), ('phase_rev_deg', direction < 0)):
        if sel.sum() >= MIN_SAMPLES // 2:
            phi = 2 * np.pi * angle[sel] / worm_theta
            ts = (t[sel] - t[sel].mean()) / max(np.ptp(t[sel]), 1e-9)
            Xd = np.column_stack([np.sin(phi), np.cos(phi), np.ones(sel.sum()), ts, ts ** 2])
            bd, _, _ = _lstsq(Xd, err[sel])
            checks[name] = round(_phase(*bd[:2]), 1)
        else:
            checks[name] = None
    if checks['phase_fwd_deg'] is not None and checks['phase_rev_deg'] is not None:
        checks['phase_split_deg'] = round(float((checks['phase_rev_deg'] - checks['phase_fwd_deg'] + 180) % 360 - 180), 1)
    else:
        checks['phase_split_deg'] = None

    good = turns >= MIN_TURNS and A / se_A >= MIN_SIGNIFICANCE
    out.update(status='COMPLETED' if good else 'POOR FIT', amplitude_arcsec=round(A, 2), phase_deg=round(_phase(a, b), 1),
               coef=[round(float(a), 4), round(float(b), 4)])
    return out


def fit_worm_samples(samples, worm_theta=6.0):
    """fit_worm_calibration on a test's kept syncs (WormCalibration.samples), adding the mean sensitivity to the checks
    and the samples themselves, ready for store_calibration."""
    col = lambda k: [x[k] for x in samples]
    r = fit_worm_calibration(col('angle'), col('err_arcsec'), col('t'), col('direction'), worm_theta=worm_theta)
    sens = [x['sensitivity'] for x in samples if x.get('sensitivity') is not None]
    r['checks']['sensitivity'] = round(float(np.mean(sens)), 2) if sens else None
    r['samples'] = samples
    return r


# warnings on the Speed Calibration row: (check, test, label)
GEAR_WARNINGS = (
    ('harmonic2_ratio', lambda v, w: v > 0.3, lambda v, w: f'2nd harm {v:.2f}'),
    ('best_worm_theta', lambda v, w: abs(v - w) > 0.2, lambda v, w: f'period {v:.2f}°'),
    ('phase_split_deg', lambda v, w: abs(v) > 30, lambda v, w: f'fwd/rev {v:+.0f}°'),
    ('sensitivity', lambda v, w: v < 0.3, lambda v, w: f'sensitivity {v:.2f}'),
)


def _profile_h1(ff, axis):
    """(amplitude, phase) of a profile's first harmonic for one motor, or None if it has none."""
    if ff is None or 1 not in ff.harmonics:
        return None
    i = 2 * list(ff.harmonics).index(1)
    a, b = ff.coef[axis, i:i + 2]
    return (float(np.hypot(a, b)), _phase(a, b)) if np.hypot(a, b) > 0 else None


def gear_row_fields(result, current, axis, worm_theta=6.0):
    """The M#-WORM-GEAR row's columns from a fit: dps (baseline) = the current profile's amplitude for that motor,
    test_result = amplitude @ phase, test_change = against the current profile (or 'new') plus any failed check,
    test_stdev = residual rms and kept syncs. `current`: the WormFeedForward in use before this test (or None)."""
    checks = result.get('checks', {})
    n = checks.get('n', 0)
    now = _profile_h1(current, axis)
    fields = {'dps': round(now[0], 2) if now else 0.0, 'test_result': '', 'test_change': '', 'test_stdev': f'n{n}'}
    A, p = result.get('amplitude_arcsec'), result.get('phase_deg')
    if A is None:
        return fields
    fields['test_result'] = f'{A:.1f}" @ {p:.1f}°'
    change = 'new' if now is None else f'{A - now[0]:+.1f}" / {(p - now[1] + 180) % 360 - 180:+.1f}°'
    warn = [label(checks[k], worm_theta) for k, bad, label in GEAR_WARNINGS
            if checks.get(k) is not None and bad(checks[k], worm_theta)]
    fields['test_change'] = change + (' ⚠ ' + ', '.join(warn) if warn else '')
    fields['test_stdev'] = f'{checks.get("rms_arcsec", 0):.1f}" rms n{n}'
    return fields


# ── profile file ──────────────────────────────────────────────────────────────────────────────
def _load_or_new(path):
    ff = WormFeedForward.load(path) if os.path.exists(path) else None
    return ff if ff is not None else WormFeedForward(worm_theta=6.0, harmonics=(1,))


def store_calibration(path, axis, result):
    """Keep a test's result (fit, checks, samples) in the profile file for review, without applying it."""
    ff = _load_or_new(path)
    cal = dict(ff.meta.get('calibration', {}))
    entry = {**result, 'created': datetime.datetime.now().isoformat(timespec='seconds'), 'applied': False,
             'angles': 'zeta (517, MCU)'}
    cal[MOTORS[axis]] = entry
    ff.meta['calibration'] = cal
    ff.save(path)


def apply_calibration(path, axis):
    """Put a stored calibration's coefficients into the profile for that motor (on MCU angles), keeping the previous
    ones to restore. False if there is no usable stored result."""
    ff = _load_or_new(path)
    m = MOTORS[axis]
    entry = ff.meta.get('calibration', {}).get(m)
    if not entry or not entry.get('coef'):
        return False
    if not entry.get('applied'):
        entry['previous'] = {'coef': [float(v) for v in ff.coef[axis]], 'angle_reference': ff.angle_reference.get(m)}
    coef = np.zeros(ff.coef.shape[1])
    i1 = list(ff.harmonics).index(1) if 1 in ff.harmonics else None
    if i1 is None:                                                  # profile without a 1st harmonic: start afresh
        ff = WormFeedForward(worm_theta=ff.worm_theta, harmonics=(1,), coef=np.zeros((3, 2)), meta=ff.meta,
                             angle_reference=ff.angle_reference)
        coef, i1 = np.zeros(2), 0
    coef[2 * i1:2 * i1 + 2] = entry['coef']
    ff.coef[axis] = coef
    ff.angle_reference[m] = 'zeta'
    entry['applied'] = True
    ff.save(path)
    return True


def revert_calibration(path, axis):
    """Undo apply_calibration for that motor. False if it was not applied."""
    ff = _load_or_new(path)
    m = MOTORS[axis]
    entry = ff.meta.get('calibration', {}).get(m)
    if not entry or not entry.get('applied'):
        return False
    prev = entry.get('previous', {})
    ff.coef[axis] = np.asarray(prev.get('coef', np.zeros(ff.coef.shape[1])), float)
    if prev.get('angle_reference'):
        ff.angle_reference[m] = prev['angle_reference']
    else:
        ff.angle_reference.pop(m, None)
    entry['applied'] = False
    ff.save(path)
    return True
