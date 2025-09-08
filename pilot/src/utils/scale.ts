import { symbol } from 'src/utils/angles'
import type { UnitKey } from 'src/utils/angles';

export type Step = {
  stepSize: number;                                  // decimal number of step size
  dFormatFn: (v: number, unit: UnitKey) => string;   // converts decimal number into formatted string with unit symbol
  level: string;                                     // level of step 'lg', 'md', 'sm'
}

export const steps: Step[] = [
  { stepSize: 200, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 180, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 90, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 30, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 15, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 10, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 6, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 5, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 3, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 2, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 1, dFormatFn: formatDegreesHr, level: 'lg' },
  { stepSize: 30 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 20 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 15 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 10 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 5 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 2 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 1 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 30 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 20 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 15 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 10 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 5 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 2 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
];

export function formatAngle(x: number, unit: UnitKey): string {
  if (x >= 1) return formatDegreesHr(x, unit)
  if (x >= 1/60) return formatArcMinutes(x, unit)
  return formatArcSeconds(x, unit)
}

export function formatDegreesHr(v: number, unit: UnitKey): string {
  return `${Math.round(v)}${symbol[unit].d}`;
}

export function formatArcMinutes(v: number, unit: UnitKey): string {
  const arcmin = Math.round((v % 1) * 60);
  const deg = Math.floor(v);
  return (arcmin === 0) ? formatDegreesHr(deg, unit) : `${arcmin}${symbol[unit].m}`;
}

export function formatArcSeconds(v: number, unit: UnitKey): string {
  const arcsec = Math.round((v * 3600) % 60);
  const arcmin = Math.floor((v * 60) % 60);
  const deg = Math.floor(v);
  if (arcsec !== 0) return `${arcsec}${symbol[unit].s}`;
  if (arcmin !== 0) return `${arcmin}${symbol[unit].m}`;
  return formatDegreesHr(deg, unit);
}

// Find the closest step tick the current number, for zoom in/out 
export function getClosestSteps(current: number): {
  nextUp?: number;
  nextDown?: number;
} {
  const step_numbers = steps.map(s => s.stepSize)
  let nextUp: number | undefined;
  let nextDown: number | undefined;

  for (const step of step_numbers) {
    if (step > current && (!nextUp || step - current < nextUp - current)) {
      nextUp = step;
    } else if (step < current && (!nextDown || current - step < current - nextDown)) {
      nextDown = step;
    }
  }

  const result: { nextUp?: number; nextDown?: number } = {};
  if (nextUp !== undefined) result.nextUp = nextUp;
  if (nextDown !== undefined) result.nextDown = nextDown;

  return result;
}


// pick the most suitable step size for the scale range
export function selectStep (scaleRange: number, minLabels: number, maxLabels: number): Step {

  // Filter steps by zoom eligibility
  const eligible = steps.filter(s => {
    if (s.level === 'sm' && scaleRange >= 8 / 60) return false;
    if (s.level === 'md' && scaleRange >= 8) return false;
    // if (s.level === 'lg' && scaleRange < 1) return false;
    return true;
  });

  // Prefer steps within label count bounds
  const preferred = eligible.find(s => {
    const count = Math.floor(scaleRange / s.stepSize);
    return count >= minLabels && count <= maxLabels;
  });

  // Fallback: pick coarsest eligible step that gives ≥ 1 label
  const fallback = eligible.find(s => Math.floor(scaleRange / s.stepSize) >= 1);

  return preferred ?? fallback ?? steps.find(s => s.level === 'lg')!;
}


