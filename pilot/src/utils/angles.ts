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


export function angularDifference(a:number, b:number) {
  return ((b - a + 180) % 360 + 360) % 360 - 180;
}

export function isAngleBetween(angle:number, min:number, max:number) {
  const diffToMin = angularDifference(min, angle);
  const diffToMax = angularDifference(max, angle);
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
