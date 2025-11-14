import ephem
from shr import rad2deg, rad2hr
from shr import angular_separation
import requests

def compose_orbital_export():
    export_data = {}
    for key, entity in orbital_data.items():
        export_data[key] = {
            "RA_hr": entity.get("RA_hr"),           # BEWARE these are JNow Epoch, Most Pilot catalog are J2000
            "DEC_deg": entity.get("DEC_deg"),
            "Proximity": entity.get("Proximity"),
        }
    return export_data

def create_satellite_orbital(logger, norad_id):
    """
    Fetches TLE data from Celestrak for a given NORAD ID, creates a PyEphem satellite,
    stores it in orbital_data using the satellite name, and returns (name, body).
    Parameters:
        norad_id (int or str): NORAD catalog number of the satellite.
    Returns:
        tuple: (name, ephem.EarthSatellite) if successful
        Logs any error condition and returns (None, None) if unsuccessful
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
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.info(f'Failed to fetch TLE data for {norad_id}, {e}:')
        return None, None

    lines = response.text.strip().splitlines()
    if len(lines) < 3:
        logger.info(f'Incomplete TLE data for NORAD ID: {norad_id}')
        return None, None

    name, line1, line2 = lines[:3]
    try:
        body = ephem.readtle(name, line1, line2)
    except Exception as e:
        logger.info(f'Failed to parse TLE data for NORAD ID: {norad_id}, {e}')
        return None, None

    orbital_data[name] = { "body": body }
    return name, body



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


