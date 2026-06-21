<template>
  <q-card style="width: 400px" class="q-px-md q-pb-md">
    <div class="text-h6 q-mb-xs q-mt-md">
      Autotune Pre-requisites
    </div>
    <q-list dense>
        <q-item>
            <q-item-section thumbnail>
                <q-icon :name="isEnoughPoints ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isEnoughPoints ? 'green' : 'red'" />
            </q-item-section>
            <q-item-section>
                <q-item-label>More than {{MIN_SYNCS}} Sync Points (currently {{ stat?.n_syncs }})</q-item-label>
            </q-item-section>
        </q-item>
        <q-item>
            <q-item-section thumbnail>
                <q-icon :name="isAltSpanOk ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isAltSpanOk ? 'green' : 'red'" />
            </q-item-section>
            <q-item-section>
                <q-item-label>Altitude spread > {{MIN_ALTSPAN}}°  (currently {{ stat?.alt_span }}° )</q-item-label>
            </q-item-section>
        </q-item>
        <q-item>
            <q-item-section thumbnail>
                <q-icon :name="isRollSpanOk ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isRollSpanOk ? 'green' : 'red'" />
            </q-item-section>
            <q-item-section>
                <q-item-label>Roll Angle spread > {{MIN_ROLLSPAN}}°  (currently {{ stat?.roll_span }}° )</q-item-label>
            </q-item-section>
        </q-item>    </q-list>
    <div class="col text-grey text-caption q-pt-sm">
        {{morePointsMsg}}
    </div>
    <div class="text-h6 q-mb-xs q-mt-md">
      Autotune Results
    </div>
    <div class="col text-grey text-caption">
        {{ stat }}
    </div>
    <q-space />

    <div class="row q-gutter-sm  q-mt-md justify-center">
      <q-btn class="col-3" label="Cancel"  outline color="grey-7" v-close-popup />
      <q-btn class="col-3" label="Run"  outline color="grey-7"  />
      <q-btn class="col-3" label="Apply" outline color="primary" @click="onApply" v-close-popup/>
    </div>

  </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useStreamStore } from 'src/stores/stream'
import type { SyncMessage }from 'src/stores/stream'

// import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()
const socket = useStreamStore()
const MIN_SYNCS = 5
const MIN_ALTSPAN = 30
const MIN_ROLLSPAN = 100

// ---------------- Helper functions
type TableRow = {
  deleted:boolean, timestamp:string, p_alt:number, p_roll:number 
}

function formatSyncData(data: SyncMessage):TableRow {
  const deleted = data.deleted ?? false
  const timestamp = data.timestamp ?? ''
  const p_alt = data.p_alt ?? 45
  const p_roll = data.p_roll ?? 0
  return { deleted, timestamp, p_alt, p_roll }
}

// ---------------- Computed functions
const isEnoughPoints = computed(() => (stat.value?.n_syncs??0)>MIN_SYNCS);
const isAltSpanOk = computed(() => (stat.value?.alt_span??0)>MIN_ALTSPAN);
const isRollSpanOk = computed(() => (stat.value?.roll_span??0)>MIN_ROLLSPAN);

const morePointsMsg = computed(() => {
    return (isEnoughPoints.value && isAltSpanOk.value && isRollSpanOk.value) ? "All pre-requisites met. Click Run to perform Autotune." :
           (!isRollSpanOk.value && !isAltSpanOk.value) ? `Collect more Sync Points with ${rollMsg.value}, and also more with ${altMsg.value}.` :
           (!isRollSpanOk.value) ? `Collect more Sync Points with ${rollMsg.value}.` :
           (!isAltSpanOk.value) ? `Collect more Sync Points with ${altMsg.value}.` : `Autotune Unavailable.`
})

const rollMsg = computed(() => `Roll < ${stat.value?.roll_min}°, or Roll > ${stat.value?.roll_max}°`)
const altMsg = computed(() => `Alt < ${stat.value?.alt_min}°, or Alt > ${stat.value?.alt_max}°`)


const telescope_syncs = computed(() =>
  Array.from(socket.syncPoints.values())
    .filter(d => d.a_az != null && d.a_alt != null)
    .map(formatSyncData)
)

const stat = computed(() => {
  const ts = telescope_syncs.value
  if (!ts.length) return null

  const alts  = ts.map(d => d.p_alt)
  const rolls = ts.map(d => d.p_roll)

  const alt_min  = Math.floor(Math.min(...alts))
  const alt_max  = Math.floor(Math.max(...alts))
  const roll_min = Math.floor(Math.min(...rolls))
  const roll_max = Math.floor(Math.max(...rolls))

  return {
    n_syncs:   ts.length,
    alt_min,  alt_max,  alt_span:  Math.floor(alt_max  - alt_min),
    roll_min, roll_max, roll_span: Math.floor(roll_max - roll_min),
  }
})


// ----------------- Lifecycle Functions

onMounted(async () => {
  const shouldFetch =  dev.restAPIConnected && dev.restAPIConnectedAt &&cfg.fetchedAt < dev.restAPIConnectedAt
  if (shouldFetch) await cfg.configFetch()
  socket.subscribe('sm')
})


async function onApply() {
  // simplest: reset inputs to defaults or close dialog
  // example reset:
//   const payload = { 
//     hstep: calc_hstep.value, 
//     vstep: calc_vstep.value,
//     sensor_size: sensor_size.value,
//     panel_overlap: panel_overlap.value,
//     focal_length: parseFirstNumber(focal_length.value) || 35
//   }
//   await cfg.configUpdate(payload)
}

</script>


