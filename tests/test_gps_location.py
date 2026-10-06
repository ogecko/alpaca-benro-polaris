import asyncio
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))

import pytest

import gps_location
from config import Config


class FakeGPSDWriter:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, data):
        self.data.extend(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True


def _install_gpsd(monkeypatch, payload, *, feed_eof=True):
    state = {}
    writer = FakeGPSDWriter()

    async def open_connection(host, port, *, limit):
        assert host == "127.0.0.1"
        assert port == 2947
        assert limit == gps_location.GPSD_LINE_LIMIT
        reader = asyncio.StreamReader()
        reader.feed_data(payload)
        if feed_eof:
            reader.feed_eof()
        state["reader"] = reader
        return reader, writer

    monkeypatch.setattr(gps_location.asyncio, "open_connection", open_connection)
    return state, writer


def _report(**fields):
    return json.dumps(fields).encode("utf-8") + b"\n"


def test_run_all_does_not_schedule_gps_task_when_disabled(monkeypatch):
    import main

    monkeypatch.setattr(Config, "gps_auto_detect", False, raising=False)
    monkeypatch.setattr(main, "_start_eventloop_watchdog", lambda lifecycle, logger: None)
    monkeypatch.setattr(main.shr, "system_vitals_init", lambda lifecycle: None)
    monkeypatch.setattr(main, "install_asyncio_exception_handler", lambda lifecycle, logger: None)
    monkeypatch.setattr(main.app_socket, "attach_publisher_to_logger", lambda name: None)
    monkeypatch.setattr(main.telescope, "start_telescope", lambda polaris, lifecycle: None)
    monkeypatch.setattr(main.rotator, "start_rotator", lambda polaris, lifecycle: None)

    async def no_op(*args, **kwargs):
        return None

    monkeypatch.setattr(main.app_api, "alpaca_rest_httpd", no_op)
    monkeypatch.setattr(main.app_socket, "alpaca_socket_httpd", no_op)
    monkeypatch.setattr(main.app_web, "alpaca_pilot_httpd", no_op)
    monkeypatch.setattr(main.discovery_mdns, "mdns_client", no_op)
    monkeypatch.setattr(main.discovery_alpaca, "socket_client", no_op)
    monkeypatch.setattr(main.stellarium, "synscan_api", no_op)

    class FakePolaris:
        def __init__(self, logger, lifecycle):
            pass

        async def client(self, logger):
            return None

        async def shutdown(self):
            return None

    class FakeLifecycle:
        def __init__(self):
            self.created_tasks = []

        def create_task(self, coroutine, name):
            self.created_tasks.append(name)
            coroutine.close()

        async def wait_for_event(self):
            return None

        async def shutdown_tasks(self):
            return None

    monkeypatch.setattr(main, "Polaris", FakePolaris)
    monkeypatch.setattr(main, "polaris", None)
    lifecycle = FakeLifecycle()
    logger = SimpleNamespace(info=lambda message: None)

    asyncio.run(main.run_all(logger, lifecycle))

    assert "GPS" not in lifecycle.created_tasks


def test_try_gpsd_reports_2d_then_returns_3d_fix(monkeypatch):
    payload = b"".join(
        [
            _report(**{"class": "VERSION", "release": "3.25"}),
            _report(**{"class": "TPV", "mode": 2, "lat": 51.5, "lon": -0.12, "alt": 900, "time": "shared"}),
            _report(**{"class": "TPV", "mode": 3, "lat": 51.6, "lon": -0.1, "altMSL": 0, "time": "shared"}),
        ]
    )
    _, writer = _install_gpsd(monkeypatch, payload)
    reported_2d_fixes = []

    gps_fix = asyncio.run(
        gps_location._try_gpsd(timeout=2.0, on_2d_fix=reported_2d_fixes.append)
    )

    assert gps_fix == gps_location.GPSFix(51.6, -0.1, 0.0, 3)
    assert reported_2d_fixes == [gps_location.GPSFix(51.5, -0.12, None, 2)]
    assert bytes(writer.data) == b'?WATCH={"enable":true,"json":true}\n'
    assert writer.closed


@pytest.mark.parametrize(
    "report",
    [
        {"mode": 1, "lat": 51.5, "lon": -0.12},
        {"mode": 2, "lat": None, "lon": -0.12},
        {"mode": 2, "lat": float("nan"), "lon": -0.12},
        {"mode": 2, "lat": 91, "lon": -0.12},
        {"mode": 2, "lat": 51.5, "lon": 181},
        {"mode": 2.5, "lat": 51.5, "lon": -0.12},
    ],
)
def test_parse_tpv_rejects_no_fix_and_invalid_positions(report):
    assert gps_location._parse_tpv(report) is None


def test_parse_tpv_2d_fix_has_no_altitude():
    gps_fix = gps_location._parse_tpv({"mode": 2, "lat": 51.5, "lon": -0.12, "alt": 500})

    assert gps_fix == gps_location.GPSFix(51.5, -0.12, None, 2)


def test_try_gpsd_skips_garbage_and_no_fix_reports(monkeypatch):
    payload = b"".join(
        [
            b"not json\n",
            _report(**{"class": "TPV", "mode": 1, "lat": 0, "lon": 0, "time": "shared"}),
            _report(**{"class": "TPV", "mode": 2, "lat": 51.5, "lon": -0.12, "time": "shared"}),
        ]
    )
    _install_gpsd(monkeypatch, payload)

    gps_fix = asyncio.run(gps_location._try_gpsd(timeout=1.0))

    assert gps_fix == gps_location.GPSFix(51.5, -0.12, None, 2)


def test_try_gpsd_times_out_on_partial_report(monkeypatch):
    state, writer = _install_gpsd(
        monkeypatch,
        _report(**{"class": "VERSION", "release": "3.25"}) + b'{"class":"TPV"',
        feed_eof=False,
    )

    gps_fix = asyncio.run(gps_location._try_gpsd(timeout=0.02))

    assert gps_fix is None
    assert state["reader"].at_eof() is False
    assert writer.closed


def test_try_gpsd_reports_2d_fix_while_waiting_for_timeout(monkeypatch):
    state, writer = _install_gpsd(
        monkeypatch,
        _report(**{"class": "TPV", "mode": 2, "lat": 51.5, "lon": -0.12, "time": "1"}),
        feed_eof=False,
    )
    reported_2d_fixes = []

    gps_fix = asyncio.run(
        gps_location._try_gpsd(timeout=0.02, on_2d_fix=reported_2d_fixes.append)
    )

    expected = gps_location.GPSFix(51.5, -0.12, None, 2)
    assert gps_fix == expected
    assert reported_2d_fixes == [expected]
    assert state["reader"].at_eof() is False
    assert writer.closed


def test_retry_delay_doubles_to_configured_maximum():
    delays = [
        gps_location._retry_delay_after_attempt(index, gps_location.DEFAULT_GPS_RETRY_MAX_DELAY)
        for index in range(gps_location.DEFAULT_GPS_MAX_ATTEMPTS - 1)
    ]

    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0] + [60.0] * 13
    assert gps_location._retry_delay_after_attempt(2, 4.0) == 4.0


def test_configured_3d_fix_count_is_bounded():
    assert gps_location._configured_3d_fix_count(3) == 3
    assert gps_location._configured_3d_fix_count(0) == 1
    assert gps_location._configured_3d_fix_count(25) == gps_location.DEFAULT_GPS_MAX_ATTEMPTS
    assert gps_location._configured_3d_fix_count(True) == gps_location.DEFAULT_GPS_3D_FIX_COUNT


def test_listener_applies_fix_once_and_preserves_elevation_for_2d(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 1, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 30.0, raising=False)
    applied_changes = []
    live_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    async def get_gps_location(timeout, on_2d_fix=None):
        gps_fix = gps_location.GPSFix(51.5, -0.12, None, 2)
        if on_2d_fix is not None:
            on_2d_fix(gps_fix)
        return gps_fix

    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    polaris = SimpleNamespace(make_config_params_live=live_changes.append)

    asyncio.run(gps_location.gps_background_listener(polaris))

    expected = {
        "site_latitude": 51.5,
        "site_longitude": -0.12,
        "location": "GPS Receiver",
    }
    assert applied_changes == [expected]
    assert live_changes == [expected]


def test_listener_continues_after_2d_until_3d_fix(monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 2, raising=False)
    monkeypatch.setattr(Config, "gps_3d_fix_count", 1, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)
        clock.value += delay

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    applied_changes = []
    live_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )
    attempt_starts = []
    fixes = [
        gps_location.GPSFix(51.5, -0.12, None, 2),
        gps_location.GPSFix(51.6, -0.1, 35.7, 3),
    ]

    async def get_gps_location(timeout, on_2d_fix=None):
        attempt_starts.append(clock.value)
        gps_fix = fixes.pop(0)
        if gps_fix.mode == 2 and on_2d_fix is not None:
            on_2d_fix(gps_fix)
        return gps_fix

    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    polaris = SimpleNamespace(make_config_params_live=live_changes.append)

    asyncio.run(gps_location.gps_background_listener(polaris))

    assert attempt_starts == pytest.approx([0.0, 1.0])
    assert sleep_delays == pytest.approx([1.0])
    assert applied_changes == [
        {
            "site_latitude": 51.5,
            "site_longitude": -0.12,
            "location": "GPS Receiver",
        },
        {
            "site_latitude": 51.6,
            "site_longitude": -0.1,
            "location": "GPS Receiver",
            "site_elevation": 36,
        },
    ]
    assert live_changes == applied_changes


def test_listener_rounds_3d_altitude(monkeypatch, caplog):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 20, raising=False)
    monkeypatch.setattr(Config, "gps_3d_fix_count", 1, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 30.0, raising=False)
    applied_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    async def get_gps_location(timeout, on_2d_fix=None):
        return gps_location.GPSFix(51.5, -0.12, 35.7, 3)

    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    polaris = SimpleNamespace(make_config_params_live=lambda changes: None)

    with caplog.at_level(logging.INFO, logger="gps_location"):
        asyncio.run(gps_location.gps_background_listener(polaris))

    assert applied_changes[0]["site_elevation"] == 36
    assert applied_changes[0]["location"] == "GPS Receiver"
    assert "==GPS== Attempt 1 of 20: found a 3D fix (1/1 consecutive within 1.0 degrees)." in caplog.messages


def test_listener_requires_consecutive_3d_fixes_within_one_degree(monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 5, raising=False)
    monkeypatch.setattr(Config, "gps_3d_fix_count", 3, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    attempt_starts = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)
        clock.value += delay

    fixes = [
        gps_location.GPSFix(51.5, -0.12, 10, 3),
        gps_location.GPSFix(54.0, -0.12, 10, 3),
        gps_location.GPSFix(54.1, -0.12, 10, 3),
        gps_location.GPSFix(54.2, -0.12, 10, 3),
    ]

    async def get_gps_location(timeout, on_2d_fix=None):
        attempt_starts.append(clock.value)
        return fixes.pop(0)

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    applied_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )
    polaris = SimpleNamespace(make_config_params_live=lambda changes: None)

    asyncio.run(gps_location.gps_background_listener(polaris))

    assert attempt_starts == pytest.approx([0.0, 1.0, 3.0, 7.0])
    assert sleep_delays == pytest.approx([1.0, 2.0, 4.0])
    assert applied_changes == [{
        "site_latitude": pytest.approx(54.1),
        "site_longitude": pytest.approx(-0.12),
        "location": "GPS Receiver",
        "site_elevation": 10,
    }]


def test_listener_2d_fix_breaks_3d_stability_streak(monkeypatch):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 5, raising=False)
    monkeypatch.setattr(Config, "gps_3d_fix_count", 3, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    attempt_starts = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)
        clock.value += delay

    fixes = [
        gps_location.GPSFix(51.5, -0.12, 10, 3),
        gps_location.GPSFix(51.5, -0.12, 10, 3),
        gps_location.GPSFix(51.5, -0.12, 10, 3),
        gps_location.GPSFix(51.5, -0.12, 10, 3),
    ]

    async def get_gps_location(timeout, on_2d_fix=None):
        attempt_index = len(attempt_starts)
        attempt_starts.append(clock.value)
        gps_fix = fixes.pop(0)
        if attempt_index == 1 and on_2d_fix is not None:
            on_2d_fix(gps_location.GPSFix(51.5, -0.12, None, 2))
        return gps_fix

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    monkeypatch.setattr(Config, "apply_changes", classmethod(lambda cls, changes: dict(changes)))

    asyncio.run(gps_location.gps_background_listener(SimpleNamespace(make_config_params_live=lambda changes: None)))

    assert attempt_starts == pytest.approx([0.0, 1.0, 3.0, 7.0])
    assert sleep_delays == pytest.approx([1.0, 2.0, 4.0])


def test_listener_exhaustion_uses_configured_attempts_and_logs_each_attempt(monkeypatch, caplog):
    clock = SimpleNamespace(value=0.0)
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 3, raising=False)
    monkeypatch.setattr(Config, "gps_3d_fix_count", 3, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    attempt_starts = []
    attempt_timeouts = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)
        clock.value += delay

    async def no_fix(timeout, on_2d_fix=None):
        attempt_starts.append(clock.value)
        attempt_timeouts.append(timeout)
        clock.value += timeout / 2
        return None

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", no_fix)
    apply_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: apply_changes.append(changes) or changes),
    )

    with caplog.at_level(logging.INFO, logger="gps_location"):
        asyncio.run(gps_location.gps_background_listener(SimpleNamespace()))

    info_records = [
        record for record in caplog.records
        if record.name == "gps_location" and record.levelno == logging.INFO
    ]
    assert attempt_starts == pytest.approx([0.0, 6.0, 13.0])
    assert attempt_timeouts == [gps_location.GPSD_ATTEMPT_TIMEOUT] * 3
    assert sleep_delays == pytest.approx([1.0, 2.0])
    assert apply_changes == []
    assert [record.getMessage() for record in info_records] == [
        "==GPS== Starting acquisition attempt 1 of 3",
        "==GPS== Attempt 1 of 3: no fix.",
        "==GPS== Waiting 1.0 seconds before the next acquisition attempt.",
        "==GPS== Starting acquisition attempt 2 of 3",
        "==GPS== Attempt 2 of 3: no fix.",
        "==GPS== Waiting 2.0 seconds before the next acquisition attempt.",
        "==GPS== Starting acquisition attempt 3 of 3",
        "==GPS== Attempt 3 of 3: no fix.",
        "==GPS== No stable 3D fix or 2D position found after 3 attempts.",
    ]