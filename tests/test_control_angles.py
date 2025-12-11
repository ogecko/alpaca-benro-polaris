import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

# import pytest
from control import angular_difference, is_angle_same, wrap_to_90, is_angle_between
from shr import deg2rad, rad2deg
import pytest

import math

def test_dummy():
    assert(1==1)

def test_is_angle_same():
    assert(is_angle_same(361, 1) == True) 
    assert(is_angle_same(-180, +180) == True) 
    assert(is_angle_same(-179, +179) == False) 
    assert(is_angle_same(25, 25.00001) == True) 
    assert(is_angle_same(25, 25.0001) == False) 

def test_angular_difference():
    assert(angular_difference(359, 1) == +2) 
    assert(angular_difference(1, 359) == -2)  
    assert(angular_difference(10, 180) == +170)
    assert(angular_difference(5, 175) == +170)
    assert(angular_difference(350, 180) == -170)  
    assert(angular_difference(280, 90) == +170)  
    assert(angular_difference(0, 180) == -180) 
    assert(angular_difference(180, 0) == -180)
    assert(angular_difference(359.5, 0.25) == 0.75)
  

def test_wrap_to_90_center_and_extremes():
    assert wrap_to_90(0) == 0.0
    assert wrap_to_90(90) == -90.0
    assert wrap_to_90(-90) == -90.0
    assert wrap_to_90(180) == 0.0
    assert wrap_to_90(-180) == 0.0

def test_wrap_to_90_positive_wraps():
    assert wrap_to_90(95) == -85.0
    assert wrap_to_90(135) == -45.0
    assert pytest.approx(wrap_to_90(179.99), abs=1e-6) == -0.01
    assert wrap_to_90(270) == -90.0
    assert wrap_to_90(360) == 0.0

def test_wrap_to_90_negative_wraps():
    assert wrap_to_90(-95) == 85.0
    assert wrap_to_90(-135) == 45.0
    assert pytest.approx(wrap_to_90(-179.99), abs=1e-6) == 0.01
    assert wrap_to_90(-270) == -90.0
    assert wrap_to_90(-360) == 0.0

def test_wrap_to_90_symmetry_and_continuity():
    assert wrap_to_90(45) == 45.0
    assert wrap_to_90(-45) == -45.0
    assert wrap_to_90(225) == 45.0
    assert wrap_to_90(-225) == -45.0
    assert wrap_to_90(315) == -45.0
    assert wrap_to_90(-315) == 45.0


def test_is_angle_between():
    assert(is_angle_between(90,80,100)==True)
    assert(is_angle_between(-84,-100,+100)==True)
    None