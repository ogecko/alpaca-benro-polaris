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
        self._sitelatitude = -33.65528161613541

    def update(self, az, alt, roll=0):
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
    sm.sync_position_angle(5)
    assert len(sm.sync_history) >= 1
    assert isinstance(sm.sync_history[0], dict)
    expected_keys = {"timestamp", "p_q1", "p_az", "p_alt", "p_roll", "a_az", "a_alt", "a_pa"}
    assert expected_keys.issubset(sm.sync_history[0].keys())
    assert sm.sync_history[0]["a_az"] == 170
    assert sm.sync_history[1]["a_pa"] == 5

def test_no_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.q1_adj * p._q1)
    assert f'{az:.6f}' == "180.000000"
    assert f'{alt:.6f}' == "45.000000"
    assert f'{roll:.6f}' == "0.000000"

def test_single_syncs_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 45)
    sm.sync_az_alt(170, 45.123456)
    az,alt = sm.azalt_polaris2ascom(180,45)
    assert f'{az:.6f}, {alt:.6f}' == "170.000000, 45.123456"
    az,alt = sm.azalt_polaris2ascom(160,45)
    assert f'{az:.6f}, {alt:.6f}' == "149.957647, 45.115995"
    az,alt = sm.azalt_polaris2ascom(180,0)
    assert f'{az:.6f}, {alt:.6f}' == "170.000000, 0.123456"
    assert f'{sm.tilt_az:.6f}, {sm.tilt_mag:.6f}' == "170.000000, 0.123456"

def test_azshift10_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(160, 45)
    sm.sync_az_alt(170, 45.123456)
    p.update(100, 45)
    sm.sync_az_alt(110, 45.123456)
    az,alt = sm.azalt_polaris2ascom(40,45)
    assert f'{az:.6f}, {alt:.6f}' == "49.877848, 44.999870"
    az,alt = sm.azalt_ascom2polaris(49.877848,44.999870)
    assert f'{az:.6f}, {alt:.6f}' == "40.000000, 45.000000"
    assert f'{sm.tilt_az:.6f}, {sm.tilt_mag:.6f}' == "139.999989, 0.122152"

def test_leveling_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 0)
    sm.sync_az_alt(180, -1) # titlted low
    p.update(270, 0)
    sm.sync_az_alt(270, 0) # now level
    p.update(90, 0)
    sm.sync_az_alt(90, 0)  # level again
    az,alt = sm.azalt_polaris2ascom(0,0)
    assert f'{az:.6f}, {alt:.6f}' == "0.000000, 1.000000"
    assert f'{sm.tilt_az:.6f}, {sm.tilt_mag:.6f}' == "0.000000, 1.000000"

def test_largetilt_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(135, 45)
    sm.sync_az_alt(180, 0) # titlted low
    p.update(225, 45)
    sm.sync_az_alt(270, 45) # now level
    p.update(45, 45)
    sm.sync_az_alt(90, 45)  # level again
    az,alt = sm.azalt_polaris2ascom(315,0)
    assert f'{az:.6f}, {alt:.6f}' == "360.000000, 22.500000"
    az,alt = sm.azalt_polaris2ascom(135,45)
    assert f'{az:.6f}, {alt:.6f}' == "180.000000, 22.500000"
    assert f'{sm.tilt_az:.6f}, {sm.tilt_mag:.6f}' == "360.000000, 21.678499"


def test_az170alt15shift_sync_adj():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 45)
    sm.sync_az_alt(10, 30)
    p.update(90, 45)
    sm.sync_az_alt(260, 45)
    p.update(270, 45)
    sm.sync_az_alt(100, 45)
    az,alt = sm.azalt_polaris2ascom(270,45)
    assert f'{az:.6f}, {alt:.6f}' == "91.215983, 43.045464"
