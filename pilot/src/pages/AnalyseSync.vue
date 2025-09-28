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
# Multi-Point Alignment and Tripod Leveling
Alpaca multi-point alignment calibrates how your mount’s internal coordinate system maps to the horizon and celestrial sky. 
By syncing with three or more known positions, it builds a correction model that accounts for tripod tilt, polar misalignment, cone error, and other mechanical offsets that can affect pointing and tracking accuracy. 

You need to perform SYNCs to add known positions to the model. The more positions you use, the better the model can correct for these errors. 
You can choose from three different options to perform SYNCs, as described below.
</q-markdown>
            </div>
            <div class="col-md-6 q-pt-sm">
              <q-list style="max-width: 800px">
                <!-- Choose Motor -->
                <q-item>
                  <q-item-section side>
                    <q-item-label>Option A</q-item-label>
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>Align using automatic Plate Solve</q-item-label>
                    <q-item-label caption>Slew to an arbitary position and initiate a manual plate solve and sync using Nina or equivalent.</q-item-label>
                    <q-item-label caption>Repeat for at least three different positions across the sky. Fastest and easiest method.</q-item-label>  
                  </q-item-section>
                </q-item>
                <q-item>
                  <q-item-section side>
                    <q-item-label>Option B</q-item-label>
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>Align using known Stars or Targets</q-item-label>
                    <q-item-label caption>Slew to a known target and center it within the cameras frame.</q-item-label>
                    <q-item-label caption>Using Stellaruium or equivalent, select the target, then choose to sync co-ordinates.</q-item-label>  
                  </q-item-section>
                </q-item>
                <q-item>
                  <q-item-section side>
                    <q-item-label>Option C</q-item-label>
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>Align using Daytime Geographic Targets</q-item-label>
                    <q-item-label caption>Slew to a known distant position and center it within the cameras frame.</q-item-label>
                    <q-item-label caption>Manually enter the Azimuth and Altitude of the position and press SYNC below.</q-item-label>  
                  </q-item-section>
                </q-item>
              </q-list>
            </div>
          </div>
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
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import ChartXY from 'src/components/ChartXY.vue'
import { useStreamStore } from 'src/stores/stream'
import { useDeviceStore } from 'src/stores/device'
import type { DataPoint } from 'src/components/ChartXY.vue'
import type { TelemetryRecord, KalmanMessage, CalibrationMessage }from 'src/stores/stream'
// import { formatAngle } from 'src/utils/scale'
import { useStatusStore } from 'src/stores/status'

const socket = useStreamStore()
const dev = useDeviceStore()
const p = useStatusStore()

const selected = ref([])
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
  const testdata = cm.map(formatTestData).filter(d => d.axis == axis.value)
  const consolidated = new Map<string, TableRow>()
  for (const test of testdata) {
    consolidated.set(test.name, test)
  }
  return Array.from(consolidated.values())
})

watch(axis, ()=>selected.value=[])

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
  { name: 'raw', align: 'center' as AlignType, label: 'Raw Command', field: 'raw', sortable: true },
  { name: 'dps', label: 'Baseline (°/s)', field: 'dps', sortable: true },
  { name: 'testdps', label: 'Test Result (°/s)', field: 'test_result', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'testchange', label: 'Change', field: 'test_change', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'teststdev', label: 'Test Stdev', field: 'test_stdev', sortable: true, sort: (a:string, b:string) => parseInt(a, 10) - parseInt(b, 10) },
  { name: 'teststatus', label: 'Test Status', field: 'test_status', sortable: true },
  ]


const initialPagination = {
        rowsPerPage: 30
      }


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