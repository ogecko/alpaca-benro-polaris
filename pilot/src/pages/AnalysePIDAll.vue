<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-col-gutter-md items-center q-mb-sm">
      <!-- Title and Subtitle -->
      <div class="col-12 col-md text-h6 q-ml-md">
        Alpaca Driver Performance Analysis
        <div class="text-caption text-grey-6">
          Use these pages to perform tests and analyse the performance of your Benro Polaris.
        </div>
      </div>

      <!-- Status and Toggle (stacked on small screens) -->
      <div class="col-12 col-md-auto q-gutter-sm flex justify-end items-center q-mr-md">
        <PIDStatus />
        <q-btn-toggle
          v-model="coord"
          push
          rounded
          glossy
          toggle-color="primary"
          :options="[
            { label: 'Mot', value: 0 },
            { label: 'Top', value: 1 },
            { label: 'Equ', value: 2 }
          ]"
        />
      </div>
    </div>

    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch q-pb-sm">
      <!-- Angular Position Plot -->
      <div v-for="n in 3" :key="n" class="col-12 col-lg-4 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <q-list>
            <q-item >
              <q-item-section>
                <q-item-label>{{axisLabel(n)}} Angular Position (degrees) vs Time (seconds)</q-item-label>
                <q-item-label caption>SP: Setpoint Position, PV: Present Value Position</q-item-label>
              </q-item-section>
              <q-item-section side >
                <q-btn size="sm" icon="mdi-chart-bell-curve-cumulative" label="Tune" :to="{path:'/pid',query:{a:n-1}}"/>
              </q-item-section>
            </q-item>
          </q-list>
          <ChartXY :data="chartPosData(n)" x1Type="time"></ChartXY>
        </q-card>
      </div>
    </div>
    <div class="row q-col-gutter-sm items-stretch">
      <!-- Angular Velocity Plot -->
      <div v-for="n in 3" :key="n" class="col-12 col-lg-4 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <q-list>
          </q-list>
            <q-item >
              <q-item-section>
                <q-item-label>{{motorLabel(n)}} Angular Velocity (degrees/s) vs Time (seconds)</q-item-label>
                <q-item-label caption>OP: Output Velocity, Kp: Proportion, Ki: Integral, Kd: Derivative, FF: Feed Forward</q-item-label>
                </q-item-section>
            </q-item>
          <ChartXY  :data="chartVelData(n)" x1Type="time"></ChartXY>
        </q-card>
      </div>    
    </div>
  </q-page>
</template>


<script setup lang="ts">
import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useConfigStore } from 'src/stores/config'
import { useDeviceStore } from 'src/stores/device'
import PIDStatus from 'src/components/PIDStatus.vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, PIDMessage }from 'src/stores/stream'

const socket = useStreamStore()
const cfg = useConfigStore()
const dev = useDeviceStore()

const coord = ref<number>(2)


const axisOptionsData = [
  [ { label: 'M1', value: 0 }, { label: 'M2', value: 1 },   { label: 'M3', value: 2 } ],
  [ { label: 'Az', value: 0 }, { label: 'Alt', value: 1 },   { label: 'Roll', value: 2 } ],
  [ { label: 'RA ', value: 0 }, { label: 'Dec', value: 1 },   { label: 'PA ', value: 2 } ],
]
const axisLabel = (n:number) => {
  const group = axisOptionsData[coord.value]
  return group?.[n-1]?.label ?? ''
}

const motorLabel = (n:number) => `M${n}`



const chartPosData = (n:number) => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatPosData(n))
}

const chartVelData = (n:number) => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatVelData(n))
}






function formatPosData(n: number) {

  return (d: TelemetryRecord): DataPoint => {
    const time = new Date(d.ts)
    const data = d.data as PIDMessage

    let pvKey: keyof PIDMessage
    let spKey: keyof PIDMessage

    if (coord.value === 0) {
      pvKey = "θ_pv"
      spKey = "θ_sp"
    } else if (coord.value === 1) {
      pvKey = "α_pv"
      spKey = "α_sp"
    } else {
      pvKey = "Δ_pv"
      spKey = "Δ_sp"
    }

    const PV = data[pvKey]?.[n-1] ?? 0
    const SP = data[spKey]?.[n-1] ?? 0

    return { x1: time, PV, SP }
  }
}


function formatVelData(n: number) {
  return (d: TelemetryRecord):DataPoint => {
    const time = new Date(d.ts)
    const data = d.data as PIDMessage
    const OP = data.ω_op[n-1] ?? 0
    const Kp = data.ω_kp[n-1] ?? 0
    const Ki = data.ω_ki[n-1] ?? 0
    const Kd = data.ω_kd[n-1] ?? 0
    const FF = data.ω_ff[n-1] ?? 0
    return { x1: time, Kp, Ki, Kd, FF, OP  }
  }
}


onMounted(async () => {
  await cfg.configFetch()
  socket.subscribe('pid')
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('pid')
})

watch(() => dev.isVisible, (isVisible) => {
  void (isVisible ? socket.subscribe('pid') : socket.unsubscribe('pid'))
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