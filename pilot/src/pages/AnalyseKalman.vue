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

    <!-- First Preamble and Chart -->
    <q-card flat bordered class="col">
      <q-markdown class="q-pa-md" :no-mark="false">
# Kalman Filter Analysis
Kalman Filter Analysis
      </q-markdown>
      <ChartXY  :data="chartData"></ChartXY>
      <div class="q-pb-xl"></div>
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

function formatChartData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts).getTime()/1000
  const data = d.data as KalmanMessage
  const y1 = ('θ1_meas' in data) ? data.θ1_meas : 0
  const y2 = ('θ1_state' in data) ? data.θ1_state : 0
  return { time, y1, y2 }
}

const chartData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatChartData)
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