import asyncio
import json
import logging
import math
import sys
import struct
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))

import pytest

import gps_receiver
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


def _install_gpsd(monkeypatch, payload, *, feed_eof=True, host="127.0.0.1", port=2947):
    state = {}
    writer = FakeGPSDWriter()

    async def open_connection(actual_host, actual_port, *, limit):
        assert (actual_host, actual_port) == (host, port)
        assert limit == gps_receiver.GPSD_LINE_LIMIT
        reader = asyncio.StreamReader()
        reader.feed_data(payload)
        if feed_eof:
            reader.feed_eof()
        state["reader"] = reader
        return reader, writer

    monkeypatch.setattr(gps_receiver.asyncio, "open_connection", open_connection)
    return state, writer


def _report(**fields):
    return json.dumps(fields).encode("utf-8") + b"\n"


def _nmea(body):
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    return f"${body}*{checksum:02X}\r\n"


def _ubx_nav_sol(lat, lon, altitude):
    semi_major_axis = 6378137.0
    flattening = 1 / 298.257223563
    eccentricity_squared = flattening * (2 - flattening)
    latitude = math.radians(lat)
    longitude = math.radians(lon)
    prime_vertical_radius = semi_major_axis / math.sqrt(
        1 - eccentricity_squared * math.sin(latitude) ** 2
    )
    x = (prime_vertical_radius + altitude) * math.cos(latitude) * math.cos(longitude)
    y = (prime_vertical_radius + altitude) * math.cos(latitude) * math.sin(longitude)
    z = (prime_vertical_radius * (1 - eccentricity_squared) + altitude) * math.sin(latitude)

    payload = bytearray(52)
    payload[10] = 3  # 3D fix
    payload[11] = 1  # gpsFixOK
    for offset, coordinate in ((12, x), (16, y), (20, z)):
        payload[offset:offset + 4] = struct.pack("<i", round(coordinate * 100))

    frame = b"\xb5\x62\x01\x06" + len(payload).to_bytes(2, "little") + payload
    checksum_a = checksum_b = 0
    for value in frame[2:]:
        checksum_a = (checksum_a + value) & 0xFF
        checksum_b = (checksum_b + checksum_a) & 0xFF
    return frame + bytes((checksum_a, checksum_b))


def test_run_all_does_not_start_gps_at_startup(monkeypatch):
    import main

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

    asyncio.run(main.run_all(SimpleNamespace(info=lambda message: None), lifecycle))

    assert "GPSLocation" not in lifecycle.created_tasks


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
def test_parse_tpv_rejects_invalid_positions(report):
    assert gps_receiver._parse_tpv(report) is None


def test_parse_tpv_ignores_altitude_for_a_2d_fix():
    assert gps_receiver._parse_tpv({
        "mode": 2,
        "lat": 51.5,
        "lon": -0.12,
        "alt": 500,
    }) == gps_receiver.GPSFix(51.5, -0.12)


def test_gpsd_reads_a_3d_fix_and_closes_connection(monkeypatch):
    payload = b"".join([
        _report(**{"class": "VERSION", "release": "3.25"}),
        _report(**{
            "class": "TPV",
            "mode": 2,
            "lat": 51.5,
            "lon": -0.12,
            "time": "shared",
        }),
        _report(**{
            "class": "TPV",
            "mode": 3,
            "lat": 51.6,
            "lon": -0.1,
            "altMSL": 0,
            "time": "shared",
        }),
    ])
    _, writer = _install_gpsd(monkeypatch, payload)

    fix = asyncio.run(gps_receiver._read_gpsd_fix(
        1.0,
        {"gpsd_host": "127.0.0.1", "gpsd_port": 2947},
    ))

    assert fix == gps_receiver.GPSFix(51.6, -0.1, 0.0)
    assert bytes(writer.data) == b'?WATCH={"enable":true,"json":true}\n'
    assert writer.closed


def test_gpsd_skips_garbage_and_returns_a_2d_fix_at_eof(monkeypatch):
    payload = b"".join([
        b"not json\n",
        _report(**{"class": "TPV", "mode": 1, "lat": 0, "lon": 0}),
        _report(**{"class": "TPV", "mode": 2, "lat": 51.5, "lon": -0.12}),
    ])
    _install_gpsd(monkeypatch, payload)

    fix = asyncio.run(gps_receiver._read_gpsd_fix(1.0, {}))

    assert fix.latitude == pytest.approx(51.5)
    assert fix.longitude == pytest.approx(-0.12)


def test_gpsd_returns_a_2d_fix_after_read_timeout(monkeypatch):
    state, writer = _install_gpsd(
        monkeypatch,
        _report(**{"class": "TPV", "mode": 2, "lat": 51.5, "lon": -0.12}),
        feed_eof=False,
    )

    fix = asyncio.run(gps_receiver._read_gpsd_fix(0.02, {}))

    assert fix.latitude == pytest.approx(51.5)
    assert fix.longitude == pytest.approx(-0.12)
    assert not state["reader"].at_eof()
    assert writer.closed


def test_gpsd_times_out_on_a_partial_report(monkeypatch):
    state, _ = _install_gpsd(
        monkeypatch,
        _report(**{"class": "VERSION", "release": "3.25"}) + b'{"class":"TPV"',
        feed_eof=False,
    )

    fix = asyncio.run(gps_receiver._read_gpsd_fix(0.02, {}))

    assert fix is None
    assert not state["reader"].at_eof()


def test_gpsd_uses_configured_host_and_port(monkeypatch):
    host, port = "gps.example.test", 2948
    _install_gpsd(monkeypatch, b"", host=host, port=port)

    assert asyncio.run(gps_receiver._read_gpsd_fix(
        1.0,
        {"gpsd_host": host, "gpsd_port": port},
    )) is None


def test_gpsd_unreachable_fails_immediately_without_config_mutation(monkeypatch):
    attempts = []

    async def refused_connection(host, port, *, limit):
        attempts.append((host, port))
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(gps_receiver.asyncio, "open_connection", refused_connection)
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: pytest.fail("provider errors must not retry"))
    before = Config.as_dict()

    with pytest.raises(gps_receiver.GPSProviderError, match="GPSD is unavailable at 127.0.0.1:2947"):
        asyncio.run(gps_receiver.get_gps_location({
            "gps_provider": "gpsd",
            "gps_max_attempts": 5,
        }))

    assert attempts == [("127.0.0.1", 2947)]
    assert Config.as_dict() == before


@pytest.mark.parametrize(
    ("provider", "reader"),
    [
        ("nmea", "_read_nmea_fix"),
        ("ubx", "_read_ubx_fix"),
    ],
)
def test_shared_workflow_dispatches_selected_serial_provider(monkeypatch, provider, reader):
    calls = []

    async def read_fix(timeout, settings):
        calls.append((timeout, settings["gps_provider"]))
        return gps_receiver.GPSFix(51.5, -0.12, 35.0)

    monkeypatch.setattr(gps_receiver, reader, read_fix)
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    result = asyncio.run(gps_receiver.get_gps_location({
        "gps_provider": provider,
        "gps_max_attempts": 3,
    }))

    assert result.found
    assert result.attempts == 3
    assert calls == [(gps_receiver.GPS_ATTEMPT_TIMEOUT, provider)] * 3


@pytest.mark.parametrize(
    ("provider", "reader", "error"),
    [
        ("nmea", "_read_nmea_fix", "No valid GPS fix after 1 attempt."),
        ("ubx", "_read_ubx_fix", "No valid GPS fix after 1 attempt."),
    ],
)
def test_no_fix_error_counts_the_attempts(monkeypatch, provider, reader, error):
    async def no_fix(timeout, settings):
        return None

    monkeypatch.setattr(gps_receiver, reader, no_fix)

    result = asyncio.run(gps_receiver.get_gps_location({
        "gps_provider": provider,
        "gps_max_attempts": 1,
    }))

    assert result.fix is None
    assert result.attempts == 1
    assert result.error == error


def test_acquisition_progress_logs_at_debug(caplog):
    async def no_fix(timeout):
        return None

    with caplog.at_level(logging.DEBUG, logger="gps_receiver"):
        result = asyncio.run(gps_receiver.acquire_location(no_fix, max_attempts=1))

    assert result.fix is None
    records = [record for record in caplog.records if record.name == "gps_receiver"]
    assert records
    assert all(record.levelno == logging.DEBUG for record in records)


@pytest.mark.parametrize(
    "fix",
    [
        gps_receiver.GPSFix(math.nan, 0.0),
        gps_receiver.GPSFix(91.0, 0.0),
        gps_receiver.GPSFix(-91.0, 0.0),
        gps_receiver.GPSFix(0.0, math.inf),
        gps_receiver.GPSFix(0.0, 181.0),
        gps_receiver.GPSFix(True, 0.0),
        object(),
    ],
)
def test_acquisition_rejects_invalid_provider_fixes(monkeypatch, fix):
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def read_fix(timeout):
        return fix

    result = asyncio.run(gps_receiver.acquire_location(read_fix, max_attempts=3))

    assert result.fix is None
    assert result.attempts == 3


def test_acquisition_ignores_nonfinite_altitude(monkeypatch):
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def read_fix(timeout):
        return gps_receiver.GPSFix(51.5, -0.12, math.nan)

    result = asyncio.run(gps_receiver.acquire_location(read_fix, max_attempts=3))

    assert result.fix == gps_receiver.GPSFix(51.5, -0.12)


def test_retry_delay_doubles_to_the_configured_maximum():
    delays = [
        gps_receiver._retry_delay_after_attempt(index, gps_receiver.DEFAULT_GPS_RETRY_MAX_DELAY)
        for index in range(9)
    ]

    assert delays == [1.0, 1.0, 2.0, 2.0, 4.0, 4.0, 8.0, 8.0, 15.0]
    assert gps_receiver._retry_delay_after_attempt(10, 4.0) == 4.0


def test_shared_workflow_averages_three_compatible_fixes_across_dateline(monkeypatch):
    fixes = [
        gps_receiver.GPSFix(51.5000, 179.9995),
        gps_receiver.GPSFix(51.5005, -179.9995, 10.0),
        gps_receiver.GPSFix(51.5010, 179.9997, 14.0),
    ]
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def read_fix(timeout):
        return fixes.pop(0)

    result = asyncio.run(gps_receiver.acquire_location(read_fix, max_attempts=4))

    assert result.found
    assert result.attempts == 3
    assert result.fix.latitude == pytest.approx(51.5005)
    assert result.fix.longitude == pytest.approx(179.9999, abs=1e-6)
    assert result.fix.altitude == pytest.approx(12.0)


def test_shared_workflow_finds_consensus_after_outliers(monkeypatch):
    fixes = [
        gps_receiver.GPSFix(0.0, 0.0),
        gps_receiver.GPSFix(51.5000, -0.1002),
        gps_receiver.GPSFix(20.0, 80.0),
        gps_receiver.GPSFix(51.5005, -0.1000),
        gps_receiver.GPSFix(51.5010, -0.0998),
    ]
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def read_fix(timeout):
        return fixes.pop(0)

    result = asyncio.run(gps_receiver.acquire_location(read_fix, max_attempts=5))

    assert result.attempts == 5
    assert result.fix.latitude == pytest.approx(51.5005)
    assert result.fix.longitude == pytest.approx(-0.1)
    assert result.fix.altitude is None


def test_shared_workflow_searches_for_compatible_altitude(monkeypatch):
    fixes = [
        gps_receiver.GPSFix(51.5000, -0.1002),
        gps_receiver.GPSFix(51.5005, -0.1000),
        gps_receiver.GPSFix(51.5010, -0.0998),
        gps_receiver.GPSFix(54.0, -0.12, 100.0),
        gps_receiver.GPSFix(51.5005, -0.1000, 35.7),
    ]
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def read_fix(timeout):
        return fixes.pop(0)

    result = asyncio.run(gps_receiver.acquire_location(read_fix, max_attempts=5))

    assert result.attempts == 5
    assert result.fix.latitude == pytest.approx(51.5005)
    assert result.fix.longitude == pytest.approx(-0.1)
    assert result.fix.altitude == pytest.approx(35.7)


def test_no_fix_exhaustion_is_capped_at_twenty_and_does_not_mutate_config(monkeypatch):
    attempts = []
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    before = Config.as_dict()

    async def no_fix(timeout):
        attempts.append(timeout)
        return None

    result = asyncio.run(gps_receiver.acquire_location(no_fix, max_attempts=99))

    assert result.fix is None
    assert not result.found
    assert result.attempts == 20
    assert len(attempts) == 20
    assert Config.as_dict() == before


def test_no_fix_uses_configured_attempt_count(monkeypatch):
    attempts = []
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def no_fix(timeout):
        attempts.append(timeout)
        return None

    result = asyncio.run(gps_receiver.acquire_location(no_fix, max_attempts=3))

    assert result.attempts == 3
    assert len(attempts) == 3


def test_default_gps_attempt_count_is_five(monkeypatch):
    attempts = []
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def no_fix(timeout):
        attempts.append(timeout)
        return None

    result = asyncio.run(gps_receiver.acquire_location(no_fix))

    assert result.attempts == 5
    assert len(attempts) == 5


def test_shared_workflow_reports_attempt_progress(monkeypatch):
    progress = []
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))

    async def no_fix(timeout):
        return None

    result = asyncio.run(gps_receiver.acquire_location(
        no_fix,
        max_attempts=3,
        on_attempt=lambda attempt, total: progress.append((attempt, total)),
    ))

    assert result.attempts == 3
    assert progress == [(1, 3), (2, 3), (3, 3)]


def test_parse_gga_nmea_fix_with_altitude():
    fix = gps_receiver._parse_nmea_sentence(
        _nmea("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,")
    )

    assert fix.latitude == pytest.approx(48.1173)
    assert fix.longitude == pytest.approx(11.5166666667)
    assert fix.altitude == pytest.approx(545.4)


def test_parse_rmc_nmea_fix_without_altitude():
    fix = gps_receiver._parse_nmea_sentence(
        _nmea("GNRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,,,A")
    )

    assert fix.latitude == pytest.approx(48.1173)
    assert fix.longitude == pytest.approx(11.5166666667)
    assert fix.altitude is None


def test_serial_stream_parser_reads_nmea_fix():
    parser = gps_receiver._NMEAStreamParser()

    fixes = parser.feed(
        b"garbage" + _nmea("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,").encode()
    )

    assert len(fixes) == 1
    assert fixes[0].latitude == pytest.approx(48.1173)
    assert fixes[0].longitude == pytest.approx(11.5166666667)
    assert fixes[0].altitude == pytest.approx(545.4)


def test_serial_provider_reads_ubx_nav_sol_position(monkeypatch):
    frame = _ubx_nav_sol(51.5, -0.12, 35.0)

    class FakeSerial:
        def __init__(self, **kwargs):
            self.timeout = kwargs["timeout"]
            self.pending = frame

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, size):
            if self.pending:
                data, self.pending = self.pending[:size], self.pending[size:]
                return data
            return b""

        def readline(self):
            if self.pending:
                data, self.pending = self.pending, b""
                return data
            return b""

    monkeypatch.setattr(gps_receiver.serial, "Serial", FakeSerial)

    fix = asyncio.run(gps_receiver._read_ubx_fix(
        0.1,
        {"gps_serial_device": "/dev/ttyACM0", "gps_serial_baudrate": 9600},
    ))

    assert fix is not None
    assert fix.latitude == pytest.approx(51.5, abs=1e-5)
    assert fix.longitude == pytest.approx(-0.12, abs=1e-5)
    assert fix.altitude == pytest.approx(35.0, abs=0.02)


def test_serial_stream_parser_rejects_ubx_checksum_and_no_fix():
    frame = _ubx_nav_sol(51.5, -0.12, 35.0)
    parser = gps_receiver._UBXStreamParser()

    assert parser.feed(frame[:-1] + bytes((frame[-1] ^ 1,))) == []

    no_fix = bytearray(frame)
    no_fix[16] = 0
    checksum_a = checksum_b = 0
    for value in no_fix[2:-2]:
        checksum_a = (checksum_a + value) & 0xFF
        checksum_b = (checksum_b + checksum_a) & 0xFF
    no_fix[-2:] = bytes((checksum_a, checksum_b))
    assert parser.feed(bytes(no_fix)) == []


@pytest.mark.parametrize(
    "body",
    [
        "GPGGA,123519,,,,,,0,08,0.9,545.4,M,46.9,M,,",
        "GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,,,A",
        "GPGGA,123519,9100.000,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,",
    ],
)
def test_nmea_parser_rejects_no_fix_or_invalid_coordinates(body):
    assert gps_receiver._parse_nmea_sentence(_nmea(body)) is None


def test_nmea_parser_rejects_bad_checksum():
    sentence = _nmea("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,")

    assert gps_receiver._parse_nmea_sentence(sentence[:-4] + "00\r\n") is None


def test_serial_open_error_is_provider_specific(monkeypatch):
    device = "/dev/ttyUSB-test"

    def fail_open(**kwargs):
        raise gps_receiver.serial.SerialException("permission denied")

    monkeypatch.setattr(gps_receiver.serial, "Serial", fail_open)

    with pytest.raises(
        gps_receiver.GPSProviderError,
        match=r"Cannot open NMEA GPS serial device '/dev/ttyUSB-test' at 9600 baud: permission denied",
    ):
        asyncio.run(gps_receiver._read_nmea_fix(
            0.1,
            {"gps_serial_device": device, "gps_serial_baudrate": 9600},
        ))


def test_serial_configuration_error_is_immediate():
    with pytest.raises(gps_receiver.GPSProviderError, match="No GPS receiver serial port is chosen"):
        asyncio.run(gps_receiver._read_nmea_fix(
            0.1,
            {"gps_serial_device": "", "gps_serial_baudrate": 9600},
        ))

    with pytest.raises(gps_receiver.GPSProviderError, match="Invalid serial GPS baud rate"):
        asyncio.run(gps_receiver._read_nmea_fix(
            0.1,
            {"gps_serial_device": "/dev/ttyUSB0", "gps_serial_baudrate": 0},
        ))


def test_serial_provider_times_out_and_logs_when_no_data_arrives(monkeypatch, caplog):
    class EmptySerial:
        def __init__(self, **kwargs):
            self.timeout = kwargs["timeout"]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, size):
            time.sleep(self.timeout)
            return b""

    monkeypatch.setattr(gps_receiver.serial, "Serial", EmptySerial)
    monkeypatch.setattr(gps_receiver, "SERIAL_READ_TIMEOUT", 0.01)
    started_at = time.monotonic()

    with caplog.at_level(logging.DEBUG, logger="gps_receiver"):
        fix = asyncio.run(gps_receiver._read_nmea_fix(
            0.05,
            {"gps_serial_device": "/dev/ttyUSB-test", "gps_serial_baudrate": 9600},
        ))

    assert fix is None
    assert time.monotonic() - started_at < 0.5
    assert "No valid NMEA position fix received from /dev/ttyUSB-test" in caplog.text


def test_serial_blocking_read_runs_off_the_event_loop(monkeypatch):
    event_loop_thread = threading.get_ident()
    worker_threads = []

    def fake_read(device, baudrate, timeout, parser, protocol_name):
        worker_threads.append(threading.get_ident())
        return gps_receiver.GPSFix(51.5, -0.12)

    monkeypatch.setattr(gps_receiver, "_read_serial_fix", fake_read)
    fix = asyncio.run(gps_receiver._read_nmea_fix(0.1, {}))

    assert fix == gps_receiver.GPSFix(51.5, -0.12)
    assert worker_threads and worker_threads[0] != event_loop_thread


def _install_telescope_action(monkeypatch, action_name, parameters=" "):
    import exceptions
    import shr
    import telescope

    request = SimpleNamespace(context=SimpleNamespace(), method="PUT")
    response = SimpleNamespace(text=None)
    request_fields = {
        "Action": action_name,
        "Parameters": parameters,
        "ClientID": "1",
        "ClientTransactionID": "1",
    }

    async def get_request_field(name, req, *args, **kwargs):
        return request_fields.get(name, kwargs.get("default", "1"))

    async def log_request(*args, **kwargs):
        return None

    async def method_response(req, error=None):
        return error if error is not None else "ok"

    async def property_response(value, req, error=None):
        return value

    monkeypatch.setattr(telescope, "get_request_field", get_request_field)
    monkeypatch.setattr(telescope, "log_request", log_request)
    monkeypatch.setattr(telescope, "MethodResponse", method_response)
    monkeypatch.setattr(telescope, "PropertyResponse", property_response)
    monkeypatch.setattr(telescope, "logger", logging.getLogger("test_gps_location"))
    monkeypatch.setattr(shr, "get_request_field", get_request_field)
    monkeypatch.setattr(shr, "log_request", log_request)
    monkeypatch.setattr(exceptions, "logger", logging.getLogger("test_gps_location"))
    return telescope, request, response


class FakeGPSLifecycle:
    def __init__(self, running_task=None):
        self.running_task = running_task
        self.created_tasks = []

    def get_task(self, name):
        assert name == "GPSLocation"
        return self.running_task

    def create_task(self, coroutine, *, name):
        self.created_tasks.append(name)
        coroutine.close()


def test_gps_locate_action_schedules_async_work(monkeypatch):
    telescope, request, response = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    lifecycle = FakeGPSLifecycle()
    monkeypatch.setattr(telescope, "lifecycle", lifecycle)

    async def acquisition(settings):
        raise AssertionError("the action must schedule, not await, acquisition")

    monkeypatch.setattr(telescope, "get_gps_location", acquisition)
    monkeypatch.setitem(gps_receiver.locate_status, "run", 4)
    asyncio.run(telescope.action().on_put(request, response, 0))

    assert response.text == {"run": 5, "joined": False}        # a new Locate, numbered for Pilot to follow
    assert lifecycle.created_tasks == ["GPSLocation"]
    assert gps_receiver.locate_status["state"] == "running"


def test_gps_locate_action_joins_a_running_locate(monkeypatch):
    class RunningTask:
        def done(self):
            return False

    telescope, request, response = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    lifecycle = FakeGPSLifecycle(RunningTask())
    monkeypatch.setattr(telescope, "lifecycle", lifecycle)

    monkeypatch.setitem(gps_receiver.locate_status, "run", 7)
    asyncio.run(telescope.action().on_put(request, response, 0))

    assert response.text == {"run": 7, "joined": True}         # e.g. started from another Pilot window
    assert lifecycle.created_tasks == []


def test_supported_actions_publish_gps_locate_not_a_status_poll(monkeypatch):
    telescope, request, response = _install_telescope_action(
        monkeypatch,
        "Polaris:GpsLocate",
    )

    asyncio.run(telescope.supportedactions().on_get(request, response, 0))

    assert "Polaris:GpsLocate" in response.text
    assert "Polaris:SerialPorts" in response.text
    assert "Polaris:GPSLocationStatus" not in response.text     # progress is in the Polaris status (gpsstate, ...)
    assert "Polaris:PollGpsLocation" not in response.text


def test_gps_runner_preserves_config_on_provider_failure(monkeypatch, caplog):
    telescope, _, _ = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    monkeypatch.setattr(telescope, "polaris", SimpleNamespace())
    monkeypatch.setattr(telescope.Config, "as_dict", classmethod(lambda cls: {"gps_provider": "gpsd"}))

    async def provider_failure(settings, on_attempt=None):
        raise gps_receiver.GPSProviderError("GPSD is unavailable at 127.0.0.1:2947: refused")

    def unexpected_config_update(changes):
        pytest.fail("failed GPS acquisition must not update Config")

    monkeypatch.setattr(telescope, "get_gps_location", provider_failure)
    monkeypatch.setattr(telescope.Config, "apply_changes", unexpected_config_update)
    with caplog.at_level(logging.INFO, logger="test_gps_location"):
        asyncio.run(telescope._run_gps_location())

    assert gps_receiver.locate_status["state"] == "error"
    assert gps_receiver.locate_status["attempts"] == 0
    assert gps_receiver.locate_status["error"] == "GPSD is unavailable at 127.0.0.1:2947: refused"
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.INFO] == [
        "==GPS== Location detection result: failed: GPSD is unavailable at 127.0.0.1:2947: refused",
    ]


def test_gps_runner_reports_no_fix_attempt_count_without_config_mutation(monkeypatch, caplog):
    telescope, _, _ = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    monkeypatch.setattr(telescope, "polaris", SimpleNamespace())
    monkeypatch.setattr(telescope.Config, "as_dict", classmethod(lambda cls: {"gps_provider": "nmea"}))

    async def no_fix(settings, on_attempt=None):
        if on_attempt is not None:
            on_attempt(4, 4)
        return gps_receiver.GPSLocationResult(None, 4)

    def unexpected_config_update(changes):
        pytest.fail("no-fix outcome must not update Config")

    monkeypatch.setattr(telescope, "get_gps_location", no_fix)
    monkeypatch.setattr(telescope.Config, "apply_changes", unexpected_config_update)
    with caplog.at_level(logging.INFO, logger="test_gps_location"):
        asyncio.run(telescope._run_gps_location())

    assert gps_receiver.locate_status["state"] == "no_fix"
    assert gps_receiver.locate_status["attempts"] == 4
    assert gps_receiver.locate_status["error"] == "No valid GPS fix after 4 attempts."
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.INFO] == [
        "==GPS== Location detection result: No valid GPS fix after 4 attempts.",
    ]


def test_gps_runner_applies_successful_fix(monkeypatch, caplog):
    telescope, _, _ = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    live_changes = []

    monkeypatch.setattr(telescope, "polaris", SimpleNamespace(
        make_config_params_live=live_changes.append,
    ))
    monkeypatch.setattr(telescope.Config, "as_dict", classmethod(lambda cls: {"gps_provider": "gpsd"}))
    monkeypatch.setattr(telescope.Config, "get", classmethod(lambda cls, key: {
        "site_latitude": 1.0,
        "site_longitude": 2.0,
        "site_elevation": 3,
        "location": "Existing",
    }[key]))
    changes_seen = []

    def config_update(changes):
        changes_seen.append(dict(changes))
        return dict(changes)

    async def successful_fix(settings, on_attempt=None):
        if on_attempt is not None:
            on_attempt(3, 3)
        return gps_receiver.GPSLocationResult(
            gps_receiver.GPSFix(-33.8, 151.2, 39.6),
            3,
        )

    monkeypatch.setattr(telescope.Config, "apply_changes", config_update)
    monkeypatch.setattr(telescope, "get_gps_location", successful_fix)
    with caplog.at_level(logging.INFO, logger="test_gps_location"):
        asyncio.run(telescope._run_gps_location())

    expected = {
        "site_latitude": -33.8,
        "site_longitude": 151.2,
        "site_elevation": 40,
    }
    assert changes_seen == [expected]
    assert live_changes == [expected]
    assert gps_receiver.locate_status["state"] == "found"
    assert gps_receiver.locate_status["attempts"] == 3
    assert gps_receiver.locate_status["error"] is None
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.INFO] == [
        "==GPS== Location detection result: location applied after 3 attempts",
    ]


def test_gps_runner_keeps_elevation_when_success_has_no_altitude(monkeypatch):
    telescope, _, _ = _install_telescope_action(monkeypatch, "Polaris:GpsLocate")
    live_changes = []
    monkeypatch.setattr(telescope, "polaris", SimpleNamespace(
        make_config_params_live=live_changes.append,
    ))
    monkeypatch.setattr(telescope.Config, "as_dict", classmethod(lambda cls: {"gps_provider": "nmea"}))
    monkeypatch.setattr(telescope.Config, "get", classmethod(lambda cls, key: {
        "site_latitude": 1.0,
        "site_longitude": 2.0,
        "location": "Existing",
    }[key]))
    changes_seen = []

    def config_update(changes):
        changes_seen.append(dict(changes))
        return dict(changes)

    async def successful_2d_fix(settings, on_attempt=None):
        if on_attempt is not None:
            on_attempt(3, 3)
        return gps_receiver.GPSLocationResult(
            gps_receiver.GPSFix(-33.8, 151.2),
            3,
        )

    monkeypatch.setattr(telescope.Config, "apply_changes", config_update)
    monkeypatch.setattr(telescope, "get_gps_location", successful_2d_fix)
    asyncio.run(telescope._run_gps_location())

    assert len(changes_seen) == 1
    assert set(changes_seen[0]) == {"site_latitude", "site_longitude"}
    assert changes_seen[0]["site_latitude"] == -33.8
    assert changes_seen[0]["site_longitude"] == 151.2
    assert "site_elevation" not in live_changes[0]
    assert gps_receiver.locate_status["state"] == "found"


def test_config_fetch_does_not_probe_gpsd_or_return_runtime_status(monkeypatch):
    telescope, request, response = _install_telescope_action(
        monkeypatch,
        "Polaris:ConfigFetch",
        "{}",
    )
    monkeypatch.setattr(telescope.Config, "as_dict", classmethod(lambda cls: {}))
    monkeypatch.setattr(
        telescope,
        "polaris",
        SimpleNamespace(sitelatitude=1.0, sitelongitude=2.0, siteelevation=3.0),
    )

    asyncio.run(telescope.action().on_put(request, response, 0))

    assert response.text == {
        "site_latitude": 1.0,
        "site_longitude": 2.0,
        "site_elevation": 3.0,
    }
    assert "gpsd_listening" not in response.text


# ── a real u-blox puck on Windows (nina01, 2026-10-13): RMC before GGA, one open per Locate, ports listed ──────────
RMC = _nmea("GPRMC,105917.00,A,3339.31734,S,15107.33579,E,0.292,,131026,,,A")
GGA = _nmea("GPGGA,105917.00,3339.31734,S,15107.33579,E,1,06,1.47,188.1,M,19.9,M,,")


class ChunkSerial:
    """A serial port that hands out its chunks one read at a time; counts opens and closes."""
    opened = 0
    closed = 0
    fail_opens = 0

    def __init__(self, **kwargs):
        if ChunkSerial.fail_opens:
            ChunkSerial.fail_opens -= 1
            raise gps_receiver.serial.SerialException("PermissionError(13, 'A device attached ...')")
        ChunkSerial.opened += 1
        self.timeout = kwargs["timeout"]
        self.chunks = [RMC.encode(), GGA.encode()] * 50

    def read(self, size):
        return self.chunks.pop(0) if self.chunks else b""

    def close(self):
        ChunkSerial.closed += 1


@pytest.fixture
def chunk_serial(monkeypatch):
    ChunkSerial.opened = ChunkSerial.closed = ChunkSerial.fail_opens = 0
    monkeypatch.setattr(gps_receiver.serial, "Serial", ChunkSerial)
    monkeypatch.setattr(gps_receiver, "OPEN_RETRY_DELAY", 0.0)
    return ChunkSerial


def test_a_fix_without_altitude_waits_for_the_gga_that_follows(chunk_serial):
    """u-blox sends RMC (no altitude) before GGA: the reader returns the GGA, with the altitude."""
    fix = asyncio.run(gps_receiver._read_nmea_fix(2.0, {"gps_serial_device": "COM9"}))
    assert fix.altitude == pytest.approx(188.1)
    assert fix.latitude == pytest.approx(-33.6552890, abs=1e-6)


def test_one_locate_opens_the_port_once_and_closes_it(chunk_serial, monkeypatch):
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    result = asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM9"}))
    assert result.found and result.fix.altitude == pytest.approx(188.1)
    assert result.attempts == 3                          # three agreeing fixes, each with its altitude
    assert chunk_serial.opened == 1 and chunk_serial.closed == 1


def test_a_port_that_refuses_once_is_retried(chunk_serial):
    chunk_serial.fail_opens = 1                          # Windows PermissionError 13 on a busy hub, then fine
    fix = asyncio.run(gps_receiver._read_nmea_fix(2.0, {"gps_serial_device": "COM9"}))
    assert fix is not None and chunk_serial.opened == 1


def test_ports_are_listed_without_opening_them(monkeypatch):
    from serial.tools import list_ports
    port = lambda device, description, vid=None, pid=None: SimpleNamespace(
        device=device, description=description, vid=vid, pid=pid, manufacturer=None,
        hwid=f"USB VID:PID={vid}:{pid}" if vid else "")
    monkeypatch.setattr(list_ports, "comports", lambda: [
        port("COM9", "USB Serial Device (COM9)", 0x1546, 0x01A7),
        port("COM7", "USB-SERIAL CH340 (COM7)", 0x1A86, 0x7523),
        port("/dev/ttyS5", "n/a"),                                  # an empty legacy port: hidden
        port("/dev/ttyS0", "n/a"),                                  # a Pi's GPIO UART (GPS HAT): kept
    ])
    monkeypatch.setattr(gps_receiver.serial, "Serial", lambda **kw: pytest.fail("a port was opened"))
    telescope, request, response = _install_telescope_action(monkeypatch, "Polaris:SerialPorts")
    asyncio.run(telescope.action().on_put(request, response, 0))
    assert [p["device"] for p in response.text] == ["/dev/ttyS0", "COM7", "COM9"]
    assert response.text[2]["description"] == "USB Serial Device (COM9)" and response.text[2]["vid"] == 0x1546
    kinds = {p["device"]: (p["kind"], p["gps"]) for p in response.text}
    assert kinds["COM9"] == ("u-blox GPS receiver", True)               # the vendor only makes GPS receivers
    assert kinds["COM7"] == ("USB-serial adapter (CH340)", False)       # could be a GPS puck or a focuser: no guess
    assert kinds["/dev/ttyS0"] == ("Built-in serial port (GPIO UART)", False)


class ReconfigureCountingSerial(ChunkSerial):
    """pyserial reconfigures the port whenever its timeout is set after opening: count those."""
    reconfigured = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._opened = True

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        if getattr(self, "_opened", False):
            ReconfigureCountingSerial.reconfigured += 1
        self._timeout = value


def test_the_port_is_not_reconfigured_while_reading(chunk_serial, monkeypatch):
    """Windows: reconfiguring a u-blox port on every read eventually fails with error 31 (device not functioning)."""
    ReconfigureCountingSerial.reconfigured = 0
    monkeypatch.setattr(gps_receiver.serial, "Serial", ReconfigureCountingSerial)
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    result = asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM10"}))
    assert result.found
    assert ReconfigureCountingSerial.reconfigured == 0


class FailOnceSerial(ChunkSerial):
    """The first port opened fails on its first read (Windows error 31); later ones read normally."""
    failed = False

    def read(self, size):
        if not FailOnceSerial.failed:
            FailOnceSerial.failed = True
            raise gps_receiver.serial.SerialException(
                "Cannot configure port, something went wrong. Original message: PermissionError(13, "
                "'A device attached to the system is not functioning.', None, 31)")
        return super().read(size)


def test_a_port_that_fails_while_reading_is_reopened_for_the_next_attempt(chunk_serial, monkeypatch):
    FailOnceSerial.failed = False
    monkeypatch.setattr(gps_receiver.serial, "Serial", FailOnceSerial)
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    result = asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM10"}))
    assert result.found and result.attempts == 4         # one failed attempt, then three agreeing fixes
    assert chunk_serial.opened == 2 and chunk_serial.closed == 2   # the failed port closed, then the session's


NO_FIX_RMC = "$GPRMC,020359.00,V,,,,,,,141026,,,N*70\r\n"          # u-blox searching: void, no position
NO_FIX_GGA = "$GPGGA,020359.00,,,,,0,00,99.99,,,,,,*6B\r\n"        # quality 0, no satellites


class SearchingSerial(ChunkSerial):
    """A receiver that is talking but has no satellite fix (just plugged in, or no view of the sky)."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chunks = [NO_FIX_RMC.encode(), NO_FIX_GGA.encode()] * 5


class SilentSerial(ChunkSerial):
    """A port with nothing on it (the wrong port, or a wrong baud rate gives garbage at best)."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chunks = []


@pytest.mark.parametrize(("port_class", "reason"), [
    (SearchingSerial, "The receiver on COM10 is sending data but hasn't acquired satellites yet. Give it a clear"
                      " view of the sky; the first fix can take several minutes."),
    (SilentSerial, "No data from COM10. Check that it is the GPS receiver's port"),
])
def test_a_failed_locate_says_whether_the_receiver_has_no_fix_or_sends_nothing(
        chunk_serial, monkeypatch, port_class, reason):
    monkeypatch.setattr(gps_receiver.serial, "Serial", port_class)
    monkeypatch.setattr(gps_receiver, "SERIAL_READ_TIMEOUT", 0.01)
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    monkeypatch.setattr(gps_receiver, "GPS_ATTEMPT_TIMEOUT", 0.05)
    result = asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM10",
                                                        "gps_max_attempts": 2}))
    assert result.fix is None
    assert result.error.startswith("No valid GPS fix after 2 attempts.")
    assert reason in result.error


def test_a_locate_logs_what_it_uses(chunk_serial, monkeypatch, caplog):
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    with caplog.at_level(logging.INFO, logger="gps_receiver"):
        asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM10",
                                                   "gps_serial_baudrate": 9600, "gps_max_attempts": 10}))
    assert "==GPS== Locating with NMEA on COM10 at 9600 baud, up to 10 attempts" in caplog.text



@pytest.mark.parametrize("enabled", [True, False])
def test_log_gps_receiver_logs_the_sentences_and_each_attempt(chunk_serial, monkeypatch, caplog, enabled):
    monkeypatch.setattr(gps_receiver, "_sleep", lambda delay: asyncio.sleep(0))
    with caplog.at_level(logging.INFO, logger="gps_receiver"):
        asyncio.run(gps_receiver.get_gps_location({"gps_provider": "nmea", "gps_serial_device": "COM9",
                                                   "log_gps_receiver": enabled}))
    sentences = [r.getMessage() for r in caplog.records if r.getMessage().startswith("==GPS-NMEA== $GP")]
    attempts = [r.getMessage() for r in caplog.records if r.getMessage().startswith("==GPS-FIX== attempt")]
    if enabled:
        assert any("$GPGGA" in s for s in sentences) and any("$GPRMC" in s for s in sentences)
        assert attempts[0] == "==GPS-FIX== attempt 1/5: -33.655289, 151.122263, 188.1 m"
    else:
        assert sentences == [] and attempts == []
