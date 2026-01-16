

<template>
  <q-card style="width: 350px" class="q-px-md q-pb-md">
    <div class="text-h6 q-mb-xs q-mt-md">
      Panel Spacing Calculator 
    </div>

    <q-select
      v-model="sensor_size" label="Sensor Size" new-value-mode="add-unique" use-input use-chips dense emit-value map-options
      :options="['Full Frame (36 × 24 mm)', 'APS-C / IMX571 (23.5 × 15.7 mm)', 'Micro Four Thirds (17.3 × 13.0 mm)', 'IMX585 (11.2 × 6.3 mm)', 'IMX533 (11.3 × 11.3 mm)']"
    />

    <q-select
      v-model="focal_length" class="q-mt-sm" label="Focal Length" new-value-mode="add-unique" use-input use-chips dense emit-value map-options
      :options="['14 mm', '24 mm', '35 mm', '50 mm', '85 mm', '100 mm', '135 mm', '200 mm', '300 mm', '400 mm', '500 mm', '600 mm', '800 mm']"
    />

    <q-select
      v-model="panel_overlap"  class="q-mt-sm" label="Overlap" new-value-mode="add-unique" use-input use-chips dense emit-value map-options
      :options="['10%', '20%', '30%', '40%', '50%', '60%', '70%', '80%']"
    />

    <div v-if="show_result">
        <div class="text-subtitle2 text-grey-6 q-mt-md q-pt-lg">
          Calculated Sensor Field of View:
        </div>    
        <div class="row q-col-gutter-lg  items-center  ">
          <q-input class="col-6" label="Horizontal FOV" suffix="°" readonly v-model="calc_hFOV_display" input-class="text-right" dense/>
          <q-input class="col-6" label="Vertical FOV" suffix="°" readonly v-model="calc_vFOV_display" input-class="text-right" dense/>
        </div>
        <div class="text-subtitle2 text-grey-6 q-mt-md">
          Recommended Panel Step ({{panel_overlap}} overlap):
        </div>    
        <div class="row q-col-gutter-lg  items-center  ">
          <q-input class="col-6" label="Horizontal Step" suffix="°" readonly v-model="calc_hstep_display" input-class="text-right" dense/>
          <q-input class="col-6" label="Vertical Step" suffix="°" readonly v-model="calc_vstep_display" input-class="text-right" dense/>
        </div>

    </div>    
    <div class="row q-gutter-sm  q-mt-md justify-center">
      <q-btn class="col-5" label="Cancel"  outline color="grey-7" v-close-popup />
      <q-btn v-if="show_result" class="col-5" label="Apply" outline color="primary" @click="onApply" v-close-popup/>
    </div>

  </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, ref, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
// import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()

const sensor_size = ref<string>(cfg.sensor_size)
const focal_length = ref<string>(`${cfg.focal_length} mm`)
const panel_overlap = ref<string>(cfg.panel_overlap)

// ---------------- Helper functions
function parseFirstNumber(str?: string): number | null {
  if (!str) return null
  const m = str.match(/[\d.]+/)
  return m ? Number(m[0]) : null
}

function parseSensorXY(str?: string): { x: number | null; y: number | null } {
  if (!str) return { x: null, y: null }

  // supports: 36 × 24, 36x24, 36 X 24
  const m = str.match(/([\d.]+)\s*[×xX]\s*([\d.]+)/)
  if (!m) return { x: null, y: null }

  return {
    x: Number(m[1]),
    y: Number(m[2])
  }
}

// ---------------- Computed functions
const sensor_size_x = computed<number | null>(() => {
  return parseSensorXY(sensor_size.value).x
})

const sensor_size_y = computed<number | null>(() => {
  return parseSensorXY(sensor_size.value).y
})

const focal_mm = computed<number | null>(() => {
  return parseFirstNumber(focal_length.value)
})

const overlap_frac = computed<number | null>(() => {
  const v = parseFirstNumber(panel_overlap.value)
  return v !== null ? v / 100 : null
})

function calcFovDeg(sensor_mm: number, focal_mm: number): number {
  return 2 * (180 / Math.PI) * Math.atan(sensor_mm / (2 * focal_mm))
}

const calc_hFOV = computed<number>(() => {
  if (!sensor_size_x.value || !focal_mm.value) return NaN
  return calcFovDeg(sensor_size_x.value, focal_mm.value)
})

const calc_vFOV = computed<number>(() => {
  if (!sensor_size_y.value || !focal_mm.value) return NaN
  return calcFovDeg(sensor_size_y.value, focal_mm.value)
})

const calc_hstep = computed<number>(() => {
  if (!calc_hFOV.value || overlap_frac.value === null) return NaN
  return calc_hFOV.value * (1 - overlap_frac.value)
})

const calc_vstep = computed<number>(() => {
  if (!calc_vFOV.value || overlap_frac.value === null) return NaN
  return calc_vFOV.value * (1 - overlap_frac.value)
})

const calc_hFOV_display = computed(() =>
  isFinite(calc_hFOV.value) ? calc_hFOV.value.toFixed(2) : ''
)

const calc_vFOV_display = computed(() =>
  isFinite(calc_vFOV.value) ? calc_vFOV.value.toFixed(2) : ''
)

const calc_hstep_display = computed(() =>
  isFinite(calc_hstep.value) ? calc_hstep.value.toFixed(2) : ''
)

const calc_vstep_display = computed(() =>
  isFinite(calc_vstep.value) ? calc_vstep.value.toFixed(2) : ''
)

const show_result = computed<boolean>(() => {
  return [
    sensor_size_x.value,
    sensor_size_y.value,
    focal_mm.value,
    overlap_frac.value,
    calc_hFOV.value,
    calc_vFOV.value,
    calc_hstep.value,
    calc_vstep.value
  ].every(v => typeof v === 'number' && isFinite(v))
})


// ----------------- Lifecycle Functions

onMounted(async () => {
  const shouldFetch =  dev.restAPIConnected && dev.restAPIConnectedAt &&cfg.fetchedAt < dev.restAPIConnectedAt
  if (shouldFetch) await cfg.configFetch()
})


async function onApply() {
  // simplest: reset inputs to defaults or close dialog
  // example reset:
  const payload = { 
    hstep: calc_hstep.value, 
    vstep: calc_vstep.value,
    sensor_size: sensor_size.value,
    panel_overlap: panel_overlap.value,
    focal_length: parseFirstNumber(focal_length.value) || 35
  }
  await cfg.configUpdate(payload)
}

</script>


