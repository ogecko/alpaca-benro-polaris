import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from unittest.mock import patch

import numpy as np
from control import SyncManager, quaternion_to_angles, angles_to_quaternion, angular_difference, calc_parallactic_angle
from polaris import Polaris

import pytest
import logging
from pyquaternion import Quaternion

import math


class PID_Controller:
    def measure(self, alpha, theta):
        return

class Polaris:
    def __init__(self):
        self.update(180, 45, 0)
        self._sitelatitude = -33.65528161613541
        self.azimuth = 180
        self._pid = PID_Controller()

    def update_ascom_from_new_q1_adj(self, q1s, azhint):
        a_t1, a_t2, a_t3, a_az, a_alt, a_roll = quaternion_to_angles(q1s, azhint=azhint)
        alpha_state = np.array([a_az, a_alt, a_roll], dtype=float)
        theta_state = np.array([a_t1, a_t2, a_t3], dtype=float)
        return alpha_state, theta_state

    def update(self, az, alt, roll=0):
        self._p_azimuth = az
        self._p_altitude = alt
        self._p_roll = roll
        self._q1 = angles_to_quaternion(az, alt, roll)
        t1,t2,t3,_,_,_ = quaternion_to_angles(self._q1)
        self._theta_meas = [t1, t2, t3]
        self._roll = roll

def test_dummy():
    assert(1==1)

def test_sync_history():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False

        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        sm.sync_az_alt(0,0,170, 45.123456)
        sm.sync_roll(5)
        assert len(sm.sync_history) >= 1
        assert isinstance(sm.sync_history[0], dict)
        expected_keys = {"timestamp", "p_az", "p_alt", "p_roll", "a_az", "a_alt", "a_roll"}
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

def test_single_syncs_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 45)
        sm.sync_az_alt(0,0,170, 45.123456)
        az,alt = sm.azalt_polaris2ascom(180,45)
        assert f'{az:.6f}, {alt:.6f}' == "170.000000, 45.123456"
        az,alt = sm.azalt_polaris2ascom(160,45)
        assert f'{az:.6f}, {alt:.6f}' == "149.957647, 45.115995"
        az,alt = sm.azalt_polaris2ascom(180,0)
        assert f'{az:.6f}, {alt:.6f}' == "170.000000, 0.123456"
        assert f'{sm.tilt_adj_az:.6f}, {sm.tilt_adj_mag:.6f}' == "170.000000, 0.123456"

def test_azshift10_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(160, 45)
        sm.sync_az_alt(0,0,170, 45.123456)
        p.update(100, 45)
        sm.sync_az_alt(0,0,110, 45.123456)
        az,alt = sm.azalt_polaris2ascom(40,45)
        assert f'{az:.6f}, {alt:.6f}' == "49.908282, 45.035241"
        az,alt = sm.azalt_ascom2polaris(49.877848,44.999870)
        assert f'{az:.6f}, {alt:.6f}' == "39.969434, 44.964695"
        assert f'{sm.tilt_adj_az:.6f}, {sm.tilt_adj_mag:.6f}' == "123.880231, 0.127161"
        assert f'{sm.az_adj:.6f}' == "10.030590"

def test_leveling_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 0)
        sm.sync_az_alt(0, 0, 180, -1) # titlted low
        p.update(270, 0)
        sm.sync_az_alt(0, 0, 270, 0) # now level
        p.update(90, 0)
        sm.sync_az_alt(0, 0, 90, 0)  # level again
        az,alt = sm.azalt_polaris2ascom(0,0)
        assert f'{az:.6f}, {alt:.6f}' == "0.000000, 1.000000"
        assert f'{sm.tilt_adj_az:.6f}, {sm.tilt_adj_mag:.6f}' == "0.000000, 1.000000"

def test_largetilt_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(135, 45)
        sm.sync_az_alt(0, 0, 180, 0) # titlted low
        p.update(225, 45)
        sm.sync_az_alt(0, 0, 270, 45) # now level
        p.update(45, 45)
        sm.sync_az_alt(0, 0, 90, 45)  # level again
        az,alt = sm.azalt_polaris2ascom(315,0)
        assert f'{az:.6f}, {alt:.6f}' == "348.980326, 10.821330"
        az,alt = sm.azalt_polaris2ascom(135,45)
        assert f'{az:.6f}, {alt:.6f}' == "169.875071, 34.170640"
        assert f'{sm.tilt_adj_az:.6f}, {sm.tilt_adj_mag:.6f}' == "354.637971, 10.778185"


def test_az170alt15shift_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        MockConfig.log_quest_model = False
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 45)
        sm.sync_az_alt(0, 0, 10, 30)
        p.update(90, 45)
        sm.sync_az_alt(0, 0, 260, 45)
        p.update(270, 45)
        sm.sync_az_alt(0, 0, 100, 45)
        az,alt = sm.azalt_polaris2ascom(270,45)
        assert f'{az:.6f}, {alt:.6f}' == "100.000000, 45.000000"

def test_zeroroll_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 45, 10)
        sm.sync_roll(10)
        a_roll = sm.roll_polaris2ascom(20)
        assert f'{a_roll:.6f}' == "20.000000"

def test_15roll_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 45, 10)
        sm.sync_roll(25)
        a_roll = sm.roll_polaris2ascom(90)
        assert f'{a_roll:.6f}' == "105.000000"

def test_neg60roll_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 30, 80)
        sm.sync_roll(30)
        a_roll = sm.roll_polaris2ascom(180)
        assert f'{a_roll:.6f}' == "130.000000"
        p_roll = sm.roll_ascom2polaris(200)
        assert f'{p_roll:.6f}' == "250.000000"

def test_tworoll_sync_adj():
    with patch('control.Config') as MockConfig:
        MockConfig.advanced_alignment = True
        MockConfig.advanced_control = True
        p = Polaris()
        logger = logging.getLogger()
        sm = SyncManager(logger,p)
        p.update(180, 30, 0)
        sm.sync_roll(30)
        p.update(180, 30, 80)
        sm.sync_roll(130)
        a_roll = sm.roll_polaris2ascom(180)
        assert f'{a_roll:.6f}' == "220.000000"  # 180 + (30+50)/2


def test_aboveSouth_roll2pa():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 45, 10)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "10.000000, -0.000000"  

def test_belowSouth_roll2pa():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 30, 10)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "190.000000, -180.000000"  

def test_belowSouth_pa2roll():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 30, 200)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "20.000000, -180.000000"  

def test_aboveNorth_roll2pa():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(0, 0, 30)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "210.000000, -180.000000"  

def test_horizEast_roll2pa():
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(90, 0, 30)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "266.344718, -123.655282"  # PA -123+30 = -93+360 = 267


def test_East_parallactic_angle():
    p = Polaris()
    pa = calc_parallactic_angle(90, 0, p._sitelatitude)
    assert f'{pa:.6f}' == "-123.655282"  

def test_West_parallactic_angle():
    p = Polaris()
    pa = calc_parallactic_angle(270, 0, p._sitelatitude)
    assert f'{pa:.6f}' == "123.655282"  

def test_Zenith_parallactic_angle():
    p = Polaris()
    pa = calc_parallactic_angle(45, 90, p._sitelatitude)
    assert f'{pa:.6f}' == "0.000000"  

def test_NearZenith_parallactic_angle():
    p = Polaris()
    pa = calc_parallactic_angle(90, 89.999, p._sitelatitude)
    assert f'{pa:.6f}' == "-90.000666"  

def test_SouthCelestrialPole_parallactic_angle():
    p = Polaris()
    pa = calc_parallactic_angle(180, p._sitelatitude, p._sitelatitude)
    assert f'{pa:.6f}' == "-180.000000"  


