<template>
  <q-card style="width: 400px" class="q-px-md q-pb-md">
    <div class="text-h6 q-mb-xs q-mt-md">
      M2 Scale AutoTune Pre-requisites
    </div>
    <q-list dense>
        <q-item>
            <q-item-section thumbnail>
                <q-icon :name="isEnoughPoints ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isEnoughPoints ? 'green' : 'red'" />
            </q-item-section>
            <q-item-section>
                <q-item-label>{{MIN_SYNCS}} or more Sync Points (currently {{ stat?.n_syncs ?? 0 }})</q-item-label>
            </q-item-section>
        </q-item>
        <q-item>
            <q-item-section thumbnail>
                <q-icon :name="isAltSpanOk ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isAltSpanOk ? 'green' : 'red'" />
            </q-item-section>
            <q-item-section>
                <q-item-label>Altitude spread {{MIN_ALTSPAN}}° or more (currently {{ stat?.alt_span ?? 0 }}°)</q-item-label>
            </q-item-section>
        </q-item>
    </q-list>
    <div class="col text-grey text-caption q-pt-sm">
        {{morePointsMsg}}
    </div>
    <div v-if="!result">
        <div style="height: 180px" class="text-grey text-caption">{{ failMsg || 'No Results yet.' }}</div>
    </div>
    <div v-else>
        <div class="text-h6 q-mb-xs q-mt-md">
        AutoTune Results
        </div>
        <div class="col text-grey text-caption">
            {{ result.message }}.
        </div>
        <div class="row q-col-gutter-lg items-center">
            <q-input class="col-4" label="M2 scale (%)"   readonly :model-value="result.m2_scale.toFixed(2)" input-class="text-right"/>
            <q-input class="col-4" label="Now (%)"         readonly :model-value="Number(cfg.align_m2_scale ?? 0).toFixed(2)" input-class="text-right"/>
            <q-input class="col-4" label="RMS (arcmin)"    readonly :model-value="`${result.rms_before.toFixed(1)} → ${result.rms_after.toFixed(1)}`" input-class="text-right"/>
        </div>
        <div class="col text-grey text-caption q-mt-sm">
            {{ resultMsg }}
        </div>
    </div>
    <q-space />
    <div class="row q-gutter-sm  q-mt-md justify-center">
      <q-btn class="col-3" label="Cancel"  outline color="grey-7" v-close-popup />
      <q-btn class="col-3" label="Run"  outline color="grey-7"  @click="onRunAutotune" :disable="!isReady"/>
      <q-btn class="col-3" label="Apply" outline color="primary" @click="onApply" :disable="!isResultOk" v-close-popup/>
    </div>

  </q-card>
</template>

<script setup lang="ts">
import { useQuasar } from 'quasar'
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useStreamStore } from 'src/stores/stream'
import type { SyncMessage }from 'src/stores/stream'

const dev = useDeviceStore()
const cfg = useConfigStore()
const socket = useStreamStore()
const $q = useQuasar()

const MIN_SYNCS = 6                 // the driver's calibrate_m2_scale: 6+ points, 20+ deg of M2
const MIN_ALTSPAN = 20
const NO_CHANGE = 0.1               // %: a result this close to the current scale has nothing to apply

type AutotuneResult = {
  success: boolean,
  m2_scale: number,                 // %
  d2: number,                       // deg
  d3: number,
  rms_before: number,               // arcmin, with the current scale
  rms_after: number,
  rms_improv: number,               // %
  n_points: number,
  message: string,
}
const result = ref<null | AutotuneResult>(null)
const failMsg = ref('')

const telescope_syncs = computed(() =>
  Array.from(socket.syncPoints.values())
    .filter((d: SyncMessage) => d.a_az != null && d.a_alt != null && !(d.deleted ?? false))
    .map((d: SyncMessage) => d.p_alt ?? 45)
)
const stat = computed(() => {
  const alts = telescope_syncs.value
  if (!alts.length) return null
  return { n_syncs: alts.length, alt_span: Math.floor(Math.max(...alts) - Math.min(...alts)) }
})
const isEnoughPoints = computed(() => (stat.value?.n_syncs ?? 0) >= MIN_SYNCS)
const isAltSpanOk = computed(() => (stat.value?.alt_span ?? 0) >= MIN_ALTSPAN)
const isReady = computed(() => isEnoughPoints.value && isAltSpanOk.value)
const morePointsMsg = computed(() =>
  isReady.value ? 'All pre-requisites met. Click Run to perform AutoTune.' :
  !isEnoughPoints.value ? 'Collect more Sync Points.' : 'Collect Sync Points at lower and higher altitudes.')

const isNoChange = computed(() => !!result.value && Math.abs(result.value.m2_scale - Number(cfg.align_m2_scale ?? 0)) < NO_CHANGE)
const isResultOk = computed(() => !!result.value && result.value.success && !isNoChange.value)
const resultMsg = computed(() => {
  if (!result.value) return ''
  if (isNoChange.value) return 'Similar to the current M2 scale. Nothing to Apply.'
  return `RMS residual ${result.value.rms_improv >= 0 ? 'improved' : 'worsened'} by ${Math.abs(result.value.rms_improv).toFixed(1)}%. ` +
         'Click Apply to save the M2 scale.'
})

onMounted(() => {
  socket.subscribe('sm')
})
onUnmounted(() => {
  socket.unsubscribe('sm')
})

async function onRunAutotune() {
  const r = await dev.alpacaAutotuneMAC() as unknown as AutotuneResult
  result.value = r.success ? r : null
  failMsg.value = r.success ? '' : r.message
}

async function onApply() {
  if (isResultOk.value && result.value) {
    await cfg.configUpdate({ align_m2_scale: result.value.m2_scale })
    const ok = await cfg.configSave()
    $q.notify({ message:`M2 scale save ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative',
                position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  }
}
</script>
