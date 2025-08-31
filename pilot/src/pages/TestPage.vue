<template>
  <q-page class="q-pa-sm">
    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Test Page
        <div v-if="$q.screen.gt.xs" class="text-caption text-grey-6">
        Test individual vue components or elements 
       </div>
      </div>
      <q-space />
      <div class="q-gutter-md flex justify-end q-mr-md">
        <q-btn-dropdown rounded color="grey-9" label="Log Settings" :content-style="{ width: '600px' }">
            dummy dropdown content
        </q-btn-dropdown>
      </div>
    </div>

    <!-- Log card fills rest -->
    <q-card flat bordered class="col q-pa-md">
        <div class="row">
            <div clas="col">
               <ScaleDisplay :sp="110.324" :pv="pv" :scaleStart="10" :scaleRange="sr" :domain="domainChoice" />
            </div>
            <div class="col-12">
                  <q-slider
                    v-model="pv"
                    :min="0"
                    :max="360"
                    :step="0.01"
                    label
                    label-always
                    color="orange"
                    track-color="brown"
                    thumb-color="black"
                  />
                  <q-slider
                    v-model="logSr"
                    :min="-2.3"
                    :max="2.3"
                    :step="0.01"
                    label
                    label-always
                    color="orange"
                    track-color="brown"
                    thumb-color="black"
                  />
                <q-btn-toggle
                    v-model="domainChoice"
                    color="brown"
                    text-color="white"
                    toggle-color="orange"
                    toggle-text-color="black"
                    rounded
                    unelevated
                    glossy
                    :options="[
                    {label: 'Linear', value: 'linear_360'},
                    {label: 'Circular', value: 'circular_360'},
                    {label: 'Semi Hi', value: 'semihi_360'},
                    {label: 'Semi Lo', value: 'semilo_360'},
                    ]"
                />
                <q-btn-toggle
                    v-model="sr"
                    color="brown"
                    text-color="white"
                    toggle-color="orange"
                    toggle-text-color="black"
                    rounded
                    unelevated
                    glossy
                    :options="[
                    {label: '200°', value: 200},
                    {label: '20°', value: 20},
                    {label: '2°', value: 2},
                    {label: '20\'', value: 20/60},
                    {label: '2\'', value: 2/60},
                    {label: '20\'\'', value: 20/3660},
                    ]"
                />
                <q-btn-toggle
                    v-model="pv"
                    color="brown"
                    text-color="white"
                    toggle-color="orange"
                    toggle-text-color="black"
                    rounded
                    unelevated
                    glossy
                    :options="[
                    {label: '358', value: 358},
                    {label: '359.9992', value: 359},
                    {label: '180', value: 180},
                    {label: '180.3', value: 180.3},
                    {label: '170', value: 170},
                    {label: '89.7', value: 89.7},
                    {label: '90.3', value: 90.3},
                    {label: '90.302', value: 90.302},
                    {label: '10.302', value: 10.302},
                    ]"
                />


  <div class="q-mt-md text-bold">
    Current range: {{ formatSr(sr) }}
  </div>


            </div>
        </div>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted,ref, computed } from 'vue'
import ScaleDisplay from 'components/ScaleDisplay.vue'
import type { DomainStyleType } from 'components/ScaleDisplay.vue'

const pv = ref<number>(120.234761)
const domainChoice = ref<DomainStyleType>('linear_360')
const logSr = ref(2) 


onMounted(() => {
})

onUnmounted(() => {
})

const sr = computed({
  get: () => Math.pow(10, logSr.value),
  set: val => { logSr.value = Math.log10(val) }
})

function formatSr(val: number): string {
  if (val >= 1) return `${val.toFixed(0)}°`
  if (val >= 1 / 60) return `${Math.round(val * 60)}′`
  return `${Math.round(val * 3600)}″`
}


</script>
