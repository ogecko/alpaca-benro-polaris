import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import PEState, PULSE_EAST, PULSE_NORTH, PULSE_SOUTH, PULSE_WEST, pe_offset_deg


# ── pe_offset_deg ──────────────────────────────────────────────────────────

def test_dc_only_model_is_linear_drift():
    # 60 arcmin/hour for 1 hour (3600s) -> 60 arcmin = 1 degree.
    assert pe_offset_deg([60, 0, 0], T_sec=2040, t_sec=3600) == pytest.approx(1.0)


def test_empty_or_zero_model_gives_zero_offset():
    assert pe_offset_deg([], T_sec=2040, t_sec=500) == 0.0
    assert pe_offset_deg([0, 0, 0], T_sec=2040, t_sec=500) == pytest.approx(0.0)


def test_harmonic_only_model_starts_at_zero():
    # Zero-phase harmonics are pure sine -> offset(0) == 0 regardless of amplitude.
    assert pe_offset_deg([0, 15.0, 4.0], T_sec=2040, t_sec=0) == pytest.approx(0.0)


def test_harmonic_peak_rate_matches_declared_amplitude():
    # d/dt of offset(t) at t=0 should equal h1's declared amplitude (arcmin/hour), converted
    # back from degrees/sec, since a zero-phase sine's rate peaks at t=0.
    T_sec = 2040
    h1_arcmin_per_hr = 12.5
    dt = 0.001
    rate_deg_per_sec = (pe_offset_deg([0, h1_arcmin_per_hr], T_sec, dt) -
                         pe_offset_deg([0, h1_arcmin_per_hr], T_sec, 0.0)) / dt
    rate_arcmin_per_hr = rate_deg_per_sec * 60 * 3600
    assert rate_arcmin_per_hr == pytest.approx(h1_arcmin_per_hr, rel=1e-3)


def test_offset_is_periodic_in_T_sec_for_harmonics_alone():
    model = [0, 10.0, 2.5]
    T_sec = 2040
    a = pe_offset_deg(model, T_sec, 137.0)
    b = pe_offset_deg(model, T_sec, 137.0 + T_sec)
    assert a == pytest.approx(b, abs=1e-9)


def test_dc_and_harmonics_combine_additively():
    T_sec = 2040
    dc_only = pe_offset_deg([5.0, 0], T_sec, 300)
    h_only = pe_offset_deg([0, 8.0], T_sec, 300)
    combined = pe_offset_deg([5.0, 8.0], T_sec, 300)
    assert combined == pytest.approx(dc_only + h_only)


# ── PEState: fake session (no network) ──────────────────────────────────────

class FakeSession:
    """Records every call instead of making real HTTP requests, and simulates a mount
    holding still at a fixed RA/Dec so synctocoordinates offsets are easy to check."""

    def __init__(self, pec_T_sec=2040, ra_h=10.0, dec_d=-30.0,
                 guide_rate_ra=0.0008, guide_rate_dec=0.0008):
        self.actions = []
        self.puts = []
        self._pec_T_sec = pec_T_sec
        self._ra_h = ra_h
        self._dec_d = dec_d
        self._guide_rate_ra = guide_rate_ra
        self._guide_rate_dec = guide_rate_dec

    def action(self, name, parameters):
        self.actions.append((name, parameters))
        if name == "Polaris:ConfigFetch":
            return {"pec_T_sec": self._pec_T_sec}
        return {}

    def get_property(self, name):
        return {
            "rightascension": self._ra_h,
            "declination": self._dec_d,
            "guideraterightascension": self._guide_rate_ra,
            "guideratedeclination": self._guide_rate_dec,
        }[name]

    def put_property(self, name, body):
        self.puts.append((name, body))


def _fake_clock():
    """A monotonic-like clock that doesn't actually depend on wall time, paired with a
    no-op sleep, so PEState.advance() runs instantly in tests."""
    t = [0.0]

    def clock():
        return t[0]

    def sleep(seconds):
        t[0] += seconds

    return clock, sleep


def test_syncguide_pe_sends_one_sync_per_step_and_marks_start_and_end():
    session = FakeSession()
    clock, sleep = _fake_clock()
    state = PEState()

    state.advance(session, "SYNCGUIDE_PE", {
        "ra_model": [0, 10.0, 0], "dec_model": [0, 0, 0],
        "exposure_s": 15, "session_min": 1,  # 4 steps
    }, sleep=sleep, clock=clock)

    sync_calls = [p for name, p in session.puts if name == "synctocoordinates"]
    assert len(sync_calls) == 4

    mark_events = [p["event"] for name, p in session.actions if name == "Polaris:ReplayMark"]
    assert mark_events == ["SYNCGUIDE_PE_start", "SYNCGUIDE_PE_end"]


def test_syncguide_pe_offset_applied_relative_to_live_position():
    session = FakeSession(ra_h=10.0, dec_d=-30.0, pec_T_sec=2040)
    clock, sleep = _fake_clock()
    state = PEState()

    state.advance(session, "SYNCGUIDE_PE", {
        "ra_model": [60, 0, 0], "dec_model": [0, 0, 0],  # 60 arcmin/hr DC drift, RA only
        "exposure_s": 3600, "session_min": 60,  # one step at t=0 (offset 0), matches base RA
    }, sleep=sleep, clock=clock)

    name, body = [p for p in session.puts if p[0] == "synctocoordinates"][0]
    assert body["RightAscension"] == pytest.approx(10.0)  # t=0 -> zero offset
    assert body["Declination"] == pytest.approx(-30.0)


def test_pec_T_sec_override_bypasses_config_fetch():
    session = FakeSession(pec_T_sec=2040)
    clock, sleep = _fake_clock()
    state = PEState()

    state.advance(session, "SYNCGUIDE_PE", {
        "ra_model": [0, 0, 0], "dec_model": [0, 0, 0],
        "exposure_s": 10, "session_min": 1, "pec_T_sec": 60,
    }, sleep=sleep, clock=clock)

    assert not any(name == "Polaris:ConfigFetch" for name, _ in session.actions)
    start_mark = next(p for name, p in session.actions if name == "Polaris:ReplayMark" and p["event"] == "SYNCGUIDE_PE_start")
    assert start_mark["pec_T_sec"] == 60


def test_two_phases_continue_offset_smoothly_not_reset_to_zero():
    session = FakeSession(ra_h=10.0, dec_d=0.0, pec_T_sec=2040)
    clock, sleep = _fake_clock()
    state = PEState()

    # Phase 1: pure DC drift, 60 arcmin/hr RA, for 60 minutes (one step, well past the
    # midpoint since exposure_s == session length here is just to force >0 accumulated drift).
    state.advance(session, "SYNCGUIDE_PE", {
        "ra_model": [60, 0, 0], "dec_model": [0, 0, 0],
        "exposure_s": 1800, "session_min": 60,  # steps at t=0 and t=1800s
    }, sleep=sleep, clock=clock)

    end_of_phase1 = state.ra_offset_deg
    assert end_of_phase1 == pytest.approx(0.5)  # 60 arcmin/hr * 0.5hr = 30 arcmin = 0.5 deg

    session.puts.clear()

    # Phase 2: no further drift (dc=0) -- should start from phase 1's accumulated offset,
    # not jump back to zero.
    state.advance(session, "SYNCGUIDE_PE", {
        "ra_model": [0, 0, 0], "dec_model": [0, 0, 0],
        "exposure_s": 10, "session_min": 1,
    }, sleep=sleep, clock=clock)

    name, body = session.puts[0]
    assert body["RightAscension"] == pytest.approx(10.0 + end_of_phase1 / 15.0)


def test_pulseguide_pe_sends_ra_then_dec_each_cycle_with_correct_directions():
    session = FakeSession(guide_rate_ra=0.001, guide_rate_dec=0.001)
    clock, sleep = _fake_clock()
    state = PEState()

    # DC-only, RA positive (East) and Dec negative (South) drift.
    state.advance(session, "PULSEGUIDE_PE", {
        "ra_model": [3600, 0, 0], "dec_model": [-3600, 0, 0],  # 1 deg/hr each axis
        "exposure_s": 3600, "session_min": 120,  # two steps: t=0 (no-op) and t=3600
    }, sleep=sleep, clock=clock)

    pulses = [p for name, p in session.puts if name == "pulseguide"]
    # First tick's delta is ~0 (t=0), skipped; second tick sends RA then Dec.
    assert [p["Direction"] for p in pulses] == [PULSE_EAST, PULSE_SOUTH]
    for p in pulses:
        assert 1 <= p["Duration"] <= 10000


def test_pulseguide_direction_flips_sign():
    session = FakeSession(guide_rate_ra=0.001, guide_rate_dec=0.001)
    clock, sleep = _fake_clock()
    state = PEState()

    state.advance(session, "PULSEGUIDE_PE", {
        "ra_model": [-3600, 0, 0], "dec_model": [3600, 0, 0],
        "exposure_s": 3600, "session_min": 120,
    }, sleep=sleep, clock=clock)

    pulses = [p for name, p in session.puts if name == "pulseguide"]
    assert [p["Direction"] for p in pulses] == [PULSE_WEST, PULSE_NORTH]


def test_pulseguide_duration_clamped_to_ascom_range():
    session = FakeSession(guide_rate_ra=0.00001, guide_rate_dec=0.00001)  # very slow guide rate
    clock, sleep = _fake_clock()
    state = PEState()

    state.advance(session, "PULSEGUIDE_PE", {
        "ra_model": [360000, 0, 0], "dec_model": [0, 0, 0],  # huge drift -> huge duration
        "exposure_s": 60, "session_min": 2,
    }, sleep=sleep, clock=clock)

    pulses = [p for name, p in session.puts if name == "pulseguide"]
    assert pulses
    assert all(p["Duration"] <= 10000 for p in pulses)
