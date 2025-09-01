<template>
  <q-page >
    <!-- Header Row -->
    <div class="row q-pa-sm q-col-gutter-md items-center">
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
    <div flat bordered class="col ">
        <div class="row">
            <div clas="col">
               <ScaleDisplay  :pv="pv" :sp="90.0023" :scaleRange="sr" :scaleStart="10"  :domain="domainChoice" />
            </div>
            <div >
            <div class="col-12 q-pa-lg q-gutter-md">
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
                    {label: '10°', value: 80},
                    {label: '5°', value: 50},
                    {label: '1°', value: 10},
                    {label: '20\'', value: 2.9},
                    {label: '10\'', value: 1.3},
                    {label: '5\'', value: 40/60},
                    {label: '1\'', value: 10/60},
                    {label: '20\'\'', value: 2.9/60},
                    {label: '10\'\'', value: 1.3/60},
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
        </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted,ref, computed } from 'vue'
import ScaleDisplay from 'components/ScaleDisplay.vue'
import type { DomainStyleType } from 'components/ScaleDisplay.vue'

const pv = ref<number>(120.234761)
const domainChoice = ref<DomainStyleType>('semilo_360')
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
