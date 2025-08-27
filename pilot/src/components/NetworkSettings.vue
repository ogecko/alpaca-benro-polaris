

<template>
    <q-card flat bordered class="q-pa-md">
        <!-- Network Services Heading -->
        <div class="text-h6">Alpaca Network Services</div>
        <div class="row">
            <div class="col text-caption text-grey-6 q-pb-md">
            The Alpaca Driver provides several network services for external aplications to use the Benro Polaris. Changes to Network Services require saving to take effect. 
            </div>
            <div class="q-gutter-md flex justify-end q-mr-md">
                <div class="col-auto q-gutter-sm flex justify-end items-center">
                    <q-btn  rounded  color="grey-9"  label="Save" 
                            @click="save" :disable="cfg.isSaving" :loading="cfg.isSaving" />
                </div>
            </div>
        </div>
        <!-- Rest API Services -->
        <div class="row q-col-gutter-sm no-wrap">
            <q-toggle class='col-8' v-bind="bindField('enable_restapi', 'Alpaca REST API Service')"/>
            <q-input class="col-4" v-bind="bindField('alpaca_restapi_port', 'Port')"
                type="number"  input-class="text-right" :style="{ visibility: cfg.enable_restapi ? 'visible' : 'hidden' }">
                <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
            </q-input>
        </div>
        <q-banner v-if="!cfg.enable_restapi" inline-actions rounded class="bg-warning">
            WARNING: The Alpaca REST API is required for Nina, Stellarium and Alpaca Pilot.
        </q-banner>
        <q-banner v-if="cfg.alpaca_restapi_port!=dev.alpacaPort" inline-actions rounded class="bg-warning">
            WARNING: The Alpaca REST API port will change. Please reconnect Alpaca Pilot when prompted. 
        </q-banner>
        <!-- Rest Discovery Services -->
        <div class="row q-col-gutter-sm no-wrap">
            <q-toggle class='col-8' v-bind="bindField('enable_discovery', 'Alpaca Discovery Service')"/>
            <q-input class="col-4" v-bind="bindField('alpaca_discovery_port', 'Port')"
                type="number" input-class="text-right" :style="{ visibility: cfg.enable_discovery ? 'visible' : 'hidden' }">
                <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
            </q-input>
        </div>
        <!-- Rest Pilot Web Services -->
        <div class="row q-col-gutter-sm no-wrap">
            <q-toggle class='col-8' v-bind="bindField('enable_pilot', 'Alpaca Pilot Webserver')"/>
            <q-input class="col-4" v-bind="bindField('alpaca_pilot_port', 'Port')"
                type="number" input-class="text-right" :style="{ visibility: cfg.enable_pilot ? 'visible' : 'hidden' }">
                <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
            </q-input>
        </div>
        <!-- Rest Pilot Socket Services -->
        <div class="row q-col-gutter-sm no-wrap">
            <q-toggle class='col-8' v-bind="bindField('enable_socket', 'Alpaca Pilot Socket IO')"/>
            <q-input class="col-4" v-bind="bindField('alpaca_socket_port', 'Port')"
                type="number" input-class="text-right" :style="{ visibility: cfg.enable_socket ? 'visible' : 'hidden' }">
                <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
            </q-input>
        </div>
        <!-- Rest SynSCAN Services -->
        <div class="row q-col-gutter-sm no-wrap">
            <q-toggle class='col-8' v-bind="bindField('enable_synscan', 'SynSCAN API Service')"/>
            <q-input class="col-4" v-bind="bindField('stellarium_synscan_port', 'Port')"
            type="number" input-class="text-right" :style="{ visibility: cfg.enable_synscan ? 'visible' : 'hidden' }">
            <template v-slot:prepend><q-icon name="mdi-network-outline"></q-icon></template>
            </q-input>
        </div>
    </q-card>

</template>

<script setup lang="ts">
// import axios from 'axios'
import { useQuasar } from 'quasar'
import { onMounted } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { debounce } from 'quasar'

const $q = useQuasar()
const dev = useDeviceStore()
const cfg = useConfigStore()

onMounted(async () => {
  const shouldFetch =
    dev.alpacaConnected &&
    dev.alpacaConnectedAt &&
    cfg.fetchedAt < dev.alpacaConnectedAt

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
  const isBoolean = type === 'boolean'
  return {
    label,
    ...(suffix ? { suffix } : {}),
    modelValue: isValid ? val : '',
    'onUpdate:modelValue': (v: string | number | boolean | null) => {
      if (v !== null && isValid) {
        // @ts-expect-error: dynamic key assignment
        cfg[key] = v
        const payload = { [key]: v }
        if (isBoolean) { put(payload) } else { putdb(payload) }
      }
    }
  }
}

// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store 
const putdb = debounce((payload) => cfg.configUpdate(payload), 500) // slow put for input text
const put = debounce((payload) => cfg.configUpdate(payload), 5)     // fast put for toggles

async function save() {
  const ok = await cfg.configSave()
  $q.notify({ message:`Configuration save ${ok?'successful':'unsucessful'}.`, type: ok?'positive':'negative', 
    position: 'top', timeout: 3000, actions: [{ icon: 'mdi-close', color: 'white' }] })
}

</script>

