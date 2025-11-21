import ephem
from shr import rad2deg, rad2hr
from shr import angular_separation
from config import Config
import aiohttp
import re
from datetime import datetime

def compose_orbital_export():
    export_data = {}
    for key, entity in orbital_data.items():
        export_data[key] = {
            "RA_hr": entity.get("RA_hr"),           # BEWARE these are JNow Epoch, Most Pilot catalog are J2000
            "DEC_deg": entity.get("DEC_deg"),
            "Proximity": entity.get("Proximity"),
        }
    return export_data

# Julian Date to Gregorian Date
def jd_to_calendar(jd):
    jd += 0.5
    Z = int(jd)
    F = jd - Z
    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - int(alpha / 4)
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)

    day = B - D - int(30.6001 * E) + F
    month = E - 1 if E < 14 else E - 13
    year = C - 4716 if month > 2 else C - 4715

    return int(month), int(day), int(year)

def orb_result(logger, name, msg):
    logger.info(msg)
    return name, msg

async def create_tle_orbital_celestrak(logger, norad_id):
    """
    Fetches Two-Line Element (TLE) data for an Earth-orbiting satellite using its NORAD catalog ID and constructs a PyEphem-compatible satellite object.

    Parameters:
    - logger (logging.Logger): Logger instance for diagnostic output.
    - norad_id (int or str): NORAD catalog number identifying the satellite (e.g., 25544 for the ISS).

    Returns:
    - Tuple[str, msg]: The orbital_name and result message if successful.
    - Tuple[None, msg]: If the NORAD ID is invalid or TLE data cannot be retrieved or parsed. Error msg.
    - Stores body in orbital_data[orbital_name] if successful

    Behavior:
    - Validates and sanitizes the NORAD ID input.
    - Sends an async GET request to Celestrak’s TLE endpoint for the specified satellite.
    - Parses the returned TLE block (name, line1, line2).
    - Constructs a PyEphem satellite object using ephem.readtle().


    Notes:
    - This function relies on publicly available TLE data from Celestrak, which may be updated daily.
    - TLE-based orbital models are suitable for short-term tracking but degrade in accuracy over time.
    """
    # ---------------- Try and parse the norad_id
    try:
        query = int(str(norad_id).strip())
        if query <= 0:
            return orb_result(logger, None, f'Celestrak: NORAD ID must be a positive integer: {norad_id}')
    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Invalid NORAD ID: {norad_id}, {e}')

    # ---------------- Try and query the Celestrak API
    try:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={query}&FORMAT=TLE"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return orb_result(logger, None, f'Celestrak: Failed to fetch TLE data for {norad_id}, status: {response.status}')
                text = await response.text()
    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to fetch TLE data for {norad_id}, {e}')

    # ---------------- Try and parse the Celestrak Response
    try:
        if Config.log_orbital_queries:
            logger.info(f'Celestrak: Response from query for {norad_id}')
            logger.info(f'{text.strip()}')

        if re.search(r"\bNo GP data found\b", text, re.IGNORECASE):
            return orb_result(logger, None, f'Celestrak: No match found for {norad_id}')

        lines = text.strip().splitlines()
        if len(lines) < 3:
            return orb_result(logger, None, f'Celestrak: Incomplete TLE data for NORAD ID: {norad_id}')

    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to parse orbital data for {norad_id}: {e}')
    
    # ---------------- Try and create the Orbital Body
    try:
        # Construct TLE strings
        name, line1, line2 = lines[:3]
        body = ephem.readtle(name, line1, line2)

        if Config.log_orbital_queries:
            logger.info(f'Celestrak: Body Orbital Parameters: {body.writedb()}')

    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to parse TLE data for NORAD ID: {norad_id}, {e}')

    orbital_data[name] = { "body": body }
    return orb_result(logger, name, f'Sucessfully retrieved orbital parameters for {name}.')



async def create_xephem_orbital_jpl(logger, name_or_designation: str):
    """
    Fetches high-precision orbital elements for a minor body from the JPL Horizons API and constructs a PyEphem-compatible object.

    Parameters:
    - logger: A logging.Logger instance for diagnostic output.
    - name_or_designation: The comet or asteroid name or designation 
        - Long-period comets: "C/2025 A6", "C/2020 F3"
        - Short-period comets: "P/2023 R1",  
        - Provisional Comet Designations: "2006 F8"
        - Named asteroids: "Ceres", "Vesta", "Pallas", "Iris", "Flora", "Hebe", "Apophis", 
        - Numbered asteroids: "00433" → Eros
        - Provisional Asteroid Designations: "2023 BU", "2021 PH27", "2022 AE1", "A801 AA" → Ceres (often near earth or newly discovered)
        - Note: Whitespace matters: Extra spaces or malformed designations may cause lookup failures.

    Returns:
    - Tuple[str, msg]: The orbital_name and result message if successful.
    - Tuple[None, msg]: If the orbital is invalid or xephem data cannot be retrieved or parsed. Error msg.
    - Stores body in orbital_data[orbital_name] if successful

    Behavior:
    - See: https://ssd-api.jpl.nasa.gov/doc/horizons.html#command
    - Sends a request to the Horizons API for orbital elements in JSON format (actual results field is text).
    - Parses key parameters: inclination, ascending node, argument of perihelion, semi-major axis, eccentricity, mean anomaly, mean motion, and epoch.
    - Converts Julian epoch to calendar date and equinox year.
    - Constructs an ephem.readdb() string and returns the resulting body object.
    - Stores body in orbital_data[name]
    """

    query = str(name_or_designation).strip()
    if not query:
        return orb_result(logger, None, 'JPL: Empty name provided.')

    # ---------------- Try and query the JPL Horizon API
    try:
        url = "https://ssd.jpl.nasa.gov/api/horizons.api"
        today = datetime.utcnow().strftime("%Y-%b-%d")
        params = {
            "format": "json",
            "COMMAND": f"'{query}'",
            "EPHEM_TYPE": "ELEMENTS",
            "OBJ_DATA": "YES",
            "MAKE_EPHEM": "NO",
            "OUT_UNITS": "AU-D",
            "ELEM_LABELS": "YES",
            "REF_PLANE": "ECLIPTIC",
            "TP_TYPE": "ABSOLUTE",
            "CSV_FORMAT": "NO",
            "CENTER": "'500@10'",       # Solar system barycenter
            "TLIST": f"'{today}'"       # Current UTC date
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status != 200:
                    return orb_result(logger, None, f'JPL: lookup failed for {query}, status: {response.status}')
                data = await response.json()
    except Exception as e:
        return orb_result(logger, None, f'JPL: Failed to fetch Orbital data for {query}: {e}')

    # ---------------- Try and parse the JPL Horizon API Response
    try:
        elements = data["result"]

        if Config.log_orbital_queries:
            logger.info(f'JPL: Response from query for {query}, {params}')
            logger.info(elements)

        if re.search(r"\bNo matches found\b", elements, re.IGNORECASE):
            return orb_result(logger, None, f'JPL: No match found for {query}')

        if re.search(r"\bMatching small-bodies\b", elements, re.IGNORECASE):
            return orb_result(logger, None, f'JPL: Multiple matching bodies found for {query}')

        def extract(label):
            match = re.search(rf"\b{label}=\s*(-?\d*\.?\d{{0,12}})", elements)
            return float(match.group(1)) if match else None

        def extractname():
            match = re.search(r"PL/HORIZONS\s+(.*?)\s+\d{4}-\w{3}-\d{2}", elements)
            return match.group(1).strip() if match else query

        name = extractname()
        i = extract("IN")
        O = extract("OM")
        o = extract("W")
        a = extract("A")
        e = extract("EC")
        M = extract("MA")
        n = extract("N")
        epoch_jd = extract("EPOCH")
        tp_jd = extract("TP")

        month, day, year = jd_to_calendar(epoch_jd)
        epoch_date = f"{month:02d}/{day:02d}/{year}"
        D = 2000

    except Exception as e:
        return orb_result(logger, None, f'JPL: Failed to parse orbital data for {query}: {e}')

    # ---------------- Try and create the Orbital Body
    try:
        # Construct xephem string
        db_string = f"{name},e,{i},{O},{o},{a},{n},{e},{M},{epoch_date},{D},,,"
        body = ephem.readdb(db_string)

        if Config.log_orbital_queries:
            logger.info(f'JPL: Body Orbital Parameters: {body.writedb()}')

    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to parse TLE data for NORAD ID: {norad_id}, {e}')

    orbital_data[name] = {"body": body}
    return orb_result(logger, name, f'Sucessfully retrieved orbital parameters for {name}.')



def find_closest_orbital(observer, scope_ra, scope_dec):
    # refresh orbital data with current observer and scope position
    update_orbital_data(observer, scope_ra, scope_dec)
    closest_entity = None
    min_proximity = float('inf')
    for key, entity in orbital_data.items():
        proximity = entity.get("Proximity", float('inf'))
        if proximity < min_proximity:
            min_proximity = proximity
            closest_entity = entity
            closest_key = key
    if closest_entity:
        return closest_key, closest_entity["body"]
    else:
        return None, None

# This function update_orbital_data is only used for the Catalog. 
# The currently tracked orbital is updated within the PID Control loop
def update_orbital_data(observer, scope_ra=0.0, scope_dec=0.0):
    global orbital_data

    for key, entity in orbital_data.items():
        orbital = entity["body"]
        orbital.compute(observer)
        ra_hr = rad2hr(orbital.ra)
        dec_deg = rad2deg(orbital.dec)

        # Store computed values
        entity["RA_hr"] = ra_hr
        entity["DEC_deg"] = dec_deg
        entity["Az_deg"] = rad2deg(orbital.az)
        entity["Alt_deg"] = rad2deg(orbital.alt)
        entity["Proximity"] = angular_separation(ra_hr, dec_deg, scope_ra, scope_dec)


orbital_data = {
    "Sun": { "body": ephem.Sun() },
    "Moon": { "body": ephem.Moon() },
    "Mercury": { "body": ephem.Mercury() },
    "Venus": { "body": ephem.Venus() },
    "Mars": { "body": ephem.Mars() },
    "Jupiter": { "body": ephem.Jupiter() },
    "Saturn": { "body": ephem.Saturn() },
    "Uranus": { "body": ephem.Uranus() },
    "Neptune": { "body": ephem.Neptune() },
    "Pluto": { "body": ephem.Pluto() },
    "Phobos": { "body": ephem.Phobos() },
    "Deimos": { "body": ephem.Deimos() },
    "Io": { "body": ephem.Io() },
    "Europa": { "body": ephem.Europa() },
    "Ganymede": { "body": ephem.Ganymede() },
    "Callisto": { "body": ephem.Callisto() },
    "Titan": { "body": ephem.Titan() },
    "Iapetus": { "body": ephem.Iapetus() },
    "Rhea": { "body": ephem.Rhea() },
    "Dione": { "body": ephem.Dione() },
    "Tethys": { "body": ephem.Tethys() },
    "Enceladus": { "body": ephem.Enceladus() },
    "Mimas": { "body": ephem.Mimas() },
    "Hyperion": { "body": ephem.Hyperion() },
}


