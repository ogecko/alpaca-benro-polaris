<template>
  <q-page class="q-pa-sm">

    <StatusBanners />

    <!----- Page header ----->
    <div class="row q-pa-md justify-center items-center q-col-gutter-sm">

      <!----- LHS Action Buttons ----->
      <div class="row col-12 col-sm-4 justify-center ">
        <div class="q-gutter-sm ">
          <q-btn label="Az/Alt"  glossy  size="md" color="secondary" :outline="isEquatorial" @click="isEquatorial=!isEquatorial"  />
          <q-btn label="Park"    glossy  size="md" color="secondary" :outline="!p.atpark"  @click="onPark"/>
          <q-btn icon="mdi-stop" glossy  size="md" color="secondary" @click="onAbort"/>
          <q-btn-dropdown label="Track" glossy size="md" color="secondary" split :outline="!p.tracking" @click="onTrack">
            <q-list dense >
              <q-item clickable v-close-popup :active="p.trackingrate==0" active-class="bg-secondary text-white" @click="onTrackRate(0)">
                <q-item-section><q-item-label>Sidereal</q-item-label></q-item-section>
              </q-item>
              <q-item clickable v-close-popup :active="p.trackingrate==1" active-class="bg-secondary text-white" @click="onTrackRate(1)">
                <q-item-section><q-item-label>Lunar</q-item-label></q-item-section>
              </q-item>
              <q-item clickable v-close-popup :active="p.trackingrate==2" active-class="bg-secondary text-white" @click="onTrackRate(2)">
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
      <div class="row col-6 col-sm-4 text-positive text-h5 q-gutter-sm justify-center ">
        <div v-if="p.tracking">
          <span>{{p.trackingratestr}}</span> 
          <q-chip color="positive">Tracking</q-chip>
        </div>
      </div>

      <!----- RHS Chip Status Info ----->
      <div class="row col-6 col-sm-4 wrap justify-end ">
        <q-chip color="positive" :outline="p.polarismode!=8">
          {{polarismodestr}}
        </q-chip>
        <q-chip color="positive" :outline="!p.slewing">
          Slewing
        </q-chip>
        <q-chip color="positive" :outline="!p.gotoing">
          Gotoing
        </q-chip>
        <q-chip color="positive" :outline="['IDLE','PARK'].includes(p.pidmode)">
          PID: {{p.pidmode}}
        </q-chip> 
      </div>
    </div>

    <!----- Dynamic Set of 3 Radial Scales ----->
    <div class="row">
       <div v-for="(cfg, i) in displayConfig" :key="i" class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay
            :label="cfg.label"
            :pv="cfg.pv"
            :sp="cfg.sp"
            :lst="p.siderealtime"
            :domain="cfg.domain"
            @clickScale="onClickScale"
            @clickFabAngle="onClickFabAngle"
            @clickMove="onClickMove"
          />
        </div>
        <div v-if="!(p.pidmode=='PARK')" class="col-12 col-md-6 col-lg-4 row justify-center ">
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[0]" label="M1" />
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[1]" label="M2" />
          <SpinnerSpeed class="q-pa-sm" :speed="p.motorref[2]" label="M3" />
        </div>
    </div>

    <!----- Logo Startup Image ----->
    <div class="row items-center q-pt-xl">
        <q-space/>
        <div class="col">
          <q-img src="../assets/abp-logo.png" fit="scale-down" position="100% 50%" style="height:200px"></q-img>
        </div>
        <div class="col">
          <div class="text-bold text-h4">
            <div>POSITION</div>
            <div>CONTROL</div>
            <div>REIMAGINED</div>
          </div>
          <div class="q-pt-lg text-primary text-subtitle1">
            <div>Slewing, Rotating, Targeting,</div>
            <div>Tracking, and Guiding.</div>
          </div>
        </div>
        <q-space/>
    </div>
  </q-page>
</template>

<script setup lang="ts" >

import { useQuasar } from 'quasar'
import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import ScaleDisplay  from 'src/components/ScaleDisplay.vue'
import StatusBanners from 'src/components/StatusBanners.vue'
import SpinnerSpeed from 'src/components/SpinnerSpeed.vue'
import type { DomainStyleType } from 'src/components/ScaleDisplay.vue'


const $q = useQuasar()
const route = useRoute()
const dev = useDeviceStore()
const p = useStatusStore()
const isEquatorial = ref<boolean>(false)

// ------------------- Layout Configuration Data ---------------------

const displayConfig = computed(() => isEquatorial.value ? [
  { label: 'Right Ascension', pv: p.rightascension, sp: p.deltarefRAhrs, domain: 'ra_24' as DomainStyleType },
  { label: 'Declination', pv: p.declination, sp: p.deltaref[1], domain: 'dec_180' as DomainStyleType },
  { label: 'Position Angle', pv: p.rotation, sp: p.deltaref[2], domain: 'pa_180' as DomainStyleType }
] : [
  { label: 'Azimuth', pv: p.azimuth, sp: p.alpharef[0], domain: 'az_360' as DomainStyleType },
  { label: 'Altitude', pv: p.altitude, sp: p.alpharef[1], domain: 'alt_90' as DomainStyleType },
  { label: 'Roll', pv: p.roll, sp: p.alpharef[2], domain: 'roll_180' as DomainStyleType }
]);
const polarisModeConfig = ['Unknown', 'Photo', 'Pano', 'Focus', 'Timelapse', 'Pathlapse', 'HDR', 'Sun', 'Astro', 'Program', 'Video']

const polarismodestr = computed(() => polarisModeConfig[p.polarismode])

// ------------------- Lifecycle Events ---------------------

onMounted(async () => {
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
  if (p.atpark) {
      $q.notify({ message: `Cannot ${cmd} while mount is parked.`, type: 'negative', position: 'top', 
                           timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }]})
      return true
  }
  return false
}

// ------------------- Event Handlers ---------------------

async function onTrack() {
  if (cannotPerformCommand('toggle tracking')) return
  const result = (p.tracking) ? await dev.alpacaTracking(false) : await dev.alpacaTracking(true);  
  console.log(result)
}

async function onTrackRate(n: number) {
  const result = await dev.alpacaTrackingRate(n);  
  console.log(result)
}

async function onPark() {
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}

async function onAbort() {
  if (cannotPerformCommand('abort')) return
  const result = await dev.alpacaAbortSlew()
  console.log(result)
}


async function onClickScale(e: { label:string, angle: number, radialOffset: number }) {
  if (cannotPerformCommand('slew')) return

  if (e.label=="Azimuth") {
    const az = e.angle
    const alt = p.alpharef[1] ?? 0
    const result = await dev.alpacaSlewToAltAz(alt, az)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
  } else if (e.label=="Altitude") {
    const az = p.alpharef[0] ?? 0
    const alt = e.angle
    const result = await dev.alpacaSlewToAltAz(alt, az)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
  } else if (e.label=="Roll") {
    const result = await dev.alpacaMoveMechanical(e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
  } else if (e.label=="Right Ascension") {
    const ra = e.angle
    const dec = p.deltaref[1] ?? 0
    const result = await dev.alpacaSlewToCoord(ra, dec)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
  } else if (e.label=="Declination") {
    const ra = p.deltarefRAhrs ?? 0
    const dec = e.angle
    const result = await dev.alpacaSlewToCoord(ra, dec)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
  } else if (e.label=="Position Angle") {
    const result = await dev.alpacaMoveAbsolute(e.angle)
    console.log(`Change ${e.label} angle to ${e.angle}`,  result);
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

type AxisLabel =
  | "Azimuth"
  | "Altitude"
  | "Roll"
  | "Right Ascension"
  | "Declination"
  | "Position Angle"

const axisMap:Record<AxisLabel, number> = {
  "Azimuth": 0,
  "Altitude": 1,
  "Roll": 2,
  "Right Ascension": 3,
  "Declination": 4,
  "Position Angle": 5  
}

async function onClickMove(e: { label: string, rateScale: number}) {
  console.log('ClickMove ', e.label, e.rateScale)
  if (!Object.keys(axisMap).includes(e.label)) return
  const axis = axisMap[e.label as AxisLabel] ?? -1
  const rate = (axis!=3) ? e.rateScale / 200*9 : e.rateScale / 12*9
  if (axis>=0 && axis<=5) {
    await dev.apiAction('Polaris:MoveAxis', `{"axis":${axis},"rate":${rate}}`)
  }
  //   // const result = await dev.alpacaMoveAxis(axis, rate)
}

</script>
