

<template>
  <q-page class="q-pa-sm">

    <StatusBanners />

    <div>
      <!-- Header Row -->
      <div class="row q-pb-sm q-col-gutter-md items-center">
        <div class="col text-h6 q-ml-md">
          Alpaca Driver Settings
          <div v-if="$q.screen.gt.xs" class="text-caption text-grey-6">
          Settings take effect instantly. Click Save to persist after restart, or Restore to revert to Config.toml defaults.
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
        <!-- Site Info -->
        <div class="col-12 col-md-6 col-lg-4 flex" >
          <q-card flat bordered class="q-pa-md full-width">
            <div class="text-h6">Observing Site Information</div>
            <div class="row q-col-gutter-lg items-center">
              <div class="col text-caption text-grey-6 q-pb-md">
                Latitude and longitude are essential for accurate tracking. Other settings follow the ASCOM Alpaca standard and are optional.
              </div>
              <div class="col-auto q-gutter-sm flex justify-end items-center">
                <q-btn outline icon="mdi-crosshairs-gps" color="grey-5" label="Locate"  @click="setFromLocationServices"/>
              </div>
            </div>
            <div class="q-pt-md q-pb-md">
              <LocationPicker :lat="cfg.site_latitude" :lon="cfg.site_longitude" @locationInfo="setFromMapClick"/>
            </div>

            <div class="row q-col-gutter-lg q-pb-md">
                <q-input class="col-3" v-bind="bindField('site_latitude', 'Latitude', '°')" type="number" input-class="text-right"/>
                <q-input class="col-3" v-bind="bindField('site_longitude','Longitude', '°')" type="number" input-class="text-right"/>
                <q-input class="col-6" v-bind="bindField('location','Location')" />
            </div>
            <div class="row q-col-gutter-lg">
                <q-input class="col-3" v-bind="bindField('site_elevation', 'Elevation', 'm')" type="number" input-class="text-right"/>
                <q-input class="col-3" v-bind="bindField('site_pressure', 'Pressure', 'hPa')" type="number" input-class="text-right"/>
                <q-input class="col-3" v-bind="bindField('focal_length', 'Focal Length', 'mm')" type="number" input-class="text-right"/>
                <q-input class="col-3" v-bind="bindField('focal_ratio', 'Focal Ratio', 'f-stop')" type="number" input-class="text-right"/>
            </div>
          </q-card>
        </div>
        <!-- Advanced Features -->
        <div class="col-12 col-md-6 col-lg-4 flex" >
          <q-card flat bordered class="q-pa-md full-width">
            <div class="text-h6">Advanced Control Features</div>
            <div class="row q-col-gutter-lg items-center">
              <div class="col text-caption text-grey-6  q-pb-md">
                Use Advanced Position Control to override the Benro Polaris default behaviour. 
                Toggle individual features below to enable advanced slewing, goto, tracking, guiding and rotator support.
              </div>
              <div class="col-auto q-gutter-sm flex justify-end">
                <q-toggle class='col' v-bind="bindField('advanced_control', 'Enable')"/>
              </div>
            </div>
            <div v-if="cfg.advanced_control" class="q-gutter-y-sm" >
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('advanced_kf', 'Kalman Filtering')"/>
                <q-toggle class='col-6' v-bind="bindField('advanced_rotator', 'Alpaca Rotator')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('advanced_slewing', 'Slewing')"/>
                <q-toggle class='col-6' v-bind="bindField('advanced_goto', 'Advanced Goto')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('advanced_tracking', 'Tracking')"/>
                <q-toggle class='col-6' v-bind="bindField('advanced_guiding', 'Pulse Guiding')"/>
              </div>
              <div class="text-caption text-grey-6 q-pt-md">Restrict the motor controller’s peak slew rate and how quickly it will accelerate.</div>
              <div class="row">
                  <q-toggle class='col-6' v-model="isRestricted">Restrict Slew and Acceleration Rates</q-toggle>
              </div>
              <div v-if="isRestricted" class="row q-pl-md q-gutter-xl">
                  <q-input class='col-4' v-bind="bindField('max_slew_rate', 'Max Slew Rate', '°/s')" 
                           type="number" :rules="max_rate_rules" input-class="text-right"/>
                  <q-input class='col-4' v-bind="bindField('max_accel_rate', 'Max Acceleration Rate', '°/s²')" 
                           type="number" :rules="max_rate_rules" input-class="text-right"/>
              </div>
            </div>
          </q-card>
        </div>
        <!-- Standard Control Features -->
        <div class="col-12 col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md full-width">
            <div class="text-h6">Standard Control Features</div>
            <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
                Aiming Adjustment improves the standard Benro Polaris Goto performance, by correcting any aiming bias, and by forward calculating co-ordinates into the future.
              </div>
            </div>
            <div class="q-gutter-y-sm" >
              <div class="row">
                <q-toggle v-bind="bindField('sync_N_point_alignment', 'Sync through to Benro Polaris (Multi Point Alignment)')"/>
              </div>
              <div class="row">
                <q-toggle v-bind="bindField('aiming_adjustment_enabled', 'Enable Aiming Adjustment')"/>
              </div>
              <div class="row q-pt-md q-pl-md q-col-gutter-lg">
                <q-input v-if="cfg.aiming_adjustment_enabled" class='col-4' v-bind="bindField('aim_max_error_correction', 'Max Bias Correction', '°')" type="number" input-class="text-right"/>
                <q-input v-if="cfg.aiming_adjustment_enabled" class='col-4' v-bind="bindField('aiming_adjustment_time', 'Future offset Time', 's')" type="number" input-class="text-right"/>
                <q-input class='col-4' v-bind="bindField('tracking_settle_time', 'Tracking Settle Time', 's')" type="number" input-class="text-right"/>
              </div>
            </div>
          </q-card>
        </div>
        <!-- Performance Logging -->
        <div class="col-12 col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md full-width">
            <div class="text-h6">Performance Recording Settings</div>
            <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
                Enable recording of data to help analyse various performance characteristics of your Benro Polaris, including aiming, tracking, and control performance.
              </div>
            </div>
            <div class="q-gutter-y-sm">
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_telemetry_data', 'Log Telementry')"/>
                <q-toggle class='col-6' v-bind="bindField('log_aiming_data', 'Log Aiming Accuracy')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_drift_data', 'Log Drift Error')"/>
                <q-toggle class='col-6' v-bind="bindField('log_periodic_data', 'Log Periodic Error')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_kalman_data', 'Log Kalman Filtering')"/>
                <q-toggle class='col-6' v-bind="bindField('log_pid_data', 'Log PID Control')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_sync_data', 'Log Sync Performance')"/>
              </div>
              
            </div>
          </q-card>
        </div>
      </div>
    </div>
</q-page>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { useQuasar, debounce } from 'quasar'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useConfigStore } from 'src/stores/config';
import { useDeviceStore } from 'src/stores/device';
import { PollingManager } from 'src/utils/polling';
import { getLocationServices } from 'src/utils/locationServices';

import type { LocationResult } from 'src/utils/locationServices';
import LocationPicker from 'src/components/LocationPicker.vue';
import StatusBanners from 'src/components/StatusBanners.vue'

const $q = useQuasar()
const dev = useDeviceStore()
const cfg = useConfigStore()
const poll = new PollingManager()
const max_rate_rules = [ 
  (x:number) => x>0.0 || 'Rate must be greater than zero',
  (x:number) => x<9.0 || 'Rate must be less than 9.0'
]

const isRestricted = ref<boolean>(cfg.max_slew_rate!=0)
watch(isRestricted, async (isRestrictedNewValueTrue) => {
  const cfgChanges = (isRestrictedNewValueTrue) ? {max_slew_rate: 8.5, max_accel_rate: 3 } : {max_slew_rate: 0, max_accel_rate: 0 }
  await cfg.configUpdate(cfgChanges)
})

watch(() => cfg.max_slew_rate, (newRate) => {
  isRestricted.value = (newRate == 0) ? false : true 
})

onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) {
    await cfg.configFetch()
  }
  poll.startPolling(() => { void cfg.configFetch() }, 10, 'configFetch')
})

onUnmounted(() => {
  poll.stopPolling()
})

function bindField(key: string, label: string, suffix?: string) {
  /**
   * Creates a v-model binding object for a given config key.
   * Supports string, number, and boolean values. Updates cfg and persists changes via api.
   * Also applies a 'taflash' class if the key is flagged for animation.
   *
   * @param key - The config key to bind
   * @param label - The label of the field
   * @param suffix - Optional suffix to display in the input
   * @returns A binding object compatible with Quasar input components
   */
  // @ts-expect-error: dynamic key access on cfg
  const val = cfg[key]
  const type = typeof val
  const isValid = ['string', 'number', 'boolean'].includes(type)
  const isBoolean = type === 'boolean'
  return {
    label,
    ...(suffix ? { suffix } : {}),
    class: { taflash: taKeys.value.has(key) },
    modelValue: isValid ? val : '',
    'onUpdate:modelValue': (v: string | number | boolean | null) => {
      if (v !== null && isValid) {
        // @ts-expect-error: dynamic key assignment
        cfg[key] = v
        const payload = { [key]: v }
        if (isBoolean) { put(payload) } else { putdb(payload) }
      }
    }
  }
}



const taKeys = ref(new Set<string>()) // set of keys to animate
function triggerAnimation(keys: string[]) {
  keys.forEach(key => taKeys.value.add(key))
  setTimeout(() => {
    keys.forEach(key => taKeys.value.delete(key))
  }, 600)
}

async function setFromLocationServices() {
  const result = await getLocationServices()
  if (result.success) {
    put(result.data)
    triggerAnimation(Object.keys(result.data))
  }
}

function setFromMapClick(result: LocationResult) {
  if (result.success) {
    put(result.data)
    triggerAnimation(Object.keys(result.data))
  }
}

async function save() {
  const ok = await cfg.configSave()
  $q.notify({ message:`Configuration save ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }] })
}

async function restore() {
  const ok = await cfg.configRestore()
  $q.notify({ message:`Configuration restore ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }] })
}

// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store 
const putdb = debounce((payload) => cfg.configUpdate(payload), 500) // slow put for input text
const put = debounce((payload) => cfg.configUpdate(payload), 5)     // fast put for toggles


</script>

<style lang="scss">
.taflash {
  animation: flash 0.6s;
}

.short {
  width: 100px;
}



// No Spinner - Chrome, Safari, Edge
input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

// No Spinner - Firefox 
input[type=number] {
  -moz-appearance: textfield;
}


// debug flexgrid .row, .col, .q-card
// .col, .q-card {
//   border: 1px dashed red;
// }

</style>