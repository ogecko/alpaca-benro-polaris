"""
Slew and Center (SCC) analysis for analyse_goto.ipynb: a client's (NINA's) centring loop as the driver logs it.

  1. GOTO        slewtocoordinates(async) to the target
  2. SYNC        synctocoordinates to the plate solve: where the goto really landed
  3. GOTO        the same target again (the correction goto, with the sync in the alignment)
  4. SYNC        ... repeated until the solve lands within the client's tolerance

The client syncs only when a solve is outside its tolerance, so the last goto of a successful SCC has no sync in the
driver log: it landed within tolerance. Each goto's miss is the separation from its target to its solve.

  parse_events       the log's slews, syncs, rotates and what the driver logged around them (BLC, MAC, alignment
                     points, the Sync Guide offset seeded from the alignment's residual)
  scc_steps          the SCCs, one row per goto: its miss (arcmin; RA/Dec and Az/Alt parts), time to its solve, the
                     BLC take-ups / give-ups while it moved, and the corrections in force
  scc_summary        one row per SCC: attempts, outcome, first (blind) miss, time
  radec_to_azalt     a target's Az/Alt from the solve's own Az/Alt (no clock or time zone needed)
"""
import math
import re

import numpy as np
import pandas as pd

_TS = re.compile(r'^(\d{4}-\d\d-\d\dT[\d:.]+) ')
_REQ = re.compile(r"-> PUT /api/v1/telescope/0/(slewtocoordinatesasync|slewtocoordinates|synctocoordinates) "
                  r"\{'RightAscension': '([-\d.eE]+)', 'Declination': '([-\d.eE]+)'.*?'ClientID': '(\d+)'")
_OTHER_MOVE = re.compile(r"-> PUT /api/v1/(?:telescope/0/(slewtoaltaz\w*|park|findhome)|rotator/0/(move\w*))")
_PILOT_MOVE = re.compile(r"(J2000Goto|SlewAbsolute|SlewRelative) \{")
_DMS = r"([+-])(\d+)d(\d+)'([\d.]+)\""
_SYNC_OBS = re.compile(r"SYNC Observed\s+Ra .*?Az " + _DMS + r"\s+Alt " + _DMS)
_BLC_TAKEUP = re.compile(r'BACKLASH taking up slack: (.*)')
_BLC_GIVEUP = re.compile(r'BACKLASH compensation stopped until .*?for (M[\d, M]+)')
_MAC = re.compile(r'MAC: (ON|OFF)')
_QUEST = re.compile(r'QUEST Model\s+\| Points: (\d+)')
_SGA = re.compile(r'SGA: (ON|OFF)')
_SEED = re.compile(r'Sync Guide seeded from QUEST residual: .*angle ' + _DMS)
_SITE = re.compile(r'Site lat = ([-\d.]+)')
_CLEARED = re.compile(r'Cleared sync data for timestamp')

SAME_TARGET_ARCSEC = 5.0        # gotos to targets this close are the same target (the client re-sends it, re-precessed)
MAX_GAP_S = 150.0               # a goto to the same target this long after the previous one starts a new sequence: a
                                # re-centre between exposures (its miss is mostly the drift since), not a correction
SYNC_WINDOW_S = 120.0           # a goto's solve is the first sync within this long after it (and before the next goto;
                                # NINA's solves land 8-45 s after the goto, other syncs minutes later)


def _dms(sign, d, m, s):
    v = int(d) + int(m) / 60 + float(s) / 3600
    return -v if sign == '-' else v


def sep_arcmin(ra1_h, dec1, ra2_h, dec2):
    """Angular separation (arcmin) of two RA (hours) / Dec (deg) positions."""
    a1, d1, a2, d2 = np.radians(np.asarray(ra1_h) * 15), np.radians(dec1), np.radians(np.asarray(ra2_h) * 15), np.radians(dec2)
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(a1 - a2)
    return np.degrees(np.arccos(np.clip(c, -1, 1))) * 60


def _azalt_from_ha(ha_deg, dec, lat):
    h, d, p = map(math.radians, (ha_deg, dec, lat))
    alt = math.asin(math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h))
    az = math.atan2(-math.sin(h) * math.cos(d), math.cos(p) * math.sin(d) - math.sin(p) * math.cos(d) * math.cos(h))
    return math.degrees(az) % 360, math.degrees(alt)


def _ha_from_azalt(az, alt, lat):
    a, h, p = map(math.radians, (az, alt, lat))
    ha = math.atan2(-math.sin(a) * math.cos(h), math.cos(p) * math.sin(h) - math.sin(p) * math.cos(h) * math.cos(a))
    return math.degrees(ha)


def radec_to_azalt(ra_h, dec, ref_ra_h, ref_az, ref_alt, lat):
    """Az/Alt (deg) of RA/Dec at the moment a reference position (ref_ra_h) was at ref_az/ref_alt: the local sidereal
    time comes from the reference itself (its hour angle at that Az/Alt), so no clock or time zone is needed."""
    lst = ref_ra_h * 15 + _ha_from_azalt(ref_az, ref_alt, lat)
    return _azalt_from_ha(lst - ra_h * 15, dec, lat)


def parse_events(path):
    """Every move and sync in a driver log, in order: DataFrame with time (ISO), kind ('slew', 'sync', 'rotate', 'move'
    -- a park, alt/az or Pilot slew), ra (h), dec, client, and per sync the Az/Alt the driver logged for it; per
    slew/sync the BLC lines, MAC/SGA state and alignment point count as last logged before it; per sync the Sync Guide
    offset (arcmin) the driver seeded from the alignment's residual there, and whether it replaced the previous sync.
    Also returns the site latitude (None if not logged)."""
    rows, lat = [], None
    state = dict(mac=None, sga=None, points=None)
    blc_seen = False
    with open(path, errors='replace') as fh:
        for line in fh:
            m = _TS.match(line)
            if not m:
                continue
            t = m.group(1)
            if lat is None and (g := _SITE.search(line)):
                lat = float(g.group(1))
            if (g := _REQ.search(line)):
                kind = 'sync' if g.group(1) == 'synctocoordinates' else 'slew'
                rows.append(dict(time=t, kind=kind, ra=float(g.group(2)), dec=float(g.group(3)), client=g.group(4),
                                 **state, takeups=[], giveups=[]))
            elif (g := _OTHER_MOVE.search(line)) or _PILOT_MOVE.search(line):
                # a rotate only turns the camera about the target; a park, alt/az or Pilot slew points somewhere else
                kind = 'rotate' if g and g.group(2) else 'move'
                rows.append(dict(time=t, kind=kind, ra=np.nan, dec=np.nan, client=None, **state, takeups=[], giveups=[]))
            elif (g := _BLC_TAKEUP.search(line)):
                blc_seen = True
                if rows:
                    rows[-1]['takeups'].append((t, g.group(1).strip()))
            elif (g := _BLC_GIVEUP.search(line)):
                blc_seen = True
                if rows:
                    rows[-1]['giveups'].append((t, g.group(1)))
            elif (g := _SYNC_OBS.search(line)):
                if rows and rows[-1]['kind'] == 'sync':
                    rows[-1]['sync_az'], rows[-1]['sync_alt'] = _dms(*g.groups()[:4]), _dms(*g.groups()[4:])
            elif (g := _SEED.search(line)):
                if rows and rows[-1]['kind'] == 'sync':
                    rows[-1]['sga_seed_arcmin'] = _dms(*g.groups()) * 60
            elif _CLEARED.search(line):
                if rows and rows[-1]['kind'] == 'sync':
                    rows[-1]['replaced_previous'] = True
            else:
                if (g := _QUEST.search(line)):
                    state['points'] = int(g.group(1))
                if (g := _MAC.search(line)):
                    # MACv2 (2026-10-11 on: M2/M3 offsets and M2 scale fitted with QUEST) logs its d2/d3; the earlier
                    # MAC (v1) doesn't
                    state['mac'] = 'OFF' if g.group(1) == 'OFF' else 'MACv2' if ' d2 ' in line else 'MACv1'
                if (g := _SGA.search(line)):
                    state['sga'] = g.group(1)
    ev = pd.DataFrame(rows)
    if len(ev):
        for c in ('sync_az', 'sync_alt', 'sga_seed_arcmin'):
            if c not in ev:
                ev[c] = np.nan
        ev['replaced_previous'] = ev.get('replaced_previous', pd.Series(False, index=ev.index)).fillna(False).astype(bool)
        ev['time'] = pd.to_datetime(ev['time'])
        ev.attrs['blc_in_log'] = blc_seen
    return ev, lat


def scc_steps(ev, lat=None, same_target_arcsec=SAME_TARGET_ARCSEC, sync_window_s=SYNC_WINDOW_S, max_gap_s=MAX_GAP_S):
    """One row per goto of each SCC (consecutive gotos to the same target, each within max_gap_s of the one before):
    scc, step (1 = the first), kind ('blind': the first goto to a new target; 'recentre': the first goto of a sequence
    to the same target as the last, after a gap -- its miss includes the drift since; 'correction': the later gotos),
    the goto's time and target, its solve (the first sync within sync_window_s and before the next move; NaN: no sync,
    i.e. within the client's tolerance or not solved), the miss (arcmin: total, east/north in RA/Dec and
    horizontal/vertical in Az/Alt -- where the goto landed relative to the target), the time from the goto to its solve,
    the slew from the previous position, the BLC take-ups / give-ups logged while it moved (and during a rotate before
    its solve: 'rotated'), and the MAC/SGA state and alignment points in force (mac: 'MACv2', 'MACv1' or 'OFF'; None
    before the log's first alignment). A single goto without a sync is not an SCC and is left out."""
    if not len(ev):
        return pd.DataFrame()
    ev = ev.reset_index(drop=True)
    gotos = ev.index[ev['kind'] == 'slew'].tolist()
    blc_in_log = bool(ev.attrs.get('blc_in_log', False))
    rows, scc, prev_target, prev_pos = [], -1, None, None
    for n, i in enumerate(gotos):
        g = ev.loc[i]
        nxt = gotos[n + 1] if n + 1 < len(gotos) else len(ev)
        between = ev.loc[i + 1:nxt - 1]
        moved = between[between['kind'] == 'move']
        stop = moved.index[0] if len(moved) else nxt
        rot = ev.loc[i + 1:stop - 1]
        rot = rot[rot['kind'] == 'rotate']
        syncs = ev.loc[i + 1:stop - 1]
        syncs = syncs[(syncs['kind'] == 'sync') & ((syncs['time'] - g['time']).dt.total_seconds() <= sync_window_s)]
        s = syncs.iloc[0] if len(syncs) else None
        rot = rot[rot['time'] <= s['time']] if s is not None else rot
        takeups = list(g['takeups']) + [x for _, e in rot.iterrows() for x in e['takeups']]
        giveups = list(g['giveups']) + [x for _, e in rot.iterrows() for x in e['giveups']]
        same = prev_target is not None and sep_arcmin(prev_target[0], prev_target[1], g['ra'], g['dec']) * 60 <= same_target_arcsec
        late = rows and (g['time'] - rows[-1]['goto_time']).total_seconds() > max_gap_s
        if not same or late:
            scc += 1
            step = 1
            kind = 'recentre' if same else 'blind'
        else:
            step = rows[-1]['step'] + 1
            kind = 'correction'
        r = dict(scc=scc, step=step, kind=kind, goto_time=g['time'], ra=g['ra'], dec=g['dec'], client=g['client'],
                 mac=g['mac'], sga=g['sga'], points=g['points'], blc='on' if blc_in_log else 'off',
                 takeups=len(takeups), giveups=';'.join(m for _, m in giveups), rotated=len(rot) > 0,
                 slew_arcmin=sep_arcmin(prev_pos[0], prev_pos[1], g['ra'], g['dec']) if prev_pos is not None else np.nan)
        if s is not None:
            de = (s['ra'] - g['ra']) * 15
            de = ((de + 180) % 360 - 180) * math.cos(math.radians(g['dec'])) * 60
            r.update(sync_time=s['time'], solved_ra=s['ra'], solved_dec=s['dec'],
                     miss=float(sep_arcmin(g['ra'], g['dec'], s['ra'], s['dec'])),
                     miss_east=de, miss_north=(s['dec'] - g['dec']) * 60,
                     to_solve_s=(s['time'] - g['time']).total_seconds(), sga_seed=s['sga_seed_arcmin'],
                     replaced_previous=bool(s['replaced_previous']), sync_az=s['sync_az'], sync_alt=s['sync_alt'])
            if lat is not None and np.isfinite(s['sync_az']) and np.isfinite(s['sync_alt']):
                taz, talt = radec_to_azalt(g['ra'], g['dec'], s['ra'], s['sync_az'], s['sync_alt'], lat)
                r['miss_h'] = ((s['sync_az'] - taz + 180) % 360 - 180) * math.cos(math.radians(s['sync_alt'])) * 60
                r['miss_v'] = (s['sync_alt'] - talt) * 60
            prev_pos = (s['ra'], s['dec'])
        else:
            prev_pos = (g['ra'], g['dec'])
        prev_target = (g['ra'], g['dec'])
        rows.append(r)
    if not rows:
        return pd.DataFrame()
    st = pd.DataFrame(rows)
    for c in ('sync_time', 'solved_ra', 'solved_dec', 'miss', 'miss_east', 'miss_north', 'miss_h', 'miss_v', 'to_solve_s',
              'sga_seed', 'sync_az', 'sync_alt'):
        if c not in st:
            st[c] = np.nan
    st['synced'] = st['miss'].notna()
    keep = st.groupby('scc')['synced'].transform('any')               # an SCC has at least one solve
    st = st[keep].copy()
    st['scc'] = st.groupby('scc', sort=False).ngroup()
    st['n_gotos'] = st.groupby('scc')['step'].transform('max')
    # what the alignment left at the solve (SGA seeds it) against how the next goto then missed
    st['next_miss'] = st.groupby('scc')['miss'].shift(-1)
    st['ratio'] = st['next_miss'] / st['miss']
    return st.reset_index(drop=True)


def scc_summary(st):
    """One row per SCC: start, kind (its first goto's: 'blind' or 'recentre'), target, gotos, solves, outcome ('within tolerance': its last goto has no solve, so the
    client accepted it; 'ended on a solve': it stopped after a solve outside tolerance -- out of attempts, or not an
    SCC but a goto and a sync), the first (blind) goto's miss, the last solved miss, seconds from the first goto to the
    last one, median seconds from a goto to its solve, and the corrections in force at the first goto."""
    if not len(st):
        return pd.DataFrame()
    g = st.groupby('scc')
    out = g.agg(start=('goto_time', 'first'), kind=('kind', 'first'), ra=('ra', 'first'), dec=('dec', 'first'),
                gotos=('step', 'max'),
                solves=('synced', 'sum'), first_miss=('miss', lambda m: m.iloc[0]), last_solved_miss=('miss', lambda m: m.dropna().iloc[-1]),
                to_last_goto_s=('goto_time', lambda t: (t.iloc[-1] - t.iloc[0]).total_seconds()),
                to_solve_median_s=('to_solve_s', 'median'), slew_arcmin=('slew_arcmin', 'first'),
                mac=('mac', 'first'), sga=('sga', 'first'), points=('points', 'first'), blc=('blc', 'first'),
                takeups=('takeups', 'sum'), giveups=('giveups', lambda x: ';'.join(v for v in x if v)),
                last_synced=('synced', 'last'))
    out['outcome'] = np.where(out['last_synced'], 'ended on a solve', 'within tolerance')
    return out.drop(columns='last_synced')
