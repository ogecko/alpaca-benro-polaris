<template>
  <q-page  class="row items-center ">
    <div class="col-6" style="display: flex; justify-content: flex-end; align-items: center;">
      <q-img src="../assets/abp-logo.png" fit="scale-down" position="100% 50%" style="height:200px"></q-img>
    </div>
    <div  class="col-6">
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
  </q-page>
</template>

<script setup lang="ts" >

import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'stores/device'

const route = useRoute()
const dev = useDeviceStore()
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
