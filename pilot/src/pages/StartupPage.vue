<template>
  <q-page class="q-pa-lg">
    <div class="row">
      <q-space />
      <q-toggle v-model="isEquatorial" label="Equatorial"/>
    </div>
    <div v-if="isEquatorial" class="row">
        <div>
          <ScaleDisplay label="Right Ascension" :pv="p.azimuth" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div>
          <ScaleDisplay label="Declination" :pv="p.altitude" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div>
          <ScaleDisplay label="Position Angle" :pv="p.roll" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
    </div>
    <div v-else class="row">
        <div>
          <ScaleDisplay label="Azimuth" :pv="p.azimuth" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div>
          <ScaleDisplay label="Altitude" :pv="p.altitude" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
        <div>
          <ScaleDisplay label="Roll" :pv="p.roll" :sp="90.0023" :scaleRange="10"  domain="semihi_360" />
        </div>
    </div>


    <div class="row items-center">
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


</script>
