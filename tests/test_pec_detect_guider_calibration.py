"""
Tests for GuiderCalibrationDetector -- recognises a guider's calibration (PHD2, CCDciel, ...)
from the pulse stream alone, so PEC can ignore calibration pulses instead of learning them
as drift.

Signature: calibration moves ONE axis at a time in ONE direction with IDENTICAL pulse
durations (PHD2), or with each pulse exactly 1.5x the previous one (CCDciel's internal guider
ramps its East pulse until the star moves). Guiding sends RA and Dec pulses in the same frame
with durations computed from the measured error, so neither run occurs while guiding.
"""
import sys
import os
import csv
import gzip
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
from control_pec import GuiderCalibrationDetector

RA, DEC = 0, 1
FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'phd2_pulse_stream_2026-09-29.csv.gz')
CCDCIEL_FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'ccdciel_pulse_stream_2026-09-12.csv.gz')
DIRECTION = {'E': (RA, +1), 'W': (RA, -1), 'N': (DEC, +1), 'S': (DEC, -1)}


def feed(det, pulses):
    """pulses: iterable of (t, 'N'|'S'|'E'|'W', ms). Returns list of verdicts."""
    out = []
    for t, d, ms in pulses:
        axis, sign = DIRECTION[d]
        out.append(det.observe(axis, sign, ms, t))
    return out


def phd2_calibration(t0, step_ms=500, n_ra=14, n_backlash=3, n_dec=10, dt=1.4):
    """Synthetic PHD2 calibration: W steps, E recenter, N backlash clearing, N steps, S recenter."""
    seq = [('W', step_ms)] * n_ra
    seq += [('E', 2500), ('E', 2500), ('E', 2000)]
    seq += [('N', step_ms)] * (n_backlash + n_dec)
    seq += [('S', 2500), ('S', 2500), ('S', 1500)]
    t, out = t0, []
    for d, ms in seq:
        t += ms / 1000 + 0.9 if ms > step_ms else dt
        out.append((t, d, ms))
    return out


def ccdciel_calibration(t0, initial_ms=100, longest_ms=500, east_steps=6, n_backlash=3, dec_ms=1000,
                        n_measure=2, gap=4.0):
    """Synthetic CCDciel internal guider calibration, as cu_autoguider_internal.InternalCalibration:
    East pulses from initial_ms, each round(1.5x) the last, until the star moves (east_steps); one West
    pulse of the last East length; North backlash clearing (min(longest, max(300, 3 x initial)), growing
    1.5x from the 3rd pulse, capped at longest); North measure (n_measure identical); the same South."""
    seq, d = [], round(initial_ms / 1.5)
    for _ in range(east_steps):
        d = round(d * 1.5)
        seq.append(('E', d))
    seq.append(('W', d))
    for dirn in ('N', 'S'):
        b = min(longest_ms, max(300, 3 * initial_ms))
        for k in range(1, n_backlash + 1):
            if k >= 3:
                b = round(min(longest_ms, 1.5 * b))
            seq.append((dirn, b))
        seq += [(dirn, dec_ms)] * n_measure
    t, out = t0, []
    for dirn, ms in seq:
        t += ms / 1000 + gap
        out.append((t, dirn, ms))
    return out


def guiding(t0, n_frames, frame_dt=1.6):
    """Guiding-like stream: RA then Dec pulse per frame, error-derived (varying) durations."""
    out = []
    for i in range(n_frames):
        t = t0 + i * frame_dt
        out.append((t, 'W' if i % 3 else 'E', 40 + (i * 37) % 160))
        out.append((t + 0.05, 'N' if i % 2 else 'S', 25 + (i * 53) % 140))
    return out


# ── run detection ─────────────────────────────────────────────────────────

def test_guiding_pulses_are_all_ingested():
    det = GuiderCalibrationDetector()
    verdicts = feed(det, guiding(0.0, 200))
    assert all(v.ingest for v in verdicts)
    assert not any(v.rollback for v in verdicts)
    assert not det.active


def test_third_identical_pulse_triggers_and_requests_rollback():
    det = GuiderCalibrationDetector()
    v1, v2, v3 = feed(det, [(1.0, 'W', 500), (2.4, 'W', 500), (3.8, 'W', 500)])
    assert v1.ingest and v1.run_start and not v1.rollback
    assert v2.ingest and not v2.run_start and not v2.rollback
    assert not v3.ingest and v3.rollback
    assert det.active


def test_rollback_is_requested_only_once_per_calibration():
    det = GuiderCalibrationDetector()
    verdicts = feed(det, phd2_calibration(0.0))
    assert sum(v.rollback for v in verdicts) == 1


def test_two_identical_pulses_do_not_trigger():
    # happens by chance during RA-only frames (59 times in the 2026-09-29 session)
    det = GuiderCalibrationDetector()
    verdicts = feed(det, [(1.0, 'E', 66), (2.6, 'E', 66), (4.2, 'E', 71)])
    assert all(v.ingest for v in verdicts)
    assert not det.active


@pytest.mark.parametrize("third", [('E', 500), ('N', 500), ('S', 500), ('W', 499), ('W', 520)])
def test_run_is_broken_by_a_different_axis_direction_or_duration(third):
    det = GuiderCalibrationDetector()
    verdicts = feed(det, [(1.0, 'W', 500), (2.4, 'W', 500), (3.8, *third)])
    assert all(v.ingest for v in verdicts)
    assert verdicts[2].run_start
    assert not det.active


def test_run_length_is_configurable():
    det = GuiderCalibrationDetector(run_length=4)
    verdicts = feed(det, [(t, 'N', 300) for t in (1.0, 2.0, 3.0, 4.0)])
    assert [v.ingest for v in verdicts] == [True, True, True, False]
    assert verdicts[3].rollback


# ── staying active through the calibration and exiting afterwards ────────

def test_no_calibration_pulse_after_the_trigger_is_ingested():
    det = GuiderCalibrationDetector()
    verdicts = feed(det, phd2_calibration(0.0))
    assert [v.ingest for v in verdicts[:2]] == [True, True]
    assert not any(v.ingest for v in verdicts[2:])
    assert det.active


def test_guiding_after_calibration_is_ignored_until_quiet_period_then_ingested():
    det = GuiderCalibrationDetector(quiet_sec=20.0)
    cal = phd2_calibration(0.0)
    feed(det, cal)
    t_last_repeat = cal[-2][0]          # S2500, S2500 -> last repeat is the 2nd S pulse
    guide = guiding(cal[-1][0] + 2.0, 40)
    verdicts = feed(det, guide)
    for (t, _, _), v in zip(guide, verdicts):
        assert v.ingest == (t - t_last_repeat > 20.0), t
    assert not det.active


def test_a_second_calibration_is_detected_again():
    det = GuiderCalibrationDetector(quiet_sec=20.0)
    feed(det, phd2_calibration(0.0))
    guide = guiding(200.0, 30)
    feed(det, guide)
    assert not det.active
    verdicts = feed(det, phd2_calibration(guide[-1][0] + 5.0))
    assert sum(v.rollback for v in verdicts) == 1
    assert not any(v.ingest for v in verdicts[2:])


def test_reset_clears_active_state_and_run():
    det = GuiderCalibrationDetector()
    feed(det, [(1.0, 'W', 500), (2.0, 'W', 500), (3.0, 'W', 500)])
    assert det.active
    det.reset()
    assert not det.active
    v = feed(det, [(4.0, 'W', 500)])[0]
    assert v.ingest and v.run_start


# ── replay of a real session (PHD2 2.6.14, 2026-09-29) ───────────────────

def load_fixture():
    rows = []
    with gzip.open(FIXTURE, 'rt') as f:
        for r in csv.reader(line for line in f if not line.startswith('#')):
            if r and r[0] != 't_sec':
                rows.append((float(r[0]), r[1], int(r[2]), r[3]))
    return rows


@pytest.fixture(scope='module')
def session():
    rows = load_fixture()
    det = GuiderCalibrationDetector()
    verdicts = feed(det, [(t, d, ms) for t, d, ms, _ in rows])
    return rows, verdicts


def test_session_fixture_has_calibrations_and_guiding(session):
    rows, _ = session
    phases = {p for *_, p in rows}
    assert phases == {'cal0', 'cal2', 'cal3', 'cal4', 'cal5', 'guide'}
    assert sum(1 for *_, p in rows if p == 'guide') > 40000


def test_session_never_triggers_during_guiding(session):
    rows, verdicts = session
    false_triggers = [r for r, v in zip(rows, verdicts) if v.rollback and r[3] == 'guide']
    assert false_triggers == []


def test_session_detects_every_calibration_and_ingests_at_most_two_of_its_pulses(session):
    rows, verdicts = session
    for cal in ('cal0', 'cal2', 'cal3', 'cal4', 'cal5'):
        cv = [v for r, v in zip(rows, verdicts) if r[3] == cal]
        assert sum(v.rollback for v in cv) == 1, cal
        assert sum(v.ingest for v in cv) == 2, cal          # the 2 before the trigger, undone by rollback


def test_session_ingests_nearly_all_guide_pulses(session):
    rows, verdicts = session
    guide = [v.ingest for r, v in zip(rows, verdicts) if r[3] == 'guide']
    # only the quiet period after each of the 5 calibrations is skipped
    assert sum(guide) / len(guide) > 0.995


# ── CCDciel: East pulse ramp of 1.5x steps ───────────────────────────────

@pytest.mark.parametrize("initial_ms, longest_ms, east_steps, n_before", [
    (100, 500, 7, 3),          # CCDciel defaults: 100 150 225 338 ... -> triggers on 338, the first >= 300 ms
    (1000, 2500, 5, 2),        # 2026-09-12 session settings: 1000 1500 2250 ... -> triggers on 2250
    (1500, 2500, 3, 2),        # 2026-09-12 23:55: 1500 2250 3375
])
def test_ccdciel_calibration_is_detected_once_and_nothing_after_the_trigger_is_ingested(
        initial_ms, longest_ms, east_steps, n_before):
    det = GuiderCalibrationDetector()
    verdicts = feed(det, ccdciel_calibration(0.0, initial_ms, longest_ms, east_steps))
    assert sum(v.rollback for v in verdicts) == 1
    assert verdicts[n_before].rollback
    assert [v.ingest for v in verdicts[:n_before]] == [True] * n_before   # undone by the rollback
    assert verdicts[0].run_start                                          # rollback point = start of the ramp
    assert not any(v.ingest for v in verdicts[n_before:])
    assert det.active


def test_ccdciel_rounding_of_half_milliseconds_still_continues_the_ramp():
    # round(3375 * 1.5) = 5062 (half-to-even, as Free Pascal's Round)
    det = GuiderCalibrationDetector(ramp_min_ms=10000)
    verdicts = feed(det, [(1.0, 'E', 3375), (5.0, 'E', 5062)])
    assert not verdicts[1].run_start


@pytest.mark.parametrize("pulses", [
    [('E', 79), ('E', 118), ('E', 176)],      # 2026-09-29 PHD2 guiding: 1.5x within 1 ms, but short and not exact
    [('E', 80), ('E', 120), ('E', 180)],      # exact 1.5x ramp of guiding-sized pulses
    [('W', 120), ('W', 180), ('W', 270)],
])
def test_a_ramp_of_short_guiding_pulses_does_not_trigger(pulses):
    det = GuiderCalibrationDetector()
    verdicts = feed(det, [(1.0 + 1.6 * i, d, ms) for i, (d, ms) in enumerate(pulses)])
    assert all(v.ingest for v in verdicts)
    assert not det.active


@pytest.mark.parametrize("third", [('E', 2260), ('E', 2251), ('W', 2250), ('N', 2250)])
def test_ramp_is_broken_by_a_different_ratio_axis_or_direction(third):
    det = GuiderCalibrationDetector()
    verdicts = feed(det, [(1.0, 'E', 1000), (6.0, 'E', 1500), (12.0, *third)])
    assert all(v.ingest for v in verdicts)
    assert verdicts[2].run_start
    assert not det.active


# ── replay of a real session (CCDciel internal guider, 2026-09-12) ───────

@pytest.fixture(scope='module')
def ccdciel_session():
    rows = []
    with gzip.open(CCDCIEL_FIXTURE, 'rt') as f:
        for r in csv.reader(line for line in f if not line.startswith('#')):
            if r and r[0] != 't_sec':
                rows.append((float(r[0]), r[1], int(r[2]), r[3]))
    det = GuiderCalibrationDetector()
    return rows, feed(det, [(t, d, ms) for t, d, ms, _ in rows])


def test_ccdciel_session_never_triggers_during_guiding(ccdciel_session):
    rows, verdicts = ccdciel_session
    assert [r for r, v in zip(rows, verdicts) if v.rollback and r[3] == 'guide'] == []


def test_ccdciel_session_detects_both_calibrations_and_ingests_at_most_two_of_their_pulses(ccdciel_session):
    rows, verdicts = ccdciel_session
    for cal in ('cal1', 'cal2'):
        cv = [v for r, v in zip(rows, verdicts) if r[3] == cal]
        assert sum(v.rollback for v in cv) == 1, cal
        assert sum(v.ingest for v in cv) == 2, cal           # the 2 before the trigger, undone by rollback
    # CCDciel's separate backlash calibration follows within the quiet period of cal1
    assert not any(v.ingest for r, v in zip(rows, verdicts) if r[3] == 'backlash1')


def test_ccdciel_session_ingests_nearly_all_guide_pulses(ccdciel_session):
    rows, verdicts = ccdciel_session
    guide = [v.ingest for r, v in zip(rows, verdicts) if r[3] == 'guide']
    assert sum(guide) / len(guide) > 0.99
