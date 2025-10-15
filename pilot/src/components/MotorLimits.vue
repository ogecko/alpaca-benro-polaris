

<template>
    <q-card flat bordered class="q-pa-md full-width">
        <!-- Logging Settings Heading -->
        <div class="text-h6">Motor Angle Limts</div>
        <div class="row">
            <div class="col text-caption text-grey-6 q-pb-md">
            To prevent cable windup, set minimum and maximum limits for each axis. Control axes directly or Park Polaris.             
            </div>
            <div class="col-auto q-gutter-sm flex justify-end items-center">
              <q-btn outline icon="mdi-parking" color="grey-5" label="Park"  @click="onPark"/>
            </div>
        </div>
        <!-- Benro Polaris Image -->
        <div class="row justify-center">
          <div class="relative-position" style="height:300px; width:300px">
            <q-img src="../assets/abp-v2-motor-limits-b.png" fit="scale-down" @contextmenu.prevent>
            </q-img>
            <MoveButton activeColor="positive" label="M3+" :opacity="1.0" size="md" color="white" icon=""  dense @push="onM3Plus" class="absolute" style="top:2%; left:47%"/>
            <MoveButton activeColor="positive" label="M3-" :opacity="1.0" size="md" color="white" icon=""  dense  @push="onM3Minus" class="absolute" style="top:2%; left:77%"/>

            <MoveButton activeColor="positive" label="M2+" :opacity="1.0" size="md" color="white" icon=""  dense  @push="onM2Plus" class="absolute" style="top:43%; left:38%"/>
            <MoveButton activeColor="positive" label="M2-" :opacity="1.0" size="md" color="white" icon=""  dense  @push="onM2Minus" class="absolute" style="top:66%; left:25%"/>

            <MoveButton activeColor="positive" label="M1+" :opacity="1.0" size="md" color="white" icon=""  dense   @push="onM1Plus" class="absolute" style="top:79%; left:11%"/>
            <MoveButton activeColor="positive" label="M1-" :opacity="1.0" size="md" color="white" icon=""  dense  @push="onM1Minus" class="absolute" style="top:91%; left:30%"/>

          </div>
        </div>
        <!-- Motor Limits -->
        <div class="row q-col-gutter-lg items-center q-pt-md">
              <div  class="text-h6">M3 <span v-if="$q.screen.gt.xs">Axis</span></div>
              <q-input class="col-3" v-bind="bindField('z3_min_limit','Min (-)', '°')" type="number" input-class="text-right" 
                       dense :bg-color="p.omegamin[2] === 0 ? 'negative' : undefined" />
              <q-input dense class="col-3" readonly label="Current" v-bind="z3curr" type="text" input-class="text-right"/>
              <q-input class="col-3" v-bind="bindField('z3_max_limit','Max (+)', '°')" type="number" input-class="text-right"
                       dense :bg-color="p.omegamax[2] === 0 ? 'negative' : undefined" />
        </div>
        <div class="row q-col-gutter-lg  items-center q-pt-sm">
            <div class="text-h6">M2 <span v-if="$q.screen.gt.xs">Axis</span></div>
            <q-input class="col-3" v-bind="bindField('z2_min_limit', 'Min (-)', '°')" type="number" input-class="text-right"
                      dense :bg-color="p.omegamin[1] === 0 ? 'negative' : undefined" />
            <q-input dense class="col-3" readonly label="Current" v-bind="z2curr" type="text" input-class="text-right"/>
            <q-input class="col-3" v-bind="bindField('z2_max_limit','Max (+)', '°')" type="number" input-class="text-right"
                      dense :bg-color="p.omegamax[1] === 0 ? 'negative' : undefined" />
        </div>
        <div class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h6">M1 <span v-if="$q.screen.gt.xs">Axis</span></div>
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
import MoveButton from 'src/components/MoveButton.vue'

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


async function onPark() {
  console.log('Goto Park Position')
  await dev.alpacaPark()
  await dev.alpacaUnPark()
}

async function onM1Plus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":0,"rate":${payload.isPressed ? 5 : 0}}`)
}
async function onM1Minus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":0,"rate":${payload.isPressed ? -5 : 0}}`)
}
async function onM2Plus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":1,"rate":${payload.isPressed ? 5 : 0}}`)
}
async function onM2Minus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":1,"rate":${payload.isPressed ? -5 : 0}}`)
}
async function onM3Plus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":2,"rate":${payload.isPressed ? 5 : 0}}`)
}
async function onM3Minus(payload: { isPressed: boolean }) {
    await dev.apiAction('Polaris:MoveMotor', `{"axis":2,"rate":${payload.isPressed ? -5 : 0}}`)
}


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
