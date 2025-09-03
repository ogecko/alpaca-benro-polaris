<template>
  <q-page class="q-pa-sm">
    <div v-if="!dev.restAPIConnected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-if="p.atpark" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: The Alpaca Driver is Parked. Most functions are disabled.
        <template v-slot:action><q-btn flat label="UnPark" @click="onPark" /></template>
      </q-banner>
    </div>
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
        <q-chip color="positive" :outline="!p.slewing">
          Slewing
        </q-chip>
        <q-chip color="positive" :outline="!p.gotoing">
          Gotoing
        </q-chip>
        <q-chip color="positive" :outline="!p.gotoing">
          PID
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
            :scaleRange="cfg.scaleRange"
            :domain="cfg.domain"
            @clickScale="cfg.onClick"
          />
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

import { onMounted, computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'stores/device'
import { useStatusStore } from 'src/stores/status'
import ScaleDisplay  from 'components/ScaleDisplay.vue'
import type { DomainStyleType } from 'components/ScaleDisplay.vue'

const route = useRoute()
const dev = useDeviceStore()
const p = useStatusStore()
const isEquatorial = ref<boolean>(false)

// ------------------- Layout Configuration Data ---------------------

const displayConfig = computed(() => isEquatorial.value ? [
  { label: 'Right Ascension', pv: p.rightascension, sp: 90.0023, scaleRange: 10, domain: 'semihi_360' as DomainStyleType, onClick: onClickRA },
  { label: 'Declination', pv: p.declination, sp: 90.0023, scaleRange: 10, domain: 'semihi_180' as DomainStyleType, onClick: onClickDec },
  { label: 'Position Angle', pv: p.rotation, sp: 90.0023, scaleRange: 10, domain: 'semihi_180' as DomainStyleType, onClick: onClickPA }
] : [
  { label: 'Azimuth', pv: p.azimuth, sp: 90.0023, scaleRange: 10, domain: 'semihi_360' as DomainStyleType, onClick: onClickAz },
  { label: 'Altitude', pv: p.altitude, sp: 90.0023, scaleRange: 10, domain: 'semihi_180' as DomainStyleType, onClick: onClickAlt },
  { label: 'Roll', pv: p.roll, sp: 90.0023, scaleRange: 10, domain: 'semihi_180' as DomainStyleType, onClick: onClickRoll }
]);

// ------------------- Lifecycle and Event Handlers ---------------------

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

async function onTrack() {
  if (p.atpark) return
  const result = (p.tracking) ? await dev.alpacaTracking(false) : await dev.alpacaTracking(true);  
  console.log(result)
}

async function onTrackRate(n: number) {
  if (p.atpark) return
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaTrackingRate(n);  
  console.log(result)
}

async function onPark() {
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}

async function onAbort() {
  if (p.atpark) return
  const result = await dev.alpacaAbortSlew()
  console.log(result)
}

function onClickAz(e: { angle: number }) {
  console.log('Clicked Az angle:', e.angle);
}

function onClickAlt(e: { angle: number }) {
  console.log('Clicked Alt angle:', e.angle);
}

function onClickRoll(e: { angle: number }) {
  console.log('Clicked Roll angle:', e.angle);
}

function onClickRA(e: { angle: number }) {
  console.log('Clicked RA angle:', e.angle);
}

function onClickDec(e: { angle: number }) {
  console.log('Clicked Dec angle:', e.angle);
}

function onClickPA(e: { angle: number }) {
  console.log('Clicked PA angle:', e.angle);
}

</script>
