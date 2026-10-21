"""
utility/scc_analysis.py: Slew and Center sequences (goto, sync, correction goto, ...) detected in the driver log.
"""
import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pytest

from scc_analysis import parse_events, scc_steps, scc_summary, radec_to_azalt, _azalt_from_ha, sep_arcmin

LAT = -33.655


def dms(v, width=3):
    s = '+' if v >= 0 else '-'
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    sec = (v - d - m / 60) * 3600
    return f"{s}{d:0{width}d}d{m:02d}'{sec:05.2f}\""


def slew(t, ra, dec, client='2103'):
    return (f"{t} INFO 1.2.3.4 -> PUT /api/v1/telescope/0/slewtocoordinatesasync {{'RightAscension': '{ra}', "
            f"'Declination': '{dec}', 'ClientID': '{client}', 'ClientTransactionID': '1'}}")


def sync(t, ra, dec, ha_deg, client='2103'):
    """A sync and the driver's SYNC Observed line, with the Az/Alt of (ra, dec) at hour angle ha_deg."""
    az, alt = _azalt_from_ha(ha_deg, dec, LAT)
    return [f"{t} INFO 1.2.3.4 -> PUT /api/v1/telescope/0/synctocoordinates {{'RightAscension': '{ra}', "
            f"'Declination': '{dec}', 'ClientID': '{client}', 'ClientTransactionID': '2'}}",
            f"{t} INFO ->> Polaris: SYNC Observed   Ra 00h00m00.00s Dec +000d00'00.00\" Az {dms(az)} Alt {dms(alt, 3)} "
            f"(Multi-Point Alignment)"]


T_RA, T_DEC = 19.2205465, -59.9473278          # the target
LOG = [
    "2026-10-14T19:53:28.723 INFO Site lat = -33.655 (-033d39'18.59\") | lon = 151.12 (+151d07'20.93\").",
    "2026-10-14T20:30:00.000 INFO QUEST Model  | Points: 10 | w: +0.99",
    "2026-10-14T20:30:00.001 INFO   MAC: ON    | d2 +000d08'43.88\" d3 -000d02'04.57\" M2 scale +1.25% (held) | SGA: ON   | RMS",
    slew('2026-10-14T20:33:13.328', T_RA, T_DEC),
    "2026-10-14T20:33:19.680 INFO ->> Polaris: BACKLASH taking up slack: M1 -144\"",
    "2026-10-14T20:33:33.748 INFO ->> Polaris: BACKLASH taking up slack: M2 -421\"",
    *sync('2026-10-14T20:33:47.411', T_RA, T_DEC + 0.1, ha_deg=-20.0),           # 6' north of the target
    "2026-10-14T20:33:47.487 INFO Sync Guide seeded from QUEST residual: Az +000d04'26.16\", Alt +000d04'09.62\", angle +000d04'47.57\"",
    slew('2026-10-14T20:33:50.024', T_RA + 1e-8, T_DEC),                         # re-sent, re-precessed: same target
    *sync('2026-10-14T20:34:07.374', T_RA + 0.2 / 60 / 15 / math.cos(math.radians(T_DEC)), T_DEC, ha_deg=-19.9),  # 0.2' east
    "2026-10-14T20:34:07.376 INFO Cleared sync data for timestamp: 2026-10-14T09:33:47.414Z",
    slew('2026-10-14T20:34:10.029', T_RA, T_DEC),                                # within tolerance: no sync follows
    "2026-10-14T20:35:02.136 INFO 1.2.3.4 -> PUT /api/v1/rotator/0/movemechanical {'Position': '60', 'ClientID': '8388'}",
    slew('2026-10-14T20:35:08.113', 1.6467, -57.0973),                           # a new target
    "2026-10-14T20:35:16.038 WARNING ->> Polaris: BACKLASH compensation stopped until the next goto for M1: crossed its slack more than 2 times",
    *sync('2026-10-14T20:35:40.000', 1.6467, -57.0973 - 0.05, ha_deg=-40.0),     # 3' south, then no more gotos
    *sync('2026-10-14T20:37:40.000', 1.6467, -57.0973, ha_deg=-39.5),            # sync guiding: not part of the SCC
    slew('2026-10-14T20:50:00.000', 3.0, -40.0),                                 # a goto never solved: not an SCC
]


@pytest.fixture
def log(tmp_path):
    f = tmp_path / 'alpaca.scc.log'
    f.write_text('\n'.join(LOG) + '\n')
    return f


def test_steps_follow_the_scc_loop(log):
    ev, lat = parse_events(log)
    assert lat == pytest.approx(LAT)
    st = scc_steps(ev, lat)
    assert list(st['scc']) == [0, 0, 0, 1]
    assert list(st['step']) == [1, 2, 3, 1]
    assert list(st['synced']) == [True, True, False, True]
    assert st['miss'].iloc[0] == pytest.approx(6.0, abs=0.01) and st['miss_north'].iloc[0] == pytest.approx(6.0, abs=0.01)
    assert st['miss'].iloc[1] == pytest.approx(0.2, abs=0.01) and st['miss_east'].iloc[1] == pytest.approx(0.2, abs=0.01)
    assert st['miss'].iloc[3] == pytest.approx(3.0, abs=0.01) and st['miss_north'].iloc[3] == pytest.approx(-3.0, abs=0.01)
    assert st['to_solve_s'].iloc[0] == pytest.approx(34.083)
    assert st['sga_seed'].iloc[0] == pytest.approx(4 + 47.57 / 60)
    assert bool(st['replaced_previous'].iloc[1]) and not bool(st['replaced_previous'].iloc[0])
    assert st['ratio'].iloc[0] == pytest.approx(0.2 / 6.0, abs=0.01)
    assert (st['mac'] == 'MACv2').all() and (st['sga'] == 'ON').all() and (st['points'] == 10).all()


def test_blc_lines_belong_to_the_goto_they_follow(log):
    st = scc_steps(*parse_events(log))
    assert list(st['takeups']) == [2, 0, 0, 0]
    assert st['giveups'].iloc[3] == 'M1'
    assert (st['blc'] == 'on').all()


def test_summary_outcomes(log):
    s = scc_summary(scc_steps(*parse_events(log)))
    assert list(s['gotos']) == [3, 1] and list(s['solves']) == [2, 1]
    assert list(s['outcome']) == ['within tolerance', 'ended on a solve']
    assert s['first_miss'].iloc[0] == pytest.approx(6.0, abs=0.01)
    assert s['to_last_goto_s'].iloc[0] == pytest.approx(56.701)


def test_misses_in_az_alt():
    """The Az/Alt parts of a miss match the target and solve placed independently at the same hour angle, and add up
    to the total. (The goto landed 6' north of a target between the south pole and the zenith: north is up there.)"""
    st = scc_steps(*parse_events_from(LOG))
    r = st.iloc[0]
    assert np.hypot(r['miss_h'], r['miss_v']) == pytest.approx(r['miss'], rel=0.01)
    az_t, alt_t = _azalt_from_ha(-20.0, T_DEC, LAT)                       # the target, same RA so same hour angle
    az_s, alt_s = _azalt_from_ha(-20.0, T_DEC + 0.1, LAT)                 # where the goto landed
    assert r['miss_v'] == pytest.approx((alt_s - alt_t) * 60, abs=0.02)   # (the log's Az/Alt are rounded to 0.01")
    assert r['miss_h'] == pytest.approx(((az_s - az_t + 180) % 360 - 180) * math.cos(math.radians(alt_s)) * 60, abs=0.02)
    assert r['miss_v'] > 3


def parse_events_from(lines, tmp=[0]):
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'alpaca.x.log')
    with open(p, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return parse_events(p)


def test_radec_to_azalt_round_trip():
    for ha, dec in [(-30, -60), (0, -10), (45, 20), (120, -80)]:
        az, alt = _azalt_from_ha(ha, dec, LAT)
        ra_ref = 5.0
        assert radec_to_azalt(ra_ref, dec, ra_ref, az, alt, LAT) == pytest.approx((az, alt), abs=1e-9)
        # an hour of RA later is an hour of hour angle earlier
        az2, alt2 = radec_to_azalt(ra_ref + 1, dec, ra_ref, az, alt, LAT)
        assert (az2, alt2) == pytest.approx(_azalt_from_ha(ha - 15, dec, LAT), abs=1e-9)


def test_no_backlash_lines_means_blc_off(tmp_path):
    f = tmp_path / 'alpaca.old.log'
    f.write_text('\n'.join(l for l in LOG if 'BACKLASH' not in l) + '\n')
    st = scc_steps(*parse_events(f))
    assert (st['blc'] == 'off').all() and (st['takeups'] == 0).all()


def test_sep_arcmin():
    assert sep_arcmin(1.0, 0.0, 1.0 + 1 / 15, 0.0) == pytest.approx(60.0)
    assert sep_arcmin(1.0, 30.0, 1.0, 30.5) == pytest.approx(30.0)


def test_a_rotate_during_a_goto_keeps_its_solve_and_a_late_sync_is_not_its_solve(tmp_path):
    """2026-10-14 20:37: Pilot rotated while NINA's goto ran; the solve 52 s later is still that goto's. A sync minutes
    after a goto (20:38 -> 20:40, 19 deg away) is something else."""
    lines = [LOG[0],
             slew('2026-10-14T20:37:27.551', 0.74978, -17.83542),
             "2026-10-14T20:37:32.839 INFO 1.2.3.4 -> PUT /api/v1/rotator/0/movemechanical {'Position': '-30', 'ClientID': '8388'}",
             "2026-10-14T20:37:40.000 INFO ->> Polaris: BACKLASH taking up slack: M3 -288\"",
             *sync('2026-10-14T20:38:19.300', 0.73635, -17.72522, ha_deg=-60.0),
             slew('2026-10-14T20:38:22.040', 0.74978, -17.83542),
             *sync('2026-10-14T20:40:50.341', 0.71194, 1.69816, ha_deg=-60.0)]
    f = tmp_path / 'alpaca.rot.log'
    f.write_text('\n'.join(lines) + '\n')
    st = scc_steps(*parse_events(f))
    assert list(st['step']) == [1, 2] and list(st['synced']) == [True, False]
    assert bool(st['rotated'].iloc[0]) and st['takeups'].iloc[0] == 1
    assert st['miss'].iloc[0] == pytest.approx(sep_arcmin(0.74978, -17.83542, 0.73635, -17.72522))


def test_mac_version_from_its_log_line(tmp_path):
    v1 = [l.replace(" d2 +000d08'43.88\" d3 -000d02'04.57\" M2 scale +1.25% (held)", '') for l in LOG]
    off = [l.replace('MAC: ON ', 'MAC: OFF') for l in v1]
    for lines, want in ((v1, 'MACv1'), (off, 'OFF')):
        f = tmp_path / f'alpaca.{want}.log'
        f.write_text('\n'.join(lines) + '\n')
        assert (scc_steps(*parse_events(f))['mac'] == want).all()


def test_a_goto_to_the_same_target_minutes_later_is_a_recentre(tmp_path):
    """2026-09-12: NINA re-centred the same target every few minutes between exposures: separate sequences, and the
    first goto of each is a re-centre (its miss is mostly drift), not a blind goto."""
    lines = [LOG[0],
             slew('2026-09-12T23:25:01.482', T_RA, T_DEC), *sync('2026-09-12T23:25:40.000', T_RA, T_DEC + 0.8, ha_deg=-20),
             slew('2026-09-12T23:26:07.207', T_RA, T_DEC),
             slew('2026-09-12T23:31:05.921', T_RA, T_DEC), *sync('2026-09-12T23:31:26.000', T_RA, T_DEC + 0.05, ha_deg=-19),
             slew('2026-09-12T23:31:28.176', T_RA, T_DEC)]
    f = tmp_path / 'alpaca.recentre.log'
    f.write_text('\n'.join(lines) + '\n')
    st = scc_steps(*parse_events(f))
    assert list(st['scc']) == [0, 0, 1, 1] and list(st['step']) == [1, 2, 1, 2]
    assert list(st['kind']) == ['blind', 'correction', 'recentre', 'correction']
    assert list(scc_summary(st)['kind']) == ['blind', 'recentre']

