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
import { onMounted, onUnmounted, computed } from 'vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import type { TelemetryRecord, KalmanMessage }from 'src/stores/stream'

const socket = useStreamStore()

function formatKalmanData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts).getTime()/1000
  const data = d.data as KalmanMessage
  const value = ('θ1_meas' in data) ? data.θ1_meas : 0
  return { time, value }
}

const kalmanData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatKalmanData)
})

onMounted(() => {
  // timer = setInterval(generateData, 50)
  socket.subscribe('kf')
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('kf')
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