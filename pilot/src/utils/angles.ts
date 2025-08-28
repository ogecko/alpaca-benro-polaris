export function deg2dms(decimalDegrees: number) {
  const sign = decimalDegrees < 0 ? '-' : '+';
  const totalSeconds = Math.abs(decimalDegrees) * 3600;

  let degrees = Math.floor(totalSeconds / 3600);
  const remainder = totalSeconds % 3600;
  let minutes = Math.floor(remainder / 60);
  let seconds = +(remainder % 60).toFixed(2);

  if (seconds >= 60.0) {
    seconds = 0.0;
    minutes += 1;
  }
  if (minutes >= 60) {
    minutes = 0;
    degrees += 1;
  }

  return { sign, degrees, minutes, seconds };
}
