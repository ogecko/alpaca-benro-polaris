import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

# import pytest
from control import angular_difference, is_angle_same 

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
  


