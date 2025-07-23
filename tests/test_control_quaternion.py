import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
import numpy as np
from control import is_angle_same, angles_to_quaternion, motors_to_quaternion, quaternion_to_angles


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
    (9, 10, 0, 80),      # High roll at flat alt

    # 🧨 Extreme altitude cases
    (10, 180, -89, 0),   # Near nadir
#    (11, 180, 90, 0),    # Zenith - causes the az to become undefined, rotating about a vertical pole with no clear left or right

    # 🔄 Azimuth wraparound cases
    (12, 359.999, 30, 10), # Just below 360°
    (13, 0.001, 30, -10),  # Just above 0°

    # 🔁 Roll near ±180°
    (14, 90, 45, 180),     # Full twist
    (15, 90, 45, -180),    # Opposite full twist

    # 🧮 Near-singularity setup
#    (16, 270, 89.999, 90), # Near zenith with roll - - causes the az to become undefined, rotating about a vertical pole with no clear left or right

    # 🔁 Flat boresight with flipped roll logic
    (18, 180, 0, 179.9),   # Roll just under 180°

    # 🔁 Roll wraparound near ±180°
    (19, 90, 45, 180.001),
    (20, 90, 45, -180.001),

    # 🧭 Azimuth discontinuity at 180°
    (21, 179.999, 45, 0),
    (22, 180.001, 45, 0),

    # 🧊 Near-zero roll with steep altitude
    (23, 90, 89.999, 0.001),
    (24, 270, -89.999, -0.001),

    # 🧮 Symmetry cases
    (27, 90, 45, 45),
    (28, 270, 45, -45),
]

@pytest.mark.parametrize("n, az, alt, roll", test_cases)
def test_angles_to_quaternion_to_angles_roundtrip(n, az, alt, roll):
    threshold = 1e-2
    q1 = angles_to_quaternion(az, alt, roll)
    t1, t2, t3, a1, a2, a3 = quaternion_to_angles(q1)

    assert abs(a1 - az) < threshold, f"Altitude mismatch: input {alt:.4f}, computed {a1:.4f} (case {n})"
    assert is_angle_same(a2, alt, threshold), f"Azimuth mismatch: input {az:.4f}, computed {a2:.4f} (case {n})"
    assert is_angle_same(a3, roll, threshold), f"Roll mismatch: input {roll:.4f}, computed {a3:.4f} (case {n})"

@pytest.mark.parametrize("n, az, alt, roll", test_cases)
def test_motors_to_quaternion_to_motors_roundtrip(n, az, alt, roll):
    threshold = 1e-2
    q0 = angles_to_quaternion(az, alt, roll)
    t1, t2, t3, _, _, _ = quaternion_to_angles(q0)
    q1 = motors_to_quaternion(t1, t2, t3)
    u1, u2, u3, _, _, _ = quaternion_to_angles(q1)

    assert abs(u1 - t1) < threshold, f"Theta1 mismatch: {t1:.4f} vs {u1:.4f} (case {n})"
    assert is_angle_same(u2, t2, threshold), f"Theta2 mismatch: {t2:.4f} vs {u2:.4f} (case {n})"
    assert is_angle_same(u3, t3, threshold), f"Theta3 mismatch: {t3:.4f} vs {u3:.4f} (case {n})"

