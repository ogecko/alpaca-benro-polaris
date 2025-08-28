<template>
  <q-page>
    <div class="row">
      {{az.sign}}{{az.degrees}} | {{az.minutes}} | {{az.seconds}}
    </div>
    <div class="row">
      {{az.sign}}{{alt.degrees}} | {{alt.minutes}} | {{alt.seconds}}
    </div>
    <div class="row">
      {{az.sign}}{{roll.degrees}} | {{roll.minutes}} | {{roll.seconds}}
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
const az = computed(() => deg2dms(p.azimuth))
const alt = computed(() => deg2dms(p.altitude))
const roll = computed(() => deg2dms(p.roll))

onMounted(async () => {

  const apiParam = Array.isArray(route.query.api)
    ? route.query.api[0]
    : route.query.api

  if (apiParam) {
    dev.alpacaPort = parseInt(apiParam)
  }

  if (!dev.alpacaHost && window.location.hostname) {
    dev.alpacaHost = window.location.hostname
  }

  if (!dev.alpacaPort && window.location.port) {
    dev.alpacaPort = parseInt(window.location.port)
  }

  if (dev.alpacaHost && dev.alpacaPort) {
    await dev.connectAlpaca()
  }
})


</script>
