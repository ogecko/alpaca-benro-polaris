# -----------------------------------------------------------------------------
# control_worm.py - worm gear periodic error: feed-forward and the worm profile test
# -----------------------------------------------------------------------------
#
# Each motor's gear train after the motor has a periodic error the MCU can't see (a 6.0 deg worm, 60 teeth:
# 960 = 16 x 60). This module holds everything about it:
#
#   WormFeedForward      the profile (per motor, per harmonic) and the base-frame correction it implies
#   zeta_raw_offset      theta_raw (518) - zeta (517): MCU motor angles from 518 angles (PECLOG, the profile)
#   WormMixin            SyncManager's worm methods: the feed-forward (WFF) in the forward kinematics, and recording
#                        plate-solve syncs during the worm profile test
#   WormProfileTest      the M1-M2-M3-WORM-PROFILE test's schedule and the syncs it keeps
#   fit_worm_profile     all three motors' worms from one or more tests (2-D joint fit)
#   store_profile_test, set_last_test_approved, rebuild_profiles   the tests kept in the profile file, and the profiles
#
# The worm profile test (Speed Calibration page, M1 row)
# -----------------------------------------------------
# Measures all three motors' worms at once from plate solves. The tracked target is stepped so that each motor turns
# its own schedule (POSITIONS: 51 positions, ~2.5 worm turns, different step sizes and reversal points per motor, so their worm phases and their
# backlash separate), while sidereal tracking holds the sky; each plate-solve sync is recorded, not applied.
#
# Stop and go, driven by the syncs: plate solving while the motors turn would smear the stars and turn the solve's
# latency into error. So the motors step, tracking holds, and the test steps again at the next kept sync. The driver
# can't know when the solve's exposure started, so it watches the step settle instead: once every motor has held
# within SETTLE_ARCSEC of its target for SETTLE_HOLD_S, a sync is kept and the motors step at once. A sync before that
# is discarded ('moving'); so is one whose error jumps more than JUMP_ARCSEC from the last kept sample (an exposure
# that caught the move) -- the sync after it was exposed after a settled sync, so it is kept. With Nina's wait between
# solves of ~10 s (a step settles in ~8 s, ~11-12 s with an overshoot), every solve is kept: one solve per position.
#
# Each sync gives the 2-D pointing error (solved minus predicted, in a tangent frame at the prediction) and each
# motor's 2-D effect on the pointing there. fit_worm_profile fits every motor's worm (1st and 2nd harmonic) to that,
# next to each motor's backlash and, per test, an offset, a drift in time and a trend across the pointing. Motors are
# told apart by their different schedules and by the direction each moves the field: at Roll 0 M1 and M3 move it the
# same way (they separate by about the roll angle), so the test first rotates to Roll +-ROLL_TARGET_DEG (the sign of the
# current roll), keeping Az/Alt, and back when it has finished -- see motor_separation().
#
# Angles are the MCU's (517 zeta: theta_raw - zeta_raw_offset), the same every session. Tests are kept in the profile
# file's calibration_history (the last CALIBRATION_HISTORY, with their samples, and the setup -- focal length and
# ratio -- they ran with), each approved or rejected: the row's button flips the last test's flag, as often as wanted,
# and only approved tests pool (a new test starts rejected). Each time the profiles are rebuilt from the approved
# tests (rebuild_profiles): each setup's own (setup_profiles, over its last POOL_TESTS: setup_tests) and a
# generic one over all setups. A motor whose worm differs with its direction of travel gets forward and reverse
# profiles (direction_pools), picked at runtime by the way it turns; the driver uses the closest setup's profile
# (setup_match), else the generic one.
# -----------------------------------------------------------------------------

import datetime
import json
import os
import time
from dataclasses import dataclass, field

import numpy as np

from config import Config, DATA_DIR
from kinematics import theta_to_q, q_to_azaltroll, azalt_to_vector, reachable_azaltroll
from quaternion import Q as Quaternion

WORM_PROFILE_PATH = DATA_DIR / 'worm_profile.json'   # the worm gear correction profile, written when a test is approved
DIRECTIONS = ('forward', 'reverse')                   # a motor's direction of travel: its MCU angle rising, falling

# ── Worm feed-forward ─────────────────────────────────────────────────────────────────────────
# Each motor's gear train after the motor has a periodic error: the true output angle = the MCU's motor angle + e_i,
# where e_i(theta_i) = sum over harmonics h of a sin(h phi_i) + b cos(h phi_i), phi_i = 360 deg x theta_i / worm_theta.
# The MCU only measures the motor shaft, so it never sees e. With a profile measured by the worm profile test (the
# worm repeats night to night on the MCU's angles), the driver builds its present value from theta + e instead of
# theta -- the true pointing -- and the PID, alignment, guiding and PEC all work from that.

@dataclass
class WormFeedForward:
    worm_theta: float = 6.0                   # deg of motor (output) rotation per worm turn (60-tooth: 960 = 16 x 60)
    harmonics: tuple = (1, 2)
    coef: np.ndarray = None                   # (3, 2 x len(harmonics)) arcsec: per motor, per harmonic, sin then cos
    meta: dict = field(default_factory=dict)  # provenance: sessions learnt from, angle reference, date, ...
    angle_reference: dict = field(default_factory=dict)   # {'M1': 'zeta'}: that motor's coef are on MCU angles (517,
                                                          # the worm profile test); otherwise on theta_raw (518)
    direction_coef: dict = field(default_factory=dict)    # {'M2': {'forward': coef, 'reverse': coef}}: a motor whose
                                                          # worm differs with its direction of travel (the gear flank
                                                          # the load rests on); `coef` is then its combined fit

    def __post_init__(self):
        n = 2 * len(self.harmonics)
        self.coef = np.zeros((3, n)) if self.coef is None else np.asarray(self.coef, float).reshape(3, n)
        self.angle_reference = dict(self.angle_reference or {})
        self.direction_coef = {M: {d: np.asarray(c[d], float).reshape(n) for d in DIRECTIONS}
                               for M, c in (self.direction_coef or {}).items()}

    def motor_coef(self, direction=None):
        """(3, n) coefficients in use: each motor's forward or reverse fit where it has one and `direction` (per motor
        +1 zeta rising, -1 falling, 0 unknown) says which, else its combined fit."""
        if not self.direction_coef or direction is None:
            return self.coef
        coef = self.coef.copy()
        for m in range(3):
            split = self.direction_coef.get(f'M{m + 1}')
            if split and direction[m]:
                coef[m] = split['forward' if direction[m] > 0 else 'reverse']
        return coef

    def error_deg(self, theta, zeta_offset=None, direction=None):
        """(3,) deg: each motor's gear error at motor angles theta (deg) -- true output angle = theta + error.
        zeta_offset: theta_raw - zeta per motor (zeta_raw_offset), for motors whose coef are on MCU angles; without
        it those motors are left out. direction: each motor's direction of travel (motor_coef)."""
        theta = np.array(theta, float)
        coef = self.motor_coef(direction)
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

    def correction_q(self, theta, zeta_offset=None, direction=None):
        """Base-frame rotation taking the pose at the measured motor angles to the true pose: q(theta + e) q(theta)^-1."""
        theta = np.asarray(theta, float)
        e = self.error_deg(theta, zeta_offset, direction)
        return (theta_to_q(*(theta + e)) * theta_to_q(*theta).inverse).normalised

    def _direction_motors(self):
        return {M: {d: [round(float(v), 4) for v in c[d]] for d in DIRECTIONS} for M, c in self.direction_coef.items()}

    def log_payload(self, path):
        """The profile the feed-forward applies, for the WORMPROFILE log line (ast.literal_eval-able, as PECLOG):
        the profile file can change after the session, so the log keeps the coefficients it ran with."""
        applied = self.meta.get('applied_profile') or {}
        out = {'path': str(path), 'worm_theta': float(self.worm_theta), 'harmonics': [int(h) for h in self.harmonics],
               'motors': {f'M{m + 1}': [round(float(v), 4) for v in self.coef[m]] for m in range(3)},
               'angle_reference': dict(self.angle_reference), 'applied': applied.get('created'),
               'learnt_from': self.meta.get('learnt_from'), 'setup': self.meta.get('profile_setup')}
        if self.direction_coef:
            out['direction_motors'] = self._direction_motors()
        return out

    def summary(self):
        """One line for the log, as the worm profile test's: per motor, amplitude @ peak (and SE, significance) of the
        applied fit when the file has it, else from the coefficients alone; 'off' for a motor without correction.
        Motors with forward and reverse profiles add them."""
        return self._summary() + direction_text(self.direction_coef, self.harmonics)

    def _summary(self):
        applied = (self.meta.get('applied_profile') or {}).get('motors')
        if applied:
            return profile_summary({'motors': applied})
        parts = []
        for m in range(3):
            c = self.coef[m]
            if not np.any(c):
                parts.append(f'M{m + 1} off')
                continue
            s = ''
            for j, h in enumerate(self.harmonics):
                a, b = float(c[2 * j]), float(c[2 * j + 1])
                if a or b:
                    s += f' h{h}' * (h != 1) + f' {np.hypot(a, b):.1f}" @{peak_deg(a, b, harmonic=h):.0f}'
            parts.append(f'M{m + 1}{s}')
        return '; '.join(parts)

    def save(self, path):
        core = {'worm_theta': float(self.worm_theta), 'harmonics': [int(h) for h in self.harmonics],
                'motors': {f'M{m + 1}': [round(float(v), 4) for v in self.coef[m]] for m in range(3)},
                'units': 'arcsec of motor angle; per harmonic: sin, cos; true angle = MCU angle + error'}
        if self.angle_reference:
            core['angle_reference'] = dict(self.angle_reference)
        if self.direction_coef:
            core['direction_motors'] = self._direction_motors()
        # the profile in use first (what a reader opens the file for), then the applied profile's details and other
        # provenance, the (long) test history last; provenance never overrides the profile
        meta = {k: v for k, v in self.meta.items() if k not in core and k not in ('profile_setup', 'profile_warnings')}
        if isinstance(meta.get('calibration_history'), list):
            meta['calibration_history'] = [_history_order(e) for e in meta['calibration_history']]
        d = {**core, **{k: v for k, v in meta.items() if k == 'applied_profile'},
             **{k: v for k, v in meta.items() if k not in ('applied_profile', 'calibration_history')},
             **{k: v for k, v in meta.items() if k == 'calibration_history'}}
        with open(path, 'w') as f:
            json.dump(d, f, indent=2)

    @classmethod
    def load(cls, path, setup=None):
        """The profile in `path`, or None if it is missing or malformed. With `setup` (make_setup), the closest of
        the setups' own profiles (setup_profiles, by setup_match: the same lens, else the same focal length, else the
        nearest focal length), else the generic profile (pooled over every setup: what is at hand);
        meta['profile_setup'] names the one chosen (None: the generic profile). A damaged setup profile is passed over
        for the next closest, and a damaged forward / reverse pair leaves that motor on its combined profile, so a bad
        entry never turns the correction off; meta['profile_warnings'] says what was skipped."""
        try:
            with open(path) as f:
                d = json.load(f)
            worm_theta = float(d['worm_theta'])
            generic = _profile_parts(d)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        if generic is None:
            return None
        warnings = list(generic[3])
        parts, own = generic, None
        profiles = d.get('setup_profiles')
        if setup is not None and isinstance(profiles, dict):
            ranked = []
            for name, sp in profiles.items():
                if not isinstance(sp, dict) or not isinstance(sp.get('setup'), dict):
                    warnings.append(f'setup profile {name!r} skipped: malformed')
                    continue
                try:
                    rank = setup_match(sp['setup'], setup)
                except (TypeError, ValueError, ZeroDivisionError):
                    warnings.append(f'setup profile {name!r} skipped: malformed setup')
                    continue
                if rank[0] < 3:
                    ranked.append((rank, name, sp))
            for _, name, sp in sorted(ranked, key=lambda r: r[0]):
                got = _profile_parts(sp)
                if got is None:
                    warnings.append(f'setup profile {name!r} skipped: malformed coefficients')
                    continue
                parts, own = got, name
                warnings += got[3]
                break
        harmonics, coef, extra, _ = parts
        meta = {k: v for k, v in d.items() if k not in ('worm_theta', 'harmonics', 'motors', 'units', 'angle_reference',
                                                        'direction_motors')}
        if setup is not None:
            meta['profile_setup'] = own
        if warnings:
            meta['profile_warnings'] = warnings
        return cls(worm_theta=worm_theta, harmonics=harmonics, coef=coef, meta=meta, **extra)


HISTORY_FIRST = ('test', 'created', 'status', 'approved', 'setup')   # a test record's keys a reader looks for first


def _history_order(entry):
    """A calibration_history record with HISTORY_FIRST at the top (in that order), then the rest as they were (the
    long samples last). A worm profile test from before the flags were kept gets them written out as they read --
    approved (they all pooled) and its setup unknown (null) -- so a test can be rejected, or its lens set, by editing
    the file."""
    if not isinstance(entry, dict):
        return entry
    if entry.get('test') == PROFILE_TEST:
        entry = {**entry, 'approved': entry.get('approved', True), 'setup': entry.get('setup')}
    first = {k: entry[k] for k in HISTORY_FIRST if k in entry}
    return {**first, **{k: v for k, v in entry.items() if k not in first}}


def _profile_parts(src):
    """(harmonics, coef (3, n), {angle_reference, direction_coef}, warnings) from a profile (the file's top level or a
    setup profile), or None if its harmonics or motors are unusable. Forward / reverse pairs that don't fit are
    dropped (that motor keeps its combined profile), with a warning."""
    try:
        harmonics = tuple(int(h) for h in src['harmonics'])
        n = 2 * len(harmonics)
        coef = np.array([src['motors'][f'M{m + 1}'] for m in range(3)], float)
        if not harmonics or coef.shape != (3, n) or not np.all(np.isfinite(coef)):
            return None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    angle_reference = src.get('angle_reference') if isinstance(src.get('angle_reference'), dict) else {}
    direction, warnings = {}, []
    raw = src.get('direction_motors') or {}
    for M, pair in (raw.items() if isinstance(raw, dict) else []):
        try:
            ok = M in MOTORS and all(np.asarray(pair[d], float).shape == (n,) and np.all(np.isfinite(pair[d]))
                                     for d in DIRECTIONS)
        except (KeyError, TypeError, ValueError):
            ok = False
        if ok:
            direction[M] = {d: list(pair[d]) for d in DIRECTIONS}
        else:
            warnings.append(f'{M} forward / reverse profiles skipped: malformed (its combined profile applies)')
    return harmonics, coef, {'angle_reference': angle_reference, 'direction_coef': direction}, warnings


def zeta_raw_offset(theta_raw, zeta):
    """theta_raw (518: the firmware's box attitude x the MCU motor angles, so M1 carries the session's compass / SPA
    heading) minus zeta (517: the MCU's own motor angles), per motor, wrapped to [-180, 180). Cached on each 517 so
    PECLOG can carry it: theta_raw - offset gives the motor angles at the 518 rate, the same every session."""
    if theta_raw is None or zeta is None:
        return None
    return [float((t - z + 180.0) % 360.0 - 180.0) for t, z in zip(theta_raw, zeta)]


class WormMixin:
    """Worm methods of SyncManager (see control.SyncManager): the feed-forward and the worm profile test's syncs."""

    def init_worm(self):
        """Create the worm state; called once from SyncManager.__init__."""
        self.corrQ_WFF = Quaternion()           # worm feed-forward: measured -> true pose, base frame (identity when off)
        self.worm_error_deg = np.zeros(3)       # each motor's worm gear correction now (deg of motor angle), for status
        self.worm_direction = np.zeros(3)       # each motor's direction of travel (+1, -1; 0 not yet moved): picks its
                                                # forward or reverse profile; kept while it stands (the same flank)
        self._worm_ff = None                    # WormFeedForward profile, loaded on first use
        self._worm_ff_path = None               # path it was loaded from (None: reload on next use)
        self.worm_test = None                   # WormProfileTest while the worm profile test runs

    # ── worm feed-forward ────────────────────────────────────────────────────────────────────
    def worm_profile_path(self):
        """The profile file: worm_profile.json in the data folder."""
        return str(WORM_PROFILE_PATH)

    def _worm_ff_profile(self):
        full, setup = self.worm_profile_path(), current_setup()
        if (full, setup) != self._worm_ff_path:                 # a new file, or the lens changed in the settings
            self._worm_ff_path = (full, setup)
            self._worm_ff = WormFeedForward.load(full, setup=setup)
            if self._worm_ff is None:
                self.logger.info(f"No worm gear profile at {full}: worm correction off")
            else:
                own = self._worm_ff.meta.get('profile_setup')
                want = setup_name(setup) or 'unset lens'
                which = (f"the {own} profile" + (f" (closest to {want})" if own != want else '')) if own else \
                    f"no profile for {want}: the generic profile"
                self.logger.info(f"WORMPROFILE CHOICE: {which}")
                for w in self._worm_ff.meta.get('profile_warnings', []):
                    self.logger.warning(f"WORMPROFILE: {w}")
                self.logger.info(f"WORMPROFILE SUMMARY: {self._worm_ff.summary()}")
                self.logger.info(f"WORMPROFILE {self._worm_ff.log_payload(full)}")
        return self._worm_ff

    def worm_ff_in_use(self):
        """The worm gear profile to correct with: when Config.advanced_pec_worm is on and worm_profile.json exists
        (on without a profile: a warning, once, and no correction), else None."""
        if not Config.advanced_pec_worm:
            self._worm_ff_warned = False
            return None
        prof = self._worm_ff_profile()
        if prof is None and not getattr(self, '_worm_ff_warned', False):
            self.logger.warning(f"PEC Worm Gear Correction is enabled but missing profile. Run Speed Calibration test {PROFILE_TEST} to create one.")
        self._worm_ff_warned = prof is None
        return prof

    def update_worm_ff(self, theta):
        """Refresh the worm feed-forward rotation for the current motor angles (deg): applied when the worm gear
        correction is in use (worm_ff_in_use), except while a worm calibration test measures the uncorrected worm."""
        self.update_worm_direction()
        prof = self.worm_ff_in_use() if self.worm_test is None else None
        offset = getattr(self.polaris, '_zeta_raw_offset', None)
        if prof is None:
            self.corrQ_WFF, self.worm_error_deg = Quaternion(), np.zeros(3)
            return
        self.worm_error_deg = prof.error_deg(theta, zeta_offset=offset, direction=self.worm_direction)
        self.corrQ_WFF = prof.correction_q(theta, zeta_offset=offset, direction=self.worm_direction)
        self._log_worm_in_use(prof)

    def worm_in_use_text(self, prof):
        """'200mm F4: M1 duplex, M2 fwd, M3 rev': the profile's setup ('generic': the generic profile, no setup's own)
        and each motor's profile now -- fwd / rev (its split profile, by its direction of travel), duplex (one profile
        for both directions, or a split motor not yet moved), off (no correction)."""
        coef = prof.motor_coef(self.worm_direction)
        parts = []
        for m, M in enumerate(MOTORS):
            if not np.any(coef[m]):
                parts.append(f'{M} off')
            elif M in prof.direction_coef and self.worm_direction[m]:
                parts.append(f"{M} {'fwd' if self.worm_direction[m] > 0 else 'rev'}")
            else:
                parts.append(f'{M} duplex')
        return f"{prof.meta.get('profile_setup') or 'generic'}: " + ', '.join(parts)

    def _log_worm_in_use(self, prof):
        """WORMPROFILE IN USE when the profile is loaded and whenever a motor's choice changes (it reverses)."""
        text = self.worm_in_use_text(prof)
        if (id(prof), text) != getattr(self, '_worm_in_use_logged', None):
            self._worm_in_use_logged = (id(prof), text)
            if self.logger:
                self.logger.info(f"WORMPROFILE IN USE: {text}")

    def update_worm_direction(self):
        """Each motor's direction of travel from the PID's feed-forward rate (tracking, slews, jogs), as the worm
        profile test reads its tracking direction; a motor standing still keeps its last one (its gear stays on that
        flank)."""
        omega = getattr(getattr(self.polaris, '_pid', None), 'omega_ff', None)
        if omega is None:
            return
        omega = np.asarray(omega, float)
        self.worm_direction = np.where(np.abs(omega) > TRACK_RATE_MIN_DPS, np.sign(omega), self.worm_direction)

    @staticmethod
    def _entry_angles(entry):
        theta = np.asarray(entry['theta'], float)
        zeta = entry.get('zeta')
        offset = theta - np.asarray(zeta, float) if zeta is not None else None
        return theta, offset, entry.get('wdir')        # wdir: the motors' directions then (None before v2.2 Beta 8)

    def entry_worm_q(self, entry):
        """The worm feed-forward rotation at a sync point, from the raw motor angles it keeps ('theta', and the MCU's
        'zeta') and the motors' directions then ('wdir'), with the profile in use now -- so QUEST and MAC predict it as
        the pointing is corrected at runtime. Identity when the correction is off, or for a sync point without its
        motor angles (saved before v2.2); a point without its directions uses each motor's combined profile."""
        prof = self.worm_ff_in_use()
        if prof is None or entry.get('theta') is None:
            return Quaternion()
        theta, offset, direction = self._entry_angles(entry)
        return prof.correction_q(theta, zeta_offset=offset, direction=direction)

    def entry_worm_error_deg(self, entry):
        """(3,) deg: the worm gear error at a sync point's raw motor angles, with the profile in use now (zeros when
        the correction is off or the point has no motor angles) -- MAC adds it to those angles."""
        prof = self.worm_ff_in_use()
        if prof is None or entry.get('theta') is None:
            return np.zeros(3)
        theta, offset, direction = self._entry_angles(entry)
        return prof.error_deg(theta, zeta_offset=offset, direction=direction)

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

    # ── worm profile test ────────────────────────────────────────────────────────────────────
    def _boresight_T(self, theta):
        az, alt, _ = q_to_azaltroll(self.pvQ_to_topoQ(theta_to_q(*theta)))
        return np.asarray(azalt_to_vector(az, alt), float)

    def pointing_jacobian(self, theta, eps_deg=0.01):
        """At motor angles theta (theta_pv space): the predicted boresight (topocentric unit vector), two tangent axes
        there (t1 horizontal, t2 up), and each motor's effect on the pointing along them (3 x 2, arcsec of sky per
        arcsec of motor angle)."""
        theta = np.asarray(theta, float)
        b0 = self._boresight_T(theta)
        t1 = np.cross([0.0, 0.0, 1.0], b0)
        t1 /= max(np.linalg.norm(t1), 1e-12)
        t2 = np.cross(b0, t1)
        J = np.zeros((3, 2))
        for m in range(3):
            e = np.zeros(3)
            e[m] = eps_deg
            d = (self._boresight_T(theta + e) - self._boresight_T(theta - e)) / (2 * eps_deg) * (180.0 / np.pi)
            J[m] = [d @ t1, d @ t2]
        return b0, t1, t2, J

    def worm_test_reach(self, theta, zeta, omega, duration_s):
        """The range of offsets (deg from theta, per motor) each motor can reach over a worm profile test that lasts
        duration_s: (lo, hi). Two limits, each with the motor's tracking travel over the test taken off the side it
        tracks towards:
          * the pointing envelope: a pose the mount can't take (M2 against the Alt/Roll limit) is clamped by
            reachable_azaltroll, so a step there never settles -- scanned along each motor from theta;
          * the motor limits (zeta): M1/M3 inside the unwind margin (an unwind mid-test would end it), M2 inside its
            hard limits."""
        theta = np.asarray(theta, float)
        zeta = np.asarray(zeta, float) if zeta is not None else None
        travel = np.asarray(omega, float) * duration_s
        lo, hi = np.full(3, -REACH_SCAN_DEG), np.full(3, REACH_SCAN_DEG)
        align = self.alignQ_B2T

        def reachable(t):
            az, alt, roll = q_to_azaltroll(align * theta_to_q(*t))
            r_az, r_alt, r_roll = reachable_azaltroll(az, alt, roll)
            return (abs(r_alt - alt) < 1e-3 and abs((r_az - az + 180) % 360 - 180) * np.cos(np.radians(alt)) < 1e-3
                    and abs((r_roll - roll + 180) % 360 - 180) < 1e-3)

        steps = np.arange(REACH_SCAN_STEP_DEG, REACH_SCAN_DEG + 1e-9, REACH_SCAN_STEP_DEG)
        for m in range(3):
            for sign, bound in ((+1, hi), (-1, lo)):
                for x in steps:
                    t = theta.copy()
                    t[m] += sign * x
                    if not reachable(t):
                        bound[m] = sign * (x - REACH_SCAN_STEP_DEG)
                        break
        if zeta is not None:
            safety = float(getattr(Config, 'zeta_safety_margin', 0.0))
            z_lo = np.array([Config.z1_min_limit + safety, Config.z2_min_limit, Config.z3_min_limit + safety], float)
            z_hi = np.array([Config.z1_max_limit - safety, Config.z2_max_limit, Config.z3_max_limit - safety], float)
            lo, hi = np.maximum(lo, z_lo - zeta), np.minimum(hi, z_hi - zeta)
        hi = hi - np.maximum(travel, 0.0)
        lo = lo - np.minimum(travel, 0.0)
        return lo, hi

    def motor_separation(self, theta):
        """(angle between the directions M1 and M3 move the field, deg; each motor's sensitivity): near 0 deg (Roll 0)
        their worms can't be told apart at this pose."""
        _, _, _, J = self.pointing_jacobian(theta)
        sens = np.linalg.norm(J, axis=1)
        cos13 = abs(J[0] @ J[2]) / max(sens[0] * sens[2], 1e-12)
        return float(np.degrees(np.arccos(min(1.0, cos13)))), [round(float(x), 3) for x in sens]

    def record_worm_sync(self, a_ra, a_dec, a_az, a_alt):
        """A plate-solve sync while the worm profile test runs: record it (not applied to any model) and step the motors
        when the test asks for it."""
        test, p = self.worm_test, self.polaris
        pid = p._pid
        theta_pv = np.array(pid.theta_pv, float)
        b0, t1, t2, J = self.pointing_jacobian(theta_pv)
        dv = np.asarray(azalt_to_vector(a_az, a_alt), float) - b0
        res = np.array([dv @ t1, dv @ t2]) * ARCSEC_PER_RAD
        theta_raw = np.array(p._theta_raw, float)
        offset = getattr(p, '_zeta_raw_offset', None)
        zeta = theta_raw - np.asarray(offset, float) if offset is not None else theta_raw
        r5 = lambda v: [round(float(x), 5) for x in v]
        sample = {'t': round(time.monotonic(), 3), 'time': datetime.datetime.now().isoformat(timespec='milliseconds'),
                  'zeta': r5(zeta), 'res': [round(float(x), 2) for x in res], 'J': [r5(row) for row in J],
                  'theta_raw': r5(theta_raw), 'zeta_offset': offset, 'theta_pv': r5(theta_pv),
                  'a_ra': a_ra, 'a_dec': a_dec, 'a_az': a_az, 'a_alt': a_alt}
        omega = np.asarray(getattr(pid, 'omega_ff', np.zeros(3)), float)
        track_dir = np.where(np.abs(omega) > TRACK_RATE_MIN_DPS, np.sign(omega), 0.0)
        step = test.on_sync(sample, track_dir=track_dir)
        if self.logger:
            if test.last_outcome == 'kept':
                k = test.samples[-1]
                timing = (f"settled {k['settle_s']} s after the step, " if k['settle_s'] is not None else '') + \
                         f"{k['since_settle_s']} s before this sync"
            elif test.last_outcome == 'moving':
                timing = 'motors not settled: discarded'
            else:
                timing = f'pointing jumped > {JUMP_ARCSEC:.0f}" from the last sample: discarded'
            # the pointing offset (solved - predicted, horizontal and up) is mostly the alignment model's error at this
            # pose plus drift -- hundreds of arcsec is normal; the fit removes it -- so it comes last, for analysis
            self.logger.info(f"WORM PROFILE TEST: sync {test.last_outcome}, position {test.index}/{len(test.positions)}, "
                             f"{timing}, solved ra {a_ra:.6f} h dec {a_dec:.5f} az {a_az:.5f} alt {a_alt:.5f}, "
                             f"pointing offset {res[0]:.1f}\" {res[1]:.1f}\", zeta {sample['zeta']}, "
                             f"theta_pv {sample['theta_pv']}")
        if step is not None:
            pid.step_motor_targets(step)


# ── worm profile test ──────────────────────────────────────────────────────────────────────────────
PROFILE_TEST = 'M1-M2-M3-WORM-PROFILE'
MOTORS = ('M1', 'M2', 'M3')
ARCSEC_PER_RAD = 206264.806
HARMONICS = (1, 2)
MIN_POSITIONS = 16            # fewer kept positions (after the start): NO DATA
MIN_SIGNIFICANCE = 4.0        # a motor's 1st harmonic amplitude / its standard error, for COMPLETED
MIN_H2_SIGNIFICANCE = 3.0     # a 2nd harmonic is applied only when at least this significant
MIN_SEPARATION_DEG = 10.0     # warn when M1 and M3 move the field within this angle (Roll ~0): their worms are less certain
ROLL_TARGET_DEG = 45.0        # the test first rotates to Roll +-this (the sign of the current roll; M1 and M3 separate by
                              # about the roll angle), and back afterwards. 2026-10-09 tests: |Roll| 45-60 (with Alt 35-45)
                              # gave the lowest SE for every motor; at Roll +-25-30 M1 and M3 are only ~25-30 deg apart
ROLL_TOLERANCE_DEG = 1.0      # already this close to the target roll: no rotation
SETTLE_ARCSEC = 10.0          # a step has settled when every motor holds within this of its target ...
SETTLE_HOLD_S = 1.0           # ... for this long
JUMP_ARCSEC = 300.0           # 2-D error change from the last kept sample that means the exposure caught the move
BACKLASH_DEG = 0.25           # a step against a motor's tracking direction overshoots by this, then approaches the
                              # position with tracking: tracking then turns each motor the way it arrived, with no
                              # backlash to take up (measured 150-620" on the real mount; ~350" drift per step without)
APPROACH_RELEASE_ARCSEC = 120.0  # the approach starts once every motor is within this of the overshoot (no hold): past
                              # the position by more than the backlash, without the slow final settle (~5 s per step)
TRACK_RATE_MIN_DPS = 1e-5     # a motor turning slower than this while tracking has no tracking direction
SETTLE_TIMEOUT_S = 90.0       # a position not settled this long after its step can't be reached: the test ends there
REACH_MARGIN_DEG = 0.5        # each motor's sweep keeps this far inside the range it can reach
REACH_SCAN_DEG = 12.0         # how far each way the reach check looks (beyond the sweep's +-7.5 deg)
REACH_SCAN_STEP_DEG = 0.1
CALIBRATION_HISTORY = 50      # tests kept in the profile's calibration_history (with their samples, ~60 KB each)
POOL_TESTS = 5                # the applied profile pools the last this many tests with a clean fit ...
POOL_MAX_RMS_ARCSEC = 20.0    # ... a residual below this (each COMPLETED, or POOR FIT only for too few sigma on its own)
POOLED_FIT_MAX_RMS_ARCSEC = 25.0  # a fit over several tests is COMPLETED below this: pooling adds the differences between
                              # tests (seeing, the gravity side), so it sits above the tests' own 12-18" (2026-10-09:
                              # every pool of 3-8 clean tests 18.9-21.7")
DIRECTION_POOL_MIN_TESTS = 3  # a motor gets forward and reverse profiles from this many tests each way it ran ...
DIRECTION_MIN_POSITIONS = 8   # ... (a test counts for a direction with this many positions arrived that way) ...
DIRECTION_SPLIT_MIN_SIGMA = 3.0   # ... when their pooled 1st harmonics differ by this many of their combined SE ...
DIRECTION_SPLIT_MIN_ARCSEC = 15.0  # ... and by more than one test's scatter about its pool (10-22" on the real mount,
                              # 2026-10-18: M2 forward 89" and reverse 31", 65" apart; M3 113" and 82", 36" apart)


def _legs(step_deg, pattern):
    out, x = [0.0], 0.0
    for sign, n in pattern:
        for _ in range(n):
            x += sign * step_deg
            out.append(x)
    return out


def _sweep(step_deg, steps_out, first, n):
    """n offsets (deg) sweeping back and forth across +-steps_out x step_deg from 0, first leg in direction `first`."""
    out, k, d = [0.0], 0, first
    for _ in range(n - 1):
        if abs(k + d) > steps_out:
            d = -d
        k += d
        out.append(k * step_deg)
    return out


# Motor offsets (deg) from the start at each of the 51 positions (50 steps, ~20 min at one solve every ~20-24 s): each motor sweeps
# back and forth across about +-7.5 deg -- ~2.5 worm turns -- with its own step and reversal points. Over only ~1.5
# turns (the 33-position schedule) a linear pointing trend mimics much of a worm cycle: on the real mount (2026-10-06)
# M2's terms correlated ~0.8 with the trend and two clean runs gave 41" and 100". The steps advance the worm phases at
# 45, 36 and 33.75 deg a step, avoiding simple ratios between one motor's 1st harmonic and another's 2nd (with 0.75
# and 0.375 deg steps, M3's 2nd harmonic advanced as fast as M1's 1st and, at Roll 0, could not be told apart).
POSITIONS = np.array([_sweep(0.75, 10, +1, 51),                           # M1 +-7.5 deg
                      _sweep(0.6, 12, -1, 51),                            # M2 +-7.2 deg
                      _sweep(0.5625, 13, +1, 51)]).T                      # M3 +-7.3 deg
SYNC_CYCLE_S = 23.5           # a solve-and-sync cycle (exposure, solve, wait) with the odd discarded sync: the test takes
                              # ~ positions x this, ~20 min (users report ~18 min; it was 17.5 s, ~15 min)
TEST_SUMMARY = f'{len(POSITIONS) - 1} steps, approx {round(len(POSITIONS) * SYNC_CYCLE_S / 60)} min'   # Raw Command column
QUAD_TREND_MIN_SPAN_DEG = 12.0  # a test sweeping every motor at least this far also fits a quadratic pointing trend


def fit_sweep(positions, lo, hi, margin=REACH_MARGIN_DEG):
    """Fit each motor's offsets (deg from the start, one column per motor) inside the range it can reach, [lo, hi]
    (deg of offset from the start): shift the motor's sweep just enough, or, where the range is narrower than the
    sweep, shrink the sweep onto the range. Returns (positions, scale per motor: 1 = full sweep); a motor whose sweep
    already fits is left alone. The first position may then be off the start: the test moves there first."""
    p = np.array(positions, float)
    scale = np.ones(p.shape[1])
    for m in range(p.shape[1]):
        a, b = lo[m] + margin, hi[m] - margin
        mn, mx = p[:, m].min(), p[:, m].max()
        if b <= a:                                   # no room at all: hold the motor at the middle of what it can reach
            p[:, m] = min(max((a + b) / 2, lo[m]), hi[m])
            scale[m] = 0.0
        elif mx - mn > b - a:                        # narrower than the sweep: shrink it onto the range
            scale[m] = (b - a) / (mx - mn)
            p[:, m] = a + (p[:, m] - mn) * scale[m]
        elif mx > b:
            p[:, m] -= mx - b
        elif mn < a:
            p[:, m] += a - mn
    return p, scale


class WormProfileTest:
    """The worm profile test: the step schedule (all motors), the step settling and the syncs it keeps."""

    def __init__(self, positions=POSITIONS, worm_theta=6.0, no_sync_timeout_s=60.0, now=None):
        self.positions = np.asarray(positions, float)
        self.worm_theta = worm_theta
        self.no_sync_timeout_s = no_sync_timeout_s
        self.last_sync = time.monotonic() if now is None else now   # start, then the last sync (kept or discarded)
        self.abort_reason = None                   # why the test was cut short (goto, jog, pulse guide, no syncs ...)
        self.index = 0                             # position the mount is at (or moving to)
        self.samples = []
        self.step_at = None                        # when the motors were told to step to this position (None: start)
        self.settled_at = None                     # when they settled there (None: still moving)
        self._within_since = None                  # since when every motor has been within SETTLE_ARCSEC
        self.clean_next = False                    # a sync arrived after settling: the next one's exposure is clean
        self.last_outcome = None                   # the last sync: 'kept', 'moving' or 'jump'
        self.discarded = {'moving': 0, 'jump': 0}
        self.settle_times = []                     # s from each step to settled
        self.approach = None                       # the move back onto the position after an overshoot (deg, per motor)
        self.arrival = None                        # each motor's direction arriving at the current position
        self.started = self.last_sync              # when the test started (settling at the start is timed from here)

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

    def settle_overdue(self, now, timeout_s=None):
        """The motors haven't settled on the current position within timeout_s of its step: it can't be reached (a
        motor held at a limit), and plate-solves arriving would otherwise keep the test waiting for ever."""
        if self.done or self.aborted or self.settled_at is not None:
            return False
        timeout_s = SETTLE_TIMEOUT_S if timeout_s is None else timeout_s
        return now - (self.step_at if self.step_at is not None else self.started) > timeout_s

    def direction(self, i):
        """Each motor's direction of travel arriving at position i (+1, -1; 0 at the start)."""
        return [0, 0, 0] if i == 0 else [int(x) for x in np.sign(self.positions[i] - self.positions[i - 1])]

    def track_settle(self, err_arcsec, now=None):
        """The largest of the motors' PID errors (arcsec) each control tick: marks the position settled once every
        motor has held within SETTLE_ARCSEC for SETTLE_HOLD_S (settled_at = when they got there). After an overshoot
        it returns the approach move (deg, per motor) for the caller to make once every motor is within
        APPROACH_RELEASE_ARCSEC of it, and settles after that."""
        if self.settled_at is not None or self.done or self.aborted:
            return None
        now = time.monotonic() if now is None else now
        if self.approach is not None:              # the overshoot is past the backlash: come back onto the position
            if abs(err_arcsec) >= APPROACH_RELEASE_ARCSEC:
                return None
            approach, self.approach, self._within_since = self.approach, None, None
            return approach
        if abs(err_arcsec) >= SETTLE_ARCSEC:
            self._within_since = None
            return None
        if self._within_since is None:
            self._within_since = now
        if now - self._within_since < SETTLE_HOLD_S:
            return None
        self.settled_at = self._within_since
        if self.step_at is not None:
            self.settle_times.append(round(self.settled_at - self.step_at, 2))
        return None

    def on_sync(self, sample, now=None, track_dir=None):
        """Record a sync (dict with 'res', the 2-D error) at the current position. Returns the step (deg, per motor)
        to make now, or None (sync discarded -- see last_outcome -- or the test is finished or aborted).
        track_dir: each motor's tracking direction (+1, -1, 0): a step against it overshoots by BACKLASH_DEG, and
        track_settle() then returns the approach back onto the position in the tracking direction."""
        if self.done or self.aborted:
            return None
        now = time.monotonic() if now is None else now
        self.last_sync = now
        if self.settled_at is None:
            return self._discard('moving')
        res = sample.get('res')
        last = self.samples[-1].get('res') if self.samples else None
        if (not self.clean_next and res is not None and last is not None
                and np.hypot(*(np.asarray(res) - np.asarray(last))) > JUMP_ARCSEC):
            self.clean_next = True
            return self._discard('jump')
        settle_s = None if self.step_at is None else round(self.settled_at - self.step_at, 2)
        self.samples.append({**sample, 'offset': [round(float(x), 4) for x in self.positions[self.index]],
                             'direction': self.arrival if self.arrival is not None else self.direction(self.index),
                             'settle_s': settle_s,
                             'since_settle_s': round(now - self.settled_at, 2)})
        self.last_outcome = 'kept'
        self.index += 1
        self.step_at, self.settled_at, self._within_since, self.clean_next = now, None, None, False
        self.approach = self.arrival = None
        if self.done:
            return None
        step = self.positions[self.index] - self.positions[self.index - 1]
        if track_dir is None:
            return step
        td, d = np.sign(np.asarray(track_dir, float)), np.sign(step)
        against = (d != 0) & (td != 0) & (d == -td)
        self.arrival = [int(x) for x in np.where(against, td, d)]
        if not against.any():
            return step
        self.approach = np.where(against, BACKLASH_DEG * td, 0.0)
        return step - self.approach                # overshoot: past the position, against tracking

    def _discard(self, why):
        self.discarded[why] += 1
        self.last_outcome = why
        return None

    def timing(self):
        """Settle times (s) and discarded syncs, for the result and the log."""
        st = self.settle_times
        return {'settle_median_s': round(float(np.median(st)), 1) if st else None,
                'settle_max_s': round(float(np.max(st)), 1) if st else None, 'discarded': dict(self.discarded)}


# ── the fit ───────────────────────────────────────────────────────────────────────────────────
def _phase(a, b):
    return float(np.degrees(np.arctan2(b, a)) % 360)


def peak_deg(a, b, harmonic=1):
    """The worm phase (deg, 0-360 over one worm turn: 360 x MCU angle / worm_theta) where a sin(h phi) + b cos(h phi)
    peaks (+A) -- the angle shown to users. The stored phase p = atan2(b, a) is a shift (A sin(phi + p)), so the
    peak is at (90 - p) / h; for a 2nd harmonic, the first of its two peaks."""
    return float(((90.0 - _phase(a, b)) % 360) / harmonic)


def profile_summary(result):
    """One line per fit for the log: each motor's 1st harmonic amplitude @ peak angle, its SE and significance, and
    whether it is applied; a 2nd harmonic when applied."""
    parts = []
    for m, v in (result.get('motors') or {}).items():
        s = f'{m} {v["amplitude"]:.1f}"±{v["se"]:.1f} @{v.get("peak", (90 - v["phase"]) % 360):.0f} ({v["significance"]:.1f}σ'
        s += ')' if v.get('applied', True) else ', off)'
        if len(v.get('coef', [])) > 2 and any(v['coef'][2:]):
            s += f' h2 {v["h2_amplitude"]:.1f}" @{v.get("h2_peak", 0):.0f}'
        parts.append(s)
    return '; '.join(parts)


N_NUISANCE = 2 + 4 + 6 + 3 + 12  # per test: 2-D offset, quadratic drift in time, linear pointing trend, backlash,
                                  # quadratic pointing trend (wide tests only, else zero columns)


def worm_columns(m, harmonic_index, direction, harmonics=HARMONICS, split=()):
    """The design column of motor m's harmonic (its sin; cos is the next) for a sample arriving in `direction`:
    a motor in `split` has its reverse worm in its own columns after the three motors' (forward) ones."""
    nh = len(harmonics)
    if m in split and direction < 0:
        return (3 * nh + list(split).index(m) * nh + harmonic_index) * 2
    return (m * nh + harmonic_index) * 2


def profile_design(tests, worm_theta=6.0, harmonics=HARMONICS, split=()):
    """The joint fit's design: (X, y, tests) with two rows (the tangent axes) per sample of each test (samples before the
    first step left out). Columns: per motor and harmonic, J_m x sin and cos of the worm phase (for the motors in
    `split`, separate forward and reverse worms, by the direction each sample arrived: worm_columns); then per test
    N_NUISANCE columns (offset, drift in time, pointing trend, and each motor's backlash moving forward)."""
    tests = [[s for s in t if any(s.get('direction', [0, 0, 0]))] for t in tests]
    tests = [t for t in tests if t]
    split = tuple(split)
    nw = (3 + len(split)) * 2 * len(harmonics)
    rows, y = [], []
    for k, t in enumerate(tests):
        tt = np.array([s['t'] for s in t], float)
        ts = (tt - tt.mean()) / max(np.ptp(tt), 1e-9)
        off = np.array([s['offset'] for s in t], float)
        offs = (off - off.mean(0)) / np.maximum(np.ptp(off, 0), 1e-9)
        base = nw + N_NUISANCE * k
        # a motor that arrives at every position the same way (each step approached with tracking) has no backlash
        # to fit: its column would only duplicate the offset
        varies = [len({s['direction'][m] for s in t}) > 1 for m in range(3)]
        # the pointing model's error is not linear across a wide test: there, also a quadratic trend in the offsets
        wide = bool(np.all(np.ptp(off, 0) >= QUAD_TREND_MIN_SPAN_DEG))
        quad = np.column_stack([offs[:, 0] ** 2, offs[:, 1] ** 2, offs[:, 2] ** 2, offs[:, 0] * offs[:, 1],
                                offs[:, 0] * offs[:, 2], offs[:, 1] * offs[:, 2]]) if wide else np.zeros((len(t), 6))
        for i, s in enumerate(t):
            J = np.asarray(s['J'], float)
            ph = 2 * np.pi * np.asarray(s['zeta'], float) / worm_theta
            for a in range(2):
                r = np.zeros(nw + N_NUISANCE * len(tests))
                for m in range(3):
                    for j, h in enumerate(harmonics):
                        c = worm_columns(m, j, s['direction'][m], harmonics, split)
                        r[c], r[c + 1] = J[m, a] * np.sin(h * ph[m]), J[m, a] * np.cos(h * ph[m])
                r[base + a] = 1.0
                r[base + 2 + 2 * a], r[base + 3 + 2 * a] = ts[i], ts[i] ** 2
                for m in range(3):
                    r[base + 6 + 2 * m + a] = offs[i, m]
                    r[base + 12 + m] = J[m, a] * (s['direction'][m] > 0) if varies[m] else 0.0
                r[base + 15 + 6 * a:base + 21 + 6 * a] = quad[i]
                rows.append(r)
                y.append(float(s['res'][a]))
    return np.array(rows), np.array(y), tests


def fit_worm_profile(tests, worm_theta=6.0, harmonics=HARMONICS, split=()):
    """Every motor's worm from the samples of one or more worm profile tests (a list of sample lists). Each sample's
    2-D error is fitted as sum over motors of J_m (the motor's effect on the pointing) x [its worm, a sin + b cos per
    harmonic of 360 x zeta_m / worm_theta, + its backlash when moving forward], plus, per test, a 2-D offset, a
    quadratic drift in time and a linear trend in each motor's offset (the pointing model across the field)
    (profile_design). Returns a dict: status (COMPLETED / POOR FIT / NO DATA), motors {M#: amplitude, phase (the shift p
    of A sin(phi + p)), peak (the worm phase of the peak, shown to users), se, coef
    (applied: a, b per harmonic, a 2nd harmonic only when significant), h2_amplitude, h2_se, significance, backlash},
    checks. With `split` (motor indices), those motors' forward and reverse worms are fitted apart: 'motors' has the
    forward one, 'split' {M: {'forward': info, 'reverse': info}} both."""
    split = tuple(split)
    X, y, tests = profile_design(tests, worm_theta, harmonics, split)
    n_pos = sum(len(t) for t in tests)
    out = {'status': 'NO DATA', 'motors': {}, 'checks': {'positions': n_pos, 'tests': len(tests)}}
    if not tests or max(len(t) for t in tests) < MIN_POSITIONS:
        return out
    nw = (3 + len(split)) * 2 * len(harmonics)
    n_nuis = N_NUISANCE
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    dof = max(len(y) - np.linalg.matrix_rank(X), 1)        # zero columns (narrow tests' quadratic trend) don't count
    s2 = float(r @ r) / dof
    cov = s2 * np.linalg.pinv(X.T @ X)
    J = np.array([s['J'] for t in tests for s in t], float)
    cos13 = np.abs(np.sum(J[:, 0] * J[:, 2], axis=1)) / np.maximum(np.linalg.norm(J[:, 0], axis=1) * np.linalg.norm(J[:, 2], axis=1), 1e-12)
    sep = np.degrees(np.arccos(np.clip(cos13, 0.0, 1.0)))
    def motor_info(m, direction):
        cm, info, measured = [], {}, False
        for j, h in enumerate(harmonics):
            c = worm_columns(m, j, direction, harmonics, split)
            a, b = float(beta[c]), float(beta[c + 1])
            A = float(np.hypot(a, b))
            se = float(np.sqrt(max((cov[c, c] + cov[c + 1, c + 1]) / 2, 0.0)))
            if h == 1:
                # each motor stands on its own: applied only when its worm is measured (a small one, like M1's
                # ~21" on the real mount, is left uncorrected rather than failing the others)
                measured = A / max(se, 1e-9) >= MIN_SIGNIFICANCE
                info.update(amplitude=round(A, 2), phase=round(_phase(a, b), 1), peak=round(peak_deg(a, b), 1),
                            se=round(se, 2),
                            significance=round(A / max(se, 1e-9), 1), applied=bool(measured))
                cm += [a, b]
            else:
                info.update(h2_amplitude=round(A, 2), h2_phase=round(_phase(a, b), 1),
                            h2_peak=round(peak_deg(a, b, harmonic=2), 1), h2_se=round(se, 2))
                cm += [a, b] if A / max(se, 1e-9) >= MIN_H2_SIGNIFICANCE else [0.0, 0.0]
        bl = [float(beta[nw + n_nuis * k + 12 + m]) for k in range(len(tests))]
        info['backlash'] = round(float(np.mean(bl)), 1)
        info['coef'] = [round(float(x), 4) for x in cm] if info['applied'] else [0.0] * len(cm)
        return info

    applied_any = False
    for m in range(3):
        info = motor_info(m, +1)
        out['motors'][MOTORS[m]] = info
        applied_any |= info['applied']
        if m in split:
            out.setdefault('split', {})[MOTORS[m]] = {'forward': info, 'reverse': motor_info(m, -1)}
            applied_any |= out['split'][MOTORS[m]]['reverse']['applied']
    out['checks'].update(rms_arcsec=round(float(np.sqrt(s2)), 2),
                         separation_deg=[round(float(sep.min()), 1), round(float(sep.max()), 1)])
    # COMPLETED: a clean fit (a residual like a test that pools; a looser limit for a pool of tests) that measured at
    # least one motor's worm
    limit = POOL_MAX_RMS_ARCSEC if len(tests) <= 1 else POOLED_FIT_MAX_RMS_ARCSEC
    out['status'] = 'COMPLETED' if applied_any and np.sqrt(s2) < limit else 'POOR FIT'
    return out


def profile_text(ff):
    """A profile in use (WormFeedForward or None) as the row shows profiles: each motor's 1st harmonic amplitude @ peak
    angle, 'off' for an uncorrected motor, 'none' without a profile."""
    if ff is None or 1 not in ff.harmonics:
        return 'none'
    j = 2 * list(ff.harmonics).index(1)
    parts = []
    for m, M in enumerate(MOTORS):
        a, b = (float(x) for x in ff.coef[m][j:j + 2])
        parts.append(f'{M} off' if a == 0 and b == 0 else f'{M} {np.hypot(a, b):.0f}"@{peak_deg(a, b):.0f}')
    return ' '.join(parts)


def baseline_text(ff):
    """The row's Baseline: the current (approved) profile, labelled; 'none' without one. It corrects the motors only
    while PEC Worm Gear Correction is on."""
    return 'none' if ff is None else f'current profile {profile_text(ff)}' + direction_text(ff.direction_coef, ff.harmonics)


def row_fields_from_file(path):
    """The row's columns from the profile file (its latest test, the pooled profile and the current profile), e.g.
    after Approve/Reject changed the current profile."""
    ff = _load_or_new(path)
    tests = [e for e in ff.meta.get('calibration_history', []) if e.get('test') == PROFILE_TEST and e.get('samples')]
    current = WormFeedForward.load(path, setup=current_setup())
    if not tests:
        return {'dps': baseline_text(current)}
    return profile_row_fields(fit_worm_profile([tests[-1]['samples']]), pooled_profile(path, with_last=True), current)


def profile_row_fields(latest, pooled, current):
    """The worm profile row's columns, each labelled (Pilot shows the label under the motors): dps (Baseline) = the
    current profile (`current`, a WormFeedForward or None); test_result = the pool approving the last test gives, per
    motor amplitude @ peak angle; test_change = how far approving moves each motor from the baseline; test_stdev = the pooled profile's uncertainty and
    significance per motor, and the residual rms of that fit (pooled: with a warning when the last test was left out)."""
    def h1(info):
        if not info:
            return '-'
        if not info.get('applied', True):
            return 'off'                       # not measured: left uncorrected (its amplitude is only noise)
        peak = info.get('peak', (90.0 - info['phase']) % 360)          # results saved before 'peak' was stored
        return f'{info["amplitude"]:.0f}"@{peak:.0f}'
    res = pooled if pooled.get('motors') else latest
    n_pooled = pooled['checks'].get('tests', 1) if pooled.get('motors') else 1
    source = f'last {n_pooled} tests pooled' if n_pooled > 1 else 'last test'
    setup = pooled.get('setup') or {}
    if setup.get('name'):
        # short, for Pilot on a phone: nothing when the tests are the lens's own
        source += '' if setup.get('matched') == 'lens' else \
            f" {setup['name'].split()[0]}" if setup.get('matched') else ' (all setups)'
    fields = {'dps': baseline_text(current),
              'test_result': f'{source} ' + ' '.join(f'{m} {h1(res["motors"].get(m))}' for m in MOTORS)
                             + direction_text(split_motors(pooled)),
              'test_change': '', 'test_stdev': ''}
    if not latest.get('motors'):
        return fields
    change = []
    for m_i, m in enumerate(MOTORS):
        new = np.asarray(res['motors'][m]['coef'][:2], float)
        old = np.zeros(2) if current is None or 1 not in current.harmonics else \
            np.asarray(current.coef[m_i][2 * list(current.harmonics).index(1):][:2], float)
        change.append(f'{m} {np.hypot(*(new - old)):+.0f}"')
    warn = ' ⚠ poor fit' if latest['status'] != 'COMPLETED' else ''
    if latest['checks'].get('separation_deg', [90, 90])[1] < MIN_SEPARATION_DEG:
        warn += ' ⚠ low separation (Roll ~0)'
    fields['test_change'] = 'from baseline ' + ' '.join(change) + warn
    # each motor's amplitude uncertainty and significance (amplitude / SE: applied from MIN_SIGNIFICANCE), as Test Result
    unc = ' '.join(f'{m} ±{v["se"]:.1f}" {v["significance"]:.1f}σ' for m, v in res['motors'].items() if 'se' in v)
    # the residual of the fit Test Result shows: the pooled fit's, flagging a last test the pool left out; or the last
    # test's own, with its positions when it stopped short
    n = latest['checks'].get('positions', 0)
    last_rms = latest['checks'].get('rms_arcsec', 0)
    split_fit = pooled.get('checks', {}).get('split_fit')
    warn_out = ''
    if split_fit:
        rms = f'direction split {split_fit["tests"]} tests {split_fit["rms_arcsec"]:.1f}" rms'
    elif n_pooled > 1:
        rms = f'pooled {pooled["checks"].get("rms_arcsec", 0):.1f}" rms'
        left_out = not _poolable({'test': PROFILE_TEST, 'status': latest['status'], 'samples': True, 'result': latest})
        warn_out = f' ⚠ last test left out: {last_rms:.1f}" rms' if left_out else ''
    else:
        rms = f'last test {last_rms:.1f}" rms' + (f', {n} positions' if n < len(POSITIONS) - 1 else '')
    fields['test_stdev'] = rms + (f' {unc}' if unc else '') + warn_out
    return fields


STALE_ROW_STATUS = ('UNTESTED', 'NO DATA', 'STOPPED')   # and PENDING...: the last attempt left no result to show


def startup_row_fields(path, status):
    """The row's columns at driver start, from the profile file (the saved row only has the last attempt's, blank after
    a NO DATA test). Its status is kept unless it is stale: then APPROVED when the last test is in the pool (so the
    button takes it out), else what the pool with it would be (COMPLETED: the button adds it)."""
    current = WormFeedForward.load(path, setup=current_setup())
    tests = [] if current is None else [e for e in current.meta.get('calibration_history', [])
                                        if e.get('test') == PROFILE_TEST and e.get('samples')]
    latest, pooled = (fit_worm_profile([tests[-1]['samples']]), pooled_profile(path, with_last=True)) if tests else ({}, {})
    fields = profile_row_fields(latest, pooled, current) if tests else {'dps': baseline_text(current)}
    if status in STALE_ROW_STATUS or str(status).startswith('PENDING'):
        fields['test_status'] = 'UNTESTED' if not tests else 'APPROVED' if tests[-1].get('approved', True) else \
            row_status(latest, pooled)
    return fields


# ── profile file ──────────────────────────────────────────────────────────────────────────────
def _load_or_new(path):
    ff = WormFeedForward.load(path) if os.path.exists(path) else None
    return ff if ff is not None else WormFeedForward(worm_theta=6.0, harmonics=HARMONICS)


def make_setup(focal_length, focal_ratio=None):
    """{'focal_length': mm, 'focal_ratio': f-number or None}: the setup (lens) a test ran with and a profile is for,
    or None when the focal length is unset."""
    try:
        fl = float(focal_length)
    except (TypeError, ValueError):
        return None
    if not fl > 0:
        return None
    try:
        fr = float(focal_ratio)
    except (TypeError, ValueError):
        fr = None
    return {'focal_length': fl, 'focal_ratio': fr if fr and fr > 0 else None}


def setup_name(setup):
    """'300mm F2.8' (the setup_profiles key, and what the log and row show), or None."""
    if not setup or not setup.get('focal_length'):
        return None
    fr = setup.get('focal_ratio')
    return f"{float(setup['focal_length']):g}mm" + (f' F{float(fr):g}' if fr else '')


def current_setup():
    """The setup the profile is for, from config focal_length and focal_ratio, or None when unset. The payload's weight
    and balance change the worm the gears show (a 300 mm load's M3 fits sat 70-130" from the 200 mm ones), so tests
    pool, and profiles apply, per setup -- the closest one there is (setup_match)."""
    return make_setup(getattr(Config, 'focal_length', None), getattr(Config, 'focal_ratio', None))


def setup_match(have, want):
    """How well a test's or profile's setup `have` stands in for `want`, smaller is closer: (tier, focal length
    distance, focal ratio distance), tier 0 the same lens (focal length and ratio), 1 the same focal length, 2 another
    focal length (the nearer, by ratio of focal lengths, the closer), 3 unknown (before setups were kept)."""
    try:
        fl_h, fl_w = float(have['focal_length']), float(want['focal_length'])
    except (TypeError, ValueError, KeyError):
        return (3, 0.0, 0.0)
    if not (fl_h > 0 and fl_w > 0 and np.isfinite(fl_h) and np.isfinite(fl_w)):
        return (3, 0.0, 0.0)
    fl_d = abs(np.log(fl_h / fl_w))
    fr_h, fr_w = have.get('focal_ratio'), want.get('focal_ratio')
    fr_d = abs(float(fr_h) - float(fr_w)) if fr_h and fr_w else 0.0
    same_fl = fl_d < 1e-6
    same_fr = (fr_h is None and fr_w is None) or (fr_h is not None and fr_w is not None and fr_d < 1e-6)
    return (0 if same_fl and same_fr else 1 if same_fl else 2, round(float(fl_d), 6), round(fr_d, 6))


def store_profile_test(path, samples, result, timing=None, setup=None):
    """Keep a test (its fit, timing and samples, and the setup it ran with) in the profile file's calibration_history
    as the last test, rejected (out of the pools) until it is approved (set_last_test_approved). Every test is kept,
    approved or rejected; only approved ones pool."""
    ff = _load_or_new(path)
    setup = current_setup() if setup is None else setup
    entry = {'test': PROFILE_TEST, 'created': datetime.datetime.now().isoformat(timespec='seconds'),
             'status': result['status'], 'approved': False, 'setup': setup,
             'result': {k: v for k, v in result.items() if k != 'status'}, 'timing': timing, 'samples': samples}
    ff.meta['calibration_history'] = (list(ff.meta.get('calibration_history', [])) + [entry])[-CALIBRATION_HISTORY:]
    ff.save(path)


def last_test(path):
    """The profile file's last worm profile test entry, or None."""
    tests = [e for e in _load_or_new(path).meta.get('calibration_history', []) if e.get('test') == PROFILE_TEST]
    return tests[-1] if tests else None


def set_last_test_approved(path, approved=True):
    """Approve or reject the last test -- its flag in the history, as often as wanted: approved tests pool -- and
    rebuild the profiles from the approved tests (rebuild_profiles). False without a last test."""
    ff = _load_or_new(path)
    history = ff.meta.get('calibration_history', [])
    tests = [e for e in history if e.get('test') == PROFILE_TEST]
    if not tests:
        return False
    tests[-1]['approved'] = bool(approved)
    rebuild_profiles(ff).save(path)
    return True


def _poolable(entry):
    """An approved test whose fit is clean: COMPLETED, or POOR FIT only because one test's worms are too uncertain on their own
    (real mount: a clean 12\" rms test reached 3.3 sigma) -- not one spoiled by something the model lacks (33\" rms)."""
    checks = (entry.get('result') or {}).get('checks') or {}
    return (entry.get('test') == PROFILE_TEST and entry.get('approved', True)      # approved (tests before the flag: all)
            and entry.get('status') in ('COMPLETED', 'POOR FIT')
            and entry.get('samples') and checks.get('positions', 0) >= MIN_POSITIONS
            and checks.get('rms_arcsec', float('inf')) < POOL_MAX_RMS_ARCSEC)


def setup_tests(entries, setup):
    """The poolable tests for a setup: those run with the same lens; when there are none, those at the same focal
    length; else every poolable test (another setup's, or tests from before setups were kept: what is at hand).
    Returns (entries, matched: 'lens', 'focal length' or None)."""
    poolable = [e for e in entries if _poolable(e)]
    if setup is not None:
        for tier, label in ((0, 'lens'), (1, 'focal length')):
            same = [e for e in poolable if setup_match(e.get('setup'), setup)[0] == tier]
            if same:
                return same, label
    return poolable, None


def _h1_phasor(info):
    return np.array(phasor_ab(info['amplitude'], info['phase']))


def phasor_ab(amplitude, phase):
    """(a, b) of a harmonic from its amplitude and phase (a sin + b cos = A sin(phi + phase))."""
    return amplitude * np.cos(np.radians(phase)), amplitude * np.sin(np.radians(phase))


def direction_positions(samples, m, sign):
    """How many of a test's positions motor m arrived at moving `sign` (+1 forward, -1 reverse)."""
    return sum(1 for s in samples if s.get('direction') and np.sign(s['direction'][m]) == sign)


def direction_pools(entries, worm_theta=6.0):
    """Per motor, whether its worm differs with its direction of travel (the gear flank the load rests on: on the real
    mount M2 measured 89" forward and 31" reverse), and its forward and reverse worms when it does. One joint fit
    (fit_worm_profile with `split`) gives each candidate motor separate forward and reverse worms, by the direction
    each sample arrived, over the last POOL_TESTS tests that ran it each way (DIRECTION_MIN_POSITIONS positions); a
    candidate needs DIRECTION_POOL_MIN_TESTS such tests each way. It splits when both worms are measured and differ by
    DIRECTION_SPLIT_MIN_SIGMA of their combined SE and by DIRECTION_SPLIT_MIN_ARCSEC (more than one test's scatter),
    and the fit is clean; a motor that doesn't is refitted with one worm. Returns {M: {'split', 'tests' [forward,
    reverse], 'reason', and when split 'difference' ("), 'sigma', 'forward', 'reverse' (fit info), 'pooled_tests'}}, and
    the split fit (None when no motor splits)."""
    out, groups = {}, {}
    for m, M in enumerate(MOTORS):
        groups[m] = {sign: [e for e in entries if direction_positions(e['samples'], m, sign) >= DIRECTION_MIN_POSITIONS]
                     [-POOL_TESTS:] for sign in (1, -1)}
        n = [len(groups[m][1]), len(groups[m][-1])]
        out[M] = {'split': False, 'tests': n}
        if min(n) < DIRECTION_POOL_MIN_TESTS:
            out[M]['reason'] = f'{n[0]} forward, {n[1]} reverse tests (needs {DIRECTION_POOL_MIN_TESTS} each way)'
    split = [m for m in range(3) if 'reason' not in out[MOTORS[m]]]
    if not split:
        return out, None
    chosen = {id(e) for m in split for g in groups[m].values() for e in g}
    pool = [e for e in entries if id(e) in chosen]                     # in history order
    fit = None
    while split:
        fit = fit_worm_profile([e['samples'] for e in pool], worm_theta=worm_theta, split=split)
        keep = []
        for m in split:
            M = MOTORS[m]
            f, r = fit['split'][M]['forward'], fit['split'][M]['reverse']
            diff = float(np.hypot(*(_h1_phasor(f) - _h1_phasor(r))))
            sigma = diff / max(float(np.hypot(f['se'], r['se'])), 1e-9)
            out[M].update(difference=round(diff, 1), sigma=round(sigma, 1))
            if not (f['applied'] and r['applied']):
                out[M]['reason'] = 'its forward or reverse worm was not measured'
            elif sigma < DIRECTION_SPLIT_MIN_SIGMA or diff < DIRECTION_SPLIT_MIN_ARCSEC:
                out[M]['reason'] = f'forward and reverse differ by {diff:.0f}" ({sigma:.1f} SE): one profile'
            else:
                keep.append(m)
        if keep == split:
            break
        split = keep
    if split and fit['status'] != 'COMPLETED':
        for m in split:
            out[MOTORS[m]]['reason'] = f'the split fit is poor ({fit["checks"].get("rms_arcsec", 0):.1f}" rms)'
        split = []
    for m in split:
        M = MOTORS[m]
        out[M].update(split=True, forward=fit['split'][M]['forward'], reverse=fit['split'][M]['reverse'],
                      pooled_tests=len(pool), rms_arcsec=fit['checks'].get('rms_arcsec'))
        out[M].pop('reason', None)
    return out, (fit if split else None)


def pooled_profile(path, worm_theta=6.0, setup=None, with_last=False):
    """fit_worm_profile over the last POOL_TESTS approved tests with a clean fit in the profile file for this setup
    (pool_history). with_last: as if the last test were approved too -- what approving it would give (the row's
    Test Result)."""
    history = [dict(e) for e in _load_or_new(path).meta.get('calibration_history', [])]
    if with_last:
        tests = [e for e in history if e.get('test') == PROFILE_TEST]
        if tests:
            tests[-1]['approved'] = True
    return pool_history(history, worm_theta=worm_theta, setup=current_setup() if setup is None else setup)


def pool_history(history, worm_theta=6.0, setup=None):
    """fit_worm_profile over the last POOL_TESTS approved tests with a clean fit for `setup` (each with its own offset,
    drift and trend; setup_tests), or a NO DATA result if there are none -- plus 'directions' (direction_pools over the
    setup's tests) and 'setup' {'name', 'matched': 'lens', 'focal length', or None when no test was run with it}."""
    entries, matched = setup_tests(history, setup)
    out = fit_worm_profile([e['samples'] for e in entries[-POOL_TESTS:]], worm_theta=worm_theta)
    if out.get('motors'):
        out['directions'], split_fit = direction_pools(entries, worm_theta=worm_theta)
        if split_fit is not None:
            # the split fit models every motor's direction, so it measures the motors that don't split better than
            # the combined one (whose residual carries the split motors' two worms): their profile comes from it, and
            # it decides the status. The split motors keep the combined fit, for when their direction is unknown.
            for M in MOTORS:
                if not out['directions'][M]['split']:
                    out['motors'][M] = split_fit['motors'][M]
            out['status'] = split_fit['status']
            out['checks']['split_fit'] = {'tests': split_fit['checks']['tests'],
                                          'rms_arcsec': split_fit['checks'].get('rms_arcsec')}
    out['setup'] = {'name': setup_name(setup), 'matched': matched}
    return out


def split_motors(pooled):
    """{M: {'forward': coef, 'reverse': coef}} for the motors the pooled profile splits by direction."""
    return {M: {d: list(v[d]['coef']) for d in DIRECTIONS}
            for M, v in (pooled.get('directions') or {}).items() if v.get('split')}


def direction_summary(pooled):
    """The log's account of each motor's direction pools: split (forward and reverse, how far apart) or why not."""
    parts = []
    for M, v in (pooled.get('directions') or {}).items():
        if v.get('split'):
            f, r = v['forward'], v['reverse']
            parts.append(f'{M} split: forward {f["amplitude"]:.0f}"@{f["peak"]:.0f} ({v["tests"][0]} tests), reverse '
                         f'{r["amplitude"]:.0f}"@{r["peak"]:.0f} ({v["tests"][1]} tests), {v["difference"]:.0f}" apart '
                         f'({v["sigma"]:.1f} SE)')
        else:
            parts.append(f'{M} one profile: {v.get("reason", "")}')
    setup = pooled.get('setup') or {}
    where = f"setup {setup.get('name') or 'unset'} (tests matched: {setup.get('matched') or 'none, all setups'})"
    return where + ('; ' + '; '.join(parts) if parts else '')


def direction_text(direction_coef, harmonics=HARMONICS):
    """' M2 fwd 89"@258 rev 31"@290' (short, for Pilot on a phone) for the motors with forward and reverse
    profiles, '' for none."""
    if not direction_coef or 1 not in harmonics:
        return ''
    j = 2 * list(harmonics).index(1)
    parts = []
    for M, c in direction_coef.items():
        s = [f'{short} {np.hypot(*np.asarray(c[d], float)[j:j + 2]):.0f}"@{peak_deg(*np.asarray(c[d], float)[j:j + 2]):.0f}'
             for d, short in zip(DIRECTIONS, ('fwd', 'rev'))]
        parts.append(f'{M} ' + ' '.join(s))
    return ' ' + ' '.join(parts)


def row_status(latest, pooled):
    """The worm profile row's status after a test, before it is approved: COMPLETED when the pool with it passes (so
    it can be approved), even if the test alone did not; else the test's own status."""
    return 'COMPLETED' if pooled.get('motors') and pooled.get('status') == 'COMPLETED' else latest['status']


def _profile_snapshot(ff):
    """The coefficients a profile applies (setup_profiles keeps one per setup)."""
    out = {'harmonics': list(ff.harmonics), 'motors': {m: [float(v) for v in ff.coef[i]] for i, m in enumerate(MOTORS)},
           'angle_reference': dict(ff.angle_reference)}
    if ff.direction_coef:
        out['direction_motors'] = ff._direction_motors()
    return out


def rebuild_profiles(ff):
    """The profiles, rebuilt from the approved tests (a WormFeedForward to save, with ff's history): the generic
    profile in use (pooled over every setup's tests: what a lens without its own uses, and with no lens set) and each
    lens's own (setup_profiles: pooled over the tests run with it), with forward and reverse profiles for the motors
    that split by direction. A pool that doesn't pass (COMPLETED) gives no profile: the generic one then corrects
    nothing, a lens falls back to the closest lens's or the generic one."""
    history = ff.meta.get('calibration_history', [])
    created = datetime.datetime.now().isoformat(timespec='seconds')
    meta = {k: v for k, v in ff.meta.items() if k not in ('applied_profile', 'setup_profiles')}

    def build(pooled):
        ok = pooled['status'] == 'COMPLETED'
        coef = np.array([pooled['motors'][m]['coef'] for m in MOTORS], float) if ok else np.zeros((3, 2 * len(HARMONICS)))
        return WormFeedForward(worm_theta=ff.worm_theta, harmonics=HARMONICS, coef=coef, meta=meta,
                               angle_reference={m: 'zeta' for m in MOTORS},
                               direction_coef=split_motors(pooled) if ok else {}), ok

    generic_pool = pool_history(history, worm_theta=ff.worm_theta, setup=None)
    new, ok = build(generic_pool)
    if ok:
        new.meta['applied_profile'] = {'created': created, 'tests': generic_pool['checks']['tests'],
                                       'motors': generic_pool['motors'], 'directions': generic_pool.get('directions')}
    setups = {}
    for e in history:
        name = setup_name(e.get('setup'))
        if name is None or name in setups or not _poolable(e):
            continue
        pooled = pool_history(history, worm_theta=ff.worm_theta, setup=e['setup'])
        if pooled['setup']['matched'] != 'lens':
            continue
        own, ok = build(pooled)
        if ok:
            setups[name] = {**_profile_snapshot(own), 'setup': e['setup'], 'created': created,
                            'tests': pooled['checks']['tests'], 'motors_fit': pooled['motors'],
                            'directions': pooled.get('directions')}
    if setups:
        new.meta['setup_profiles'] = setups
    return new
