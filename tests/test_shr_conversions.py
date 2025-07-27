import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
import math

from shr import (
    deg2dms, hr2hms, dms2dec, rad2hr, hr2rad, rad2deg, deg2rad, hms2hr, hms2rad, dms2rad, rad2hms
)

# DEG2DMS Tests
def test_deg2dms():
    assert deg2dms(12.3456) == "+12d20'44.16\""
    assert deg2dms(-0.75) == "-0d45'00.00\""
    assert deg2dms(0) == "+0d00'00.00\""
    assert deg2dms(180) == "+180d00'00.00\""
    assert deg2dms(-180.75) == "-180d45'00.00\""

# HR2HMS Tests
def test_hr2hms():
    assert hr2hms(13.5) == "13h30m00.00s"
    assert hr2hms(1.2556) == "01h15m20.16s"
    assert hr2hms(0.0) == "00h00m00.00s"
    assert hr2hms(23.9997) == "23h59m58.92s"
    assert hr2hms(-1.234) == "-01h14m02.40s"


# DMS2DEC Tests
def test_dms2dec():
    assert pytest.approx(dms2dec("12d30'30.00"), 0.00001) == 12.5083
    assert pytest.approx(dms2dec("00d00'00.00"), 0.00001) == 0.0
    assert pytest.approx(dms2dec("-45d15'15.00"), 0.00001) == -45.254166

# RAD2HR Tests
def test_rad2hr():
    assert pytest.approx(rad2hr(math.pi)) == 12
    assert pytest.approx(rad2hr(math.pi/2)) == 6
    assert pytest.approx(rad2hr(0)) == 0
    assert pytest.approx(rad2hr(2*math.pi)) == 24

# HR2RAD Tests
def test_hr2rad():
    assert pytest.approx(hr2rad(12)) == math.pi
    assert pytest.approx(hr2rad(6)) == math.pi / 2
    assert pytest.approx(hr2rad(0)) == 0
    assert pytest.approx(hr2rad(24)) == 2 * math.pi

# RAD2DEG Tests
def test_rad2deg():
    assert pytest.approx(rad2deg(math.pi)) == 180
    assert pytest.approx(rad2deg(math.pi/2)) == 90
    assert pytest.approx(rad2deg(0)) == 0
    assert pytest.approx(rad2deg(2*math.pi)) == 360

# DEG2RAD Tests
def test_deg2rad():
    assert pytest.approx(deg2rad(180)) == math.pi
    assert pytest.approx(deg2rad(90)) == math.pi / 2
    assert pytest.approx(deg2rad(0)) == 0
    assert pytest.approx(deg2rad(360)) == 2 * math.pi

# HMS2HR Tests
def test_hms2hr():
    assert pytest.approx(hms2hr("02h30m00s")) == 2.5
    assert pytest.approx(hms2hr("01h45m30s")) == 1.758333333
    assert pytest.approx(hms2hr("00h00m00s")) == 0.0
    assert pytest.approx(hms2hr("23h59m59.99s"), 1e-4) == 23.999997

# Round-trip accuracy checks (optional)
def test_roundtrip_hr():
    hr_value = 5.25
    assert pytest.approx(hms2hr(hr2hms(hr_value))) == hr_value

def test_roundtrip_deg():
    deg_value = -73.789
    dms_str = deg2dms(deg_value)
    reconstructed = dms2dec(dms_str)
    assert pytest.approx(reconstructed, 0.001) == deg_value

def test_hms2rad_basic():
    assert pytest.approx(hms2rad("12h00m00s")) == math.pi
    assert pytest.approx(hms2rad("06h00m00s")) == math.pi / 2
    assert pytest.approx(hms2rad("00h00m00s")) == 0.0
    assert pytest.approx(hms2rad("24h00m00s")) == 2 * math.pi

def test_hms2rad_fractional():
    assert pytest.approx(hms2rad("01h30m00s")) == math.pi / 8
    assert pytest.approx(hms2rad("02h24m00s"),0.000001) == math.pi / 5

def test_hms2rad_high_precision():
    result = hms2rad("23h59m59.99s")
    expected = hr2rad(23.9999972222)
    assert pytest.approx(result, abs=1e-8) == expected

def test_hms2rad_invalid_format():
    with pytest.raises(ValueError):
        hms2rad("invalid string")

def test_dms2rad_zero():
    assert pytest.approx(dms2rad("0d0'0\"")) == 0.0

def test_dms2rad_positive():
    assert pytest.approx(dms2rad("180d00'00.00\"")) == math.pi
    assert pytest.approx(dms2rad("90d00'00\"")) == math.pi / 2
    assert pytest.approx(dms2rad("45d30'00\"")) == deg2rad(45.5)

def test_dms2rad_negative():
    assert pytest.approx(dms2rad("-180d00'00\"")) == -math.pi
    assert pytest.approx(dms2rad("-90d30'00\"")) == deg2rad(-90.5)

def test_dms2rad_fractional():
    assert pytest.approx(dms2rad("+12d34'56.78\"")) == deg2rad(12 + 34/60 + 56.78/3600)

def test_dms2rad_incomplete_input():
    assert pytest.approx(dms2rad("123d")) == deg2rad(123)
    assert pytest.approx(dms2rad("-123d45'")) == deg2rad(-123 - 45/60)

def test_dms2rad_invalid():
    with pytest.raises(ValueError):
        dms2rad("not_a_dms")

def test_rad2hms_basic():
    assert rad2hms(0) == "00h00m00.00s"
    assert rad2hms(math.pi / 2) == "06h00m00.00s"
    assert rad2hms(math.pi) == "12h00m00.00s"
    assert rad2hms(2 * math.pi) == "24h00m00.00s"

def test_rad2hms_fractional():
    assert rad2hms(math.pi / 4) == "03h00m00.00s"
    assert rad2hms(1.234) == "04h42m48.72s"
    assert rad2hms(0.0001) == "00h00m01.38s"

def test_rad2hms_wraparound():
    # 25 hours worth of radians should wrap to 25h00m00.00s
    rad_25h = 25 * math.pi / 12
    assert rad2hms(rad_25h) == "25h00m00.00s"

def test_rad2hms_precision():
    assert rad2hms(math.pi / 6) == "02h00m00.00s"
    assert rad2hms(math.pi / 3) == "04h00m00.00s"

def test_rad2hms_negative():
    assert rad2hms(-math.pi / 2) == "-06h00m00.00s"
