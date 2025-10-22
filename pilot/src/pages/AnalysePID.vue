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
          <!-- PID intro description -->
          <div class="col-md-6">
<q-markdown  :no-mark="false">
# PID Controller Tuning
The purpose of the PID controller is to regulate the mount’s motion so that it accurately follows the target setpoint position.

This page displays the SP, PV, OP and Error Signals. Changes to PID gains take effect immediately. Use Save to store your adjustments.
</q-markdown>
          </div>
          <!-- PID intro settings -->
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
                  </q-item-label>
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
                <q-item-label>Angular Position (degrees) vs Time (seconds)</q-item-label>
                <q-item-label caption>SP: Setpoint Green, PV: Present Value White</q-item-label>
              </q-item-section>
            </q-item>
          <ChartXY :data="chartPosData" x1Type="time"></ChartXY>
          <div class="row q-pt-lg q-pl-xl items-center justify-center">
            <div class="col row q-gutter-sm">
                <q-knob v-model="Ke_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="1.0" :max="1.2" :step="0.01">{{Ke_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Ke</div>
                  <div class="text-caption">Expotential Smoothing Gain</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kc_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="2.0" :max="2.2" :step="0.01">{{Kc_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kc</div>
                  <div class="text-caption">Goto Tollerance (arc-min)</div>
                </div> 
            </div>
          </div>
          </q-list>
          <div class="q-pb-xl"></div>
        </q-card>
      </div>
      <!-- Angular Velocity Plot -->
      <div class="col-12 col-lg-6 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <q-list>
          </q-list>
            <q-item >
              <q-item-section>
                <q-item-label>Angular Velocity (degrees/s) vs Time (seconds)</q-item-label>
                <q-item-label caption>OP: Output Red, Kp: Proportion Yellow, Ki: Integral Orange, Kd: Derivative Red, FF: Slew Rate Green</q-item-label>
              </q-item-section>
            </q-item>
          <ChartXY  :data="chartVelData" x1Type="time"></ChartXY>
          <div class="row q-pt-lg q-pl-xl items-center justify-center">
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kp_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="2.0" :max="2.2" :step="0.01">{{Kp_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kp</div>
                  <div class="text-caption">Proportional Gain</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Ki_var" show-value :min="-0.2" :inner-min="0.0" :inner-max="2.0" :max="2.2" :step="0.01">{{Ki_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Ki</div>
                  <div class="text-caption">Integral Gain</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kd_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="2.0" :max="2.2" :step="0.01">{{Kd_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kd</div>
                  <div class="text-caption">Derivative Gain</div>
                </div> 
            </div>
          </div>

          <div class="q-pb-xl"></div>
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
import MoveButton from 'src/components/MoveButton.vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, PIDMessage }from 'src/stores/stream'

const $q = useQuasar()
const socket = useStreamStore()
const cfg = useConfigStore()
const dev = useDeviceStore()

const axis = ref<number>(0)
const Kp_var = ref<number>(0)
const Ki_var = ref<number>(0)      
const Kd_var = ref<number>(0)      
const Ke_var = ref<number>(0)      
const Kc_var = ref<number>(0)      

const motor = computed<string>(() => `M${axis.value+1}`)
const Kp_str = computed<string>(() => var2str(Kp_var.value))
const Ki_str = computed<string>(() => var2str(Ki_var.value))
const Kd_str = computed<string>(() => var2str(Kd_var.value))
const Ke_str = computed<string>(() => var2str(Ke_var.value))
const Kc_str = computed<string>(() => var2str(Kc_var.value))
const var2str = (x:number) => x.toFixed(2)

const chartPosData = computed<DataPoint[]>(() => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatPosData)
})

const chartVelData = computed<DataPoint[]>(() => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatVelData)
})


watch([Kp_var, Ki_var, Kd_var, Ke_var, Kc_var], (newVal)=>{
  const payload = { pid_Kp: [...cfg.pid_Kp], pid_Ki: [...cfg.pid_Ki], pid_Kd:[...cfg.pid_Kd], pid_Ke:[...cfg.pid_Ke], pid_Kc:[...cfg.pid_Kc]}
  payload.pid_Kp[axis.value] = newVal[0]
  payload.pid_Ki[axis.value] = newVal[1]
  payload.pid_Kd[axis.value] = newVal[2]
  payload.pid_Ke[axis.value] = newVal[3]
  payload.pid_Kc[axis.value] = newVal[4]
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

  Kp_var.value = cfg.pid_Kp[idx] ?? 0;
  Ki_var.value = cfg.pid_Ki[idx] ?? 0;
  Kd_var.value = cfg.pid_Kd[idx] ?? 0;
  Ke_var.value = cfg.pid_Ke[idx] ?? 0;
  Kc_var.value = cfg.pid_Kc[idx] ?? 0;
}


function formatPosData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as PIDMessage
  const y1 = data.θ_pv[axis.value] ?? 0
  const y2 = data.θ_sp[axis.value] ?? 0
  return { x1: time, y1, y2 }
}

function formatVelData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as PIDMessage
  const y1 = data.ω_kp[axis.value] ?? 0
  const y2 = data.ω_op[axis.value] ?? 0
  const y3 = data.ω_ff[axis.value] ?? 0
  const y4 = data.ω_ki[axis.value] ?? 0
  const y5 = data.ω_kd[axis.value] ?? 0
  return { x1: time, y1, y2, y3, y4, y5 }
}


onMounted(async () => {
  await cfg.configFetch()
  socket.subscribe('pid')
  setKnobValues()
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('pid')
})

watch(() => dev.isVisible, (isVisible) => {
  void (isVisible ? socket.subscribe('pid') : socket.unsubscribe('pid'))
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