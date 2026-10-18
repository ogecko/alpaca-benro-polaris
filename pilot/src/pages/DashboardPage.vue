<template>
  <q-page class="q-pa-sm">

    <StatusBanners />

    <!----- Page header ----->
    <div class="row q-pa-xs items-center q-col-gutter-sm">

      <!----- LHS Action Buttons ----->
      <div class="q-pb-sm">
        <div class="q-gutter-md ">
          <q-btn-group >
            <q-btn
              :icon="ui.coordFrame === 0 ? 'mdi-compass' : ui.coordFrame === 1 ? 'mdi-telescope' : 'mdi-cryengine'"
              glossy :dense="btnDense" :size="btnSize" color="secondary" push outline
              @click="ui.cycleCoordFrame()"
            >
              <q-tooltip>
                Coordinate frame: {{  ui.coordFrame === 0 ? 'Topocentric (Az, Alt, Roll)' : ui.coordFrame === 1 ? 'Equatorial (RA, Dec, PA)' : 'Galactic (l, b, GPA)' }}
              </q-tooltip>
            </q-btn>
            <q-btn v-if="isDeviated" icon="mdi-format-horizontal-align-center"  glossy :dense="btnDense" :size="btnSize" color="secondary" outline @click="onResetSP">
              <q-tooltip>Reset all setpoints to their current values.</q-tooltip>
            </q-btn>
            <q-btn icon="mdi-home"  glossy :dense="btnDense" :size="btnSize" color="secondary" :outline="p.pidmode!='HOMING'"  @click="onHome">
              <q-tooltip>Return the mount to its Home position</q-tooltip>
            </q-btn>
            <q-btn icon="mdi-parking"  glossy :dense="btnDense" :size="btnSize" color="secondary" :outline="p.pidmode!='PARKING'"  @click="onPark">
              <q-tooltip>Return the mount to its Park position.</q-tooltip>
            </q-btn>
            <q-btn icon="mdi-stop" glossy :dense="btnDense" :size="btnSize" color="secondary" :outline="isStopOutline" @click="onAbort">
              <q-tooltip>Stop all motion of the mount.</q-tooltip>
            </q-btn>
          </q-btn-group>
          <q-btn-dropdown :dense="btnDense" glossy :size="btnSize" color="secondary" split :outline="!p.tracking" @click="onTrack">
            <template #label>
              <q-icon name="mdi-star-shooting-outline"/>
              <q-tooltip>Toggle tracking on and off.</q-tooltip>
            </template>
            <q-list  dense >
              <q-item clickable v-close-popup :active="p.trackingrate==0" active-class="bg-secondary text-white" @click="onTrackRate(0)">
                <q-item-section><q-item-label>Sidereal</q-item-label></q-item-section>
              </q-item>
              <q-item clickable v-close-popup :active="p.trackingrate==1" active-class="bg-secondary text-white" @click="onTrackRate(1)">
                <q-item-section><q-item-label>Lunar</q-item-label></q-item-section>
              </q-item>
              <q-item clickable v-close-popup :active="p.trackingrate==2" active-class="bg-secondary text-white" @click="onTrackSolar()">
                <q-item-section><q-item-label>Solar</q-item-label></q-item-section>
              </q-item>
              <q-item clickable v-close-popup :active="p.trackingrate==3" active-class="bg-secondary text-white" @click="onTrackRate(3)">
                <q-item-section><q-item-label>Custom</q-item-label></q-item-section>
              </q-item>
            </q-list>
          </q-btn-dropdown>
        </div>
      </div>

      <!----- Center Tracking Info ----->
      <!-- <div class="row col-6 col-sm-4 text-positive text-h5 q-gutter-sm justify-center ">
        <div v-if="p.tracking">
          <span>{{p.trackingratestr}}</span> 
          <q-chip color="positive">Tracking</q-chip>
        </div>
      </div> -->

      <q-space />
      <!----- RHS Chip Status Info ----->
      <PIDStatus />
    </div>

    <!----- Dynamic Set of 3 Radial Scales ----->
    <div class="row">
       <div v-for="(cfg, i) in displayConfig" :key="i" class="col-12 col-md-6 col-lg-4 col-xl-3">
          <ScaleDisplay
            :label="cfg.label"
            :pv="cfg.pv"
            :sp="cfg.sp"
            :lst="p.siderealtime"
            :domain="cfg.domain"
            :warnings="cfg.warnings"
            @clickScale="onClickScale"
            @clickFabAngle="onClickFabAngle"
            @clickMove="onClickMove"
          />
        </div>
        <div v-if="cfg.show_panels==true" class="col-12 col-md-6 col-lg-4 col-xl-3 q-pa-lg justify-center content-center">
          <div class="text-h6 text-grey-6">
            <q-btn round icon="mdi-crosshairs-gps" @click="onClickRecenterGrid">
              <q-tooltip>Recenter the grid to match the mount’s current orientation.</q-tooltip>
            </q-btn>
            Panel Navigation
          </div>
          <PanoNavigation />
        </div>

        <StatusPanel />
      </div>

  </q-page>
</template>

<script setup lang="ts" >

import { useQuasar } from 'quasar'
import { onMounted, computed, ref } from 'vue'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'src/stores/config'
import { useUIStore } from 'src/stores/ui'
import ScaleDisplay  from 'src/components/ScaleDisplay.vue'
import StatusBanners from 'src/components/StatusBanners.vue'
import PanoNavigation from 'src/components/PanoNavigation.vue'
import PIDStatus from 'src/components/PIDStatus.vue'
import StatusPanel  from 'src/components/StatusPanel.vue'
import type { DomainStyleType } from 'src/components/ScaleDisplay.vue'
import { angularDifference } from 'src/utils/angles'
import { zeroM2Roll } from 'src/utils/zeroM2'


const $q = useQuasar()
const dev = useDeviceStore()
const p = useStatusStore()
const cfg= useConfigStore()
const ui = useUIStore()
const isStopOutline = ref<boolean>(true)

// ------------------- Layout Configuration Data ---------------------

const noWarnings:     [number, number][] = []
const glatWarnings:   [number, number][] = [[90,200],[-90,-200]]
const azWarnings = computed((): [number, number][] => {
    if (!cfg.advanced_eq_mode) return []        // level: M2 doesn't depend on Az
    const alt = Math.round((p.altitude ?? 0) * 2) / 2, roll = Math.round((p.roll ?? 0) * 2) / 2
    return eqWarningRuns(p.azimuth ?? 0, (az) => [az, alt, roll])
})
const rollWarnings = computed((): [number, number][] => {
    if (cfg.advanced_eq_mode) return eqRotationWarnings(p.roll ?? 0)
    const altRounded = Math.round((p.altitude ?? 0) * 2) / 2 // round to 0.5 deg
    const maxRoll = altitudeToMaxRoll(altRounded)
    if (maxRoll <= 0) return []
    const rollAdj = p.roll_adj ?? 0
    return [[maxRoll + rollAdj, 270], [-maxRoll + rollAdj, -270]]
})
const paWarnings = computed((): [number, number][] => {
    if (!cfg.advanced_eq_mode) return []        // level: PA follows roll, whose limit the Roll dial shows
    return eqRotationWarnings(p.positionangle ?? 0)
})
const altWarnings = computed((): [number, number][] => {
    if (cfg.advanced_eq_mode) {
        const az = Math.round((p.azimuth ?? 0) * 2) / 2, roll = Math.round((p.roll ?? 0) * 2) / 2
        return eqWarningRuns(p.altitude ?? 0, (alt) => [az, alt, roll])
    }
    const rollAdj = p.roll_adj ?? 0
    const mechRoll = (p.roll ?? 0) - rollAdj
    const rollRounded = Math.round(mechRoll * 2) / 2 // round to 0.5 deg
    const maxAlt = altitudeToMaxRoll(rollRounded)
    if (maxAlt <= 0) return []
    return [[maxAlt, 270], [-maxAlt, -270]]
})
const raWarnings = computed((): [number, number][] => {
    const lst = Math.round((p.siderealtime ?? 0) * 4) / 4
    const dec = Math.round((p.declination   ?? 0) * 2) / 2
    const lat = cfg.site_latitude

    const cosHA = -Math.tan(lat * Math.PI / 180) * Math.tan(dec * Math.PI / 180)
    const haLimitHrs = cosHA > 1  ? 0  :   // never rises
                       cosHA < -1 ? 12 :   // circumpolar
                       Math.acos(cosHA) * 12 / Math.PI

    if (haLimitHrs >= 12) return []         // always visible, no warning
    // Safe window: [raWest, raEast] in raw (unwrapped) hours
    const raWest = lst - haLimitHrs         // western (past meridian) limit
    const raEast = lst + haLimitHrs         // eastern (not yet risen) limit
    return [                                // Warning zones are everything OUTSIDE [raWest, raEast].
        [raEast, raEast+12] as [number, number],
        [raWest-12, raWest] as [number, number],
    ]
})
const decWarnings = computed((): [number, number][] => {
    const lat = cfg.site_latitude
    const maxDec = Math.min(90, Math.round(lat + 90))
    const minDec = Math.max(-90, Math.round(lat - 90))
    const horizon: [number, number][] = [
        [maxDec, 200] as [number, number],
        [-200, minDec] as [number, number],
    ]
    if (!cfg.advanced_eq_mode) return horizon
    // Eq: the base frame is equatorial, so its altitude is Dec toward the visible pole and a Dec move at a fixed PA
    // keeps its roll. M2 stops at the cap around the pole: |base alt| > altitudeToMaxRoll(base roll).
    const maxBaseAlt = altitudeToMaxRoll(Math.round((p.proll ?? 0) * 2) / 2)
    const toDec = (lat >= 0 ? 1 : -1)
    const dec = p.declination ?? 0, baseAlt = p.paltitude ?? 0
    const capEdge = dec + toDec * (maxBaseAlt - baseAlt), farEdge = dec + toDec * (-maxBaseAlt - baseAlt)
    return [...horizon, [capEdge, capEdge + toDec * 200], [farEdge, farEdge - toDec * 200]]
})



const displayConfig = computed(() => {
    if (ui.coordFrame === 1) return [
        { label: 'Right Ascension', pv: p.rightascension, sp: p.deltarefRAhrs, domain: 'ra_24' as DomainStyleType,   warnings: raWarnings.value },
        { label: 'Declination',     pv: p.declination,    sp: p.deltaref[1],   domain: 'dec_180' as DomainStyleType, warnings: decWarnings.value },
        { label: 'Position Angle',  pv: p.positionangle,  sp: p.deltaref[2],   domain: 'pa_360' as DomainStyleType,  warnings: paWarnings.value }
    ]
    if (ui.coordFrame === 2) return [
        { label: 'Galactic Lon', pv: p.gpv[0], sp: p.gsp[0], domain: 'az_360' as DomainStyleType,   warnings: noWarnings },
        { label: 'Galactic Lat', pv: p.gpv[1], sp: p.gsp[1], domain: 'dec_180' as DomainStyleType,  warnings: glatWarnings },
        { label: 'Galactic PA',  pv: p.gpv[2], sp: p.gsp[2], domain: 'gpa_180' as DomainStyleType,  warnings: noWarnings }
    ]
    return [
        { label: 'Azimuth',  pv: p.azimuth,  sp: p.alpharef[0], domain: 'az_360' as DomainStyleType,   warnings: azWarnings.value },
        { label: 'Altitude', pv: p.altitude, sp: p.alpharef[1], domain: 'alt_90' as DomainStyleType,   warnings: altWarnings.value },
        { label: 'Roll',     pv: p.roll,     sp: p.alpharef[2], domain: 'roll_180' as DomainStyleType, warnings: rollWarnings.value }
    ]
})

const isDeviated = computed(() => {
  if (p.pidmode!='IDLE') return false
  if (ui.coordFrame === 2) return false
  const RAD = angularDifference(p.rightascension, p.deltarefRAhrs)
  const DecD = angularDifference(p.declination, p.deltaref[1]?? 0)
  const PAD = angularDifference(p.positionangle, p.deltaref[2]?? 0)
  const AzD = angularDifference(p.azimuth, p.alpharef[0]?? 0)
  const AltD = angularDifference(p.altitude, p.alpharef[1]?? 0)
  const RollD = angularDifference(p.roll, p.alpharef[2]?? 0)
  const delta = RAD*RAD + DecD*DecD + PAD*PAD + AzD*AzD + AltD*AltD + RollD*RollD
  return delta > 1
})

const btnSize = computed(() =>
  $q.screen.lt.sm ? 'md' : 'md'   // leave at md
)
const btnDense = computed(() =>
  $q.screen.lt.md ? true : false
)

const centerPanel = computed(() => Math.floor((cfg.rows * cfg.cols + 1) / 2))

// ------------------- Lifecycle Events ---------------------

onMounted(async () => {
})

// ------------------- Helper Functions ---------------------

function cannotPerformCommand(cmd:string) {
  if (p.atpark && cmd!='Park') {
      $q.notify({ message: `Cannot ${cmd} while mount is parked. Unpark Mount.`, type: 'negative', position: 'top', 
                           timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }]})
      return true
  }
  if (p.pidmode=='LIMIT') {
      $q.notify({ message: `Cannot ${cmd} while past motor angle limit. Reset the Limit.`, type: 'negative', position: 'top', 
                           timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }]})
      return true
  }
  return false
}

function altitudeToMaxRoll(altDeg: number, theta2Max = 81.5): number {
    const cosRatio = Math.cos(theta2Max * Math.PI / 180) / Math.cos(altDeg * Math.PI / 180)
    if (Math.abs(cosRatio) > 1) return 0
    return Math.acos(cosRatio) * 180 / Math.PI
}

// Eq mode (wedge): M2's angle is the angle between the camera's up axis and the base's M1 axis, cos(theta2) =
// up . baseZ (driver kinematics; level, baseZ is the zenith and this is altitudeToMaxRoll's cos(alt) x cos(roll)).
// The wedge tilts baseZ to the pole, so M2's limit is no longer a fixed band in Alt and Roll.

// A rotation about the boresight (Roll, PA) moves the base roll by the same amount, so its limit is the base
// frame's: |base roll| > altitudeToMaxRoll(base alt), offset to the dial's angle.
function eqRotationWarnings(pv: number): [number, number][] {
    const maxBaseRoll = altitudeToMaxRoll(Math.round((p.paltitude ?? 0) * 2) / 2)
    const offset = pv - (p.proll ?? 0)
    if (maxBaseRoll <= 0) return []
    return [[maxBaseRoll + offset, offset + 270], [-maxBaseRoll + offset, offset - 270]]
}

type Vec3 = [number, number, number]
type Quat = [number, number, number, number]   // w, x, y, z

function quatRotate(q: Quat, v: Vec3): Vec3 {
    const [w, x, y, z] = q
    const tx = 2 * (y * v[2] - z * v[1]), ty = 2 * (z * v[0] - x * v[2]), tz = 2 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx)]
}

// baseZ in topocentric (East, North, Up): camera = align x motor, so align = qpv x qstate^-1
function eqBaseZ(): Vec3 | null {
    const qpv = p.qpv as Quat, qs = p.qstate as Quat
    if (!qpv || !qs || (qs[0] === 0 && qs[1] === 0 && qs[2] === 0 && qs[3] === 0)) return null
    const motorZ = quatRotate(qs.map((c, i) => (i === 0 ? c : -c)) as Quat, [0, 0, 1])
    return quatRotate(qpv, motorZ)
}

// The camera's up axis (camera +X) at az/alt/roll, as the driver's q_to_azaltroll
function cameraUp(az: number, alt: number, roll: number): Vec3 {
    const A = az * Math.PI / 180, L = alt * Math.PI / 180, R = roll * Math.PI / 180
    const sA = Math.sin(A), cA = Math.cos(A), sL = Math.sin(L), cL = Math.cos(L), cR = Math.cos(R), sR = Math.sin(R)
    return [-cR * sL * sA - sR * cA, -cR * sL * cA + sR * sA, cR * cL]
}

// The parts of a dial (pv +-180, unwrapped like the dial's own domain) where M2 would pass THETA2_MAX
function eqWarningRuns(pv: number, pose: (v: number) => [number, number, number], step = 0.5): [number, number][] {
    const baseZ = eqBaseZ()
    if (!baseZ) return []
    const cosMax = Math.cos(81.5 * Math.PI / 180)
    const runs: [number, number][] = []
    let start: number | null = null
    const v0 = Math.round(pv / step) * step
    for (let v = v0 - 180; v <= v0 + 180; v += step) {
        const [az, alt, roll] = pose(v)
        const u = cameraUp(az, alt, roll)
        const blocked = u[0] * baseZ[0] + u[1] * baseZ[1] + u[2] * baseZ[2] < cosMax
        if (blocked && start === null) start = v
        if (!blocked && start !== null) { runs.push([start, v]); start = null }
    }
    if (start !== null) runs.push([start, v0 + 180])
    return runs
}

// ------------------- Event Handlers ---------------------

async function onResetSP() {
  const result = await dev.alpacaResetSP()
  console.log(result)
}


async function onTrack() {
  if (cannotPerformCommand('toggle tracking')) return
  const result = (p.tracking) ? await dev.alpacaTracking(false) : await dev.alpacaTracking(true);  
  console.log(result)
}

function onTrackSolar() {
  $q.notify({ type: 'warning', message: 'Are you sure you want to point the mount towards the Sun?', position: 'top', timeout: 0, 
    actions: [
      { icon: 'mdi-check', label: 'Yes', color: 'yellow', handler: () => { void (async () => { await onTrackRate(2); })(); }},
      { icon: 'mdi-close', label: 'No', color: 'white', handler: () => { /* ... */ } }
    ]
  });

}

async function onTrackRate(n: number) {
  const result = await dev.alpacaTrackingRate(n);  
  console.log(result)
}

async function onHome() {
  if (cannotPerformCommand('find Home')) return
  const result = await dev.alpacaFindHome();  
  console.log(result)
}

async function onPark() {
  if (cannotPerformCommand('Park')) return
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}

async function onAbort() {
  if (cannotPerformCommand('abort')) return
  isStopOutline.value = false
  setTimeout(() => { isStopOutline.value = true }, 200)
  const result = await dev.alpacaAbortSlew()
  console.log(result)
}


async function onClickScale(e: { label:string, angle: number, radialOffset: number }) {
  if (cannotPerformCommand('slew')) return

  if (e.label=="Azimuth") {
    const result = await dev.alpacaSlewToAltAz(p.alpharef[1] ?? 0, e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Altitude") {
    const result = await dev.alpacaSlewToAltAz(e.angle, p.alpharef[0] ?? 0)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Roll") {
    const result = await dev.alpacaMoveMechanical(e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Right Ascension") {
    const result = await dev.alpacaSlewToCoord(e.angle, p.deltaref[1] ?? 0)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Declination") {
    const result = await dev.alpacaSlewToCoord(p.deltarefRAhrs ?? 0, e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Position Angle") {
    const result = await dev.alpacaMoveAbsolute(e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Galactic Lon") {
    const result = await dev.alpacaSlewAbsolute({ l: e.angle, b: p.gsp[1] ?? 0, gpa: p.gsp[2] ?? 0 })
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Galactic Lat") {
    const result = await dev.alpacaSlewAbsolute({ l: p.gsp[0] ?? 0, b: e.angle, gpa: p.gsp[2] ?? 0 })
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else if (e.label=="Galactic PA") {
    const result = await dev.alpacaSlewAbsolute({ l: p.gsp[0] ?? 0, b: p.gsp[1] ?? 0, gpa: e.angle })
    console.log(`Change ${e.label} angle to ${e.angle}`, result);
  } else {
    console.log(`Click ${e.label} angle: ${e.angle}, offset: ${e.radialOffset}`);
  }
}


async function onClickFabAngle(e: { az?: number, alt?: number, roll?: number, zm2?: boolean }) {
  if (cannotPerformCommand('slew')) return

  if (e.zm2) {
    // ZM2: the roll that keeps M2 still for the next couple of hours (src/utils/zeroM2.ts)
    const best = zeroM2Roll(p.rightascension, p.declination, cfg.site_latitude, cfg.site_longitude)
    if (!best) {
      $q.notify({ message: 'ZM2: target too low to choose a roll', type: 'warning', position: 'top' })
      return
    }
    $q.notify({ message: `ZM2: Roll ${best.roll.toFixed(1)}°, M2 ~${best.m2Mean.toFixed(1)}"/s over the next ${best.minutes} min`,
                type: 'info', position: 'top', timeout: 5000 })
    await dev.alpacaMoveMechanical(best.roll)
    console.log('Fab ZM2:', best)
    return
  }

  const az = e.az ?? p.alpharef[0] ?? 0;
  const alt = e.alt ?? p.alpharef[1] ?? 0;
  if (e.roll !== undefined) {
    await dev.alpacaMoveMechanical(e.roll);
  }
  if (e.az !== undefined || e.alt !== undefined) {
    await dev.alpacaSlewToAltAz(alt, az);
  }
  console.log('Fab Angle:', e);
}



async function onClickRecenterGrid() {
  await dev.alpacaPanoGrid(`{"anchor":0, "ref_action":"update", "panel": ${centerPanel.value}}`)
  console.log('Recenter PanoGrid');
}


type AxisLabel =
  | "Azimuth"
  | "Altitude"
  | "Roll"
  | "Right Ascension"
  | "Declination"
  | "Position Angle"
  | "Galactic Lon"
  | "Galactic Lat"
  | "Galactic PA"



const axisMap:Record<AxisLabel, number> = {
  "Azimuth": 0,
  "Altitude": 1,
  "Roll": 2,
  "Right Ascension": 3,
  "Declination": 4,
  "Position Angle": 5,
  "Galactic Lon": 6,
  "Galactic Lat": 7,
  "Galactic PA": 8
}

async function onClickMove(e: { label: string, rateScale: number}) {
  console.log('ClickMove ', e.label, e.rateScale)
  if (!Object.keys(axisMap).includes(e.label)) return
  const axis = axisMap[e.label as AxisLabel] ?? -1
  const rate = (axis!=3) ? (e.rateScale / 200)*9 : (e.rateScale / 12)*9
  if (axis>=0 && axis<=8) {
    await dev.apiAction('Polaris:MoveAxis', `{"axis":${axis},"rate":${rate}}`)
  }
  //   // const result = await dev.alpacaMoveAxis(axis, rate)
}

</script>
