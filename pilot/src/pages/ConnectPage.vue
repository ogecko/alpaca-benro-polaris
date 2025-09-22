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

            <div class="text-h6"><q-checkbox label="Connect to Alpaca Driver" color="positive" 
              :model-value="dev.restAPIConnected" @update:model-value="onAlpacaCheckboxToggle" /></div>
            <q-list class="q-pl-lg">

              <!-- Alpaca Connecting -->
              <q-item v-if="dev.restAPIConnectingMsg">
                <q-item-section thumbnail>
                  <q-circular-progress indeterminate rounded size="lg" color="positive" />
                </q-item-section>
                <q-item-section>{{ dev.restAPIConnectingMsg }}</q-item-section>
              </q-item>

              <!-- Alpaca Connected -->
              <q-item v-else-if="dev.restAPIConnected">
                <q-item-section thumbnail>
                  <q-icon name='mdi-check-circle' color='green'/>
                </q-item-section>
                <q-item-section>
                  <q-item-label>
                    {{ dev.alpacaServerName }}
                    <span class="q-gutter-sm q-pl-sm">
                    <q-badge>v{{ dev.alpacaServerVersion }}</q-badge> 
                    <q-badge v-for="id in dev.alpacaDevices" :key="id" color="positive">{{ id }}</q-badge>
                    </span>
                  </q-item-label>
                </q-item-section>
              </q-item>

              <!-- Alpaca Connection Problem -->
              <q-item v-else>
                <q-item-section thumbnail>
                  <q-icon name='mdi-alert-circle' color='red'/>
                </q-item-section>
                <q-item-section>
                  <q-item-label>Alpaca Driver Connection Problem</q-item-label>
                  <q-item-label caption>{{ dev.restAPIConnectErrorMsg }}</q-item-label>
                </q-item-section>
                <q-item-section v-if="!dev.restAPIConnected" side>
                  <q-btn label="Connect" icon="mdi-wifi"  @click="attemmptConnectToAlpaca" class="fixedWidth" />
                </q-item-section>
              </q-item>

              <!-- Alpaca Connection Settings -->
              <q-item v-if="!dev.restAPIConnected && !dev.restAPIConnectingMsg"  :inset-level="0.5">
                <q-item-section>
                  <div class="row items-start">
                    <q-input class="col-8" v-model="dev.alpacaHost" @keyup.enter="attemmptConnectToAlpaca" label="Host Name / IP Address"  />
                    <q-input class="col-4" label='Port' v-model="dev.restAPIPort" @keyup.enter="attemmptConnectToAlpaca" type="number" input-class="text-right">
                    <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
                    </q-input>
                  </div>
                </q-item-section>
              </q-item>

            </q-list>
        </q-card>
      </div>      

      <div v-if="dev.restAPIConnected" class="col-12 col-md-6 flex">
        <!-- Section 2: Connect Benro Polaris -->
        <q-card flat bordered class="q-pa-md full-width">
          <div class="text-h6">
            <q-checkbox :model-value="p.connected" @update:model-value="onPolarisCheckboxToggle" color="positive" label="Connect Driver to Benro Polaris" />
          </div>

          <!-- Polaris Connection Steps -->
          <div class="q-mt-md q-pl-lg">
            <q-list >
              <!-- Select Polaris Device -->
              <q-item>
                <q-item-section thumbnail>
                  <q-icon :name="isBLESelected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isBLESelected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Select Benro Polaris</q-item-label>
                  <q-item-label caption>{{ bleCaption }}</q-item-label>
                </q-item-section>
                <q-item-section v-if="bleLen>0" side>
                  <q-select  label="Device" v-model="p.bleselected" :onUpdate:modelValue="onBleSelected" :options="p.bledevices"  dense options-dense
                            :display-value="`${isBLESelected ? p.bleselected : 'Unselected'}`" color="secondary">
                    <template v-slot:before>
                      <q-circular-progress v-if="p.bleisenablingwifi" indeterminate rounded size="sm" color="primary" />
                      <q-btn v-else round dense flat icon="mdi-wifi-sync" :color="(p.bleiswifienabled)?'primary':'white'" @click="onBleEnableWifi"/>
                    </template>
                  </q-select>
                </q-item-section>
              </q-item>

              <!-- Polaris Connecting -->
              <q-item v-if="p.connecting && p.bleselected">
                <q-item-section thumbnail>
                  <q-circular-progress indeterminate rounded size="lg" color="positive" />
                </q-item-section>
                <q-item-section>Connecting...</q-item-section>
              </q-item>

              <!-- Polaris Connected -->
              <q-item v-else-if="isPolarisConnected">
                <q-item-section thumbnail>
                  <q-icon name="mdi-check-circle" color="green" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>
                    Benro Polaris
                    <span class="q-gutter-sm q-pl-sm">
                      <q-badge>hw v{{ p.polarishwver }}</q-badge>
                      <q-badge>sw v{{ p.polarisswver }}</q-badge> 
                    </span>
                  </q-item-label>
                </q-item-section>
              </q-item>

              <div v-else-if="isBLESelected">
                <!-- Polaris Connection Problem -->
                <q-item>
                  <q-item-section thumbnail>
                    <q-icon name="mdi-alert-circle" color="red" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>Benro Polaris Connection Problem</q-item-label>
                    <q-item-label caption>{{p.connectionmsg}}</q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-btn label="Connect" icon="mdi-wifi"  @click="attemmptConnectToPolaris" class="fixedWidth" />
                  </q-item-section>
                </q-item>

                <!-- Polaris Network Settings -->
                <q-item :inset-level="0.5">
                  <q-item-section>
                    <div  class="row items-start">
                      <q-input class="col-8 q-pt-none" label="Host Name / IP Address"
                        v-model="cfg.polaris_ip_address" :onUpdate:modelValue="onPolarisIPChange" @keyup.enter="attemmptConnectToPolaris" >
                      </q-input>
                      <q-input class="col-4" label="Port" type="number" input-class="text-right"
                        v-model="cfg.polaris_port" :onUpdate:modelValue="onPolarisPortChange" @keyup.enter="attemmptConnectToPolaris" >
                        <template v-slot:prepend><q-icon name="mdi-network-outline" /></template>
                      </q-input>
                    </div>
                  </q-item-section>
                </q-item>
              </div>

              <!-- Select Astro Mode -->
              <q-item v-if="p.connected">
                <q-item-section thumbnail>
                  <q-icon :name="isAstroMode ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isAstroMode ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Select Astro Mode</q-item-label>
                  <q-item-label caption>{{ astroCaption }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-select label="Mode" v-model="p.polarismode" @update:modelValue="onModeUpdate" :options="polarisModeOptions" :display-value="`${p.polarismodestr}`"
                             emit-value map-options dense options-dense  class="fixedWidth" color="secondary">
                    <template>
                      <q-icon name="mdi-satellite-variant"></q-icon>
                    </template>
                  </q-select>
                </q-item-section>
              </q-item>

              <!-- Park -->
              <q-item v-if="p.connected">
                <q-item-section thumbnail>
                  <q-icon :name="isPolarisConnected ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="isPolarisConnected ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Goto Park Position</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn label="Park" icon="mdi-parking"  class="fixedWidth" @click="onPark"/>
                </q-item-section>
              </q-item>

              <!-- Compass -->
              <q-item v-if="p.connected">
                <q-item-section thumbnail>
                  <q-icon :name="p.compassed ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="p.compassed ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Compass Alignment</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn-dropdown label="Skip" split icon="mdi-compass"  @click="onCompass(default_az)" class="fixedWidth">
                    <q-list dense class="q-mt-md q-mb-md">
                      <q-item>
                        <q-item-section>
                          <q-item-label caption>Use this default.</q-item-label>
                          <q-item-label caption>Plate solve later.</q-item-label>
                        </q-item-section>
                      </q-item>
                      <q-item>
                        <q-input label="Azimuth" v-model="default_az" number input-class="text-right" class="fixedWidth"/>
                      </q-item>
                    </q-list>
                  </q-btn-dropdown>
                </q-item-section>
              </q-item>

              <!-- Single Star Align -->
              <q-item v-if="p.connected">
                <q-item-section thumbnail>
                  <q-icon :name="p.aligned ? 'mdi-check-circle' : 'mdi-alert-circle'" :color="p.aligned ? 'green' : 'red'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>Single Star Alignment</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-sm">
                    <q-circular-progress v-if="p.aligning" indeterminate rounded size="sm" />
                    <q-btn-dropdown label="Skip" split icon="mdi-flare"  @click="onAlignment(default_az, default_alt)" class="fixedWidth">
                      <q-list dense class="q-mt-md q-mb-md">
                        <q-item>
                          <q-item-section>
                            <q-item-label caption>Use these defaults.</q-item-label>
                            <q-item-label caption>Plate solve later.</q-item-label>
                          </q-item-section>
                        </q-item>
                        <q-item>
                          <q-input label="Azimuth" v-model="default_az" number input-class="text-right" class="fixedWidth"/>
                        </q-item>
                        <q-item>
                          <q-input label="Altitude" v-model="default_alt" number input-class="text-right" class="fixedWidth"/>
                        </q-item>
                      </q-list>
                    </q-btn-dropdown>
                  </div>
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
import { useQuasar, debounce } from 'quasar'
import { useDeviceStore } from 'stores/device'
import { useConfigStore } from 'stores/config'
import { useStatusStore, polarisModeOptions } from 'stores/status'
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import NetworkSettings from 'components/NetworkSettings.vue'

const $q = useQuasar()
const dev = useDeviceStore()
const cfg = useConfigStore()
const p = useStatusStore()

const default_az = ref<number>(180)
const default_alt = ref<number>(45)

// ------------------- Computed Resources ---------------------

const bleLen = computed(() => p.bledevices.length);
const isBLESelected = computed(() => !!p.bleselected && bleLen.value>0);
const isPolarisConnected = computed(() => (!!p.connected));
const bleCaption = computed(() => {
  return (bleLen.value==0) ? 'Check Power, no devices discovered.' :
         (bleLen.value>1) ? 'Multiple devices discovered.' :
         (isBLESelected.value) ? '' : 'Please select device.'
});
const isAstroMode = computed(() => p.polarismode==8);
const astroCaption = computed(() => {
  return (isAstroMode.value) ? '' : 'Change Polaris Mode to Astro.'
});

// ------------------- Lifecycle Events ---------------------

onMounted(async () => {

})

onUnmounted(() => {

})


// ------------------- Event Handlers ---------------------

async function onBleSelected(newVal:string) {
  await dev.bleSelectDevice(newVal)
}

async function onBleEnableWifi() {
  await dev.bleEnableWifi()
}

async function onPark() {
  console.log('Goto Park Position')
  await dev.alpacaPark()
  await dev.alpacaUnPark()
}

async function onCompass(newVal:number = 180.0) {
  console.log('Set Compass Alignment')
  await dev.setPolarisCompass(newVal)
}

async function onAlignment(az:number = 180.0, alt:number = 45.0) {
  console.log('Set Alignment Alignment')
  await dev.setPolarisAlignment(az, alt)
}


async function onModeUpdate(newVal:number) {
  console.log("Polaris Mode", newVal)
  await dev.setPolarisMode(newVal)
}

// ------------------- Alpaca Connection Helper Functions ---------------------
async function onAlpacaCheckboxToggle(checked:boolean) {
  if (checked && !dev.restAPIConnected) {
    await attemmptConnectToAlpaca()
  } else if (!checked && dev.restAPIConnected) {
    attemptDisconnectFromAlpaca()
  }
}


watch(() => dev.restAPIConnected, async (newVal) => {
  if (newVal) {
    await cfg.configFetch()     // ensure config store is refreshed after any connect
    $q.notify({
      message: 'Alpaca Driver successfuly connected.',
      type: 'positive', position: 'top', timeout: 3000,
      actions: [{ icon: 'mdi-close', color: 'white' }]
    })
  }
})

// connect when user checks the checkbox or presses enter on Host or Port field
async function attemmptConnectToAlpaca() {
  if (!dev.restAPIConnected) await dev.connectRestAPI()
}

// disconnect when user unchecks the checkbox
function attemptDisconnectFromAlpaca() {
  if (dev.restAPIConnected) dev.disconnectRestAPI()
}

// ------------------- Polaris Connection Helper Functions ---------------------

async function onPolarisCheckboxToggle(checked:boolean) {
  if (checked && !p.connected) {
    await attemmptConnectToPolaris()
  } else if (!checked && p.connected) {
    await attemptDisconnectFromPolaris()
  }
}


watch(()=>p.connected, (newVal)=>{
  if (newVal) {
      $q.notify({
        message: 'Benro Polaris successfuly connected.',
        type: 'positive', position: 'top', timeout: 3000,
        actions: [{ icon: 'mdi-close', color: 'white' }]
      })
  } 
})

async function attemmptConnectToPolaris() {
  console.log('Connecting to Polaris')
  if (!p.connected) await dev.connectPolaris()
}

// disconnect when user unchecks the checkbox
async function attemptDisconnectFromPolaris() {
  console.log('Disconnect Polaris')
  if (p.connected) await dev.disconnectPolaris()
}

// ------------------- Misc Helper Functions ---------------------

function onPolarisIPChange(v: string | number | boolean | null) {
  putdb({ polaris_ip_address: v })

}

function onPolarisPortChange(v: string | number | boolean | null) {
  putdb({ polaris_port: v })
}



const putdb = debounce((payload) => cfg.configUpdate(payload), 500) // slow put for input text

</script>

<style lang="scss">

.fixedWidth {
  width:140px;
}

</style>

