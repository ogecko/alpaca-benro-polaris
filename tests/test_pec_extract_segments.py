"""
Tests for utility/extract_segments.py -- one standard drift dataset per catalogued tracking segment:
time, RA/Dec drift (arcsec, the driver's correction convention), motor angles theta1-3 and pose,
whatever records the source log has.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pandas as pd
import pytest

from catalog_logs import catalog_session
from extract_segments import extract_segment, stitch_accum, target_pose
from kinematics import azaltroll_to_theta_ik


def ts(t0, sec):
    return (t0 + pd.Timedelta(seconds=sec)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]


T0 = pd.Timestamp('2026-09-01T20:00:00')


def write_session(tmp_path, body):
    p = tmp_path / 'alpaca.x.log'
    p.write_text(f"{ts(T0, 0)} INFO ->> Polaris: GOTO Observed   RA 10h45m16.17s     Dec -060d01'59.75\"\n"
                 f"{ts(T0, 2)} INFO Advanced Control: START tracking\n" + ''.join(body)
                 + f"{ts(T0, 4000)} INFO Advanced Control: STOP tracking\n", encoding='utf-8')
    return [str(p)]


def peclog(k, n, accum, az=150.0, alt=40.0, roll=10.0):
    return (f"{ts(T0, 60 + k)} INFO PECLOG {{'n': {n}, 'inhibit': ['VALID', 'VALID'], 'resid': [0.01, None], "
            f"'pec_accum': [0.0, 0.0], 'total_accum': [{accum[0]}, {accum[1]}], 'az': {az}, 'alt': {alt}, 'roll': {roll}}}\n")


def test_stitch_accum_joins_resets_into_one_running_total():
    values = np.array([0.0, 1.0, 2.0, 3.0, 0.5, 1.5])          # model reset before the 5th sample
    reset = np.array([False, False, False, False, True, False])
    assert list(stitch_accum(values, reset)) == [0.0, 1.0, 2.0, 3.0, 3.5, 4.5]


def test_drift_from_peclog_total_accum_in_arcsec_across_a_pec_reset(tmp_path):
    body = [peclog(k, 2 + i, (0.1 * i, -0.05 * i)) for i, k in enumerate(range(0, 1800, 30))]
    body += [peclog(1800 + k, 2 + i, (0.1 * i, 0.0)) for i, k in enumerate(range(0, 1800, 30))]   # n restarts
    paths = write_session(tmp_path, body)
    seg = catalog_session(paths)[0]
    d = extract_segment(paths, seg)
    assert d['drift_source'].iloc[0] == 'peclog'
    assert d['drift_ra_arcsec'].iloc[59] == pytest.approx(0.1 * 59 * 60)
    assert d['drift_ra_arcsec'].iloc[-1] == pytest.approx((0.1 * 59 + 0.1 * 59) * 60)
    assert d['drift_dec_arcsec'].iloc[-1] == pytest.approx(-0.05 * 59 * 60)
    assert d['t_sec'].iloc[0] == 0.0


def test_theta_from_peclog_pose_through_ik(tmp_path):
    body = [peclog(k, 2 + i, (0.0, 0.0), az=150 + k / 360, alt=40.0, roll=10.0) for i, k in enumerate(range(0, 3600, 60))]
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['theta_source'].iloc[0] == 'peclog'
    exp = azaltroll_to_theta_ik(d['az'].iloc[10], 40.0, 10.0)
    assert [d['theta1'].iloc[10], d['theta2'].iloc[10], d['theta3'].iloc[10]] == pytest.approx(list(exp), abs=1e-6)


def test_kflog_theta_is_preferred_and_interpolated_to_drift_times(tmp_path):
    body = [peclog(k, 2 + i, (0.0, 0.0)) for i, k in enumerate(range(0, 3600, 60))]
    for k in range(0, 3600, 10):
        body.append(f"{ts(T0, 65 + k)} INFO KFLOG {{'θ_meas_raw': [{100 + k / 100}, 50.0, {-20 - k / 200}]}}\n")
    body.sort(key=lambda l: l[:23])
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['theta_source'].iloc[0] == 'kflog'
    row = d.iloc[20]                                            # PECLOG at 60+1200 s; KFLOG at 65+k
    k = (row['timestamp'] - T0).total_seconds() - 65
    assert row['theta1'] == pytest.approx(100 + k / 100, abs=0.02)
    assert row['theta3'] == pytest.approx(-20 - k / 200, abs=0.02)


def test_segment_without_drift_records_is_empty(tmp_path):
    paths = write_session(tmp_path, [])
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d.empty


def test_target_pose_matches_an_observed_quest_point():
    # 2026-09-29 20:24:18 local (UTC+10), Mount Colah: QUEST observed RA 18.13h Dec -24.22 at Az 272.30 Alt 51.10
    az, alt = target_pose(18.13, -24.22, pd.Timestamp('2026-09-29 20:24:18'), lat=-33.654651, lon=151.12, utc_offset_h=10)
    assert az == pytest.approx(272.30, abs=0.15) and alt == pytest.approx(51.10, abs=0.15)


def phd2_frames(n=100):
    t = [T0 + pd.Timedelta(seconds=120 + 2 * k) for k in range(n)]
    return pd.DataFrame({'timestamp': t, 'ra_pulse_arcsec': [0.5] * n, 'dec_pulse_arcsec': [-0.25] * n})


def test_phd2_drift_is_used_when_pec_is_off(tmp_path):
    p = tmp_path / 'alpaca.y.log'
    p.write_text(f"{ts(T0, 0)} INFO ->> Polaris: Rotate Absolute Observed   RollAngle -035d00'00.00\"\n"
                 f"{ts(T0, 1)} INFO ->> Polaris: GOTO Observed   RA 10h45m16.17s     Dec -060d01'59.75\"\n"
                 f"{ts(T0, 2)} INFO Advanced Control: START tracking\n"
                 f"{ts(T0, 4000)} INFO Advanced Control: STOP tracking\n", encoding='utf-8')
    seg = catalog_session([str(p)])[0]
    d = extract_segment([str(p)], seg, phd2_frames=phd2_frames())
    assert d['drift_source'].iloc[0] == 'phd2' and d['theta_source'].iloc[0] == 'target'
    assert d['drift_ra_arcsec'].iloc[-1] == pytest.approx(50.0) and d['drift_dec_arcsec'].iloc[-1] == pytest.approx(-25.0)


def test_peclog_drift_wins_over_phd2_when_pec_is_on(tmp_path):
    body = [peclog(k, 2 + i, (0.1 * i, 0.0)) for i, k in enumerate(range(0, 1800, 30))]
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0], phd2_frames=phd2_frames())
    assert d['drift_source'].iloc[0] == 'peclog'


def test_drift_from_legacy_peclog_accum(tmp_path):
    body = [f"{ts(T0, 60 + k)} INFO PECLOG  n,{2 + i},VALID,VALID, | R2,0.9,0.9, | rmse,0.1,0.1, | Rate,-3.2,+6.7, | "
            f"Guide,-0.8,+1.8, | Accum,{0.1 * i:+.5f},{-0.2 * i:+.5f}, | Pos,150.00,40.00,5.00, | RA_model,-3.2,0.0,0.0, | "
            f"Dec_model,+6.7,0.0,0.0, | lambda,0.98,0.98\n" for i, k in enumerate(range(0, 3600, 60))]
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['drift_source'].iloc[0] == 'peclog'
    assert d['drift_ra_arcsec'].iloc[-1] == pytest.approx(0.1 * 59 * 60)
    assert d['drift_dec_arcsec'].iloc[-1] == pytest.approx(-0.2 * 59 * 60)


def test_drift_from_sync_guiding_lines_when_there_are_no_drift_records(tmp_path):
    body = [f"{ts(T0, 60 + k)} INFO ->> Polaris: SYNC GUIDING    Ra +000d00'02.00\", Dec -000d00'01.00\" Residuals\n"
            for k in range(0, 3600, 90)]
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['drift_source'].iloc[0] == 'sync_lines'
    assert d['drift_ra_arcsec'].iloc[-1] == pytest.approx(2.0 * 40)
    assert d['drift_dec_arcsec'].iloc[-1] == pytest.approx(-1.0 * 40)


def test_raw_motor_angles_logged_in_peclog_are_used_when_there_is_no_kflog(tmp_path):
    body = []
    for i, k in enumerate(range(0, 3600, 60)):
        line = peclog(k, 2 + i, (0.0, 0.0), az=150 + k / 360)
        body.append(line.replace("'roll': 10.0}", f"'roll': 10.0, 'theta_raw': [{200 + k / 100}, 45.0, {-30 - k / 200}]}}"))
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['theta_source'].iloc[0] == 'peclog_raw'
    row = d.iloc[20]
    k = (row['timestamp'] - T0).total_seconds() - 60
    assert row['theta1'] == pytest.approx(200 + k / 100, abs=1e-6)
    assert row['theta3'] == pytest.approx(-30 - k / 200, abs=1e-6)


def test_peclog_rows_logged_before_the_first_518_have_no_raw_angles(tmp_path):
    body = [peclog(k, 2 + i, (0.0, 0.0)).replace("'roll': 10.0}", "'roll': 10.0, 'theta_raw': [None, None, None]}")
            for i, k in enumerate(range(0, 3600, 60))]
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['theta_source'].iloc[0] == 'peclog'                 # falls back to the pose through the IK


def test_motor_angles_from_theta_raw_minus_the_517_offset_are_preferred(tmp_path):
    body = []
    for i, k in enumerate(range(0, 3600, 60)):
        off = "[None, None, None]" if i < 3 else "[175.5, 45.0, 0.25]"           # no 517 yet for the first rows
        line = peclog(k, 2 + i, (0.0, 0.0), az=150 + k / 360)
        body.append(line.replace("'roll': 10.0}", f"'roll': 10.0, 'theta_raw': [{200 + k / 100}, 45.0, {-30 - k / 200}], "
                                                  f"'zeta_offset': {off}}}"))
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    assert d['theta_source'].iloc[0] == 'peclog_zeta'
    row = d.iloc[20]
    k = (row['timestamp'] - T0).total_seconds() - 60
    assert row['theta1'] == pytest.approx(200 + k / 100 - 175.5, abs=1e-6)
    assert row['theta2'] == pytest.approx(0.0, abs=1e-6)
    assert row['theta3'] == pytest.approx(-30 - k / 200 - 0.25, abs=1e-6)


def test_on_a_worm_feed_forward_night_the_drift_adds_back_what_it_corrected(tmp_path):
    # the feed-forward took the worm out of the guide corrections; PECLOG logs it as wff (arcmin), drift = total_accum + wff
    body = []
    for i, k in enumerate(range(0, 3600, 60)):
        wff = (0.2 * np.sin(k / 600), -0.1 * np.cos(k / 600))
        line = peclog(k, 2 + i, (0.01 * i, 0.0))
        body.append(line.replace("'roll': 10.0}", f"'roll': 10.0, 'wff': [{wff[0]:.6f}, {wff[1]:.6f}]}}"))
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    k = 20 * 60
    assert d['drift_ra_arcsec'].iloc[20] == pytest.approx((0.01 * 20 + 0.2 * np.sin(k / 600)) * 60, abs=1e-3)
    assert d['drift_dec_arcsec'].iloc[20] == pytest.approx(-0.1 * np.cos(k / 600) * 60, abs=1e-3)


def test_a_rapid_solve_burst_counts_the_residuals_but_not_pecs_phantom_correction(tmp_path):
    """Syncs seconds apart re-anchor the model before the mount has carried out PEC's correction, so PECLOG's
    pec_accum over those short intervals never happened: the drift there is the residuals alone (2026-08-30: the
    solved position stayed on target while total_accum climbed 340" on pec_accum)."""
    body, total = [], [0.0, 0.0]
    times = [6 * i for i in range(25)] + [150 + 180 * i for i in range(20)]
    for i, k in enumerate(times):
        fast = 0 < i < 25
        resid, pec = (0.02, 0.01), ((0.25, 0.1) if fast else (0.05, 0.02))       # arcmin
        total = [total[0] + resid[0] + pec[0], total[1] + resid[1] + pec[1]]
        body.append(f"{ts(T0, 60 + k)} INFO PECLOG {{'n': {2 + i}, 'inhibit': ['VALID', 'VALID'], "
                    f"'resid': [{resid[0]}, {resid[1]}], 'pec_accum': [{pec[0]}, {pec[1]}], "
                    f"'total_accum': [{total[0]:.4f}, {total[1]:.4f}], 'az': 150.0, 'alt': 40.0, 'roll': 10.0}}\n")
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0])
    ra = d['drift_ra_arcsec'].values
    assert ra[24] - ra[0] == pytest.approx(24 * 0.02 * 60, abs=1e-6)               # burst: residuals only
    assert ra[30] - ra[29] == pytest.approx((0.02 + 0.05) * 60, abs=1e-6)          # normal cadence: resid + PEC


def test_pose_derived_motor_angles_have_the_accumulated_corrections_taken_out(tmp_path):
    from pe_analysis import remove_corrections
    body = [peclog(k, 2 + i, (0.0, 30.0 * i / 59), az=150 + k / 360) for i, k in enumerate(range(0, 3600, 60))]  # Dec 30'
    paths = write_session(tmp_path, body)
    d = extract_segment(paths, catalog_session(paths)[0], site=(-33.65, 151.1))
    assert d['theta_source'].iloc[0] == 'peclog'
    pose = np.array([azaltroll_to_theta_ik(a, 40.0, 10.0) for a in d['az']])
    want = remove_corrections(pose, d['drift_ra_arcsec'].values, d['drift_dec_arcsec'].values, -33.65)
    got = d[['theta1', 'theta2', 'theta3']].values
    assert np.abs(got - want).max() < 1e-6
    assert np.abs(got - pose)[-1].max() > 0.1                       # the 30' of Dec corrections moved them
