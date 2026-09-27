"""
Hardware test: gotos while tracking must settle into the tracking tolerance quickly, as used by
slew-and-center: a large goto, plate solve, then a small corrective goto.

While tracking a goto completes (Slewing false) when every motor's PID error is within the tracking
tolerance (pid_Kc/60/20 = 2.25" by default) or after 45 s. For each step this measures:
  arrive    - first time every motor error is within 0.1 deg
  tolerance - first time every motor error is within the tracking tolerance
  complete  - when the goto reported complete (Slewing false), and whether the 45 s timeout ended it
A roll (PA) step while tracking must also keep pointing (reported Az/Alt, net of sidereal motion via
RA/Dec) within 30'.

Runs only when the driver allows hardware unit tests (config log_hardware_unit_tests) and the Polaris
is connected, aligned and not slewing. Leaves tracking off and the mount stopped. ~4 minutes.
"""
import math
import time

import numpy as np
import pytest

from polaris_hw import (URL, _check, _txn, action, get, hardware_tests_disabled_reason, requests, set_tracking,
                        slew_absolute, status, stop_all)

POSE = (135.0, 45.0, 0.0)            # az, alt, roll to start tracking from
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


def slew_to_coordinates(ra_h, dec_deg):
    data = {"RightAscension": ra_h, "Declination": dec_deg, "ClientID": 77, "ClientTransactionID": next(_txn)}
    _check(requests.put(f"{URL}/slewtocoordinatesasync", data=data, timeout=10), "slewtocoordinatesasync")


def tolerance_deg():
    kc = action("Polaris:ConfigFetch", {"configNames": ["pid_Kc"]}).get("pid_Kc", 0.75)
    return kc / 60 / 20


@pytest.fixture(scope="module", autouse=True)
def tracking_at_pose():
    reason = hardware_tests_disabled_reason() or not_ready_reason()
    if reason:
        pytest.skip(f"Hardware test skipped: {reason}")
    set_tracking(False)
    stop_all()
    slew_absolute(*POSE)
    set_tracking(True)
    time.sleep(20)
    yield
    set_tracking(False)
    stop_all()
    print("\nGoto-while-tracking settle times (s): arrive / tolerance / complete [timed out]")
    for name, r in RESULTS.items():
        print(f"  {name:22s} {r}")


def measure_goto(start_goto, max_s=60.0):
    tol = tolerance_deg()
    start_goto()
    t0 = time.monotonic()
    arrive = within = complete = None
    time.sleep(0.3)
    while time.monotonic() - t0 < max_s:
        s = status()
        t = time.monotonic() - t0
        err = np.abs(np.array(s["errsig"]))
        if arrive is None and np.all(err < 0.1):
            arrive = t
        if within is None and np.all(err < tol):
            within = t
        if complete is None and not s["gotoing"] and not s["slewing"]:
            complete = t
        if complete is not None and within is not None:
            break
        time.sleep(0.1)
    return {"arrive": arrive, "tolerance": within, "complete": complete,
            "timed_out": complete is not None and complete >= 44.0}


def fmt(r):
    f = lambda x: "-" if x is None else f"{x:.1f}"
    return f"{f(r['arrive'])} / {f(r['tolerance'])} / {f(r['complete'])}{' [timeout]' if r['timed_out'] else ''}"


def test_large_goto_then_corrective_goto_settle_quickly():
    s = status()
    ra, dec = s["rightascension"], s["declination"]
    large = measure_goto(lambda: slew_to_coordinates((ra + 5 / 15) % 24, dec))
    RESULTS["large goto 5 deg RA"] = fmt(large)
    time.sleep(3)
    s = status()
    corrective = measure_goto(lambda: slew_to_coordinates(s["rightascension"], s["declination"] + 3 / 60))
    RESULTS["corrective goto 3' Dec"] = fmt(corrective)
    print(f"\n  large {fmt(large)}   corrective {fmt(corrective)}")
    assert large["complete"] is not None and large["complete"] <= 20.0, (
        f"large 5 deg goto while tracking took {large['complete']} s to complete (limit 20 s): {fmt(large)}")
    assert corrective["complete"] is not None and corrective["complete"] <= 8.0, (
        f"3' corrective goto while tracking took {corrective['complete']} s to complete (limit 8 s): {fmt(corrective)}")


def test_roll_step_while_tracking_keeps_pointing():
    s0 = status()
    ra0, dec0 = s0["rightascension"], s0["declination"]
    action("Polaris:SlewRelative", {"roll": 30.0, "isasync": True})
    worst, t0 = 0.0, time.monotonic()
    time.sleep(0.3)
    while time.monotonic() - t0 < 60:
        s = status()
        d_ra = (s["rightascension"] - ra0) * 15 * math.cos(math.radians(dec0))
        worst = max(worst, math.hypot(d_ra, s["declination"] - dec0) * 60)
        if not s["gotoing"] and not s["slewing"]:
            break
        time.sleep(0.2)
    took = time.monotonic() - t0
    RESULTS["roll step +30 tracking"] = f"pointing wandered {worst:.1f}' , complete {took:.1f}"
    print(f"\n  roll step while tracking: pointing wandered {worst:.1f}' , took {took:.1f} s")
    assert worst <= 30.0, f"a 30 deg roll step while tracking moved the pointing {worst:.1f}' (limit 30')"
