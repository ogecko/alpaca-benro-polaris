import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947
GPSD_LINE_LIMIT = 65536
GPSD_CONNECT_TIMEOUT = 2.0
GPSD_READ_TIMEOUT = 2.0
GPSD_ATTEMPT_TIMEOUT = 10.0
GPSD_FIX_SAMPLES = 3
DEFAULT_GPS_MAX_ATTEMPTS = 20
DEFAULT_GPS_RETRY_MAX_DELAY = 60.0


@dataclass(frozen=True)
class GPSFix:
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    mode: int = 2


def _monotonic() -> float:
    return asyncio.get_running_loop().time()


async def _sleep(delay: float) -> None:
    await asyncio.sleep(delay)


def _configured_attempts(value) -> int:
    if isinstance(value, bool):
        attempts = DEFAULT_GPS_MAX_ATTEMPTS
    else:
        try:
            attempts = int(value)
        except (TypeError, ValueError, OverflowError):
            attempts = DEFAULT_GPS_MAX_ATTEMPTS

    bounded_attempts = min(DEFAULT_GPS_MAX_ATTEMPTS, max(1, attempts))
    if bounded_attempts != attempts:
        logger.debug("==GPS== Clamped gps_max_attempts from %r to %d", value, bounded_attempts)
    return bounded_attempts


def _configured_retry_max_delay(value) -> float:
    try:
        delay = float(value)
    except (TypeError, ValueError, OverflowError):
        delay = DEFAULT_GPS_RETRY_MAX_DELAY

    if not math.isfinite(delay) or delay <= 0:
        logger.debug("==GPS== Invalid gps_retry_max_delay %r; using %.1f seconds", value, DEFAULT_GPS_RETRY_MAX_DELAY)
        return DEFAULT_GPS_RETRY_MAX_DELAY
    return delay


def _retry_delay_after_attempt(attempt_index: int, max_delay: float) -> float:
    return min(2.0 ** attempt_index, max_delay)


def _finite_float(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


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

    return GPSFix(latitude, longitude, altitude, mode)


def _average_fixes(fixes: list[GPSFix]) -> GPSFix:
    if len(fixes) == 1:
        return fixes[0]

    latitude = sum(fix.latitude for fix in fixes) / len(fixes)
    longitude_sine = sum(math.sin(math.radians(fix.longitude)) for fix in fixes)
    longitude_cosine = sum(math.cos(math.radians(fix.longitude)) for fix in fixes)
    if math.isclose(longitude_sine, 0.0, abs_tol=1e-12) and math.isclose(longitude_cosine, 0.0, abs_tol=1e-12):
        longitude = fixes[-1].longitude
    else:
        longitude = math.degrees(math.atan2(longitude_sine, longitude_cosine))

    altitudes = [fix.altitude for fix in fixes if fix.altitude is not None]
    altitude = sum(altitudes) / len(altitudes) if altitudes else None
    mode = max(fix.mode for fix in fixes)
    return GPSFix(latitude, longitude, altitude, mode)


async def gps_background_listener(polaris):
    """Apply a 2D fix immediately and keep polling until 3D or timeout."""
    from config import Config

    attempts = _configured_attempts(getattr(Config, "gps_max_attempts", DEFAULT_GPS_MAX_ATTEMPTS))
    retry_max_delay = _configured_retry_max_delay(
        getattr(Config, "gps_retry_max_delay", DEFAULT_GPS_RETRY_MAX_DELAY)
    )

    last_applied_fix = None

    def apply_fix(gps_fix: GPSFix) -> None:
        nonlocal last_applied_fix
        changes = {
            "site_latitude": gps_fix.latitude,
            "site_longitude": gps_fix.longitude,
            "location": "GPS Receiver",
        }
        if gps_fix.altitude is not None:
            changes["site_elevation"] = round(gps_fix.altitude)

        applied = Config.apply_changes(changes)
        if applied:
            polaris.make_config_params_live(applied)
            logger.info("==GPS== Coordinates applied to live configuration.")
        last_applied_fix = gps_fix

    def apply_2d_fix(gps_fix: GPSFix) -> None:
        if last_applied_fix is None:
            apply_fix(gps_fix)

    for attempt_index in range(attempts):
        attempt_timeout = GPSD_ATTEMPT_TIMEOUT
        logger.info("==GPS== Starting acquisition attempt %d of %d", attempt_index + 1, attempts)
        try:
            gps_fix = await get_gps_location(
                timeout=attempt_timeout,
                on_2d_fix=apply_2d_fix,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.info("==GPS== Acquisition attempt %d failed: %s", attempt_index + 1, error)
            gps_fix = None

        if gps_fix is None:
            logger.info("==GPS== Attempt %d of %d: no fix.", attempt_index + 1, attempts)
        else:
            if gps_fix != last_applied_fix:
                apply_fix(gps_fix)
            fix_dimension = "3D" if gps_fix.mode >= 3 else "2D"
            logger.info("==GPS== Attempt %d of %d: found a %s fix.", attempt_index + 1, attempts, fix_dimension)
            if gps_fix.mode >= 3:
                return

        if attempt_index + 1 < attempts:
            retry_delay = _retry_delay_after_attempt(attempt_index, retry_max_delay)
            logger.info("==GPS== Waiting %.1f seconds before the next acquisition attempt.", retry_delay)
            await _sleep(retry_delay)

    if last_applied_fix is None:
        logger.info("==GPS== No fix found after %d attempts.", attempts)
    else:
        logger.info("==GPS== No 3D fix found after %d attempts; keeping the 2D position.", attempts)


async def get_gps_location(
    timeout: float = GPSD_ATTEMPT_TIMEOUT,
    on_2d_fix: Optional[Callable[[GPSFix], None]] = None,
) -> Optional[GPSFix]:
    """Read gpsd until a 3D fix or timeout, reporting 2D fixes as they arrive."""
    return await _try_gpsd(timeout, on_2d_fix)


async def _try_gpsd(
    timeout: float,
    on_2d_fix: Optional[Callable[[GPSFix], None]] = None,
) -> Optional[GPSFix]:
    timeout = _finite_float(timeout)
    if timeout is None or timeout <= 0:
        return None

    deadline = _monotonic() + timeout
    reader = None
    writer = None
    fixes: list[GPSFix] = []
    seen_timestamps = set()
    has_2d_fix = False

    try:
        connect_timeout = min(GPSD_CONNECT_TIMEOUT, deadline - _monotonic())
        if connect_timeout <= 0:
            return None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(GPSD_HOST, GPSD_PORT, limit=GPSD_LINE_LIMIT),
            timeout=connect_timeout,
        )

        writer.write(b'?WATCH={"enable":true,"json":true}\n')
        drain_timeout = min(GPSD_CONNECT_TIMEOUT, deadline - _monotonic())
        if drain_timeout <= 0:
            return None
        await asyncio.wait_for(writer.drain(), timeout=drain_timeout)

        while True:
            remaining = deadline - _monotonic()
            if remaining <= 0:
                break
            try:
                line = await asyncio.wait_for(
                    reader.readline(), timeout=min(GPSD_READ_TIMEOUT, remaining)
                )
            except TimeoutError:
                logger.debug("==GPS== Timed out waiting for a gpsd report")
                if _monotonic() >= deadline:
                    break
                continue
            if not line:
                break

            try:
                report = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.debug("==GPS== Ignoring malformed gpsd report")
                await asyncio.sleep(0)
                continue

            if not isinstance(report, dict) or report.get("class") != "TPV":
                await asyncio.sleep(0)
                continue

            fix = _parse_tpv(report)
            if fix is None:
                logger.debug("==GPS== Ignoring gpsd TPV report without a valid position fix")
                await asyncio.sleep(0)
                continue

            timestamp = report.get("time")
            if timestamp is not None:
                timestamp_key = str(timestamp)
                if timestamp_key in seen_timestamps:
                    if fix.mode >= 3:
                        return fix
                    await asyncio.sleep(0)
                    continue
                seen_timestamps.add(timestamp_key)

            fixes.append(fix)
            if len(fixes) > GPSD_FIX_SAMPLES:
                fixes.pop(0)
            if fix.mode == 2 and not has_2d_fix:
                has_2d_fix = True
                if on_2d_fix is not None:
                    on_2d_fix(fix)
            if fix.mode >= 3:
                return _average_fixes(fixes)
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        raise
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        logger.info("==GPS== gpsd query failed: %s", error)
    finally:
        if writer is not None:
            writer.close()

    return _average_fixes(fixes) if fixes else None
