<template>
  <q-page class="">
    <div class="row q-pa-md justify-center ">
      <div class="col-12 col-sm-6 q-gutter-sm q-mb-md justify-left">
        <q-btn-group class="q-gutter-sm ">
          <q-btn round color="secondary" dense  icon="mdi-parking" />
          <q-btn round color="secondary" dense  icon="mdi-stop" />
          <q-btn round color="secondary" dense  label="Tr" />
        </q-btn-group>
        <q-toggle v-model="isEquatorial" label="Equatorial"/>
      </div>
      <div class="row col-12 col-sm-6 q-gutter-sm  justify-end ">
        <q-chip color="positive" :outline="!p.slewing">
          Slewing
        </q-chip>
        <q-chip color="positive" :outline="!p.gotoing">
          Gotoing
        </q-chip>
        <q-chip color="positive" :outline="!p.atpark">
          Parked
        </q-chip> 
        <q-chip color="positive" :outline="!p.gotoing">
          PID
        </q-chip> 
        <q-chip color="positive" :outline="!p.tracking">
          Tracking
        </q-chip>
      </div>
    </div>
    <div v-if="isEquatorial" class="row">
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickRA" label="Right Ascension" :pv="p.rightascension" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickDec" label="Declination" :pv="p.declination" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickPA" label="Position Angle" :pv="p.rotation" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
    </div>
    <div v-else class="row">
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickAz" label="Azimuth" :pv="p.azimuth" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickAlt" label="Altitude" :pv="p.altitude" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div class="col-12 col-md-6 col-lg-4">
          <ScaleDisplay @clickScale="onClickRoll" label="Roll" :pv="p.roll" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
    </div>


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

import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'stores/device'
import { useStatusStore } from 'src/stores/status'
import ScaleDisplay from 'components/ScaleDisplay.vue'

const route = useRoute()
const dev = useDeviceStore()
const p = useStatusStore()
const isEquatorial = ref<boolean>(false)


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
