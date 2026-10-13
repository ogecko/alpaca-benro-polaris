<template>
    <q-card flat bordered class="q-pa-md gps-card">
        <!-- GPS Receiver Heading -->
        <div class="text-h6">GPS Receiver</div>
        <div class="text-caption text-grey-6 q-pb-md wrap-to-fit">
            A GPS receiver connected to the computer running the Alpaca Driver. Locate uses it to determine the
            observing site's latitude, longitude, and elevation.
        </div>
        <div class="q-gutter-y-md">
            <!-- Connection: gpsd is only offered when the driver runs on Linux -->
            <q-select v-if="protocolOptions.length > 1" v-model="draft.gps_provider" :options="protocolOptions"
                      label="Connection" emit-value map-options/>
            <template v-if="draft.gps_provider === 'gpsd'">
                <div class="row q-col-gutter-md">
                    <q-input class="col-8" v-model="draft.gpsd_host" label="gpsd Host"/>
                    <q-input class="col-4" v-model.number="draft.gpsd_port" label="Port" type="number" input-class="text-right"/>
                </div>
            </template>
            <template v-else>
                <!-- Invisible copies of the port names: they set the panel's width, so the longest one shows in full -->
                <div class="port-sizer" aria-hidden="true">
                    <div v-for="o in portOptions" :key="o.value">{{ o.label }}</div>
                </div>
                <!-- Serial Port: what each device is, likely GPS receivers marked -->
                <q-select v-model="draft.gps_serial_device" :options="portOptions" label="Serial Port"
                          emit-value map-options :loading="portsLoading">
                    <template v-slot:option="scope">
                        <q-item v-bind="scope.itemProps">
                            <q-item-section avatar>
                                <q-icon :name="scope.opt.gps ? 'mdi-crosshairs-gps' : 'mdi-serial-port'"
                                        :color="scope.opt.gps ? 'positive' : 'grey-6'"/>
                            </q-item-section>
                            <q-item-section>
                                <q-item-label>{{ scope.opt.label }}</q-item-label>
                                <q-item-label caption>{{ scope.opt.caption }}</q-item-label>
                            </q-item-section>
                        </q-item>
                    </template>
                    <template v-slot:no-option>
                        <q-item><q-item-section class="text-grey-6">No serial ports found</q-item-section></q-item>
                    </template>
                    <template v-slot:after>
                        <q-btn flat round icon="mdi-refresh" color="grey-6" @click="loadSerialPorts">
                            <q-tooltip>Refresh serial ports</q-tooltip>
                        </q-btn>
                    </template>
                </q-select>
                <div v-if="noPorts" class="text-caption text-grey-6">
                    No serial ports found. Connect the GPS receiver, then refresh.
                </div>
                <div>
                    <q-select v-model="draft.gps_serial_baudrate" :options="BAUD_RATES" label="Baud Rate"/>
                    <div class="text-caption text-grey-6 q-pt-xs">
                        Ignored by GPS receivers that connect directly over USB, such as u-blox receivers.
                    </div>
                </div>
            </template>
        </div>
        <div class="row justify-end q-gutter-sm q-pt-lg">
            <q-btn rounded flat color="grey-5" label="Cancel" @click="emit('close')"/>
            <q-btn rounded color="grey-9" label="OK" @click="save" :disable="!canSave"/>
        </div>
    </q-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useConfigStore } from 'stores/config'
import { useDeviceStore } from 'stores/device'
import type { SerialPort } from 'stores/device'
import { useStatusStore } from 'stores/status'

const emit = defineEmits<{ close: [] }>()

const cfg = useConfigStore()
const dev = useDeviceStore()
const p = useStatusStore()

const BAUD_RATES = [4800, 9600, 38400, 115200]

// Edits are held here until OK; Cancel (or clicking away) leaves the config untouched
const draft = reactive({
  gps_provider: ((cfg.gps_provider === 'gpsd' && p.platform === 'linux') ? 'gpsd' : 'nmea') as 'gpsd' | 'nmea',
  gpsd_host: cfg.gpsd_host,
  gpsd_port: cfg.gpsd_port,
  gps_serial_device: cfg.gps_serial_device,
  gps_serial_baudrate: cfg.gps_serial_baudrate,
})

const protocolOptions = computed(() => p.platform === 'linux'
  ? [{ label: 'USB / Serial (NMEA)', value: 'nmea' }, { label: 'gpsd', value: 'gpsd' }]
  : [{ label: 'USB / Serial (NMEA)', value: 'nmea' }])

// Ports are listed by the driver without opening them (opening can reset a device such as a focuser)
const serialPorts = ref<SerialPort[]>([])
const portsLoading = ref(false)

const portOptions = computed(() => {
  const options = serialPorts.value.map(sp => ({
    value: sp.device,
    label: `${sp.device} – ${sp.kind}`,
    caption: sp.gps ? 'GPS receiver'
      : sp.kind.startsWith('USB-serial') ? 'Could be a GPS receiver, focuser or other device'
      : (sp.manufacturer || sp.description),
    gps: sp.gps,
  }))
  if (draft.gps_serial_device && !options.some(o => o.value === draft.gps_serial_device)) {
    options.unshift({ value: draft.gps_serial_device, label: `${draft.gps_serial_device} – not connected`,
      caption: 'Plug the receiver in, then refresh', gps: false })
  }
  return options
})

// Nothing to choose: say so (and OK stays off) rather than show an empty dropdown
const noPorts = computed(() => !portsLoading.value && portOptions.value.length === 0)
const canSave = computed(() => draft.gps_provider === 'gpsd' || !!draft.gps_serial_device)

async function loadSerialPorts() {
  portsLoading.value = true
  try {
    serialPorts.value = (await dev.alpacaSerialPorts()) ?? []
    // With no port chosen yet, pick the one GPS receiver if exactly one is present
    const gpsPorts = serialPorts.value.filter(sp => sp.gps)
    if (!draft.gps_serial_device && gpsPorts.length === 1) draft.gps_serial_device = gpsPorts[0]!.device
  } finally {
    portsLoading.value = false
  }
}

async function save() {
  await cfg.configUpdate({ location_source: 'gps', ...draft })
  emit('close')
}

onMounted(loadSerialPorts)
</script>


<style scoped>
/* The panel is as wide as its longest port name (at least 300px), not as wide as the description would like */
.gps-card {
  width: max-content;
  min-width: 300px;
  max-width: 95vw;
}
.wrap-to-fit {
  width: 0;
  min-width: 100%;
}
/* Room for the dropdown arrow and the refresh button beside the port name */
.port-sizer {
  height: 0;
  overflow: hidden;
  visibility: hidden;
  padding-right: 80px;
  margin: 0 !important;
}
</style>
