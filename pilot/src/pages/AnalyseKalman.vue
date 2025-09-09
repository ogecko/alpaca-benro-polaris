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
# Kalman Filter Tuning
The Kalman filter uses a model of how noisy our measurements are. For example, if our angular accelon sensor is accurate to within ±0.1°, we tell the filter that the standard deviation of the position measurement error is 0.1°. That helps it decide how much to trust each reading.      </q-markdown>
      <q-list>
        <q-item>
          <q-item-section side top>
            <q-knob v-model="axis_knob" show-value :min="0" :inner-min="1" :inner-max="3" :max="4" :step="1"></q-knob>
          </q-item-section>
          <q-item-section>
            <q-item-label> Choosen Motor Axis</q-item-label>
            <q-item-label caption>
              Pick the motor axis that you wish to analyse and tune. Motor 1 = Azimuth, Motor 2 = "Altitude", Motor 3 = "Astro head". 
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item>
          <q-item-section side top>
            <q-knob v-model="pos_variance_log" show-value :min="1" :max="6" :step="0.1">{{pos_stdev}}</q-knob>
          </q-item-section>
          <q-item-section>
            <q-item-label> Angular Position Measurement Error for M{{ axis_knob }}</q-item-label>
            <q-item-label caption>
              This defines the expected uncertainty in the measurement of angular position. 
              Larger values means less trust in position measurement, smoother but possibly lagging estimates. 
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item>
          <q-item-section side top>
            <q-knob v-model="accel_variance_factor" show-value :min="1" :max="100" :step="0.1">{{accel_stdev}}</q-knob>
          </q-item-section>
          <q-item-section>
            <q-item-label> Angular Velocity Measurement Error for M{{ axis_knob }}</q-item-label>
            <q-item-label caption>
              The velocity is calculated from the change in position and its uncertainty is based on the position uncertainty times this factor. 
              A larger factor means less trust in velocity measurement, smoother but possibly lagging estimates. 
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item class="col-6 row items-top">
        
        </q-item>
      </q-list>
      <ChartXY  :data="chartData"></ChartXY>
      <div class="q-pb-xl"></div>
    </q-card>


</q-page>
</template>


<script setup lang="ts">
import { debounce } from 'quasar'
import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useConfigStore } from 'src/stores/config'
import { formatAngle } from 'src/utils/scale'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, KalmanMessage }from 'src/stores/stream'

const socket = useStreamStore()
const cfg = useConfigStore()

const axis_knob = ref<number>(1)
const pos_variance_log = ref<number>(5)
const accel_variance_factor = ref<number>(5)      // typically 1 to 10

const dt = 0.2 // 200ms
const axis = computed<number>(() => axis_knob.value - 1)
const pos_variance = computed<number>(() =>Math.pow(10,-6+pos_variance_log.value))
const pos_stdev = computed<string>(() => formatAngle(Math.sqrt(pos_variance.value),'deg'))
const accel_variance = computed<number>(() => accel_variance_factor.value * pos_variance.value / dt / dt)
const accel_stdev = computed<string>(() => formatAngle(Math.sqrt(accel_variance.value),'deg'))

const chartData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatChartData)
})

watch(pos_variance, (newVal)=>{
  const payload = { kf_measure_noise: cfg.kf_measure_noise}
  payload.kf_measure_noise[axis.value] = newVal
  putdb(payload)
})

watch(accel_variance, (newVal)=>{
  const payload = { kf_measure_noise: cfg.kf_measure_noise}
  payload.kf_measure_noise[axis.value+3] = newVal
  putdb(payload)
})

watch(axis, () => setKnobValues())

function setKnobValues() {
  const idx = axis.value ?? 0
  const posVar = cfg.kf_measure_noise[idx] ?? 1e-6;
  pos_variance_log.value = Math.log10(posVar) + 6;

  const accelVar = cfg.kf_measure_noise[idx + 3] ?? 1e-4;
  accel_variance_factor.value = accelVar * dt * dt / posVar;
}

function formatChartData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts).getTime()/1000
  const data = d.data as KalmanMessage
  let y1 = 0
  let y2 = 0
  if (axis.value==0) {
    y1 = ('θ1_meas' in data) ? data.θ1_meas : 0
    y2 = ('θ1_state' in data) ? data.θ1_state : 0
  } else if (axis.value==1) {
    y1 = ('θ2_meas' in data) ? data.θ2_meas : 0
    y2 = ('θ2_state' in data) ? data.θ2_state : 0
  } else if (axis.value==2) {
    y1 = ('θ3_meas' in data) ? data.θ3_meas : 0
    y2 = ('θ3_state' in data) ? data.θ3_state : 0
  }
  return { time, y1, y2 }
}

onMounted(() => {
  socket.subscribe('kf')
  setKnobValues()
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('kf')
})


// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store 
const putdb = debounce((payload) => cfg.configUpdate(payload), 500) // slow put for input text


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