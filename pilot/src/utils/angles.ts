export function deg2dms(decimalDegrees: number, precision: number) {
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

  // Format secondstr with fixed precision
  const padLength = precision === 0 ? 2 : 3 + precision;
  const secondstr = rawSeconds.toFixed(precision).padStart(padLength, '0'); // "nn.n", "nn.nn", "nn.nnn"
  const minutestr = minutes.toString().padStart(2, '0');


  return {
    sign,
    degrees,
    minutes,
    seconds,
    milliseconds,
    minutestr,
    secondstr,
  };
}
