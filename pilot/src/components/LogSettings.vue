

<template>
    <q-card flat bordered class="q-pa-md">
        <!-- Logging Settings Heading -->
        <div class="text-h6">Protocol Log Settings</div>
        <div class="row">
            <div class="col-12 text-caption text-grey-6 q-pb-md">
            Select which messages to log, such as those from Alpaca clients (NINA, CCDciel, Pilot), 
            SynScan apps (Stellarium), and the messages sent to the Benro Polaris.              
            </div>
        </div>
        <!-- Logging Level -->
        <div class="row q-mb-md">
            <q-select
            class="col-12 q-pb-md" 
            filled
            v-bind="bindField('log_level', 'Log Detail and Verbosity Level')"
            :options="[
                { label: 'DEBUG – Detailed diagnostic logs', value: 'DEBUG' },
                { label: 'INFO – Default routine logging information', value: 'INFO' },
                { label: 'WARNING – Only log unexpected issues and above', value: 'WARNING' },
                { label: 'ERROR – Only log serious functional problems', value: 'ERROR' },
                { label: 'CRITICAL – Only log fatal system errors', value: 'CRITICAL' }
            ]"
            emit-value
            map-options/>
        </div>
        <!-- Logging Flags -->
        <div class="q-gutter-y-sm">
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_alpaca_protocol', 'Log Alpaca Protocol')"/>
            <q-toggle class='col-6' v-bind="bindField('log_alpaca_polling', 'Log Alpaca Polling')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_alpaca_discovery', 'Log Alpaca Discovery')"/>
            <q-toggle class='col-6' v-bind="bindField('log_alpaca_actions', 'Log Action Invokation')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_rotator_protocol', 'Log Rotator Protocol')"/>
            <q-toggle class='col-6' v-bind="bindField('log_pulse_guiding', 'Log Pulse Guiding')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_synscan_protocol', 'Log SynSCAN Protocol')"/>
            <q-toggle class='col-6' v-bind="bindField('log_synscan_polling', 'Log SynSCAN Polling')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_polaris_protocol', 'Log Benro Polaris Protocol')"/>
            <q-toggle class='col-6' v-bind="bindField('log_polaris_polling', 'Log Benro Polaris Polling')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_polaris_ble', 'Log Bluetooth Low Energy')"/>
            <q-toggle class='col-6' v-bind="bindField('log_quest_model', 'Log Multi-Point Sync')"/>
            </div>
            <div class="row">
            <q-toggle class='col-6' v-bind="bindField('log_orbital_queries', 'Log Orbital Queries')"/>
            </div>
        </div>
    </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()

onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) {
    await cfg.configFetch()
  }
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
  return {
    label,
    ...(suffix ? { suffix } : {}),
    modelValue: isValid ? val : '',
    'onUpdate:modelValue': (v: string | number | boolean | null) => {
      if (v !== null && isValid) {
        // @ts-expect-error: dynamic key assignment
        cfg[key] = v
        const payload = { [key]: v }
        put(payload)
      }
    }
  }
}


// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store 
const put = debounce((payload) => cfg.configUpdate(payload), 5)     // fast put for toggles


</script>
