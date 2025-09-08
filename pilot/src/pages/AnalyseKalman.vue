<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Driver Performance Analysis
        <div class="text-caption text-grey-6">
        Use these pages to perform tests and analyse the performance of your Benro Polaris. 
       </div>
      </div>
      <q-space />
    </div>
    <q-card flat bordered class="col">
      <div>
      <q-markdown class="q-pa-md" :no-mark="false">
# Kalman Filter Analysis
Kalman Filter Analysis
        </q-markdown>

        <ChartXY  :data="kalmanData"></ChartXY>

        <div class="q-pb-xl"></div>
      </div>

    </q-card>
  </q-page>
</template>


<script setup lang="ts">
import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, ref } from 'vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import ChartXY from 'src/components/ChartXY.vue'

const kalmanData = ref<DataPoint[]>([])


function generateData() {
  const t = Date.now() / 1000
  const noisy = Math.sin(t) + Math.random() * 0.5

  // Simple Kalman filter stub (replace with real logic)
  const filtered = noisy

  kalmanData.value.push({ time: t, value: filtered })
  if (kalmanData.value.length > 500) kalmanData.value.shift()
}

let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  timer = setInterval(generateData, 100)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

</script>

<style lang="scss">
  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>