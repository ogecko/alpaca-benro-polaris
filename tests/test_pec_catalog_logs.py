"""
Tests for utility/catalog_logs.py -- the inventory of archived driver logs used to find segments of
steady tracking on one target that can be used to study the mount's drift / periodic error.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import json
import math
import pandas as pd
import pytest

from catalog_logs import session_key, catalog_session, MIN_SEGMENT_MIN
from kinematics import azaltroll_to_theta_ik


@pytest.mark.parametrize("name, key", [
    ("alpaca.soak_Beta4.3_08_31_sg_kfposlog_Dec72_504m_a08.log", "alpaca.soak_Beta4.3_08_31_sg_kfposlog_Dec72_504m"),
    ("alpaca.mark_Beta4.4_09_05_a1.log", "alpaca.mark_Beta4.4_09_05"),
    ("alpaca.jdm_Beta7.1_09_29_pulseguide_a1.log", "alpaca.jdm_Beta7.1_09_29_pulseguide"),
    ("alpaca.mark_Beta2.9_07_26_b.log", "alpaca.mark_Beta2.9_07_26_b"),
    ("alpaca.pec_rls_Beta2.0_07_20_h2.log", "alpaca.pec_rls_Beta2.0_07_20_h2"),
])
def test_rotated_parts_share_a_session_key(name, key):
    assert session_key(name) == key


def ts(t0, sec):
    return (t0 + pd.Timedelta(seconds=sec)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]


def peclog(t, az, alt, roll, resid=(0.01, None)):
    r = [None if v is None else v for v in resid]
    return (f"{t} INFO PECLOG {{'n': 5, 'inhibit': ['VALID', 'VALID'], 'resid': {r}, 'pec_accum': [0.0, 0.0], "
            f"'total_accum': [0.1, 0.2], 'az': {az}, 'alt': {alt}, 'roll': {roll}, 'pec_active': True}}\n")


@pytest.fixture
def session(tmp_path):
    t0 = pd.Timestamp('2026-09-01T20:00:00')
    L = [f"{ts(t0, 0)} INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER v2.2.0 Beta 4.4 =========== \n",
         f"{ts(t0, 5)} INFO 1.2.3.4 -> PUT /api/v1/telescope/0/action {{'Action': 'Polaris:ConfigUpdate', 'Parameters': {{'advanced_pec': True}}, 'ClientID': 1}}\n",
         f"{ts(t0, 10)} INFO ->> Polaris: GOTO Observed   RA 10h45m16.17s     Dec -060d01'59.75\"\n",
         f"{ts(t0, 12)} INFO Advanced Control: START tracking\n"]
    # segment 1: 80 min, az 150->160, alt 40->45, roll 10 (PECLOG every 30 s), sync guiding every 2 min
    for k in range(0, 80 * 60, 30):
        f = k / (80 * 60)
        L.append(peclog(ts(t0, 60 + k), 150 + 10 * f, 40 + 5 * f, 10.0, resid=(0.01, None) if k % 60 else (None, 0.02)))
        if k % 120 == 0 and k:
            L.append(f"{ts(t0, 61 + k)} INFO ->> Polaris: SYNC GUIDING    Ra +000d00'01.18\", Dec +000d00'21.65\" Residuals\n")
    L.append(f"{ts(t0, 60 + 80 * 60 + 5)} INFO 1.2.3.4 -> PUT /api/v1/telescope/0/action {{'Action': 'Polaris:MoveAxis', 'Parameters': '{{\"axis\":0,\"rate\":0.5}}', 'ClientID': 1}}\n")
    # segment 2: too short (10 min), then tracking stops
    t1 = 60 + 80 * 60 + 30
    for k in range(0, 10 * 60, 30):
        L.append(peclog(ts(t0, t1 + 60 + k), 200.0, 30.0, 0.0))
    L.append(f"{ts(t0, t1 + 60 + 10 * 60 + 5)} INFO Advanced Control: STOP tracking\n")
    p1, p2 = tmp_path / 'alpaca.test_Beta4.4_09_01_a1.log', tmp_path / 'alpaca.test_Beta4.4_09_01_a2.log'
    half = len(L) // 2
    p1.write_text(''.join(L[:half]), encoding='utf-8')
    p2.write_text(''.join(L[half:]), encoding='utf-8')
    return [str(p2), str(p1)]                       # out of order on purpose


def test_segments_split_at_moves_and_tracking_stops(session):
    segs = catalog_session(session)
    assert len(segs) == 2
    s = segs[0]
    assert s['duration_min'] == pytest.approx(80 - 1, abs=1.5)   # first minute after the goto skipped as settling
    assert s['start_reason'] == 'goto' and s['end_reason'] == 'move'
    assert segs[1]['end_reason'] == 'tracking_off'
    assert segs[1]['usable'] is False and segs[1]['duration_min'] < MIN_SEGMENT_MIN


def test_segment_records_version_target_pose_and_data(session):
    s = catalog_session(session)[0]
    assert s['driver_version'] == 'v2.2.0 Beta 4.4'
    assert s['target_ra_h'] == pytest.approx(10 + 45 / 60 + 16.17 / 3600, abs=1e-4)
    assert s['target_dec'] == pytest.approx(-(60 + 1 / 60 + 59.75 / 3600), abs=1e-4)
    assert s['az_start'] == pytest.approx(150, abs=0.5) and s['az_end'] == pytest.approx(160, abs=0.5)
    assert s['alt_start'] == pytest.approx(40, abs=0.2) and s['roll_mean'] == pytest.approx(10)
    assert s['n_peclog'] > 150 and s['n_sglog'] == 0 and s['n_kflog'] == 0
    assert s['pose_source'] == 'peclog'
    assert s['pec'] == 'on'
    assert s['n_sync_guide'] == 39 and s['sync_interval_s'] == pytest.approx(120, abs=1)
    assert s['pulse_guiding'] is True              # PECLOG rows with only one resid axis


def test_motor_rates_come_from_the_inverse_kinematics_of_the_pose(session):
    s = catalog_session(session)[0]
    a = azaltroll_to_theta_ik(150.3, 40.15, 10.0)
    b = azaltroll_to_theta_ik(159.8, 44.9, 10.0)
    hours = s['duration_min'] / 60
    for i in range(3):
        expected = abs(b[i] - a[i]) / hours
        assert s[f'm{i+1}_dps_hr'] == pytest.approx(expected, rel=0.1, abs=0.2)
        assert s[f'm{i+1}_travel_deg'] == pytest.approx(abs(b[i] - a[i]), rel=0.1, abs=0.2)


def test_segment_without_pose_records_is_flagged(tmp_path):
    t0 = pd.Timestamp('2026-09-01T20:00:00')
    p = tmp_path / 'alpaca.nopose.log'
    p.write_text(f"{ts(t0, 0)} INFO Advanced Control: START tracking\n"
                 f"{ts(t0, 3 * 3600)} INFO Advanced Control: STOP tracking\n", encoding='utf-8')
    s = catalog_session([str(p)])[0]
    assert s['pose_source'] == 'none'
    assert math.isnan(s['m1_dps_hr'])
    assert s['usable'] is False


def test_legacy_peclog_pose_is_used(tmp_path):
    t0 = pd.Timestamp('2026-07-20T20:00:00')
    L = [f"{ts(t0, 0)} INFO ->> Polaris: GOTO Observed   RA 01h34m03.63s     Dec -055d33'14.93\"\n",
         f"{ts(t0, 2)} INFO Advanced Control: START tracking\n"]
    for k in range(0, 60 * 60, 60):
        az = 150 + 5 * k / 3600
        L.append(f"{ts(t0, 60 + k)} INFO PECLOG  n,{k},VALID,VALID, | R2,0.9,0.9, | rmse,0.1,0.1, | Rate,-3.2,+6.7, | "
                 f"Guide,-0.8,+1.8, | Accum,-0.8,+1.8, | Pos,{az:.2f},40.00,5.00, | RA_model,-3.2,0.0,0.0, | "
                 f"Dec_model,+6.7,0.0,0.0, | lambda,0.98,0.98\n")
    L.append(f"{ts(t0, 3700)} INFO Advanced Control: STOP tracking\n")
    p = tmp_path / 'alpaca.legacy.log'
    p.write_text(''.join(L), encoding='utf-8')
    s = catalog_session([str(p)])[0]
    assert s['pose_source'] == 'peclog' and s['pec'] == 'on'
    assert s['az_start'] == pytest.approx(150, abs=0.2) and s['roll_mean'] == pytest.approx(5)


def test_segment_without_records_but_with_a_target_can_be_rebuilt(tmp_path):
    t0 = pd.Timestamp('2026-09-29T20:25:00')
    p = tmp_path / 'alpaca.target.log'
    p.write_text(f"{ts(t0, 0)} INFO ->> Polaris: Rotate Absolute Observed   RollAngle -035d00'00.00\"\n"
                 f"{ts(t0, 5)} INFO ->> Polaris: GOTO Observed   RA 18h07m45.58s     Dec -024d11'23.83\"\n"
                 f"{ts(t0, 7)} INFO Advanced Control: START tracking\n"
                 f"{ts(t0, 2 * 3600)} INFO Advanced Control: STOP tracking\n", encoding='utf-8')
    s = catalog_session([str(p)])[0]
    assert s['pose_source'] == 'target'
    assert s['roll_set'] == pytest.approx(-35.0)
    assert s['usable'] is True
