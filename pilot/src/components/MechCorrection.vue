<template>
    <q-card flat bordered class="q-pa-md full-width">
      <div class="text-h6">Mechanical Alignment Correction Model</div>
      <div class="row">
        <div class="col text-grey text-caption">
          Reduce pointing residuals by fitting the mount's and camera's mechanical geometry alongside the alignment. 
        </div>
        <q-space />
        <div class="q-gutter-md flex justify-end q-mr-md">
          <q-item-section>
            <div>
              <q-btn-toggle v-model="cfg.advanced_align_mac" push rounded glossy toggle-color="primary"
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

      <div class="col-12 text-h7 q-pt-md">M2 and M3 Offsets</div>
      <div class="row q-col-gutter-md">
        <div class="col-9 text-grey text-caption">
          <div>Fitted automatically at every alignment sync, these offsets compensate for the current setup.</div>
          <div class="q-pl-md q-pt-sm text-body1">θ₂′ = θ₂ + M2 offset, &nbsp; θ₃′ = θ₃ + M3 offset</div>
        </div>
        <div class="col-3">
          <q-input label="M2 offset (arcmin)" readonly :model-value="d2_str" input-class="text-right" :disable="!cfg.advanced_align_mac"/>
          <q-input label="M3 offset (arcmin)" readonly :model-value="d3_str" input-class="text-right" :disable="!cfg.advanced_align_mac"/>
        </div>
      </div>
      <div class="col-12 text-h7 q-pt-sm">M2 Scale</div>
      <div class="row q-col-gutter-md q-pb-lg">
        <div class="col-9 text-grey text-caption">
          <div>M2 can turn slightly further than its reported angle. 
            AutoTune refines it from an alignment of 6 or more points spread in altitude.</div>
          <div class="q-pl-md q-pt-sm text-body1">θ₂′ = θ₂ + M2 offset + scale × (θ₂ − 45°)</div>
        </div>
        <div class="col-3">
          <q-input label="M2 scale (%)" v-model="m2_scale_str" input-class="text-right" :disable="!cfg.advanced_align_mac"/>
          <div class="q-pt-md q-gutter-sm column items-center">
            <q-btn  v-if="is_dirty" rounded  color="grey-9"  label="Apply Changes" @click="apply_params"/>
            <q-btn  v-else label="AutoTune" icon='mdi-tune-vertical' rounded  color="grey-9" :disable="!cfg.advanced_align_mac">
              <q-popup-proxy><MechAutotune class="" /></q-popup-proxy>
            </q-btn>
          </div>
        </div>
      </div>

    </q-card>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useConfigStore } from 'stores/config';
import { useStatusStore } from 'src/stores/status'
import MechAutotune from 'src/components/MechAutotune.vue';

const cfg = useConfigStore()
const p = useStatusStore()

const d2_str = computed(() => ((p.alignmodel?.[0] ?? 0) * 60).toFixed(1))
const d3_str = computed(() => ((p.alignmodel?.[1] ?? 0) * 60).toFixed(1))

const m2_scale_str = ref('1.00')
const snapshot = ref('')
const is_dirty = computed(() => m2_scale_str.value != snapshot.value)

watch(() => cfg.align_m2_scale, () => load_params())

function load_params() {
  m2_scale_str.value = Number(cfg.align_m2_scale ?? 0).toFixed(2)
  snapshot.value = m2_scale_str.value
}

async function apply_params() {
  const v = parseFloat(m2_scale_str.value)
  if (!Number.isFinite(v)) {
    load_params()
    return
  }
  await cfg.configUpdate({ align_m2_scale: v })
  load_params()
}

onMounted(() => {
  load_params()
})

async function onModelUpdate(v: boolean) {
  await cfg.configUpdate({ advanced_align_mac: v })
  load_params()
}
</script>
