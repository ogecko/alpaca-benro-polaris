import sys
import os
from pyquaternion import Quaternion
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
import numpy as np
from control import angles_to_quaternion, motors_to_quaternion, quaternion_to_angles


test_cases = [
    # 🔁 Slight altitude around Az=160°
    (1, 160, 5, -6),     # Low alt, negative roll
    (2, 160, 5, 12),     # Low alt, positive roll

    # 🧭 Steeper altitude around Az=240°
    (3, 240, 60, 30),    # Mid-alt, positive roll
    (4, 240, 60, -35),   # Mid-alt, negative roll
    (5, 240, 60, 0),     # Mid-alt, zero roll
    (6, 0, 60, 0),       # Mid-alt, azimuth wraparound

    # 🧊 Zero altitude cases
    (7, 359, 0, 0),      # Azimuth near 360°
    (8, 0, 0, 0),        # Azimuth at 0°
    # (9, 10, 0, 80),      # High roll at flat alt - INVALID TEST: ambiguous theta1 vs theta3

    # 🧨 Extreme altitude cases
    (10, 180, -89, 0),   # Near nadir
    # (11, 180, 90, 0),    # Zenith - INVALID TEST: unreachable Alt, ambiguous Az

    # 🔄 Azimuth wraparound cases
    (12, 359.999, 30, 10), # Just below 360°
    (13, 0.001, 30, -10),  # Just above 0°

    # 🔁 Roll near ±180°
    # (14, 90, 45, 180),     # Full twist - INVALID TEST: due to full theta3 rotation
    # (15, 90, 45, -180),    # Opposite full twist - INVALID TEST: due to full theta3 rotation

    # 🧮 Near-singularity setup
    # (16, 270, 89.999, 90), # Near zenith with roll - INVALID TEST: unreachable Alt

    # 🔁 Flat boresight with flipped roll logic
    # (18, 180, 0, 179.9),   # Roll just under 180° - INVALID TEST: ambiguous theta1 and theta3

    # 🔁 Roll wraparound near ±180°
    #(19, 90, 45, 180.001),  # INVALID TEST - unreachable theta3 or Roll
    #(20, 90, 45, -180.001), # INVALID TEST - unreachable theta3 or Roll

    # 🧭 Azimuth discontinuity at 180°
    (21, 179.999, 45, 0),
    (22, 180.001, 45, 0),

    # 🧊 Near-zero roll with steep altitude
    (23, 90, 89.999, 0.001),
    # (24, 270, -89.999, -0.001), # INVALID TEST - unreachable Alt

    # 🧮 Symmetry cases
    (27, 90, 45, 45),
    (28, 270, 45, -45),
]

def approx_quaternion_to_angles(w,x,y,z):
    q1=Quaternion(w,x,y,z)
    results = quaternion_to_angles(q1)
    rounded = [float(round(x,1)) for x in results]
    return str(rounded)

def approx(array_input, precision=5):
    return [ 0.0 if float(round(x, precision))==-0.0 else float(round(x, precision)) for x in array_input ]

def test_motor_to_quaternion():
    assert str(motors_to_quaternion(2, 45, -5)) == str(Quaternion(+0.247, +0.653, -0.652, +0.295))
    assert str(motors_to_quaternion(2, 45, +5)) == str(Quaternion(-0.303, -0.629, +0.676, -0.237))
    assert str(motors_to_quaternion(90, 45, -5)) == str(Quaternion(+0.382, +0.017, -0.923, +0.040))
    assert str(motors_to_quaternion(90, 45, +5)) == str(Quaternion(-0.382, +0.017, +0.923, +0.040))
    assert str(motors_to_quaternion(177, 60, -5)) == str(Quaternion(+0.217, -0.656, -0.708, -0.147))
    assert str(motors_to_quaternion(177, 60, +5)) == str(Quaternion(-0.159, +0.672, +0.692, +0.209))
    assert str(motors_to_quaternion(177, +2, +5)) == str(Quaternion(-0.482, +0.517, +0.500, +0.500))
    assert str(motors_to_quaternion(177, -2, +5)) == str(Quaternion(-0.500, +0.500, +0.482, +0.517))
    assert str(motors_to_quaternion(260, +2, +5)) == str(Quaternion(-0.029, +0.719, +0.032, +0.694))
    assert str(motors_to_quaternion(260, +2, -5)) == str(Quaternion(+0.092, -0.713, -0.093, -0.689))
    assert str(motors_to_quaternion(260, -2, -5)) == str(Quaternion(+0.093, -0.689, -0.092, -0.713))
    assert str(motors_to_quaternion(280, 30, +5)) == str(Quaternion(+0.081, +0.860, -0.097, +0.494))
    assert str(motors_to_quaternion(280, 30, -5)) == str(Quaternion(-0.006, -0.864, +0.054, -0.501))
    assert str(motors_to_quaternion(297, 30, -5)) == str(Quaternion(-0.080, -0.846, +0.181, -0.495))
    assert str(motors_to_quaternion(330, 30, -5)) == str(Quaternion(-0.217, -0.760, +0.414, -0.451))
    assert str(motors_to_quaternion(340, 30, -5)) == str(Quaternion(-0.256, -0.721, +0.478, -0.431))
    #assert str(motors_to_quaternion(340.0125, 30, -5)) == str(Quaternion(+0.256, +0.721, -0.478, +0.431)) # Wrong sign
    #assert str(motors_to_quaternion(340, 30, -5)) == str(Quaternion(+0.256, +0.721, -0.478, +0.431)) # Wrong Sign
    #assert str(motors_to_quaternion(350, 30, -5)) == str(Quaternion(+0.292, +0.677, -0.539, +0.407)) # wrong Sign
    #assert str(motors_to_quaternion(358, 45, -5)) == str(Quaternion(+0.237, +0.675, -0.629, +0.303))  # wrong sign
    #assert str(motors_to_quaternion(358, 45, +5)) == str(Quaternion(-0.295, -0.652, +0.653, -0.247))  # wrong sign
    

def test_angles_to_quaternion():
    assert str(angles_to_quaternion(+97.0875,+44.7835,-4.9968)) == str(Quaternion(-0.382, +0.017, +0.923, +0.040))  # 90, 45, -5
    assert str(angles_to_quaternion(+82.9540,+44.7845,+4.9851)) == str(Quaternion(+0.382, +0.017, -0.923, +0.040))  # 90, 45, +5
    # assert str(angles_to_quaternion(+354.9565,+44.7846,+4.9850)) == str(Quaternion(+0.247, +0.653, -0.652, +0.295)) # 2, 45, -5 ** wrong sign
    assert str(angles_to_quaternion(+9.0678,+44.7843,-4.9894)) == str(Quaternion(-0.303, -0.629, +0.676, -0.237))   # 2, 45, +5
    # assert str(angles_to_quaternion(+350.9593,+44.7846,+4.9830)) == str(Quaternion(+0.237, +0.675, -0.629, +0.303))  # 358, 45, -5 **wrong sign
    assert str(angles_to_quaternion(+5.0797,+44.7842,-4.9892)) == str(Quaternion(-0.295, -0.652, +0.653, -0.247))   # 358, 45, +5
    assert str(angles_to_quaternion(+167.0704,+59.6340,+8.5897)) == str(Quaternion(+0.217, -0.656, -0.708, -0.147)) # 177, 60, -5
    assert str(angles_to_quaternion(+186.9383,+59.6312,-8.5961)) == str(Quaternion(-0.158, +0.672, +0.692, +0.209)) # 177, 60, +5
    assert str(angles_to_quaternion(+182.0085,+1.9935,-0.1747)) == str(Quaternion(-0.482, +0.517, +0.500, +0.500))  # 177, +2, +5
    assert str(angles_to_quaternion(+182.0086,-1.9875,-0.1741)) == str(Quaternion(-0.499, +0.499, +0.483, +0.518))  # 177, -2, +5
    assert str(angles_to_quaternion(+265.0099,+1.9935,-0.1747)) == str(Quaternion(-0.029, +0.719, +0.032, +0.694))  # 260, +2, +5
    assert str(angles_to_quaternion(+254.9864,+1.9933,+0.1748)) == str(Quaternion(+0.092, -0.713, -0.093, -0.689))  # 260, +2, -5
    assert str(angles_to_quaternion(+254.9868,-1.9940,+0.174)) == str(Quaternion(+0.095, -0.689, -0.090, -0.713))   # 260, -2, -5

def test_quaternion_to_angles():
    assert approx_quaternion_to_angles(+0.247, +0.653, -0.652, +0.295) == str([2.0, 45.0, -5.0, 354.9, 44.7, 5.0])
    assert approx_quaternion_to_angles(-0.303, -0.629, +0.676, -0.237) == str([2.1, 45.0, 4.9, 9.0, 44.8, -4.9])
    assert approx_quaternion_to_angles(-0.382, +0.017, +0.923, +0.040) == str([90.1, 45.0, 4.9, 97.0, 44.8, -4.9])
    assert approx_quaternion_to_angles(+0.382, +0.017, -0.923, +0.040) == str([89.9, 45.0, -4.9, 83.0, 44.8, +4.9])
    assert approx_quaternion_to_angles(+0.217, -0.656, -0.708, -0.147) == str([177.0, 60.0, -5.1, 166.9, 59.6, 8.7])
    assert approx_quaternion_to_angles(-0.159, +0.672, +0.692, +0.209) == str([177.0, 59.9, 5.0, 186.9, 59.5, -8.6])
    assert approx_quaternion_to_angles(-0.482, +0.517, +0.500, +0.500) == str([179.4, 2.0, 2.6, 182.0, 2.0, -0.1])
    assert approx_quaternion_to_angles(-0.500, +0.500, +0.482, +0.517) == str([179.4, -2.0, 2.6, 182.0, -2.0, -0.1]) 
    assert approx_quaternion_to_angles(-0.029, +0.719, +0.032, +0.694) == str([260.7, 2.0, 4.4, 265.1, 2.0, -0.2])
    assert approx_quaternion_to_angles(+0.092, -0.713, -0.093, -0.689) == str([260.1, 1.9, -5.1, 255.0, 1.9, 0.2])
    assert approx_quaternion_to_angles(+0.093, -0.689, -0.092, -0.713) == str([260.1, -1.9, -5.1, 255.0, -1.9, 0.2]) 
    assert approx_quaternion_to_angles(+0.081, +0.860, -0.097, +0.494) == str([280.0, 30.0, 5.0, 285.7, 29.9, -2.9])
    assert approx_quaternion_to_angles(-0.006, -0.864, +0.054, -0.501) == str([280.0, 30.0, -5.0, 274.3, 29.9, 2.9])
    assert approx_quaternion_to_angles(-0.080, -0.846, +0.181, -0.495) == str([297.1, 29.9, -5.0, 291.3, 29.8, 2.9])
    assert approx_quaternion_to_angles(-0.217, -0.760, +0.414, -0.451) == str([330.0, 30.0, -5.0, 324.3, 29.9, 2.9])
    assert approx_quaternion_to_angles(-0.256, -0.721, +0.478, -0.431) == str([339.9, 29.9, -4.9, 334.3, 29.8, 2.8])
    assert approx_quaternion_to_angles(+0.256, +0.721, -0.478, +0.431) == str([339.9, 29.9, -4.9, 334.3, 29.8, 2.8])
    assert approx_quaternion_to_angles(+0.292, +0.677, -0.539, +0.407) == str([349.9, 30.0, -5.0, 344.2, 29.9, 2.9])
    assert approx_quaternion_to_angles(+0.237, +0.675, -0.629, +0.303) == str([358.0, 44.9, -5.0, 351.0, 44.7, 4.9])
    assert approx_quaternion_to_angles(-0.295, -0.652, +0.653, -0.247) == str([358.0, 45.0, 5.0, 5.1, 44.7, -5.0])


@pytest.mark.parametrize("n, az, alt, roll", test_cases)
def test_angles_to_quaternion_to_angles_roundtrip(n, az, alt, roll):
    az1,alt1,roll1 = approx( [az,alt,roll] )
    q1 = angles_to_quaternion(az, alt, roll)
    angles = quaternion_to_angles(q1)
    _,_,_,az2,alt2,roll2 = approx( angles )
    assert str([f'C{n}', az2,alt2,roll2]) == str([f'C{n}', az1,alt1,roll1])

@pytest.mark.parametrize("n, az, alt, roll", test_cases)
def test_motors_to_quaternion_to_motors_roundtrip(n, az, alt, roll):
    t1,t2,t3 = approx( [az,alt,roll] )
    q1 = motors_to_quaternion(t1, t2, t3)
    angles = quaternion_to_angles(q1)
    u1,u2,u3,_,_,_ = approx( angles )
    assert str([f'D{n}', u1,u2,u3]) == str([f'D{n}', t1,t2,t3])

def test_all_positions():
    n=200
    # Zero Alt tests
    alt, roll = 0, 0 # extend for various rolls (maintain roll?)
    for az in range(0,360,30):
        n += 1
        test_angles_to_quaternion_to_angles_roundtrip(n,az,alt,roll)
    
    # Positive Alt tests
    for alt in range(1,90,10):
        for az in range(0,360,30):
            for roll in range(-175,180,30):
                n += 1
                test_angles_to_quaternion_to_angles_roundtrip(n,az,alt,roll)
                #test_motors_to_quaternion_to_motors_roundtrip(n,az,alt,roll)