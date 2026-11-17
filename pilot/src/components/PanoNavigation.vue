

<template>
    <q-scroll-area class="panel-scroll" :style="{height: gridHeight}">
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
  const total = rows * cols
  if (rows <= 0 || cols <= 0)
    return []

  const first = Number(cfg.first ?? 0)
  const order = Number(cfg.order ?? 0)
  const grid: number[][] = Array.from({ length: rows }, () =>
    Array(cols).fill(0)
  )

  // Critical function MUST MATCH panel_to_rc() in driver/polaris.py
  function panelToRC(panel: number): [number, number] {
    // Panel 0 means center of grid
      if (panel === 0) {
        return [ (rows - 1) / 2, (cols - 1) / 2 ]
      }
    const i = panel - 1
    let r = 0
    let c = 0
    // Apply Panel Order adjustment
    if (order === 0) {          // row-major
      r = Math.floor(i / cols)
      c = i % cols
    } else if (order === 1) {   // column-major
      c = Math.floor(i / rows)
      r = i % rows
    } else {                    // serpentine
      r = Math.floor(i / cols)
      c = i % cols
      if (r % 2 === 1)
        c = cols - 1 - c
    }
    // Apply First Panel adjustment
    if (first === 0) {           // Top Left (mirrow row axis)
      r = rows - 1 - r
    } else if (first === 1) {     // Top Right (mirror row and col axis)
      r = rows - 1 - r
      c = cols - 1 - c
    }
    else if (first === 3) {       // Bottom Right (mirror col axis)
      c = cols - 1 - c
    }
    return [r, c]
  }

  // create the grid
  for (let p = 1; p <= total; p++) {
    const [r, c] = panelToRC(p)
    const row = grid[r]
    if (!row) continue
    row[c] = p
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

const gridHeight = computed(() => {
  const rows = Number(cfg.rows ?? 0)
  const rowsClamped = Math.min(Math.max(rows, 1), 5)
  // gridHeight = (35 cellHeight + 5 gap) * rows + 18 scrollbar space
  return `${(35 + 5) * rowsClamped + 18}px`
})


onMounted(async () => {
})

async function slewToPanel(panel: number) {
  cfg.panel = panel
  await dev.alpacaPanoSlew(panel)
  console.log(`SlewToPanel: ${panel}` )
}


</script>

<style lang="css">

.panel-scroll {
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
  height: 35px;
  min-width: 35px;
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

