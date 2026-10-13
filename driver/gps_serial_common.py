import asyncio
import logging
import math
import time
from collections.abc import Mapping
from typing import Callable, Optional, Protocol

import serial

from gps_location import GPSFix, GPSProviderError

logger = logging.getLogger(__name__)

DEFAULT_SERIAL_DEVICE = "/dev/ttyUSB0"
DEFAULT_SERIAL_BAUDRATE = 9600
SERIAL_READ_TIMEOUT = 1.0


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
            f"{protocol_name} GPS serial device path must be configured in Network Services."
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
        with serial.Serial(
            port=device,
            baudrate=baudrate,
            timeout=min(SERIAL_READ_TIMEOUT, timeout),
        ) as connection:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.debug(
                        "==GPS-SERIAL== No valid %s position fix received from %s",
                        protocol_name,
                        device,
                    )
                    return None
                connection.timeout = min(SERIAL_READ_TIMEOUT, remaining)
                chunk = connection.read(256)
                if not chunk:
                    continue
                fixes = parser.feed(chunk)
                if fixes:
                    logger.debug(
                        "==GPS-SERIAL== Read a valid %s position fix from %s",
                        protocol_name,
                        device,
                    )
                    return fixes[0]
    except (serial.SerialException, OSError, ValueError) as error:
        raise GPSProviderError(
            f"Cannot open {protocol_name} GPS serial device '{device}' at {baudrate} baud: {error}"
        ) from error


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
