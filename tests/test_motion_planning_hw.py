"""
Hardware acceptance test for coordinated_speed_control (GotoTrajectory + jog shaping).

For each case the same move is made with coordinated_speed_control off (legacy) and on:
  * roll-only goto at low altitude: pointing (reported Az/Alt) must stay within 10' of the start
    Az/Alt with planning, and be better than legacy;
  * Az jog released after 5 s: M1's overshoot past the reference (PID error signal) must be at most
    10' with planning, and less than legacy.

Runs only when the driver allows hardware unit tests (config log_hardware_unit_tests) and the Polaris
is connected, aligned and not slewing. Stops tracking, restores coordinated_speed_control, leaves the
mount stopped. ~4 minutes.
"""
import math
import time

import numpy as np
import pytest

from polaris_hw import (action, get, hardware_tests_disabled_reason, set_tracking, slew_absolute, status, stop_all)

ARCMIN = 60.0
RESULTS = {}


def not_ready_reason():
    try:
        if not get("connected", timeout=2):
            return "driver is not connected to the Polaris"
        s = status()
    except Exception as e:
        return f"driver not reachable ({e.__class__.__name__})"
    if not s["aligned"]:
        return "Polaris is not aligned"
    if s["slewing"]:
        return "Polaris is slewing"
    return None


def set_planning(on):
    action("Polaris:ConfigUpdate", {"coordinated_speed_control": bool(on)})
    time.sleep(0.5)


def wait_idle(timeout=90):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        s = status()
        if not s["gotoing"] and not s["slewing"] and s["pidmode"] == "IDLE":
            return s
        time.sleep(0.5)
    return status()


def separation_arcmin(az1, alt1, az2, alt2):
    a1, h1, a2, h2 = map(math.radians, (az1, alt1, az2, alt2))
    c = math.sin(h1) * math.sin(h2) + math.cos(h1) * math.cos(h2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * ARCMIN


@pytest.fixture(scope="module", autouse=True)
def mount():
    reason = hardware_tests_disabled_reason() or not_ready_reason()
    if reason:
        pytest.skip(f"Hardware test skipped: {reason}")
    original = action("Polaris:ConfigFetch", {"configNames": ["coordinated_speed_control"]}).get("coordinated_speed_control", False)
    set_tracking(False)
    stop_all()
    yield
    set_tracking(False)
    stop_all()
    set_planning(original)
    print("\ncoordinated_speed_control acceptance:")
    for name, r in RESULTS.items():
        print(f"  {name:28s} legacy {r['legacy']}   planned {r['planned']}")


def roll_goto(az, alt, roll0, roll1):
    slew_absolute(az, alt, roll0)
    s0 = wait_idle()
    az0, alt0 = s0["azimuth"], s0["altitude"]
    action("Polaris:SlewAbsolute", {"roll": roll1, "isasync": True})
    worst, t0 = 0.0, time.monotonic()
    time.sleep(0.3)
    while time.monotonic() - t0 < 90:
        s = status()
        worst = max(worst, separation_arcmin(az0, alt0, s["azimuth"], s["altitude"]))
        if not s["gotoing"] and s["pidmode"] == "IDLE":
            break
        time.sleep(0.2)
    return worst, time.monotonic() - t0, s["roll"]


@pytest.mark.parametrize("az,alt,roll0,roll1", [(180.0, 20.0, 0.0, 45.0)], ids=["alt20_roll_0_to_45"])
def test_roll_goto_keeps_pointing(az, alt, roll0, roll1):
    out = {}
    for label, on in (("legacy", False), ("planned", True)):
        set_planning(on)
        worst, took, roll = roll_goto(az, alt, roll0, roll1)
        out[label] = (round(worst, 1), round(took, 1))
        print(f"\n  roll goto {label:7s}: pointing wandered {worst:.1f}' in {took:.1f} s, ended at roll {roll:.2f}")
    RESULTS[f"roll goto alt{alt:.0f} {roll0:+.0f}->{roll1:+.0f}"] = {k: f"{v[0]}' {v[1]}s" for k, v in out.items()}
    assert out["planned"][0] <= 10.0, f"with planning, pointing wandered {out['planned'][0]}' during the roll change (limit 10')"
    assert out["planned"][0] < out["legacy"][0], f"planning ({out['planned'][0]}') was not better than legacy ({out['legacy'][0]}')"


def az_jog(rate, on_s=5.0, after_s=8.0):
    slew_absolute(180.0, 45.0, 0.0)
    wait_idle()
    action("Polaris:MoveAxis", {"axis": 0, "rate": rate})
    time.sleep(on_s)
    action("Polaris:MoveAxis", {"axis": 0, "rate": 0})
    overshoot, prev_cmd, t0 = 0.0, None, time.monotonic()
    while time.monotonic() - t0 < after_s:
        s = status()
        overshoot = max(overshoot, -np.sign(rate) * s["errsig"][0] * ARCMIN)   # M1 past its reference
        time.sleep(0.1)
    wait_idle()
    return overshoot


@pytest.mark.parametrize("rate", [3.0], ids=["az_jog_3dps"])
def test_jog_release_overshoot(rate):
    out = {}
    for label, on in (("legacy", False), ("planned", True)):
        set_planning(on)
        out[label] = round(az_jog(rate), 1)
        print(f"\n  az jog {rate} deg/s {label:7s}: M1 overshoot after release {out[label]}'")
    RESULTS[f"az jog {rate} deg/s release"] = {k: f"{v}'" for k, v in out.items()}
    assert out["planned"] <= 10.0, f"with planning, M1 overshot {out['planned']}' after the jog (limit 10')"
    assert out["planned"] < out["legacy"], f"planning ({out['planned']}') was not better than legacy ({out['legacy']}')"
