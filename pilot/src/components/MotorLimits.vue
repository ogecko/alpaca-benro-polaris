

<template>
    <q-card flat bordered class="q-pa-md full-width">
        <!-- Logging Settings Heading -->
        <div class="text-h6">Motor Angle Limts</div>
        <div class="row">
            <div class="col text-caption text-grey-6 q-pb-md">
            To prevent windup, set minimum and maximum limits for each axis.              
            </div>
            <div class="col-auto q-gutter-sm flex justify-end">
              <q-btn class='col' label="Defaults"/>
            </div>
        </div>
        <q-img src="../assets/abp-v2-motor-limits.png" fit="scale-down" position="50% 50%" style="height:300px"></q-img>
        <!-- Motor Limits -->
        <div class="row q-col-gutter-lg items-center q-pt-md">
              <div  class="text-h6">Z3 <span v-if="$q.screen.gt.xs">Axis</span></div>
              <q-input class="col-3" v-bind="bindField('z3_min_limit','Min (-)', '°')" type="number" input-class="text-right" 
                       dense :bg-color="p.omegamin[2] === 0 ? 'negative' : undefined" />
              <q-input dense class="col-3" readonly label="Current" v-bind="z3curr" type="text" input-class="text-right"/>
              <q-input class="col-3" v-bind="bindField('z3_max_limit','Max (+)', '°')" type="number" input-class="text-right"
                       dense :bg-color="p.omegamax[2] === 0 ? 'negative' : undefined" />
        </div>
        <div class="row q-col-gutter-lg  items-center q-pt-sm">
            <div class="text-h6">Z2 <span v-if="$q.screen.gt.xs">Axis</span></div>
            <q-input class="col-3" v-bind="bindField('z2_min_limit', 'Min (-)', '°')" type="number" input-class="text-right"
                      dense :bg-color="p.omegamin[1] === 0 ? 'negative' : undefined" />
            <q-input dense class="col-3" readonly label="Current" v-bind="z2curr" type="text" input-class="text-right"/>
            <q-input class="col-3" v-bind="bindField('z2_max_limit','Max (+)', '°')" type="number" input-class="text-right"
                      dense :bg-color="p.omegamax[1] === 0 ? 'negative' : undefined" />
        </div>
        <div class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h6">Z1 <span v-if="$q.screen.gt.xs">Axis</span></div>
            <q-input class="col-3" v-bind="bindField('z1_min_limit', 'Min (-)', '°')" type="number" input-class="text-right"
                     dense  :bg-color="p.omegamin[0] === 0 ? 'negative' : undefined" />
            <q-input dense class="col-3" readonly label="Current" v-bind="z1curr" type="text" input-class="text-right"/>
            <q-input class="col-3" v-bind="bindField('z1_max_limit','Max (+)', '°')" type="number" input-class="text-right"
                     dense  :bg-color="p.omegamax[0] === 0 ? 'negative' : undefined" />
        </div>

    </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useStatusStore } from 'src/stores/status';
import { debounce } from 'quasar'
import { formatDegreesHr } from 'src/utils/scale'

const dev = useDeviceStore()
const cfg = useConfigStore()
const p = useStatusStore()


const z3curr = computed(() => ({ modelValue: formatDegreesHr(p.zetameas[2]??0,"deg",1) }));
const z2curr = computed(() => ({ modelValue: formatDegreesHr(p.zetameas[1]??0,"deg",1) }));
const z1curr = computed(() => ({ modelValue: formatDegreesHr(p.zetameas[0]??0,"deg",1) }));


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
