import axios from 'axios'

export type LocationResult =
  | { success: true; data: LocationData }
  | { success: false; reason: 'no-location' | 'lookup-failed' }

export interface LocationData {
  location: string
  site_elevation: number
  site_pressure: number
  site_latitude: number
  site_longitude: number
}

export const toRadians = (d: number) => d * Math.PI / 180;
export const toDegrees = (r: number) => r * 180 / Math.PI;


// Retrieve navigator geolocation (requires HTTPS hosting of app)
async function getNavigatorLocation(): Promise<{ lat: number; lon: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null)

    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 3000 }
    )
  })
}

// Retrieve IP-based location as a backup
// Note: This may not be accurate and requires an external service
async function getIPLocation(): Promise<{ lat: number; lon: number } | null> {
  try {
    const { data } = await axios.get('https://ipapi.co/json/')
    return { lat: data.latitude, lon: data.longitude }
  } catch {
    return null
  }
}

// Retrieve location name from OpenStreetMap Nominatim
async function getLocationName(lat: number, lon: number): Promise<string> {
  try {
    const { data } = await axios.get('https://nominatim.openstreetmap.org/reverse', {
      params: { lat, lon, format: 'json', addressdetails: 1 }
    });
    const { suburb, city, country } = data.address || {};
    const nameParts = [suburb, city, country].filter(Boolean);
    const name = nameParts.join(', ');
    // Optional: trim to 50 characters
    return name || 'Unknown location';
  } catch {
    return 'Unknown location';
  }
}

// Retrieve elevation from Open-Elevation (use open-metro.com data instead for elevation)
// async function getElevation(lat: number, lon: number): Promise<number> {
//   try {
//     const { data } = await axios.get('https://api.open-elevation.com/api/v1/lookup', {
//       params: {
//         locations: `${lat},${lon}`
//       }
//     })
//     return data.results?.[0]?.elevation || 100
//   } catch {
//     return 100
//   }
// }

// Retrieve elevation and pressure from Open-Meteo Weather API
export async function getWeatherData(lat: number, lon: number): Promise<{ pressure: number; elevation: number }> {
    const { data } = await axios.get('https://api.open-meteo.com/v1/forecast', {
        params: { latitude: lat, longitude: lon, hourly: 'surface_pressure', current_weather: true, timezone: 'auto' }
    });
    const pressure = data.hourly?.surface_pressure?.[0] ?? 1013;
    const elevation = data.elevation ?? 100; // fallback if missing
    return { pressure, elevation };
}

export async function getLocationServices(inputLat?: number, inputLon?: number): Promise<LocationResult> {
/**
 * Retrieves enriched location metadata based on latitude and longitude input.
 * If coordinates are not provided, attempts to infer location via browser geolocation or IP fallback.
 * Returns site coordinates, elevation, pressure, and a human-readable location name.
 * If no location can be determined or external lookups fail, returns a structured failure response.
 */
  let lat = inputLat
  let lon = inputLon

  // If lat/lon not provided, try to get from browser or IP
  if (typeof lat !== 'number' || typeof lon !== 'number') {
    const browserLoc = await getNavigatorLocation()
    if (browserLoc) {
      lat = browserLoc.lat
      lon = browserLoc.lon
    } else {
      const ipLoc = await getIPLocation()
      if (ipLoc) {
        lat = ipLoc.lat
        lon = ipLoc.lon
      } else {
        return { success: false, reason: 'no-location' }
      }
    }
  }

  // Now we have lat/lon, get location name and weather data
  try {
    const [location, weather] = await Promise.all([
      getLocationName(lat, lon),
      getWeatherData(lat, lon)
    ])
    return {
      success: true,
      data: {
        site_latitude: lat,
        site_longitude: lon,
        location,
        site_elevation: weather.elevation,
        site_pressure: weather.pressure
      }
    }
  } catch {
    return { success: false, reason: 'lookup-failed' }
  }
}


export function deltalatlon2AzAlt(site_lat: number, site_lon: number, site_elev: number,
  lm_lat: number, lm_lon: number, lm_elevation: number): { azimuth: number; altitude: number } | null {
/**
 * Converts a landmark's latitude, longitude, and elevation into azimuth and altitude angles
 * relative to a site location defined by its latitude, longitude, and elevation.
 * Uses the Haversine formula for distance calculation and basic trigonometry for angles.
 * Returns null if any input is invalid.
 */
    if (
      [site_lat, site_lon, site_elev, lm_lat, lm_lon, lm_elevation].some(v => typeof v !== 'number' || isNaN(v))
    ) return null 

    // Convert to radians
    const φ1 = toRadians(site_lat)
    const λ1 = toRadians(site_lon)
    const φ2 = toRadians(lm_lat)
    const λ2 = toRadians(lm_lon)

    // Δ values
    const Δλ = λ2 - λ1
    const Δφ = φ2 - φ1

    // Haversine distance (horizontal)
    const R = 6371000 // Earth radius in meters
    const a = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    const horizontalDist = R * c

    // Elevation difference
    const Δelev = lm_elevation - site_elev

    // Altitude angle
    const alt = toDegrees(Math.atan2(Δelev, horizontalDist))

    // Azimuth angle (bearing from site to landmark)
    const y = Math.sin(Δλ) * Math.cos(φ2)
    const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ)
    const az = (toDegrees(Math.atan2(y, x)) + 360) % 360

    return { azimuth: az, altitude: alt }
}