

<template>
    <q-card flat bordered class="q-pa-md full-width">
        <div class="text-h6">Panorama/Mosaic Layout</div>
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
        <div class="text-h6 q-pt-lg">Recenter at Reference Point</div>
        <div class="row q-col-gutter-lg  items-center q-pt-lg">
            <q-select
              class="col-6 q-pt-none" label="Recenter Element" emit-value map-options
              v-model="cfg.r_align" @update:model-value="v => putdb({ r_align: v })"
              :options="panoRefAlignOptions"
            />
            <q-select
              class="col-6 q-pt-none" label="at Reference" emit-value map-options
              v-model="cfg.r_type" @update:model-value="v => putdb({ r_type: v })"
              :options="panoRefTypeOptions"
            />
        </div>
        <div v-if="cfg.r_type==0" class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h7 col-3">Reference</div>
            <q-input class="col-3" v-bind="bindField('r_az', 'Azimuth', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r_alt', 'Altitude', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r_roll', 'Roll Angle', '°')" type="number" input-class="text-right" dense/>
        </div>
        <div v-if="cfg.r_type==1" class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h7 col-3">Reference</div>
            <q-input class="col-3" v-bind="bindField('r_az', 'Right Ascension', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r_alt', 'Declination', '°')" type="number" input-class="text-right" dense/>
            <q-input class="col-3" v-bind="bindField('r_roll', 'Position Angle', '°')" type="number" input-class="text-right" dense/>
        </div>
        <div v-if="cfg.r_type==2" class="row q-col-gutter-lg q-pb-md items-center q-pt-sm">
            <div class="text-h7 col-6">Reference</div>
            <q-input class="col-6" v-bind="bindField('r_az', 'Orbital ID')" type="number" input-class="text-right" dense/>
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
            </div>
          </template>
        </div>
    </q-card>
</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
// import { useStatusStore } from 'src/stores/status';
import { debounce } from 'quasar'
// import { formatDegreesHr } from 'src/utils/scale'

const dev = useDeviceStore()
const cfg = useConfigStore()
// const p = useStatusStore()

const panoTrackingOptions = [
  { label: 'Foreground - Untracked', value: 0 },
  { label: 'Sky - Horizon-Locked', value: 1 },
  { label: 'Sky - Celestrial', value: 2 },
  { label: 'Sky - Orbital', value: 3 },
]

const panoOrderOptions = [
  { label: 'Row - Major', value: 0 },
  { label: 'Column - Major', value: 1 },
  { label: 'Serpentine', value: 2 },
]
const panoRefAlignOptions = [
  { label: 'Whole Mosaic', value: 0 },
  { label: 'Panel 1', value: 1 },
  { label: 'Panel 2', value: 2 },
]

const panoRefTypeOptions = [
  { label: 'Az/Alt Point', value: 0 },
  { label: 'RA/Dec Point', value: 1 },
  { label: 'Orbital Element', value: 2 },
  { label: 'Current Orientation', value: 3 },
]


const panelGrid = computed(() => {
  const rows = Number(cfg.rows ?? 0)
  const cols = Number(cfg.cols ?? 0)
  const order = Number(cfg.order ?? 0)

  let n = 1
  const grid: number[][] = Array.from({ length: rows }, () =>
    Array(cols).fill(0)
  )

  // const rowFromBottom = (r: number) => rows - 1 - r

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
  console.log(grid)
  return grid
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

function slewToPanel(panel: number) {
  cfg.panel = panel
  console.log('SlewToPanel', { panel })
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
</style>

