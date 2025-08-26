

<template>
  <q-page class="q-pa-sm">
    <div v-if="!dev.alpacaConnected" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <div v-else>
      <div class="row q-col-gutter-sm q-pb-sm">
        <div class="col">
          <!-- Page Heading -->
          <q-card flat bordered class="q-pa-md">
            <div class="text-h5">Alpaca Driver Settings</div>
            <div v-if="!cfg.fetchedAt" class="text-negative">
              <q-separator spaced />
              Configuration not loaded.
            </div>
              <div class="row q-col-gutter-lg items-center">
                <div class="col text-caption text-grey-6">
                  Changes in Alpaca Pilot Settings apply immediately. Click Save to keep them after restarting. 
                  Click Restore to reset all settings back to Config.toml defaults.
                </div>
                <div class="col-auto q-gutter-sm flex justify-end items-center">
                  <q-btn outline size="md" color="grey-5"  label="Save" 
                         @click="save" :disable="cfg.isSaving" :loading="cfg.isSaving" />
                  <q-btn outline color="grey-5"  label="Restore" 
                         @click="restore" :disable="cfg.isRestoring" :loading="cfg.isRestoring"/>
                </div>
              </div>
          </q-card>
        </div>
      </div>
      <div class="row q-col-gutter-sm items-stretch">
        <!-- Site Info -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Observing Site Information</div>
            <div class="row q-col-gutter-lg items-center">
              <div class="col text-caption text-grey-6  q-pb-md">
                Latitude and longitude are essential for accurate tracking. Other settings follow the ASCOM Alpaca standard and are optional.
              </div>
              <div class="col-auto q-gutter-sm flex justify-end items-center">
                <q-btn outline icon="my_location" color="grey-5" label="Locate"  @click="setFromLocationServices"/>
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
        <!-- Network -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Network Services</div>
            <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
                The Alpaca Driver provides several network services for external aplications to use the Benro Polaris. Changes to Network Services require saving to take effect. 
              </div>
            </div>
            <div class="row q-col-gutter-sm no-wrap">
                <q-toggle class='col-8' v-bind="bindField('enable_restapi', 'Alpaca REST API')"/>
                <q-input class="col-4" v-bind="bindField('alpaca_restapi_port', 'Port')"
                  type="number"  input-class="text-right" :style="{ visibility: cfg.enable_restapi ? 'visible' : 'hidden' }">
                  <template v-slot:prepend><q-icon name="nat"></q-icon></template>
                </q-input>
              </div>
                <q-banner v-if="!cfg.enable_restapi" inline-actions rounded class="bg-warning">
                    WARNING: The Alpaca REST API is required for Nina, Stellarium and Alpaca Pilot.
                </q-banner>
                <q-banner v-if="cfg.alpaca_restapi_port!=dev.alpacaPort" inline-actions rounded class="bg-warning">
                    WARNING: The Alpaca REST API port will change. Please reconnect Alpaca Pilot when prompted. 
                </q-banner>
            <div class="row q-col-gutter-sm no-wrap">
                <q-toggle class='col-8' v-bind="bindField('enable_discovery', 'Alpaca Discovery')"/>
                <q-input class="col-4" v-bind="bindField('alpaca_discovery_port', 'Port')"
                  type="number" input-class="text-right" :style="{ visibility: cfg.enable_discovery ? 'visible' : 'hidden' }">
                  <template v-slot:prepend><q-icon name="nat"></q-icon></template>
                </q-input>
            </div>
            <div class="row q-col-gutter-sm no-wrap">
                <q-toggle class='col-8' v-bind="bindField('enable_pilot', 'Alpaca Pilot')"/>
                <q-input class="col-4" v-bind="bindField('alpaca_pilot_port', 'Port')"
                  type="number" input-class="text-right" :style="{ visibility: cfg.enable_pilot ? 'visible' : 'hidden' }">
                  <template v-slot:prepend><q-icon name="nat"></q-icon></template>
                </q-input>
            </div>
            <div class="row q-col-gutter-sm no-wrap">
              <q-toggle class='col-8' v-bind="bindField('enable_synscan', 'SynSCAN API')"/>
              <q-input class="col-4" v-bind="bindField('stellarium_synscan_port', 'Port')"
                type="number" input-class="text-right" :style="{ visibility: cfg.enable_synscan ? 'visible' : 'hidden' }">
                <template v-slot:prepend><q-icon name="nat"></q-icon></template>
              </q-input>
            </div>
          </q-card>
        </div>
        <!-- Advanced Features -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
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
                <q-toggle class='col-6' v-bind="bindField('advanced_slewing', 'Slewing')"/>
                <q-toggle class='col-6' v-bind="bindField('advanced_goto', 'Advanced Goto')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('advanced_tracking', 'Tracking')"/>
                <q-toggle class='col-6' v-bind="bindField('advanced_guiding', 'Pulse Guiding')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('advanced_rotator', 'Alpaca Rotator')"/>
              </div>
              <div class="row q-pt-md q-pl-md q-col-gutter-lg">
                  <q-input class='col-4' v-bind="bindField('max_slew_rate', 'Max Slew Rate', '°/s')" type="number" input-class="text-right"/>
                  <q-input class='col-4' v-bind="bindField('max_accel_rate', 'Max Accel Rate', '°/s²')" type="number" input-class="text-right"/>
              </div>
            </div>
          </q-card>
        </div>
        <!-- Standard Control Features -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
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
        <!-- Protocol Logging -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Protocol Log Settings</div>
            <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
                Select which messages to log, such as those from Alpaca clients (NINA, CCDciel, Pilot), 
                SynScan apps (Stellarium), and the messages sent to the Benro Polaris.              
              </div>
            </div>
            <div class="row q-mb-md">
              <q-select
                class="col-12 q-pb-md"
                filled
                v-bind="bindField('log_level', 'Log Detail and Verbosity Level')"
                :options="[
                  { label: 'DEBUG – Detailed diagnostic logs', value: 'DEBUG' },
                  { label: 'INFO – Default routine logging information', value: 'INFO' },
                  { label: 'WARNING – Only log unexpected issues and above', value: 'WARNING' },
                  { label: 'ERROR – Only log serious functional problems', value: 'ERROR' },
                  { label: 'CRITICAL – Only log fatal system errors', value: 'CRITICAL' }
                ]"
                emit-value
                map-options
              />
            </div>
            <div class="q-gutter-y-sm">
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_alpaca_protocol', 'Log Alpaca Protocol')"/>
                <q-toggle class='col-6' v-bind="bindField('log_alpaca_polling', 'Log Alpaca Polling')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_alpaca_discovery', 'Log Alpaca Discovery')"/>
                <q-toggle class='col-6' v-bind="bindField('log_alpaca_actions', 'Log Action Invokation')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_rotator_protocol', 'Log Rotator Protocol')"/>
                <q-toggle class='col-6' v-bind="bindField('log_pulse_guiding', 'Log Pulse Guiding')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_synscan_protocol', 'Log SynSCAN Protocol')"/>
                <q-toggle class='col-6' v-bind="bindField('log_synscan_polling', 'Log SynSCAN Polling')"/>
              </div>
              <div class="row">
                <q-toggle class='col-6' v-bind="bindField('log_polaris_protocol', 'Log Benro Polaris Protocol')"/>
                <q-toggle class='col-6' v-bind="bindField('log_polaris_polling', 'Log Benro Polaris Polling')"/>
              </div>
            </div>
          </q-card>
        </div>
        <!-- Performance Logging -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
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
import { useQuasar } from 'quasar'
import { onMounted, onUnmounted, ref } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { debounce } from 'quasar'
import { PollingManager } from 'src/utils/polling';
import LocationPicker from 'components/LocationPicker.vue';
import { getLocationServices } from 'src/utils/locationServices';
import type { LocationResult } from 'src/utils/locationServices';

const $q = useQuasar()
const dev = useDeviceStore()
const cfg = useConfigStore()

const poll = new PollingManager()

onMounted(async () => {
  const shouldFetch =
    dev.alpacaConnected &&
    dev.alpacaConnectedAt &&
    cfg.fetchedAt < dev.alpacaConnectedAt

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
    position: 'top', timeout: 3000, actions: [{ icon: 'close', color: 'white' }] })
}

async function restore() {
  const ok = await cfg.configRestore()
  $q.notify({ message:`Configuration restore ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'close', color: 'white' }] })
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