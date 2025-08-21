

<template>
  <q-page class="q-pa-md">
    <div v-if="!dev.alpacaConnected" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action><q-btn flat label="Reconnect" to="/connect" /></template>
      </q-banner>
    </div>
    <q-card flat bordered class="q-pa-md">
      <div class="text-h6">Alpaca Driver Configuration</div>
      <q-separator spaced />
      <div v-if="!cfg.fetchedAt" class="text-negative">
        Configuration not loaded.
      </div>
      <div v-else>
        <!-- Network -->
        <div class="text-subtitle1 q-mt-md">Network Services</div>
        <div class="text-caption text-grey-6">
       The Alpaca Driver provides several network services for external aplications to use the Benro Polaris.
        </div>
        <div class="row  q-gutter-sm">
            <q-toggle v-model="cfg.enable_restapi" label="Alpaca REST API Service."  @update:model-value="put({enable_restapi: cfg.enable_restapi})"/>
            <q-input v-if="cfg.enable_restapi" dense prefix="Port:" type="number"  v-model="cfg.alpaca_restapi_port" @update:model-value="put({alpaca_restapi_port: cfg.alpaca_restapi_port})"/>
            <q-banner v-if="!cfg.enable_restapi" inline-actions rounded class="bg-warning">
                WARNING: The REST API is required for Nina, Stellarium and Alpaca Pilot.
            </q-banner>
            <q-banner v-if="cfg.alpaca_restapi_port!=dev.alpacaPort" inline-actions rounded class="bg-warning">
                WARNING: The REST API Port is different to the current Alpaca Connection. 
            </q-banner>
        </div>
        <div class="row  q-gutter-sm">
            <q-toggle v-model="cfg.enable_discovery" label="Alpaca Discovery Service."  @update:model-value="put({enable_discovery: cfg.enable_discovery})" />
            <q-input v-if="cfg.enable_discovery" dense prefix="Port:" type="number"  v-model="cfg.alpaca_discovery_port" @update:model-value="put({alpaca_discovery_port: cfg.alpaca_discovery_port})"/>
        </div>
        <div class="row  q-gutter-sm">
            <q-toggle v-model="cfg.enable_pilot" label="Alpaca Pilot Web Service."  @update:model-value="put({enable_pilot: cfg.enable_pilot})" />
            <q-input v-if="cfg.enable_pilot" dense prefix="Port:" type="number" v-model="cfg.alpaca_pilot_port" @update:model-value="put({alpaca_pilot_port: cfg.alpaca_pilot_port})"/>
        </div>
        <div class="row  q-gutter-sm">
           <q-toggle v-model="cfg.enable_synscan" label="Stellarium/SynSCAN Service."  @update:model-value="put({enable_synscan: cfg.enable_synscan})" />
           <q-input v-if="cfg.enable_synscan" dense prefix="Port:" type="number" v-model.number="cfg.stellarium_synscan_port" @update:model-value="put({stellarium_synscan_port: cfg.stellarium_synscan_port})"/>
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input v-model="cfg.polaris_ip_address" label="Polaris IP" @update:model-value="put({polaris_ip_address: cfg.polaris_ip_address})" />
            <q-input type="number" v-model.number="cfg.polaris_port" label="Polaris Port" @update:model-value="put({polaris_port: cfg.polaris_port})" />
        </div>
        <!-- Site Info -->
        <div class="text-subtitle1 q-mt-md">Observing Site Information</div>
        <div class="text-caption text-grey-6">
        The latitude and longitude are critical for accurate co-ordinate conversion and sidereal tracking. The elevation and pressure can further refine conversion calculations. All other settings are part of the ASCOM Alpaca standard and optional. 
        </div>

        <div class="row q-pl-md q-gutter-lg">
            <div class="q-pa-md"><q-btn class="col-5" label="Use GPS" icon="my_location" color="secondary" @click="setFromPhoneLocation"/></div>
            <q-input class="col-5" v-model="cfg.location" label="Location" @update:model-value="put({location: cfg.location})" />
        </div>
        <div >
            <div class="row q-pl-md q-gutter-lg">
                <q-input type="number" v-model.number="cfg.site_latitude" label="Latitude" @update:model-value="put({site_latitude: cfg.site_latitude})" :class="{ taflash: taKey=='latlon'}"/>
                <q-input type="number" v-model.number="cfg.site_longitude" label="Longitude" @update:model-value="put({site_longitude: cfg.site_longitude})" :class="{ taflash: taKey=='latlon'}"/>
            </div>
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input type="number" v-model.number="cfg.site_elevation" label="Elevation (m)" @update:model-value="put({site_elevation: cfg.site_elevation})" />
            <q-input type="number" v-model.number="cfg.site_pressure" label="Pressure (hPa)" @update:model-value="put({site_pressure: cfg.site_pressure})" />
        </div>
        <div class="row q-pl-md q-gutter-lg">
            <q-input type="number" v-model.number="cfg.focal_length" label="Focal Length (mm)" @update:model-value="put({focal_length: cfg.focal_length})" />
            <q-input type="number" v-model.number="cfg.focal_ratio" label="Focal Ratio (f-stop)" @update:model-value="put({focal_ratio: cfg.focal_ratio})" />
        </div>

        <!-- Advanced Features -->
        <div class="text-subtitle1 q-mt-md">Advanced Control Features</div>
        <div class="text-caption text-grey-6">
        The Alpaca Driver can perform advanced position control, overriding the Benro Polaris standard features. Choose which features you would like the Alpaca Driver to control. 
        </div>

        <q-toggle v-model="cfg.advanced_control" label="Advanced Control" @update:model-value="put({advanced_control: cfg.advanced_control})" />
        <q-toggle v-model="cfg.advanced_slewing" label="Advanced Slewing" @update:model-value="put({advanced_slewing: cfg.advanced_slewing})" />
        <q-toggle v-model="cfg.advanced_tracking" label="Advanced Tracking" @update:model-value="put({advanced_tracking: cfg.advanced_tracking})" />
        <q-toggle v-model="cfg.advanced_goto" label="Advanced Goto" @update:model-value="put({advanced_goto: cfg.advanced_goto})" />
        <q-toggle v-model="cfg.advanced_rotator" label="Advanced Rotator" @update:model-value="put({advanced_rotator: cfg.advanced_rotator})" />
        <q-toggle v-model="cfg.advanced_guiding" label="Advanced Guiding" @update:model-value="put({advanced_guiding: cfg.advanced_guiding})" />

        <div class="row q-pl-md q-gutter-lg">
            <q-input type="number" v-model.number="cfg.max_slew_rate" label="Max Slew Rate" @update:model-value="put({max_slew_rate: cfg.max_slew_rate})" />
            <q-input type="number" v-model.number="cfg.max_accel_rate" label="Max Accel Rate" @update:model-value="put({max_accel_rate: cfg.max_accel_rate})" />
            <q-input type="number" v-model.number="cfg.tracking_settle_time" label="Tracking Settle Time" @update:model-value="put({tracking_settle_time: cfg.tracking_settle_time})" />
        </div>

        <!-- Aiming Adjustment -->
        <div class="text-subtitle1 q-mt-md">Aiming Adjustment</div>
        <q-toggle v-model="cfg.aiming_adjustment_enabled" label="Enable Adjustment" @update:model-value="put({aiming_adjustment_enabled: cfg.aiming_adjustment_enabled})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_time" label="Adjustment Time" @update:model-value="put({aiming_adjustment_time: cfg.aiming_adjustment_time})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_az" label="Adjustment Az" @update:model-value="put({aiming_adjustment_az: cfg.aiming_adjustment_az})" />
        <q-input type="number" v-model.number="cfg.aiming_adjustment_alt" label="Adjustment Alt" @update:model-value="put({aiming_adjustment_alt: cfg.aiming_adjustment_alt})" />
        <q-input type="number" v-model.number="cfg.aim_max_error_correction" label="Max Error Correction" @update:model-value="put({aim_max_error_correction: cfg.aim_max_error_correction})" />

        <!--  Sync -->
        <div class="text-subtitle1 q-mt-md">Sync</div>
        <q-input type="number" v-model.number="cfg.sync_pointing_model" label="Pointing Model" @update:model-value="put({sync_pointing_model: cfg.sync_pointing_model})" />
        <q-toggle v-model="cfg.sync_N_point_alignment" label="N-Point Alignment" @update:model-value="put({sync_N_point_alignment: cfg.sync_N_point_alignment})" />

        <!-- Logging -->
        <div class="text-subtitle1 q-mt-md">Logging</div>
        <q-toggle v-model="cfg.log_to_file" label="Log to File" @update:model-value="put({log_to_file: cfg.log_to_file})" />
        <q-toggle v-model="cfg.log_to_stdout" label="Log to Stdout" @update:model-value="put({log_to_stdout: cfg.log_to_stdout})" />
        <q-toggle v-model="cfg.log_polaris" label="Log Polaris" @update:model-value="put({log_polaris: cfg.log_polaris})" />
        <q-toggle v-model="cfg.log_polaris_protocol" label="Log Polaris Protocol" @update:model-value="put({log_polaris_protocol: cfg.log_polaris_protocol})" />
        <q-toggle v-model="cfg.log_stellarium_protocol" label="Log Stellarium Protocol" @update:model-value="put({log_stellarium_protocol: cfg.log_stellarium_protocol})" />
        <q-input type="number" v-model.number="cfg.log_level" label="Log Level" @update:model-value="put({log_level: cfg.log_level})" />
        <q-input type="number" v-model.number="cfg.log_performance_data" label="Performance Data" @update:model-value="put({log_performance_data: cfg.log_performance_data})" />
        <q-input type="number" v-model.number="cfg.log_performance_data_test" label="Perf Data Test" @update:model-value="put({log_performance_data_test: cfg.log_performance_data_test})" />
        <q-input type="number" v-model.number="cfg.log_perf_speed_interval" label="Perf Speed Interval" @update:model-value="put({log_perf_speed_interval: cfg.log_perf_speed_interval})" />
      </div>
    </q-card>
</q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import type { ConfigResponse } from 'stores/config';
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
const put = debounce(rawUpdateFields, 500)
async function rawUpdateFields(payload: Partial<typeof cfg.$state>) {
  try {
    const updated = await dev.apiAction<ConfigResponse>('ConfigTOML', payload)
    cfg.$patch(updated)
  } catch (err) {
    const keys = Object.keys(payload).join(', ')
    console.warn(`Failed to update ${keys}:`, err)
  }
}

</script>

<style lang="scss">
.taflash {
  animation: flash 0.6s;
}

</style>