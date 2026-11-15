"""
A goto during a Home or Park interrupts it, as a goto during a goto does (2026-11-15: a Pilot dial click during Home was
dropped -- the PID stayed in HOMING, whose reset_sp wiped the new target each tick, and the Home ran on).
Run on the digital twin (tests/sim_digital_twin.py).
"""
import numpy as np
import pytest

from sim_digital_twin import Twin

START = (200.0, 40.0, 0.0)
TARGET_AZ, TARGET_ALT = 215.0, 50.0


@pytest.mark.parametrize("target_type", ["alpha", "delta"])
@pytest.mark.parametrize("mode", ["HOMING", "PARKING"])
def test_a_goto_interrupts_a_home_or_park(mode, target_type):
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place(START)
        fired = []
        tw.pid.set_pid_mode(mode)                     # as findHome / park leave it
        tw.pid.set_homing_complete_callback(lambda: fired.append("home"))
        tw.pid.set_parking_complete_callback(lambda: fired.append("park"))

        if target_type == "alpha":
            tw.pid.set_alpha_target({"az": TARGET_AZ, "alt": TARGET_ALT})
        else:
            ra, dec = tw.polaris.altaz2radec(TARGET_ALT, TARGET_AZ)
            tw.pid.set_delta_target({"ra": ra, "dec": dec})
        done, t0 = {}, tw.clock.t
        tw.pid.set_goto_complete_callback(lambda: done.setdefault("goto", tw.clock.t))   # as slew_axis does
        assert tw.pid.mode == "AUTO"

        while tw.clock.t - t0 < 60 and "goto" not in done:
            tw.run(0.2)
        tw.close()
    finally:
        mp.undo()

    assert "goto" in done and done["goto"] - t0 < 40, "the goto should arrive, not time out (45 s)"
    if target_type == "alpha":
        assert np.allclose(tw.pid.alpha_sp[:2], [TARGET_AZ, TARGET_ALT], atol=1e-6), "the target survived the Home/Park"
    assert fired == [], "the abandoned Home/Park must not report completion"


@pytest.mark.parametrize("mode", ["HOMING", "PARKING"])
def test_a_rotate_interrupting_a_home_or_park_clears_slewing(mode, monkeypatch):
    """A rotate's markRotateAsUnderway leaves Polaris' slewing flag alone, so RotateToRollAngle has to cancel the
    Home/Park itself, or Slewing stayed True with no callback left to clear it."""
    import logging
    import threading
    import types

    from config import Config
    from polaris import Polaris

    monkeypatch.setattr(Config, "advanced_rotator", True, raising=False)
    monkeypatch.setattr(Config, "advanced_control", True, raising=False)

    class FakePID:
        def __init__(self):
            self.mode, self.targets = mode, []

        def set_alpha_target(self, sp):
            self.targets.append(sp)
            self.mode = "AUTO"                         # as _interrupt_home_or_park does

        def set_homing_complete_callback(self, fn):
            pass

        def set_parking_complete_callback(self, fn):
            pass

        def set_rotate_complete_callback(self, fn):
            pass

    p = types.SimpleNamespace(_lock=threading.Lock(), _pid=FakePID(), _slewing=True, _athome=False, _atpark=False,
                              _rotating=False, _rotate_complete_event=None, rotating=True,
                              _sm=types.SimpleNamespace(invalidate_sync_guiding=lambda: None),
                              logger=logging.getLogger("test"))
    for name in ("markHomingAsCanceled", "markParkingAsCanceled", "markRotateAsUnderway", "markRotateAsComplete"):
        setattr(p, name, types.MethodType(getattr(Polaris, name), p))

    Polaris.RotateToRollAngle(p, 30.0)

    assert p._pid.targets == [{"roll": 30.0}]
    assert p._slewing is False and p._rotating is True
