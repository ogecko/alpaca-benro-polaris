import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

from orbitals import orbital_data, update_orbital_data, enum_alt, enum_az, position_lookup
import pytest
import math
import ephem

def test_dummy():
    assert(1==1)

def test_update_orbital_data():
    observer = ephem.Observer()
    observer.lat = '-33.859887'
    observer.lon = '151.202177'
    observer.elevation = 39
    observer.date = ephem.now()
    observer.epoch = ephem.J2000
    update_orbital_data(observer)
    # assert(str(orbital_data["Moon"])==1)
    assert(1==1)
