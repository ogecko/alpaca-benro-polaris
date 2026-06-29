
import json
import os
import re
import ephem
import ssl
import certifi
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from shr import rad2deg, rad2hr
from kinematics import angular_separation
from config import Config
import aiohttp

logger = logging.getLogger(__name__)

DRIVER_DIR = Path(__file__).resolve().parent
DATA_DIR   = DRIVER_DIR.parent / 'data'
CACHE_PATH = DATA_DIR / 'orbitals.json'
CATALOG_PATH = DATA_DIR / 'catalog.json'

# Category constants (matches catalog.ts typeLookup)
C1_SATELLITE = 6
C1_COMET     = 7
C1_ASTEROID  = 8
 
# C2 subtypes
C2_SATELLITE = 36
C2_COMET     = 39
C2_ASTEROID  = 40
 
# Cn=84 = "Orbit" — the frontend getRaDec() branch for live orbital positions
CN_ORBIT = 84

# Defaults for catalog fields
DEFAULTS = {
    "MainID": "", "Name": "", "Notes": "", "Class": "", "OtherIDs": "",
    "Rt": 5, "Sz": 8, "Vz": 7, "C1": 10, "C2": 41, "Cn": 85
}


# ── Helper Methods ─────────────────────────────────────────────────────────────

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



def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
 
 
def _c1_c2_for_source(source: str, query: str = '') -> tuple[int, int]:
    """Infer C1/C2 catalog type from fetch source."""
    if source == 'celestrak':
        return C1_SATELLITE, C2_SATELLITE
    # JPL: distinguish comet vs asteroid by query prefix
    q = query.strip().upper()
    if q.startswith('C/') or q.startswith('P/') or q.startswith('D/'):
        return C1_COMET, C2_COMET
    return C1_ASTEROID, C2_ASTEROID
 
 
def ensure_data_dir_exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def orb_result(logger, name, msg):
    logger.info(msg)
    return name, msg



# ── Orbital Parameter Web Query Methods ─────────────────────────────────────────────────────────────

async def _fetch_tle_from_celestrak(logger, norad_id):
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
            return orb_result(logger, None, f'Celestrak: NORAD ID must be a positive integer.')
    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Invalid NORAD ID {norad_id}.')

    # ---------------- Try and query the Celestrak API
    try:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={query}&FORMAT=TLE"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return orb_result(logger, None, f'Celestrak: Failed to fetch TLE data, response 200.')
                text = await response.text()
    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to fetch TLE data.')

    # ---------------- Try and parse the Celestrak Response
    try:
        if Config.log_orbital_queries:
            logger.info(f'Celestrak: Response from query for {norad_id}')
            logger.info(f'{text.strip()}')

        if re.search(r"\bNo GP data found\b", text, re.IGNORECASE):
            return orb_result(logger, None, f'Celestrak: No match found.')

        lines = text.strip().splitlines()
        if len(lines) < 3:
            return orb_result(logger, None, f'Celestrak: Incomplete TLE data.')

    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to parse orbital data.')
    
    # ---------------- Try and create the Orbital Body
    try:
        # Construct TLE strings
        name, line1, line2 = lines[:3]
        name = name.strip()  
        body = ephem.readtle(name, line1, line2)

        if Config.log_orbital_queries:
            logger.info(f'Celestrak: Body Orbital Parameters: {body.writedb()}')

    except Exception as e:
        return orb_result(logger, None, f'Celestrak: Failed to create TLE body.')

    orbital_data[name] = {
        'body':     body,
        'MainID':   name,                    # e.g. "STARLINK-34643"
        'OtherIDs': str(norad_id).strip(),   # original NORAD query
        'C1':       C1_SATELLITE,
        'C2':       C2_SATELLITE,
        'Cn':       CN_ORBIT,
    }

    # ---------------- Persist to cache (best-effort)
    try:
        store_orbital_body_to_cache(body, source='celestrak', query=str(norad_id))
    except Exception as ex:
        logger.warning(f'Celestrak: Failed to cache orbital — {ex}')
 
    return orb_result(logger, name, f'Sucessfully retrieved orbital parameters for {name}.')




async def _fetch_xephem_from_jpl(logger, name_or_designation: str):
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
    ssl_context = ssl.create_default_context(cafile=certifi.where())
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
            "REF_PLANE": "FRAME",       # was "ECLIPTIC" — xephem readdb() expects equatorial J2000
            "TP_TYPE": "ABSOLUTE",
            "CSV_FORMAT": "NO",
            "CENTER": "'500@10'",       # Solar system barycenter
            "TLIST": f"'{today}'"       # Current UTC date
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, ssl=ssl_context, timeout=15) as response:
                if response.status != 200:
                    return orb_result(logger, None, f'JPL: Failed to fetch ephem data, response 200.')
                data = await response.json()
    except Exception as e:
        msg = f'JPL: Failed to decode JSON, exception: {e}, params: {params}'
        logger.error(msg)
        return orb_result(logger, None, f'JPL: Failed to fetch ephem data.')

    # ---------------- Try and parse the JPL Horizon API Response
    try:
        elements = data["result"]

        if Config.log_orbital_queries:
            logger.info(f'JPL: Response from query for {query}, {params}')
            logger.info(elements)

        if re.search(r"\bNo matches found\b", elements, re.IGNORECASE):
            return orb_result(logger, None, f'JPL: No match found.')

        if re.search(r"\bMatching small-bodies\b", elements, re.IGNORECASE):
            return orb_result(logger, None, f'JPL: Multiple matching small bodies found.')

        if re.search(r"\bNumber of matches\b", elements, re.IGNORECASE):
            return orb_result(logger, None, f'JPL: Multiple matching bodies found.')

        def extract(label):
            match = re.search(rf"\b{label}=\s*(-?\d*\.?\d{{0,12}})", elements)
            return float(match.group(1)) if match else None

        def extractname():
            match = re.search(r"PL/HORIZONS\s+(.*?)\s+\d{4}-\w{3}-\d{2}", elements)
            return match.group(1).strip() if match else query

        logger.info(f'JPL RAW ELEMENTS: IN={extract("IN")}, OM={extract("OM")}, W={extract("W")}')

        name = extractname()
        i = extract("IN")
        O = extract("OM")
        o = extract("W")
        a = extract("A")
        e = extract("EC")
        M = extract("MA")
        n = extract("N")
        epoch_jd = extract("EPOCH")
        qr = extract("QR")          # perihelion distance in AU
        tp_jd = extract("TP")       # time of perihelion (Julian Date)

        month, day, year = jd_to_calendar(epoch_jd)
        epoch_date = f"{month:02d}/{day:02d}/{year}"
        D = 2000

        # Construct xephem string
        if e is not None and e >= 1.0:
            # Hyperbolic/near-parabolic: use HyperbolicBody format
            tp_month, tp_day, tp_year = jd_to_calendar(tp_jd)
            tp_date = f"{tp_month:02d}/{tp_day:02d}/{tp_year}"
            db_string = f"{name},h,{tp_date},{qr},{i},{O},{o},{e},{D},0,0,0"
        else:
            # Elliptical: existing path
            db_string = f"{name},e,{i},{O},{o},{a},{n},{e},{M},{epoch_date},{D},,,"

    except Exception as e:
        return orb_result(logger, None, f'JPL: Failed to parse orbital data.')

    # ---------------- Try and create the Orbital Body
    try:
        body = ephem.readdb(db_string)
        if Config.log_orbital_queries:
            logger.info(f'JPL: Body Orbital Parameters: {body.writedb()}')

    except Exception as e:
        return orb_result(logger, None, f'JPL: Failed to create orbital body.')

    c1, c2 = _c1_c2_for_source('jpl', query)
    orbital_data[name] = {
        'body':     body,
        'MainID':   name,
        'OtherIDs': query,       # original designation e.g. "C/2025 R3"
        'C1':       c1,
        'C2':       c2,
        'Cn':       CN_ORBIT,
    }

    # ---------------- Persist to cache (best-effort)
    try:
        store_orbital_body_to_cache(body, source='jpl', query=query)
    except Exception as ex:
        logger.warning(f'JPL: Failed to cache orbital — {ex}')

    return orb_result(logger, name, f'Sucessfully retrieved orbital parameters for {name}.')




# ── Orbital Data object creation from Cache or Web ─────────────────────────────────────────────────────────────

async def create_tle_orbital_celestrak(logger, norad_id):
    """
    Public API for PID/tracking. Returns immediately if body already in orbital_data,
    then fires a background refresh. If not cached, fetches synchronously.
    """
    name = str(norad_id).strip()

    if name in orbital_data:
        # Already have a body — return it immediately and refresh in background
        query = orbital_data[name].get('OtherIDs', '').strip() or name
        asyncio.create_task(_fetch_tle_from_celestrak(logger, query))
        return orb_result(logger, name, f'Celestrak: Using cached body for {name}, refreshing.')

    # Not in orbital_data — fetch synchronously so tracking can start
    return await _fetch_tle_from_celestrak(logger, name)


async def create_xephem_orbital_jpl(logger, name_or_designation: str):
    """Public API for PID/tracking."""
    name = str(name_or_designation).strip()

    if name in orbital_data:
        query  = orbital_data[name].get('OtherIDs', '').strip() or name
        asyncio.create_task(_fetch_xephem_from_jpl(logger, query))
        return orb_result(logger, name, f'JPL: Using cached body for {name}, refreshing.')

    # Not cached — fetch synchronously, with offline fallback
    return await _fetch_xephem_from_jpl(logger, name)



# ── Orbital Cache File Load/Save ─────────────────────────────────────────────────────────────
 
def load_cache() -> dict[str, dict]:
    """
    Load orbitals.json from disk.
    Returns a dict keyed by body name (same key used in orbital_data).
    Returns {} if file missing or corrupt.
    """
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            logger.warning('orbitals.json: expected a list, ignoring.')
            return {}
        return {e['MainID']: e for e in entries if isinstance(e, dict) and 'MainID' in e}
    except Exception as ex:
        logger.warning(f'orbitals.json: failed to load — {ex}')
        return {}
 
 
def save_cache(cache: dict[str, dict]):
    """Persist the cache dict (keyed by MainID) to orbitals.json."""
    ensure_data_dir_exists()
    try:
        entries = list(cache.values())
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2)
    except Exception as ex:
        logger.warning(f'orbitals.json: failed to save — {ex}')
 
 
# ── Orbital store / restore / refresh cache ─────────────────────────────────────────────────────────────
 
def store_orbital_body_to_cache(body, source: str, query: str = '', name_override: str = '') -> None:
    """
    Persist a freshly-fetched pyephem body to orbitals.json.
 
    body         — the ephem body object (readtle or readdb result)
    source       — 'celestrak' or 'jpl'
    query        — the original user query string (used to infer C1/C2 for JPL)
    name_override — optional friendly name; defaults to body.name
    """
    try:
        writedb_str = body.writedb()
        c1, c2      = _c1_c2_for_source(source, query)
        if source == 'celestrak':
            main_id = name_override or body.name.strip()
            name    = ''
        else:
            main_id = name_override or body.name.strip()
            name    = ''
 
        cache = load_cache()
        existing = cache.get(main_id, {})
 
        entry = {
            'source':     source,
            'writedb':    writedb_str,
            'fetched_at': _now_utc_iso(),
            # Catalog fields
            'MainID':   main_id,
            'Name':     existing.get('Name', name),
            'Notes':    existing.get('Notes', f'Cached {source.upper()} orbital. Last fetched: {_now_utc_iso()}'),
            'Class':    existing.get('Class', ''),
            'OtherIDs': existing.get('OtherIDs', query if query != name else ''),
            'Rt':       existing.get('Rt', 2),   # 'Typical'
            'Sz':       existing.get('Sz', 8),   # 'Unknown'
            'Vz':       existing.get('Vz', 7),   # 'Unknown'
            'C1':       c1,
            'C2':       c2,
            'Cn':       CN_ORBIT,                # 84 = Orbit → live RA/Dec from orbs
        }
        # Update Notes to reflect latest fetch time
        entry['Notes'] = f'Cached {source.upper()} orbital. Last fetched: {entry["fetched_at"]}'
 
        cache[main_id] = entry
        save_cache(cache)
        logger.info(f'orbital_cache: saved "{main_id}" (source={source})')
    except Exception as ex:
        logger.warning(f'orbital_cache: failed to cache body — {ex}')
 
 

 
def restore_orbital_bodies_from_orbital_cache() -> int:
    """
    Called at startup. Reads orbitals.json and, for each entry, reconstructs
    the pyephem body via ephem.readdb() and inserts it into orbital_data.
    Bodies already present in orbital_data (built-in planets etc.) are skipped.
 
    Returns the number of bodies successfully restored.
    """
    cache = load_cache()
    count = 0
    for name, entry in cache.items():
        if name in orbital_data:
            logger.info(f'orbital_cache: "{name}" already in orbital_data, skipping restore.')
            continue
        writedb_str = entry.get('writedb', '')
        if not writedb_str:
            logger.warning(f'orbital_cache: "{name}" has no writedb string, skipping.')
            continue
        try:
            body = ephem.readdb(writedb_str)
            orbital_data[name] = {
                'body':     body,
                'MainID':   entry.get('MainID', name),
                'OtherIDs': entry.get('OtherIDs', ''),
                'C1':       entry.get('C1', C1_SATELLITE),
                'C2':       entry.get('C2', C2_SATELLITE),
                'Cn':       CN_ORBIT,
            }
            count += 1
            logger.info(f'orbital_cache: restored "{name}" from cache (fetched {entry.get("fetched_at","?")})')
        except Exception as ex:
            logger.warning(f'orbital_cache: failed to restore "{name}" — {ex}')
    return count
 

 
def restore_catalog_items_from_orbital_cache() -> list[dict]:
    """
    Returns the catalog-compatible list of dicts from orbitals.json.
    Each dict has the standard catalog fields (MainID, Name, C1, C2, Cn=84, …).
    RA_hr / Dec_deg are intentionally omitted here — the frontend resolves them
    live from the orbs export (Cn=84 branch in getRaDec).
    """
    cache = load_cache()
    items = []
    for entry in cache.values():
        item = {
            'MainID':   entry.get('MainID', ''),
            'Name':     entry.get('Name', ''),
            'Notes':    entry.get('Notes', ''),
            'Class':    entry.get('Class', ''),
            'OtherIDs': entry.get('OtherIDs', ''),
            'Rt':       entry.get('Rt', 2),
            'Sz':       entry.get('Sz', 8),
            'Vz':       entry.get('Vz', 7),
            'C1':       entry.get('C1', C1_SATELLITE),
            'C2':       entry.get('C2', C2_SATELLITE),
            'Cn':       CN_ORBIT,
            # RA_hr / Dec_deg left absent; frontend uses orbs live data
        }
        items.append(item)
    return items
 
 

async def refresh_orbital_cache_from_internet(logger_instance) -> None:
    """Calls _fetch_* directly using the original query in OtherIDs. Never calls create_* wrappers."""
    cache = load_cache()
    for main_id, entry in cache.items():
        source = entry.get('source', '')
        query  = entry.get('OtherIDs', '').strip() or main_id
        try:
            if source == 'celestrak':
                await _fetch_tle_from_celestrak(logger_instance, query)
            elif source == 'jpl':
                await _fetch_xephem_from_jpl(logger_instance, query)
        except Exception as ex:
            logger_instance.info(f'orbital_cache refresh: "{main_id}" offline or failed — {ex}')


# ── Orbital Position Refresh Methods ─────────────────────────────────────────────────────────────

def find_closest_orbital(observer, scope_ra, scope_dec):
    """ Refresh orbital data with current observer and scope position """
    update_orbital_positions(observer, scope_ra, scope_dec)
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

def update_orbital_positions(observer, scope_ra=0.0, scope_dec=0.0):
    """ Updates Orbital entities RADec, AzAlt, Proximity properties. PID Control loop updates body """
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

BUILTIN_ORBITAL_KEYS = {
    "Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn",
    "Uranus","Neptune","Pluto","Phobos","Deimos","Io","Europa",
    "Ganymede","Callisto","Titan","Iapetus","Rhea","Dione",
    "Tethys","Enceladus","Mimas","Hyperion"
}

def compose_orbital_positions_for_catalog():
    export_data = {}
    for key, entity in orbital_data.items():
        entry = {
            "RA_hr": entity.get("RA_hr"),           # BEWARE these are JNow Epoch, Most Pilot catalog are J2000
            "DEC_deg": entity.get("DEC_deg"),
            "Proximity": entity.get("Proximity"),
        }
        if key not in BUILTIN_ORBITAL_KEYS:
            entry["MainID"]   = entity.get("MainID", key)
            entry["OtherIDs"] = entity.get("OtherIDs", "")
            entry["C1"]       = entity.get("C1", C1_SATELLITE)
            entry["C2"]       = entity.get("C2", C2_SATELLITE)
            entry["Cn"]       = CN_ORBIT
            entry["RA_hr"]    = entity.get("RA_hr")    # already set above, explicit for clarity
            entry["DEC_deg"]  = entity.get("DEC_deg")
        export_data[key] = entry
    return export_data

# ── Standard Orbital Bodies included in Catalog ─────────────────────────────────────────────────────────────

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




# ── Custom Catalog Items (user defined + cached orbitals) ──────────────────────────────────────

def loadCustomCatalogDataFromFile(path=CATALOG_PATH):
    """
    Loads the custom catalog JSON file, stripping // comments, trailing commas,
    and enforcing required schema + default values.
 
    Also merges in any cached orbitals from data/orbitals.json so that
    satellites, comets, and asteroids previously fetched online appear in the
    catalog at dark sites without internet access.
 
    Returns:
        list of dicts (always)
    """
    if not os.path.exists(path):
        user_items = []
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
 
            # Remove comment lines --- Example matched: "// comment", "   // comment"
            clean = re.sub(r'^\s*//.*$', '', raw, flags=re.MULTILINE)
            # Remove trailing commas BEFORE } --- Example:  "Name": "Galaxy", }
            clean = re.sub(r',\s*}', '}', clean)
            # --- Remove trailing commas BEFORE ] --- Example:  }, ]
            clean = re.sub(r',\s*]', ']', clean)
 
            items = json.loads(clean)
 
            # Ensure JSON is an array
            if not isinstance(items, list):
                raise ValueError("Catalog: Top-level catalog.json must be an array")
 
            user_items = []
            for obj in items:
                if not isinstance(obj, dict):
                    continue  # skip invalid items
                cleaned = {}
                # Ensure all required fields exist with correct types / defaults
                for key, default in DEFAULTS.items():
                    value = obj.get(key, default)
                    if isinstance(default, int):
                        try:
                            value = int(value)
                        except:
                            value = default
                    else:
                        value = str(value) if value is not None else ""
                    cleaned[key] = value
 
                # Copy any extra fields (e.g., RA_hr, Dec_deg, etc.)
                for key, value in obj.items():
                    if key not in cleaned:
                        cleaned[key] = value
 
                # Clamp numeric ranges 
                cleaned["Rt"] = max(0, min(5, cleaned["Rt"]))
                cleaned["Sz"] = max(0, min(8, cleaned["Sz"]))
                cleaned["Vz"] = max(0, min(7, cleaned["Vz"]))
                cleaned["C1"] = max(0, min(10, cleaned["C1"]))
                cleaned["C2"] = max(0, min(41, cleaned["C2"]))
                cleaned["Cn"] = max(0, min(85, cleaned["Cn"]))
                user_items.append(cleaned)
 
        except Exception as e:
            print(f"Catalog: Error loading custom catalog: {e}")
            user_items = []
 
    # ── Merge cached orbitals ─────────────────────────────────────────────
    # load_cached_catalog_items() returns a list of dicts with standard
    # catalog fields (MainID, Name, C1, C2, Cn=84, etc.).  We skip any
    # entry whose MainID already appears in user_items (user catalog wins).
    try:
        existing_ids = {item.get('MainID') for item in user_items}
        orbital_items = restore_catalog_items_from_orbital_cache()
        for orb in orbital_items:
            if orb.get('MainID') not in existing_ids:
                user_items.append(orb)
    except Exception as e:
        print(f"Catalog: Error merging cached orbitals: {e}")
 
    return user_items



