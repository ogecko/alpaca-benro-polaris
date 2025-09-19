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
        <!-- Section 2: Connect Benro Polaris -->
        <q-card flat bordered class="q-pa-md full-width">
          <div class="text-h6">
            <q-checkbox v-model="connectToPolarisCheckbox" color="positive" label="Connect to Benro Polaris" />
          </div>

          <div class="q-pl-xl q-mt-sm">
          </div>

          <!-- Polaris Connection Steps -->
          <div class="q-mt-md q-pl-lg">
            <q-list >
              <!-- Select Polaris Device -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Select Benro Polaris</q-item-label>
                  <q-item-label caption>{{ bleCaption }}</q-item-label>
                </q-item-section>
                <q-item-section v-if="bleLen>0" side>
                  <q-select label="Device" v-model="p.bleselected" :onUpdate:modelValue="onBleSelected" :options="p.bledevices" class="fixedWidth"
                            :display-value="`${isBLESelected ? p.bleselected : 'Unselected'}`" color="secondary">
                    <template>
                      <q-icon name="mdi-satellite-variant"></q-icon>
                    </template>
                  </q-select>
                </q-item-section>
              </q-item>
              <!-- Connect via Network -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isPolarisConnected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isPolarisConnected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Device Connection</q-item-label>
                  <q-item-label caption>{{ openCaption }}</q-item-label>
                </q-item-section>
              </q-item>
              <!-- Enable Wifi -->
              <q-item :inset-level="1.5">
                <q-item-section><q-item-label caption>Enable Polaris Wifi Hotspot</q-item-label></q-item-section>
                <q-circular-progress v-if="p.bleisenablingwifi" indeterminate rounded size="md" color="positive" />
                <q-item-section side>
                  <q-badge v-if="p.bleiswifienabled">On</q-badge>
                  <q-btn label="Enable" icon="mdi-wifi"  @click="onBleEnableWifi" class="fixedWidth" />
                </q-item-section>
              </q-item>
              <!-- Network Settings -->
              <q-item  :inset-level="1.5">
                <q-item-section>
                  <div  class="row items-start ">
                    <q-input class="col-8 q-pt-none" label="Host Name / IP Address"
                      v-model="cfg.polaris_ip_address" @keyup.enter="attemmptConnectToPolaris" >
                    </q-input>
                    <q-input class="col-4" label="Port" type="number" input-class="text-right"
                      v-model="cfg.polaris_port" @keyup.enter="attemmptConnectToPolaris" >
                      <template v-slot:prepend><q-icon name="mdi-network-outline" /></template>
                    </q-input>
                  </div>
                </q-item-section>
              </q-item>
              <!-- Select Astro Mode -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Select Astro Mode</q-item-label>
                  <q-item-label caption>{{ astroCaption }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-select label="Mode" v-model="p.polarismode" :options="polarisModeOptions" options-dense  class="fixedWidth"
                            :display-value="`${p.polarismodestr}`" color="secondary">
                    <template>
                      <q-icon name="mdi-satellite-variant"></q-icon>
                    </template>
                  </q-select>
                </q-item-section>
              </q-item>
              <!-- Park -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Goto Park Position</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn label="Park" icon="mdi-parking"  @click="onBleEnableWifi" class="fixedWidth"/>
                </q-item-section>
              </q-item>
              <!-- Compass -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Align Compass Azimuth</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn label="Skip" icon="mdi-compass"  @click="onBleEnableWifi" class="fixedWidth"/>
                </q-item-section>
              </q-item>
              <!-- Single Star Align -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Single Star Alignment</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn label="Skip" icon="mdi-flare"  @click="onBleEnableWifi" class="fixedWidth"/>
                </q-item-section>
              </q-item>
              <!-- Multi Star Align -->
              <q-item>
                <q-item-section avatar>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Multi Star Alignment</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn label="Begin" icon="mdi-creation-outline"  @click="onBleEnableWifi" class="fixedWidth"/>
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
import { useConfigStore } from 'stores/config'
import { useStatusStore, polarisModeOptions } from 'stores/status'
import { ref, watch, computed } from 'vue'
import NetworkSettings from 'components/NetworkSettings.vue'

const $q = useQuasar()
const dev = useDeviceStore()
const cfg = useConfigStore()
const p = useStatusStore()

const connectToAlpacaCheckbox = ref(dev.restAPIConnected);
const connectToPolarisCheckbox = ref(false)
const isPolarisConnected = ref(false)

const bleLen = computed(() => p.bledevices.length);
const isBLESelected = computed(() => !!p.bleselected && bleLen.value>0);
const bleCaption = computed(() => {
  return (bleLen.value==0) ? 'Check Power, no devices discovered.' :
         (bleLen.value>1) ? 'Multiple devices discovered.' :
         (isBLESelected.value) ? 'Device discovered and selected.' :
                                 'Please select device.'
});
const openCaption = computed(() => {
  return (!isPolarisConnected.value) ? 'Check Network settings, cannot open connection.' :
                          'Device connected.'
});
const astroCaption = computed(() => {
  return (!isPolarisConnected.value) ? 'Check Astro Module, none detected.' :
                          'Change Polaris Mode to Astro.'
});



watch(connectToAlpacaCheckbox, async (newVal) => {
  if (newVal) {
    await attemmptConnectToAlpaca()
  } else {
    attemptDisconnectFromAlpaca()
  }
})

async function onBleSelected(newVal:string) {
  await dev.bleSelectDevice(newVal)
}

async function onBleEnableWifi() {
  await dev.bleEnableWifi()
}

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

watch(connectToPolarisCheckbox, (newVal) => {
  if (newVal) {
    attemmptConnectToPolaris()
  } else {
    attemptDisconnectFromPolaris()
  }
})

// disconnect when user unchecks the checkbox
function attemptDisconnectFromPolaris() {
  console.log('Disconnect Polaris')
}

function attemmptConnectToPolaris() {
  console.log('Connecting to Polaris')
}


</script>

<style lang="scss">

.fixedWidth {
  width:140px;
}

</style>

