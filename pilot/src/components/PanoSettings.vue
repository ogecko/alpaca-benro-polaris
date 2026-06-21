<template>
  <q-card flat bordered class="q-pa-md full-width">
    <div class="row items-center justify-between">
      <div class="text-h6">Panorama Grid Layout</div>
      <q-btn-group>
      <q-btn label="Calc" icon="mdi-calculator" class="text-grey-6"  >
        <q-popup-proxy><PanoCalculator class="" /></q-popup-proxy>
      </q-btn>
      <q-btn label="Swap" icon="mdi-phone-rotate-landscape"  class="text-grey-6"  @click="swapStepSettings"/>
      <q-btn label="Copy" icon="mdi-content-copy"  class="text-grey-6"  @click="copyPanoSettings"/>
      </q-btn-group>
    </div>
    <div class="row q-col-gutter-lg items-center q-pt-sm">
      <q-input class="col-3" v-bind="bindField('cols', 'Columns')" type="number" input-class="text-right" />
      <q-input class="col-3" v-bind="bindField('rows', 'Rows')" type="number" input-class="text-right" />
                <div class="col-6">
                  <q-select
                    label="Panorama Preset" :model-value="cfg.pano_name" :options="panoOptions" 
                    use-input input-debounce="0" fill-input hide-selected
                    emit-value @update:model-value="onPanoSelect" @input-value="onPanoTyped" 
                  >
                    <template v-slot:append>
                      <q-icon name="mdi-content-save" class="cursor-pointer" color="grey-6" @click.stop="onPanoSave">
                        <q-tooltip>Save current panorama</q-tooltip>
                      </q-icon>
                    </template>
                    <template v-slot:option="scope">
                      <q-item v-bind="scope.itemProps">
                        <q-item-section>
                          <q-item-label>{{ scope.opt }}</q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <q-icon name="mdi-close-circle" color="grey-6" class="cursor-pointer" @click.stop="onPanoDelete(scope.opt)">
                            <q-tooltip>Delete this panorama</q-tooltip>
                          </q-icon>
                        </q-item-section>
                      </q-item>
                    </template>
                  </q-select>
                </div>
    </div>
    <div class="row q-col-gutter-lg items-center">
      <q-input class="col-3" v-bind="bindField('hstep', hStepLabel, '°')" type="number" input-class="text-right" />
      <q-input class="col-3" v-bind="bindField('vstep', vStepLabel, '°')" type="number" input-class="text-right" />
      <q-select class="col-3" v-bind="bindField('first', 'First Panel')" :options="panoStartingPositionOptions" emit-value map-options />
      <q-select class="col-3" v-bind="bindField('order', 'Panel Order')" :options="panoOrderOptions" emit-value map-options />
    </div>
    <div class="text-h6 q-pt-lg">Panorama Grid Positioning</div>
    <div class="row q-col-gutter-lg items-center">
      <q-select class="col-3" v-bind="bindField('anchor', 'Anchor Panel')" :options="panoRefAlignOptions" emit-value map-options />
      <q-select class="col-3" v-bind="bindField('ref', 'Reference Frame')" :options="panoRefTypeOptions" emit-value map-options />
      <q-select class="col-6" v-bind="bindField('track', 'Rotation and Tracking')" :options="panoTrackingOptions" emit-value map-options />
    </div>
    <div class="row q-col-gutter-lg q-pb-md items-center q-pt-md">
      <div class="text-caption text-grey-5 col-3">Anchor Position
        <q-btn outline label="Update" icon="mdi-crosshairs-gps" @click="put({ref_action:'update'}); triggerAnimation(['r1', 'r2', 'r3'])" no-wrap>
          <q-tooltip>Update Anchor Position with current mount orientation</q-tooltip>
        </q-btn>
      </div>
      <q-input class="col-3" v-bind="bindField('r1', r1Label, (cfg.ref==1)?'ʰ':'°')" type="number" step="0.01" input-class="text-right" />
      <q-input class="col-3" v-bind="bindField('r2', r2Label, '°')" type="number" input-class="text-right" />
      <q-input class="col-3" v-bind="bindField('r3', r3Label, '°')" type="number" input-class="text-right" />
    </div>
    <div class="text-h6 q-pt-lg">Panel Navigation</div>
    <div class="col text-caption text-grey-6 q-pb-none">
      Click a panel number to slew the mount to the corresponding panel position.
    </div>

    <PanoNavigation />

    <div class="col text-caption text-grey-6 q-pt-md">
      ✱ Indicates the next panel in the panorama sequence
    </div>
    <div class="col text-caption text-grey-6">
      ⚓ Which part of the mosaic to be placed at the reference position
    </div>
    <div class="row text-grey-6">
      <q-toggle v-bind="bindField('show_panels', 'Show Panel Navigation on Main Dashboard')" />
    </div>
  </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed, ref } from 'vue';
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { useQuasar, debounce } from 'quasar';
import PanoNavigation from 'src/components/PanoNavigation.vue';
import PanoCalculator from 'src/components/PanoCalculator.vue';

const $q = useQuasar()
const dev = useDeviceStore();
const cfg = useConfigStore();
// cfg properties {"cols":5, "rows":3, "hstep": 50, "vstep": 30, "first":0, "order":2, "track":2, "anchor":3, "ref":0, "r1":180, "r2":30, "r3":10, "panel":2 }

const panoTrackingOptions = [
  { label: 'Landscape - Untracked', value: 0 },
  { label: 'Sky - Horizon-Locked', value: 1 },
  { label: 'Sky - Celestrial', value: 2 },
  { label: 'Sky - Milky Way', value: 3 },
];

const panoOrderOptions = [
  { label: 'Row - Major', value: 0 },
  { label: 'Column - Major', value: 1 },
  { label: 'Serpentine', value: 2 },
];

const panoStartingPositionOptions = [
  { label: 'Top Left', value: 0 },
  { label: 'Top Right', value: 1 },
  { label: 'Bottom Left', value: 2 },
  { label: 'Bottom Right', value: 3 },
];

const panoRefTypeOptions = [
  { label: 'Topocentric', value: 0 },
  { label: 'Equatorial', value: 1 },
  { label: 'Galactic', value: 2 },
];

const panoRefAlignOptions = computed(() => {
  const panelCount = Number(cfg.rows ?? 1) * Number(cfg.cols ?? 3);
  const options = [{ label: 'Whole Mosaic', value: 0 }];
  for (let i = 1; i <= panelCount; i++) {
    options.push({ label: `Panel ${i}`, value: i });
  }
  return options;
});

const r1Label = computed(() => `${(cfg.ref==2)?'Galactic longitude': (cfg.ref==1)?'Right Ascension' :'Azimuth'}`)
const r2Label = computed(() => `${(cfg.ref==2)?'Galactic latitude': (cfg.ref==1)?'Declination'     :'Altitude'}`)
const r3Label = computed(() => `${(cfg.ref==2)?'Galactic PA':  (cfg.ref==1)?'Position Angle'  :'Roll Angle'}`)
const hStepLabel = computed(() => `${(cfg.ref==2)?'Galactic Lon Step':  (cfg.ref==1)?'Right Ascension Step'  :'Horizontal Step'}`)
const vStepLabel = computed(() => `${(cfg.ref==2)?'Galactic Lat Step':  (cfg.ref==1)?'Declination Step'  :'Vertical Step'}`)

function swapStepSettings() {
  const vstep = cfg.hstep
  const hstep = cfg.vstep
  const sensor_size = cfg.sensor_size.replace(/([\d.]+)(\s*[×xX]\s*)([\d.]+)/,'$3$2$1')

  put({hstep, vstep, sensor_size})
}

async function copyPanoSettings() {
  const payload = {
    cols: Number(cfg.cols),
    rows: Number(cfg.rows),
    hstep: Number(cfg.hstep),
    vstep: Number(cfg.vstep),
    first: Number(cfg.first),
    order: Number(cfg.order),
    track: Number(cfg.track),
    anchor: Number(cfg.anchor),
    ref: Number(cfg.ref),
    r1: Number(cfg.r1),
    r2: Number(cfg.r2),
    r3: Number(cfg.r3),
    panel: Number(cfg.panel),
  };
  const json = JSON.stringify(payload);
  try {
    await navigator.clipboard.writeText(json);
    console.log('Pano settings copied:', json);
  } catch (err) {
    console.error('Clipboard copy failed:', err);
  }
}


onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected && dev.restAPIConnectedAt && cfg.fetchedAt < dev.restAPIConnectedAt;
  if (shouldFetch) await cfg.configFetch();
});


// Derive the dropdown options from the pipe-separated pano_list
const panoOptions = computed<string[]>(() =>
  cfg.pano_list
    ? cfg.pano_list.split('|').filter(Boolean)
    : []
)
 
// User picked an existing entry from the dropdown → load it
function onPanoSelect(name: string | null) {
  if (!name) return
  put({ preset_name: name, preset_action: 'load_pano', })
  triggerAnimation(['cols', 'rows', 'hstep', 'vstep', 'first', 'order',
            'track', 'anchor', 'ref', 'r1', 'r2', 'r3',
            'panel', 'sensor_size', 'panel_overlap'])
}
 
// User is typing a new name (free-text) → just update pano_name, no action
function onPanoTyped(val: string) {
  cfg.pano_name = val
  putdb({ pano_name: val })
}
 
// User clicked the save icon → save current pano under current name
function onPanoSave() {
  const name = cfg.pano_name
  if (!name) return
  put({ preset_name: name, preset_action: 'save_pano' })
  $q.notify({
    message: `Panorama "${name}" saved.`,
    type: 'positive', position: 'top', timeout: 3000,
    actions: [{ icon: 'mdi-close', color: 'white' }],
  })
}
 
// User clicked the delete icon on a dropdown row
function onPanoDelete(name: string) {
  put({ preset_name: name, preset_action: 'delete_pano' })
  $q.notify({
    message: `Panorama "${name}" deleted.`,
    type: 'positive', position: 'top', timeout: 3000,
    actions: [{ icon: 'mdi-close', color: 'white' }],
  })
}





const taKeys = ref(new Set<string>()) // set of keys to animate
function triggerAnimation(keys: string[]) {
  keys.forEach(key => taKeys.value.add(key))
  setTimeout(() => {
    keys.forEach(key => taKeys.value.delete(key))
  }, 600)
}


function bindField(key: string, label: string, suffix?: string, decimals?: number) {
  /**
   * Creates a v-model binding object for a given config key.
   * Supports string, number, and boolean values. Updates cfg and persists changes via api.
   * Also applies a 'taflash' class if the key is flagged for animation.
   *
   * @param key - The config key to bind
   * @param label - The label of the field
   * @param suffix - Optional suffix to display in the input
   * @param decimals - Optional number of decimal places to display
   * @returns A binding object compatible with Quasar input components
   */
  // @ts-expect-error: dynamic key access on cfg
  const val = cfg[key];
  const type = typeof val;
  const isValid = ['string', 'number', 'boolean'].includes(type);
  const isBoolean = type === 'boolean'
  const dp = decimals ?? (suffix === '°' || suffix === 'ʰ' ? 6 : undefined)
  const displayVal = (typeof val === 'number' && dp !== undefined)
    ? parseFloat(val.toFixed(dp))   // toFixed then parseFloat strips trailing zeros
    : (isValid ? val : '')

  return {
    label,
    ...(suffix ? { suffix } : {}),
    class: { taflash: taKeys.value.has(key) },
    modelValue: displayVal,
    'onUpdate:modelValue': (v: string | number | boolean | null) => {
      if (v !== null && isValid) {
        // @ts-expect-error: dynamic key assignment
        cfg[key] = v;
        const payload = { [key]: v };
        if (isBoolean) { put(payload) } else { putdb(payload) }

      }
    },
  };
}

// debounced payload key/values (a) sent to Alpaca Server and (b) patched into cfg store
const put = debounce((payload) => cfg.configUpdate(payload), 5); // fast put for toggles
const putdb = debounce((payload) => cfg.configUpdate(payload), 500); // slow put for input text
</script>

<style lang="scss">
.taflash {
  animation: flash 0.6s;
}
</style>