"""
Offline closed-loop tracking test: with the PID tracking a sidereal reference, the v2 speed
controller's RMS tracking error must be no worse than the legacy controller's, at orientations
that exercise different M1/M3 motor rates (same poses as tests/test_speed_controller_hw_tracking.py).

Uses tests/pid_loop_sim.py (PID TRACK law mirror -> speed controller -> MCU model -> 518 cadence).
"""
import numpy as np
import pytest

import pid_loop_sim as sim
from test_speed_controller_hw_tracking import ORIENTATIONS


@pytest.fixture(scope="module")
def cm():
    return sim.calibration()


@pytest.mark.parametrize("name", ORIENTATIONS.keys())
def test_v2_tracking_rms_no_worse_than_legacy_sim(cm, name):
    az, alt, roll = ORIENTATIONS[name]
    rates = sim.orientation_motor_rates(az, alt, roll)
    legacy = sim.track(sim.LegacyDriver(cm), rates)
    v2 = sim.track(sim.V2Driver(cm), rates)
    assert v2[1] <= legacy[1], (
        f"{name} (motor rates {np.round(rates, 4)} dps): simulated PID tracking RMS with v2 {v2[1]:.1f} arcsec "
        f"is worse than legacy {legacy[1]:.1f} arcsec (per motor v2 {np.round(v2[0], 1)}, legacy {np.round(legacy[0], 1)})")
