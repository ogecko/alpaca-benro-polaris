"""
Backlash Compensation (advanced_backlash, driver/control_backlash.py): the PID controls each motor's output shaft, a
dead band of backlash_deg after the motor, while a goto completes and through a planned tracking reversal, so the
motor finishes engaged the way it tracks and the camera doesn't fall behind by the slack.

The MCU measures each motor's angle before the gearbox, so a motor that finishes a goto moving against its tracking
direction arrives (by its own angle) while the output shaft still lags by the backlash: Slew & Center corrections then
land several arcminutes off (nina01 2026-10-11: Albaldah 12.5' -> 9.7' -> 2.2'). The twin models the backlash as a dead
band between the motor angle (measured) and the output shaft (the pointing).
"""
import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

from config import Config
from control_backlash import BacklashCompensator, PUSH_DPS, PUSH_ENGAGE_ERR_ARCSEC, HOLD_ARCSEC, MAX_CROSSINGS, TURN_LEAD_SEC
from kinematics import azaltroll_to_theta_ik, q_to_azaltroll, theta_to_q
from sim_digital_twin import Twin
from test_motion_outcomes import radec_sep_arcmin, run_goto

BACKLASH = 0.1                          # deg (360"), within the 150-620" measured on the real mount
POSE = (304.0, 69.9, -40.0)             # high in the north-west, as Albaldah on 2026-10-11
STEP = 5 / 60                           # deg: a Slew & Center correction
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
SMC_BEFORE_TURN = (161.7, 43.7, 13.8)   # the SMC from Sydney ~5 min before M2 turned (2026-10-11, 21:19)
ARCSEC = 3600.0


def config(on=True, slack=BACKLASH, **extra):
    return {'coordinated_speed_control': True, 'advanced_backlash': on, 'backlash_deg': [slack] * 3, **extra}


def tracking_twin(monkeypatch, on=True, slack=BACKLASH, twin_backlash=BACKLASH, pose=POSE, settle_s=30):
    tw = Twin(monkeypatch, config=config(on, slack), backlash_deg=twin_backlash)
    tw.place(azaltroll_to_theta_ik(*pose))
    tw.start_tracking()
    tw.run(settle_s)                    # tracking takes the slack up in each motor's tracking direction
    return tw


def aligned_radec(tw, flank=None):
    """The output shafts' pointing with the engaged offset removed (as an alignment taken while tracking does):
    engaged on flank (default each motor's tracking direction now). A motor with no tracking direction (under 0.5"/s,
    at its turning point) has no engaged side for anything to restore: it counts at its motor angle."""
    if flank is None:
        w = np.asarray(tw.pid.omega_ff) * ARCSEC
        theta = np.where(np.abs(w) > 0.5, tw.true_theta + np.sign(w) * tw.backlash / 2, tw.theta)
    else:
        theta = tw.true_theta + flank * tw.backlash / 2
    az, alt, _ = q_to_azaltroll(theta_to_q(*theta))
    return tw.polaris.altaz2radec(alt, az)


def engaged(tw):
    """Per tracking motor: the output shaft trails the motor by half its dead band in the tracking direction."""
    d = np.sign(tw.pid.omega_ff)
    lead = (tw.theta - tw.true_theta) * d
    return [bool(lead[m] > 0.9 * tw.backlash[m] / 2 - 1e-9) for m in range(3) if d[m] != 0]


def correction(tw, d_ra, d_dec, settle_s=5.0):
    """A Slew & Center correction of STEP in RA/Dec, then an exposure's worth of tracking: (seconds to complete,
    pointing error in arcmin as the alignment sees it)."""
    cosd = math.cos(math.radians(tw.pid.delta_sp[1]))
    done, _, _ = run_goto(tw, lambda: tw.slew_relative(ra=d_ra * STEP / max(cosd, 0.1) / 15, dec=d_dec * STEP))
    tw.run(settle_s)
    return done, radec_sep_arcmin(tw.pid.delta_sp[0] / 15, tw.pid.delta_sp[1], *aligned_radec(tw))


# ── the compensator on its own ────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def comp(monkeypatch):
    for key, value in config().items():
        monkeypatch.setattr(Config, key, value, raising=False)
    return BacklashCompensator()


TRACK = np.array([10.0, -5.0, 0.0]) / ARCSEC        # M1 tracks +, M2 -, M3 barely moves (deg/s)
HALF = BACKLASH / 2


def test_switched_off_it_never_adjusts(comp, monkeypatch):
    monkeypatch.setattr(Config, 'advanced_backlash', False)
    assert not np.any(comp.update([1.0, 45.0, 3.0], TRACK, True, True))
    assert not np.any(comp.push([1.0, 1.0, 1.0], [1.0, 45.0, 3.0], 0.2))


def test_engaged_the_way_it_tracks_the_motor_reads_its_own_angle(comp):
    assert not np.any(comp.update([1.0, 45.0, 3.0], TRACK, True, True))
    assert np.allclose(comp.flank, [1, -1, 0])          # M3 has no tracking direction: never compensated


def test_reversing_inside_the_slack_holds_the_output_until_it_is_crossed(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    adj = comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, True)     # M1 back 0.06 deg: inside its 0.1 deg slack
    assert adj[0] == pytest.approx(-0.06)                            # the output hasn't moved
    adj = comp.update([1.0 - 0.15, 45.0, 3.0], TRACK, True, True)     # past the far flank: the output follows, 0.1 behind
    assert adj[0] == pytest.approx(-BACKLASH)
    adj = comp.update([1.0 - 0.15 + BACKLASH, 45.0, 3.0], TRACK, True, True)     # back the tracking way: engaged again
    assert adj[0] == pytest.approx(0.0)


def test_ordinary_tracking_and_guiding_see_the_motor_angles(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, False)
    adj = comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, False)    # a guide pulse reversing M1: no goto, no turn
    assert not np.any(adj) and not np.any(comp.active)


def test_after_a_goto_a_motor_stays_compensated_until_it_is_engaged(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, True)           # the goto ends with M1's slack open
    assert comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, False)[0] == pytest.approx(-0.06)
    assert comp.update([1.0 + 0.06, 45.0, 3.0], TRACK, True, False)[0] == pytest.approx(0.0)    # crossed: engaged
    assert not comp.active[0]
    assert not np.any(comp.update([1.0, 45.0, 3.0], TRACK, True, False))    # released: guiding sees motor angles


def test_a_planned_reversal_is_latched_with_the_old_flank_until_the_next_goto(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    turns = [(0, 100.0, 1.0, 1e-6)]                                  # M1 turns at t = 100 s
    comp.update([1.0, 45.0, 3.0], TRACK, True, False, turns, now=100.0 - TURN_LEAD_SEC - 1)
    assert not comp.latched[0]
    comp.update([1.0, 45.0, 3.0], TRACK, True, False, turns, now=100.0 - TURN_LEAD_SEC + 1)
    assert comp.latched[0] and comp.active[0]
    reversed_ = TRACK * [-1, 1, 1]                                    # after the turn M1 tracks the other way
    adj = comp.update([1.0 - 0.06, 45.0, 3.0], reversed_, True, False, turns, now=150.0)
    assert comp.flank[0] == 1 and adj[0] == pytest.approx(-0.06)      # still the flank the alignment was learnt on
    adj = comp.update([1.0 - 0.2, 45.0, 3.0], reversed_, True, False, turns, now=200.0)
    assert adj[0] == pytest.approx(-BACKLASH)                         # carried: the motor runs the slack ahead
    comp.update([1.0 - 0.2, 45.0, 3.0], reversed_, True, True, turns, now=300.0)     # a goto
    assert not comp.latched[0] and comp.flank[0] == -1               # re-engages the way it now tracks
    comp.update([1.0 - 0.2, 45.0, 3.0], reversed_, True, False, turns, now=310.0)
    assert not comp.latched[0]                                        # that turn is done with


def test_a_motor_too_slow_to_load_its_gear_is_left_alone(comp):
    slow = np.array([10.0, 0.01, -5.0]) / ARCSEC                     # M2 at 0.01"/s: no side to engage
    comp.update([1.0, 45.0, 3.0], slow, True, True)
    adj = comp.update([1.0, 45.0 + 0.03, 3.0], slow, True, True)
    assert adj[1] == 0.0 and not comp.active[1]


def test_a_turn_latches_only_a_motor_engaged_on_its_old_flank(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, True)           # a goto leaves M1 inside its slack ...
    turns = [(0, 100.0, 1.0, 1e-6)]
    comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, False, turns, now=95.0)    # ... right at its turning point
    assert not comp.latched[0]                                        # no tracked flank to keep
    comp.update([1.0 + 0.1, 45.0, 3.0], TRACK, True, False, turns, now=96.0)     # engaged again before the turn
    assert comp.latched[0]


def test_taking_up_until_every_compensated_motor_is_engaged(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    assert not comp.taking_up()
    comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, True)          # M1 inside its slack
    assert comp.taking_up()
    comp.update([1.0 + 0.1, 45.0, 3.0], TRACK, True, True)           # crossed: engaged
    assert not comp.taking_up()


def test_the_push_only_goes_towards_the_tracking_flank_and_slows_into_it(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    comp.update([1.0 - 0.06, 45.0, 3.0], TRACK, True, True)          # M1 inside its slack (0.06 to its tracking flank)
    theta = [1.0 - 0.06, 45.0, 3.0]
    small = np.array([(PUSH_ENGAGE_ERR_ARCSEC - 1) / ARCSEC, 0.0, 0.0])
    assert not np.any(comp.push(small, theta, 0.2))                   # PID noise: no push
    towards = np.array([60 / ARCSEC, 0.0, 0.0])                       # M1 tracks +: the target is ahead
    assert comp.push(towards, theta, 0.2)[0] == pytest.approx(PUSH_DPS)
    omega = comp.push(towards, [1.0 - 0.001, 45.0, 3.0], 0.2)         # 0.001 deg left: a share of it per tick
    assert 0 < omega[0] < PUSH_DPS and omega[0] * 0.2 < 0.001
    assert not np.any(comp.push(-10 * towards, theta, 0.2))           # never back across, however large the error


def test_an_engaged_motor_a_little_ahead_holds_instead_of_reversing(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)                  # engaged, M1 tracks +, M2 -
    behind = np.array([-(HOLD_ARCSEC - 10) / ARCSEC, 0.0, 0.0])       # M1 ran ahead: its target is behind
    assert comp.holding(behind)[0]
    omega = comp.clutch(np.array([-20.0, -5.0, 1.0]) / ARCSEC, behind)
    assert omega[0] == 0.0 and omega[1] == pytest.approx(-5.0 / ARCSEC)  # held at zero, not reversed; M2 untouched
    far = np.array([-(HOLD_ARCSEC + 10) / ARCSEC, 0.0, 0.0])          # a real move back: not held
    assert not comp.holding(far)[0]


def test_a_motor_crossing_its_slack_again_and_again_is_given_up_until_the_next_goto(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    towards = np.array([60 / ARCSEC, 0.0, 0.0])
    theta = 1.0
    for i in range(MAX_CROSSINGS + 1):
        comp.update([theta, 45.0, 3.0], TRACK, True, True)            # engaged the way it tracks (+)
        theta -= BACKLASH + 0.02                                      # something drives it back past the slack
        comp.update([theta, 45.0, 3.0], TRACK, True, True)            # ... all the slack ahead again
        comp.push(np.zeros(3), [theta, 45.0, 3.0], 0.2)               # (a fresh push each time)
        comp.push(towards, [theta, 45.0, 3.0], 0.2)
        theta += BACKLASH                                             # it crosses
    assert comp.given_up[0] and not comp.active[0]
    comp.update([theta, 45.0, 3.0], TRACK, True, False)
    comp.update([theta, 45.0, 3.0], TRACK, True, True)                # the next goto
    assert not comp.given_up[0]


def test_not_tracking_resets_it(comp):
    comp.update([1.0, 45.0, 3.0], TRACK, True, True)
    assert not np.any(comp.update([1.5, 45.0, 3.0], TRACK, False, True)) and comp.output is None


# ── on the twin ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_switched_off_small_corrections_land_off_by_the_backlash(monkeypatch):
    tw = tracking_twin(monkeypatch, on=False)
    errs = [correction(tw, *d)[1] for d in DIRECTIONS]
    assert max(errs) > 2.0, errs                     # the bug, reproduced: 360" of slack left in a motor


def test_corrections_land_with_every_motor_engaged(monkeypatch):
    """All but the odd one: a quick reversal's overshoot between the 518 samples (M3's held ~0.6 s) can move the
    output further than the estimate sees (control_backlash.py, limits)."""
    tw = tracking_twin(monkeypatch)
    errs, ok = [], 0
    for d in DIRECTIONS:
        done, err = correction(tw, *d)
        assert done is not None and done < 40.0, (d, done)          # ~12-17 s (off: 4-6 s, two legs: ~19 s)
        errs.append(err)
        ok += all(engaged(tw))
    assert ok >= 6 and sorted(errs)[-3] < 0.15 and max(errs) < 1.5, (ok, errs)     # off: 0.5-4.9'


def test_a_larger_goto_lands_engaged(monkeypatch):
    tw = tracking_twin(monkeypatch)
    cosd = math.cos(math.radians(tw.pid.delta_sp[1]))
    done, _, _ = run_goto(tw, lambda: tw.slew_relative(ra=3.0 / cosd / 15, dec=-3.0))
    tw.run(5.0)
    err = radec_sep_arcmin(tw.pid.delta_sp[0] / 15, tw.pid.delta_sp[1], *aligned_radec(tw))
    assert done is not None and err < 0.25 and all(engaged(tw)), (done, err, engaged(tw))


@pytest.mark.parametrize('slack, twin_backlash', [
    (1.3 * BACKLASH, BACKLASH),                      # backlash_deg 30% too large
    (0.7 * BACKLASH, BACKLASH),                      # ... 30% too small
    (BACKLASH, [BACKLASH, 0.0, BACKLASH]),           # gravity holds M2 on one flank: no slack to take up
])
def test_a_wrong_backlash_is_still_better_than_none(monkeypatch, slack, twin_backlash):
    """Too small leaves the shortfall open; too large overshoots by the excess while the motor is still compensated.
    Either way well short of what's left uncompensated."""
    errs = {}
    for on in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            tw = tracking_twin(mp, on=on, slack=slack, twin_backlash=twin_backlash)
            errs[on] = []
            for d in DIRECTIONS:
                done, err = correction(tw, *d)
                assert done is not None, d
                errs[on].append(err)
        finally:
            mp.undo()
    assert np.median(errs[True]) < 0.5 * np.median(errs[False]), errs
    assert max(errs[True]) < max(errs[False]), errs


def test_tracking_through_a_planned_reversal_keeps_the_camera_on_target(monkeypatch):
    """The SMC's M2 reversal: switched off, the camera falls behind by the slack while the motor crosses it (the drift
    bump on 2026-10-11); compensated, the motor is driven through it and runs the slack ahead of its old path."""
    drift = {}
    for on in (False, True):
        tw = tracking_twin(monkeypatch, on=on, pose=SMC_BEFORE_TURN, settle_s=60)
        flank = np.sign(tw.pid.omega_ff)                  # the flank the alignment was learnt on
        tw.output = tw.theta - flank * tw.backlash / 2    # engaged, as after hours of tracking (M2 creeps at 0.17"/s)
        if on:                                           # ... and so the compensator's estimate of it
            tw.pid.backlash.output = np.asarray(tw.polaris._theta_raw, float) - flank * BACKLASH / 2
        target = lambda: (tw.pid.delta_sp[0] / 15, tw.pid.delta_sp[1])
        start = radec_sep_arcmin(*target(), *aligned_radec(tw, flank)) * 60
        tw.run(900)                                      # M2 turns ~3 min in
        drift[on] = radec_sep_arcmin(*target(), *aligned_radec(tw, flank)) * 60 - start
        assert np.sign(tw.pid.omega_ff[1]) != flank[1]   # M2 did reverse
        if on:
            assert tw.pid.backlash.latched[1]
    assert drift[False] > 150, drift                     # ~200": the camera fell behind by the slack
    assert abs(drift[True]) < 60, drift


@pytest.mark.parametrize('pose', [(300.0, 40.0, 45.0), (240.0, 40.0, -45.0)])   # M1/M2 barely moving
def test_guiding_is_unchanged(monkeypatch, pose):
    """A motor barely moving reverses under every other guide pulse; compensating that became a limit cycle, so
    ordinary guiding isn't compensated: the same guiding, on or off."""
    from sim_guider import SimGuider

    class OutputGuider(SimGuider):
        def encoder_radec(self):                         # the camera follows the output shafts, not the motors
            az, alt, _ = q_to_azaltroll(self.tw.polaris._sm.alignQ_B2T * theta_to_q(*self.tw.true_theta))
            ra_h, dec = self.tw.polaris.altaz2radec(alt, az)
            return ra_h * 15.0, dec

    rms = {}
    for on in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            tw = tracking_twin(mp, on=on, pose=pose, settle_s=60)
            walk = np.cumsum(np.random.default_rng(1).normal(0, 0.4 / ARCSEC, (800, 2)), axis=0)
            g = OutputGuider(tw, drift=lambda t: tuple(walk[min(int(t), len(walk) - 1)]), seeing_arcsec=0.7, seed=1)
            g.start()
            g.guide(300)
            rms[on] = np.hypot(*g.error_rms_arcsec(since_s=60))
            assert not np.any(tw.pid.backlash.active)
        finally:
            mp.undo()
    assert rms[True] == pytest.approx(rms[False], rel=0.05), rms


def test_tracking_restore_finishes_with_every_motor_engaged(monkeypatch, tmp_path):
    """After a driver restart the Polaris has run its last speed command, so the mount can be ahead of its target: the
    catch-up then turns every motor back against tracking. Restore completes like a goto, so compensated it finishes
    with the slack taken up; off, the camera trails by up to the backlash until tracking takes it up again."""
    import asyncio
    import logging
    import tracking_restore as tr
    from polaris import Polaris

    results = {}
    for on in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            tw = tracking_twin(mp, on=on)
            state = tr.capture(True, tw.pid, 0, [0.0, 0.0, 0.0])
            ahead = np.sign(tw.pid.omega_ff) * 0.3                     # each motor 0.3 deg ahead the way it tracks
            tw2 = Twin(mp, config=config(on), backlash_deg=BACKLASH)
            tw2.place(tw.theta + ahead)
            tw2.output = tw2.theta - np.sign(tw.pid.omega_ff) * BACKLASH / 2   # engaged: it was running forwards
            p = tw2.polaris
            p.logger = logging.getLogger('test')

            async def start_tracking():
                tw2.start_tracking()
            p.start_tracking = start_tracking
            asyncio.run(Polaris._restore_tracking(p, state))
            assert tw2.pid.move_pending()
            t0, done = tw2.clock.t, None
            while tw2.clock.t - t0 < 60 and done is None:
                tw2.run(0.2)
                if not tw2.pid.move_pending():                            # the restore's completion callback ran
                    done = tw2.clock.t - t0
            tw2.run(5.0)
            target = (tw2.pid.delta_sp[0] / 15, tw2.pid.delta_sp[1])
            results[on] = (done, radec_sep_arcmin(*target, *aligned_radec(tw2)), all(engaged(tw2)))
        finally:
            mp.undo()
    assert results[True][0] is not None and results[True][0] < 40 and results[True][1] < 0.25 and results[True][2], results
    assert results[False][1] > 1.0, results                            # off: the slack left open


def test_off_by_default():
    Config.load()
    assert Config.advanced_backlash is False
    assert len(Config.backlash_deg) == 3
