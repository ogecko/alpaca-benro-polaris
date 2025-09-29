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
      <!-- Multi-Point Alignment Intro -->
      <div class="col-12 flex">
        <q-card flat bordered class="col q-pa-md">
          <div class="row">
            <!-- KF intro -->
            <div class="col-md-12">
<q-markdown  :no-mark="false">
# Multi-Point Alignment 
Alpaca multi-point alignment calibrates how your mount’s internal coordinate system maps to the horizon and celestrial sky. By syncing with three or more known positions, it builds a correction model that accounts for tripod tilt, polar misalignment, cone error, and other mechanical offsets that can affect pointing and tracking accuracy. 
</q-markdown>
            </div>
          </div>
        </q-card>
      </div>
   
      <!-- Telescope Alignment Row -->
      <div class="col-12 col-md-6 col-lg-4 flex">
        <q-card flat bordered class="q-pa-md full-width">
          <div class="text-h6">Telescope Alignment Model</div>
          <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
              Add more SYNCs to improve the model. Remove any that show large residuals or are no longer valid. 
              </div>
          </div>
          <!-- Telescope Sync Summary Row -->
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
          <!-- Telescope Correction Summary Row -->
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
                <div class="text-caption">Highest Tilt Az</div>
            </div>

          </div>
        </q-card>
      </div>

      <!-- Rotator Alignment Row -->
      <div class="col-12 col-md-6 col-lg-4 flex">
        <q-card flat bordered class="q-pa-md full-width">
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
                  <div class="text-h4">{{p.battery_level}}°</div>
                  <div class="text-caption">Roll Correction</div>
              </div>

          </div>
          </q-card>
      </div>

      <!-- Telescope Alignment Row -->
      <div class="col-12 col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md full-width">
          <div class="text-h6">Methods to add SYNC Points</div>
          <div class="row">
              <div class="col-12  text-grey-6 q-pb-md">

              </div>
          </div>
          <q-tabs v-model="tab" dense class="text-grey" 
              active-color="primary" indicator-color="primary"
              align="justify" narrow-indicator
          >
              <q-tab name="plate" label="Plate Solve" />
              <q-tab name="star" label="Celestrial" />
              <q-tab name="map" label="Geographic" />
          </q-tabs>
     <q-tab-panels v-model="tab" animated >
        <q-tab-panel name="plate" class="text-grey-8">
          <div class="text-grey text-caption">
            The quickest way to perform a SYNC is by using plate solving to determine the telescope’s true sky orientation.
            You will need to use an external application to plate solve.
          </div>
          <ol class="text-grey text-caption">
            <li>Enable Sidereal Tracking to follow the stars.</li>
            <li>Goto an arbitrary location in the sky.</li>
            <li>Using Nina, run a manual plate solve and sync.</li>
            <li>Repeat for three or more positions spread across the sky.</li>
          </ol>
        </q-tab-panel>

        <q-tab-panel name="star">
          <div class="text-grey text-caption">
            You can manually align to a known star or celestrial target. 
            This is typically done using a planetarium application such as Stellarium. 
          </div>
          <ol class="text-grey text-caption">
            <li>Enable Sidereal Tracking to follow the stars.</li>
            <li>Goto any known celestrial target in the sky.</li>
            <li>Slew to center the target within the camera's frame.</li>
            <li>Using Stellarium, select the known target.</li>
            <li>Press Ctrl+0, Current Object, and Sync.</li>
            <li>Repeat for three or more targets spread across the sky.</li>
          </ol>
          <div class="text-grey text-caption">
            Alternately enter the current RA/Dec/PA below and SYNC. 
          </div>
          <div class="row q-col-gutter-sm text-center items-center">
            <div class="col-4">
              <q-input   label="RA (hh:mm:ss)" v-model="RA_str"/>
            </div>
            <div class="col-4">
              <q-input   label="Dec (deg:mm:ss)" v-model="Dec_str"/>
            </div>
            <div class="col-4">
              <q-btn label="SYNC" icon="mdi-telescope" />
            </div>
          </div>
          <div class="row q-col-gutter-sm q-pt-md text-center items-center">
            <div class="col">
              <q-input   label="Position Angle (deg:mm:ss)" v-model="PA_str"/>
            </div>
            <div class="col-4">
              <q-btn label="SYNC" icon="mdi-restore"  />
            </div>
          </div>
        </q-tab-panel>

        <q-tab-panel name="map">
          <div class="text-grey text-caption">
            During daylight hours, center a known landmark within the camera's frame. Tap the landmap on the map below to set coordinates.
          </div>
          <div class="q-pt-md q-pb-md">
            <LocationPicker arrow :lat="cfg.site_latitude" :lon="cfg.site_longitude" @locationInfo="setFromMapClick"/>
          </div>
          <div class="text-grey text-caption">
            Adjust the current Az/Alt/Roll below and SYNC. 
          </div>
          <div class="row q-col-gutter-sm text-center items-center">
            <div class="col-4">
              <q-input   label="Azimuth (deg:mm:ss)" v-model="Az_Str"/>
            </div>
            <div class="col-4">
              <q-input   label="Altitude (deg:mm:ss)" v-model="Alt_str"/>
            </div>
            <div class="col-4">
              <q-btn label="SYNC" icon="mdi-telescope" />
            </div>
          </div>
          <div class="row q-col-gutter-sm q-pt-md text-center items-center">
            <div class="col">
              <q-input   label="Roll Angle (deg:mm:ss)" v-model="Roll_str"/>
            </div>
            <div class="col-4">
              <q-btn label="SYNC" icon="mdi-restore"  />
            </div>
          </div>
        </q-tab-panel>
      </q-tab-panels>

          </q-card>
      </div>

  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { useStreamStore } from 'src/stores/stream'
import { useConfigStore } from 'src/stores/config'
import type { TelemetryRecord, SyncMessage }from 'src/stores/stream'
import { formatAngle } from 'src/utils/scale'
import { useStatusStore } from 'src/stores/status'
import type { LocationResult } from 'src/utils/locationServices';
import LocationPicker from 'src/components/LocationPicker.vue';

const socket = useStreamStore()
const p = useStatusStore()
const cfg = useConfigStore()

const selected = ref([])
const axis = ref<number>(0)
const tab = ref('plate')
const RA_str = ref('00:00:00')
const Dec_str = ref('000:00:00')
const PA_str = ref('000:00:00')
const Az_Str = ref('180:00:00')
const Alt_str = ref('045:00:00')
const Roll_str = ref('000:00:00')

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

onMounted(async () => {
  socket.subscribe('sm')
  await cfg.configFetch()
})

onUnmounted(() => {
  // if (timer) clearInterval(timer)
  socket.unsubscribe('sm')
})

function setFromMapClick (result: LocationResult) {
  console.log('Map Click', result)
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