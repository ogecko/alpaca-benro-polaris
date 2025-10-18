export type LevelKey = 'lg' | 'md' | 'sm';
export type UnitKey = 'deg' | 'hr';
export type SymbolKey = 'd' | 'm' | 's';
export type SymbolMap = Record<UnitKey, Record<SymbolKey, string>>;
export const symbol: SymbolMap = {
  deg: { d: '°', m: '′', s: '″' },
  hr:  { d: 'ʰ', m: 'ᵐ', s: 'ˢ' },
};


export function deg2dms(decimalDegrees: number | undefined, precision: number = 1, unit: UnitKey = 'deg') {

  if (decimalDegrees === undefined) return {}
  const sign = decimalDegrees < 0 ? '-' : '+';
  const totalSeconds = Math.abs(decimalDegrees) * 3600;

  let degrees = Math.floor(totalSeconds / 3600);
  const remainder = totalSeconds % 3600;
  let minutes = Math.floor(remainder / 60);
  const rawSeconds = remainder % 60;

  // Split seconds into integer and milliseconds
  let seconds = Math.floor(rawSeconds); // whole number
  let milliseconds = Math.round((rawSeconds - seconds) * 1000); // whole number

  // Handle overflow
  if (milliseconds >= 1000) {
    milliseconds = 0;
    seconds += 1;
  }
  if (seconds >= 60) {
    seconds = 0;
    minutes += 1;
  }
  if (minutes >= 60) {
    minutes = 0;
    degrees += 1;
  }

  // Format degreestr, minutestr, secondstr with fixed precision and relevant symbol
  const padLength = precision === 0 ? 2 : 3 + precision;
  const secondstr = `${rawSeconds.toFixed(precision).padStart(padLength, '0')}${symbol[unit].s}`;   // "nn.n", "nn.nn", "nn.nnn"
  const minutestr = `${minutes.toString().padStart(2, '0')}${symbol[unit].m}`;
  const degreestr = `${degrees.toString()}${symbol[unit].d}`;

  return {
    sign,
    degrees,
    minutes,
    seconds,
    milliseconds,
    degreestr,
    minutestr,
    secondstr,
  };
}


export function deg2fulldms(angle:number, precision: number = 1, unit:UnitKey = 'deg') {
  const dms = deg2dms(angle, precision, unit)
  const str = (dms ? ((dms.sign??'') + dms.degreestr + dms.minutestr + dms.secondstr) : '') 
  return str
}

export function dms2deg(str: string | undefined, unit: UnitKey = 'deg'): number {
  // check input format
  if (!str || typeof str !== 'string') return 0;

  // Normalize separators to colon
  const { d, m, s } = symbol[unit]
  const cleaned = str
    .replace(/[^\d.+-]+/g, ':') // Replace all non-numeric separators with colon
    .replace(new RegExp(`[${d}${m}${s}]`, 'g'), ':') // Replace unit symbols with colon
    .trim()

  // Extract sign
  const signMatch = cleaned.match(/^[-+]/)
  const sign = signMatch?.[0] === '-' ? -1 : 1

  // Split and parse parts
  const parts = cleaned.split(':').map(p => parseFloat(p)).filter(p => !isNaN(p))
  if (parts.length === 0) return 0
  
  while (parts.length < 3) {
    parts.push(0)
  }

  const [degreesRaw = 0, minutes = 0, seconds = 0] = parts
  const degrees = Math.abs(degreesRaw)
  const decimal = degrees + minutes / 60 + seconds / 3600

  return sign * decimal
}



export function angularDifference(a:number, b:number) {
  return ((b - a + 180) % 360 + 360) % 360 - 180;
}

/**
 * Computes angular separation (in degrees) between two azimuth/altitude points.
 * Uses spherical law of cosines and handles azimuth wrapping.
 */
export function angularSeparation(
  az1: number, alt1: number,
  az2: number, alt2: number
): number {
  const alt1Rad = toRad(alt1);
  const alt2Rad = toRad(alt2);
  const azDiffRad = toRad(Math.abs(angularDifference(az1, az2)));

  const cosSep = Math.sin(alt1Rad) * Math.sin(alt2Rad) +
                 Math.cos(alt1Rad) * Math.cos(alt2Rad) * Math.cos(azDiffRad);

  const sepRad = Math.acos(Math.min(Math.max(cosSep, -1), 1)); // Clamp for safety
  return toDeg(sepRad);
}



export function isAngleBetween(angle:number, min:number, max:number) {
  const diffToMin = angle - min
  const diffToMax = angle - max
  return diffToMin >= 0 && diffToMax <= 0;
}

// Wraps angle to [0, 360)
export function wrapTo360(angle: number) {
  return ((angle % 360) + 360) % 360;
}

// Wraps angle to [-180, +180)
export function wrapTo180(angle: number) {
  return ((angle + 180) % 360 + 360) % 360 - 180;
}

// Wraps angle to [-90, +90)
export function wrapTo90(angle: number) {
  return ((angle + 90) % 180 + 180) % 180 - 90;
}

// Wraps angle to [0, 24)
export function wrapTo24(angle: number) {
  return ((angle % 24) + 24) % 24;
}


export const toRad = (d: number) => d * Math.PI / 180;
export const toDeg = (r: number) => r * 180 / Math.PI;

// calculates the RA rising and setting values for a given Declination, Lattitude and Local Sidereal Time
export function raAtAltitudeZero(decDeg: number, latDeg: number, lstDeg: number): number[] | null {

  const dec = toRad(decDeg);
  const lat = toRad(latDeg);

  const cosHA = -Math.sin(lat) * Math.sin(dec) / (Math.cos(lat) * Math.cos(dec));

  if (Math.abs(cosHA) > 1) return null; // always above or below horizon

  const HA1 = toDeg(Math.acos(cosHA));
  const HA2 = -HA1;

  const RA1 = (lstDeg - HA1 + 360) % 360;
  const RA2 = (lstDeg - HA2 + 360) % 360;

  return [RA1, RA2]; // rising and setting RA
}


// Calculate range of Dec that is always above or below the horizon
// eg invalidDeclinationRange(-33.9)
// Output:
// alwaysAbove: [-90, -56.1]   // Southern circumpolar zone
// alwaysBelow: [56.1, 90]     // Northern never-rises zone
export function invalidDeclinationRange(latDeg: number): { alwaysAbove?: [number, number], alwaysBelow?: [number, number] } {
  const absLat = Math.abs(latDeg);

  if (absLat >= 90) {
    // At the poles: all Dec > 0 or < 0 are always above/below
    return latDeg > 0
      ? { alwaysBelow: [-90, 0], alwaysAbove: [0, 90] }
      : { alwaysBelow: [0, 90], alwaysAbove: [-90, 0] };
  }

  const decAbove = latDeg > 0
    ? 90 - absLat
    : -(90 - absLat);

  const decBelow = latDeg > 0
    ? -(90 - absLat)
    : 90 - absLat;

  return {
    alwaysAbove: latDeg > 0 ? [decAbove, 90] : [-90, decAbove],
    alwaysBelow: latDeg > 0 ? [-90, decBelow] : [decBelow, 90]
  };
}

/**
 * Computes approximate azimuth and altitude for a celestial object
 * given RA/Dec, observer latitude and longitude, and a JS Date.
 */
export function getAzAlt(
  raHr: number,           // Right Ascension in hours
  decDeg: number,         // Declination in degrees
  latDeg: number,         // Observer latitude in degrees
  lonDeg: number,         // Observer longitude in degrees (east positive)
  date: Date = new Date() // UTC or local time, defaulting to now
): { az: number; alt: number } {
  // Convert UTC time to Julian Date
  const JD = (date.getTime() / 86400000) + 2440587.5;

  // Calculate Greenwich Mean Sidereal Time (GMST) in hours
  const T = (JD - 2451545.0) / 36525;
  const GMST = (280.46061837 + 360.98564736629 * (JD - 2451545.0) +
                0.000387933 * T * T - T * T * T / 38710000) % 360;

  const lstDeg = (GMST + lonDeg + 360) % 360;
  const lstHr = lstDeg / 15;

  const raDeg = raHr * 15;
  const haDeg = (lstHr * 15 - raDeg + 360) % 360;

  const haRad = toRad(haDeg);
  const decRad = toRad(decDeg);
  const latRad = toRad(latDeg);

  // Altitude
  const sinAlt = Math.sin(decRad) * Math.sin(latRad) +
                 Math.cos(decRad) * Math.cos(latRad) * Math.cos(haRad);
  const altRad = Math.asin(sinAlt);
  const altDeg = toDeg(altRad);

  // Azimuth
  const cosAz = (Math.sin(decRad) - Math.sin(altRad) * Math.sin(latRad)) /
                (Math.cos(altRad) * Math.cos(latRad));
  let azRad = Math.acos(Math.min(Math.max(cosAz, -1), 1));

  if (Math.sin(haRad) > 0) {
    azRad = 2 * Math.PI - azRad;
  }

  const azDeg = toDeg(azRad);
  return { az: azDeg, alt: altDeg };
}


export function computeVisibilityRanges(raDeg: number, decDeg: number) {
  const toRadians = (deg:number) => deg * Math.PI / 180;
  const toDegrees = (rad:number) => rad * 180 / Math.PI;
  const wrap = (deg:number) => ((deg % 360) + 360) % 360;

  const latitude = 0, siderealTimeDeg=0 ;//***********************************TODO************************** */
  const phi = toRadians(latitude);

  function raInvalidRanges(dec:number) {
    const delta = toRadians(dec);
    const cosH = -Math.tan(phi) * Math.tan(delta);

    if (cosH < -1) return []; // Always visible
    if (cosH > 1) return [[0, 360]]; // Always below

    const H = toDegrees(Math.acos(cosH));
    const raMin = wrap(siderealTimeDeg - H);
    const raMax = wrap(siderealTimeDeg + H);

    if (raMin < raMax) {
      return [[0, raMin], [raMax, 360]];
    } else {
      return [[raMax, raMin]]; // Wraparound
    }
  }

  function decInvalidRanges(ra:number) {
    const H = toRadians(wrap(siderealTimeDeg - ra));
    const cosH = Math.cos(H);
    const tanDelta = -Math.cos(phi) * cosH / Math.sin(phi);

    if (Math.abs(tanDelta) < 1e-6) return [[-90, 90]]; // Equator always visible

    const delta = toDegrees(Math.atan(tanDelta));
    if (delta < -90) return [[-90, 90]]; // Always below
    if (delta > 90) return []; // Always above

    return [[-90, delta]];
  }

  return {
    RAWarnings: raInvalidRanges(decDeg),
    DecWarnings: decInvalidRanges(raDeg)
  };
}
