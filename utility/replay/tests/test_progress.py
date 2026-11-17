import io
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import PEState, _fmt_duration, _progress, countdown_sleep, wait_settled


def test_fmt_duration_seconds_only():
    assert _fmt_duration(0) == "0s"
    assert _fmt_duration(5) == "5s"
    assert _fmt_duration(59) == "59s"


def test_fmt_duration_minutes():
    assert _fmt_duration(60) == "1m00s"
    assert _fmt_duration(125) == "2m05s"


def test_fmt_duration_hours():
    assert _fmt_duration(3661) == "1h01m01s"
    assert _fmt_duration(7200) == "2h00m00s"


def test_fmt_duration_negative_clamped_to_zero():
    assert _fmt_duration(-5) == "0s"


def test_progress_overwrites_with_carriage_return_and_no_newline_by_default():
    out = io.StringIO()
    _progress(out, "hello")
    assert out.getvalue().startswith("\rhello")
    assert not out.getvalue().endswith("\n")


def test_progress_final_adds_newline():
    out = io.StringIO()
    _progress(out, "done", final=True)
    assert out.getvalue().endswith("\n")


def _fake_clock():
    t = [0.0]

    def clock():
        return t[0]

    def sleep(seconds):
        t[0] += seconds

    return clock, sleep


def test_countdown_sleep_advances_full_duration_and_writes_progress():
    clock, sleep = _fake_clock()
    out = io.StringIO()
    countdown_sleep(3.0, sleep=sleep, clock=clock, out=out, tick_s=1.0)
    assert clock() == pytest.approx(3.0)
    # At least one intermediate countdown line, plus a final "done" line.
    assert "remaining" in out.getvalue()
    assert out.getvalue().rstrip("\n").split("\r")[-1].startswith("SLEEP: done.")


def test_countdown_sleep_zero_duration_prints_done_immediately():
    clock, sleep = _fake_clock()
    out = io.StringIO()
    countdown_sleep(0, sleep=sleep, clock=clock, out=out)
    assert clock() == 0.0
    assert "done" in out.getvalue()


class FakeSlewSession:
    def __init__(self, slewing_ticks):
        self.slewing_ticks = slewing_ticks
        self.polls = 0

    def get_property(self, name):
        self.polls += 1
        return self.polls <= self.slewing_ticks


def test_wait_settled_prints_progress_and_final_settled_line():
    session = FakeSlewSession(slewing_ticks=2)
    clock, sleep = _fake_clock()
    out = io.StringIO()
    wait_settled(session, timeout_s=30, poll_s=1.0, sleep=sleep, clock=clock, out=out)
    text = out.getvalue()
    assert "slewing" in text
    assert text.rstrip("\n").split("\r")[-1].startswith("WAIT_SETTLED: settled after")


def test_advance_prints_tick_progress_for_each_step():
    class FakeSession:
        def action(self, name, parameters):
            return {"pec_T_sec": 2040, "pec_accum": [0.0, 0.0]}

        def get_property(self, name):
            return {"rightascension": 10.0, "declination": -30.0}[name]

        def put_property(self, name, body):
            pass

    clock, sleep = _fake_clock()
    out = io.StringIO()
    state = PEState()
    state.advance(FakeSession(), "SYNCGUIDE_PE", {
        "ra_model": [1, 0, 0], "dec_model": [0, 0, 0], "exposure_s": 10, "session_min": 1,
    }, sleep=sleep, clock=clock, out=out)
    text = out.getvalue()
    assert "SYNCGUIDE_PE: tick 1/6" in text
    assert "SYNCGUIDE_PE: tick 6/6" in text
    assert text.rstrip("\n").split("\r")[-1].startswith("SYNCGUIDE_PE: complete")
