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
   
        <div class="col-md-6 ">
            <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Telescope Alignment Model</div>
            <div class="row">
                <div class="col-12 text-caption text-grey-6 q-pb-md">
                Add more SYNCs to improve the model. Remove any that show large residuals or are no longer valid. 
                </div>
            </div>
          <q-list bordered separator dense >
            <q-item v-for="data in telescope_syncs" :key="data.timestamp">
                <q-item-section>
                    <q-item-label >SYNC @ 10:20</q-item-label>
                </q-item-section>
                <q-item-section>
                    <q-item-label caption>Az {{data.a_az}} Alt {{data.a_alt}} </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <q-item-label caption>Residual {{data.resmag}}</q-item-label>
                    <q-item-label></q-item-label>
                </q-item-section>
                <q-item-section side>
                    <q-btn dense size="sm" round icon="mdi-close" />
                </q-item-section>
            </q-item>
            </q-list>
            <div class="text-h7 q-pt-md">Correction Summary</div>
            <div class="row">
                <div class="col-12 text-caption text-grey-6">
                The telescope alignment model is correcting for the following adjustments.
                </div>
            </div>
            <div class="row text-center">
                <div class="col-4">
                    <div class="text-h4">12°</div>
                    <div class="text-caption">Az Correction</div>
                </div>
                <div class="col-4">
                    <div class="text-h4">12°</div>
                    <div class="text-caption">Tilt Correction</div>
                </div>
                <div class="col-4">
                    <div class="text-h4">12°</div>
                    <div class="text-caption">Highest Tilt</div>
                </div>

            </div>
            </q-card>
        </div>

        <div class="col-md-6 ">
            <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Rotator Alignment Model</div>
            <div class="row">
                <div class="col-12 text-caption text-grey-6 q-pb-md">
                Corrects rotational misalignment between the camera and mount optical axis.
                </div>
            </div>
          <q-list bordered separator dense >
            <q-item v-for="data in rotator_syncs" :key="data.timestamp">
                <q-item-section>
                    <q-item-label >SYNC @ 10:20</q-item-label>
                </q-item-section>
                <q-item-section>
                    <q-item-label caption>Roll {{data.a_roll}} </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <q-item-label caption>Residual {{data.resmag}}</q-item-label>
                    <q-item-label></q-item-label>
                </q-item-section>
                <q-item-section side>
                    <q-btn dense size="sm" round icon="mdi-close" />
                </q-item-section>
            </q-item>
            </q-list>
            <div class="text-h7 q-pt-md">Correction Summary</div>
            <div class="row">
                <div class="col-12 text-caption text-grey-6">
                The rotator alignment model is correcting for the following adjustment.
                </div>
            </div>
            <div class="row text-center">
                <div class="col-4">
                    <div class="text-h4">12°</div>
                    <div class="text-caption">Roll Correction</div>
                </div>

            </div>
            </q-card>
        </div>



  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { useStreamStore } from 'src/stores/stream'
import type { TelemetryRecord, SyncMessage }from 'src/stores/stream'
import { formatAngle } from 'src/utils/scale'
import { useStatusStore } from 'src/stores/status'

const socket = useStreamStore()
const p = useStatusStore()

const selected = ref([])
const axis = ref<number>(0)

const telescope_syncs = computed(() => {
  const sm = socket.topics?.sm ?? [] as TelemetryRecord[];
  const syncdata = sm.map(formatSyncData).filter(d=>d.a_az !== null && d.a_alt !== null)
  const consolidated = new Map<string, TableRow>()
  for (const data of syncdata) {
    consolidated.set(data.timestamp, data)
  }
  return Array.from(consolidated.values())
})

const rotator_syncs = computed(() => {
  const sm = socket.topics?.sm ?? [] as TelemetryRecord[];
  const syncdata = sm.map(formatSyncData).filter(d=>d.a_roll !== null)
  const consolidated = new Map<string, TableRow>()
  for (const data of syncdata) {
    consolidated.set(data.timestamp, data)
  }
  return Array.from(consolidated.values())
})


watch(axis, ()=>selected.value=[])

type TableRow = {
  timestamp:string, a_az:string, a_alt:string, a_roll:string, resmag:string, resvec:[number, number] 
}


function formatSyncData(d: TelemetryRecord):TableRow {
  const data = d.data as SyncMessage
  const timestamp = data.timestamp ?? 0
  const a_az = formatAngle(data.a_az ?? 0, 'deg', 1)
  const a_alt = formatAngle(data.a_alt ?? 0, 'deg', 1)
  const a_roll = formatAngle(data.a_roll ?? 0, 'deg', 1)
  const resmag = formatAngle(data.residual_magnitude ?? 0, 'deg', 1)
  const resvec = data.residual_vector ?? [0,0]
  return { timestamp, a_az, a_alt, a_roll, resmag, resvec }
}

onMounted(() => {
  socket.subscribe('sm')
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('sm')
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