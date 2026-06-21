<template>
  <q-card style="width: 400px; height:500px" class="q-px-md q-pb-md">
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
    <div v-if="isResultRun">
        <div class="text-h6 q-mb-xs q-mt-md">
        Autotune Results
        </div>
        <div class="col text-grey text-caption">
            Parameters based on {{n_points}} Sync Points and {{n_iter}} iterations. 
        </div>
        <div class="row q-col-gutter-lg  items-center">
            <q-input class="col-4" label="Param A (arcmin)" readonly :model-value="param_A" input-class="text-right"/>
            <q-input class="col-4" label="Param B (deg)"    readonly :model-value="param_B" input-class="text-right"/>
            <q-input class="col-4" label="Param C (arcmin)" readonly :model-value="param_C" input-class="text-right"/>
        </div>
        <div class="col text-grey text-caption q-mt-md">
            <q-list dense>
                <q-item>
                    <q-item-section thumbnail>
                        <q-icon :name="isR2Ok ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isR2Ok ? 'green' : 'red'" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>R2 fit quality {{r2str}} (need > {{MIN_R2}})</q-item-label>
                    </q-item-section>
                </q-item>
                <q-item>
                    <q-item-section thumbnail>
                        <q-icon :name="isRmsOk ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isRmsOk ? 'green' : 'red'" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>RMS {{rmsstr}} (need > {{MIN_RMS}}%)</q-item-label>
                    </q-item-section>
                </q-item>    

            </q-list>
        </div>
        <div class="col text-grey text-caption q-mt-sm">
            {{resultSummaryMsg}} 
        </div>

    </div>
    <q-space />
    <div class="row q-gutter-sm  q-mt-md justify-center">
      <q-btn class="col-3" label="Cancel"  outline color="grey-7" v-close-popup />
      <q-btn class="col-3" label="Run"  outline color="grey-7"  @click="onRunAutotune"/>
      <q-btn class="col-3" label="Apply" outline color="primary" @click="onApply" :disable="!isRestultOk" v-close-popup/>
    </div>

  </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { useQuasar } from 'quasar'
import { onMounted, computed, ref } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useStreamStore } from 'src/stores/stream'
import type { SyncMessage }from 'src/stores/stream'

// import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()
const socket = useStreamStore()
const $q = useQuasar()

const MIN_SYNCS = 5
const MIN_ALTSPAN = 30
const MIN_ROLLSPAN = 100
const MIN_RMS = 10
const MIN_R2 = 0.4

type AutotuneResult = {
  success: boolean,
  m2_tilt_dm2_amp: number,
  m2_tilt_dm2_zero: number,
  m3_tilt_dm1: number,
  rms_before: number,
  rms_after: number,
  rms_improv: number,
  r2: number,
  n_points: number,
  nit: number,
  message: string,
}

const autotuneResult = ref<null | AutotuneResult>(null)

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

// ---------------- Sync Statistics Computed functions
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

// ---------------- Autotune Result Statistics Computed functions
const isResultRun = computed(() => autotuneResult.value)
const isRestultOk  = computed(() => (isR2Ok.value && isRmsOk.value))

const isR2Ok  = computed(() => (autotuneResult.value?.r2 ?? 0) > MIN_R2)
const r2str = computed(() => autotuneResult.value ? formatAutotuneR2(autotuneResult.value.r2) : 'unknown' )
function formatAutotuneR2(r2: number) {
    const quality = (r2>0.9) ? 'Excellent' : (r2>0.7) ? 'Good' : (r2>0.4) ? 'Satisfactory' : (r2>0.1) ? 'Weak' : 'Poor'
    return `${r2.toFixed(3)} ${quality}`
}

const isRmsOk = computed(() => (autotuneResult.value?.rms_improv ?? 0) > MIN_RMS)
const rmsstr = computed(() => autotuneResult.value ? formatRms(autotuneResult.value.rms_improv) : 'unknown' )
function formatRms(rms: number) {
    const quality = (rms>0) ? 'improved' : 'worsened'
    return `${quality} by ${rms.toFixed(1)}%`
}
const n_points = computed(() => autotuneResult.value ? autotuneResult.value.n_points : 'N/A' )
const n_iter = computed(() => autotuneResult.value ? autotuneResult.value.nit : 'N/A' )
const param_A = computed(() => autotuneResult.value ? autotuneResult.value.m2_tilt_dm2_amp.toFixed(1) : 'N/A' )
const param_B = computed(() => autotuneResult.value ? autotuneResult.value.m2_tilt_dm2_zero.toFixed(1) : 'N/A' )
const param_C = computed(() => autotuneResult.value ? autotuneResult.value.m3_tilt_dm1.toFixed(1) : 'N/A' )
const resultSummaryMsg = computed(() => {
    return (isR2Ok.value && isRmsOk.value) ? "All result checks met. Click apply to accept results." :
           (!isRmsOk.value) ? `MAC has not improved RMS Residulas enough. Do not Apply.` :
           (!isR2Ok.value) ? `MAC does not explain RMS Residuals. Do not Apply.` : `Autotune Results Unavailable.`
})
// ---------------- Telescope Sync Computed functions
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

async function onRunAutotune() {
  const result = await dev.alpacaAutotuneMAC()
  autotuneResult.value = result as unknown as AutotuneResult
  console.log(result)
}
async function onApply() {
  if (isRestultOk.value && autotuneResult.value) {
    const payload = { 
        m2_tilt_dm2_amp: autotuneResult.value.m2_tilt_dm2_amp, 
        m2_tilt_dm2_zero: autotuneResult.value.m2_tilt_dm2_zero,
        m3_tilt_dm1: autotuneResult.value.m3_tilt_dm1,
    }
    await cfg.configUpdate(payload)
    const ok = await cfg.configSave()
    $q.notify({ message:`Autotune Parameters save ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
                position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  }
}

</script>


