#!/usr/bin/env python3
"""
replay.py -- Alpaca Benro Polaris replay/diagnostic/system-test tool.

Reads a text replay file (either a real captured alpaca.log, or a hand-written test file
in the same shape) and sends the same requests to a live driver. See README.md for the
full file format and design rationale.

Usage:
    python replay.py -l tests/some_test.log
    python replay.py -l /path/to/alpaca.log --host 192.168.1.50 --port 5555
"""
import argparse
import ast
import itertools
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl

import requests


# ── Line parsing ─────────────────────────────────────────────────────────────

@dataclass
class RequestLine:
    """A real captured Alpaca REST request, replayed verbatim (minus ClientID/ClientTransactionID)."""
    method: str
    path: str
    query: dict
    body: Optional[dict]


@dataclass
class KeywordLine:
    """A replay.py instruction (SLEEP, SYNCGUIDE_PE, PULSEGUIDE_PE, ...)."""
    keyword: str
    payload: dict


# Matches "-> METHOD PATH[?query] [{'body': 'dict'}]" anywhere in the line -- the optional
# leading timestamp/level/IP text (real captured lines) is simply not part of the match.
_REQUEST_RE = re.compile(r'->\s+(GET|PUT)\s+(\S+?)(?:\s+(\{.*\}))?\s*$')

# Matches "KEYWORD {json payload}" anywhere in the line -- the leading timestamp/level word
# (real or hand-written, e.g. "REPLAY" instead of "INFO") is ignored, not parsed.
_KEYWORD_RE = re.compile(r'\b(SLEEP|WAIT_SETTLED|SYNC_RESIDUAL|SYNCGUIDE_PE|PULSEGUIDE_PE)\s+(\{.*\})\s*$')

# Not replayed -- a fresh pair is minted per request by DriverSession.
_SESSION_KEYS = {'ClientID', 'ClientTransactionID'}

# A captured synctocoordinates PUT is immediately followed by the driver's own
# "SYNC Observed" then "SYNC GUIDING ... Residuals" lines *only* when process_guide_sync()
# actually accepted it as a small, clamped guide correction (control.py's sync_az_alt() --
# the alternative path, process_quest_sync(), never logs this). That residual is the
# location/time-invariant delta a real autoguider's correction represents -- see
# _pair_sync_residual() below, which extracts it so the raw (non-portable) absolute RA/Dec
# never needs to be replayed at all for this, the common, case.
_SYNC_GUIDING_RESIDUAL_RE = re.compile(
    r"SYNC GUIDING\s+Ra\s+([+-])(\d+)d(\d+)'([\d.]+)\",\s*Dec\s+([+-])(\d+)d(\d+)'([\d.]+)\"\s+Residuals"
)


def _dms_to_deg(sign, d, m, s):
    val = float(d) + float(m) / 60 + float(s) / 3600
    return -val if sign == '-' else val


def _pair_sync_residual(lines, put_line_idx):
    """Look up to 3 lines past a captured synctocoordinates PUT (0-based index) for the
    driver's own SYNC GUIDING residual line. Returns (ra_resid_deg, dec_resid_deg) or None."""
    for line in lines[put_line_idx + 1: put_line_idx + 4]:
        m = _SYNC_GUIDING_RESIDUAL_RE.search(line)
        if m:
            ra_sign, ra_d, ra_m, ra_s, dec_sign, dec_d, dec_m, dec_s = m.groups()
            return (_dms_to_deg(ra_sign, ra_d, ra_m, ra_s), _dms_to_deg(dec_sign, dec_d, dec_m, dec_s))
    return None


def parse_line(line: str):
    """Parse one replay-file line. Returns a RequestLine, a KeywordLine, or None if the line
    isn't one replay.py acts on (startup banners, PECLOG/PIDLOG, Polaris pushes, warnings, ...)."""
    line = line.rstrip('\n')
    if not line.strip():
        return None

    m = _KEYWORD_RE.search(line)
    if m:
        keyword, payload_str = m.groups()
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed {keyword} payload: {e}") from e
        return KeywordLine(keyword, payload)

    m = _REQUEST_RE.search(line)
    if m:
        method, path_and_query, body_str = m.groups()
        path, _, qs = path_and_query.partition('?')
        query = {k: v for k, v in parse_qsl(qs) if k not in _SESSION_KEYS}
        body = None
        if body_str:
            try:
                parsed = ast.literal_eval(body_str)
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"malformed request body: {e}") from e
            if not isinstance(parsed, dict):
                raise ValueError(f"request body is not a dict: {body_str!r}")
            body = {k: v for k, v in parsed.items() if k not in _SESSION_KEYS}
        return RequestLine(method, path, query, body)

    return None


def parse_file(path):
    """Parse a replay file into a list of (line_no, instruction) pairs. Lines that parse to
    None (not recognised) are dropped.

    A captured synctocoordinates PUT paired with the driver's own SYNC GUIDING residual line
    (see _pair_sync_residual) is converted to a SYNC_RESIDUAL keyword instruction instead of a
    plain RequestLine -- replaying the residual against the target's own current position,
    rather than the original absolute RA/Dec, which isn't portable across sites/times. An
    unpaired synctocoordinates (no residual line -- it went through the real alignment-model
    update path instead) is left as a normal RequestLine, where is_location_dependent() will
    catch it."""
    with open(path) as f:
        lines = f.readlines()

    instructions = []
    for i, line in enumerate(lines):
        line_no = i + 1
        if '-> PUT' in line and '/synctocoordinates' in line:
            residual = _pair_sync_residual(lines, i)
            if residual is not None:
                ra_resid_deg, dec_resid_deg = residual
                instructions.append((line_no, KeywordLine(
                    "SYNC_RESIDUAL", {"ra_resid_deg": ra_resid_deg, "dec_resid_deg": dec_resid_deg})))
                continue
        try:
            instr = parse_line(line)
        except ValueError as e:
            raise ValueError(f"{path}:{line_no}: {e}") from e
        if instr is not None:
            instructions.append((line_no, instr))
    return instructions


# ── HTTP session against the target driver ───────────────────────────────────

class DriverError(RuntimeError):
    def __init__(self, error_number, message):
        self.error_number = error_number
        super().__init__(f"ErrorNumber {error_number}: {message}")


# Alpaca ErrorNumbers safe to retry rather than fail the whole run over: 1031 is
# NotConnectedException, observed in practice as a brief, self-recovering state flip on a real
# WiFi-connected mount (correlates with the driver's own "position update lag"/NetDrops
# warnings), not a genuine bad request.
_TRANSIENT_ALPACA_ERRORS = {1031}


class DriverSession:
    """Minimal Alpaca REST client. Mints a fresh ClientID once per session and an
    incrementing ClientTransactionID per request -- the values in a captured log line are
    never reused, since they aren't meaningful outside the session they were captured in."""

    def __init__(self, base_url, client_id=None, timeout=30, retries=3, retry_backoff_s=1.5, sleep=time.sleep):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id if client_id is not None else (int(time.time()) % 100000)
        self.timeout = timeout
        self.retries = retries
        self.retry_backoff_s = retry_backoff_s
        self._sleep = sleep
        self._txn = itertools.count(1)

    def _ids(self):
        return {'ClientID': self.client_id, 'ClientTransactionID': next(self._txn)}

    @staticmethod
    def _unwrap(body):
        if body.get('ErrorNumber'):
            raise DriverError(body['ErrorNumber'], body.get('ErrorMessage'))
        return body.get('Value')

    def _with_retry(self, attempt_fn):
        """Retries a request on a network-level failure or a known-transient Alpaca error
        (see _TRANSIENT_ALPACA_ERRORS) -- anything else (a genuine bad request, an unexpected
        ErrorNumber) fails immediately, since retrying it would just fail again."""
        for attempt in range(1, self.retries + 1):
            try:
                return attempt_fn()
            except requests.RequestException:
                if attempt == self.retries:
                    raise
            except DriverError as e:
                if e.error_number not in _TRANSIENT_ALPACA_ERRORS or attempt == self.retries:
                    raise
            self._sleep(self.retry_backoff_s)

    def get(self, path, query=None):
        def attempt():
            params = {**(query or {}), **self._ids()}
            r = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
            r.raise_for_status()
            return self._unwrap(r.json())
        return self._with_retry(attempt)

    def put(self, path, body=None):
        def attempt():
            data = {**(body or {}), **self._ids()}
            r = requests.put(f"{self.base_url}{path}", data=data, timeout=self.timeout)
            r.raise_for_status()
            return self._unwrap(r.json())
        return self._with_retry(attempt)

    def action(self, name, parameters):
        return self.put("/api/v1/telescope/0/action",
                         {"Action": name, "Parameters": json.dumps(parameters)})

    # Convenience wrappers for the standard Telescope device, used by the PE engines below.
    def get_property(self, name):
        return self.get(f"/api/v1/telescope/0/{name}")

    def put_property(self, name, body):
        return self.put(f"/api/v1/telescope/0/{name}", body)


# ── Periodic-error (PE) simulation ────────────────────────────────────────────

ARCMIN_PER_DEG = 60
SEC_PER_HOUR = 3600

# Guide-pulse direction codes, matching control.py's process_pulse_guide_axis convention.
PULSE_NORTH, PULSE_SOUTH, PULSE_EAST, PULSE_WEST = 0, 1, 2, 3


def pe_offset_deg(model, T_sec, t_sec):
    """Position offset (degrees) implied by a PECLOG-style [dc, h1, h2, ...] rate model
    (arcmin/hour, same convention as PECLOG's ra_model/dec_model) at time t_sec since this
    model's own t=0, for a worm period T_sec. Each harmonic is assumed zero-phase (a pure
    sine in the rate domain relative to t=0 of this model), matching harmonic_rate()'s
    magnitude-only convention in control.py."""
    if not model:
        return 0.0
    dc = model[0]
    harmonics = model[1:]
    w = 2 * math.pi / T_sec
    offset = (dc / ARCMIN_PER_DEG / SEC_PER_HOUR) * t_sec
    for h_idx, h_val in enumerate(harmonics, start=1):
        if not h_val:
            continue
        hw = h_idx * w
        offset += (h_val / ARCMIN_PER_DEG / SEC_PER_HOUR) / hw * math.sin(hw * t_sec)
    return offset


class PEState:
    """Carries the accumulated simulated RA/Dec position offset across consecutive
    SYNCGUIDE_PE/PULSEGUIDE_PE lines in one replay run, so a new phase continues smoothly
    from wherever the previous one left off instead of jumping back to zero."""

    def __init__(self):
        self.ra_offset_deg = 0.0
        self.dec_offset_deg = 0.0
        self._pec_T_sec = None  # resolved lazily from the driver, cached for the whole run
        self._sync_baseline = None  # (ra_hours, dec_deg), captured once -- see _resolve_sync_baseline
        self.applied_ra_deg = 0.0   # running total of what the driver's own PEC correction has
        self.applied_dec_deg = 0.0  # already applied to the real motors -- see _credit_applied_pec

    def _resolve_pec_T_sec(self, session, override):
        if override is not None:
            return override
        if self._pec_T_sec is None:
            cfg = session.action("Polaris:ConfigFetch", {"configNames": ["pec_T_sec"]})
            self._pec_T_sec = cfg["pec_T_sec"]
        return self._pec_T_sec

    def _resolve_sync_baseline(self, session):
        """The RA/Dec every SYNCGUIDE_PE target is computed relative to -- captured once, from
        the driver's live position the first time it's needed, and never re-read after that.
        Re-reading it on every tick would be wrong: the driver applies its own PEC-fitted
        correction to the real motors between our syncs (trained on our *previous* syncs), so
        its live position already reflects that correction. Basing our next target on it would
        double-count the driver's own contribution on top of ours and diverge instead of
        converging -- exactly what was observed the first time this ran for real (fit_rate grew
        unbounded instead of settling near the declared dc)."""
        if self._sync_baseline is None:
            self._sync_baseline = (session.get_property("rightascension"), session.get_property("declination"))
        return self._sync_baseline

    def _credit_applied_pec(self, session):
        """A real autoguider plate-solves the real sky, so its measured residual already
        reflects however much the driver's own PEC correction has physically moved the real
        motors since the last sync -- our simulated mount doesn't move on its own, so we have
        to credit that correction manually or every sync would re-report the full raw
        uncorrected drift, which is what caused the fit to run away instead of converging.
        Polaris:StatusFetch's pec_accum is the driver's own precise account of exactly that
        (arcmin applied since its previous guide-sync ingest, resets each time) -- reading it
        right before each sync and folding it into a running total is the live equivalent of
        what a real plate-solve would show."""
        status = session.action("Polaris:StatusFetch", {})
        pec_accum_ra_arcmin, pec_accum_dec_arcmin = status["pec_accum"]
        self.applied_ra_deg += pec_accum_ra_arcmin / ARCMIN_PER_DEG
        self.applied_dec_deg += pec_accum_dec_arcmin / ARCMIN_PER_DEG

    def advance(self, session, keyword, payload, sleep=time.sleep, clock=time.monotonic):
        ra_model = payload["ra_model"]
        dec_model = payload["dec_model"]
        exposure_s = payload["exposure_s"]
        session_min = payload["session_min"]
        T_sec = self._resolve_pec_T_sec(session, payload.get("pec_T_sec"))

        ra_phase_start = self.ra_offset_deg
        dec_phase_start = self.dec_offset_deg

        session.action("Polaris:ReplayMark", {
            "event": f"{keyword}_start", "mechanism": keyword,
            "ra_model": ra_model, "dec_model": dec_model,
            "exposure_s": exposure_s, "session_min": session_min, "pec_T_sec": T_sec,
        })

        n_steps = max(1, round(session_min * 60 / exposure_s))
        guide_rates = None
        prev_ra_total = ra_phase_start
        prev_dec_total = dec_phase_start

        t0 = clock()
        for i in range(n_steps):
            t = i * exposure_s
            total_ra = ra_phase_start + pe_offset_deg(ra_model, T_sec, t)
            total_dec = dec_phase_start + pe_offset_deg(dec_model, T_sec, t)

            if keyword == "SYNCGUIDE_PE":
                if i > 0:
                    self._credit_applied_pec(session)
                ra_base_h, dec_base_deg = self._resolve_sync_baseline(session)
                net_ra = total_ra - self.applied_ra_deg
                net_dec = total_dec - self.applied_dec_deg
                _send_sync(session, ra_base_h, dec_base_deg, net_ra, net_dec)
            else:
                if guide_rates is None:
                    guide_rates = (session.get_property("guideraterightascension"),
                                   session.get_property("guideratedeclination"))
                _send_pulses(session, total_ra - prev_ra_total, total_dec - prev_dec_total, guide_rates)

            prev_ra_total, prev_dec_total = total_ra, total_dec

            next_at = t0 + (i + 1) * exposure_s
            sleep_for = next_at - clock()
            if sleep_for > 0:
                sleep(sleep_for)

        self.ra_offset_deg, self.dec_offset_deg = prev_ra_total, prev_dec_total

        session.action("Polaris:ReplayMark", {
            "event": f"{keyword}_end", "mechanism": keyword,
            "ra_model": ra_model, "dec_model": dec_model,
            "exposure_s": exposure_s, "session_min": session_min, "pec_T_sec": T_sec,
        })


def _send_sync(session, ra_base_h, dec_base_deg, ra_offset_deg, dec_offset_deg):
    session.put_property("synctocoordinates", {
        "RightAscension": ra_base_h + ra_offset_deg / 15.0,
        "Declination": dec_base_deg + dec_offset_deg,
    })


def send_sync_residual(session, ra_resid_deg, dec_resid_deg):
    """Replay a real captured guide-sync residual (see parse_file/_pair_sync_residual) against
    the replay target's own current position, instead of the raw absolute RA/Dec that residual
    was originally captured relative to -- portable across sites and times, unlike the raw
    sync would be."""
    ra_h = session.get_property("rightascension")
    dec_d = session.get_property("declination")
    session.put_property("synctocoordinates", {
        "RightAscension": ra_h + ra_resid_deg / 15.0,
        "Declination": dec_d + dec_resid_deg,
    })


def _send_pulses(session, delta_ra_deg, delta_dec_deg, guide_rates):
    """Send RA then Dec pulses for this cycle's incremental correction, matching the order
    a real autoguider (e.g. PHD2) issues them in."""
    ra_rate, dec_rate = guide_rates
    for delta, rate, positive_dir, negative_dir in (
        (delta_ra_deg, ra_rate, PULSE_EAST, PULSE_WEST),
        (delta_dec_deg, dec_rate, PULSE_NORTH, PULSE_SOUTH),
    ):
        if rate is None or rate <= 0 or abs(delta) < 1e-9:
            continue
        duration_ms = int(round(abs(delta) / rate * 1000))
        duration_ms = max(1, min(10000, duration_ms))
        direction = positive_dir if delta > 0 else negative_dir
        session.put_property("pulseguide", {"Direction": direction, "Duration": duration_ms})


def wait_settled(session, timeout_s=60, poll_s=1.0, sleep=time.sleep, clock=time.monotonic):
    """Poll telescope/0/slewing until it clears, instead of guessing a fixed SLEEP duration.
    Matches how a real client (e.g. Nina) actually sequences a goto -- fire it, then wait for
    completion -- rather than relying on a captured SlewAbsolute line's isasync value, which is
    both implicit (easy to silently lose if a captured line's isasync gets edited) and blocks
    inside the HTTP call itself rather than being a visible step in the test file."""
    deadline = clock() + timeout_s
    while session.get_property("slewing"):
        if clock() >= deadline:
            raise TimeoutError(f"WAIT_SETTLED: still slewing after {timeout_s}s")
        sleep(poll_s)


# ── Location-dependent commands ───────────────────────────────────────────────
#
# Anything expressed in equatorial (RA/Dec) or galactic (l/b/gpa) coordinates is only
# meaningful relative to the site lat/lon *and* local sidereal time (site longitude + time of
# day/date) it was captured at -- RA/Dec -> Alt/Az depends on both. Replaying it verbatim
# elsewhere, or even at the same site but a different time, can point at a completely
# different or unreachable part of the sky -- a DSO near the celestial equator is
# particularly sensitive to this, since its Alt/Az (and which side of the meridian it's on)
# changes fast with time even when RA/Dec stay fixed. Topocentric az/alt/roll is the one frame
# that's already relative to the local horizon and safe to replay anywhere, any time. Skipped
# by default; --allow-equatorial replays these anyway -- only meaningful if you've checked
# both the site lat/lon *and* that the target is actually above the horizon right now, not
# just that the site matches.

# Standard ASCOM Telescope endpoints that carry an absolute equatorial target.
_EQUATORIAL_PATHS = {
    '/api/v1/telescope/0/synctocoordinates',
    '/api/v1/telescope/0/slewtocoordinates',
    '/api/v1/telescope/0/slewtocoordinatesasync',
    '/api/v1/telescope/0/synctotarget',
    '/api/v1/telescope/0/slewtotarget',
    '/api/v1/telescope/0/slewtotargetasync',
    '/api/v1/telescope/0/targetrightascension',
    '/api/v1/telescope/0/targetdeclination',
}

# Polaris: actions that are always sky/time-dependent regardless of parameters (named
# catalog/orbital targets, J2000 catalog syncs) -- not just "might carry ra/dec".
_ALWAYS_LOCATION_DEPENDENT_ACTIONS = {
    'Polaris:J2000Sync', 'Polaris:J2000Goto',
    'Polaris:TrackOrbital', 'Polaris:GetOrbitals',
}

# Polaris: actions that accept a mix of coordinate frames in one call (see
# Polaris:SlewAbsolute's az/alt/roll vs ra/dec/pa vs l/b/gpa) -- only location-dependent if
# the specific call actually used a non-topocentric key.
_MIXED_FRAME_ACTIONS = {'Polaris:SlewAbsolute', 'Polaris:SlewRelative'}
_NON_TOPOCENTRIC_KEYS = {'ra', 'dec', 'pa', 'l', 'b', 'gpa'}


def is_location_dependent(instr: RequestLine) -> bool:
    if instr.method != "PUT" or not instr.body:
        return False
    if instr.path in _EQUATORIAL_PATHS:
        return True
    if instr.path.endswith('/action'):
        action = instr.body.get('Action')
        if action in _ALWAYS_LOCATION_DEPENDENT_ACTIONS:
            return True
        if action in _MIXED_FRAME_ACTIONS:
            raw_params = instr.body.get('Parameters')
            try:
                params = json.loads(raw_params) if isinstance(raw_params, str) else (raw_params or {})
            except (TypeError, json.JSONDecodeError):
                params = {}
            if isinstance(params, dict) and any(k in params for k in _NON_TOPOCENTRIC_KEYS):
                return True
    return False


# ── Execution ─────────────────────────────────────────────────────────────────

def run(instructions, session, pe_state=None, log=print, allow_equatorial=False):
    pe_state = pe_state or PEState()
    for line_no, instr in instructions:
        if isinstance(instr, KeywordLine):
            if instr.keyword == "SLEEP":
                log(f"[{line_no}] SLEEP {instr.payload['seconds']}s")
                time.sleep(instr.payload["seconds"])
            elif instr.keyword == "WAIT_SETTLED":
                log(f"[{line_no}] WAIT_SETTLED {instr.payload}")
                wait_settled(session, **{k: v for k, v in instr.payload.items() if k in ("timeout_s", "poll_s")})
            elif instr.keyword == "SYNC_RESIDUAL":
                log(f"[{line_no}] SYNC_RESIDUAL {instr.payload}")
                send_sync_residual(session, instr.payload["ra_resid_deg"], instr.payload["dec_resid_deg"])
            else:
                log(f"[{line_no}] {instr.keyword} {instr.payload}")
                pe_state.advance(session, instr.keyword, instr.payload)
        elif isinstance(instr, RequestLine):
            if not allow_equatorial and is_location_dependent(instr):
                log(f"[{line_no}] SKIPPED (location/time-dependent, not portable across sites or times): "
                    f"{instr.method} {instr.path} {instr.body} -- pass --allow-equatorial only if the "
                    f"replay target is at the same site lat/lon AND the target is actually above the "
                    f"horizon right now")
                continue
            log(f"[{line_no}] {instr.method} {instr.path} {instr.body or instr.query or ''}")
            if instr.method == "GET":
                session.get(instr.path, instr.query)
            else:
                session.put(instr.path, instr.body)
    return pe_state


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-l", "--log", required=True, help="Replay file: a captured alpaca.log or a hand-written test.log")
    p.add_argument("--host", default="localhost", help="Target driver host (default: localhost)")
    p.add_argument("--port", type=int, default=5555, help="Target driver Alpaca REST port (default: 5555)")
    p.add_argument("--client-id", type=int, default=None, help="Alpaca ClientID to use for this replay session (default: derived from current time)")
    p.add_argument("--allow-equatorial", action="store_true",
                    help="Replay RA/Dec, galactic, and orbital/catalog commands too, instead of skipping them. "
                         "Only safe if the replay target is at the same site lat/lon AND the target is "
                         "actually above the horizon right now -- same lat/lon alone isn't enough, since "
                         "RA/Dec -> Alt/Az also depends on time (a DSO near the celestial equator can be "
                         "unreachable at a different time of day even at the same site).")
    args = p.parse_args()

    instructions = parse_file(args.log)
    session = DriverSession(f"http://{args.host}:{args.port}", client_id=args.client_id)
    print(f"Replaying {len(instructions)} instruction(s) from {args.log} against {session.base_url} (ClientID={session.client_id})")
    run(instructions, session, allow_equatorial=args.allow_equatorial)
    print("Done.")


if __name__ == "__main__":
    main()
