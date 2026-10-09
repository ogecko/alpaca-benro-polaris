import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_GPS_MAX_ATTEMPTS = 10
MAX_GPS_ATTEMPTS = 20
DEFAULT_GPS_RETRY_MAX_DELAY = 15.0
GPS_ATTEMPT_TIMEOUT = 10.0
GPS_FIX_CONSENSUS_TOLERANCE_DEG = 1.0


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
    attempt_timeout=GPS_ATTEMPT_TIMEOUT,
    on_attempt: Optional[GPSAttemptCallback] = None,
) -> GPSLocationResult:
    """Acquire a three-fix consensus without changing application configuration."""
    attempts = _configured_attempts(max_attempts)
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


async def get_gps_location(
    settings: Mapping[str, object],
    on_attempt: Optional[GPSAttemptCallback] = None,
) -> GPSLocationResult:
    """Run the configured GPS provider through the shared consensus workflow."""
    provider_name = settings.get("gps_provider", "none")
    if provider_name == "gpsd":
        from gpsd_location import get_gps_location as read_provider_fix
    elif provider_name == "nmea":
        from gps_nmea_location import get_gps_location as read_provider_fix
    elif provider_name == "ubx":
        from gps_ubx_location import get_gps_location as read_provider_fix
    elif provider_name == "none":
        raise GPSProviderError(
            "GPS provider is set to none. Select GPSD, Serial (NMEA), or Serial (UBX) in Network Services."
        )
    else:
        raise GPSProviderError(f"Unknown GPS provider: {provider_name!r}.")

    async def read_fix(timeout: float) -> Optional[GPSFix]:
        return await read_provider_fix(timeout, settings)

    result = await acquire_location(
        read_fix,
        max_attempts=settings.get("gps_max_attempts", DEFAULT_GPS_MAX_ATTEMPTS),
        retry_max_delay=settings.get("gps_retry_max_delay", DEFAULT_GPS_RETRY_MAX_DELAY),
        on_attempt=on_attempt,
    )
    if result.fix is None:
        provider_label = {"gpsd": "GPSD", "nmea": "NMEA", "ubx": "UBX"}[provider_name]
        error = f"No valid {provider_label} GPS fix found after {result.attempts} attempts."
        return GPSLocationResult(None, result.attempts, error)
    return result
