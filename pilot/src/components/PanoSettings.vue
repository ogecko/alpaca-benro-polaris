

<template>
    <q-card flat bordered class="q-pa-md full-width">
        <div class="text-h6">Panorama Layout and Behaviour</div>
        <div class="row q-col-gutter-lg  items-center q-pt-sm">
            <q-input class="col-3" v-bind="bindField('cols', 'Columns')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('rows', 'Rows')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('hstep', 'Horz Step', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('vstep', 'Vert Step', '°')" type="number" input-class="text-right" dense/>
        </div>
        <div class="row q-col-gutter-lg  items-center q-pt-lg">
            <q-select
              class="col-6 q-pt-none" label="Panel Order" emit-value map-options
              v-model="cfg.order" @update:model-value="v => putdb({ order: v })"
              :options="panoOrderOptions"
            />
            <q-select
              class="col-6 q-pt-none" label="Orientation and Tracking" emit-value map-options
              v-model="cfg.track" @update:model-value="v => putdb({ track: v })"
              :options="panoTrackingOptions"
            />
        </div>
        <div class="text-h6 q-pt-lg">Panorama Positioning</div>
        <div class="row q-col-gutter-lg  items-center q-pt-lg">
            <q-select
              class="col-6 q-pt-none" label="Anchor Panel" emit-value map-options
              v-model="cfg.anchor" @update:model-value="v => putdb({ anchor: v })"
              :options="panoRefAlignOptions"
            />
            <q-select
              class="col-6 q-pt-none" label="to Reference Position" emit-value map-options
              v-model="cfg.ref" @update:model-value="v => putdb({ ref: v })"
              :options="panoRefTypeOptions"
            />
        </div>
        <div v-if="cfg.ref==0" class="row q-col-gutter-lg q-pb-md items-center q-pt-md">
            <div class="text-h7 col-3">Reference Position</div>
            <q-input class="col-3" v-bind="bindField('r1', 'Azimuth', '°')" type="number" step="0.01" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r2', 'Altitude', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r3', 'Roll Angle', '°')" type="number" input-class="text-right" dense/>
        </div>
        <div v-if="cfg.ref==1" class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h7 col-3">Reference</div>
            <q-input class="col-3" v-bind="bindField('r1', 'Right Ascension', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r2', 'Declination', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r3', 'Position Angle', '°')" type="number" input-class="text-right" dense/>
        </div>
        <div v-if="cfg.ref==2" class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h7 col-6">Reference</div>
            <q-input class="col-6" v-bind="bindField('r1', 'Orbital ID')" type="number" input-class="text-right" dense/>
        </div>
        <div class="text-h6 q-pt-lg">Panel Navigation</div>
        <div class="col text-caption text-grey-6 q-pb-none">
          Click a panel number to slew the mount to the corresponding panel position.
        </div>

        <div class="panel-grid q-mt-sm" :style="{ gridTemplateColumns: `repeat(${cfg.cols}, 1fr)` }">
          <template v-for="(row, r) in [...panelGrid].reverse()" :key="`row-${r}`">
            <div
              v-for="panel in row"
              :key="panel"
              class="panel-cell" :class="{ active: panel === cfg.panel }"
              @click="slewToPanel(panel)"
            >
              {{ panel }}
              <span v-if="panel === nextPanel" class="next-marker" title="Next panel in sequence">✱</span>
              <span v-if="panel === cfg.anchor" class="next-marker" title="Anchor panel to Reference Position">⚓</span>
            </div>
          </template>
        </div>
        <div class="col text-caption text-grey-6 q-pt-md">
         ✱ Indicates the next panel in the panorama sequence
        </div>
        <div class="col text-caption text-grey-6 ">
        ⚓ Which part of the mosaic to be placed at the reference position
        </div>
      </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()
// cfg properties {"cols":5, "rows":3, "hstep": 50, "vstep": 30, "order":2, "track":2, "anchor":3, "ref":0, "r1":180, "r2":30, "r3":10, "panel":2 }

const panoTrackingOptions = [
  { label: 'Landscape - Untracked', value: 0 },
  { label: 'Sky - Horizon-Locked', value: 1 },
  { label: 'Sky - Celestrial', value: 2 },
  // { label: 'Sky - Orbital', value: 3 },
]

const panoOrderOptions = [
  { label: 'Row - Major', value: 0 },
  { label: 'Column - Major', value: 1 },
  { label: 'Serpentine', value: 2 },
]


const panoRefTypeOptions = [
  { label: 'Az/Alt Point', value: 0 },
  // { label: 'RA/Dec Point', value: 1 },
  // { label: 'Orbital Element', value: 2 },
  { label: 'Current Orientation', value: 3 },
]


const panoRefAlignOptions = computed(() => {
  const panelCount =   Number(cfg.rows ?? 1) * Number(cfg.cols ?? 3)
  const options = [{ label: 'Whole Mosaic', value: 0 }];
  for (let i = 1; i <= panelCount; i++) {
    options.push({ label: `Panel ${i}`, value: i });
  }
  return options;
});

const panelGrid = computed(() => {
  const rows = Number(cfg.rows ?? 0)
  const cols = Number(cfg.cols ?? 0)
  const order = Number(cfg.order ?? 0)

  let n = 1
  const grid: number[][] = Array.from({ length: rows }, () =>
    Array(cols).fill(0)
  )

  // grid Layout: 
  // Row 0 = bottom Row (we reverse it in the HTML template to display it correctly)
  // Column 0 = left Column

  if (order === 0) {
    // Row-major, bottom-up
    for (let r = 0; r < rows; r++) {
      const row = grid[r]
      if (!row) continue
      for (let c = 0; c < cols; c++) row[c] = n++
    }
  } else if (order === 1) {
    // Column-major, bottom-up
    for (let c = 0; c < cols; c++)
      for (let r = 0; r < rows; r++) {
        const row = grid[r]
        if (row) row[c] = n++
      }
  } else {
    // Serpentine, bottom-up
    for (let r = 0; r < rows; r++) {
      const row = grid[r]
      if (!row) continue
      const cs = r % 2
        ? [...Array(cols).keys()].reverse()
        : [...Array(cols).keys()]
      for (const c of cs) row[c] = n++
    }
  }
  return grid
})

const nextPanel = computed(() => {
  const rows = Number(cfg.rows ?? 0)
  const cols = Number(cfg.cols ?? 0)
  const total = rows * cols
  const current = Number(cfg.panel ?? 0)
  if (!current || current >= total) return 1
  return current + 1
})

onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) {
    await cfg.configFetch()
  }
})

async function slewToPanel(panel: number) {
  cfg.panel = panel
  await dev.alpacaPanoSlew(panel)
  console.log(`SlewToPanel: ${panel}` )
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
const putdb = debounce((payload) => cfg.configUpdate(payload), 500) // slow put for input text


</script>

<style lang="css">
  .panel-grid {
  display: grid;
  gap: 8px;
}

.panel-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  cursor: pointer;
  font-weight: 500;
  border-radius: 6px;
  border: 1px solid #8d8d8d; /* grey-4 equivalent */
  background: #474747;

}

.panel-cell:hover {
  background: var(--q-color-primary-1);
}

.panel-cell.active {
  background: #1976d2;      /* Quasar primary */
  color: white;
  font-weight: 600;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.5);
}

.next-marker {
  vertical-align: super;
  margin-left: 2px;
  font-weight: 600;
}
</style>

