

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
            <div class="text-h5">Alpaca Driver Configuration</div>
            <div v-if="!cfg.fetchedAt" class="text-negative">
              <q-separator spaced />
              Configuration not loaded.
            </div>
              <div class="row q-col-gutter-lg items-center">
                <div class="col text-caption text-grey-6">
                  Changes in Alpaca Pilot apply immediately. Click Save to keep them after restarting. 
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
        <!-- Advanced Features -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Advanced Control Features</div>
            <div class="row q-col-gutter-lg items-center">
              <div class="col text-caption text-grey-6  q-pb-md">
                Use Advanced Position Control to override the Benro Polaris default behaviour. 
                Toggle individual features below to enable advanced slewing, goto, tracking, guiding and rotator support.
              </div>
              <div class="col-auto q-gutter-sm flex justify-end items-center">
                <q-toggle class='col' v-model="cfg.advanced_control" label="Enable" @update:model-value="put({advanced_control: cfg.advanced_control})" />
              </div>
            </div>
            <div v-if="cfg.advanced_control" >
              <div class="row">
                <q-toggle class='col-6' v-model="cfg.advanced_slewing" label="Slewing" @update:model-value="put({advanced_slewing: cfg.advanced_slewing})" />
                <q-toggle class='col-6' v-model="cfg.advanced_goto" label="Advanced Goto" @update:model-value="put({advanced_goto: cfg.advanced_goto})" />
              </div>
              <div class="row">
                <q-toggle class='col-6' v-model="cfg.advanced_tracking" label="Tracking" @update:model-value="put({advanced_tracking: cfg.advanced_tracking})" />
                <q-toggle class='col-6' v-model="cfg.advanced_guiding" label="Pulse Guiding" @update:model-value="put({advanced_guiding: cfg.advanced_guiding})" />
              </div>
              <div class="row">
                <q-toggle class='col-6' v-model="cfg.advanced_rotator" label="Alpaca Rotator" @update:model-value="put({advanced_rotator: cfg.advanced_rotator})" />
              </div>
              <div class="row q-col-gutter-lg">
                  <q-input class='col-3' type="number" label="Max Slew Rate" suffix="°/s" input-class="text-right"
                    v-model.number="cfg.max_slew_rate" @update:model-value="putdb({max_slew_rate: cfg.max_slew_rate})" />
                  <q-input class='col-3' type="number" label="Max Accel Rate" suffix="°/s²" input-class="text-right"
                    v-model.number="cfg.max_accel_rate" @update:model-value="putdb({max_accel_rate: cfg.max_accel_rate})" />
                  <q-input class='col-3' type="number" label="Settle Time" suffix="s" input-class="text-right"
                    v-model.number="cfg.tracking_settle_time"  @update:model-value="putdb({tracking_settle_time: cfg.tracking_settle_time})" />
              </div>
            </div>
          </q-card>
        </div>
        <!-- Aiming Adjustment -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Aiming Adjustment</div>
            <q-toggle v-model="cfg.aiming_adjustment_enabled" label="Enable Adjustment" @update:model-value="put({aiming_adjustment_enabled: cfg.aiming_adjustment_enabled})" />
            <div class="row q-pl-md q-gutter-lg">
              <q-input class='col-3' type="number" v-model.number="cfg.aiming_adjustment_time" label="Adjustment Time" @update:model-value="putdb({aiming_adjustment_time: cfg.aiming_adjustment_time})" />
              <q-input class='col-3' type="number" v-model.number="cfg.aiming_adjustment_az" label="Adjustment Az" @update:model-value="putdb({aiming_adjustment_az: cfg.aiming_adjustment_az})" />
              <q-input class='col-3' type="number" v-model.number="cfg.aiming_adjustment_alt" label="Adjustment Alt" @update:model-value="putdb({aiming_adjustment_alt: cfg.aiming_adjustment_alt})" />
              <q-input class='col-3' type="number" v-model.number="cfg.aim_max_error_correction" label="Max Error Correction" @update:model-value="putdb({aim_max_error_correction: cfg.aim_max_error_correction})" />
            </div>
            <!--  Sync -->
            <div class="text-h6 q-mt-lg">Sync</div>
            <q-input type="number" v-model.number="cfg.sync_pointing_model" label="Pointing Model" @update:model-value="putdb({sync_pointing_model: cfg.sync_pointing_model})" />
            <q-toggle v-model="cfg.sync_N_point_alignment" label="N-Point Alignment" @update:model-value="put({sync_N_point_alignment: cfg.sync_N_point_alignment})" />
          </q-card>
        </div>
        <!-- Logging -->
        <div class="col-md-6 col-lg-4 flex">
          <q-card flat bordered class="q-pa-md">
            <div class="text-h6">Logging</div>
            <q-toggle v-model="cfg.log_to_file" label="Log to File" @update:model-value="put({log_to_file: cfg.log_to_file})" />
            <q-toggle v-model="cfg.log_to_stdout" label="Log to Stdout" @update:model-value="put({log_to_stdout: cfg.log_to_stdout})" />
            <q-toggle v-model="cfg.log_polaris" label="Log Polaris" @update:model-value="put({log_polaris: cfg.log_polaris})" />
            <q-toggle v-model="cfg.log_polaris_protocol" label="Log Polaris Protocol" @update:model-value="put({log_polaris_protocol: cfg.log_polaris_protocol})" />
            <q-toggle v-model="cfg.log_stellarium_protocol" label="Log Stellarium Protocol" @update:model-value="put({log_stellarium_protocol: cfg.log_stellarium_protocol})" />
            <q-input v-model.number="cfg.log_level" label="Log Level" @update:model-value="putdb({log_level: cfg.log_level})" />
            <q-input type="number" v-model.number="cfg.log_performance_data" label="Performance Data" @update:model-value="putdb({log_performance_data: cfg.log_performance_data})" />
            <q-input type="number" v-model.number="cfg.log_performance_data_test" label="Perf Data Test" @update:model-value="putdb({log_performance_data_test: cfg.log_performance_data_test})" />
            <q-input type="number" v-model.number="cfg.log_perf_speed_interval" label="Perf Speed Interval" @update:model-value="putdb({log_perf_speed_interval: cfg.log_perf_speed_interval})" />
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