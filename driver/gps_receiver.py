# -----------------------------------------------------------------------------
# gps_receiver.py - the observing site's location from a GPS receiver
# -----------------------------------------------------------------------------
#
# Pilot's Locate (location_source = 'gps') asks the driver for a fix: polls are repeated until three fixes agree
# (acquire_location), from the configured provider:
#
#   nmea   a receiver on a serial / USB port sending NMEA sentences (all platforms; u-blox send NMEA by default)
#   ubx    a u-blox receiver sending its binary UBX protocol
#   gpsd   the gpsd service, sharing one receiver between programs (Linux)
#
# Also lists the serial ports present (list_serial_ports, the Polaris:SerialPorts action), without opening them.
# The serial code is generic, so it can move to its own module when other serial devices arrive (LX200 / OnStepX).
#
# Sections: consensus | serial ports | serial reading | NMEA | UBX | gpsd | provider dispatch
# -----------------------------------------------------------------------------

import asyncio
import json
import logging
import math
import sys
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from itertools import combinations
from typing import Optional, Protocol

import serial

logger = logging.getLogger(__name__)

DEFAULT_GPS_MAX_ATTEMPTS = 5            # 3 agreeing fixes needed; a receiver with no fix gives up in ~1 min
MAX_GPS_ATTEMPTS = 20
DEFAULT_GPS_RETRY_MAX_DELAY = 15.0
GPS_ATTEMPT_TIMEOUT = 10.0
GPS_FIX_CONSENSUS_TOLERANCE_DEG = 0.002   # ~200 m: fixes of one receiver agree to metres (1.0 deg was ~111 km)


@dataclass(frozen=True)
class GPSFix:
    latitude: float
    longitude: float
    altitude: Optional[float] = None


@dataclass(frozen=True)
class GPSLocationResult:
    fix: Optional[GPSFix]
    attempts: int
    error: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.fix is not None


# The driver's GPS Locate, as Pilot sees it: sent in the Polaris status (gpsrun, gpsstate, gpsattempts, gpserror), so
# every Pilot window shows its progress and result. run counts Locates, so a window knows which result is the one it
# started or joined. state: idle | running | found | no_fix | error
locate_status = {"run": 0, "state": "idle", "attempts": 0, "error": None}

# log_gps_receiver: log what the receiver sends (NMEA sentences, UBX frames, GPSD reports) and each attempt's result,
# for diagnosing a receiver that gives no fix. Set from the config at the start of each Locate.
_log_receiver = False


def _log_traffic(protocol: str, message: str) -> None:
    if _log_receiver:
        logger.info("==GPS-%s== %s", protocol, message)


class GPSProviderError(Exception):
    """An immediate, provider-specific acquisition or configuration failure."""


GPSFixReader = Callable[[float], Awaitable[Optional[GPSFix]]]
GPSAttemptCallback = Callable[[int, int], None]


def _finite_float(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _validated_fix(fix: object) -> Optional[GPSFix]:
    if not isinstance(fix, GPSFix):
        return None

    latitude = _finite_float(fix.latitude)
    longitude = _finite_float(fix.longitude)
    if (
        latitude is None
        or longitude is None
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None

    return GPSFix(latitude, longitude, _finite_float(fix.altitude))


def _configured_attempts(value) -> int:
    if isinstance(value, bool):
        attempts = DEFAULT_GPS_MAX_ATTEMPTS
    else:
        try:
            attempts = int(value)
        except (TypeError, ValueError, OverflowError):
            attempts = DEFAULT_GPS_MAX_ATTEMPTS

    bounded_attempts = min(MAX_GPS_ATTEMPTS, max(1, attempts))
    if bounded_attempts != attempts:
        logger.debug("==GPS== Clamped gps_max_attempts from %r to %d", value, bounded_attempts)
    return bounded_attempts


def _configured_retry_max_delay(value) -> float:
    delay = _finite_float(value)
    if delay is None or delay <= 0:
        logger.debug(
            "==GPS== Invalid gps_retry_max_delay %r; using %.1f seconds",
            value,
            DEFAULT_GPS_RETRY_MAX_DELAY,
        )
        return DEFAULT_GPS_RETRY_MAX_DELAY
    return delay


def _retry_delay_after_attempt(attempt_index: int, max_delay: float) -> float:
    return min(2.0 ** (attempt_index // 2), max_delay)


def _average_fixes(fixes: list[GPSFix]) -> GPSFix:
    latitude = sum(fix.latitude for fix in fixes) / len(fixes)
    longitude_sine = sum(math.sin(math.radians(fix.longitude)) for fix in fixes)
    longitude_cosine = sum(math.cos(math.radians(fix.longitude)) for fix in fixes)
    if math.isclose(longitude_sine, 0.0, abs_tol=1e-12) and math.isclose(longitude_cosine, 0.0, abs_tol=1e-12):
        longitude = fixes[-1].longitude
    else:
        longitude = math.degrees(math.atan2(longitude_sine, longitude_cosine))

    altitudes = [fix.altitude for fix in fixes if fix.altitude is not None]
    altitude = sum(altitudes) / len(altitudes) if altitudes else None
    return GPSFix(latitude, longitude, altitude)


def _angular_distance_degrees(first: GPSFix, second: GPSFix) -> float:
    latitude1 = math.radians(first.latitude)
    latitude2 = math.radians(second.latitude)
    delta_latitude = latitude2 - latitude1
    delta_longitude = math.radians(second.longitude - first.longitude)
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude1) * math.cos(latitude2) * math.sin(delta_longitude / 2) ** 2
    )
    return math.degrees(2 * math.asin(math.sqrt(min(1.0, haversine))))


async def _sleep(delay: float) -> None:
    await asyncio.sleep(delay)


async def acquire_location(
    read_fix: GPSFixReader,
    *,
    max_attempts=DEFAULT_GPS_MAX_ATTEMPTS,
    retry_max_delay=DEFAULT_GPS_RETRY_MAX_DELAY,
    attempt_timeout: Optional[float] = None,
    on_attempt: Optional[GPSAttemptCallback] = None,
) -> GPSLocationResult:
    """Acquire a three-fix consensus without changing application configuration."""
    attempts = _configured_attempts(max_attempts)
    if attempt_timeout is None:
        attempt_timeout = GPS_ATTEMPT_TIMEOUT          # read at call time (tests shorten it)
    retry_delay_cap = _configured_retry_max_delay(retry_max_delay)
    fix_history: list[GPSFix] = []
    consensus: Optional[tuple[GPSFix, GPSFix, GPSFix]] = None
    consensus_fix: Optional[GPSFix] = None
    consensus_altitudes: list[float] = []

    for attempt_index in range(attempts):
        attempt_number = attempt_index + 1
        if on_attempt is not None:
            on_attempt(attempt_number, attempts)
        logger.debug("==GPS== Starting acquisition attempt %d/%d", attempt_number, attempts)
        attempt_started_at = asyncio.get_running_loop().time()
        raw_fix = await read_fix(attempt_timeout)
        fix = _validated_fix(raw_fix)
        if fix is None:
            _log_traffic("FIX", f"attempt {attempt_number}/{attempts}: no fix")
        else:
            altitude = "no altitude" if fix.altitude is None else f"{fix.altitude:.1f} m"
            _log_traffic("FIX", f"attempt {attempt_number}/{attempts}: {fix.latitude:.6f}, {fix.longitude:.6f}, {altitude}")
        if raw_fix is not None and fix is None:
            logger.debug(
                "==GPS== Rejected invalid fix in acquisition attempt %d/%d",
                attempt_number,
                attempts,
            )
        elif raw_fix is not None and raw_fix.altitude is not None and fix.altitude is None:
            logger.debug(
                "==GPS== Ignoring invalid altitude in acquisition attempt %d/%d",
                attempt_number,
                attempts,
            )
        elapsed = asyncio.get_running_loop().time() - attempt_started_at
        if fix is not None:
            fix_history.append(fix)
            logger.debug(
                "==GPS== Attempt %d/%d returned a fix in %.1f seconds",
                attempt_number,
                attempts,
                elapsed,
            )

            if consensus is None:
                for first_fix, second_fix in combinations(fix_history[:-1], 2):
                    triple = (first_fix, second_fix, fix)
                    if all(
                        _angular_distance_degrees(first, second)
                        <= GPS_FIX_CONSENSUS_TOLERANCE_DEG
                        for first, second in combinations(triple, 2)
                    ):
                        consensus = triple
                        consensus_fix = _average_fixes(list(triple))
                        consensus_altitudes = [
                            item.altitude
                            for item in triple
                            if item.altitude is not None
                        ]
                        if consensus_altitudes:
                            averaged = GPSFix(
                                consensus_fix.latitude,
                                consensus_fix.longitude,
                                sum(consensus_altitudes) / len(consensus_altitudes),
                            )
                            return GPSLocationResult(averaged, attempt_number)
                        break
            elif (
                fix.altitude is not None
                and all(
                    _angular_distance_degrees(consensus_fix, fix)
                    <= GPS_FIX_CONSENSUS_TOLERANCE_DEG
                    for consensus_fix in consensus
                )
            ):
                altitudes = [*consensus_altitudes, fix.altitude]
                averaged = GPSFix(
                    consensus_fix.latitude,
                    consensus_fix.longitude,
                    sum(altitudes) / len(altitudes),
                )
                return GPSLocationResult(averaged, attempt_number)
        else:
            logger.debug(
                "==GPS== Attempt %d/%d returned no fix in %.1f seconds",
                attempt_number,
                attempts,
                elapsed,
            )

        if attempt_index + 1 < attempts:
            delay = _retry_delay_after_attempt(attempt_index, retry_delay_cap)
            logger.debug("==GPS== Waiting %.1f seconds before the next attempt", delay)
            await _sleep(delay)

    if consensus_fix is None:
        return GPSLocationResult(None, attempts)

    return GPSLocationResult(consensus_fix, attempts)

# -----------------------------------------------------------------------------
# Serial ports: listed for Pilot, never opened (opening can reset a device such as a focuser)
#
#   Windows   COM ports, as Device Manager shows them
#   Linux     /dev/ttyACM* (native USB, e.g. a u-blox GPS), /dev/ttyUSB* (USB bridges, e.g. CH340); the empty legacy
#             /dev/ttyS* ports are left out, except /dev/ttyS0 and /dev/ttyAMA* (a Raspberry Pi's GPIO UART: GPS HATs)
#   macOS     /dev/cu.* only (the /dev/tty.* twin can block when opened)
# -----------------------------------------------------------------------------

# What the USB vendor:product ID says the device is, so Pilot can show more than "USB Serial Device (COM9)".
# gps=True only for vendors that make GPS receivers alone; a USB-serial bridge (CH340, CP210x, FTDI, Prolific)
# could be a GPS puck, a focuser or anything else, so it is named but not guessed at.
USB_KINDS = {
    0x1546: ("u-blox GPS receiver", True),
    0x091E: ("Garmin GPS receiver", True),
    0x1A86: ("USB-serial adapter (CH340)", False),
    0x10C4: ("USB-serial adapter (CP210x)", False),
    0x0403: ("USB-serial adapter (FTDI)", False),
    0x067B: ("USB-serial adapter (Prolific)", False),
    0x2341: ("Arduino", False),
    0x2E8A: ("Raspberry Pi Pico", False),
}


def describe_port(device, vid):
    """(kind, gps) for a port: what the device is, and whether it is almost certainly a GPS receiver."""
    if vid in USB_KINDS:
        return USB_KINDS[vid]
    if device.startswith(('/dev/ttyAMA', '/dev/ttyS0', '/dev/serial0')):
        return ("Built-in serial port (GPIO UART)", False)
    return ("USB serial device" if vid is not None else "Serial port", False)


def list_serial_ports():
    """[{device, description, kind, gps, manufacturer, vid, pid, hwid}] for the serial ports present, sorted by device
    ([] without pyserial)."""
    try:
        from serial.tools import list_ports
        found = list_ports.comports()
    except Exception as error:                      # pyserial missing, or the platform can't enumerate
        logger.info("Cannot list serial ports: %s", error)
        return []
    ports = []
    for port in sorted(found, key=lambda p: p.device):
        if sys.platform == 'darwin' and port.device.startswith('/dev/tty.'):
            continue
        if (port.description in ('', 'n/a', None) and port.vid is None
                and not port.device.startswith(('/dev/ttyAMA', '/dev/ttyS0'))):
            continue
        kind, gps = describe_port(port.device, port.vid)
        ports.append({"device": port.device, "description": port.description or "", "kind": kind, "gps": gps,
                      "manufacturer": port.manufacturer or "",
                      "vid": port.vid, "pid": port.pid, "hwid": port.hwid or ""})
    return ports

# -----------------------------------------------------------------------------
# Serial reading: one open port per Locate, shared by the NMEA and UBX providers
# -----------------------------------------------------------------------------

DEFAULT_SERIAL_DEVICE = "/dev/ttyUSB0"
DEFAULT_SERIAL_BAUDRATE = 9600
SERIAL_READ_TIMEOUT = 1.0
OPEN_RETRIES = 3              # a port that fails to open is retried (Windows: a USB GPS on a busy hub can refuse
OPEN_RETRY_DELAY = 0.5        # once with PermissionError 13, then open fine)
ALTITUDE_GRACE = 1.5          # after a fix without altitude (RMC), wait this long for one with it (GGA follows it)

# One Locate keeps its port open across attempts (serial_session): reopening it for every attempt stalled the
# driver's event loop on Windows and, once, left the port refusing to reopen
_session_active = False
_sessions: dict = {}
_received: dict[str, bool] = {}    # per port this Locate: did it send anything? (no fix vs no data, in the error)


class serial_session:
    """Keep serial ports open for one acquisition (all its attempts), and close them at the end."""
    def __enter__(self):
        global _session_active
        _session_active = True
        _received.clear()
        return self

    def __exit__(self, *_):
        global _session_active
        _session_active = False
        for connection in list(_sessions.values()):
            try:
                connection.close()
            except Exception:
                pass
        _sessions.clear()
        return False


def _open_serial(device: str, baudrate: int, timeout: float):
    key = (device, baudrate)
    if _session_active and key in _sessions:
        return _sessions[key]
    error = None
    for attempt in range(OPEN_RETRIES):
        try:
            connection = serial.Serial(port=device, baudrate=baudrate, timeout=timeout)
            if _session_active:
                _sessions[key] = connection
            return connection
        except (serial.SerialException, OSError, ValueError) as caught:
            error = caught
            if attempt + 1 < OPEN_RETRIES:
                logger.debug("==GPS-SERIAL== Opening %s failed (%s), retrying", device, caught)
                time.sleep(OPEN_RETRY_DELAY)
    raise error


def _discard_session_port(device: str, baudrate: int, connection) -> None:
    """Forget and close a port that failed, rather than keep reading a broken connection."""
    if _sessions.get((device, baudrate)) is connection:
        del _sessions[(device, baudrate)]
    try:
        connection.close()
    except Exception:
        pass


class GPSStreamParser(Protocol):
    def feed(self, data: bytes) -> list[GPSFix]: ...


ParserFactory = Callable[[], GPSStreamParser]


def _configured_serial(
    settings: Mapping[str, object],
    protocol_name: str,
) -> tuple[str, int]:
    raw_device = settings.get("gps_serial_device", DEFAULT_SERIAL_DEVICE)
    if not isinstance(raw_device, str) or not raw_device.strip():
        raise GPSProviderError(
            "No GPS receiver serial port is chosen. Choose it in Pilot's GPS Receiver settings (beside Locate)."
        )

    raw_baudrate = settings.get("gps_serial_baudrate", DEFAULT_SERIAL_BAUDRATE)
    if isinstance(raw_baudrate, bool):
        raise GPSProviderError(f"Invalid serial GPS baud rate: {raw_baudrate!r}.")
    try:
        baudrate = int(raw_baudrate)
    except (TypeError, ValueError, OverflowError) as error:
        raise GPSProviderError(f"Invalid serial GPS baud rate: {raw_baudrate!r}.") from error
    if (isinstance(raw_baudrate, float) and raw_baudrate != baudrate) or baudrate <= 0:
        raise GPSProviderError(f"Invalid serial GPS baud rate: {raw_baudrate!r}.")
    return raw_device.strip(), baudrate


def _read_serial_fix(
    device: str,
    baudrate: int,
    timeout: float,
    parser: GPSStreamParser,
    protocol_name: str,
) -> Optional[GPSFix]:
    logger.debug(
        "==GPS-SERIAL== Reading %s from %s at %d baud (%.1fs attempt timeout)",
        protocol_name,
        device,
        baudrate,
        timeout,
    )
    try:
        connection = _open_serial(device, baudrate, min(SERIAL_READ_TIMEOUT, timeout))
    except (serial.SerialException, OSError, ValueError) as error:
        raise GPSProviderError(
            f"Cannot open {protocol_name} GPS serial device '{device}' at {baudrate} baud: {error}"
        ) from error
    try:
        deadline = time.monotonic() + timeout
        without_altitude = None              # a fix without altitude (e.g. RMC), kept in case no GGA follows
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if without_altitude is not None:
                    return without_altitude
                logger.debug(
                    "==GPS-SERIAL== No valid %s position fix received from %s",
                    protocol_name,
                    device,
                )
                return None
            # the read timeout is set once, at open: setting it here reconfigures the port on every read (pyserial),
            # which a u-blox on a busy Windows USB hub eventually refuses ("device ... not functioning", error 31)
            chunk = connection.read(256)
            if not chunk:
                _received.setdefault(device, False)
                continue
            _received[device] = True
            fixes = parser.feed(chunk)
            if not fixes:
                continue
            with_altitude = next((fix for fix in fixes if fix.altitude is not None), None)
            if with_altitude is not None:
                logger.debug("==GPS-SERIAL== Read a valid %s position fix from %s", protocol_name, device)
                return with_altitude
            if without_altitude is None:     # prefer the GGA that follows an RMC: it carries the altitude
                deadline = min(deadline, time.monotonic() + ALTITUDE_GRACE)
            without_altitude = fixes[-1]
    except (serial.SerialException, OSError) as error:
        # one failed attempt, not a failed Locate: the next attempt reopens the port (and if it cannot be reopened,
        # that open error ends the Locate)
        logger.info("==GPS== %s GPS serial device '%s' failed, reopening it: %s", protocol_name, device, error)
        _discard_session_port(device, baudrate, connection)
        return None
    finally:
        if not _session_active:
            close = getattr(connection, "close", None)
            if close is not None:
                close()


async def get_serial_gps_location(
    timeout: float,
    settings: Mapping[str, object],
    parser_factory: ParserFactory,
    protocol_name: str,
) -> Optional[GPSFix]:
    device, baudrate = _configured_serial(settings, protocol_name)
    try:
        timeout = float(timeout)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(timeout) or timeout <= 0:
        return None

    return await asyncio.to_thread(
        _read_serial_fix,
        device,
        baudrate,
        timeout,
        parser_factory(),
        protocol_name,
    )

# -----------------------------------------------------------------------------
# NMEA provider
# -----------------------------------------------------------------------------

MAX_NMEA_LINE_LENGTH = 1024


def _coordinate(value: str, hemisphere: str, degrees_digits: int, limit: int) -> Optional[float]:
    try:
        raw = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(raw) or raw < 0:
        return None

    degrees = int(raw // 100)
    minutes = raw - degrees * 100
    if minutes >= 60 or degrees > limit or (degrees == limit and minutes > 0):
        return None
    if len(str(degrees)) > degrees_digits:
        return None

    if hemisphere in ("N", "E"):
        return degrees + minutes / 60
    if hemisphere in ("S", "W"):
        return -(degrees + minutes / 60)
    return None


def _checksum_is_valid(sentence: str, checksum: str) -> bool:
    if len(checksum) < 2:
        return False
    try:
        expected = int(checksum[:2], 16)
    except ValueError:
        return False

    actual = 0
    for character in sentence[1:]:
        actual ^= ord(character)
    return actual == expected


def _parse_nmea_sentence(line: str) -> Optional[GPSFix]:
    sentence, separator, checksum = line.strip().partition("*")
    if not sentence.startswith("$"):
        return None
    if separator and not _checksum_is_valid(sentence, checksum):
        return None

    fields = sentence[1:].split(",")
    if not fields:
        return None
    sentence_type = fields[0][-3:]

    if sentence_type == "GGA":
        if len(fields) < 7:
            return None
        try:
            fix_quality = int(fields[6])
        except (TypeError, ValueError, OverflowError):
            return None
        if fix_quality <= 0:
            return None
        latitude = _coordinate(fields[2], fields[3], 2, 90)
        longitude = _coordinate(fields[4], fields[5], 3, 180)
        altitude = None
        if len(fields) > 10 and fields[10] == "M":
            try:
                candidate = float(fields[9])
            except (TypeError, ValueError, OverflowError):
                candidate = math.nan
            if math.isfinite(candidate):
                altitude = candidate
    elif sentence_type == "RMC":
        if len(fields) < 7 or fields[2] != "A":
            return None
        latitude = _coordinate(fields[3], fields[4], 2, 90)
        longitude = _coordinate(fields[5], fields[6], 3, 180)
        altitude = None
    else:
        return None

    if latitude is None or longitude is None:
        return None
    return GPSFix(latitude, longitude, altitude)


class _NMEAStreamParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[GPSFix]:
        self.buffer.extend(data)
        fixes = []
        while True:
            newline = self.buffer.find(b"\n")
            sentence_start = self.buffer.find(b"$")
            if newline < 0:
                if sentence_start > 0:
                    del self.buffer[:sentence_start]
                if len(self.buffer) > MAX_NMEA_LINE_LENGTH:
                    self.buffer.clear()
                break
            if sentence_start < 0 or sentence_start > newline:
                del self.buffer[:newline + 1]
                continue
            if sentence_start > 0:
                del self.buffer[:sentence_start]
                newline -= sentence_start
            raw_line = bytes(self.buffer[:newline + 1])
            del self.buffer[:newline + 1]
            try:
                line = raw_line.decode("ascii").strip()
            except UnicodeDecodeError:
                continue
            _log_traffic("NMEA", line)
            fix = _parse_nmea_sentence(line)
            if fix is not None:
                fixes.append(fix)
        return fixes


async def _read_nmea_fix(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
    return await get_serial_gps_location(
        timeout,
        settings,
        _NMEAStreamParser,
        "NMEA",
    )

# -----------------------------------------------------------------------------
# UBX provider
# -----------------------------------------------------------------------------

MAX_UBX_PAYLOAD_LENGTH = 1024

WGS84_SEMI_MAJOR_AXIS = 6378137.0
WGS84_FLATTENING = 1 / 298.257223563
WGS84_ECCENTRICITY_SQUARED = WGS84_FLATTENING * (2 - WGS84_FLATTENING)


def _ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    semi_minor_axis = WGS84_SEMI_MAJOR_AXIS * (1 - WGS84_FLATTENING)
    second_eccentricity_squared = (
        WGS84_SEMI_MAJOR_AXIS**2 - semi_minor_axis**2
    ) / semi_minor_axis**2
    horizontal_distance = math.hypot(x, y)
    longitude = math.atan2(y, x)
    theta = math.atan2(z * WGS84_SEMI_MAJOR_AXIS, horizontal_distance * semi_minor_axis)
    latitude = math.atan2(
        z + second_eccentricity_squared * semi_minor_axis * math.sin(theta) ** 3,
        horizontal_distance
        - WGS84_ECCENTRICITY_SQUARED * WGS84_SEMI_MAJOR_AXIS * math.cos(theta) ** 3,
    )
    prime_vertical_radius = WGS84_SEMI_MAJOR_AXIS / math.sqrt(
        1 - WGS84_ECCENTRICITY_SQUARED * math.sin(latitude) ** 2
    )
    if math.isclose(math.cos(latitude), 0.0, abs_tol=1e-12):
        altitude = abs(z) - semi_minor_axis
    else:
        altitude = horizontal_distance / math.cos(latitude) - prime_vertical_radius
    return math.degrees(latitude), math.degrees(longitude), altitude


def _parse_ubx_frame(frame: bytes) -> Optional[GPSFix]:
    if len(frame) < 8 or frame[:2] != b"\xb5\x62":
        return None
    payload_length = int.from_bytes(frame[4:6], "little")
    if len(frame) != payload_length + 8:
        return None

    checksum_a = checksum_b = 0
    for value in frame[2:-2]:
        checksum_a = (checksum_a + value) & 0xFF
        checksum_b = (checksum_b + checksum_a) & 0xFF
    if (checksum_a, checksum_b) != (frame[-2], frame[-1]):
        return None

    payload = frame[6:-2]
    if frame[2:4] == b"\x01\x06" and len(payload) >= 24:
        fix_type, flags = payload[10], payload[11]
        if fix_type < 2 or not flags & 0x01:
            return None
        ecef_cm = (
            int.from_bytes(payload[12:16], "little", signed=True),
            int.from_bytes(payload[16:20], "little", signed=True),
            int.from_bytes(payload[20:24], "little", signed=True),
        )
        latitude, longitude, ellipsoid_altitude = _ecef_to_geodetic(
            *(coordinate / 100 for coordinate in ecef_cm)
        )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return None
        return GPSFix(
            latitude,
            longitude,
            ellipsoid_altitude if fix_type >= 3 else None,
        )

    if frame[2:4] == b"\x01\x07" and len(payload) >= 40:
        fix_type, flags = payload[20], payload[21]
        if fix_type < 2 or not flags & 0x01:
            return None
        longitude = int.from_bytes(payload[24:28], "little", signed=True) * 1e-7
        latitude = int.from_bytes(payload[28:32], "little", signed=True) * 1e-7
        msl_altitude = int.from_bytes(payload[36:40], "little", signed=True) / 1000
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return None
        return GPSFix(latitude, longitude, msl_altitude)

    return None


class _UBXStreamParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[GPSFix]:
        self.buffer.extend(data)
        fixes = []
        while self.buffer:
            if self.buffer.startswith(b"\xb5"):
                if len(self.buffer) < 2:
                    break
                if self.buffer[1] != 0x62:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 6:
                    break
                payload_length = int.from_bytes(self.buffer[4:6], "little")
                if payload_length > MAX_UBX_PAYLOAD_LENGTH:
                    del self.buffer[:2]
                    continue
                frame_length = payload_length + 8
                if len(self.buffer) < frame_length:
                    break
                frame = bytes(self.buffer[:frame_length])
                del self.buffer[:frame_length]
                _log_traffic("UBX", f"class 0x{frame[2]:02X} id 0x{frame[3]:02X} ({payload_length} bytes) {frame.hex()}")
                fix = _parse_ubx_frame(frame)
                if fix is not None:
                    fixes.append(fix)
                continue

            ubx_start = self.buffer.find(b"\xb5\x62")
            if ubx_start >= 0:
                del self.buffer[:ubx_start]
            else:
                keep_sync_prefix = self.buffer[-1:] == b"\xb5"
                self.buffer[:] = b"\xb5" if keep_sync_prefix else b""
                break
        return fixes


async def _read_ubx_fix(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
    return await get_serial_gps_location(
        timeout,
        settings,
        _UBXStreamParser,
        "UBX",
    )

# -----------------------------------------------------------------------------
# gpsd provider
# -----------------------------------------------------------------------------

GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947
GPSD_LINE_LIMIT = 65536
GPSD_CONNECT_TIMEOUT = 2.0
GPSD_READ_TIMEOUT = 2.0
GPSD_FIX_SAMPLES = 3


def _parse_tpv(report: dict) -> Optional[GPSFix]:
    raw_mode = report.get("mode")
    if isinstance(raw_mode, bool):
        return None
    try:
        mode = int(raw_mode)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(raw_mode, float) and not raw_mode.is_integer():
        return None
    if mode < 2:
        return None

    latitude = _finite_float(report.get("lat"))
    longitude = _finite_float(report.get("lon"))
    if latitude is None or longitude is None:
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None

    altitude = None
    if mode >= 3:
        raw_altitude = report.get("altMSL")
        if raw_altitude is None:
            raw_altitude = report.get("alt")
        altitude = _finite_float(raw_altitude)

    return GPSFix(latitude, longitude, altitude)


def _configured_endpoint(settings: Mapping[str, object]) -> tuple[str, int]:
    raw_host = settings.get("gpsd_host", GPSD_HOST)
    if not isinstance(raw_host, str) or not raw_host.strip():
        raise GPSProviderError("No GPSD host is set. Set it in Pilot's GPS Receiver settings (beside Locate).")

    raw_port = settings.get("gpsd_port", GPSD_PORT)
    if isinstance(raw_port, bool):
        raise GPSProviderError(f"Invalid GPSD port: {raw_port!r}.")
    try:
        port = int(raw_port)
    except (TypeError, ValueError, OverflowError) as error:
        raise GPSProviderError(f"Invalid GPSD port: {raw_port!r}.") from error
    if (isinstance(raw_port, float) and raw_port != port) or not 1 <= port <= 65535:
        raise GPSProviderError(f"Invalid GPSD port: {raw_port!r}.")
    return raw_host.strip(), port


async def _read_gpsd_fix(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
    host, port = _configured_endpoint(settings)
    try:
        timeout = float(timeout)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(timeout) or timeout <= 0:
        return None

    deadline = asyncio.get_running_loop().time() + timeout
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, limit=GPSD_LINE_LIMIT),
            timeout=min(GPSD_CONNECT_TIMEOUT, timeout),
        )
    except asyncio.CancelledError:
        raise
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        raise GPSProviderError(f"GPSD is unavailable at {host}:{port}: {error}") from error

    fixes: list[GPSFix] = []
    seen_timestamps = set()
    try:
        try:
            writer.write(b'?WATCH={"enable":true,"json":true}\n')
            await asyncio.wait_for(
                writer.drain(),
                timeout=min(GPSD_CONNECT_TIMEOUT, max(0.0, deadline - asyncio.get_running_loop().time())),
            )
        except asyncio.CancelledError:
            raise
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            raise GPSProviderError(f"GPSD connection at {host}:{port} failed: {error}") from error

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                line = await asyncio.wait_for(
                    reader.readline(),
                    timeout=min(GPSD_READ_TIMEOUT, remaining),
                )
            except TimeoutError:
                if asyncio.get_running_loop().time() >= deadline:
                    break
                continue
            except asyncio.CancelledError:
                raise
            except (OSError, RuntimeError, ValueError) as error:
                raise GPSProviderError(f"GPSD connection at {host}:{port} failed: {error}") from error
            if not line:
                break

            _log_traffic("GPSD", line.decode("utf-8", "replace").strip() if isinstance(line, bytes) else str(line).strip())
            try:
                report = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.debug("Ignoring malformed GPSD report")
                await asyncio.sleep(0)
                continue

            if not isinstance(report, dict) or report.get("class") != "TPV":
                await asyncio.sleep(0)
                continue

            fix = _parse_tpv(report)
            if fix is None:
                logger.debug("Ignoring GPSD TPV report without a valid position fix")
                await asyncio.sleep(0)
                continue

            timestamp = report.get("time")
            if timestamp is not None:
                timestamp_key = str(timestamp)
                if timestamp_key in seen_timestamps:
                    if fix.altitude is not None:
                        return fix
                    await asyncio.sleep(0)
                    continue
                seen_timestamps.add(timestamp_key)

            fixes.append(fix)
            if len(fixes) > GPSD_FIX_SAMPLES:
                fixes.pop(0)
            if fix.altitude is not None:
                return _average_fixes(fixes)
            await asyncio.sleep(0)
    finally:
        writer.close()

    return _average_fixes(fixes) if fixes else None

# -----------------------------------------------------------------------------
# Provider dispatch
# -----------------------------------------------------------------------------

async def get_gps_location(
    settings: Mapping[str, object],
    on_attempt: Optional[GPSAttemptCallback] = None,
) -> GPSLocationResult:
    """Run the configured GPS provider through the shared consensus workflow."""
    provider_name = settings.get("gps_provider", "none")
    if provider_name == "gpsd":
        read_provider_fix = _read_gpsd_fix
    elif provider_name == "nmea":
        read_provider_fix = _read_nmea_fix
    elif provider_name == "ubx":
        read_provider_fix = _read_ubx_fix
    elif provider_name == "none":
        raise GPSProviderError("No GPS receiver is configured. Choose Use GPS Receiver beside Pilot's Locate button.")
    else:
        raise GPSProviderError(f"Unknown GPS provider: {provider_name!r}.")

    async def read_fix(timeout: float) -> Optional[GPSFix]:
        return await read_provider_fix(timeout, settings)

    global _log_receiver
    _log_receiver = bool(settings.get("log_gps_receiver", False))
    provider_label = {"gpsd": "GPSD", "nmea": "NMEA", "ubx": "UBX"}[provider_name]
    max_attempts = settings.get("gps_max_attempts", DEFAULT_GPS_MAX_ATTEMPTS)
    if provider_name == "gpsd":
        host, port = _configured_endpoint(settings)
        where = f"GPSD at {host}:{port}"
    else:
        device, baudrate = _configured_serial(settings, provider_label)
        where = f"{provider_label} on {device} at {baudrate} baud"
    logger.info("==GPS== Locating with %s, up to %s attempts", where, max_attempts)

    if provider_name in ("nmea", "ubx"):
        session = serial_session()            # one open port for all the attempts
    else:
        session = nullcontext()
    with session:
        result = await acquire_location(
            read_fix,
            max_attempts=max_attempts,
            retry_max_delay=settings.get("gps_retry_max_delay", DEFAULT_GPS_RETRY_MAX_DELAY),
            on_attempt=on_attempt,
        )
    if result.fix is None:
        # what was used is in the log ("Locating with NMEA on COM10 ..."); the message says what to do about it
        attempts = f"{result.attempts} attempt{'' if result.attempts == 1 else 's'}"
        error = f"No valid GPS fix after {attempts}."
        if provider_name != "gpsd" and _received.get(device) is True:
            error += (f" The receiver on {device} is sending data but hasn't acquired satellites yet. Give it a clear"
                      " view of the sky; the first fix can take several minutes.")
        elif provider_name != "gpsd" and _received.get(device) is False:
            error += f" No data from {device}. Check that it is the GPS receiver's port, and its baud rate."
        return GPSLocationResult(None, result.attempts, error)
    return result
