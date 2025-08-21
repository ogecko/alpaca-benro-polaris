<template>
  <q-page class="q-pa-md">
    <q-card flat bordered class="q-pa-md">

      <!-- Section 1: Connect Alpaca -->
      <q-card-section>
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
              <q-input v-model="dev.alpacaHost" @keyup.enter="connect" label="Host Name / IP Address" class="col-8 q-mt-sm" />
              <q-input v-model="dev.alpacaPort" @keyup.enter="connect" label="Port" type="number" class="col-4 q-mt-sm" />
            </div>
          </q-item>

        </q-list>
      </q-card-section>

      <q-separator />

      <!-- Section 2: Connect Polaris -->
      <q-card-section>
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
      </q-card-section>

      <q-separator />

      <!-- Section 3: Observer Location -->
      <q-card-section>
        <div class="text-h6"><q-checkbox v-model="locationSynced" color="positive" label="Observer Location Sync"/></div>
        <q-item class="q-pl-xl">
            <q-item-section>
            <div class="row items-start">
              <q-input v-model="latitude" label="Latitude" type="number" class="col-6 q-mt-sm" />
              <q-input v-model="longitude" label="Longitude" type="number" class="col-6 q-mt-sm" />
            </div>
            </q-item-section>
            <q-item-section side>
            <q-btn label="GPS" icon="my_location" color="secondary"  />
            </q-item-section>
        </q-item>
      </q-card-section>

    </q-card>
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
const locationSynced = ref(false)
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



const latitude = ref<number | null>(null)
const longitude = ref<number | null>(null)
</script>


