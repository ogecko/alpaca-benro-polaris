<template>
  <q-page class="q-pa-sm">
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12 col-md-6 flex">
        <!-- Section 1: Connect Alpaca -->
        <q-card flat bordered class="q-pa-md full-width">

            <div class="text-h6"><q-checkbox v-model="connectToAlpacaCheckbox" color="positive" label="Connect to Alpaca Driver"/></div>
            <q-list class="q-pl-lg">

              <q-item v-if="dev.alpacaConnectingMsg">
                <q-item-section avatar>
                  <q-circular-progress indeterminate rounded size="lg" color="positive" />
                </q-item-section>
                <q-item-section>{{ dev.alpacaConnectingMsg }}</q-item-section>
              </q-item>

              <q-item v-else-if="dev.alpacaConnected">
                <q-item-section avatar>
                  <q-icon name='check_circle' color='green'/>
                </q-item-section>
                <q-item-section>
                  <div class="q-gutter-sm">
                    {{ dev.alpacaServerName }}
                    <q-badge>v{{ dev.alpacaServerVersion }}</q-badge> 
                    <q-badge v-for="id in dev.alpacaDevices" :key="id" color="positive">{{ id }}</q-badge>
                  </div>
                </q-item-section>
              </q-item>

              <q-item v-if="dev.alpacaConnectErrorMsg">
                <q-item-section avatar>
                  <q-icon name='error' color='red'/>
                </q-item-section>
                <q-item-section>{{ dev.alpacaConnectErrorMsg }}</q-item-section>
              </q-item>

              <q-item v-if="!dev.alpacaConnected && !dev.alpacaConnectingMsg">
                <div class="row items-start">
                  <q-input class="col-8" v-model="dev.alpacaHost" @keyup.enter="connect" label="Host Name / IP Address"  />
                  <q-input class="col-4" label='Port' v-model="dev.alpacaPort" @keyup.enter="connect" type="number" input-class="text-right">
                  <template v-slot:prepend><q-icon name="nat"></q-icon></template>
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
                    <q-icon :name="step.status ? 'check_circle' : 'error'" :color="step.status ? 'green' : 'red'" />
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








        
<q-card flat bordered class="q-pa-md full-width">
  <div class="text-h6">
    <q-checkbox v-model="polarisConnected" color="positive" label="Connect to Benro Polaris" />
  </div>

  <div class="q-pl-xl q-mt-sm">
    <q-expansion-item
      icon="satellite_alt"
      label="Nearby Benro Polaris Devices"
      caption="Select a discovered device or enter manually"
      dense
      expand-separator
      default-opened
    >
      <div class="q-mb-sm">
        <q-btn
          label="Refresh Device List"
          icon="refresh"
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
          @keyup.enter="connect"
          label="Host Name / IP Address"
        />
        <q-input
          class="col-4"
          label="Port"
          v-model="dev.alpacaPort"
          @keyup.enter="connect"
          type="number"
          input-class="text-right"
        >
          <template v-slot:prepend><q-icon name="nat" /></template>
        </q-input>
      </div>
    </q-expansion-item>
  </div>

  <!-- Polaris Connection Steps -->
  <div class="q-mt-md q-pl-lg">
    <q-list dense>
      <q-item v-for="(step, index) in polarisSteps" :key="index" class="q-mb-sm">
        <q-item-section avatar>
          <q-icon :name="step.status ? 'check_circle' : 'error'" :color="step.status ? 'green' : 'red'" />
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

const $q = useQuasar()
const dev = useDeviceStore()

const connectToAlpacaCheckbox = ref(dev.alpacaConnected);
const polarisConnected = ref(false)
const selectedPolarisDevice = ref(null)

const availablePolarisDevices = ref([
  { id: 'benro-001', name: 'Benro Polaris A' },
  { id: 'benro-002', name: 'Benro Polaris B' },
  { id: 'benro-003', name: 'Benro Polaris C' }
])

const polarisSteps = ref([
  { label: 'WiFi Enabled', icon: 'wifi', status: false },
  { label: 'Astro Mode', icon: 'camera', status: false },
  { label: 'Aligned', icon: 'add', status: false },
  { label: 'Running', icon: 'check_circle', status: false }
])

watch(connectToAlpacaCheckbox, async (newVal) => {
  if (newVal && !dev.alpacaConnected) {
    await dev.connectAlpaca()
    if (dev.alpacaConnected) {
      $q.notify({
        message: 'Alpaca Driver successfuly connected.',
        type: 'positive', position: 'top', timeout: 3000,
        actions: [{ icon: 'close', color: 'white' }]
      })
    }
  }
  if (!newVal) {
    dev.disconnectAlpaca()
  }
  connectToAlpacaCheckbox.value = dev.alpacaConnected
})

async function connect() {
  await dev.connectAlpaca()
  connectToAlpacaCheckbox.value = dev.alpacaConnected
}
function fixStep(index: number) {
  const step = polarisSteps.value[index]
  if (step) step.status = true
}

</script>


