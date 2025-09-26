import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

# import pytest
from control import SyncManager, quaternion_to_angles, angles_to_quaternion, angular_difference
from polaris import Polaris

import pytest
import logging
from pyquaternion import Quaternion

import math

class Polaris:
    def __init__(self):
        self.update(180, 45, 0)

    def update(self, az, alt, roll):
        self._p_azimuth = az
        self._p_altitude = alt
        self._p_roll = roll
        self._q1 = angles_to_quaternion(az, alt, roll)


def test_dummy():
    assert(1==1)

def test_sync_history():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    sm.sync_az_alt(170, 45.123456)
    sm.sync_roll(5)
    assert len(sm.sync_history) >= 1
    assert isinstance(sm.sync_history[0], dict)
    expected_keys = {"timestamp", "q1", "p_az", "p_alt", "p_roll", "a_az", "a_alt", "a_roll", "cost"}
    assert expected_keys.issubset(sm.sync_history[0].keys())
    assert sm.sync_history[0]["a_az"] == 170
    assert sm.sync_history[1]["a_roll"] == 5

def test_no_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.q1_adj * p._q1)
    assert f'{az:.6f}' == "180.000000"
    assert f'{alt:.6f}' == "45.000000"
    assert f'{roll:.6f}' == "0.000000"

def test_no_roll_syncs_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    sm.sync_az_alt(170, 45.123456)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.q1_adj * p._q1)
    assert f'{az:.6f}' == "170.000000"
    assert f'{alt:.6f}' == "45.123456"
    assert f'{abs(roll):.6f}' == "0.000000"

def test_azalt_and_roll_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    sm.sync_az_alt(170, 45.123456)
    sm.sync_roll(5)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.q1_adj * p._q1)
    assert f'{az:.6f}' == "170.000000"
    assert f'{alt:.6f}' == "45.123456"
    assert f'{roll:.6f}' == "5.000000"

def test_leveling_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 10, 0)
    sm.sync_az_alt(180, 30) # 1 degree high
    p.update(270, 10, 0)
    sm.sync_az_alt(270, 10) # now level
    p.update(90, 10, 0)
    sm.sync_az_alt(90, 10)  # level again
    p.update(0, 10, 0)
    sm.sync_az_alt(0, -10)  # level again
    p.update(0, 10, 0)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.q1_adj * p._q1)
    assert f'{az:.6f}, {alt:.6f}, {abs(roll):.6f}' == "360.000000, 44.749995, 0.000000"
    assert f'{[float(x['cost']) for x in sm.sync_history]}' == "0.000000"