"""
Tests for the PHD2 guide-log loader and time-window helper in utility/analyse_helpers.py,
used by analyse_pec_delta.ipynb to compare PEC with what the guider actually did.

Sign convention matches the driver's pulse residuals (control.process_pulse_guide_axis):
East and North pulses are positive, West and South negative.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import pandas as pd
import pytest

from analyse_helpers import load_phd2_guidelog, window_df

HEADER = "Frame,Time,mount,dx,dy,RARawDistance,DECRawDistance,RAGuideDistance,DECGuideDistance,RADuration,RADirection,DECDuration,DECDirection,XStep,YStep,StarMass,SNR,ErrorCode"

SAMPLE = f"""PHD2 version 2.6.14 [Windows], Log version 2.5. Log enabled at 2026-09-29 18:53:15

Calibration Begins at 2026-09-29 18:55:33
Pixel scale = 3.15 arc-sec/px, Binning = 1, Focal length = 190 mm
West,0,0.000,0.000,1178.292,590.287,0.000
West,1,0.401,-0.536,1177.891,590.823,0.669
Calibration complete, mount = Alpaca Benro Polaris Telescope (ASCOM).

Guiding Begins at 2026-09-29 18:56:28
Pixel scale = 3.15 arc-sec/px, Binning = 1, Focal length = 190 mm
RA Guide Speed = 15.0 a-s/s, Dec Guide Speed = 15.0 a-s/s
{HEADER}
1,1.114,"Mount",-1.075,-1.253,0.451,-1.588,0.081,-0.286,31,W,67,N,,,8000,40.0,0
2,2.151,"Mount",-1.270,-1.545,-0.587,1.912,0.107,-0.350,41,E,81,S,,,8000,40.0,0
3,3.226,"DROP",,,,,,,,,,,,,0,0.00,2,"Star lost - low SNR"
4,4.313,"Mount",-2.622,-1.041,-0.580,-2.761,-0.102,-0.507,0,,118,N,,,8000,40.0,0
INFO: DITHER by 1.200, -0.800, new lock pos = 1173.959, 589.265
5,5.265,"Mount",-1.282,-0.776,-0.061,-1.498,0.000,-0.280,0,,0,,,,8000,40.0,0
Guiding Ends at 2026-09-29 18:58:07

Guiding Begins at 2026-09-30 00:50:47
Pixel scale = 1.50 arc-sec/px, Binning = 1, Focal length = 400 mm
RA Guide Speed = 7.5 a-s/s, Dec Guide Speed = 7.5 a-s/s
{HEADER}
1,0.781,"Mount",0.103,-0.811,0.086,-0.813,0.000,-0.512,0,,102,N,,,8000,40.0,0
Guiding Ends at 2026-09-30 00:51:00
"""


@pytest.fixture
def guidelog(tmp_path):
    p = tmp_path / 'PHD2_GuideLog_test.txt'
    p.write_text(SAMPLE, encoding='utf-8')
    return str(p)


def test_frames_have_timestamps_from_each_guiding_segment(guidelog):
    frames, _ = load_phd2_guidelog(guidelog)
    assert list(frames['frame']) == [1, 2, 4, 5, 1]                  # DROP frame excluded
    assert frames['timestamp'].iloc[0] == pd.Timestamp('2026-09-29 18:56:29.114')
    assert frames['timestamp'].iloc[-1] == pd.Timestamp('2026-09-30 00:50:47.781')
    assert list(frames['segment']) == [0, 0, 0, 0, 1]


def test_raw_errors_are_converted_to_arcsec_with_each_segments_pixel_scale(guidelog):
    frames, _ = load_phd2_guidelog(guidelog)
    assert frames['ra_arcsec'].iloc[0] == pytest.approx(0.451 * 3.15)
    assert frames['dec_arcsec'].iloc[0] == pytest.approx(-1.588 * 3.15)
    assert frames['ra_arcsec'].iloc[-1] == pytest.approx(0.086 * 1.50)


def test_pulses_are_signed_like_the_driver_east_north_positive(guidelog):
    frames, _ = load_phd2_guidelog(guidelog)
    assert list(frames['ra_ms']) == [-31, 41, 0, 0, 0]
    assert list(frames['dec_ms']) == [67, -81, 118, 0, 102]


def test_pulse_arcsec_uses_each_segments_guide_speed(guidelog):
    frames, _ = load_phd2_guidelog(guidelog)
    assert frames['ra_pulse_arcsec'].iloc[0] == pytest.approx(-0.031 * 15.0)
    assert frames['dec_pulse_arcsec'].iloc[-1] == pytest.approx(0.102 * 7.5)


def test_events_include_guiding_calibration_dither_and_star_lost(guidelog):
    _, events = load_phd2_guidelog(guidelog)
    kinds = list(events['kind'])
    assert kinds == ['calibration', 'guiding_start', 'star_lost', 'dither', 'guiding_end',
                     'guiding_start', 'guiding_end']
    dither = events[events['kind'] == 'dither'].iloc[0]
    assert dither['timestamp'] == pd.Timestamp('2026-09-29 18:56:32.313')   # after frame 4
    assert events['timestamp'].iloc[0] == pd.Timestamp('2026-09-29 18:55:33')


def test_missing_guidelog_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_phd2_guidelog(str(tmp_path / 'nope.txt'))


def test_guidelog_without_guiding_returns_empty_frames(tmp_path):
    p = tmp_path / 'cal_only.txt'
    p.write_text(SAMPLE.split('Guiding Begins')[0], encoding='utf-8')
    frames, events = load_phd2_guidelog(str(p))
    assert frames.empty
    assert list(events['kind']) == ['calibration']


# ── window_df ─────────────────────────────────────────────────────────────

@pytest.fixture
def df():
    ts = pd.to_datetime(['2026-09-30 01:00', '2026-09-30 01:30', '2026-09-30 02:00', '2026-09-30 02:30'])
    return pd.DataFrame({'timestamp': ts, 'v': [1, 2, 3, 4], 't_sec': [0.0, 1800.0, 3600.0, 5400.0]})


def test_window_df_keeps_rows_inside_and_restarts_t_sec(df):
    w = window_df(df, '2026-09-30 01:15', '2026-09-30 02:00')
    assert list(w['v']) == [2, 3]
    assert list(w['t_sec']) == [0.0, 1800.0]


def test_window_df_with_no_limits_returns_everything_unchanged(df):
    w = window_df(df, None, None)
    assert list(w['v']) == [1, 2, 3, 4]
    assert list(w['t_sec']) == [0.0, 1800.0, 3600.0, 5400.0]


def test_window_df_open_ended(df):
    assert list(window_df(df, '2026-09-30 01:30', None)['v']) == [2, 3, 4]
    assert list(window_df(df, None, '2026-09-30 01:30')['v']) == [1, 2]


def test_window_df_without_t_sec_column(df):
    w = window_df(df.drop(columns='t_sec'), '2026-09-30 02:00', None)
    assert list(w['v']) == [3, 4]
    assert 't_sec' not in w.columns


def test_window_df_on_empty_frame_returns_empty():
    assert window_df(pd.DataFrame(), '2026-09-30 01:00', None).empty
