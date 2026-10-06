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


def test_listener_waits_for_three_returned_fixes_and_averages_mixed_consensus(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 4, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 30.0, raising=False)
    sleep_delays = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    applied_changes = []
    live_changes = []
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )
    fixes = [
        gps_location.GPSFix(51.5, 179.8, None, 2),
        gps_location.GPSFix(51.6, -179.9, 10.0, 3),
        gps_location.GPSFix(51.7, 179.9, 14.0, 3),
    ]
    attempts = []

    async def get_gps_location(timeout, on_2d_fix=None):
        attempt_index = len(attempts)
        attempts.append(attempt_index)
        if on_2d_fix is not None:
            on_2d_fix(gps_location.GPSFix(0.0, 0.0, None, 2))
        assert applied_changes == []
        return fixes[attempt_index]

    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    polaris = SimpleNamespace(make_config_params_live=live_changes.append)

    asyncio.run(gps_location.gps_background_listener(polaris))

    assert attempts == [0, 1, 2]
    assert applied_changes == [{
        "site_latitude": pytest.approx(51.6),
        "site_longitude": pytest.approx(179.93333333333334),
        "location": "GPS Receiver",
        "site_elevation": 12,
    }]
    assert live_changes == applied_changes


def test_listener_retains_outliers_and_finds_a_later_triple(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 5, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    applied_changes = []
    fixes = [
        gps_location.GPSFix(0.0, 0.0, None, 2),
        gps_location.GPSFix(51.5, -0.12, None, 2),
        gps_location.GPSFix(20.0, 80.0, None, 2),
        gps_location.GPSFix(51.6, -0.1, None, 2),
        gps_location.GPSFix(51.7, -0.08, None, 2),
    ]
    attempts = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    async def get_gps_location(timeout, on_2d_fix=None):
        attempts.append(len(attempts))
        assert applied_changes == []
        return fixes[len(attempts) - 1]

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    asyncio.run(gps_location.gps_background_listener(SimpleNamespace(
        make_config_params_live=lambda changes: None
    )))

    assert attempts == [0, 1, 2, 3, 4]
    assert sleep_delays == pytest.approx([1.0, 2.0, 4.0, 4.0])
    assert applied_changes == [{
        "site_latitude": pytest.approx(51.6),
        "site_longitude": pytest.approx(-0.1),
        "location": "GPS Receiver",
    }]


def test_listener_waits_for_compatible_3d_altitude(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 5, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    applied_changes = []
    live_changes = []
    fixes = [
        gps_location.GPSFix(51.5, -0.12, None, 2),
        gps_location.GPSFix(51.6, -0.1, None, 3),
        gps_location.GPSFix(51.7, -0.08, None, 2),
        gps_location.GPSFix(54.0, -0.12, 100.0, 3),
        gps_location.GPSFix(51.6, -0.1, 35.7, 3),
    ]
    attempts = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    async def get_gps_location(timeout, on_2d_fix=None):
        attempts.append(len(attempts))
        if len(attempts) >= 4:
            assert applied_changes == [{
                "site_latitude": pytest.approx(51.6),
                "site_longitude": pytest.approx(-0.1),
                "location": "GPS Receiver",
            }]
        return fixes[len(attempts) - 1]

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )
    polaris = SimpleNamespace(make_config_params_live=live_changes.append)

    asyncio.run(gps_location.gps_background_listener(polaris))

    assert attempts == [0, 1, 2, 3, 4]
    assert sleep_delays == pytest.approx([1.0, 2.0, 4.0, 4.0])
    assert applied_changes == [
        {
            "site_latitude": pytest.approx(51.6),
            "site_longitude": pytest.approx(-0.1),
            "location": "GPS Receiver",
        },
        {"site_elevation": 36},
    ]
    assert live_changes == applied_changes


def test_listener_retains_horizontal_consensus_if_no_altitude_is_compatible(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 4, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    applied_changes = []
    fixes = [
        gps_location.GPSFix(51.5, -0.12, None, 2),
        gps_location.GPSFix(51.6, -0.1, None, 2),
        gps_location.GPSFix(51.7, -0.08, None, 2),
        gps_location.GPSFix(54.0, -0.12, 100.0, 3),
    ]

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    async def get_gps_location(timeout, on_2d_fix=None):
        return fixes.pop(0)

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    asyncio.run(gps_location.gps_background_listener(SimpleNamespace(
        make_config_params_live=lambda changes: None
    )))

    assert sleep_delays == pytest.approx([1.0, 2.0, 4.0])
    assert applied_changes == [{
        "site_latitude": pytest.approx(51.6),
        "site_longitude": pytest.approx(-0.1),
        "location": "GPS Receiver",
    }]
    assert "site_elevation" not in applied_changes[0]


def test_listener_leaves_config_untouched_without_horizontal_consensus(monkeypatch):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 2, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    applied_changes = []
    live_changes = []
    fixes = [
        gps_location.GPSFix(51.5, -0.12, None, 2),
        gps_location.GPSFix(51.6, -0.1, None, 2),
    ]

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    async def get_gps_location(timeout, on_2d_fix=None):
        return fixes.pop(0)

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location, "get_gps_location", get_gps_location)
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    asyncio.run(gps_location.gps_background_listener(SimpleNamespace(
        make_config_params_live=live_changes.append
    )))

    assert sleep_delays == pytest.approx([1.0])
    assert applied_changes == []
    assert live_changes == []


def test_listener_retries_connection_refused_without_mutating_config(monkeypatch, caplog):
    monkeypatch.setattr(Config, "gps_auto_detect", True, raising=False)
    monkeypatch.setattr(Config, "gps_max_attempts", 3, raising=False)
    monkeypatch.setattr(Config, "gps_retry_max_delay", 4.0, raising=False)
    sleep_delays = []
    connection_attempts = []
    applied_changes = []
    live_changes = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    async def refused_connection(host, port, *, limit):
        connection_attempts.append((host, port, limit))
        raise ConnectionRefusedError("gpsd unavailable")

    monkeypatch.setattr(gps_location, "_sleep", fake_sleep)
    monkeypatch.setattr(gps_location.asyncio, "open_connection", refused_connection)
    monkeypatch.setattr(
        Config,
        "apply_changes",
        classmethod(lambda cls, changes: applied_changes.append(dict(changes)) or dict(changes)),
    )

    with caplog.at_level(logging.INFO, logger="gps_location"):
        asyncio.run(gps_location.gps_background_listener(SimpleNamespace(
            make_config_params_live=live_changes.append
        )))

    info_records = [
        record for record in caplog.records
        if record.name == "gps_location" and record.levelno == logging.INFO
    ]
    assert connection_attempts == [
        (gps_location.GPSD_HOST, gps_location.GPSD_PORT, gps_location.GPSD_LINE_LIMIT)
    ] * 3
    assert sleep_delays == pytest.approx([1.0, 2.0])
    assert applied_changes == []
    assert live_changes == []
    assert [record.getMessage() for record in info_records] == [
        "==GPS== Waiting for gpsd fix",
        "==GPS== No fix after 3 attempts",
    ]