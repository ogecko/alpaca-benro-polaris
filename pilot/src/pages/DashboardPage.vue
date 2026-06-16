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
              :icon="isEq === 0 ? 'mdi-compass' : isEq === 1 ? 'mdi-telescope' : 'mdi-cryengine'"
              glossy :dense="btnDense" :size="btnSize" color="secondary" push
              @click="isEq = ((isEq + 1) % 3) as 0 | 1 | 2"
            >
              <q-tooltip>
                Coordinate frame: {{  isEq === 0 ? 'Topocentric (Az, Alt, Roll)' : isEq === 1 ? 'Equatorial (RA, Dec, PA)' : 'Galactic (l, b, GPA)' }}
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
        <div v-if="!(p.pidmode=='PARK')" class="col-12 col-md-6 col-lg-4  col-xl-3 row justify-center ">
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[0]" :position="p.zetameas[0]" label="M1" />
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[1]" :position="p.zetameas[1]" label="M2" />
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[2]" :position="p.zetameas[2]" label="M3" />
        </div>
      </div>

  </q-page>
</template>

<script setup lang="ts" >

import { useQuasar } from 'quasar'
import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'src/stores/config'
import ScaleDisplay  from 'src/components/ScaleDisplay.vue'
import StatusBanners from 'src/components/StatusBanners.vue'
import SpinnerSpeed from 'src/components/SpinnerSpeed.vue'
import PanoNavigation from 'src/components/PanoNavigation.vue'
import PIDStatus from 'src/components/PIDStatus.vue'
import type { DomainStyleType } from 'src/components/ScaleDisplay.vue'
import { angularDifference } from 'src/utils/angles'


const $q = useQuasar()
const route = useRoute()
const dev = useDeviceStore()
const p = useStatusStore()
const cfg= useConfigStore()
const isEq = ref<0 | 1 | 2>(0)
const isStopOutline = ref<boolean>(true)

// ------------------- Layout Configuration Data ---------------------

const noWarnings:     [number, number][] = []
const altWarnings:    [number, number][] = [[81.5, 200], [-200, -81.5]]
const glatWarnings:   [number, number][] = [[90,200],[-90,-200]]
const rollWarnings = computed((): [number, number][] => {
    const altRounded = Math.round((p.altitude ?? 0) * 2) / 2 // round to 0.5 deg
    const maxRoll = altitudeToMaxRoll(altRounded)
    if (maxRoll <= 0) return []
    return [[maxRoll, 200], [-maxRoll, -200]]
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
    return [
        [maxDec, 200] as [number, number],
        [-200, minDec] as [number, number],
    ]
})



const displayConfig = computed(() => {
    if (isEq.value === 1) return [
        { label: 'Right Ascension', pv: p.rightascension, sp: p.deltarefRAhrs, domain: 'ra_24' as DomainStyleType,   warnings: raWarnings.value },
        { label: 'Declination',     pv: p.declination,    sp: p.deltaref[1],   domain: 'dec_180' as DomainStyleType, warnings: decWarnings.value },
        { label: 'Position Angle',  pv: p.positionangle,  sp: p.deltaref[2],   domain: 'pa_360' as DomainStyleType,  warnings: noWarnings }
    ]
    if (isEq.value === 2) return [
        { label: 'Galactic Lon', pv: p.gpv[0], sp: p.gsp[0], domain: 'az_360' as DomainStyleType,   warnings: noWarnings },
        { label: 'Galactic Lat', pv: p.gpv[1], sp: p.gsp[1], domain: 'dec_180' as DomainStyleType,  warnings: glatWarnings },
        { label: 'Galactic PA',  pv: p.gpv[2], sp: p.gsp[2], domain: 'gpa_180' as DomainStyleType,  warnings: noWarnings }
    ]
    return [
        { label: 'Azimuth',  pv: p.azimuth,  sp: p.alpharef[0], domain: 'az_360' as DomainStyleType,   warnings: noWarnings },
        { label: 'Altitude', pv: p.altitude, sp: p.alpharef[1], domain: 'alt_90' as DomainStyleType,   warnings: altWarnings },
        { label: 'Roll',     pv: p.roll,     sp: p.alpharef[2], domain: 'roll_180' as DomainStyleType, warnings: rollWarnings.value }
    ]
})

const isDeviated = computed(() => {
  if (p.pidmode!='IDLE') return false
  if (isEq.value === 2) return false
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
  const shouldFetch =  dev.restAPIConnected && dev.restAPIConnectedAt &&cfg.fetchedAt < dev.restAPIConnectedAt
  if (shouldFetch) await cfg.configFetch()

  const apiParam = Array.isArray(route.query.api)
    ? route.query.api[0]
    : route.query.api

  if (apiParam) {
    dev.restAPIPort = parseInt(apiParam)
  }

  if (!dev.alpacaHost && window.location.hostname) {
    dev.alpacaHost = window.location.hostname
  }

  if (!dev.restAPIPort && window.location.port) {
    dev.restAPIPort = parseInt(window.location.port)
  }

  if (dev.alpacaHost && dev.restAPIPort) {
    await dev.connectRestAPI()
  }
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


async function onClickFabAngle(e: { az?: number, alt?: number, roll?: number}) {
  if (cannotPerformCommand('slew')) return

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
  await dev.alpacaPanoGrid(`{"anchor":0, "ref":3, "panel": ${centerPanel.value}}`)
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
  if (axis>=0 && axis<=5) {
    await dev.apiAction('Polaris:MoveAxis', `{"axis":${axis},"rate":${rate}}`)
  }
  //   // const result = await dev.alpacaMoveAxis(axis, rate)
}

</script>
