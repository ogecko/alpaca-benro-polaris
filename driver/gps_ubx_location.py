import math
from collections.abc import Mapping
from typing import Optional

from gps_location import GPSFix
from gps_serial_common import get_serial_gps_location

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


async def get_gps_location(timeout: float, settings: Mapping[str, object]) -> Optional[GPSFix]:
    return await get_serial_gps_location(
        timeout,
        settings,
        _UBXStreamParser,
        "UBX",
    )
