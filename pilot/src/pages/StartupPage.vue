<template>
  <q-page class="q-pa-lg">
    <div class="row items-center">
      <q-space/>
      <div>
      <div class="col">
        <div class="row items-center ">
          <div class="col-auto text-h4">{{az.sign}}</div>
          <div class="col-auto text-h2 text-weight-bold">{{az.degrees}}°</div>
          <div class="col-auto columns q-pl-sm">
            <div class="col text-h5 text-grey-4">{{az.minutestr}}'</div>
            <div class="col text-caption text-grey-5">{{az.secondstr}}"</div>
          </div>
        </div>
        <div class="row items-center text-h4 text-grey-6 text-center">
          <div class="col-auto">
          Azimuth
          </div>
        </div>
      </div>
      <div class="col">
        <div class="row items-center ">
          <div class="col-auto text-h4">{{alt.sign}}</div>
          <div class="col-auto text-h2 text-weight-bold">{{alt.degrees}}°</div>
          <div class="col-auto columns q-pl-sm">
            <div class="col text-h5 text-grey-4">{{alt.minutestr}}'</div>
            <div class="col text-caption text-grey-5">{{alt.secondstr}}"</div>
          </div>
        </div>
        <div class="row items-center text-h4 text-grey-6 text-center">
          <div class="col-auto">
          Altitude
          </div>
        </div>
      </div>
      <div class="col">
        <div class="row items-center ">
          <div class="col-auto text-h4">{{roll.sign}}</div>
          <div class="col-auto text-h2 text-weight-bold">{{roll.degrees}}°</div>
          <div class="col-auto columns q-pl-sm">
            <div class="col text-h5 text-grey-4">{{roll.minutestr}}'</div>
            <div class="col text-caption text-grey-5">{{roll.secondstr}}"</div>
          </div>
        </div>
        <div class="row items-center text-h4 text-grey-6 text-center">
          <div class="col-auto">
          Roll
          </div>
        </div>
      </div>

      </div>
      <q-space/>
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

import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'stores/device'
import { useStatusStore } from 'src/stores/status'
import { deg2dms } from 'src/utils/angles'

const route = useRoute()
const dev = useDeviceStore()
const p = useStatusStore()
const az = computed(() => deg2dms(p.azimuth,1))
const alt = computed(() => deg2dms(p.altitude,1))
const roll = computed(() => deg2dms(p.roll,1))

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
