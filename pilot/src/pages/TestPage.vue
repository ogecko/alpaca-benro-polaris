<template>
  <q-page>
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
        <q-btn-dropdown rounded color="grey-9" label="Log Settings" :content-style="{ width: '400px' }">
          dummy dropdown content
        </q-btn-dropdown>
      </div>
    </div>

    <!-- Log card fills rest -->
    <div flat bordered class="col ">
      <div class="row">
        <div clas="col">
          <ScaleDisplay :pv="pv" :sp="sp" label="Azimuth" :scaleRange="12" :scaleStart="10" :domain="domainChoice" />
        </div>
        <div class="col-12 q-pa-lg q-gutter-md">
          <q-btn-toggle v-model="domainChoice" color="brown" text-color="white" toggle-color="orange"
            toggle-text-color="black" rounded unelevated glossy :options="[
                  {label: 'Az', value: 'az_360'},
                  {label: 'Alt', value: 'alt_90'},
                  {label: 'Roll', value: 'roll_180'},
                  {label: 'RA', value: 'ra_24'},
                  {label: 'Dec', value: 'dec_180'},
                  {label: 'PA', value: 'pa_180'},
                  {label: 'Linear', value: 'linear_360'},
                  {label: 'Circular', value: 'circular_360'},
                  ]" />
          <q-list>
            <q-item>
              <q-item-section avatar>
                <q-icon name="mdi-triangle">PV</q-icon>
              </q-item-section>
              <q-item-section>
                <q-slider v-model="pv" :min="0" :max="360" :step="0.01" label label-always color="orange" track-color="brown" thumb-color="black" />
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section avatar>
                <q-icon color="positive" name="mdi-arrow-up-bold" >SP</q-icon>
              </q-item-section>
              <q-item-section>
                <q-slider v-model="sp" :min="0" :max="360" :step="0.01" label label-always color="orange" track-color="brown" thumb-color="black" />
              </q-item-section>
            </q-item>
          </q-list>
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted,ref } from 'vue'
import ScaleDisplay from 'components/ScaleDisplay.vue'
import type { DomainStyleType } from 'components/ScaleDisplay.vue'

const pv = ref<number>(0)
const sp = ref<number>(90)
const domainChoice = ref<DomainStyleType>('az_360')



onMounted(() => {
})

onUnmounted(() => {
})


</script>
