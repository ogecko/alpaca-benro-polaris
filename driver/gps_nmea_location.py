import logging
import math
from collections.abc import Mapping
from typing import Optional

from gps_location import GPSFix
from gps_serial_common import get_serial_gps_location

logger = logging.getLogger(__name__)

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
            fix = _parse_nmea_sentence(line)
            if fix is not None:
                fixes.append(fix)
        return fixes


async def get_gps_location(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
    return await get_serial_gps_location(
        timeout,
        settings,
        _NMEAStreamParser,
        "NMEA",
    )
