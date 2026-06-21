<template>
  <q-card style="width: 400px" class="q-px-md q-pb-md">
    <div class="text-h6 q-mb-xs q-mt-md">
      MAC Autotune 
    </div>
    <div class="col text-grey text-caption">
        This form helps you tune the Mechanical Alignment Correction Model parameters to your specific mount. 
    </div>
    {{ sync_summary }}
    <q-space />

    <div class="row q-gutter-sm  q-mt-md justify-center">
      <q-btn class="col-5" label="Cancel"  outline color="grey-7" v-close-popup />
      <q-btn class="col-5" label="Apply" outline color="primary" @click="onApply" v-close-popup/>
    </div>

  </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, ref, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useStreamStore } from 'src/stores/stream'
import type { TelemetryRecord, SyncMessage }from 'src/stores/stream'

// import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()
const socket = useStreamStore()

// ---------------- Helper functions
type TableRow = {
  deleted:boolean, timestamp:string, p_alt:number, p_roll:number 
}

function formatSyncData(d: TelemetryRecord):TableRow {
  const data = d.data as SyncMessage
  const deleted = data.deleted ?? false
  const timestamp = data.timestamp ?? ''
  const p_alt = data.p_alt ?? 0
  const p_roll = data.p_roll ?? 0
  return { deleted, timestamp, p_alt, p_roll }
}

// ---------------- Computed functions
const telescope_syncs = computed(() => {
  const sm = socket.topics?.sm ?? [] as TelemetryRecord[];
  const syncdata = sm.map(formatSyncData).filter(d=>((d.p_roll != 0) && (d.p_alt != 0)))
  const consolidated = new Map<string, TableRow>()
  for (const data of syncdata) {
    if (data.timestamp == 'reset') {
      consolidated.clear()
    } else {
      consolidated.set(data.timestamp, data)
    }
  }
  return Array.from(consolidated.values()).filter(d=>(!d.deleted))
})

const sync_summary = computed(() => {
  const ts = telescope_syncs.value
  if (!ts.length) return null

  const alts  = ts.map(d => d.p_alt)
  const rolls = ts.map(d => d.p_roll)

  const alt_min  = Math.min(...alts)
  const alt_max  = Math.max(...alts)
  const roll_min = Math.min(...rolls)
  const roll_max = Math.max(...rolls)

  return {
    n_syncs:   ts.length,
    alt_min,  alt_max,  alt_span:  alt_max  - alt_min,
    roll_min, roll_max, roll_span: roll_max - roll_min,
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


