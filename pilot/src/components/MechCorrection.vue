

<template>
    <q-card flat bordered class="q-pa-md full-width">
      <div class="text-h6">Mechanical Alignment Correction Models</div>
      <div class="row">
      <div class="col text-grey text-caption">
        Reduce pointing residuals. Fine tune adjustments that correct for mechanical imperfections in the Benro Polaris and mount geometry. 
      </div>
        <q-space />
        <div class="q-gutter-md flex justify-end q-mr-md">
          <q-item-section>
            <div>
              <q-btn  v-if="is_dirty" rounded  color="grey-9"  label="Apply" @click="apply_params"/>
              <q-btn-toggle v-model="cfg.advanced_align_rbc" push rounded glossy toggle-color="primary"  
                @update:model-value="onModelUpdate"
                :options="[
                  {label: 'On', value: true},
                  {label: 'Off', value: false},
                ]"
              />
            </div>
          </q-item-section>

        </div>

      </div>

      <div class="col-12 text-h7 q-pt-md">M2 Axis Alignment Correction</div>
      <div class="row q-col-gutter-md">
        <div class="col-9 text-grey text-caption">
          <div>The Altitude Axis may not be perfectly perpenticular to the M1 axis. This may introduce a mechanical error, dependent on θ₂. </div>
          <div  class="q-pl-md q-pt-sm text-body1">Altitude Residual = A x sin( θ₂ - B )</div>
        </div>
        <div class="col-3">
          <q-input label="Parameter A (arcmin/M2°)" v-model="m2_tilt_dm2_amp_str" :disable="!cfg.advanced_align_rbc"/>
          <q-input label="Parameter B (degrees)" v-model="m2_tilt_dm2_zero_str" :disable="!cfg.advanced_align_rbc"/>
        </div>
      </div>
      <div class="col-12 text-h7 q-pt-sm">M3 Axis Alignment Correction</div>
      <div class="row q-col-gutter-md q-pb-lg">
        <div class="col-9 text-grey text-caption">
          <div>The Astro Axis may not be perfectly perpendicular to the M2 axis. This may introduce a mechanical error, depenent on θ₂ and θ₃. </div>
          <div class="q-pl-md q-pt-sm text-body1 ">Azimuth Residual = G x (1 - cos( θ₃ ))</div>
          <div  class="q-pl-md q-pt-sm text-body1">Roll Residual = -cos( θ₂ ) x Azimuth Residual</div>
        </div>
        <div class="col-3">
          <q-input label="Parameter G (arcmin/M3°)" v-model="m3_tilt_dm1_str" :disable="!cfg.advanced_align_rbc"/>
        </div>
      </div>

    </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, ref, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { deg2min, dms2deg } from 'src/utils/angles'

const dev = useDeviceStore()
const cfg = useConfigStore()

const m3_tilt_dm1_str       = ref('0.0')
const m3_tilt_dm2_str      = ref('0.0')
const m2_tilt_dm2_amp_str  = ref('0.0')
const m2_tilt_dm2_zero_str = ref('0.0')
const m2_roll_coupling_str = ref('0.0')
const m2_roll_zero_str     = ref('0.0')
const m1_offset_str        = ref('0.0')
const m2_offset_str        = ref('0.0')
const m3_offset_str        = ref('0.0')

function load_params() {
  m3_tilt_dm1_str.value = deg2min(cfg.m3_tilt_dm1/60, 1)
  m3_tilt_dm2_str.value = deg2min(cfg.m3_tilt_dm2/60, 1)
  m2_tilt_dm2_amp_str.value = deg2min(cfg.m2_tilt_dm2_amp/60, 1)
  m2_tilt_dm2_zero_str.value = deg2min(cfg.m2_tilt_dm2_zero/60, 1)
  m2_roll_coupling_str.value = deg2min(cfg.m2_roll_coupling/60, 1)
  m2_roll_zero_str.value = deg2min(cfg.m2_roll_zero/60, 4)
  m1_offset_str.value = deg2min(cfg.m1_offset/60, 4)
  m2_offset_str.value = deg2min(cfg.m2_offset/60, 4)
  m3_offset_str.value = deg2min(cfg.m3_offset/60, 4)
  update_snapshot_params()
}

const snapshot_params      = ref('')
const update_snapshot_params = () => snapshot_params.value = current_params.value
const current_params = computed(() => `${m3_tilt_dm1_str.value}${m3_tilt_dm2_str.value}${m2_tilt_dm2_amp_str.value}${m2_tilt_dm2_zero_str.value}${m2_roll_coupling_str.value}${m2_roll_zero_str.value}${m1_offset_str.value}${m2_offset_str.value}${m3_offset_str.value}`)
const is_dirty = computed(() => current_params.value != snapshot_params.value)



async function apply_params() {
  const payload = {
    m3_tilt_dm1: dms2deg(m3_tilt_dm1_str.value, 'deg'),
    m3_tilt_dm2: dms2deg(m3_tilt_dm2_str.value, 'deg'),
    m2_tilt_dm2_amp: dms2deg(m2_tilt_dm2_amp_str.value, 'deg'),
    m2_tilt_dm2_zero: dms2deg(m2_tilt_dm2_zero_str.value, 'deg'),
    m2_roll_coupling: dms2deg(m2_roll_coupling_str.value, 'deg'),
    m2_roll_zero: dms2deg(m2_roll_zero_str.value, 'deg'),
    m1_offset: dms2deg(m1_offset_str.value, 'deg'),
    m2_offset: dms2deg(m2_offset_str.value, 'deg'),
    m3_offset: dms2deg(m3_offset_str.value, 'deg'),
    advanced_align_rbc: true,
  }
  await cfg.configUpdate(payload)
  load_params()
}


onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) {
    await cfg.configFetch()
  }
  load_params()
})


async function onModelUpdate(v:  boolean ) {
  const payload = { advanced_align_rbc: v }
  console.log(payload)
  await cfg.configUpdate(payload) 
  load_params()
}

// async function onM1Plus(payload: { isPressed: boolean }) {
//     await dev.apiAction('Polaris:MoveMotor', `{"axis":0,"rate":${payload.isPressed ? 5 : 0}}`)
// }

</script>
