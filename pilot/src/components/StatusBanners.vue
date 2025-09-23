<template>
    <div v-if="!dev.restAPIConnected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="!p.connected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Driver has lost connection to the Benro Polaris.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-if="p.atpark" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: The Alpaca Driver is parking/parked. Most functions are disabled.
        <template v-slot:action><q-btn flat label="UnPark" @click="onPark" /></template>
      </q-banner>
    </div>
</template>

<script setup lang="ts">
import { useDeviceStore } from 'src/stores/device';
import { useStatusStore } from 'src/stores/status';

const dev = useDeviceStore()
const p = useStatusStore()



async function onPark() {
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}


</script>

