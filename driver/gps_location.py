import logging
import time
import asyncio
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

async def gps_background_listener(polaris):
    """Runs indefinitely in the background until a GPS fix is found."""
    from config import Config
    
    logger.info("GPS background listener started. Waiting for a GPS fix...")
    while getattr(Config, "gps_auto_detect", True):
        # Run the synchronous detection in a background thread to avoid blocking the event loop
        gps_fix = await asyncio.to_thread(get_gps_location, timeout=10.0)
        
        if gps_fix:
            gps_lat, gps_lon, gps_alt = gps_fix
            changed = Config.apply_changes({
                "site_latitude":  gps_lat,
                "site_longitude": gps_lon,
                "site_elevation": gps_alt,
            })
            if changed:
                polaris.make_config_params_live(changed)
                logger.info("GPS coordinates applied to live configuration.")
            
            # Mount is stationary; stop listening once we have a fix
            break
            
        # Sleep before trying again
        await asyncio.sleep(5.0)

def get_gps_location(timeout: float = 10.0) -> Optional[Tuple[float, float, float]]:
    """Try to get GPS location, returning (lat, lon, alt) or None."""
    
    # 1. Try gpsd first (Linux standard)
    loc = _try_gpsd(timeout=2.0)
    if loc:
        return loc
        
    # 2. Fallback to direct Serial NMEA parsing
    loc = _try_serial_nmea(timeout=timeout)
    if loc:
        return loc
        
    return None

def _try_gpsd(timeout: float) -> Optional[Tuple[float, float, float]]:
    try:
        from gpsdclient import GPSDClient
    except ImportError:
        logger.debug("gpsdclient not installed - skipping gpsd lookup")
        return None

    try:
        with GPSDClient(host="127.0.0.1", port=2947) as client:
            start_time = time.time()
            for result in client.dict_stream(convert_datetime=True, filter=["TPV"]):
                if time.time() - start_time > timeout:
                    logger.debug("gpsd timeout waiting for fix")
                    break

                mode = result.get("mode", 0)
                if mode < 2:
                    continue

                lat = result.get("lat")
                lon = result.get("lon")
                alt = result.get("altMSL", result.get("alt", 0.0))

                if lat is not None and lon is not None:
                    logger.info("GPS fix acquired via gpsd: lat=%.6f lon=%.6f alt=%.1f m", lat, lon, alt or 0.0)
                    return (float(lat), float(lon), float(alt or 0.0))
    except Exception as ex:
        logger.debug("gpsd query failed: %s", ex)
        
    return None

def _try_serial_nmea(timeout: float) -> Optional[Tuple[float, float, float]]:
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        logger.debug("pyserial not installed - skipping serial GPS fallback")
        return None

    ports = serial.tools.list_ports.comports()
    # Filter for likely USB serial devices
    usb_ports = [p for p in ports if "USB" in (p.description or "").upper() or "USB" in (p.hwid or "").upper()]
    
    for port in usb_ports:
        try:
            with serial.Serial(port.device, baudrate=9600, timeout=1) as ser:
                start_time = time.time()
                while time.time() - start_time < timeout:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line.startswith("$GPGGA") or line.startswith("$GNGGA"):
                        parts = line.split(',')
                        # Example: $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
                        if len(parts) >= 10 and parts[6] in ['1', '2'] and parts[2] and parts[4]:
                            lat_raw = parts[2]
                            lat_dir = parts[3]
                            lon_raw = parts[4]
                            lon_dir = parts[5]
                            alt_raw = parts[9]
                            
                            # Convert DDMM.MMMM to DD.DDDD
                            lat_deg = float(lat_raw[:2]) + float(lat_raw[2:]) / 60.0
                            if lat_dir == 'S':
                                lat_deg = -lat_deg
                                
                            lon_deg = float(lon_raw[:3]) + float(lon_raw[3:]) / 60.0
                            if lon_dir == 'W':
                                lon_deg = -lon_deg
                                
                            alt = float(alt_raw) if alt_raw else 0.0
                            
                            logger.info("GPS fix acquired via serial %s: lat=%.6f lon=%.6f alt=%.1f m", port.device, lat_deg, lon_deg, alt)
                            return (lat_deg, lon_deg, alt)
        except Exception as ex:
            logger.debug("Failed to read from %s: %s", port.device, ex)
            continue
            
    return None
