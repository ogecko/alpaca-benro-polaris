import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

# import pytest
import ephem
import math
import numpy as np
import datetime
from shr import deg2rad, rad2hr, rad2deg, rad2hms, hr2rad, deg2dms, hr2hms, hms2rad, dms2rad
from control import angular_difference, is_angle_same, compute_body_trajectory, compute_desired_motor_angles

def test_dummy():
    assert(1==1)



def test_target_ref():
    observer = ephem.Observer()
    observer.lat = '-33.859887'
    observer.lon = '151.202177'
    observer.elevation = 39
    observer.date = ephem.now()
    observer.epoch = ephem.J2000
    
    # 47 Tuc (J2000)
    ra = '0h24m07.23s'
    dec = '-72d04m35.0s'

    # Obtain the target's current az alt position
    body = ephem.FixedBody()
    body._ra = hms2rad(ra)
    body._dec = dms2rad(dec)
    body._epoch = ephem.J2000  # Use J2000 epoch for RA/Dec
    body.compute(observer)
    az = rad2deg(body.az)
    alt = rad2deg(body.alt) 

    N = 60
    Δt = 1
 
    azaltroll_ref = compute_body_trajectory(N, Δt, observer, body, is_equatorial_roll=True)
    theta_ref = compute_desired_motor_angles(azaltroll_ref)
      
    assert(1==1)


        # target = ephem.FixedBody()
        # target._ra = hr2rad(ra)
        # target._dec = deg2rad(dec)
        # target._epoch = epoch
        # now = datetime.datetime.now(tz=datetime.timezone.utc)
        # self._observer.date = now + datetime.timedelta(seconds=inthefuture)
        # target.compute(self._observer)
        # alt = rad2deg(target.alt)
        # az = rad2deg(target.az)
        # return alt,az
