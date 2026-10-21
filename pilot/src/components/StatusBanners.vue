<template>
    <div v-if="!dev.restAPIConnected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect Driver" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="isStatusOld" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Pilot is not receiving updates from the Driver. Check Driver is running. 
        <template v-slot:action><q-btn flat label="Reconnect Driver" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="!p.connected" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Driver has lost connection to the Benro Polaris.
        <template v-slot:action><q-btn flat label="Reconnect Polaris" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="isNoAstroModule" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: No Astro version detected. Please attach Polaris Astro module, then disconnect and reconnect the Polaris.
        <template v-slot:action><q-btn flat label="Reconnect Astro" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="isNoAstroMode" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: Polaris not in the Astro imaging mode. Please select Polaris Astro mode.
        <template v-slot:action><q-btn flat label="Astro Mode" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="p.pidmode=='PRESETUP'" >
      <q-banner inline-actions rounded class="bg-warning">
        PRESETUP: Check your Observing Site Lattitude and Longitude, then proceed to connect to Benro Polaris.
        <template v-slot:action><q-btn flat label="PRESETUP" to="/config" /></template>
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
    <div v-else-if="isNoSingleStarAligned" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Polaris has not completed initial Single Star Alignment. Check Setup. 
        <template v-slot:action><q-btn flat label="Star Alignment" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="is518Old" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Driver is not receiving 200ms position updates from Polaris. Check Setup. 
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else-if="is517Old" >
      <q-banner inline-actions rounded class="bg-warning" >
        WARNING: The Alpaca Driver is not receiving 1s orientation updates from Polaris. Check Setup. 
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
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
import { useUIStore } from 'src/stores/ui'
import { computed, ref, watch } from 'vue'
import { useInterval } from 'quasar'

const dev = useDeviceStore()
const p = useStatusStore()
const ui = useUIStore()
const { registerInterval } = useInterval()

const now = ref(Date.now());
registerInterval( ()  => { now.value = Date.now() }, 1000 )

// Status arrives every 200ms, but a Wi-Fi client in power-save mode (phones, a laptop on battery -- worst on the Pi's
// alpaca-hotspot) gets it in bursts, with gaps over 1s. So allow 3s, as for the 517/518 updates below. A hidden tab
// unsubscribes from status (AltLayout.vue), so on its return the last status is old until the resubscribe delivers:
// count the 3s from when the tab became visible again too, not just from the last status.
const visibleSince = ref(Date.now())
watch(() => dev.isVisible, (visible) => { if (visible) { visibleSince.value = now.value = Date.now() } })

const isStatusOld = computed(() => { return now.value - Math.max(p.fetchedAt, visibleSince.value) > ui.driverTimeout;   });
const is517Old = computed(() => { return p.age517 > 3.0;   });
const is518Old = computed(() => { return p.age518 > 3.0;   });
const isNoAstroModule = computed(() => { return p.polarisastrover==''   });
const isNoAstroMode = computed(() => { return p.polarismode!=8   });
const isNoSingleStarAligned = computed(() => { return !p.aligned   });


async function onPark() {
  const result = (p.atpark) ? await dev.alpacaUnPark() : await dev.alpacaPark();  
  console.log(result)
}


</script>

