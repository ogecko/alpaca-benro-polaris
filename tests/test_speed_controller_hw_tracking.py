"""
Hardware test: PID sidereal tracking error with the v2 speed controller must be no worse than legacy.

For each orientation (chosen to exercise different M1/M3 motor rates), and for each controller in
turn (legacy, then v2, switched live): slew there with Polaris:SlewAbsolute, enable tracking, wait
for it to settle, then sample the PID error signal (StatusFetch `errsig`, theta_ref - theta_pv) at
4 Hz and compute its RMS per motor and in total.

Runs only against a live driver whose Polaris is connected and aligned; stops any tracking in
progress, restores the original speed controller setting and leaves tracking off. ~18 minutes.
"""
import time

import numpy as np
import pytest

from polaris_hw import (get, sample_tracking_error, set_speed_controller, set_tracking, slew_absolute,
                        speed_controller, status, stop_all)

ORIENTATIONS = {                        # az, alt, roll (deg); motor rates at lat -33.7 in comments
    "pole_alt15_roll0": (180.0, 15.0, 0.0),    # M1 -0.0153, M3 +0.0134 (counter-rotating, above level 1)
    "pole_alt20_roll0": (180.0, 20.0, 0.0),    # M1 -0.0119, M3 +0.0102 (at the level-1 limit)
    "pole_alt20_roll45": (180.0, 20.0, 45.0),  # M1 -0.0033, M2 -0.0033, M3 +0.0015 (roll removes it)
    "north_alt15_roll0": (0.0, 15.0, 0.0),     # M1 +0.0107, M3 -0.0134
    "mid_alt_meridian": (0.0, 50.0, 0.0),      # M1 +0.0006, M3 -0.0045
}
SETTLE_S = 30.0
MEASURE_S = 60.0
ARCSEC = 3600.0
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


@pytest.fixture(scope="module", autouse=True)
def mount():
    reason = not_ready_reason()
    if reason:
        pytest.skip(f"Hardware test skipped: {reason}")
    original = speed_controller()
    set_tracking(False)
    stop_all()
    yield
    set_tracking(False)
    stop_all()
    if original in ("legacy", "v2"):
        set_speed_controller(original == "v2")
    print("\nPID tracking RMS error (arcsec) [M1, M2, M3] total:")
    for name, r in RESULTS.items():
        print(f"  {name:20s} " + "   ".join(f"{c}: {np.round(v[0], 1)} {v[1]:.1f}" for c, v in r.items()))


def track_and_measure(az, alt, roll):
    set_tracking(False)
    slew_absolute(az, alt, roll)
    set_tracking(True)
    time.sleep(SETTLE_S)
    err, cmds = sample_tracking_error(MEASURE_S)
    set_tracking(False)
    err = err * ARCSEC
    per_axis = np.sqrt(np.mean(err ** 2, axis=0))
    total = float(np.sqrt(np.mean(np.sum(err ** 2, axis=1))))
    return per_axis, total, cmds


@pytest.mark.parametrize("name", ORIENTATIONS.keys())
def test_v2_tracking_rms_no_worse_than_legacy(name):
    az, alt, roll = ORIENTATIONS[name]
    RESULTS[name] = {}
    for label, use_v2 in (("legacy", False), ("v2", True)):
        set_speed_controller(use_v2)
        per_axis, total, cmds = track_and_measure(az, alt, roll)
        RESULTS[name][label] = (per_axis, total)
        common = max(set(cmds), key=cmds.count)
        print(f"\n  {name} {label:6s}: RMS {np.round(per_axis, 1)} arcsec, total {total:.1f}; typical motorcmd {common}")
    legacy, v2 = RESULTS[name]["legacy"][1], RESULTS[name]["v2"][1]
    assert v2 <= legacy, (
        f"{name} (az {az}, alt {alt}, roll {roll}): PID tracking RMS with v2 {v2:.1f} arcsec is worse "
        f"than legacy {legacy:.1f} arcsec (per motor v2 {np.round(RESULTS[name]['v2'][0], 1)}, "
        f"legacy {np.round(RESULTS[name]['legacy'][0], 1)})")
