

<template>
    <q-scroll-area class="panel-scroll">
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
    </q-scroll-area>


</template>

<script setup lang="ts">
// import axios from 'axios'
import { onMounted, computed } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';

const dev = useDeviceStore()
const cfg = useConfigStore()
// cfg properties {"cols":5, "rows":3, "hstep": 50, "vstep": 30, "order":2, "track":2, "anchor":3, "ref":0, "r1":180, "r2":30, "r3":10, "panel":2 }


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
  const shouldFetch =  dev.restAPIConnected && dev.restAPIConnectedAt &&cfg.fetchedAt < dev.restAPIConnectedAt
  if (shouldFetch) await cfg.configFetch()
})

async function slewToPanel(panel: number) {
  cfg.panel = panel
  await dev.alpacaPanoSlew(panel)
  console.log(`SlewToPanel: ${panel}` )
}


</script>

<style lang="css">

.panel-scroll {
height: 180px; 
max-width: 100%;
}

.panel-grid {
  display: grid;
  gap: 5px;
}

.panel-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 45px;
  min-width: 45px;
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

