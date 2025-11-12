import ephem
from shr import rad2deg, rad2hr

# Enum banding functions
def enum_alt(alt_deg):
    if alt_deg < 0:
        return 0
    elif alt_deg < 15:
        return 1
    elif alt_deg < 30:
        return 2
    elif alt_deg < 45:
        return 3
    elif alt_deg < 60:
        return 4
    elif alt_deg < 82:
        return 5
    else:
        return 6

def enum_az(az_deg):
    az = az_deg % 360
    if az < 22.5 or az >= 337.5:
        return 0  # North
    elif az < 67.5:
        return 1  # NE
    elif az < 112.5:
        return 2  # East
    elif az < 157.5:
        return 3  # SE
    elif az < 202.5:
        return 4  # South
    elif az < 247.5:
        return 5  # SW
    elif az < 292.5:
        return 6  # West
    else:
        return 7  # NW

def position_lookup(az_enum, alt_enum):
    az_lookup = {
        0: 'North', 1: 'NE', 2: 'East', 3: 'SE',
        4: 'South', 5: 'SW', 6: 'West', 7: 'NW'
    }
    alt_lookup = {
        0: 'Below-Horizon < 0°',
        1: 'Horizon (0–15°)',
        2: 'Low (15–30°)',
        3: 'Mid-Low (30–45°)',
        4: 'Mid-High (45–60°)',
        5: 'High (60–82°)',
        6: 'Near-Zenith > 82°'
    }

    az_str = az_lookup.get(az_enum, '')
    alt_str = alt_lookup.get(alt_enum, '').split()[0]


    if alt_enum in (0, 6):
        return alt_str
    elif alt_enum == 1:
        return f"At {az_str} {alt_str}"
    else:
        return f"{alt_str} {az_str}"


def compose_orbital_export():
    export_data = []
    for key, entity in orbital_data.items():
        export_data.append({
            "ID": key,
            "Name": entity.get("Name"),
            "MainID": entity.get("MainID"),
            "class": entity.get("class"),
            "C1": entity.get("C1"),
            "Rt": entity.get("Rt"),
            "Size": entity.get("Size"),
            "Magnitude": entity.get("Magnitude"),
            "RA_hr": entity.get("RA_hr"),
            "DEC_deg": entity.get("DEC_deg"),
            "Az_deg": entity.get("Az_deg"),
            "Alt_deg": entity.get("Alt_deg"),
            "Az": entity.get("Az"),
            "Alt": entity.get("Alt"),
            "Position": entity.get("Position"),
            "Proximity": entity.get("Proximity"),
            "notes": entity.get("notes")
        })
    return export_data


def update_orbital_data(observer):
    global orbital_data

    for key, entity in orbital_data.items():
        orbital = entity["body"]
        orbital.compute(observer)

        ra_hr = rad2hr(orbital.ra)
        dec_deg = rad2deg(orbital.dec)
        az_deg = rad2deg(orbital.az)
        alt_deg = rad2deg(orbital.alt)

        az_enum = enum_az(az_deg)
        alt_enum = enum_alt(alt_deg)
        position = position_lookup(az_enum, alt_enum)

        # Store computed values
        entity["RA_hr"] = ra_hr
        entity["DEC_deg"] = dec_deg
        entity["Az_deg"] = az_deg
        entity["Alt_deg"] = alt_deg
        entity["Az"] = az_enum
        entity["Alt"] = alt_enum
        entity["Position"] = position
        entity["Proximity"] = 0

orbital_data = {
    "Sun": {"body": ephem.Sun(), "Name": "Sun", "class": "Star", "MainID": "Sol", "Rt": 5, "Size": 0.53, "Magnitude": -26.74, "C1": 3, "notes": "Our star; never observe directly without solar filters."},
    "Moon": {"body": ephem.Moon(), "Name": "Moon", "class": "Natural Satellite", "MainID": "Luna", "Rt": 5, "Size": 0.52, "Magnitude": -12.7, "C1": 5, "notes": "Earth's natural satellite; excellent for lunar imaging."},
    "Mercury": {"body": ephem.Mercury(), "Name": "Mercury", "class": "Planet", "MainID": "IAU:199", "Rt": 3, "Size": 0.005, "Magnitude": -1.9, "C1": 4, "notes": "Inner planet; best seen during twilight."},
    "Venus": {"body": ephem.Venus(), "Name": "Venus", "class": "Planet", "MainID": "IAU:299", "Rt": 5, "Size": 0.01, "Magnitude": -4.9, "C1": 4, "notes": "Brightest planet; shows phases like the Moon."},
    "Mars": {"body": ephem.Mars(), "Name": "Mars", "class": "Planet", "MainID": "IAU:499", "Rt": 4, "Size": 0.006, "Magnitude": -2.9, "C1": 4, "notes": "Red planet; best at opposition for surface detail."},
    "Jupiter": {"body": ephem.Jupiter(), "Name": "Jupiter", "class": "Planet", "MainID": "IAU:599", "Rt": 5, "Size": 0.02, "Magnitude": -2.9, "C1": 4, "notes": "Largest planet; shows bands and moons easily."},
    "Saturn": {"body": ephem.Saturn(), "Name": "Saturn", "class": "Planet", "MainID": "IAU:699", "Rt": 5, "Size": 0.01, "Magnitude": -0.5, "C1": 4, "notes": "Famous for its rings; best viewed with a telescope."},
    "Uranus": {"body": ephem.Uranus(), "Name": "Uranus", "class": "Planet", "MainID": "IAU:799", "Rt": 2, "Size": 0.003, "Magnitude": 5.7, "C1": 4, "notes": "Faint blue-green disk; visible in binoculars."},
    "Neptune": {"body": ephem.Neptune(), "Name": "Neptune", "class": "Planet", "MainID": "IAU:899", "Rt": 2, "Size": 0.002, "Magnitude": 7.8, "C1": 4, "notes": "Distant blue planet; requires telescope."},
    "Pluto": {"body": ephem.Pluto(), "Name": "Pluto", "class": "Dwarf Planet", "MainID": "IAU:999", "Rt": 1, "Size": 0.0001, "Magnitude": 14.0, "C1": 4, "notes": "Dwarf planet; very faint, needs large aperture."},
    "Phobos": {"body": ephem.Phobos(), "Name": "Phobos", "class": "Martian Moon", "MainID": "IAU:401", "Rt": 1, "Size": 0.00005, "Magnitude": 11.3, "C1": 5, "notes": "Inner moon of Mars; extremely faint."},
    "Deimos": {"body": ephem.Deimos(), "Name": "Deimos", "class": "Martian Moon", "MainID": "IAU:402", "Rt": 1, "Size": 0.00004, "Magnitude": 12.4, "C1": 5, "notes": "Outer moon of Mars; very faint."},
    "Io": {"body": ephem.Io(), "Name": "Io", "class": "Galilean Moon", "MainID": "IAU:501", "Rt": 4, "Size": 0.001, "Magnitude": 5.0, "C1": 5, "notes": "Volcanically active; easily visible near Jupiter."},
    "Europa": {"body": ephem.Europa(), "Name": "Europa", "class": "Galilean Moon", "MainID": "IAU:502", "Rt": 4, "Size": 0.001, "Magnitude": 5.3, "C1": 5, "notes": "Icy surface; visible in small scopes."},
    "Ganymede": {"body": ephem.Ganymede(), "Name": "Ganymede", "class": "Galilean Moon", "MainID": "IAU:503", "Rt": 5, "Size": 0.0015, "Magnitude": 4.6, "C1": 5, "notes": "Largest moon in the solar system."},
    "Callisto": {"body": ephem.Callisto(), "Name": "Callisto", "class": "Galilean Moon", "MainID": "IAU:504", "Rt": 4, "Size": 0.0014, "Magnitude": 5.6, "C1": 5, "notes": "Dark, cratered surface; visible near Jupiter."},
    "Titan": {"body": ephem.Titan(), "Name": "Titan", "class": "Saturnian Moon", "MainID": "IAU:606", "Rt": 4, "Size": 0.0012, "Magnitude": 8.4, "C1": 5, "notes": "Thick atmosphere; visible in medium scopes."},
    "Iapetus": {"body": ephem.Iapetus(), "Name": "Iapetus", "class": "Saturnian Moon", "MainID": "IAU:608", "Rt": 3, "Size": 0.0008, "Magnitude": 10.2, "C1": 5, "notes": "Two-toned surface; brightness varies with orbit."},
    "Rhea": {"body": ephem.Rhea(), "Name": "Rhea", "class": "Saturnian Moon", "MainID": "IAU:605", "Rt": 3, "Size": 0.0009, "Magnitude": 10.0, "C1": 5, "notes": "Second-largest Saturn moon; faint but visible."},
    "Dione": {"body": ephem.Dione(), "Name": "Dione", "class": "Saturnian Moon", "MainID": "IAU:604", "Rt": 2, "Size": 0.0007, "Magnitude": 10.4, "C1": 5, "notes": "Bright icy surface; visible in large scopes."},
    "Tethys": {"body": ephem.Tethys(), "Name": "Tethys", "class": "Saturnian Moon", "MainID": "IAU:603", "Rt": 2, "Size": 0.0006, "Magnitude": 10.2, "C1": 5, "notes": "Small and faint; requires dark skies."},
    "Enceladus": {"body": ephem.Enceladus(), "Name": "Enceladus", "class": "Saturnian Moon", "MainID": "IAU:602", "Rt": 2, "Size": 0.0005, "Magnitude": 11.7, "C1": 5, "notes": "Bright icy moon with geysers; very faint."},
    "Mimas": {"body": ephem.Mimas(), "Name": "Mimas", "class": "Saturnian Moon", "MainID": "IAU:601", "Rt": 1, "Size": 0.0004, "Magnitude": 12.9, "C1": 5, "notes": "Small Saturnian moon with a large crater; faint and difficult to image."},
    "Hyperion": {"body": ephem.Hyperion(), "Name": "Hyperion", "class": "Saturnian Moon", "MainID": "IAU:610", "Rt": 1, "Size": 0.0005, "Magnitude": 14.1, "C1": 5, "notes": "Chaotic rotation and sponge-like surface; very faint."}
}


