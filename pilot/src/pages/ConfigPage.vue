

<template>
  <q-page class="q-pa-md">
    <div v-if="!dev.alpacaConnected" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>

    <q-card flat bordered class="q-pa-md">
      <div class="text-h5">Alpaca Driver Configuration</div>
      <div v-if="!cfg.fetchedAt" class="text-negative">
        <q-separator spaced />
        Configuration not loaded.
      </div>
      <div v-else>
        <div class="row q-pb-md">
          <div class="col-8 text-caption text-grey-6">
            Changes in Alpaca Pilot apply immediately. Click Save to keep them after restarting. 
            Network Services require saving to take effect. Click Restore to reset all settings back to Config.toml defaults.
          </div>
          <div class="col self-center q-pl-lg q-gutter-md">
            <q-btn outline size="md" color="grey-5"  label="Save" @click="dev.apiAction('RestartDriver')" />
            <q-btn outline color="grey-5"  label="Restore" to="/connect" />
          </div>
        </div>
        <!-- Network -->
        <q-separator spaced />
        <div class="text-h6 q-mt-md">Network Services</div>
        <div class="row">
          <div class="col text-caption text-grey-6">
            The Alpaca Driver provides several network services for external aplications to use the Benro Polaris. 
          </div>
        </div>
        <div class="row no-wrap q-gutter-sm">
            <q-toggle class='col-8' v-model="cfg.enable_restapi" label="Alpaca REST API"  @update:model-value="put({enable_restapi: cfg.enable_restapi})"/>
            <q-input class="short" v-if="cfg.enable_restapi" dense label="Port" type="number"  
              v-model="cfg.alpaca_restapi_port" @update:model-value="putdb({alpaca_restapi_port: cfg.alpaca_restapi_port})">
              <template v-slot:prepend><q-icon name="nat"></q-icon></template>
            </q-input>
          </div>
            <q-banner v-if="!cfg.enable_restapi" inline-actions rounded class="bg-warning">
                WARNING: The Alpaca REST API is required for Nina, Stellarium and Alpaca Pilot.
            </q-banner>
            <q-banner v-if="cfg.alpaca_restapi_port!=dev.alpacaPort" inline-actions rounded class="bg-warning">
                WARNING: The Alpaca REST API port will change. Please reconnect Alpaca Pilot when prompted. 
            </q-banner>
        <div class="row no-wrap q-gutter-sm">
            <q-toggle class='col-8' v-model="cfg.enable_discovery" label="Alpaca Discovery"  @update:model-value="put({enable_discovery: cfg.enable_discovery})" />
            <q-input v-if="cfg.enable_discovery" label="Port" dense class="short" type="number"
              v-model="cfg.alpaca_discovery_port" @update:model-value="putdb({alpaca_discovery_port: cfg.alpaca_discovery_port})">
              <template v-slot:prepend><q-icon name="nat"></q-icon></template>
            </q-input>
        </div>
        <div class="row no-wrap  q-gutter-sm">
            <q-toggle class='col-8' v-model="cfg.enable_pilot" label="Alpaca Pilot"  @update:model-value="put({enable_pilot: cfg.enable_pilot})" />
            <q-input v-if="cfg.enable_pilot" label="Port" dense class="short" type="number"
              v-model="cfg.alpaca_pilot_port" @update:model-value="putdb({alpaca_pilot_port: cfg.alpaca_pilot_port})">
              <template v-slot:prepend><q-icon name="nat"></q-icon></template>
            </q-input>
        </div>
        <div class="row no-wrap  q-gutter-sm">
           <q-toggle class='col-8' v-model="cfg.enable_synscan" label="SynSCAN API"  @update:model-value="put({enable_synscan: cfg.enable_synscan})" />
           <q-input v-if="cfg.enable_synscan" label="Port" dense class="short" type="number"
             v-model.number="cfg.stellarium_synscan_port" @update:model-value="putdb({stellarium_synscan_port: cfg.stellarium_synscan_port})">
              <template v-slot:prepend><q-icon name="nat"></q-icon></template>
            </q-input>
        </div>
        <div class="row no-wrap q-gutter-sm">
            <q-input class='col-8 q-pl-sm' label="Polaris IP" dense v-model="cfg.polaris_ip_address" @update:model-value="putdb({polaris_ip_address: cfg.polaris_ip_address})" />
            <q-input label="Port" dense class="short" type="number" 
              v-model.number="cfg.polaris_port" @update:model-value="putdb({polaris_port: cfg.polaris_port})">
              <template v-slot:prepend><q-icon name="nat"></q-icon></template>
            </q-input>
        </div>
        <!-- Site Info -->
        <div class="text-h6 q-mt-lg">Observing Site Information</div>
        <div class="row">
          <div class="col-8 text-caption text-grey-6">
            Latitude and longitude are essential for accurate tracking. Elevation and pressure improve precision. 
            Click GPS to use your device’s location. Other settings follow the ASCOM Alpaca standard and are optional.
          </div>
          <div class="col q-pl-lg q-gutter-md">
            <q-btn outline color="grey-5" label="GPS" icon="my_location" @click="setFromPhoneLocation"/>
          </div>
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input class="col-3" type="number" v-model.number="cfg.site_latitude" label="Latitude" @update:model-value="putdb({site_latitude: cfg.site_latitude})" :class="{ taflash: taKey=='latlon'}"/>
            <q-input class="col-3" type="number" v-model.number="cfg.site_longitude" label="Longitude" @update:model-value="putdb({site_longitude: cfg.site_longitude})" :class="{ taflash: taKey=='latlon'}"/>
            <q-input class="col-5" v-model="cfg.location" label="Location" @update:model-value="putdb({location: cfg.location})" />
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input class="col-3" type="number" v-model.number="cfg.site_elevation" label="Elevation (m)" @update:model-value="putdb({site_elevation: cfg.site_elevation})" />
            <q-input class="col-3" type="number" v-model.number="cfg.site_pressure" label="Pressure (hPa)" @update:model-value="putdb({site_pressure: cfg.site_pressure})" />
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input class="col-3" type="number" v-model.number="cfg.focal_length" label="Focal Length (mm)" @update:model-value="putdb({focal_length: cfg.focal_length})" />
            <q-input class="col-3" type="number" v-model.number="cfg.focal_ratio" label="Focal Ratio (f-stop)" @update:model-value="putdb({focal_ratio: cfg.focal_ratio})" />
        </div>

        <!-- Advanced Features -->
        <div class="text-h6 q-mt-lg">Advanced Control Features</div>
        <div class="row q-pb-md">
          <div class="col-8 text-caption text-grey-6">
            Use Advanced Position Control to override the Benro Polaris default behaviour. 
            Toggle individual features below to enable advanced slewing, goto, tracking, guiding and rotator support.
          </div>
          <div class="col">
            <q-toggle class='col' v-model="cfg.advanced_control" label="Enable" @update:model-value="put({advanced_control: cfg.advanced_control})" />
          </div>
        </div>
        <div v-if="cfg.advanced_control">
          <div class="row">
            <q-toggle class='col-4' v-model="cfg.advanced_slewing" label="Advanced Slewing" @update:model-value="put({advanced_slewing: cfg.advanced_slewing})" />
            <q-toggle class='col-4' v-model="cfg.advanced_goto" label="Advanced Goto" @update:model-value="put({advanced_goto: cfg.advanced_goto})" />
          </div>
          <div class="row">
            <q-toggle class='col-4' v-model="cfg.advanced_tracking" label="Advanced Tracking" @update:model-value="put({advanced_tracking: cfg.advanced_tracking})" />
            <q-toggle class='col-4' v-model="cfg.advanced_guiding" label="Advanced Guiding" @update:model-value="put({advanced_guiding: cfg.advanced_guiding})" />
          </div>
          <div class="row">
            <q-toggle class='col-4' v-model="cfg.advanced_rotator" label="Advanced Rotator" @update:model-value="put({advanced_rotator: cfg.advanced_rotator})" />
          </div>
          <div class="row q-pl-md q-gutter-lg">
              <q-input class='col-3' type="number" v-model.number="cfg.max_slew_rate" label="Max Slew Rate" @update:model-value="putdb({max_slew_rate: cfg.max_slew_rate})" />
              <q-input class='col-3' type="number" v-model.number="cfg.max_accel_rate" label="Max Accel Rate" @update:model-value="putdb({max_accel_rate: cfg.max_accel_rate})" />
              <q-input class='col-3' type="number" v-model.number="cfg.tracking_settle_time" label="Tracking Settle Time" @update:model-value="putdb({tracking_settle_time: cfg.tracking_settle_time})" />
          </div>
        </div>

        <!-- Aiming Adjustment -->
        <div class="text-h6 q-mt-lg">Aiming Adjustment</div>
        <q-toggle v-model="cfg.aiming_adjustment_enabled" label="Enable Adjustment" @update:model-value="put({aiming_adjustment_enabled: cfg.aiming_adjustment_enabled})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_time" label="Adjustment Time" @update:model-value="putdb({aiming_adjustment_time: cfg.aiming_adjustment_time})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_az" label="Adjustment Az" @update:model-value="putdb({aiming_adjustment_az: cfg.aiming_adjustment_az})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_alt" label="Adjustment Alt" @update:model-value="putdb({aiming_adjustment_alt: cfg.aiming_adjustment_alt})" />
        <q-input type="number" v-model.number="cfg.aim_max_error_correction" label="Max Error Correction" @update:model-value="putdb({aim_max_error_correction: cfg.aim_max_error_correction})" />

        <!--  Sync -->
        <div class="text-h6 q-mt-lg">Sync</div>
        <q-input type="number" v-model.number="cfg.sync_pointing_model" label="Pointing Model" @update:model-value="putdb({sync_pointing_model: cfg.sync_pointing_model})" />
        <q-toggle v-model="cfg.sync_N_point_alignment" label="N-Point Alignment" @update:model-value="put({sync_N_point_alignment: cfg.sync_N_point_alignment})" />

        <!-- Logging -->
        <div class="text-h6 q-mt-lg">Logging</div>
        <q-toggle v-model="cfg.log_to_file" label="Log to File" @update:model-value="put({log_to_file: cfg.log_to_file})" />
        <q-toggle v-model="cfg.log_to_stdout" label="Log to Stdout" @update:model-value="put({log_to_stdout: cfg.log_to_stdout})" />
        <q-toggle v-model="cfg.log_polaris" label="Log Polaris" @update:model-value="put({log_polaris: cfg.log_polaris})" />
        <q-toggle v-model="cfg.log_polaris_protocol" label="Log Polaris Protocol" @update:model-value="put({log_polaris_protocol: cfg.log_polaris_protocol})" />
        <q-toggle v-model="cfg.log_stellarium_protocol" label="Log Stellarium Protocol" @update:model-value="put({log_stellarium_protocol: cfg.log_stellarium_protocol})" />
        <q-input type="number" v-model.number="cfg.log_level" label="Log Level" @update:model-value="putdb({log_level: cfg.log_level})" />
        <q-input type="number" v-model.number="cfg.log_performance_data" label="Performance Data" @update:model-value="putdb({log_performance_data: cfg.log_performance_data})" />
        <q-input type="number" v-model.number="cfg.log_performance_data_test" label="Perf Data Test" @update:model-value="putdb({log_performance_data_test: cfg.log_performance_data_test})" />
        <q-input type="number" v-model.number="cfg.log_perf_speed_interval" label="Perf Speed Interval" @update:model-value="putdb({log_perf_speed_interval: cfg.log_perf_speed_interval})" />
      </div>
    </q-card>
</q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()

const taKey = ref<string | null>(null)      // Used to trigger animations on a particular Key'ed element

onMounted(async () => {
  const shouldFetch =
    dev.alpacaConnected &&
    dev.alpacaConnectedAt &&
    cfg.fetchedAt < dev.alpacaConnectedAt

  if (shouldFetch) {
    await cfg.fetchConfig()
  }
})

function setFromPhoneLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition((pos) => {
        put({ site_latitude: pos.coords.latitude, site_longitude: pos.coords.longitude })
        triggerAnimation('latlon')
    }, (err) => {
        console.error('Location error:', err)
    })
  } else {
    console.warn('Geolocation not supported')
  }
}

function triggerAnimation(field: string) {
  taKey.value = field
  setTimeout(() => { taKey.value = null }, 600) // match animation duration
}

// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store 
const putdb = debounce((payload) => cfg.updateConfig(payload), 500) // slow put for input text
const put = debounce((payload) => cfg.updateConfig(payload), 5)     // fast put for toggles

</script>

<style lang="scss">
.taflash {
  animation: flash 0.6s;
}

.short {
  width: 100px;
}

</style>