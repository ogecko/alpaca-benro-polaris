import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
from control import SyncManager
from kinematics import calc_parallactic_angle, calc_equatorial_axes_B, radec_to_altaz, azalt_to_radec
from kinematics import quaternion_to_angles, azaltroll_to_q, q_to_azaltroll
from shr import format_timestamp

import pytest
import logging
from quaternion import Q as Quaternion

import math

DEFAULT_LAT    = -33.86
DEFAULT_LON    = 151.12

@pytest.fixture
def mock_config():
    defaults = {
        "advanced_alignment":       True,
        "advanced_align_lga":       False,
        "advanced_align_mac":       False,
        "advanced_control":         True,
        "advanced_sync_guiding":    True,
        "advanced_scc_enabled":     True,
        "advanced_scc_choice":      0,
        "advanced_pec":             True,
        "log_quest_model":          False,
        "log_pec":                  False,
        "pec_forgetting_factor":    0.98,
        "pec_min_observations":     3,
        "pec_max_step_arcmin":      0.5,
        "pec_max_covariance":       0.01,
        "pec_max_rmse_arcmin":      6.0,
        "pec_max_resid_arcmin":     10.0,
        "pec_forget_horiz":         35*60,
        "pec_interv_alpha":         0.3,
        "pec_min_r2":               0.5,
        "m3_tilt_dm1":              0, 
        "m3_tilt_dm2":              0, 
        "m3_tilt_dm3":              0, 
        "m2_tilt_dm2_amp":          0,
        "m2_tilt_dm2_zero":         0, 
        "m2_roll_coupling":         0, 
        "m2_roll_zero":             0, 
        "m1_offset":                0, 
        "m2_offset":                0, 
        "m3_offset":                0, 
        
    }
    config_obj = SimpleNamespace(**defaults)

    with patch('control.Config', config_obj):
        yield config_obj

class PID_Controller:
    def measure(self, alpha, theta):
        return 0.0
    def reset_sp(self, alpha):
        return 0.0

class Polaris:
    def __init__(self):
        self.update(180, 45, 0)
        self._sitelatitude = -33.65528161613541
        self._sitelongitude = DEFAULT_LON 
        self.azimuth = 180
        self.rightascension = 0
        self.declination= -75
        self._pid = PID_Controller()
        self._motorQ_state = Quaternion([1,0,0,0])

    def update_ascom_from_new_alignQ_B2T(self, q1s):
        a_t1, a_t2, a_t3, a_az, a_alt, a_roll = quaternion_to_angles(q1s)
        alpha_state = np.array([a_az, a_alt, a_roll], dtype=float)
        theta_state = np.array([a_t1, a_t2, a_t3], dtype=float)
        return alpha_state, theta_state

    def update(self, az, alt, roll=0):
        self._p_azimuth = az
        self._p_altitude = alt
        self._p_roll = roll
        self._q1 = azaltroll_to_q(az, alt, roll)
        self._motorQ_state = self._q1
        t1,t2,t3,_,_,_ = quaternion_to_angles(self._q1)
        self._theta_raw = [t1, t2, t3]
        self._roll = roll

    def update_ascom_radec(self, ra, dec):
        """ Updates the RA (hr) and DEC (deg) of the Polaris object """
        self.rightascension = ra
        self.declination = dec

def test_dummy():
    assert(1==1)

def test_sync_history(mock_config):
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

def test_no_sync_adj(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    az,alt,roll,_,_,_ = quaternion_to_angles(sm.alignQ_B2T * p._q1)
    assert az == pytest.approx(180.0, abs=1e-6)
    assert alt == pytest.approx(45.0, abs=1e-6)
    assert roll == pytest.approx(0.0, abs=1e-6)

def test_single_syncs_adj(mock_config):
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

def test_azshift10_sync_adj(mock_config):
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

def test_leveling_sync_adj(mock_config):
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

def test_largetilt_sync_adj(mock_config):
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


def test_az170alt15shift_sync_adj(mock_config):
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

def test_zeroroll_sync_adj(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 45, 10)
    sm.sync_roll(10)
    a_roll = sm.roll_polaris2ascom(20)
    assert f'{a_roll:.6f}' == "20.000000"

def test_15roll_sync_adj(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 45, 10)
    sm.sync_roll(25)
    a_roll = sm.roll_polaris2ascom(90)
    assert f'{a_roll:.6f}' == "105.000000"

def test_neg60roll_sync_adj(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 30, 80)
    sm.sync_roll(30)
    a_roll = sm.roll_polaris2ascom(180)
    assert f'{a_roll:.6f}' == "130.000000"
    p_roll = sm.roll_ascom2polaris(200)
    assert f'{p_roll:.6f}' == "250.000000"

def test_tworoll_sync_adj(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    p.update(180, 30, 0)
    sm.sync_roll(30)
    p.update(180, 30, 80)
    sm.sync_roll(130)
    a_roll = sm.roll_polaris2ascom(180)
    assert f'{a_roll:.6f}' == "220.000000"  # 180 + (30+50)/2

def test_aboveSouth_roll2pa(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 45, 10)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "10.000000, -0.000000"  

def test_belowSouth_roll2pa(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 30, 10)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "190.000000, -180.000000"  

def test_belowSouth_pa2roll(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(180, 30, 200)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "20.000000, -180.000000"  

def test_aboveNorth_roll2pa(mock_config):
    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger,p)
    position_ang, parallactic_ang = sm.roll2pa(0, 0, 30)
    assert f'{position_ang:.6f}, {parallactic_ang:.6f}' == "210.000000, -180.000000"  

def test_horizEast_roll2pa(mock_config):
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


def test_sgc_seed_from_quest_residual(mock_config):
    """
    Test that after a QUEST sync with scc_choice=2, the SGC seed
    shifts the FK output to match the observed position.
    """
    mock_config.advanced_scc_enabled = True
    mock_config.advanced_scc_choice = 2
    mock_config.advanced_sync_guiding = True
    mock_config.advanced_align_mac = False

    p = Polaris()
    logger = logging.getLogger()
    sm = SyncManager(logger, p)

    # Three sync points to build a reasonable QUEST model
    p.update(180, 45)
    sm.sync_az_alt(0, 0, 170, 45)

    p.update(90, 45)
    sm.sync_az_alt(0, 0, 80, 45)

    p.update(270, 45)
    sm.sync_az_alt(0, 0, 260, 45)

    # Now simulate a slew to a new position and plate solve
    # Mount reports az=190, alt=45 but plate solve sees az=180, alt=46; ie RA_resid 0, Dec_resid close to -1 degree
    p.update(190, 45)

    # Seed equatorial axes so SGC can build correction quaternion
    cameraQ, _ = sm.baseQ_to_topoQ(p._motorQ_state)
    sm.equatorial_axes_B = calc_equatorial_axes_B(cameraQ, sm.alignQ_B2T_inv, p._sitelatitude)

    # Perform a QUEST sync at the new position with a slight +ve Dec error TO BE PICKED UP BY SGA
    sm.sync_az_alt(0, 0, 180.0, 46.0)
    cameraQ, _ = sm.baseQ_to_topoQ(p._motorQ_state)
    az, alt, _ = q_to_azaltroll(cameraQ)

    # The FK output should now be close to the observed plate solve position, not exactly because QUEST has been refreshed and may absorb some of the residual.
    assert abs(az - 180) < 0.02,  f"Az {az:.3f} not close to observed 180"
    assert abs(alt - 46) < 0.02, f"Alt {alt:.3f} not close to observed 46"

    # And SGC accumulator should be non-zero
    assert sm.q_syncguide_B != Quaternion([1,0,0,0]), "q_syncguide_B should not be identity"

    # Perform a QUEST sync at the same position with a slight -ve Dec error (mock of Polaris causes every sync to be a QUEST sync)
    sm.sync_az_alt(0, 0, 180.0, 44.0)
    cameraQ, _ = sm.baseQ_to_topoQ(p._motorQ_state)
    az, alt, _ = q_to_azaltroll(cameraQ)

    assert abs(az - 180) < 0.02,  f"Az {az:.3f} not close to observed 180"
    assert abs(alt - 44) < 0.02, f"Alt {alt:.3f} not close to observed 44"

    # Perform a GUIDE sync in the North with a zero residual 

    a_ra, a_dec = 90, -75
    a_az, a_alt = radec_to_altaz(a_ra, a_dec, DEFAULT_LAT, DEFAULT_LON, format_timestamp())
    topoQ = azaltroll_to_q(a_az,a_alt,0)
    baseQ = sm.topoQ_to_baseQ(topoQ)
    p_az, p_alt, p_roll = q_to_azaltroll(baseQ)
    # Receive 518 msg and predict
    p.update(p_az, p_alt)
    cameraQ, _ = sm.baseQ_to_topoQ(p._motorQ_state)
    fk_az, fk_alt, _ = q_to_azaltroll(cameraQ)
    fk_ra, fk_dec = azalt_to_radec(fk_az, fk_alt, DEFAULT_LAT, DEFAULT_LON, format_timestamp())
    p.update_ascom_radec(fk_ra/15, fk_dec)
    # Plate solve observed
    observed_ra, observed_dec = a_ra, a_dec
    result = sm.process_guide_sync(observed_ra/15, observed_dec, a_az, a_alt)
    assert result == True, "Guide sync should be accepted"
    cameraQ, _ = sm.baseQ_to_topoQ(p._motorQ_state)
    az, alt, _ = q_to_azaltroll(cameraQ)

    assert abs(az - a_az) < 0.8,  f"Az {az:.3f} not close to observed {a_az}"
    assert abs(alt - a_alt) < 0.8, f"Alt {alt:.3f} not close to observed {a_alt}"

