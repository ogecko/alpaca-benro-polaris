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
      <div class="q-gutter-md flex justify-end q-mr-md">
        <div class="col-auto q-gutter-sm flex justify-end items-center">
          <q-btn  rounded  color="grey-9"  label="Save" 
                  @click="save" :disable="cfg.isSaving" :loading="cfg.isSaving" />
          <q-btn rounded color="grey-9"  label="Restore" 
                  @click="restore" :disable="cfg.isRestoring" :loading="cfg.isRestoring"/>
        </div>
      </div>

    </div>

    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12 flex">
      <q-card flat bordered class="col q-pa-md">
        <div class="row">
          <!-- KF intro description -->
          <div class="col-md-6">
<q-markdown  :no-mark="false">
# Kalman Filter Tuning
The purpose of a Kalman Filter (KF) is to estimate the true orientation of the telescope mount. It combines noisy sensor measurements and expected motion to produce the most accurate result possible. 

This page presents the raw sensor data in dark green, the filtered data in yellow, and the control velocity in red. Changes take effect immediately, use Settings Save to store adjustments.
</q-markdown>
          </div>
          <!-- KF intro settings -->
          <div class="col-md-6 q-pt-sm">
            <q-list >
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
                    Use the following action buttons to move the motor and monitor how the filtered position tracks the raw sensor readings. 
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </div>
      </q-card>
      </div>
      <!-- Angular Position Plot -->
      <div class="col-12 col-lg-6 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <q-list>
            <q-item >
              <q-item-section>
                <q-item-label>Angular Position (degrees) vs Time (seconds);  K Gain = {{ K_gain.pos }}</q-item-label>
                <q-item-label caption>M1-3: Measured Position, PV: Present Value Position </q-item-label>
              </q-item-section>
            </q-item>
            <ChartXY :data="chartPosData" x1Type="time"></ChartXY>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="pos_meas_var_log" show-value :min="0" :inner-min="1" :inner-max="6" :max="7" :step="0.1">{{pos_meas_str}}</q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Angular Position Measurement Error (R) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  This defines the expected uncertainty in the measurement of angular position. 
                  Larger values means less trust in position measurement, smoother but possibly lagging estimates. 
                </q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="pos_proc_var_log" show-value :min="0" :inner-min="1" :inner-max="6" :max="7" :step="0.1">{{pos_proc_str}}</q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Angular Position Process Error (Q) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  This defines the expected uncertainty in the dynamic process of predicting angular position.  
                  Larger values means less trust in position prediction, smoother but possibly lagging estimates. 
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card>
      </div>
      <!-- Angular Velocity Plot -->
      <div class="col-12 col-lg-6 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <q-list>
            <q-item >
              <q-item-section>
                <q-item-label>Angular Velocity (degrees/s) vs Time (seconds);  K Gain = {{ K_gain.vel }}</q-item-label>
                <q-item-label caption>M1-3: Measured Velocity, PV: Present Value Velocity. SP: Setpoint Velocity</q-item-label>
              </q-item-section>
            </q-item>
            <ChartXY  :data="chartVelData" x1Type="time"></ChartXY>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="vel_meas_var_log" show-value :min="0" :inner-min="1" :inner-max="6" :max="7" :step="0.1">{{vel_meas_str}}</q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Angular Velocity Measurement Error (R) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  The defines the expected uncertainty in the measurement of angular velocity.  
                  Larger values means less trust in velocity measurement, smoother but possibly lagging estimates. 
                </q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section side top>
                <q-knob v-model="vel_proc_var_log" show-value :min="0" :inner-min="1" :inner-max="6" :max="7" :step="0.1">{{vel_proc_str}}</q-knob>
              </q-item-section>
              <q-item-section>
                <q-item-label> Angular Velocity Process Error (Q) for {{ motor }}</q-item-label>
                <q-item-label caption>
                  This defines the expected uncertainty in the dynamic process of predicting angular velocity.  
                  Larger values means less trust in velocity prediction, smoother but possibly lagging estimates. 
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card>
      </div>    
    </div>
  </q-page>
</template>


<script setup lang="ts">
import { useQuasar, debounce } from 'quasar'
import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useConfigStore } from 'src/stores/config'
import { useDeviceStore } from 'src/stores/device'
import { formatAngle } from 'src/utils/scale'
import MoveButton from 'src/components/MoveButton.vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, KalmanMessage }from 'src/stores/stream'

const $q = useQuasar()
const socket = useStreamStore()
const cfg = useConfigStore()
const dev = useDeviceStore()

const axis = ref<number>(0)
const pos_meas_var_log = ref<number>(5)
const vel_meas_var_log = ref<number>(5)      // typically 1 to 10
const pos_proc_var_log = ref<number>(5)
const vel_proc_var_log = ref<number>(5)      

const motor = computed<string>(() => `M${axis.value+1}`)
const pos_meas_var = computed<number>(() => log2var(pos_meas_var_log.value))
const pos_meas_str = computed<string>(() => var2str(pos_meas_var.value))
const vel_meas_var = computed<number>(() => log2var(vel_meas_var_log.value))
const vel_meas_str = computed<string>(() => var2str(vel_meas_var.value))
const pos_proc_var = computed<number>(() => log2var(pos_proc_var_log.value))
const pos_proc_str = computed<string>(() => var2str(pos_proc_var.value))
const vel_proc_var = computed<number>(() => log2var(vel_proc_var_log.value))
const vel_proc_str = computed<string>(() => var2str(vel_proc_var.value))
const var2log = (x:number) => Math.log10(x) + 6
const log2var = (k:number) => Math.pow(10,-6 + k)
const var2str = (x:number) => formatAngle(x,'deg',1)

const chartPosData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatPosData)
})

const chartVelData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatVelData)
})

const K_gain = computed((): { pos: string; vel: string } => {
  const last = socket.topics?.kf?.[socket.topics.kf.length - 1];
  if (!last) return { pos: '', vel: '' };

  const data = last.data as Partial<KalmanMessage>;
  const gain = data.K_gain;

  if (Array.isArray(gain) && gain.length === 6 && axis.value >= 0 && axis.value < 3) {
    const pos = gain[axis.value] ?? 0;
    const vel = gain[axis.value + 3] ?? 0;
    return {
      pos: pos.toFixed(2),
      vel: vel.toFixed(2),
    };
  }

  return { pos: '', vel: '' };
});



watch([pos_meas_var, vel_meas_var, pos_proc_var, vel_proc_var], (newVal)=>{
  const payload = { kf_measure_noise: [...cfg.kf_measure_noise], kf_process_noise: [...cfg.kf_process_noise]}
  payload.kf_measure_noise[axis.value] = newVal[0]
  payload.kf_measure_noise[axis.value+3] = newVal[1]
  payload.kf_process_noise[axis.value] = newVal[2]
  payload.kf_process_noise[axis.value+3] = newVal[3]
  putdb(payload)
})

watch(axis, () => setKnobValues())

async function onPlus(payload: { isPressed: boolean }) {
    const isPressed = payload.isPressed
    await dev.apiAction('Polaris:MoveMotor', `{"axis":${axis.value},"rate":${isPressed ? 0.0178360 : 0}}`)

}
async function onMinus(payload: { isPressed: boolean }) {
    const isPressed = payload.isPressed
    await dev.apiAction('Polaris:MoveMotor', `{"axis":${axis.value},"rate":${isPressed ? -0.0178360 : 0}}`)
}


function setKnobValues() {
  const idx = axis.value ?? 0

  const pos_meas_var = cfg.kf_measure_noise[idx] ?? 1e-6;
  pos_meas_var_log.value = var2log(pos_meas_var);

  const vel_meas_var = cfg.kf_measure_noise[idx + 3] ?? 1e-6;
  vel_meas_var_log.value = var2log(vel_meas_var)
  
  const pos_proc_var = cfg.kf_process_noise[idx] ?? 1e-6;
  pos_proc_var_log.value = var2log(pos_proc_var);

  const acc_proc_var = cfg.kf_process_noise[idx] ?? 1e-6;
  vel_proc_var_log.value = var2log(acc_proc_var);
}


function formatPosData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as KalmanMessage
  const mxKey = `M${axis.value + 1}`
  const MX = data.θ_meas[axis.value] ?? 0
  const PV = data.θ_state[axis.value] ?? 0
  return { x1: time, [mxKey]: MX, PV }
}

function formatVelData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as KalmanMessage
  const mxKey = `M${axis.value + 1}`
  const MX = data.ω_meas[axis.value] ?? 0
  const PV = data.ω_state[axis.value] ?? 0
  const SP = data.ω_ref[axis.value] ?? 0
  return { x1: time, [mxKey]: MX, PV, SP }
}


onMounted(async () => {
  await cfg.configFetch()
  socket.subscribe('kf')
  setKnobValues()
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('kf')
})

watch(() => dev.isVisible, (isVisible) => {
  void (isVisible ? socket.subscribe('kf') : socket.unsubscribe('kf'))
})

async function save() {
  const ok = await cfg.configSave()
  $q.notify({ message:`Configuration save ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }] })
}

async function restore() {
  const ok = await cfg.configRestore()
  $q.notify({ message:`Configuration restore ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  setKnobValues()
}

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