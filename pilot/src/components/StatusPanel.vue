<template>
  <div class="col-12 col-md-6 col-lg-4  col-xl-3">
    <q-list  >
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-engine" 
                   :color="isEnabled(p.pidmode!='IDLE')" @click="onAbort"/>
          </q-item-section>
          <q-item-section>Motor Speed & Position</q-item-section>
          <q-item-section side @click="router.push('/pidall')">
            <div class="row q-bt-none">
              <SpinnerSpeed class="q-pl-md" :speed="p.motorref[0]" :position="p.zetameas[0]" label="M1" />
              <SpinnerSpeed class="q-pl-md" :speed="p.motorref[1]" :position="p.zetameas[1]" label="M2" />
              <SpinnerSpeed class="q-pl-md" :speed="p.motorref[2]" :position="p.zetameas[2]" label="M3" />
            </div>
          </q-item-section>
      </q-item>
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-star-shooting-outline" 
                    :color="isEnabled(p.tracking)"  @click="onTrack"/>
          </q-item-section>
          <q-item-section>Tracking Performance</q-item-section>
          <q-item-section side @click="router.push('/pidall')"><StatusTracking /></q-item-section>
      </q-item>
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-pulse" 
                    :color="isEnabled(cfg.advanced_pulse_guiding)" @click="toggle('advanced_pulse_guiding')" />
          </q-item-section>
          <q-item-section>Pulse Guiding</q-item-section>
          <q-item-section side @click="router.push('/position')"><StatusPulseGuiding /></q-item-section>

      </q-item>
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-sine-wave" 
                    :color="isEnabled(cfg.advanced_pec)" @click="toggle('advanced_pec')" />
          </q-item-section>
          <q-item-section>Periodic Error Correction</q-item-section>
          <q-item-section side @click="router.push('/position')"><StatusPEC /></q-item-section>
      </q-item>
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-sync" 
                    :color="isEnabled(cfg.advanced_sync_guiding)" @click="toggle('advanced_sync_guiding')" />
          </q-item-section>
          <q-item-section>Sync Guiding</q-item-section>
          <q-item-section side @click="router.push('/position')"><StatusSyncGuiding /></q-item-section>
      </q-item>
      <q-item>
          <q-item-section avatar>
            <q-btn size="lg" dense round flat icon="mdi-globe-model" 
                    :color="isEnabled(cfg.advanced_alignment)" @click="toggle('advanced_alignment')" />
          </q-item-section>
          <q-item-section>Alignment Model</q-item-section>
          <q-item-section side @click="router.push('/sync')"><StatusAlignment /></q-item-section>
      </q-item>
    </q-list>
  </div>

</template>

<script setup lang="ts">
import { debounce } from 'quasar'
import { useRouter } from 'vue-router'
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'stores/config';
import { useUIStore } from 'src/stores/ui'
import SpinnerSpeed from 'src/components/SpinnerSpeed.vue'
import StatusAlignment from 'src/components/statusAlignment.vue'
import StatusPulseGuiding from 'src/components/statusPulseGuiding.vue'
import StatusSyncGuiding from 'src/components/statusSyncGuiding.vue'
import StatusTracking from 'src/components/statusTracking.vue'
import StatusPEC from 'src/components/statusPEC.vue'

const router = useRouter()
const p = useStatusStore()
const cfg = useConfigStore()
const ui = useUIStore()
const dev = useDeviceStore()

async function  onAbort() {
    const result = await dev.alpacaAbortSlew()
    console.log(result)
}

async function  onTrack() {
  const result = (p.tracking) ? await dev.alpacaTracking(false) : await dev.alpacaTracking(true);  
  console.log(result)
}



function isEnabled(status: boolean) {
  return (status == true) ? "primary" : 'grey-8'
}

function toggle(key:string) {
  // @ts-expect-error: dynamic key access on cfg
  const val = cfg[key];
  const payload = { [key]: !val }
  put(payload)
}

  const put = debounce((payload) => cfg.configUpdate(payload), 5)     // fast put for toggles


</script>

<style scoped>

</style>