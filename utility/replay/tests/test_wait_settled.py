import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import KeywordLine, run, wait_settled


class FakeSlewSession:
    """slewing() reports True for the first `slewing_ticks` polls, then False."""

    def __init__(self, slewing_ticks):
        self.slewing_ticks = slewing_ticks
        self.polls = 0
        self.actions = []

    def action(self, name, parameters):
        self.actions.append((name, parameters))
        return f"{name} ok"

    def get_property(self, name):
        assert name == "slewing"
        self.polls += 1
        return self.polls <= self.slewing_ticks


def _fake_clock(step=1.0):
    t = [0.0]

    def clock():
        return t[0]

    def sleep(seconds):
        t[0] += seconds

    return clock, sleep


def test_wait_settled_returns_once_slewing_clears():
    session = FakeSlewSession(slewing_ticks=3)
    clock, sleep = _fake_clock()
    wait_settled(session, timeout_s=60, poll_s=1.0, sleep=sleep, clock=clock)
    assert session.polls == 4  # 3 "still slewing" + 1 "clear"


def test_wait_settled_returns_immediately_if_already_settled():
    session = FakeSlewSession(slewing_ticks=0)
    clock, sleep = _fake_clock()
    wait_settled(session, timeout_s=60, poll_s=1.0, sleep=sleep, clock=clock)
    assert session.polls == 1


def test_wait_settled_times_out_if_never_clears():
    session = FakeSlewSession(slewing_ticks=10_000)
    clock, sleep = _fake_clock()
    with pytest.raises(TimeoutError, match="WAIT_SETTLED"):
        wait_settled(session, timeout_s=5, poll_s=1.0, sleep=sleep, clock=clock)


def test_run_dispatches_wait_settled_keyword_line():
    session = FakeSlewSession(slewing_ticks=2)
    instructions = [(1, KeywordLine("WAIT_SETTLED", {"timeout_s": 30, "poll_s": 1.0}))]
    # run() uses the real time.sleep for WAIT_SETTLED today -- keep this fast by using a tiny
    # poll interval rather than injecting a fake clock (run() doesn't expose one for this path).
    instructions = [(1, KeywordLine("WAIT_SETTLED", {"timeout_s": 30, "poll_s": 0.001}))]
    run(instructions, session, log=lambda *a: None)
    assert session.polls == 3
