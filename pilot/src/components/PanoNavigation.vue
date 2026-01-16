

<template>
  <svg ref="svgRef" class="pano-svg q-mt-sm"></svg>
</template>

<script setup lang="ts">
import { onMounted, computed, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useConfigStore } from 'stores/config'
import { useDeviceStore } from 'src/stores/device'

const dev = useDeviceStore()
const cfg = useConfigStore()

const svgRef = ref<SVGSVGElement | null>(null)

// --- layout constants ---
const CELL = 48
const GAP = 8

const panelGrid = computed<number[][]>(() => {
  const rows = Number(cfg.rows ?? 0)
  const cols = Number(cfg.cols ?? 0)
  const order = Number(cfg.order ?? 0)

  let n = 1

  // initialize grid
  const grid: number[][] = []
  for (let r = 0; r < rows; r++) {
    grid.push(new Array(cols).fill(0))
  }

  if (order === 0) {
    // Row-major, bottom-up
    for (let r = 0; r < rows; r++) {
      const row = grid[r] as number[]  // <-- TS-safe assertion
      for (let c = 0; c < cols; c++) {
        row[c] = n++
      }
    }
  } else if (order === 1) {
    // Column-major
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const row = grid[r] as number[]  // <-- TS-safe assertion
        row[c] = n++
      }
    }
  } else {
    // Serpentine
    for (let r = 0; r < rows; r++) {
      const row = grid[r] as number[]  // <-- TS-safe assertion
      const cs = r % 2 ? [...Array(cols).keys()].reverse() : [...Array(cols).keys()]
      for (const c of cs) {
        row[c] = n++
      }
    }
  }

  return grid
})

const nextPanel = computed(() => {
  const total = (cfg.rows ?? 0) * (cfg.cols ?? 0)
  const current = Number(cfg.panel ?? 0)
  if (!current || current >= total) return 1
  return current + 1
})

interface PanelCell {
  row: number
  col: number
  panel: number
}

// --- flatten grid for D3 ---
const cells = computed(() => {
  const rows = panelGrid.value.length
  const cols = panelGrid.value[0]?.length ?? 0

const out: PanelCell[] = []
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++)
      out.push({
        row: r,
        col: c,
        panel: panelGrid.value[r]![c]!
      })

  return out
})

// --- draw / redraw ---
function render() {
  if (!svgRef.value) return

  const rows = cfg.rows ?? 0
  const cols = cfg.cols ?? 0

  const width = cols * (CELL + GAP)
  const height = rows * (CELL + GAP)

  const svg = d3.select(svgRef.value)
    .attr('width', width)
    .attr('height', height)

  // one group for everything
  let g = svg.select<SVGGElement>('g.grid')
  if (g.empty()) {
    g = svg.append('g').attr('class', 'grid')
  }

  // --- panels ---
  const panels = g.selectAll<SVGRectElement, PanelCell>('rect.panel')
    .data(cells.value, d => d.panel)

  panels.enter()
    .append('rect')
    .attr('class', 'panel')
    .merge(panels)
    .attr('x', d => d.col * (CELL + GAP))
    .attr('y', d => (rows - 1 - d.row) * (CELL + GAP)) // bottom-up
    .attr('width', CELL)
    .attr('height', CELL)
    .classed('active', d => d.panel === cfg.panel)
    .on('click', (_, d) => { void slewToPanel(d.panel) })
    
  panels.exit().remove()

  // --- labels ---
  const labels = g.selectAll<SVGTextElement, PanelCell>('text.label')
    .data(cells.value, d => d.panel)

  labels.enter()
    .append('text')
    .attr('class', 'label')
    .merge(labels)
    .attr('x', d => d.col * (CELL + GAP) + CELL / 2)
    .attr('y', d => (rows - 1 - d.row) * (CELL + GAP) + CELL / 2 + 4)
    .text(d => {
      if (d.panel === cfg.anchor) return `${d.panel} ⚓`
      if (d.panel === nextPanel.value) return `${d.panel} ✱`
      return d.panel
    })

  labels.exit().remove()
}

// --- lifecycle ---
onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) await cfg.configFetch()
  render()
})

// redraw when relevant state changes
watch(
  () => [cfg.rows, cfg.cols, cfg.order, cfg.panel, cfg.anchor],
  render,
  { deep: true }
)

async function slewToPanel(panel: number) {
  cfg.panel = panel
  await dev.alpacaPanoSlew(panel)
  console.log(`SlewToPanel: ${panel}`)
}
</script>

<style lang="css">
.pano-svg {
  user-select: none;
  
}

.panel {
  rx: 6;
  ry: 6;
  fill: #474747;
  stroke: #8d8d8d;
  cursor: pointer;
}

.panel:hover {
  fill: var(--q-color-primary-1);
}

.panel.active {
  fill: #1976d2;
  stroke-width: 2;
}

.label {
  fill: white;
  font-size: 14px;
  font-weight: 500;
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
}</style>

