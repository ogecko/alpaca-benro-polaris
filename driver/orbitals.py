import ephem
from shr import rad2deg, rad2hr
from shr import angular_separation
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



async def create_tle_orbital_celestrak(logger, norad_id):
    """
    Fetches Two-Line Element (TLE) data for an Earth-orbiting satellite using its NORAD catalog ID and constructs a PyEphem-compatible satellite object.

    Parameters:
    - logger (logging.Logger): Logger instance for diagnostic output.
    - norad_id (int or str): NORAD catalog number identifying the satellite (e.g., 25544 for the ISS).

    Returns:
    - Tuple[str, ephem.Body]: The satellite name and PyEphem body object if successful.
    - Tuple[None, None]: If the NORAD ID is invalid or TLE data cannot be retrieved or parsed.

    Behavior:
    - Validates and sanitizes the NORAD ID input.
    - Sends an async GET request to Celestrak’s TLE endpoint for the specified satellite.
    - Parses the returned TLE block (name, line1, line2).
    - Constructs a PyEphem satellite object using ephem.readtle().
    - Stores body in orbital_data[name]

    Notes:
    - This function relies on publicly available TLE data from Celestrak, which may be updated daily.
    - TLE-based orbital models are suitable for short-term tracking but degrade in accuracy over time.
    """

    try:
        norad_id = int(str(norad_id).strip())
        if norad_id <= 0:
            logger.info(f'NORAD ID must be a positive integer: {norad_id}')
            return None, None
    except Exception as e:
        logger.info(f'Invalid NORAD ID: {norad_id}, {e}')
        return None, None

    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    logger.info(f'NORAD ID Failed to fetch TLE data for {norad_id}, status: {response.status}')
                    return None, None
                text = await response.text()
    except Exception as e:
        logger.info(f'NORAD ID Failed to fetch TLE data for {norad_id}, {e}')
        return None, None

    lines = text.strip().splitlines()
    if len(lines) < 3:
        logger.info(f'NORAD ID Incomplete TLE data for NORAD ID: {norad_id}')
        return None, None

    name, line1, line2 = lines[:3]
    logger.info(f'NORAD ID Orbital Parameters: {name}\n{line1}\n{line2}')
    try:
        body = ephem.readtle(name, line1, line2)
    except Exception as e:
        logger.info(f'NORAD ID Failed to parse TLE data for NORAD ID: {norad_id}, {e}')
        return None, None

    orbital_data[name] = { "body": body }
    return name, body



async def create_xephem_orbital_jpl(logger, name_or_designation: str):
    """
    Fetches high-precision orbital elements for a minor body from the JPL Horizons API and constructs a PyEphem-compatible object.

    Parameters:
    - logger: A logging.Logger instance for diagnostic output.
    - name_or_designation: The comet or asteroid name or designation 
        - Long-period comets: "C/2025 A6", "C/2020 F3", 
        - Short-period comets: "P/2023 R1",  
        - MPC-style Provisional Designations: "2023 BU", "2021 PH27", "2022 AE1"
        - Named comets: "C/2025 A6 (Lemmon)", "1P/Halley"?
        - Numbered asteroids: "00433" → Eros?
        - Named asteroids: "Eros", "Apophis"?
        - Numbered + named asteroids: "433 Eros", "99942 Apophis"?
        - Spacecraft: "Voyager 1"?
        - Special Horizons Aliases: "DES=2025A6", "DES=2023BU", "DES=1P", "DES=99942"?
        - Note: Whitespace matters: Extra spaces or malformed designations may cause lookup failures.

    Returns:
    - Tuple (fullname, ephem.Body) if successful, or (None, None) on failure.

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
        logger.info("JPL: Empty name or designation provided.")
        return None, None

    url = "https://ssd.jpl.nasa.gov/api/horizons.api"
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
        "CSV_FORMAT": "NO"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status != 200:
                    logger.info(f"JPL lookup failed for {query}, status: {response.status}")
                    return None, None
                data = await response.json()
    except Exception as e:
        logger.info(f"JPL request error for {query}: {e}")
        return None, None

    try:
        elements = data["result"]
        logger.info(elements)

        if re.search(r"\bNo matches found\b", elements, re.IGNORECASE):
            logger.info(f"JPL: No match found for {query}")
            return None, None

        if re.search(r"\bMatching small-bodies\b", elements, re.IGNORECASE):
            logger.info(f"JPL: Multiple matching bodies found for {query}")
            return None, None


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
        D = year

        # Construct ephem string
        db_string = f"{name},e,{i},{O},{o},{a},{n},{e},{M},{epoch_date},{D},,,"
        logger.info(f'dbread Orbital Parameters: {db_string}')
        body = ephem.readdb(db_string)
        logger.info(f'JPL Orbital Parameters: {body.writedb()}')
        orbital_data[name] = {"body": body}
        return name, body

    except Exception as e:
        logger.info(f"JPL: Failed to parse orbital data for {query}: {e}")
        return None, None


# Not very accurate - decommisioned
async def create_xephem_orbital_cobs(logger, name_or_designation: str):
    """
    Fetches orbital elements for a minor body from the COBS (Comet Observation Database) API and constructs a PyEphem-compatible object.

    Note:
    This method provides only approximate orbital data. COBS values may be rounded, incomplete, or outdated, and are not suitable for high-precision ephemeris generation or telescope control. Use JPL Horizons or MPC for authoritative results.

    Parameters:
    - logger (logging.Logger): Logger instance for diagnostic output.
    - name_or_designation (str): Comet or asteroid name/designation (e.g., "C/2025 A6").

    Returns:
    - Tuple[str, ephem.Body]: The full object name and PyEphem body if successful.
    - Tuple[None, None]: If lookup or parsing fails.

    Behavior:
    - Sends an async GET request to the COBS API for orbital and object metadata.
    - Extracts key orbital elements: inclination, ascending node, argument of perihelion, semi-major axis, eccentricity, mean anomaly, orbital period, and epoch.
    - Computes mean daily motion from the orbital period.
    - Converts epoch to MM/DD/YYYY format (fixed equinox year = 2000).
    - Optionally includes magnitude model from peak brightness.
    - Constructs an ephem.readdb() string and returns the resulting body.
    - Stores body in orbital_data[name]
    """

    query = str(name_or_designation).strip()
    if not query:
        logger.info("COBS Empty name or designation provided.")
        return None, None

    url = f"https://cobs.si/api/comet.api?des={query}&orbit=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    logger.info(f"COBS lookup failed for {query}, status: {response.status}")
                    return None, None
                data = await response.json()
    except Exception as e:
        logger.info(f"COBS request error for {query}: {e}")
        return None, None

    try:
        obj = data.get("object", {})
        orbit = data.get("orbit", {})
        fullname = obj.get("fullname", query)

        # Extract and convert orbital elements
        i = float(orbit.get("i"))  # inclination (ephem i)
        O = float(orbit.get("om")) # longitude of ascending node (ephem O)
        o = float(orbit.get("w"))  # argument of perihelion (ephem o)
        a = float(orbit.get("a"))  # semi-major axis (AU) (ephem a)
        e = float(orbit.get("e"))  # eccentricity (ephem e)
        M = float(orbit.get("ma")) # mean anomaly  (ephem M)
        epoch_str = orbit.get("epoch") # epoch date (YYYY-MM-DD) (ephem E)
        tp_cd = orbit.get("tp_cd")     # time of perihelion passage
        E = datetime.strptime(epoch_str, "%Y-%m-%d").strftime("%m/%d/%Y")
        D = 2000

        # Compute mean daily motion n from orbital period
        P = float(orbit.get("per"))  # orbital period (years)(ephem n)
        n = 0.9856076686 / P

        # Estimate magnitude model from peak_mag
        H = obj.get("peak_mag")     # peak brightness (ephem H)
        H_str = f"H{H}" if H else ""

        # Construct ephem string
        #             {fullname},e,{i},{O},{o},{a},{n},{e},{M},{E},{D},{H_str},0.15"
        db_string = f"{fullname},e,{i},{O},{o},{a},{n},{e},{M},{E},{D},{H_str},0.15"

        logger.info(f'COBS Orbital Parameters: {db_string}')

        body = ephem.readdb(db_string)
        logger.info(f'Body Orbital Parameters: {body.writedb()}')
        orbital_data[fullname] = {"body": body}
        return fullname, body

    except Exception as e:
        logger.info(f"COBS Failed to parse orbital data for {query}: {e}")
        return None, None



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


