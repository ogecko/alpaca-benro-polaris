"""
Integration tests against a real, running driver (localhost:5555 by default -- override with
the ALPACA_REPLAY_TEST_HOST / ALPACA_REPLAY_TEST_PORT env vars).

Deliberately scoped to safe, non-motion operations only (connectivity, read-only
Polaris:ConfigFetch, and the Polaris:ReplayMark log marker) -- these run automatically
whenever a driver is reachable. Anything that moves the mount (SYNCGUIDE_PE/PULSEGUIDE_PE
against real hardware) is explicitly NOT exercised here; that's a real-test-case session run
by hand, not part of the automated suite.

Skips automatically (not a failure) if no driver is reachable.
"""
import os
import re
import sys

import pytest
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from replay import DriverSession, parse_file, run

HOST = os.environ.get("ALPACA_REPLAY_TEST_HOST", "localhost")
PORT = int(os.environ.get("ALPACA_REPLAY_TEST_PORT", "5555"))
TEST_LOGS = os.path.join(os.path.dirname(__file__), "..", "logs")


def _driver_reachable():
    try:
        r = requests.get(f"http://{HOST}:{PORT}/management/v1/description", timeout=2)
        return r.status_code == 200
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(not _driver_reachable(), reason=f"no driver reachable at {HOST}:{PORT}")


@pytest.fixture
def session():
    return DriverSession(f"http://{HOST}:{PORT}")


def test_connected_property_round_trips(session):
    assert session.get_property("connected") is True


def test_config_fetch_action_returns_real_values(session):
    result = session.action("Polaris:ConfigFetch", {"configNames": ["pec_T_sec"]})
    assert "pec_T_sec" in result
    assert result["pec_T_sec"] > 0


def test_replay_mark_action_is_supported_and_logs(session):
    supported = session.get_property("supportedactions")
    assert "Polaris:ReplayMark" in supported

    marker = {"event": "integration_test_marker", "probe": "test_replay_mark_action_is_supported_and_logs"}
    result = session.action("Polaris:ReplayMark", marker)
    assert result == "Polaris:ReplayMark ok"


def test_safe_smoke_replay_file_runs_clean(session):
    instructions = parse_file(os.path.join(TEST_LOGS, "safe_smoke.log"))
    assert len(instructions) == 3  # GET connected, PUT ConfigFetch action, SLEEP
    run(instructions, session, log=lambda *a: None)  # raises on any DriverError/HTTP error
