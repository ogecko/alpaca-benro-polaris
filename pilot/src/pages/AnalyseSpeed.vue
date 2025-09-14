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
  # Motor Speed Calibration
  The lowest layer of the Alpaca Control System is an open loop motor speed controller. You give it a speed in degrees per second and it makes it happen.

  This page allows you to evaluate the calibration of the motor speed controller.
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
                      <q-btn icon="mdi-clock-start" @click="startTest">Test</q-btn>
                    </div>
                  </q-item-section>
                  <q-item-section >
                    <q-item-label> Start Speed Test of {{ motor }}</q-item-label>
                    <q-item-label caption>
                      Initiate a speed test that measures actual angular velocity for a range of inputs.
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
              <q-item-section>
                <q-item-label> Angular Position for {{ motor }}</q-item-label>
                <q-item-label caption>
                  Measured (green) and Filtered (yellow) angular position.
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
              <q-item-section>
                <q-item-label> Angular Velocity for {{ motor }}</q-item-label>
                <q-item-label caption>
                  Control reference (red), Measured (green) and Filtered (yellow) Angular Velocity. 
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <ChartXY  :data="chartVelData" x1Type="time"></ChartXY>
        </q-card>
      </div>    
      <div class="col-12 flex">
        <q-card flat bordered class="col">
          <div class="q-pa-md">
              <q-table title="Speed Calibration Test Results" dense
                    :selected-rows-label="getSelectedString" :pagination="initialPagination"
      selection="multiple"
      v-model:selected="selected"

                :rows="rows" :columns="columns" row-key="name">
              </q-table>
              Selected: {{ JSON.stringify(selected) }}
          </div>
        </q-card>
    </div>    
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useDeviceStore } from 'src/stores/device'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, KalmanMessage, CalibrationMessage }from 'src/stores/stream'
// import { formatAngle } from 'src/utils/scale'
import { sleep } from 'src/utils/sleep'

const socket = useStreamStore()
const dev = useDeviceStore()

const axis = ref<number>(0)
const motor = computed<string>(() => `M${axis.value+1}`)

const chartPosData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatPosData)
})
const chartVelData = computed<DataPoint[]>(() => {
   const kf = socket.topics?.kf ?? [] as TelemetryRecord[];
   return kf.map(formatVelData)
})
const rows = computed<TableRow[]>(() => {
   const cm = socket.topics?.cm ?? [] as TelemetryRecord[];
   return cm
    .map(formatTestData)
    .filter(d => d.axis == axis.value)
})

type TableRow = {
  name:string, axis:number, raw:number, ascom:number, dps:number, 
  test_result:string, test_change:string, test_stdev:string, test_status:string 
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

function formatTestData(d: TelemetryRecord):TableRow {
  const data = d.data as CalibrationMessage
  const name = data.name ?? ''
  const axis = data.axis ?? 0
  const raw = data.raw ?? 0
  const ascom = data.ascom ?? 0
  const dps = data.dps ?? 0
  const test_result = data.test_result ?? ''
  const test_change = data.test_change ?? ''
  const test_stdev = data.test_stdev ?? ''
  const test_status = data.test_status ?? ''
  return { name, axis, raw, ascom, dps, test_result, test_change, test_stdev, test_status }
}

onMounted(() => {
  socket.subscribe('cm')
  socket.subscribe('kf')
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('cm')
  socket.unsubscribe('kf')
})


async function startTest() {
  console.log('start test')
  await dev.apiAction('Polaris:SpeedTest', `{"axis":${axis.value},"rates":[3,4]}`)
  await sleep(5000)
 
}

type AlignType = 'left' | 'center' | 'right'

const columns = [
  {
    name: 'name',
    required: true,
    label: 'Test Case',
    align: 'left' as AlignType,
    field: (row: { name: string }) => row.name,
    format: (val: string) => `${val}`,
    sortable: true
  },
  { name: 'raw', align: 'center' as AlignType, label: 'Raw Rate', field: 'raw', sortable: true },
  { name: 'dps', label: 'Baseline (°/s)', field: 'dps', sortable: true },
  { name: 'testdps', label: 'Test Result (°/s)', field: 'test_result', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'testchange', label: 'Change', field: 'test_change', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'teststdev', label: 'Test Stdev', field: 'test_stdev', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'teststatus', label: 'Test Status', field: 'test_status', sortable: true },
  ]


const initialPagination = {
        rowsPerPage: 30
      }

const selected = ref([])

function getSelectedString () {
        return selected.value.length === 0 ? '' : `${selected.value.length} Test${selected.value.length > 1 ? 's' : ''} selected of ${rows.value.length}`
}

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