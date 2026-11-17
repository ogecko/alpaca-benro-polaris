"""
Tests for utility/sessions.py -- the single registry of captured log sessions (utility/sessions.toml) that every
analysis notebook selects from with SESSION = "<key>".
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import pandas as pd
import pytest

from sessions import load_registry, get_session, list_sessions, scan_new, add_new


def write(p, lines):
    p.write_text(''.join(l + '\n' for l in lines), encoding='utf-8')


@pytest.fixture
def archive(tmp_path):
    logs = tmp_path / 'logs'
    logs.mkdir()
    write(logs / 'alpaca.jdm_Beta7.1_09_29_pulseguide_a1.log', [
        "2026-09-29T18:34:58.077 INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER v2.2.0 Beta 7.1 =========== ",
        "2026-09-29T18:55:35.198 INFO PECLOG {'n': 2, 'resid': [-0.125, None]}",
        "2026-09-29T18:55:36.198 INFO ->> Polaris: SYNC GUIDING    Ra +000d00'01.18\", Dec +000d00'21.65\" Residuals",
    ])
    write(logs / 'alpaca.jdm_Beta7.1_09_29_pulseguide_a2.log', ["2026-09-29T20:00:00.000 INFO KFLOG {'θ_meas_raw': [1, 2, 3]}"])
    write(logs / 'alpaca.jdm_Beta7.1_09_29_pulseguide_a1_PHD2_GuideLog_2026-09-29_185315.txt', ["PHD2 version 2.6.14"])
    write(logs / 'alpaca.rpi_Beta5.0_09_13_kfpidlog_a1.log', [
        "2026-09-13T19:54:00.000 INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER v2.2.0 Beta 5.0 =========== ",
        "2026-09-13T19:55:00.000 INFO PIDLOG {'x': 1}"])
    reg = tmp_path / 'sessions.toml'
    reg.write_text('# Captured log sessions\n[defaults]\nlog_dir = "logs"\n\n'
                   '[sessions."rpi_Beta5.0_09_13_kfpidlog"]\nlogs = ["alpaca.rpi_Beta5.0_09_13_kfpidlog_a*.log"]\n'
                   'notes = "tracking, Raspberry Pi"   # my own note\n', encoding='utf-8')
    return tmp_path, reg


def test_get_session_resolves_files_relative_to_the_registry(archive):
    root, reg = archive
    s = get_session('rpi_Beta5.0_09_13_kfpidlog', registry=reg)
    assert s.log_dir == str(root / 'logs')
    assert s.log_filenames == ['alpaca.rpi_Beta5.0_09_13_kfpidlog_a*.log']
    assert [os.path.basename(p) for p in s.paths] == ['alpaca.rpi_Beta5.0_09_13_kfpidlog_a1.log']
    assert s.phd2 is None and s.t_from is None and s.notes == 'tracking, Raspberry Pi'


def test_unknown_session_suggests_close_matches(archive):
    _, reg = archive
    with pytest.raises(KeyError, match='rpi_Beta5.0_09_13_kfpidlog'):
        get_session('rpi_Beta5_09_13', registry=reg)


def test_scan_finds_new_sessions_with_detected_details(archive):
    _, reg = archive
    new = scan_new(registry=reg)
    assert list(new) == ['jdm_Beta7.1_09_29_pulseguide']
    e = new['jdm_Beta7.1_09_29_pulseguide']
    assert e['logs'] == ['alpaca.jdm_Beta7.1_09_29_pulseguide_a*.log']
    assert e['phd2'] == 'alpaca.jdm_Beta7.1_09_29_pulseguide_a1_PHD2_GuideLog_2026-09-29_185315.txt'
    assert e['date'] == '2026-09-29' and e['driver'] == 'v2.2.0 Beta 7.1'
    assert e['records'] == ['kf', 'pec', 'sync'] and e['guiding'] == 'pulse (PHD2) + sync'


def test_add_new_appends_without_touching_existing_entries(archive):
    _, reg = archive
    before = reg.read_text(encoding='utf-8')
    added = add_new(registry=reg, notes={'alpaca.jdm_Beta7.1_09_29_pulseguide': 'pulse guiding night'})
    after = reg.read_text(encoding='utf-8')
    assert added == ['jdm_Beta7.1_09_29_pulseguide']
    assert after.startswith(before)                                   # existing text, comments and notes kept
    s = get_session('jdm_Beta7.1_09_29_pulseguide', registry=reg)
    assert s.notes == 'pulse guiding night'
    assert s.phd2.endswith('_PHD2_GuideLog_2026-09-29_185315.txt') and os.path.isabs(s.phd2)
    assert add_new(registry=reg) == []                                 # idempotent


def test_list_sessions_table_and_filters(archive):
    _, reg = archive
    add_new(registry=reg)
    t = list_sessions(registry=reg)
    assert isinstance(t, pd.DataFrame) and set(t.index) == {'rpi_Beta5.0_09_13_kfpidlog', 'jdm_Beta7.1_09_29_pulseguide'}
    assert list(list_sessions(registry=reg, records='kf').index) == ['jdm_Beta7.1_09_29_pulseguide']
    assert list(list_sessions(registry=reg, contains='raspberry').index) == ['rpi_Beta5.0_09_13_kfpidlog']
    assert t.loc['jdm_Beta7.1_09_29_pulseguide', 'files'] == 2 and t.loc['jdm_Beta7.1_09_29_pulseguide', 'phd2']


def test_window_is_passed_through(archive):
    _, reg = archive
    with open(reg, 'a', encoding='utf-8') as f:
        f.write('t_from = "2026-09-13 20:00"\n')
    s = get_session('rpi_Beta5.0_09_13_kfpidlog', registry=reg)
    assert s.t_from == '2026-09-13 20:00' and s.t_to is None


def test_catalog_maps_are_keyed_by_the_catalog_session_name(archive):
    """catalog_logs / extract_segments key sessions as 'alpaca.<name>' with rotated parts merged; a registry
    entry that groups several files (k1..k4) gives each of them its notes and PHD2 log."""
    from sessions import catalog_notes, catalog_phd2
    _, reg = archive
    add_new(registry=reg, notes={'jdm_Beta7.1_09_29_pulseguide': 'pulse guiding night'})
    notes = catalog_notes(registry=reg)
    assert notes == {'alpaca.rpi_Beta5.0_09_13_kfpidlog': 'tracking, Raspberry Pi',
                     'alpaca.jdm_Beta7.1_09_29_pulseguide': 'pulse guiding night'}
    phd2 = catalog_phd2(registry=reg)
    assert list(phd2) == ['alpaca.jdm_Beta7.1_09_29_pulseguide'] and os.path.exists(phd2['alpaca.jdm_Beta7.1_09_29_pulseguide'])


def test_a_multi_file_entry_maps_every_file(tmp_path):
    from sessions import catalog_notes
    (tmp_path / 'logs').mkdir()
    for k in (1, 2):
        write(tmp_path / 'logs' / f'alpaca.soak_08_28k{k}.log', ["2026-08-28T20:00:00.000 INFO x"])
    reg = tmp_path / 'sessions.toml'
    reg.write_text('[defaults]\nlog_dir = "logs"\n[sessions."soak_08_28k"]\n'
                   'logs = ["alpaca.soak_08_28k1.log", "alpaca.soak_08_28k2.log"]\nnotes = "soak"\n', encoding='utf-8')
    assert catalog_notes(registry=reg) == {'alpaca.soak_08_28k1': 'soak', 'alpaca.soak_08_28k2': 'soak'}


def test_site_latitude_comes_from_the_session_log_or_the_default(archive):
    from sessions import site_latitude
    root, reg = archive
    add_new(registry=reg)
    with open(root / 'logs' / 'alpaca.jdm_Beta7.1_09_29_pulseguide_a2.log', 'a', encoding='utf-8') as f:
        f.write("2026-09-29T20:01:00.000 INFO 127.0.0.1 -> PUT /api/v1/telescope/0/sitelatitude "
                "{'SiteLatitude': '43.6163888888889', 'ClientID': '1', 'ClientTransactionID': '2'}\n")
    assert site_latitude('jdm_Beta7.1_09_29_pulseguide', registry=reg) == pytest.approx(43.6163888888889)
    assert site_latitude('alpaca.jdm_Beta7.1_09_29_pulseguide', registry=reg) == pytest.approx(43.6163888888889)
    assert site_latitude('rpi_Beta5.0_09_13_kfpidlog', registry=reg, default=-33.65) == -33.65


@pytest.fixture
def multi_night(tmp_path):
    """One driver run left up over three nights (the host slept in between, logged on waking), the middle one idle,
    with a PHD2 guide log per guided night and two N.I.N.A. logs on the last."""
    logs = tmp_path / 'logs'
    logs.mkdir()
    write(logs / 'alpaca.steve_Beta8.0_11_03_a1_alpaca.log', [
        "2026-10-22T21:00:00.000 INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER v2.2.0 Beta 8.0 =========== ",
        "2026-10-22T21:05:00.000 INFO PECLOG {'n': 1, 'resid': [0.1, 0.2]}",
        "2026-10-23T00:57:00.000 INFO PECLOG {'n': 2, 'resid': [0.1, 0.2]}",
        "2026-10-27T17:34:49.000 WARNING ->> Heartbeat lag detected:   pulse 409055.865s (expected 0.100s)",
        "2026-10-27T17:34:49.100 WARNING ->> Event loop lag detected:  slept 409055.865s (expected 0.500s)",
        "2026-10-27T23:17:00.000 INFO <<- Polaris: BATTERY status changed",
        "2026-11-02T19:26:22.622 WARNING ->> Heartbeat lag detected:   pulse 414464.887s (expected 0.100s)",
        "2026-11-02T19:26:22.700 WARNING ->> Event loop lag detected:  slept 414465.303s (expected 0.500s)",
        "2026-11-02T19:30:00.000 INFO PECLOG {'n': 3, 'resid': [0.1, None]}",
        "2026-11-03T00:02:00.000 INFO PECLOG {'n': 4, 'resid': [0.1, 0.2]}",
        "2026-11-03T19:39:31.632 WARNING ->> Heartbeat lag detected:   pulse 70624.294s (expected 0.100s)",
        "2026-11-03T19:39:31.670 WARNING ->> Event loop lag detected:  slept 70624.559s (expected 0.500s)",
        "2026-11-03T19:45:00.000 INFO ->> Polaris: SYNC GUIDING    Ra +000d00'01.18\", Dec +000d00'21.65\" Residuals",
        "2026-11-03T22:36:00.000 INFO PECLOG {'n': 5, 'resid': [0.1, 0.2]}",
    ])
    write(logs / 'alpaca.steve_Beta8.0_11_03_a1_PHD2_GuideLog_2026-11-02_193340.txt', ["PHD2 version 2.6.14"])
    write(logs / 'alpaca.steve_Beta8.0_11_03_a1_PHD2_GuideLog_2026-11-03_194900.txt', ["PHD2 version 2.6.14"])
    nina_header = ["-" * 70, "--------------N.I.N.A. - Nighttime Imaging 'N' Astronomy--------------"]
    write(logs / 'alpaca.steve_Beta8.0_11_03_a2_Nina_20261103-194809.log',
          nina_header + ["2026-11-03T19:48:09.1234|INFO|App.cs|Start|1|started"])
    write(logs / 'alpaca.steve_Beta8.0_11_03_a3_Nina_20261103-233901.log',
          nina_header + ["2026-11-03T23:39:01.1234|INFO|App.cs|Start|1|started"])
    write(logs / 'alpaca.other_Beta8.0_11_03_a1_PHD2_GuideLog_2026-11-03_194900.txt', ["PHD2 version 2.6.14"])
    reg = tmp_path / 'sessions.toml'
    reg.write_text('[defaults]\nlog_dir = "logs"\n', encoding='utf-8')
    return tmp_path, reg


def test_a_log_over_several_nights_is_split_into_windowed_sessions_with_their_companion_logs(multi_night):
    _, reg = multi_night
    new = scan_new(registry=reg)
    assert list(new) == ['steve_Beta8.0_10_22', 'steve_Beta8.0_11_02', 'steve_Beta8.0_11_03']   # the idle 10-27 left out
    a, b, c = new.values()
    assert all(e['logs'] == ['alpaca.steve_Beta8.0_11_03_a1_alpaca.log'] for e in (a, b, c))
    assert (a['t_from'], a['t_to'], a['date']) == ('2026-10-22 21:00', '2026-10-23 00:57', '2026-10-22')
    assert (b['t_from'], b['t_to']) == ('2026-11-02 19:26', '2026-11-03 00:02')   # the wake-up heartbeat is the 11-03 night's
    assert (c['t_from'], c['t_to']) == ('2026-11-03 19:39', '2026-11-03 22:36')
    assert all(e['driver'] == 'v2.2.0 Beta 8.0' for e in (a, b, c))               # carried across the sleeps
    assert 'phd2' not in a and 'nina' not in a and a['guiding'] == 'none'
    assert b['phd2'] == 'alpaca.steve_Beta8.0_11_03_a1_PHD2_GuideLog_2026-11-02_193340.txt' and 'nina' not in b
    assert c['phd2'] == 'alpaca.steve_Beta8.0_11_03_a1_PHD2_GuideLog_2026-11-03_194900.txt'   # not other's same night
    assert c['nina'] == ['alpaca.steve_Beta8.0_11_03_a2_Nina_20261103-194809.log',
                         'alpaca.steve_Beta8.0_11_03_a3_Nina_20261103-233901.log']
    assert c['records'] == ['pec', 'sync'] and c['guiding'] == 'pulse (PHD2) + sync'


def test_nina_logs_are_never_taken_for_driver_sessions(multi_night):
    from sessions import driver_logs, is_nina_log
    root, reg = multi_night
    assert [os.path.basename(p) for p in driver_logs(str(root / 'logs'))] == ['alpaca.steve_Beta8.0_11_03_a1_alpaca.log']
    unnamed = root / 'logs' / 'alpaca.x_a1.log'
    write(unnamed, ["-" * 70, "--------------N.I.N.A. - Nighttime Imaging 'N' Astronomy--------------"])
    assert is_nina_log(str(unnamed))                                              # by its header, whatever its name


def test_multi_night_sessions_round_trip_and_catalog_maps_pick_by_time(multi_night):
    from sessions import catalog_notes, catalog_phd2, value_at
    _, reg = multi_night
    add_new(registry=reg, notes={'steve_Beta8.0_11_02': 'night two', 'steve_Beta8.0_11_03': 'night three'})
    assert scan_new(registry=reg) == {}                                           # everything covered now
    s = get_session('steve_Beta8.0_11_03', registry=reg)
    assert (s.t_from, s.t_to) == ('2026-11-03 19:39', '2026-11-03 22:36') and len(s.nina) == 2
    assert all(os.path.isabs(n) and os.path.exists(n) for n in s.nina)
    assert list_sessions(registry=reg).loc['steve_Beta8.0_11_03', 'nina'] == 2
    notes = catalog_notes(registry=reg)['alpaca.steve_Beta8.0_11_03_a1_alpaca']
    assert value_at(notes, '2026-11-02 21:00') == 'night two' and value_at(notes, '2026-11-03 20:00') == 'night three'
    assert value_at(notes, '2026-10-27 18:00') is None                             # the idle night between
    phd2 = catalog_phd2(registry=reg)['alpaca.steve_Beta8.0_11_03_a1_alpaca']
    assert value_at(phd2, '2026-11-03 20:00').endswith('_2026-11-03_194900.txt')
    assert value_at(phd2, '2026-10-22 22:00') is None
