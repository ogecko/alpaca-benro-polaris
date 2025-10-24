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
The purpose of the PID controller is to regulate the mount’s motion so that it accurately follows the setpoint position. This page displays the SP, PV, and OP sent to the Speed Controller. The contribution of Kp, Ki, Kd and feed forward are also shown.

Changes to PID gains take effect immediately. Use Save to store your adjustments.
</q-markdown>
          </div>
          <!-- PID intro settings -->
          <div class="col-md-6 q-pt-sm">
            <q-list >
              <!-- Choose Coordinates  -->
              <q-item>
                <q-item-section side top>
                    <q-btn-toggle v-model="coord" push rounded glossy toggle-color="primary"  
                      :options="[
                        {label: 'Mot', value: 0},
                        {label: 'Top', value: 1},
                        {label: 'Equ', value: 2}
                      ]"
                    />
                </q-item-section>
                <q-item-section>
                  <q-item-label> Choosen Co-ordinate System</q-item-label>
                  <q-item-label caption>
                    Choose from Motor Angles, Topocentric or Equatorial. 
                  </q-item-label>
                </q-item-section>
              </q-item>

              <!-- Choose Motor -->
              <q-item>
                <q-item-section side top>
                    <q-btn-toggle v-model="axis" push rounded glossy toggle-color="primary" :options="axisOptions" />
                </q-item-section>
                <q-item-section>
                  <q-item-label> Choosen Motor Axis</q-item-label>
                  <q-item-label caption>
                    Select the motor axis you'd like to analyse and tune. 
                  </q-item-label>
                </q-item-section>
              </q-item>

              <!-- Test Case -->
              <q-item :inset-level="1">
                <q-item-section top side>
                  <div class=" q-gutter-ax">
                  <q-select label="Test Case"  v-model="testcase" :options="testcaseOptionsData">
                    <template v-slot:option="scope">
                      <q-item dense v-bind="scope.itemProps">
                        <q-item-section avatar>
                          <q-icon size="xs" :name="scope.opt.icon" />
                        </q-item-section>
                        <q-item-section>
                          <q-item-label>{{ scope.opt.label }}</q-item-label>
                        </q-item-section>
                      </q-item>
                    </template>
                  </q-select>
                  <MoveButton activeColor="positive" icon="mdi-minus-circle" @push="onMinus"/>
                  <MoveButton activeColor="positive" icon="mdi-plus-circle" @push="onPlus"/>
                  </div>
                </q-item-section>
                <q-item-section >
                  <q-item-label> Choose Test Case for {{ motor }}</q-item-label>
                  <q-item-label caption>
                    Choose the type and magnitude of the test case. Use the action buttons to move the motor and monitor PID response. 
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
                <q-item-label caption>SP: Setpoint Position, PV: Present Value Position</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <ChartXY :data="chartPosData" x1Type="time"></ChartXY>
          <div class="row q-pt-lg q-pl-xl items-top justify-center">
            <div class="col row q-gutter-sm">
                <q-knob v-model="Ka_var" show-value :min="-0.5" :inner-min="0.0" :inner-max="5.0" :max="5.5" :step="0.1">{{Ka_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Ka</div>
                  <div class="text-caption">Max OP Acceleration Rate (°/s²)</div>
                  <div class="text-caption">0 = Use Default Max</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kv_var" show-value :min="-1" :inner-min="0.0" :inner-max="9.5" :max="11" :step="0.1">{{Kv_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kv</div>
                  <div class="text-caption">Max OP Slew Velocity (°/s)</div>
                  <div class="text-caption">0 = Use Motor Calibration Max</div>
                </div> 
            </div>
          </div>
          <div class="row q-pt-lg q-pl-xl items-top justify-center">
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kc_var" show-value :min="-1" :inner-min="0.01" :inner-max="10.0" :max="11" :step="0.01">{{Kc_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kc</div>
                  <div class="text-caption">Goto Tollerance (arc-min)</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Ke_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="1.0" :max="1.2" :step="0.01">{{Ke_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Ke</div>
                  <div class="text-caption">Expotential OP Smoothing</div>
                </div> 
            </div>
          </div>
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
                <q-item-label caption>OP: Output Velocity, Kp: Proportion, Ki: Integral, Kd: Derivative, FF: Feed Forward</q-item-label>
                </q-item-section>
            </q-item>
          <ChartXY  :data="chartVelData" x1Type="time"></ChartXY>
          <div class="row q-pt-lg q-pl-xl items-top justify-center">
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kp_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="2.0" :max="2.2" :step="0.01">{{Kp_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kp<sub>{{ idx }}</sub></div>
                  <div class="text-caption">Proportional Gain</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Ki_var" show-value :min="-0.1" :inner-min="0.0" :inner-max="0.5" :max="0.6" :step="0.01">{{Ki_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Ki<sub>{{ idx }}</sub></div>
                  <div class="text-caption">Integral Gain</div>
                </div> 
            </div>
            <div class="col row q-gutter-sm">
                <q-knob v-model="Kd_var" show-value :min="-0.2" :inner-min="0.01" :inner-max="2.0" :max="2.2" :step="0.01">{{Kd_str}}</q-knob>
                <div class="column">
                  <div class="text-h6">Kd<sub>{{ idx }}</sub></div>
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
import { useStatusStore } from 'src/stores/status'
import MoveButton from 'src/components/MoveButton.vue'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, PIDMessage }from 'src/stores/stream'
import { wrapTo360, wrapTo90 } from 'src/utils/angles'

const $q = useQuasar()
const socket = useStreamStore()
const cfg = useConfigStore()
const dev = useDeviceStore()
const p = useStatusStore()
const var2str = (x:number) => x.toFixed(2)

const coord = ref<number>(0)
const axis = ref<number>(0)
const Kp_var = ref<number>(0)
const Ki_var = ref<number>(0)      
const Kd_var = ref<number>(0)      
const Ke_var = ref<number>(0)      
const Kc_var = ref<number>(0)      
const Kv_var = ref<number>(0)      
const Ka_var = ref<number>(0)      

type TestCaseOption = {
  label: string
  value: number
  case: 'goto' | 'slew' | 'pulse'
  icon: string
}

const axisOptionsData = [
  [ { label: 'M1', value: 0 }, { label: 'M2', value: 1 },   { label: 'M3', value: 2 } ],
  [ { label: 'Az', value: 0 }, { label: 'Alt', value: 1 },   { label: 'Roll', value: 2 } ],
  [ { label: 'RA ', value: 0 }, { label: 'Dec', value: 1 },   { label: 'PA ', value: 2 } ],
]
const axisOptions = computed(() => axisOptionsData[coord.value] ?? [])

const testcaseOptionsData:TestCaseOption[] = [
  { label: '30′ Goto', value: 5/60, case: 'goto', icon: 'mdi-move-resize-variant' },
  { label: '5° Goto', value: 5, case: 'goto', icon: 'mdi-move-resize-variant' },
  { label: '45° Goto', value: 45, case: 'goto', icon: 'mdi-move-resize-variant' },
  { label: '90° Goto', value: 90, case: 'goto', icon: 'mdi-move-resize-variant' },
  { label: '0.006°/s Slew', value: 1.0, case: 'slew', icon: 'mdi-arrow-right' },
  { label: '0.2°/s Slew', value: 5.01, case: 'slew', icon: 'mdi-arrow-right' },
  { label: '1.0°/s Slew', value: 5.87, case: 'slew', icon: 'mdi-arrow-right' },
  { label: '250ms Pulse', value: 0.25, case: 'pulse', icon: 'mdi-pulse' },
  { label: '2000ms Pulse', value: 2.0, case: 'pulse', icon: 'mdi-pulse' },
  { label: '4000ms Pulse', value: 4.0, case: 'pulse', icon: 'mdi-pulse' },
]
const testcase = ref<TestCaseOption | undefined>(testcaseOptionsData[1])

const motor = computed<string>(() => `M${axis.value+1}`)
const Kp_str = computed<string>(() => var2str(Kp_var.value))
const Ki_str = computed<string>(() => var2str(Ki_var.value))
const Kd_str = computed<string>(() => var2str(Kd_var.value))
const Ke_str = computed<string>(() => var2str(Ke_var.value))
const Kc_str = computed<string>(() => var2str(Kc_var.value))
const Kv_str = computed<string>(() => var2str(Kv_var.value))
const Ka_str = computed<string>(() => var2str(Ka_var.value))
const idx = computed<number>(() => axis.value + 1)

const chartPosData = computed<DataPoint[]>(() => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatPosData)
})

const chartVelData = computed<DataPoint[]>(() => {
   const pid = socket.topics?.pid ?? [] as TelemetryRecord[];
   return pid.map(formatVelData)
})

watch(testcase, async (newVal,oldVal) => {
  if (newVal?.case=='pulse' && oldVal?.case!='pulse')  await dev.alpacaTracking(true)
  if (newVal?.case!='pulse' && oldVal?.case=='pulse')  await dev.alpacaTracking(false)
}
)

watch([Kp_var, Ki_var, Kd_var, Ke_var, Kc_var], (newVal)=>{
  const payload = { pid_Kp: [...cfg.pid_Kp], pid_Ki: [...cfg.pid_Ki], pid_Kd:[...cfg.pid_Kd] }
  payload.pid_Kp[axis.value] = newVal[0]
  payload.pid_Ki[axis.value] = newVal[1]
  payload.pid_Kd[axis.value] = newVal[2]
  putdb(payload)
})

watch([Ke_var, Kc_var], (newVal)=>{
  const payload = {
    pid_Ke: newVal[0],
    pid_Kc: newVal[1]
  }
  putdb(payload)
})

watch([Kv_var, Ka_var], (newVal)=>{
  const payload = {
    pid_Kv: newVal[0],
    pid_Ka: newVal[1]
  }
  putdb(payload)
})

watch(axis, () => setKnobValues())

const onMinus = (payload: { isPressed: boolean }) => runTestCase(payload, -1)
const onPlus = (payload: { isPressed: boolean }) => runTestCase(payload, +1)

async function runTestCase(payload: { isPressed: boolean }, sign:number) {
    if (testcase.value?.case=='goto' && payload.isPressed) {
      await dev.alpacaResetSP()
      if (axis.value==0) {
        const az = wrapTo360(p.azimuth + sign * testcase.value?.value)
        const alt = p.altitude 
        await dev.alpacaSlewToAltAz(alt, az)
      } else if (axis.value==1) {
        const az = p.azimuth 
        const alt = wrapTo90(p.altitude + sign * testcase.value?.value)
        await dev.alpacaSlewToAltAz(alt, az)
      } else {
        const roll = p.roll + sign * testcase.value?.value
        await dev.alpacaMoveMechanical(roll)
      }

    } else if (testcase.value?.case=='slew') {
      await dev.alpacaResetSP()
      const isPressed = payload.isPressed
      await dev.alpacaMoveAxis(axis.value, isPressed ? sign*testcase.value?.value : 0)
    } else {
      console.log('pulse test case not implemented')
    }
}


function setKnobValues() {
  const idx = axis.value ?? 0

  Kp_var.value = cfg.pid_Kp[idx] ?? 0;
  Ki_var.value = cfg.pid_Ki[idx] ?? 0;
  Kd_var.value = cfg.pid_Kd[idx] ?? 0;
  Ke_var.value = cfg.pid_Ke ?? 0;
  Kc_var.value = cfg.pid_Kc ?? 0;
  Kv_var.value = cfg.pid_Kv ?? 0;
  Ka_var.value = cfg.pid_Ka ?? 0;
}


function formatPosData(d: TelemetryRecord): DataPoint {
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

  const PV = data[pvKey]?.[axis.value] ?? 0
  const SP = data[spKey]?.[axis.value] ?? 0

  return { x1: time, PV, SP }
}


function formatVelData(d: TelemetryRecord):DataPoint {
  const time = new Date(d.ts)
  const data = d.data as PIDMessage
  const OP = data.ω_op[axis.value] ?? 0
  const Kp = data.ω_kp[axis.value] ?? 0
  const Ki = data.ω_ki[axis.value] ?? 0
  const Kd = data.ω_kd[axis.value] ?? 0
  const FF = data.ω_ff[axis.value] ?? 0
  return { x1: time, Kp, Ki, Kd, FF, OP  }
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