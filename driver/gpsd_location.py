import asyncio
import json
import logging
import math
from collections.abc import Mapping
from typing import Optional

from gps_location import GPSFix, GPSProviderError, _average_fixes

logger = logging.getLogger(__name__)

GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947
GPSD_LINE_LIMIT = 65536
GPSD_CONNECT_TIMEOUT = 2.0
GPSD_READ_TIMEOUT = 2.0
GPSD_FIX_SAMPLES = 3


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

    return GPSFix(latitude, longitude, altitude)


def _configured_endpoint(settings: Mapping[str, object]) -> tuple[str, int]:
    raw_host = settings.get("gpsd_host", GPSD_HOST)
    if not isinstance(raw_host, str) or not raw_host.strip():
        raise GPSProviderError("GPSD host must be configured in Network Services.")

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


async def get_gps_location(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
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
