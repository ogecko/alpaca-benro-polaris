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
_KEYWORD_RE = re.compile(r'\b(SLEEP|SYNCGUIDE_PE|PULSEGUIDE_PE)\s+(\{.*\})\s*$')

# Not replayed -- a fresh pair is minted per request by DriverSession.
_SESSION_KEYS = {'ClientID', 'ClientTransactionID'}


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
    None (not recognised) are dropped."""
    instructions = []
    with open(path) as f:
        for line_no, line in enumerate(f, start=1):
            try:
                instr = parse_line(line)
            except ValueError as e:
                raise ValueError(f"{path}:{line_no}: {e}") from e
            if instr is not None:
                instructions.append((line_no, instr))
    return instructions


# ── HTTP session against the target driver ───────────────────────────────────

class DriverError(RuntimeError):
    pass


class DriverSession:
    """Minimal Alpaca REST client. Mints a fresh ClientID once per session and an
    incrementing ClientTransactionID per request -- the values in a captured log line are
    never reused, since they aren't meaningful outside the session they were captured in."""

    def __init__(self, base_url, client_id=None, timeout=30):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id if client_id is not None else (int(time.time()) % 100000)
        self.timeout = timeout
        self._txn = itertools.count(1)

    def _ids(self):
        return {'ClientID': self.client_id, 'ClientTransactionID': next(self._txn)}

    @staticmethod
    def _unwrap(body):
        if body.get('ErrorNumber'):
            raise DriverError(f"ErrorNumber {body['ErrorNumber']}: {body.get('ErrorMessage')}")
        return body.get('Value')

    def get(self, path, query=None):
        params = {**(query or {}), **self._ids()}
        r = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return self._unwrap(r.json())

    def put(self, path, body=None):
        data = {**(body or {}), **self._ids()}
        r = requests.put(f"{self.base_url}{path}", data=data, timeout=self.timeout)
        r.raise_for_status()
        return self._unwrap(r.json())

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

    def _resolve_pec_T_sec(self, session, override):
        if override is not None:
            return override
        if self._pec_T_sec is None:
            cfg = session.action("Polaris:ConfigFetch", {"configNames": ["pec_T_sec"]})
            self._pec_T_sec = cfg["pec_T_sec"]
        return self._pec_T_sec

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
                _send_sync(session, total_ra, total_dec)
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


def _send_sync(session, ra_offset_deg, dec_offset_deg):
    ra_h = session.get_property("rightascension")
    dec_d = session.get_property("declination")
    session.put_property("synctocoordinates", {
        "RightAscension": ra_h + ra_offset_deg / 15.0,
        "Declination": dec_d + dec_offset_deg,
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


# ── Execution ─────────────────────────────────────────────────────────────────

def run(instructions, session, pe_state=None, log=print):
    pe_state = pe_state or PEState()
    for line_no, instr in instructions:
        if isinstance(instr, KeywordLine):
            if instr.keyword == "SLEEP":
                log(f"[{line_no}] SLEEP {instr.payload['seconds']}s")
                time.sleep(instr.payload["seconds"])
            else:
                log(f"[{line_no}] {instr.keyword} {instr.payload}")
                pe_state.advance(session, instr.keyword, instr.payload)
        elif isinstance(instr, RequestLine):
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
    args = p.parse_args()

    instructions = parse_file(args.log)
    session = DriverSession(f"http://{args.host}:{args.port}", client_id=args.client_id)
    print(f"Replaying {len(instructions)} instruction(s) from {args.log} against {session.base_url} (ClientID={session.client_id})")
    run(instructions, session)
    print("Done.")


if __name__ == "__main__":
    main()
