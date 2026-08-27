import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import KeywordLine, RequestLine, is_location_dependent, parse_line, run


def test_topocentric_slewabsolute_is_not_location_dependent():
    instr = parse_line(
        "127.0.0.1 -> PUT /api/v1/telescope/0/action "
        "{'Action': 'Polaris:SlewAbsolute', 'Parameters': '{\"az\": 240, \"alt\": 45, \"roll\": 0, \"isasync\": true}'}"
    )
    assert is_location_dependent(instr) is False


def test_equatorial_slewabsolute_is_location_dependent():
    instr = parse_line(
        "127.0.0.1 -> PUT /api/v1/telescope/0/action "
        "{'Action': 'Polaris:SlewAbsolute', 'Parameters': '{\"ra\": 5.5, \"dec\": -30, \"isasync\": true}'}"
    )
    assert is_location_dependent(instr) is True


def test_galactic_slewrelative_is_location_dependent():
    instr = parse_line(
        "127.0.0.1 -> PUT /api/v1/telescope/0/action "
        "{'Action': 'Polaris:SlewRelative', 'Parameters': '{\"l\": 10, \"b\": 5}'}"
    )
    assert is_location_dependent(instr) is True


@pytest.mark.parametrize("path", [
    "/api/v1/telescope/0/synctocoordinates",
    "/api/v1/telescope/0/slewtocoordinates",
    "/api/v1/telescope/0/slewtocoordinatesasync",
    "/api/v1/telescope/0/synctotarget",
    "/api/v1/telescope/0/targetrightascension",
])
def test_standard_ascom_equatorial_endpoints_are_location_dependent(path):
    instr = RequestLine(method="PUT", path=path, query={}, body={"RightAscension": 5.5, "Declination": -30})
    assert is_location_dependent(instr) is True


def test_synctocoordinates_get_is_not_flagged():
    # GETs are read-only status checks, not commands -- never location-dependent to replay.
    instr = RequestLine(method="GET", path="/api/v1/telescope/0/targetrightascension", query={}, body=None)
    assert is_location_dependent(instr) is False


@pytest.mark.parametrize("action", ["Polaris:J2000Sync", "Polaris:J2000Goto", "Polaris:TrackOrbital", "Polaris:GetOrbitals"])
def test_always_location_dependent_actions(action):
    instr = RequestLine(method="PUT", path="/api/v1/telescope/0/action", query={},
                         body={"Action": action, "Parameters": "{}"})
    assert is_location_dependent(instr) is True


def test_ordinary_tracking_put_is_not_location_dependent():
    instr = parse_line("127.0.0.1 -> PUT /api/v1/telescope/0/tracking {'Tracking': 'true'}")
    assert is_location_dependent(instr) is False


def test_config_update_action_is_not_location_dependent():
    instr = parse_line(
        "127.0.0.1 -> PUT /api/v1/telescope/0/action "
        "{'Action': 'Polaris:ConfigUpdate', 'Parameters': '{\"advanced_pec\": true}'}"
    )
    assert is_location_dependent(instr) is False


# ── run() integration: skip vs allow ────────────────────────────────────────

class RecordingSession:
    def __init__(self):
        self.puts = []

    def put(self, path, body):
        self.puts.append((path, body))

    def get(self, path, query=None):
        return None


def test_run_skips_location_dependent_lines_by_default():
    instructions = [
        (1, RequestLine("PUT", "/api/v1/telescope/0/tracking", {}, {"Tracking": "true"})),
        (2, RequestLine("PUT", "/api/v1/telescope/0/synctocoordinates", {}, {"RightAscension": 5.5, "Declination": -30})),
    ]
    session = RecordingSession()
    run(instructions, session, log=lambda *a: None)
    assert session.puts == [("/api/v1/telescope/0/tracking", {"Tracking": "true"})]


def test_run_sends_location_dependent_lines_when_allowed():
    instructions = [
        (1, RequestLine("PUT", "/api/v1/telescope/0/synctocoordinates", {}, {"RightAscension": 5.5, "Declination": -30})),
    ]
    session = RecordingSession()
    run(instructions, session, log=lambda *a: None, allow_equatorial=True)
    assert session.puts == [("/api/v1/telescope/0/synctocoordinates", {"RightAscension": 5.5, "Declination": -30})]
