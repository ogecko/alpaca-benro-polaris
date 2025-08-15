<template>
  <q-page class="q-pa-md">
    <q-card flat bordered class="q-pa-md">

      <!-- Section 1: Connect Alpaca -->
      <q-card-section>
        <div class="text-h6"><q-checkbox v-model="alpacaConnected" color="positive" label="Connect to Alpaca Driver" @update:model-value="attemptConnectAlpaca"/></div>
        <div class="q-pl-xl q-mt-sm">
            <q-select
              v-model="selectedAlpacaDevice"
              :options="availableAlpacaDevices"
              label="Nearby Alpaca Drivers"
              dense
              outlined
              emit-value
              map-options
              option-label="name"
              option-value="id"
            />
          </div>
        <q-item class="q-pl-xl">
          <q-item-section>
            <div class="row items-start">
              <q-input v-model="alpacaHost" label="Host Name" class="col-8 q-mt-sm" />
              <q-input v-model="alpacaPort" label="Port" type="number" class="col-4 q-mt-sm" />
            </div>
          </q-item-section>
          <q-item-section side>
            <q-btn label="Default" icon="computer" color="secondary" @click="setFromPhoneLocation" />
          </q-item-section>
        </q-item>
        <div class="row q-pl-xl items-start">
        </div>        
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
            <q-btn label="Get GPS" icon="my_location" color="secondary" @click="setFromPhoneLocation" />
            </q-item-section>
        </q-item>
      </q-card-section>

    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useQuasar } from 'quasar'

const $q = useQuasar()

const alpacaConnected = ref(false)
const alpacaHost = ref('localhost')
const alpacaPort = ref(11111)
const polarisConnected = ref(false)
const locationSynced = ref(false)
const selectedPolarisDevice = ref(null)
const selectedAlpacaDevice = ref(null)

const availableAlpacaDevices = ref([
  { id: 'alpaca-001', name: 'Alpaca A' },
  { id: 'alpaca-002', name: 'Alpaca B' },
  { id: 'alpaca-003', name: 'Alpaca C' }
])

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

function fixStep(index:number) {
  // Simulate fixing the step
    const step = polarisSteps.value[index]
    if (step) {
      step.status = true
    }
}

function attemptConnectAlpaca(newValue: boolean) {
  // Simulate fixing the step

  if (newValue) {
    if (!selectedAlpacaDevice.value) {
      $q.notify({
        type: 'negative', // or 'negative' for red
        message: 'Select an Alpaca Driver before attempting to connect',
        position: 'top', // 'bottom', 'left', 'right' also valid
        timeout: 3000,   // milliseconds before auto-dismiss
        actions: [{ icon: 'close', color: 'white' }]
      })
      alpacaConnected.value = false

    }
  }

}
const latitude = ref<number | null>(null)
const longitude = ref<number | null>(null)

function setFromPhoneLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition((pos) => {
      latitude.value = pos.coords.latitude
      longitude.value = pos.coords.longitude
    }, (err) => {
      console.error('Location error:', err)
    })
  } else {
    console.warn('Geolocation not supported')
  }
}
</script>

