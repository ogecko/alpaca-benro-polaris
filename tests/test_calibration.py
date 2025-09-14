import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

from control import CalibrationManager
import pytest
import math

def test_dummy():
    assert(1==1)

def test_baseline():
    cm = CalibrationManager()
    assert(cm.baseline_data[0]['RAW'][1]==0.5)

def test_calibrationFromBaseline():
    cm = CalibrationManager()
    cm.createTestDataFromBaseline()
    assert(cm.test_data['M0-SLOW-5.0']=={
        'name': 'M0-SLOW-5.0', 'axis': 0, 'raw': 5.0, 'ascom': 5.0, 'dps': 0.2078883, 
        'test_result': '', 'test_change': '', 'test_stdev': '', 'test_status': 'UNTESTED' 
    })

def test_addTestResult():
    cm = CalibrationManager()
    cm.addTestResult(0, 3.0, 0.0476541, 0.0002345678, 'PENDING')
    assert(cm.test_data['M0-SLOW-3.0']=={
        'name': 'M0-SLOW-3.0', 'axis': 0, 'raw': 3.0, 'ascom': 3.0, 'dps':  0.0473643, 
        'test_result': '0.0476541', 'test_change': '0.61%', 'test_stdev': '0.0002346', 'test_status': 'PENDING' 
    })
    cm.addTestResult(1, 2500, 7.012345678, 0.0002345678, 'PENDING')
    assert(cm.test_data['M1-FAST-2500']=={
        'name': 'M1-FAST-2500', 'axis': 1, 'raw': 2500, 'ascom': 8.903224431248036, 'dps':  7.1661097, 
        'test_result': '7.0123457', 'test_change': '-2.15%', 'test_stdev': '0.0002346', 'test_status': 'PENDING' 
    })

def test_ApproveRejectTest():
    cm = CalibrationManager()
    cm.addTestResult(0, 3.0, 0.0476541, 0.0002345678, 'PENDING')
    cm.addTestResult(1, 2500, 7.012345678, 0.0002345678, 'BAD READ')
    cm.addTestResult(1, 2000, 7.012345678, 0.0002345678, 'PENDING')
    cm.addTestResult(1, 1000, 7.012345678, 0.0002345678, 'PENDING')
    cm.approveTests(['M0-SLOW-3.0','M1-FAST-2500','M1-FAST-2000', 'DUMMY'])
    assert(cm.test_data['M0-SLOW-3.0']['test_status']=='APPROVED')
    assert(cm.test_data['M1-FAST-2500']['test_status']=='BAD READ')
    assert(cm.test_data['M1-FAST-2000']['test_status']=='APPROVED')
    assert(cm.test_data['M1-FAST-1000']['test_status']=='PENDING')
    cm.rejectTests(['M0-SLOW-3.0'])
    assert(cm.test_data['M0-SLOW-3.0']['test_status']=='REJECTED')
    assert(cm.test_data['M1-FAST-1000']['test_status']=='PENDING')
    cm.rejectTests([])
    assert(cm.test_data['M0-SLOW-3.0']['test_status']=='REJECTED')
    assert(cm.test_data['M1-FAST-2500']['test_status']=='BAD READ')
    assert(cm.test_data['M1-FAST-2000']['test_status']=='REJECTED')
    assert(cm.test_data['M1-FAST-2000']['test_status']=='REJECTED')
