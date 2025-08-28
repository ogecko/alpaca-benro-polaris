<template>
  <q-page class="q-pa-sm">
    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Device Connections
        <div v-if="$q.screen.gt.xs" class="text-caption text-grey-6">
        Connect to the Alpaca Driver and Benro Polaris.
       </div>
      </div>
      <q-space />
      <div class="q-gutter-md flex justify-end q-mr-md">
        <q-btn-dropdown rounded color="grey-9" label="Network Services" :content-style="{ width: '600px' }">
          <NetworkSettings />
        </q-btn-dropdown>
      </div>
    </div>
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12 col-md-6 flex">
        <!-- Section 1: Connect Alpaca Driver -->
        <q-card flat bordered class="q-pa-md full-width">

            <div class="text-h6"><q-checkbox v-model="connectToAlpacaCheckbox" color="positive" label="Connect to Alpaca Driver"/></div>
            <q-list class="q-pl-lg">

              <q-item v-if="dev.restAPIConnectingMsg">
                <q-item-section avatar>
                  <q-circular-progress indeterminate rounded size="lg" color="positive" />
                </q-item-section>
                <q-item-section>{{ dev.restAPIConnectingMsg }}</q-item-section>
              </q-item>

              <q-item v-else-if="dev.restAPIConnected">
                <q-item-section avatar>
                  <q-icon name='mdi-check-circle' color='green'/>
                </q-item-section>
                <q-item-section>
                  <div class="q-gutter-sm">
                    {{ dev.alpacaServerName }}
                    <q-badge>v{{ dev.alpacaServerVersion }}</q-badge> 
                    <q-badge v-for="id in dev.alpacaDevices" :key="id" color="positive">{{ id }}</q-badge>
                  </div>
                </q-item-section>
              </q-item>

              <q-item v-if="dev.restAPIConnectErrorMsg">
                <q-item-section avatar>
                  <q-icon name='mdi-alert-circle' color='red'/>
                </q-item-section>
                <q-item-section>{{ dev.restAPIConnectErrorMsg }}</q-item-section>
              </q-item>

              <q-item v-if="!dev.restAPIConnected && !dev.restAPIConnectingMsg">
                <div class="row items-start">
                  <q-input class="col-8" v-model="dev.alpacaHost" @keyup.enter="attemmptConnectToAlpaca" label="Host Name / IP Address"  />
                  <q-input class="col-4" label='Port' v-model="dev.restAPIPort" @keyup.enter="attemmptConnectToAlpaca" type="number" input-class="text-right">
                  <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
                  </q-input>
                </div>
              </q-item>

            </q-list>
        </q-card>
      </div>      
      <div class="col-12 col-md-6 flex">
        <!-- Section 2: Connect Polaris -->
        <q-card flat bordered class="q-pa-md full-width">
            <div class="text-h6"><q-checkbox v-model="polarisConnected" color="positive" label="Connect to Benro Polaris"/></div>
            <div class="q-pl-xl q-mt-sm">
                <q-select 
                  v-model="selectedPolarisDevice"
                  :options="availablePolarisDevices"
                  label="Nearby Benro Polaris Devices"
                  dense
                  outlined
                  emit-value
                  map-options
                  option-label="name"
                  option-value="id"
                  class="q-mb-md"
                />
              </div>

            <div class="q-mt-md q-pl-lg ">
              <q-list :dense="true">
                <q-item v-for="(step, index) in polarisSteps" :key="index" class="q-mb-sm">
                  <q-item-section avatar>
                    <q-icon :name="step.status ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="step.status ? 'green' : 'red'" />
                  </q-item-section>
                  <q-item-section>
                    <div>{{ step.label }}</div>
                  </q-item-section>
                  <q-item-section side>
                    <q-btn label="Fix" :icon="step.icon" color="secondary" @click="fixStep(index)" />
                  </q-item-section>
                </q-item>

              </q-list>
            </div>
        </q-card>


<!-- Section 2: Temporary Junk Polaris -->
<q-card flat bordered class="q-pa-md full-width">
  <div class="text-h6">
    <q-checkbox v-model="polarisConnected" color="positive" label="Connect to Benro Polaris" />
  </div>

  <div class="q-pl-xl q-mt-sm">
    <q-expansion-item
      icon="mdi-satellite_alt"
      label="Nearby Benro Polaris Devices"
      caption="Select a discovered device or enter manually"
      dense
      expand-separator
      default-opened
    >
      <div class="q-mb-sm">
        <q-btn
          label="Refresh Device List"
          icon="mdi-refresh"
          color="primary"
          flat
          dense
        />
      </div>

      <q-select
        v-model="selectedPolarisDevice"
        :options="availablePolarisDevices"
        label="Discovered Devices"
        emit-value
        map-options
        option-label="name"
        option-value="id"
        outlined
        dense
        class="q-mb-md"
      >
        <template v-slot:no-option>
          <q-item>
            <q-item-section>No devices found. Please enter manually.</q-item-section>
          </q-item>
        </template>
      </q-select>

      <!-- Manual Entry Fallback -->
      <div  class="row items-start q-mt-sm">
        <q-input
          class="col-8"
          v-model="dev.alpacaHost"
          @keyup.enter="attemmptConnectToAlpaca"
          label="Host Name / IP Address"
        />
        <q-input
          class="col-4"
          label="Port"
          v-model="dev.restAPIPort"
          @keyup.enter="attemmptConnectToAlpaca"
          type="number"
          input-class="text-right"
        >
          <template v-slot:prepend><q-icon name="mdi-network-outline" /></template>
        </q-input>
      </div>
    </q-expansion-item>
  </div>

  <!-- Polaris Connection Steps -->
  <div class="q-mt-md q-pl-lg">
    <q-list dense>
      <q-item v-for="(step, index) in polarisSteps" :key="index" class="q-mb-sm">
        <q-item-section avatar>
          <q-icon :name="step.status ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="step.status ? 'green' : 'red'" />
        </q-item-section>
        <q-item-section>
          <div>{{ step.label }}</div>
        </q-item-section>
        <q-item-section side>
          <q-btn label="Fix" :icon="step.icon" color="secondary" @click="fixStep(index)" />
        </q-item-section>
      </q-item>
    </q-list>
  </div>
</q-card>


      </div>      
    </div>

</q-page>
</template>

<script setup lang="ts">
import { useQuasar } from 'quasar'
import { useDeviceStore } from 'stores/device'
import { ref, watch } from 'vue'
import NetworkSettings from 'components/NetworkSettings.vue'

const $q = useQuasar()
const dev = useDeviceStore()

const connectToAlpacaCheckbox = ref(dev.restAPIConnected);
const polarisConnected = ref(false)
const selectedPolarisDevice = ref(null)

const availablePolarisDevices = ref([
  { id: 'benro-001', name: 'Benro Polaris A' },
  { id: 'benro-002', name: 'Benro Polaris B' },
  { id: 'benro-003', name: 'Benro Polaris C' }
])

const polarisSteps = ref([
  { label: 'WiFi Enabled', icon: 'mdi-wifi', status: false },
  { label: 'Astro Mode', icon: 'mdi-camera', status: false },
  { label: 'Aligned', icon: 'mdi-altimeter', status: false },
  { label: 'Running', icon: 'mdi-check-circle', status: false }
])

watch(connectToAlpacaCheckbox, async (newVal) => {
  if (newVal) {
    await attemmptConnectToAlpaca()
  } else {
    attemptDisconnectFromAlpaca()
  }
})

// disconnect when user unchecks the checkbox
function attemptDisconnectFromAlpaca() {
  dev.disconnectRestAPI()
  connectToAlpacaCheckbox.value = dev.restAPIConnected
}

// connect when user checks the checkbox or presses enter on Host or Port field
async function attemmptConnectToAlpaca() {
  if (!dev.restAPIConnected) {
    await dev.connectRestAPI()
    connectToAlpacaCheckbox.value = dev.restAPIConnected
    if (dev.restAPIConnected) {
      $q.notify({
        message: 'Alpaca Driver successfuly connected.',
        type: 'positive', position: 'top', timeout: 3000,
        actions: [{ icon: 'mdi-close', color: 'white' }]
      })
    }
  }
}

function fixStep(index: number) {
  const step = polarisSteps.value[index]
  if (step) step.status = true
}

</script>


