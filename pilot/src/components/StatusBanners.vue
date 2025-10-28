<template>
    <div v-if="!dev.restAPIConnected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn v-if="isShowReconnect" flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="!p.connected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Driver has lost connection to the Benro Polaris.
        <template v-slot:action><q-btn v-if="isShowReconnect" flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="p.pidmode=='PRESETUP'" >
      <q-banner inline-actions rounded class="bg-warning">
        PRESETUP: Please set your Observing Site Lattitude and Longitude before proceeding.
        <template v-slot:action><q-btn flat label="Setup" to="/config" /></template>
      </q-banner>
    </div>
    <div v-else-if="p.pidmode=='LIMIT'" >
      <q-banner inline-actions rounded class="bg-warning">
        LIMIT: The Polaris has reached an anti-windup Motor Angle Limit. Please Review and Reset.
        <template v-slot:action>
          <q-btn flat label="Review" to="/config" />
          <q-btn flat label="Reset" @click="dev.ackLimitAlarm()" />
        </template>
      </q-banner>
    </div>
    <div v-else-if="p.atpark" >
      <q-banner inline-actions rounded class="bg-warning">
        PARK: The Alpaca Driver is parked. Most functions are disabled.
        <template v-slot:action><q-btn flat label="UnPark" @click="onPark" /></template>
      </q-banner>
    </div>
</template>

<script setup lang="ts">
import { useDeviceStore } from 'src/stores/device';
import { useStatusStore } from 'src/stores/status';
import { useRoute } from 'vue-router'
import { computed  } from 'vue'

const dev = useDeviceStore()
const p = useStatusStore()
const route = useRoute()

const isShowReconnect = computed(() => route.path != '/connect')

async function onPark() {
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}


</script>

