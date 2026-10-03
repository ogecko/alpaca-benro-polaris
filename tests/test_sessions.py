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
