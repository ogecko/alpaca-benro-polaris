// Zero M2: the roll that keeps M2 (the motor carrying the camera's weight off its axis) as still as possible while
// tracking a target. M2's angle depends only on Alt and Roll: cos(theta2) = cos(roll) x cos(alt) (driver
// kinematics.azaltroll_to_theta_ik), and while tracking the roll drifts with the parallactic angle. Each candidate
// starting roll is followed over the coming hours, within the mount's roll limit, and the one with the least M2
// motion is chosen.
import { getAzAlt, toRad, toDeg, wrapTo180 } from 'src/utils/angles'

const THETA2_MAX = 81.5       // mechanical limit of M2 (driver kinematics.THETA2_MAX)
const MIN_ALT = 10            // the window ends when the target drops below this

// Parallactic angle, as the driver's kinematics.calc_parallactic_angle
function parallacticAngle(az: number, alt: number, lat: number): number {
  if (Math.abs(alt - 90) < 1e-6) return 0
  const num = Math.sin(toRad(az))
  const den = Math.tan(toRad(lat)) * Math.cos(toRad(alt)) - Math.sin(toRad(alt)) * Math.cos(toRad(az))
  return wrapTo180(-toDeg(Math.atan2(num, den)))
}

// Largest roll reachable at an altitude, as kinematics.altitude_to_maxroll
function maxRoll(alt: number): number {
  const c = Math.cos(toRad(THETA2_MAX)) / Math.cos(toRad(alt))
  return c >= 1 ? 0 : toDeg(Math.acos(Math.max(c, -1)))
}

function theta2(alt: number, roll: number): number {
  return toDeg(Math.acos(Math.min(1, Math.max(-1, Math.cos(toRad(roll)) * Math.cos(toRad(alt))))))
}

export interface ZeroM2Result {
  roll: number           // starting roll (deg)
  m2Mean: number         // M2's mean speed over the window ("/s)
  minutes: number        // length of the window it was chosen over
}

export function zeroM2Roll(raHr: number, decDeg: number, latDeg: number, lonDeg: number,
                           now: Date = new Date(), hours = 2, stepMin = 5): ZeroM2Result | null {
  // the target's path: alt and the change in parallactic angle (unwrapped) from now
  const alt: number[] = [], dpa: number[] = []
  let prev = 0, acc = 0
  for (let m = 0; m <= hours * 60; m += stepMin) {
    const { az, alt: a } = getAzAlt(raHr, decDeg, latDeg, lonDeg, new Date(now.getTime() + m * 60000))
    if (a < MIN_ALT) break
    const pa = parallacticAngle(az, a, latDeg)
    if (alt.length > 0) acc += wrapTo180(pa - prev)
    prev = pa
    alt.push(a); dpa.push(acc)
  }
  if (alt.length < 2) return null

  let best: ZeroM2Result | null = null, bestSteps = 0
  for (let r0 = -80; r0 <= 80; r0 += 0.5) {
    // while tracking, roll = r0 - change in parallactic angle (matches the motor rates logged on the mount)
    let steps = 0, sum = 0, t2prev = NaN
    for (let i = 0; i < alt.length; i++) {
      const r = r0 - (dpa[i] ?? 0), a = alt[i] ?? 0
      if (Math.abs(r) > maxRoll(a)) break
      const t2 = theta2(a, r)
      if (i > 0) { sum += Math.abs(t2 - t2prev); steps++ }
      t2prev = t2
    }
    if (steps === 0) continue
    const m2Mean = sum / (steps * stepMin / 60)          // deg/hr = "/s
    if (steps > bestSteps || (steps === bestSteps && best !== null && m2Mean < best.m2Mean)) {
      best = { roll: r0, m2Mean, minutes: steps * stepMin }
      bestSteps = steps
    }
  }
  return best
}
