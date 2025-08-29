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
    <q-card flat bordered class="col q-pa-lg">
        <div class="row">
            <div clas="col">
               <ScaleDisplay :sp="110.324" :pv="110.33245" :scaleStart="10" :scaleRange="sr" :domain="ic" />
            </div>
            <div class="col-12">
                <q-btn-toggle
                    v-model="ic"
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
            </div>
        </div>

    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted,ref } from 'vue'
import ScaleDisplay from 'components/ScaleDisplay.vue'
import type { ScaleDomainType } from 'components/ScaleDisplay.vue'

const sr = ref<number>(2)
const ic = ref<ScaleDomainType>('linear_360')

onMounted(() => {
})

onUnmounted(() => {
})


</script>
