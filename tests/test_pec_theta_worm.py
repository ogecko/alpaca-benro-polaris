"""
Tests for the theta-space PEC experiment in utility/pe_analysis.py: a worm profile per MOTOR -- each motor's
angle error as sin/cos of its worm phase -- mapped to RA/Dec at each pose (sky_weights: the rotation about the
motor's axis split along the pole, the Dec axis and the boresight, as the driver's equatorial axes), fitted on
RA and Dec drift jointly, and replayed as PEC: EMA follows the drift with the profile removed, plus the
profile's own rate from the current motor angles.

Synthetic segments carry a known motor-space worm on M1 and M3 at different poses (motor angles, latitude),
so recovery, transfer between poses and causal learning can be checked.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from pe_analysis import (WORM_THETA, worm_features, sky_weights, fit_worm, WormProfile,
                         replay_worm_pec_rate, causal_worm_pec_rate, replay_pec_rate, rate_scores, PecModel, Segment)

EMA = PecModel('EMA 7.5m', 450)
H = (1, 2)
LAT = -33.65
TRUE = np.zeros(3 * 2 * len(H))
TRUE[0:4] = [10.0, 6.0, 0.0, 3.0]                           # M1: h1 sin/cos, h2 sin/cos (arcsec of M1 angle)
TRUE[8:12] = [20.0, -12.0, 6.0, 4.0]                        # M3


def part(seed, hours=2.5, rates=(12.0, 1.0, 14.0), start=(30.0, 40.0, None), lat=LAT, phase_deg=0.0, coef=TRUE,
         trend=(6.0, -3.0), noise=2.0, dt=10.0):
    """(t, ra, dec, theta, lat): motors at `rates` deg/hr from `start`; drift = per-axis linear trend + the
    motor-space worm mapped to RA/Dec at each pose + noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(0, hours * 3600, dt)
    s3 = rng.uniform(-60, 60) if start[2] is None else start[2]
    theta = np.column_stack([start[0] + rates[0] * t / 3600, start[1] + rates[1] * t / 3600, s3 + rates[2] * t / 3600])
    ra, dec = WormProfile(coef, WORM_THETA, H).drift(theta + [phase_deg, 0, phase_deg], lat)
    ra = ra + trend[0] * t / 60 + rng.normal(0, noise, len(t))
    dec = dec + trend[1] * t / 60 + rng.normal(0, noise, len(t))
    return t, ra, dec, theta, lat


def guide_rms(p, rates, dt=120):
    t, ra, dec = p[0], p[1], p[2]
    r = [rate_scores(t, y, {'m': r}, guide_intervals_s=(dt,), warmup_s=1800)['guide_rms'][dt]['m']
         for y, r in ((ra, rates[0]), (dec, rates[1]))]
    return float(np.hypot(*r))


def ema(p):
    return replay_pec_rate(p[0], p[1], EMA), replay_pec_rate(p[0], p[2], EMA)


# ── mapping between a motor's angle error and RA/Dec ─────────────────────

def test_at_the_pole_an_m1_error_is_pure_ra():
    # latitude 90: the vertical M1 axis is the celestial pole, so M1 only ever moves RA
    theta = np.array([[30.0, 40.0, 10.0], [200.0, 25.0, -40.0], [95.0, 60.0, 5.0]])
    w = sky_weights(theta, 90.0)
    assert w.shape == (3, 2, 3)
    assert np.allclose(np.abs(w[:, 0, 0]), 1.0, atol=1e-6)
    assert np.allclose(w[:, 1, 0], 0.0, atol=1e-6)


def test_an_m2_error_moves_the_boresight_and_so_shows_in_ra_or_dec():
    w = sky_weights(np.array([[30.0, 40.0, 0.0]]), LAT)
    assert np.hypot(w[0, 0, 1], w[0, 1, 1]) > 0.5


def test_worm_features_repeat_every_worm_turn_of_each_motor():
    th = np.array([[10.0, 20.0, 30.0]])
    f = worm_features(th, WORM_THETA, H)
    assert f.shape == (1, 3 * 2 * len(H))
    for m in range(3):
        shifted = th.copy()
        shifted[0, m] += WORM_THETA
        assert np.allclose(worm_features(shifted, WORM_THETA, H), f)


# ── fitting and replay ───────────────────────────────────────────────────

def test_fit_recovers_the_motor_profile_from_parts_at_different_poses():
    parts = [part(k, start=(30.0 + 50 * k, 25.0 + 15 * k, None), trend=(4.0 * k - 5, 2.0 - k)) for k in range(3)]
    prof = fit_worm(parts, harmonics=H)
    assert np.abs(prof.coef - TRUE).max() < 0.15 * np.abs(TRUE).max()


def test_zero_profile_replays_exactly_as_ema():
    p = part(1)
    zero = WormProfile(np.zeros_like(TRUE), WORM_THETA, H)
    for got, want in zip(replay_worm_pec_rate(*p[:5], zero, EMA), ema(p)):
        assert np.allclose(got, want, atol=1e-9)


def test_the_true_profile_leaves_much_less_drift_for_the_guider_than_ema():
    p = part(2)
    true = WormProfile(TRUE, WORM_THETA, H)
    assert guide_rms(p, replay_worm_pec_rate(*p[:5], true, EMA)) < 0.6 * guide_rms(p, ema(p))


def test_a_profile_learnt_at_other_poses_and_latitudes_transfers():
    prof = fit_worm([part(3, start=(20.0, 30.0, None)), part(4, start=(150.0, 55.0, None), lat=-20.0)], harmonics=H)
    p = part(5, start=(280.0, 70.0, None), lat=-40.0, rates=(9.0, 2.0, 17.0))
    assert guide_rms(p, replay_worm_pec_rate(*p[:5], prof, EMA)) < 0.7 * guide_rms(p, ema(p))


def test_no_transfer_when_each_session_has_its_own_motor_angle_reference():
    prof = fit_worm([part(6, phase_deg=0.0), part(7, start=(150.0, 55.0, None), phase_deg=2.2)], harmonics=H)
    p = part(8, start=(280.0, 50.0, None), phase_deg=4.4)
    assert guide_rms(p, replay_worm_pec_rate(*p[:5], prof, EMA)) > 0.9 * guide_rms(p, ema(p))


def test_causal_learning_from_the_segment_so_far_beats_ema_on_a_long_worm_segment():
    p = part(9, hours=4.0)
    assert guide_rms(p, causal_worm_pec_rate(*p[:5], EMA, harmonics=H)) < 0.8 * guide_rms(p, ema(p))


def test_causal_learning_is_causal():
    p = part(10, hours=3.0)
    full = causal_worm_pec_rate(*p[:5], EMA, harmonics=H)
    cut = len(p[0]) * 2 // 3
    head = causal_worm_pec_rate(p[0][:cut], p[1][:cut], p[2][:cut], p[3][:cut], p[4], EMA, harmonics=H)
    for f, h in zip(full, head):
        assert np.allclose(f[:cut], h, atol=1e-9)


def test_a_motor_turning_less_than_one_worm_turn_is_not_fitted():
    # M2 moves 2.5 deg here: its worm terms would only mimic the trend
    prof = fit_worm([part(k) for k in (14, 15)], harmonics=H)
    assert np.allclose(prof.coef[4:8], 0.0)
    assert np.abs(prof.coef[8:]).max() > 1.0


def test_without_a_worm_the_fitted_profile_is_small_and_changes_little():
    zero = np.zeros_like(TRUE)
    prof = fit_worm([part(k, coef=zero) for k in (11, 12)], harmonics=H)
    p = part(13, coef=zero)
    assert np.abs(prof.coef).max() < 1.5
    assert guide_rms(p, replay_worm_pec_rate(*p[:5], prof, EMA)) == pytest.approx(guide_rms(p, ema(p)), rel=0.05)


# ── benchmark helpers used by analyse_pec_theta.ipynb ────────────────────

def seg(name, session, seed, **kw):
    t, ra, dec, th, lat = part(seed, **kw)
    return Segment(name=name, session=session, t=t, ra=ra, dec=dec, theta=th)


def test_worm_benchmark_scores_every_tier_against_ema():
    from pe_analysis import worm_benchmark, relative_to
    segs = [seg('a#0', 'a', 20), seg('a#1', 'a', 21, start=(120.0, 50.0, None)),
            seg('b#0', 'b', 22, start=(220.0, 35.0, None)), seg('c#0', 'c', 23, start=(300.0, 60.0, None))]
    df = worm_benchmark(segs, EMA, lat_of=lambda session: LAT, raw_theta={'a#0', 'a#1', 'b#0', 'c#0'},
                        guide_intervals_s=(120,), harmonics=H)
    assert set(df['model']) == {'no_pec', EMA.name, 'worm: hindsight', 'worm: same session', 'worm: other sessions',
                                'worm: live'}
    assert set(df['axis']) == {'ra', 'dec'}
    rel = relative_to(df, EMA.name)
    assert rel.loc['worm: other sessions', (120, 'n')] == 4
    assert rel.loc['worm: same session', (120, 'n')] == 2          # only session a has another segment
    assert rel.loc['worm: same session', (120, 'vs ref')] < 0.7     # a motor-space profile survives a pose change
    assert rel.loc['worm: other sessions', (120, 'vs ref')] < 0.7
    assert rel.loc[EMA.name, (120, 'vs ref')] == pytest.approx(1.0)


def test_other_sessions_tier_needs_raw_motor_angles_from_the_same_mount():
    from pe_analysis import worm_benchmark
    segs = [seg('a#0', 'a', 24), seg('b#0', 'b', 25, start=(150.0, 50.0, None)), seg('c#0', 'c', 26)]
    same_mount = lambda s1, s2: {s1, s2} != {'a', 'c'}
    df = worm_benchmark(segs, EMA, lat_of=lambda session: LAT, raw_theta={'a#0', 'b#0'}, same_mount=same_mount,
                        guide_intervals_s=(120,), harmonics=H)
    assert set(df.loc[df['model'] == 'worm: other sessions', 'seg']) == {'a#0', 'b#0'}   # c has no raw angles


def test_worm_angle_control_is_lowest_at_the_true_worm_angle():
    from pe_analysis import worm_angle_control
    segs = [seg(f'{k}#0', str(k), 30 + k, start=(40.0 * k, 30.0 + 10 * k, None)) for k in range(3)]
    ctl = worm_angle_control(segs, (4.3, WORM_THETA, 9.1), EMA, lat_of=lambda session: LAT, harmonics=H)
    assert ctl.idxmin() == pytest.approx(WORM_THETA)
    assert ctl[WORM_THETA] < 0.7


def test_sky_weights_match_the_driver_kinematics():
    """Vectorised maths == kinematics.theta_to_jacobian + calc_equatorial_axes_B (pyquaternion) at random poses."""
    from quaternion import Q as Quaternion                         # the driver's quaternion class
    from kinematics import theta_to_jacobian, theta_to_q, calc_equatorial_axes_B
    rng = np.random.default_rng(0)
    theta = np.column_stack([rng.uniform(0, 360, 20), rng.uniform(5, 85, 20), rng.uniform(-80, 80, 20)])
    for lat in (-33.65, 43.6):
        w = sky_weights(theta, lat)
        for k, th in enumerate(theta):
            p, d, v = calc_equatorial_axes_B(theta_to_q(*th), Quaternion(), lat)
            c = np.linalg.solve(np.column_stack([p, d, v]), theta_to_jacobian(*th))
            assert np.allclose(w[k], c[:2], atol=1e-9)


# ── per-motor view: partial residuals ────────────────────────────────────

def test_worm_phase_table_finds_the_same_phase_in_every_session_with_a_consistent_worm():
    from pe_analysis import worm_phase_table, phase_consistency
    segs = [seg(f'{k}#0', str(k), 50 + k, start=(30.0 + 40 * k, 30.0 + 8 * k, None)) for k in range(4)]
    tab = worm_phase_table(segs, lat_of=lambda session: LAT, harmonics=H)
    m3 = tab[tab['motor'] == 'M3']
    assert len(m3) == 4 and (m3['turns'] >= 2).all()
    assert set(tab['motor']) == {'M1', 'M3'}                       # M2 turns < 2 worm turns here
    true_phase = np.degrees(np.arctan2(TRUE[9], TRUE[8])) % 360
    assert all(abs((p - true_phase + 180) % 360 - 180) < 15 for p in m3['phase'])
    c = phase_consistency(m3['phase'])
    assert c['R'] > 0.95 and c['p'] < 0.05


def test_phase_consistency_of_random_phases_is_low():
    from pe_analysis import phase_consistency
    rng = np.random.default_rng(1)
    c = phase_consistency(rng.uniform(0, 360, 12))
    assert c['R'] < 0.5 and c['p'] > 0.05


def test_removing_the_accumulated_corrections_recovers_the_motor_angles():
    """PECLOG/SGLOG az/alt/roll is the driver's present value: the motor pose rotated by every guide and PEC
    correction (total_accum, about the RA and Dec axes). Through the inverse kinematics that shifts the motor angles by
    up to ~1 deg over a night -- tens of degrees of worm phase -- unless the corrections are taken back out."""
    from pe_analysis import remove_corrections
    from kinematics import theta_to_q, q_to_azaltroll, azaltroll_to_theta_ik, calc_equatorial_axes_B
    from quaternion import Q
    rng = np.random.default_rng(3)
    n = 30
    raw = np.column_stack([150 - 12 * np.linspace(0, 1.5, n), 69 + 6 * np.linspace(0, 1.5, n), 14 + 11 * np.linspace(0, 1.5, n)])
    ra = np.r_[0.0, np.cumsum(rng.normal(-20, 30, n - 1))]                     # arcsec, accumulated corrections
    dec = np.r_[0.0, np.cumsum(rng.normal(120, 30, n - 1))]                    # ~1 deg by the end
    pv = []
    for th, r, d in zip(raw, ra, dec):
        p, dax, _ = calc_equatorial_axes_B(theta_to_q(*th), Q(), LAT)
        q = (Q(axis=p, degrees=r / 3600) * Q(axis=dax, degrees=d / 3600) * theta_to_q(*th)).normalised
        pv.append(azaltroll_to_theta_ik(*q_to_azaltroll(q)))
    pv = np.array(pv)
    assert np.abs(pv - raw).max() > 0.5                                         # what the pose-derived angles look like
    got = remove_corrections(pv, ra, dec, LAT)
    assert np.abs(got - raw).max() < 0.01


# ── multi-turn cleanup: direction of travel, stationary motors, turns-based trend ──

def test_a_motor_needs_two_worm_turns_to_be_fitted():
    p = part(16, rates=(12.0, 4.0, 14.0))                                       # M2 moves 10 deg = 1.7 turns
    prof = fit_worm([p], harmonics=H)
    assert np.allclose(prof.coef[4:8], 0.0) and np.abs(prof.coef[8:]).max() > 1.0



def test_auto_trend_stays_quadratic_with_two_turns():
    from pe_analysis import auto_trend_degree
    th = np.column_stack([np.linspace(0, 13, 50), np.linspace(0, 1, 50), np.linspace(0, 12.5, 50)])
    assert auto_trend_degree(th, 6.0) == 2
    th[:, 2] = np.linspace(0, 40, 50)                                           # M3 6.7 turns, M1 2.2
    assert auto_trend_degree(th, 6.0) == 2                                      # limited by the slowest fitted motor
    th[:, 0] = np.linspace(0, 30, 50)
    assert auto_trend_degree(th, 6.0) == 4


def test_windowed_fit_tracks_a_steady_worm_at_its_true_amplitude_and_phase():
    from pe_analysis import windowed_worm
    t, ra, dec, th, lat = part(80, hours=4.0, rates=(14.0, 1.0, 16.0))
    s = Segment('w', 'w', t, ra, dec, th)
    w = windowed_worm(s, lat, window_s=5400, step_s=900)
    m3 = w[(w['motor'] == 'M3') & w['fitted']]
    assert len(m3) >= 8
    true_amp, true_phase = np.hypot(TRUE[8], TRUE[9]), np.degrees(np.arctan2(TRUE[9], TRUE[8])) % 360
    assert np.abs(m3['amp'] - true_amp).max() < 0.2 * true_amp
    assert np.abs((m3['phase'] - true_phase + 180) % 360 - 180).max() < 15
    assert not w.loc[w['motor'] == 'M2', 'fitted'].any()                       # M2 hardly turns


def test_windowed_fit_keeps_m3s_worm_out_of_m1():
    """Only M3 has a worm, and M1 and M3 move the star alike; fitted per window, M1 comes out near zero because its
    worm repeats at a different rate."""
    from pe_analysis import windowed_worm
    coef = np.zeros_like(TRUE)
    coef[8:12] = TRUE[8:12]
    t, ra, dec, th, lat = part(81, hours=4.0, rates=(7.0, 1.0, 15.0), start=(30.0, 12.0, None), coef=coef)
    w = windowed_worm(Segment('x', 'x', t, ra, dec, th), lat, window_s=5400, step_s=900)
    m1 = w[(w['motor'] == 'M1') & w['fitted']]
    assert len(m1) >= 5 and m1['amp'].max() < 5.0


def test_windowed_fit_shows_a_worm_whose_amplitude_changes_through_the_night():
    from pe_analysis import windowed_worm
    t, ra, dec, th, lat = part(82, hours=5.0, rates=(14.0, 1.0, 16.0), coef=np.zeros_like(TRUE), noise=1.0)
    grow = 10 + 60 * t / t[-1]                                                  # M3 worm amplitude 10" -> 70"
    e3 = grow * np.sin(2 * np.pi * th[:, 2] / WORM_THETA)
    w3 = sky_weights(th, lat)[:, :, 2]
    s = Segment('g', 'g', t, ra + w3[:, 0] * e3, dec + w3[:, 1] * e3, th)
    m3 = windowed_worm(s, lat, window_s=5400, step_s=900)
    m3 = m3[(m3['motor'] == 'M3') & m3['fitted']].sort_values('t_min')
    assert m3['amp'].iloc[-1] > 2.5 * m3['amp'].iloc[0]


def test_windows_where_m1_and_m3_turn_at_about_the_same_speed_are_flagged():
    """Then their worms repeat at nearly the same rate in time, and even a joint fit can't tell them apart."""
    from pe_analysis import windowed_worm
    t, ra, dec, th, lat = part(83, hours=3.0, rates=(-16.0, 1.0, 15.0))
    w = windowed_worm(Segment('s', 's', t, ra, dec, th), lat)
    assert set(w.columns) >= {'rate', 'm1_m3_separable'}
    assert not w['m1_m3_separable'].any()
    assert w.loc[w['motor'] == 'M1', 'rate'].iloc[0] == pytest.approx(-16.0, abs=0.5)
    t, ra, dec, th, lat = part(84, hours=3.0, rates=(7.0, 1.0, 15.0))
    assert windowed_worm(Segment('s', 's', t, ra, dec, th), lat)['m1_m3_separable'].all()


# ── motors too slow to fit in a segment: use their profile from the other sessions ──

def test_only_keeps_the_named_motors():
    prof = WormProfile(TRUE, WORM_THETA, H)
    m3 = prof.only(['M3'])
    assert np.allclose(m3.coef[:8], 0.0) and np.allclose(m3.coef[8:], TRUE[8:])


def shared_coef(A, phases):
    """WormProfile coefficients (harmonic 1 only) for e_i = A sin(phi_i + p_i)."""
    p = np.radians(phases)
    return np.column_stack([A * np.cos(p), A * np.sin(p)]).ravel()

