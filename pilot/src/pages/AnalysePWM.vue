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

    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12 flex">
      <q-card flat bordered class="col q-pa-md">
        <div class="row">
          <!-- KF intro -->
          <div class="col-md-6">
<q-markdown  :no-mark="false">
# Motor PWM Testing
To achieve the precise, low-speed motion required for sidereal tracking, we control the motors using Pulse Width Modulation (PWM). By adjusting the period and pulse width, we can finely tune motor behavior to maintain consistent tracking rates.

This page allows you to evaluate the speed performance of each motor across a range of PWM configurations, helping you identify optimal settings for smooth, accurate motion.
</q-markdown>
          </div>
          <div class="col-md-6 q-pt-sm">
            <q-list style="max-width: 800px">
              <!-- Choose Motor -->
              <q-item>
                <q-item-section side top>
                    <q-btn-toggle v-model="axis" push rounded glossy toggle-color="primary"  
                      :options="[
                        {label: 'M1', value: 0},
                        {label: 'M2', value: 1},
                        {label: 'M3', value: 2}
                      ]"
                    />
                </q-item-section>
                <q-item-section>
                  <q-item-label> Choosen Motor Axis</q-item-label>
                  <q-item-label caption>
                    Select the motor axis you'd like to analyse and tune. Motor 1 Azimuth; Motor 2 Altitude; Motor 3 Astro head. 
                    Keep in mind: when Motor 3 (Astro Head) is rotated, the orientation of Motor 1 and Motor 2 no longer corresponds directly to Azimuth and Altitude.            </q-item-label>
                </q-item-section>
              </q-item>
              <!-- Test Motor -->
              <q-item :inset-level="1">
                <q-item-section top side>
                  <div class=" q-gutter-ax">
                  <MoveButton activeColor="positive" icon="mdi-minus-circle" @push="onMinus"/>
                  <MoveButton activeColor="positive" icon="mdi-plus-circle" @push="onPlus"/>
                  </div>
                </q-item-section>
                <q-item-section >
                  <q-item-label> Test movement of {{ motor }}</q-item-label>
                  <q-item-label caption>
                    Use the following action buttons to move the motor and monitor how well the motor speed is controlled. 
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </div>
      </q-card>
      </div>
      <div class="col-md-6 flex">
        <q-card flat bordered class="col">
          <q-list style="max-width: 800px">
            <q-item>
              <q-item-section side top>
                <q-knob v-model="active_rate" show-value :min="0" :inner-min="1" :inner-max="5" :max="6" :step="1"></q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> On Duty Slew Rate for {{ motor }}</q-item-label>
                <q-item-label caption>
                  The active duty slew rate based on the fine motion rates used in the Polaris app.
                </q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="delta_rate" show-value :min="0" :inner-min="1" :inner-max="2" :max="3" :step="1">{{ inactive_rate }}</q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Off Duty Slew Rate for {{ motor }}</q-item-label>
                <q-item-label caption>
                  The inactive duty slew rate either 1 or 2 below the active duty rate.
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <ChartXY  :data="chartPosData" x1Type="time"></ChartXY>
          <div class="q-pb-xl"></div>
        </q-card>
    </div>    
      <div class="col-md-6 flex">
        <q-card flat bordered class="col">
          <q-list>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="pulse_width" show-value :min="-1" :inner-min="0.01" :inner-max="cycle_period-0.01" :max="cycle_period+1" :step="0.01"></q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> On Duty Pulse width (s) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  This is the time a signal remains at the higher level during one complete cycle. 
                </q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="cycle_period" show-value :min="-1" :inner-min=".1" :inner-max="5" :max="6" :step="0.01"></q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Control Cycle Period (s) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  The total time for one complete ON–OFF cycle of the control signal. 
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <ChartXY  :data="chartVelData" x1Type="time"></ChartXY>
        </q-card>
      </div>    
  </div>

    <!-- First Preamble and Chart -->

</q-page>
</template>


<script setup lang="ts">
import { useTimeout } from 'quasar'
import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useDeviceStore } from 'src/stores/device'
// import { formatAngle } from 'src/utils/scale'
import MoveButton from 'src/components/MoveButton.vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, KalmanMessage }from 'src/stores/stream'

const socket = useStreamStore()
const dev = useDeviceStore()
const { registerTimeout, removeTimeout } = useTimeout()

const axis = ref<number>(0)
const cycle_period = ref<number>(1)
const pulse_width = ref<number>(0.5)
const active_rate = ref<number>(2)
const delta_rate = ref<number>(1)
const direction = ref<number>(1)

const motor = computed<string>(() => `M${axis.value+1}`)
const inactive_rate = computed<number>(() => active_rate.value - delta_rate.value)

const chartPosData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatPosData)
})
const chartVelData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatVelData)
})


async function onPlus(payload: { isPressed: boolean }) {
    direction.value = +1
    if (payload.isPressed) {
      await startPWM()
    } else {
      await stopPWM()
    }
}
async function onMinus(payload: { isPressed: boolean }) {
    direction.value = -1
    if (payload.isPressed) {
      await startPWM()
    } else {
      await stopPWM()
    }
}

async function startPWM() {
  await dutyOn()
}

async function stopPWM() {
  await dev.apiAction('Polaris:MoveMotor', `{"axis":${axis.value},"rate":0}`)

  removeTimeout()
}

async function dutyOn() {
  registerTimeout(() => { void dutyOff() }, pulse_width.value*1000)
  await dev.apiAction('Polaris:MoveMotor', `{"axis":${axis.value},"rate":${direction.value * active_rate.value}}`)
}

async function dutyOff() {
  registerTimeout(() => { void dutyOn() }, cycle_period.value*1000 - pulse_width.value*1000)
  await dev.apiAction('Polaris:MoveMotor', `{"axis":${axis.value},"rate":${direction.value * inactive_rate.value}}`)
}

function formatPosData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as KalmanMessage
  const y1 = data.θ_meas[axis.value] ?? 0
  const y2 = data.θ_state[axis.value] ?? 0
  return { x1: time, y1, y2 }
}


function formatVelData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as KalmanMessage
  const y1 = data.ω_meas[axis.value] ?? 0
  const y2 = data.ω_state[axis.value] ?? 0
  const y3 = data.ω_ref[axis.value] ?? 0
  return { x1: time, y1, y2, y3 }
}


onMounted(() => {
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